"""Spot on-screen text (burned-in subtitles, captions, big titles).

Before a clip is used, a few frames from it are read with Tesseract (free
text recognition). Clips where much of the picture carries text are
skipped, because adding our captions on top of existing text looks messy.

Text that is on screen almost all the time (a game HUD, a streamer's name,
a channel watermark) is treated as part of the picture and ignored.
"""
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

MAX_TEXT_SHARE = 0.25   # skip a clip if more than 25% of its frames have text
MIN_WORDS = 2           # a frame "has text" with 2+ words, or one word of 5+ letters
EVERY = 2.0             # read one frame every 2 seconds


def tesseract():
    for c in (shutil.which("tesseract"), "/opt/homebrew/bin/tesseract",
              "/usr/local/bin/tesseract", r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
        if c and os.path.isfile(c):
            return c
    return None


INSTALL_HINT = ("To skip parts with text on screen, install Tesseract once:\n"
                "  Mac: brew install tesseract    Windows: winget install UB-Mannheim.TesseractOCR")


def sample_frames(video, ffmpeg, folder):
    os.makedirs(folder, exist_ok=True)
    subprocess.run([ffmpeg, "-y", "-i", video, "-vf", f"fps=1/{EVERY},scale=960:-2",
                    "-q:v", "3", os.path.join(folder, "f%04d.jpg")],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".jpg"))


def frame_words(exe, image):
    """Confident, real-looking words Tesseract finds in one frame."""
    # One thread per Tesseract: several run side by side, and their default
    # multi-threading makes them fight over the CPU and crawl.
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    r = subprocess.run([exe, image, "stdout", "--psm", "11", "tsv"], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
    words = set()
    for row in r.stdout.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) < 12:
            continue
        try:
            conf = float(cols[10])
        except ValueError:
            continue
        w = re.sub(r"[^A-Za-z0-9']", "", cols[11]).lower()
        # Game textures and noise come out as short or low-confidence junk.
        if conf >= 70 and len(w) >= 3 and re.search(r"[a-z]{2}", w):
            words.add(w)
    return words


def has_text(words):
    return len(words) >= MIN_WORDS or any(len(w) >= 5 for w in words)


def check(candidates, fetch, ffmpeg, workdir, count, log=print):
    """Read each candidate clip's frames; keep up to `count` clips without much text.

    fetch(start, end) -> path of a (low-resolution) video of that part.
    Adds "text_share" to each kept clip. Returns the kept clips.
    """
    exe = tesseract()
    if not exe:
        log(INSTALL_HINT)
        return candidates[:count]
    log(f"Checking {len(candidates)} moments for text on screen...")
    frames = []   # per candidate: list of word sets
    for i, c in enumerate(candidates):
        try:
            video = fetch(c["start"], c["end"])
            imgs = sample_frames(video, ffmpeg, os.path.join(workdir, f"txt{i}"))
            with ThreadPoolExecutor(max_workers=4) as pool:
                frames.append(list(pool.map(lambda im: frame_words(exe, im), imgs)))
        except Exception as err:  # can't check this one; don't block it
            log(f"  couldn't check {fmt(c['start'])}: {err}")
            frames.append([])

    # Overlay/HUD text (a streamer's name, a watermark) shows up in several
    # different moments; subtitles change all the time. Words found in 2+
    # moments, or in 40%+ of all frames, are treated as part of the picture.
    all_frames = [f for fl in frames for f in fl]
    in_frames, in_clips = {}, {}
    for fl in frames:
        for w in set().union(*fl) if fl else ():
            in_clips[w] = in_clips.get(w, 0) + 1
        for f in fl:
            for w in f:
                in_frames[w] = in_frames.get(w, 0) + 1
    overlay = {w for w in in_frames
               if in_clips.get(w, 0) >= 2 or in_frames[w] / max(1, len(all_frames)) >= 0.4}

    kept, rejected = [], []
    for c, fl in zip(candidates, frames):
        texty = sum(1 for f in fl if has_text(f - overlay))
        share = texty / len(fl) if fl else 0.0
        c = dict(c, text_share=round(share, 2))
        if share > MAX_TEXT_SHARE:
            log(f"  skipped {fmt(c['start'])}-{fmt(c['end'])}: text on screen "
                f"in {round(100 * share)}% of it")
            rejected.append(c)
        else:
            if share > 0:
                c["reason"] += f" · a little on-screen text ({round(100 * share)}%)"
            kept.append(c)
        if len(kept) == count:
            break
    if not kept and rejected:
        log("  every moment had text on screen; showing the least texty ones.")
        rejected.sort(key=lambda c: c["text_share"])
        for c in rejected[:count]:
            c["reason"] += f" · has on-screen text ({round(100 * c['text_share'])}%)"
        kept = rejected[:count]
    return kept


def fmt(t):
    t = int(t)
    return f"{t // 60}:{t % 60:02d}"
