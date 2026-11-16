#!/usr/bin/env python3
"""Outreach folders: one folder per streamer, plus a tracker.

Keeps everything about contacting streamers (research, form answers, drafted
messages, what was said, sample clips) in a fixed layout so people and agents
always know where things are. Nothing here sends anything.

Usage (run from the Clip Maker folder):
  python3 clipper/outreach.py new "Streamer Name" --platform Twitch --link URL
  python3 clipper/outreach.py log "Streamer Name" sent email "First message, offered a sample clip"
  python3 clipper/outreach.py log "Streamer Name" received email "Said yes, clip away"
  python3 clipper/outreach.py status "Streamer Name" approved
  python3 clipper/outreach.py tracker          rebuild Outreach/tracker.md
  python3 clipper/outreach.py list             print the tracker

Use --root FOLDER to keep Outreach somewhere other than ./Outreach.
"""
import argparse
import datetime
import os
import re
import sys

STATUSES = ["researching", "drafted", "sent", "replied", "approved", "declined", "no reply"]

ABOUT_ME = """# About me (the clipper)

Agents: use ONLY the details on this page when writing to streamers. Never
invent followers, views, results or experience. If something below is blank,
leave it out of the message.

- **Name to sign messages with:**
- **Clipping channel name:** Los Santos Daily
- **TikTok:**
- **YouTube:**
- **Instagram:**
- **Email to reply to:**
- **Example clips (links):**
- **What I offer:** vertical Shorts/TikToks of their best moments with captions,
  posted on my channels with credit and a link to them. Free sample first.
- **Anything to avoid saying:**
"""

README = """# Outreach

One folder per streamer. Agents research and draft; **the commander sends every
message and submits every form**.

| File | What's in it |
|---|---|
| `profile.md` | Research: platform, links, audience, content, clipping program, best contact, status |
| `forms.md` | Draft answers for sign-up or application forms (to copy in by hand) |
| `messages/` | Drafted emails/DMs, numbered: `01-first-contact.md`, `02-follow-up.md`, ... |
| `conversation.md` | Log of what was sent and what they replied, newest last |
| `samples/` | Sample clips made from their videos (not posted) |

Statuses: researching, drafted, sent, replied, approved, declined, no reply.
`tracker.md` lists everyone; rebuild it with `python3 clipper/outreach.py tracker`.
"""

PROFILE = """# {name}

- **Status:** researching
- **Platform:** {platform}
- **Channel link:** {link}
- **Audience:**
- **Content:**
- **Clipping program:** unknown
- **Program link:**
- **Best contact:**
- **Contact address:**
- **Last contact:**
- **Approved to clip:** no

## Notes

## Sources
"""

FORMS = """# Forms for {name}

Draft answers only. The commander fills in and submits forms themselves; agents
never submit forms, sign up, or enter passwords.

<!-- For each form:
## Form: NAME OF PROGRAM / FORM
Link:
| Question | Draft answer |
|---|---|
-->
"""

CONVERSATION = """# Conversation with {name}

Newest last. Only record what was actually sent or received.

| Date | Direction | Channel | Summary |
|---|---|---|---|
"""


def outreach_root(root):
    return os.path.abspath(root or "Outreach")


def folder_name(name):
    clean = re.sub(r'[\\\\/:*?"<>|]+', "", name).strip().strip(".")
    return clean or "Unnamed"


def ensure_root(root):
    os.makedirs(root, exist_ok=True)
    for fname, text in (("about-me.md", ABOUT_ME), ("README.md", README)):
        path = os.path.join(root, fname)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)


def streamer_dir(root, name):
    path = os.path.join(root, folder_name(name))
    if not os.path.isdir(path):
        sys.exit(f"No outreach folder for {name!r}. Create it with: outreach.py new \"{name}\"")
    return path


def cmd_new(a):
    root = outreach_root(a.root)
    ensure_root(root)
    path = os.path.join(root, folder_name(a.name))
    if os.path.exists(path):
        print(f"Already exists: {path}")
        return
    os.makedirs(os.path.join(path, "messages"))
    os.makedirs(os.path.join(path, "samples"))
    files = {"profile.md": PROFILE.format(name=a.name, platform=a.platform or "", link=a.link or ""),
             "forms.md": FORMS.format(name=a.name),
             "conversation.md": CONVERSATION.format(name=a.name)}
    for fname, text in files.items():
        with open(os.path.join(path, fname), "w", encoding="utf-8") as fh:
            fh.write(text)
    build_tracker(root)
    print(f"Created: {path}")


