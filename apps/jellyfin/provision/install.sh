#!/bin/bash
set -euo pipefail

MEDIA_PATH="${MEDIA_PATH:-/mnt/media}"
HTTP_PORT="${HTTP_PORT:-8096}"
CACHE_PATH="${CACHE_PATH:-/var/cache/jellyfin}"
HW_ACCEL="${HW_ACCEL:-none}"
TRANSCODE_THREADS="${TRANSCODE_THREADS:-0}"

apt-get update
apt-get install -y curl gnupg

curl -fsSL https://repo.jellyfin.org/install-debuntu.sh | bash

# Create media and cache directories
mkdir -p "$MEDIA_PATH"
mkdir -p "$CACHE_PATH"
chown -R jellyfin:jellyfin "$CACHE_PATH"

# Configure custom port if non-default
if [ "$HTTP_PORT" != "8096" ]; then
  mkdir -p /etc/jellyfin
  cat > /etc/jellyfin/network.xml <<JFEOF
<?xml version="1.0" encoding="utf-8"?>
<NetworkConfiguration>
  <HttpServerPortNumber>${HTTP_PORT}</HttpServerPortNumber>
</NetworkConfiguration>
JFEOF
  chown jellyfin:jellyfin /etc/jellyfin/network.xml
fi

systemctl enable jellyfin
systemctl start jellyfin
echo "Jellyfin installed successfully"
