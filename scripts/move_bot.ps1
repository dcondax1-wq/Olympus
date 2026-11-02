<#
MOVE THE BOT to another PC (owner 2026-11-01: run the bots on the main PC instead of the Surface). Two PCs must never run
the bot on the same accounts (double orders), so the old PC is retired in the same step that packs its state.

OLD PC (the Surface), double-click MOVE_BOT.bat, choose 1 = "pack and retire this PC":
  - refuses on weekdays 01:15-16:05 ET (the bot may be trading); do it after the close
  - stops the bot (scripts\stop_bot.ps1: the server, the supervisor, auto-start cleared)
  - turns auto-resume off (python -m engine.ninjatrader --disable-auto-resume)
  - removes the start-at-logon tasks (LiquidityEngine, LiquidityEngineOps) and the LE START Startup shortcut
  - packs the bot's own state: data\ (accounts, eval anchor, ledgers, journal, bar archive, auto-resume record) and
    .env.local.ps1 (the live switch) into OneDrive\BOT_MOVE\le-bot-state-<date>.zip (Desktop when there is no OneDrive),
    plus this script and MOVE_BOT.bat so the new PC has them (the repo is private)
NEW PC (the main PC), double-click MOVE_BOT.bat from OneDrive\BOT_MOVE, choose 2 = "set this PC up":
  - installs Git and Python 3.12 with winget when missing
  - clones the bot into %USERPROFILE%\nq-liquidity-engine (GitHub asks you to sign in once)
  - restores the packed state into it, installs the Python packages and starts ONE_TIME_SETUP.bat (power, logon tasks,
    icons, auto-update, the bot)
Still by hand on the new PC: NinjaTrader 8 installed and logged in, the MFFU connection, AT Interface on, and the MNQ
12-26 5-minute chart (30 days) with LE_BarFeed (ninjatrader\LE_BarFeed.cs: NinjaScript Editor, F5).

  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\move_bot.ps1 -Pack [-DryRun]
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\move_bot.ps1 -NewPC [-Zip <path>] [-DryRun]
#>
param([switch]$Pack, [switch]$NewPC, [string]$Zip = "", [switch]$DryRun, [switch]$Force)

