<#
Creates the Windows Task Scheduler task "LiquidityEngine" that runs scripts\run_bot.ps1:
  * triggers  : at logon of the current user, and on workstation unlock (same user)
  * principal : current user, "Run only when user is logged on" (interactive: Tailscale + your env work), not elevated
  * settings  : restart on failure 3 x every 1 min, no execution time limit, runs on battery and is not stopped
                when switching to battery, start when available, a second trigger while running is ignored

The OWNER runs this once:   powershell -ExecutionPolicy Bypass -File .\scripts\install_autostart.ps1
Preview without changing anything:                          ... install_autostart.ps1 -DryRun
Remove it again:                                            ... uninstall_autostart.ps1
#>
param(
    [int]$Port = 8766,
    [string]$Python = "",
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$TaskName = 'LiquidityEngine'
$Root = Split-Path -Parent $PSScriptRoot
$RunBot = Join-Path $PSScriptRoot 'run_bot.ps1'
$PsExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$User = "$env:USERDOMAIN\$env:USERNAME"

if (-not $Python) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $Python = $cmd.Source }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) { throw "python not found; pass -Python C:\path\to\python.exe" }
if ($Python -like '*\WindowsApps\*') { Write-Warning "python resolves to the Microsoft Store alias ($Python); pass -Python with the real python.exe" }

$argLine = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$RunBot`" -Port $Port -Python `"$Python`""
$action = New-ScheduledTaskAction -Execute $PsExe -Argument $argLine -WorkingDirectory $Root
$tLogon = New-ScheduledTaskTrigger -AtLogOn -User $User
$cls = Get-CimClass -Namespace 'Root/Microsoft/Windows/TaskScheduler' -ClassName 'MSFT_TaskSessionStateChangeTrigger'
$tUnlock = New-CimInstance -CimClass $cls -ClientOnly -Property @{ StateChange = [uint32]8; UserId = $User; Enabled = $true }  # 8 = SessionUnlock
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew -DontStopOnIdleEnd
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$desc = "Liquidity Engine supervisor: keeps server.py (dashboard + paper bot) running on port $Port. Installed $(Get-Date -Format 'yyyy-MM-dd HH:mm') from $Root"
$task = New-ScheduledTask -Action $action -Trigger @($tLogon, $tUnlock) -Settings $settings -Principal $principal -Description $desc

function Show-Plan {
    Write-Host "Task name   : $TaskName"
    Write-Host "Runs as     : $User (only when logged on, not elevated)"
    Write-Host "Program     : $PsExe"
    Write-Host "Arguments   : $argLine"
    Write-Host "Start in    : $Root"
    Write-Host "Triggers    : at logon of $User; on workstation unlock of $User"
    Write-Host "On failure  : restart every 1 min, up to 3 times"
    Write-Host "Time limit  : none (ExecutionTimeLimit PT0S)"
    Write-Host "Battery     : starts on battery, not stopped when going to battery"
    Write-Host "Overlap     : a new trigger while it runs is ignored (run_bot.ps1 also refuses a second copy)"
}

if ($DryRun) {
    Write-Host "DRY RUN - nothing registered. Would create:"
    Show-Plan
    Write-Host ("Settings XML check: ExecutionTimeLimit={0} RestartCount={1} RestartInterval={2} MultipleInstances={3} DisallowStartIfOnBatteries={4} StopIfGoingOnBatteries={5}" -f `
        $settings.ExecutionTimeLimit, $settings.RestartCount, $settings.RestartInterval, $settings.MultipleInstances, `
        $settings.DisallowStartIfOnBatteries, $settings.StopIfGoingOnBatteries)
    exit 0
}

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Task $TaskName exists: replacing it"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
try {
    Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
} catch {
    Write-Host "Register-ScheduledTask failed: $($_.Exception.Message)"
    Write-Host "If it says 'Access is denied', run this script once from PowerShell opened with 'Run as administrator' (the task still runs as you, not elevated)."
    exit 1
}
$t = Get-ScheduledTask -TaskName $TaskName
Write-Host "CREATED scheduled task:"
Show-Plan
Write-Host ("Registered state: {0}; triggers: {1}" -f $t.State, (($t.Triggers | ForEach-Object { $_.CimClass.CimClassName }) -join ', '))
Write-Host ""
Write-Host "Start it now without logging off:  Start-ScheduledTask -TaskName $TaskName   (after stopping any server already on port $Port)"
Write-Host "Check it:                          powershell -ExecutionPolicy Bypass -File `"$PSScriptRoot\status.ps1`""
