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
# Physical actuation layer (LEDs + buzzer). Harmless if it can't install — gpio.py no-ops.
pip install RPi.GPIO || echo "  (RPi.GPIO not installed — edge runs, LEDs/buzzer disabled)"
echo "== done =="
echo ""
echo "Wiring (BCM pins, see docs/06-HARDWARE.md):"
echo "  GPIO17->GREEN  GPIO27->AMBER  GPIO22->RED (each via ~330Ohm)  GPIO23->BUZZER"
echo "  Test the signals:   cd edge && python3 gpio.py"
echo ""
echo "Now run the edge runner (replace <CLOUD-IP>, e.g. Proxmox CT201 or Mac IP):"
echo "  source .venv-edge/bin/activate"
echo "  cd edge && SENTINEL_CLOUD=http://<CLOUD-IP>:8000 python3 runner.py"
