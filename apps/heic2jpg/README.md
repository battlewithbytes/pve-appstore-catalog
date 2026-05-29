# HEIC to JPG

A zero-backend, browser-based **HEIC → JPG converter**. Drop multiple `.heic`
photos and the browser decodes them with libheif, re-encodes to JPEG, and
bundles the results into a downloadable ZIP. **Images never leave the
browser** — there is no upload or server-side processing.

This LXC just serves the static SPA over nginx; all conversion runs
client-side in a pool of Web Workers (one per CPU core, each using libheif +
OffscreenCanvas), so large batches convert in parallel and the UI stays
responsive.

## Install inputs

| Key | Default | Description |
|-----|---------|-------------|
| `port` | `80` | Port nginx listens on inside the container. |

## How it works

The web assets (HTML/JS/CSS + bundled `libheif` and `JSZip`) ship inside the
app as `provision/web.tgz`. The provision script installs `nginx-light`,
extracts the bundle to `/opt/heic2jpg/web`, and serves it. No external CDN or
network dependency at runtime.

After install, open the **Web UI** output URL and drop in your HEIC files.
