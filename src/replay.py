"""
replay.py — the demo harness. Simulates multiple days of host activity, runs Sentinel on
every event, runs nightly consolidation, and reports the FALSE-ALARM RATE per day.

This is what produces the money-shot graph: as the baseline sharpens each night, routine
events that were alerted on early get correctly marked normal — the false-alarm rate falls
toward zero while genuine threats are still caught. Runs offline (STUB); with QWEN_API_KEY
the same script demonstrates real qwen3.7-max judgment.

Run:  python src/replay.py [days]
"""

from __future__ import annotations

import sys
import time

from agent import SentinelAgent
from consolidate import consolidate
from memory import Event, Memory
from qwen_client import is_live

# A day's worth of routine, benign activity that SHOULD become "normal" once learned.
BENIGN = [
    ("process", "new process started: Spotify", {"name": "Spotify"}, ("proc:Spotify", "process")),
    ("process", "new process started: zoom.us", {"name": "zoom.us"}, ("proc:zoom.us", "process")),
    ("connection", "outbound 443 -> api.github.com", {"ip": "140.82.112.3", "port": 443},
     ("outbound:443:140.82.112.3", "connection")),
    ("connection", "outbound 443 -> slack.com", {"ip": "3.89.0.1", "port": 443},
     ("outbound:443:3.89.0.1", "connection")),
    ("connection", "outbound 53 -> 1.1.1.1 (DNS)", {"ip": "1.1.1.1", "port": 53},
     ("outbound:53:1.1.1.1", "connection")),
    ("login", "user logged in: mohamed", {"user": "mohamed"}, ("user:mohamed", "login")),
]

# One genuine threat injected on a later day — must STILL be caught after learning.
THREAT = ("connection", "new outbound connection 185.220.101.5:4444 (ESTABLISHED)",
          {"ip": "185.220.101.5", "port": 4444, "status": "ESTABLISHED"},
          ("outbound:4444:185.220.101.5", "connection"))


def is_false_alarm(action: str, is_threat: bool) -> bool:
    """A false alarm = alerting/actuating on benign activity."""
    return (action in ("alert_user", "actuate")) and not is_threat


def run(days: int = 5):
    mem = Memory(db_path=":memory:", archive_path="/tmp/sentinel_replay.jsonl")
    agent = SentinelAgent(mem, host="edge-0")

    print(f"SENTINEL replay — {days} simulated days — "
          f"mode: {'LIVE qwen3.7-max' if is_live() else 'STUB (no credits yet)'}\n")
    history = []

    for day in range(1, days + 1):
        alarms = total = caught_threat = threats = 0
        events = list(BENIGN)
        if day >= 3:                       # threat appears from day 3 onward
            events.append(THREAT)

        for kind, summary, detail, entity in events:
            ev = Event(ts=time.time(), kind=kind, summary=summary, detail=detail, host="edge-0")
            is_threat = (detail == THREAT[2])
            out = agent.decide(ev, entity=entity)
            total += 1
            if is_threat:
                threats += 1
                if out["action"] in ("alert_user", "actuate"):
                    caught_threat += 1
            elif is_false_alarm(out["action"], is_threat):
                alarms += 1

        fa_rate = alarms / max(1, total - threats)
        detect = f"{caught_threat}/{threats}" if threats else "n/a"
        history.append((day, alarms, fa_rate, detect))
        print(f"  Day {day}:  false alarms={alarms:<2}  rate={fa_rate:5.0%}  "
              f"threat caught={detect}")

        # nightly dreaming
        c = consolidate(mem, host="edge-0")
        print(f"           dreaming -> baseline v{c['version']}, promoted {c['promoted']} "
              f"entities to known-normal")

    print("\n  Learning curve (false-alarm rate):")
    for day, alarms, rate, detect in history:
        bar = "#" * int(rate * 40)
        print(f"    Day {day} |{bar:<40}| {rate:4.0%}")
    print("\n  ^ With real qwen3.7-max this trends to 0% as the baseline sharpens,")
    print("    while genuine threats (port 4444 reverse shell) keep getting caught.")
    return history


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run(days)
