#!/usr/bin/env bash
# =====================================================================
# redeploy.sh — push latest code + systemd units to the Proxmox CTs.
# RUN FROM YOUR MAC (needs sshpass). Re-runnable any time you change code.
#
#   PVE_HOST=YOUR_PVE_HOST PVE_PASS=YOUR_PVE_PASSWORD ./deploy/redeploy.sh
#
# CT201 sentinel-cloud (10.10.10.201) = brain + nightly dream timer
# CT202 sentinel-edge  (10.10.10.202) = edge collector
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

PVE_HOST="${PVE_HOST:-YOUR_PVE_HOST}"
PVE_PASS="${PVE_PASS:-YOUR_PVE_PASSWORD}"
CLOUD_ID=201
EDGE_ID=202

echo "==> building code tarball"
# Exclude .env: the API key is managed separately on CT201 (never bundle a secret into the
# deploy tarball, and the edge CT never needs it). data/ excluded to preserve live history.
tar --exclude='.venv' --exclude='.venv-edge' --exclude='.git' --exclude='data' \
    --exclude='.env' --exclude='__pycache__' --exclude='*.pyc' -czf /tmp/sentinel-code.tgz .

echo "==> copying to PVE host"
SSHPASS="$PVE_PASS" sshpass -e scp -o StrictHostKeyChecking=accept-new \
    /tmp/sentinel-code.tgz "root@${PVE_HOST}:/tmp/sentinel-code.tgz"

echo "==> pushing + applying on PVE"
SSHPASS="$PVE_PASS" sshpass -e ssh -o StrictHostKeyChecking=accept-new "root@${PVE_HOST}" \
  CLOUD_ID="$CLOUD_ID" EDGE_ID="$EDGE_ID" 'bash -s' <<'REMOTE'
set -e
export LC_ALL=C

for id in "$CLOUD_ID" "$EDGE_ID"; do
  echo "  -- CT $id: unpack code"
  pct exec "$id" -- mkdir -p /root/sentinel
  pct push "$id" /tmp/sentinel-code.tgz /root/sentinel/code.tgz
  pct exec "$id" -- bash -c 'cd /root/sentinel && tar xzf code.tgz && rm -f code.tgz && find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true'
done

echo "  -- CT $CLOUD_ID: install systemd units (cloud + dream + watchdog)"
pct exec "$CLOUD_ID" -- bash -c '
  cp /root/sentinel/deploy/systemd/sentinel-cloud.service    /etc/systemd/system/
  cp /root/sentinel/deploy/systemd/sentinel-dream.service    /etc/systemd/system/
  cp /root/sentinel/deploy/systemd/sentinel-dream.timer      /etc/systemd/system/
  cp /root/sentinel/deploy/systemd/sentinel-watchdog.service /etc/systemd/system/
  cp /root/sentinel/deploy/systemd/sentinel-watchdog.timer   /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable -q sentinel-cloud sentinel-dream.timer sentinel-watchdog.timer
  systemctl restart sentinel-cloud
  systemctl restart sentinel-dream.timer
  systemctl restart sentinel-watchdog.timer
'

echo "  -- CT $EDGE_ID: install systemd unit (edge)"
pct exec "$EDGE_ID" -- bash -c '
  cp /root/sentinel/deploy/systemd/sentinel-edge.service /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable -q sentinel-edge
  systemctl restart sentinel-edge
'

sleep 5
echo "  -- status"
echo -n "     cloud: "; pct exec "$CLOUD_ID" -- systemctl is-active sentinel-cloud
echo -n "     edge : "; pct exec "$EDGE_ID"  -- systemctl is-active sentinel-edge
echo -n "     dream timer next: "; pct exec "$CLOUD_ID" -- bash -c "systemctl list-timers sentinel-dream.timer --no-pager | sed -n 2p | awk '{print \$1, \$2, \$3}'"
REMOTE

echo "==> redeploy complete"
