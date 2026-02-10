# PVE App Store Catalog

App catalog for the [PVE App Store](https://github.com/battlewithbytes/pve-appstore) — a collection of one-click LXC container apps for Proxmox VE.

Browse and install apps through the web UI — search by name, category, or tag.

## Apps

| App | Version | Category | GPU |
|-----|---------|----------|-----|
| [Crawl4AI](apps/crawl4ai/) | 0.4.0 | ai, tools | - |
| [Gluetun VPN Client](apps/gluetun/) | 3.40.0 | networking, vpn | - |
| [Hello World (Nginx)](apps/hello-world/) | 1.0.1 | web, tools | - |
| [Home Assistant](apps/homeassistant/) | 2025.1.0 | automation, smart-home | - |
| [Jellyfin](apps/jellyfin/) | 10.10.0 | media, entertainment | intel, nvidia |
| [Nginx](apps/nginx/) | 1.27.0 | networking, web | - |
| [Ollama](apps/ollama/) | 0.6.0 | ai, tools | intel, nvidia |
| [Plex Media Server](apps/plex/) | 1.41.0 | media, entertainment | intel, nvidia |

## Structure

```
apps/<app-id>/
  app.yml              # App manifest (metadata, LXC defaults, inputs, permissions, provisioning, GPU)
  provision/
    install.py         # Install script (Python SDK, runs inside the container)
  icon.png             # Optional app icon
  README.md            # Optional detailed documentation
  test.yml             # Optional test config (inputs for automated testing)
```

## Contributing

To add a new app, create a directory under `apps/` with a unique kebab-case ID and include at minimum:

1. `app.yml` — manifest following the schema below
2. `provision/install.py` — Python install script using the App SDK

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
  extra_config:               # Optional raw LXC config lines (allowlisted keys only)
    - "lxc.cap.add: net_admin"

inputs:                       # User-configurable parameters
  - key: param_name
    label: Display Label
    type: string|number|boolean|select|secret
    default: value
    required: false
    group: General
    description: What this parameter controls
    help: Help text for the user

permissions:                  # Security allowlist — the SDK enforces these
  packages: [nginx]           # APT packages the app may install
  pip: [somelib]              # pip packages (installed in a venv)
  urls: ["https://example.com/*"]  # URLs the app may download from (glob)
  paths: ["/opt/myapp/"]     # Filesystem paths the app may write to (prefix match)
  services: [myapp]          # systemd services the app may enable/start
  users: [myapp]             # System users the app may create
  commands: [myapp-setup]    # Commands the app may run directly
  installer_scripts: ["https://example.com/install.sh"]  # Remote scripts allowed to execute
  apt_repos: ["deb ..."]     # APT repository lines the app may add

provisioning:
  script: provision/install.py  # Must be a .py file using the Python SDK
  timeout_sec: 300
  redact_keys: [secret_key]  # Input keys to redact from logs

outputs:                      # Shown to user after install
  - key: url
    label: Web UI
    value: "http://{{ip}}:8080"

gpu:
  supported: []               # empty, or [intel], [nvidia], [intel, nvidia]
  required: false
  profiles: [dri-render, nvidia-basic]
```

### Security

- **Permissions allowlist**: Every SDK operation (installing packages, writing files, downloading URLs) is checked against the `permissions` section. Unauthorized operations are blocked at runtime.
- **Input validation**: Hostnames, IP addresses, bridge names, bind mount paths, environment variables, and device paths are validated server-side before any container operations.
- **Secret inputs**: Use `type: secret` for sensitive inputs (passwords, API keys). Combine with `redact_keys` under `provisioning` to prevent them from appearing in job logs.
- **Extra LXC config**: The `extra_config` field only allows a strict set of LXC configuration keys (`lxc.cap.add`, `lxc.cap.drop`, `lxc.environment`, `lxc.mount.entry`, `lxc.net.*`, `lxc.cgroup2.*`). All other keys are rejected.

### Writing an Install Script

Install scripts use the Python SDK (`BaseApp`). Every operation (installing packages, writing files, enabling services) is checked against the `permissions` allowlist in `app.yml`. Unauthorized operations are blocked at runtime.

```python
import sys, os
sys.path.insert(0, os.environ.get("PYTHONPATH", "/opt/appstore/sdk"))
from appstore import BaseApp, run

class MyApp(BaseApp):
    def install(self):
        self.log.info("Installing My App")
        self.apt_install("nginx")
        self.write_config("/opt/myapp/config.yml", CONFIG_TEMPLATE,
            port=self.inputs.string("http_port", "8080"))
        self.enable_service("nginx")
        self.log.output("url", f"http://localhost:{self.inputs.string('http_port', '8080')}")

run(MyApp)
```

Available helpers: `apt_install()`, `pip_install()`, `create_venv()`, `write_config()`, `enable_service()`, `restart_service()`, `create_dir()`, `download()`, `create_user()`, `add_apt_key()`, `add_apt_repo()`, `run_command()`, `run_installer_script()`, `chown()`.

### Test Config (test.yml)

Apps can include a `test.yml` file with default inputs for automated integration testing:

```yaml
inputs:
  http_port: "8080"
  bind_address: "0.0.0.0"
```

Run tests with `pve-appstore test-apps --app <id>`.
