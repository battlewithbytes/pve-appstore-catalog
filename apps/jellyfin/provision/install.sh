#!/bin/bash
set -euo pipefail
apt-get update
apt-get install -y curl gnupg
curl -fsSL https://repo.jellyfin.org/install-debuntu.sh | bash
systemctl enable jellyfin
systemctl start jellyfin
echo "Jellyfin installed successfully"
