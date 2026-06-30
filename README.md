# Sentinel

A self-improving autonomous edge guardian — and a **fleet mind** that catches attacks no
single host, no rule engine, and no retrieval system can see. A long-horizon Qwen3.7-max agent
watches a fleet of hosts, investigates multi-step, acts on the edge, and **gets measurably
smarter every night** by consolidating its memory — while auditing its own learning so it can
never be slowly trained to stand down.

Built for the **Global AI Hackathon Series with Qwen Cloud** (Track 5: EdgeAgent).
Personal project · solo build.

> Most agents forget. Sentinel sleeps on it and wakes up sharper — but never forgets to be paranoid.

## The headline: a cross-host APT only the full haystack reveals

One Qwen agent holds an **entire fleet's lifetime in one large context** and catches a slow,
lateral campaign whose individual steps are each benign on their own host:

```
web-01: new ssh source → db-02: pg_dumpall → ci-03: new :8443 listener → nas-04: external egress
```

Each event is correctly `normal` per-host. Only by reasoning over **every host's full timeline
at once** does the campaign appear — and we prove it: the *same* data through a 128k window or
top-k RAG returns CLEAN, because the signal lives in the joint distribution of the whole
haystack. Reproduce in one command: `python src/compare_context.py`.

## What it does, that others can't — proven on the live model

Everything below is measured against the **real qwen3.7-max** agent (re-run it yourself):

- **Fleet Mind** (`src/fleet_mind.py`) — one real qwen3.7-max call correlates a cross-host APT
  across an entire fleet's timeline. Verified live 5/5; CLEAR on a clean fleet.
- **Real-model benchmark** (`src/benchmark_live.py`) — the *actual* agent, scored live:
  **100% recall / 0% false-alarm / 0 missed** over reverse-shell, bind-shell, novel non-signature
  egress, crypto-miner, external-root-login, and C2 scenarios. Every verdict is a Qwen decision.
- **Memory-grounded judgment** (`src/demo_recall.py`) — the same event flips *alert → normal*
  once the host is learned; qwen3.7-max recalls it as the restic backup. A stateless model can't.
- **Boiling-frog meta-defense** (`src/boiling_frog.py`) — a frozen reference baseline audits the
  nightly dream, so a low-and-slow attacker can't train Sentinel to normalize an intrusion.
- **Deterministic safety floor** (`src/safety.py`) — attack signatures are *always* caught.

> Two helper scripts illustrate the *logic* deterministically (no Qwen call) so anyone can
> reason about it offline: `src/compare_context.py` (why full context beats a 128k window and
> RAG on a cross-host APT) and `src/benchmark.py` (the detection rules vs static-rule baselines).
> These are models of the logic; the **live** proofs above are the measurements of the real agent.

**Proof it runs on Qwen Cloud:** `src/verify_qwen.py` (and the captured `docs/proof-of-qwen.txt`)
— the dashscope-intl server echoes back `model=qwen3.7-max` and the model self-identifies as
"Qwen, developed by Alibaba Group's Tongyi Lab."

## Why Qwen Cloud

- **Large native context** holds an entire fleet's operational history as one living working
  memory — the Fleet Mind and nightly dream genuinely need it (proven live, not asserted).
- **Long-horizon, multi-step investigation** — the agent gathers evidence across tools before acting.
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
