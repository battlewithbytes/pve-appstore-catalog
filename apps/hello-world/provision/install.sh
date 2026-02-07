#!/bin/bash
set -euo pipefail

GREETING="${GREETING:-Hello from Proxmox!}"
SUBTITLE="${SUBTITLE:-Your PVE App Store is working correctly.}"
HTTP_PORT="${HTTP_PORT:-80}"
BG_COLOR="${BG_COLOR:-#1a1a2e}"

apt-get update
apt-get install -y nginx

# Create the hello world page
cat > /var/www/html/index.html <<HTMLEOF
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${GREETING}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: ${BG_COLOR};
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #fff;
    }
    .container {
      text-align: center;
      padding: 48px;
    }
    .icon { font-size: 64px; margin-bottom: 24px; }
    h1 { font-size: 2.5rem; font-weight: 700; margin-bottom: 12px; }
    p { font-size: 1.1rem; color: #aaa; margin-bottom: 32px; }
    .badge {
      display: inline-block;
      padding: 6px 16px;
      background: rgba(255,255,255,0.1);
      border-radius: 20px;
      font-size: 0.85rem;
      color: #7ec8e3;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="icon">&#9881;</div>
    <h1>${GREETING}</h1>
    <p>${SUBTITLE}</p>
    <span class="badge">PVE App Store</span>
  </div>
</body>
</html>
HTMLEOF

# Configure Nginx with custom port
if [ "$HTTP_PORT" != "80" ]; then
  cat > /etc/nginx/sites-available/default <<NGEOF
server {
    listen ${HTTP_PORT} default_server;
    listen [::]:${HTTP_PORT} default_server;
    root /var/www/html;
    index index.html;
    location / {
        try_files \$uri \$uri/ =404;
    }
}
NGEOF
fi

systemctl enable nginx
systemctl start nginx
echo "Hello World installed successfully"
