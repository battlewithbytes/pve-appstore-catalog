#!/usr/bin/env python3
"""ComfyUI history gallery.

Serves a browsable history of every image in ComfyUI's output directory,
alongside the prompt and settings that produced it. ComfyUI embeds the
executed graph as JSON in each PNG's "prompt" text chunk, so no database is
needed: the PNGs are the history.

Stdlib only. Usage:
  gallery.py --output /var/lib/comfyui/output --listen 0.0.0.0 --port 8189
"""

import argparse
import glob
import json
import mimetypes
import os
import shutil
import struct
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TRASH = ".trash"          # inside the output dir; dot-dirs are never indexed
TRASH_DAYS = 30           # trashed files older than this are purged
PNG_SIG = b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------- metadata

def read_png_text(path):
    """Return the tEXt/zTXt/iTXt chunks of a PNG as a dict (stops at IDAT)."""
    out = {}
    try:
        with open(path, "rb") as f:
            if f.read(8) != PNG_SIG:
                return out
            while True:
                head = f.read(8)
                if len(head) < 8:
                    break
                length, ctype = struct.unpack(">I4s", head)
                if ctype == b"IDAT" or ctype == b"IEND":
                    break
                data = f.read(length)
                f.read(4)  # CRC
                try:
                    if ctype == b"tEXt":
                        k, v = data.split(b"\0", 1)
                        out[k.decode("latin-1")] = v.decode("latin-1")
                    elif ctype == b"zTXt":
                        k, rest = data.split(b"\0", 1)
                        out[k.decode("latin-1")] = zlib.decompress(rest[1:]).decode("latin-1")
                    elif ctype == b"iTXt":
                        k, rest = data.split(b"\0", 1)
                        comp, _method = rest[0], rest[1]
                        _lang, rest = rest[2:].split(b"\0", 1)
                        _tkey, text = rest.split(b"\0", 1)
                        if comp:
                            text = zlib.decompress(text)
                        out[k.decode("latin-1")] = text.decode("utf-8", "replace")
                except (ValueError, zlib.error):
                    continue
    except OSError:
        pass
    return out


def _resolve(graph, value, depth=0):
    """Follow [node_id, slot] links to a literal value where possible."""
    if depth > 8:
        return None
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
        node = graph.get(value[0]) or {}
        inputs = node.get("inputs", {})
        for key in ("text", "value", "string", "text_g", "seed", "noise_seed", "int", "float"):
            if key in inputs:
                return _resolve(graph, inputs[key], depth + 1)
        return None
    return value


def _text_of(graph, link, depth=0):
    """Collect prompt text upstream of a conditioning link."""
    if depth > 12 or not (isinstance(link, list) and len(link) == 2):
        return []
    node = graph.get(str(link[0])) or {}
    inputs = node.get("inputs", {})
    texts = []
    for key in ("text", "text_g", "text_l", "prompt"):
        if key in inputs:
            v = _resolve(graph, inputs[key])
            if isinstance(v, str) and v.strip() and v not in texts:
                texts.append(v)
    if texts:
        return texts
    # Conditioning combiners / ControlNet apply etc: walk every conditioning-ish input.
    for key, v in inputs.items():
        if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
            if any(k in key for k in ("conditioning", "positive", "negative", "cond")):
                for t in _text_of(graph, v, depth + 1):
                    if t not in texts:
                        texts.append(t)
    return texts


