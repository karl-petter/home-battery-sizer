#!/bin/bash
set -e

USER="${1:-root}"
HOST_ARG="${2:-kp-home.no-ip.org}"
HOST="$USER@$HOST_ARG"
REMOTE_DIR="/config/custom_components/home_battery_sizer"

echo "==> Creating remote directories..."
ssh -o BatchMode=yes "$HOST" "sudo mkdir -p $REMOTE_DIR/translations && sudo chmod 777 $REMOTE_DIR/translations $REMOTE_DIR"

echo "==> Syncing files..."
rsync -av --exclude='__pycache__' --exclude='.DS_Store' \
  custom_components/home_battery_sizer/ \
  "$HOST:$REMOTE_DIR/" || true

echo "==> Done! Now restart HA manually: Settings → System → Restart."
