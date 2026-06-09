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

import time

from memory import Event, Memory
from qwen_client import chat, is_live
from tools import TOOL_SCHEMAS, execute

SYSTEM_PROMPT = """You are Sentinel, an autonomous security guardian running on a single host.
Your job: for each observed event, decide if it is NORMAL for this host or an ANOMALY.

You learn what is normal from the baseline and known-normal entities given to you. Be
calibrated: most events on a working machine are routine — do not cry wolf. Reserve alerts
for genuinely unusual activity, and reserve `actuate` for high-confidence malicious behavior
that contradicts the baseline (e.g. an unknown process opening an unexpected listening port
or connecting to a suspicious endpoint).

Always choose exactly ONE tool. Prefer `mark_normal` when the event fits the learned
baseline. Your goal over time is to drive false alarms toward zero while never missing a
real threat."""


class SentinelAgent:
    def __init__(self, memory: Memory, host: str = "edge-0"):
        self.memory = memory
        self.host = host

    def _working_memory_block(self, max_events: int = 200) -> str:
        """Assemble the host's living memory for the 1M context window."""
        baseline = self.memory.current_baseline(self.host)
        version = self.memory.baseline_version(self.host)
        normals = self.memory.known_normal_entities()
        recent = self.memory.recent_events(limit=max_events)

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

    def decide(self, ev: Event, entity: tuple[str, str] | None = None) -> dict:
        """Run one perceive->reason->act->record cycle for a single event."""
        # track the entity (have we seen this before?)
        if entity:
            self.memory.touch_entity(entity[0], entity[1], ev.ts)

        event_id = self.memory.record_event(ev)

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
