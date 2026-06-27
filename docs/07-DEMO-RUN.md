# Sentinel — Demo Run Sheet

Exact commands to make the live dashboard come alive for the video. The system is real;
this just gives a quiet host something to guard so decisions stream on camera.

Dashboard: **https://proxmox.YOUR-TAILNET.ts.net:8443/**

## Why the dashboard looks quiet normally

CT202 (the "edge") guards an empty Debian container — ~17 processes, nothing happens, so
~1 real event every 1–2 hours. That's expected: a bare host is a boring thing to watch. For a
compelling demo you want either (a) the edge pointed at a busy machine, or (b) the activity
generator below. Both produce REAL qwen3.7-max decisions — nothing is faked.

## Option A — ambient realism (point the edge at a busy host)

Run the real collector against a machine that actually does things (your Mac, or a workload
CT/VM). On that host:
```bash
SENTINEL_CLOUD=http://10.10.10.201:8000 python3 edge/runner.py
```
Real processes, connections, and logins now populate the dashboard continuously.

## Option B — drive a demo on demand (the activity generator)

From CT202 (or anywhere that can reach the cloud):
```bash
cd /root/sentinel/edge
# fill the dashboard fast with ~20 believable home/lab events:
SENTINEL_CLOUD=http://10.10.10.201:8000 python3 demo_activity.py --burst 20
# OR a steady ambient stream while you narrate (Ctrl-C to stop):
SENTINEL_CLOUD=http://10.10.10.201:8000 python3 demo_activity.py
```

## The money-shot sequence for the video

1. **Open the dashboard**, show the green "LIVE · qwen3.7-max" banner.
2. **Steady stream** running — narrate the feed: events come in, most → ✓ normal, the
   baseline version + known-normal list + context-usage tile updating.
3. **The memory beat** — run the recall demo so the "same event, opposite verdict" lands:
   ```bash
   cd /root/sentinel/src && SENTINEL_SIM=0 python3 demo_recall.py
   ```
4. **The threat** — fire the reverse shell, watch it actuate on the dashboard:
   ```bash
   cd /root/sentinel/edge && SENTINEL_CLOUD=http://10.10.10.201:8000 python3 demo_activity.py --attack
   ```
   (On the Pi this also lights the red LED + buzzer — `docs/06-HARDWARE.md`.)
5. **Architecture slide** (`docs/architecture.png`) + close.

## Reset between takes (optional)

The DB persists. To start a take from a clean slate, snapshot/restore the data dir:
```bash
pct exec 201 -- bash -c 'cp /root/sentinel/data/sentinel.db /root/sentinel/data/sentinel.db.bak'
# ...restore: cp ...db.bak ...db && systemctl restart sentinel-cloud
```
Keep the real history if you'd rather show a host that's genuinely been learning for days —
that's the stronger story (baseline v14, hundreds of events).
