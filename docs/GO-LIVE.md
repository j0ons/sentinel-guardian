# GO LIVE — flip Sentinel to real qwen3.7-max (when credits land)

Verified working: a key in `.env` makes the system reach the real Qwen Cloud endpoint
(`dashscope-intl…`, model `qwen3.7-max`). Until then it runs in safe SIM mode.

## The 3 commands (run from your Mac)

```bash
# 1. put your real key into the cloud container's .env
SSHPASS='root@123' sshpass -e ssh root@100.114.4.79 \
  "pct exec 201 -- bash -c 'echo QWEN_API_KEY=sk-YOUR-REAL-KEY > /root/sentinel/.env'"

# 2. switch the service out of SIM mode
SSHPASS='root@123' sshpass -e ssh root@100.114.4.79 \
  "pct exec 201 -- sed -i 's/SENTINEL_SIM=1/SENTINEL_SIM=0/' /etc/systemd/system/sentinel-cloud.service"

# 3. reload + restart
SSHPASS='root@123' sshpass -e ssh root@100.114.4.79 \
  "pct exec 201 -- bash -c 'systemctl daemon-reload && systemctl restart sentinel-cloud'"
```

## Confirm it's live
```bash
SSHPASS='root@123' sshpass -e ssh root@100.114.4.79 \
  "pct exec 201 -- curl -s http://127.0.0.1:8000/health"
# expect:  "mode":"live-qwen3.7-max"
```

That's it. The edge keeps running unchanged; only the brain's reasoning swaps from the
SIM heuristic to real qwen3.7-max judgment over the full 1M-context working memory.

## After going live — capture the demo
1. Let it run / replay a few "days" so the baseline sharpens with real reasoning.
2. Run the dashboard (`src/dashboard.py` pointed at `http://10.10.10.201:8000`) and
   screen-record Sentinel thinking out loud — that's demo asset #2.
3. Run `scripts/demo-replay.sh 6` against the live brain for the falling-false-alarm graph.

## Cost guardrails (already in place)
- `qwen3.6-flash` is wired for cheap perceive/triage; `qwen3.7-max` only for reasoning +
  nightly consolidation. Adjust models in `.env` (QWEN_MODEL_REASON / QWEN_MODEL_FAST).
- Nightly dreaming is one call/day. Per-event reasoning is one call/event — the edge only
  emits events on *change*, so an idle host costs almost nothing.
