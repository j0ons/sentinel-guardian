# Sentinel — Session Log

Running journal of work sessions. Newest entry on top. Every detail captured so the
project can be resumed cold.

---

## 2026-06-23 — Submission assets, a hidden dreaming bug, optimizations, two outages

**Headline:** built the submission deliverables, then a full system checkup uncovered that
the deployed "dreaming" was fake (stub, not Qwen). Fixed that + a cluster of robustness bugs
exposed by trying to watch a busy host. System is now genuinely self-improving and hardened.
Free qwen3.7-max quota ran out mid-session → now on pay-as-you-go from the $40 coupon.

### Submission assets created
- `docs/architecture.svg`/`.png` — submission architecture diagram (edge/cloud, 3-tier
  memory, dreaming core; lands the three Qwen claims). Rendered via rsvg-convert.
- `docs/05-WRITEUP.md` — Devpost write-up mirroring judging criteria (2 placeholder links).
- `docs/02-PRIVACY.md` — privacy/data-handling (change-driven events, tailnet-only, retention).
- `docs/06-HARDWARE.md` — Pi GPIO wiring/BOM (physical-device requirement).
- `edge/gpio.py` — physical actuation (green/amber/red LED + buzzer on the verdict; lazy
  RPi.GPIO import = silent no-op off a Pi). Wired into runner.apply_action.
- `docs/07-DEMO-RUN.md` — recording run-sheet.
- `edge/demo_activity.py` — paced realistic-activity generator for demo fill.

### Track-4 rubric: closed the two gaps (physical device + privacy). All 7 items now met.

### The big bug — dreaming was FAKE in production
- Symptom: every baseline on CT201 was the deterministic `(auto)` stub, not qwen3.7-max.
  The novel core wasn't actually running live.
- Misdirection: NOT the stub fallback. `chat()` returned 211 real chars, is_live=True, the
  fallback condition was correctly False. The MODEL itself was copying the `(auto)` format —
  early SIM baselines fed back as "PREVIOUS BASELINE" taught it to parrot the template. A
  self-reinforcing pollution loop: each stub baseline bred another.
- Fix (`consolidate.py`): prompt forbids copying prior wording / the `(auto)` template,
  demands fresh categorized analysis; strip `(auto)` framing from the prev-baseline shown.
  Verified: prod dream v14 now writes real analysis ("pickup: Postfix daemon, observed 142×").
- Also: CT201 was running STALE code (missing the safety floor too) → redeployed to latest.
- Hardened `qwen_client.chat()` with retry/backoff + explicit error (was silently degrading).
- Deploy hygiene: service SENTINEL_SIM=0 baked in; `.env` excluded from the deploy tarball.

### Optimizations (score-moving)
- **#1 made 1M-context REAL**: agent fed only a fixed 200-event cap (a sliver of the window,
  undercutting the headline claim). Now token-budgeted, pulls full history; context-usage
  stats exposed on `/api/overview` (verified prod: 234/234 events, ~3767 tokens). Demo line:
  "reasoning over its entire N-event history in one context."
- **#2 wired qwen3.6-flash cost-routing**: every event used to hit qwen3.7-max; now a cheap
  flash gate clears obvious-normal known entities, never fast-paths a threat signature.

### Bugs found by pointing the collector at the busy Proxmox host (instead of empty CT202)
- **Latency regression**: feeding full history into EVERY decision pushed one decision to
  ~31s. Fixed — split budget: per-decision SENTINEL_DECISION_TOKENS=8k (fast ~9s),
  consolidation keeps full 200k.
- **IPv6 crash**: connections packed `ip:port:status` and split on `:` corrupted IPv6 addrs
  → crashed every diff cycle on any host with IPv6. Now `|` delimiter.
- **Edge POST timeout** 10s < 9-30s reasoning → raised to 60s (SENTINEL_POST_TIMEOUT).
- **Noise/volume**: busy host floods + wastes tokens → filter (drop TIME_WAIT/loopback,
  prioritize login>listen>external-conn>process, cap SENTINEL_MAX_EVENTS_PER_CYCLE=6).
