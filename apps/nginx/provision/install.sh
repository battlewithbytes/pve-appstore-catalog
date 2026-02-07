#!/bin/bash
set -euo pipefail
apt-get update
apt-get install -y nginx
systemctl enable nginx
systemctl start nginx
echo "Nginx installed successfully"
