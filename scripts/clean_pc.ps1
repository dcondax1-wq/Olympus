<#
CLEAN_PC (double-click CLEAN_PC.bat in the bot folder). The owner, 2026-11-01: "start clearing my pc and make it run smoothly,
go deep". The Surface has 3.6 GB of memory and ran at 90%+ with the CPU at 100%, which slows NinjaTrader and the bot and heats
the tablet (its screen glitches when hot). This makes it lighter. NinjaTrader, the bot (python), PowerShell, Edge (the Start
page), Explorer, OneDrive (Documents and NinjaTrader's folder may live in OneDrive), Git and the Claude app are never touched.

LIGHT part (any time, also while the bot trades; no Administrator):
  1. before: memory, CPU, the 12 programs using the most memory, disk
  2. closes programs not needed for trading (Discord, Obsidian, Spotify, Steam, Epic, Teams, Skype, Zoom, Widgets,
     Phone Link, Xbox / Game Bar, Telegram, WhatsApp ...)
  3. keeps those from starting at sign-in: the same switch as Task Manager > Startup apps > Disabled (turn one back on there)
  4. a lighter Windows: transparency, taskbar animations and window animations off; the Widgets and Copilot buttons off;
     no more suggested / silently installed apps
  5. junk: your Temp folder (files older than 2 days), crash dumps, NinjaTrader's own old log and trace files (14+ days)
DEEP part (Administrator: Windows asks once; only outside trading hours: weekdays 16:05-01:15 ET, weekends any time;
each heavy step checks the clock again and stops before 01:15 ET so it never runs while the bot can trade):
  6. Windows Search indexing off (it re-reads the whole disk after every restart; Start menu search still finds apps)
  7. Store apps stop running in the background (desktop programs like NinjaTrader are not affected)
  8. Windows Temp, error reports, the Delivery Optimization cache
  9. preinstalled apps not used here: Xbox, Solitaire, Clipchamp, News, Weather, Tips, Get Help, Feedback Hub, Maps,
     People, Movies & TV, Skype, Teams (personal), Mixed Reality (they come back from the Microsoft Store if wanted)
 10. Windows' component store clean-up (DISM /StartComponentCleanup: old update files; this one takes a while)
 11. a Microsoft Defender quick scan
  after: memory again and what changed. Log: logs\clean_pc-YYYYMMDD-HHMM.txt

  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\clean_pc.ps1            (CLEAN_PC.bat runs this)
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\clean_pc.ps1 -DryRun    (shows the plan, changes nothing)
#>
param(
    [switch]$DryRun,
    [switch]$LightOnly,
    [switch]$AdminPart,     # internal: the elevated deep part, started by this script with a UAC prompt
    [string]$Log = ""       # internal: the same log file for both parts
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root 'logs'
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
if (-not $Log) { $Log = Join-Path $LogDir ("clean_pc-" + (Get-Date -Format 'yyyyMMdd-HHmm') + ".txt") }

function Say([string]$Kind, [string]$Text) {
    $line = "  [$Kind] $Text"
    $color = 'Gray'
    if ($Kind -eq 'OK') { $color = 'Green' } elseif ($Kind -eq 'FIX') { $color = 'Red' } elseif ($Kind -eq 'SKIP') { $color = 'Yellow' }
    Write-Host $line -ForegroundColor $color
    try { Add-Content -LiteralPath $Log -Value $line -Encoding UTF8 } catch { }
}
function Head([string]$Text) { Write-Host ""; Write-Host $Text -ForegroundColor Cyan; try { Add-Content -LiteralPath $Log -Value ("`r`n" + $Text) -Encoding UTF8 } catch { } }

# ------------------------------------------------------------------ what is never touched, and what goes
$Protect = @('ninjatrader', 'liquidity', 'le start', 'le_start', 'python', 'pythonw', 'onedrive', 'securityhealth', 'windowsdefender',
             'msmpeng', 'realtek', 'rtkaud', 'intel', 'igfx', 'surface', 'synaptics', 'bluetooth', 'audio', 'claude', 'git')
# process names (exact, any case) closed now
$CloseProcs = @('Discord', 'Obsidian', 'Spotify', 'steam', 'steamwebhelper', 'EpicGamesLauncher', 'EpicWebHelper', 'Teams', 'ms-teams',
                'msteams', 'Skype', 'Zoom', 'Telegram', 'WhatsApp', 'Messenger', 'Widgets', 'WidgetService', 'PhoneExperienceHost',
                'YourPhone', 'GameBar', 'GameBarFTServer', 'XboxPcApp', 'XboxPcAppFT', 'Overwolf', 'RiotClientServices', 'Battle.net',
                'EADesktop', 'Origin', 'GrammarlyHelper', 'Grammarly.Desktop')
# start-up entries (name or command contains, any case) switched off at sign-in
$StartupOff = @('discord', 'obsidian', 'spotify', 'steam', 'epicgames', 'teams', 'skype', 'zoom', 'telegram', 'whatsapp', 'messenger',
                'grammarly', 'overwolf', 'riotclient', 'battle.net', 'eadesktop', 'microsoftedgeautolaunch', 'yourphone', 'phonelink')
$BloatApps = @('Microsoft.BingNews', 'Microsoft.BingWeather', 'Microsoft.GetHelp', 'Microsoft.Getstarted', 'Microsoft.MicrosoftSolitaireCollection',
               'Microsoft.WindowsFeedbackHub', 'Microsoft.WindowsMaps', 'Microsoft.XboxApp', 'Microsoft.GamingApp', 'Microsoft.XboxGamingOverlay',
               'Microsoft.XboxGameOverlay', 'Microsoft.XboxSpeechToTextOverlay', 'Microsoft.Xbox.TCUI', 'Clipchamp.Clipchamp', 'Microsoft.People',
               'Microsoft.ZuneVideo', 'Microsoft.SkypeApp', 'MicrosoftTeams', 'MSTeams', 'Microsoft.MixedReality.Portal')

function Is-Protected([string]$Text) { $t = $Text.ToLowerInvariant(); foreach ($p in $Protect) { if ($t.Contains($p)) { return $true } }; return $false }
function Is-StartupJunk([string]$Name, [string]$Command) {
    $t = ($Name + ' ' + $Command).ToLowerInvariant()
    if (Is-Protected $t) { return $false }
    foreach ($p in $StartupOff) { if ($t.Contains($p)) { return $true } }
    return $false
}
# ET clock: the deep part never runs while the bot can trade (weekdays 01:15-16:05 ET)
function Get-ET { try { return [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Eastern Standard Time') } catch { return [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'America/New_York') } }
function Is-TradingWindow([DateTime]$Et) {
    if ($Et.DayOfWeek -eq 'Saturday' -or $Et.DayOfWeek -eq 'Sunday') { return $false }
    $m = $Et.Hour * 60 + $Et.Minute
    return ($m -ge 75 -and $m -lt 965)          # 01:15 - 16:05 ET
}
function Deep-Allowed { return -not (Is-TradingWindow (Get-ET)) }

function Mem-Line {
    try {
        $os = Get-CimInstance Win32_OperatingSystem
        $tot = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1); $free = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
        $used = [math]::Round(100 * (1 - $os.FreePhysicalMemory / $os.TotalVisibleMemorySize))
        $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
        return [pscustomobject]@{ Used = $used; FreeGB = $free; TotalGB = $tot; Cpu = $cpu; Text = "memory $used% used ($free GB free of $tot GB), CPU $cpu%" }
    } catch { return [pscustomobject]@{ Used = $null; FreeGB = $null; TotalGB = $null; Cpu = $null; Text = 'memory: not readable' } }
}
function Top-Programs([int]$N = 12) {
    try {
        Get-Process | Group-Object ProcessName | ForEach-Object { [pscustomobject]@{ Name = $_.Name; MB = [math]::Round((($_.Group | Measure-Object WorkingSet64 -Sum).Sum) / 1MB) } } |
            Sort-Object MB -Descending | Select-Object -First $N
    } catch { @() }
}
function Disabled-Bytes { $b = New-Object byte[] 12; $b[0] = 3; [BitConverter]::GetBytes((Get-Date).ToFileTime()).CopyTo($b, 4); return ,$b }
function Set-StartupOff([string]$ApprovedKey, [string]$ValueName) {
    if ($DryRun) { return $true }
    try {
        if (-not (Test-Path $ApprovedKey)) { New-Item -Path $ApprovedKey -Force | Out-Null }
        New-ItemProperty -Path $ApprovedKey -Name $ValueName -PropertyType Binary -Value (Disabled-Bytes) -Force | Out-Null
        return $true
    } catch { return $false }
}
function Set-Reg([string]$Key, [string]$Name, $Value, [string]$Type = 'DWord') {
    if ($DryRun) { return $true }
    try { if (-not (Test-Path $Key)) { New-Item -Path $Key -Force | Out-Null }; New-ItemProperty -Path $Key -Name $Name -Value $Value -PropertyType $Type -Force | Out-Null; return $true } catch { return $false }
}
function Remove-Old([string]$Dir, [int]$Days, [string]$Filter = '*') {
    $n = 0; $bytes = 0
    if (-not $Dir -or -not (Test-Path -LiteralPath $Dir)) { return @(0, 0) }
    $cut = (Get-Date).AddDays(-$Days)
    Get-ChildItem -LiteralPath $Dir -Filter $Filter -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt $cut } | ForEach-Object {
        $len = $_.Length
        if ($DryRun) { $n++; $bytes += $len } else { try { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop; $n++; $bytes += $len } catch { } }
    }
    return @($n, $bytes)
}
function MB($b) { return [math]::Round($b / 1MB) }

# ================================================================== the deep part (elevated)
if ($AdminPart) {
    Head "DEEP PART (Administrator)$(if ($DryRun) { ' - dry run, nothing changed' })"
    if (-not (Deep-Allowed)) { Say 'SKIP' 'Trading hours (weekdays 01:15-16:05 ET): the deep part waits. Double-click CLEAN_PC.bat again after 4:05 PM ET.'; exit 0 }
    # 6. Windows Search indexing off
    try {
        $s = Get-Service WSearch -ErrorAction Stop
        if (-not $DryRun) { Stop-Service WSearch -Force -ErrorAction SilentlyContinue; Set-Service WSearch -StartupType Disabled -ErrorAction Stop }
        Say 'OK' "Windows Search indexing off (was $($s.Status)); the Start menu still finds apps. Back on: services.msc > Windows Search > Automatic."
    } catch { Say 'SKIP' "Windows Search indexing: $($_.Exception.Message)" }
    # 7. Store apps in the background
    if (Set-Reg 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy' 'LetAppsRunInBackground' 2) { Say 'OK' 'Store apps no longer run in the background (desktop programs such as NinjaTrader are not affected)' }
    else { Say 'SKIP' 'Store apps in the background: not changed' }
    # 8. Windows junk
    $r = Remove-Old "$env:WINDIR\Temp" 2; Say 'OK' "Windows Temp: $($r[0]) files, $(MB $r[1]) MB"
    $wer = 0; foreach ($d in @("$env:ProgramData\Microsoft\Windows\WER\ReportArchive", "$env:ProgramData\Microsoft\Windows\WER\ReportQueue")) { $x = Remove-Old $d 0; $wer += $x[1] }
    Say 'OK' "Windows error reports: $(MB $wer) MB"
    $r = Remove-Old "$env:WINDIR\Minidump" 0; Say 'OK' "Crash dumps (Windows): $($r[0]) files, $(MB $r[1]) MB"
    try { if (-not $DryRun) { Delete-DeliveryOptimizationCache -Force -ErrorAction Stop | Out-Null }; Say 'OK' 'Delivery Optimization cache emptied' } catch { Say 'SKIP' 'Delivery Optimization cache: not available here' }
    # 10. component store (slow): only when there is time before 01:15 ET
    if (Deep-Allowed) {
        Say '..' 'Windows component store clean-up (old update files). This can take 10-30 minutes on this PC; leave the window open.'
        if (-not $DryRun) { & dism.exe /Online /Cleanup-Image /StartComponentCleanup /Quiet; if ($LASTEXITCODE -eq 0) { Say 'OK' 'Component store cleaned' } else { Say 'SKIP' "Component store clean-up ended with code $LASTEXITCODE" } }
    } else { Say 'SKIP' 'Component store clean-up: too close to trading hours; next time after 4:05 PM ET' }
    # 11. Defender quick scan
    if (Deep-Allowed) {
        try { if (-not $DryRun) { Start-MpScan -ScanType QuickScan -ErrorAction Stop }; Say 'OK' 'Microsoft Defender quick scan done' } catch { Say 'SKIP' "Defender quick scan: $($_.Exception.Message)" }
    } else { Say 'SKIP' 'Defender quick scan: too close to trading hours; next time after 4:05 PM ET' }
    exit 0
}

# ================================================================== the light part (the signed-in user)
Head "CLEAN PC: $(Get-Date -Format 'ddd yyyy-MM-dd HH:mm')$(if ($DryRun) { ' - DRY RUN: shows the plan, changes nothing' })"
$before = Mem-Line
Say '..' "Before: $($before.Text)"
Say '..' ('Using the most memory: ' + ((Top-Programs 12 | ForEach-Object { "$($_.Name) $($_.MB) MB" }) -join ', '))

# 2. close what trading does not need
Head 'Programs closed now (not needed for trading)'
$closed = @()
foreach ($name in $CloseProcs) {
    $ps = @(Get-Process -Name $name -ErrorAction SilentlyContinue)
    if ($ps.Count -eq 0) { continue }
    $mb = [math]::Round((($ps | Measure-Object WorkingSet64 -Sum).Sum) / 1MB)
    if (-not $DryRun) { $ps | Stop-Process -Force -ErrorAction SilentlyContinue }
    $closed += "$name ($mb MB)"
}
if ($closed.Count) { Say 'OK' ('Closed: ' + ($closed -join ', ')) } else { Say 'OK' 'Nothing to close' }

# 3. keep them from starting at sign-in (Task Manager's own switch)
Head 'Start at sign-in'
$off = @(); $kept = @()
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
try {
    $props = Get-ItemProperty -Path $runKey -ErrorAction Stop
    foreach ($p in $props.PSObject.Properties) {
        if ($p.Name -like 'PS*') { continue }
        if (Is-StartupJunk $p.Name ([string]$p.Value)) {
            if (Set-StartupOff 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run' $p.Name) { $off += $p.Name }
        } else { $kept += $p.Name }
    }
} catch { }
$startDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
if (Test-Path -LiteralPath $startDir) {
    Get-ChildItem -LiteralPath $startDir -File -ErrorAction SilentlyContinue | ForEach-Object {
        if (Is-StartupJunk $_.Name '') {
            if (Set-StartupOff 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder' $_.Name) { $off += $_.BaseName }
        } else { $kept += $_.BaseName }
    }
}
if ($off.Count) { Say 'OK' ('Off at sign-in: ' + ($off -join ', ') + '  (back on: Task Manager > Startup apps > Enable)') } else { Say 'OK' 'No extra apps start at sign-in' }
if ($kept.Count) { Say '..' ('Still starting (left as is): ' + ($kept -join ', ')) }

# 4. a lighter Windows
Head 'A lighter Windows'
$tw = @()
if (Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize' 'EnableTransparency' 0) { $tw += 'transparency off' }
if (Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'TaskbarAnimations' 0) { $tw += 'taskbar animations off' }
if (Set-Reg 'HKCU:\Control Panel\Desktop\WindowMetrics' 'MinAnimate' '0' 'String') { $tw += 'window animations off' }
if (Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'TaskbarDa' 0) { $tw += 'Widgets button off' }
if (Set-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'ShowCopilotButton' 0) { $tw += 'Copilot button off' }
$cdm = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager'
$sug = $true
foreach ($n in @('SilentInstalledAppsEnabled', 'SystemPaneSuggestionsEnabled', 'SoftLandingEnabled', 'SubscribedContent-338388Enabled', 'SubscribedContent-338389Enabled')) { if (-not (Set-Reg $cdm $n 0)) { $sug = $false } }
if ($sug) { $tw += 'no suggested or silently installed apps' }
Say 'OK' (($tw -join ', ') + ' (fully applied after the next restart)')

# 5. junk
Head 'Junk files'
$r = Remove-Old $env:TEMP 2; Say 'OK' "Your Temp folder: $($r[0]) files, $(MB $r[1]) MB"
$r = Remove-Old (Join-Path $env:LOCALAPPDATA 'CrashDumps') 0; Say 'OK' "Crash dumps: $($r[0]) files, $(MB $r[1]) MB"
$ntDirs = @()
foreach ($docs in @([Environment]::GetFolderPath('MyDocuments'), $(if ($env:OneDrive) { Join-Path $env:OneDrive 'Documents' }))) {
    if ($docs) { $nt = Join-Path $docs 'NinjaTrader 8'; if ((Test-Path -LiteralPath $nt) -and ($ntDirs -notcontains $nt)) { $ntDirs += $nt } }
}
$ntN = 0; $ntB = 0
foreach ($nt in $ntDirs) { foreach ($sub in @('log', 'trace')) { $x = Remove-Old (Join-Path $nt $sub) 14 '*.txt'; $ntN += $x[0]; $ntB += $x[1] } }
Say 'OK' "NinjaTrader's old log and trace files (14+ days): $ntN files, $(MB $ntB) MB (today's are kept)"

# the deep part: elevated, outside trading hours
if (-not $LightOnly) {
    Head 'Deep clean (needs Administrator)'
    if (-not (Deep-Allowed)) {
        Say 'SKIP' 'Trading hours (weekdays 01:15-16:05 ET): the deep part waits so it never slows the bot. Double-click CLEAN_PC.bat again after 4:05 PM ET.'
    } elseif ($DryRun) {
        Say '..' 'Would ask Windows for Administrator and run steps 6-11 (search indexing off, background Store apps off, Windows junk, unused preinstalled apps, component store, Defender quick scan).'
    } else {
        # 9. preinstalled apps: removed for this user (here, not elevated: the apps belong to the signed-in user)
        $gone = @()
        foreach ($a in $BloatApps) {
            $pk = @(Get-AppxPackage -Name $a -ErrorAction SilentlyContinue)
            foreach ($p in $pk) { try { Remove-AppxPackage -Package $p.PackageFullName -ErrorAction Stop; $gone += $a.Split('.')[-1] } catch { } }
        }
        if ($gone.Count) { Say 'OK' ('Removed preinstalled apps: ' + (($gone | Select-Object -Unique) -join ', ') + ' (the Microsoft Store has them back if wanted)') } else { Say 'OK' 'No unused preinstalled apps left to remove' }
        Say '..' 'Windows asks "Do you want to allow this app to make changes?": click Yes. The deep part runs in a second window; this one waits for it.'
        try {
            $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-AdminPart', '-Log', "`"$Log`"")
            $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $argList -Verb RunAs -PassThru -Wait
            if ($p.ExitCode -eq 0) { Say 'OK' 'Deep part done (its lines are in the log)' } else { Say 'SKIP' "Deep part ended with code $($p.ExitCode)" }
        } catch { Say 'SKIP' 'Deep part not run (Administrator was declined). Double-click CLEAN_PC.bat again and click Yes.' }
    }
}

# after
Start-Sleep -Seconds 3
$after = Mem-Line
Head 'Result'
Say 'OK' "After: $($after.Text)"
if ($before.FreeGB -ne $null -and $after.FreeGB -ne $null) { Say 'OK' ("Memory freed: about " + [math]::Round(($after.FreeGB - $before.FreeGB) * 1024) + " MB") }
Say '..' "Full log: $Log"
Say '..' 'NinjaTrader and the bot were not touched. A restart finishes the Windows changes: do it after 4 PM ET (the bot comes back by itself; open the MNQ chart with LE_BarFeed again if it does not reopen).'
exit 0
