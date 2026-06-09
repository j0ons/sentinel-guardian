"""
dashboard.py — live terminal view of Sentinel reasoning out loud. DEMO ASSET #2.

Polls the cloud service /feed and prints each decision as it happens, color-coded, with
the "dreaming" passes called out. This is what we screen-record for the demo video — the
audience watches Sentinel think, recall, and act in real time.

Run:  python dashboard.py            (defaults to http://127.0.0.1:8000)
      SENTINEL_CLOUD=http://host:8000 python dashboard.py
"""

from __future__ import annotations

import os
import time

import requests

CLOUD = os.getenv("SENTINEL_CLOUD", "http://127.0.0.1:8000").rstrip("/")

RESET = "\033[0m"
C = {"mark_normal": "\033[32m", "alert_user": "\033[33m", "actuate": "\033[31m",
     "consolidate": "\033[36m", "dim": "\033[2m", "bold": "\033[1m"}
TAG = {"mark_normal": " NORMAL ", "alert_user": " ALERT  ", "actuate": " ACT!   ",
       "consolidate": " DREAM  "}


def banner():
    print(C["bold"] + "=" * 70)
    print("  SENTINEL — live decision feed")
    try:
        h = requests.get(f"{CLOUD}/health", timeout=5).json()
        mode = h.get("mode")
        print(f"  cloud: {CLOUD}   mode: {mode}   baseline: v{h.get('baseline_version')}"
              f"   known-normal: {h.get('known_normal')}")
    except requests.RequestException:
        print(f"  cloud: {CLOUD}   (not reachable — start server.py)")
    print("=" * 70 + RESET)


def render(item: dict):
    action = item.get("action", "?")
    color = C.get(action, "")
    tag = TAG.get(action, f" {action} ")
    ts = time.strftime("%H:%M:%S", time.localtime(item.get("ts", time.time())))
    if action == "consolidate":
        r = item.get("result", {})
        print(f"{color}{ts} [{tag}]{RESET} baseline -> v{r.get('version')}, "
              f"promoted {r.get('promoted')} entities to known-normal")
        print(f"        {C['dim']}{r.get('baseline_preview','')}{RESET}")
        return
    event = item.get("event", "")
    reason = item.get("reason", "")
    print(f"{color}{ts} [{tag}]{RESET} {event}")
    if reason:
        print(f"        {C['dim']}reasoning: {reason}{RESET}")


def main():
    banner()
    since = 0.0
    print(f"{C['dim']}(waiting for events… run the edge runner or replay harness){RESET}\n")
    while True:
        try:
            data = requests.get(f"{CLOUD}/feed", params={"since": since}, timeout=10).json()
            for item in data.get("items", []):
                render(item)
                since = max(since, item["ts"])
        except requests.RequestException:
            pass
        time.sleep(1)


if __name__ == "__main__":
    main()
