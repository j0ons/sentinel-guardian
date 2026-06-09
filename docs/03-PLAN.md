# SENTINEL — 30-Day Build Plan

Deadline **Jul 9, 2:00pm PDT**. Solo build, evenings + weekends. Each week ends at a **gate** — a thing that must demonstrably work before moving on. Cut scope, never the gate.

---

## WEEK 0 — Setup (Days 1–2, June 9–10) — *do today*

- [ ] Register/join hackathon on Devpost (account `j0ons`).
- [ ] Qwen Cloud signup → API key → **submit credit-coupon form** (do FIRST, approval lags).
- [ ] Join Qwen Cloud Discord.
- [ ] Order Raspberry Pi 5 (+ camera, SD card, PSU). ~$80–120.
- [ ] `src/qwen_client.py`: first successful `chat.completions.create` against dashscope-intl. **Print a response.** ← proof-of-deployment file is born.
- [ ] Confirm tool-calling + embeddings work from the OpenAI SDK.

**GATE 0:** a Python script makes a real Qwen3.7-max call and a tool call. Credits requested.

---

## WEEK 1 — Vertical slice (Days 3–9) — *make the whole loop work, tiny*

Goal: end-to-end **perceive → reason → act → record** on the laptop webcam (Pi not needed yet).

- [ ] `edge/perceive.py`: webcam → motion trigger → frame → caption (qwen3.7-plus vision) → compact JSON event.
- [ ] `src/agent.py`: the long-horizon loop. Takes events, holds a working-memory log in context, calls qwen3.7-max with tools, executes the chosen tool.
- [ ] `src/tools.py`: `alert_user`, `mark_normal`, `query_memory`, `escalate` (stub actuate).
- [ ] `src/memory.py`: SQLite + JSONL append. (Vector recall comes Week 2.)
- [ ] Wire it: a person walks past the webcam → event → agent decides "log, normal" or "alert".

**GATE 1:** webcam → agent → a sensible decision, logged to memory. The skeleton is alive.

---

## WEEK 2 — Memory + self-improvement (Days 10–16) — *the moat*

Goal: the part that makes us win — 3-tier memory + the **consolidation loop**.

- [ ] Add recall tier: `text-embedding-v4` + vector index; `query_memory` does real semantic lookup.
- [ ] Entity tracking in SQLite ("the gray cat", "side door", "my car") — agent names and reuses entities.
- [ ] `src/consolidate.py`: nightly pass. qwen3.7-max reads the day's working memory → rewrites the "what's normal here" baseline → promotes/forgets. **Versioned baselines** so we can chart improvement.
- [ ] 1M-context working memory: load full operational history into the decision prompt; measure the difference vs top-k.
- [ ] Metric: track **false-alarm rate over time** — must trend down as baseline sharpens.

**GATE 2:** run the replay harness over "3 simulated days" → false-alarm rate visibly drops. The self-improvement is real and measurable.

---

## WEEK 3 — Edge hardening + Pi + 2nd entry (Days 17–23)

Goal: real hardware, robustness, and spin out entry #2.

- [ ] Flash Pi 5, deploy `edge/` to it, camera working, POSTs events to the cloud FastAPI service.
- [ ] Action path back to edge: `actuate` actually does something visible (LED / buzzer / speaker TTS via cosyvoice).
- [ ] Robustness: reconnects, offline buffering on edge, cost guards (flash vs max routing).
- [ ] **Entry #2 — Sentinel-Mind:** wrap the memory core as a cloud-only "remembers everything across our sessions" personal assistant. Different UI/product, same engine. ~3 days. Ship only if flagship is on track.
- [ ] Start the **blog post** draft from the docs.

**GATE 3:** Pi running the full loop, an action visibly fires on the device. Entry #2 demoable.

---

## WEEK 4 — Polish, demo, submit (Days 24–30, ends Jul 9)

Goal: win the 15% presentation, lock everything, submit with buffer.

- [ ] **Demo video (<3 min):** scripted. Story = "watch it get smarter." Use the replay harness to show a multi-day learning montage + a live Pi moment. (See `04-DEMO.md`.)
- [ ] Architecture diagram (clean export of `01-ARCHITECTURE.md`).
- [ ] README: problem, how it uses Qwen (1M ctx + long-horizon + consolidation), setup, OSS license.
- [ ] Confirm proof-of-deployment link (`src/qwen_client.py`).
- [ ] Finish + publish blog post (separate prize).
- [ ] **Submit by Jul 7** — 2-day buffer before the Jul 9 deadline. Submit entry #2 if ready.

**GATE 4 (Jul 7):** flagship submitted. Everything after is bonus.

---

## Scope-cut order (if behind)

Cut from the bottom up, in this order:
1. Entry #2 (Sentinel-Mind) — drop entirely.
2. Physical actuation on Pi → just an on-screen/alert action.
3. Pi hardware → laptop webcam is fine for the demo.
4. Vision captioning → synthetic/text events only.

**Never cut:** the consolidation loop + the falling-false-alarm metric. That IS the project. If only one thing works on Jul 7, it must be "it measurably gets smarter."

---

## Standing weekly rhythm

- **Mon:** review gate from last week, set the week's 3 must-dos.
- **Wed:** mid-week checkpoint, course-correct.
- **Sun:** demo-to-self — record a 60s clip of current state (also feeds the final video).
