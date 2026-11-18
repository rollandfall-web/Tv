#!/usr/bin/env python3
"""Outreach folders: one folder per streamer, plus a tracker.

Keeps everything about contacting streamers (research, form answers, drafted
messages, what was said, sample clips) in a fixed layout so people and agents
always know where things are. Nothing here sends anything.

Usage (run from the Clip Maker folder):
  python3 clipper/outreach.py new "Streamer Name" --platform Twitch --link URL
  python3 clipper/outreach.py log "Streamer Name" sent email "First message, offered a sample clip"
  python3 clipper/outreach.py log "Streamer Name" received email "Said yes, clip away"
  python3 clipper/outreach.py approve "Streamer Name"   COMMANDER ONLY: opens a pop-up you click yourself
  python3 clipper/outreach.py revoke "Streamer Name"    take an approval back
  python3 clipper/outreach.py verify           check every profile's evidence; un-approve any without proof
  python3 clipper/outreach.py tracker          rebuild Outreach/tracker.md
  python3 clipper/outreach.py list             print the tracker

Use --root FOLDER to keep Outreach somewhere other than ./Outreach.
"""
import argparse
import datetime
import hashlib
import os
import re
import subprocess
import sys

STATUSES = ["researching", "unverified", "drafted", "sent", "replied", "approved", "declined",
            "no reply"]

# Approvals live only in this ledger, written only by `approve`, which needs the
# commander to click a pop-up on their own screen. A profile that says approved
# without a matching ledger line is reset by every list/tracker/verify run.
LEDGER = "approved.md"
LEDGER_HEAD = """# Approved to clip (commander's list)

Only `python3 clipper/outreach.py approve "NAME"` adds a line here, after the
commander clicks Approve in a pop-up on their own screen. Agents can't approve.
If you see a name here you didn't approve yourself, delete its line.

| Streamer | Approved on | Proof | Fingerprint |
|---|---|---|---|
"""

EVIDENCE_HELP = (
    "Evidence = screenshot files proving the facts, saved in Outreach/<Streamer>/evidence/ "
    "(or ClipMaker/shots/). List them in profile.md as: - **Evidence:** evidence/about-page.png, ...")

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
| `evidence/` | Screenshots that prove the facts in profile.md (about page, permission, replies) |

Statuses: researching, unverified, drafted, sent, replied, approved, declined, no reply.

**Evidence rule:** facts in profile.md only count when a screenshot proves them.
Save screenshots in `evidence/` and list them on the `Evidence:` line. **Only the commander approves.** `outreach.py approve "NAME"` opens a pop-up on
the commander's screen showing the proof; it's added to `approved.md` only when
they click Approve. Agents can't do this. Anyone marked approved any other way is
reset to unverified the next time the tracker runs. The tracker shows MISSING when proof is absent.
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
- **Evidence:**

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
    os.makedirs(os.path.join(path, "evidence"))
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


def evidence_files(root, folder, fields):
    """Evidence paths listed in the profile that really exist on disk."""
    found = []
    clipmaker = os.path.dirname(root)
    for item in re.split(r"[,\n]", fields.get("Evidence", "")):
        item = item.strip().strip("`")
        if not item:
            continue
        for base in (folder, clipmaker, root):
            cand = item if os.path.isabs(item) else os.path.join(base, item)
            if os.path.isfile(cand) and os.path.getsize(cand) > 0:
                found.append(cand)
                break
    return found


def cmd_status(a):
    root = outreach_root(a.root)
    path = streamer_dir(root, a.name)
    if a.status not in STATUSES:
        sys.exit("Status must be one of: " + ", ".join(STATUSES))
    if a.status == "approved":
        sys.exit("Refused: only the commander can approve, by clicking a pop-up on their own "
                 "screen.\nAgents: tell the commander what proof you have and stop. Do not mark "
                 "anyone approved, and do not report them as approved.\n"
                 f"Commander: run  python3 clipper/outreach.py approve \"{a.name}\"  in your own Terminal.")
    profile = os.path.join(path, "profile.md")
    set_field(profile, "Status", a.status)
    if a.status == "declined":
        set_field(profile, "Approved to clip", "no")
    build_tracker(root)
    print(f"{a.name}: {a.status}")


