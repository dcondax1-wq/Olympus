<#
ONE_TIME_SETUP (double-click ONE_TIME_SETUP.bat in the bot folder): the last visit to the Surface. After it the Surface
stays awake, comes back by itself after a restart, updates itself, starts the bot and NinjaTrader at logon, and the phone
app shouts when it goes offline. Steps, each with a green [OK] or a red [FIX] line:

  a. stop the bot, get the new version from main (git pull --ff-only), install the packages (pip)
  b. power (needs Administrator: Windows asks once): never sleep or hibernate on AC, lid close = do nothing on AC,
     USB selective suspend off, Wi-Fi full power on AC
  c. Windows Update: paused 5 weeks (the most Windows allows), active hours 00:00-18:00 ET (no restart then),
     no automatic restart while you are signed in
  d. at logon: the bot supervisor (scripts\install_autostart.ps1), the 5-minute helper (scripts\install_ops_task.ps1)
     and NinjaTrader (a Startup shortcut; its "connect on startup" is 3 clicks inside NinjaTrader, printed at the end)
  e. the desktop icons (scripts\make_shortcuts.ps1)
  f. automatic updates of the bot (python -m engine.autoupdate --enable)
  g. starts the bot in its own window, asks for your eval account name and your confirm phrase (hidden, kept in memory
     only, never shown or saved by this script), then runs the existing commands
     python -m engine.ninjatrader --start / --enable-auto-resume with them. Enter = Sim101 (practice) instead.
  h. the health check (python -m engine.ops_checks)
  i. what is left for your hands: Chrome Remote Desktop (free) and automatic sign-in (Microsoft's free Autologon)

  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\one_time_setup.ps1           (ONE_TIME_SETUP.bat runs this)
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\one_time_setup.ps1 -DryRun   (show the plan, change nothing)
The elevated part (b, c and the logon tasks of d) is this same script started again with -AdminPart through a UAC prompt;
it writes its green / red lines to logs\one_time_setup_admin.txt for the first window to show. Docs: docs\ONE_TIME_SETUP.md.
#>
param(
    [int]$Port = 8766,
    [string]$Python = "",
    [switch]$DryRun,
    [switch]$AdminPart,          # internal: the elevated part (b, c, logon tasks); started by this script with a UAC prompt
    [string]$ForUser = "",       # internal: DOMAIN\name of the signed-in owner (the logon tasks run as this user)
    [string]$Report = ""         # internal: where the elevated part writes its OK / FIX lines
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
$LogDir = Join-Path $Root 'logs'
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$Summary = New-Object System.Collections.ArrayList
$PsExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$Stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'

function Say-Ok([string]$Text) {
    Write-Host "  [OK]  $Text" -ForegroundColor Green
    [void]$Summary.Add("OK|$Text")
    if ($Report) { Add-Content -LiteralPath $Report -Value "OK|$Text" -Encoding UTF8 }
}
function Say-Fix([string]$Text) {
    Write-Host "  [FIX] $Text" -ForegroundColor Red
    [void]$Summary.Add("FIX|$Text")
    if ($Report) { Add-Content -LiteralPath $Report -Value "FIX|$Text" -Encoding UTF8 }
}
function Say-Info([string]$Text) { Write-Host "        $Text" }
function Step([string]$Text) { Write-Host ""; Write-Host "== $Text" -ForegroundColor Cyan }

function Test-PythonExe([string]$Exe, [string[]]$Pre = @()) {
    # the real python.exe behind a name (a Store python in WindowsApps, the py launcher); $null when it does not run
    try {
        $out = & $Exe @Pre -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1
        if ($LASTEXITCODE -eq 0 -and $out -and (Test-Path -LiteralPath "$out".Trim())) { return "$out".Trim() }
    } catch { }
    return $null
}

function Find-Python {
    if ($Python -and (Test-Path -LiteralPath $Python)) { return $Python }
    if ($env:LE_PYTHON -and (Test-Path -LiteralPath $env:LE_PYTHON)) { return $env:LE_PYTHON }
    $c = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { $r = Test-PythonExe $c.Source; if ($r) { return $r } }           # the empty Store alias does not run: skipped
    $c = Get-Command py -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { $r = Test-PythonExe $c.Source @('-3'); if ($r) { return $r } }   # python.org without "Add to PATH": the py launcher
    return $null
}

function Get-StartupFolder {
    $d = [Environment]::GetFolderPath('Startup')
    if (-not $d) { $d = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup' }
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
    return $d
}

function Find-NinjaTrader {
    $p = Get-Process -Name NinjaTrader -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p -and $p.Path) { return $p.Path }
    $cands = @()
    foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramW6432, 'C:\Program Files')) {
        if ($base) { $cands += (Join-Path $base 'NinjaTrader 8\bin\NinjaTrader.exe') }
    }
    foreach ($k in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
                     'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*')) {
        Get-ItemProperty $k -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like 'NinjaTrader*' -and $_.InstallLocation } |
            ForEach-Object { $cands += (Join-Path $_.InstallLocation 'bin\NinjaTrader.exe'); $cands += (Join-Path $_.InstallLocation 'NinjaTrader.exe') }
    }
    foreach ($c in $cands) { if ($c -and (Test-Path -LiteralPath $c)) { return $c } }
    return $null
}

