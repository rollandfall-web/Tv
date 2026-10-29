#!/usr/bin/env bash
# Speed up an Android TV, Google TV, or Amazon Fire TV over the network.
#
# Usage:
#   ./android-tv-speedup.sh <tv-ip-address>          apply speedups
#   ./android-tv-speedup.sh <tv-ip-address> --undo   put everything back
#
# Before running: turn on Developer options and "Network debugging" /
# "ADB debugging" on the TV (see README.md), and install adb on your computer.
set -euo pipefail

TV_IP="${1:-}"
MODE="${2:-apply}"

if [[ -z "$TV_IP" ]]; then
  echo "Usage: $0 <tv-ip-address> [--undo]" >&2
  exit 1
fi

if ! command -v adb >/dev/null 2>&1; then
  echo "adb is not installed. Install 'Android platform-tools' first." >&2
  exit 1
fi

# Recommendation and ad services that are safe to turn off.
# Disabling is reversible with --undo; nothing is deleted.
AD_PACKAGES=(
  com.google.android.tvrecommendations              # Android TV recommendation rows
  com.google.android.leanbacklauncher.recommendations
  com.amazon.device.crashmanager                    # Fire TV crash reporting
  com.amazon.ags.app                                # Fire TV GameCircle
)

tv() { adb -s "$TV_IP:5555" shell "$@"; }

echo "Connecting to $TV_IP ... (accept the prompt on the TV if one appears)"
adb connect "$TV_IP:5555" >/dev/null
adb -s "$TV_IP:5555" wait-for-device

installed="$(tv pm list packages)"

if [[ "$MODE" == "--undo" ]]; then
  for scale in window_animation_scale transition_animation_scale animator_duration_scale; do
    tv settings put global "$scale" 1.0
  done
  for pkg in "${AD_PACKAGES[@]}"; do
    if grep -qx "package:$pkg" <<<"$installed"; then
      tv pm enable "$pkg" >/dev/null && echo "Re-enabled $pkg"
    fi
  done
  echo "Done. Everything is back to normal."
  exit 0
fi

echo "1/3 Making menus snappier (shorter animations)..."
for scale in window_animation_scale transition_animation_scale animator_duration_scale; do
  tv settings put global "$scale" 0.5
done

echo "2/3 Turning off ad and recommendation services..."
for pkg in "${AD_PACKAGES[@]}"; do
  if grep -qx "package:$pkg" <<<"$installed"; then
    tv pm disable-user --user 0 "$pkg" >/dev/null && echo "  Disabled $pkg"
  fi
done

echo "3/3 Clearing app caches to free up storage..."
tv pm trim-caches 999G >/dev/null 2>&1 || echo "  (This TV does not allow cache clearing over adb; skipped.)"

echo
echo "Apps you installed (uninstall any you don't use to free memory):"
tv pm list packages -3 | sed 's/^package:/  /' | sort

echo
echo "Done. Restart the TV now: unplug it for 60 seconds, then plug it back in."
