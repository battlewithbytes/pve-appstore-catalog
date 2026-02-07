#!/bin/bash
set -euo pipefail

HTTP_PORT="${HTTP_PORT:-80}"
HTTPS_PORT="${HTTPS_PORT:-443}"
WORKER_PROCESSES="${WORKER_PROCESSES:-0}"
DOMAIN="${DOMAIN:-}"
ENABLE_SSL="${ENABLE_SSL:-false}"

apt-get update
apt-get install -y nginx

# Configure worker processes
if [ "$WORKER_PROCESSES" != "0" ]; then
  sed -i "s/worker_processes auto;/worker_processes ${WORKER_PROCESSES};/" /etc/nginx/nginx.conf
fi

# Configure default server block with custom ports
cat > /etc/nginx/sites-available/default <<NGEOF
server {
    listen ${HTTP_PORT} default_server;
    listen [::]:${HTTP_PORT} default_server;
    ${DOMAIN:+server_name ${DOMAIN};}

    root /var/www/html;
    index index.html index.htm;

    location / {
        try_files \$uri \$uri/ =404;
    }
}
NGEOF

# Generate self-signed SSL certificate if requested
if [ "$ENABLE_SSL" = "true" ]; then
  mkdir -p /etc/nginx/ssl
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/nginx.key \
    -out /etc/nginx/ssl/nginx.crt \
    -subj "/CN=${DOMAIN:-localhost}"

  cat >> /etc/nginx/sites-available/default <<SSLEOF

server {
    listen ${HTTPS_PORT} ssl default_server;
    listen [::]:${HTTPS_PORT} ssl default_server;
    ${DOMAIN:+server_name ${DOMAIN};}

    ssl_certificate /etc/nginx/ssl/nginx.crt;
    ssl_certificate_key /etc/nginx/ssl/nginx.key;

    root /var/www/html;
    index index.html index.htm;

    location / {
        try_files \$uri \$uri/ =404;
    }
}
SSLEOF
fi

systemctl enable nginx
systemctl start nginx
echo "Nginx installed successfully"
