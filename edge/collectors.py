"""
collectors.py — Sentinel's edge perception layer.

Runs ON the edge device (Pi or laptop). Watches the host cheaply and emits compact
Event objects — NO LLM here. This is the "sensors" in the architecture diagram, adapted
for the system/network-guardian build: processes, network connections, logins, listening
ports. Designed to run continuously with a low footprint (suitable for a Pi).

Usage:
    from collectors import snapshot, diff_events
    prev = snapshot()
    ...later...
    now = snapshot()
    events = diff_events(prev, now)     # only what CHANGED becomes an event
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field

import psutil


@dataclass
class Event:
    """One thing Sentinel perceived on the edge.

    Defined here (not imported from src.memory) so the edge node stays minimal — it only
    needs psutil + requests, never the cloud's LLM/DB dependencies. The cloud's
    src.memory.Event mirrors this shape; events cross the wire as plain JSON anyway.
    """
    ts: float
    kind: str
    summary: str
    detail: dict = field(default_factory=dict)
    host: str = "edge-0"

    def to_text(self) -> str:
        return f"[{self.kind}] {self.summary}"


HOST = socket.gethostname()


@dataclass
class Snapshot:
    ts: float
    procs: dict           # pid -> name
    conns: set            # "raddr_ip:raddr_port:status"
    listens: set          # "laddr_ip:laddr_port"
    users: set            # logged-in usernames
    meta: dict = field(default_factory=dict)


def snapshot() -> Snapshot:
    """Cheap point-in-time read of the host's security-relevant state."""
    procs = {}
    for p in psutil.process_iter(["pid", "name"]):
        try:
            procs[p.info["pid"]] = p.info["name"] or "?"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    conns, listens = set(), set()
    try:
        for c in psutil.net_connections(kind="inet"):
            if c.status == psutil.CONN_LISTEN and c.laddr:
                listens.add(f"{c.laddr.ip}:{c.laddr.port}")
            elif c.raddr:
                conns.add(f"{c.raddr.ip}:{c.raddr.port}:{c.status}")
    except (psutil.AccessDenied, PermissionError):
        # net_connections needs privileges on macOS; degrade gracefully.
        pass

    users = set()
    try:
        users = {u.name for u in psutil.users()}
    except Exception:
        pass

    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory().percent
    return Snapshot(ts=time.time(), procs=procs, conns=conns, listens=listens,
                    users=users, meta={"cpu": cpu, "mem": mem})


def diff_events(prev: Snapshot, now: Snapshot) -> list[Event]:
    """Turn the delta between two snapshots into discrete events worth reasoning about."""
    events: list[Event] = []

    # New processes
    for pid, name in now.procs.items():
        if pid not in prev.procs:
            events.append(Event(ts=now.ts, kind="process", host=HOST,
                                summary=f"new process started: {name} (pid {pid})",
                                detail={"pid": pid, "name": name}))

    # New outbound connections
    for c in now.conns - prev.conns:
        ip, port, status = c.split(":", 2)
        events.append(Event(ts=now.ts, kind="connection", host=HOST,
                            summary=f"new outbound connection {ip}:{port} ({status})",
                            detail={"ip": ip, "port": int(port), "status": status}))

    # New listening ports (a service started listening — classic anomaly signal)
    for l in now.listens - prev.listens:
        events.append(Event(ts=now.ts, kind="listen", host=HOST,
                            summary=f"new listening port {l}",
                            detail={"addr": l}))

    # New / departed logins
    for u in now.users - prev.users:
        events.append(Event(ts=now.ts, kind="login", host=HOST,
                            summary=f"user logged in: {u}", detail={"user": u}))

    return events


def event_entity(ev: Event) -> tuple[str, str] | None:
    """Canonical entity key for an event, used to track 'have we seen this before'."""
    d = ev.detail
    if ev.kind == "process":
        return (f"proc:{d.get('name')}", "process")
    if ev.kind == "connection":
        return (f"outbound:{d.get('port')}:{d.get('ip')}", "connection")
    if ev.kind == "listen":
        return (f"listen:{d.get('addr')}", "listen")
    if ev.kind == "login":
        return (f"user:{d.get('user')}", "login")
    return None


if __name__ == "__main__":
    print(f"Sentinel collectors on host '{HOST}' — taking two snapshots 2s apart...")
    a = snapshot()
    time.sleep(2)
    b = snapshot()
    evs = diff_events(a, b)
    print(f"baseline: {len(a.procs)} procs, {len(a.conns)} conns, {len(a.listens)} listening")
    print(f"changed in 2s -> {len(evs)} events:")
    for e in evs[:15]:
        print("  -", e.to_text())
    if not evs:
        print("  (no changes — run again or open/close an app to see events)")