def summarize(graph):
    """Pull the interesting bits out of a ComfyUI API-format graph."""
    info = {"positive": [], "negative": [], "checkpoints": [], "loras": [],
            "sampler": None, "size": None, "nodes": []}
    if not isinstance(graph, dict):
        return info
    for nid, node in graph.items():
        if not isinstance(node, dict):
            continue
        ctype = node.get("class_type", "")
        inputs = node.get("inputs", {}) or {}
        info["nodes"].append(ctype)
        if "ckpt_name" in inputs or "unet_name" in inputs:
            name = inputs.get("ckpt_name") or inputs.get("unet_name")
            if isinstance(name, str) and name not in info["checkpoints"]:
                info["checkpoints"].append(name)
        if "lora_name" in inputs and isinstance(inputs["lora_name"], str):
            info["loras"].append({
                "name": inputs["lora_name"],
                "strength": inputs.get("strength_model", inputs.get("strength")),
            })
        if ("positive" in inputs or "negative" in inputs) and ("seed" in inputs or "noise_seed" in inputs or "steps" in inputs):
            info["positive"] += [t for t in _text_of(graph, inputs.get("positive")) if t not in info["positive"]]
            info["negative"] += [t for t in _text_of(graph, inputs.get("negative")) if t not in info["negative"]]
            if info["sampler"] is None:
                info["sampler"] = {
                    "node": ctype,
                    "seed": _resolve(graph, inputs.get("seed", inputs.get("noise_seed"))),
                    "steps": _resolve(graph, inputs.get("steps")),
                    "cfg": _resolve(graph, inputs.get("cfg")),
                    "sampler": inputs.get("sampler_name"),
                    "scheduler": inputs.get("scheduler"),
                    "denoise": _resolve(graph, inputs.get("denoise")),
                }
        if ctype.startswith("Empty") and "Latent" in ctype and "width" in inputs:
            w, h = _resolve(graph, inputs.get("width")), _resolve(graph, inputs.get("height"))
            if isinstance(w, int) and isinstance(h, int):
                info["size"] = f"{w}x{h}"
        if ctype == "LoadImage" and isinstance(inputs.get("image"), str):
            info.setdefault("source_images", []).append(inputs["image"])
    # Fallback: a graph with text encoders but no recognizable sampler.
    if not info["positive"]:
        for node in graph.values():
            if isinstance(node, dict) and "CLIPTextEncode" in node.get("class_type", ""):
                v = _resolve(graph, (node.get("inputs") or {}).get("text"))
                if isinstance(v, str) and v.strip() and v not in info["positive"]:
                    info["positive"].append(v)
    info["nodes"] = sorted(set(info["nodes"]))
    return info


