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
import json
import os
import re
import subprocess
import sys

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


def download_audio(source, ytdlp, ffmpeg, workdir):
    out = os.path.join(workdir, "audio.%(ext)s")
    subprocess.run(ytdlp + ["--no-playlist", "--quiet", "--no-warnings", "-f", "ba/b",
                            "--ffmpeg-location", ffmpeg, "-o", out, source],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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


def signal_clips(curve, label, duration, count, min_len, max_len, cues):
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
        start, end = snap(start, end, cues, min_len, max_len)
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


def claude_clips(cues, curve, title, count, min_len, max_len):
    """Ask Claude to choose clips from the transcript. Returns list or raises."""
    import anthropic  # imported here so free mode works without it

    client = anthropic.Anthropic()
    prompt = (
        f"Video title: {title}\n\n"
        f"Pick the {count} best clips, each between {min_len:.0f} and {max_len:.0f} seconds long.\n"
        f"{heatmap_summary(curve)}\n"
        "Most-replayed peaks are a strong hint of what viewers liked; prefer clips that "
        "cover them when the transcript there is good.\n\n"
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


# ---------------------------------------------------------------- main entry

def find_clips(source, *, is_local, ytdlp, ffmpeg, workdir, count=5,
               min_len=15, max_len=60, use_ai=True, log=print, skip_text=None):
    """Return (title, clips). Each clip: start, end, score, title, reason.

    skip_text: optional fetch(start, end) -> video path. When given, extra
    moments are found and any with a lot of on-screen text are skipped.
    """
    if not skip_text:
        return _find(source, is_local, ytdlp, ffmpeg, workdir, count,
                     min_len, max_len, use_ai, log)
    import textcheck
    title, cands = _find(source, is_local, ytdlp, ffmpeg, workdir, count * 2 + 2,
                         min_len, max_len, use_ai, log)
    if not textcheck.tesseract():
        log(textcheck.INSTALL_HINT)
        return title, cands[:count]
    return title, textcheck.check(cands, skip_text, ffmpeg, workdir, count, log)


def _find(source, is_local, ytdlp, ffmpeg, workdir, count, min_len, max_len, use_ai, log):
    cues, curve, info = [], None, {}
    if is_local:
        title = os.path.splitext(os.path.basename(source))[0]
        duration = None
    else:
        log("Reading video details...")
        info = video_info(source, ytdlp)
        title = info.get("title") or "clip"
        duration = float(info.get("duration") or 0)
        curve = heatmap_curve(info)
        log("  'Most replayed' graph: " + ("found" if curve else "not available"))
        log("Getting transcript...")
        cues = download_transcript(source, ytdlp, workdir)
        log(f"  transcript: {len(cues)} lines" if cues else "  transcript: none")

    have_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    if use_ai and cues and have_key:
        log(f"Asking Claude to pick the best {count} moments...")
        try:
            picks = claude_clips(cues, curve, title, count, min_len, max_len)
            out = []
            for p in picks:
                s, e = float(p["start"]), float(p["end"])
                if duration:
                    s, e = max(0.0, min(s, duration - 1)), min(e, duration)
                if e - s < 3:
                    continue
                s, e = snap(s, e, cues, min_len, max_len)
                if duration:
                    e = min(e, duration)
                ai = (p["hook"] * 0.4 + p["standalone"] * 0.3 + p["payoff"] * 0.3) / 10
                score = 0.75 * ai + 0.25 * window_mean(curve, s, e) if curve else ai
                out.append({"start": s, "end": e, "score": round(100 * score),
                            "title": p["title"], "reason": p["reason"]})
            out = pick_top(out, count)
            if out:
                return title, out
            log("  Claude returned no usable clips; using the free method instead.")
        except Exception as err:  # network, auth, bad output: fall back to free mode
            log(f"  Claude scoring failed ({err}); using the free method instead.")
    elif use_ai and cues and not have_key:
        log("No ANTHROPIC_API_KEY set: using the free method (no AI scoring).")

    if curve:
        return title, signal_clips(curve, "Most replayed section", duration,
                                   count, min_len, max_len, cues)

    log("Measuring audio loudness...")
    media = source if is_local else download_audio(source, ytdlp, ffmpeg, workdir)
    loud = loudness_curve(media, ffmpeg) if media else None
    if not loud:
        raise RuntimeError("couldn't find any signal to pick clips from "
                           "(no 'Most replayed' graph, transcript scoring, or audio).")
    duration = duration or len(loud)
    return title, signal_clips(loud, "Loud, energetic section", duration,
                               count, min_len, max_len, cues)


def print_clips(clips, out=sys.stdout):
    for i, c in enumerate(clips, 1):
        name = f"  {c['title']}" if c.get("title") else ""
        print(f"  {i}. {fmt(c['start'])}-{fmt(c['end'])}  "
              f"({c['end'] - c['start']:.0f}s)  score {c['score']}{name}", file=out)
        print(f"     {c['reason']}", file=out)
