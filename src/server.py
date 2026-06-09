"""
server.py — Sentinel's cloud service (runs on the Mac tonight; a real cloud VM later).

The Pi POSTs perceived events here; the Sentinel agent reasons (qwen3.7-max when live,
SIM/STUB otherwise) and returns the chosen action. Also runs the nightly "dreaming"
consolidation on demand, and serves a live feed of recent decisions for the dashboard.

Run:  uvicorn server:app --host 0.0.0.0 --port 8000        (from the src/ dir)
   or: python server.py
"""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import FastAPI
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


class EventIn(BaseModel):
    kind: str
    summary: str
    detail: dict = {}
    host: str = "edge-0"
    entity: list | None = None         # [name, kind] or null


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


if __name__ == "__main__":
    import uvicorn
    print("Sentinel cloud service starting on http://0.0.0.0:8000")
    print("  mode:", "LIVE qwen3.7-max" if is_live() else "STUB/SIM (no credits yet)")
    uvicorn.run(app, host="0.0.0.0", port=8000)
