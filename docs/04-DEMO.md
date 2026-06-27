# SENTINEL — Demo & Submission Playbook

The demo is 15% of the score but it's how judges *feel* the other 85%. The whole video
answers one question: **"can it make a judgment a stateless model can't?"** — because that
is the thing no other entry will show, and it's the honest core of Sentinel.

> ⚠️ Direction note (revised after live testing on qwen3.7-max): the original pitch was a
> falling false-alarm curve (Day 1 = 14 false alarms → Day 7 = 0). **That curve does not
> reproduce honestly** — qwen3.7-max is well-calibrated and correctly judges routine activity
> on day 1, so there is no "false alarms falling" phenomenon to film. Do NOT fake it. The
> real, verified, *stronger* story is **memory-grounded judgment** (below): the same event
> gets opposite verdicts before vs. after the host learns its context, and a hard safety
> floor keeps threats caught even on a fully-trusting host. This is `src/demo_recall.py`.

## The core demo beat (real output, captured live)

Same event — an outbound connection to `10.10.10.50:9000` — judged twice:

| State | Verdict | qwen3.7-max's actual reason |
|---|---|---|
| **COLD** (no baseline) | ⚠️ alert | "…on a host with **no established baseline**… worth human verification." |
| **WARM** (after 3 nights) | ✓ normal | "Matches the **learned baseline** for the **restic backup** utility connecting to its internal REST backend repository. Also in **known-normal entities**." |
| **THREAT** `:4444` Tor exit | ⛔ ACTUATE | "Known Tor exit, port 4444 (classic reverse-shell/C2). Not in baseline. **High-confidence malicious**." |

The model *inferred from accumulated memory* that `:9000` was the backup's REST backend.
A stateless chatbot cannot do this. The threat is still neutralized on the trusting host —
the **safety floor** (attack signatures always win) holds. This is the whole pitch in 3 frames.

## The 3-minute video script (target 2:45)

| Time | Beat | What's on screen |
|---|---|---|
| 0:00–0:20 | **Hook** | The live dashboard (green "LIVE · qwen3.7-max"), feed scrolling. "This is Sentinel. It's been guarding my home lab — and it reasons over everything it has ever seen." |
| 0:20–0:50 | **Problem** | A stateless security model has to be told the rules forever; it has no memory of *your* host. Show it either crying wolf or rubber-stamping. |
| 0:50–1:40 | **THE moment** | Run `demo_recall.py` live. COLD: alerts on the `:9000` backup (it doesn't know the host yet). "Sentinel is dreaming…" → 3 baselines. WARM: the SAME event → **normal**, and read its reason aloud — it recalled the restic backup. **This is the money shot.** |
| 1:40–2:10 | **Safety floor** | Fire the `:4444` reverse shell at the now-trusting host → ⛔ ACTUATE. "A permissive baseline never overrides an attack signature." Defense-in-depth: LLM judgment + a deterministic floor. |
| 2:10–2:40 | **Architecture in 30s** | `docs/architecture.png`. Land the three claims: 1M-context working memory · long-horizon autonomy · nightly consolidation that rewrites the host's normal. |
| 2:40–2:55 | **Close** | "Edge perception, cloud reasoning, memory that improves itself — and never forgets to be paranoid. Built solo in 30 days on Qwen Cloud." |

### Production tips
- Record `demo_recall.py` running live FIRST — it's the riskiest, highest-value asset.
- Show the dashboard (`https://proxmox.YOUR-TAILNET.ts.net:8443/`) for the live/ambient shots.
- Read the model's WARM reason verbatim on camera — "the restic backup utility" lands hard.
- Hard-cap under 3:00. Judges watch hundreds.

## Submission checklist (paste into Devpost)

- [ ] **Track:** Autopilot Agent (Track 4).
- [ ] **Public repo**, OSS license (MIT) present and detectable.
- [ ] **Proof of Alibaba Cloud deployment:** direct link to `src/qwen_client.py` (dashscope-intl).
- [ ] **Architecture diagram:** `docs/architecture.png`.
- [ ] **Demo video** (<3:00) on YouTube, public/unlisted.
- [ ] **Write-up:** problem · solution · how it uses Qwen (1M ctx + long-horizon + consolidation
      + the safety floor) · what's novel.
- [ ] Submit by **Jul 7** (buffer before the Jul 9 deadline).

## Write-up talking points (judges' criteria, mirrored back)

- **Innovation:** "Memory that reorganizes itself nightly so the agent reasons over the full
  deployment history (1M context, not top-k retrieval). The same event flips from *alert* to
  *normal* once the host's context is learned — judgment a stateless model can't reproduce."
- **Technical depth:** edge/cloud split · 3-tier memory · long-horizon tool loop · versioned
  baselines · cost-routed models (flash triage / max reason) · **a deterministic safety floor
  so learned permissiveness never erodes threat detection** (defense-in-depth).
- **Impact:** a self-improving guardian for homes/labs/SMBs; the consolidation + safety-floor
  pattern generalizes to any long-running monitoring agent.
- **Honesty note that *helps*:** we tested the naive "falling curve" pitch, found the model
  too well-calibrated for it to be real, and found+fixed a genuine bug (over-broad
  consolidation could miss a threat). Showing this engineering maturity is itself a signal.
- **One-liner:** *"Most agents forget. Sentinel sleeps on it and wakes up sharper — but never
  forgets to be paranoid."*

## Blog post (separate prize, ~1 day)

Title idea: *"Teaching an Edge Agent to Dream — and Why a Smarter Model Broke My Demo."*
The honest narrative (naive curve → too-smart model → real consolidation bug → safety floor)
is a genuinely good engineering story. Reuse `docs/SESSION-LOG.md`. Submit for the Blog Award.
