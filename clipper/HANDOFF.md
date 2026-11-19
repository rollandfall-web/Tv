# Handoff: LS Daily Cuts clipping setup

Read this first if you're a Claude (Cowork, Claude Code or chat) picking up this
project. It sums up everything set up so far, how the commander works, and the
rules. Last updated: Nov 19, 2026 (GTA 6 launch night).

The commander is non-technical: give short, numbered steps, exact things to
click or paste, and ask for screenshots when unsure. Time zone: Mountain
(America/Denver). Uses a MacBook Air; Chrome for the Clip Maker app (Safari
blocks it).

## The goal

Earn from GTA clipping: post short vertical clips through paid clipping
campaigns and with streamers' permission, starting with the GTA 6 launch
(Nov 18, 10 PM Mountain). Not art, not merch.

## Accounts (brand: LS Daily Cuts)

- TikTok @lsdaily.cuts (older account, one video with ~1.2M views)
- YouTube @LsDailyCuts
- Instagram @lsdaily.cuts
- X @LSdailycuts
- Whop / Content Rewards username: lsdailycuts
- Discord: "LS Daily Cut's Server", with the StarNet bot "LS Station"

Keep the commander's real name out of everything. Never ask for passwords,
login codes, tokens, ID or bank details.

## Campaigns (as of Nov 19, 2026)

| Campaign | State | Key rules |
|---|---|---|
| Tokyo Girl (Placements, Whop/Content Rewards) | JOINED and approved by the commander. Clip 1 (heist chase edit) posted on TikTok and submitted. | TikTok + Instagram Reels only. Official Tokyo Girl sound as main audio, no talking (clips made muted). Caption line "Song: Tokyo Girl by @Passive" (IG: @PassiveBand). Official Rockstar footage only, no trailer text or logos. Paid-content disclosure on. $0.70/1K views, $2 min, $35 max per clip. |
| Lacy GTA 6 marathon (Clip Money / reachclipping.com/LACYGTA) | JOINED and approved by the commander. Marathon live now; VOD https://www.twitch.tv/videos/2932194507. No Lacy clips confirmed yet. | Lacy the main focus the whole clip. Caption or on-screen text says LACY; caption has #LACY. No logos of any kind. Positive only, no hate farming. TikTok, Reels, Shorts, X. 50%+ English-speaking audience. Pool campaign: only approved videos count, total view requirement. Ends when the marathon ends. |
| Lysium (Content Rewards) | Applied, sample sent in Support chat, no reply. NOT approved. | NoPixel V streams only, credit twitch.tv/Lysium on screen, 30-60 s, no drama baiting. |
| Gattouz x GTA VI x 1WIN | Joined by mistake; SKIP. | Requires visible 1WIN gambling branding (account and legal risk); pays only at 100K views per clip. |
| SypherPK | Not joined. | Fortnite, off-niche. |

The commander's approvals are in `Outreach/approved.md` (written only by the
commander's own `outreach.py approve` pop-up). That file is the only truth.

## The Clip Maker (this folder)

Location: `/Volumes/Mac Memory Drive/ClipMaker`. Clips save to `ClipMaker/Clips`.

- Start: `cd "/Volumes/Mac Memory Drive/ClipMaker" && python3 clipper/app.py`,
  then http://127.0.0.1:8765 in Chrome. Keep the Terminal window open.
- Main page: A. Find the best moments (Focus words, count, length), B. Edit an
  exact part (times like 2:05:10), C. Record live (records the next N minutes
  of a live stream into `Recordings/`, then loads it).
- Long VODs: the first search downloads the stream's audio once (a long
  marathon can take most of an hour); after that, searching the same link is
  instant and a clickable hype map of the whole stream appears.
