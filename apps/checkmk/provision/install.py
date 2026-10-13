#!/usr/bin/env python3
"""Checkmk Community — IT infrastructure monitoring (OMD site)."""
import os
from appstore import BaseApp, run

CMK_VERSION = "2.5.0p15"
DISTRO = "resolute"  # Ubuntu 26.04
PKG_URL = (f"https://download.checkmk.com/checkmk/{CMK_VERSION}/"
           f"check-mk-community-{CMK_VERSION}_0.{DISTRO}_amd64.deb")
PKG_PATH = f"/tmp/check-mk-community-{CMK_VERSION}.deb"


class CheckmkApp(BaseApp):
    def install(self):
        site = self.inputs.string("site_name", "monitoring")
        self.pkg_install("ca-certificates", "curl", "tzdata")
        self.set_timezone(self.inputs.string("timezone", "Etc/UTC"))

        # The .deb pulls in Apache, Python, RRDtool, etc. as dependencies.
        self.download(PKG_URL, PKG_PATH)
        self.log.info(f"Installing Checkmk Community {CMK_VERSION} (this takes a few minutes)...")
        self.run_command(["apt-get", "update", "-qq"])
        self.run_command(["apt-get", "install", "-y", "-qq", PKG_PATH],
                         env={"DEBIAN_FRONTEND": "noninteractive"}, quiet=True)
        self.run_command(["rm", "-f", PKG_PATH])

        if os.path.isdir(f"/omd/sites/{site}"):
            raise RuntimeError(
                f"/omd/sites/{site} already exists on the site volume; "
                "choose a different site name or install without keeping the volume")

        password = self.inputs.string("admin_password", "") or self.random_password(16)

        self.log.info(f"Creating OMD site '{site}'...")
        # Unprivileged LXC cannot mount the per-site tmpfs; use a plain directory.
        # omd prints its own random admin password, so keep its output quiet and
        # set ours afterwards via stdin to keep it out of the install log.
        self.run_command(["omd", "create", "--no-tmpfs", site], quiet=True)
        self._set_password(site, password)
        self.run_command(["omd", "start", site])

        if not self.wait_for_http(f"http://127.0.0.1/{site}/check_mk/login.py", timeout=120):
            raise RuntimeError("Checkmk web UI did not come up")

        self.log.output("admin_password", password)
        self.log.info(f"Checkmk ready at http://{os.environ.get('CONTAINER_IP', '<ip>')}/{site}/")

    def configure(self):
        """Apply a new admin password on reconfigure."""
        password = self.inputs.string("admin_password", "")
        if not password:
            return
        site = self.inputs.string("site_name", "monitoring")
        self._set_password(site, password)
        self.log.output("admin_password", password)

    def _set_password(self, site, password):
        self.log.info("Setting cmkadmin password...")
        self.run_command(["su", "-", site, "-c", "cmk-passwd --stdin cmkadmin"],
                         input_text=password + "\n", quiet=True)


run(CheckmkApp)
