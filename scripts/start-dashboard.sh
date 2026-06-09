#!/usr/bin/env bash
# Live "thinking out loud" dashboard (run on the Mac, in a 2nd terminal). DEMO ASSET.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
cd src
exec python dashboard.py
