"""Animated word-by-word captions, burned into the clip.

Word timings come from YouTube's captions (json3 format, which has a time
for every word in auto-generated captions). The words are written to an
ASS subtitle file and drawn onto the video by ffmpeg.

Styles:
  bold   - big UPPERCASE, 2-3 words at a time, current word pops in yellow
           (the "Hormozi" look most clipping campaigns ask for)
  clean  - sentence case, up to 6 words, current word highlighted in green
"""
import glob
import json
import os
import re
import subprocess

STYLES = ("bold", "clean")


# ---------------------------------------------------------------- word timings

def fetch_words(source, ytdlp, workdir):
    """Download YouTube captions and return [(start, end, word)] in seconds."""
    base = os.path.join(workdir, "capwords")
    subprocess.run(
        ytdlp + ["--no-playlist", "--skip-download", "--write-subs", "--write-auto-subs",
                 "--sub-langs", "en.*,en,-live_chat", "--sub-format", "json3",
                 "-o", base, source],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    files = sorted(glob.glob(base + "*.json3"), key=len)
    best = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                words = words_from_json3(fh.read())
        except (OSError, ValueError):
            continue
        if len(words) > len(best):
            best = words
    return best


def words_from_json3(text):
    """Per-word timings from YouTube json3 captions.

    Auto captions give each word an offset (tOffsetMs). Hand-made captions
    only time whole lines, so their words are spread evenly across the line.
    """
    words = []
    for ev in json.loads(text).get("events", []):
        segs = [s for s in ev.get("segs") or [] if s.get("utf8", "").strip()]
        if not segs or "tStartMs" not in ev:
            continue
        start = ev["tStartMs"] / 1000
        end = start + ev.get("dDurationMs", 0) / 1000
        timed = any("tOffsetMs" in s for s in segs)
        if timed:
            times = [start + s.get("tOffsetMs", 0) / 1000 for s in segs]
            for i, seg in enumerate(segs):
                w_end = times[i + 1] if i + 1 < len(segs) else end
                for w in seg["utf8"].split():
                    words.append([times[i], w_end, w])
        else:
            parts = " ".join(s["utf8"] for s in segs).split()
            step = (end - start) / max(1, len(parts))
            for i, w in enumerate(parts):
                words.append([start + i * step, start + (i + 1) * step, w])
    words.sort(key=lambda w: w[0])
    # Each word ends when the next one starts (no overlaps), and no word
    # stays on screen for more than 1.5 s on its own.
    for i, w in enumerate(words):
        nxt = words[i + 1][0] if i + 1 < len(words) else w[1]
        w[1] = max(w[0] + 0.05, min(w[1], nxt, w[0] + 1.5))
    return [tuple(w) for w in words]


def words_in(words, start, end):
    """Words inside [start, end], shifted so the clip starts at 0."""
    out = []
    for s, e, w in words:
        if e <= start or s >= end:
            continue
        out.append((max(0.0, s - start), min(end, e) - start, w))
    return out


# ---------------------------------------------------------------- ASS file

def ass_time(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def clean_word(w):
    return w.replace("\\", "").replace("{", "").replace("}", "")


def chunk_words(words, max_words):
    """Group words into short lines; break on pauses and sentence ends."""
    chunks, cur = [], []
    for i, word in enumerate(words):
        if cur and (len(cur) >= max_words or word[0] - cur[-1][1] > 0.6):
            chunks.append(cur)
            cur = []
        cur.append(word)
        if re.search(r"[.!?]$", word[2]):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(words, width, height, style="bold"):
    """ASS subtitle text for words already shifted to clip time."""
    vertical = height > width
    if style == "bold":
        size = int(min(width * (0.095 if vertical else 0.06), height * 0.09))
        max_words, upper = (3 if vertical else 4), True
        active = r"{\c&H00FFFF&\fscx112\fscy112}"   # yellow, a bit bigger
        outline, shadow = max(4, size // 12), 2
    else:
        size = int(min(width * (0.06 if vertical else 0.045), height * 0.07))
        max_words, upper = 6, False
        active = r"{\c&H55FF55&}"                     # green
        outline, shadow = max(3, size // 16), 1
    margin_v = int(height * (0.28 if vertical else 0.08))
    margin_h = int(width * 0.06)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    reset = r"{\r}"
    for chunk in chunk_words(words, max_words):
        texts = [clean_word(w[2].upper() if upper else w[2]) for w in chunk]
        for i, (s, _, _) in enumerate(chunk):
            # Show this line from this word's start until the next word starts
            # (or the line ends), with the current word highlighted.
            e = chunk[i + 1][0] if i + 1 < len(chunk) else chunk[-1][1]
            if e - s < 0.02:
                continue
            parts = [f"{active}{t}{reset}" if j == i else t for j, t in enumerate(texts)]
            lines.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Cap,,0,0,0,,{' '.join(parts)}")
    return header + "\n".join(lines) + "\n"


def write_ass(path, words, width, height, style="bold"):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_ass(words, width, height, style))
    return path
