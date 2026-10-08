"""ComfyUI — node-based diffusion image generation server, plus a history gallery.

Layout inside the CT:
  /opt/comfyui            ComfyUI git checkout (CT-private)
  /opt/comfyui-venv       Python venv (torch from download.pytorch.org)
  /opt/comfyui-gallery    Prompt/image history web page (stdlib HTTP server)
  /var/lib/comfyui/models Models volume (symlinked as /opt/comfyui/models)
  /var/lib/comfyui/output Output volume (symlinked as /opt/comfyui/output)

PyTorch CUDA wheels bundle the CUDA runtime, so only the host driver libs
(mounted at /usr/lib/nvidia by the nvidia-basic profile) are needed.
"""

import os

from appstore import BaseApp, run


COMFY_REPO = "https://github.com/comfyanonymous/ComfyUI.git"
MANAGER_REPO = "https://github.com/ltdrdata/ComfyUI-Manager.git"
IPADAPTER_REPO = "https://github.com/cubiq/ComfyUI_IPAdapter_plus.git"
APP_DIR = "/opt/comfyui"
VENV = "/opt/comfyui-venv"
GALLERY_DIR = "/opt/comfyui-gallery"
DATA_DIR = "/var/lib/comfyui"
MODELS_DIR = f"{DATA_DIR}/models"
OUTPUT_DIR = f"{DATA_DIR}/output"
WORKFLOWS_DIR = f"{DATA_DIR}/workflows"
SHARE_GROUP = "comfyshare"

MODEL_SUBDIRS = [
    "checkpoints", "loras", "vae", "clip", "clip_vision", "controlnet",
    "diffusion_models", "embeddings", "ipadapter", "text_encoders", "unet",
    "upscale_models",
]

HF = "https://huggingface.co"
SDXL_URL = f"{HF}/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"
PIXEL_LORA_URL = f"{HF}/nerijs/pixel-art-xl/resolve/main/pixel-art-xl.safetensors"
# xinsir ControlNet++ union (Apache-2.0): one SDXL model for openpose/depth/canny/lineart/...
CONTROLNET_UNION_URL = (
    f"{HF}/xinsir/controlnet-union-sdxl-1.0/resolve/main/diffusion_pytorch_model_promax.safetensors"
)
# IP-Adapter Plus SDXL (Apache-2.0) and the ViT-H image encoder it needs, under the
# filenames ComfyUI_IPAdapter_plus's unified loader looks for.
IPADAPTER_URL = f"{HF}/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"
CLIP_VISION_URL = f"{HF}/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors"


