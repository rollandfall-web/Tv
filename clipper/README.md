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

## Make a clip

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
