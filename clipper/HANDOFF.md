# Handoff: LS Daily Cuts clipping setup

Read this first if you're a Claude (Cowork, Claude Code or chat) picking up this
project. It sums up everything set up so far, how the commander works, and the
rules. Last updated: Nov 18, 2026, 11:40 PM Mountain (GTA 6 launch night), merged
from Claude Code's handoff and the Claude chat session. Committed to the repo Nov 19.

**Also read before working:** `Outreach/TEAM-STATE.md` (current priorities, approvals,
ready clips), `Outreach/PRIVATE.md` (team details, shared Drive folder link, codes;
local only, never in the repo) and `Outreach/<Name>/CAMPAIGN.md` (full rules for each
campaign). The same TEAM-STATE lives in the team's shared Google Drive folder
"GTA Clipping Team" (link in PRIVATE.md).
At the end of a session, add one dated line to TEAM-STATE's session log saying what changed.

The commander is non-technical: give short, numbered steps, exact things to
click or paste, and ask for screenshots when unsure. Time zone: Mountain
(America/Denver). Uses a MacBook Air; Chrome for the Clip Maker app (Safari
blocks it). Prefers plain language and no em dashes.

## The goal

Earn from GTA clipping: post short vertical clips through paid clipping
campaigns and with streamers' permission, starting with the GTA 6 launch
(Nov 18-19, 2026). Not art, not merch.

## Team

