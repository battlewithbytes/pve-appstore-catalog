"""HEIC2JPG — serve a static, client-side HEIC→JPG converter SPA via nginx.

No application backend: the static web assets are bundled with this app as
provision/web.tgz, extracted into the container, and served by nginx. All
HEIC→JPG conversion runs in the visitor's browser.
"""

import os

from appstore import BaseApp, run


HERE = os.path.dirname(os.path.abspath(__file__))
WEB_TGZ = os.path.join(HERE, "web.tgz")
APP_ROOT = "/opt/heic2jpg"
WEB_ROOT = APP_ROOT + "/web"
SITE_FILE = "/etc/nginx/sites-available/heic2jpg.conf"
SITE_LINK = "/etc/nginx/sites-enabled/heic2jpg.conf"


class Heic2Jpg(BaseApp):
    def install(self):
        port = self.inputs.integer("port", 80)

        # 1. Lightweight nginx.
        self.apt_install("nginx-light", "ca-certificates")

        # 2. Extract the bundled static assets (web/ tree) into the container.
        self.create_dir(APP_ROOT)
        self.run_command(["tar", "-xzf", WEB_TGZ, "-C", APP_ROOT])
        # nginx (www-data) must be able to read everything we just extracted.
        self.run_command(["chown", "-R", "www-data:www-data", APP_ROOT])

        # 3. Server block.
        site = (
            "server {\n"
            f"    listen {port} default_server;\n"
            f"    listen [::]:{port} default_server;\n"
            "    server_name _;\n"
            f"    root {WEB_ROOT};\n"
            "    index index.html;\n"
            "\n"
            "    # libheif + JSZip are large, immutable, bundled assets.\n"
            "    location /vendor/ {\n"
            "        expires 30d;\n"
            "        add_header Cache-Control \"public, immutable\";\n"
            "    }\n"
            "\n"
            "    location / {\n"
            "        try_files $uri $uri/ =404;\n"
            "    }\n"
            "}\n"
        )
        self.write_config(SITE_FILE, site)

        # 4. Enable our site, drop the stock default.
        self.run_command(["rm", "-f", "/etc/nginx/sites-enabled/default"])
        self.run_command(["ln", "-sf", SITE_FILE, SITE_LINK])

        # 5. Validate, enable, (re)start.
        self.run_command(["nginx", "-t"])
        self.enable_service("nginx")
        self.restart_service("nginx")

        # 6. Health check.
        self.wait_for_http(f"http://127.0.0.1:{port}/", timeout=30)
        self.log.info(f"HEIC→JPG converter is live on port {port}. Serving {WEB_ROOT}.")


run(Heic2Jpg)
