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

ROOT = os.path.dirname(HERE)                       # the Clip Maker folder
SETTINGS_FILE = os.path.join(ROOT, "clipmaker-settings.json")


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def default_out_dir():
    """Where clips go unless the user picked a folder.

    On another drive (Mac: /Volumes/..., Windows: not the system drive), clips
    are kept next to the app in a "Clips" folder, so everything stays on that
    drive. Otherwise they go to Movies (Mac) or Videos (Windows).
    """
    if os.environ.get("CLIPMAKER_OUT"):
        return os.path.expanduser(os.environ["CLIPMAKER_OUT"])
    system_drive = os.path.splitdrive(os.path.expanduser("~"))[0].lower()
    if ROOT.startswith("/Volumes/") or (os.name == "nt" and
                                        os.path.splitdrive(ROOT)[0].lower() != system_drive):
        return os.path.join(ROOT, "Clips")
    home = os.path.expanduser("~")
    base = next((os.path.join(home, d) for d in ("Movies", "Videos")
                 if os.path.isdir(os.path.join(home, d))), home)
    return os.path.join(base, "Clip Maker")


OUT_DIR = load_settings().get("out_dir") or default_out_dir()
if not os.path.isdir(os.path.dirname(OUT_DIR.rstrip("/\\")) or "."):
    OUT_DIR = default_out_dir()          # the saved folder's drive isn't connected
CACHE_DIR = os.path.join(tempfile.gettempdir(), "clipmaker_cache")
OVERLAY_DIR = os.path.join(ROOT, "Overlays")      # images people upload for overlays
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def save_overlay(name, data_url):
    """Store an uploaded overlay image; returns its file name in OVERLAY_DIR."""
    import base64
    ext = os.path.splitext(str(name or ""))[1].lower()
    if ext not in IMAGE_TYPES:
        raise RuntimeError("Overlays must be PNG, JPG or WebP images.")
    try:
        raw = base64.b64decode(str(data_url).split(",", 1)[-1], validate=False)
    except ValueError:
        raise RuntimeError("That image couldn't be read.")
    if not raw or len(raw) > 20 * 1024 * 1024:
        raise RuntimeError("The image must be under 20 MB.")
    os.makedirs(OVERLAY_DIR, exist_ok=True)
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.splitext(os.path.basename(name))[0])[:60] or "overlay"
    fname = base + ext
    with open(os.path.join(OVERLAY_DIR, fname), "wb") as fh:
        fh.write(raw)
    return fname
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)


def set_out_dir(path):
    """Change where clips are saved (remembered next to the app)."""
    global OUT_DIR
    path = os.path.abspath(os.path.expanduser(path.strip().strip("'\"")))
    if not path or not os.path.isdir(os.path.dirname(path)):
        raise RuntimeError("That folder's location doesn't exist. Is the drive connected?")
    os.makedirs(path, exist_ok=True)
    test = os.path.join(path, ".clipmaker-write-test")
    try:
        with open(test, "w") as fh:
            fh.write("ok")
        os.remove(test)
    except OSError:
        raise RuntimeError("Clip Maker can't save files in that folder.")
    settings = load_settings()
    settings["out_dir"] = path
    with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)
    OUT_DIR = path
    return path

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
        self.pct = 0.0

    def span(self, lo, hi):
        """Progress callback covering lo..hi of this job (0..1)."""
        def report(frac):
            self.pct = max(self.pct, min(hi, lo + (hi - lo) * max(0.0, min(1.0, frac))))
        return report

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

PAD = 10.0   # seconds downloaded before and after a moment, for trimming


def job_find(job, p):
    use_browser(p.get("browser"))
    url = p["url"].strip()
    local = clip.is_local_file(url)
    ffmpeg = clip.find_ffmpeg()
    with tempfile.TemporaryDirectory(prefix="clipfind_") as work:
        fetch = None
        if p.get("skip_text"):
            def fetch(s, e):
                return clip.fetch_section(url, s, e, 360, tempfile.mkdtemp(dir=work), ffmpeg)
        title, picks = finder.find_clips(
            url, is_local=local, ytdlp=None if local else clip.ytdlp_cmd(),
            ffmpeg=ffmpeg, workdir=work,
            count=int(p.get("count") or 5), min_len=float(p.get("min") or 15),
            max_len=float(p.get("max") or 60), use_ai=True, log=job.log, skip_text=fetch,
            focus=(p.get("focus") or "").strip(), progress=job.span(0, 1))
    return {"title": title, "clips": picks}


def section_key(url, start, end, quality):
    return hashlib.sha1(f"{url}|{start:.2f}|{end:.2f}|{quality}".encode()).hexdigest()[:16]


def ensure_section(job, url, start, end, quality=1080, progress=None):
    """Download [start, end] once; reuse it for preview and final render."""
    key = section_key(url, start, end, quality)
    folder = os.path.join(CACHE_DIR, key)
    path = os.path.join(folder, "section.mp4")
    if os.path.isfile(path):
        return key, path
    os.makedirs(folder, exist_ok=True)
    job.log("Downloading this part of the video...")
    raw = clip.fetch_section(url, start, end, quality, folder, clip.find_ffmpeg(),
                             on_progress=progress)
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


def speech_words(job, key, path, progress=None):
    """Transcribe a downloaded section on this computer (cached)."""
    cache = os.path.join(CACHE_DIR, key, "speech.json")
    if os.path.isfile(cache):
        with open(cache) as fh:
            return [tuple(w) for w in json.load(fh)]
    with tempfile.TemporaryDirectory(prefix="clipspeech_") as work:
        words = captions.transcribe(path, clip.find_ffmpeg(), work, log=job.log,
                                    progress=progress)
    with open(cache, "w") as fh:
        json.dump(words, fh)
    return words


def job_prepare(job, p):
    """Download a moment (with extra time around it) and get its caption words."""
    use_browser(p.get("browser"))
    url = p["url"].strip()
    start, end = float(p["start"]), float(p["end"])
    if end - start < 1:
        raise RuntimeError("The clip must be at least 1 second long.")
    sec_start, sec_end = max(0.0, start - PAD), end + PAD
    source = p.get("words_from", "auto")     # auto | youtube | speech | none
    may_speak = source != "none" and bool(captions.whisper_backend())
    key, path = ensure_section(job, url, sec_start, sec_end,
                               progress=job.span(0, 0.6 if may_speak else 0.9))
    ffmpeg = clip.find_ffmpeg()
    length = clip.local_duration(path, ffmpeg) or (sec_end - sec_start)

    words, used, note = [], "none", ""
    if source in ("auto", "youtube"):
        words = captions.words_in(video_words(job, url, p.get("browser")), sec_start, sec_end)
        used = "youtube" if words else "none"
    if (source == "speech" or (source == "auto" and not words)) and captions.whisper_backend():
        try:
            words, used = speech_words(job, key, path, job.span(0.62, 0.99)), "speech"
        except RuntimeError as err:
            if source == "speech":
                raise
            note = f"{err} For now, you can type captions with \u201c+ Add line\u201d."
    w, h = clip.video_size(path, ffmpeg)
    cut_in, cut_out, snapped = start - sec_start, min(length, end - sec_start), False
    if words and p.get("snap", True):
        # Start and end on whole sentences, not mid-word.
        a, b, snapped = captions.sentence_snap(cut_in, cut_out, words, min_len=1.0, reach=6)
        cut_in, cut_out = max(0.0, a), min(length, b)
    return {"video": f"/media/{key}/section.mp4", "width": w, "height": h,
            "sec_start": sec_start, "sec_end": sec_end, "length": length,
            "cut_in": cut_in, "cut_out": cut_out, "snapped": snapped, "note": note,
            "words_from": used,
            "words": [{"s": round(a, 3), "e": round(b, 3), "w": t} for a, b, t in words]}


