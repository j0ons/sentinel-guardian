#!/usr/bin/env bash
# Run the multi-day learning-curve demo (the money-shot graph). No Pi needed.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
cd src
export SENTINEL_SIM=${SENTINEL_SIM:-1}
exec python replay.py "${1:-6}"