- Fixed `sentinel-edge.service` StartLimitIntervalSec (wrong section).
- Decision: Proxmox is the real/authentic vantage point but RUN ON-DEMAND for the demo, not
  24/7 (a steady host is quiet anyway + saves coupon). PVE collector staged at
  `/opt/sentinel-edge` (psutil installed via apt).

### Two outages (both fixed)
1. Proxmox host's **Tailscale node drifted offline** (daemon up, control heartbeat stale) →
   dashboard unreachable. Fix: clean `systemctl restart tailscaled`. (My `tailscale up
   --reset` attempt briefly knocked it fully off-tailnet + dropped SSH — mistake; don't use
   --reset. Recurrence one-liner: `ssh root@YOUR_PVE_HOST systemctl restart tailscaled`.)
2. **Self-inflicted "CLOUD OFFLINE"**: watchdog restarted the brain if `/health` didn't
   answer in 8s, but today's slower reasoning (9-30s, holding the global LOCK + saturating
   the sync threadpool) blocked /health → watchdog kept KILLING the busy brain. Fix:
   `/health` now async + dependency-free (answers ~0.001s even mid-reasoning, verified 5/5
   under load); watchdog requires 3 consecutive 30s failures before restart.

### Billing
- Free qwen3.7-max quota EXHAUSTED mid-session → now pay-as-you-go from the $40 coupon
  (verified calls still work → "Stop When Free Quota Used Up" not enabled). Spend tiny
  (~8.9k tokens/decision, est ~2¢ of usage). Don't run the live collector 24/7. Authoritative
  balance: Alibaba console → Expenses → Coupons.

### End state
System live + hardened + genuinely self-improving (real Qwen baselines). Dashboard back up.
Advice given: FREEZE infra, pivot to submission deliverables (GitHub push, video, key
rotation) — none of which touch the live system or burn coupon.

### Still to do (need user)
- Rotate the chat-exposed Qwen key; push to public GitHub (fill 2 links in 05-WRITEUP.md);
  film the <3-min video (money shot = `demo_recall.py`; run Proxmox collector live during
  recording + scripted `demo_activity.py --attack` for the climax). Deadline Jul 9 2pm PDT.

---

## 2026-06-22 — GO LIVE: flipped Sentinel to real qwen3.7-max on Proxmox/Tailscale

**Headline:** Sentinel went from "built but stuck in SIM mode awaiting credits" to
**fully live on real qwen3.7-max, deployed on Proxmox (CT201), watchable over Tailscale.**
The QwenCloud hackathon voucher arrived; this session unblocked the API and shipped it live.

### Starting state (cold open)
- Repo: `/Users/mohamedshanan/Desktop/sentinel-hackathon`, git, 5 commits, HEAD `6ca0303`.
- ~1,395 lines Python across `src/` + `edge/`. Worked end-to-end in **SIM mode**.
- **Uncommitted work on disk since Jun 20** (at risk of loss):
  - `src/dashboard.html` (new, 26 KB self-contained live dashboard)
  - `src/server.py` (+139 lines: `/`, `/api/overview`, `/api/series`, `/api/timeline`,
    `/api/events`, `/api/edge/ping`)
  - `edge/runner.py` (+ `ping_cloud()` heartbeat each cycle)
  - `src/memory.py` (`SENTINEL_DATA_DIR` env override)
  - `docs/GO-LIVE.md` (tailnet "WATCH IT" section)
  - untracked: `deploy/serve-dashboard.sh`, `scripts/watch-live.sh`
- Verified SIM still works: `./scripts/demo-replay.sh 6` → false-alarm 100%→0% over 6
  days, threat caught daily, baseline v1→v6. (Note: imports run from inside `src/`, e.g.
  `cd src && python replay.py` — module-style `python -m src.replay` fails on bare imports.)

