<#
Turns a spare Windows PC (a Surface, say) into the always-on trading box: never sleeps while plugged in, screen off,
comes back by itself after a reboot or a Windows update, starts the bot (and NinjaTrader) at logon, and reports a
heartbeat to the cloud so your phone is alerted if it ever goes quiet.

Run ONCE in an Administrator PowerShell in the project folder:
  powershell -ExecutionPolicy Bypass -File .\scripts\setup_dedicated_pc.ps1 -NinjaTrader "C:\Program Files\NinjaTrader 8\bin\NinjaTrader.exe"
  ... -DryRun     show the checks and the plan, change nothing

What it does: checks the machine (64-bit, RAM, disk, Windows S mode, git, python), power plan (AC: never sleep or
hibernate, screen off after 10 min, lid close = nothing, wake timers on), Windows Update active hours 01:00-17:00 New
York time (converted to this PC's clock; LIT trades from 02:00 ET, so restarts must land 17:00-01:00 ET) plus "no automatic
restart while someone is signed in", installs the LiquidityEngine logon task (install_autostart.ps1), a NinjaTrader Startup
shortcut, and prints what you still do by hand: automatic sign-in (Microsoft's free Autologon tool), NinjaTrader's
"connect on startup", and MFFU's written OK for automation. Details: scripts/PC_OFF_OPTIONS.md (option E).
#>
param(
    [string]$NinjaTrader = "",
    [int]$Port = 8766,
    [switch]$DryRun
)
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$warn = @()

Write-Host "== Machine check"
$cs = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem
$arch = $env:PROCESSOR_ARCHITECTURE
$ramGb = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
$disk = Get-PSDrive -Name ($Root.Substring(0, 1)) -ErrorAction SilentlyContinue
$freeGb = if ($disk) { [math]::Round($disk.Free / 1GB, 1) } else { -1 }
Write-Host ("Model       : {0} {1}" -f $cs.Manufacturer, $cs.Model)
Write-Host ("Windows     : {0} ({1}) build {2}" -f $os.Caption, $arch, $os.BuildNumber)
Write-Host ("RAM         : {0} GB   Disk free: {1} GB" -f $ramGb, $freeGb)
if ($arch -ne 'AMD64') { $warn += "CPU is $arch, not 64-bit x86: NinjaTrader 8 needs x64 Windows (Surface Pro X / ARM runs it only in emulation; Surface RT / Surface 2 cannot run it at all)." }
if ($ramGb -lt 4) { $warn += "Only $ramGb GB RAM: NinjaTrader wants 4 GB (8 GB recommended). Keep ONE chart open and close everything else." }
elseif ($ramGb -lt 8) { $warn += "$ramGb GB RAM is workable: one NinjaTrader chart, no Market Analyzer, no browser left open." }
if ($freeGb -ge 0 -and $freeGb -lt 10) { $warn += "Less than 10 GB free on the project drive: clear space (logs, downloads) or the bot's data refresh will fail." }
try {
    $sMode = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CI\Policy' -Name SkuPolicyRequired -ErrorAction Stop).SkuPolicyRequired
    if ($sMode -eq 1) { $warn += "Windows is in S mode: python and NinjaTrader cannot run. Settings > System > Activation > 'Switch to Windows 11 Home/Pro' (free, one-way)." }
} catch { }
foreach ($tool in @('git', 'python')) {
    $c = Get-Command $tool -ErrorAction SilentlyContinue
    if ($c -and $c.Source -notlike '*\WindowsApps\*') { Write-Host ("{0,-12}: {1}" -f $tool, $c.Source) }
    else { $warn += "$tool not found (or only the Store alias): install it and re-run (git: git-scm.com, python: python.org, tick 'Add to PATH')." }
}
if ($NinjaTrader -and -not (Test-Path -LiteralPath $NinjaTrader)) { $warn += "NinjaTrader.exe not found at $NinjaTrader (install NinjaTrader 8 first, then re-run with the right path)." }
$push = & git -C $Root push --dry-run origin HEAD 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { $warn += "git cannot push from this PC (needed for the heartbeat): sign in once with 'git push' in this folder (Git Credential Manager pops up a browser login)." }
if (-not $isAdmin) { $warn += "Not an Administrator PowerShell: the power and Windows Update settings below will be skipped. Right-click PowerShell > Run as administrator and re-run." }
foreach ($w in $warn) { Write-Warning $w }
if ($DryRun) { Write-Host "Dry run: nothing changed."; exit 0 }

if ($isAdmin) {
    Write-Host "== Power: never sleep on AC, screen off after 10 min, lid close = nothing, wake timers on, hibernation available"
    & powercfg /change standby-timeout-ac 0 | Out-Null
    & powercfg /change hibernate-timeout-ac 0 | Out-Null
    & powercfg /change monitor-timeout-ac 10 | Out-Null
    & powercfg /change disk-timeout-ac 0 | Out-Null
    & powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 | Out-Null      # lid close: do nothing
    & powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS PBUTTONACTION 3 | Out-Null  # power button: shut down (so you can still stop it)
    & powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1 | Out-Null
    & powercfg /hibernate on | Out-Null
    & powercfg /setactive SCHEME_CURRENT | Out-Null
    # LIT enters 02:00-15:30 ET and is flat at 15:55, so a Windows Update restart must land between 17:00 and 01:00 New York
    # time. Active hours are in this PC's own clock (max 18 h): convert 01:00 / 17:00 ET once (re-run after a DST change if
    # this PC is not on US time: Europe and the US change clocks on different weekends, Oct 25 / Nov 1 2026, Mar 28 / Mar 14 2027).
    $etZone = [TimeZoneInfo]::FindSystemTimeZoneById('Eastern Standard Time')
    $d0 = [DateTime]::SpecifyKind((Get-Date).Date, 'Unspecified')
    $ahStart = [TimeZoneInfo]::ConvertTimeToUtc($d0.AddHours(1), $etZone).ToLocalTime().Hour
    $ahEnd = [TimeZoneInfo]::ConvertTimeToUtc($d0.AddHours(17), $etZone).ToLocalTime().Hour
    Write-Host "== Windows Update: active hours 01:00-17:00 ET = $($ahStart):00-$($ahEnd):00 on this PC (restarts only 17:00-01:00 ET; the bot comes back by itself)"
    $ux = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'
    if (-not (Test-Path $ux)) { New-Item -Path $ux -Force | Out-Null }
    Set-ItemProperty -Path $ux -Name ActiveHoursStart -Value $ahStart -Type DWord
    Set-ItemProperty -Path $ux -Name ActiveHoursEnd -Value $ahEnd -Type DWord
    # no forced restart while the (auto-)signed-in user is logged on; updates still install, the restart waits for you
    $au = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
    if (-not (Test-Path $au)) { New-Item -Path $au -Force | Out-Null }
    Set-ItemProperty -Path $au -Name NoAutoRebootWithLoggedOnUsers -Value 1 -Type DWord
    Set-ItemProperty -Path $ux -Name SmartActiveHoursState -Value 0 -Type DWord -ErrorAction SilentlyContinue
}

Write-Host "== Bot supervisor at logon (scripts\install_autostart.ps1)"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'install_autostart.ps1') -Port $Port

if ($NinjaTrader) {
    Write-Host "== NinjaTrader starts at logon (Startup folder shortcut)"
    $startup = [Environment]::GetFolderPath('Startup')
    $lnk = Join-Path $startup 'NinjaTrader 8 (Liquidity Engine).lnk'
    $sh = New-Object -ComObject WScript.Shell
    $s = $sh.CreateShortcut($lnk); $s.TargetPath = $NinjaTrader; $s.WorkingDirectory = Split-Path -Parent $NinjaTrader; $s.Save()
    Write-Host "   $lnk"
}

Write-Host ""
Write-Host "== Still by hand (5 minutes):"
Write-Host " 1. Automatic sign-in after a restart: download Microsoft's free Autologon (learn.microsoft.com/sysinternals/downloads/autologon),"
Write-Host "    run it once, enter your Windows password, Enable. (It stores the password encrypted; this PC is for the bot only.)"
Write-Host " 2. NinjaTrader: Connections > Configure: tick 'Connect on startup' for the MFFU (Tradovate) connection; Tools > Options >"
Write-Host "    Automated Trading Interface: tick 'AT Interface'. Save the workspace with ONE MNQ 5-minute chart that has LE_BarFeed on it (ninjatrader\SETUP.md)."
Write-Host " 3. Start the bot once with: python -m engine.ninjatrader --start  (Sim101: it then resumes by itself after a restart;"
Write-Host "    a real account only after your one-time --enable-auto-resume, see docs\GO_LIVE_TONIGHT.md 'Make it run on its own')"
Write-Host " 4. Lock the screen (Win+L) and leave it plugged in. Your phone app gets a 'PC bot silent' notification from the cloud monitor if this PC goes quiet in a session."
Write-Host " 5. Restart this PC yourself once a week after 17:00 ET on Friday (Settings > Windows Update > Restart now) so updates do not pile up;"
Write-Host "    during an eval you can also Pause updates for 1-5 weeks there. Never restart between 01:30 and 16:00 ET on a weekday."
Write-Host " 6. Before any real order: MFFU's written OK for automated trading on your account."