def set_field(path, field, value):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    pattern = rf"^(- \*\*{re.escape(field)}:\*\*).*$"
    if re.search(pattern, text, flags=re.M):
        text = re.sub(pattern, lambda m: f"{m.group(1)} {value}", text, count=1, flags=re.M)
    else:
        text = text.replace("\n## Notes", f"- **{field}:** {value}\n\n## Notes", 1)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def get_fields(path):
    fields = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^- \*\*(.+?):\*\*\s*(.*)$", line.rstrip())
            if m:
                fields[m.group(1).strip()] = m.group(2).strip()
    return fields


def cmd_log(a):
    root = outreach_root(a.root)
    path = streamer_dir(root, a.name)
    today = datetime.date.today().isoformat()
    summary = a.summary.replace("|", "/").replace("\n", " ")
    with open(os.path.join(path, "conversation.md"), "a", encoding="utf-8") as fh:
        fh.write(f"| {today} | {a.direction} | {a.channel} | {summary} |\n")
    profile = os.path.join(path, "profile.md")
    set_field(profile, "Last contact", f"{today} ({a.direction}, {a.channel})")
    status = get_fields(profile).get("Status", "")
    if a.direction == "sent" and status in ("", "researching", "drafted"):
        set_field(profile, "Status", "sent")
    elif a.direction == "received" and status in ("", "researching", "drafted", "sent", "no reply"):
        set_field(profile, "Status", "replied")
    build_tracker(root)
    print(f"Logged for {a.name}.")


def cmd_status(a):
    root = outreach_root(a.root)
    path = streamer_dir(root, a.name)
    if a.status not in STATUSES:
        sys.exit("Status must be one of: " + ", ".join(STATUSES))
    profile = os.path.join(path, "profile.md")
    set_field(profile, "Status", a.status)
    if a.status == "approved":
        set_field(profile, "Approved to clip", "yes")
    elif a.status == "declined":
        set_field(profile, "Approved to clip", "no")
    build_tracker(root)
    print(f"{a.name}: {a.status}")


def build_tracker(root):
    rows = []
    for entry in sorted(os.listdir(root), key=str.lower):
        profile = os.path.join(root, entry, "profile.md")
        if not os.path.isfile(profile):
            continue
        f = get_fields(profile)
        drafts = len([m for m in os.listdir(os.path.join(root, entry, "messages"))
                      if m.endswith(".md")]) if os.path.isdir(os.path.join(root, entry, "messages")) else 0
        rows.append((entry, f.get("Status", ""), f.get("Platform", ""),
                     f.get("Clipping program", ""), f.get("Best contact", ""),
                     f.get("Last contact", ""), f.get("Approved to clip", ""), str(drafts)))
    order = {s: i for i, s in enumerate(["approved", "replied", "sent", "drafted",
                                          "researching", "no reply", "declined"])}
    rows.sort(key=lambda r: (order.get(r[1], 99), r[0].lower()))
    lines = ["# Outreach tracker", "",
             f"Updated {datetime.datetime.now():%Y-%m-%d %H:%M}. Rebuild: `python3 clipper/outreach.py tracker`", "",
             "| Streamer | Status | Platform | Clipping program | Contact | Last contact | Approved | Drafts |",
             "|---|---|---|---|---|---|---|---|"]
    lines += ["| " + " | ".join(c.replace("|", "/") for c in r) + " |" for r in rows]
    with open(os.path.join(root, "tracker.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return lines


def cmd_tracker(a):
    root = outreach_root(a.root)
    ensure_root(root)
    build_tracker(root)
    print(f"Updated {os.path.join(root, 'tracker.md')}")


def cmd_list(a):
    root = outreach_root(a.root)
    ensure_root(root)
    print("\n".join(build_tracker(root)))


def main():
    p = argparse.ArgumentParser(description="Outreach folders for streamers.")
    p.add_argument("--root", help="Outreach folder (default: ./Outreach)")
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", help="create a streamer's folder")
    n.add_argument("name")
    n.add_argument("--platform")
    n.add_argument("--link")
    n.set_defaults(fn=cmd_new)
    lg = sub.add_parser("log", help="record a sent or received message")
    lg.add_argument("name")
    lg.add_argument("direction", choices=["sent", "received"])
    lg.add_argument("channel", help="email, discord, twitter, form, ...")
    lg.add_argument("summary")
    lg.set_defaults(fn=cmd_log)
    st = sub.add_parser("status", help="set a streamer's status")
    st.add_argument("name")
    st.add_argument("status")
    st.set_defaults(fn=cmd_status)
    sub.add_parser("tracker", help="rebuild tracker.md").set_defaults(fn=cmd_tracker)
    sub.add_parser("list", help="print the tracker").set_defaults(fn=cmd_list)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
