# SENTINEL — Demo & Submission Playbook

The demo is 15% of the score but it's how judges *feel* the other 85%. The whole video must answer one question: **"does it actually get smarter?"** — because that's the thing no other entry will show.

## The 3-minute video script (target 2:45)

| Time | Beat | What's on screen |
|---|---|---|
| 0:00–0:20 | **Hook** | The Pi watching a real space. "This is Sentinel. It's been watching my [lab/home] for a week. It didn't just record — it *learned*." |
| 0:20–0:50 | **Problem** | Normal security/automation: dumb, re-asks, false alarms forever. Show a generic system crying wolf. |
| 0:50–1:30 | **The learning curve** | THE money shot. Replay-harness montage: Day 1 = 14 false alarms. Consolidation runs ("Sentinel is dreaming…"). Day 3 = 2. Day 7 = 0. **Show the falling graph.** Narrate that the baseline is being rewritten by qwen3.7-max each night. |
| 1:30–2:10 | **Live moment** | Real Pi: something happens → Sentinel recalls a named entity ("that's the gray cat again, normal") vs flags a genuine anomaly → fires an action on the device (buzzer/LED/voice). |
| 2:10–2:40 | **Architecture in 30s** | The diagram. Land the three claims: 1M-context working memory · long-horizon autonomy · nightly consolidation. |
| 2:40–2:55 | **Close** | "Edge perception, cloud reasoning, memory that improves itself. Built solo in 30 days on Qwen Cloud." |

### Production tips
- Record the learning montage *first* — it's the riskiest asset. Everything else is easy.
- Screen-record the consolidation log live; "watching it think" is compelling.
- Keep it under 3:00 hard. Judges watch hundreds.

## Submission checklist (paste into Devpost)

- [ ] **Track:** Autopilot Agent (Track 4).
- [ ] **Public repo**, OSS license (MIT) present and detectable.
- [ ] **Proof of Alibaba Cloud deployment:** direct link to `src/qwen_client.py` (calls dashscope-intl).
- [ ] **Architecture diagram** image attached.
- [ ] **Demo video** (<3:00) on YouTube, public/unlisted.
- [ ] **Write-up:** problem · solution · how it uses Qwen (1M ctx + long-horizon + consolidation) · what's novel.
- [ ] Submit by **Jul 7** (buffer).

## Write-up talking points (the judges' criteria, mirrored back)

- **Innovation:** "Memory that reorganizes itself nightly to improve future decisions — needs Qwen3.7-max's 1M context to reason over full deployment history, not top-k retrieval."
- **Technical depth:** edge/cloud split, 3-tier memory, long-horizon tool loop, versioned baselines, cost-routed model usage.
- **Impact:** a self-improving guardian for homes/labs/SMBs; the consolidation pattern generalizes to any long-running monitoring agent.
- **One-liner:** *"Most agents forget. Sentinel sleeps on it and wakes up sharper."*

## Blog post (separate prize, ~1 day)

Title idea: *"Teaching an Edge Agent to Dream: long-horizon memory consolidation on Qwen3.7-max's 1M context."* Reuse these docs. Submit for the Blog Award track.
