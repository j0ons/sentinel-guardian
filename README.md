# Sentinel

A self-improving autonomous edge guardian. A Raspberry Pi watches a space; a long-horizon
Qwen3.7-max agent in the cloud perceives, reasons, acts, remembers — and **gets measurably
smarter every night** by consolidating its memory and rewriting its model of "what's normal here."

Built for the **Global AI Hackathon Series with Qwen Cloud** (Track 4: Autopilot Agent).
Personal project · solo build · 30 days.

> Most agents forget. Sentinel sleeps on it and wakes up sharper.

## The idea in one diagram

Edge (Pi) perceives cheaply → Cloud (Qwen3.7-max) reasons over the **full deployment history
in 1M context** → acts on the edge → records to 3-tier memory → a nightly **consolidation pass**
("dreaming") rewrites the behavioral baseline so false alarms trend to zero.

See `docs/01-ARCHITECTURE.md`.

## Why Qwen Cloud

- **1M-token context** holds the entire operational log as living working memory (not top-k retrieval).
- **Long-horizon tool-calling** for perpetual perceive→act autonomy.
- **Nightly consolidation** with qwen3.7-max — the self-improvement loop and the novel core.

## A physical edge device

Sentinel runs on a **Raspberry Pi** and acts on its own hardware: a 3-LED + buzzer status head
on GPIO fires the verdict locally — green (normal), amber (alert), **red + buzzer (threat
actuated)** — with no screen and independent of the network. Off a Pi the GPIO layer is a
silent no-op, so the same edge runner works on a Mac/container too (graceful degradation by
construction). Wiring + BOM: `docs/06-HARDWARE.md`. Privacy model: `docs/02-PRIVACY.md`.

## Docs

- `docs/00-STRATEGY.md` — why this wins, the multi-entry play, risks.
- `docs/01-ARCHITECTURE.md` — system design, memory tiers, edge/cloud split.
- `docs/02-PRIVACY.md` — what stays on the edge, what crosses the wire, retention.
- `docs/04-DEMO.md` — the real memory-recall demo, video script, submission checklist.
- `docs/05-WRITEUP.md` — the Devpost submission write-up.
- `docs/06-HARDWARE.md` — the Pi, GPIO wiring, physical signals.

## Quick start

```
# 1. cloud brain (Mac, terminal 1)
./scripts/start-cloud.sh
# 2. live decision feed (Mac, terminal 2)
./scripts/start-dashboard.sh
# 3. edge agent (Pi):  SENTINEL_CLOUD=http://<mac-ip>:8000 python3 edge/runner.py
# demo graph anytime:  ./scripts/demo-replay.sh 6
```

See `docs/TONIGHT.md` for the full Pi bring-up.

## Status

**LIVE on real qwen3.7-max**, deployed on Proxmox and watchable over Tailscale. Full loop
runs end-to-end: edge perception → cloud agent → tools → 3-tier memory → nightly
consolidation.

The headline demo is **memory-grounded judgment** (`src/demo_recall.py`): the same ambiguous
event (`:9000`) is judged *alert* on a cold host and *normal* once the agent has learned the
host's context — qwen3.7-max recalls it as the restic backup's backend. A genuine reverse
shell (`:4444` Tor exit) is neutralized even on a fully-trusting host, because a deterministic
**safety floor** keeps attack signatures from ever being normalized. See `docs/04-DEMO.md`.

> Note: the earlier "false alarms fall 100%→0%" pitch did **not** reproduce — qwen3.7-max is
> well-calibrated on day 1, so there's no curve to show. Live testing also surfaced (and we
> fixed) a real bug where over-broad consolidation could miss a threat. The honest
> memory-recall story is stronger anyway.

## License

MIT (see `LICENSE`).
