#!/usr/bin/env bash
# RUN THIS ON THE PI (Raspberry Pi OS / Debian). Installs the edge runner deps.
set -e
echo "== Sentinel edge setup =="
sudo apt-get update -qq
sudo apt-get install -y python3-pip python3-venv git
cd "$(dirname "$0")/.."
python3 -m venv .venv-edge
source .venv-edge/bin/activate
pip install --upgrade pip
pip install psutil requests
echo "== done =="
echo "Now run the edge runner (replace <MAC-IP>):"
echo "  source .venv-edge/bin/activate"
echo "  cd edge && SENTINEL_CLOUD=http://<MAC-IP>:8000 python3 runner.py"
