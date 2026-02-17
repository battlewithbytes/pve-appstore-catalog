"""
Provisioning script for binhex-official-pihole.
Imported from Unraid template — original Docker image: pihole/pihole
https://pi-hole.net/
"""
from appstore import BaseApp, run


class PiholeOfficial(BaseApp):
    def install(self):
        self.create_dir("/etc/pihole")

        # Write unattended config before installer runs
        self._write_setup_vars()

        # Unattended install — no TUI dialogs
        self.run_shell("curl -sSL https://install.pi-hole.net | bash /dev/stdin --unattended")

        # Configure lighttpd port + restart (now that files exist)
        self.configure()

        self.enable_service("pihole-FTL")

        self.log.info("Pi-hole installation complete")

    def _write_setup_vars(self):
        """Write setupVars.conf (needed before installer runs)."""
        dns_1 = self.inputs.string("dns_1")
        dns_2 = self.inputs.string("dns_2")
        dnsmasq_listening = self.inputs.string("dnsmasq_listening")

        setup_vars = (
            "PIHOLE_INTERFACE=eth0\n"
            f"PIHOLE_DNS_1={dns_1}\n"
            f"PIHOLE_DNS_2={dns_2}\n"
            f"DNSMASQ_LISTENING={dnsmasq_listening}\n"
            "QUERY_LOGGING=true\n"
            "CACHE_SIZE=10000\n"
            "DNS_FQDN_REQUIRED=true\n"
            "DNS_BOGUS_PRIV=true\n"
            "BLOCKING_ENABLED=true\n"
            "WEBPASSWORD=\n"
        )
        self.write_config("/etc/pihole/setupVars.conf", setup_vars)

    def configure(self):
      self._write_setup_vars()
      port_web_interface = self.inputs.integer("port_web_interface")
      if port_web_interface != 80:
          # Pi-hole v6: FTL has a built-in web server, no lighttpd
          self.run_command(
              ["pihole-FTL", "--config", "webserver.port", f"{port_web_interface}"]
          )
        # LXC containers inherit time from host — disable FTL's NTP client
      self.run_command(["pihole-FTL", "--config", "ntp.sync.active", "false"])
      
      self.restart_service("pihole-FTL")


run(PiholeOfficial)