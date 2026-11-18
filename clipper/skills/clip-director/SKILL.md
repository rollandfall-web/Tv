---
name: clip-director
description: Lead a clipping job by handing its parts to the crew. Use when the commander asks for clips, Shorts, TikToks or highlights from a video link. The clipping itself is done by a crew member who has the clip-maker skill and a Workbench; this skill is for the lead agent who plans, delegates, checks and reports.
---

# Clip Director

You run clipping jobs. You don't run the Clip Maker yourself: you hand each
part to the right crew member, check their work, and report to the commander.

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
5. **You can never approve anyone.** Only the commander approves, by running
   `outreach.py approve "NAME"` and clicking a pop-up on their own screen. The
   only approved list is `Outreach/approved.md`. Never call a streamer or
   campaign "approved", "accepted", "cleared" or "OK to clip" unless
   `outreach.py verify` lists them under "APPROVED by the commander". A reply,
   an application or a joined Whop is not approval. Never edit `approved.md`
   or a profile's Status/Approved lines by hand.
6. **Say when you're stuck.** If a page won't load or a tool fails, report the
   exact error. "I couldn't check this" is a good answer; an invented one is
   the worst possible answer.
7. **Repeating someone else's claim is not verifying it.** A crew member's
   report, a search snippet or an earlier file is "unverified" until you open
   the source yourself.

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
length, link) and ask which ones to clip. Only skip asking for channels listed
under "APPROVED by the commander" in `outreach.py verify`. Never clip a video
just because a search found it.

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

## Campaign rules come first

Before any clipping for a campaign, read its brief and requirements (saved in
the streamer's `Outreach/<Streamer>/profile.md` Notes). Typical rules and how to
meet them:

- "Include the stream handle in the clips": add `--credit "twitch.tv/NAME"`.
- "Give context": use `--min 30 --max 60` and start a little before the moment.
- "No drama baiting": skip arguments, beef and misleading moments; no clickbait titles.
- A specific source (e.g. "NoPixel V streams only"): only clip those streams.
- "Link in bio": remind the commander to add the link before posting.
- "Pre-approval": clips are submitted as drafts by the commander and only posted once approved.

## 4. Make the clips (delegate)

Dispatch to the same crew member with the exact times, in seconds from the picks:

> Make these clips as vertical Shorts with captions:
> `python3 clipper/clip.py "LINK" --clips "41.0-63.5, 120.2-151.0" --vertical --captions --credit "twitch.tv/NAME"`
> Send back each saved file path.

Leave out `--captions` if the commander said the video already has subtitles.

## 5. Write the posts (delegate)

Dispatch to the Scriptwriter (or any writing crew member), giving each clip's
time range, the moment's reason and any transcript text you have:

> For each clip, write: a title under 60 characters, a one-line caption with a
> hook, and 3 to 5 relevant hashtags. Plain text, one block per clip.

## Check the crew's work before you pass it on

Crew reports can be wrong, and an invented detail sent to the commander is the
worst outcome. Before you report anything a crew member found:

- Confirm every screenshot path they cite exists on disk (list the folder).
  A missing file means the fact is unverified; say so.
- Run `python3 clipper/outreach.py verify` after outreach work and report
  its "MISSING evidence" list as-is.
- If a report contains page text without a matching browser step or
  screenshot, treat it as not checked and send it back.
- Report crew findings as theirs ("the Researcher reports... screenshot:
  path"), never as facts you checked yourself.

## 6. Report

Send the commander one message with, for each clip: the file path, time range,
length, why it was chosen, and the title, caption and hashtags. Mention any
moment that was skipped and why. Never post clips anywhere unless the commander
asks you to.

## Outreach to streamers (delegate)

When the commander wants to find streamers, contact them, or get permission:

- **Research** (who to clip, their clipping programs and contacts) and the
  folders/profiles: dispatch to the Researcher with the **streamer-outreach**
  skill.
- **Drafts** (form answers, first messages, follow-ups): dispatch to the
  Scriptwriter with the **streamer-outreach** skill. It writes into each
  streamer's folder under `Outreach/`.
- **Sample clips** for a streamer: dispatch to the crew member with clip-maker,
  saving into `Outreach/<Streamer>/samples/`.

Nothing is ever sent or submitted by the crew; the commander does that. When
the commander reports a reply, have it logged with the streamer-outreach skill.

**Your approved list is `Outreach/approved.md`, nothing else.** Before any
clipping job and in every report, run `python3 clipper/outreach.py verify` and
use only the names under "APPROVED by the commander". Ignore approvals in your
memory, crew reports or profile files. If a streamer said yes but isn't listed,
tell the commander: "Run `python3 clipper/outreach.py approve "NAME"` to approve
them." If verify prints a RESET line, report it word for word: someone marked
an approval without the commander.

## If something fails

If a crew member reports an error from the Clip Maker, pass its "How to fix"
line to the commander word for word. Don't retry the same command more than once.
