"""PDF2Text — FastAPI PDF text-extraction service.

Clones https://github.com/ril3y/pdf2text into /opt/pdf2text, builds a venv at
/opt/pdf2text-venv, and runs uvicorn under systemd as the unprivileged
pdf2text user. No Docker.
"""

import os

from appstore import BaseApp, run


REPO_URL = "https://github.com/ril3y/pdf2text.git"
SRC_DIR = "/opt/pdf2text"
VENV_DIR = "/opt/pdf2text-venv"
DATA_DIR = "/var/lib/pdf2text"
LOG_DIR = "/var/log/pdf2text"
ENV_FILE = "/etc/default/pdf2text"
UNIT_FILE = "/etc/systemd/system/pdf2text.service"
SERVICE_USER = "pdf2text"


class Pdf2Text(BaseApp):
    def install(self):
        git_ref = self.inputs.string("git_ref", "main")
        port = self.inputs.integer("port", 8000)
        workers = self.inputs.integer("workers", 4)
        max_file_size_mb = self.inputs.integer("max_file_size_mb", 50)
        log_level = self.inputs.string("log_level", "INFO").lower()
        api_key = self.inputs.string("api_key", "")

        # 1. Base packages
        self.apt_install(
            "python3", "python3-venv", "python3-pip", "python3-dev",
            "build-essential", "git", "curl", "ca-certificates",
        )

        # 2. Service user + data/log dirs
        self._ensure_service_user()
        self.create_dir(DATA_DIR, mode="0755")
        self.create_dir(f"{DATA_DIR}/uploads", mode="0755")
        self.create_dir(f"{DATA_DIR}/outputs", mode="0755")
        self.create_dir(LOG_DIR, mode="0755")

        # 3. Clone or update source
        if not os.path.isdir(f"{SRC_DIR}/.git"):
            self.run_command([
                "git", "clone", "--depth", "1", "--branch", git_ref,
                REPO_URL, SRC_DIR,
            ])
        else:
            self.run_command(["git", "-C", SRC_DIR, "fetch", "--depth", "1", "origin", git_ref])
            self.run_command(["git", "-C", SRC_DIR, "checkout", git_ref])
            self.run_command(["git", "-C", SRC_DIR, "reset", "--hard", f"origin/{git_ref}"])

        # 4. Venv + deps (kept outside SRC_DIR per appstore-pve gotcha #6)
        if not os.path.isfile(f"{VENV_DIR}/bin/pip"):
            self.run_command(["python3", "-m", "venv", VENV_DIR])
        self.run_command([f"{VENV_DIR}/bin/pip", "install", "--upgrade", "pip", "wheel"])
        self.run_command([
            f"{VENV_DIR}/bin/pip", "install", "-r", f"{SRC_DIR}/requirements.txt",
        ])

        # 5. Ownership: service user owns source, venv, data, logs
        self.run_command(["chown", "-R", f"{SERVICE_USER}:{SERVICE_USER}", SRC_DIR])
        self.run_command(["chown", "-R", f"{SERVICE_USER}:{SERVICE_USER}", VENV_DIR])
        self.run_command(["chown", "-R", f"{SERVICE_USER}:{SERVICE_USER}", DATA_DIR])
        self.run_command(["chown", "-R", f"{SERVICE_USER}:{SERVICE_USER}", LOG_DIR])

        # 6. EnvironmentFile for systemd
        env = {
            "PDF2TEXT_HOST": "0.0.0.0",
            "PDF2TEXT_PORT": str(port),
            "PDF2TEXT_WORKERS": str(workers),
            "PDF2TEXT_LOG_LEVEL": log_level,
            "PDF2TEXT_MAX_FILE_SIZE_MB": str(max_file_size_mb),
            "PDF2TEXT_TEMP_DIR": DATA_DIR,
            "PDF2TEXT_UPLOAD_DIR": f"{DATA_DIR}/uploads",
            "PDF2TEXT_OUTPUT_DIR": f"{DATA_DIR}/outputs",
            "PDF2TEXT_API_KEY": api_key,
        }
        self.write_env_file(ENV_FILE, env, mode="0640")
        self.run_command(["chown", f"root:{SERVICE_USER}", ENV_FILE])

        # 7. systemd unit
        unit = (
            "[Unit]\n"
            "Description=PDF2Text — FastAPI PDF text extraction service\n"
            "After=network-online.target\n"
            "Wants=network-online.target\n"
            "\n"
            "[Service]\n"
            "Type=simple\n"
            f"User={SERVICE_USER}\n"
            f"Group={SERVICE_USER}\n"
            f"WorkingDirectory={SRC_DIR}\n"
            f"EnvironmentFile={ENV_FILE}\n"
            f"ExecStart={VENV_DIR}/bin/uvicorn app.main:app "
            "--host ${PDF2TEXT_HOST} --port ${PDF2TEXT_PORT} "
            "--workers ${PDF2TEXT_WORKERS} --log-level ${PDF2TEXT_LOG_LEVEL}\n"
            "Restart=on-failure\n"
            "RestartSec=5\n"
            f"StandardOutput=append:{LOG_DIR}/pdf2text.log\n"
            f"StandardError=append:{LOG_DIR}/pdf2text.log\n"
            "\n"
            "# Light hardening\n"
            "NoNewPrivileges=true\n"
            "PrivateTmp=true\n"
            "ProtectSystem=full\n"
            f"ReadWritePaths={DATA_DIR} {LOG_DIR}\n"
            "\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )
        self.write_config(UNIT_FILE, unit)
        self.run_command(["systemctl", "daemon-reload"])

        # 8. Enable + start, then health-check
        self.enable_service("pdf2text")
        self.wait_for_http(
            f"http://127.0.0.1:{port}/api/v1/health",
            timeout=60,
        )

        self.log.info("PDF2Text is up.")
        self.log.info(f"  Web UI:    http://<ct-ip>:{port}/")
        self.log.info(f"  API docs:  http://<ct-ip>:{port}/docs")
        self.log.info(f"  Health:    http://<ct-ip>:{port}/api/v1/health")
        if api_key:
            self.log.info("API key auth ENABLED — send X-API-Key header.")
        else:
            self.log.info("API key auth DISABLED — service is open.")

    def _ensure_service_user(self):
        try:
            self.run_command(["id", SERVICE_USER])
        except Exception:
            self.run_command([
                "useradd", "--system", "--home-dir", SRC_DIR,
                "--shell", "/usr/sbin/nologin", SERVICE_USER,
            ])


run(Pdf2Text)
