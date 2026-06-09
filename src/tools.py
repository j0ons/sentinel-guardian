"""
tools.py — the actions Sentinel can take, exposed to Qwen as function-calling tools.

The OpenAI-format schemas are what we hand to qwen3.7-max; `execute()` runs the chosen
tool. On the edge SOC build the "actuate" actions (kill process / block IP) are real
capabilities — kept SAFE-BY-DEFAULT here (dry-run unless explicitly armed) so a demo or a
hallucinated decision can never harm the host.
"""

from __future__ import annotations

import os

ARMED = os.getenv("SENTINEL_ARMED", "0") == "1"   # destructive actions only when armed

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "mark_normal",
            "description": "Record that this event is normal/expected for this host. Use when the "
                           "event matches the learned baseline or known-good entities. This is the "
                           "default for routine activity and is what reduces false alarms over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why this is normal."},
                    "entity": {"type": "string", "description": "Canonical entity key, if any."},
                },
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "alert_user",
            "description": "Raise a low/medium alert for human review. Use for something unusual but "
                           "not clearly malicious — worth a human's eyes, not an automatic response.",
            "parameters": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["low", "medium"]},
                    "reason": {"type": "string"},
                },
                "required": ["severity", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "actuate",
            "description": "Take a defensive action on the edge host: kill a process or block an IP. "
                           "Use ONLY for high-confidence malicious activity that contradicts the "
                           "baseline (e.g. an unknown process opening a reverse shell). Safe-by-default: "
                           "runs as a dry-run unless the host is explicitly armed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["kill_process", "block_ip"]},
                    "target": {"type": "string", "description": "pid for kill_process, ip for block_ip"},
                    "reason": {"type": "string"},
                },
                "required": ["action", "target", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_memory",
            "description": "Semantically search Sentinel's past events before deciding. Use when you "
                           "are unsure whether something has been seen before on this host.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]


def execute(name: str, args: dict, *, memory=None) -> dict:
    """Run a tool. Returns a result dict the agent can fold back into the conversation."""
    if name == "mark_normal":
        return {"ok": True, "action": "mark_normal", "reason": args.get("reason", "")}

    if name == "alert_user":
        sev = args.get("severity", "low")
        return {"ok": True, "action": "alert_user", "severity": sev, "reason": args.get("reason", "")}

    if name == "actuate":
        action = args.get("action")
        target = args.get("target")
        reason = args.get("reason", "")
        if not ARMED:
            return {"ok": True, "action": "actuate", "dry_run": True,
                    "would": f"{action} {target}", "reason": reason}
        return _actuate_real(action, target, reason)

    if name == "query_memory":
        if memory is None:
            return {"ok": False, "error": "no memory bound"}
        hits = memory.search_recall(args.get("query", ""), k=5)
        return {"ok": True, "results": [{"score": round(s, 3), "event": e.to_text()}
                                        for s, e in hits]}

    return {"ok": False, "error": f"unknown tool {name}"}


def _actuate_real(action: str, target: str, reason: str) -> dict:
    """Real defensive actions — only reached when SENTINEL_ARMED=1."""
    import signal
    if action == "kill_process":
        try:
            os.kill(int(target), signal.SIGTERM)
            return {"ok": True, "action": "kill_process", "target": target, "armed": True}
        except (ProcessLookupError, ValueError, PermissionError) as e:
            return {"ok": False, "error": str(e)}
    if action == "block_ip":
        # On the Pi (Linux) this would shell out to nftables/iptables. Recorded as intent here.
        return {"ok": True, "action": "block_ip", "target": target, "armed": True,
                "note": "would add nftables drop rule on Linux edge"}
    return {"ok": False, "error": f"unknown actuate action {action}"}
