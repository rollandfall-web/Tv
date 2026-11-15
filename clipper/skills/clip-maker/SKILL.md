---
name: clip-maker
description: Make short vertical clips (YouTube Shorts, TikTok, Reels) from a YouTube or Twitch link, or from a video file, using the Clip Maker tool on this computer. Use when the commander asks to clip a video, find its best moments, make Shorts, or add captions to a clip. Needs the Workbench (terminal).
---

# Clip Maker

Clip Maker is a command-line tool on this computer. It finds the best moments
in a video, cuts them, makes them vertical, and burns in animated captions.
Everything runs locally. It is free; it never needs an API key.

## Before you start

1. **Find the tool.** It is a folder containing `clipper/clip.py`. Use the
   first of these that exists:
   - a folder the commander told you about
   - `~/ClipMaker`
   - a `ClipMaker` folder on another drive: `ls -d /Volumes/*/ClipMaker`
   - `~/Downloads/Tv-claude-youtube-clip-maker-lyx2h0`

   If none exists, ask the commander where the Clip Maker folder is, and check
   that its drive is connected. Run every command below from inside that
   folder (`cd` into it first).
2. **Check permission.** Only clip videos the commander owns or has permission
   to use (for example, a streamer's clipping campaign). If the commander asks
   to clip someone else's video and permission is unclear, ask once before
   making clips. Never post clips anywhere unless the commander asks.
3. **Use `python3`** on macOS. On Windows use `python`.

## Find the best moments (no cutting)

```bash
python3 clipper/clip.py "LINK" --auto --list --json --count 5
```

The last line of the output starts with `@@PICKS@@` followed by JSON:
`{"title": ..., "clips": [{"start": 41.0, "end": 63.5, "score": 82, "title": ..., "reason": ...}]}`.
Times are seconds. Score is 0 to 100 and only compares moments within the same video.

Useful options:

| Option | Use |
|---|---|
| `--focus "car chases, funny reactions"` | What the commander wants. Pass their words. |
| `--count 3` | How many moments. |
| `--min 15 --max 45` | Clip length range in seconds (default 15 to 60). |
| `--skip-text` | Skip moments that already have subtitles or titles on screen (needs Tesseract). |
| `--browser chrome` | Only if an error says the video is age-restricted or asks to "confirm you're not a bot". Uses Chrome's YouTube sign-in. |

## Make the clips

Shorts with captions, best moments chosen automatically:

```bash
python3 clipper/clip.py "LINK" --auto --count 3 --vertical --captions --focus "WHAT THEY WANT"
```

Exact times the commander gives (start and end, or start and `+seconds`):

```bash
python3 clipper/clip.py "LINK" 1:23 1:45 --vertical --captions
python3 clipper/clip.py "LINK" --clips "0:10-0:25, 3:00+12" --vertical --captions
```

Other outputs: leave out `--vertical` for 16:9, `--gif` for a GIF, `--mp3` for audio.
`--caption-style clean` gives smaller, sentence-case captions instead of the bold
yellow-highlight style. Leave out `--captions` if the video already has subtitles.

Clips are saved in the `clips` folder inside the Clip Maker folder, so they stay
on the same drive as the tool (change with `-o FOLDER`). The output lists each file as `saved PATH` and ends with
`Done. N clip(s) saved in: FOLDER`. Report those paths to the commander.

Clips start and end on full sentences when the video has speech.

## How long it takes

Reading a video takes a few seconds. Each clip downloads only its own part, then
encodes for about as long as the clip lasts. A video without a "Most replayed"
graph (Twitch, some YouTube videos) needs its whole audio downloaded first,
which can take a few minutes for a long stream. Let commands run; don't restart them.

## When something fails

Read the line starting `How to fix:` in the output and follow it, or tell the
commander exactly what it says. Common cases:

| Message contains | Do this |
|---|---|
| `age-restricted` / `not a bot` | Run again with `--browser chrome`. |
| `CERTIFICATE_VERIFY_FAILED` | Ask the commander to run `python3 -m pip install -U certifi yt-dlp`. |
| `Requested format is not available` | Ask the commander to run `brew install deno` and `python3 -m pip install -U "yt-dlp[default]"`. |
| `can't draw captions` | Clips were still made, without captions. Ask the commander to run `brew install ffmpeg-full`. |
| `yt-dlp is not installed` / `ffmpeg was not found` | Ask the commander to finish the setup in `clipper/README.md`. |

Don't install software yourself unless the commander asks you to.

## Report back

Give the commander, for each clip: the file path, the time range, its length,
the score, and the reason. If you used `--focus`, say how each clip matches it.
If a moment was skipped (on-screen text, no speech), say so.
