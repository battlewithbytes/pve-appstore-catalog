# Checkmk Community

IT infrastructure monitoring for servers, networks, containers, and applications, running in a Proxmox LXC container.

## What's Included

The official Checkmk Community package (formerly Checkmk Raw) from checkmk.com, installed as an OMD monitoring site:

- **Monitoring core** — Nagios-based core with thousands of check plug-ins
- **Auto-discovery** — services on Linux/Windows agents, SNMP devices, and cloud/container hosts
- **Web UI** — dashboards, views, graphing (RRD), and Setup (WATO) configuration
- **Event Console** — syslog/SNMP trap processing
- **Notifications** — email and scriptable alert channels

## Requirements

- **Minimum:** 2 cores, 4 GB RAM, 16 GB root disk + 20 GB site volume
- Ubuntu 26.04 LXC container (unprivileged, nesting enabled)

## Inputs

| Input | Default | Reconfigurable | Description |
|-------|---------|---------------|-------------|
| Site Name | `monitoring` | No | OMD site name; also the URL path and Linux user |
| Admin Password | random | Yes | Password for the `cmkadmin` web user (min 8 chars) |
| Timezone | `Etc/UTC` | No | Container timezone |

## Post-Install

- Open the web UI at `http://<container-ip>/<site>/` and log in as `cmkadmin` with the password shown in outputs.
- Command-line administration: `pct enter <ctid>`, then `omd su <site>`.
- To monitor the container itself, install the Linux agent from **Setup → Agents** inside the container and add `localhost` as a host.

## Storage

Site data lives on a dedicated volume mounted at `/opt/omd/sites` (`/omd/sites` via the package's `/omd → /opt/omd` symlink): configuration, performance data, logs, and history.

## Notes

- The site runs with `TMPFS=off` because unprivileged containers cannot mount the per-site tmpfs. This has a small I/O cost on very large installations.
- Reconfiguring with a new Admin Password updates `cmkadmin` via `cmk-passwd`.
- To upgrade Checkmk, install the newer `.deb` inside the container and run `omd update <site>` — see the [Checkmk update guide](https://docs.checkmk.com/latest/en/update.html).
