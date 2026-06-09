# SENTINEL — Architecture

## System overview

```
┌──────────────────────────────────────────────────────────────────┐
│  EDGE  (Raspberry Pi 5 / phone-webcam fallback)                    │
│                                                                    │
│   sensors ──► perception ──► event ──► uplink                      │
│   (camera,    (cheap local   (compact   (HTTPS to                  │
│    mic, sys    detection +    JSON       cloud agent)              │
│    metrics)    qwen3.6-flash  "what I                              │
│                captioning)    saw")                                │
│                                                                    │
│   ◄── action commands (speak / alert / actuate / log) ──┐         │
└─────────────────────────────────────────────────────────┼─────────┘
                                                           │
┌──────────────────────────────────────────────────────────▼─────────┐
│  CLOUD  (Qwen Cloud — dashscope-intl OpenAI-compatible endpoint)     │
│                                                                      │
│   ┌────────────────────────────────────────────────────────────┐   │
│   │  SENTINEL AGENT  — long-horizon tool loop (qwen3.7-max)     │   │
│   │  perceive → recall → reason → act → record                  │   │
│   └───────────┬───────────────────────────────┬────────────────┘   │
│               │                               │                    │
│        ┌──────▼───────┐               ┌───────▼────────┐           │
│        │  MEMORY      │               │   TOOLS         │           │
│        │  (3-tier)    │               │  (function-call)│           │
│        │              │               │                 │           │
│        │ • working    │               │ • alert_user    │           │
│        │   (1M ctx)   │               │ • actuate(edge) │           │
│        │ • recall     │               │ • query_memory  │           │
│        │   (vector +  │               │ • mark_normal   │           │
│        │    SQL)      │               │ • escalate      │           │
│        │ • archival   │               └─────────────────┘           │
│        └──────┬───────┘                                             │
│               │                                                    │
│        ┌──────▼─────────────────────────────────────┐             │
│        │  CONSOLIDATION ("Dreaming") — async, nightly │             │
│        │  qwen3.7-max reads the day's working memory, │             │
│        │  rewrites the "what is normal here" model,   │             │
│        │  promotes/forgets, updates baselines.        │             │
│        │  → THIS is the self-improvement loop.        │             │
│        └──────────────────────────────────────────────┘             │
└──────────────────────────────────────────────────────────────────┘
```

## Why each piece needs Qwen3.7-max specifically

- **Working memory in 1M context:** the agent's prompt carries the *running operational log* of the deployment (events, prior decisions, the current "normal" model). At decision time it reasons over the whole history, not a top-k retrieval. This is the part that's impossible on a small-context model and the thing judges will notice.
- **Long-horizon loop:** Sentinel runs continuously, hundreds–thousands of perceive→act steps. Matches Qwen3.7-max's training target.
- **Consolidation pass:** the novelty. A nightly `qwen3.7-max` job reads the day, **rewrites the environment's behavioral baseline**, and decides what to remember vs forget. Accuracy improves because the baseline gets sharper — demonstrable as a falling false-alarm rate.

## Memory design (3-tier, per 2026 best practice)

| Tier | Store | Holds | Lifetime |
|---|---|---|---|
| Working | 1M context window | recent events, active "normal" model, open decisions | this session |
| Recall | vector (embeddings) + SQLite (entities/facts) | searchable past events, known entities (people/devices), baselines | persistent |
| Archival | flat files (JSONL) | full cold history, audit trail | forever |

Consolidation moves data Working→Recall→Archival and rewrites the baseline. SQLite for structured facts (entity = "the gray cat", "the side door"), vector for semantic recall, JSONL for the immutable log.

## Edge/cloud split (cost + latency)

- **On-edge, free/cheap:** motion/sound trigger, frame capture, a *first-pass* caption (local model or `qwen3.6-flash`) → emits a compact event. Avoids streaming video to the cloud.
- **In-cloud, `qwen3.7-max`:** only the reasoning/decision and consolidation. Keeps token spend sane while still showcasing the flagship model where it matters.

## Tech stack (lean, solo-buildable)

- **Language:** Python 3.11.
- **LLM:** OpenAI SDK pointed at `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`. Models: `qwen3.7-max` (reason/consolidate), `qwen3.6-flash` (cheap perceive), `text-embedding-v4` (recall), `qwen3.7-plus` (vision captioning).
- **Edge:** Pi 5 + USB/Pi camera; `picamera2` or OpenCV. Fallback: laptop webcam.
- **Storage:** SQLite + a local vector index (e.g. `sqlite-vec` or FAISS) + JSONL.
- **Transport:** simple FastAPI service (cloud) the edge POSTs to; WebSocket or long-poll for action commands back.
- **Demo harness:** a replay engine that injects synthetic event streams at high speed to simulate days of learning.

## Proof-of-Alibaba-Cloud-deployment file

`src/qwen_client.py` — the single file that wraps the dashscope-intl endpoint. We link this directly in the submission. Keep it obvious and well-commented.
