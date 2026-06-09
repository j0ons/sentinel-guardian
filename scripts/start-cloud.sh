#!/usr/bin/env bash
# Start the Sentinel cloud service (run on the Mac). Reachable by the Pi on your LAN.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
cd src
# SENTINEL_SIM=1 gives realistic offline judgment until Qwen credits land.
# Once QWEN_API_KEY is in ../.env, REMOVE SENTINEL_SIM to use real qwen3.7-max.
export SENTINEL_SIM=${SENTINEL_SIM:-1}
echo "Starting Sentinel cloud on 0.0.0.0:8000  (SIM=$SENTINEL_SIM)"
echo "Your Mac LAN IP (give this to the Pi):"
ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "  (check System Settings > Network)"
exec python -m uvicorn server:app --host 0.0.0.0 --port 8000
