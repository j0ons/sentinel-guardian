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

import os
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
            # Pack with '|' (never appears in an IP/port) so IPv6 addresses — which contain
            # colons — round-trip cleanly. A ':' delimiter broke parsing on hosts with IPv6.
            if c.status == psutil.CONN_LISTEN and c.laddr:
                listens.add(f"{c.laddr.ip}|{c.laddr.port}")
            elif c.raddr:
                conns.add(f"{c.raddr.ip}|{c.raddr.port}|{c.status}")
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


# Noise control. A busy host (e.g. a Proxmox node) emits far more raw deltas than deep
# per-event reasoning can keep up with — and every event reasoned costs tokens. A guardian
# should focus on security-relevant signal, not transient churn. So we (1) drop noise,
# (2) prioritise the interesting kinds, and (3) cap events per cycle. Tunables via env.
MAX_EVENTS_PER_CYCLE = int(os.getenv("SENTINEL_MAX_EVENTS_PER_CYCLE", "6"))
_NOISE_STATUSES = {"TIME_WAIT", "CLOSE_WAIT", "LAST_ACK", "FIN_WAIT1", "FIN_WAIT2", "CLOSING"}
_LOOPBACK_PREFIXES = ("127.", "::1")
# Higher = more security-interesting → reasoned first when we have to cap.
_KIND_PRIORITY = {"login": 0, "listen": 1, "connection": 2, "process": 3}


def _is_noise_conn(ip: str, status: str) -> bool:
    """Transient/loopback connections that aren't worth a reasoning call."""
    if status in _NOISE_STATUSES:
        return True
    if ip.startswith(_LOOPBACK_PREFIXES) or ip in ("0.0.0.0", "::", ""):
        return True
    return False


def _is_external(ip: str) -> bool:
    """Rough 'leaves the local network' test — external egress is more interesting."""
    return not (ip.startswith(("10.", "192.168.", "172.", "127.", "169.254.", "fe80", "::1"))
                or ip in ("0.0.0.0", "::", ""))


def diff_events(prev: Snapshot, now: Snapshot) -> list[Event]:
    """Turn the delta between two snapshots into discrete, security-relevant events.

    Filters noise and caps volume so deep reasoning (and token spend) stays bounded on a
    busy host. The cap keeps the highest-signal events (logins > new listeners > external
    connections > new processes) and drops the transient tail."""
    events: list[Event] = []

    # New processes
    for pid, name in now.procs.items():
        if pid not in prev.procs:
            events.append(Event(ts=now.ts, kind="process", host=HOST,
                                summary=f"new process started: {name} (pid {pid})",
                                detail={"pid": pid, "name": name}))

    # New outbound connections (skip transient/loopback noise)
    for c in now.conns - prev.conns:
        ip, port, status = c.split("|", 2)
        if _is_noise_conn(ip, status):
            continue
        port_i = int(port) if port.isdigit() else 0
        events.append(Event(ts=now.ts, kind="connection", host=HOST,
                            summary=f"new outbound connection {ip}:{port} ({status})",
                            detail={"ip": ip, "port": port_i, "status": status,
                                    "external": _is_external(ip)}))

    # New listening ports (a service started listening — classic anomaly signal)
    for l in now.listens - prev.listens:
        ip, _, port = l.rpartition("|")
        events.append(Event(ts=now.ts, kind="listen", host=HOST,
                            summary=f"new listening port {ip}:{port}",
                            detail={"addr": f"{ip}:{port}", "ip": ip, "port": port}))

    # New / departed logins
    for u in now.users - prev.users:
        events.append(Event(ts=now.ts, kind="login", host=HOST,
                            summary=f"user logged in: {u}", detail={"user": u}))

    # Prioritise by security interest, then external-first within connections, and cap volume.
    def _rank(e: Event) -> tuple:
        return (_KIND_PRIORITY.get(e.kind, 9), 0 if e.detail.get("external") else 1)
    events.sort(key=_rank)
    return events[:MAX_EVENTS_PER_CYCLE]


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
