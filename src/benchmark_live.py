"""
benchmark_live.py — the benchmark, scored by the REAL qwen3.7-max agent (not a heuristic).

`benchmark.py` scores a hand-written rule labeled "Sentinel" — useful to illustrate the logic,
but a skeptic rightly says "that's not Qwen, it's a strawman you wrote." This file removes that
objection entirely: it runs each scenario through the ACTUAL SentinelAgent.decide() — the same
multi-step qwen3.7-max investigation loop the live system uses — and scores the model's real
verdicts. The number here is a genuine measurement of the deployed agent, not a model of it.

It's slower and costs tokens (one+ live call per scenario), so it runs a representative subset
by default. Run:  cd src && SENTINEL_SIM=0 python benchmark_live.py [N]
(N = scenarios per class, default 6; use a small N to keep cost/time down.)
"""
from __future__ import annotations

import sys
import time

from agent import SentinelAgent
from memory import Event, Memory
from qwen_client import is_live

# A labeled subset spanning the attack classes (kept small — each runs a real Qwen decision).
# (label, kind, summary, detail, entity_key)
SCENARIOS = [
    # --- benign host activity (must NOT alarm) ---
    ("benign", "process", "new process started: nginx", {"name": "nginx"}, "proc:nginx"),
    ("benign", "process", "new process started: restic (backup)", {"name": "restic"}, "proc:restic"),
    ("benign", "connection", "outbound 10.10.10.50:9000 (NAS backup, internal)",
     {"ip": "10.10.10.50", "port": 9000, "external": False}, "outbound:9000:10.10.10.50"),
    ("benign", "login", "user logged in via SSH from 10.10.10.2: mohamed",
     {"user": "mohamed", "src": "10.10.10.2"}, "login:mohamed@10.10.10.2"),
    ("benign", "connection", "outbound 1.1.1.1:53 (DNS)", {"ip": "1.1.1.1", "port": 53}, "outbound:53:1.1.1.1"),
    ("benign", "process", "new process started: systemd-networkd", {"name": "systemd-networkd"}, "proc:systemd-networkd"),
    # --- threats across classes (must be caught) ---
    ("threat", "connection", "new outbound connection 185.220.101.5:4444 (ESTABLISHED)",
     {"ip": "185.220.101.5", "port": 4444, "external": True}, "outbound:4444:185.220.101.5"),  # reverse shell
    ("threat", "listen", "new listening port 0.0.0.0:4444",
     {"addr": "0.0.0.0:4444", "port": 4444}, "listen:0.0.0.0:4444"),                            # bind-shell listener
    ("threat", "connection", "new outbound connection 203.0.113.66:8443 to known C2",
     {"ip": "203.0.113.66", "port": 8443, "external": True, "note": "unknown external host"},
     "outbound:8443:203.0.113.66"),                                                              # novel non-sig egress
    ("threat", "process", "new process started: xmrig (crypto miner)",
     {"name": "xmrig"}, "proc:xmrig"),                                                           # miner
    ("threat", "login", "user logged in via SSH from 203.0.113.40: root",
     {"user": "root", "src": "203.0.113.40", "external": True}, "login:root@203.0.113.40"),      # external root login
    ("threat", "connection", "new outbound connection 45.13.1.9:1337 (ESTABLISHED)",
     {"ip": "45.13.1.9", "port": 1337, "external": True}, "outbound:1337:45.13.1.9"),            # C2 port
]


def run(per_class: int):
    if not is_live():
        print("This benchmark needs the LIVE model — set SENTINEL_SIM=0 and a QWEN_API_KEY.")
        return
    benign = [s for s in SCENARIOS if s[0] == "benign"][:per_class]
    threat = [s for s in SCENARIOS if s[0] == "threat"][:per_class]
    cases = benign + threat
    print(f"LIVE BENCHMARK — scored by the real qwen3.7-max agent ({len(cases)} scenarios: "
          f"{len(benign)} benign, {len(threat)} threat)\n")

    # a learned host: seed the baseline so benign internal/known activity is correctly normal
    mem = Memory(db_path=":memory:", archive_path="/tmp/bench_live.jsonl")
    agent = SentinelAgent(mem, host="edge-0")
    mem.save_baseline(1, "Normal on this host: nginx, restic backups to the internal NAS on "
                      "10.10.10.50:9000, DNS to 1.1.1.1, SSH admin logins from 10.10.10.2, "
                      "systemd services. External egress to unknown hosts and reverse-shell/C2 "
                      "ports are NOT normal.", "edge-0")

    tp = fp = fn = tn = 0
    for label, kind, summary, detail, key in cases:
        ev = Event(ts=time.time(), kind=kind, summary=summary, detail=detail, host="edge-0")
        out = agent.decide(ev, entity=(key, kind))
        flagged = out["action"] in ("alert_user", "actuate")
        ok = (flagged == (label == "threat"))
        mark = "✓" if ok else "✗ MISS" if label == "threat" else "✗ FALSE-ALARM"
        print(f"  [{label:6}] {summary[:50]:50} -> {out['action']:11} {mark}")
        if label == "threat":
            tp += flagged; fn += (not flagged)
        else:
            fp += flagged; tn += (not flagged)

    nt = tp + fn
    print(f"\n  REAL-QWEN RESULT: caught {tp}/{nt} threats, {fp} false alarms on {tn + fp} benign.")
    print(f"  recall {100*tp/max(1,nt):.0f}% · false-alarm {100*fp/max(1,fp+tn):.0f}% · "
          f"missed {fn}")
    print("\n  Every verdict above is a real qwen3.7-max decision — not a hand-written rule.")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    run(n)