- **Commander** (LS Daily Cuts owner): posts, submits, and is the only one who approves.
- **Teammate** (the commander's brother): has his own Claude. Launch-week role still open
  (editor for LS Daily Cuts, or second clipper on his own pages). Has a starter kit
  (`GTA-Clipping-Team-Kit.zip`). Details in `Outreach/PRIVATE.md` and TEAM-STATE.

## Accounts (brand: LS Daily Cuts)

- TikTok @lsdaily.cuts (older account; "one video with ~1.2M views" is unverified)
- YouTube @LsDailyCuts
- Instagram @lsdaily.cuts
- X @LSdailycuts
- Whop / Content Rewards: lsdailycuts. TikTok, Instagram and YouTube are connected in
  Content Rewards; X is not. "Auto-join brand Discords" is ON.
- Discord: "LS Daily Cut's Server", with the StarNet bot "LS Station" (paired Nov 18).
  Joined: Clipping Nation, Ruckus, Reach Clipping (phone verify still needed),
  GTA Clipper. Onboarding questions in Clipping Nation and Ruckus may still be open.

Keep the commander's real name out of everything. Never ask for passwords,
login codes, tokens, ID or bank details.

## Campaigns (all on Content Rewards unless noted; as of Nov 18, 11:40 PM)

Approved in `Outreach/approved.md` so far: **Tokyo Girl, Lacy** only. Everything else
has join proof in `Outreach/<Name>/evidence/joined.jpg` and waits for the commander's
`python3 clipper/outreach.py approve "NAME"`.

**Submission caps:** Tomo and KreekCraft allow 3 submissions until the account is
approved by the campaign. Each post on each platform is one submission. Check every
new campaign for a cap. Tomo's 3 are USED (same clip on TikTok, IG, YT). Don't post
more Tomo until the campaign approves the account.

| Campaign | Pay | State / key rules |
|---|---|---|
| **Tokyo Girl** (Placements) | $0.70/1K, $2 min, $35 max | Approved. TikTok + Reels only. Official Tokyo Girl sound only (clips muted), caption "Song: Tokyo Girl by @Passive" (IG @PassiveBand). Official Rockstar footage, NO trailer text or logos (the Launch Trailer has "Rockstar Games presents" at 0:16-0:17, the logo at 0:22-0:25 and from 1:16 on). 3 clean clips in `Ready/` (A, B, C) |
| **Lacy GTA VI Marathon** (Reach) | $12.5K pool, 750K views needed | Approved. VOD https://www.twitch.tv/videos/2932194507. Lacy the main focus; LACY in caption or text + #LACY; no logos; positive only. **GTA VI chapters only**: he also streamed IRL (a gas station). Job file `Jobs/inbox/2026-11-19-lacy-clips.md` |
| **Tomo GTA VI** (Clipping Nation) | $1.50/1K after 2,334 views, $150 max | Budget draining ($388 of $1,000 used at 8 PM). Source VOD https://www.youtube.com/watch?v=XRo2L3077NI. Moments in `Outreach/Tomo/samples/moments.md`, captions in `messages/captions.md`. Caption: "Subscribe to Tomo on YouTube" + @Tomovids #tomovids #gta6. Tags: TikTok @tomovidslive, IG @tomovids, YT @Tomovids. Send the country-breakdown screenshot to the Clipping Nation Discord at 2,334 views. Cap used |
| **KreekCraft GTA 6** (ClipLaunch) | $1/1K, $2 min, $400 max | Overlay required the whole clip (download from the campaign page, use `--overlay`). Caption "Watch KreekCraft on YouTube and Twitch" + #GTA6 #KreekCraft #GrandTheftAutoVI. Tags: TikTok @dakreekcraft, IG @kreekcraft, YT @Kreek, Twitch kreekcraft. Moments in `Outreach/KreekCraft/samples/moments.md` (YouTube time = Twitch time minus 1:20). Cap: 3, one different clip per platform |
| **Dylan Page GTA VI Marathon** (NewsDaddy) | $1/1K, $10 min, $250 max | 120-hour marathon on YouTube (@dylan.page.). #DylanPage, Dylan in the clip |
| **Aron Orlando "Miami House Party"** (music) | $1/1K, 5,000-view minimum, $100 max | DRAFTS NEED PRE-APPROVAL before posting. Use the platform's campaign sound (links in CAMPAIGN.md); the song must be clearly audible. GTA 6 edits and memes |
| **Kai Cenat GTA 6 Pool** (Clipped & Shipped) | $10K pool, 750K needed | New agency, no proof Kai runs it. Test 1-2 clips max. #KaiCenat |
| **Dasgasd3m x Ruckus** | $1/1K, $10 min | Kick. Nov 18 VOD https://kick.com/dasgasd3m/videos/01a1f07f-5c68-76ff-a91d-c61d275a4edd. Credit kick.com/dasgasd3m, #dasgasdom3, keep his face or voice. TikTok + Shorts only |
| **Clix GTA VI Marathon** (Reach) | $5K pool, 400K needed | Crowded. #Clix |
| **JasonTheWeen Pool** (Reach) | $9K pool, 700K needed | Very crowded (2,593). GTA VI VOD https://www.twitch.tv/videos/2932190650 |
| **YourRAGE GTA 6** (Reach) | $5K pool, 500K needed | Marathon hadn't started as of 6 PM. #yourrage |
| **Bobby Van Riper** (Clipping Nation) | $1/1K after 1,950 views | No GTA VI stream yet. #bobbyvanriper |
| **Marlon** (Reach) | $2.50/1K, $25 min | Rules page locked (code in `Outreach/PRIVATE.md`), not read yet. No GTA VOD seen |
| **Lysium / Benji Ramos** | $1.50/1K | Applied, pending. NoPixel V only. Don't post |
| **Gattouz x 1WIN** | $0.35/1K | Joined; SKIP (gambling branding) |
| SypherPK | | Not joined. Fortnite, off-niche |

Reach campaigns (Lacy, Clix, YourRAGE, Jason, Marlon) ban AI content and give a
one-strike ban across all of them.

## Clips on disk to know about

- `Ready/TokyoGirl_LaunchTrailer_A/B/C_clean.mp4`: clean and muted, ready for Tokyo Girl.
- Do NOT post `Ready/Grand_Theft_Auto_VI_Launch_Trailer_1m04s-1m20s_vertical.mp4` (it shows the GTA VI logo).
- `Clips/GTA_6_LIVE_FULL_GAME_GIVEAWAYS_DAY_1_*`: these are **KreekCraft**, not Lacy. 5h46m50s cuts = the shark scene, 6h40m54s and 6h41m01s cuts = the "sorry sorry bro" store scene. They need his overlay before posting.
- `Clips/PLAYING_GTA_6_FOR_THE_FIRST_TIME_*`: Tomo (club night 1:01:34, shark 2:09:34).

## The Clip Maker (this folder)

Location: `/Volumes/Mac Memory Drive/ClipMaker`. Clips save to `ClipMaker/Clips`.

- Start: `cd "/Volumes/Mac Memory Drive/ClipMaker" && python3 clipper/app.py`,
  then http://127.0.0.1:8765 in Chrome. Keep the Terminal window open.
- Main page: A. Find the best moments (Focus words, count, length), B. Edit an
  exact part (times like 2:05:10), C. Record live (records the next N minutes
  of a live stream into `Recordings/`, then loads it).
- Live streams: a channel link (twitch.tv/NAME) or a YouTube stream that's still live
  can't be cut directly. Use Record live, a Twitch VOD link (parts at least 10-15 minutes old),
  or a Twitch viewer clip link.
- Long VODs: the first search downloads the stream's audio once (a long
  marathon can take most of an hour); after that, searching the same link is
  instant and a clickable hype map of the whole stream appears.
- Found moments show **3 preview frames each** (at 15%, 50% and 85% of the clip), so
  you can tell gameplay from menus or chatting before loading a clip. Frames are cached;
  if they can't be fetched, the moment shows "No preview frames" and still works.
- Start it by double-clicking `Clip Maker.command`: it picks a Python that has yt-dlp
  (Homebrew's newest Python often doesn't, which caused "couldn't find any signal").
- Videos already on the Mac: the **Upload video** button copies a file (MP4, MOV, MKV,
  WebM) into `Raw/_uploads/` with a progress bar (never overwrites: _2, _3) and loads it
  like a pasted link. Or pick a video already in `Raw/` from the list (no copy), or
  click "Open Raw folder". A `.txt` card next to the video (or in `Raw/STREAMER/` with
  the same name, for uploads) is shown: Source, Timestamp, Facecam, Caption idea; its
  `--face "X,Y,W,H"` turns on Facecam on top with that box. Nothing leaves the Mac.
