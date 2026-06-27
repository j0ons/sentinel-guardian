#!/usr/bin/env bash
# =====================================================================
# serve-dashboard.sh — expose the Sentinel watch dashboard over Tailscale.
# RUN FROM YOUR MAC (needs sshpass). One-time; the mapping persists in
# tailscaled.state and survives reboots.
#
#   PVE_HOST=YOUR_PVE_HOST PVE_PASS=YOUR_PVE_PASSWORD ./deploy/serve-dashboard.sh
#
# What it does: tells the Proxmox host's Tailscale to publish
#     https://<host>.<tailnet>.ts.net:8443/   ->   http://10.10.10.201:8000  (CT201, the brain)
#
# This is ADDITIVE: it adds a new HTTPS port (8443) and does NOT touch the
# Command Deck already served on 443. Tailnet-only (not Funnel) — reachable
# from your devices, not the public internet. Auto-provisions its TLS cert.
# =====================================================================
set -euo pipefail

PVE_HOST="${PVE_HOST:-YOUR_PVE_HOST}"
PVE_PASS="${PVE_PASS:-YOUR_PVE_PASSWORD}"
CLOUD_IP="${CLOUD_IP:-10.10.10.201}"   # CT201 sentinel-cloud on vmbr1
PORT="${PORT:-8443}"

command -v sshpass >/dev/null || { echo "ERROR: sshpass not installed (brew install sshpass)"; exit 1; }

echo "==> publishing CT201:8000 on the host's tailnet at :$PORT (additive, tailnet-only)"
SSHPASS="$PVE_PASS" sshpass -e ssh -o StrictHostKeyChecking=accept-new "root@${PVE_HOST}" \
  CLOUD_IP="$CLOUD_IP" PORT="$PORT" 'bash -s' <<'REMOTE'
set -e
# sanity: can the host reach the brain?
if ! curl -sf -m 5 "http://${CLOUD_IP}:8000/health" >/dev/null; then
  echo "WARNING: host can't reach http://${CLOUD_IP}:8000/health — is sentinel-cloud up on CT201?"
  echo "         (run ./deploy/redeploy.sh first). Continuing to set the serve mapping anyway."
fi
# additive serve on a dedicated HTTPS port -> the brain. Does not disturb existing 443 config.
tailscale serve --bg --https="${PORT}" "http://${CLOUD_IP}:8000" >/dev/null 2>&1 || \
  tailscale serve --bg --https=${PORT} http://${CLOUD_IP}:8000   # fallback for older CLI arg style
echo "--- tailscale serve status ---"
tailscale serve status || true
# print the exact URL
NAME=$(tailscale status --json 2>/dev/null | sed -n 's/.*"DNSName": *"\([^"]*\)".*/\1/p' | head -1 | sed 's/\.$//')
if [ -n "$NAME" ]; then
  echo ""
  echo "==> WATCH URL:  https://${NAME}:${PORT}/"
fi
REMOTE

echo ""
echo "==> done. Open the WATCH URL above on any device signed into your tailnet."
echo "    Backend check (from the host):  curl -s http://${CLOUD_IP}:8000/api/overview"
echo "    To remove later:  ssh root@${PVE_HOST} 'tailscale serve --https=${PORT} off'"
