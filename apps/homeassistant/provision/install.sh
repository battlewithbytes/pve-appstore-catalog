#!/bin/bash
set -euo pipefail
apt-get update
apt-get install -y python3 python3-venv python3-pip
python3 -m venv /opt/homeassistant
/opt/homeassistant/bin/pip install homeassistant
echo "Home Assistant installed successfully"
