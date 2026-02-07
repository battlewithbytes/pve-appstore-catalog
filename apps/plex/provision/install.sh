#!/bin/bash
set -euo pipefail

MEDIA_PATH="${MEDIA_PATH:-/mnt/media}"
TRANSCODE_PATH="${TRANSCODE_PATH:-/tmp/plex-transcode}"
HTTP_PORT="${HTTP_PORT:-32400}"
FRIENDLY_NAME="${FRIENDLY_NAME:-Proxmox Plex}"

apt-get update
apt-get install -y curl

curl -fsSL https://downloads.plex.tv/plex-keys/PlexSign.key | gpg --dearmor -o /usr/share/keyrings/plex-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/plex-archive-keyring.gpg] https://downloads.plex.tv/repo/deb public main" > /etc/apt/sources.list.d/plexmediaserver.list
apt-get update
apt-get install -y plexmediaserver

# Create media and transcode directories
mkdir -p "$MEDIA_PATH"
mkdir -p "$TRANSCODE_PATH"
chown -R plex:plex "$TRANSCODE_PATH"

# Configure Plex preferences
PLEX_PREFS="/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Preferences.xml"
mkdir -p "$(dirname "$PLEX_PREFS")"

PREFS_ATTRS="FriendlyName=\"${FRIENDLY_NAME}\" ManualPortMappingPort=\"${HTTP_PORT}\" customConnections=\"http://$(hostname -I | awk '{print $1}'):${HTTP_PORT}\" TranscoderTempDirectory=\"${TRANSCODE_PATH}\""

if [ -n "${PLEX_CLAIM:-}" ]; then
  PREFS_ATTRS="$PREFS_ATTRS"
fi

cat > "$PLEX_PREFS" <<PLEOF
<?xml version="1.0" encoding="utf-8"?>
<Preferences ${PREFS_ATTRS}/>
PLEOF
chown plex:plex "$PLEX_PREFS"

systemctl enable plexmediaserver
systemctl start plexmediaserver
echo "Plex Media Server installed successfully"
