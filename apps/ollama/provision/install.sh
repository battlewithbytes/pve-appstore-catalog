#!/bin/bash
set -euo pipefail

API_PORT="${API_PORT:-11434}"
BIND_ADDRESS="${BIND_ADDRESS:-0.0.0.0}"
MODELS_PATH="${MODELS_PATH:-/usr/share/ollama/.ollama/models}"
NUM_CTX="${NUM_CTX:-2048}"

curl -fsSL https://ollama.ai/install.sh | sh

# Configure Ollama environment
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/override.conf <<OLEOF
[Service]
Environment="OLLAMA_HOST=${BIND_ADDRESS}:${API_PORT}"
Environment="OLLAMA_MODELS=${MODELS_PATH}"
Environment="OLLAMA_NUM_CTX=${NUM_CTX}"
OLEOF

mkdir -p "$MODELS_PATH"
systemctl daemon-reload
systemctl restart ollama

if [ -n "${DEFAULT_MODEL:-}" ]; then
  ollama pull "$DEFAULT_MODEL"
fi

echo "Ollama installed successfully"
