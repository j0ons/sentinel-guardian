# SENTINEL — Architecture

> **What it is:** a system/network guardian — *not* a camera. Sentinel watches a host's
> **process / network / login** activity (edge SOC), learns each machine's "normal," reasons
> about it with a long-horizon qwen3.7-max agent, and acts on the edge. This document
> describes the system **as built and deployed** — it matches the code in `src/` and `edge/`.

## System overview

```
┌────────────────────────────────────────────────────────────────────┐
│  EDGE  (Raspberry Pi / Proxmox container — runs edge/)              │
│                                                                    │
│   collectors ──► diff ──► event ──► uplink ──► (HTTPS+token)        │
│   (psutil:        (only      (compact   (POST /event                │
│    processes,      changes    JSON: kind, to the cloud brain;       │
│    connections,    become     summary,    buffers to outbox.jsonl   │
│    listeners,      events)    detail)     if offline, replays)      │
│    logins)                                                          │
│                                                                    │
│   ◄── decision (mark_normal / alert_user / actuate) ──┐            │
│        physical signal on the Pi: GPIO LEDs + buzzer  │            │
└───────────────────────────────────────────────────────┼───────────┘
                                                         │
┌──────────────────────────────────────────────────────▼─────────────┐
│  CLOUD  (Qwen Cloud — dashscope-intl, OpenAI-compatible endpoint)    │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐ │
│   │  SENTINEL AGENT — multi-step investigation loop (qwen3.7-max) │ │
│   │  perceive → INVESTIGATE → reason → act → record               │ │
│   │  investigative tools: check_entity, correlate_recent,         │ │
│   │  query_memory  →  terminal: mark_normal / alert_user / actuate│ │
│   │  cheap qwen3.6-flash gate fast-paths obvious-normal events    │ │
│   └──────────┬──────────────────────────────────┬─────────────────┘ │
│              │                                  │                   │
│       ┌──────▼───────┐                  ┌───────▼────────┐          │
│       │  MEMORY      │                  │  SAFETY FLOOR   │          │
│       │  (3-tier)    │                  │  (deterministic)│          │
│       │ • working    │                  │  attack-port /  │          │
│       │   (context)  │                  │  C2 signatures  │          │
│       │ • recall     │                  │  ALWAYS caught, │          │
│       │   (SQLite +  │                  │  never promoted │          │
│       │    embeds)   │                  │  to normal      │          │
│       │ • archival   │                  └─────────────────┘          │
│       │   (JSONL)    │                                               │
│       └──────┬───────┘                                               │
│              │                                                      │
│       ┌──────▼──────────────────────────────────────┐              │
│       │  CONSOLIDATION ("Dreaming") — nightly        │              │
│       │  qwen3.7-max reads the FULL operational      │              │
│       │  history in large context and REWRITES the   │              │
│       │  host's "what is normal here" baseline;      │              │
│       │  promotes routinely-seen entities to normal. │              │
│       │  → the self-improvement loop, the novel core │              │
│       └──────────────────────────────────────────────┘              │
└────────────────────────────────────────────────────────────────────┘
```

A live web dashboard (served by the cloud, published over Tailscale) shows the decision feed,
the agent's investigation traces, the learned baseline, the working-memory gauge, and the
defensive posture in real time.

## Why each piece needs Qwen3.7-max specifically

- **Long-horizon investigation:** for an ambiguous event the agent doesn't answer in one shot
  — it calls investigative tools (`check_entity`, `correlate_recent`) across multiple steps to
  gather evidence, then takes a terminal action. This is the regime qwen3.7-max is trained for,
  and it's what lets Sentinel catch a **novel multi-step attack chain** (unknown process → new
  listener → external egress) that has no single known signature — something a rule engine
  structurally cannot do.
- **Large context for the nightly dream:** consolidation reasons over the deployment's *full
  operational history* in one context (latency is irrelevant once a day) to rewrite the host's
  baseline — not a top-k retrieval. This is where Qwen's large context window genuinely pays off.
- **The consolidation pass itself** is the novelty: a `qwen3.7-max` job that rewrites the
  environment's behavioral model between sessions, so the agent reasons against a sharper
  baseline each day. The same event flips from *alert* (cold) to *normal* (warm) once the host
  is learned — judgment a stateless model can't reproduce.

## Memory design (3-tier)

| Tier | Store | Holds | Lifetime |
|---|---|---|---|
| Working | the agent's context window | recent events, the active baseline, known-normal entities | this decision |
| Recall | SQLite (entities/facts/baselines) + embeddings | searchable past events, known entities, versioned baselines | persistent |
| Archival | flat files (JSONL) | full cold history, immutable audit trail | forever |

Consolidation rewrites the baseline and promotes entities across tiers. SQLite holds structured
facts (entity = `proc:nginx`, `outbound:9000:10.10.10.50`), embeddings back semantic recall,
JSONL is the immutable log. (Code: `src/memory.py`, `src/consolidate.py`.)

## The safety floor (defense in depth)

The learned baseline describes *benign* routine — it is never a license to ignore an attack.
A deterministic floor (`src/safety.py`) guarantees attack-port / reverse-shell / C2 signatures
are **always** treated as threats regardless of how permissive the baseline has become, and the
nightly dream can **never** promote a threat-signature entity to "normal." LLM judgment plus a
hard rule the model can't override — how a real security control is built.

## Edge/cloud split (cost + latency)

- **On-edge, cheap:** `psutil` snapshots of processes/connections/listeners/logins, diffed so
  only *changes* become events (an idle host costs almost nothing). A `qwen3.6-flash` triage
  gate clears obvious-normal known entities without the expensive call.
- **In-cloud, `qwen3.7-max`:** the multi-step reasoning/decision and the nightly consolidation —
  the flagship model only where it matters. Per-decision context is kept small for latency; the
  dream uses the large context.
- **Graceful degradation:** events that can't be sent buffer to `outbox.jsonl` and replay on
  reconnect; the physical edge response (GPIO) and audit trail keep working offline — only cloud
  *reasoning* pauses.

## Tech stack (lean, solo-buildable — as deployed)

- **Language:** Python 3.13.
- **LLM:** OpenAI SDK → `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`. Models:
  `qwen3.7-max` (reason + consolidate), `qwen3.6-flash` (cheap triage), `text-embedding-v4`
  (recall).
- **Edge:** `psutil` collectors; on a Raspberry Pi, `RPi.GPIO` drives LED/buzzer actuation
  (no-op off a Pi, so the same code runs in a container).
- **Storage:** SQLite (WAL) + JSON-encoded embeddings + JSONL archive.
- **Transport / API:** FastAPI; the edge POSTs events (bearer-token auth on mutating routes);
  the dashboard polls read-only `/api/*` + `/feed`.
- **Deployment:** 2-container Proxmox topology (brain + edge) published over Tailscale; nightly
  dream + watchdog as systemd timers.
- **Demo harness:** `edge/demo_activity.py` injects realistic activity (incl. a novel
  `--killchain`); `src/demo_recall.py` shows the cold-vs-warm memory flip.

## Proof-of-Alibaba-Cloud-deployment file

`src/qwen_client.py` — the single file that wraps the dashscope-intl endpoint. Linked directly
in the submission.
