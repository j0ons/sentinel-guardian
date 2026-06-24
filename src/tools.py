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
    {
        "type": "function",
        "function": {
            "name": "check_entity",
            "description": "Look up the full history of a specific entity (process/connection/login) — "
                           "how many times it's been seen, when first/last, and whether it's trusted. "
                           "Use while investigating to ground a verdict in this host's actual history.",
            "parameters": {
                "type": "object",
                "properties": {"entity": {"type": "string",
                               "description": "canonical key, e.g. 'proc:nginx' or 'outbound:4444:1.2.3.4'"}},
                "required": ["entity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "correlate_recent",
            "description": "List the host's activity in the last N seconds, to see if THIS event is "
                           "part of a larger pattern — an attack rarely happens alone (e.g. a new "
                           "process, then a new listener, then an external connection = a kill-chain). "
                           "Use to detect novel multi-step threats, not just known-bad signatures.",
            "parameters": {
                "type": "object",
                "properties": {"seconds": {"type": "integer",
                               "description": "look-back window in seconds (e.g. 120)"}},
                "required": ["seconds"],
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

    if name == "check_entity":
        if memory is None:
            return {"ok": False, "error": "no memory bound"}
        return {"ok": True, **memory.entity_history(args.get("entity", ""))}

    if name == "correlate_recent":
        if memory is None:
            return {"ok": False, "error": "no memory bound"}
        secs = float(args.get("seconds", 120))
        evs = memory.events_in_window(secs, limit=40)
        return {"ok": True, "window_s": secs, "count": len(evs),
                "events": [e.to_text() for e in evs]}

    return {"ok": False, "error": f"unknown tool {name}"}


def _actuate_real(action: str, target: str, reason: str) -> dict:
    """Real defensive actions — only reached when SENTINEL_ARMED=1."""
    import signal
    if action == "kill_process":
        # Validate the PID hard: int('-1')==-1 → os.kill(-1, ...) signals EVERY process;
        # int('0')==0 → the whole process group. A hallucinated/injected target:"-1" would
        # take down the host. Refuse anything <= 1 (and PID 1 = init).
        try:
            pid = int(target)
        except (TypeError, ValueError):
            return {"ok": False, "error": f"invalid pid {target!r}"}
        if pid <= 1:
            return {"ok": False, "error": f"refusing to kill pid {pid} (<=1: would hit a "
                    "process group / init / every process)"}
        try:
            os.kill(pid, signal.SIGTERM)
            # Keep the same keys the dry-run path emits (would/dry_run) so the dashboard
            # kill-lock + drawer render identically whether SAFE or ARMED.
            return {"ok": True, "action": "actuate", "dry_run": False,
                    "would": f"kill_process {pid}", "target": pid, "armed": True, "reason": reason}
        except (ProcessLookupError, PermissionError) as e:
            return {"ok": False, "error": str(e), "dry_run": False, "would": f"kill_process {target}"}
    if action == "block_ip":
        # Validate as a real IP before any future nftables/iptables shell-out (never interpolate
        # an unvalidated string into a command). Currently records intent only.
        import ipaddress
        try:
            ip = str(ipaddress.ip_address(target))
        except ValueError:
            return {"ok": False, "error": f"invalid ip {target!r}"}
        return {"ok": True, "action": "actuate", "dry_run": False,
                "would": f"block_ip {ip}", "target": ip, "armed": True,
                "note": "would add nftables drop rule on Linux edge", "reason": reason}
    return {"ok": False, "error": f"unknown actuate action {action}"}
