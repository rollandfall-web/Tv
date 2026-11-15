#!/usr/bin/env python3
"""YouTube clip maker.

Cuts one or more clips out of a YouTube video (or a video file on your
computer) and saves them as MP4, a vertical 9:16 MP4 for Shorts/Reels/TikTok,
a GIF, or an MP3.

Only the part of the video you ask for is downloaded, so clips from long
videos are fast.

Usage:
  python clip.py                                    ask questions step by step
  python clip.py URL 1:23 1:45                      one clip, 1:23 to 1:45
  python clip.py URL 1:23 +20                       20 seconds from 1:23
  python clip.py URL --clips "0:10-0:25,3:00-3:12"  several clips at once
  python clip.py URL 1:23 1:45 --vertical           9:16 for Shorts / Reels
  python clip.py URL 1:23 1:45 --gif                animated GIF
  python clip.py URL 1:23 1:45 --mp3                audio only
  python clip.py my-video.mp4 0:05 0:15             clip a file you already have
  python clip.py URL --auto                         find the best moments for you
  python clip.py URL --auto --count 3 --vertical    top 3, ready for Shorts
  python clip.py URL --auto --list                  only show the picks, cut nothing
  python clip.py URL --auto --vertical --captions   Shorts with animated captions

Needs: Python 3.8+, ffmpeg, and yt-dlp (pip install yt-dlp).
For AI scoring in --auto mode: pip install anthropic, and set ANTHROPIC_API_KEY.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlparse

FORMATS = ("mp4", "vertical", "gif", "mp3")


# ---------------------------------------------------------------- helpers

def die(msg):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_time(text):
    """Turn '83', '1:23', '1:02:03', '1m23s' or '83.5' into seconds."""
    text = str(text).strip().lower()
    if not text:
        raise ValueError("empty time")
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", text)
    if m and any(m.groups()):
        h, mnt, s = m.groups()
        return int(h or 0) * 3600 + int(mnt or 0) * 60 + float(s or 0)
    parts = text.split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"bad time: {text}")
    total = 0.0
    for p in parts:
        if not re.fullmatch(r"\d+(?:\.\d+)?", p):
            raise ValueError(f"bad time: {text}")
        total = total * 60 + float(p)
    return total


def fmt_time(seconds):
    """Seconds -> 'H:MM:SS.mmm' (what ffmpeg and yt-dlp accept)."""
    seconds = max(0.0, seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:06.3f}"


def label_time(seconds):
    """Seconds -> filename-friendly '1m23s'."""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return (f"{h}h" if h else "") + f"{m}m{s:02d}s"


def parse_range(start, end):
    """Parse a start and an end ('1:45') or length ('+20'). Returns (s, e)."""
    s = parse_time(start)
    end = str(end).strip()
    e = s + parse_time(end[1:]) if end.startswith("+") else parse_time(end)
    if e <= s:
        raise ValueError(f"end ({end}) must be after start ({start})")
    return s, e


def parse_clip_list(text):
    """'0:10-0:25, 3:00+12' -> [(10, 25), (180, 192)]."""
    clips = []
    for item in filter(None, (x.strip() for x in text.split(","))):
        if "+" in item:
            a, b = item.split("+", 1)
            clips.append(parse_range(a, "+" + b))
        elif "-" in item:
            a, b = item.split("-", 1)
            clips.append(parse_range(a, b))
        else:
            raise ValueError(f"'{item}' should look like 1:00-1:20 or 1:00+20")
    if not clips:
        raise ValueError("no clips given")
    return clips


def start_from_url(url):
    """Read the ?t=83 / &t=1m23s start time that YouTube 'share' links have."""
    try:
        q = parse_qs(urlparse(url).query)
        if "t" in q:
            return parse_time(q["t"][0])
    except ValueError:
        pass
    return None


def is_local_file(source):
    return os.path.isfile(source)


def safe_name(text, limit=60):
    text = re.sub(r"[^\w\- ]+", "", text, flags=re.UNICODE).strip()
    return re.sub(r"\s+", "_", text)[:limit] or "clip"


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("ffmpeg", "ffmpeg.exe"):
        for cand in (os.path.join(here, name), os.path.join(here, "bin", name)):
            if os.path.isfile(cand):
                return cand
    die("ffmpeg was not found. Install it (see README) and try again.")


# Set by --browser: borrow that browser's YouTube sign-in (for age-restricted
# videos, or when YouTube asks to "confirm you're not a bot").
BROWSER = None


def ytdlp_cmd():
    extra = ["--cookies-from-browser", BROWSER] if BROWSER else []
    if shutil.which("yt-dlp"):
        return ["yt-dlp"] + extra
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"] + extra
    except ImportError:
        die("yt-dlp is not installed. Run:  python3 -m pip install -U yt-dlp")


def explain(msg):
    """Add a plain-English fix to common yt-dlp errors."""
    low = msg.lower()
    if "certificate_verify_failed" in low or "certificate verify failed" in low:
        tip = ("Python can't check website certificates yet (common on Mac). Run:\n"
               "  open \"/Applications/Python 3.14/Install Certificates.command\"\n"
               "  python3 -m pip install -U certifi yt-dlp\n"
               "(Change 3.14 to your Python version; see the folder in Applications.)")
    elif "confirm your age" in low or "age-restricted" in low or "inappropriate for some users" in low:
        tip = ("This video is age-restricted. Sign in to YouTube in Chrome, then add "
               "--browser chrome to the command (or --browser safari / firefox).")
    elif "not a bot" in low or "sign in to confirm" in low:
        tip = ("YouTube wants a signed-in user. Sign in to YouTube in Chrome, then add "
               "--browser chrome to the command.")
    elif "cookies" in low and BROWSER:
        tip = (f"Couldn't read {BROWSER}'s sign-in. Close {BROWSER} completely and try again. "
               "For Safari, give Terminal Full Disk Access in System Settings > "
               "Privacy & Security, or use --browser chrome.")
    elif "video unavailable" in low or "private video" in low:
        tip = "The video is private, deleted, or blocked in your country. Check the link."
    elif "403" in low or "unable to extract" in low or "requested format" in low:
        tip = "YouTube changed something. Update yt-dlp:  python3 -m pip install -U yt-dlp"
    else:
        tip = ("Check the link, then update yt-dlp:  python3 -m pip install -U yt-dlp")
    return f"{msg}\n\nHow to fix: {tip}"


def run(cmd, quiet=True, cwd=None):
    result = subprocess.run(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE if quiet else None,
        stderr=subprocess.PIPE if quiet else None,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()[-8:] if quiet else []
        die("command failed:\n  " + " ".join(cmd[:3]) + " ...\n" + "\n".join(detail))
    return result


# ---------------------------------------------------------------- work

def video_title(source):
    if is_local_file(source):
        return os.path.splitext(os.path.basename(source))[0]
    r = subprocess.run(
        ytdlp_cmd() + ["--no-playlist", "--skip-download", "--print", "title", source],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if r.returncode != 0:
        msg = (r.stderr or "").strip().splitlines()
        die(explain("could not read that video. " + (msg[-1] if msg else "")))
    return r.stdout.strip().splitlines()[0] if r.stdout.strip() else "clip"


def local_duration(path, ffmpeg):
    """Length of a local video in seconds, or None if it can't be read."""
    r = subprocess.run([ffmpeg, "-i", path], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if not m:
        return None
    h, mnt, sec = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(sec)


def fetch_section(source, start, end, quality, workdir, ffmpeg):
    """Get just [start, end] of the video as an MP4 in workdir."""
    out = os.path.join(workdir, f"raw_{int(start * 1000)}.mp4")
    if is_local_file(source):
        length = local_duration(source, ffmpeg)
        if length is not None and start >= length:
            die(f"start time {fmt_time(start)} is past the end of the video "
                f"({fmt_time(length)}).")
        run([ffmpeg, "-y", "-ss", fmt_time(start), "-to", fmt_time(end),
             "-i", source, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
        return out

    fmt = (f"bv*[height<={quality}][ext=mp4]+ba[ext=m4a]/"
           f"bv*[height<={quality}]+ba/b[height<={quality}]/b")
    cmd = ytdlp_cmd() + [
        "--no-playlist", "--quiet", "--no-warnings", "--progress",
        "-f", fmt,
        "--download-sections", f"*{fmt_time(start)}-{fmt_time(end)}",
        "--force-keyframes-at-cuts",
        "--merge-output-format", "mp4",
        "--ffmpeg-location", ffmpeg,
        "-o", os.path.join(workdir, f"dl_{int(start * 1000)}.%(ext)s"),
        source,
    ]
    run(cmd, quiet=False)
    files = [f for f in os.listdir(workdir) if f.startswith(f"dl_{int(start * 1000)}.")]
    if not files:
        die("the download finished but no file was saved.")
    os.replace(os.path.join(workdir, files[0]), out)
    return out


def video_size(path, ffmpeg):
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", path], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True)
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", r.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else (1920, 1080)


def convert(raw, dest, kind, ffmpeg, gif_width, gif_fps, words=None, style="bold"):
    """Turn the downloaded section into the final file.

    words: caption words in clip time, burned in for mp4/vertical output.
    """
    if kind in ("mp4", "vertical"):
        filters = []
        if kind == "vertical":
            # Crop the centre to 9:16 and scale to 1080x1920.
            filters.append("crop='min(iw,ih*9/16)':ih,scale=1080:1920:flags=lanczos,setsar=1")
            size = (1080, 1920)
        else:
            size = video_size(raw, ffmpeg)
        if words:
            import captions
            ass = os.path.join(os.path.dirname(os.path.abspath(raw)), "captions.ass")
            captions.write_ass(ass, words, size[0], size[1], style)
            # Bare file name + cwd avoids ffmpeg's path escaping rules (Windows "C:").
            filters.append("subtitles=captions.ass")
        if not filters:
            shutil.move(raw, dest)
            return
        run([ffmpeg, "-y", "-i", os.path.abspath(raw), "-vf", ",".join(filters),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
             os.path.abspath(dest)], cwd=os.path.dirname(os.path.abspath(raw)))
    elif kind == "gif":
        vf = (f"fps={gif_fps},scale={gif_width}:-1:flags=lanczos,split[a][b];"
              f"[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5")
        run([ffmpeg, "-y", "-i", raw, "-filter_complex", vf, "-loop", "0", dest])
    elif kind == "mp3":
        run([ffmpeg, "-y", "-i", raw, "-vn", "-c:a", "libmp3lame", "-q:a", "2", dest])


def make_clips(source, clips, kind, outdir, name, quality, gif_width, gif_fps,
               add_captions=False, caption_style="bold"):
    ffmpeg = find_ffmpeg()
    os.makedirs(outdir, exist_ok=True)
    base = safe_name(name or video_title(source))
    ext = {"mp4": "mp4", "vertical": "mp4", "gif": "gif", "mp3": "mp3"}[kind]
    suffix = "_vertical" if kind == "vertical" else ""
    made = []
    with tempfile.TemporaryDirectory(prefix="clipmaker_") as work:
        words = []
        if add_captions and kind in ("mp4", "vertical"):
            if is_local_file(source):
                print("Captions need YouTube captions; local files aren't supported yet. "
                      "Making clips without captions.")
            else:
                import captions
                print("Getting word timings for captions...")
                words = captions.fetch_words(source, ytdlp_cmd(), work)
                if not words:
                    print("  This video has no English captions; making clips without them.")
        elif add_captions:
            print("Captions only work for MP4 and vertical clips; skipping them.")
        for i, (s, e) in enumerate(clips, 1):
            print(f"\n[{i}/{len(clips)}] {fmt_time(s)} -> {fmt_time(e)} "
                  f"({e - s:.1f}s)")
            raw = fetch_section(source, s, e, quality, work, ffmpeg)
            dest = os.path.join(
                outdir, f"{base}_{label_time(s)}-{label_time(e)}{suffix}.{ext}")
            clip_words = None
            if words:
                import captions
                clip_words = captions.words_in(words, s, e)
                if not clip_words:
                    print("    (no speech in this clip, so no captions)")
            convert(raw, dest, kind, ffmpeg, gif_width, gif_fps, clip_words, caption_style)
            print(f"    saved {dest}")
            made.append(dest)
    return made


def auto_select(source, count, min_len, max_len, use_ai):
    """Run the highlight finder. Returns (title, clips list from finder)."""
    import finder

    ffmpeg = find_ffmpeg()
    local = is_local_file(source)
    if min_len >= max_len:
        die("--min must be shorter than --max.")
    with tempfile.TemporaryDirectory(prefix="clipfinder_") as work:
        try:
            title, picks = finder.find_clips(
                source, is_local=local, ytdlp=None if local else ytdlp_cmd(),
                ffmpeg=ffmpeg, workdir=work, count=count,
                min_len=min_len, max_len=max_len, use_ai=use_ai)
        except RuntimeError as err:
            die(explain(str(err)))
    if not picks:
        die("no clips found.")
    print(f"\nBest moments in \"{title}\":")
    finder.print_clips(picks)
    return title, picks


def choose_picks(picks):
    """Let the user keep some of the found clips: '1,3' or 'all'."""
    answer = ask("Which clips to make? (e.g. 1,3 or all)", "all").lower()
    if answer in ("all", "a", "*"):
        return picks
    keep = []
    for part in re.split(r"[ ,]+", answer):
        if part.isdigit() and 1 <= int(part) <= len(picks):
            keep.append(picks[int(part) - 1])
    return keep or picks


# ---------------------------------------------------------------- input

def ask(prompt, default=None):
    tip = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{tip}: ").strip()
    except EOFError:
        answer = ""
    return answer or (default or "")


def interactive():
    print("YouTube clip maker\n------------------")
    source = ask("Paste the YouTube link (or a video file path)")
    if not source:
        die("no link given.")
    url_start = start_from_url(source)
    print("Type  auto  to let the tool find the best moments for you.")
    print("Or type times like 83, 1:23, or 1:02:03.")
    print("For several clips, type them like  0:10-0:25, 3:00-3:12")
    title = None
    while True:
        try:
            first = ask("Start time (or a list of clips, or auto)",
                        label_time(url_start) if url_start is not None else "auto")
            if first.lower() == "auto":
                count = int(ask("How many clips to find", "5") or 5)
                title, picks = auto_select(source, count, 15, 60, True)
                clips = [(c["start"], c["end"]) for c in choose_picks(picks)]
            elif "," in first or re.search(r"\d[-+]\d", first):
                clips = parse_clip_list(first)
            else:
                end = ask("End time, or +seconds for a length", "+30")
                clips = [parse_range(first, end)]
            break
        except ValueError as err:
            print(f"  {err}. Try again.")
    print("Save as: 1) MP4   2) Vertical MP4 for Shorts/Reels/TikTok   3) GIF   4) MP3")
    choice = ask("Pick 1-4", "1")
    kind = {"1": "mp4", "2": "vertical", "3": "gif", "4": "mp3"}.get(choice, "mp4")
    caps = False
    if kind in ("mp4", "vertical") and not is_local_file(source):
        caps = ask("Add animated captions? (y/n)", "y").lower().startswith("y")
    return source, clips, kind, title, caps


def main():
    p = argparse.ArgumentParser(
        description="Cut clips from a YouTube video or a local video file.",
        epilog="Example: python clip.py https://youtu.be/VIDEO 1:23 +20 --vertical")
    p.add_argument("source", nargs="?", help="YouTube link or path to a video file")
    p.add_argument("start", nargs="?", help="start time, e.g. 1:23")
    p.add_argument("end", nargs="?", help="end time (1:45) or length (+20)")
    p.add_argument("--clips", help='several clips: "0:10-0:25,3:00+12"')
    group = p.add_mutually_exclusive_group()
    group.add_argument("--vertical", action="store_true", help="9:16 for Shorts/Reels/TikTok")
    group.add_argument("--gif", action="store_true", help="save as an animated GIF")
    group.add_argument("--mp3", action="store_true", help="save audio only")
    p.add_argument("-o", "--out", default="clips", help="folder to save to (default: clips)")
    p.add_argument("-n", "--name", help="file name to use instead of the video title")
    p.add_argument("-q", "--quality", type=int, default=1080,
                   help="max video height to download (default: 1080)")
    p.add_argument("--gif-width", type=int, default=480, help="GIF width (default: 480)")
    p.add_argument("--gif-fps", type=int, default=12, help="GIF frames/sec (default: 12)")
    p.add_argument("--browser", choices=("chrome", "safari", "firefox", "edge", "brave"),
                   help="use this browser's YouTube sign-in (for age-restricted videos)")
    auto = p.add_argument_group("automatic clip finding")
    auto.add_argument("--auto", action="store_true",
                      help="find the best moments automatically")
    auto.add_argument("--count", type=int, default=5, help="how many clips to find (default: 5)")
    auto.add_argument("--min", type=float, default=15, help="shortest clip in seconds (default: 15)")
    auto.add_argument("--max", type=float, default=60, help="longest clip in seconds (default: 60)")
    auto.add_argument("--no-ai", action="store_true",
                      help="don't use Claude, even if an API key is set")
    auto.add_argument("--list", action="store_true",
                      help="only list the clips found, don't cut them")
    cap = p.add_argument_group("captions")
    cap.add_argument("--captions", action="store_true",
                     help="burn in animated word-by-word captions")
    cap.add_argument("--caption-style", choices=("bold", "clean"), default="bold",
                     help="bold = big yellow-highlight words (default); clean = smaller, sentence case")
    a = p.parse_args()
    global BROWSER
    BROWSER = a.browser

    title = None
    if not a.source:
        source, clips, kind, title, a.captions = interactive()
    elif a.auto:
        source = a.source
        kind = "vertical" if a.vertical else "gif" if a.gif else "mp3" if a.mp3 else "mp4"
        title, picks = auto_select(source, max(1, a.count), a.min, a.max, not a.no_ai)
        if a.list:
            return
        clips = [(c["start"], c["end"]) for c in picks]
    else:
        source = a.source
        kind = "vertical" if a.vertical else "gif" if a.gif else "mp3" if a.mp3 else "mp4"
        try:
            if a.clips:
                clips = parse_clip_list(a.clips)
            else:
                start = a.start
                if start is None:
                    t = start_from_url(source)
                    if t is None:
                        p.error("give a start time, or use --clips")
                    start = str(t)
                clips = [parse_range(start, a.end or "+30")]
        except ValueError as err:
            p.error(str(err))

    made = make_clips(source, clips, kind, a.out, a.name or title, a.quality,
                      a.gif_width, a.gif_fps, a.captions, a.caption_style)
    print(f"\nDone. {len(made)} clip(s) saved in: {os.path.abspath(a.out)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(130)
