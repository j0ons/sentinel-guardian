# TONIGHT — get Sentinel running on the Pi

Everything is built and tested. Tonight is just wiring. ~30–40 min.
You'll have **3 terminals**: two on the Mac (cloud + dashboard), one on the Pi (edge runner).

> Note on credits: until your Qwen key lands, we run in **SIM mode** — a heuristic that
> mimics real qwen3.7-max judgment so the whole system (and the demo) works tonight.
> When credits arrive, one change (below) flips it to real reasoning. Nothing else changes.

---

## Step 1 — Find your Mac's LAN IP (the Pi needs it)
On the Mac:
```
ipconfig getifaddr en0 || ipconfig getifaddr en1
```
Write it down, e.g. `192.168.1.50`. Mac and Pi must be on the **same network**.

## Step 2 — Start the cloud service (Mac, Terminal 1)
```
cd ~/Desktop/sentinel-hackathon
./scripts/start-cloud.sh
```
It prints the LAN IP and serves on port 8000. Leave it running.
Sanity check in a browser: `http://localhost:8000/health` → should show `{"ok":true,...}`.

## Step 3 — Start the live dashboard (Mac, Terminal 2) — the demo view
```
cd ~/Desktop/sentinel-hackathon
./scripts/start-dashboard.sh
```
This is what we screen-record: Sentinel reasoning out loud, color-coded.

## Step 4 — Prep the Pi (Pi terminal, one-time)
Get the project onto the Pi (either `git clone` your repo, or copy the folder via
`scp -r ~/Desktop/sentinel-hackathon pi@<PI-IP>:~/`). Then on the Pi:
```
cd ~/sentinel-hackathon
./scripts/pi-setup.sh
```
Installs Python + `psutil` + `requests` in a Pi-local venv (`.venv-edge`).

## Step 5 — Run the edge agent (Pi terminal)
Replace `<MAC-IP>` with the IP from Step 1:
```
cd ~/sentinel-hackathon
source .venv-edge/bin/activate
cd edge
SENTINEL_CLOUD=http://<MAC-IP>:8000 python3 runner.py
```
The Pi now snapshots itself every 5s, sends changes to the Mac, and prints decisions.
**Watch Terminal 2 (dashboard) on the Mac** — events from the Pi appear live.
On Linux the Pi sees full network connections + listening ports (macOS hides these).

## Step 6 — Trigger a threat (Pi terminal, 2nd tab) — the wow moment
Simulate a reverse-shell-style connection to prove detection:
```
# harmless: opens a short-lived high-port listener the collector will flag
python3 -c "import socket,time; s=socket.socket(); s.bind(('0.0.0.0',4444)); s.listen(); print('listening 4444'); time.sleep(8)"
```
Sentinel should flag/`actuate` on the `:4444` listener while ignoring routine activity.

## Step 7 — Make it dream (Mac, any terminal)
After it's seen normal activity for a bit, run a consolidation pass:
```
curl -s -X POST http://localhost:8000/consolidate | python3 -m json.tool
```
Re-run Step 6 routine activity afterward → fewer false alarms. That's the learning loop, live.

---

## When your Qwen credits land (1–2 days) — flip to real reasoning
1. Put the key in `.env`:
   ```
   cd ~/Desktop/sentinel-hackathon
   printf 'QWEN_API_KEY=sk-your-real-key\n' > .env
   ```
2. Start the cloud WITHOUT sim mode:
   ```
   SENTINEL_SIM=0 ./scripts/start-cloud.sh
   ```
   `health` will now show `mode: live-qwen3.7-max`. Same system, real intelligence.

---

## The demo graph (no Pi needed — run anytime)
```
./scripts/demo-replay.sh 6
```
Shows the false-alarm rate falling 100% → 0% over 6 days while the threat stays caught.
This is the money-shot for the video.

## If something doesn't connect
- Pi can't reach cloud → check both on same Wi-Fi; try `curl http://<MAC-IP>:8000/health` from the Pi.
- macOS firewall may prompt to allow incoming connections to Python — click **Allow**.
- Events buffer to `edge/outbox.jsonl` if the cloud is down, and auto-replay when it returns.
