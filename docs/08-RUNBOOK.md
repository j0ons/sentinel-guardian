# Sentinel — Demo-Day Runbook

The exact sequence to film the <3-min video. The system is FROZEN and verified demo-ready
(2026-06-24). Don't change code before filming — just run these commands.

## Before you hit record

1. **Open the dashboard** (with the operator token so the ARM switch + verdict buttons work):
   ```
   https://proxmox.tail7b566b.ts.net:8443/?token=<SENTINEL_TOKEN>
   ```
   Token is in `/tmp/sentinel_token.txt` on your Mac. Without `?token=` the page still works
   for viewing, but Arm/verdict actions no-op with a toast.

2. **Confirm the calm "before" state:** banner GREEN `LIVE · qwen3.7-max`, posture spine
   `GUARDED · all quiet`, voice line "All quiet…", Threats stopped = **0**, a learned
   baseline (v1+), working-memory gauge showing a small fill. If Threats ≠ 0, run the reset
   (bottom of this doc) before filming.

3. **Two terminals ready** on your Mac, each with the token exported:
   ```
   export TOK=$(cat /tmp/sentinel_token.txt)
   export PVE=root@100.114.4.79          # password: root@123
   ```

## The shot sequence (≈2:45)

**[0:00–0:30] Establish — the living, calm watch.**
Show the dashboard at rest: GUARDED spine breathing, the first-person voice, the 1M
working-memory gauge, the heartbeat line, baseline version. Narrate: *"This is Sentinel —
it's been guarding my home-lab host, learning what's normal, reasoning over its whole memory."*

**[0:30–1:00] Memory money-shot (it's not a classifier).**
Run the cold-vs-warm recall demo in a terminal:
```
ssh $PVE "pct exec 201 -- bash -c 'cd /root/sentinel/src && SENTINEL_SIM=0 python3 demo_recall.py'"
```
Read the result aloud: the SAME `:9000` connection is **ALERT when cold**, **NORMAL when warm**
("…the restic backup utility connecting to its internal REST backend…"). No stateless model
can do that.

**[1:00–1:20] The operator takes command (raise the stakes).**
On camera, click the **SAFE → ARMED** switch in the dashboard header. It turns red.
Narrate: *"I'm arming it — the next threat won't be a drill."*

**[1:20–1:50] THE KILL (the gasp).**
Fire the novel kill-chain (port 8443, no signature) from a terminal:
```
ssh $PVE "cd /opt/sentinel-edge && SENTINEL_CLOUD=http://10.10.10.201:8000 SENTINEL_TOKEN=$TOK SENTINEL_DEMO_HOST=homelab-01 python3 demo_activity.py --killchain"
```
Watch the dashboard: the spine **SLAMS** to red `UNDER ATTACK`, the screen flashes, the radar
locks a reticle, the `KILL-CHAIN NEUTRALIZED` stamp punches in with the target, "Threats
stopped" ticks 0→1, the voice rewrites to *"I just caught an intrusion…"*.
(Each chain event takes ~10–30s to reason; the strike lands on the 2nd/3rd event. Be patient
on camera — the investigation IS the story.)

**[1:50–2:10] The believer's payoff (drill into the evidence).**
Click the red ACTUATE row in the feed → the evidence drawer slides open showing the
investigation steps WITH observations (`correlate_recent` returning the literal 3-event chain,
`check_entity` showing UNTRUSTED). Narrate: *"It didn't pattern-match — it correlated a chain
across events. That's what a rule engine can't do."* Optionally click CONFIRM THREAT.

**[2:10–2:35] Architecture + the proof.**
Show `docs/architecture.png`. Land the three claims: large-context nightly dream that rewrites
normal, multi-step investigation, the safety floor. Optionally flash the `compare_rules.py`
table (Sentinel 0 false-alarms / 0 missed vs rules that miss-or-storm).

**[2:35–2:50] Resolve.**
Back to the dashboard: spine eases to green `THREAT NEUTRALIZED → host secured`, then back to
calm GUARDED, breathing. *"Edge perception, cloud reasoning, memory that improves itself — and
never forgets to be paranoid. Built solo on Qwen Cloud."*

## Reset to a clean slate (only if needed before filming)

```
ssh $PVE "pct exec 201 -- bash -c 'cd /root/sentinel/data && cp sentinel.db sentinel.db.bak-\$(date +%s); systemctl stop sentinel-cloud && rm -f sentinel.db sentinel.db-wal sentinel.db-shm archive.jsonl && systemctl start sentinel-cloud'"
sleep 4
# seed a calm learned baseline:
ssh $PVE "cd /opt/sentinel-edge && SENTINEL_CLOUD=http://10.10.10.201:8000 SENTINEL_TOKEN=$TOK SENTINEL_DEMO_HOST=homelab-01 python3 demo_activity.py --burst 8"
ssh $PVE "curl -s -X POST -H 'Authorization: Bearer $TOK' http://10.10.10.201:8000/consolidate >/dev/null"
# then DISARM so the demo starts SAFE:
ssh $PVE "echo '{\"armed\":false}' >/tmp/d.json; curl -s -X POST -H 'Authorization: Bearer $TOK' -H 'Content-Type: application/json' --data @/tmp/d.json http://10.10.10.201:8000/api/posture"
```

## If the dashboard ever shows CLOUD OFFLINE
The Proxmox host's Tailscale node occasionally drifts offline. One-liner fix:
```
ssh $PVE "systemctl restart tailscaled"      # NOT 'tailscale up --reset'
```

## Health one-liner (sanity before filming)
```
ssh $PVE "curl -s http://10.10.10.201:8000/api/overview" | python3 -m json.tool | grep -E 'mode|baseline|threats|armed|edge_alive'
```
