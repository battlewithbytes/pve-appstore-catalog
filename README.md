# PVE App Store Catalog

App catalog for the [PVE App Store](https://github.com/battlewithbytes/pve-appstore) — a collection of one-click LXC container apps for Proxmox VE.

Browse and install apps through the web UI at `http://your-proxmox-ip:8088`. Search by name, category, or tag.

## Features

- **One-click install** — pick an app, configure inputs, and the store creates an LXC container and provisions it automatically
- **Live monitoring** — CPU, memory, disk, network stats polled from the Proxmox API
- **Web terminal** — shell into any container directly from the browser
- **Multi-app stacks** — bundle multiple apps into a single container with shared resources
- **GPU passthrough** — Intel QSV and NVIDIA profiles for media transcoding and AI workloads
- **Config backup & restore** — export all installs and settings as portable YAML
- **Reconfigure in-place** — change app settings and container resources without rebuilding
- **Developer mode** — build, test, and publish custom apps with a built-in IDE and GitHub integration
- **Sandboxed provisioning** — Python SDK with enforced per-app permission boundaries
- **Alpine + Debian support** — SDK auto-detects the OS and uses the right package manager, init system, and service management

## Apps

<!-- BEGIN_APP_TABLE -->

| App | Version | Category | OS | GPU |
|-----|---------|----------|----|-----|
| [Crawl4AI](apps/crawl4ai/) | 0.5.0 | ai, tools | debian-12 | - |
| [GitLab CE](apps/gitlab/) | 1.1.3 | development, devops | ubuntu-24.04 | - |
| [Gluetun VPN Client](apps/gluetun/) | 3.40.0 | networking, security | debian-12 | - |
| [Hello World (Nginx)](apps/hello-world/) | 1.0.1 | web, tools | debian-12 | - |
| [Home Assistant](apps/homeassistant/) | 2025.1.0 | automation, smart-home | debian-12 | - |
| [Jellyfin](apps/jellyfin/) | 10.10.2 | media, entertainment | debian-12 | - |
| [Nginx](apps/nginx/) | 1.27.0 | networking, web | debian-12 | - |
| [Ollama](apps/ollama/) | 0.6.1 | ai, tools | debian-12 | - |
| [pihole-official](apps/pihole-official/) | 1.1.0 | networking | debian-12 | - |
| [Plex Media Server](apps/plex/) | 1.41.3 | media, entertainment | debian-12 | - |
| [qBittorrent](apps/qbittorrent/) | 5.1.2 | media, tools | alpine-3.22 | - |
| [Resilio Sync](apps/resilio-sync/) | 1.0.0 | utilities, backup | debian-12 | - |
| [SWAG](apps/swag/) | 1.0.0 | networking | alpine-3.22 | - |
<!-- END_APP_TABLE -->

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

## Creating an App

There are two ways to create apps: using the built-in Developer IDE (recommended) or manually.

### Option 1: Developer IDE (Recommended)

The PVE App Store includes a full developer environment accessible from the web UI.

![Developer IDE](devide.png)

**Setup:**

1. Open the web UI and go to **Settings**
2. Enable **Developer Mode**
3. Click **Developer** in the top navigation

**Create your app:**

1. Click **New App** and choose a starter template (Minimal, Web App, Database, etc.) or import from a Dockerfile/ZIP
2. Edit the manifest (`app.yml`) and install script (`install.py`) in the built-in CodeMirror editor with SDK autocompletion and hover docs
3. Click **Validate** — checks manifest schema, Python syntax, permission consistency, and unknown SDK methods
4. Click **Deploy** to inject your app into the local catalog for testing — it appears alongside official apps
5. Install and test your app from the Apps page like any other app
6. Iterate: edit, validate, deploy, reinstall

**Publish to the catalog:**

1. In the Developer IDE, click **GitHub** and connect your GitHub account
2. Fork this catalog repository (`battlewithbytes/pve-appstore-catalog`)
3. Click **Publish** — this pushes your app to a branch on your fork
4. Open a pull request from GitHub to submit your app for review
5. Once merged, your app is available to all PVE App Store users

**Alternatively, export and submit manually:**

1. Click **Export** to download your app as a `.zip` file
2. Extract it into `apps/<your-app-id>/` in your fork of this repo
3. Open a pull request

### Option 2: Manual Creation

Create a directory under `apps/` with a unique kebab-case ID and include:

1. `app.yml` — manifest following the schema below
2. `provision/install.py` — Python install script using the SDK

## Manifest Schema (app.yml)

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

volumes:                      # Managed volumes and bind mounts
  - name: data
    path: /opt/myapp/data
    type: managed             # managed = auto-created on storage pool
    default_size_gb: 10
  - name: media
    path: /mnt/media
    type: bind                # bind = user provides host path
    description: Path to media library

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
from appstore import BaseApp, run

class MyApp(BaseApp):
    def install(self):
        http_port = self.inputs.integer("http_port", 8080)
        enable_ssl = self.inputs.boolean("enable_ssl", False)

        self.pkg_install("nginx")
        self.render_template("config.yml", "/opt/myapp/config.yml",
            port=http_port)
        self.deploy_provision_file("site.conf", "/etc/nginx/sites-available/default")
        self.enable_service("nginx")

run(MyApp)
```

Key SDK methods:

| Method | Purpose |
|--------|---------|
| `pkg_install()` | Install packages (auto-detects apt/apk) |
| `pip_install()` | Install pip packages in a venv |
| `render_template()` | Read a template from `provision/`, substitute variables, write to dest |
| `deploy_provision_file()` | Copy a file from `provision/` to dest (no substitution) |
| `provision_file()` | Read a provision file and return its contents as a string |
| `write_config()` | Write a string template to a path with variable substitution |
| `create_service()` | Create and start a systemd/OpenRC service |
| `enable_service()` | Enable and start an existing service |
| `create_dir()` | Create a directory with optional ownership |
| `download()` | Download a URL to a file |
| `create_user()` | Create a system user |
| `add_apt_repository()` | Add an APT repo with signing key |
| `run_command()` | Run a shell command (must be in permissions) |
| `run_installer_script()` | Download and execute a remote install script |
| `chown()` | Change file/directory ownership |
| `wait_for_http()` | Poll an HTTP endpoint until it responds 200 |
| `write_env_file()` | Write a KEY=VALUE environment file |
| `random_password()` | Generate a cryptographically secure password |
| `pbkdf2_hash()` | Hash a password with PBKDF2 |
| `sysctl()` | Apply persistent kernel parameters |
| `disable_ipv6()` | Disable IPv6 in a container |
| `run_shell()` | Run a shell command with pipes/redirects |
| `pull_oci_binary()` | Extract a binary from a Docker/OCI image without Docker |
| `enable_repo()` | Enable an OS package repository |
| `create_venv()` | Create a Python virtual environment |
| `status_page()` | Deploy a self-contained status page server |

Use `inputs.string()`, `inputs.integer()`, and `inputs.boolean()` to read typed inputs. Keep config files as separate templates in `provision/` — avoid inline string constants.

### Lifecycle Methods

Apps can override these methods in their `BaseApp` subclass:

| Method | When it runs |
|--------|-------------|
| `install()` | **Required.** Runs on first install |
| `configure()` | Optional. Runs on reconfigure (change settings without full reinstall) |
| `healthcheck()` | Optional. Validates the install succeeded |
| `uninstall()` | Optional. Cleanup on removal |

If your app defines `configure()`, `install()` should call `self.configure()` so the config logic is shared.

### Platform Support

The SDK auto-detects the container OS and uses the right tools:

| Feature | Debian | Alpine |
|---------|--------|--------|
| Packages | `apt-get` | `apk` |
| Services | systemd | OpenRC |
| `create_service()` | `.service` unit | `/etc/init.d/` script |
| `create_user()` | `useradd` | `adduser` |
| Logs | `journalctl` | `/var/log/messages` |

Use `pkg_install()` instead of `apt_install()` for OS-agnostic package installation.

### Test Config (test.yml)

Apps can include a `test.yml` file with default inputs for automated integration testing:

```yaml
inputs:
  http_port: "8080"
  bind_address: "0.0.0.0"
```

Run tests with `pve-appstore test-apps --app <id>`.

## Contributing

1. Fork this repository
2. Create your app under `apps/<your-app-id>/` (or use the Developer IDE's Publish feature)
3. Test it using Developer Mode's deploy feature
4. Open a pull request

**Guidelines:**
- Use kebab-case for app IDs (`my-cool-app`)
- Prefer unprivileged containers (`unprivileged: true`)
- Keep LXC defaults minimal — users can increase resources at install time
- Declare all permissions your script needs — the SDK blocks undeclared operations
- Include an `icon.png` (256x256 recommended)
- Add a `README.md` with setup notes, default credentials, and post-install steps

## Links

- [PVE App Store](https://github.com/battlewithbytes/pve-appstore) — the main application
- [Install Guide](https://github.com/battlewithbytes/pve-appstore#quick-start) — one-liner setup
- [Security Model](https://github.com/battlewithbytes/pve-appstore/blob/main/SECURITY.md) — how permissions work
