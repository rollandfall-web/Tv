#!/usr/bin/env python3
"""Clip Maker app: the clip maker in your web browser, no typing commands.

Start it by double-clicking "Clip Maker.command" (Mac) or "Clip Maker.bat"
(Windows), or run:  python3 clipper/app.py

It runs only on your own computer (http://127.0.0.1) and saves clips to
Movies/Clip Maker (Mac) or Videos/Clip Maker (Windows).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import clip      # noqa: E402
import captions  # noqa: E402
import finder    # noqa: E402


def _raise(msg):
    raise RuntimeError(msg)


clip.die = _raise   # in the app, errors are shown on the page instead of exiting

home = os.path.expanduser("~")
_base = next((os.path.join(home, d) for d in ("Movies", "Videos")
              if os.path.isdir(os.path.join(home, d))), home)
OUT_DIR = os.path.join(_base, "Clip Maker")
CACHE_DIR = os.path.join(tempfile.gettempdir(), "clipmaker_cache")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

JOBS = {}
WORDS = {}           # (url, browser) -> caption words for the whole video
LOCK = threading.Lock()


# ---------------------------------------------------------------- jobs

class Job:
    def __init__(self):
        self.id = uuid.uuid4().hex[:12]
        self.status = "running"
        self.lines = []
        self.result = None
        self.error = None

    def log(self, msg):
        for line in str(msg).splitlines():
            if line.strip():
                self.lines.append(line.rstrip())
        del self.lines[:-200]


def start_job(fn, *args):
    job = Job()
    JOBS[job.id] = job

    def runner():
        try:
            job.result = fn(job, *args)
            job.status = "done"
        except Exception as err:  # shown to the user on the page
            job.error = str(err) or err.__class__.__name__
            job.status = "error"
    threading.Thread(target=runner, daemon=True).start()
    return job.id


def use_browser(name):
    clip.BROWSER = name or None


# ---------------------------------------------------------------- work

def job_find(job, p):
    use_browser(p.get("browser"))
    url = p["url"].strip()
    local = clip.is_local_file(url)
    with tempfile.TemporaryDirectory(prefix="clipfind_") as work:
        title, picks = finder.find_clips(
            url, is_local=local, ytdlp=None if local else clip.ytdlp_cmd(),
            ffmpeg=clip.find_ffmpeg(), workdir=work,
            count=int(p.get("count") or 5), min_len=float(p.get("min") or 15),
            max_len=float(p.get("max") or 60), use_ai=True, log=job.log)
    return {"title": title, "clips": picks}


def section_key(url, start, end, quality):
    return hashlib.sha1(f"{url}|{start:.2f}|{end:.2f}|{quality}".encode()).hexdigest()[:16]


def ensure_section(job, url, start, end, quality=1080):
    """Download [start, end] once; reuse it for preview and final render."""
    key = section_key(url, start, end, quality)
    folder = os.path.join(CACHE_DIR, key)
    path = os.path.join(folder, "section.mp4")
    if os.path.isfile(path):
        return key, path
    os.makedirs(folder, exist_ok=True)
    job.log("Downloading this part of the video...")
    raw = clip.fetch_section(url, start, end, quality, folder, clip.find_ffmpeg())
    os.replace(raw, path)
    return key, path


def video_words(job, url, browser):
    if clip.is_local_file(url):
        return []
    k = (url, browser or "")
    if k not in WORDS:
        job.log("Getting caption timings...")
        with tempfile.TemporaryDirectory(prefix="clipwords_") as work:
            WORDS[k] = captions.fetch_words(url, clip.ytdlp_cmd(), work)
    return WORDS[k]


def job_prepare(job, p):
    use_browser(p.get("browser"))
    url = p["url"].strip()
    start, end = float(p["start"]), float(p["end"])
    if end - start < 1:
        raise RuntimeError("The clip must be at least 1 second long.")
    key, path = ensure_section(job, url, start, end)
    words = captions.words_in(video_words(job, url, p.get("browser")), start, end)
    w, h = clip.video_size(path, clip.find_ffmpeg())
    return {"video": f"/media/{key}/section.mp4", "width": w, "height": h,
            "words": [{"s": round(a, 3), "e": round(b, 3), "w": t} for a, b, t in words]}


def job_make(job, p):
    use_browser(p.get("browser"))
    url = p["url"].strip()
    start, end = float(p["start"]), float(p["end"])
    kind = "vertical" if p.get("format") == "vertical" else "mp4"
    ffmpeg = clip.find_ffmpeg()
    _, path = ensure_section(job, url, start, end)
    words = p.get("words") or None
    lines = p.get("lines") or None
    if words and not p.get("captions", True):
        words = lines = None
    if words and not clip.has_captions_support(ffmpeg):
        job.log("Your ffmpeg can't draw captions (Mac fix: brew install ffmpeg-full). "
                "Making the clip without them.")
        words = lines = None
    title = (p.get("title") or "").strip() or clip.video_title(url)
    base = clip.safe_name(title)
    suffix = "_vertical" if kind == "vertical" else ""
    name = f"{base}_{clip.label_time(start)}-{clip.label_time(end)}{suffix}.mp4"
    dest = os.path.join(OUT_DIR, name)
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(OUT_DIR, name.replace(".mp4", f"_{n}.mp4"))
        n += 1
    job.log("Making the clip (this can take a minute)...")
    with tempfile.TemporaryDirectory(prefix="clipmake_") as work:
        raw = os.path.join(work, "raw.mp4")
        shutil.copy(path, raw)
        style = p.get("style") or "bold"
        clip.convert(raw, dest, kind, ffmpeg, 480, 12, words, style, lines)
    return {"file": "/out/" + os.path.basename(dest), "name": os.path.basename(dest)}


def info():
    ffmpeg_ok, caps = True, False
    try:
        caps = clip.has_captions_support(clip.find_ffmpeg())
    except RuntimeError:
        ffmpeg_ok = False
    try:
        clip.ytdlp_cmd()
        ytdlp_ok = True
    except RuntimeError:
        ytdlp_ok = False
    return {
        "out_dir": OUT_DIR, "ffmpeg": ffmpeg_ok, "captions": caps, "ytdlp": ytdlp_ok,
        "ai": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "presets": {name: {"vertical": captions.preset(name, True),
                           "landscape": captions.preset(name, False)}
                    for name in captions.PRESETS},
        "mac": sys.platform == "darwin",
    }


def open_folder():
    if sys.platform == "darwin":
        subprocess.Popen(["open", OUT_DIR])
    elif os.name == "nt":
        os.startfile(OUT_DIR)  # noqa: S606 (Windows only)
    else:
        subprocess.Popen(["xdg-open", OUT_DIR])


# ---------------------------------------------------------------- web server

class Handler(BaseHTTPRequestHandler):
    server_version = "ClipMaker"

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

    def host_ok(self):
        port = self.server.server_address[1]
        return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, ctype):
        size = os.path.getsize(path)
        start, end = 0, size - 1
        rng = self.headers.get("Range")
        m = re.match(r"bytes=(\d*)-(\d*)", rng or "")
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(path, "rb") as fh:
            fh.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = fh.read(min(left, 1 << 16))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def safe_path(self, root, rel):
        full = os.path.realpath(os.path.join(root, unquote(rel)))
        if not full.startswith(os.path.realpath(root) + os.sep) or not os.path.isfile(full):
            return None
        return full

    def do_GET(self):
        if not self.host_ok():
            return self.send_error(403)
        path = urlparse(self.path).path
        if path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if path == "/api/info":
            return self.send_json(info())
        if path.startswith("/api/job/"):
            job = JOBS.get(path.rsplit("/", 1)[-1])
            if not job:
                return self.send_json({"error": "unknown job"}, 404)
            return self.send_json({"status": job.status, "log": job.lines[-6:],
                                   "result": job.result, "error": job.error})
        for prefix, root in (("/media/", CACHE_DIR), ("/out/", OUT_DIR)):
            if path.startswith(prefix):
                full = self.safe_path(root, path[len(prefix):])
                if not full:
                    return self.send_error(404)
                return self.send_file(full, "video/mp4")
        self.send_error(404)

    def do_POST(self):
        if not self.host_ok():
            return self.send_error(403)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            p = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.send_json({"error": "bad request"}, 400)
        path = urlparse(self.path).path
        if path == "/api/find":
            return self.send_json({"job": start_job(job_find, p)})
        if path == "/api/prepare":
            return self.send_json({"job": start_job(job_prepare, p)})
        if path == "/api/make":
            return self.send_json({"job": start_job(job_make, p)})
        if path == "/api/open":
            open_folder()
            return self.send_json({"ok": True})
        self.send_error(404)


def main():
    server = None
    for port in range(8765, 8785):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if not server:
        print("Couldn't start: ports 8765-8784 are all busy.")
        sys.exit(1)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print("\n  Clip Maker is running at " + url)
    print("  Your browser should open by itself. If not, open that address.")
    print("  Keep this window open while you use it. Close it to stop.\n")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clip Maker</title>
<style>
:root{--bg:#f6f6f4;--card:#fff;--ink:#16161a;--muted:#6b6b76;--line:#e3e3e0;--accent:#ff3d5a;--accent-ink:#fff;--soft:#f0f0ed;--ok:#1f9d55;--err:#d12f2f}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121215;--card:#1b1b20;--ink:#f1f1f3;--muted:#9a9aa6;--line:#2c2c33;--soft:#24242a}}
:root[data-theme="dark"]{--bg:#121215;--card:#1b1b20;--ink:#f1f1f3;--muted:#9a9aa6;--line:#2c2c33;--soft:#24242a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}
h2{font-size:17px;margin:0 0 12px}
h3{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:18px 0 8px}
.sub{color:var(--muted);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:16px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
input[type=text],input[type=number],select{font:inherit;color:var(--ink);background:var(--soft);border:1px solid var(--line);border-radius:9px;padding:9px 11px;min-width:0}
input[type=text].url{flex:1 1 320px}
input[type=number]{width:76px}
button{font:inherit;font-weight:600;border:0;border-radius:9px;padding:10px 16px;cursor:pointer;background:var(--soft);color:var(--ink)}
button.primary{background:var(--accent);color:var(--accent-ink)}
button:disabled{opacity:.5;cursor:default}
button.small{padding:6px 10px;font-size:13px}
label{color:var(--muted);font-size:13px}
.status{display:none;margin-top:12px;padding:10px 12px;border-radius:9px;background:var(--soft);font-size:13px;white-space:pre-wrap}
.status.err{color:var(--err)}
.spin{display:inline-block;width:12px;height:12px;border:2px solid var(--muted);border-top-color:transparent;border-radius:50%;animation:s .8s linear infinite;margin-right:8px;vertical-align:-1px}
@keyframes s{to{transform:rotate(360deg)}}
.pick{display:flex;gap:12px;align-items:center;padding:12px 0;border-top:1px solid var(--line)}
.pick:first-of-type{border-top:0}
.score{flex:none;width:48px;height:48px;border-radius:12px;display:grid;place-items:center;font-weight:700;background:var(--soft)}
.pick .meta{flex:1;min-width:0}
.pick .t{font-weight:600}
.pick .r{color:var(--muted);font-size:13px}
.editor{display:grid;grid-template-columns:minmax(260px,360px) 1fr;gap:20px;align-items:start}
@media (max-width:760px){.editor{grid-template-columns:1fr}}
.frame{position:relative;background:#000;border-radius:12px;overflow:hidden;margin:0 auto;width:100%}
.frame.v{aspect-ratio:9/16;max-width:340px}
.frame.h{aspect-ratio:16/9}
.frame video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.frame.h video{object-fit:contain}
.cap{position:absolute;left:6%;right:6%;text-align:center;pointer-events:none;line-height:1.15}
.cap .box{display:inline;box-decoration-break:clone;-webkit-box-decoration-break:clone}
.cap span.wd{display:inline-block;transition:transform .08s;margin:0 .06em}
.lines{max-height:300px;overflow:auto;border:1px solid var(--line);border-radius:10px}
.line{display:flex;gap:8px;align-items:center;padding:6px 8px;border-top:1px solid var(--line)}
.line:first-child{border-top:0}
.line.now{background:var(--soft)}
.line .tm{flex:none;width:44px;font-size:12px;color:var(--muted);cursor:pointer}
.line input{flex:1}
.ctl{display:grid;grid-template-columns:130px 1fr 44px;gap:8px;align-items:center;margin:6px 0}
.ctl output{font-size:12px;color:var(--muted);text-align:right}
.ctl input[type=range]{width:100%}
.ctl input[type=color]{width:44px;height:30px;border:0;background:none;padding:0}
.seg{display:inline-flex;background:var(--soft);border-radius:9px;padding:3px}
.seg button{background:none;padding:7px 12px}
.seg button.on{background:var(--card);box-shadow:0 1px 2px rgba(0,0,0,.15)}
.hint{color:var(--muted);font-size:12px;margin:6px 0 0}
.result video{width:100%;max-width:340px;border-radius:12px;display:block;margin:10px 0}
.warn{background:#fff4d6;color:#6b4b00;border-radius:9px;padding:10px 12px;font-size:13px;margin-bottom:12px}
@media (prefers-color-scheme:dark){.warn{background:#3a2f12;color:#f3d98b}}
.hidden{display:none!important}
</style>
</head>
<body>
<main>
  <h1>Clip Maker</h1>
  <p class="sub">Paste a YouTube link, find the best moments, style the captions, and make your clip.</p>
  <div id="warn"></div>

  <section class="card">
    <h2>1. Video</h2>
    <div class="row">
      <input id="url" class="url" type="text" placeholder="https://www.youtube.com/watch?v=...">
      <select id="browser" title="Use this browser's YouTube sign-in (needed for age-restricted videos)">
        <option value="">No sign-in</option><option value="chrome">Chrome sign-in</option>
        <option value="safari">Safari sign-in</option><option value="firefox">Firefox sign-in</option>
        <option value="edge">Edge sign-in</option><option value="brave">Brave sign-in</option>
      </select>
    </div>
    <div class="row" style="margin-top:10px">
      <label>Clips <input id="count" type="number" min="1" max="15" value="5"></label>
      <label>Length <input id="minl" type="number" min="3" value="15"> to <input id="maxl" type="number" min="5" value="60"> sec</label>
      <button id="findBtn" class="primary">Find best moments</button>
    </div>
    <div class="row" style="margin-top:10px">
      <label>Or pick the time yourself:</label>
      <input id="ms" type="text" placeholder="1:23" style="width:80px"> to
      <input id="me" type="text" placeholder="1:45" style="width:80px">
      <button id="manualBtn">Edit this part</button>
    </div>
    <div id="findStatus" class="status"></div>
  </section>

  <section id="picksCard" class="card hidden">
    <h2>2. Best moments</h2>
    <div id="picks"></div>
  </section>

  <section id="editCard" class="card hidden">
    <h2>3. Edit &amp; make</h2>
    <div id="prepStatus" class="status"></div>
    <div id="editor" class="editor hidden">
      <div>
        <div id="frame" class="frame v"><video id="vid" controls playsinline preload="auto"></video><div id="cap" class="cap"></div></div>
        <p class="hint" style="text-align:center">Preview is close to the final clip; the made clip is exact.</p>
      </div>
      <div>
        <div class="row">
          <div class="seg" id="fmtSeg"><button data-v="vertical" class="on">Vertical 9:16</button><button data-v="landscape">Landscape</button></div>
          <label class="row" style="gap:6px"><input id="capOn" type="checkbox" checked> Captions</label>
        </div>

        <div id="capPanel">
        <h3>Style preset</h3>
        <div class="row"><button class="small" data-preset="bold">Bold (yellow pop)</button><button class="small" data-preset="clean">Clean</button></div>

        <h3>Words</h3>
        <div id="lines" class="lines"></div>
        <div class="row" style="margin-top:8px">
          <button class="small" id="addLine">+ Add line here</button>
          <label style="flex:1">Wrap a word in *stars* to always highlight it. Click a time to jump there.</label>
        </div>
        <div class="ctl"><label>Words per line</label><input id="wpl" type="range" min="1" max="8" step="1"><output></output></div>

        <h3>Look</h3>
        <div class="ctl"><label>Font</label><select id="font">
          <option>Arial</option><option>Arial Black</option><option>Impact</option><option>Helvetica Neue</option>
          <option>Avenir Next</option><option>Futura</option><option>Verdana</option><option>Georgia</option><option>Comic Sans MS</option>
        </select><span></span></div>
        <div class="ctl"><label>Size</label><input id="size" type="range" min="1.5" max="14" step="0.1"><output></output></div>
        <div class="ctl"><label>Position (from bottom)</label><input id="position" type="range" min="2" max="90" step="1"><output></output></div>
        <div class="ctl"><label>Text color</label><input id="color" type="color"><span></span></div>
        <div class="ctl"><label>Highlight color</label><input id="highlight" type="color"><span></span></div>
        <div class="ctl"><label>Outline</label><input id="outline" type="range" min="0" max="25" step="1"><output></output></div>
        <div class="ctl"><label>Outline color</label><input id="outline_color" type="color"><span></span></div>
        <div class="row" style="margin:8px 0">
          <label class="row" style="gap:6px"><input id="bold" type="checkbox"> Bold</label>
          <label class="row" style="gap:6px"><input id="uppercase" type="checkbox"> UPPERCASE</label>
          <label class="row" style="gap:6px"><input id="hlword" type="checkbox"> Highlight spoken word</label>
          <label class="row" style="gap:6px"><input id="pop" type="checkbox"> Pop</label>
          <label class="row" style="gap:6px"><input id="shadow" type="checkbox"> Shadow</label>
        </div>

        <h3>Opacity</h3>
        <div class="ctl"><label>Text opacity</label><input id="text_opacity" type="range" min="0" max="100" step="5"><output></output></div>
        <div class="row" style="margin:8px 0"><label class="row" style="gap:6px"><input id="box" type="checkbox"> Background box</label></div>
        <div class="ctl"><label>Box color</label><input id="box_color" type="color"><span></span></div>
        <div class="ctl"><label>Box opacity</label><input id="box_opacity" type="range" min="0" max="100" step="5"><output></output></div>
        </div>

        <div class="row" style="margin-top:18px">
          <button id="makeBtn" class="primary">Make clip</button>
          <button id="openBtn">Open clips folder</button>
        </div>
        <div id="makeStatus" class="status"></div>
        <div id="result" class="result"></div>
      </div>
    </div>
  </section>
</main>

<script>
const $ = s => document.querySelector(s);
const S = {info:null, title:"", clip:null, fmt:"vertical", style:{}, lines:[], dims:[1920,1080]};
const STYLE_KEYS = ["font","size","position","color","highlight","outline","outline_color","text_opacity","box_color","box_opacity","words_per_line"];
const CHECK_KEYS = ["bold","uppercase","pop","shadow","box"];

const fmtT = t => { t = Math.max(0, t); const m = Math.floor(t/60), s = Math.floor(t%60); return m + ":" + String(s).padStart(2,"0"); };
function parseT(x){ x = String(x).trim(); if(!x) return NaN; if(/^\d+(\.\d+)?$/.test(x)) return +x;
  const p = x.split(":").map(Number); if(p.some(isNaN)) return NaN; return p.reduce((a,b)=>a*60+b,0); }
async function api(path, body){ const r = await fetch(path, body ? {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)} : {}); return r.json(); }

function status(el, msg, kind){ el.style.display = msg ? "block" : "none"; el.className = "status" + (kind==="err" ? " err" : "");
  el.innerHTML = (kind==="busy" ? '<span class="spin"></span>' : "") + escapeHtml(msg || ""); }
function escapeHtml(s){ return String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }

async function runJob(path, body, el){
  const {job} = await api(path, body);
  return new Promise((resolve, reject) => {
    const tick = async () => {
      const j = await api("/api/job/" + job);
      if (j.status === "running"){ status(el, (j.log.slice(-1)[0] || "Working..."), "busy"); setTimeout(tick, 700); }
      else if (j.status === "done"){ status(el, ""); resolve(j.result); }
      else { status(el, j.error, "err"); reject(new Error(j.error)); }
    };
    tick();
  });
}

// ---------------------------------------------------------------- step 1-2
$("#findBtn").onclick = async () => {
  const url = $("#url").value.trim(); if(!url) return $("#url").focus();
  $("#findBtn").disabled = true;
  try {
    const r = await runJob("/api/find", {url, browser:$("#browser").value, count:$("#count").value, min:$("#minl").value, max:$("#maxl").value}, $("#findStatus"));
    S.title = r.title; showPicks(r.clips);
  } catch(e) {} finally { $("#findBtn").disabled = false; }
};
$("#manualBtn").onclick = () => {
  const s = parseT($("#ms").value), e = parseT($("#me").value);
  if (!(e > s)) return status($("#findStatus"), "Type a start and end time, like 1:23 and 1:45.", "err");
  status($("#findStatus"), ""); openEditor({start:s, end:e, title:""});
};
function showPicks(clips){
  $("#picksCard").classList.remove("hidden");
  const box = $("#picks"); box.innerHTML = "";
  if (!clips.length) box.textContent = "No moments found.";
  clips.forEach(c => {
    const d = document.createElement("div"); d.className = "pick";
    d.innerHTML = `<div class="score">${c.score}</div><div class="meta"><div class="t">${fmtT(c.start)}–${fmtT(c.end)} · ${Math.round(c.end-c.start)}s ${c.title ? "· " + escapeHtml(c.title) : ""}</div><div class="r">${escapeHtml(c.reason)}</div></div>`;
    const b = document.createElement("button"); b.className = "small primary"; b.textContent = "Edit & make";
    b.onclick = () => openEditor(c); d.appendChild(b); box.appendChild(d);
  });
}

// ---------------------------------------------------------------- step 3
async function openEditor(c){
  S.clip = c; $("#editCard").classList.remove("hidden"); $("#editor").classList.add("hidden"); $("#result").innerHTML = "";
  $("#editCard").scrollIntoView({behavior:"smooth"});
  try {
    const r = await runJob("/api/prepare", {url:$("#url").value.trim(), browser:$("#browser").value, start:c.start, end:c.end}, $("#prepStatus"));
    S.dims = [r.width, r.height];
    $("#vid").src = r.video;
    S.lines = chunk(r.words.map(w => ({...w, emph:false})), S.style.words_per_line || 3);
    $("#editor").classList.remove("hidden");
    if (!r.words.length) status($("#prepStatus"), "No captions were found for this part. Use “+ Add line here” to type your own, or turn Captions off.", "");
    renderLines(); renderCap();
  } catch(e) {}
}

function chunk(words, max){
  const out = []; let cur = [];
  words.forEach(w => {
    if (cur.length && (cur.length >= max || w.s - cur[cur.length-1].e > 0.6)) { out.push(cur); cur = []; }
    cur.push(w);
    if (/[.!?]$/.test(w.w)) { out.push(cur); cur = []; }
  });
  if (cur.length) out.push(cur);
  return out;
}
const lineText = l => l.map(w => w.emph ? "*" + w.w + "*" : w.w).join(" ");
const lineEnd = l => Math.max(...l.map(w => w.e));

function setLineText(i, text){
  const old = S.lines[i], s = old[0].s, e = lineEnd(old);
  const toks = text.trim().split(/\s+/).filter(Boolean);
  if (!toks.length) { S.lines.splice(i, 1); renderLines(); renderCap(); return; }
  const parsed = toks.map(t => { const m = t.match(/^\*(.+)\*$/); return {w: m ? m[1] : t, emph: !!m}; });
  let nl;
  if (parsed.length === old.length) nl = parsed.map((p, j) => ({...old[j], w:p.w, emph:p.emph}));
  else { const step = (e - s) / parsed.length; nl = parsed.map((p, j) => ({s: s + j*step, e: s + (j+1)*step, w:p.w, emph:p.emph})); }
  S.lines[i] = nl; renderCap();
}

function renderLines(){
  const box = $("#lines"); box.innerHTML = "";
  if (!S.lines.length) { box.innerHTML = '<div class="line"><span class="hint">No caption lines yet.</span></div>'; return; }
  S.lines.forEach((l, i) => {
    const d = document.createElement("div"); d.className = "line"; d.dataset.i = i;
    const tm = document.createElement("span"); tm.className = "tm"; tm.textContent = fmtT(l[0].s); tm.title = "Jump here";
    tm.onclick = () => { $("#vid").currentTime = l[0].s + 0.01; };
    const inp = document.createElement("input"); inp.type = "text"; inp.value = lineText(l);
    inp.oninput = () => setLineText(+d.dataset.i, inp.value);
    inp.onchange = renderLines;
    const del = document.createElement("button"); del.className = "small"; del.textContent = "×"; del.title = "Delete line";
    del.onclick = () => { S.lines.splice(i, 1); renderLines(); renderCap(); };
    d.append(tm, inp, del); box.appendChild(d);
  });
}
$("#addLine").onclick = () => {
  const v = $("#vid"), t = v.currentTime || 0, dur = (v.duration || t + 2);
  const e = Math.min(dur, t + 2);
  const nl = [{s:t, e:Math.max(e, t + 0.5), w:"TEXT", emph:false}];
  S.lines.push(nl); S.lines.sort((a, b) => a[0].s - b[0].s); renderLines(); renderCap();
};

// ---------------------------------------------------------------- style controls
function hex2rgba(h, a){ h = h.replace("#",""); return `rgba(${parseInt(h.slice(0,2),16)},${parseInt(h.slice(2,4),16)},${parseInt(h.slice(4,6),16)},${a})`; }

function loadStyle(st){
  S.style = {...st};
  STYLE_KEYS.forEach(k => { const el = document.getElementById(k === "words_per_line" ? "wpl" : k); if (el) el.value = st[k]; });
  CHECK_KEYS.forEach(k => { $("#" + k).checked = !!st[k]; });
  $("#hlword").checked = st.highlight_mode === "word";
  showOutputs();
}
function readStyle(){
  STYLE_KEYS.forEach(k => { const el = document.getElementById(k === "words_per_line" ? "wpl" : k);
    S.style[k] = (el.type === "range") ? +el.value : el.value; });
  CHECK_KEYS.forEach(k => { S.style[k] = $("#" + k).checked; });
  S.style.highlight_mode = $("#hlword").checked ? "word" : "none";
  showOutputs();
}
function showOutputs(){
  document.querySelectorAll(".ctl").forEach(c => { const i = c.querySelector("input[type=range]"), o = c.querySelector("output");
    if (i && o) o.textContent = i.id.includes("opacity") ? i.value + "%" : i.value; });
}
document.querySelectorAll("#capPanel input, #capPanel select").forEach(el => {
  if (el.closest("#lines")) return;
  el.addEventListener("input", () => {
    const oldW = S.style.words_per_line; readStyle();
    if (el.id === "wpl" && oldW !== S.style.words_per_line) { S.lines = chunk(S.lines.flat(), S.style.words_per_line); renderLines(); }
    renderCap();
  });
});
document.querySelectorAll("[data-preset]").forEach(b => b.onclick = () => {
  loadStyle(S.info.presets[b.dataset.preset][S.fmt]);
  S.lines = chunk(S.lines.flat(), S.style.words_per_line); renderLines(); renderCap();
});
$("#fmtSeg").onclick = e => {
  const v = e.target.dataset.v; if (!v || v === S.fmt) return;
  [...$("#fmtSeg").children].forEach(b => b.classList.toggle("on", b.dataset.v === v));
  const ratio = 1.9;
  if (v === "landscape") { S.style.size = +(S.style.size * ratio).toFixed(1); S.style.position = 8; }
  else { S.style.size = +(S.style.size / ratio).toFixed(1); S.style.position = 28; }
  S.fmt = v; loadStyle(S.style);
  $("#frame").className = "frame " + (v === "vertical" ? "v" : "h"); renderCap();
};
$("#capOn").onchange = () => { $("#capPanel").classList.toggle("hidden", !$("#capOn").checked); renderCap(); };

// ---------------------------------------------------------------- live preview
function renderCap(){
  const cap = $("#cap"), v = $("#vid"), st = S.style;
  if (!$("#capOn").checked || !S.lines.length) { cap.innerHTML = ""; return; }
  const t = v.currentTime || 0;
  const line = S.lines.find(l => t >= l[0].s && t < lineEnd(l));
  if (!line) { cap.innerHTML = ""; return; }
  let active = -1; line.forEach((w, i) => { if (w.s <= t) active = i; });
  const H = $("#frame").clientHeight, size = H * st.size / 100;
  const op = st.text_opacity / 100, ow = size * st.outline / 100;
  cap.style.bottom = st.position + "%";
  cap.style.fontFamily = `"${st.font}", Arial, sans-serif`;
  cap.style.fontSize = size + "px"; cap.style.fontWeight = st.bold ? "800" : "400";
  const box = st.box ? `background:${hex2rgba(st.box_color, st.box_opacity/100)};padding:${size*0.12}px ${size*0.2}px;` : "";
  const shadow = st.shadow ? `text-shadow:0 ${size*0.04}px ${size*0.06}px rgba(0,0,0,${0.5*op});` : "";
  const html = line.map((w, i) => {
    let txt = escapeHtml(st.uppercase ? w.w.toUpperCase() : w.w);
    const hl = (i === active && st.highlight_mode === "word") || w.emph;
    const col = hex2rgba(hl ? st.highlight : st.color, op);
    const scale = (i === active && st.highlight_mode === "word" && st.pop) ? "transform:scale(1.12);" : "";
    return `<span class="wd" style="color:${col};-webkit-text-stroke:${ow*2}px ${hex2rgba(st.outline_color, op)};paint-order:stroke fill;${shadow}${scale}">${txt}</span>`;
  }).join(" ");
  cap.innerHTML = `<span class="box" style="${box}">${html}</span>`;
  document.querySelectorAll(".line").forEach(d => d.classList.toggle("now", S.lines[+d.dataset.i] === line));
}
(function loop(){ if (!$("#editor").classList.contains("hidden")) renderCap(); requestAnimationFrame(loop); })();

// ---------------------------------------------------------------- make
$("#makeBtn").onclick = async () => {
  $("#makeBtn").disabled = true; $("#result").innerHTML = "";
  const words = [], lines = [];
  S.lines.forEach(l => { const idx = []; l.forEach(w => { idx.push(words.length); words.push({s:w.s, e:w.e, w:w.w, emph:w.emph}); }); lines.push(idx); });
  try {
    const r = await runJob("/api/make", {url:$("#url").value.trim(), browser:$("#browser").value, start:S.clip.start, end:S.clip.end,
      title:S.title || S.clip.title || "", format:S.fmt, captions:$("#capOn").checked, words, lines, style:S.style}, $("#makeStatus"));
    $("#result").innerHTML = `<video src="${r.file}" controls playsinline></video><div class="hint">Saved as <b>${escapeHtml(r.name)}</b> in ${escapeHtml(S.info.out_dir)}</div>`;
  } catch(e) {} finally { $("#makeBtn").disabled = false; }
};
$("#openBtn").onclick = () => api("/api/open", {});

// ---------------------------------------------------------------- start
(async () => {
  S.info = await api("/api/info");
  loadStyle(S.info.presets.bold.vertical);
  const w = [];
  if (!S.info.ytdlp) w.push("yt-dlp isn't installed. In Terminal run: python3 -m pip install -U \"yt-dlp[default]\"");
  if (!S.info.ffmpeg) w.push("ffmpeg isn't installed. Mac: brew install ffmpeg-full");
  else if (!S.info.captions) w.push("Your ffmpeg can't draw captions, so clips will be made without them. Mac fix: brew install ffmpeg-full (then restart Clip Maker).");
  $("#warn").innerHTML = w.map(x => `<div class="warn">${escapeHtml(x)}</div>`).join("");
  if (S.info.mac) $("#browser").value = "chrome";
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
