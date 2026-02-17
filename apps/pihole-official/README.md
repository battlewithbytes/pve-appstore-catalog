 # Pi-hole

  Pi-hole is a network-wide ad blocker that acts as a DNS sinkhole, blocking ads and trackers for all devices on your network without requiring client-side
  software.

  **Homepage:** https://pi-hole.net/
  **Source:** https://github.com/pi-hole/pi-hole

  ## What's Included

  - Pi-hole v6 with built-in web server (FTL)
  - DNS sinkhole with customizable blocklists
  - Web admin dashboard for statistics and configuration
  - DHCP server (optional, disabled by default)

  ## Setup

  1. **Install** from the App Store — set your desired web interface port and upstream DNS servers
  2. **Point your DNS** — configure your router's DHCP settings to hand out the container's IP as the DNS server, or set it per-device
  3. **Access the dashboard** at `http://<container-ip>:<port>/admin`

  ## Default Configuration

  | Setting | Default |
  |---------|---------|
  | Web Interface Port | 8155 |
  | Upstream DNS 1 | 8.8.8.8 (Google) |
  | Upstream DNS 2 | 8.8.4.4 (Google) |
  | DNSMASQ Listening | all |

  ## Notes

  - The container requires a **static IP** since all network clients will point their DNS to it
  - Runs as a **privileged** container (required for network-level DNS interception)
  - NTP sync is disabled — the container inherits time from the Proxmox host
  - To set an admin password after install, open a terminal and run: `pihole -a -p`