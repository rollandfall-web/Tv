---
name: clip-maker
description: Make short vertical clips (YouTube Shorts, TikTok, Reels) from a YouTube or Twitch link, or from a video file, using the Clip Maker tool on this computer. Use when the commander asks to clip a video, find its best moments, make Shorts, or add captions to a clip. Needs the Workbench (terminal).
---

# Clip Maker

Clip Maker is a command-line tool on this computer. It finds the best moments
in a video, cuts them, makes them vertical, and burns in animated captions.
Everything runs locally. It is free; it never needs an API key.

## Truth rules (read first, every job)

These override everything else in this skill.

1. **Only report what you saw.** Every fact about a person, page, campaign,
   number, date or quote must come from a page you opened in this job with a
   real browser step. Save a screenshot and give its path in the same report.
2. **No estimates, no gap-filling.** If you didn't see it, write `not checked`
   or `not visible`. Never guess follower counts, pay rates, dates, handles,
   invite links or quotes, and never present a guess as a finding.
3. **Never write page text yourself.** Quotes must be copied from a browser
   tool's output. Never type something that looks like a tool result.
4. **Keep the proof.** Save screenshots in `Outreach/<Streamer>/evidence/`
   (or `shots/`) and list them on the profile's `Evidence:` line. Run
   `python3 clipper/outreach.py verify` after updating profiles.
5. **Approval needs proof of permission:** a screenshot of the streamer's reply
   or of their page allowing reposts, or a campaign the commander says they
   joined. `outreach.py status ... approved` refuses without it.
6. **Say when you're stuck.** If a page won't load or a tool fails, report the
   exact error. "I couldn't check this" is a good answer; an invented one is
   the worst possible answer.
7. **Repeating someone else's claim is not verifying it.** A crew member's
   report, a search snippet or an earlier file is "unverified" until you open
   the source yourself.

## Before you start

1. **Find the tool.** It is a folder containing `clipper/clip.py`. Use the
   first of these that exists:
   - a folder the commander told you about
   - `~/ClipMaker` or `~/Clip Maker`
   - a Clip Maker folder on another drive. List candidates with:
     `ls -d /Volumes/*/ClipMaker /Volumes/*/"Clip Maker" /Volumes/*/Tv-claude-youtube-clip-maker-lyx2h0 2>/dev/null`
   - `~/Downloads/Tv-claude-youtube-clip-maker-lyx2h0`

   Folder names may contain spaces: always put the path in double quotes,
   e.g. `cd "/Volumes/Mac Memory Drive/Clip Maker"`.

   If none exists, ask the commander where the Clip Maker folder is, and check
   that its drive is connected. Run every command below from inside that
   folder (`cd` into it first).
2. **Check permission.** Only clip videos the commander owns or has permission
   to use (for example, a streamer's clipping campaign). If the commander asks
   to clip someone else's video and permission is unclear, ask once before
   making clips. Never post clips anywhere unless the commander asks.
3. **Use `python3`** on macOS. On Windows use `python`.

## Find videos

Search YouTube (the number after `ytsearch` is how many results):

```bash
yt-dlp --flat-playlist --print "%(title)s | %(channel)s | %(duration_string)s | %(view_count)s views | %(url)s" "ytsearch10:GTA 6 funny moments"
```

Newest uploads from a channel, or a Twitch streamer's latest streams:

```bash
yt-dlp --flat-playlist -I 1:10 --print "%(title)s | %(duration_string)s | %(view_count)s views | %(url)s" "https://www.youtube.com/@CHANNEL/videos"
yt-dlp --flat-playlist -I 1:10 --print "%(title)s | %(duration_string)s | %(url)s" "https://www.twitch.tv/STREAMER/videos?filter=archives"
```

Some fields can show `NA` (for example views in search results); that's normal.
Return the list as it is. Finding a video is not permission to clip it.

If Twitch or YouTube refuses (sign-in needed, subscriber-only, age-restricted),
add `--cookies-from-browser chrome` to yt-dlp, or `--browser chrome` to clip.py.
That uses the commander's own Chrome sign-in; never ask for a password.

## Find the best moments (no cutting)

```bash
python3 clipper/clip.py "LINK" --auto --list --json --count 5
```

The last line of the output starts with `@@PICKS@@` followed by JSON:
`{"title": ..., "clips": [{"start": 41.0, "end": 63.5, "score": 82, "title": ..., "reason": ...}]}`.
Times are seconds. Score is 0 to 100 and only compares moments within the same video.
`--auto` works on a whole VOD; you never need timestamps to start.

Useful options:

| Option | Use |
|---|---|
| `--focus "car chases, funny reactions"` | What the commander wants. Pass their words. |
| `--count 3` | How many moments. |
| `--min 15 --max 45` | Clip length range in seconds (default 15 to 60). |
| `--credit "twitch.tv/NAME"` | Shows the streamer's handle on screen for the whole clip. Use it whenever a campaign asks to "include the stream handle in the clip", and for any streamer you clip. |
| `--headline "TEXT"` | Big text across the top for the whole clip (music edits with no talking). `" | "` starts a new line. |
| `--mute` or `--volume 20` | Remove the clip's own audio (to add a song in TikTok/Reels), or keep it quietly under music. |
| `--skip-text` | Skip moments that already have subtitles or titles on screen (needs Tesseract). |
| `--browser chrome` | When a video needs sign-in, is age-restricted or asks to "confirm you're not a bot". Uses Chrome's sign-in. |

## Make the clips

Shorts with captions and the streamer's handle, best moments chosen automatically:

```bash
python3 clipper/clip.py "LINK" --auto --count 3 --vertical --captions --credit "twitch.tv/NAME" --focus "WHAT THEY WANT"
```

For campaigns that want context (most do), use longer clips: add `--min 30 --max 60`.

Exact times the commander gives (start and end, or start and `+seconds`):

```bash
python3 clipper/clip.py "LINK" 1:23 1:45 --vertical --captions
python3 clipper/clip.py "LINK" --clips "0:10-0:25, 3:00+12" --vertical --captions
```

Music campaigns (the song must be the main audio, no talking): cut a short
clip with no captions, a headline, and no original audio, then the commander
adds the official sound when posting:

    python3 clipper/clip.py "TRAILER_LINK" 1:02 +15 --vertical --headline "When GTA 6 finally | drops tomorrow" --mute

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
| `age-restricted` / `not a bot` / sign-in needed | Run again with `--browser chrome`. |
| `CERTIFICATE_VERIFY_FAILED` | Ask the commander to run `python3 -m pip install -U certifi yt-dlp`. |
| `Requested format is not available` | Ask the commander to run `brew install deno` and `python3 -m pip install -U "yt-dlp[default]"`. |
| `can't draw captions` | Clips were still made, without captions. Ask the commander to run `brew install ffmpeg-full`. |
| `unrecognized arguments` | The Clip Maker on disk is out of date. Ask the commander to update it. |
| `yt-dlp is not installed` / `ffmpeg was not found` | Ask the commander to finish the setup in `clipper/README.md`. |

Don't install software yourself unless the commander asks you to. Don't invent
workarounds; report the exact error instead.

## Report back

Give the commander, for each clip: the file path, the time range, its length,
the score, and the reason. If you used `--focus`, say how each clip matches it.
If a moment was skipped (on-screen text, no speech), say so.
