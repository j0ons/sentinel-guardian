"""
demo_activity.py — generate realistic host activity so Sentinel has something to guard.

A bare container is a boring thing to watch (the dashboard stays empty). This injects a
believable stream of home/lab activity DIRECTLY as events to the cloud — the same wire format
the real collector uses — so the dashboard fills with genuine qwen3.7-max decisions for a
live demo, and (with --attack) stages a reverse-shell moment to show the threat response.

This does NOT fake decisions: every event is really judged by the live model. It only
supplies the *input* a quiet host lacks. For ambient realism point the real collector at a
busy machine instead (see docs); use this to drive a demo on demand.

Run on the edge (or anywhere that can reach the cloud):
    SENTINEL_CLOUD=http://10.10.10.201:8000 python3 demo_activity.py            # steady stream
    SENTINEL_CLOUD=http://10.10.10.201:8000 python3 demo_activity.py --attack   # + a threat
    SENTINEL_CLOUD=http://10.10.10.201:8000 python3 demo_activity.py --burst 20 # 20 events fast
"""
from __future__ import annotations

import os
import sys
import time

import requests

CLOUD = os.getenv("SENTINEL_CLOUD", "http://127.0.0.1:8000").rstrip("/")
HOST = os.getenv("SENTINEL_DEMO_HOST", "homelab-01")
_TOKEN = os.getenv("SENTINEL_TOKEN", "").strip()
_AUTH = {"Authorization": f"Bearer {_TOKEN}"} if _TOKEN else {}

# The NOVEL kill-chain: three steps that are each individually unremarkable and use a port
# (8443) that is NOT in the hardcoded threat list — so a signature/rule engine sees nothing.
# Only an agent that CORRELATES them (unknown process -> new listener -> external egress)
# catches it. This is the demo's whole point: detection a static ruleset structurally cannot do.
KILLCHAIN = [
    ("process", "new process started: dbus-daemon-helper (pid {pid})",
     {"name": "dbus-daemon-helper"}, "proc:dbus-daemon-helper"),
    ("listen", "new listening port 0.0.0.0:8443",
     {"addr": "0.0.0.0:8443", "port": 8443}, "listen:0.0.0.0:8443"),
    ("connection", "new outbound connection 203.0.113.66:8443 (ESTABLISHED)",
     {"ip": "203.0.113.66", "port": 8443, "status": "ESTABLISHED", "external": True},
     "outbound:8443:203.0.113.66"),
]

# Believable home/lab activity. (kind, summary, detail, entity_key)
BENIGN = [
    ("process", "new process started: restic (pid {pid})", {"name": "restic"}, "proc:restic"),
    ("process", "new process started: jellyfin-ffmpeg (pid {pid})", {"name": "jellyfin-ffmpeg"}, "proc:jellyfin-ffmpeg"),
    ("process", "new process started: docker-proxy (pid {pid})", {"name": "docker-proxy"}, "proc:docker-proxy"),
    ("process", "new process started: node_exporter (pid {pid})", {"name": "node_exporter"}, "proc:node_exporter"),
    ("connection", "new outbound connection 10.10.10.50:9000 (ESTABLISHED)", {"ip": "10.10.10.50", "port": 9000}, "outbound:9000:10.10.10.50"),
    ("connection", "new outbound connection 10.10.10.60:445 (ESTABLISHED)", {"ip": "10.10.10.60", "port": 445}, "outbound:445:10.10.10.60"),
    ("connection", "outbound 443 -> updates.jellyfin.org", {"ip": "104.21.0.9", "port": 443}, "outbound:443:updates.jellyfin.org"),
    ("connection", "outbound 8123 -> 10.10.10.70 (home-assistant)", {"ip": "10.10.10.70", "port": 8123}, "outbound:8123:10.10.10.70"),
    ("login", "user logged in via SSH from 10.10.10.2: mohamed", {"user": "mohamed", "src": "10.10.10.2"}, "login:mohamed@10.10.10.2"),
    ("listen", "new listening port 0.0.0.0:8096", {"addr": "0.0.0.0:8096"}, "listen:0.0.0.0:8096"),
]

ATTACK = ("connection", "new outbound connection 185.220.101.5:4444 (ESTABLISHED)",
          {"ip": "185.220.101.5", "port": 4444, "status": "ESTABLISHED"},
          "outbound:4444:185.220.101.5")


def send(kind, summary, detail, entity_key, pid=None, show_trace=False):
    payload = {"kind": kind, "summary": summary.format(pid=pid or 0),
               "detail": detail, "host": HOST, "entity": [entity_key, kind]}
    try:
        r = requests.post(f"{CLOUD}/event", json=payload, headers=_AUTH, timeout=90)
        d = r.json()
        tag = {"mark_normal": "✓", "alert_user": "⚠", "actuate": "⛔"}.get(d.get("action"), "?")
        via = d.get("triage", "reason")
        print(f"  {tag} [{via:6}] {payload['summary'][:52]:52} -> {d.get('action')}")
        if show_trace and d.get("investigation"):
            for s in d["investigation"]:
                print(f"        ↳ step {s['step']}: {s['tool']}({s.get('args')})")
            print(f"        reason: {d.get('reason','')[:140]}")
        return d
    except Exception as e:
        print(f"  ! failed: {e}")
        return None


def main():
    args = sys.argv[1:]
    print(f"demo_activity -> {CLOUD}  host={HOST}")
    if "--attack" in args:
        print("\n>>> staging the reverse-shell moment (known :4444 signature):")
        send(*ATTACK)
        return
    if "--killchain" in args:
        print("\n>>> staging a NOVEL multi-step intrusion on port 8443 (NOT a known signature).")
        print(">>> A rule engine sees three unrelated events. Watch Sentinel correlate them:\n")
        pid = 4000
        for i, step in enumerate(KILLCHAIN):
            pid += 13
            last = (i == len(KILLCHAIN) - 1)
            print(f"  [{i+1}/3] {step[1].format(pid=pid)}")
            send(*step, pid=pid, show_trace=last)   # show the agent's investigation on the final step
            time.sleep(1)
        return
    burst = 0
    if "--burst" in args:
        burst = int(args[args.index("--burst") + 1])

    pid = 1000
    if burst:
        for i in range(burst):
            pid += 7
            send(*BENIGN[i % len(BENIGN)], pid=pid)
        return

    print("\nsteady stream (Ctrl-C to stop)...")
    i = 0
    while True:
        pid += 7
        send(*BENIGN[i % len(BENIGN)], pid=pid)
        i += 1
        time.sleep(float(os.getenv("SENTINEL_DEMO_DELAY", "8")))


if __name__ == "__main__":
    main()
