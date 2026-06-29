# Sentinel — Demo Teleprompter (read this while recording)

A <3-min video. Every command below is VERIFIED working (dry-run 2026-06-29). Read the
**bold narration** out loud; run the `commands` when cued. Target ~2:45.

> SETUP before you hit record:
> - Screen recorder on (QuickTime: File → New Screen Recording, or OBS).
> - Dashboard open in a browser: `https://proxmox.<your-tailnet>.ts.net:8443/?token=<your-token>`
> - One terminal open, with these set:
>   ```
>   export PVE=root@<your-pve-host>          # password: <your-pve-password>
>   export VPY=/root/sentinel/.venv/bin/python   # the venv python (IMPORTANT — plain python3 fails)
>   ```
> - Confirm calm state: dashboard banner GREEN, posture GUARDED, Threats = 0.

---

## ACT 1 — THE FLEET MIND (≈60s) — your #1 differentiator

**"This is Sentinel. It guards a fleet of machines. Watch what it catches that nothing else can."**

Run (live qwen3.7-max — takes ~15-20s, let it think on camera):
```
ssh $PVE "pct exec 201 -- bash -c 'cd /root/sentinel/src && SENTINEL_SIM=0 $VPY fleet_mind.py --demo'"
```
When `CAMPAIGN_DETECTED` + the chain prints, read it:

**"Four events. Four different hosts. Spread across days. Each one — a new login, a database dump,
a new listening port, an outbound connection — is completely normal on its own machine. No
per-host security tool flags any of them. But Sentinel holds the entire fleet's history in one
context, and qwen3.7-max sees what they are together: a single attacker moving laterally —
access, collection, staging, exfil."**

Then the proof it's not luck — run:
```
cd ~/Desktop/sentinel-hackathon/src && python3 compare_context.py
```
When the table prints (full-context YES, 128k NO, RAG NO):

**"The same data through a 128-thousand-token window? It misses it — the early steps fall off the
back. Through retrieval — RAG? It misses it too — no single event ranks as relevant. The attack
only exists in the joint distribution of the whole haystack. This is impossible without Qwen's
large context. That's the headline."**

---

## ACT 2 — THE LIVE KILL (≈50s) — the gasp

**"It doesn't just detect. Watch it act — for real."**

On the dashboard, **click the SAFE → ARMED switch** (it turns red). Say:
**"I'm arming it. Now the response is real, not a drill."**

In the terminal, start a real attacker process on the edge:
```
ssh $PVE "pct exec 202 -- bash -c 'cd /root/sentinel/edge && SENTINEL_ARMED=1 $VPY attacker.py'" &
```
**"That's a real backdoor — a real process, a real listener on port 8443, beaconing out."**

Now trigger the kill-chain so Sentinel sees and reasons about it:
```
ssh $PVE "pct exec 202 -- bash -c 'cd /root/sentinel/edge && SENTINEL_CLOUD=http://10.10.10.201:8000 SENTINEL_TOKEN=<token> SENTINEL_ARMED=1 SENTINEL_DEMO_HOST=homelab-01 $VPY demo_activity.py --killchain'"
```
Watch: the dashboard posture **slams red → UNDER ATTACK**, "KILL-CHAIN NEUTRALIZED" stamps, and in
the attacker terminal **the beacon STOPS** — the process is dead. Say:

**"It correlated the chain, and because it's armed, it killed the actual process. The attacker's
shell just died — mid-beacon. Not a flag. A kill."**

---

## ACT 3 — IT CANNOT BE BOILED (≈40s) — the frontier twist

**"One more thing. A patient attacker doesn't break in loudly — they go slow, hoping the AI learns
to accept them as normal. So Sentinel audits its own learning."**

Run:
```
ssh $PVE "pct exec 201 -- bash -c 'cd /root/sentinel/src && $VPY boiling_frog.py'"
```
When `BASELINE_POISONING` prints:

**"Its nightly learning tried to normalize the intrusion. A frozen reference baseline caught it,
flagged it as baseline-poisoning, and rolled it back. Every self-improving agent can be trained
to stand down. This one notices when it's being trained."**

---

## CLOSE (≈15s)

Show the benchmark (or `docs/benchmark.png`):
```
cd ~/Desktop/sentinel-hackathon/src && python3 benchmark.py
```
**"On 42 attack scenarios: a hundred percent caught, zero false alarms — versus rule engines that
either miss novel attacks or drown you in noise. Edge perception, fleet-wide reasoning, memory
that improves itself — and never forgets to be paranoid. Built solo on Qwen Cloud."**

---

## AFTER RECORDING
1. Trim to <3:00. Upload to YouTube (public or unlisted).
2. Paste the link into `docs/05-WRITEUP.md` (replace `<ADD YOUTUBE URL>`).
3. Submit on Devpost — Track 4 (Autopilot Agent). Proof-of-deployment = `src/qwen_client.py`.

## VERIFIED COMMANDS (cheat sheet — all dry-run 2026-06-29, use the venv python on CT201/CT202)
- Fleet Mind:   `SENTINEL_SIM=0 /root/sentinel/.venv/bin/python fleet_mind.py --demo`  → CAMPAIGN_DETECTED ✓
- Boiling-frog: `/root/sentinel/.venv/bin/python boiling_frog.py`  → BASELINE_POISONING ✓
- Benchmark (Mac): `python3 benchmark.py`  → 100% / 0% / 0 ✓
- Context A/B (Mac): `python3 compare_context.py`  → full YES, 128k NO, RAG NO ✓
- ⚠️ NEVER use plain `python3` on CT201/CT202 — it lacks the deps (no dotenv). Always the venv python.
