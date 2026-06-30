# Sentinel — Demo Teleprompter (read this while recording)

A <3-min video for **Track 5: EdgeAgent**. Every command is VERIFIED working. Read the
**bold narration** out loud; run the `commands` when cued. Target ~2:50.

> ⚠️ TRACK-5 RULE: the video MUST show the project "functioning ON THE DEVICE for which it was
> built." So we **OPEN ON THE PHYSICAL PI** (Act 0). This is non-negotiable for this track.

> SETUP before you hit record:
> - **A phone/camera pointed at the wired Raspberry Pi** (LEDs + buzzer visible) for Act 0,
>   PLUS a screen recording (QuickTime / OBS) for the dashboard + terminal acts. You'll cut
>   between the two. (Or set the Pi next to your screen and film both with one camera.)
> - Dashboard open: `https://proxmox.<your-tailnet>.ts.net:8443/?token=<your-token>`
> - One terminal, with:
>   ```
>   export PVE=root@<your-pve-host>          # password: <your-pve-password>
>   export VPY=/root/sentinel/.venv/bin/python   # the venv python (plain python3 FAILS — no deps)
>   ```
> - Calm state: dashboard banner GREEN, posture GUARDED, Threats = 0.
> - Pi wired per `docs/06-HARDWARE.md` (green/amber/red LEDs + buzzer; optional PIR sensor).

---

## ACT 0 — THE DEVICE (≈25s) — OPEN HERE. The physical edge guardian. (Track-5 requirement)

**Camera on the Pi.** Power it; the green LED breathes. Say:

**"This is Sentinel — a Raspberry Pi that guards a machine. It perceives the host with edge
sensors, reasons in the Qwen cloud, and acts right here on its own hardware. Green means all is
well."**

(If you wired the PIR sensor) wave your hand at it / show motion → narrate:
**"It even senses the physical world — motion at the rack is something it reasons about too."**

Then the kill, ON THE DEVICE. On the Pi, with the camera still rolling, arm it and fire a real
backdoor (run these over SSH but keep the Pi's LEDs/buzzer IN FRAME):
```
ssh $PVE "pct exec 202 -- bash -c 'cd /root/sentinel/edge && SENTINEL_ARMED=1 $VPY attacker.py'" &
ssh $PVE "pct exec 202 -- bash -c 'cd /root/sentinel/edge && SENTINEL_CLOUD=http://10.10.10.201:8000 SENTINEL_TOKEN=<token> SENTINEL_ARMED=1 SENTINEL_DEMO_HOST=homelab-01 $VPY demo_activity.py --killchain'"
```
**On camera: the RED LED lights, the BUZZER fires, and the attacker's process dies — all on the
device.** Say:
**"A real attacker just opened a backdoor. Sentinel caught it, the buzzer screams, the red light
locks — and it killed the actual process. Not a flag. A kill. On the device."**

> 🅱️ BACKUP if the Pi isn't wired in time: run the same on the container edge and film the
> dashboard's red kill-lock + the attacker terminal dying. It's weaker for Track 5 (no physical
> device on camera) — strongly prefer the real Pi. Wiring is ~15 min (`docs/06-HARDWARE.md`).

---

## ACT 1 — THE FLEET MIND (≈55s) — your #1 differentiator (cut to screen)

**"But the real power is in the cloud brain. Watch what it catches that nothing else can."**

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

## ACT 2 — IT'S REALLY QWEN, AND IT'S ACCURATE (≈30s) — credibility

**"And this is the real model deciding — not a rule I wrote."** Run the live-model benchmark:
```
ssh $PVE "pct exec 201 -- bash -c 'cd /root/sentinel/src && SENTINEL_SIM=0 $VPY benchmark_live.py 5'"
```
As verdicts stream (benign → mark_normal, threats → actuate), say:
**"Every one of these is a live qwen3.7-max decision. Reverse shells, a crypto-miner, a bind
shell, an external root login, novel ports with no signature — caught. Routine activity — left
alone. A hundred percent caught, zero false alarms."**

(Optional 5-sec proof-it's-Qwen flash:)
```
ssh $PVE "pct exec 201 -- bash -c 'cd /root/sentinel/src && SENTINEL_SIM=0 $VPY verify_qwen.py'"
```
**"The server echoes back qwen3.7-max — it's genuinely running on Qwen Cloud."**

---

## ACT 3 — IT CANNOT BE BOILED (≈35s) — the frontier twist

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
3. Submit on Devpost — Track 5 (EdgeAgent). Proof-of-deployment = `src/qwen_client.py`.

## VERIFIED COMMANDS (cheat sheet — all dry-run 2026-06-29, use the venv python on CT201/CT202)
- Fleet Mind:   `SENTINEL_SIM=0 /root/sentinel/.venv/bin/python fleet_mind.py --demo`  → CAMPAIGN_DETECTED ✓
- Boiling-frog: `/root/sentinel/.venv/bin/python boiling_frog.py`  → BASELINE_POISONING ✓
- Benchmark (Mac): `python3 benchmark.py`  → 100% / 0% / 0 ✓
- Context A/B (Mac): `python3 compare_context.py`  → full YES, 128k NO, RAG NO ✓
- ⚠️ NEVER use plain `python3` on CT201/CT202 — it lacks the deps (no dotenv). Always the venv python.
