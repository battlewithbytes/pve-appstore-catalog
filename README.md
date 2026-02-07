# PVE App Store Catalog

App catalog for the [PVE App Store](https://github.com/battlewithbytes/pve-appstore) — a collection of one-click LXC container apps for Proxmox VE.

## Structure

```
apps/<app-id>/
  app.yml              # App manifest (metadata, LXC defaults, inputs, provisioning, GPU)
  provision/
    install.sh         # Install script (runs inside the container)
    upgrade.sh         # Optional upgrade script
    uninstall.sh       # Optional cleanup script
    healthcheck.sh     # Optional health check
  templates/           # Optional config templates
  icon.png             # Optional app icon
  README.md            # Optional detailed documentation
```

## Available Apps

| App | Category | GPU | Description |
|-----|----------|-----|-------------|
| [nginx](apps/nginx/) | networking, web | - | HTTP server and reverse proxy |
| [ollama](apps/ollama/) | ai, tools | Intel, NVIDIA | Run large language models locally |
| [homeassistant](apps/homeassistant/) | automation, smart-home | - | Open source home automation |
| [jellyfin](apps/jellyfin/) | media, entertainment | Intel, NVIDIA | Free media server with HW transcoding |
| [plex](apps/plex/) | media, entertainment | Intel, NVIDIA | Personal media server |

## Contributing

To add a new app, create a directory under `apps/` with a unique kebab-case ID and include at minimum:

1. `app.yml` — manifest following the schema below
2. `provision/install.sh` — install script that runs inside a Debian 12 LXC container

### Manifest Schema (app.yml)

```yaml
id: my-app                    # Unique kebab-case identifier
name: My App                  # Display name
description: Short summary    # One-line description
version: 1.0.0               # App version
categories: [category]        # One or more categories
tags: [tag1, tag2]            # Searchable tags
homepage: https://example.com
license: MIT
maintainers: [Your Name]

lxc:
  ostemplate: debian-12       # Base OS template
  defaults:
    unprivileged: true        # Always prefer unprivileged
    cores: 2
    memory_mb: 2048
    disk_gb: 8
    features: [nesting]
    onboot: true

inputs:                       # User-configurable parameters
  - key: param_name
    label: Display Label
    type: string|number|boolean|select|secret
    default: value
    required: false
    help: Description for the user

provisioning:
  script: provision/install.sh
  timeout_sec: 300
  env:
    PARAM: "{{param_name}}"   # Template variables from inputs

outputs:                      # Shown to user after install
  - key: url
    label: Web UI
    value: "http://{{ip}}:8080"

gpu:
  supported: []               # empty, or [intel], [nvidia], [intel, nvidia]
  required: false
  profiles: [dri-render, nvidia-basic]
```
