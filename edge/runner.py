"""
runner.py — Sentinel's edge agent. RUNS ON THE PI.

Loop: snapshot host -> diff to events -> POST each event to the cloud service ->
execute any returned action locally (safe-by-default). Buffers events to disk if the
cloud is unreachable, and replays them when it returns (offline resilience).

Config via env:
  SENTINEL_CLOUD   cloud service base URL   (e.g. http://192.168.1.50:8000)
  SENTINEL_INTERVAL seconds between snapshots (default 5)
  SENTINEL_ARMED   "1" to allow real local actuation (default off = dry-run)

Run on the Pi:  SENTINEL_CLOUD=http://<mac-ip>:8000 python3 runner.py
"""

from __future__ import annotations

import json
import os
import socket
import time

import requests

import collectors

CLOUD = os.getenv("SENTINEL_CLOUD", "http://127.0.0.1:8000").rstrip("/")
INTERVAL = float(os.getenv("SENTINEL_INTERVAL", "5"))
HOST = socket.gethostname()
BUFFER = os.path.join(os.path.dirname(__file__), "outbox.jsonl")


def post_event(payload: dict) -> dict | None:
    try:
        r = requests.post(f"{CLOUD}/event", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def buffer_event(payload: dict):
    with open(BUFFER, "a") as f:
        f.write(json.dumps(payload) + "\n")


def flush_buffer():
    """Replay any events buffered while the cloud was down."""
    if not os.path.exists(BUFFER):
        return
    pending = [json.loads(l) for l in open(BUFFER) if l.strip()]
    if not pending:
        return
    survived = []
    for p in pending:
        if post_event(p) is None:
            survived.append(p)            # still down — keep it
    with open(BUFFER, "w") as f:
        for p in survived:
            f.write(json.dumps(p) + "\n")
    if not survived:
        print(f"[edge] flushed {len(pending)} buffered events")


def apply_action(decision: dict):
    """Execute the cloud's decision locally. Actuation is handled server-side in dry-run;
    here we just surface it. Real local enforcement (nftables/kill) would live here when armed."""
    action = decision.get("action")
    reason = decision.get("reason", "")
    tag = {"mark_normal": "ok ", "alert_user": "ALERT", "actuate": "ACT!"}.get(action, "?")
    print(f"  [{tag}] {decision.get('event','')}  ->  {action}  ({reason})")


def main():
    print(f"Sentinel EDGE runner on '{HOST}' -> cloud {CLOUD} (every {INTERVAL}s)")
    try:
        h = requests.get(f"{CLOUD}/health", timeout=5).json()
        print(f"  cloud OK — mode={h.get('mode')} baseline=v{h.get('baseline_version')}")
    except requests.RequestException:
        print("  cloud not reachable yet — will buffer events until it is")

    prev = collectors.snapshot()
    while True:
        time.sleep(INTERVAL)
        try:
            flush_buffer()
            now = collectors.snapshot()
            events = collectors.diff_events(prev, now)
            prev = now
        except Exception as e:                 # never let a bad snapshot kill the agent
            print(f"  [warn] snapshot/diff error, skipping cycle: {e}", flush=True)
            continue

        for ev in events:
            try:
                ent = collectors.event_entity(ev)
                payload = {"kind": ev.kind, "summary": ev.summary, "detail": ev.detail,
                           "host": HOST, "entity": list(ent) if ent else None}
                decision = post_event(payload)
                if decision is None:
                    buffer_event(payload)
                    print(f"  [buffered] {ev.to_text()}", flush=True)
                else:
                    apply_action(decision)
            except Exception as e:             # one bad event must not stop the rest
                print(f"  [warn] failed handling event {ev.to_text()}: {e}", flush=True)


if __name__ == "__main__":
    main()
