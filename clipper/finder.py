"""Find the best moments in a video automatically.

Signals, best first:
  1. YouTube's "Most replayed" graph (heatmap) - where viewers rewatch.
  2. The transcript, scored by Claude for hook / stands-alone / payoff
     (only when an Anthropic API key is set up).
  3. Audio loudness - laughter, applause, raised voices (used when the
     video has no "Most replayed" graph, and for local files).

Each found clip gets a score from 0 to 100 and a short reason.
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

CLAUDE_MODEL = "claude-opus-5-5"


# ---------------------------------------------------------------- data

def video_info(source, ytdlp):
    """Full yt-dlp metadata (duration, title, heatmap, captions)."""
    r = subprocess.run(ytdlp + ["--no-playlist", "--ignore-no-formats-error", "-J", source],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        msg = (r.stderr or "").strip().splitlines()
        raise RuntimeError("could not read that video. " + (msg[-1] if msg else ""))
    return json.loads(r.stdout)


def heatmap_curve(info):
    """Per-second 'most replayed' value (0-1) from yt-dlp's heatmap, or None."""
    hm = info.get("heatmap") or []
    duration = int(info.get("duration") or 0)
    if not hm or not duration:
        return None
    curve = [0.0] * (duration + 1)
    for seg in hm:
        a, b = int(seg["start_time"]), int(seg["end_time"])
        for t in range(max(0, a), min(duration, b) + 1):
            curve[t] = max(curve[t], float(seg.get("value") or 0))
    top = max(curve) or 1.0
    return [v / top for v in curve]


