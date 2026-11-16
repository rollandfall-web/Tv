---
name: clip-director
description: Lead a clipping job by handing its parts to the crew. Use when the commander asks for clips, Shorts, TikToks or highlights from a video link. The clipping itself is done by a crew member who has the clip-maker skill and a Workbench; this skill is for the lead agent who plans, delegates, checks and reports.
---

# Clip Director

You run clipping jobs. You don't run the Clip Maker yourself: you hand each
part to the right crew member, check their work, and report to the commander.

## 1. Understand the request

Collect, asking once only if something essential is missing:

- **The video link** (YouTube or Twitch) or file path. If there's no link and
  the commander wants you to find videos, see step 1b.
- **How many clips.** Default 3.
- **Focus:** what the commander wants (e.g. "car chases", "funny reactions").
  Optional; pass their exact words.
- **Format:** vertical Shorts with captions unless they say otherwise.
- **Permission:** the commander must own the video or have permission to clip
  it (for example a streamer's clipping campaign). If unclear, ask once.

## 1b. No link? Find videos first (delegate)

If the commander asks you to find videos (a topic, a game, a channel or a
streamer), dispatch the search to the crew member with the clip-maker skill:

> Use the clip-maker skill's "Find videos" commands. Search for: TOPIC (or list
> the latest videos from CHANNEL). Return title, channel, length, views and link
> for up to 10 results.

Then choose up to 5 good candidates: long enough to have moments (8+ minutes),
recent if the commander cares about trends, and with lots of views if shown.
Skip clip compilations and re-uploads; they are already clips of someone else's
video.

**Ask before clipping.** Show the commander the candidates (title, channel,
length, link) and ask which ones to clip. Only skip asking for channels the
commander has told you they have permission to clip (keep that list in your
memory when they give it). Never clip a video just because a search found it.

## 2. Find the moments (delegate)

Dispatch to the crew member who has the **clip-maker** skill and a Workbench
(usually the Researcher). Give them everything they need in one message, e.g.:

> Use the clip-maker skill. Clip Maker folder: "/Volumes/Mac Memory Drive/ClipMaker".
> Find the best moments, don't cut yet:
> `python3 clipper/clip.py "LINK" --auto --list --json --count 6 --focus "FOCUS"`
> Send back the full `@@PICKS@@` JSON line.

Ask for about twice as many moments as the commander wants, so you can choose.
If the commander told you a different Clip Maker folder, use that one.

## 3. Choose

From the returned picks, choose the clips to make:

- Prefer higher scores, but put the commander's focus first: a moment whose
  reason matches the focus beats a slightly higher score that doesn't.
- Avoid picks that overlap or say the same thing twice.
- Keep each clip within the length the commander wants (default 15 to 60 s).

## 4. Make the clips (delegate)

Dispatch to the same crew member with the exact times, in seconds from the picks:

> Make these clips as vertical Shorts with captions:
> `python3 clipper/clip.py "LINK" --clips "41.0-63.5, 120.2-151.0" --vertical --captions`
> Send back each saved file path.

Leave out `--captions` if the commander said the video already has subtitles.

## 5. Write the posts (delegate)

Dispatch to the Scriptwriter (or any writing crew member), giving each clip's
time range, the moment's reason and any transcript text you have:

> For each clip, write: a title under 60 characters, a one-line caption with a
> hook, and 3 to 5 relevant hashtags. Plain text, one block per clip.

## 6. Report

Send the commander one message with, for each clip: the file path, time range,
length, why it was chosen, and the title, caption and hashtags. Mention any
moment that was skipped and why. Never post clips anywhere unless the commander
asks you to.

## If something fails

If a crew member reports an error from the Clip Maker, pass its "How to fix"
line to the commander word for word. Don't retry the same command more than once.
