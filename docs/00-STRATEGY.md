# SENTINEL — Hackathon Strategy

> Personal project. Global AI Hackathon Series with Qwen Cloud.
> **Deadline: July 9, 2026 @ 2:00pm PDT.** Today: June 9, 2026 → **30 days.**
>
> ⚠️ **SUPERSEDED in places (this is the original June-9 plan, kept for history).** Two things
> changed: (1) the correct track is **Track 5: EdgeAgent**, not Track 4. (2) The Raspberry Pi is
> the **spine** of the project, not "an upgrade" — Sentinel is an edge device that perceives via
> sensors, reasons via Qwen cloud, and acts locally on its own hardware (GPIO + a real process
> kill). The current source of truth is `docs/05-WRITEUP.md` and the root `README.md`.

---

## 1. The competition (facts that drive every decision)

| Item | Detail |
|---|---|
| Prize / track | **$7,000 cash + $3,000 credits** to the winner of each of 5 tracks |
| Other prizes | 10× Honorable Mention ($500+$500), 10× Blog Award ($500+$500) |
| Field size | ~2,339 participants |
| Required submission | Public GitHub repo (OSS license) · proof-of-Alibaba-Cloud-deployment (link to a code file using the API) · architecture diagram · **<3-min demo video** (YouTube/Vimeo/Youku) · write-up · track ID |
| Multiple entries | **Allowed** — each must be "substantially different" |
| IP | **You keep it.** Sponsor gets non-exclusive license for judging/promo only |

### Judging (each ~equal-ish, these are the levers)
- **Innovation & AI Creativity — 30%** → *sophisticated Qwen API use, novel algorithms*
- **Technical Depth & Engineering — 30%** → *architecture quality, advanced patterns*
- **Problem Value & Impact — 25%** → *real-world relevance, scalability*
- **Presentation & Documentation — 15%** → *demo clarity, diagrams*

**Implication:** 60% of the score is Innovation + Technical Depth. Win those two and you're in contention regardless of polish.

---

## 2. The exploitable edge (why we can win)

Qwen3.7-max's signature capabilities, from research:
- **1,000,000-token native context** (not sliding-window) — 90.4 on MRCR-v2 128k retrieval.
- **Long-horizon agency** — trained for tasks spanning **hundreds to thousands of steps**.
- **Strong tool/function calling**, OpenAI-compatible endpoint.

**The thesis:** Most of 2,339 entries will be chatbots + a bolted-on vector DB. They will NOT build something that *architecturally requires* 1M context and 1000-step autonomy. If our project is **impossible without those features**, we auto-score the 30% "sophisticated Qwen API use" criterion. That is the moat.

---

## 3. The flagship: SENTINEL

**Track 4 (Autopilot Agent)** — with an Edge + Memory core that also showcases Tracks 1 & 5.

> A cheap edge device (Raspberry Pi 5) continuously watches a space/system. A **long-horizon Qwen3.7-max agent** runs perpetual autonomy: **perceive → reason → act → remember → improve.** The 1M context holds the *entire operational history of the deployment* as living working memory, so Sentinel stops re-asking, learns the environment's normal patterns, and makes increasingly accurate decisions over days/weeks — detecting anomalies and self-healing.

**Why it wins on each criterion:**
- *Innovation (30%):* memory that **reorganizes between sessions to improve future decisions** (a "consolidation" pass) — the 2026 frontier (cf. Anthropic "Dreaming", Google Memory Bank). Genuinely needs 1M context.
- *Technical Depth (30%):* edge↔cloud split, long-horizon tool-loop, 3-tier memory (working/recall/archival), self-healing action layer.
- *Problem Value (25%):* a self-improving guardian for a home/lab/small-business is a real, scalable product story.
- *Presentation (15%):* a physical device on camera that visibly "learns" across a multi-day montage is a killer 3-min demo.

**Fuses all 3 of your stated interests:** autonomous systems + edge/IoT + memory.

---

## 4. The "try all" play — done correctly

Not 5 weak entries. **One flagship + one cheap 2nd entry + a blog = 3 prize surfaces from ~1 codebase.**

| # | Entry | Track | Effort | Reuse |
|---|---|---|---|---|
| 1 | **Sentinel** (edge guardian) | 4 — Autopilot | Primary (weeks 1–4) | — |
| 2 | **Sentinel-Mind** (cloud-only memory agent; the memory engine as a standalone "remembers everything across sessions" assistant) | 1 — MemoryAgent | ~3 days, week 4 | Shares the memory core, "substantially different" product/UI |
| 3 | **Blog post** documenting the long-horizon-memory architecture | Blog Award | ~1 day, written *as we build* | The docs in this folder |

Decision gate: only ship entry #2 if #1 is locked by ~Jul 2. Never let the 2nd entry endanger the flagship.

---

## 5. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Can't *prove* multi-day learning in a 3-min video | Build a **time-compression / replay harness** from day 1 — feed weeks of synthetic events fast, record the learning curve. Plan in `04-DEMO.md`. |
| Qwen credits run out (1M-context calls are pricey) | Request hackathon credits via coupon form **today**. Use `qwen3.6-flash` for cheap perceive/triage steps, reserve `qwen3.7-max` for reasoning/consolidation. |
| Pi hardware late/flaky | Phone/webcam fallback path kept working the whole time; Pi is an upgrade, not a dependency. |
| Scope creep | Milestone gates in `03-PLAN.md`. Vertical slice working end-to-end by end of Week 1. |
| "Proof of deployment" ambiguity | Keep one clearly-named file (`src/qwen_client.py`) that obviously calls the Alibaba endpoint; link it directly. |

---

## 6. Immediate actions (today)

1. ✅ Project scaffold created.
2. ⬜ Register on Devpost (already have account `j0ons`) + **join the hackathon**.
3. ⬜ Sign up Qwen Cloud, get API key, **submit credit-coupon form** (5 min, do first — approval takes time).
4. ⬜ Join Qwen Cloud Discord.
5. ⬜ First API call working (`src/qwen_client.py`) — proves endpoint + becomes proof-of-deployment file.
6. ⬜ Order Raspberry Pi 5.