def download_transcript(source, ytdlp, workdir):
    """YouTube captions (manual first, then auto) as [(start, end, text)]."""
    base = os.path.join(workdir, "subs")
    subprocess.run(
        ytdlp + ["--no-playlist", "--skip-download", "--ignore-no-formats-error", "--write-subs", "--write-auto-subs",
                 "--sub-langs", "en.*,en,-live_chat", "--sub-format", "json3/vtt/best",
                 "-o", base, source],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    files = sorted(glob.glob(base + "*"))
    # Prefer human-made subtitles (shorter language code like 'en') over 'en-orig' etc.
    files.sort(key=lambda f: (not f.endswith(".json3"), len(f)))
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                text = fh.read()
            cues = parse_json3(text) if f.endswith(".json3") else parse_vtt(text)
            if cues:
                return cues
        except (OSError, ValueError):
            continue
    return []


def parse_json3(text):
    cues = []
    for ev in json.loads(text).get("events", []):
        words = "".join(s.get("utf8", "") for s in ev.get("segs") or []).strip()
        if not words or "tStartMs" not in ev:
            continue
        start = ev["tStartMs"] / 1000
        cues.append((start, start + ev.get("dDurationMs", 0) / 1000, words.replace("\n", " ")))
    return merge_cues(cues)


def parse_vtt(text):
    cues = []
    ts = r"(\d+):(\d+):(\d+(?:\.\d+)?)|(\d+):(\d+(?:\.\d+)?)"

    def sec(m):
        if m.group(1) is not None:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        return int(m.group(4)) * 60 + float(m.group(5))

    blocks = re.split(r"\n\s*\n", text.replace("\r", ""))
    for block in blocks:
        lines = block.strip().splitlines()
        for i, line in enumerate(lines):
            if "-->" in line:
                a, b = line.split("-->", 1)
                ma, mb = re.search(ts, a), re.search(ts, b)
                if not (ma and mb):
                    break
                words = " ".join(re.sub(r"<[^>]+>", "", l) for l in lines[i + 1:]).strip()
                if words:
                    cues.append((sec(ma), sec(mb), words))
                break
    return merge_cues(cues)


def merge_cues(cues):
    """Drop the repeated lines that YouTube auto-captions roll forward."""
    out = []
    for s, e, t in sorted(cues):
        if out and (t == out[-1][2] or out[-1][2].endswith(t)):
            out[-1] = (out[-1][0], max(e, out[-1][1]), out[-1][2])
            continue
        if out and t.startswith(out[-1][2]):
            t = t[len(out[-1][2]):].strip() or t
        out.append((s, e, t))
    return out


def loudness_curve(media, ffmpeg):
    """Per-second loudness (0-1) using ffmpeg's astats, or None."""
    r = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-i", media, "-vn", "-af",
         "aresample=8000,asetnsamples=n=8000,astats=metadata=1:reset=1,"
         "ametadata=print:key=lavfi.astats.Overall.RMS_level",
         "-f", "null", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    levels = []
    for m in re.finditer(r"RMS_level=(-?inf|-?\d+(?:\.\d+)?)", r.stderr):
        v = m.group(1)
        levels.append(-90.0 if "inf" in v else max(-90.0, float(v)))
    if len(levels) < 5:
        return None
    # Rank-based scaling: robust to music beds and quiet intros.
    order = sorted(levels)
    n = len(order) - 1
    rank = {}
    for i, v in enumerate(order):
        rank.setdefault(v, i / n)
    return [rank[v] for v in levels]


# Loudness maps of long streams are saved here, so a 12-hour VOD is downloaded
# and measured once; later searches (new focus, count or length) are instant.
CURVE_CACHE = os.path.join(tempfile.gettempdir(), "clipmaker_cache", "loudness")
LAST_MAP = {}     # source -> (curve, duration) from the latest search, for the hype map


def _curve_key(source, is_local):
    tag = source
    if is_local:
        try:
            st = os.stat(source)
            tag = f"{os.path.abspath(source)}|{st.st_size}|{int(st.st_mtime)}"
        except OSError:
            pass
    return hashlib.sha1(tag.encode()).hexdigest()[:20]


def cached_curve(source, is_local):
    try:
        with open(os.path.join(CURVE_CACHE, _curve_key(source, is_local) + ".json")) as fh:
            curve = json.load(fh)
        return curve if isinstance(curve, list) and len(curve) >= 5 else None
    except (OSError, ValueError):
        return None


def save_curve(source, is_local, curve):
    try:
        os.makedirs(CURVE_CACHE, exist_ok=True)
        with open(os.path.join(CURVE_CACHE, _curve_key(source, is_local) + ".json"), "w") as fh:
            json.dump([round(v, 4) for v in curve], fh)
    except OSError:
        pass


def hype_map(curve, points=600):
    """The loudness curve squeezed to at most `points` values (each a max) for drawing."""
    if not curve:
        return []
    step = max(1, -(-len(curve) // points))
    return [round(max(curve[i:i + step]), 3) for i in range(0, len(curve), step)]


def download_audio(source, ytdlp, ffmpeg, workdir, progress=None):
    out = os.path.join(workdir, "audio.%(ext)s")
    # Streams (Twitch, Kick) come in thousands of small pieces: fetch 8 at once.
    cmd = ytdlp + ["--no-playlist", "--no-warnings", "--newline", "-f", "ba/b",
                   "--concurrent-fragments", "8",
                   "--ffmpeg-location", ffmpeg, "-o", out, source]
    if progress:
        import clip
        try:
            clip.run_progress(cmd, progress)
        except (RuntimeError, SystemExit):
            pass
    else:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    found = glob.glob(os.path.join(workdir, "audio.*"))
    return found[0] if found else None


# ---------------------------------------------------------------- scoring

def window_mean(curve, s, e):
    if not curve:
        return 0.0
    a, b = max(0, int(s)), min(len(curve), max(int(s) + 1, int(e)))
    seg = curve[a:b]
    return sum(seg) / len(seg) if seg else 0.0


def snap(start, end, cues, min_len, max_len):
    """Move cut points to sentence/caption edges so nothing starts mid-word."""
    if not cues:
        return start, end
    starts = [c[0] for c in cues]
    ends = [c[1] for c in cues]
    s = max([x for x in starts if x <= start + 0.5] or [start])
    if start - s > 4:          # nearest caption start is too far back
        s = start
    later = [x for x in ends if x >= end - 0.5]
    e = min(later) if later else end
    if e - end > 4:
        e = end
    if e - s > max_len:
        e = s + max_len
    if e - s < min_len:
        e = s + min_len
    return round(s, 2), round(e, 2)


def overlaps(a, b, gap=2.0):
    return a[0] < b[1] + gap and b[0] < a[1] + gap


def pick_top(candidates, count):
    chosen = []
    for c in sorted(candidates, key=lambda c: c["score"], reverse=True):
        if all(not overlaps((c["start"], c["end"]), (x["start"], x["end"])) for x in chosen):
            chosen.append(c)
        if len(chosen) == count:
            break
    return sorted(chosen, key=lambda c: c["score"], reverse=True)


def fmt(t):
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def damp_edges(curve, duration):
    """Turn down the opening and the ending before picking peaks.

    Nearly everyone watches a video's first seconds, so YouTube's "Most
    replayed" graph is usually highest right at the start, and intros and
    end screens are often the loudest parts. Without this, clips pile up at
    the beginning. The first and last few percent ramp from 25% weight up
    to full weight; the curve is then rescaled so its top is 1 again.
    """
    n = len(curve)
    edge = int(min(45, max(8, 0.04 * duration)))
    out = list(curve)
    for i in range(n):
        dist = min(i, n - 1 - i)
        if dist < edge:
            out[i] *= 0.25 + 0.75 * dist / edge
    top = max(out) or 1.0
    return [v / top for v in out]


def signal_clips(curve, label, duration, count, min_len, max_len, cues, words=None):
    """Free mode: grow a clip around each peak of the curve.

    Starting at the highest point, the clip widens while the curve stays
    above 60% of the peak, then is padded or trimmed to fit min/max length.
    """
    n = min(len(curve), int(duration) + 1)
    if n <= 0:
        return []
    curve = damp_edges(curve[:n], duration)
    used = [False] * n
    out = []
    for peak in sorted(range(n), key=lambda i: curve[i], reverse=True):
        if len(out) == count:
            break
        if used[peak] or curve[peak] <= 0:
            continue
        floor = 0.6 * curve[peak]
        s = e = peak
        while s > 0 and not used[s - 1] and curve[s - 1] >= floor and e - s < max_len:
            s -= 1
        while e < n - 1 and not used[e + 1] and curve[e + 1] >= floor and e - s < max_len:
            e += 1
        start, end = float(s), float(e + 1)
        if end - start < min_len:                       # pad evenly around the peak
            extra = min_len - (end - start)
            start = max(0.0, start - extra / 2)
            end = min(float(duration), start + min_len)
            start = max(0.0, end - min_len)
        start, end = edge_snap(start, end, cues, words, min_len, max_len)
        end = min(end, float(duration))
        if any(overlaps((start, end), (c["start"], c["end"]), 0) for c in out):
            for i in range(int(start), min(n, int(end) + 1)):
                used[i] = True
            continue
        for i in range(int(start), min(n, int(end) + 1)):
            used[i] = True
        out.append({
            "start": start, "end": end,
            "score": round(100 * window_mean(curve, start, end)),
            "title": "", "reason": f"{label} (peak at {fmt(peak)})",
        })
    out.sort(key=lambda c: c["score"], reverse=True)
    # Flat stretches make long, dull clips; keep only ones near the best.
    return [c for c in out if c["score"] >= 0.35 * out[0]["score"]] if out else out


def transcript_text(cues):
    return "\n".join(f"[{s:.1f}] {t}" for s, _, t in cues)


def heatmap_summary(curve):
    if not curve:
        return "No 'Most replayed' data for this video."
    peaks = sorted(range(len(curve)), key=lambda i: curve[i], reverse=True)
    picked = []
    for i in peaks:
        if all(abs(i - p) > 20 for p in picked):
            picked.append(i)
        if len(picked) == 10:
            break
    return "Most-replayed peaks (time: strength 0-1): " + ", ".join(
        f"{fmt(p)}: {curve[p]:.2f}" for p in sorted(picked))


CLIP_SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number", "description": "seconds"},
                    "end": {"type": "number", "description": "seconds"},
                    "title": {"type": "string"},
                    "hook": {"type": "integer", "description": "0-10"},
                    "standalone": {"type": "integer", "description": "0-10"},
                    "payoff": {"type": "integer", "description": "0-10"},
                    "reason": {"type": "string"},
                },
                "required": ["start", "end", "title", "hook", "standalone", "payoff", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You pick short-form clips (YouTube Shorts, Reels, TikTok) from long videos.

A good clip:
- Hook: the first 3 seconds make a viewer stop scrolling (a bold claim, a question, a surprise, a strong opinion, a funny line). Start on that line, not on filler like "so", "um", or "anyway".
- Standalone: makes sense to someone who has not seen the rest of the video. No "as I said earlier" or unexplained references.
- Payoff: ends on a punchline, reveal, useful tip, or emotional peak, at the end of a sentence.

Score each of hook, standalone, and payoff from 0 to 10 honestly; do not inflate.
Use the timestamps in the transcript: start = the timestamp of the clip's first line, end = the timestamp of the line after its last line.
Clips must not overlap. The reason is one short sentence a creator would find useful.
The title is a short, catchy title for the clip (under 60 characters)."""


def claude_clips(cues, curve, title, count, min_len, max_len, focus=""):
    """Ask Claude to choose clips from the transcript. Returns list or raises."""
    import anthropic  # imported here so free mode works without it

    client = anthropic.Anthropic()
    wish = (f"The creator wants clips about: {focus}\nStrongly prefer moments that match "
            "this. If only a few match, return fewer clips rather than unrelated ones, and "
            "say in the reason how each clip matches.\n" if focus else "")
    prompt = (
        f"Video title: {title}\n\n"
        f"Pick the {count} best clips, each between {min_len:.0f} and {max_len:.0f} seconds long.\n"
        f"{wish}"
        f"{heatmap_summary(curve)}\n"
        "Most-replayed peaks are a strong hint of what viewers liked; prefer clips that "
        "cover them when the transcript there is good.\n"
        "Every clip must start at the beginning of a sentence and end at the end of one.\n\n"
        f"<transcript>\n{transcript_text(cues)}\n</transcript>"
    )
    response = client.beta.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM_PROMPT,
        output_config={"effort": "medium",
                       "format": {"type": "json_schema", "schema": CLIP_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Claude's answer was cut off")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["clips"]


def edge_snap(start, end, cues, words, min_len, max_len):
    """Cut on whole sentences when we have word timings, else on caption lines."""
    if words:
        import captions
        s, e, _ = captions.sentence_snap(start, end, words, min_len * 0.8, max_len)
        return s, e
    return snap(start, end, cues, min_len, max_len)


# ---------------------------------------------------------------- free local AI (Ollama)

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
if not OLLAMA.startswith("http"):
    OLLAMA = "http://" + OLLAMA
LOCAL_MODEL = os.environ.get("CLIPMAKER_LOCAL_MODEL", "llama3.2")
LOCAL_HINT = ("For smarter free picks, install Ollama (ollama.com), then in Terminal run:  "
              f"ollama pull {LOCAL_MODEL}")


def _ollama(path, body=None, timeout=120):
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # it's local
    req = urllib.request.Request(OLLAMA + path, method="POST" if body else "GET",
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def local_ai_status():
    """(ready, note). Ready when Ollama runs and has the model."""
    try:
        names = [m.get("name", "") for m in _ollama("/api/tags", timeout=1.5).get("models", [])]
    except Exception:
        return False, None
    if any(n == LOCAL_MODEL or n.startswith(LOCAL_MODEL + ":") for n in names):
        return True, None
    return False, f"Ollama is running but doesn't have the model yet. In Terminal run:  ollama pull {LOCAL_MODEL}"


RATE_SCHEMA = {
    "type": "object",
    "properties": {"hook": {"type": "integer"}, "standalone": {"type": "integer"},
                   "payoff": {"type": "integer"}, "focus_match": {"type": "integer"},
                   "title": {"type": "string"}, "reason": {"type": "string"}},
    "required": ["hook", "standalone", "payoff", "focus_match", "title", "reason"],
}

RATE_PROMPT = """You rate short video clips for YouTube Shorts / TikTok from their transcript.
Score each from 0 to 10, honestly (most clips are 3-7):
- hook: do the first words make a viewer stop scrolling?
- standalone: does it make sense without the rest of the video?
- payoff: does it end on a punchline, reveal, useful tip or emotional peak?
- focus_match: how well it matches what the creator asked for (10 if nothing was asked).
title: a short catchy title under 60 characters. reason: one short sentence."""


def local_rate(text, title, focus):
    body = {"model": LOCAL_MODEL, "stream": False, "format": RATE_SCHEMA,
            "options": {"temperature": 0.2, "num_ctx": 4096},
            "messages": [{"role": "system", "content": RATE_PROMPT},
                         {"role": "user", "content":
                          f"Video: {title}\nThe creator wants: {focus or 'the best moments'}\n\n"
                          f"Clip transcript:\n{text[:3000]}"}]}
    out = json.loads(_ollama("/api/chat", body)["message"]["content"])
    clamp = lambda v: max(0, min(10, int(v)))
    return {k: clamp(out.get(k, 5)) for k in ("hook", "standalone", "payoff", "focus_match")} | \
           {"title": str(out.get("title", ""))[:80], "reason": str(out.get("reason", ""))[:200]}


def local_rerank(clips, cues, title, focus, count, log, prog):
    """Have the local model read each candidate's transcript and re-score it."""
    log(f"Reading {len(clips)} moments with the free local AI ({LOCAL_MODEL})...")
    out = []
    for i, c in enumerate(clips):
        prog(i / max(1, len(clips)))
        text = " ".join(t for s, e, t in cues if e > c["start"] and s < c["end"])
        if not text.strip():
            out.append(c)
            continue
        try:
            r = local_rate(text, title, focus)
        except Exception as err:
            log(f"  local AI couldn't rate {fmt(c['start'])} ({err}); keeping its score.")
            out.append(c)
            continue
        ai = (r["hook"] * 0.4 + r["standalone"] * 0.3 + r["payoff"] * 0.3) / 10
        if focus:
            ai = 0.6 * ai + 0.4 * r["focus_match"] / 10
        out.append(dict(c, score=round(100 * (0.55 * ai + 0.45 * c["score"] / 100)),
                        title=r["title"], reason=f"{r['reason']} ({c['reason'].split(' (')[0]})"))
    prog(1.0)
    return sorted(out, key=lambda c: c["score"], reverse=True)[:count]


# ---------------------------------------------------------------- focus

STOP = set("""a an and are as at be but by for from has have he her his i in into is it its
me my of on or our she so that the their them they this to was we were what when where which
who will with you your about moments moment clips clip parts part video videos stuff things
thing find show want like some any more most just only really very please focus""".split())


def stem(w):
    for suf in ("ing", "ers", "er", "ed", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def focus_terms(focus):
    """'car chases and funny reactions' -> {'car', 'chas', 'funny', 'reaction'}"""
    words = re.findall(r"[a-z0-9']+", (focus or "").lower())
    return {stem(w) for w in words if w not in STOP and len(w) > 2}


def focus_curve(terms, cues, n):
    """Per-second score of how much the transcript matches the focus words."""
    curve = [0.0] * n
    for s, e, text in cues:
        toks = {stem(t) for t in re.findall(r"[a-z0-9']+", text.lower())}
        hits = len(terms & toks)
        if hits:
            for t in range(max(0, int(s)), min(n, int(e) + 1)):
                curve[t] += hits
    if not any(curve):
        return None
    sm = []                                    # spread each hit over ~10 s
    for i in range(n):
        a, b = max(0, i - 5), min(n, i + 6)
        sm.append(sum(curve[a:b]) / (b - a))
    top = max(sm) or 1.0
    return [v / top for v in sm]


def matched_words(terms, cues, s, e):
    found = []
    for cs, ce, text in cues:
        if ce < s or cs > e:
            continue
        for t in re.findall(r"[a-z0-9']+", text.lower()):
            if stem(t) in terms and t not in found:
                found.append(t)
    return found


# ---------------------------------------------------------------- main entry

def find_clips(source, *, is_local, ytdlp, ffmpeg, workdir, count=5,
               min_len=15, max_len=60, use_ai=True, log=print, skip_text=None,
               focus="", progress=None):
    """Return (title, clips). Each clip: start, end, score, title, reason.

    skip_text: optional fetch(start, end) -> video path. When given, extra
    moments are found and any with a lot of on-screen text are skipped.
    focus: optional text, e.g. "car chases, funny reactions".
    progress: optional callback(fraction 0..1).
    """
    prog = progress or (lambda f: None)
    if not skip_text:
        return _find(source, is_local, ytdlp, ffmpeg, workdir, count,
                     min_len, max_len, use_ai, log, focus, prog)
    import textcheck
    title, cands = _find(source, is_local, ytdlp, ffmpeg, workdir, count * 2 + 2,
                         min_len, max_len, use_ai, log, focus, lambda f: prog(0.5 * f))
    if not textcheck.tesseract():
        log(textcheck.INSTALL_HINT)
        prog(1.0)
        return title, cands[:count]
    return title, textcheck.check(cands, skip_text, ffmpeg, workdir, count, log,
                                  progress=lambda f: prog(0.5 + 0.5 * f))


def _find(source, is_local, ytdlp, ffmpeg, workdir, count, min_len, max_len, use_ai, log,
          focus="", prog=lambda f: None):
    import captions
    cues, curve, info, words = [], None, {}, []
    terms = focus_terms(focus)
    if is_local:
        title = os.path.splitext(os.path.basename(source))[0]
        duration = None
    else:
        log("Reading video details...")
        prog(0.02)
        info = video_info(source, ytdlp)
        title = info.get("title") or "clip"
        duration = float(info.get("duration") or 0)
        curve = heatmap_curve(info)
        log("  'Most replayed' graph: " + ("found" if curve else "not available"))
        prog(0.12)
        log("Getting transcript...")
        cues = download_transcript(source, ytdlp, workdir)
        words = captions.fetch_words(source, ytdlp, workdir) if cues else []
        log(f"  transcript: {len(cues)} lines" if cues else "  transcript: none")
        prog(0.25)
    if focus and not cues:
        log(f"  No transcript, so the focus (\"{focus}\") can't be matched to what's said.")

    have_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    if use_ai and cues and have_key:
        log(f"Asking Claude to pick the best {count} moments"
            + (f' about "{focus}"' if focus else "") + " (about a minute)...")
        try:
            picks = claude_clips(cues, curve, title, count, min_len, max_len, focus)
            out = []
            for p in picks:
                s, e = float(p["start"]), float(p["end"])
                if duration:
                    s, e = max(0.0, min(s, duration - 1)), min(e, duration)
                if e - s < 3:
                    continue
                s, e = edge_snap(s, e, cues, words, min_len, max_len)
                if duration:
                    e = min(e, duration)
                ai = (p["hook"] * 0.4 + p["standalone"] * 0.3 + p["payoff"] * 0.3) / 10
                score = 0.75 * ai + 0.25 * window_mean(curve, s, e) if curve else ai
                out.append({"start": s, "end": e, "score": round(100 * score),
                            "title": p["title"], "reason": p["reason"]})
            out = pick_top(out, count)
            if out:
                prog(1.0)
                return title, out
            log("  Claude returned no usable clips; using the free method instead.")
        except Exception as err:  # network, auth, bad output: fall back to free mode
            log(f"  Claude scoring failed ({err}); using the free method instead.")
    local_ok = False
    if use_ai and cues and not have_key:
        local_ok, note = local_ai_status()
        if not local_ok:
            log("No ANTHROPIC_API_KEY set: using the free method (no AI scoring).")
            log("  " + (note or LOCAL_HINT))

    label = "Most replayed section"
    if not curve:
        curve = cached_curve(source, is_local)
        if curve:
            log("Using the audio scan saved from last time (no download needed).")
    if not curve:
        log("Measuring audio loudness (long streams: this downloads the whole audio once)...")
        if is_local:
            media = source
        else:
            media = download_audio(source, ytdlp, ffmpeg, workdir,
                                   progress=lambda f: prog(0.3 + 0.5 * f))
        curve = loudness_curve(media, ffmpeg) if media else None
        if curve:
            save_curve(source, is_local, curve)
        if not curve:
            raise RuntimeError("couldn't find any signal to pick clips from "
                               "(no 'Most replayed' graph, transcript scoring, or audio).")
        duration = duration or len(curve)
        label = "Loud, energetic section"
    prog(0.85)

    if terms and cues:
        fc = focus_curve(terms, cues, len(curve))
        if fc:
            curve = [0.35 * a + 0.65 * b for a, b in zip(curve, fc)]
            label = f'Matches "{focus}"'
        else:
            log(f'  Nothing said in the video matched "{focus}"; picking the best moments overall.')
            terms = set()
    LAST_MAP[source] = (hype_map(curve), float(duration or len(curve)))
    want = count * 3 if local_ok else count
    clips = signal_clips(curve, label, duration, want, min_len, max_len, cues, words)
    for c in clips:
        if terms:
            hit = matched_words(terms, cues, c["start"], c["end"])
            c["reason"] = (f'Mentions {", ".join(hit[:4])}' if hit else "Near the focus") + \
                          " · " + c["reason"].split(" (peak")[0].replace(label, "popular part") \
                          if hit else c["reason"]
    if local_ok:
        clips = local_rerank(clips, cues, title, focus, count, log,
                             lambda f: prog(0.88 + 0.12 * f))
    prog(1.0)
    return title, clips


def print_clips(clips, out=sys.stdout):
    for i, c in enumerate(clips, 1):
        name = f"  {c['title']}" if c.get("title") else ""
        print(f"  {i}. {fmt(c['start'])}-{fmt(c['end'])}  "
              f"({c['end'] - c['start']:.0f}s)  score {c['score']}{name}", file=out)
        print(f"     {c['reason']}", file=out)
