# YouTube Clip Maker

Cuts clips out of a YouTube video and saves them as MP4, as a vertical video for Shorts, Reels or TikTok, as a GIF, or as an MP3. It downloads only the part you ask for, so clips from long videos are fast. It also works on video files already on your computer.

> Only clip videos you own or have permission to use. Downloading other people's videos may break YouTube's terms of service.

## The easy way: the Clip Maker app

After the one-time setup below, **double-click `Clip Maker.command`** (Mac) or **`Clip Maker.bat`** (Windows) in this folder. A small window opens (leave it open) and Clip Maker opens in your web browser. There, you:

1. Paste a YouTube or Twitch link and click **Find best moments** (or type a start and end time).
   - **Focus on (optional):** say what you want, like "funny reactions" or "when they talk about the heist".
   - **Add captions:** turn this off if the video already has subtitles burned in.
   - **Skip moments with text already on screen:** leaves out parts with subtitles, captions or big titles. Text that is always there, like a game HUD or a streamer's name, is ignored.
2. Click **Edit & make** on a moment.
3. Frame it:
   - **Size:** 9:16 (Shorts, TikTok, Reels), 4:5 (Instagram feed), 1:1 (square) or 16:9 (YouTube).
   - **Drag the video** to choose what's in frame, and use **Zoom** to get closer.
   - **Start / End:** nudge them, or play and click **Set to playhead**. You can go up to 10 seconds past the picked moment.
   - When there's speech, clips start and end on **full sentences** automatically. After trimming, click **Snap to sentences** to fix the edges again.
4. Edit the captions:
   - **Words:** they come from YouTube's captions, or from **Transcribe speech** (speech-to-text on your computer). Fix any word, delete lines, or add your own. Wrap a word in `*stars*` to highlight it.
   - **Style:** font, size, position, colors, outline, bold, uppercase, pop, shadow, words per line.
   - **Opacity:** text opacity, plus a background box with its own color and opacity.
   - **Credit on screen:** type the streamer's handle (for example `twitch.tv/Lysium`) to show it near the top for the whole clip. Many campaigns require it. From Terminal: `--credit "twitch.tv/Lysium"`.
5. Click **Make clip**. Clips are saved in **Movies/Clip Maker** (Videos/Clip Maker on Windows).

Close the small window to quit. The first time on a Mac, if it says the file can't be opened, right-click it, choose **Open**, then **Open** again.

### Optional extras

| Extra | What it does | Install once |
|---|---|---|
| Speech-to-text | Writes captions for videos without them (Twitch, your own files) | `python3 -m pip install -U faster-whisper` (Mac, if that fails: `python3 -m pip install -U mlx-whisper`) |
| Text detection | Skips moments with text already on screen | Mac: `brew install tesseract` · Windows: `winget install UB-Mannheim.TesseractOCR` |
| Free local AI | Reads the transcript and judges each moment (hook, makes sense alone, payoff, your focus). No API key and no cost. | Install [Ollama](https://ollama.com), open it, then run `ollama pull llama3.2` |

The first time you transcribe, the speech model downloads (about 500 MB). After that it works offline.

**Which "smart picks" you get:** with an Anthropic API key, Claude reads the transcript (best). Without one, the free local AI does it if Ollama is installed and open. Otherwise, the free method picks by popularity, loudness and words that match your focus. The app shows which one it's using under the focus box.

## Set up (once)

1. Install [Python 3](https://www.python.org/downloads/). On Windows, tick **Add Python to PATH** during install.
2. Install ffmpeg:
   - **Windows:** `winget install ffmpeg`
   - **Mac:** `brew install ffmpeg`
   - **Linux:** `sudo apt install ffmpeg`
3. Install yt-dlp and Deno (a helper YouTube now requires):
   ```bash
   python -m pip install -U "yt-dlp[default]" certifi
   ```
   - **Windows:** `winget install DenoLand.Deno`
   - **Mac:** `brew install deno`

If clips stop downloading, YouTube has changed something. Run the step 3 command again to update yt-dlp.

**Age-restricted videos** (like game trailers) or a **"confirm you're not a bot"** error: sign in to YouTube in Chrome, then add `--browser chrome` to the command. The tool borrows Chrome's sign-in. Safari and Firefox work too (`--browser safari`), but Safari needs Terminal to have Full Disk Access (System Settings > Privacy & Security).

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

**Mac:** Homebrew's normal ffmpeg can't draw captions. Run `brew install ffmpeg-full` once; the tool finds it automatically.

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

## Moving Clip Maker to another drive

1. Quit Clip Maker (close its small window).
2. In Finder, drag the Clip Maker folder onto the other drive, rename it `ClipMaker`, then delete the old copy.
3. Double-click `Clip Maker.command` inside the moved folder.

When the app runs from another drive, new clips are saved in a `Clips` folder next to it on that drive. To pick a different folder, open **Save clips to** in the app, drag a folder into the box, and click **Save**. Keep the drive plugged in while you use Clip Maker. If it isn't connected, clips go to Movies/Clip Maker instead.

Python, ffmpeg and the other tools stay installed on your Mac; only the Clip Maker folder moves.

## Use it with StarNet agents

[StarNet](https://starnetos.com) agents can run Clip Maker for you, from the station or from your phone on Telegram.

1. **Move the folder somewhere permanent (optional but recommended):** rename the unzipped folder to `ClipMaker` and put it in your home folder, so it's at `~/ClipMaker`.
2. **Give your agent a terminal:** in StarNet's build mode, place a **Workbench** in the agent's room.
3. **Add the skill:** in StarNet, open **CONNECT › ABILITIES › SKILL MARKET › ADD FROM A LINK**, paste this link, click **INSPECT**, then install:
   `https://github.com/rollandfall-web/Tv/blob/claude/youtube-clip-maker-lyx2h0/clipper/skills/clip-maker/SKILL.md`
4. **Ask for clips** in COMMS or Telegram, for example: "Make 3 Shorts with captions from LINK, focus on the car chases."

To clip on a schedule, save that request as a recipe and click **MAKE ROUTINE**, then turn scheduling on.

