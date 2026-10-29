#!/usr/bin/env bash
# Speed up an Android TV, Google TV, or Amazon Fire TV over the network.
#
# Usage:
#   ./android-tv-speedup.sh <tv-ip-address>          apply speedups
#   ./android-tv-speedup.sh <tv-ip-address> --undo   put everything back
#
# Before running: turn on Developer options and "Network debugging" /
# "ADB debugging" on the TV (see README.md), and unzip Android platform-tools
# into this folder (or install adb another way).
set -euo pipefail

TV_IP="${1:-}"
MODE="${2:-apply}"

if [[ -z "$TV_IP" ]]; then
  echo "Usage: $0 <tv-ip-address> [--undo]" >&2
  exit 1
fi

# Find adb: on the PATH, or in a platform-tools folder next to this script.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if command -v adb >/dev/null 2>&1; then
  ADB=adb
elif [[ -x "$SCRIPT_DIR/platform-tools/adb" ]]; then
  ADB="$SCRIPT_DIR/platform-tools/adb"
else
  echo "adb was not found. Download Android platform-tools and unzip it into: $SCRIPT_DIR" >&2
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

tv() { "$ADB" -s "$TV_IP:5555" shell "$@"; }

# Colors only when printing to a terminal.
if [[ -t 1 ]]; then
  C1=$'\033[1;36m' C2=$'\033[1;35m' C3=$'\033[1;33m' C4=$'\033[1;32m' R=$'\033[0m'
else
  C1='' C2='' C3='' C4='' R=''
fi

banner() {
  cat <<EOF
${C2}            \\   /
             \\ /${R}
${C1}    .=====================.
    |  ${C3}.---------------.${C1}  |
    |  ${C3}|${R}  NO MORE ADS  ${C3}|${C1}  |
    |  ${C3}|${R}  FAST TV MODE ${C3}|${C1}  |
    |  ${C3}'---------------'${C1}  |
    '====================='
         _|_       _|_${R}
${C2}     TV Ad Blocker & Speed-Up${R}

EOF
}

celebrate() {
  cat <<EOF

${C3}      *    .  *       .   *    *${R}
${C4}     \\o/  ALL DONE!  Your TV is faster!  \\o/${R}
${C3}    *   .    *    .     *   .     *${R}

EOF
}

banner

echo "Connecting to $TV_IP ... (accept the prompt on the TV if one appears)"
"$ADB" connect "$TV_IP:5555" >/dev/null
"$ADB" -s "$TV_IP:5555" wait-for-device

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

celebrate
echo "Done. Restart the TV now: unplug it for 60 seconds, then plug it back in."