### The voucher — what it actually is
- Screenshot from Alibaba Cloud billing console showed: **$40 USD Cash Coupon**,
  Coupon No. **<redacted>**, Balance 40 USD, type "General Use (Exclusions Apply)",
  owner `mohamed.shanan9@gmail.com`.
- **Key realization:** the coupon is NOT an API key. It is account credit that
  auto-applies to pay-as-you-go bills at billing time (confirmed via Alibaba help docs).
  Nothing about the coupon goes into `.env`.
- Org (Discord) sent links: `home.qwencloud.com/benefits/voucher`,
  `billing-cost.console.alibabacloud.com/coupons/coupon`, and the how-to-use-coupons help page.

### The blocker (and the diagnosis trail)
1. First key tried: `sk-ws-<REDACTED>` created in Alibaba **Model Studio, China (Beijing)**
   region. Placed in `.env`. Test against intl endpoint → **401 invalid_api_key**.
2. Key is **region-bound**. Beijing key 401s on `dashscope-intl.aliyuncs.com`.
3. Tried Beijing endpoint (`dashscope.aliyuncs.com/compatible-mode/v1`) → auth PASSED but
   **403 "Access to model denied / make sure you are eligible"** on EVERY model, including
   the always-on `qwen-turbo`. → not a per-model lock; the **whole service is inactive**.
4. Root cause found via screenshot: Alibaba **Account Center → Identity Verification** =
   *"Your request is submitted. Please wait... within 3 business days."* Model Studio
   serves NOTHING until ID verification approves. This is what the "⚠ Some Features
   Restricted" banner meant. Personal Alibaba account was gated.

### The unlock
- Org-provided **Qwen Cloud portal** (`home.qwencloud.com`) issues its OWN API key,
  independent of the Alibaba console / identity verification.
- Second key from Qwen portal: `sk-ws-<REDACTED>`
- Tested → **✅ works on the INTL endpoint** (`dashscope-intl.aliyuncs.com/compatible-mode/v1`):
  `qwen3.7-max`, `qwen3.6-flash`, `qwen-max`, `qwen-turbo` all return `OK`.
  (401s on Beijing endpoint — it's an intl key, which matches the code's default base_url.)
- **This bypassed the 3-day Alibaba verification wait entirely.**

### Actions taken
1. Wrote `scripts/set-key.sh` — pastes key via hidden terminal input (not chat), writes
   `.env`, runs a live health check. (`chmod +x`.)
2. Placed working key in Mac repo `.env` (gitignored, perms 600). `is_live()` → True.
   base_url already `dashscope-intl…`, model `qwen3.7-max` — **no code change needed**.
3. Ran live replay `SENTINEL_SIM=0 python replay.py 3` → **mode: LIVE qwen3.7-max**,
   threat caught 1/1 day 3, dreaming promoted 6 entities to known-normal.
4. Secret-scanned all pending changes (no keys in tracked files), confirmed `.env` is
   gitignored + not staged. **Committed dashboard work** → commit `7f5ef98`
   ("Live watch dashboard + edge heartbeat; verified live on qwen3.7-max").
5. (Briefly started a local Mac uvicorn on :8000 to view dashboard — WRONG, the real
   deployment is Proxmox/Tailscale. Killed it.)

### Proxmox / Tailscale — the real deployment
- Proxmox host: **`YOUR_PVE_HOST`** (tailnet), root password **`YOUR_PVE_PASSWORD`**.
  ⚠️ SSH needs password-only: `-o PreferredAuthentications=password -o PubkeyAuthentication=no`
  (otherwise pubkey attempts exhaust and it returns "Permission denied").
- Containers: CT201 `sentinel-cloud` (brain, `10.10.10.201:8000`), CT202 `sentinel-edge`,
  plus CT102 + CT104 pihole. Edge heartbeats CT201 via `/api/edge/ping`.
