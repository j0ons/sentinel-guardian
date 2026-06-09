"""
memory.py — Sentinel's 3-tier memory.

  Working   : the recent event log + the active "normal" baseline, fed into the 1M
              context at decision time (assembled here, lives in the prompt).
  Recall    : searchable past — SQLite for structured facts/entities/baselines, plus
              embedding vectors for semantic lookup.
  Archival  : immutable JSONL audit trail of every event and decision, forever.

No LLM is required for storage; embeddings come from qwen_client.embed() (stubbed
until credits land). This whole module runs today with no API key.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from qwen_client import embed

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "sentinel.db")
ARCHIVE_PATH = os.path.join(DATA_DIR, "archive.jsonl")


@dataclass
class Event:
    """One thing Sentinel perceived on the edge."""
    ts: float
    kind: str            # process | connection | log | login | filesystem | ...
    summary: str         # human-readable one-liner
    detail: dict = field(default_factory=dict)
    host: str = "edge-0"

    def to_text(self) -> str:
        return f"[{self.kind}] {self.summary}"


class Memory:
    def __init__(self, db_path: str = DB_PATH, archive_path: str = ARCHIVE_PATH):
        # check_same_thread=False: FastAPI serves from a threadpool; server.py serializes
        # all DB access behind a single lock, so cross-thread reuse is safe here.
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.archive_path = archive_path
        self._init_schema()

    def _init_schema(self):
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, kind TEXT, summary TEXT, detail TEXT, host TEXT,
                embedding TEXT          -- json float list (recall tier)
            );
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,       -- e.g. "outbound:443:api.github.com", "proc:nginx"
                kind TEXT,
                first_seen REAL, last_seen REAL, seen_count INTEGER DEFAULT 1,
                normal INTEGER DEFAULT 0,   -- 1 once consolidation marks it baseline-normal
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS baselines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER, ts REAL, host TEXT,
                model TEXT              -- the consolidated "what's normal here" text
            );
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, event_id INTEGER, action TEXT, reason TEXT, was_false_alarm INTEGER
            );
            """
        )
        self.db.commit()

    # --- write paths --------------------------------------------------------
    def record_event(self, ev: Event) -> int:
        vec = embed([ev.to_text()])[0]
        cur = self.db.execute(
            "INSERT INTO events (ts,kind,summary,detail,host,embedding) VALUES (?,?,?,?,?,?)",
            (ev.ts, ev.kind, ev.summary, json.dumps(ev.detail), ev.host, json.dumps(vec)),
        )
        self.db.commit()
        self._archive({"type": "event", **asdict(ev)})
        return cur.lastrowid

    def touch_entity(self, name: str, kind: str, ts: float):
        row = self.db.execute("SELECT id, seen_count FROM entities WHERE name=?", (name,)).fetchone()
        if row:
            self.db.execute(
                "UPDATE entities SET last_seen=?, seen_count=seen_count+1 WHERE id=?",
                (ts, row["id"]),
            )
        else:
            self.db.execute(
                "INSERT INTO entities (name,kind,first_seen,last_seen) VALUES (?,?,?,?)",
                (name, kind, ts, ts),
            )
        self.db.commit()

    def record_decision(self, event_id: int, action: str, reason: str, ts: float):
        self.db.execute(
            "INSERT INTO decisions (ts,event_id,action,reason,was_false_alarm) VALUES (?,?,?,?,NULL)",
            (ts, event_id, action, reason),
        )
        self.db.commit()
        self._archive({"type": "decision", "event_id": event_id, "action": action,
                       "reason": reason, "ts": ts})

    def save_baseline(self, version: int, model_text: str, host: str = "edge-0"):
        self.db.execute(
            "INSERT INTO baselines (version,ts,host,model) VALUES (?,?,?,?)",
            (version, time.time(), host, model_text),
        )
        self.db.commit()

    # --- read paths (assemble working memory for the 1M context) ------------
    def recent_events(self, limit: int = 50) -> list[Event]:
        rows = self.db.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_event(r) for r in reversed(rows)]

    def current_baseline(self, host: str = "edge-0") -> str:
        row = self.db.execute(
            "SELECT model FROM baselines WHERE host=? ORDER BY version DESC LIMIT 1", (host,)
        ).fetchone()
        return row["model"] if row else "(no baseline yet — everything is unknown)"

    def baseline_version(self, host: str = "edge-0") -> int:
        row = self.db.execute(
            "SELECT MAX(version) v FROM baselines WHERE host=?", (host,)
        ).fetchone()
        return (row["v"] or 0) if row else 0

    def known_normal_entities(self) -> list[str]:
        rows = self.db.execute(
            "SELECT name FROM entities WHERE normal=1 ORDER BY seen_count DESC"
        ).fetchall()
        return [r["name"] for r in rows]

    def search_recall(self, query: str, k: int = 5) -> list[tuple[float, Event]]:
        """Semantic search over past events via cosine similarity on embeddings."""
        qv = embed([query])[0]
        rows = self.db.execute("SELECT * FROM events WHERE embedding IS NOT NULL").fetchall()
        scored = []
        for r in rows:
            vec = json.loads(r["embedding"])
            scored.append((_cosine(qv, vec), self._row_to_event(r)))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]

    # --- helpers ------------------------------------------------------------
    def _row_to_event(self, r: sqlite3.Row) -> Event:
        return Event(ts=r["ts"], kind=r["kind"], summary=r["summary"],
                     detail=json.loads(r["detail"] or "{}"), host=r["host"])

    def _archive(self, obj: dict):
        with open(self.archive_path, "a") as f:
            f.write(json.dumps(obj) + "\n")


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a[:n])) or 1e-9
    nb = math.sqrt(sum(x * x for x in b[:n])) or 1e-9
    return dot / (na * nb)


if __name__ == "__main__":
    m = Memory(db_path=":memory:", archive_path="/tmp/sentinel_test.jsonl")
    eid = m.record_event(Event(ts=time.time(), kind="connection",
                               summary="outbound 443 -> api.github.com"))
    m.touch_entity("outbound:443:api.github.com", "connection", time.time())
    m.record_decision(eid, "mark_normal", "known dev traffic", time.time())
    print("events:", [e.to_text() for e in m.recent_events()])
    print("recall:", [(round(s, 2), e.to_text()) for s, e in m.search_recall("github")])
    print("memory.py OK")
