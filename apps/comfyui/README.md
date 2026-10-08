# ComfyUI

[ComfyUI](https://github.com/comfyanonymous/ComfyUI) node-based diffusion image generation, installed natively in an unprivileged LXC (Python venv + systemd, no Docker), plus a **History Gallery** that shows every generated image with the prompt and settings that produced it.

| Service | Default port | What |
|---|---|---|
| `comfyui` | 8188 | Web UI and HTTP/WebSocket API |
| `comfyui-gallery` | 8189 | Read-only history: image grid, prompt, negative, model, LoRAs, seed, sampler, size; search; workflow download |

## GPU

Install with the `nvidia-basic` GPU profile. PyTorch's CUDA wheels include their own CUDA runtime, so the container only needs the host NVIDIA driver (550 or newer for the default `cu128` build). Without a GPU the installer switches to the CPU PyTorch build and starts ComfyUI with `--cpu`.

## Storage

| Volume | Mount in CT | Notes |
|---|---|---|
| `models` | `/var/lib/comfyui/models` | ComfyUI `models/` tree (checkpoints, loras, vae, ...). Bind it to an existing host model library to avoid re-downloading. |
| `output` | `/var/lib/comfyui/output` | Generated images. The gallery reads from here. |
| `workflows` | `/var/lib/comfyui/workflows` | Saved workflows (the UI's Workflows sidebar, `/api/userdata/workflows`). |

All three are symlinked into `/opt/comfyui`, so ComfyUI sees its normal layout. A host bind mount for `models` or `output` gets chowned to the container's root (UID 100000), which the host can still read. `workflows` keeps its host ownership (`shared_host_path`), so it can live inside a git repo.

### Keeping a host folder writable from both sides

Unprivileged containers shift IDs by 100000, and the appstore does not allow `lxc.idmap`. To share a host folder (for example `workflows`) with read-write access on both sides, use a shared group:

```bash
# host: group whose GID is 100000 + the container GID you pick (1000 here)
groupadd -g 101000 comfyshare
usermod -aG comfyshare <your-user>
chgrp comfyshare /path/to/workflows && chmod 2775 /path/to/workflows
```

Then install with **Shared Group GID** = `1000`. ComfyUI runs with that supplementary group and `UMask=0002`, so files either side creates stay group-writable.

## Inputs

- **ComfyUI Version**: git branch or tag (default `master`).
- **PyTorch Build**: `cu128` (default), `cu126` or `cpu`.
- **Install ComfyUI-Manager**: on by default.
- **Download SDXL Base 1.0** (~6.9 GB) and **pixel-art-xl LoRA** (~170 MB): off by default; skipped if the file already exists.
- **Download ControlNet Union (SDXL)** (~2.4 GB, Apache-2.0): xinsir ControlNet++ ProMax, one model for openpose, depth, canny, lineart, tile and more. Use with the core `ControlNetLoader` + `SetUnionControlNetType` nodes.
- **Install IP-Adapter Plus (SDXL)** (~3.2 GB, Apache-2.0 models): the `ComfyUI_IPAdapter_plus` node (GPL-3.0) plus `ip-adapter-plus_sdxl_vit-h` and the ViT-H image encoder, under the filenames the node's unified loader expects. Transfers style or design from a reference image.
- **Shared Group GID**: see above.
- **Extra Launch Arguments**: e.g. `--lowvram`.

## How the gallery works

ComfyUI writes the executed graph as JSON into each PNG's `prompt` text chunk. The gallery (`/opt/comfyui-gallery/gallery.py`, Python stdlib only) scans the output volume, parses those chunks and traces each sampler's positive and negative conditioning back to the text encoders. It keeps no database, so the history covers every image on the volume, including ones made before the gallery was installed.

Delete images from the detail view (button or Del key) or in bulk with **Select**. Deleted files move to `output/.trash/` and can be undone from the toast; trash older than 30 days is purged.

API: `GET /api/images?q=<search>&offset=&limit=` returns JSON, `GET /img/<path>` returns the image and `GET /workflow/<path>` returns the embedded workflow. `POST /api/delete` and `POST /api/restore` take `{"paths": [...]}` and require an `X-Gallery: 1` header.

## Using it from scripts / MCP servers

Point any ComfyUI client at `http://<ct-ip>:8188` (for example `COMFY_URL=http://<ct-ip>:8188`). Images come back over `/view`, so clients don't need filesystem access to the container.

## Operations

```bash
pct exec <ctid> -- journalctl -u comfyui -u comfyui-gallery -f
pct exec <ctid> -- systemctl restart comfyui
```
