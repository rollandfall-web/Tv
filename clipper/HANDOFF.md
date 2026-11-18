# Handoff: LS Daily Cuts clipping setup

Read this first if you're a Claude (Cowork, Claude Code or chat) picking up this
project. It sums up everything set up so far, how the commander works, and the
rules. The commander is non-technical: give short, numbered steps, exact things
to click or paste, and ask for screenshots when unsure.

## The goal

Earn from clipping GTA content around the GTA 6 launch (Nov 18, 2026, 10 PM
Mountain time) by posting short vertical clips through paid clipping campaigns.
The commander is in Denver (Mountain time), uses a MacBook Air, and can't
afford API keys or the game.

## Accounts (brand: LS Daily Cuts)

- TikTok @lsdaily.cuts (older account, one video with ~1.2M views)
- YouTube @LsDailyCuts
- Instagram @lsdaily.cuts
- X @LSdailycuts
- Whop / Content Rewards username: lsdailycuts
- Discord server exists (invite link not recorded here)

Keep the commander's real name out of everything. Never ask for passwords,
login codes, ID or bank details.

## The Clip Maker (this folder)

Location on the Mac: `/Volumes/Mac Memory Drive/ClipMaker` (external drive).
Clips save to `ClipMaker/Clips`.

- Start the app: `cd "/Volumes/Mac Memory Drive/ClipMaker" && python3 clipper/app.py`,
  then open http://127.0.0.1:8765 in **Chrome** (Safari blocks it).
- App features: finds best moments from a YouTube/Twitch/Kick link (Focus box
  steers it), 9:16/4:5/1:1/16:9 framing with drag and zoom, trim, sentence snap,
  editable animated captions (drag to move; animations none/pop/bounce/fade/
  slide/typewriter), credit text, headline text, original-audio volume/mute,
  skip moments with on-screen text (Tesseract installed).
- Command line: `python3 clipper/clip.py --help`. Common:
  `python3 clipper/clip.py "LINK" --auto --list --count 6 --focus "funny"`
  `python3 clipper/clip.py "LINK" --clips "41-63" --vertical --captions --credit "twitch.tv/NAME"`
  `python3 clipper/clip.py "LINK" 1:02 +15 --vertical --mute --headline "Line one | line two"`
- Update to the newest version (keeps clips and settings):
  ```
  cd "/Volumes/Mac Memory Drive"
  curl -L -o clipmaker.zip https://github.com/rollandfall-web/Tv/archive/refs/heads/claude/youtube-clip-maker-lyx2h0.zip
  unzip -o -q clipmaker.zip && cp -R Tv-claude-youtube-clip-maker-lyx2h0/ ClipMaker/
  rm -rf Tv-claude-youtube-clip-maker-lyx2h0 clipmaker.zip
  ```
- Errors print a "How to fix" line; follow it.

## StarNet AI crew

Agents in StarNet (starnetos.com): OPPEN (lead, clip-director skill),
RESEARCHER (clip-maker + streamer-outreach skills, has a terminal), SCRIPTWRITER
(streamer-outreach skill). Skills live in `clipper/skills/`.

**The agents have repeatedly made things up** (follower counts, quotes, a
"verified" report whose screenshots never existed, calling campaigns approved).
Treat every agent report as unverified until the commander or a file on disk
confirms it. Good uses for them: running the Clip Maker (checkable: the file is
in Clips/ or not) and drafting captions.

## Approvals and outreach (`clipper/outreach.py`)

- One folder per streamer or campaign in `Outreach/`, with `evidence/` screenshots.
- **Only the commander approves**: `python3 clipper/outreach.py approve "NAME"`
  opens the proof screenshot and a pop-up they click. The only approved list is
  `Outreach/approved.md`. `status ... approved` always refuses. `verify`,
  `list` and `tracker` reset anything marked approved without the commander.
- `python3 clipper/outreach.py verify` shows who's approved and who lacks proof.

## Campaigns (as of Nov 18, 2026)

| Campaign | Where | State | Key rules |
|---|---|---|---|
| Tokyo Girl (Placements) | Whop / Content Rewards | Joined; clip 1 (heist chase) posted on TikTok and submitted | TikTok + Reels only. Official Tokyo Girl sound as main audio, no talking (make clips with --mute). Caption must include "Song: Tokyo Girl by @Passive" (IG: @PassiveBand). Official Rockstar footage only, no trailer text/logos. Paid-content disclosure on. $0.70/1K, $2 min, $35 max. |
| Lacy GTA 6 marathon | Clip Money (reachclipping.com/LACYGTA) | Commander reviewing / joining | Lacy must be the focus; caption or text must say LACY and use #LACY; no logos; positive only; 50%+ English-speaking audience; pool campaign (only approved videos, total view requirement). Ends when the marathon ends. |
| Lysium | Content Rewards | Applied, sample sent in Support chat, no reply yet | NoPixel V streams only, handle in clip (--credit "twitch.tv/Lysium"), 30-60 s with context, no drama baiting. Don't post until approved. |
| Gattouz x GTA VI x 1WIN | Content Rewards | Joined but advised to SKIP | 1WIN gambling branding must stay visible (account and legal risk); $0.35/1K with $35 min = needs 100K views per clip to pay anything. |
| SypherPK | Content Rewards | Not joined, not approved | Fortnite, off-niche. Agents falsely called it approved. |

## Rules that always apply

- Only clip streamers who approved it or campaigns the commander joined.
- Read each campaign brief before clipping; follow it exactly.
- No bought views, bots, paid boosting or reposting other clippers' edits.
- Skip campaigns that require gambling, betting, crypto-trading or "free money" branding.
- Post 1-3 times a day per platform, evenings US time; reply to early comments.
- Check analytics (top countries, watch time) after 2-3 days.

## Where to pick up

1. Help the commander clip Lacy's marathon (get the VOD link from his channel's
   Videos tab, use the app with Focus "funny, no way, oh my god, chase, cops",
   captions on, caption with LACY and #LACY).
2. Keep posting Tokyo Girl edits (Vice City views, Jason & Lucia, hype) and check
   Whop > Submissions for approvals or rejections.
3. Watch for Lysium's reply; when a campaign accepts, the commander saves a
   screenshot and runs `outreach.py approve`.
4. Find smaller GTA streamers (Twitch GTA V category, 20-500 viewers) and draft
   permission messages.
