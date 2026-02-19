"""qBittorrent — lightweight BitTorrent client with WebUI (Alpine Linux)."""

import os

from appstore import BaseApp, run


class QBittorrentApp(BaseApp):
    def install(self):
        webui_port = self.inputs.string("webui_port", "8080")
        torrent_port = self.inputs.string("torrent_port", "6881")
        password = self.inputs.string("initial_password", "changeme")
        download_path = "/downloads"

        # Enable Alpine community repository (required for qbittorrent-nox)
        self.enable_repo("community")

        # Install packages via OS-aware helper (apk on Alpine)
        self.pkg_install("qbittorrent-nox", "python3", "p7zip")

        # Create service user
        self.create_user("qbittorrent", system=True, home="/var/lib/qbittorrent")

        # Create directories
        config_dir = "/var/lib/qbittorrent/.config/qBittorrent"
        self.create_dir(config_dir)
        self.create_dir(download_path)
        self.create_dir(f"{download_path}/incomplete")
        
        # Only write config if it doesn't already exist (preserves settings on reinstall)
        config_file = f"{config_dir}/qBittorrent.conf"
        if not os.path.exists(config_file):
            # Generate PBKDF2 password hash for qBittorrent config
            h = self.pbkdf2_hash(password)
            password_hash = f"@ByteArray({h['salt']}:{h['hash']})"

            template = self.provision_file("qBittorrent.conf")
            self.write_config(
                config_file,
                template,
                torrent_port=torrent_port,
                download_path=download_path,
                webui_port=webui_port,
                password_hash=password_hash,
            )

        # Set ownership of all qbittorrent data
        self.chown("/var/lib/qbittorrent", "qbittorrent:qbittorrent", recursive=True)
        self.chown(download_path, "qbittorrent:qbittorrent", recursive=True)

        # Create and start OpenRC service
        self.create_service(
            "qbittorrent-nox",
            exec_start=(
                f"/usr/bin/qbittorrent-nox"
                f" --webui-port={webui_port}"
                f" --torrenting-port={torrent_port}"
            ),
            description="qBittorrent-nox BitTorrent client",
            user="qbittorrent",
            environment={
                "HOME": "/var/lib/qbittorrent",
                "XDG_CONFIG_HOME": "/var/lib/qbittorrent/.config",
                "XDG_DATA_HOME": "/var/lib/qbittorrent/.local/share",
            },
        )

        # Emit outputs
        self.log.output("webui_password", password)
        self.log.info("qBittorrent installed successfully")


run(QBittorrentApp)