$ErrorActionPreference = 'Continue'
$Repo = 'https://github.com/demetrades2000-coder/nq-liquidity-engine.git'
function Say([string]$Kind, [string]$Text) {
    $c = 'Gray'; if ($Kind -eq 'OK') { $c = 'Green' } elseif ($Kind -eq 'FIX') { $c = 'Red' } elseif ($Kind -eq 'SKIP') { $c = 'Yellow' }
    Write-Host "  [$Kind] $Text" -ForegroundColor $c
}
function Get-ET { try { return [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Eastern Standard Time') } catch { return [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'America/New_York') } }
function Is-TradingWindow([DateTime]$Et) {
    if ($Et.DayOfWeek -eq 'Saturday' -or $Et.DayOfWeek -eq 'Sunday') { return $false }
    $m = $Et.Hour * 60 + $Et.Minute
    return ($m -ge 75 -and $m -lt 965)
}
function Get-MoveDir {
    if ($env:OneDrive -and (Test-Path -LiteralPath $env:OneDrive)) { return (Join-Path $env:OneDrive 'BOT_MOVE') }
    $dt = [Environment]::GetFolderPath('Desktop'); if (-not $dt) { $dt = $HOME }
    return (Join-Path $dt 'BOT_MOVE')
}
function Is-BotFolder([string]$Dir) { return ($Dir -and (Test-Path -LiteralPath (Join-Path $Dir 'server.py')) -and (Test-Path -LiteralPath (Join-Path $Dir 'engine\ninjatrader.py'))) }
function Find-Python([string]$BotDir) {
    $c = @((Join-Path $BotDir '.venv\Scripts\python.exe'), (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'))
    foreach ($p in $c) { if ($p -and (Test-Path -LiteralPath $p)) { return $p } }
    $g = Get-Command python -ErrorAction SilentlyContinue; if ($g) { return $g.Source }
    $g = Get-Command py -ErrorAction SilentlyContinue; if ($g) { return $g.Source }
    return $null
}
# what the pack holds: the bot's own state only, i.e. data\ files git does not track (accounts, eval anchor, ledgers,
# journal, bar archive, auto-resume record) and the live switch .env.local.ps1. Never the code or the tracked price history:
# the new PC clones those.
function Pack-Items([string]$BotDir) {
    $rel = @()
    Push-Location $BotDir
    try {
        $rel += @(& git ls-files --others --exclude-standard -- data 2>$null)
        $rel += @(& git ls-files --others --ignored --exclude-standard -- data 2>$null)
    } finally { Pop-Location }
    if (Test-Path -LiteralPath (Join-Path $BotDir '.env.local.ps1')) { $rel += '.env.local.ps1' }
    return ,@($rel | Where-Object { $_ -and $_ -notmatch '__pycache__|\.pyc$' } | Sort-Object -Unique)
}
function Stage-Pack([string]$BotDir, [string[]]$Rel, [string]$Stage) {
    foreach ($r in $Rel) {
        $src = Join-Path $BotDir $r; $dst = Join-Path $Stage $r
        $pd = Split-Path -Parent $dst; if (-not (Test-Path -LiteralPath $pd)) { New-Item -ItemType Directory -Path $pd -Force | Out-Null }
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
}

if (-not $Pack -and -not $NewPC) {
    Write-Host ""
    Write-Host "MOVE THE BOT" -ForegroundColor Cyan
    Write-Host "  1 = pack and retire THIS PC (the old one: the Surface)"
    Write-Host "  2 = set THIS PC up (the new one: the main PC)"
    $a = Read-Host "Type 1 or 2 and press Enter"
    if ($a -eq '1') { $Pack = $true } elseif ($a -eq '2') { $NewPC = $true } else { Say 'SKIP' 'Nothing chosen: nothing changed.'; exit 0 }
}

# ================================================================== old PC: pack and retire
if ($Pack) {
    $Bot = Split-Path -Parent $PSScriptRoot
    if (-not (Is-BotFolder $Bot)) { Say 'FIX' "Run this from the bot folder (no server.py in $Bot)."; exit 1 }
    if ((Is-TradingWindow (Get-ET)) -and -not $Force) { Say 'FIX' 'Weekdays 01:15-16:05 ET the bot may be trading: nothing changed. Run it again after 4:05 PM ET.'; exit 1 }
    $dir = Get-MoveDir
    Say '..' "Retiring this PC as the trading PC and packing its state into $dir"
    if (-not $DryRun) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Bot 'scripts\stop_bot.ps1')
        Say 'OK' 'Bot stopped (auto-start cleared)'
        $py = Find-Python $Bot
        if ($py) { Push-Location $Bot; & $py -m engine.ninjatrader --disable-auto-resume; Pop-Location; Say 'OK' 'Auto-resume off' } else { Say 'FIX' 'Python not found: auto-resume could not be turned off' }
        foreach ($t in @('LiquidityEngine', 'LiquidityEngineOps')) {
            try { Unregister-ScheduledTask -TaskName $t -Confirm:$false -ErrorAction Stop; Say 'OK' "Start-at-logon task $t removed" } catch { Say 'SKIP' "Task $t not there (or needs Administrator)" }
        }
        $su = [Environment]::GetFolderPath('Startup')
        if ($su) { Get-ChildItem -LiteralPath $su -Filter '*LE START*' -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force; Say 'OK' "Startup shortcut $($_.Name) removed" } }
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        $zipPath = Join-Path $dir ("le-bot-state-" + (Get-Date -Format 'yyyyMMdd-HHmm') + ".zip")
        $rel = Pack-Items $Bot
        $stage = Join-Path ([IO.Path]::GetTempPath()) ('le-move-' + [guid]::NewGuid())
        Stage-Pack $Bot $rel $stage
        Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath -Force
        Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
        Say 'OK' "$($rel.Count) state files packed"
        Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $dir 'move_bot.ps1') -Force
        Copy-Item -LiteralPath (Join-Path $Bot 'MOVE_BOT.bat') -Destination (Join-Path $dir 'MOVE_BOT.bat') -Force
        Say 'OK' "Packed: $zipPath ($([math]::Round((Get-Item $zipPath).Length / 1MB, 1)) MB)"
    } else { $rel = Pack-Items $Bot; Say '..' ("Dry run: would stop the bot, turn auto-resume off, remove the logon tasks and pack $($rel.Count) state files: " + (($rel | Select-Object -First 12) -join ', ')) }
    Say 'OK' 'This PC no longer starts or resumes the bot. On the main PC: open the BOT_MOVE folder, double-click MOVE_BOT.bat, choose 2.'
    exit 0
}

# ================================================================== new PC: set up
if ($NewPC) {
    $here = $PSScriptRoot
    if (-not $Zip) { $z = Get-ChildItem -LiteralPath $here -Filter 'le-bot-state-*.zip' -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1; if ($z) { $Zip = $z.FullName } }
    if (-not $Zip -or -not (Test-Path -LiteralPath $Zip)) { Say 'FIX' "No le-bot-state-*.zip next to this script ($here): pack the old PC first (choose 1 there)."; exit 1 }
    Say 'OK' "State pack: $Zip"
    foreach ($w in @(@('git', 'Git.Git'), @('python', 'Python.Python.3.12'))) {
        if (Get-Command $w[0] -ErrorAction SilentlyContinue) { Say 'OK' "$($w[0]) is installed"; continue }
        if ($DryRun) { Say '..' "Would install $($w[1]) with winget"; continue }
        & winget install -e --id $w[1] --accept-package-agreements --accept-source-agreements
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
        if (Get-Command $w[0] -ErrorAction SilentlyContinue) { Say 'OK' "$($w[1]) installed" } else { Say 'FIX' "$($w[1]) not found after installing: close this window, open a new one and run MOVE_BOT.bat again" ; exit 1 }
    }
    $bot = Join-Path $env:USERPROFILE 'nq-liquidity-engine'
    if (Is-BotFolder $bot) { Say 'OK' "Bot folder already here: $bot" }
    elseif ($DryRun) { Say '..' "Would clone $Repo into $bot" }
    else {
        Say '..' 'Getting the bot from GitHub (a GitHub sign-in window may open: sign in)'
        & git clone $Repo $bot
        if (-not (Is-BotFolder $bot)) { Say 'FIX' 'The clone did not work (sign-in?). Send Claude a photo of this window.'; exit 1 }
        Say 'OK' "Bot cloned into $bot"
    }
    if ($DryRun) { Say '..' "Would restore $Zip into $bot, pip install, start ONE_TIME_SETUP.bat"; exit 0 }
    Expand-Archive -LiteralPath $Zip -DestinationPath $bot -Force
    Say 'OK' 'State restored (data\ and the live switch)'
    $py = Find-Python $bot
    if (-not $py) { Say 'FIX' 'Python not found: close this window, open a new one and run MOVE_BOT.bat again'; exit 1 }
    Push-Location $bot; & $py -m pip install -r requirements.txt; Pop-Location
    Say 'OK' 'Packages installed'
    Say '..' 'Next: NinjaTrader on this PC must be logged in with the MFFU connection, AT Interface on, and the MNQ 12-26 5-minute chart (30 days) with LE_BarFeed. Then the setup starts the bot.'
    Start-Process -FilePath (Join-Path $bot 'ONE_TIME_SETUP.bat') -WorkingDirectory $bot
    exit 0
}