# ===================================================================================== the elevated part (b, c, logon tasks)
function Invoke-AdminPart([string]$User, [string]$Py) {
    Step "b. Power: the Surface never sleeps while plugged in"
    $ok = $true
    $cmds = @(
        @('/change', 'standby-timeout-ac', '0'),
        @('/change', 'hibernate-timeout-ac', '0'),
        @('/change', 'monitor-timeout-ac', '10'),
        @('/change', 'disk-timeout-ac', '0'),
        @('/setacvalueindex', 'SCHEME_CURRENT', 'SUB_BUTTONS', 'LIDACTION', '0'),                 # lid close on AC: do nothing
        @('/setacvalueindex', 'SCHEME_CURRENT', '2a737441-1930-4402-8d77-b2bebba308a3', '48e6b7a6-50f5-4782-a5d4-53bb8f07e226', '0'),  # USB selective suspend off
        @('/setacvalueindex', 'SCHEME_CURRENT', '19cbb8fa-5279-450e-9fac-8a3d5fedd0c1', '12bbebe6-58d6-4636-95bb-3217ef867c1a', '0'),  # Wi-Fi: maximum performance on AC
        @('/setacvalueindex', 'SCHEME_CURRENT', 'SUB_SLEEP', 'RTCWAKE', '1'),                     # wake timers on
        @('/setactive', 'SCHEME_CURRENT')
    )
    $usb = 'off'
    foreach ($c in $cmds) {
        & powercfg @c 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { continue }
        if ($c[2] -eq '2a737441-1930-4402-8d77-b2bebba308a3') { $usb = 'not on this PC (fine)'; continue }   # not every Surface has it
        if ($c[2] -eq '19cbb8fa-5279-450e-9fac-8a3d5fedd0c1') { continue }                                   # Wi-Fi power: optional
        $ok = $false; Say-Info "powercfg $($c -join ' ') failed"
    }
    if ($ok) { Say-Ok "Power: no sleep / hibernate on AC, lid close = do nothing on AC, USB selective suspend $usb, screen off after 10 min" }
    else { Say-Fix "Some power settings did not apply: Settings > System > Power > Screen and sleep: 'When plugged in, put my device to sleep after' = Never" }

    Step "c. Windows Update: no restart while the bot trades"
    try {
        $ux = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'
        if (-not (Test-Path $ux)) { New-Item -Path $ux -Force | Out-Null }
        # active hours 00:00-18:00 New York time (18 h, the most Windows allows), in this PC's own clock
        $etZone = [TimeZoneInfo]::FindSystemTimeZoneById('Eastern Standard Time')
        $d0 = [DateTime]::SpecifyKind((Get-Date).Date, 'Unspecified')
        $ahStart = [TimeZoneInfo]::ConvertTimeToUtc($d0, $etZone).ToLocalTime().Hour
        $ahEnd = [TimeZoneInfo]::ConvertTimeToUtc($d0.AddHours(18), $etZone).ToLocalTime().Hour
        Set-ItemProperty -Path $ux -Name ActiveHoursStart -Value $ahStart -Type DWord
        Set-ItemProperty -Path $ux -Name ActiveHoursEnd -Value $ahEnd -Type DWord
        Set-ItemProperty -Path $ux -Name SmartActiveHoursState -Value 0 -Type DWord -ErrorAction SilentlyContinue
        Set-ItemProperty -Path $ux -Name IsExpedited -Value 0 -Type DWord -ErrorAction SilentlyContinue        # "Get me up to date" off
        # pause updates for 35 days (the most Windows allows from Settings; afterwards it installs, then you can pause again)
        $from = (Get-Date).ToUniversalTime()
        $until = $from.AddDays(35)
        $inv = [Globalization.CultureInfo]::InvariantCulture      # ':' stays ':' whatever the PC's language
        $f = $from.ToString('yyyy-MM-ddTHH:mm:ssZ', $inv); $u = $until.ToString('yyyy-MM-ddTHH:mm:ssZ', $inv)
        foreach ($n in @('PauseUpdatesStartTime', 'PauseFeatureUpdatesStartTime', 'PauseQualityUpdatesStartTime')) { Set-ItemProperty -Path $ux -Name $n -Value $f -Type String }
        foreach ($n in @('PauseUpdatesExpiryTime', 'PauseFeatureUpdatesEndTime', 'PauseQualityUpdatesEndTime')) { Set-ItemProperty -Path $ux -Name $n -Value $u -Type String }
        # no forced restart while you are signed in (the automatic sign-in keeps you signed in)
        $au = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
        if (-not (Test-Path $au)) { New-Item -Path $au -Force | Out-Null }
        Set-ItemProperty -Path $au -Name NoAutoRebootWithLoggedOnUsers -Value 1 -Type DWord
        Say-Ok ("Windows Update paused until {0:yyyy-MM-dd}; active hours 00:00-18:00 ET (= {1}:00-{2}:00 on this PC); no automatic restart while signed in" -f $until.ToLocalTime(), $ahStart, $ahEnd)
    } catch { Say-Fix "Windows Update settings: $($_.Exception.Message). By hand: Settings > Windows Update > Pause updates (5 weeks) and Active hours" }

    Step "d. Start at logon: the bot supervisor and the 5-minute helper (they run as $User, not as Administrator)"
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'install_autostart.ps1'), '-Port', "$Port", '-User', $User)
    if ($Py) { $a += @('-Python', $Py) }
    & $PsExe @a
    if ($LASTEXITCODE -eq 0) { Say-Ok "Logon task (bot): LiquidityEngine starts the bot supervisor (scripts\run_bot.ps1) at logon and unlock" }
    else { Say-Fix "Logon task (bot): the LiquidityEngine logon task was not created (see the lines above)" }
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'install_ops_task.ps1'), '-User', $User)
    if ($Py) { $a += @('-Python', $Py) }
    & $PsExe @a
    if ($LASTEXITCODE -eq 0) { Say-Ok "Logon task (helper): LiquidityEngineOps runs the 5-minute helper (phone notices, nightly backup)" }
    else { Say-Fix "Logon task (helper): the LiquidityEngineOps task was not created (see the lines above)" }
}