- Editor: 9:16 / 4:5 / 1:1 / 16:9, drag and zoom framing, "Facecam on top, game
  below", trim, captions you can edit and drag, caption animations, streamer
  handle text, title text, clip sound volume (0% for music campaigns), overlay
  image (only when a campaign requires it).
- Command line: `python3 clipper/clip.py --help`. Useful:
  `--auto --list --focus "funny"`, `--clips "41-63"`, `--vertical --captions`,
  `--credit "twitch.tv/NAME"`, `--headline "Line one | line two"`, `--mute`,
  `--face "75,0,25,30"` (camera box, % of the source), `--overlay FILE.png`,
  `--browser chrome` (sign-in for age-restricted or Twitch).
- Update to the newest version (keeps clips, settings and everything in `Outreach/`):
  ```
  cd "/Volumes/Mac Memory Drive"
  curl -L -o clipmaker.zip https://github.com/rollandfall-web/Tv/archive/refs/heads/claude/youtube-clip-maker-lyx2h0.zip
  unzip -o -q clipmaker.zip && cp -R Tv-claude-youtube-clip-maker-lyx2h0/ ClipMaker/
  rm -rf Tv-claude-youtube-clip-maker-lyx2h0 clipmaker.zip
  ```
  Then restart the app and open a new Chrome tab. This replaces `clipper/HANDOFF.md`
  with the repo's copy, so edit HANDOFF through the repo (ask Claude Code to commit
  changes). Keep private details in `Outreach/PRIVATE.md`; the repo is public.
- Errors print a "How to fix" line; follow it.

## StarNet AI crew

Agents in StarNet: OPPEN (lead), RESEARCHER (runs the Clip Maker), SCRIPTWRITER
(captions, messages). Skills live in `clipper/skills/`. Brief: `STARNET-BRIEF.md`.

- PERMISSIONS: all three on LET IT WORK (approval: ask, reach: trusted-project).
  FULL POWER override OFF. Approve Clip Maker commands in the ClipMaker folder;
  deny anything that posts, sends, logs in or submits.
- Trusted project: only `/Volumes/Mac Memory Drive/ClipMaker`.
- AUTONOMY (away jobs): SUGGEST or WAIT, reach LOCAL ONLY, pace LIGHT.
- Discord: the LS Station bot is paired with the commander's account. If
  `channel.targets` is empty, the commander sends the bot a DM, then the agent checks again.
- Routine "Clip Done Watch" checks Clips/ every 30 minutes. Two older routines failed
  with "CLAUDE CLI is not set up" (fix in SETTINGS > AI & MODELS).
- Jobs: job files go in `Jobs/inbox/`; reports go to `Jobs/done/`. Telling
  @RESEARCHER directly to run a job file works better than OPPEN's "handoff queued".

**The agents have repeatedly made things up** (follower counts, quotes, a
"verified" report whose screenshots never existed, campaigns called approved, and
"your goal is art and merch"). Treat every agent report as unverified until a file on
disk confirms it. On "check results", list each file the agents claim (size and
date) and say what's real and what's missing.

## Rules that always apply

- Only clip campaigns the commander approved (`Outreach/approved.md`) or
  streamers who said yes in writing. Read each brief first and follow it exactly.
- Check for submission caps and draft pre-approval before posting.
- Submit each post in Content Rewards within 30 minutes. One post goes to one campaign.
- No bought views, bots, paid boosting, reposting other clippers' edits, AI voices or AI visuals.
- Skip gambling, betting, crypto-trading or "free money" branding.
- Agents and Claudes never post, send, submit, sign up or approve. The commander does.
  (Claude chat joined campaigns tonight only on the commander's explicit request.)
- Post 1-3 times a day per platform, evenings US time; reply to early comments.

## Where to pick up

1. Commander: run approve for Tomo, KreekCraft, Dylan Page and Aron Orlando.
2. Lacy: 3 clips from GTA VI chapters only (job file above). Facecam on top, LACY + #LACY.
3. KreekCraft: add the overlay to the shark and store clips; jackpot clip (Twitch 12:24:38) for YouTube.
4. Tokyo Girl: post A, B, C over the next few evenings; check Submissions.
5. Dylan Page: clip his live marathon (0 competition when joined).
6. Aron Orlando: make one strong Vice City edit, submit it as a draft first.
7. Teammate: share the Drive folder and settle his role (see TEAM-STATE open questions).

## Change log

Newest first. Claude Code adds a line here with every change it commits.

- Nov 25, 2026: Preview frames under each found moment (3 per moment). `Clip Maker.command`
  now starts with a Python that has yt-dlp. Tested here on a local file and a web link;
  still to test on the Mac with a real YouTube and a real Twitch link. Ideas for later
  (owner's call, not built): flag picks whose frames look like menus, maps or loading
  screens; a "show 10, I pick 3" mode.
- Nov 20, 2026: Upload video button and Raw folder picker (with .txt cards and facecam
  pre-fill). Editor preview uses much less CPU; page loads faster.
- Nov 19, 2026: Merged campaign list committed (private details moved to
  `Outreach/PRIVATE.md`). Live recording, saved scans and hype map for long VODs,
  facecam split, overlays, caption drag and animations, faster downloads, clearer layout.
