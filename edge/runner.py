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
import gpio                                  # physical actuation layer (no-op off a Pi)

CLOUD = os.getenv("SENTINEL_CLOUD", "http://127.0.0.1:8000").rstrip("/")
INTERVAL = float(os.getenv("SENTINEL_INTERVAL", "5"))
# The cloud reasons with qwen3.7-max, which can take tens of seconds for a novel event over
# a large context. Give the POST room so verdicts aren't dropped to the buffer prematurely.
POST_TIMEOUT = float(os.getenv("SENTINEL_POST_TIMEOUT", "60"))
HOST = socket.gethostname()
BUFFER = os.path.join(os.path.dirname(__file__), "outbox.jsonl")
# Bearer token for the cloud's authenticated endpoints (must match server SENTINEL_TOKEN).
_TOKEN = os.getenv("SENTINEL_TOKEN", "").strip()
_AUTH = {"Authorization": f"Bearer {_TOKEN}"} if _TOKEN else {}


def post_event(payload: dict) -> dict | None:
    try:
        r = requests.post(f"{CLOUD}/event", json=payload, headers=_AUTH, timeout=POST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def ping_cloud():
    """Lightweight heartbeat so the dashboard knows the edge is alive even on a quiet cycle."""
    try:
        requests.post(f"{CLOUD}/api/edge/ping", json={"host": HOST}, headers=_AUTH, timeout=5)
    except requests.RequestException:
        pass


def buffer_event(payload: dict):
    with open(BUFFER, "a") as f:
        f.write(json.dumps(payload) + "\n")


def flush_buffer():
    """Replay any events buffered while the cloud was down.

    Each line is parsed independently: a single torn write (a Pi losing power mid-append —
    exactly the scenario the buffer exists for) must not brick the whole runner. Undecodable
    lines are dropped + logged, never allowed to raise and kill the main loop forever."""
    if not os.path.exists(BUFFER):
        return
    pending, corrupt = [], 0
    with open(BUFFER) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                pending.append(json.loads(line))
            except json.JSONDecodeError:
                corrupt += 1                  # drop the poison-pill line, keep going
    if corrupt:
        print(f"[edge] dropped {corrupt} corrupt buffer line(s)", flush=True)
    if not pending:
        if corrupt:                           # clear the file of the dropped junk
            open(BUFFER, "w").close()
        return
    survived = []
    for p in pending:
        decision = post_event(p)
        if decision is None:
            survived.append(p)                # still down — keep it
        else:
            apply_action(decision)            # a buffered threat must still fire locally
    with open(BUFFER, "w") as f:
        for p in survived:
            f.write(json.dumps(p) + "\n")
    if not survived:
        print(f"[edge] flushed {len(pending)} buffered events", flush=True)


def apply_action(decision: dict):
    """Execute the cloud's decision locally — including PHYSICAL signalling on the Pi.

    The cloud reasons; the edge device acts on its own hardware. This is the local-actuation
    half of the perceive->reason->act loop: a `mark_normal` blinks the status LED green-ish,
    an `alert_user` raises the amber alert line, and an `actuate` (high-confidence threat)
    fires the red LED + buzzer so the threat is visible/audible at the device itself —
    independent of any screen or network. On non-Pi hosts gpio.* are safe no-ops."""
    action = decision.get("action")
    reason = decision.get("reason", "")
    tag = {"mark_normal": "ok ", "alert_user": "ALERT", "actuate": "ACT!"}.get(action, "?")
    print(f"  [{tag}] {decision.get('event','')}  ->  {action}  ({reason})")

    if action == "actuate":
        gpio.threat()                          # red LED solid + buzzer pulse
        _local_kill(decision)                  # the Live Kill: terminate the malicious PID locally
    elif action == "alert_user":
        gpio.alert()                           # amber LED blink
    else:
        gpio.heartbeat_ok()                    # brief green tick — system alive & calm


def _local_kill(decision: dict):
    """THE LIVE KILL — when armed, terminate the offending local process on THIS host. The
    cloud reasons; the kill lands where the malicious process actually runs. Armed-only and
    PID-validated (never signal a group/init). Set SENTINEL_ARMED=1 on the edge to enable."""
    if os.getenv("SENTINEL_ARMED", "0") != "1":
        would = (decision.get("result") or {}).get("would", "")
        print(f"  [ACT!] SAFE/dry-run — would: {would or 'kill the offending process'}", flush=True)
        return
    # find the malicious pid: prefer the decision's result target, else the killchain process
    result = decision.get("result") or {}
    target = result.get("target")
    pid = None
    try:
        pid = int(target)
    except (TypeError, ValueError):
        pid = _find_attacker_pid()             # fall back to locating the backdoor by name/port
    if not pid or pid <= 1:
        print(f"  [ACT!] no valid local PID to kill (target={target!r})", flush=True)
        return
    try:
        import signal
        os.kill(pid, signal.SIGTERM)
        print(f"  [ACT!] ⛔ KILLED malicious process PID {pid} — threat neutralized on the host",
              flush=True)
    except (ProcessLookupError, PermissionError) as e:
        print(f"  [ACT!] kill PID {pid} failed: {e}", flush=True)


def _find_attacker_pid():
    """Locate the backdoor process (the attacker.py / a listener on the chain port) by scanning
    psutil — used when the decision didn't carry an explicit PID."""
    try:
        import psutil
    except Exception:
        return None
    port = int(os.getenv("ATTACKER_PORT", "8443"))
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cl = " ".join(p.info.get("cmdline") or [])
            if "attacker.py" in cl or f":{port}" in cl:
                return p.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def main():
    print(f"Sentinel EDGE runner on '{HOST}' -> cloud {CLOUD} (every {INTERVAL}s)")
    try:
        h = requests.get(f"{CLOUD}/health", timeout=5).json()
        print(f"  cloud OK — mode={h.get('mode')} baseline=v{h.get('baseline_version')}")
    except requests.RequestException:
        print("  cloud not reachable yet — will buffer events until it is")

    import sensors
    if sensors.available():
        print("  physical sensors: ACTIVE (PIR motion + tamper switch on GPIO)")
    prev = collectors.snapshot()
    while True:
        time.sleep(INTERVAL)
        try:
            flush_buffer()
            ping_cloud()                       # heartbeat every cycle (alive even with no changes)
            now = collectors.snapshot()
            events = collectors.diff_events(prev, now)
            prev = now
            # PHYSICAL sensing: fold any real hardware events (motion / tamper) into the same
            # perceive->reason->act loop — Sentinel reasons about the physical world too.
            for s in sensors.poll():
                events.append(collectors.Event(ts=time.time(), kind=s["kind"],
                              summary=s["summary"], detail=s.get("detail", {}), host=HOST))
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
