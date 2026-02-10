# Quickstart: Create an App in 5 Minutes

The bare minimum to get a working app in the PVE App Store catalog.

## 1. Create two files

```
apps/my-app/
  app.yml
  provision/
    install.py
```

## 2. Write the manifest

`apps/my-app/app.yml`:

```yaml
id: my-app
name: My App
description: One-line summary of what this app does.
version: 1.0.0
categories: [tools]
tags: [example]

lxc:
  ostemplate: debian-12
  defaults:
    unprivileged: true
    cores: 1
    memory_mb: 256
    disk_gb: 2
    onboot: true

inputs:
  - key: http_port
    label: HTTP Port
    type: number
    default: 8080
    required: false

permissions:
  packages: [nginx]
  paths: ["/var/www/"]
  services: [nginx]

provisioning:
  script: provision/install.py

outputs:
  - key: url
    label: Web UI
    value: "http://{{ip}}:{{http_port}}"
```

## 3. Write the install script

`apps/my-app/provision/install.py`:

```python
from appstore import BaseApp, run

class MyApp(BaseApp):
    def install(self):
        self.apt_install("nginx")
        port = self.inputs.string("http_port", "8080")
        self.write_config("/var/www/html/index.html", "<h1>It works!</h1>")
        self.enable_service("nginx")

run(MyApp)
```

## 4. Test it

Copy into the catalog and install via the web UI or API:

```bash
cp -r apps/my-app /var/lib/pve-appstore/catalog/apps/
# Refresh catalog in the web UI (Config > Refresh) or restart the service
```

## That's it

Everything declared in `permissions` is enforced by the SDK. If your script tries to install a package or write to a path not listed, it fails with `PermissionDeniedError`.

For the full reference (inputs, GPU, volumes, secrets, lifecycle methods), see the [App Development Tutorial](https://github.com/battlewithbytes/pve-appstore/blob/main/tutorial.md).