class Index:
    """Cached scan of the output dir, keyed by (path, mtime, size)."""

    def __init__(self, root):
        self.root = os.path.realpath(root)
        self.cache = {}
        self.lock = threading.Lock()

    def entries(self):
        found = []
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if os.path.splitext(name)[1].lower() not in IMAGE_EXTS:
                    continue
                full = os.path.join(dirpath, name)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                found.append((full, st.st_mtime, st.st_size))
        found.sort(key=lambda e: e[1], reverse=True)

        result, seen = [], set()
        with self.lock:
            for full, mtime, size in found:
                seen.add(full)
                cached = self.cache.get(full)
                if cached and cached[0] == (mtime, size):
                    result.append(cached[1])
                    continue
                entry = self._build(full, mtime, size)
                self.cache[full] = ((mtime, size), entry)
                result.append(entry)
            for gone in set(self.cache) - seen:
                del self.cache[gone]
        return result

    def _build(self, full, mtime, size):
        rel = os.path.relpath(full, self.root)
        entry = {"path": rel, "mtime": mtime, "bytes": size}
        if full.lower().endswith(".png"):
            chunks = read_png_text(full)
            graph = None
            if "prompt" in chunks:
                try:
                    graph = json.loads(chunks["prompt"])
                except ValueError:
                    graph = None
            entry["has_workflow"] = "workflow" in chunks
            if graph is not None:
                entry.update(summarize(graph))
                entry["has_prompt"] = True
            elif "parameters" in chunks:  # A1111-style metadata
                entry["positive"] = [chunks["parameters"]]
        return entry


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    index: Index = None
    server_version = "comfyui-gallery/0.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode(), "application/json", {"Cache-Control": "no-store"})

    def _safe_path(self, rel):
        full = os.path.realpath(os.path.join(self.index.root, rel))
        if not full.startswith(self.index.root + os.sep) or not os.path.isfile(full):
            return None
        return full

    def _trash_root(self):
        return os.path.join(self.index.root, TRASH)

    def _trash_path(self, rel):
        trash = self._trash_root()
        full = os.path.realpath(os.path.join(trash, rel))
        if not full.startswith(trash + os.sep) or not os.path.isfile(full):
            return None
        return full

    def _purge_trash(self):
        cutoff = time.time() - TRASH_DAYS * 86400
        for dirpath, _dirs, files in os.walk(self._trash_root(), topdown=False):
            for name in files:
                full = os.path.join(dirpath, name)
                try:
                    if os.stat(full).st_ctime < cutoff:  # ctime = when it was trashed
                        os.remove(full)
                except OSError:
                    pass
            if dirpath != self._trash_root():
                try:
                    os.rmdir(dirpath)
                except OSError:
                    pass

    @staticmethod
    def _unique(dest):
        base, ext = os.path.splitext(dest)
        n = 1
        while os.path.exists(dest):
            dest = f"{base}~{n}{ext}"
            n += 1
        return dest

    def do_POST(self):
        url = urlparse(self.path)
        # A custom header forces a CORS preflight, so other sites can't post here.
        if self.headers.get("X-Gallery") != "1":
            return self._send(403, b"forbidden", "text/plain")
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 1_000_000:
                raise ValueError
            paths = json.loads(self.rfile.read(length) or b"{}").get("paths")
            if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths) or len(paths) > 5000:
                raise ValueError
        except ValueError:
            return self._send(400, b"bad request", "text/plain")

        done, failed = [], []
        if url.path == "/api/delete":
            for rel in paths:
                full = self._safe_path(rel)
                if not full or any(part.startswith(".") for part in rel.split("/")):
                    failed.append(rel)
                    continue
                dest = self._unique(os.path.join(self._trash_root(), os.path.relpath(full, self.index.root)))
                try:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    os.rename(full, dest)
                    done.append({"path": rel, "trash": os.path.relpath(dest, self._trash_root())})
                except OSError:
                    failed.append(rel)
            self._purge_trash()
            return self._json({"deleted": done, "failed": failed})
        if url.path == "/api/restore":
            for rel in paths:
                full = self._trash_path(rel)
                if not full:
                    failed.append(rel)
                    continue
                dest = self._unique(os.path.join(self.index.root, rel))
                try:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    os.rename(full, dest)
                    done.append(os.path.relpath(dest, self.index.root))
                except OSError:
                    failed.append(rel)
            return self._json({"restored": done, "failed": failed})
        self._send(404, b"not found", "text/plain")

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        if url.path in ("/", "/index.html"):
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        if url.path == "/api/images":
            items = self.index.entries()
            q = (qs.get("q", [""])[0] or "").strip().lower()
            if q:
                def hay(e):
                    parts = [e["path"]] + e.get("positive", []) + e.get("negative", []) + e.get("checkpoints", [])
                    parts += [l["name"] for l in e.get("loras", [])]
                    return " ".join(str(p) for p in parts).lower()
                terms = q.split()
                items = [e for e in items if all(t in hay(e) for t in terms)]
            try:
                offset = max(0, int(qs.get("offset", ["0"])[0]))
                limit = min(500, max(1, int(qs.get("limit", ["120"])[0])))
            except ValueError:
                offset, limit = 0, 120
            return self._json({"total": len(items), "items": items[offset:offset + limit]})
        if url.path.startswith("/img/"):
            full = self._safe_path(unquote(url.path[5:]))
            if not full:
                return self._send(404, b"not found", "text/plain")
            with open(full, "rb") as f:
                body = f.read()
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            return self._send(200, body, ctype, {"Cache-Control": "public, max-age=86400"})
        if url.path.startswith("/workflow/"):
            full = self._safe_path(unquote(url.path[10:]))
            chunks = read_png_text(full) if full else {}
            key = "workflow" if "workflow" in chunks else "prompt"
            if key not in chunks:
                return self._send(404, b"no workflow", "text/plain")
            name = os.path.splitext(os.path.basename(full))[0] + ".json"
            return self._send(200, chunks[key].encode(), "application/json",
                              {"Content-Disposition": f"attachment; filename=\"{quote(name)}\""})
        if url.path == "/favicon.ico":
            icons = glob.glob(os.path.join(
                os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                "comfyui-venv", "lib", "python3*", "site-packages",
                "comfyui_frontend_package", "static", "assets", "favicon.ico"))
            if icons:
                with open(icons[0], "rb") as f:
                    return self._send(200, f.read(), "image/x-icon", {"Cache-Control": "public, max-age=86400"})
            return self._send(404, b"", "text/plain")
        if url.path == "/healthz":
            return self._json({"ok": True})
        self._send(404, b"not found", "text/plain")


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ComfyUI History</title>
<style>
:root{--bg:#f6f6f4;--panel:#fff;--fg:#1d1d1b;--muted:#6b6b66;--line:#e2e1dc;--accent:#3b6fd8;--chip:#eeede8;--check:#e8e8e3;--danger:#c4372d}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--panel:#1e1e1c;--fg:#ecebe6;--muted:#9a9993;--line:#2f2f2c;--accent:#7aa2f7;--chip:#2a2a27;--check:#232321;--danger:#f2786d}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
h1{font-size:16px;margin:0;font-weight:600}
#count{color:var(--muted);font-size:13px}
#q{flex:1;min-width:180px;max-width:520px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--fg);font:inherit}
label.t{display:flex;gap:6px;align-items:center;color:var(--muted);font-size:13px;cursor:pointer}
main{padding:16px}
h2{font-size:13px;font-weight:600;color:var(--muted);margin:18px 0 8px;text-transform:uppercase;letter-spacing:.04em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--tile,180px),1fr));gap:10px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden;cursor:pointer;display:flex;flex-direction:column}
.card:focus-visible,.card:hover{outline:2px solid var(--accent);outline-offset:-1px}
.thumb{aspect-ratio:1;background:repeating-conic-gradient(var(--check) 0 25%,transparent 0 50%) 0 0/16px 16px;display:flex;align-items:center;justify-content:center}
.thumb img{max-width:100%;max-height:100%;object-fit:contain}
.pix .thumb img,.pix #big{image-rendering:pixelated}
.cap{padding:7px 9px;font-size:12px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.9em}
#more{display:block;margin:20px auto;padding:9px 18px;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--fg);font:inherit;cursor:pointer}
#empty{color:var(--muted);text-align:center;padding:60px 16px}
dialog{border:none;padding:0;background:var(--panel);color:var(--fg);border-radius:12px;width:min(1200px,96vw);max-height:94vh}
dialog::backdrop{background:rgba(0,0,0,.6)}
.dv{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(280px,1fr);max-height:94vh}
@media (max-width:760px){.dv{grid-template-columns:1fr;overflow:auto}}
.stage{background:repeating-conic-gradient(var(--check) 0 25%,transparent 0 50%) 0 0/20px 20px;display:flex;align-items:center;justify-content:center;min-height:300px}
#big{max-width:100%;max-height:94vh;object-fit:contain}
.meta{padding:16px 18px;overflow:auto;max-height:94vh}
.meta h3{margin:14px 0 4px;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;display:flex;justify-content:space-between;align-items:center}
.meta pre{white-space:pre-wrap;word-break:break-word;margin:0;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--chip);padding:8px 10px;border-radius:8px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{background:var(--chip);border-radius:999px;padding:3px 10px;font-size:12px}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.btn{border:1px solid var(--line);background:var(--panel);color:var(--fg);border-radius:8px;padding:6px 12px;font:inherit;font-size:13px;cursor:pointer;text-decoration:none}
.btn.sm{padding:2px 8px;font-size:11px;text-transform:none;letter-spacing:0}
.top{display:flex;justify-content:space-between;align-items:start;gap:8px}
.path{font-size:12px;color:var(--muted);word-break:break-all}
.btn.danger{color:var(--danger);border-color:var(--danger)}
.btn.on{background:var(--accent);border-color:var(--accent);color:#fff}
.card{position:relative}
.selecting .card{cursor:copy}
.card.sel{outline:3px solid var(--accent);outline-offset:-2px}
.card.sel::after{content:"✓";position:absolute;top:6px;right:6px;width:22px;height:22px;border-radius:50%;background:var(--accent);color:#fff;font-size:13px;display:flex;align-items:center;justify-content:center}
#toast{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);background:var(--fg);color:var(--bg);padding:10px 14px;border-radius:10px;display:flex;gap:12px;align-items:center;z-index:20;box-shadow:0 4px 18px rgba(0,0,0,.25)}
#toast button{background:none;border:none;color:var(--accent);font:inherit;font-weight:600;cursor:pointer}
</style></head>
<body>
<header>
  <h1>ComfyUI History</h1><span id="count"></span>
  <input id="q" type="search" placeholder="Search prompts, models, LoRAs, filenames…" autocomplete="off">
  <label class="t"><input type="checkbox" id="pix"> Pixel-perfect</label>
  <label class="t">Size <input type="range" id="tile" min="100" max="360" value="180"></label>
  <button class="btn" id="selbtn" title="Select images to delete (Esc to exit)">Select</button>
  <button class="btn danger" id="delsel" hidden>Delete selected</button>
</header>
<main><div id="list"></div><div id="empty" hidden>No images yet. Generate something in ComfyUI and it will show up here.</div>
<button id="more" hidden>Load more</button></main>
<dialog id="dlg"><div class="dv">
  <div class="stage"><img id="big" alt=""></div>
  <div class="meta">
    <div class="top"><div><div id="when"></div><div class="path" id="dpath"></div></div>
      <button class="btn" id="close" aria-label="Close">✕</button></div>
    <div id="fields"></div>
    <div class="row">
      <a class="btn" id="open" target="_blank" rel="noopener">Open full size</a>
      <a class="btn" id="wf">Download workflow</a>
      <button class="btn" id="prev">← Prev</button><button class="btn" id="next">Next →</button>
      <button class="btn danger" id="del" title="Delete (Del key)">Delete</button>
    </div>
  </div></div></dialog>
<div id="toast" hidden><span id="tmsg"></span><button id="undo">Undo</button></div>
<script>
const $=s=>document.querySelector(s);
const PAGE=120;let items=[],total=0,cur=-1,q="",timer,selecting=false,toastTimer;const sel=new Set();
const store={get(k){try{return localStorage.getItem(k)}catch(e){return null}},set(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
function esc(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function imgUrl(e){return "/img/"+e.path.split("/").map(encodeURIComponent).join("/")+"?v="+e.mtime}
function day(t){const d=new Date(t*1000);return d.toLocaleDateString(undefined,{weekday:"short",year:"numeric",month:"short",day:"numeric"})}
async function load(reset){
  if(reset){items=[];$("#list").innerHTML=""}
  const r=await fetch(`/api/images?offset=${items.length}&limit=${PAGE}&q=${encodeURIComponent(q)}`);
  const j=await r.json();total=j.total;const start=items.length;items=items.concat(j.items);render(start);
}
function render(start){
  const list=$("#list");let grid=list.lastElementChild,lastDay=start?day(items[start-1].mtime):null;
  for(let i=start;i<items.length;i++){
    const e=items[i],d=day(e.mtime);
    if(d!==lastDay){const h=document.createElement("h2");h.textContent=d;list.append(h);grid=document.createElement("div");grid.className="grid";list.append(grid);lastDay=d}
    const c=document.createElement("div");c.className="card"+(sel.has(e.path)?" sel":"");c.tabIndex=0;
    c.innerHTML=`<div class="thumb"><img loading="lazy" src="${imgUrl(e)}" alt=""></div><div class="cap">${esc((e.positive||[])[0]||e.path)}</div>`;
    const act=()=>{if(!selecting)return show(i);sel.has(e.path)?sel.delete(e.path):sel.add(e.path);c.classList.toggle("sel",sel.has(e.path));updSel()};
    c.onclick=act;c.onkeydown=ev=>{if(ev.key==="Enter"||(selecting&&ev.key===" ")){ev.preventDefault();act()}};grid.append(c);
  }
  $("#count").textContent=`${total} image${total===1?"":"s"}`;
  $("#more").hidden=items.length>=total;$("#empty").hidden=total>0;
}
function field(title,body,copy){return `<h3>${title}${copy?` <button class="btn sm" data-copy="${esc(copy)}">Copy</button>`:""}</h3>${body}`}
function show(i){
  cur=i;const e=items[i];if(!e)return;
  $("#big").src=imgUrl(e);$("#open").href=imgUrl(e);
  $("#when").textContent=new Date(e.mtime*1000).toLocaleString();$("#dpath").textContent=e.path;
  $("#wf").hidden=!(e.has_workflow||e.has_prompt);$("#wf").href="/workflow/"+e.path.split("/").map(encodeURIComponent).join("/");
  let h="";
  if(e.positive&&e.positive.length)h+=field("Prompt",`<pre>${esc(e.positive.join("\n\n"))}</pre>`,e.positive.join("\n\n"));
  if(e.negative&&e.negative.length)h+=field("Negative",`<pre>${esc(e.negative.join("\n\n"))}</pre>`,e.negative.join("\n\n"));
  if(e.checkpoints&&e.checkpoints.length)h+=field("Model",`<div class="chips">${e.checkpoints.map(c=>`<span class="chip">${esc(c)}</span>`).join("")}</div>`);
  if(e.loras&&e.loras.length)h+=field("LoRAs",`<div class="chips">${e.loras.map(l=>`<span class="chip">${esc(l.name)}${l.strength!=null?" · "+esc(l.strength):""}</span>`).join("")}</div>`);
  const s=e.sampler;
  if(s){const kv=[["seed",s.seed],["steps",s.steps],["cfg",s.cfg],["sampler",s.sampler],["scheduler",s.scheduler],["denoise",s.denoise],["size",e.size]].filter(x=>x[1]!=null&&x[1]!=="");
    h+=field("Settings",`<div class="chips">${kv.map(([k,v])=>`<span class="chip">${k}: ${esc(v)}</span>`).join("")}</div>`)}
  if(e.source_images)h+=field("Source images",`<div class="chips">${e.source_images.map(c=>`<span class="chip">${esc(c)}</span>`).join("")}</div>`);
  if(!h)h=`<p style="color:var(--muted)">No generation metadata embedded in this file.</p>`;
  h+=`<p class="path">${(e.bytes/1024).toFixed(0)} KB</p>`;
  $("#fields").innerHTML=h;
  if(!$("#dlg").open)$("#dlg").showModal();
}
document.addEventListener("click",async ev=>{const b=ev.target.closest("[data-copy]");if(!b)return;
  try{await navigator.clipboard.writeText(b.dataset.copy);b.textContent="Copied"}catch(e){b.textContent="Copy failed"}setTimeout(()=>b.textContent="Copy",1200)});
function updSel(){const n=sel.size;$("#delsel").hidden=!selecting;$("#delsel").disabled=!n;$("#delsel").textContent=n?`Delete ${n}`:"Delete selected"}
function setSelecting(on){selecting=on;if(!on)sel.clear();document.body.classList.toggle("selecting",on);$("#selbtn").classList.toggle("on",on);$("#selbtn").textContent=on?"Done":"Select";
  document.querySelectorAll(".card.sel").forEach(c=>c.classList.remove("sel"));updSel()}
function rerender(){$("#list").innerHTML="";render(0)}
const api=(path,paths)=>fetch(path,{method:"POST",headers:{"Content-Type":"application/json","X-Gallery":"1"},body:JSON.stringify({paths})}).then(r=>{if(!r.ok)throw new Error(r.status);return r.json()});
function toast(msg,onUndo){clearTimeout(toastTimer);$("#tmsg").textContent=msg;$("#undo").hidden=!onUndo;$("#undo").onclick=async()=>{$("#toast").hidden=true;await onUndo()};
  $("#toast").hidden=false;toastTimer=setTimeout(()=>$("#toast").hidden=true,10000)}
async function del(paths){
  if(!paths.length)return;
  let res;try{res=await api("/api/delete",paths)}catch(e){return toast("Delete failed ("+e.message+")")}
  const gone=new Set(res.deleted.map(d=>d.path));
  items=items.filter(e=>!gone.has(e.path));total-=gone.size;gone.forEach(p=>sel.delete(p));rerender();updSel();
  const n=gone.size;
  toast(`Deleted ${n} image${n===1?"":"s"}`+(res.failed.length?` (${res.failed.length} failed)`:""),n?async()=>{
    try{const r=await api("/api/restore",res.deleted.map(d=>d.trash));toast(`Restored ${r.restored.length}`)}catch(e){toast("Restore failed")}
    await load(true)}:null);
  return gone;
}
$("#del").onclick=async()=>{const e=items[cur];if(!e)return;const i=cur;await del([e.path]);
  if(items[i])show(i);else if(i>0)show(i-1);else $("#dlg").close()};
$("#selbtn").onclick=()=>setSelecting(!selecting);
$("#delsel").onclick=async()=>{await del([...sel]);setSelecting(false)};
$("#close").onclick=()=>$("#dlg").close();
$("#dlg").addEventListener("click",ev=>{if(ev.target===$("#dlg"))$("#dlg").close()});
$("#prev").onclick=()=>cur>0&&show(cur-1);
$("#next").onclick=async()=>{if(cur+1>=items.length&&items.length<total)await load(false);if(cur+1<items.length)show(cur+1)};
document.addEventListener("keydown",ev=>{
  if(!$("#dlg").open){if(selecting&&ev.key==="Escape")setSelecting(false);if(selecting&&ev.key==="Delete"&&sel.size)$("#delsel").click();return}
  if(ev.key==="ArrowLeft")$("#prev").click();if(ev.key==="ArrowRight")$("#next").click();if(ev.key==="Delete")$("#del").click()});
$("#more").onclick=()=>load(false);
$("#q").oninput=ev=>{clearTimeout(timer);timer=setTimeout(()=>{q=ev.target.value.trim();load(true)},250)};
const pix=$("#pix");pix.checked=store.get("pix")!=="0";document.body.classList.toggle("pix",pix.checked);
pix.onchange=()=>{document.body.classList.toggle("pix",pix.checked);store.set("pix",pix.checked?"1":"0")};
const tile=$("#tile");tile.value=store.get("tile")||180;document.body.style.setProperty("--tile",tile.value+"px");
tile.oninput=()=>{document.body.style.setProperty("--tile",tile.value+"px");store.set("tile",tile.value)};
load(true);
setInterval(async()=>{if(q||selecting||$("#dlg").open)return;const r=await fetch("/api/images?limit=1");const j=await r.json();if(j.total!==total)load(true)},15000);
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output", default="/var/lib/comfyui/output")
    ap.add_argument("--listen", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8189)
    args = ap.parse_args()
    Handler.index = Index(args.output)
    srv = ThreadingHTTPServer((args.listen, args.port), Handler)
    print(f"gallery: serving {Handler.index.root} on http://{args.listen}:{args.port}/", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
