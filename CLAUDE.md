# Notes for Claude Code in this repo

This repo holds the LS Daily Cuts Clip Maker (`clipper/`). Read `clipper/HANDOFF.md`
before working; it explains the project, the campaigns and the rules.

## Standing rule: hand off every change

After every change you commit (code, skills or docs):

1. Update `clipper/HANDOFF.md` ("the team build"): describe the change where it
   belongs (for example the Clip Maker section) and add a dated line to its
   "Change log" section.
2. Commit and push it with the change.
3. In your reply, give the commander:
   - a ready-to-paste message for Cowork (which works on the commander's Mac
     folder `/Volumes/Mac Memory Drive/ClipMaker`): what changed, the update
     command to run first, and what Cowork should check or do;
   - one dated line for the session log in `Outreach/TEAM-STATE.md`.

## Other rules

- The repo is public: never commit the commander's real name, email, Drive links,
  codes, or teammates' names. Those go in the local-only `Outreach/PRIVATE.md`.
- The commander is non-technical: short numbered steps, exact commands, no em dashes
  in files they read.
- Run the tests before pushing (the app, the command line, and any feature touched).
