#!/bin/bash
set -euo pipefail

CONFIG_PATH="${CONFIG_PATH:-/opt/homeassistant/config}"
HTTP_PORT="${HTTP_PORT:-8123}"
ENABLE_MQTT="${ENABLE_MQTT:-false}"

apt-get update
apt-get install -y python3 python3-venv python3-pip

python3 -m venv /opt/homeassistant
/opt/homeassistant/bin/pip install homeassistant

mkdir -p "$CONFIG_PATH"

# Configure custom port if non-default
if [ "$HTTP_PORT" != "8123" ]; then
  mkdir -p "$CONFIG_PATH"
  cat > "$CONFIG_PATH/configuration.yaml" <<HAEOF
http:
  server_port: ${HTTP_PORT}
HAEOF
fi

# Install MQTT broker if requested
if [ "$ENABLE_MQTT" = "true" ]; then
  apt-get install -y mosquitto mosquitto-clients
  systemctl enable mosquitto
  systemctl start mosquitto
  echo "MQTT broker installed and running on port 1883"
fi

echo "Home Assistant installed successfully"
