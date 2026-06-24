# Sentinel — Submission Write-up

> **Track 4 — Autopilot Agent** · Global AI Hackathon Series with Qwen Cloud · solo build, 30 days
> Repo: <ADD PUBLIC GITHUB URL> · Demo video: <ADD YOUTUBE URL>
> Proof of Alibaba Cloud deployment: [`src/qwen_client.py`](../src/qwen_client.py) — wraps the
> `dashscope-intl` OpenAI-compatible endpoint, models `qwen3.7-max` / `qwen3.6-flash`.

*Paste this into Devpost. Replace the two `<ADD …>` links before submitting. There's a short
version at the bottom if a field has a tight character limit.*

---

## One line

**Most agents forget. Sentinel sleeps on it and wakes up sharper — but never forgets to be paranoid.**

A self-improving edge security guardian: a cheap always-on device watches a host's process,
network, and login activity; a long-horizon **qwen3.7-max** agent in the cloud reasons over
the *entire* operational history in 1M context, acts on the edge, and every night
**consolidates its memory** — rewriting its model of "what's normal on this host" so its
judgment keeps improving. A deterministic safety floor guarantees attack signatures are never
normalized away.

## The problem

Security and monitoring agents are stateless. They judge each event with no memory of *your*
specific machine, so they either cry wolf at routine activity or need humans to hand-write
rules forever. Bolting a vector DB onto a chatbot gives you top-k retrieval — fuzzy snippets,
not a coherent, evolving model of a host. Nobody's home/lab/SMB server gets a guardian that
actually *learns the place*.

## What Sentinel does (and why it needs Qwen)

**The core capability — memory-grounded judgment.** The same ambiguous event gets opposite,
correct verdicts depending on what the agent has learned. Captured live from `qwen3.7-max`:

- **Cold host**, outbound connection to `10.10.10.50:9000`:
  → ⚠️ *alert* — "…on a host with **no established baseline**… worth human verification."
- **Warm host** (after 3 nights of consolidation), the **same** `:9000` connection:
  → ✓ *normal* — "Matches the **learned baseline** for the **restic backup** utility
    connecting to its internal REST backend repository. Also in known-normal entities."

The model *inferred from accumulated memory* that `:9000` is the backup's backend. That is a
judgment a stateless model structurally cannot make — and it's why this needs Qwen specifically:

- **Large native context for the nightly "dream"** — the consolidation pass reasons over the
  deployment's *full operational history* (thousands of events) in one context to rewrite the
  host's behavioural baseline; this is where Qwen's large context window is genuinely exploited
  (latency is irrelevant once a day). Per-event decisions use a focused recent window for speed,
  grounded against that model-written baseline — not a top-k vector retrieval.
- **Long-horizon agency** — Sentinel runs a continuous perceive → recall → reason → act →
  record loop across hundreds–thousands of steps, the regime qwen3.7-max is trained for.
- **Nightly consolidation ("dreaming")** — a qwen3.7-max pass reads the day's working memory
  and **rewrites the host's behavioral baseline**, promoting routinely-seen entities to
  known-normal. This self-reorganizing memory is the novel core.

## What's novel

Memory that **reorganizes itself between sessions to make future decisions better** — versioned,
host-specific baselines authored by the model from its own full history. This is the 2026
frontier (cf. memory-consolidation / "dreaming" research), realized as a working autonomous
guardian rather than a chat assistant.

## Engineering depth (and an honest finding)

- **Edge/cloud split** — change-driven perception on the edge (cheap, `qwen3.6-flash` triage),
  reasoning + consolidation in the cloud (`qwen3.7-max`). Idle hosts cost almost nothing.
- **3-tier memory** — working (1M context) · recall (SQLite entities/facts + embeddings) ·
  archival (immutable JSONL audit trail). Consolidation moves and rewrites across tiers.
- **Long-horizon tool loop** — function-calling over `mark_normal` / `alert_user` /
  `actuate` (kill process / block IP, safe-by-default) / `query_memory`.