if ($AdminPart) {
    if ($Report) { Set-Content -LiteralPath $Report -Value "STARTED|$Stamp" -Encoding UTF8 }
    Write-Host "Liquidity Engine - ONE TIME SETUP (Administrator part)" -ForegroundColor Cyan
    Invoke-AdminPart -User $ForUser -Py $Python
    Write-Host ""
    Write-Host "Administrator part done. This window closes in 10 seconds; the first window carries on." -ForegroundColor Cyan
    Start-Sleep -Seconds 10
    exit 0
}

# ===================================================================================== the normal part (runs as you)
Write-Host ""
Write-Host "  ==== Liquidity Engine: ONE TIME SETUP ====" -ForegroundColor Cyan
Write-Host "  About 5 minutes. Green [OK] = done, red [FIX] = the one thing to do. Take a photo of the end if anything is red."
$Me = "$env:USERDOMAIN\$env:USERNAME"
$isAdmin = $false
try { $isAdmin = [bool]([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) } catch { }
$Py = Find-Python
if (-not $Py) { Say-Fix "Python not found: install Python 3.12 from python.org (tick 'Add python.exe to PATH'), then run ONE_TIME_SETUP again"; exit 1 }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Say-Fix "Git not found: install Git for Windows from git-scm.com, then run ONE_TIME_SETUP again"; exit 1 }
$env:PYTHONIOENCODING = 'utf-8'

