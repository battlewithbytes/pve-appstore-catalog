#!/bin/bash
set -euo pipefail
curl -fsSL https://ollama.ai/install.sh | sh
if [ -n "${DEFAULT_MODEL:-}" ]; then
  ollama pull "$DEFAULT_MODEL"
fi
echo "Ollama installed successfully"