def job_make(job, p):
    use_browser(p.get("browser"))
    url = p["url"].strip()
    sec_start, sec_end = float(p["sec_start"]), float(p["sec_end"])
    cut_in, cut_out = float(p["cut_in"]), float(p["cut_out"])
    if cut_out - cut_in < 1:
        raise RuntimeError("The clip must be at least 1 second long.")
    aspect = p.get("aspect") or "9:16"
    ffmpeg = clip.find_ffmpeg()
    _, path = ensure_section(job, url, sec_start, sec_end, progress=job.span(0, 0.1))

    words, lines = None, None
    if p.get("captions", True) and p.get("words"):
        if not clip.has_captions_support(ffmpeg):
            job.log("Your ffmpeg can't draw captions (Mac fix: brew install ffmpeg-full). "
                    "Making the clip without them.")
        else:
            # Shift words to the trimmed clip's time; keep only those inside it.
            keep, words = {}, []
            for i, w in enumerate(p["words"]):
                s, e = float(w["s"]) - cut_in, float(w["e"]) - cut_in
                if e > 0 and s < cut_out - cut_in:
                    keep[i] = len(words)
                    words.append({"s": max(0.0, s), "e": min(cut_out - cut_in, e),
                                  "w": w["w"], "emph": w.get("emph")})
            lines = [[keep[i] for i in line if i in keep] for line in p.get("lines") or []]
            lines = [l for l in lines if l] or None
            words = words or None

    title = (p.get("title") or "").strip() or clip.video_title(url)
    abs_in, abs_out = sec_start + cut_in, sec_start + cut_out
    tag = aspect.replace(":", "x")
    name = f"{clip.safe_name(title)}_{clip.label_time(abs_in)}-{clip.label_time(abs_out)}_{tag}.mp4"
    dest = os.path.join(OUT_DIR, name)
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(OUT_DIR, name.replace(".mp4", f"_{n}.mp4"))
        n += 1
    job.log("Making the clip (this can take a minute)...")
    with tempfile.TemporaryDirectory(prefix="clipmake_") as work:
        raw = os.path.join(work, "raw.mp4")
        clip.run_ffmpeg([ffmpeg, "-y", "-i", path, "-ss", f"{cut_in:.3f}", "-to", f"{cut_out:.3f}",
                         "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                         "-c:a", "aac", "-b:a", "192k", raw],
                        job.span(0.1, 0.35), cut_out - cut_in)
        crop = dict(p.get("crop") or {}, aspect=aspect)
        credit = (p.get("credit") or "").strip()[:80] or None
        if credit and not clip.has_captions_support(ffmpeg):
            job.log("Your ffmpeg can't draw text, so the credit wasn't added (Mac fix: brew install ffmpeg-full).")
        headline = (p.get("headline") or "").strip()[:200] or None
        try:
            volume = int(p.get("volume", 100))
        except (TypeError, ValueError):
            volume = 100
        overlay = None
        ov = p.get("overlay") or {}
        if ov.get("name"):
            f = os.path.join(OVERLAY_DIR, os.path.basename(str(ov["name"])))
            if os.path.isfile(f):
                overlay = dict(ov, file=f)
            else:
                job.log("The overlay image is missing, so it wasn't added. Upload it again.")
        clip.convert(raw, dest, "mp4", ffmpeg, 480, 12, words, p.get("style") or "bold",
                     lines, crop, on_progress=job.span(0.35, 1.0), credit=credit,
                     headline=headline, volume=volume, overlay=overlay)
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
    import textcheck
    local_ok, local_note = finder.local_ai_status()
    return {
        "smart": ("claude" if os.environ.get("ANTHROPIC_API_KEY") else
                  "local" if local_ok else "free"),
        "local_note": local_note or finder.LOCAL_HINT,
        "out_dir": OUT_DIR, "ffmpeg": ffmpeg_ok, "captions": caps, "ytdlp": ytdlp_ok,
        "whisper": bool(captions.whisper_backend()), "whisper_hint": captions.INSTALL_HINT,
        "tesseract": bool(textcheck.tesseract()), "tesseract_hint": textcheck.INSTALL_HINT,
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
                                   "pct": round(job.pct, 4),
                                   "result": job.result, "error": job.error})
        if path.startswith("/overlay/"):
            full = self.safe_path(OVERLAY_DIR, path[len("/overlay/"):])
            ctype = IMAGE_TYPES.get(os.path.splitext(full or "")[1].lower())
            if not full or not ctype:
                return self.send_error(404)
            return self.send_file(full, ctype)
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
        if path == "/api/overlay":
            try:
                name = save_overlay(p.get("name"), p.get("data"))
            except RuntimeError as err:
                return self.send_json({"error": str(err)}, 400)
            return self.send_json({"name": name, "url": "/overlay/" + name})
        if path == "/api/open":
            open_folder()
            return self.send_json({"ok": True})
        if path == "/api/settings":
            try:
                return self.send_json({"out_dir": set_out_dir(str(p.get("out_dir") or ""))})
            except RuntimeError as err:
                return self.send_json({"error": str(err)}, 400)
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
:root{--bg:#f6f6f4;--card:#fff;--ink:#16161a;--muted:#6b6b76;--line:#e3e3e0;--accent:#ff3d5a;--accent-ink:#fff;--soft:#f0f0ed;--err:#d12f2f;--sel:rgba(255,61,90,.25)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121215;--card:#1b1b20;--ink:#f1f1f3;--muted:#9a9aa6;--line:#2c2c33;--soft:#24242a}}
:root[data-theme="dark"]{--bg:#121215;--card:#1b1b20;--ink:#f1f1f3;--muted:#9a9aa6;--line:#2c2c33;--soft:#24242a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1120px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}
h2{font-size:17px;margin:0 0 12px}
h3{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:18px 0 8px}
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
label.chk{display:inline-flex;gap:6px;align-items:center;color:var(--ink);font-size:14px}
.status{display:none;margin-top:12px;padding:10px 12px;border-radius:9px;background:var(--soft);font-size:13px;white-space:pre-wrap}
.status.err{color:var(--err)}
.pbar{height:8px;background:var(--line);border-radius:4px;overflow:hidden;margin:8px 0 4px}
.pbar i{display:block;height:100%;width:0;background:var(--accent);border-radius:4px;transition:width .5s ease}
.pmeta{display:flex;justify-content:space-between;gap:10px;color:var(--muted);font-size:12px}
textarea{font:inherit;color:var(--ink);background:var(--soft);border:1px solid var(--line);border-radius:9px;padding:9px 11px;width:100%;resize:vertical;min-height:44px}
.spin{display:inline-block;width:12px;height:12px;border:2px solid var(--muted);border-top-color:transparent;border-radius:50%;animation:s .8s linear infinite;margin-right:8px;vertical-align:-1px}
@keyframes s{to{transform:rotate(360deg)}}
.pick{display:flex;gap:12px;align-items:center;padding:12px 0;border-top:1px solid var(--line)}
.pick:first-of-type{border-top:0}
.score{flex:none;width:48px;height:48px;border-radius:12px;display:grid;place-items:center;font-weight:700;background:var(--soft)}
.pick .meta{flex:1;min-width:0}
.pick .t{font-weight:600}
.pick .r{color:var(--muted);font-size:13px}
.editor{display:grid;grid-template-columns:minmax(280px,400px) 1fr;gap:24px;align-items:start}
@media (max-width:800px){.editor{grid-template-columns:1fr}}
.stage{display:flex;justify-content:center}
.frame{position:relative;background:#000;border-radius:12px;overflow:hidden;width:100%;touch-action:none}
.frame video{position:absolute;max-width:none;object-fit:fill}
.drag{position:absolute;inset:0;cursor:grab}
.splitcv{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;display:none}
.frame.split .splitcv{display:block}
.ovprev{position:absolute;pointer-events:none;display:none;transform:translate(-50%,-50%);z-index:2}
.ovprev.full{left:0!important;top:0!important;width:100%!important;height:100%!important;transform:none}
.ovprev.movable{pointer-events:auto;cursor:move;touch-action:none}
.ovprev.movable:hover{outline:2px dashed rgba(255,255,255,.7)}
.frame.split video{opacity:0}
#faceCv{display:block;width:100%;border-radius:8px;background:#000;cursor:move;touch-action:none;margin:6px 0}
.drag:active{cursor:grabbing}
.cap{position:absolute;left:6%;right:6%;text-align:center;pointer-events:none;line-height:1.15;transform-origin:50% 100%}
.cap.movable{pointer-events:auto;cursor:move;z-index:3;touch-action:none}
.cap.movable:hover,.cap.moving{outline:2px dashed rgba(255,255,255,.7);outline-offset:4px;border-radius:4px}
.cap.ghost{opacity:.55}
.cap .box{box-decoration-break:clone;-webkit-box-decoration-break:clone}
.headline{position:absolute;left:7%;right:7%;text-align:center;pointer-events:none;color:#fff;font-weight:800;font-family:Arial,sans-serif;-webkit-text-stroke:3px #000;paint-order:stroke fill;white-space:pre-line;line-height:1.15}
.credit{position:absolute;left:4%;right:4%;text-align:center;pointer-events:none;color:#fff;font-weight:800;font-family:Arial,sans-serif;-webkit-text-stroke:2px #000;paint-order:stroke fill}
.cap span.wd{display:inline-block;transition:transform .08s;margin:0 .06em}
.playbar{display:flex;gap:8px;align-items:center;margin-top:10px}
.playbar .tc{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;width:86px;text-align:right}
.track{position:relative;flex:1;height:30px}
.track .sel{position:absolute;top:11px;height:8px;background:var(--sel);border-radius:4px}
.track input{position:absolute;inset:0;width:100%;margin:0}
.trim{display:grid;grid-template-columns:44px auto 1fr;gap:6px 8px;align-items:center;margin-top:8px;font-size:13px}
.trim b{font-variant-numeric:tabular-nums}
.lines{max-height:280px;overflow:auto;border:1px solid var(--line);border-radius:10px}
.line{display:flex;gap:8px;align-items:center;padding:6px 8px;border-top:1px solid var(--line)}
.line:first-child{border-top:0}
.line.now{background:var(--soft)}
.line.out{opacity:.45}
.line .tm{flex:none;width:44px;font-size:12px;color:var(--muted);cursor:pointer}
.line input{flex:1}
.ctl{display:grid;grid-template-columns:140px 1fr 48px;gap:8px;align-items:center;margin:6px 0}
.ctl output{font-size:12px;color:var(--muted);text-align:right}
.ctl input[type=range]{width:100%}
.ctl input[type=color]{width:44px;height:30px;border:0;background:none;padding:0}
.seg{display:inline-flex;flex-wrap:wrap;background:var(--soft);border-radius:9px;padding:3px;gap:2px}
.seg button{background:none;padding:7px 11px;font-size:13px}
.seg button small{display:block;font-weight:400;color:var(--muted);font-size:11px}
.seg button.on{background:var(--card);box-shadow:0 1px 2px rgba(0,0,0,.15)}
.hint{color:var(--muted);font-size:12px;margin:6px 0 0}
.result video{width:100%;max-width:360px;border-radius:12px;display:block;margin:10px 0}
.warn{background:#fff4d6;color:#6b4b00;border-radius:9px;padding:10px 12px;font-size:13px;margin-bottom:12px;white-space:pre-wrap}
@media (prefers-color-scheme:dark){.warn{background:#3a2f12;color:#f3d98b}}
.hidden{display:none!important}
</style>
</head>
<body>
<main>
  <h1>Clip Maker</h1>
  <p class="sub">Paste a YouTube or Twitch link, find the best moments, frame and caption them, and make your clip.</p>
  <div id="warn"></div>

  <section class="card">
    <h2>1. Video</h2>
    <div class="row">
      <input id="url" class="url" type="text" placeholder="https://www.youtube.com/watch?v=...">
      <select id="browser" title="Use this browser's sign-in (needed for age-restricted videos)">
        <option value="">No sign-in</option><option value="chrome">Chrome sign-in</option>
        <option value="safari">Safari sign-in</option><option value="firefox">Firefox sign-in</option>
        <option value="edge">Edge sign-in</option><option value="brave">Brave sign-in</option>
      </select>
    </div>
    <div class="row" style="margin-top:10px">
      <label>Clips <input id="count" type="number" min="1" max="15" value="5"></label>
      <label>Length <input id="minl" type="number" min="3" value="15"> to <input id="maxl" type="number" min="5" value="60"> sec</label>
    </div>
    <div style="margin-top:12px">
      <label for="focus">Focus on (optional)</label>
      <textarea id="focus" rows="1" placeholder="e.g. funny reactions, car chases, when they talk about the heist"></textarea>
      <p class="hint" id="smartLine"></p>
    </div>
    <div class="row" style="margin-top:10px">
      <label class="chk"><input id="capDefault" type="checkbox" checked> Add captions</label>
      <label class="chk" id="skipLbl"><input id="skipText" type="checkbox" checked> Skip moments with text already on screen</label>
    </div>
    <p class="hint">Turn off captions if the video already has subtitles burned in.</p>
    <div class="row" style="margin-top:10px">
      <button id="findBtn" class="primary">Find best moments</button>
      <label>or pick the time yourself:</label>
      <input id="ms" type="text" placeholder="1:23" style="width:76px"> to
      <input id="me" type="text" placeholder="1:45" style="width:76px">
      <button id="manualBtn">Edit this part</button>
    </div>
    <div id="findStatus" class="status"></div>
    <details style="margin-top:14px"><summary class="hint" style="cursor:pointer">Save clips to: <b id="outDirLbl"></b></summary>
      <div class="row" style="margin-top:8px">
        <input id="outDir" type="text" class="url" placeholder="/Volumes/MyDrive/Clips">
        <button class="small" id="outDirBtn">Save</button>
      </div>
      <p class="hint">Tip: drag a folder from Finder into this box to fill in its location. The choice is remembered.</p>
      <div id="outStatus" class="status"></div>
    </details>
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
        <div class="seg" id="aspSeg" style="margin-bottom:12px">
          <button data-a="9:16" class="on">9:16<small>Shorts · TikTok · Reels</small></button>
          <button data-a="4:5">4:5<small>Instagram feed</small></button>
          <button data-a="1:1">1:1<small>Square</small></button>
          <button data-a="16:9">16:9<small>YouTube</small></button>
        </div>
        <div class="stage"><div id="frame" class="frame">
          <video id="vid" playsinline preload="auto"></video>
          <canvas id="splitCv" class="splitcv"></canvas>
          <img id="ovPrev" class="ovprev" alt="">
          <div id="cap" class="cap"></div>
          <div id="creditPrev" class="credit"></div>
          <div id="headPrev" class="headline"></div>
          <div id="drag" class="drag" title="Drag to move the picture. Click to play or pause."></div>
        </div></div>
        <div class="row" id="splitRow" style="margin:8px 0 2px"><label class="chk"><input id="splitOn" type="checkbox"> Facecam on top, game below</label></div>
        <div id="facePanel" class="hidden">
          <p class="hint" style="margin:2px 0">Drag the box onto the streamer's camera. Drag its corner to resize. The game part below still moves with the drag and Zoom.</p>
          <canvas id="faceCv"></canvas>
          <div class="ctl"><label>Facecam height</label><input id="splitPct" type="range" min="20" max="60" step="1" value="40"><output></output></div>
        </div>
        <div class="ctl"><label>Zoom</label><input id="zoom" type="range" min="1" max="3" step="0.05" value="1"><output></output></div>
        <div class="row"><button class="small" id="centerBtn">Center</button><span class="hint" style="margin:0">Drag the video to choose what's in frame.</span></div>

        <div class="playbar">
          <button class="small" id="playBtn">▶</button>
          <div class="track"><div id="selBar" class="sel"></div><input id="seek" type="range" min="0" step="0.05" value="0"></div>
          <span class="tc" id="tc">0:00.0</span>
        </div>
        <div class="trim">
          <span>Start</span><span><button class="small" data-t="in" data-d="-1">−1s</button> <button class="small" data-t="in" data-d="-0.2">−.2</button> <b id="inT">0:00.0</b> <button class="small" data-t="in" data-d="0.2">+.2</button> <button class="small" data-t="in" data-d="1">+1s</button></span><button class="small" data-set="in">Set to playhead</button>
          <span>End</span><span><button class="small" data-t="out" data-d="-1">−1s</button> <button class="small" data-t="out" data-d="-0.2">−.2</button> <b id="outT">0:00.0</b> <button class="small" data-t="out" data-d="0.2">+.2</button> <button class="small" data-t="out" data-d="1">+1s</button></span><button class="small" data-set="out">Set to playhead</button>
        </div>
        <div class="row" style="margin-top:8px"><button class="small" id="snapBtn">Snap to sentences</button><span class="hint" id="snapNote" style="margin:0"></span></div>
        <p class="hint">Length: <b id="lenT">0s</b>. You can move the start and end up to 10 seconds past the picked moment.</p>
      </div>

      <div>
        <div class="ctl" style="grid-template-columns:140px 1fr"><label for="credit">Credit on screen</label><input id="credit" type="text" placeholder="e.g. twitch.tv/Lysium" maxlength="80"></div>
        <p class="hint" style="margin:-2px 0 12px">Shown near the top for the whole clip. Many campaigns require the streamer's handle.</p>
        <div class="ctl" style="grid-template-columns:140px 1fr"><label for="headline">Headline text</label><textarea id="headline" rows="2" maxlength="200" placeholder="e.g. When GTA 6 finally drops tomorrow"></textarea></div>
        <p class="hint" style="margin:-2px 0 12px">Big text across the top for the whole clip, for edits with music and no talking. Press Enter for a new line.</p>
        <div class="ctl"><label for="volume">Original audio</label><input id="volume" type="range" min="0" max="100" step="5" value="100"><output></output></div>
        <p class="hint" style="margin:-2px 0 12px">0% removes the clip's own sound, ready for adding a song in TikTok or Reels. Around 20% keeps game sounds quietly under music.</p>
        <h3 style="margin-top:4px">Overlay</h3>
        <div class="row" style="margin-bottom:6px"><input id="ovFile" type="file" accept="image/png,image/jpeg,image/webp" style="flex:1;min-width:0"><button class="small hidden" id="ovClear">Remove</button></div>
        <p class="hint" style="margin:-2px 0 8px">A streamer's frame, logo or watermark (a PNG with a see-through background works best). Remembered for your next clips.</p>
        <div id="ovCtl" class="hidden">
          <label class="chk"><input id="ovFull" type="checkbox"> Cover the whole frame (for full-size frames)</label>
          <div class="ctl"><label>Overlay size</label><input id="ovsize" type="range" min="5" max="100" step="1" value="30"><output></output></div>
          <div class="ctl"><label>Overlay opacity</label><input id="ov_opacity" type="range" min="10" max="100" step="5" value="100"><output></output></div>
          <p class="hint" style="margin:-2px 0 12px">Drag the overlay on the video to move it.</p>
        </div>
        <label class="chk"><input id="capOn" type="checkbox" checked> Captions</label>
        <span class="hint" style="margin-left:6px">Off if the video already has subtitles.</span>

        <div id="capPanel">
        <h3>Words</h3>
        <div class="row" style="margin-bottom:8px">
          <span id="srcLbl" class="hint" style="margin:0;flex:1"></span>
          <button class="small" id="speechBtn">Transcribe speech</button>
          <button class="small" id="ytBtn">Use YouTube captions</button>
        </div>
        <div id="lines" class="lines"></div>
        <div class="row" style="margin-top:8px">
          <button class="small" id="addLine">+ Add line at playhead</button>
          <label style="flex:1">Wrap a word in *stars* to always highlight it. Click a time to jump there.</label>
        </div>

        <h3>Style</h3>
        <div class="row"><button class="small" data-preset="bold">Bold (yellow pop)</button><button class="small" data-preset="clean">Clean</button></div>
        <div class="ctl"><label>Words per line</label><input id="wpl" type="range" min="1" max="8" step="1"><output></output></div>
        <div class="ctl"><label>Font</label><select id="font">
          <option>Arial</option><option>Arial Black</option><option>Impact</option><option>Helvetica Neue</option>
          <option>Avenir Next</option><option>Futura</option><option>Verdana</option><option>Georgia</option><option>Comic Sans MS</option>
        </select><span></span></div>
        <div class="ctl"><label>Size</label><input id="size" type="range" min="1.5" max="14" step="0.1"><output></output></div>
        <div class="ctl"><label>Position (from bottom)</label><input id="position" type="range" min="2" max="90" step="1"><output></output></div>
        <div class="ctl"><label>Left / right</label><input id="x" type="range" min="10" max="90" step="1"><output></output></div>
        <p class="hint" style="margin:-2px 0 8px">Or drag the captions on the video. Keep them above the bottom 20%, where TikTok puts the caption and buttons.</p>
        <div class="ctl"><label>Animation</label><select id="animation">
          <option value="none">None</option><option value="pop">Pop (spoken word grows)</option>
          <option value="bounce">Bounce in</option><option value="fade">Fade in</option>
          <option value="slide">Slide up</option><option value="typewriter">Typewriter (word by word)</option>
        </select><span></span></div>
        <div class="ctl"><label>Text color</label><input id="color" type="color"><span></span></div>
        <div class="ctl"><label>Highlight color</label><input id="highlight" type="color"><span></span></div>
        <div class="ctl"><label>Outline</label><input id="outline" type="range" min="0" max="25" step="1"><output></output></div>
        <div class="ctl"><label>Outline color</label><input id="outline_color" type="color"><span></span></div>
        <div class="row" style="margin:8px 0">
          <label class="chk"><input id="bold" type="checkbox"> Bold</label>
          <label class="chk"><input id="uppercase" type="checkbox"> UPPERCASE</label>
          <label class="chk"><input id="hlword" type="checkbox"> Highlight spoken word</label>
          <label class="chk"><input id="shadow" type="checkbox"> Shadow</label>
        </div>

        <h3>Opacity</h3>
        <div class="ctl"><label>Text opacity</label><input id="text_opacity" type="range" min="0" max="100" step="5"><output></output></div>
        <div class="row" style="margin:8px 0"><label class="chk"><input id="box" type="checkbox"> Background box</label></div>
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
const vid = () => $("#vid");
const S = {info:null, title:"", clip:null, prep:null, aspect:"9:16", style:{}, lines:[], dims:[1280,720],
           crop:{x:0.5, y:0.5, zoom:1}, cut:[0,0], splitOn:false, split:0.4,
           face:{x:0.72, y:0.02, w:0.26, h:0.32}};
const STYLE_KEYS = ["font","size","position","x","animation","color","highlight","outline","outline_color","text_opacity","box_color","box_opacity","words_per_line"];
const CHECK_KEYS = ["bold","uppercase","shadow","box"];
const RATIO = {"9:16":9/16, "4:5":4/5, "1:1":1, "16:9":16/9};
const store = {get(k, d){ try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch(e){ return d; } },
               set(k, v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch(e){} }};

const fmtT = t => { t = Math.max(0, t || 0); const m = Math.floor(t/60), s = Math.floor(t%60); return m + ":" + String(s).padStart(2,"0"); };
const fmtT1 = t => { t = Math.max(0, t || 0); const m = Math.floor(t/60), s = (t%60).toFixed(1); return m + ":" + s.padStart(4,"0"); };
function parseT(x){ x = String(x).trim(); if(!x) return NaN; if(/^\d+(\.\d+)?$/.test(x)) return +x;
  const p = x.split(":").map(Number); if(p.some(isNaN)) return NaN; return p.reduce((a,b)=>a*60+b,0); }
async function api(path, body){ const r = await fetch(path, body ? {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)} : {}); return r.json(); }
function escapeHtml(s){ return String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function status(el, msg, kind, prog){
  el.style.display = msg ? "block" : "none"; el.className = "status" + (kind==="err" ? " err" : "");
  if (kind === "busy" && prog) {
    const pct = Math.round(prog.pct * 100);
    let left = "";
    if (prog.pct >= 0.05 && prog.pct < 0.995) {
      const secs = prog.elapsed * (1 - prog.pct) / prog.pct;
      left = secs < 10 ? "a few seconds left" : secs < 90 ? `about ${Math.round(secs / 5) * 5}s left` : `about ${Math.round(secs / 60)} min left`;
    }
    el.innerHTML = `<div>${escapeHtml(msg || "Working...")}</div><div class="pbar"><i style="width:${Math.max(2, pct)}%"></i></div>` +
      `<div class="pmeta"><span>${pct}%</span><span>${left || fmtT(prog.elapsed) + " so far"}</span></div>`;
    return;
  }
  el.innerHTML = (kind==="busy" ? '<span class="spin"></span>' : "") + escapeHtml(msg || ""); }

async function runJob(path, body, el){
  await READY;
  let job;
  try { ({job} = await api(path, body)); }
  catch (e) { status(el, "Couldn't reach Clip Maker. Is its window still open?", "err"); throw e; }
  const t0 = Date.now();
  return new Promise((resolve, reject) => {
    const tick = async () => {
      const j = await api("/api/job/" + job);
      if (j.status === "running"){ status(el, (j.log.slice(-1)[0] || "Working...").trim(), "busy", {pct:j.pct || 0, elapsed:(Date.now() - t0) / 1000}); setTimeout(tick, 600); }
      else if (j.status === "done"){ status(el, ""); resolve(j.result); }
      else { status(el, j.error, "err"); reject(new Error(j.error)); }
    };
    tick();
  });
}

// ---------------------------------------------------------------- steps 1-2
["capDefault","skipText"].forEach(id => { const el = $("#"+id); el.checked = store.get(id, true); el.onchange = () => store.set(id, el.checked); });
$("#findBtn").onclick = async () => {
  const url = $("#url").value.trim(); if(!url) return $("#url").focus();
  $("#findBtn").disabled = true;
  try {
    await READY;
    const r = await runJob("/api/find", {url, browser:$("#browser").value, count:$("#count").value, min:$("#minl").value,
      max:$("#maxl").value, skip_text:$("#skipText").checked && S.info.tesseract,
      focus:$("#focus").value.trim()}, $("#findStatus"));
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

// ---------------------------------------------------------------- step 3: load
async function openEditor(c, wordsFrom){
  S.clip = c; $("#editCard").classList.remove("hidden"); $("#result").innerHTML = "";
  if (!wordsFrom) { $("#editor").classList.add("hidden"); $("#editCard").scrollIntoView({behavior:"smooth"}); }
  const capOn = $("#capDefault").checked;
  try {
    const r = await runJob("/api/prepare", {url:$("#url").value.trim(), browser:$("#browser").value, start:c.start, end:c.end,
      words_from: wordsFrom || (capOn ? "auto" : "none")}, $("#prepStatus"));
    const first = !wordsFrom;
    S.prep = r; S.dims = [r.width, r.height];
    $("#snapNote").textContent = r.snapped ? "Adjusted so it starts and ends on full sentences." : "";
    if (first) {
      S.cut = [r.cut_in, r.cut_out]; S.crop = {x:0.5, y:0.5, zoom:1}; $("#zoom").value = 1;
      $("#capOn").checked = capOn; $("#capPanel").classList.toggle("hidden", !capOn);
      vid().src = r.video; vid().currentTime = r.cut_in;
      $("#seek").max = r.length;
    }
    S.lines = chunk(r.words.map(w => ({...w, emph:false})), S.style.words_per_line || 3);
    $("#editor").classList.remove("hidden");
    $("#srcLbl").textContent = {youtube:"From YouTube's captions.", speech:"From speech-to-text on this computer.", none:"No captions yet."}[r.words_from];
    $("#ytBtn").classList.toggle("hidden", r.words_from === "youtube" || /^\//.test($("#url").value.trim()));
    $("#speechBtn").classList.toggle("hidden", r.words_from === "speech");
    if (r.note) status($("#prepStatus"), r.note, "");
    else if (capOn && !r.words.length && r.words_from === "none")
      status($("#prepStatus"), S.info.whisper ? "No speech found here. Use “+ Add line” to type your own." :
        "No captions found for this part. Type your own with “+ Add line”, or install speech-to-text:\n" + S.info.whisper_hint, "");
    renderLines(); layout(); updateTrim();
  } catch(e) {}
}
// Start/end on whole sentences: a sentence ends at . ! ? or a pause of 0.7s+.
function sentenceSnap(a, b){
  const ws = S.lines.flat().slice().sort((x, y) => x.s - y.s);
  if (!ws.length) return null;
  const ends = [], starts = [ws[0].s];
  ws.forEach((w, i) => { const n = ws[i + 1];
    if (!n || /[.!?…]['")\]]*$/.test(w.w) || n.s - w.e >= 0.7) { ends.push(w.e); if (n) starts.push(n.s); } });
  const near = (list, t, lo, hi) => list.filter(x => x >= t - lo && x <= t + hi).sort((x, y) => Math.abs(x - t) - Math.abs(y - t))[0];
  let s = near(starts, a, 6, 1.5), e = near(ends, b, 6, 6);
  if (s === undefined) { const w = ws.find(w => w.s < a && a < w.e); s = w ? w.s : a; }
  if (e === undefined) { const w = ws.find(w => w.s < b && b < w.e); e = w ? w.e : b; }
  return [Math.max(0, s - 0.15), Math.min(S.prep.length, e + 0.35)];
}
$("#snapBtn").onclick = () => {
  const r = sentenceSnap(S.cut[0], S.cut[1]);
  if (!r) { $("#snapNote").textContent = "No caption words to snap to."; return; }
  if (r[1] - r[0] < 1) { $("#snapNote").textContent = "Couldn't find whole sentences here."; return; }
  S.cut = r; updateTrim(); $("#snapNote").textContent = "Starts and ends on full sentences."; vid().currentTime = S.cut[0];
};
$("#speechBtn").onclick = () => {
  if (!S.info.whisper) return status($("#prepStatus"), S.info.whisper_hint, "err");
  openEditor(S.clip, "speech");
};
$("#ytBtn").onclick = () => openEditor(S.clip, "youtube");

// ---------------------------------------------------------------- framing (aspect, drag, zoom)
function frameSize(){
  const col = $("#frame").parentElement.clientWidth, r = RATIO[S.aspect];
  const maxH = Math.min(window.innerHeight * 0.62, 640);
  let w = Math.min(col, r < 1 ? 360 : col), h = w / r;
  if (h > maxH) { h = maxH; w = h * r; }
  return [w, h];
}
const splitting = () => S.splitOn && S.aspect !== "16:9";
const gameRatio = () => splitting() ? RATIO[S.aspect] / (1 - S.split) : RATIO[S.aspect];
function cropBox(){
  const [sw, sh] = S.dims, r = gameRatio();
  const cw = Math.min(sw, sh * r) / S.crop.zoom; return [cw, cw / r];
}
function layout(){
  const [w, h] = frameSize(), F = $("#frame");
  F.style.width = w + "px"; F.style.height = h + "px";
  const [sw, sh] = S.dims, [cw, ch] = cropBox(), k = w / cw, v = vid();
  v.style.width = sw * k + "px"; v.style.height = sh * k + "px";
  v.style.left = -(sw - cw) * S.crop.x * k + "px"; v.style.top = -(sh - ch) * S.crop.y * k + "px";
  F.classList.toggle("split", splitting());
  $("#splitRow").classList.toggle("hidden", S.aspect === "16:9");
  $("#facePanel").classList.toggle("hidden", !splitting());
  drawSplit(); drawFacePicker(); renderCap();
}
// Same rule as the final render (clip.py face_rect): grow the box to the panel's shape.
function faceRect(panelRatio){
  const [sw, sh] = S.dims, f = S.face, cl = (v, a, b) => Math.max(a, Math.min(b, v));
  let fw = cl(f.w, 0.02, 1) * sw, fh = cl(f.h, 0.02, 1) * sh;
  const cx = cl(f.x, 0, 1) * sw + fw / 2, cy = cl(f.y, 0, 1) * sh + fh / 2;
  if (fw / fh > panelRatio) fh = fw / panelRatio; else fw = fh * panelRatio;
  if (fw > sw) { fw = sw; fh = sw / panelRatio; }
  if (fh > sh) { fh = sh; fw = sh * panelRatio; }
  return [cl(cx - fw / 2, 0, sw - fw), cl(cy - fh / 2, 0, sh - fh), fw, fh];
}
function drawSplit(){
  if (!splitting() || !S.prep) return;
  const cv = $("#splitCv"), v = vid(), F = $("#frame"), dpr = window.devicePixelRatio || 1;
  const W = F.clientWidth, H = F.clientHeight;
  if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
  if (!v.videoWidth) return;
  const g = cv.getContext("2d"), [sw, sh] = S.dims, kx = v.videoWidth / sw, ky = v.videoHeight / sh;
  const topH = Math.round(cv.height * S.split);
  const [fx, fy, fw, fh] = faceRect(cv.width / topH);
  g.drawImage(v, fx * kx, fy * ky, fw * kx, fh * ky, 0, 0, cv.width, topH);
  const [cw, ch] = cropBox(), gx = (sw - cw) * S.crop.x, gy = (sh - ch) * S.crop.y;
  g.drawImage(v, gx * kx, gy * ky, cw * kx, ch * ky, 0, topH, cv.width, cv.height - topH);
}
// ---------------------------------------------------------------- overlay image
S.ov = null;   // {name, url, full, x, y, w, opacity}
function renderOverlay(){
  const img = $("#ovPrev"), ov = S.ov;
  $("#ovCtl").classList.toggle("hidden", !ov); $("#ovClear").classList.toggle("hidden", !ov);
  if (!ov) { img.style.display = "none"; return; }
  if (img.getAttribute("src") !== ov.url) img.src = ov.url;
  img.style.display = "block"; img.style.opacity = ov.opacity / 100;
  img.classList.toggle("full", !!ov.full); img.classList.toggle("movable", !ov.full);
  img.style.left = ov.x + "%"; img.style.top = ov.y + "%"; img.style.width = ov.w + "%"; img.style.height = "auto";
  $("#ovFull").checked = !!ov.full; $("#ovsize").value = ov.w; $("#ov_opacity").value = ov.opacity; showOutputs();
}
function saveOv(){ store.set("overlay", S.ov); renderOverlay(); }
$("#ovFile").onchange = () => {
  const f = $("#ovFile").files[0]; if (!f) return;
  const rd = new FileReader();
  rd.onload = async () => {
    const r = await api("/api/overlay", {name:f.name, data:rd.result});
    if (r.error) { alert(r.error); return; }
    const im = new Image();
    im.onload = () => {   // a picture the shape of the clip is a full frame; anything else a logo
      const full = Math.abs(im.width / im.height - RATIO[S.aspect]) < 0.03;
      S.ov = {name:r.name, url:r.url + "?t=" + Date.now(), full, x:50, y:full ? 50 : 12, w:full ? 100 : 30, opacity:100};
      saveOv();
    };
    im.src = r.url + "?t=" + Date.now();
  };
  rd.readAsDataURL(f);
};
$("#ovClear").onclick = () => { S.ov = null; $("#ovFile").value = ""; saveOv(); };
$("#ovFull").onchange = () => { if (S.ov) { S.ov.full = $("#ovFull").checked; if (!S.ov.full && S.ov.w > 90) S.ov.w = 30; saveOv(); } };
$("#ovsize").oninput = () => { if (S.ov) { S.ov.w = +$("#ovsize").value; saveOv(); } };
$("#ov_opacity").oninput = () => { if (S.ov) { S.ov.opacity = +$("#ov_opacity").value; saveOv(); } };
(function(){
  const img = $("#ovPrev"); let d = null;
  img.addEventListener("pointerdown", e => {
    if (!S.ov || S.ov.full) return;
    e.preventDefault(); e.stopPropagation(); img.setPointerCapture(e.pointerId);
    const r = $("#frame").getBoundingClientRect(); d = {x:e.clientX, y:e.clientY, w:r.width, h:r.height, x0:S.ov.x, y0:S.ov.y};
  });
  img.addEventListener("pointermove", e => {
    if (!d) return;
    S.ov.x = Math.round(Math.max(0, Math.min(100, d.x0 + (e.clientX - d.x) / d.w * 100)));
    S.ov.y = Math.round(Math.max(0, Math.min(100, d.y0 + (e.clientY - d.y) / d.h * 100)));
    renderOverlay();
  });
  const end = () => { if (d) saveOv(); d = null; };
  img.addEventListener("pointerup", end); img.addEventListener("pointercancel", end);
})();
function drawFacePicker(){
  if (!splitting() || !S.prep) return;
  const cv = $("#faceCv"), v = vid(), [sw, sh] = S.dims, dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth || 300, H = W * sh / sw;
  if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); cv.style.height = H + "px"; }
  const g = cv.getContext("2d"), X = cv.width, Y = cv.height;
  if (v.videoWidth) g.drawImage(v, 0, 0, X, Y); else { g.fillStyle = "#000"; g.fillRect(0, 0, X, Y); }
  const f = S.face, bx = f.x * X, by = f.y * Y, bw = f.w * X, bh = f.h * Y;
  g.fillStyle = "rgba(0,0,0,.45)";
  g.fillRect(0, 0, X, by); g.fillRect(0, by + bh, X, Y - by - bh); g.fillRect(0, by, bx, bh); g.fillRect(bx + bw, by, X - bx - bw, bh);
  g.strokeStyle = "#ffe000"; g.lineWidth = 2 * dpr; g.strokeRect(bx, by, bw, bh);
  g.fillStyle = "#ffe000"; g.fillRect(bx + bw - 7 * dpr, by + bh - 7 * dpr, 14 * dpr, 14 * dpr);
}
vid().addEventListener("seeked", drawFacePicker);
vid().addEventListener("loadeddata", () => { drawFacePicker(); drawSplit(); });
$("#splitOn").onchange = () => {
  S.splitOn = $("#splitOn").checked; store.set("splitOn", S.splitOn);
  S.crop.y = 0.5; layout();
};
$("#splitPct").oninput = () => { S.split = +$("#splitPct").value / 100; store.set("split", S.split); showOutputs(); layout(); };
(function(){
  const cv = $("#faceCv"); let d = null;
  cv.addEventListener("pointerdown", e => {
    e.preventDefault(); cv.setPointerCapture(e.pointerId);
    const r = cv.getBoundingClientRect(), px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height, f = S.face;
    const corner = Math.abs(px - (f.x + f.w)) < 0.04 && Math.abs(py - (f.y + f.h)) < 0.06;
    d = {px, py, f:{...f}, mode: corner ? "size" : "move", r};
  });
  cv.addEventListener("pointermove", e => {
    if (!d) return;
    const px = (e.clientX - d.r.left) / d.r.width, py = (e.clientY - d.r.top) / d.r.height, f = d.f, cl = (v, a, b) => Math.max(a, Math.min(b, v));
    if (d.mode === "move") { S.face.x = cl(f.x + px - d.px, 0, 1 - f.w); S.face.y = cl(f.y + py - d.py, 0, 1 - f.h); }
    else { S.face.w = cl(f.w + px - d.px, 0.05, 1 - f.x); S.face.h = cl(f.h + py - d.py, 0.05, 1 - f.y); }
    drawFacePicker(); drawSplit();
  });
  const end = () => { if (d) store.set("face", S.face); d = null; };
  cv.addEventListener("pointerup", end); cv.addEventListener("pointercancel", end);
})();
window.addEventListener("resize", () => { if (S.prep) layout(); });
$("#aspSeg").onclick = e => {
  const b = e.target.closest("button"); if (!b || b.dataset.a === S.aspect) return;
  const wasWide = S.aspect === "16:9", nowWide = b.dataset.a === "16:9";
  [...$("#aspSeg").children].forEach(x => x.classList.toggle("on", x === b));
  S.aspect = b.dataset.a;
  if (wasWide !== nowWide) {
    S.style.size = +(nowWide ? S.style.size * 1.9 : S.style.size / 1.9).toFixed(1);
    S.style.position = nowWide ? 8 : 28; loadStyle(S.style);
  }
  layout();
};
$("#zoom").oninput = () => { S.crop.zoom = +$("#zoom").value; showOutputs(); layout(); };
$("#centerBtn").onclick = () => { S.crop = {x:0.5, y:0.5, zoom:1}; $("#zoom").value = 1; showOutputs(); layout(); };
(function(){
  let drag = null;
  const D = $("#drag");
  D.addEventListener("pointerdown", e => { D.setPointerCapture(e.pointerId); drag = {x:e.clientX, y:e.clientY, moved:false}; });
  D.addEventListener("pointermove", e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    const [w] = frameSize(), [sw, sh] = S.dims, [cw, ch] = cropBox(), k = w / cw;
    if (sw - cw > 1) S.crop.x = Math.min(1, Math.max(0, S.crop.x - dx / ((sw - cw) * k)));
    if (sh - ch > 1) S.crop.y = Math.min(1, Math.max(0, S.crop.y - dy / ((sh - ch) * k)));
    drag.x = e.clientX; drag.y = e.clientY; layout();
  });
  D.addEventListener("pointerup", () => { if (drag && !drag.moved) togglePlay(); drag = null; });
})();

// ---------------------------------------------------------------- playback & trim
function togglePlay(){ const v = vid(); if (v.paused) { if (v.currentTime >= S.cut[1] - 0.05 || v.currentTime < S.cut[0]) v.currentTime = S.cut[0]; v.play(); } else v.pause(); }
$("#playBtn").onclick = togglePlay;
$("#seek").oninput = () => { vid().currentTime = +$("#seek").value; };
function updateTrim(){
  const L = S.prep ? S.prep.length : 0;
  S.cut[0] = Math.max(0, Math.min(S.cut[0], S.cut[1] - 1)); S.cut[1] = Math.min(L, Math.max(S.cut[1], S.cut[0] + 1));
  $("#inT").textContent = fmtT1(S.prep.sec_start + S.cut[0]); $("#outT").textContent = fmtT1(S.prep.sec_start + S.cut[1]);
  $("#lenT").textContent = (S.cut[1] - S.cut[0]).toFixed(1) + "s";
  $("#selBar").style.left = (S.cut[0] / L * 100) + "%"; $("#selBar").style.width = ((S.cut[1] - S.cut[0]) / L * 100) + "%";
  renderLines();
}
document.querySelectorAll("[data-t]").forEach(b => b.onclick = () => { const i = b.dataset.t === "in" ? 0 : 1; S.cut[i] += +b.dataset.d; updateTrim(); vid().currentTime = S.cut[i] - (i ? 1.5 : 0); });
document.querySelectorAll("[data-set]").forEach(b => b.onclick = () => { S.cut[b.dataset.set === "in" ? 0 : 1] = vid().currentTime; updateTrim(); });
(function loop(){
  const v = vid();
  if (S.prep && !$("#editor").classList.contains("hidden")) {
    if (!v.paused && v.currentTime >= S.cut[1]) { v.pause(); v.currentTime = S.cut[1]; }
    $("#seek").value = v.currentTime; $("#tc").textContent = fmtT1(S.prep.sec_start + v.currentTime);
    $("#playBtn").textContent = v.paused ? "▶" : "❚❚";
    drawSplit(); if (!v.paused) drawFacePicker();
    renderCap();
  }
  requestAnimationFrame(loop);
})();

// ---------------------------------------------------------------- caption words
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
  if (!toks.length) { S.lines.splice(i, 1); renderLines(); return; }
  const parsed = toks.map(t => { const m = t.match(/^\*(.+)\*$/); return {w: m ? m[1] : t, emph: !!m}; });
  let nl;
  if (parsed.length === old.length) nl = parsed.map((p, j) => ({...old[j], w:p.w, emph:p.emph}));
  else { const step = (e - s) / parsed.length; nl = parsed.map((p, j) => ({s: s + j*step, e: s + (j+1)*step, w:p.w, emph:p.emph})); }
  S.lines[i] = nl;
}
function renderLines(){
  const box = $("#lines"); if (!box) return; box.innerHTML = "";
  if (!S.lines.length) { box.innerHTML = '<div class="line"><span class="hint">No caption lines.</span></div>'; return; }
  S.lines.forEach((l, i) => {
    const d = document.createElement("div"); d.className = "line"; d.dataset.i = i;
    if (lineEnd(l) <= S.cut[0] || l[0].s >= S.cut[1]) d.classList.add("out");
    const tm = document.createElement("span"); tm.className = "tm"; tm.textContent = fmtT((S.prep ? S.prep.sec_start : 0) + l[0].s); tm.title = "Jump here";
    tm.onclick = () => { vid().currentTime = l[0].s + 0.01; };
    const inp = document.createElement("input"); inp.type = "text"; inp.value = lineText(l);
    inp.oninput = () => setLineText(+d.dataset.i, inp.value);
    inp.onchange = renderLines;
    const del = document.createElement("button"); del.className = "small"; del.textContent = "×"; del.title = "Delete line";
    del.onclick = () => { S.lines.splice(i, 1); renderLines(); };
    d.append(tm, inp, del); box.appendChild(d);
  });
}
$("#addLine").onclick = () => {
  const t = vid().currentTime || S.cut[0];
  S.lines.push([{s:t, e:Math.min(S.prep.length, t + 2), w:"TEXT", emph:false}]);
  S.lines.sort((a, b) => a[0].s - b[0].s); renderLines();
};

// ---------------------------------------------------------------- style controls
function hex2rgba(h, a){ h = h.replace("#",""); return `rgba(${parseInt(h.slice(0,2),16)},${parseInt(h.slice(2,4),16)},${parseInt(h.slice(4,6),16)},${a})`; }
function loadStyle(st){
  S.style = {x:50, ...st};
  if (!S.style.animation) S.style.animation = S.style.pop ? "pop" : "none";
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
  S.style.pop = S.style.animation === "pop";
  showOutputs(); renderCap();
}
function showOutputs(){
  document.querySelectorAll(".ctl").forEach(c => { const i = c.querySelector("input[type=range]"), o = c.querySelector("output");
    if (i && o) o.textContent = (i.id.includes("opacity") || i.id === "volume") ? i.value + "%" : (i.id === "zoom" ? (+i.value).toFixed(2) + "×" : i.value); });
}
document.querySelectorAll("#capPanel input, #capPanel select").forEach(el => {
  if (el.closest("#lines")) return;
  el.addEventListener("input", () => {
    const oldW = S.style.words_per_line; readStyle();
    if (el.id === "wpl" && oldW !== S.style.words_per_line) { S.lines = chunk(S.lines.flat(), S.style.words_per_line); renderLines(); }
  });
});
document.querySelectorAll("[data-preset]").forEach(b => b.onclick = () => {
  loadStyle(S.info.presets[b.dataset.preset][S.aspect === "16:9" ? "landscape" : "vertical"]);
  S.lines = chunk(S.lines.flat(), S.style.words_per_line); renderLines();
});
$("#capOn").onchange = () => $("#capPanel").classList.toggle("hidden", !$("#capOn").checked);

// ---------------------------------------------------------------- live caption preview
function renderCredit(){
  const el = $("#creditPrev"), t = $("#credit").value.trim(), H = $("#frame").clientHeight, vertical = S.aspect !== "16:9";
  el.textContent = t;
  el.style.top = (vertical ? 12 : 5) + "%";
  el.style.fontSize = (H * (vertical ? 0.03 : 0.045)) + "px";
}
$("#credit").addEventListener("input", () => { store.set("credit", $("#credit").value); renderCredit(); });
function renderHeadline(){
  const el = $("#headPrev"), H = $("#frame").clientHeight, vertical = S.aspect !== "16:9";
  el.textContent = $("#headline").value.trim();
  el.style.top = (vertical ? 19 : 12) + "%";
  el.style.fontSize = (H * (vertical ? 0.045 : 0.07)) + "px";
}
$("#headline").addEventListener("input", renderHeadline);
$("#volume").addEventListener("input", () => {
  const v = +$("#volume").value; vid().volume = v / 100; vid().muted = v === 0;
  $("#volume").parentElement.querySelector("output").textContent = v + "%";
});
function renderCap(){
  renderCredit(); renderHeadline();
  const cap = $("#cap"), st = S.style;
  cap.classList.remove("movable", "ghost"); cap.style.transform = ""; cap.style.opacity = "";
  if (!$("#capOn").checked || !S.lines.length) { cap.innerHTML = ""; return; }
  const t = vid().currentTime || 0;
  let line = S.lines.find(l => t >= l[0].s && t < lineEnd(l));
  document.querySelectorAll(".line").forEach(d => d.classList.toggle("now", S.lines[+d.dataset.i] === line));
  if (line && (t < S.cut[0] || t > S.cut[1])) line = null;
  let ghost = false;
  if (!line) {               // paused between lines: show one faded so it can be dragged into place
    if (!vid().paused) { cap.innerHTML = ""; return; }
    line = S.lines.find(l => lineEnd(l) > S.cut[0]) || S.lines[0]; ghost = true;
  }
  cap.classList.add("movable"); cap.classList.toggle("ghost", ghost);
  let active = -1; if (!ghost) line.forEach((w, i) => { if (w.s <= t) active = i; });
  const H = $("#frame").clientHeight, size = H * st.size / 100;
  const op = st.text_opacity / 100, ow = size * st.outline / 100;
  cap.style.bottom = st.position + "%";
  const x = st.x == null ? 50 : st.x; cap.style.left = (x - 44) + "%"; cap.style.right = (56 - x) + "%";
  const anim = st.animation || (st.pop ? "pop" : "none"), p = ghost ? 9 : t - line[0].s;
  if (anim === "fade") cap.style.opacity = Math.min(1, p / 0.16);
  if (anim === "bounce") cap.style.transform = `scale(${p < 0.09 ? 0.7 + 0.38 * p / 0.09 : p < 0.17 ? 1.08 - 0.08 * (p - 0.09) / 0.08 : 1})`;
  if (anim === "slide") { const q = Math.min(1, p / 0.16); cap.style.transform = `translateY(${(1 - q) * size * 0.8}px)`; cap.style.opacity = Math.min(1, p / 0.12); }
  cap.style.fontFamily = `"${st.font}", Arial, sans-serif`;
  cap.style.fontSize = size + "px"; cap.style.fontWeight = st.bold ? "800" : "400";
  const box = st.box ? `background:${hex2rgba(st.box_color, st.box_opacity/100)};padding:${size*0.12}px ${size*0.2}px;` : "";
  const shadow = st.shadow ? `text-shadow:0 ${size*0.04}px ${size*0.06}px rgba(0,0,0,${0.5*op});` : "";
  const html = line.map((w, i) => {
    const txt = escapeHtml(st.uppercase ? w.w.toUpperCase() : w.w);
    const on = i === active && st.highlight_mode === "word";
    const hide = anim === "typewriter" && !ghost && i > active ? "visibility:hidden;" : "";
    const col = hex2rgba(on || w.emph ? st.highlight : st.color, op);
    const scale = on && anim === "pop" ? "transform:scale(1.12);" : "";
    return `<span class="wd" style="color:${col};-webkit-text-stroke:${ow*2}px ${hex2rgba(st.outline_color, op)};paint-order:stroke fill;${shadow}${scale}${hide}">${txt}</span>`;
  }).join(" ");
  cap.innerHTML = `<span class="box" style="${box}">${html}</span>`;
  // Same rule as the final render: pull the line in so none of it goes off screen.
  const W = $("#frame").clientWidth, tw = Math.min(cap.firstChild.getBoundingClientRect().width, W * 0.88);
  const half = tw / 2 / W * 100, cx = Math.max(half + 3, Math.min(100 - half - 3, x));
  cap.style.left = (cx - 44) + "%"; cap.style.right = (56 - cx) + "%";
}

(function(){                // drag the captions to place them
  const cap = $("#cap"); let d = null;
  cap.addEventListener("pointerdown", e => {
    e.preventDefault(); e.stopPropagation(); cap.setPointerCapture(e.pointerId);
    const r = $("#frame").getBoundingClientRect();
    d = {x:e.clientX, y:e.clientY, w:r.width, h:r.height, x0:S.style.x == null ? 50 : S.style.x, p0:S.style.position};
    cap.classList.add("moving");
  });
  cap.addEventListener("pointermove", e => {
    if (!d) return;
    S.style.x = Math.round(Math.max(10, Math.min(90, d.x0 + (e.clientX - d.x) / d.w * 100)));
    S.style.position = Math.round(Math.max(2, Math.min(90, d.p0 - (e.clientY - d.y) / d.h * 100)));
    $("#x").value = S.style.x; $("#position").value = S.style.position; showOutputs(); renderCap();
  });
  const end = () => { d = null; cap.classList.remove("moving"); };
  cap.addEventListener("pointerup", end); cap.addEventListener("pointercancel", end);
})();

// ---------------------------------------------------------------- make
$("#makeBtn").onclick = async () => {
  $("#makeBtn").disabled = true; $("#result").innerHTML = ""; vid().pause();
  const words = [], lines = [];
  S.lines.forEach(l => { const idx = []; l.forEach(w => { idx.push(words.length); words.push({s:w.s, e:w.e, w:w.w, emph:w.emph}); }); lines.push(idx); });
  try {
    const r = await runJob("/api/make", {url:$("#url").value.trim(), browser:$("#browser").value,
      sec_start:S.prep.sec_start, sec_end:S.prep.sec_end, cut_in:S.cut[0], cut_out:S.cut[1],
      title:S.title || S.clip.title || "", aspect:S.aspect, crop: splitting() ? {...S.crop, face:S.face, split:S.split} : S.crop,
      overlay: S.ov ? {name:S.ov.name, full:S.ov.full, x:S.ov.x, y:S.ov.y, w:S.ov.w, opacity:S.ov.opacity} : null,
      captions:$("#capOn").checked, words, lines, style:S.style, credit:$("#credit").value.trim(),
      headline:$("#headline").value.trim(), volume:+$("#volume").value}, $("#makeStatus"));
    $("#result").innerHTML = `<video src="${r.file}" controls playsinline></video><div class="hint">Saved as <b>${escapeHtml(r.name)}</b> in ${escapeHtml(S.info.out_dir)}</div>`;
  } catch(e) {} finally { $("#makeBtn").disabled = false; }
};
$("#openBtn").onclick = () => api("/api/open", {});
function showOutDir(){ $("#outDirLbl").textContent = S.info.out_dir; $("#outDir").value = S.info.out_dir; }
$("#outDir").addEventListener("drop", e => {
  // Finder drops a file:// URL; turn it into a plain path.
  const t = e.dataTransfer.getData("text/uri-list") || e.dataTransfer.getData("text/plain");
  if (t && t.startsWith("file://")) { e.preventDefault(); $("#outDir").value = decodeURIComponent(t.replace("file://", "").trim()); }
});
$("#outDirBtn").onclick = async () => {
  const r = await fetch("/api/settings", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({out_dir:$("#outDir").value})});
  const j = await r.json();
  if (j.error) return status($("#outStatus"), j.error, "err");
  S.info.out_dir = j.out_dir; showOutDir(); status($("#outStatus"), "Saved. New clips will go to " + j.out_dir, "");
};

// ---------------------------------------------------------------- start
const READY = (async () => {
  S.info = await api("/api/info");
  loadStyle(S.info.presets.bold.vertical);
  const w = [];
  if (!S.info.ytdlp) w.push("yt-dlp isn't installed. In Terminal run: python3 -m pip install -U \"yt-dlp[default]\"");
  if (!S.info.ffmpeg) w.push("ffmpeg isn't installed. Mac: brew install ffmpeg-full");
  else if (!S.info.captions) w.push("Your ffmpeg can't draw captions, so clips will be made without them. Mac fix: brew install ffmpeg-full (then restart Clip Maker).");
  if (!S.info.tesseract) { $("#skipText").checked = false; $("#skipText").disabled = true;
    $("#skipLbl").title = S.info.tesseract_hint; w.push(S.info.tesseract_hint); }
  $("#warn").innerHTML = w.map(x => `<div class="warn">${escapeHtml(x)}</div>`).join("");
  if (S.info.mac) $("#browser").value = "chrome";
  showOutDir();
  $("#credit").value = store.get("credit", "");
  S.splitOn = !!store.get("splitOn", false); $("#splitOn").checked = S.splitOn;
  S.split = +store.get("split", 0.4) || 0.4; $("#splitPct").value = Math.round(S.split * 100);
  const sf = store.get("face", null); if (sf && sf.w > 0 && sf.h > 0) S.face = sf;
  const so = store.get("overlay", null); if (so && so.name) { S.ov = so; renderOverlay(); }
  $("#smartLine").textContent = {
    claude:"Smart picks: Claude reads the transcript.",
    local:"Smart picks: the free local AI (Ollama) reads the transcript.",
    free:"Free picks: by popularity, loudness and words matching your focus. " + S.info.local_note}[S.info.smart];
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
