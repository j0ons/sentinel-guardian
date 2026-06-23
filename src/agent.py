"""
agent.py — Sentinel's long-horizon decision loop.

For each incoming Event, the agent:
  1. assembles WORKING MEMORY into the prompt — the current baseline, known-normal
     entities, recent event log, and (the win condition) as much operational history as
     fits, exploiting qwen3.7-max's 1M context rather than top-k retrieval;
  2. asks qwen3.7-max to choose ONE tool (mark_normal / alert_user / actuate / query_memory);
  3. executes it, records the decision, and updates entity tracking.

This is "perceive -> recall -> reason -> act -> record". Runs today against the STUB
client; flips to real qwen3.7-max reasoning the moment QWEN_API_KEY is set.
"""

from __future__ import annotations

import os
import time

from memory import Event, Memory
from qwen_client import MODEL_FAST, chat, is_live
from safety import event_is_threat_signature
from tools import TOOL_SCHEMAS, execute

# Terminal actions end the investigation; everything else is an investigative tool.
TERMINAL_ACTIONS = ("mark_normal", "alert_user", "actuate")
# How many investigative tool calls the agent may make before it must decide (long-horizon
# autonomy, bounded so a single event can't run away in cost/latency).
MAX_INVESTIGATION_STEPS = int(os.getenv("SENTINEL_MAX_INVESTIGATION_STEPS", "4"))

SYSTEM_PROMPT = """You are Sentinel, an autonomous security guardian running on a single host.
Your job: for each observed event, decide if it is NORMAL for this host or an ANOMALY.

You learn what is normal from the baseline and known-normal entities given to you. Be
calibrated: most events on a working machine are routine — do not cry wolf. Reserve alerts
for genuinely unusual activity, and reserve `actuate` for high-confidence malicious behavior
that contradicts the baseline (e.g. an unknown process opening an unexpected listening port
or connecting to a suspicious endpoint).

You are an AGENT, not a one-shot classifier. When an event is ambiguous or suspicious,
INVESTIGATE before deciding — you have tools:
  - check_entity(entity): has this been seen before on this host, how often, is it trusted?
  - correlate_recent(seconds): what else happened around this event? Attacks rarely happen
    alone — look for a CHAIN (e.g. a new/unknown process, THEN a new listening port, THEN an
    outbound connection to an external host = a likely intrusion kill-chain, even if no single
    step is a known-bad signature). Reason about NOVEL attack patterns, not just known ports.
  - query_memory(query): semantic search of past events.
Gather evidence across a few steps, then take ONE terminal action. RULE: for any unknown or
external connection, an unknown new process, or a new listening port, you MUST call
correlate_recent FIRST to check for a surrounding attack chain before deciding — do not
mark_normal or alert on these without correlating. If correlate_recent reveals a chain
(unknown process + new listener + external egress in the same window), that is an intrusion —
actuate.

NON-NEGOTIABLE SAFETY FLOOR — a permissive baseline NEVER overrides these. Even if the host
looks quiet and most activity is normal, ALWAYS treat the following as a threat and `actuate`
(or at minimum `alert_user` with severity=medium), regardless of what the baseline says:
  - outbound connections to ephemeral/uncommon high ports (e.g. 4444, 1337, 31337) to an
    unknown or external destination — classic reverse-shell / C2 signature;
  - a connection to a known-bad destination (Tor exits, flagged IPs);
  - an unknown process opening a listener or spawning a shell with network egress.
A baseline describes routine BENIGN activity; it is not a license to ignore attack
signatures. When the signature above is present, the threat verdict wins — full stop.

Terminal actions: mark_normal (fits the learned baseline, no anomaly, investigation clean),
alert_user (unusual, worth a human), actuate (high-confidence malicious — known signature OR
a correlated attack chain you uncovered). Drive false alarms toward zero while NEVER missing a
real threat — missing a threat is far worse than a false alarm."""


