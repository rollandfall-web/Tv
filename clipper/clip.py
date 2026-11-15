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

Needs: Python 3.8+, ffmpeg, and yt-dlp (pip install yt-dlp).
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


def ytdlp_cmd():
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        die("yt-dlp is not installed. Run:  python -m pip install -U yt-dlp")


def run(cmd, quiet=True):
    result = subprocess.run(
        cmd,
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
        die("could not read that video. " + (msg[-1] if msg else ""))
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


def convert(raw, dest, kind, ffmpeg, gif_width, gif_fps):
    if kind == "mp4":
        shutil.move(raw, dest)
    elif kind == "vertical":
        # Crop the centre to 9:16 and scale to 1080x1920.
        run([ffmpeg, "-y", "-i", raw,
             "-vf", "crop='min(iw,ih*9/16)':ih,scale=1080:1920:flags=lanczos,setsar=1",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", dest])
    elif kind == "gif":
        vf = (f"fps={gif_fps},scale={gif_width}:-1:flags=lanczos,split[a][b];"
              f"[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5")
        run([ffmpeg, "-y", "-i", raw, "-filter_complex", vf, "-loop", "0", dest])
    elif kind == "mp3":
        run([ffmpeg, "-y", "-i", raw, "-vn", "-c:a", "libmp3lame", "-q:a", "2", dest])


def make_clips(source, clips, kind, outdir, name, quality, gif_width, gif_fps):
    ffmpeg = find_ffmpeg()
    os.makedirs(outdir, exist_ok=True)
    base = safe_name(name or video_title(source))
    ext = {"mp4": "mp4", "vertical": "mp4", "gif": "gif", "mp3": "mp3"}[kind]
    suffix = "_vertical" if kind == "vertical" else ""
    made = []
    with tempfile.TemporaryDirectory(prefix="clipmaker_") as work:
        for i, (s, e) in enumerate(clips, 1):
            print(f"\n[{i}/{len(clips)}] {fmt_time(s)} -> {fmt_time(e)} "
                  f"({e - s:.1f}s)")
            raw = fetch_section(source, s, e, quality, work, ffmpeg)
            dest = os.path.join(
                outdir, f"{base}_{label_time(s)}-{label_time(e)}{suffix}.{ext}")
            convert(raw, dest, kind, ffmpeg, gif_width, gif_fps)
            print(f"    saved {dest}")
            made.append(dest)
    return made


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
    print("Times can look like 83, 1:23, or 1:02:03.")
    print("For several clips, type them like  0:10-0:25, 3:00-3:12")
    while True:
        try:
            first = ask("Start time (or a list of clips)",
                        label_time(url_start) if url_start is not None else None)
            if "," in first or re.search(r"\d[-+]\d", first):
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
    return source, clips, kind


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
    a = p.parse_args()

    if not a.source:
        source, clips, kind = interactive()
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

    made = make_clips(source, clips, kind, a.out, a.name, a.quality,
                      a.gif_width, a.gif_fps)
    print(f"\nDone. {len(made)} clip(s) saved in: {os.path.abspath(a.out)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(130)