- **A deterministic safety floor — defense in depth.** While building the cold-start demo I
  discovered a real failure mode: after several nights of "everything here is normal,"
  over-broad consolidation could let a reverse shell slip through (threat caught 0/1 on day 5).
  Fix: attack signatures (reverse-shell/C2 ports, known-bad destinations, shell-spawning
  egress) are a **non-negotiable floor** — always caught regardless of the learned baseline,
  and the dreaming pass can never promote a threat-signature entity to normal. After the fix,
  the threat is caught **1/1 on every day**. LLM judgment *plus* a hard rule the model can't
  override — exactly how a real security control should be built.
- **Production deployment** — runs live on a Proxmox 2-container topology (brain + edge),
  published over Tailscale with a live web dashboard (mode banner, decision feed, learned
  baseline, known-normal entities, threats neutralized).

> Note on rigor: the project's first pitch was a falling false-alarm curve. Live testing
> showed qwen3.7-max is too well-calibrated for that to be a real phenomenon, so I did **not**
> stage it — I pivoted to the memory-recall demonstration, which is both honest and a stronger
> proof of the thesis. The bug-find-and-fix above came out of that same testing.

## Impact

A self-improving guardian for homes, labs, and small businesses — the people who can't afford
a SOC. The consolidation + safety-floor pattern generalizes to **any** long-running monitoring
agent (infrastructure, IoT fleets, application logs): learn the environment's normal, keep
getting sharper, never normalize an attack.

## Why it beats a static rule engine (the impact, quantified)

A signature/rule engine (Suricata/CrowdSec-style) can only match what it has a rule for, has no
memory of *your* host, and cannot correlate events into a chain — so it faces an unwinnable
trade-off. On the same 12-event stream (8 benign home/lab events + 2 threat incidents: a novel
kill-chain on port 8443 with no signature, and a classic `:4444` reverse shell):

| Detector | False alarms | Threats missed | Caught |
|---|---|---|---|
| Static rules — tight signatures | 0 | 1 | 1/2 — **misses the novel chain** |
| Static rules — loose heuristics | 3 | 0 | 2/2 — **but false-positive storm** |
| **Sentinel** (baseline + correlation) | **0** | **0** | **2/2** |

Tight rules stay quiet but miss anything novel; loose rules catch more but storm false alarms
on normal host activity. Sentinel wins both axes — it learned this host (so backups to odd
internal ports are normal) **and** correlated the kill-chain (unknown process → new listener →
external egress) that no single signature covers. Reproduce: `cd src && python compare_rules.py`.

## How it uses Alibaba Cloud / Qwen

OpenAI SDK pointed at `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`.
`qwen3.7-max` for reasoning + nightly consolidation; `qwen3.6-flash` for cheap edge triage;
`text-embedding-v4` for recall. Single proof-of-deployment file: `src/qwen_client.py`.

## Try it

```bash
# the money shot — memory-grounded judgment, live
cd src && SENTINEL_SIM=0 python demo_recall.py
# cold-start replay (threat caught every day)
cd src && SENTINEL_SIM=0 python demo_scenario.py 5
# live dashboard (deployed): https://<your-tailnet>.ts.net:8443/
```

---

### Short version (for tight character limits)

Sentinel is a self-improving edge security guardian on Qwen Cloud. An always-on device watches
a host; a long-horizon **qwen3.7-max** agent reasons over the *entire* operational history in
1M context, acts on the edge, and every night **consolidates its memory** — rewriting its model
of "what's normal here." Result: the same event flips from *alert* to *normal* once the host's
context is learned (the model recalls a `:9000` connection as the restic backup's backend) —
judgment a stateless model can't make. A deterministic safety floor guarantees attack
signatures (e.g. a `:4444` reverse shell to a Tor exit) are caught even on a fully-trusting
host. Live on a Proxmox/Tailscale deployment with a web dashboard. Needs Qwen's 1M context +
long-horizon tool-calling by design. Track 4. Proof: `src/qwen_client.py`.
```
```
