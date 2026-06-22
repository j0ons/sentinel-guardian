"""
server.py — Sentinel's cloud service (runs on the Mac tonight; a real cloud VM later).

The Pi POSTs perceived events here; the Sentinel agent reasons (qwen3.7-max when live,
SIM/STUB otherwise) and returns the chosen action. Also runs the nightly "dreaming"
consolidation on demand, and serves a live feed of recent decisions for the dashboard.

Run:  uvicorn server:app --host 0.0.0.0 --port 8000        (from the src/ dir)
   or: python server.py
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent import SentinelAgent
from consolidate import consolidate
from memory import Event, Memory
from qwen_client import is_live

app = FastAPI(title="Sentinel", version="1.0")

# Single shared brain for the deployment.
MEMORY = Memory()                      # persists to data/sentinel.db
AGENT = SentinelAgent(MEMORY, host="edge-0")
FEED: deque = deque(maxlen=200)        # recent decisions, for the dashboard
LOCK = threading.Lock()                # agent decisions are serialized
STARTED_AT = time.time()               # process start, for the dashboard's uptime
EDGE = {"last_contact": 0.0}           # last time any edge talked to us (heartbeat or event)

HOST = "edge-0"
EDGE_TIMEOUT = 20.0                    # edge counts as "online" if seen within this (4x the 5s interval)
DASHBOARD_HTML = os.path.join(os.path.dirname(__file__), "dashboard.html")

# Actions that mean "this was flagged as not-normal" (for the alert-share trend).
_ALERTING = ("alert_user", "actuate")


class EventIn(BaseModel):
    kind: str
    summary: str
    detail: dict = {}
    host: str = "edge-0"
    entity: list | None = None         # [name, kind] or null


class PingIn(BaseModel):
    host: str = "edge-0"


@app.get("/health")
def health():
    return {"ok": True, "mode": "live-qwen3.7-max" if is_live() else "stub/sim",
            "baseline_version": MEMORY.baseline_version("edge-0"),
            "known_normal": len(MEMORY.known_normal_entities())}


@app.post("/event")
def ingest(ev: EventIn):
    """Receive one edge event, reason about it, return the action to take.

    Never 500s on a single bad event: any failure degrades to a safe 'alert_user' so the
    edge keeps a clean request/response contract and the deployment stays up unattended.
    """
    EDGE["last_contact"] = time.time()     # an event proves the edge is alive
    event = Event(ts=time.time(), kind=ev.kind, summary=ev.summary,
                  detail=ev.detail, host=ev.host)
    entity = tuple(ev.entity) if ev.entity else None
    try:
        with LOCK:
            out = AGENT.decide(event, entity=entity)
    except Exception as e:
        out = {"event": event.to_text(), "action": "alert_user",
               "reason": f"decision error (safe default): {e}", "result": {"ok": False},
               "live": is_live()}
    record = {"ts": time.time(), **out}
    FEED.append(record)
    return record


@app.post("/consolidate")
def dream(host: str = "edge-0"):
    """Trigger a nightly consolidation pass ('dreaming')."""
    with LOCK:
        result = consolidate(MEMORY, host=host)
    FEED.append({"ts": time.time(), "event": "*** DREAMING ***",
                 "action": "consolidate", "result": result})
    return result


@app.get("/feed")
def feed(since: float = 0.0):
    """Recent decisions newer than `since` (epoch seconds) — powers the dashboard."""
    return {"now": time.time(), "items": [r for r in FEED if r["ts"] > since]}


@app.get("/stats")
def stats():
    """Aggregate counts for quick status."""
    rows = MEMORY.db.execute(
        "SELECT action, COUNT(*) c FROM decisions GROUP BY action").fetchall()
    return {"mode": "live-qwen3.7-max" if is_live() else "stub/sim",
            "baseline_version": MEMORY.baseline_version("edge-0"),
            "known_normal_entities": MEMORY.known_normal_entities(),
            "decisions_by_action": {r["action"]: r["c"] for r in rows}}


# ---------------------------------------------------------------------------
# Dashboard — a read-only watch view. Serves a single self-contained page at /
# plus a small /api/* surface it polls. All read-only: SELECTs only, no LOCK
# (WAL lets reads run concurrently with the serialized writers). Nothing here
# changes Sentinel's behaviour; it only observes the live deployment.
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard_page():
    """The live watch dashboard. Self-contained HTML; safe to edit without a restart."""
    try:
        with open(DASHBOARD_HTML, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse(
            "<h1>Sentinel</h1><p>dashboard.html not deployed next to server.py. "
            "API is up: try <a href='/api/overview'>/api/overview</a>.</p>",
            status_code=200,
        )


@app.get("/api/overview")
def api_overview():
    """One snapshot the dashboard polls every few seconds — everything for the header + tiles."""
    db = MEMORY.db
    by_action = {r["action"]: r["c"] for r in db.execute(
        "SELECT action, COUNT(*) c FROM decisions GROUP BY action").fetchall()}
    total_decisions = sum(by_action.values())
    total_events = db.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]
    last_event_ts = db.execute("SELECT MAX(ts) t FROM events").fetchone()["t"] or 0.0
    last_dream_ts = db.execute(
        "SELECT MAX(ts) t FROM baselines WHERE host=?", (HOST,)).fetchone()["t"] or 0.0
    normals = MEMORY.known_normal_entities()
    now = time.time()
    return {
        "now": now,
        "mode": "live-qwen3.7-max" if is_live() else "stub/sim",
        "live": is_live(),
        "uptime_s": now - STARTED_AT,
        "baseline_version": MEMORY.baseline_version(HOST),
        "known_normal_count": len(normals),
        "known_normal": normals[:40],
        "total_events": total_events,
        "total_decisions": total_decisions,
        "decisions_by_action": by_action,
        "threats_neutralized": by_action.get("actuate", 0),
        "alerts": by_action.get("alert_user", 0),
        "marked_normal": by_action.get("mark_normal", 0),
        "last_event_ts": last_event_ts,
        "last_event_age_s": (now - last_event_ts) if last_event_ts else None,
        "edge_alive": bool(EDGE["last_contact"]) and (now - EDGE["last_contact"]) < EDGE_TIMEOUT,
        "edge_last_contact_s": (now - EDGE["last_contact"]) if EDGE["last_contact"] else None,
        "last_dream_ts": last_dream_ts,
    }


@app.post("/api/edge/ping")
def edge_ping(p: PingIn):
    """Edge heartbeat. The runner calls this every cycle so 'edge online' is true even when
    nothing changed (events are change-driven and can be minutes apart on a quiet host)."""
    EDGE["last_contact"] = time.time()
    return {"ok": True, "live": is_live(),
            "mode": "live-qwen3.7-max" if is_live() else "stub/sim"}


@app.get("/api/series")
def api_series(minutes: int = 120, buckets: int = 60):
    """Decisions bucketed over a recent window, split normal vs alert vs actuate.

    Powers the activity chart and the alert-share trend (the real, live 'is it learning?'
    signal: as the baseline sharpens, the share of alerting decisions falls)."""
    minutes = max(5, min(minutes, 1440))
    buckets = max(6, min(buckets, 240))
    now = time.time()
    span = minutes * 60
    start = now - span
    width = span / buckets
    rows = MEMORY.db.execute(
        "SELECT ts, action FROM decisions WHERE ts >= ? ORDER BY ts", (start,)).fetchall()
    normal = [0] * buckets
    alert = [0] * buckets
    actuate = [0] * buckets
    for r in rows:
        i = int((r["ts"] - start) / width)
        if i < 0 or i >= buckets:
            continue
        a = r["action"]
        if a == "actuate":
            actuate[i] += 1
        elif a in _ALERTING:
            alert[i] += 1
        else:
            normal[i] += 1
    share = []
    for i in range(buckets):
        tot = normal[i] + alert[i] + actuate[i]
        share.append(round((alert[i] + actuate[i]) / tot, 4) if tot else None)
    return {"now": now, "start": start, "bucket_s": width, "buckets": buckets,
            "normal": normal, "alert": alert, "actuate": actuate, "alert_share": share}


@app.get("/api/timeline")
def api_timeline(limit: int = 20):
    """Baseline history — the nightly 'dreaming' passes, newest first. The learning timeline."""
    limit = max(1, min(limit, 200))
    rows = MEMORY.db.execute(
        "SELECT version, ts, model FROM baselines WHERE host=? ORDER BY version DESC LIMIT ?",
        (HOST, limit)).fetchall()
    return {"items": [{"version": r["version"], "ts": r["ts"],
                       "preview": (r["model"] or "")[:240]} for r in rows]}


@app.get("/api/events")
def api_events(limit: int = 60):
    """Recent perceived events from the DB — seeds the feed with history on first load."""
    limit = max(1, min(limit, 300))
    rows = MEMORY.db.execute(
        "SELECT ts, kind, summary, host FROM events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return {"items": [{"ts": r["ts"], "kind": r["kind"], "summary": r["summary"],
                       "host": r["host"]} for r in reversed(rows)]}


if __name__ == "__main__":
    import uvicorn
    print("Sentinel cloud service starting on http://0.0.0.0:8000")
    print("  mode:", "LIVE qwen3.7-max" if is_live() else "STUB/SIM (no credits yet)")
    uvicorn.run(app, host="0.0.0.0", port=8000)