if ($DryRun) {
    Write-Host "DRY RUN - nothing changed. Would run, in order:"
    Write-Host "  a. scripts\stop_bot.ps1 -KeepAutostart; git checkout main (only when no local changes); git pull --ff-only origin main; pip install -r requirements.txt"
    Write-Host "  b+c+d. ask Windows for Administrator (UAC) once: powercfg (no sleep / hibernate on AC, lid = nothing, USB suspend off),"
    Write-Host "         Windows Update paused 5 weeks + active hours 00:00-18:00 ET + no restart while signed in, logon tasks for $Me"
    Write-Host "  d. NinjaTrader Startup shortcut: $(Find-NinjaTrader)"
    Write-Host "  e. scripts\make_shortcuts.ps1   f. $Py -m engine.autoupdate --enable"
    Write-Host "  g. scripts\run_bot.ps1 in its own window; ask the eval account + confirm phrase (hidden; Enter = Sim101);"
    Write-Host "     $Py -m engine.ninjatrader --start / --enable-auto-resume"
    Write-Host "  h. $Py -m engine.ops_checks   i. print Chrome Remote Desktop + Autologon steps"
    exit 0
}

# ---------------------------------------------------------------------------------------------- a. stop, update, packages
Step "a. Stop the bot, get the new version, install the packages"
& $Py -X utf8 -m engine.ops_checks --update-guard 2>$null | Out-Host
if ($LASTEXITCODE -eq 1 -or $LASTEXITCODE -eq 2) {
    $ans = Read-Host "  A trade or a setup may be open (or it is trading time). Type Y then Enter to carry on anyway (Enter = stop here)"
    if ($ans -notmatch '^[Yy]') { Say-Fix "Stopped: run ONE_TIME_SETUP again after the trade closes (best after 16:00 ET)"; exit 1 }
}
& $PsExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'stop_bot.ps1') -KeepAutostart | Out-Host
Say-Ok "Bot stopped (it restarts at the end of this setup)"
$br = (& git rev-parse --abbrev-ref HEAD 2>$null | Out-String).Trim()
if ($br -ne 'main') {
    $dirty = (& git status --porcelain --untracked-files=no 2>$null | Out-String).Trim()
    if ($dirty) {
        Say-Fix "The bot folder is on branch '$br' with files changed by hand, so it was not switched to main. Send a photo of this window to Claude."
        Say-Info ((($dirty -split "`n") | Select-Object -First 5) -join '; ')
        exit 1
    }
    & git fetch -q origin main 2>&1 | ForEach-Object { "$_" } | Out-Host
    & git checkout main 2>&1 | ForEach-Object { "$_" } | Out-Host
    $br = (& git rev-parse --abbrev-ref HEAD 2>$null | Out-String).Trim()
    if ($br -eq 'main') { Say-Ok "Switched the bot folder to the main branch" }
    else { Say-Fix "Could not switch to main (still on '$br'). Send a photo of this window to Claude."; exit 1 }
}
& git pull --ff-only origin main 2>&1 | ForEach-Object { "$_" } | Out-Host
if ($LASTEXITCODE -eq 0) { Say-Ok "Code is up to date (main)" }
else { Say-Fix "git pull failed: the version you have stays. Send a photo of this window to Claude (the rest of the setup still runs)" }
& $Py -m pip install -r requirements.txt --disable-pip-version-check -q 2>&1 | ForEach-Object { "$_" } | Out-Host
if ($LASTEXITCODE -eq 0) { Say-Ok "Packages installed" } else { Say-Fix "pip install failed: check the internet, then run ONE_TIME_SETUP again" }