- `tailscale serve` on host already published: **`https://proxmox.YOUR-TAILNET.ts.net:8443`
  → `http://10.10.10.201:8000`** (tailnet-only, not public Funnel). Also `/` and `/shell`
  on 443 (the existing Command Deck — untouched).
- Dashboard code was ALREADY deployed on CT201 (`GET /` and `/api/overview` → 200), but
  the brain there was still **`mode: stub/sim`**, baseline v10, 4 known-normal entities.

### The flip (per docs/GO-LIVE.md)
Service unit: `/etc/systemd/system/sentinel-cloud.service`, `WorkingDirectory=/root/sentinel/src`,
`ExecStart=/root/sentinel/.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000`,
had `Environment=SENTINEL_SIM=1`.

1. Wrote `QWEN_API_KEY` to `/root/sentinel/.env` AND `/root/sentinel/src/.env` (chmod 600).
2. `sed -i 's/SENTINEL_SIM=1/SENTINEL_SIM=0/'` on the service unit.
3. `systemctl daemon-reload && systemctl restart sentinel-cloud`.
4. Verified: `curl http://10.10.10.201:8000/health` →
   **`{"ok":true,"mode":"live-qwen3.7-max","baseline_version":10,"known_normal":4}`**.
   Service active, journal shows clean 200s, edge (10.10.10.202) pinging.

### END STATE — ✅ LIVE
| Component | Where | Status |
|---|---|---|
| Brain `sentinel-cloud` | CT201 `10.10.10.201:8000` | **live-qwen3.7-max**, baseline v10 |
| Edge `sentinel-edge` | CT202 (`10.10.10.202`) | heartbeating CT201 |
| Dashboard | served by CT201 `/` | HTTP 200, polling |
| Tailscale serve | host `YOUR_PVE_HOST` :8443 → CT201:8000 | live, tailnet-only |
| Qwen key | CT201 `.env` + Mac repo `.env` | live, intl endpoint |
| Mac repo | commit `7f5ef98` | dashboard committed |

**WATCH URL: https://proxmox.YOUR-TAILNET.ts.net:8443/** — banner flips amber→green
"LIVE · qwen3.7-max" on next poll.

### Open items / next session
1. **🔴 ROTATE KEYS** — two `sk-ws-<REDACTED>` keys were pasted into the chat (the live Qwen one
   + the dead Beijing one). Rotate the live one in the Qwen portal, then re-push to BOTH
   Mac `.env` and CT201 (`/root/sentinel/.env` + `src/.env`) and restart sentinel-cloud.
2. **Redeploy to be safe** — CT201 already serves a working dashboard, but run
   `./deploy/redeploy.sh` to guarantee it matches Mac commit `7f5ef98` exactly.
3. **🔴 DEMO FLATNESS** — real qwen3.7-max judges correctly from day 1, so the false-alarm
   rate starts at 0% and the "watch it learn 100%→0%" money-shot curve is FLAT. Need a
   cold-start tweak (deliberately empty/cold baseline, or a harder set of ambiguous events)
   before recording the <3-min demo video. This is the main thing between now and submission.
4. **Push to public GitHub** — required for submission (OSS license already MIT).
5. Alibaba identity verification will still approve in ~3 days (backup path; not needed now).
6. Hackathon deadline: **July 9, 2026 @ 2:00 pm PDT.** Track 4 (Autopilot Agent).

### Useful commands (verified this session)
```bash
# Local SIM demo (no Pi/cloud): money-shot graph
cd ~/Desktop/sentinel-hackathon && ./scripts/demo-replay.sh 6
# Local live replay
cd src && SENTINEL_SIM=0 python replay.py 3
# SSH to Proxmox (password-only!)
SSHPASS='YOUR_PVE_PASSWORD' sshpass -e ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no root@YOUR_PVE_HOST
# CT201 health
... 'curl -s http://10.10.10.201:8000/health'   # expect mode: live-qwen3.7-max
```
