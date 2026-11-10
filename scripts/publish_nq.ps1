<#
PUBLISH_NQ (double-click PUBLISH_NQ.bat). The NQ reporting chain without GitHub (docs\NQ_BOT_BACK.md).

  default   sets up the 15-minute Windows task "OlympusPublishNQ" (runs tools\pc_publish.py with pythonw, no window, only
            while you are signed in), switches the bot to GitHub-free mode (the file %USERPROFILE%\.olympus\no_github: the bot
            writes its heartbeat to logs\pc_hb on this PC instead of pushing to GitHub; it takes effect when the bot next
            starts), then runs one publish right now and shows its six lines.
  -Remove   UNDO: deletes the task and the no_github file (the bot goes back to its old GitHub behaviour at its next start).
            Your Netlify / folder settings in %USERPROFILE%\.olympus stay; nothing else is touched.
  -DryRun   says what it would do, changes nothing.
  -Now      only the one publish (no task, no switch).
It never starts, stops, arms or routes the bot, never touches NinjaTrader or any order, and never prints a token.
Tests: tests\test_win_scripts.py (fake python and schtasks in tests\win_harness).
#>
param(
    [switch]$Remove,
    [switch]$DryRun,
    [switch]$Now,
    [string]$Python = ""
)

$ErrorActionPreference = 'Continue'
trap {
    Write-Host ''
    Write-Host '  [FIX] Something unexpected stopped this: take a photo of this window and send it to Claude.' -ForegroundColor Red
    exit 1
}
$TaskName = 'OlympusPublishNQ'
$Root = Split-Path -Parent $PSScriptRoot
$Script = Join-Path (Join-Path $Root 'tools') 'pc_publish.py'
$Home1 = $env:OLYMPUS_HOME
if (-not $Home1) {
    $up = $env:USERPROFILE; if (-not $up) { $up = $HOME }
    $Home1 = Join-Path $up '.olympus'
}
$Marker = Join-Path $Home1 'no_github'

if ($Remove) {
    if ($DryRun) { Write-Host "DRY RUN - would delete the task $TaskName and the file $Marker"; exit 0 }
    try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch { }
    if (Test-Path -LiteralPath $Marker) { Remove-Item -LiteralPath $Marker -Force -ErrorAction SilentlyContinue }
    Write-Host "[OK]  publish task $TaskName removed, GitHub-free bot mode switched off (applies at the bot's next start)."
    Write-Host '      Your Netlify / folder settings were kept. To publish once by hand: PUBLISH_NQ.bat'
    exit 0
}

if (-not $Python) {
    if ($env:LE_PYTHON) { $Python = $env:LE_PYTHON }
    else {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { $Python = $cmd.Source }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) {
    Write-Host '[FIX] python not found: install Python 3.12 (tick "Add python.exe to PATH"), then double-click PUBLISH_NQ.bat again.'
    exit 1
}
if (-not (Test-Path -LiteralPath $Script)) { Write-Host "[FIX] tools\pc_publish.py is missing in ${Root}: send a photo of this window to Claude."; exit 1 }
$Pyw = Join-Path (Split-Path -Parent $Python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $Pyw)) { $Pyw = $Python }
$argLine = "-X utf8 `"$Script`" --min-interval 10"

if ($DryRun) {
    Write-Host 'DRY RUN - nothing changed. Would:'
    Write-Host "  task      : $TaskName every 15 minutes, only while you are signed in: $Pyw $argLine"
    Write-Host "  start in  : $Root"
    Write-Host "  bot mode  : create $Marker (GitHub-free; applies at the bot's next start)"
    Write-Host '  then      : one publish now (tools\pc_publish.py)'
    exit 0
}

if (-not $Now) {
    try {
        $user = "$env:USERDOMAIN\$env:USERNAME"
        $action = New-ScheduledTaskAction -Execute $Pyw -Argument $argLine -WorkingDirectory $Root
        $every = New-ScheduledTaskTrigger -Once -At '00:00' -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 1)
        $daily = New-ScheduledTaskTrigger -Daily -At '00:00'
        $daily.Repetition = $every.Repetition
        $logon = New-ScheduledTaskTrigger -AtLogOn -User $user
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
        $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
        $task = New-ScheduledTask -Action $action -Trigger @($daily, $logon) -Settings $settings -Principal $principal `
            -Description "OLYMPUS: build the NQ state and site on this PC and publish it (no GitHub). Installed from $Root"
        if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
        Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
        Write-Host "[OK]  task ${TaskName}: publishes every 15 minutes while you are signed in"
    } catch {
        Write-Host "[FIX] could not create the task: $($_.Exception.Message)"
        Write-Host '      Right-click PUBLISH_NQ.bat > Run as administrator once, or send a photo of this window to Claude.'
        exit 1
    }
    try {
        New-Item -ItemType Directory -Force -Path $Home1 | Out-Null
        if (-not (Test-Path -LiteralPath $Marker)) { Set-Content -LiteralPath $Marker -Value 'GitHub-free bot mode (PUBLISH_NQ.bat). Delete this file or run UNDO_PUBLISH_NQ.bat to undo.' }
        Write-Host '[OK]  bot mode: GitHub-free (the bot writes logs\pc_hb on this PC; restart the bot once when the market is closed)'
    } catch { Write-Host "[SKIP] could not write ${Marker}: $($_.Exception.Message)" }
}

Write-Host ''
Write-Host 'Publishing once now (this can take a minute)...'
& $Python -X utf8 $Script
Write-Host ''
Write-Host "Settings folder (outside the repo, never uploaded): $Home1"
exit 0
