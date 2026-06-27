"""
attacker.py — a REAL adversary for the Live Kill demo. (Runs on the edge host.)

This is not a simulation: it spawns a genuine backdoor process — an actual listener on a
non-signature port (8443) plus a beaconing loop — that holds a real PID and a real socket.
Sentinel perceives it via the normal collector path (a new process + a new listener + outbound
egress = a kill-chain), reasons about it, and when the host is ARMED, `actuate` issues a real
SIGTERM that terminates THIS process. On camera: the attacker's shell dies mid-beacon.

It prints its own PID and a heartbeat so you can SEE it alive, then SEE it die.

Run on the edge host:  python3 attacker.py
Stop manually:         Ctrl-C  (or let Sentinel kill it)
"""
from __future__ import annotations

import os
import socket
import sys
import time

PORT = int(os.getenv("ATTACKER_PORT", "8443"))
BEACON = os.getenv("ATTACKER_C2", "203.0.113.66")  # the "C2" the beacon pretends to reach


def main():
    pid = os.getpid()
    print(f"[attacker] backdoor live — PID {pid}, opening listener on 0.0.0.0:{PORT}")
    print(f"[attacker] (Sentinel should detect the chain and, if ARMED, kill this PID)")

    # a real listening socket on the non-signature port — the chain's "staging" step
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("0.0.0.0", PORT))
        srv.listen(1)
        srv.settimeout(1.0)
    except OSError as e:
        print(f"[attacker] couldn't bind :{PORT} ({e}); continuing with beacon only")

    # beacon loop — prints a heartbeat so the demo shows it ALIVE until Sentinel kills it
    n = 0
    while True:
        n += 1
        # a real (best-effort) outbound connection attempt = the egress step of the chain
        try:
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.settimeout(0.4)
            c.connect_ex((BEACON, PORT))
            c.close()
        except Exception:
            pass
        print(f"[attacker] beacon #{n} → {BEACON}:{PORT}  (PID {pid} still alive)", flush=True)
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[attacker] stopped by hand.")
        sys.exit(0)
