#!/bin/bash
# Double-click to start Clip Maker (Mac). Keep this window open while you use it.
cd "$(dirname "$0")"
# Put the Pythons that usually have yt-dlp first (Homebrew's newest Python often doesn't).
export PATH="/usr/local/bin:/Library/Frameworks/Python.framework/Versions/3.14/bin:/opt/homebrew/bin:$PATH"; hash -r
# Then use the first Python that can actually import yt-dlp.
PY=python3
for c in python3 /Library/Frameworks/Python.framework/Versions/*/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
  if "$c" -c "import yt_dlp" 2>/dev/null; then PY="$c"; break; fi
done
"$PY" clipper/app.py
