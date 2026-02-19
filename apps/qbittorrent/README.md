# qBittorrent

Lightweight, open-source BitTorrent client with a powerful web interface, running headless on Alpine Linux.

## Features

- **Web UI** — Full-featured web interface for managing torrents from any browser
- **RSS feeds** — Automatic downloading via RSS with smart episode filters
- **Sequential downloading** — Stream media files while they download
- **Bandwidth scheduling** — Set speed limits by time of day
- **IP filtering** — Block unwanted peers with customizable blocklists
- **Web API** — Full REST API for integration with Sonarr, Radarr, Prowlarr, and other automation tools
- **Alpine Linux** — Minimal footprint (~50MB RAM idle)

## Default Credentials

| Field    | Value      |
|----------|------------|
| Username | `admin`    |
| Password | *(set during install, shown in outputs)* |

Change your password immediately after first login via **Options > Web UI > Authentication**.

## Configuration

After installation, access the WebUI at `http://<container-ip>:8080` (or your chosen port).

### Recommended Settings

- **Downloads > Default Save Path**: `/downloads` (mapped to your host storage via bind mount)
- **Connection > Listening Port**: Forward this port on your router for best speeds
- **Speed > Alternative Rate Limits**: Set up bandwidth scheduling to limit during peak hours
- **BitTorrent > Seeding Limits**: Configure ratio/time limits to manage disk space

## Persistent Config

The config volume at `/var/lib/qbittorrent` preserves all qBittorrent settings across reinstalls. On first install, a default config is written with your chosen ports and password. On subsequent installs (with the config volume intact), your existing settings are preserved.

## Arr Stack Integration

To connect Sonarr, Radarr, or Prowlarr:

1. In the Arr app, go to **Settings > Download Clients > Add > qBittorrent**
2. Set **Host** to the container IP and **Port** to the WebUI port
3. Enter `admin` and your password
4. Set **Category** (e.g. `sonarr`, `radarr`) to keep downloads organized

## Bind Mount

Mount your storage directly into the container using the **Downloads** volume option during install. This avoids copying files between storage pools.

Example: `/mnt/storage/downloads` on the host maps to `/downloads` in the container.

## Troubleshooting

- **WebUI not loading**: Wait 30 seconds after install for qBittorrent to fully start, then refresh
- **Slow speeds**: Ensure the torrent port is forwarded on your router and not blocked by your ISP
- **Permission errors**: The `qbittorrent` service user owns `/var/lib/qbittorrent` and `/downloads`
