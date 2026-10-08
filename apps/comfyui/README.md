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

Both are symlinked into `/opt/comfyui`, so ComfyUI sees its normal layout. A host bind mount gets chowned to the container's root (UID 100000), which the host can still read.

## Inputs

- **ComfyUI Version**: git branch or tag (default `master`).
- **PyTorch Build**: `cu128` (default), `cu126` or `cpu`.
- **Install ComfyUI-Manager**: on by default.
- **Download SDXL Base 1.0** (~6.9 GB) and **pixel-art-xl LoRA** (~170 MB): off by default; skipped if the file already exists.
- **Extra Launch Arguments**: e.g. `--lowvram`.

## How the gallery works

ComfyUI writes the executed graph as JSON into each PNG's `prompt` text chunk. The gallery (`/opt/comfyui-gallery/gallery.py`, Python stdlib only) scans the output volume, parses those chunks and traces each sampler's positive and negative conditioning back to the text encoders. It keeps no database, so the history covers every image on the volume, including ones made before the gallery was installed.

API: `GET /api/images?q=<search>&offset=&limit=` returns JSON, `GET /img/<path>` returns the image and `GET /workflow/<path>` returns the embedded workflow.

## Using it from scripts / MCP servers

Point any ComfyUI client at `http://<ct-ip>:8188` (for example `COMFY_URL=http://<ct-ip>:8188`). Images come back over `/view`, so clients don't need filesystem access to the container.

## Operations

```bash
pct exec <ctid> -- journalctl -u comfyui -u comfyui-gallery -f
pct exec <ctid> -- systemctl restart comfyui
```