# ---------------------------------------------------------------------------------------------- b, c, d (tasks): Administrator
Step "b-d. Power, Windows Update and the logon tasks (needs Administrator)"
$rep = Join-Path $LogDir 'one_time_setup_admin.txt'
Remove-Item -LiteralPath $rep -ErrorAction SilentlyContinue
if ($isAdmin) {
    $Report = $rep
    Invoke-AdminPart -User $Me -Py $Py
    $Report = ""
} else {
    Write-Host "  Windows now asks 'Do you want to allow this app to make changes to your device?'. Click YES." -ForegroundColor Yellow
    Write-Host "  Why: only an Administrator may change the power plan (no sleep), Windows Update (no restart during trading)"
    Write-Host "  and add the start-at-logon tasks. A second blue window does it and closes by itself."
    try {
        $argLine = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -AdminPart -Port $Port -ForUser `"$Me`" -Python `"$Py`" -Report `"$rep`""
        Start-Process -FilePath $PsExe -Verb RunAs -Wait -ArgumentList $argLine
    } catch { Write-Host "  (the Administrator window did not start: $($_.Exception.Message))" }
    if (Test-Path -LiteralPath $rep) {
        Write-Host "  The Administrator window reported:"
        foreach ($ln in (Get-Content -LiteralPath $rep -Encoding UTF8)) {
            $k, $t = $ln -split '\|', 2
            if ($k -eq 'OK') { Say-Ok $t } elseif ($k -eq 'FIX') { Say-Fix $t }
        }
    } else {
        Say-Fix "No Administrator rights (you clicked No?): power and Windows Update are NOT set. Run ONE_TIME_SETUP again and click Yes."
    }
}
$adminLines = @()
if (Test-Path -LiteralPath $rep) { $adminLines = @(Get-Content -LiteralPath $rep -Encoding UTF8) }
if (-not ($adminLines -match '^OK\|Logon task \(bot\)')) {
    Say-Info "Trying the bot logon task without Administrator rights"
    & $PsExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'install_autostart.ps1') -Port $Port -Python $Py | Out-Host
    if ($LASTEXITCODE -eq 0) { Say-Ok "Task LiquidityEngine starts the bot at logon" } else { Say-Fix "The bot logon task is missing: run ONE_TIME_SETUP again and click Yes" }
}
if (-not ($adminLines -match '^OK\|Logon task \(helper\)')) {
    & $PsExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'install_ops_task.ps1') -Python $Py | Out-Host
    if ($LASTEXITCODE -eq 0) { Say-Ok "Task LiquidityEngineOps runs the 5-minute helper" } else { Say-Fix "The helper task is missing: run ONE_TIME_SETUP again and click Yes" }
}

