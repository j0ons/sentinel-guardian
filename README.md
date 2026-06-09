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

## Docs

- `docs/00-STRATEGY.md` — why this wins, the multi-entry play, risks.
- `docs/01-ARCHITECTURE.md` — system design, memory tiers, edge/cloud split.
- `docs/03-PLAN.md` — 30-day milestone plan with weekly gates.
- `docs/04-DEMO.md` — video script + submission checklist.

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

Week 1–2 done early. Full loop built & tested offline (SIM mode): edge perception →
cloud agent → tools → 3-tier memory → nightly consolidation. False-alarm rate falls
100%→0% over 6 days, threat caught every day. Pi deployment kit ready (`docs/TONIGHT.md`).
Next: run on the Pi tonight; flip to live qwen3.7-max when credits land.

## License

MIT (see `LICENSE`).
