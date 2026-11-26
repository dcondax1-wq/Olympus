<#
NT_OFF_ONEDRIVE (day-ops2 2026-11-26; the health check's WARN "the NinjaTrader folder is inside OneDrive (syncing can lock order
files)"). One click, no administrator. Two steps, each safe to run twice:
  1. PIN: attrib +P on the NinjaTrader 8 folder ("Always keep on this device"): OneDrive never turns a NinjaTrader file into a
     cloud-only placeholder (the failure that breaks NinjaTrader: a file it cannot open). Nothing moves. Always done.
  2. MOVE (only with -Move, asked by the .bat with Y, NinjaTrader CLOSED, never 01:50-16:00 ET on a weekday, every bot flat):
     the folder's files are copied to %USERPROFILE%\NinjaTrader 8 (outside OneDrive; robocopy, counted and compared), the old
     folder is RENAMED (kept: "NinjaTrader 8.onedrive-backup-<date>") and a junction with the old name points at the new place,
     so NinjaTrader and the bot find everything where they always did. OneDrive does not sync the inside of a junction (Microsoft:
     OneDrive skips symbolic links and junctions); if its icon still shows NinjaTrader 8 syncing, run with -Undo.
  -Undo puts it back exactly (the junction removed, the current files copied back into the original folder name).
It never touches an order, the bot's files or OneDrive's settings. Windows PowerShell 5.1 safe, ASCII only.
#>
param([switch]$Move, [switch]$Undo)
$ErrorActionPreference = 'Stop'
function Say([string]$k, [string]$t) { Write-Host (' [' + $k + '] ' + $t) }
$root = Split-Path -Parent $PSScriptRoot
$docs = [Environment]::GetFolderPath('MyDocuments')
$nt = Join-Path $docs 'NinjaTrader 8'
$target = Join-Path $env:USERPROFILE 'NinjaTrader 8'
$robo = Join-Path ([Environment]::GetFolderPath('System')) 'robocopy.exe'
$cmd = Join-Path ([Environment]::GetFolderPath('System')) 'cmd.exe'

function Is-Junction([string]$p) {
    try { $i = Get-Item -LiteralPath $p -Force; return [bool]($i.Attributes -band [IO.FileAttributes]::ReparsePoint) } catch { return $false }
}
function Not-Now {
    if (Get-Process -Name 'NinjaTrader' -ErrorAction SilentlyContinue) { return 'NinjaTrader is open: close it first (File > Exit)' }
    $et = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Eastern Standard Time')
    $m = $et.Hour * 60 + $et.Minute
    if ($et.DayOfWeek -ne 'Saturday' -and $et.DayOfWeek -ne 'Sunday' -and $m -ge 110 -and $m -lt 960) { return 'trading hours (01:50-16:00 ET): after 16:00 ET' }
    $py = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $py)) { $py = 'python' }
    try {
        $why = & $py -X utf8 -c "import sys; sys.path.insert(0, r'$root'); from engine.autoupdate import files_flat_reason as f; print(f() or '')" 2>$null
        if ($why -and $why.Trim()) { return ('a trade may be open: ' + $why.Trim()) }
    } catch { }
    return $null
}
function Count([string]$p) {
    $f = @(Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue)
    return @($f.Count, (($f | Measure-Object -Property Length -Sum).Sum))
}

if (-not (Test-Path -LiteralPath $nt)) { Say 'OK' "No NinjaTrader 8 folder in Documents ($docs): nothing to do."; exit 0 }
if ($nt -notmatch 'OneDrive' -and -not $Undo) { Say 'OK' 'The NinjaTrader folder is not inside OneDrive: nothing to do.'; exit 0 }

if ($Undo) {
    if (-not (Is-Junction $nt)) { Say 'OK' 'No junction: nothing to undo.'; exit 0 }
    $why = Not-Now; if ($why) { Say 'FIX' ("Not now: " + $why); exit 1 }
    $bak = @(Get-ChildItem -LiteralPath $docs -Directory -Filter 'NinjaTrader 8.onedrive-backup-*' | Sort-Object Name -Descending | Select-Object -First 1)
    & $cmd /c rmdir "$nt"
    if ($bak.Count -eq 1) { Rename-Item -LiteralPath $bak[0].FullName -NewName 'NinjaTrader 8' } else { New-Item -ItemType Directory -Path $nt | Out-Null }
    & $robo $target $nt /E /COPY:DAT /R:2 /W:2 /XJ /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) { Say 'FIX' "Copy back failed (robocopy $LASTEXITCODE): your files are still in $target. Send Claude a photo."; exit 1 }
    Say 'OK' "Back as before: $nt (the copy in $target can be deleted once NinjaTrader runs fine)."
    exit 0
}

# 1. pin
if (-not (Is-Junction $nt)) {
    & attrib.exe +P "$nt" /S /D 2>$null | Out-Null
    Say 'OK' 'NinjaTrader files pinned: OneDrive keeps them on this PC (never cloud-only).'
}
if (-not $Move) { exit 0 }

# 2. move
if (Is-Junction $nt) { Say 'OK' "Already moved: $nt points to $target."; exit 0 }
$why = Not-Now; if ($why) { Say 'FIX' ("Not now: " + $why + '. Nothing moved (the pin above is done).'); exit 1 }
if (Test-Path -LiteralPath $target) { Say 'FIX' "$target already exists: rename it, then run this again."; exit 1 }
$before = Count $nt
& $robo $nt $target /E /COPY:DAT /R:2 /W:2 /XJ /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { Say 'FIX' "Copy failed (robocopy $LASTEXITCODE): nothing changed. Send Claude a photo."; exit 1 }
$after = Count $target
if ($after[0] -lt $before[0] -or $after[1] -lt $before[1]) {
    Say 'FIX' ("Copy incomplete (" + $after[0] + " of " + $before[0] + " files): nothing changed; the copy in $target can be deleted."); exit 1
}
$stamp = (Get-Date).ToString('yyyyMMdd-HHmm')
Rename-Item -LiteralPath $nt -NewName ('NinjaTrader 8.onedrive-backup-' + $stamp)
& $cmd /c mklink /J "$nt" "$target" | Out-Null
if (-not (Is-Junction $nt) -or -not (Test-Path -LiteralPath (Join-Path $nt 'bin'))) {
    Say 'FIX' 'The junction did not work: putting the folder back.'
    if (Test-Path -LiteralPath $nt) { & $cmd /c rmdir "$nt" }
    Rename-Item -LiteralPath (Join-Path $docs ('NinjaTrader 8.onedrive-backup-' + $stamp)) -NewName 'NinjaTrader 8'
    exit 1
}
Say 'OK' ("Moved: NinjaTrader's files are in $target (" + $after[0] + " files); $nt points there. Open NinjaTrader as usual.")
Say '..' ("The old copy stays as 'NinjaTrader 8.onedrive-backup-" + $stamp + "' in Documents: delete it after a week of normal trading.")
exit 0
