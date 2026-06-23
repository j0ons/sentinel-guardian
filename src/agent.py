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
from tools import TOOL_SCHEMAS, execute

# Threat-signature markers that must never be cleared by the cheap triage gate (safety floor).
THREAT_MARKERS = (":4444:", ":1337:", ":31337:", ":5555:", ":6667:")

SYSTEM_PROMPT = """You are Sentinel, an autonomous security guardian running on a single host.
Your job: for each observed event, decide if it is NORMAL for this host or an ANOMALY.

You learn what is normal from the baseline and known-normal entities given to you. Be
calibrated: most events on a working machine are routine — do not cry wolf. Reserve alerts
for genuinely unusual activity, and reserve `actuate` for high-confidence malicious behavior
that contradicts the baseline (e.g. an unknown process opening an unexpected listening port
or connecting to a suspicious endpoint).

NON-NEGOTIABLE SAFETY FLOOR — a permissive baseline NEVER overrides these. Even if the host
looks quiet and most activity is normal, ALWAYS treat the following as a threat and `actuate`
(or at minimum `alert_user` with severity=medium), regardless of what the baseline says:
  - outbound connections to ephemeral/uncommon high ports (e.g. 4444, 1337, 31337) to an
    unknown or external destination — classic reverse-shell / C2 signature;
  - a connection to a known-bad destination (Tor exits, flagged IPs);
  - an unknown process opening a listener or spawning a shell with network egress.
A baseline describes routine BENIGN activity; it is not a license to ignore attack
signatures. When the signature above is present, the threat verdict wins — full stop.

Always choose exactly ONE tool. Prefer `mark_normal` when the event fits the learned
baseline AND shows no attack signature. Your goal over time is to drive false alarms toward
zero while NEVER missing a real threat — missing a threat is far worse than a false alarm."""


# qwen3.7-max has a 1M-token context window. The whole point of Sentinel is to use it as
# living working memory — reason over the deployment's FULL operational history, not a small
# top-k slice. We budget by characters (~4 chars/token) and pull as much history as fits,
# defaulting to a generous slice of context rather than an arbitrary 200-event cap.
CONTEXT_TOKEN_BUDGET = int(os.getenv("SENTINEL_CONTEXT_TOKENS", "200000"))  # tokens of history
_CHARS_PER_TOKEN = 4
MAX_HISTORY_EVENTS = int(os.getenv("SENTINEL_MAX_HISTORY_EVENTS", "5000"))  # hard upper bound


class SentinelAgent:
    def __init__(self, memory: Memory, host: str = "edge-0"):
        self.memory = memory
        self.host = host
        self.last_context_stats: dict = {}     # exposed for the dashboard/demo

    def _working_memory_block(self, max_events: int = MAX_HISTORY_EVENTS) -> str:
        """Assemble the host's living memory for the 1M context window.

        Pulls the full operational history up to a token budget — this is the 1M-context claim
        made real: at decision time the agent sees the deployment's whole timeline (or as much
        of it as the budget allows), not a fixed small window. Records how much it used in
        `last_context_stats` so the demo can show the context actually filling up over time."""
        baseline = self.memory.current_baseline(self.host)
        version = self.memory.baseline_version(self.host)
        normals = self.memory.known_normal_entities()
        recent = self.memory.recent_events(limit=max_events)

        # Drop oldest events first if we'd blow the token budget (keep the most recent history).
        char_budget = CONTEXT_TOKEN_BUDGET * _CHARS_PER_TOKEN
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
            "token_budget": CONTEXT_TOKEN_BUDGET,
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
        if any(m in key for m in THREAT_MARKERS):       # never fast-path an attack signature
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
                    "live": is_live(), "triage": "flash"}

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                self._working_memory_block()
                + "\n\n=== NEW EVENT TO JUDGE ===\n"
                + ev.to_text()
                + f"\ndetail: {ev.detail}"
                + (f"\nentity: {entity[0]}" if entity else "")
                + "\n\nDecide. Call exactly one tool."
            )},
        ]

        resp = chat(messages, tools=TOOL_SCHEMAS)
        tool_calls = resp.get("tool_calls") or []

        if not tool_calls:
            # model answered in text instead of calling a tool — default to a soft alert
            action, args = "alert_user", {"severity": "low", "reason": resp.get("text", "")[:200]}
        else:
            tc = tool_calls[0]
            action, args = tc["name"], tc["arguments"]

        # one-hop tool chaining: if it asked to look something up, do it and let it re-decide
        if action == "query_memory":
            lookup = execute("query_memory", args, memory=self.memory)
            messages.append({"role": "assistant", "content": f"(queried memory: {lookup})"})
            messages.append({"role": "user", "content": "Now decide with a final action tool."})
            resp = chat(messages, tools=TOOL_SCHEMAS)
            tcs = resp.get("tool_calls") or []
            if tcs:
                action, args = tcs[0]["name"], tcs[0]["arguments"]
            else:
                action, args = "alert_user", {"severity": "low", "reason": "inconclusive after lookup"}

        result = execute(action, args, memory=self.memory)
        reason = args.get("reason", "")
        self.memory.record_decision(event_id, action, reason, ev.ts)

        return {"event": ev.to_text(), "action": action, "reason": reason,
                "result": result, "live": is_live()}


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
