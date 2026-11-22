<#
FIX_CLOCK: make the Windows clock follow internet time for good (owner 2026-11-22: the PC ran 24.5 s behind and the bot's clock
guard, rightly, blocked every new entry). Run ONCE as administrator (FIX_CLOCK.bat checks that). It
  1. sets the Windows Time service (w32time) to Automatic and starts it,
  2. sets the time servers (time.cloudflare.com, time.windows.com, pool.ntp.org, flag 0x9), a 900 s poll and a phase-correction
     limit big enough that a 30 s jump is accepted (the default refuses big steps),
  3. turns on "Set time automatically" (Type NTP) and syncs now (w32tm /resync /force),
  4. registers the Scheduled Task OlympusClock: runs as SYSTEM, every 15 minutes + at boot + at wake, w32tm /resync /force, and
     the owner's own (non-admin) account may start it (schtasks /run /tn OlympusClock), so the bot's Start page "Sync the clock"
     works without an administrator,
  5. prints the drift BEFORE and AFTER (HTTPS Date header of three sites, median; w32tm /stripchart as the fallback) and one
     [OK] / [FIX] line.
Safe to run twice. -Off removes the task (FIX_CLOCK_OFF.bat); it leaves the time service on Automatic.
It touches only Windows' own time settings: no trading file, no strategy, no live switch. Windows PowerShell 5.1 safe, ASCII only.
#>
param([switch]$Off)
$ErrorActionPreference = 'Continue'
$TaskName = 'OlympusClock'
$Peers = 'time.cloudflare.com,0x9 time.windows.com,0x9 pool.ntp.org,0x9'

function Say([string]$t) { Write-Host ('  ' + $t) }

function Test-Admin {
    try {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        return (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch { return $false }
}

# PC drift in seconds: server time minus this PC's time (positive = the PC is BEHIND). $null = no answer.
function Get-Drift {
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
    $vals = @()
    foreach ($u in @('https://www.cloudflare.com', 'https://www.microsoft.com', 'https://www.google.com')) {
        try {
            $sw = [Diagnostics.Stopwatch]::StartNew()
            $r = Invoke-WebRequest -Uri $u -Method Head -UseBasicParsing -TimeoutSec 8
            $sw.Stop()
            $local = [DateTimeOffset]::UtcNow.AddMilliseconds(-($sw.ElapsedMilliseconds / 2.0))
            $d = [string]($r.Headers['Date'])
            if ($d) {
                $srv = [DateTimeOffset]::Parse($d, [Globalization.CultureInfo]::InvariantCulture)
                $vals += ($srv - $local).TotalSeconds
            }
        } catch { }
    }
    if ($vals.Count -ge 1) {
        $s = @($vals | Sort-Object)
        return [double]$s[[int][Math]::Floor(($s.Count - 1) / 2)]
    }
    return $null
}

# Fallback: w32tm's own chart against Cloudflare; the sign of w32tm's offset is not relied on, so only the size is shown.
function Get-DriftAbs {
    try {
        $o = & w32tm /stripchart /computer:time.cloudflare.com /samples:3 /dataonly 2>&1 | Out-String
        $m = [regex]::Matches($o, '([+-]\d+\.\d+)s')
        if ($m.Count -ge 1) { return [Math]::Abs([double]$m[$m.Count - 1].Groups[1].Value) }
    } catch { }
    return $null
}

function Show-Drift([string]$label) {
    $d = Get-Drift
    if ($null -ne $d) {
        $side = 'behind'
        if ($d -lt 0) { $side = 'ahead of' }
        Say ("{0}: the PC clock is {1:N1} s {2} internet time" -f $label, [Math]::Abs($d), $side)
        return $d
    }
    $a = Get-DriftAbs
    if ($null -ne $a) {
        Say ("{0}: the PC clock is {1:N1} s off internet time (w32tm)" -f $label, $a)
        return $a
    }
    Say ("{0}: could not read internet time (no internet?)" -f $label)
    return $null
}

Write-Host ''
Write-Host '  ==== FIX THE CLOCK ===='
if (-not (Test-Admin)) {
    Write-Host '  [FIX] This needs an administrator: close this window, right-click FIX_CLOCK.bat and choose "Run as administrator".'
    exit 1
}

if ($Off) {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($t) { Write-Host '  [FIX] Could not remove the OlympusClock task. Send a photo of this window to Claude.'; exit 1 }
        Write-Host '  [OK] The OlympusClock task is removed. Windows keeps its own time service on; run FIX_CLOCK.bat again any time.'
    } else {
        Write-Host '  [OK] There was no OlympusClock task: nothing to remove.'
    }
    exit 0
}

$before = Show-Drift 'BEFORE'

# 1. the Windows Time service: Automatic and running
try { & sc.exe config w32time start= auto | Out-Null } catch { }
try { Set-Service -Name w32time -StartupType Automatic -ErrorAction Stop } catch { }
try { Start-Service -Name w32time -ErrorAction Stop } catch { }
Start-Sleep -Seconds 2
$svc = Get-Service -Name w32time -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -eq 'Running') { Say 'Windows Time service: Automatic, running' } else { Say 'Windows Time service: could not start it yet' }

