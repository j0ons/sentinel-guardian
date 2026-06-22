#!/usr/bin/env bash
# watch-live.sh — open the Sentinel watch dashboard and smoke-test it (run on your Mac).
# Assumes deploy/serve-dashboard.sh has been run once.
#
#   ./scripts/watch-live.sh                 # auto-detect tailnet host name
#   WATCH_URL=https://proxmox.tailXXXX.ts.net:8443/ ./scripts/watch-live.sh
set -euo pipefail

PORT="${PORT:-8443}"
URL="${WATCH_URL:-}"

if [ -z "$URL" ]; then
  # find the Proxmox host's MagicDNS name from this Mac's tailscale
  TS="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
  [ -x "$TS" ] || TS="tailscale"
  NAME=$("$TS" status --json 2>/dev/null \
    | sed -n 's/.*"DNSName": *"\([^"]*\)".*/\1/p' \
    | grep -i 'proxmox' | head -1 | sed 's/\.$//') || true
  if [ -z "${NAME:-}" ]; then
    echo "Could not auto-find the proxmox tailnet name. Pass it explicitly:"
    echo "  WATCH_URL=https://proxmox.<your-tailnet>.ts.net:${PORT}/ $0"
    exit 1
  fi
  URL="https://${NAME}:${PORT}/"
fi

echo "==> Sentinel watch: $URL"
echo -n "==> smoke test /api/overview … "
if OV=$(curl -sf -m 8 "${URL%/}/api/overview" 2>/dev/null); then
  MODE=$(printf '%s' "$OV" | sed -n 's/.*"mode": *"\([^"]*\)".*/\1/p')
  BV=$(printf '%s' "$OV" | sed -n 's/.*"baseline_version": *\([0-9]*\).*/\1/p')
  echo "OK  (mode=${MODE:-?}  baseline=v${BV:-?})"
else
  echo "unreachable — has deploy/serve-dashboard.sh been run? Is CT201 up?"
fi

command -v open >/dev/null && open "$URL" || echo "Open it in your browser: $URL"
