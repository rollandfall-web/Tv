# Speed up an Android TV, Google TV, or Amazon Fire TV over the network (Windows).
#
# Easiest way: right-click this file and choose "Run with PowerShell".
# It asks for your TV's IP address and whether to apply or undo.
#
# Or from a PowerShell window:
#   .\android-tv-speedup.ps1 192.168.1.50          apply speedups
#   .\android-tv-speedup.ps1 192.168.1.50 -Undo    put everything back
#
# Before running: turn on Developer options and "USB debugging" on the TV
# (see README.md), and unzip Android platform-tools into this folder.
param(
    [string]$TvIp,
    [switch]$Undo
)

$ErrorActionPreference = 'Continue'

function Finish($code) {
    Read-Host "`nPress Enter to close"
    exit $code
}

# Find adb: on the PATH, next to this script, or in a platform-tools folder here.
$adb = (Get-Command adb -ErrorAction SilentlyContinue).Source
foreach ($candidate in @("$PSScriptRoot\adb.exe", "$PSScriptRoot\platform-tools\adb.exe")) {
    if (-not $adb -and (Test-Path $candidate)) { $adb = $candidate }
}
if (-not $adb) {
    Write-Host "adb was not found. Download Android platform-tools for Windows and"
    Write-Host "unzip it into this folder: $PSScriptRoot"
    Finish 1
}

if (-not $TvIp) {
    $TvIp = Read-Host "Type your TV's IP address (Settings > Network on the TV)"
    $choice = Read-Host "Type 1 to speed up the TV, or 2 to undo a previous run"
    if ($choice -eq '2') { $Undo = $true }
}
$target = "${TvIp}:5555"

# Recommendation and ad services that are safe to turn off.
# Disabling is reversible with -Undo; nothing is deleted.
$adPackages = @(
    'com.google.android.tvrecommendations'               # Android TV recommendation rows
    'com.google.android.leanbacklauncher.recommendations'
    'com.amazon.device.crashmanager'                     # Fire TV crash reporting
    'com.amazon.ags.app'                                 # Fire TV GameCircle
)
$scales = @('window_animation_scale', 'transition_animation_scale', 'animator_duration_scale')

function Tv { & $adb -s $target shell @args }

Write-Host "Connecting to $TvIp ... (choose Allow if a prompt appears on the TV)"
& $adb connect $target | Out-Null
& $adb -s $target wait-for-device

$installed = @(Tv pm list packages | ForEach-Object { $_.Trim() })
if (-not $installed) {
    Write-Host "Could not talk to the TV. Check the IP address and that USB debugging is on."
    Finish 1
}

if ($Undo) {
    foreach ($scale in $scales) { Tv settings put global $scale '1.0' }
    foreach ($pkg in $adPackages) {
        if ($installed -contains "package:$pkg") {
            Tv pm enable $pkg | Out-Null
            Write-Host "Re-enabled $pkg"
        }
    }
    Write-Host "Done. Everything is back to normal."
    Finish 0
}

Write-Host "1/3 Making menus snappier (shorter animations)..."
foreach ($scale in $scales) { Tv settings put global $scale '0.5' }

Write-Host "2/3 Turning off ad and recommendation services..."
foreach ($pkg in $adPackages) {
    if ($installed -contains "package:$pkg") {
        Tv pm disable-user '--user' 0 $pkg | Out-Null
        Write-Host "  Disabled $pkg"
    }
}

Write-Host "3/3 Clearing app caches to free up storage..."
Tv pm trim-caches 999G 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "  (This TV does not allow cache clearing over adb; skipped.)" }

Write-Host "`nApps you installed (uninstall any you don't use to free memory):"
Tv pm list packages '-3' | ForEach-Object { '  ' + ($_ -replace '^package:', '') } | Sort-Object

Write-Host "`nDone. Restart the TV now: unplug it for 60 seconds, then plug it back in."
Finish 0
