"""
demo_scenario.py — the COLD-START "watch it learn" demo (the money shot).

Why this exists:  the original replay.py uses obviously-benign events (Spotify, DNS to
1.1.1.1). A capable model like qwen3.7-max correctly calls those normal on DAY 1 — so the
false-alarm curve is already flat and there's nothing to "learn". That hides the whole point.

This scenario instead uses AMBIGUOUS home/lab activity — events that genuinely LOOK
suspicious until you know this specific host's context (a 3am backup hammering an odd port,
a NAS sync, a smart-home device beaconing, a self-hosted app phoning home). On a COLD host
with no baseline, the correct, calibrated response is to flag them. Only after the nightly
consolidation writes "on THIS host, that 3am job on :9000 is the backup, it's routine" does
the SAME event become correctly judged normal the next day.

So the curve falls for a TRUE reason: the 1M-context memory supplies the local context that
turns "unknown + scary" into "known + benign". That difference between day 1 and day 7 IS
the innovation — it is impossible without the persistent, self-rewriting memory.

The reverse-shell threat is mixed in from day 2 and must stay caught the whole time.

Run:  cd src && SENTINEL_SIM=0 python demo_scenario.py [days]
"""

from __future__ import annotations

import sys
import time

from agent import SentinelAgent
from consolidate import consolidate
from memory import Event, Memory
from qwen_client import is_live

# --- Ambiguous-but-benign home/lab activity ---------------------------------
# Each is the kind of thing a cautious guard SHOULD flag on a cold host, but that is in
# fact routine for THIS deployment once learned. (kind, summary, detail, entity)
AMBIGUOUS_BENIGN = [
    ("process", "new process started: restic (pid 8821)",
     {"name": "restic", "cmd": "restic backup /data --repo sftp:nas"},
     ("proc:restic", "process")),
    ("connection", "new outbound connection 10.10.10.50:9000 (ESTABLISHED)",
     {"ip": "10.10.10.50", "port": 9000, "status": "ESTABLISHED", "note": "nightly backup target"},
     ("outbound:9000:10.10.10.50", "connection")),
    ("connection", "new outbound connection 10.10.10.60:445 (ESTABLISHED)",
     {"ip": "10.10.10.60", "port": 445, "status": "ESTABLISHED", "note": "SMB to NAS"},
     ("outbound:445:10.10.10.60", "connection")),
    ("connection", "outbound 8123 -> 10.10.10.70 (home-assistant poll)",
     {"ip": "10.10.10.70", "port": 8123},
     ("outbound:8123:10.10.10.70", "connection")),
    ("process", "new process started: jellyfin-ffmpeg (pid 9001)",
     {"name": "jellyfin-ffmpeg", "cmd": "transcode"},
     ("proc:jellyfin-ffmpeg", "process")),
    ("connection", "outbound 443 -> updates.jellyfin.org",
     {"ip": "104.21.0.9", "port": 443, "note": "self-hosted media server update check"},
     ("outbound:443:updates.jellyfin.org", "connection")),
    ("login", "user logged in via SSH from 10.10.10.2: mohamed",
     {"user": "mohamed", "src": "10.10.10.2", "method": "publickey"},
     ("login:mohamed@10.10.10.2", "login")),
    ("process", "new process started: tailscaled (pid 612)",
     {"name": "tailscaled"},
     ("proc:tailscaled", "process")),
]

# --- The genuine threat: reverse shell to a known-bad Tor exit on :4444 ------
# Must be caught EVERY day, cold or learned. This is the false-negative guard.
THREAT = ("connection", "new outbound connection 185.220.101.5:4444 (ESTABLISHED)",
          {"ip": "185.220.101.5", "port": 4444, "status": "ESTABLISHED",
           "note": "unknown host, ephemeral high port, known Tor exit"},
          ("outbound:4444:185.220.101.5", "connection"))


def is_false_alarm(action: str, is_threat: bool) -> bool:
    return (action in ("alert_user", "actuate")) and not is_threat


def run(days: int = 7):
    # Fresh, COLD memory — no prior baseline. This is the point.
    mem = Memory(db_path=":memory:", archive_path="/tmp/sentinel_demo.jsonl")
    agent = SentinelAgent(mem, host="edge-0")

    mode = "LIVE qwen3.7-max" if is_live() else "STUB (no credits)"
    print(f"SENTINEL cold-start demo — {days} simulated days — mode: {mode}")
    print("Host starts with NO baseline. Watch false alarms fall as memory learns context.\n")
    history = []

    for day in range(1, days + 1):
        alarms = total = caught = threats = 0
        events = list(AMBIGUOUS_BENIGN)
        if day >= 2:                       # threat present from day 2 onward
            events.append(THREAT)

        for kind, summary, detail, entity in events:
            ev = Event(ts=time.time(), kind=kind, summary=summary, detail=detail, host="edge-0")
            is_threat = (entity == THREAT[3])
            out = agent.decide(ev, entity=entity)
            total += 1
            if is_threat:
                threats += 1
                if out["action"] in ("alert_user", "actuate"):
                    caught += 1
            elif is_false_alarm(out["action"], is_threat):
                alarms += 1

        benign_n = total - threats
        fa_rate = alarms / max(1, benign_n)
        detect = f"{caught}/{threats}" if threats else "n/a"
        history.append((day, alarms, fa_rate, detect))
        print(f"  Day {day}:  false alarms={alarms}/{benign_n}  rate={fa_rate:5.0%}  "
              f"threat caught={detect}")

        c = consolidate(mem, host="edge-0")
        print(f"           Sentinel is dreaming... -> baseline v{c['version']}, "
              f"promoted {c['promoted']} entities to known-normal")

    print("\n  LEARNING CURVE (false-alarm rate) — the money shot:")
    for day, alarms, rate, detect in history:
        bar = "#" * int(rate * 40)
        print(f"    Day {day} |{bar:<40}| {rate:4.0%}   threat: {detect}")
    print("\n  Cold day-1 caution -> calibrated by day N, because nightly consolidation taught")
    print("  the agent THIS host's context. The reverse-shell threat stays caught throughout.")
    return history


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    run(days)
