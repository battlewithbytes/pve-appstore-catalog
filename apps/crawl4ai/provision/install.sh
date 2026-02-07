#!/bin/bash
set -euo pipefail

API_PORT="${API_PORT:-11235}"
BIND_ADDRESS="${BIND_ADDRESS:-0.0.0.0}"
MAX_CONCURRENT="${MAX_CONCURRENT:-5}"
CACHE_DIR="${CACHE_DIR:-/var/lib/crawl4ai/cache}"
HEADLESS="${HEADLESS:-true}"

# Install Python and dependencies
apt-get update
apt-get install -y python3 python3-venv python3-pip curl wget gnupg

# Install Chromium dependencies for Playwright
apt-get install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
  libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0

# Create app user and directories
useradd -r -s /bin/false -m -d /opt/crawl4ai crawl4ai || true
mkdir -p "$CACHE_DIR"
mkdir -p /opt/crawl4ai

# Install crawl4ai in a venv
python3 -m venv /opt/crawl4ai/venv
/opt/crawl4ai/venv/bin/pip install -U pip
/opt/crawl4ai/venv/bin/pip install crawl4ai

# Install Playwright browsers
/opt/crawl4ai/venv/bin/crawl4ai-setup

chown -R crawl4ai:crawl4ai /opt/crawl4ai "$CACHE_DIR"

# Create systemd service
cat > /etc/systemd/system/crawl4ai.service <<EOF
[Unit]
Description=Crawl4AI Web Crawler API
After=network.target

[Service]
Type=simple
User=crawl4ai
Environment="CRAWL4AI_API_PORT=${API_PORT}"
Environment="CRAWL4AI_HOST=${BIND_ADDRESS}"
Environment="CRAWL4AI_MAX_CONCURRENT=${MAX_CONCURRENT}"
Environment="CRAWL4AI_CACHE_DIR=${CACHE_DIR}"
Environment="CRAWL4AI_HEADLESS=${HEADLESS}"
ExecStart=/opt/crawl4ai/venv/bin/python -m crawl4ai.server --host ${BIND_ADDRESS} --port ${API_PORT}
Restart=on-failure
RestartSec=5
WorkingDirectory=/opt/crawl4ai

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable crawl4ai
systemctl start crawl4ai

echo "Crawl4AI installed successfully"
