<#
Kalshi to Jarvis, the PC FALLBACK (docs/KALSHI_PUBLISH.md section 2). The normal way is the bot's own server publishing by
itself (tools/kalshi_kit/public/SETUP.md, set up by the kalshi-server chat). Use this only until then: it keeps the
Kalshi numbers on the phone from this PC while the PC is on.

What it does, in order:
  1. finds Python (the NQ bot's) and checks that it can run the PC's srv.py helper (paramiko);
  2. reads the bot's numbers once over SSH (python -m engine.kalshi_publish --ssh --once) and pushes them, read-only;
  3. creates the Task Scheduler task "Kalshi to Jarvis": at logon, no window (pythonw), restarts every minute on failure,
     no time limit, one copy: pythonw -X utf8 -m engine.kalshi_publish --ssh --loop (every 60 s, a push only on a change
     or every 10 min), and starts it.
It never touches trading, the Kalshi bot, its server's files, or the NQ bot's tasks. The server's address stays in
srv.py. Log: %LOCALAPPDATA%\KalshiToJarvis\kalshi_to_jarvis.log

  powershell -ExecutionPolicy Bypass -File .\tools\kalshi_kit\install_windows.ps1
  powershell -ExecutionPolicy Bypass -File .\tools\kalshi_kit\install_windows.ps1 -DryRun
  powershell -ExecutionPolicy Bypass -File .\tools\kalshi_kit\install_windows.ps1 -Remove     (once the server pushes)
Options: -Python <python.exe> (default: LE_PYTHON, else python on PATH), -VmPython <python.exe with paramiko> (default:
the same), -VmHelper <path to srv.py> (default: found under %APPDATA%\Claude\scratch-workspaces).
#>
param(
    [string]$Python = "",
    [string]$VmPython = "",
    [string]$VmHelper = "",
    [switch]$DryRun,
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$TaskName = 'Kalshi to Jarvis'
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)          # the repo: tools\kalshi_kit\ -> ..\..
$User = "$env:USERDOMAIN\$env:USERNAME"

if ($Remove) {
    if ($DryRun) { Write-Host "would remove the task '$TaskName'"; exit 0 }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK]  task '$TaskName' removed (the server keeps publishing by itself if it was set up)"
    exit 0
}

if (-not (Test-Path -LiteralPath (Join-Path $Root 'engine\kalshi_publish.py'))) {
    Write-Host "[FIX] run this from the nq-liquidity-engine folder (engine\kalshi_publish.py not found under $Root)"
    exit 1
}
if (-not $Python) {
    if ($env:LE_PYTHON) { $Python = $env:LE_PYTHON }
    else {
        $cmd = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) { $Python = $cmd.Source }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) {
    Write-Host "[FIX] python not found: pass -Python C:\path\to\python.exe (the one the NQ bot uses)"
    exit 1
}
if ($Python -like '*\WindowsApps\*') { Write-Host "[WARN] python is the Microsoft Store alias ($Python); pass -Python with the real python.exe if the task does nothing" }
$Pyw = Join-Path (Split-Path -Parent $Python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $Pyw)) { $Pyw = $Python }
if (-not $VmPython) { $VmPython = $Python }

# srv.py needs paramiko in the Python that runs it
& $VmPython -c "import paramiko" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FIX] $VmPython has no paramiko, which the PC's srv.py needs. Pass -VmPython with the python that runs srv.py"
    Write-Host "      (the one 'python srv.py check.sh' uses in the Kalshi scratch folder)."
    exit 1
}

$extra = @('--vm-python', "`"$VmPython`"")
if ($VmHelper) { $extra += @('--vm-helper', "`"$VmHelper`"") }
$argLine = "-X utf8 -m engine.kalshi_publish --ssh --loop " + ($extra -join ' ')

if ($DryRun) {
    Write-Host "DRY RUN - nothing pushed or registered. Would:"
    Write-Host "  push once : $Python -X utf8 -m engine.kalshi_publish --ssh --once $($extra -join ' ')"
    Write-Host "  task      : '$TaskName' (runs as $User at logon, only when logged on, not elevated, no window)"
    Write-Host "  program   : $Pyw $argLine"
    Write-Host "  start in  : $Root"
    exit 0
}

Write-Host "Reading the Kalshi bot's numbers on its server (read-only) and pushing them once ..."
Push-Location $Root
try {
    $once = @('-X', 'utf8', '-m', 'engine.kalshi_publish', '--ssh', '--once', '--vm-python', $VmPython)
    if ($VmHelper) { $once += @('--vm-helper', $VmHelper) }
    & $Python @once
    $ok = ($LASTEXITCODE -eq 0)
} finally {
    Pop-Location
}
if (-not $ok) {
    Write-Host "[FIX] the first push did not work (the line above says why). Nothing was registered."
    exit 1
}

$action = New-ScheduledTaskAction -Execute $Pyw -Argument $argLine -WorkingDirectory $Root
$logon = New-ScheduledTaskTrigger -AtLogOn -User $User
$settings = New-ScheduledTaskSettingsSet -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$desc = "Kalshi numbers to the phone (Jarvis), read-only, over the PC's SSH helper. Fallback until the bot's server publishes by itself. Installed $(Get-Date -Format 'yyyy-MM-dd HH:mm') from $Root"
$task = New-ScheduledTask -Action $action -Trigger $logon -Settings $settings -Principal $principal -Description $desc

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
try {
    Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
    Start-ScheduledTask -TaskName $TaskName
} catch {
    Write-Host "[FIX] could not create the task: $($_.Exception.Message)"
    exit 1
}
Write-Host "[OK]  '$TaskName' runs now and at every logon (every 60 s; a push only when the numbers change, else every 10 min)"
Write-Host "      phone reads: https://raw.githubusercontent.com/demetrades2000-coder/nq-dashboard/kalshi/kalshi.json"
Write-Host "      log: $env:LOCALAPPDATA\KalshiToJarvis\kalshi_to_jarvis.log"
Write-Host "      once the bot's server publishes by itself: run this again with -Remove"