class ComfyUIApp(BaseApp):
    def _has_nvidia(self) -> bool:
        if os.path.exists("/dev/nvidia0"):
            self.log.info("NVIDIA GPU detected (/dev/nvidia0 present)")
            return True
        self.log.warn("No /dev/nvidia0 — ComfyUI will run in CPU mode (slow)")
        return False

    def _clone(self, repo: str, dest: str, ref: str) -> None:
        if os.path.isdir(os.path.join(dest, ".git")):
            self.log.info(f"Updating {dest} to {ref}")
            self.run_command(["git", "-C", dest, "fetch", "--depth", "1", "origin", ref])
            self.run_command(["git", "-C", dest, "checkout", "-f", "FETCH_HEAD"])
        else:
            self.log.info(f"Cloning {repo} ({ref}) into {dest}")
            self.run_command(["git", "clone", "--depth", "1", "--branch", ref, repo, dest])

    def _link_data_dir(self, name: str, target: str) -> None:
        """Replace a dir under ComfyUI with a symlink to the volume.

        Anything already in the dir (placeholders, or workflows saved before the
        volume existed) is copied onto the volume without overwriting first.
        """
        link = os.path.join(APP_DIR, name)
        if os.path.islink(link):
            return
        if os.path.isdir(link):
            self.run_command(["cp", "-rn", f"{link}/.", f"{target}/"])
            self.run_command(["rm", "-rf", link])
        self.create_dir(os.path.dirname(link))
        self.run_command(["ln", "-s", target, link])

    def _install_node(self, repo: str, name: str, pip: str) -> None:
        dest = f"{APP_DIR}/custom_nodes/{name}"
        self._clone(repo, dest, "main")
        if os.path.isfile(f"{dest}/requirements.txt"):
            self.run_command([
                pip, "install", "--progress-bar", "off", "-r", f"{dest}/requirements.txt",
            ], quiet=True)

    def _download_model(self, url: str, dest: str) -> None:
        if os.path.isfile(dest) and os.path.getsize(dest) > 0:
            self.log.info(f"Model already present, skipping: {dest}")
            return
        self.log.info(f"Downloading {url} -> {dest}")
        self.permissions.check_url(url)
        self.run_command([
            "curl", "-L", "--fail", "--retry", "5", "-C", "-",
            "-o", dest + ".part", url,
        ], quiet=True)
        os.replace(dest + ".part", dest)

    def install(self):
        port = self.inputs.integer("port", 8188)
        bind_address = self.inputs.string("bind_address", "0.0.0.0")
        ref = self.inputs.string("comfyui_ref", "master") or "master"
        torch_variant = self.inputs.string("torch_variant", "cu128") or "cu128"
        install_manager = self.inputs.boolean("install_manager", True)
        download_sdxl = self.inputs.boolean("download_sdxl", False)
        download_lora = self.inputs.boolean("download_pixel_art_lora", False)
        extra_args = self.inputs.string("extra_args", "")
        gallery_port = self.inputs.integer("gallery_port", 8189)
        download_controlnet = self.inputs.boolean("download_controlnet_union", False)
        install_ipadapter = self.inputs.boolean("install_ipadapter", False)
        share_gid = self.inputs.string("share_gid", "").strip()

        has_gpu = self._has_nvidia()
        if not has_gpu:
            torch_variant = "cpu"

        # 1. System packages
        self.apt_install(
            "git", "ca-certificates", "curl",
            "python3", "python3-venv", "python3-dev", "build-essential",
            "libgl1", "libglib2.0-0",
        )

        # 2. ComfyUI source
        self._clone(COMFY_REPO, APP_DIR, ref)

        # 3. Data volumes
        for sub in MODEL_SUBDIRS:
            self.create_dir(f"{MODELS_DIR}/{sub}")
        self.create_dir(OUTPUT_DIR)
        self.create_dir(WORKFLOWS_DIR)
        self._link_data_dir("models", MODELS_DIR)
        self._link_data_dir("output", OUTPUT_DIR)
        # Saved workflows (the UI's Workflows sidebar and /api/userdata/workflows)
        self._link_data_dir("user/default/workflows", WORKFLOWS_DIR)

        # 4. Python venv: torch first (from the PyTorch index), then ComfyUI reqs
        self.create_venv(VENV)
        pip = f"{VENV}/bin/pip"
        self.log.info(f"Installing PyTorch ({torch_variant}) — large download")
        self.run_command([
            pip, "install", "--progress-bar", "off",
            "torch", "torchvision", "torchaudio",
            "--index-url", f"https://download.pytorch.org/whl/{torch_variant}",
        ], quiet=True)
        self.log.info("Installing ComfyUI requirements")
        self.run_command([
            pip, "install", "--progress-bar", "off",
            "-r", f"{APP_DIR}/requirements.txt",
        ], quiet=True)

        # 5. Optional custom nodes
        if install_manager:
            self._install_node(MANAGER_REPO, "ComfyUI-Manager", pip)
        if install_ipadapter:
            self._install_node(IPADAPTER_REPO, "ComfyUI_IPAdapter_plus", pip)

        # 6. Optional starter models
        if download_sdxl:
            self._download_model(SDXL_URL, f"{MODELS_DIR}/checkpoints/sd_xl_base_1.0.safetensors")
        if download_lora:
            self._download_model(PIXEL_LORA_URL, f"{MODELS_DIR}/loras/pixel-art-xl.safetensors")
        if download_controlnet:
            self._download_model(
                CONTROLNET_UNION_URL,
                f"{MODELS_DIR}/controlnet/controlnet-union-sdxl-1.0-promax.safetensors",
            )
        if install_ipadapter:
            self._download_model(IPADAPTER_URL, f"{MODELS_DIR}/ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors")
            self._download_model(
                CLIP_VISION_URL,
                f"{MODELS_DIR}/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
            )

        # Optional shared group so host bind mounts can stay writable by a host
        # user: CT gid N appears on the host as 100000+N.
        extra_service = None
        if share_gid:
            if not share_gid.isdigit():
                raise ValueError(f"share_gid must be numeric, got {share_gid!r}")
            self.run_command(["groupadd", "-f", "-g", share_gid, SHARE_GROUP])
            extra_service = f"SupplementaryGroups={SHARE_GROUP}\nUMask=0002"
            # ComfyUI saves userdata via mkstemp (always 0600) + rename, which
            # ignores the umask; re-grant group access whenever the dir changes.
            self.write_config(
                "/etc/systemd/system/comfyui-share-perms.service",
                "[Unit]\nDescription=Keep ComfyUI workflows group-writable\n\n"
                "[Service]\nType=oneshot\n"
                f"ExecStart=/usr/bin/find {WORKFLOWS_DIR} -mindepth 1"
                " ( -type f ! -perm -g+rw -exec chmod g+rw {} + )"
                " -o ( -type d ! -perm -g+rwxs -exec chmod g+rwxs {} + )\n",
            )
            self.write_config(
                "/etc/systemd/system/comfyui-share-perms.path",
                "[Unit]\nDescription=Watch ComfyUI workflows for new files\n\n"
                f"[Path]\nPathChanged={WORKFLOWS_DIR}\n\n"
                "[Install]\nWantedBy=multi-user.target\n",
            )
            self.run_command(["systemctl", "daemon-reload"])
            self.run_command(["systemctl", "enable", "--now", "comfyui-share-perms.path"])
            self.run_command(["systemctl", "start", "comfyui-share-perms.service"])

        # 7. ComfyUI service
        args = f"--listen {bind_address} --port {port}"
        if not has_gpu:
            args += " --cpu"
        if extra_args.strip():
            args += " " + extra_args.strip()
        self.create_service(
            "comfyui",
            exec_start=f"{VENV}/bin/python {APP_DIR}/main.py {args}",
            description="ComfyUI image generation server",
            working_directory=APP_DIR,
            environment={
                "NVIDIA_VISIBLE_DEVICES": "all",
                "NVIDIA_DRIVER_CAPABILITIES": "compute,utility",
                "PYTHONUNBUFFERED": "1",
            },
            extra_service=extra_service,
        )
        # Pick up new custom nodes / args when re-provisioning an existing CT.
        self.restart_service("comfyui")

        # 8. History gallery service
        self.create_dir(GALLERY_DIR)
        self.deploy_provision_file("gallery.py", f"{GALLERY_DIR}/gallery.py", mode="0755")
        self.create_service(
            "comfyui-gallery",
            exec_start=(
                f"{VENV}/bin/python {GALLERY_DIR}/gallery.py "
                f"--output {OUTPUT_DIR} --listen {bind_address} --port {gallery_port}"
            ),
            description="ComfyUI prompt/image history gallery",
            after="comfyui.service",
            environment={"PYTHONUNBUFFERED": "1"},
        )
        self.restart_service("comfyui-gallery")

        # 9. Wait for ComfyUI
        if self.wait_for_http(f"http://127.0.0.1:{port}/system_stats", timeout=180, interval=5):
            self.log.info("ComfyUI is up")
        else:
            self.log.warn("ComfyUI did not answer within 180s — check: journalctl -u comfyui")
        if self.wait_for_http(f"http://127.0.0.1:{gallery_port}/", timeout=30, interval=2):
            self.log.info("Gallery is up")
        else:
            self.log.warn("Gallery did not answer — check: journalctl -u comfyui-gallery")

        self.log.info(f"ComfyUI: http://<ct-ip>:{port}/   Gallery: http://<ct-ip>:{gallery_port}/")
        self.log.info(f"Put models in {MODELS_DIR}/<type>/ (checkpoints, loras, ...)")


run(ComfyUIApp)