- Editor: 9:16 / 4:5 / 1:1 / 16:9, drag and zoom framing, "Facecam on top, game
  below" (drag a box onto the streamer's camera), trim, captions you can edit
  and drag, caption animations (pop, bounce, fade, slide, typewriter), streamer
  handle text, title text, clip sound volume (0% for music campaigns), overlay
  image (a streamer's frame or logo, only when required).
- Command line: `python3 clipper/clip.py --help`. Useful:
  `--auto --list --focus "funny"`, `--clips "41-63"`, `--vertical --captions`,
  `--credit "twitch.tv/NAME"`, `--headline "Line one | line two"`, `--mute`,
  `--face "75,0,25,30"` (camera box, % of the source), `--overlay FILE.png`,
  `--browser chrome` (sign-in for age-restricted or Twitch).
- Update to the newest version (keeps clips and settings):
  ```
  cd "/Volumes/Mac Memory Drive"
  curl -L -o clipmaker.zip https://github.com/rollandfall-web/Tv/archive/refs/heads/claude/youtube-clip-maker-lyx2h0.zip
  unzip -o -q clipmaker.zip && cp -R Tv-claude-youtube-clip-maker-lyx2h0/ ClipMaker/
  rm -rf Tv-claude-youtube-clip-maker-lyx2h0 clipmaker.zip
  ```
  Then restart the app and open a new Chrome tab.
- Errors print a "How to fix" line; follow it.

## StarNet AI crew

Agents in StarNet: OPPEN (lead), RESEARCHER (runs the Clip Maker), SCRIPTWRITER
(captions, messages). Skills live in `clipper/skills/`.

Settings now in place:
- PERMISSIONS: all three on LET IT WORK (approval: ask, reach: trusted-project).
  FULL POWER override OFF. They ask before risky steps; approve Clip Maker
  commands in the ClipMaker folder, deny anything that posts, sends, logs in or
  submits.
- Trusted project: only `/Volumes/Mac Memory Drive/ClipMaker`.
- AUTONOMY (away jobs): should be SUGGEST or WAIT, reach LOCAL ONLY, pace
  LIGHT, focus = the ClipMaker folder, off-limits "art and merch listings".
- Discord: the LS Station bot can DM the commander (channel.targets shows one
  Discord chat). The bot once claimed "no campaign is joined" and "your goal is
  art and merch"; both wrong. The Discord chat should be bound to OPPEN.
- Jobs: job files go in `Jobs/inbox/`; when the commander says "check jobs",
  OPPEN runs them and writes reports to `Jobs/done/`.
- Known problem: OPPEN's "handoff queued" to the crew often never runs. Telling
  @RESEARCHER directly to run a job file itself works better.

**The agents have repeatedly made things up** (follower counts, quotes, a
"verified" report whose screenshots never existed, campaigns called approved).
Treat every agent report as unverified until a file on disk confirms it. When
the commander says "check results", list each file the agents claim (size and
date) and say what's real and what's missing.

## Rules that always apply

- Only clip campaigns the commander joined (see `Outreach/approved.md`) or
  streamers who said yes in writing.
- Read each campaign brief before clipping; follow it exactly.
- No bought views, bots, paid boosting, or reposting other clippers' edits.
- Skip campaigns that require gambling, betting, crypto-trading or "free money"
  branding.
- Agents never post, send, submit, join, sign up or approve; the commander does.
- Post 1-3 times a day per platform, evenings US time; reply to early comments.

## Where to pick up

1. Lacy: get 3-4 clips out while the marathon runs (VOD above, or moments from
   twitch.tv/lacy/clips via "Watch Full Video" times). Facecam on top, captions
   on, no logos, caption with LACY and #LACY. The commander submits each link.
2. Tokyo Girl: keep posting muted edits from official footage (Vice City views,
   Jason & Lucia, hype); check Whop > Submissions for approvals or rejections.
3. Lysium: wait for their reply; then the commander approves with
   `python3 clipper/outreach.py approve "Lysium"`.
4. Check the Clips folder for the 4 "GTA_6_LIVE_FULL_GAME_GIVEAWAYS_DAY_1" clips
   from Nov 18 evening: confirm which stream and campaign they belong to before
   posting (skip giveaway segments for Lacy).
5. Find smaller GTA streamers (Twitch GTA V category, 20-500 viewers) and draft
   permission messages for the commander to send.
