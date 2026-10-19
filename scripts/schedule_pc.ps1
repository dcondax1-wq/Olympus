<#
"Acts like it's off": the PC wakes itself before the session, runs the bot (and NinjaTrader) through the day, and
hibernates after the close. Nothing to touch, screen off, no power bill overnight. Free.

Creates two Task Scheduler tasks (times are given in New York time and converted to this PC's clock):
  LiquidityEngineWake   Mon-Fri at -WakeEt (default 01:30 ET; LIT enters from 02:00 ET, 95 of 120 2026 trades before 08:00): wakes the PC ("wake to run"), starts the LiquidityEngine
                        supervisor task (scripts\install_autostart.ps1 must have been run once) and, if -NinjaTrader is
                        given, NinjaTrader 8 (ninjatrader\SETUP.md: auto-connect to the MFFU account on start).
  LiquidityEngineSleep  Mon-Fri at -SleepEt (default 16:35 ET): hibernates the PC, unless the bot still has an open
                        position (then it tries again every 10 minutes until 18:00 ET and gives up).
Also turns hibernation and wake timers on (both need an Administrator PowerShell).

  powershell -ExecutionPolicy Bypass -File .\scripts\schedule_pc.ps1                      # install with the defaults
  ... schedule_pc.ps1 -NinjaTrader "C:\Program Files\NinjaTrader 8\bin\NinjaTrader.exe"   # also start NinjaTrader
  ... schedule_pc.ps1 -DryRun                                                             # show the plan only
  ... schedule_pc.ps1 -Uninstall                                                           # remove both tasks

Wake timers wake a PC from sleep or hibernation, not from a full shutdown. If you shut the PC down instead of letting
the Sleep task hibernate it, turn on "Power On By RTC Alarm" (name varies) in the BIOS for the same time, or just leave
the Sleep task to it. Laptops: keep the lid open or set "lid close" to "do nothing" and plug in the charger.
The cloud monitor (GitHub Actions) alerts your phone when the PC bot is not polling during a session.
#>
param(
    [string]$WakeEt = "01:30",          # LIT (live since 2026-10-18) trades London from 02:00 ET: the old 07:50 missed it
    [string]$SleepEt = "16:35",
    [string]$NinjaTrader = "",
    [int]$Port = 8766,
    [switch]$DryRun,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$PsExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$User = "$env:USERDOMAIN\$env:USERNAME"
$WakeTask, $SleepTask, $BotTask = 'LiquidityEngineWake', 'LiquidityEngineSleep', 'LiquidityEngine'
$Helper = Join-Path $PSScriptRoot 'schedule_pc_run.ps1'

function Convert-EtToLocal([string]$hhmm) {
    # today's ET wall time -> this PC's wall time. Fixed at install: a PC outside the US sees the offset move for a week or
    # three a year (Europe: Oct 25-Nov 1 2026, Mar 14-28 2027): re-run this script after each of those clock changes.
    $et = [TimeZoneInfo]::FindSystemTimeZoneById('Eastern Standard Time')
    $h, $m = $hhmm.Split(':') | ForEach-Object { [int]$_ }
    $todayEt = [DateTime]::SpecifyKind((Get-Date).Date.AddHours($h).AddMinutes($m), 'Unspecified')
    $utc = [TimeZoneInfo]::ConvertTimeToUtc($todayEt, $et)
    return [TimeZoneInfo]::ConvertTimeFromUtc($utc, [TimeZoneInfo]::Local)
}

if ($Uninstall) {
    foreach ($t in @($WakeTask, $SleepTask)) {
        if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) {
            if ($DryRun) { Write-Host "would remove task $t" } else { Unregister-ScheduledTask -TaskName $t -Confirm:$false; Write-Host "removed task $t" }
        } else { Write-Host "task $t not present" }
    }
    exit 0
}

if (-not (Get-ScheduledTask -TaskName $BotTask -ErrorAction SilentlyContinue)) {
    Write-Warning "Task $BotTask is missing: run scripts\install_autostart.ps1 first (the Wake task starts it)."
}
if ($NinjaTrader -and -not (Test-Path -LiteralPath $NinjaTrader)) { throw "NinjaTrader.exe not found at $NinjaTrader" }

$wakeLocal = Convert-EtToLocal $WakeEt
$sleepLocal = Convert-EtToLocal $SleepEt
$days = 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'

$wakeArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Helper`" -Mode wake -Port $Port" + $(if ($NinjaTrader) { " -NinjaTrader `"$NinjaTrader`"" } else { "" })
$sleepArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Helper`" -Mode sleep -Port $Port"
$wakeAction = New-ScheduledTaskAction -Execute $PsExe -Argument $wakeArgs -WorkingDirectory $Root
$sleepAction = New-ScheduledTaskAction -Execute $PsExe -Argument $sleepArgs -WorkingDirectory $Root
$wakeTrig = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $wakeLocal
$sleepTrig = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $sleepLocal
$wakeSet = New-ScheduledTaskSettingsSet -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
$sleepSet = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
$wakeTaskObj = New-ScheduledTask -Action $wakeAction -Trigger $wakeTrig -Settings $wakeSet -Principal $principal `
    -Description "Liquidity Engine: wake the PC and start the bot$(if ($NinjaTrader) { ' + NinjaTrader' }) at $WakeEt ET on weekdays. Installed $stamp"
$sleepTaskObj = New-ScheduledTask -Action $sleepAction -Trigger $sleepTrig -Settings $sleepSet -Principal $principal `
    -Description "Liquidity Engine: hibernate the PC at $SleepEt ET on weekdays unless a position is open. Installed $stamp"

Write-Host "PC time zone : $([TimeZoneInfo]::Local.DisplayName)"
Write-Host "Wake         : $WakeEt ET = $($wakeLocal.ToString('HH:mm')) on this PC, Mon-Fri (wake timer) -> starts task $BotTask$(if ($NinjaTrader) { ' and NinjaTrader' })"
Write-Host "Sleep        : $SleepEt ET = $($sleepLocal.ToString('HH:mm')) on this PC, Mon-Fri -> hibernate unless a position is open"
Write-Host "Runs as      : $User (only when logged on; keep the user logged in, lock the screen if you like)"
if ($DryRun) { Write-Host "Dry run: nothing changed."; exit 0 }

# power settings: hibernation + wake timers (needs Administrator; warn instead of failing when it is not)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {
    & powercfg /hibernate on | Out-Null
    & powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1 | Out-Null
    & powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1 | Out-Null
    & powercfg /setactive SCHEME_CURRENT | Out-Null
    Write-Host "Power        : hibernation on, wake timers enabled (AC and battery)"
} else {
    Write-Warning "Not running as Administrator: could not turn on hibernation / wake timers. Re-run this script from an Administrator PowerShell once, or set Power Options > Advanced > Sleep > Allow wake timers = Enable by hand."
}

foreach ($pair in @(@($WakeTask, $wakeTaskObj), @($SleepTask, $sleepTaskObj))) {
    $name, $obj = $pair
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $name -Confirm:$false }
    Register-ScheduledTask -TaskName $name -InputObject $obj | Out-Null
    $t = Get-ScheduledTask -TaskName $name
    Write-Host ("Task {0,-22} {1}" -f $name, $t.State)
}
Write-Host "Done. Test the wake now: put the PC to sleep and set a one-off trigger a few minutes ahead with"
Write-Host "  Set-ScheduledTask -TaskName $WakeTask -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(3))   (then re-run this script to restore the weekly trigger)"
