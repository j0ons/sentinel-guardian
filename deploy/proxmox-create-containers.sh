#!/usr/bin/env bash
# =====================================================================
# RUN THIS ON THE PROXMOX HOST (shell of your Proxmox node, as root).
# Creates two Debian-12 LXC containers on the same bridge:
#   - sentinel-cloud  : runs the brain (server.py + dashboard + memory)
#   - sentinel-edge   : runs the edge collector (treated as the "Pi")
# Idempotent-ish: edit the CTID/IP block if those IDs are taken.
# =====================================================================
set -euo pipefail

# ---- config (change if these collide with existing guests) ----------
CLOUD_ID=201
EDGE_ID=202
BRIDGE=vmbr0                  # your main bridge; check with: brctl show / ip a
STORAGE=local-lvm            # container rootfs storage; check: pvesm status
TEMPLATE_STORE=local         # where templates live
DISK=4                       # GB rootfs
CLOUD_MEM=1024               # MB
EDGE_MEM=512                 # MB (Pi-like)
PASSWORD="sentinel"          # root pw for both CTs (change after)
# Use DHCP by default so it just works on your LAN. For static, see comments below.
NET="name=eth0,bridge=${BRIDGE},ip=dhcp"
# ---------------------------------------------------------------------

TEMPLATE="debian-12-standard_12.7-1_amd64.tar.zst"

echo "==> Ensuring Debian 12 template is present..."
pveam update || true
if ! pveam list "${TEMPLATE_STORE}" | grep -q "${TEMPLATE}"; then
  echo "    downloading ${TEMPLATE}..."
  pveam download "${TEMPLATE_STORE}" "${TEMPLATE}"
fi
TPL="${TEMPLATE_STORE}:vztmpl/${TEMPLATE}"

create_ct () {
  local id=$1 name=$2 mem=$3
  if pct status "$id" >/dev/null 2>&1; then
    echo "==> CT $id ($name) already exists — skipping create."
    return
  fi
  echo "==> Creating CT $id ($name)..."
  pct create "$id" "$TPL" \
    --hostname "$name" \
    --cores 2 --memory "$mem" --swap 256 \
    --rootfs "${STORAGE}:${DISK}" \
    --net0 "$NET" \
    --features nesting=1 \
    --unprivileged 1 \
    --password "$PASSWORD" \
    --onboot 1 \
    --start 1
  echo "    waiting for $name to boot + get an IP..."
  sleep 8
}

create_ct "$CLOUD_ID" sentinel-cloud "$CLOUD_MEM"
create_ct "$EDGE_ID"  sentinel-edge  "$EDGE_MEM"

echo
echo "==> Container IPs:"
for id in "$CLOUD_ID" "$EDGE_ID"; do
  ip=$(pct exec "$id" -- bash -c "hostname -I 2>/dev/null | awk '{print \$1}'" || echo "?")
  name=$(pct config "$id" | awk -F': ' '/^hostname/{print $2}')
  echo "    CT $id  $name  ->  ${ip:-<no ip yet>}"
done
echo
echo "Next:"
echo "  1) Push the code tarball into each CT (from your Mac, see deploy/README.md)."
echo "  2) In sentinel-cloud:  bash /root/sentinel/deploy/bootstrap-cloud.sh"
echo "  3) In sentinel-edge :  SENTINEL_CLOUD=http://<cloud-ip>:8000 bash /root/sentinel/deploy/bootstrap-edge.sh"