# ---------------------------------------------------------------------------------------------- d. NinjaTrader at logon
Step "d. NinjaTrader starts at logon"
$Nt = Find-NinjaTrader
if ($Nt) {
    try {
        $lnk = Join-Path (Get-StartupFolder) 'NinjaTrader 8 (Liquidity Engine).lnk'
        $sh = New-Object -ComObject WScript.Shell
        $s = $sh.CreateShortcut($lnk); $s.TargetPath = $Nt; $s.WorkingDirectory = Split-Path -Parent $Nt; $s.Save()
        Say-Ok "NinjaTrader starts at logon ($Nt)"
    } catch { Say-Fix "Could not add NinjaTrader to Startup: $($_.Exception.Message)" }
    if (-not (Get-Process -Name NinjaTrader -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $Nt -WorkingDirectory (Split-Path -Parent $Nt)
        Say-Info "NinjaTrader is starting now: log in to it while this setup carries on"
    }
} else {
    Say-Fix "NinjaTrader.exe not found: install NinjaTrader 8 (ninjatrader.com, free), then run ONE_TIME_SETUP again"
}

# ---------------------------------------------------------------------------------------------- e. desktop icons
Step "e. Desktop icons"
& $PsExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'make_shortcuts.ps1') | Out-Host
if ($LASTEXITCODE -eq 0) { Say-Ok "Desktop icons: LE UPDATE, LE DASHBOARD, LE HEALTH CHECK, LE STOP BOT" } else { Say-Fix "Desktop icons not made (see above)" }

# ---------------------------------------------------------------------------------------------- f. auto-update
Step "f. The bot updates itself (outside trading hours, when flat)"
& $Py -X utf8 -m engine.autoupdate --enable | Out-Host
if ($LASTEXITCODE -eq 0) { Say-Ok "Auto-update is on" } else { Say-Fix "Auto-update not turned on (see above)" }

