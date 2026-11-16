---
name: streamer-outreach
description: Research streamers to clip and prepare everything needed to contact them - a folder per streamer with their profile, draft form answers, drafted emails or DMs, a conversation log and sample clips - without ever sending or submitting anything. Use when the commander asks to find streamers to clip, prepare outreach, draft messages to streamers, fill out clipping program forms, or update who said yes.
---

# Streamer outreach

You prepare outreach so the commander can get permission to clip streamers.
**You never send a message, submit a form, sign up for anything, or enter a
password.** You research, write drafts and keep records; the commander sends.

## Where everything lives

The Clip Maker folder (find it as the clip-maker skill describes; on this
station it is usually `/Volumes/Mac Memory Drive/ClipMaker`). Inside it:

```
Outreach/
  about-me.md          the commander's details; use ONLY these in messages
  tracker.md           everyone at a glance (rebuilt by the helper)
  <Streamer>/
    profile.md         research and status
    forms.md           draft answers for forms
    messages/          01-first-contact.md, 02-follow-up.md, ...
    conversation.md    what was sent / received
    samples/           sample clips (never posted)
```

Use the helper from the Clip Maker folder (needs the Workbench). Quote names
with spaces:

```bash
python3 clipper/outreach.py new "Streamer Name" --platform Twitch --link "https://..."
python3 clipper/outreach.py status "Streamer Name" drafted
python3 clipper/outreach.py log "Streamer Name" sent email "One-line summary"
python3 clipper/outreach.py list
```

Without a terminal, create the same files by hand with the same headings.
If `Outreach/about-me.md` has blanks the commander hasn't filled, tell them
once and leave those details out of messages.

## The process, per streamer

1. **Create the folder** with `outreach.py new`.
2. **Research and fill `profile.md`:** platform and channel link, audience size
   (followers or average viewers, with the date you saw it), what their content
   is like, whether they run a clipping program or pay clippers (e.g. on Whop
   Content Rewards or a campaign site) with its link and rules, and their best
   public contact (business email, contact form, Discord server, or a DM
   channel they say they accept). Put every source link under "Sources".
   Only use contact details the streamer published for business or fans; never
   look for private or personal contact information.
3. **Clipping program? Fill `forms.md`.** Open the program's sign-up or
   application form, copy each question, and write a draft answer from
   `about-me.md`. Note which fields need the commander (logins, payment details,
   tax info, ID): write "COMMANDER FILLS IN" for those. Do not submit.
4. **No program? Draft a first message** in `messages/01-first-contact.md`:
   - Top lines: `To:` (address or channel), `Channel:` (email, Discord, form...),
     `Subject:` (for email).
   - Under 80 words, friendly and specific: name one thing about their content,
     offer a free sample clip, say clips credit and link to them, ask if they're
     open to it. Sign with the name in `about-me.md`.
   - Honest: no invented numbers, no pretending to be a fan of things you haven't
     checked, no pressure, no promises about views or money.
5. **Sample clip:** ask the crew member with the clip-maker skill to make one
   vertical clip with captions from a recent video of theirs, saved into
   `Outreach/<Streamer>/samples/` (`-o "Outreach/<Streamer>/samples"`).
   It is for showing them only; never post it.
6. **Set status** to `drafted` and tell the commander it's ready to send.

## After the commander sends or gets a reply

When the commander says they sent something or got a reply, record it:

- `outreach.py log "<Streamer>" sent email "what was sent, one line"`
- `outreach.py log "<Streamer>" received email "what they said, one line"`
- If they said yes: `outreach.py status "<Streamer>" approved`, and add the
  streamer's channels to the approved list the lead keeps in memory, with any
  rules they gave (tags, credit format, platforms) in `profile.md` Notes.
- If they said no: `status ... declined`. Don't contact them again.
- No reply after 7 days: draft **one** polite follow-up as
  `messages/02-follow-up.md`. After that, set `no reply` and stop.

Only record what actually happened; don't guess replies.

## Report

Give the commander: the tracker (`outreach.py list`), which drafts are ready to
send (with their file paths), which forms need their details, and anything
you couldn't find.
