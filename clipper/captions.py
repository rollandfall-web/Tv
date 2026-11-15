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
        ytdlp + ["--no-playlist", "--skip-download", "--ignore-no-formats-error", "--write-subs", "--write-auto-subs",
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


PRESETS = {
    # size = % of video height, outline = % of font size, position = % from bottom
    "bold": dict(font="Arial", bold=True, size=5.0, uppercase=True, words_per_line=3,
                 color="#FFFFFF", highlight="#FFE000", highlight_mode="word", pop=True,
                 outline=9, outline_color="#000000", shadow=True, text_opacity=100,
                 box=False, box_color="#000000", box_opacity=60, position=28),
    "clean": dict(font="Arial", bold=True, size=3.4, uppercase=False, words_per_line=6,
                  color="#FFFFFF", highlight="#55FF55", highlight_mode="word", pop=False,
                  outline=6, outline_color="#000000", shadow=True, text_opacity=100,
                  box=False, box_color="#000000", box_opacity=60, position=28),
}


def preset(name, vertical=True):
    """A full style dict for a preset, adjusted for landscape video."""
    st = dict(PRESETS.get(name, PRESETS["bold"]))
    if not vertical:
        st["size"] = round(st["size"] * 1.9, 1)
        st["words_per_line"] = st["words_per_line"] + 1
        st["position"] = 8
    return st


def ass_color(hex_rgb, opacity=100):
    """'#RRGGBB' + opacity % -> ASS '&HAABBGGRR' (ASS alpha 00 = solid)."""
    h = (hex_rgb or "#FFFFFF").lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        h = "FFFFFF"
    alpha = round(255 * (1 - max(0, min(100, opacity)) / 100))
    return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def norm_words(words):
    """Accept (s, e, w) or (s, e, w, emph) tuples or dicts; return dicts."""
    out = []
    for w in words:
        if isinstance(w, dict):
            out.append({"s": float(w["s"]), "e": float(w["e"]), "w": str(w["w"]),
                        "emph": bool(w.get("emph"))})
        else:
            out.append({"s": float(w[0]), "e": float(w[1]), "w": str(w[2]),
                        "emph": bool(w[3]) if len(w) > 3 else False})
    return [w for w in out if w["w"].strip()]


def build_ass(words, width, height, style="bold", lines=None):
    """ASS subtitle text for words already shifted to clip time.

    style: a preset name ("bold"/"clean") or a full style dict (see PRESETS).
    lines: optional list of word-index lists giving the caption lines; by
           default words are grouped automatically (words_per_line).
    """
    if isinstance(style, str):
        style = preset(style, vertical=height > width)
    st = dict(PRESETS["bold"], **style)
    words = norm_words(words)

    size = max(8, round(height * float(st["size"]) / 100))
    outline = round(size * float(st["outline"]) / 100, 1)
    shadow = max(1, size // 30) if st["shadow"] else 0
    margin_v = round(height * float(st["position"]) / 100)
    margin_h = round(width * 0.06)
    op = float(st["text_opacity"])
    font = re.sub(r"[,\n]", "", str(st["font"])) or "Arial"
    bold = -1 if st["bold"] else 0
    fill = ass_color(st["color"], op)
    edge = ass_color(st["outline_color"], op)
    shade = ass_color("#000000", op * 0.5)
    hl = "&H" + ass_color(st["highlight"])[4:] + "&"   # colour only; \\c keeps alpha
    box = ass_color(st["box_color"], float(st["box_opacity"]))
    box_pad = max(4, size // 5)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},{fill},{fill},{edge},{shade},{bold},0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_h},{margin_h},{margin_v},1
Style: Box,{font},{size},&HFF000000,&HFF000000,{box},&HFF000000,{bold},0,0,0,100,100,0,0,3,{box_pad},0,2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    if lines is None:
        groups = chunk_words([(w["s"], w["e"], w["w"]) for w in words],
                             max(1, int(st["words_per_line"])))
        lines, i = [], 0
        for g in groups:
            lines.append(list(range(i, i + len(g))))
            i += len(g)

    def text_of(w):
        t = clean_word(w["w"])
        return t.upper() if st["uppercase"] else t

    pop = r"\fscx112\fscy112" if st["pop"] else ""
    events = []
    for idx in lines:
        chunk = [words[i] for i in idx if 0 <= i < len(words)]
        if not chunk:
            continue
        texts = [text_of(w) for w in chunk]
        start, end = chunk[0]["s"], max(w["e"] for w in chunk)
        if end - start < 0.02:
            continue
        if st["box"]:
            events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Box,,0,0,0,,"
                          + " ".join(texts))
        if st["highlight_mode"] == "word":
            spans = []
            for i, w in enumerate(chunk):
                e = chunk[i + 1]["s"] if i + 1 < len(chunk) else end
                if e - w["s"] >= 0.02:
                    spans.append((w["s"], e, i))
        else:
            spans = [(start, end, None)]
        for s, e, active in spans:
            parts = []
            for j, (w, t) in enumerate(zip(chunk, texts)):
                if j == active:
                    parts.append(f"{{\\c{hl}{pop}}}{t}{{\\r}}")
                elif w["emph"]:
                    parts.append(f"{{\\c{hl}}}{t}{{\\r}}")
                else:
                    parts.append(t)
            events.append(f"Dialogue: 1,{ass_time(s)},{ass_time(e)},Cap,,0,0,0,,{' '.join(parts)}")
    return header + "\n".join(events) + "\n"


def write_ass(path, words, width, height, style="bold", lines=None):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_ass(words, width, height, style, lines))
    return path


# ---------------------------------------------------------------- speech to text

_MODEL = {}
WHISPER_SIZE = os.environ.get("CLIPMAKER_WHISPER", "small")   # tiny/base/small/medium


def whisper_backend():
    """Name of the installed speech-to-text library, or None."""
    for name in ("faster_whisper", "mlx_whisper", "whisper"):
        try:
            __import__(name)
            return name
        except Exception:  # not installed, or broken install
            continue
    return None


INSTALL_HINT = ("Install speech-to-text once:  python3 -m pip install -U faster-whisper\n"
                "(on a Mac, if that fails:  python3 -m pip install -U mlx-whisper)")


def transcribe(media, ffmpeg, workdir, log=print, progress=None):
    """Transcribe a video/audio file on this computer.

    Returns [(start, end, word)] in seconds from the start of the file. The
    first run downloads the speech model (small: about 500 MB).
    """
    backend = whisper_backend()
    if not backend:
        raise RuntimeError("Speech-to-text isn't installed. " + INSTALL_HINT)
    wav = os.path.join(workdir, "speech.wav")
    r = subprocess.run([ffmpeg, "-y", "-i", media, "-vn", "-ac", "1", "-ar", "16000", wav],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0 or not os.path.isfile(wav):
        raise RuntimeError("Couldn't read the audio for transcription.")
    if backend not in _MODEL:
        log(f"Loading the speech model ({WHISPER_SIZE}). The first time, this downloads it "
            "and can take a few minutes...")
    log("Transcribing speech...")
    try:
        return _transcribe(backend, wav, progress or (lambda f: None))
    except Exception as err:  # model download blocked, out of memory, broken install
        raise RuntimeError(
            f"Speech-to-text didn't work ({err}). The first time, it needs internet to "
            "download the speech model; if that's fine, try updating it:  "
            "python3 -m pip install -U faster-whisper") from err


def _transcribe(backend, wav, prog):
    words = []
    if backend == "faster_whisper":
        from faster_whisper import WhisperModel
        if backend not in _MODEL:
            _MODEL[backend] = WhisperModel(WHISPER_SIZE, device="auto", compute_type="int8")
        segments, info = _MODEL[backend].transcribe(wav, word_timestamps=True, vad_filter=True)
        total = float(getattr(info, "duration", 0) or 0)
        for seg in segments:
            if total:
                prog(min(0.99, seg.end / total))
            for w in seg.words or []:
                words.append((float(w.start), float(w.end), w.word.strip()))
    else:
        if backend == "mlx_whisper":
            import mlx_whisper
            _MODEL[backend] = True
            result = mlx_whisper.transcribe(
                wav, path_or_hf_repo=f"mlx-community/whisper-{WHISPER_SIZE}-mlx",
                word_timestamps=True)
        else:
            import whisper
            if backend not in _MODEL:
                _MODEL[backend] = whisper.load_model(WHISPER_SIZE)
            result = _MODEL[backend].transcribe(wav, word_timestamps=True)
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                words.append((float(w["start"]), float(w["end"]), str(w["word"]).strip()))
    return [w for w in words if w[2] and w[1] > w[0]]


# ---------------------------------------------------------------- sentence edges

def sentence_snap(start, end, words, min_len=3.0, max_len=None, reach=10.0):
    """Move a clip's start and end so speech isn't cut off mid-sentence.

    words: [(start, end, word)] (or dicts with s/e/w). A sentence ends at a
    word ending in . ! or ?, or at a pause of 0.7 s or more (YouTube's
    auto-captions have no punctuation, so pauses matter). The end may move up
    to `reach` seconds either way, and the clip may run a little past
    max_len rather than stop mid-sentence. Returns (start, end, changed).
    """
    ws = [(w["s"], w["e"], w["w"]) if isinstance(w, dict) else (w[0], w[1], w[2])
          for w in words]
    ws = sorted(w for w in ws if w[1] > w[0])
    if not ws:
        return start, end, False
    ends, starts = [], [ws[0][0]]
    for i, (s, e, t) in enumerate(ws):
        nxt = ws[i + 1][0] if i + 1 < len(ws) else None
        if nxt is None or re.search(r"[.!?…]['\")\]]*$", t) or nxt - e >= 0.7:
            ends.append(e)
            if nxt is not None:
                starts.append(nxt)
    limit = (max_len + 8) if max_len else None

    # Start: the nearest sentence start at or a little before the chosen start.
    new_s = start
    cand = [b for b in starts if start - reach * 0.6 <= b <= start + 1.5]
    if cand:
        new_s = min(cand, key=lambda b: (abs(b - start) if b <= start else abs(b - start) * 2))
    else:
        for s, e, _ in ws:                     # never start inside a word
            if s < start < e:
                new_s = s
                break
    new_s = max(0.0, new_s - 0.15)

    # End: the sentence end closest to the chosen end (a little later is fine).
    new_e = end
    cand = [b for b in ends if b - new_s >= min_len and abs(b - end) <= reach
            and (limit is None or b - new_s <= limit)]
    if cand:
        new_e = min(cand, key=lambda b: abs(b - end) * (0.8 if b >= end else 1.0))
    else:
        for s, e, _ in ws:                     # never stop inside a word
            if s < end < e:
                new_e = e
                break
    new_e = new_e + 0.35                       # let the last word ring out
    changed = abs(new_s - start) > 0.2 or abs(new_e - end) > 0.2
    return round(new_s, 2), round(new_e, 2), changed