# ---------------------------------------------------------------------------------------------- g. start the bot
Step "g. Start the bot on your eval account"
Write-Host "  Your eval account name is in NinjaTrader: Control Center > Accounts tab > 'Name' column (not Sim101)."
$acct = (Read-Host "  Eval account name (just Enter = practice on Sim101)").Trim()
$live = $acct -and ($acct -notmatch '^Sim')
$envFile = Join-Path $Root '.env.local.ps1'
if ($live) {
    $has = (Test-Path -LiteralPath $envFile) -and (Select-String -LiteralPath $envFile -Pattern 'NINJATRADER_LIVE' -Quiet)
    # the live switch is yours to set (this script never writes it): docs\GO_LIVE_TONIGHT.md step 10
    for ($i = 0; $i -lt 2 -and -not $has; $i++) {
        Write-Host "  The eval needs your live switch in .env.local.ps1 and it is not there yet." -ForegroundColor Yellow
        Write-Host "  Add it yourself as in docs\GO_LIVE_TONIGHT.md step 10 (one Add-Content line in a second PowerShell window in this folder)."
        $ans = Read-Host "  Press Enter when it is added (type S then Enter = practice on Sim101 instead)"
        if ($ans -match '^[Ss]') { break }
        $has = (Test-Path -LiteralPath $envFile) -and (Select-String -LiteralPath $envFile -Pattern 'NINJATRADER_LIVE' -Quiet)
    }
    if ($has) { Say-Ok "Your live switch is in .env.local.ps1" }
    else { $live = $false; Say-Fix "No live switch in .env.local.ps1: starting on Sim101 (practice). GO_LIVE_TONIGHT.md step 10, then run ONE_TIME_SETUP again" }
}
Start-Process -FilePath $PsExe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot 'run_bot.ps1')`""
Say-Info "The bot server is starting in its own window ('Liquidity Engine bot'): leave that window open"
& $Py -X utf8 -m engine.ops_checks --wait-server 120 | Out-Host
if ($LASTEXITCODE -ne 0) { Say-Fix "The bot server did not answer in 2 minutes: look at the other window, then run ONE_TIME_SETUP again" }
else {
    & $Py -X utf8 -m engine.ninjatrader --stop --port $Port 2>&1 | Out-Null       # a bot that resumed by itself (paper / Sim) first
    $started = $false
    if ($live) {
        for ($try = 1; $try -le 2 -and -not $started; $try++) {
            $sec = Read-Host -AsSecureString "  Your confirm phrase for $acct (hidden while you type; just Enter = Sim101)"
            $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
            try { $phrase = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
            if (-not $phrase) { break }
            & $Py -X utf8 -m engine.ninjatrader --start --account $acct --confirm $phrase --port $Port | Out-Host
            if ($LASTEXITCODE -eq 0) {
                $started = $true
                Say-Ok "The bot runs on your eval account $acct"
                & $Py -X utf8 -m engine.ninjatrader --enable-auto-resume --account $acct --confirm $phrase --port $Port | Out-Host
                if ($LASTEXITCODE -eq 0) { Say-Ok "Auto-resume is on for ${acct}: after a restart or an update the bot comes back by itself" }
                else { Say-Fix "Auto-resume was not turned on (see above): after a restart start the bot from the dashboard" }
            } else { Write-Host "  That did not start (wrong phrase or account name?)." -ForegroundColor Yellow }
            $phrase = $null
        }
        Remove-Variable phrase -ErrorAction SilentlyContinue
        $sec = $null
    }
    if (-not $started) {
        if ($live) { Say-Fix "Not started on ${acct}: the bot runs on Sim101 (practice) instead. Start the eval later from the dashboard or run ONE_TIME_SETUP again" }
        & $Py -X utf8 -m engine.ninjatrader --start --account Sim101 --port $Port | Out-Host
        if ($LASTEXITCODE -eq 0) { Say-Ok "The bot runs on Sim101 (practice, no real orders; it comes back by itself after a restart)" }
        else { Say-Fix "The bot did not start on Sim101 either (see above). Is NinjaTrader open and connected?" }
    }
}

# ---------------------------------------------------------------------------------------------- h. health check
Step "h. Health check"
Start-Sleep -Seconds 5
& $Py -X utf8 -m engine.ops_checks | Out-Host
if ($LASTEXITCODE -eq 0) { Say-Ok "Health check: no red lines" } else { Say-Fix "Health check: fix the red lines above (each has its fix on the next line)" }

# ---------------------------------------------------------------------------------------------- i. what is left for your hands
Step "i. Still by hand (free, about 10 minutes, once)"
Write-Host "  1. NinjaTrader connects by itself (3 clicks): Control Center > Connections > Configure > select your MFFU connection,"
Write-Host "     tick 'Connect on startup', OK. Also check Tools > Options > Automated trading interface > 'AT Interface' is ticked,"
Write-Host "     and save the workspace with the MNQ chart that has LE_BarFeed on it (Workspaces > Save)."
Write-Host "  2. Automatic sign-in after a restart (Microsoft's free Autologon, nothing is saved by this script):"
Write-Host "     open learn.microsoft.com/sysinternals/downloads/autologon, download, unzip, run Autologon64.exe,"
Write-Host "     type your Windows password, click Enable. (It stores it encrypted by Windows; this PC is only for the bot.)"
Write-Host "  3. Reach the Surface from your phone (Chrome Remote Desktop, free):"
Write-Host "     on the Surface open remotedesktop.google.com/access in Chrome, sign in with your Google account,"
Write-Host "     'Set up remote access' > Download > install the host > give the Surface a name > choose a PIN (6+ digits)."
Write-Host "     On the phone install 'Chrome Remote Desktop' (App Store / Play Store), same Google account, tap the Surface, PIN."
Write-Host "  4. Leave it plugged in, lid open or closed, Wi-Fi on. Lock it with Win+L. The phone app says 'Surface offline' if it ever goes quiet."

Write-Host ""
Write-Host "  ==== Summary ====" -ForegroundColor Cyan
$nFix = 0
foreach ($ln in $Summary) {
    $k, $t = $ln -split '\|', 2
    if ($k -eq 'OK') { Write-Host "  [OK]  $t" -ForegroundColor Green } else { $nFix++; Write-Host "  [FIX] $t" -ForegroundColor Red }
}
try { Set-Content -LiteralPath (Join-Path $LogDir 'one_time_setup.log') -Value (@("ONE_TIME_SETUP $Stamp") + $Summary) -Encoding UTF8 } catch { }
Write-Host ""
if ($nFix -eq 0) { Write-Host "  ALL GREEN. You can leave the Surface now." -ForegroundColor Green }
else { Write-Host "  $nFix red line(s): do the [FIX] above, or send a photo of this window to Claude." -ForegroundColor Red }
exit 0