# qwen3.7-max has a 1M-token context window. Sentinel uses it as living working memory, but
# context size trades off against latency, so we budget it deliberately per use:
#   * PER-DECISION: a modest recent window keeps each event's verdict fast (sub-few-seconds),
#     which the edge loop and a live demo need. The baseline already distils older history.
#   * CONSOLIDATION ("dreaming"): runs once/night where latency is irrelevant, so it exploits
#     the FULL history in 1M context — that's where the big-context claim genuinely pays off.
_CHARS_PER_TOKEN = 4
DECISION_TOKEN_BUDGET = int(os.getenv("SENTINEL_DECISION_TOKENS", "8000"))     # fast per-event
MAX_HISTORY_EVENTS = int(os.getenv("SENTINEL_MAX_HISTORY_EVENTS", "5000"))     # hard upper bound
# (The large full-history budget lives in consolidate.py, where the nightly dream actually
#  uses it — per-event decisions stay small for latency. See consolidate.CONTEXT_TOKEN_BUDGET.)


class SentinelAgent:
    def __init__(self, memory: Memory, host: str = "edge-0"):
        self.memory = memory
        self.host = host
        self.last_context_stats: dict = {}     # exposed for the dashboard/demo

    def _working_memory_block(self, max_events: int = MAX_HISTORY_EVENTS,
                              token_budget: int = DECISION_TOKEN_BUDGET) -> str:
        """Assemble the host's living memory. `token_budget` caps how much history is included:
        small for fast per-event decisions; the nightly dream uses a much larger budget.

        Records how much it used in `last_context_stats` so the demo can show context usage."""
        baseline = self.memory.current_baseline(self.host)
        version = self.memory.baseline_version(self.host)
        normals = self.memory.known_normal_entities()
        recent = self.memory.recent_events(limit=max_events)

        # Drop oldest events first if we'd blow the token budget (keep the most recent history).
        char_budget = token_budget * _CHARS_PER_TOKEN
        kept: list = []
        used = 0
        for e in reversed(recent):                 # newest first
            line_len = len(e.to_text()) + 12       # +timestamp prefix
            if used + line_len > char_budget:
                break
            kept.append(e)
            used += line_len
        kept.reverse()                             # back to chronological order
        self.last_context_stats = {
            "events_in_context": len(kept),
            "events_available": self.memory.event_count(),
            "approx_tokens": used // _CHARS_PER_TOKEN,
            "token_budget": token_budget,
        }
        recent = kept

        lines = [
            f"=== HOST: {self.host} ===",
            f"=== LEARNED BASELINE (v{version}) — what is normal here ===",
            baseline,
            "",
            f"=== KNOWN-NORMAL ENTITIES ({len(normals)}) ===",
            ", ".join(normals) if normals else "(none yet)",
            "",
            f"=== RECENT OPERATIONAL HISTORY ({len(recent)} events) ===",
        ]
        lines += [f"  {time.strftime('%H:%M:%S', time.localtime(e.ts))}  {e.to_text()}"
                  for e in recent]
        return "\n".join(lines)

    def _flash_triage(self, ev: Event, entity: tuple[str, str] | None) -> bool:
        """Cheap qwen3.6-flash pre-filter: is this event OBVIOUSLY routine for this host?

        Cost-routed edge-cloud orchestration: most events on a working host are mundane. We
        spend the expensive qwen3.7-max reasoning (with full 1M-context history) only on events
        flash can't confidently clear. Returns True only for a high-confidence "clearly normal"
        — and NEVER for anything carrying a threat signature, so the safety floor is untouched."""
        if entity is None:
            return False
        key = entity[0]
        # never fast-path an attack signature (position-aware; catches listen:...:4444 too)
        if event_is_threat_signature(ev.detail, key):
            return False
        if key not in set(self.memory.known_normal_entities()):
            return False                                # only fast-path already-trusted entities
        prompt = (
            "You are a fast triage gate for a host security agent. The entity below is already "
            "on this host's KNOWN-NORMAL list. Answer with exactly one word: NORMAL if this "
            "event is clearly routine and benign, or ESCALATE if anything is even slightly off "
            "and deserves the full reasoning model.\n\n"
            f"event: {ev.to_text()}\ndetail: {ev.detail}\nentity: {key}\nAnswer:"
        )
        resp = chat([{"role": "user", "content": prompt}], model=MODEL_FAST,
                    max_tokens=4, temperature=0.0)
        return (resp.get("text") or "").strip().upper().startswith("NORMAL")

    def decide(self, ev: Event, entity: tuple[str, str] | None = None) -> dict:
        """Run one perceive->reason->act->record cycle for a single event."""
        # track the entity (have we seen this before?)
        if entity:
            self.memory.touch_entity(entity[0], entity[1], ev.ts)

        event_id = self.memory.record_event(ev)

        # Cost-routing fast path: flash clears obvious-normal events without the expensive
        # qwen3.7-max call. Disabled with SENTINEL_NO_TRIAGE=1.
        if is_live() and os.getenv("SENTINEL_NO_TRIAGE") != "1" and self._flash_triage(ev, entity):
            result = execute("mark_normal", {"reason": "cleared by qwen3.6-flash fast triage "
                                             "(known-normal entity, no anomaly)"}, memory=self.memory)
            self.memory.record_decision(event_id, "mark_normal", result.get("reason", ""), ev.ts)
            return {"event": ev.to_text(), "action": "mark_normal",
                    "reason": result.get("reason", ""), "result": result,
                    "live": is_live(), "triage": "flash", "investigation": [], "steps": 0}

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                self._working_memory_block()
                + "\n\n=== NEW EVENT TO JUDGE ===\n"
                + ev.to_text()
                + f"\ndetail: {ev.detail}"
                + (f"\nentity: {entity[0]}" if entity else "")
                + "\n\nInvestigate if needed (check_entity / correlate_recent / query_memory), "
                "then take exactly one terminal action (mark_normal / alert_user / actuate)."
            )},
        ]

        # Multi-step investigation loop: the agent may call investigative tools repeatedly to
        # gather evidence before committing to a terminal action. This is the autonomy that the
        # long-horizon + 1M-context claim is FOR — it correlates across events to catch novel
        # multi-step attacks, not just one isolated signature. The trace is captured for the demo.
        investigation: list[dict] = []
        action, args = "alert_user", {"severity": "low", "reason": "inconclusive"}
        for step in range(MAX_INVESTIGATION_STEPS):
            resp = chat(messages, tools=TOOL_SCHEMAS)
            tool_calls = resp.get("tool_calls") or []
            if not tool_calls:
                # answered in prose instead of a tool — treat as a soft alert and stop
                action, args = "alert_user", {"severity": "low",
                                              "reason": (resp.get("text") or "")[:200] or "no tool called"}
                break
            tc = tool_calls[0]
            name, a = tc["name"], tc["arguments"]
            if name in TERMINAL_ACTIONS:
                action, args = name, a
                break
            # investigative tool → run it, feed the result back, let the agent keep reasoning
            obs = execute(name, a, memory=self.memory)
            investigation.append({"step": step + 1, "tool": name, "args": a, "observation": obs})
            messages.append({"role": "assistant",
                             "content": f"[investigate] {name}({a}) -> {obs}"})
            messages.append({"role": "user",
                             "content": "Continue investigating, or take a terminal action now."})
        else:
            # ran out of steps without a terminal action — force a final decision
            messages.append({"role": "user", "content": "Investigation budget reached. Decide NOW: "
                             "call mark_normal, alert_user, or actuate."})
            resp = chat(messages, tools=TOOL_SCHEMAS)
            tcs = [t for t in (resp.get("tool_calls") or []) if t["name"] in TERMINAL_ACTIONS]
            if tcs:
                action, args = tcs[0]["name"], tcs[0]["arguments"]

        result = execute(action, args, memory=self.memory)
        reason = args.get("reason", "")
        self.memory.record_decision(event_id, action, reason, ev.ts)

        return {"event": ev.to_text(), "action": action, "reason": reason,
                "result": result, "live": is_live(),
                "investigation": investigation,                 # the agent's investigative trace
                "steps": len(investigation)}


if __name__ == "__main__":
    mem = Memory(db_path=":memory:", archive_path="/tmp/sentinel_agent_test.jsonl")
    agent = SentinelAgent(mem)
    test = Event(ts=time.time(), kind="connection",
                 summary="new outbound connection 185.220.101.5:4444 (ESTABLISHED)",
                 detail={"ip": "185.220.101.5", "port": 4444, "status": "ESTABLISHED"})
    out = agent.decide(test, entity=("outbound:4444:185.220.101.5", "connection"))
    print("MODE:", "LIVE qwen3.7-max" if out["live"] else "STUB")
    print("event :", out["event"])
    print("action:", out["action"], "->", out["result"])
