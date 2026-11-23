<#
PC REPORT task (tools\bat\BOTS_BACK.bat installs it, tools\bat\UNDO_BOTS_BACK.bat removes it; docs\BOTS_BACK.md).

  default   installs (or replaces) the Windows task "OlympusPCReport": every 15 minutes, and at sign-in, it runs
            tools\pc_report.py --quiet with pythonw (no window), only while you are signed in, at most one at a time. It reads the
            bot's own files on this PC and sends the phone alerts and the site's status to ntfy.sh (free, no account).
  -Remove   deletes the task. Nothing else.
  -DryRun   says what it would do, changes nothing.
It never starts, stops, arms or routes the bot and never touches NinjaTrader or an order.
Tests: tests\test_bots_back.py (LE_BB_T_LOG=<file>: the task is written to that file instead of Task Scheduler).
#>
param(
    [switch]$Remove,
    [switch]$DryRun,
    [string]$Python = ""
)

$ErrorActionPreference = 'Continue'
trap {
    Write-Host '  [FIX] The report task could not be set up: take a photo of this window and send it to Claude.' -ForegroundColor Red
    exit 1
}
$TaskName = 'OlympusPCReport'
$Root = Split-Path -Parent $PSScriptRoot
$Script = [System.IO.Path]::Combine([System.IO.Path]::Combine($Root, 'tools'), 'pc_report.py')

if ($Remove) {
    if ($DryRun) { Write-Host "  DRY RUN - would delete the task $TaskName"; exit 0 }
    if ($env:LE_BB_T_LOG) { Add-Content -LiteralPath $env:LE_BB_T_LOG -Value "TASK REMOVE $TaskName" }
    else { try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch { } }
    Write-Host "  [OK] report task $TaskName removed"
    exit 0
}

if (-not $Python) {
    if ($env:LE_PYTHON) { $Python = $env:LE_PYTHON }
    else {
        $cmd = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) { $Python = $cmd.Source }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) { Write-Host '  [FIX] python not found: the report task was not set up.'; exit 1 }
if (-not (Test-Path -LiteralPath $Script)) { Write-Host '  [FIX] tools\pc_report.py is missing: update the bot folder from the zip first.'; exit 1 }
$Pyw = [System.IO.Path]::Combine((Split-Path -Parent $Python), 'pythonw.exe')
if (-not (Test-Path -LiteralPath $Pyw)) { $Pyw = $Python }
$argLine = "-X utf8 `"$Script`" --quiet --by task"

if ($DryRun) {
    Write-Host "  DRY RUN - would install the task $TaskName every 15 minutes while you are signed in: $Pyw $argLine (start in $Root)"
    exit 0
}

if ($env:LE_BB_T_LOG) {
    Add-Content -LiteralPath $env:LE_BB_T_LOG -Value "TASK REGISTER $TaskName every 15 min: $Pyw $argLine"
    Write-Host "  [OK] 4/5 report task ${TaskName}: every 15 minutes (phone alerts + site status, free ntfy.sh)"
    exit 0
}
try {
    $user = "$env:USERDOMAIN\$env:USERNAME"
    $action = New-ScheduledTaskAction -Execute $Pyw -Argument $argLine -WorkingDirectory $Root
    $every = New-ScheduledTaskTrigger -Once -At '00:00' -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 1)
    $daily = New-ScheduledTaskTrigger -Daily -At '00:00'
    $daily.Repetition = $every.Repetition
    $logon = New-ScheduledTaskTrigger -AtLogOn -User $user
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $task = New-ScheduledTask -Action $action -Trigger @($daily, $logon) -Settings $settings -Principal $principal `
        -Description "OLYMPUS: report the PC bots to the phone without GitHub (ntfy.sh). Installed by tools\bat\BOTS_BACK.bat from $Root"
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
    Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
    Write-Host "  [OK] 4/5 report task ${TaskName}: every 15 minutes (phone alerts + site status, free ntfy.sh)"
} catch {
    Write-Host "  [FIX] 4/5 could not create the report task: $($_.Exception.Message)"
    Write-Host '        Right-click tools\bat\BOTS_BACK.bat > Run as administrator once, or send a photo of this window to Claude.'
    exit 1
}
exit 0
