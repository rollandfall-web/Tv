# YouTube Clip Maker

Cuts clips out of a YouTube video and saves them as MP4, as a vertical video for Shorts, Reels or TikTok, as a GIF, or as an MP3. It downloads only the part you ask for, so clips from long videos are fast. It also works on video files already on your computer.

> Only clip videos you own or have permission to use. Downloading other people's videos may break YouTube's terms of service.

## Set up (once)

1. Install [Python 3](https://www.python.org/downloads/). On Windows, tick **Add Python to PATH** during install.
2. Install ffmpeg:
   - **Windows:** `winget install ffmpeg`
   - **Mac:** `brew install ffmpeg`
   - **Linux:** `sudo apt install ffmpeg`
3. Install yt-dlp:
   ```bash
   python -m pip install -U yt-dlp
   ```

If clips stop downloading, YouTube has changed something. Run the step 3 command again to update yt-dlp.

## Let it find the best moments (like Opus Clip)

```bash
python clipper/clip.py "LINK" --auto
```

It finds the 5 best moments, shows them with a score and a reason, and cuts them. Useful extras:

| What you want | Add |
|---|---|
| Just see the picks, don't cut | `--list` |
| A different number of clips | `--count 3` |
| Shorter or longer clips (seconds) | `--min 20 --max 45` |
| Ready for Shorts / Reels / TikTok | `--vertical` |

In the step-by-step mode, type `auto` when it asks for a start time. You can then choose which of the found clips to keep.

### How it picks

1. **What viewers rewatch.** YouTube's "Most replayed" graph shows where people jump back to. Clips are built around its peaks.
2. **What's said (optional, smarter).** With an Anthropic API key, Claude reads the transcript and scores each moment on:
   - **Hook:** do the first few seconds grab attention?
   - **Makes sense alone:** does it work without the rest of the video?
   - **Payoff:** does it end on a punchline, reveal or useful tip?

   It also gives each clip a title. This costs a few cents per video.
3. **How loud it is.** If a video has no "Most replayed" graph, or it is a file on your computer, it looks for loud, energetic parts such as laughter, applause and raised voices.

Cut points snap to the edges of caption lines, so clips don't start or end mid-word.

### Turn on AI scoring (optional)

1. Get an API key at [console.anthropic.com](https://console.anthropic.com).
2. Install the library: `python -m pip install -U anthropic`
3. Set the key before running the script:
   - **Windows (PowerShell):** `$env:ANTHROPIC_API_KEY = "your-key"`
   - **Mac / Linux:** `export ANTHROPIC_API_KEY="your-key"`

Without a key, it uses the free method (steps 1 and 3). To skip the AI even with a key set, add `--no-ai`.

## Animated captions

Add `--captions` to burn in word-by-word captions, the style most Shorts and clipping campaigns use:

```bash
python clipper/clip.py "LINK" --auto --vertical --captions
```

- `--caption-style bold` (default): big uppercase words, 2–3 at a time, with the spoken word popping in yellow.
- `--caption-style clean`: smaller, normal case, with the spoken word in green.

Captions use the video's YouTube captions, so they work for any video with English captions, including auto-generated ones. They don't work on files from your computer yet.

## Make a clip by choosing the times yourself

The easiest way: run the script with nothing after it, and it asks you questions.

```bash
python clipper/clip.py
```

Or type everything at once:

| What you want | Command |
|---|---|
| 1:23 to 1:45 | `python clipper/clip.py "LINK" 1:23 1:45` |
| 20 seconds starting at 1:23 | `python clipper/clip.py "LINK" 1:23 +20` |
| Several clips from one video | `python clipper/clip.py "LINK" --clips "0:10-0:25, 3:00+12"` |
| Vertical, for Shorts / Reels / TikTok | add `--vertical` |
| Animated GIF | add `--gif` |
| Audio only | add `--mp3` |
| Lower quality, smaller file | add `-q 720` |
| Choose the file name | add `-n my-clip` |
| Clip a file on your computer | `python clipper/clip.py my-video.mp4 0:05 0:15` |

Clips are saved in a `clips` folder. Use `-o another-folder` to save somewhere else.

Times can be written as `83`, `1:23`, `1:02:03` or `1m23s`. If your link has a start time in it (a "Share > Start at" link), you can leave out the start time.

**Vertical clips** keep the middle of the picture and cut off the sides. Keep the action centred.