# 2. time servers, 900 s poll, big steps accepted, "Set time automatically" (Type NTP)
try { & w32tm /config /syncfromflags:manual /manualpeerlist:"$Peers" /reliable:no /update 2>&1 | Out-Null } catch { }
$p = 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time'
try {
    Set-ItemProperty -Path "$p\Parameters" -Name Type -Value 'NTP' -ErrorAction Stop
    Set-ItemProperty -Path "$p\Parameters" -Name NtpServer -Value $Peers -ErrorAction Stop
    Set-ItemProperty -Path "$p\TimeProviders\NtpClient" -Name SpecialPollInterval -Value 900 -Type DWord -ErrorAction Stop
    Set-ItemProperty -Path "$p\Config" -Name MaxPosPhaseCorrection -Value 86400 -Type DWord -ErrorAction Stop
    Set-ItemProperty -Path "$p\Config" -Name MaxNegPhaseCorrection -Value 86400 -Type DWord -ErrorAction Stop
    Say 'Time servers: cloudflare, windows, pool.ntp.org; polls every 15 min; steps up to a day accepted'
} catch {
    Say ('Could not write a time setting: ' + $_.Exception.Message)
}
try { Restart-Service -Name w32time -ErrorAction Stop } catch { try { Start-Service -Name w32time -ErrorAction SilentlyContinue } catch { } }
Start-Sleep -Seconds 3

# 3. sync now (the service needs a moment after a restart: up to 4 tries)
$synced = $false
for ($i = 1; $i -le 4; $i++) {
    $o = & w32tm /resync /force 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0 -and $o -notmatch 'error|denied|not been started') { $synced = $true; break }
    Start-Sleep -Seconds 3
}
if ($synced) { Say 'Sync now: done' } else { Say 'Sync now: Windows did not answer yet (the task below keeps trying)' }

# 4. the Scheduled Task OlympusClock (SYSTEM, every 15 min + boot + wake)
$taskOk = $false
try {
    $act = New-ScheduledTaskAction -Execute 'w32tm.exe' -Argument '/resync /force'
    $trg = @()
    $trg += New-ScheduledTaskTrigger -AtStartup
    $trg += New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 7300)
    try {
        $xml = '<QueryList><Query Id="0" Path="System"><Select Path="System">*[System[Provider[@Name=''Microsoft-Windows-Power-Troubleshooter''] and EventID=1]]</Select></Query></QueryList>'
        $ev = New-CimInstance -ClassName MSFT_TaskEventTrigger -Namespace Root/Microsoft/Windows/TaskScheduler -ClientOnly -Property @{ Enabled = $true; Subscription = $xml }
        $trg += $ev
    } catch { Say 'Wake trigger not added (the 15-minute run covers it)' }
    $pri = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $set = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
    Register-ScheduledTask -TaskName $TaskName -Action $act -Trigger $trg -Principal $pri -Settings $set -Force -ErrorAction Stop | Out-Null
    $taskOk = $true
    # the owner's own (non-administrator) account may START it: read + execute for Authenticated Users
    try {
        $svcObj = New-Object -ComObject 'Schedule.Service'
        $svcObj.Connect()
        $tk = $svcObj.GetFolder('\').GetTask($TaskName)
        $tk.SetSecurityDescriptor('D:(A;;FA;;;BA)(A;;FA;;;SY)(A;;GRGX;;;AU)', 0)
    } catch { Say 'Note: could not let your normal account start the task; the Start page button may ask for an administrator.' }
} catch {
    Say ('Could not register the task: ' + $_.Exception.Message)
}
if ($taskOk) { Say 'Task OlympusClock: every 15 min, at boot and at wake, as SYSTEM (no administrator needed again)' }

# 5. AFTER
Start-Sleep -Seconds 3
$after = Show-Drift 'AFTER '
Write-Host ''
$ok = ($null -ne $after) -and ([Math]::Abs($after) -le 2.0) -and $taskOk
if ($ok) {
    Write-Host '  [OK] The clock matches internet time and OlympusClock keeps it that way. You never need to run this again.'
    exit 0
}
if ($null -ne $after -and [Math]::Abs($after) -le 5.0 -and $taskOk) {
    Write-Host '  [OK] The clock is inside the bot''s 5 s limit and OlympusClock keeps correcting it every 15 minutes.'
    exit 0
}
if (-not $taskOk) {
    Write-Host '  [FIX] The clock task could not be set up. Send a photo of this window to Claude.'
} elseif ($null -eq $after) {
    Write-Host '  [FIX] No internet answer to measure. Check the Wi-Fi, then right-click FIX_CLOCK.bat > Run as administrator once more.'
} else {
    Write-Host '  [FIX] The clock is still off. Wait 15 minutes (the task retries) and open the Start page; if it is still red, send a photo of this window to Claude.'
}
exit 1