def fingerprint(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def read_ledger(root):
    """{folder: (date, proof path, fingerprint)} from approved.md."""
    out = {}
    path = os.path.join(root, LEDGER)
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 4 and cells[0] not in ("Streamer", "---") and not cells[0].startswith("-"):
                out[cells[0]] = (cells[1], cells[2].strip("`"), cells[3].strip("`"))
    return out


def write_ledger(root, entries):
    rows = "".join(f"| {k} | {d} | `{p}` | `{h}` |\n" for k, (d, p, h) in sorted(entries.items()))
    with open(os.path.join(root, LEDGER), "w", encoding="utf-8") as fh:
        fh.write(LEDGER_HEAD + rows)


def approval_valid(root, folder, entry):
    """A ledger line counts only if its proof file still exists, unchanged."""
    if not entry:
        return False
    _, proof, fp = entry
    cand = proof if os.path.isabs(proof) else os.path.join(root, folder, proof)
    return os.path.isfile(cand) and fingerprint(cand) == fp


def ask_commander(name, proof):
    """Show a pop-up on the commander's screen. True only if a person clicks Approve."""
    msg = (f"Approve {name} to be clipped?\n\nProof: {os.path.basename(proof)}\n\n"
           "Only click Approve if YOU saw their permission (their reply or the campaign "
           "accepting you) with your own eyes. If an agent asked you to click this, check first.")
    if sys.platform == "darwin":
        subprocess.run(["open", proof], check=False)
        script = ('display dialog ' + _applescript(msg) + ' with title "Clip Maker approval" '
                  'buttons {"Cancel", "Approve"} default button "Cancel" cancel button "Cancel" '
                  'with icon caution')
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        return r.returncode == 0 and "Approve" in r.stdout
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    print(msg)
    try:
        typed = input(f'Type the streamer name ({name}) to approve, or press Enter to cancel: ')
    except EOFError:
        return False
    return typed.strip().lower() == name.strip().lower()


def _applescript(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def cmd_approve(a):
    root = outreach_root(a.root)
    path = streamer_dir(root, a.name)
    folder = os.path.basename(path)
    profile = os.path.join(path, "profile.md")
    proofs = evidence_files(root, path, get_fields(profile))
    if a.proof:
        cand = a.proof if os.path.isabs(a.proof) else os.path.join(path, a.proof)
        proofs = [cand] if os.path.isfile(cand) else []
    if not proofs:
        sys.exit(f"Refused: {a.name} has no proof on disk. Save a screenshot of their permission "
                 f"(their reply, or the campaign accepting you) in {os.path.join(path, 'evidence')} "
                 "and list it on the profile's Evidence: line, or pass --proof FILE.")
    proof = proofs[-1]
    if not ask_commander(a.name, proof):
        sys.exit("Not approved: the commander didn't click Approve. Nothing changed.")
    entries = read_ledger(root)
    rel = os.path.relpath(proof, path)
    entries[folder] = (datetime.date.today().isoformat(), rel, fingerprint(proof))
    write_ledger(root, entries)
    set_field(profile, "Status", "approved")
    set_field(profile, "Approved to clip", "yes")
    build_tracker(root)
    print(f"{a.name}: approved by the commander (proof: {rel}).")


def cmd_revoke(a):
    root = outreach_root(a.root)
    path = streamer_dir(root, a.name)
    entries = read_ledger(root)
    entries.pop(os.path.basename(path), None)
    write_ledger(root, entries)
    profile = os.path.join(path, "profile.md")
    set_field(profile, "Status", "unverified")
    set_field(profile, "Approved to clip", "no")
    build_tracker(root)
    print(f"{a.name}: approval removed.")


def enforce_approvals(root):
    """Reset every profile that claims approval without a valid commander ledger line."""
    ledger = read_ledger(root)
    reset = []
    for entry in sorted(os.listdir(root), key=str.lower):
        profile = os.path.join(root, entry, "profile.md")
        if not os.path.isfile(profile):
            continue
        f = get_fields(profile)
        claims = f.get("Status") == "approved" or f.get("Approved to clip", "").lower().startswith("yes")
        valid = approval_valid(root, entry, ledger.get(entry))
        if claims and not valid:
            set_field(profile, "Status", "unverified")
            set_field(profile, "Approved to clip", "no")
            reset.append(entry)
        elif valid and not claims:
            set_field(profile, "Status", "approved")
            set_field(profile, "Approved to clip", "yes")
    return reset


def cmd_verify(a):
    root = outreach_root(a.root)
    ensure_root(root)
    downgraded = enforce_approvals(root)
    missing, ok = [], []
    for entry in sorted(os.listdir(root), key=str.lower):
        folder = os.path.join(root, entry)
        profile = os.path.join(folder, "profile.md")
        if not os.path.isfile(profile):
            continue
        f = get_fields(profile)
        if evidence_files(root, folder, f):
            ok.append(entry)
            continue
        missing.append(entry)
    build_tracker(root, enforce=False)
    approved = sorted(k for k, v in read_ledger(root).items() if approval_valid(root, k, v))
    print(f"With evidence ({len(ok)}): " + (", ".join(ok) or "none"))
    print(f"MISSING evidence ({len(missing)}): " + (", ".join(missing) or "none"))
    print(f"APPROVED by the commander ({len(approved)}): " + (", ".join(approved) or "none"))
    if downgraded:
        print("RESET, approved without the commander (now unverified): " + ", ".join(downgraded))
    print(EVIDENCE_HELP)


def build_tracker(root, enforce=True):
    reset = enforce_approvals(root) if enforce else []
    ledger = read_ledger(root)
    rows = []
    for entry in sorted(os.listdir(root), key=str.lower):
        profile = os.path.join(root, entry, "profile.md")
        if not os.path.isfile(profile):
            continue
        f = get_fields(profile)
        drafts = len([m for m in os.listdir(os.path.join(root, entry, "messages"))
                      if m.endswith(".md")]) if os.path.isdir(os.path.join(root, entry, "messages")) else 0
        proof = len(evidence_files(root, os.path.join(root, entry), f))
        rows.append((entry, f.get("Status", ""), f.get("Platform", ""),
                     f.get("Clipping program", ""), f.get("Best contact", ""),
                     f.get("Last contact", ""),
                     "YES (commander)" if approval_valid(root, entry, ledger.get(entry)) else "no",
                     f"ok ({proof})" if proof else "MISSING", str(drafts)))
    order = {s: i for i, s in enumerate(["approved", "replied", "sent", "drafted",
                                          "researching", "unverified", "no reply", "declined"])}
    rows.sort(key=lambda r: (order.get(r[1], 99), r[0].lower()))
    lines = ["# Outreach tracker", "",
             f"Updated {datetime.datetime.now():%Y-%m-%d %H:%M}. Rebuild: `python3 clipper/outreach.py tracker`", "",
             "Evidence MISSING means nothing in that row is proven yet. See README.md.",
             "Approved = YES only when the commander approved it themselves (see approved.md).", "",
             "| Streamer | Status | Platform | Clipping program | Contact | Last contact | Approved | Evidence | Drafts |",
             "|---|---|---|---|---|---|---|---|---|"]
    lines += ["| " + " | ".join(c.replace("|", "/") for c in r) + " |" for r in rows]
    if reset:
        lines += ["", "RESET to unverified (marked approved without the commander): " + ", ".join(reset)]
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
    ap = sub.add_parser("approve", help="COMMANDER ONLY: approve after clicking a pop-up")
    ap.add_argument("name")
    ap.add_argument("--proof", help="screenshot proving permission (default: last Evidence file)")
    ap.set_defaults(fn=cmd_approve)
    rv = sub.add_parser("revoke", help="remove an approval")
    rv.add_argument("name")
    rv.set_defaults(fn=cmd_revoke)
    sub.add_parser("tracker", help="rebuild tracker.md").set_defaults(fn=cmd_tracker)
    sub.add_parser("verify", help="check evidence; un-approve anyone without proof").set_defaults(fn=cmd_verify)
    sub.add_parser("list", help="print the tracker").set_defaults(fn=cmd_list)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
