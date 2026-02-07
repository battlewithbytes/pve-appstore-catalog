#!/bin/bash
set -euo pipefail
apt-get update
apt-get install -y curl
curl -fsSL https://downloads.plex.tv/plex-keys/PlexSign.key | gpg --dearmor -o /usr/share/keyrings/plex-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/plex-archive-keyring.gpg] https://downloads.plex.tv/repo/deb public main" > /etc/apt/sources.list.d/plexmediaserver.list
apt-get update
apt-get install -y plexmediaserver
systemctl enable plexmediaserver
systemctl start plexmediaserver
echo "Plex Media Server installed successfully"
