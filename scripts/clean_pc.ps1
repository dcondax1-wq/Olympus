<#
CLEAN_PC (double-click CLEAN_PC.bat in the bot folder). The owner, 2026-11-01: "start clearing my pc and make it run smoothly,
go deep". The Surface has 3.6 GB of memory and ran at 90%+ with the CPU at 100%, which slows NinjaTrader and the bot and heats
the tablet (its screen glitches when hot). This makes it lighter. NinjaTrader, the bot (python), PowerShell, Edge (the Start
page), Explorer, OneDrive (Documents and NinjaTrader's folder may live in OneDrive), Git and the Claude app are never touched.

LIGHT part (any time, also while the bot trades; no Administrator):
  1. before: memory, CPU, the 12 programs using the most memory, disk
  2. closes programs not needed for trading (Discord, Spotify, Steam, Epic, Teams, Skype, Zoom, Widgets,
     Phone Link, Xbox / Game Bar, Telegram, WhatsApp ...)
  3. keeps those from starting at sign-in: the same switch as Task Manager > Startup apps > Disabled (turn one back on there).
     Obsidian is protected (2026-11-03: the owner's notes vault, Jarvis syncs it with Obsidian Git): never closed, never
     switched off, and a sign-in entry an older CLEAN_PC switched off is switched back on (every run and -Undo).
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
 12. v2 DEEP TUNE (scripts\pc_tune.ps1, before step 10): a trading power plan (Surface: CPU capped for less heat), unneeded
     services off, memory settings by RAM size, Defender skips only NinjaTrader's / the bot's data folders, network power
     saving off, Edge / Chrome / Office lighter, Storage Sense, a priority helper task and a Sunday care task. Every change is
     recorded first and UNDO_PC_TUNE.bat (or -Undo) puts it all back. Details: the top of scripts\pc_tune.ps1.
  after: memory again and what changed, a HEALTH SCORE before and after (0-100: free memory, CPU idle, start-up apps, free
  disk, temperature when readable). Log: logs\clean_pc-YYYYMMDD-HHMM.txt
ALSO (read-only, every run):
  NinjaTrader check: reads (never changes) NinjaTrader's folder: OneDrive sync, workspaces and charts (days loaded, Tick
     Replay, indicators), ATI, the size of its historical data; prints what to change by hand. Copies the workspaces to
     logs\nt_workspaces-YYYYMMDD (a backup before you change anything). NinjaTrader is never closed or modified.
  PC report: CPU, cores, memory (total, speed, slots), disks (SSD/HDD, free), graphics, Windows build, power plan,
     start-up programs -> PC_REPORT-<computer>.txt next to CLEAN_PC.bat.

MAIN PC (no bot folder): copy the PC_KIT folder (CLEAN_PC.bat + scripts\clean_pc.ps1; the Surface run puts it in
  OneDrive\PC_KIT, or on the Desktop) and double-click CLEAN_PC.bat there. It sees there is no bot (no server.py) and
  runs STANDALONE: it closes nothing that is running (it only lists it), keeps the Xbox / gaming apps, and the deep part
  runs any time unless NinjaTrader is open (then the same 01:15-16:05 ET weekday wait). -Standalone forces this mode.

  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\clean_pc.ps1            (CLEAN_PC.bat runs this)
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\clean_pc.ps1 -DryRun    (shows the plan, changes nothing)
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\clean_pc.ps1 -Report    (only the PC report + NinjaTrader check)
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\clean_pc.ps1 -Undo      (undo the deep tune; UNDO_PC_TUNE.bat)
#>
param(
    [switch]$DryRun,
    [switch]$LightOnly,
    [switch]$Standalone,    # main PC: no bot folder (auto when server.py / engine\ninjatrader.py are missing)
    [switch]$Report,        # only the PC report and the NinjaTrader check; changes nothing
    [switch]$Undo,          # undo the v2 deep tune (scripts\pc_tune.ps1 -Undo)
    [switch]$AdminPart,     # internal: the elevated deep part, started by this script with a UAC prompt
    [string]$Log = ""       # internal: the same log file for both parts
)

$ErrorActionPreference = 'Continue'
$script:HealthBefore = $null
$Root = Split-Path -Parent $PSScriptRoot
function Test-BotFolder([string]$Dir) {
    if (-not $Dir) { return $false }
    return ((Test-Path -LiteralPath (Join-Path $Dir 'server.py')) -and (Test-Path -LiteralPath (Join-Path (Join-Path $Dir 'engine') 'ninjatrader.py')))
}
if (-not (Test-BotFolder $Root)) { $Standalone = $true }
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
$Protect = @('ninjatrader', 'liquidity', 'le start', 'le_start', 'python', 'pythonw', 'onedrive', 'obsidian', 'securityhealth', 'windowsdefender',
             'msmpeng', 'realtek', 'rtkaud', 'intel', 'igfx', 'surface', 'synaptics', 'bluetooth', 'audio', 'claude', 'git')
# process names (exact, any case) closed now
$CloseProcs = @('Discord', 'Spotify', 'steam', 'steamwebhelper', 'EpicGamesLauncher', 'EpicWebHelper', 'Teams', 'ms-teams',
                'msteams', 'Skype', 'Zoom', 'Telegram', 'WhatsApp', 'Messenger', 'Widgets', 'WidgetService', 'PhoneExperienceHost',
                'YourPhone', 'GameBar', 'GameBarFTServer', 'XboxPcApp', 'XboxPcAppFT', 'Overwolf', 'RiotClientServices', 'Battle.net',
                'EADesktop', 'Origin', 'GrammarlyHelper', 'Grammarly.Desktop')
# start-up entries (name or command contains, any case) switched off at sign-in
$StartupOff = @('discord', 'spotify', 'steam', 'epicgames', 'teams', 'skype', 'zoom', 'telegram', 'whatsapp', 'messenger',
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
# ET clock: the deep part never runs while the bot can trade (weekdays 01:15-16:05 ET). LE_T_ET: test clock only.
function Get-ET {
    if ($env:LE_T_ET) { return [DateTime]::Parse($env:LE_T_ET, [Globalization.CultureInfo]::InvariantCulture) }
    try { return [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Eastern Standard Time') } catch { return [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'America/New_York') } }
function Is-TradingWindow([DateTime]$Et) {
    if ($Et.DayOfWeek -eq 'Saturday' -or $Et.DayOfWeek -eq 'Sunday') { return $false }
    $m = $Et.Hour * 60 + $Et.Minute
    return ($m -ge 75 -and $m -lt 965)          # 01:15 - 16:05 ET
}
function Nt-Running { return (@(Get-Process -Name 'NinjaTrader' -ErrorAction SilentlyContinue).Count -gt 0) }
# the main PC (standalone) without NinjaTrader open has no trading hours to protect
function Test-DeepAllowed([DateTime]$Et, [bool]$IsStandalone, [bool]$NtOpen) {
    if ($IsStandalone -and -not $NtOpen) { return $true }
    return -not (Is-TradingWindow $Et)
}
function Deep-Allowed { return (Test-DeepAllowed (Get-ET) ([bool]$Standalone) (Nt-Running)) }

function Mem-Line {
    try {
        $os = Get-CimInstance Win32_OperatingSystem
        $tot = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1); $free = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
        $used = [math]::Round(100 * (1 - $os.FreePhysicalMemory / $os.TotalVisibleMemorySize))
        $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
        return [pscustomobject]@{ Used = $used; FreeGB = $free; TotalGB = $tot; Cpu = $cpu; Text = "memory $used% used ($free GB free of $tot GB), CPU $cpu%" }
    } catch { return [pscustomobject]@{ Used = $null; FreeGB = $null; TotalGB = $null; Cpu = $null; Text = 'memory: not readable' } }
}
# HEALTH SCORE 0-100 (higher = more room for NinjaTrader and the bot): free memory 30, CPU idle 30, start-up apps 15,
# free disk 15, temperature 10 (when Windows lets it be read; otherwise the other parts are scaled to 100)
function Get-HealthScore($FreePct, $IdlePct, $Startup, $DiskGB, $TempC) {
    $pts = 0.0; $max = 0.0
    if ($null -ne $FreePct) { $pts += 30 * [math]::Min(1, [math]::Max(0, [double]$FreePct / 40)); $max += 30 }
    if ($null -ne $IdlePct) { $pts += 30 * [math]::Min(1, [math]::Max(0, [double]$IdlePct / 100)); $max += 30 }
    if ($null -ne $Startup) { $pts += 15 * [math]::Max(0, 1 - [double]$Startup / 20); $max += 15 }
    if ($null -ne $DiskGB) { $pts += 15 * [math]::Min(1, [math]::Max(0, [double]$DiskGB / 30)); $max += 15 }
    if ($null -ne $TempC) { $pts += 10 * [math]::Min(1, [math]::Max(0, (95 - [double]$TempC) / 35)); $max += 10 }
    if ($max -le 0) { return $null }
    return [int][math]::Round(100 * $pts / $max)
}
function Measure-Health {
    $free = $null; $idle = $null; $st = $null; $disk = $null; $temp = $null
    try { $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop; $free = [math]::Round(100 * $os.FreePhysicalMemory / $os.TotalVisibleMemorySize) } catch { }
    try {
        $s = @()
        for ($i = 0; $i -lt 3; $i++) {
            $s += [double]((@(Get-CimInstance Win32_Processor -ErrorAction Stop) | Measure-Object -Property LoadPercentage -Average).Average)
            if ($i -lt 2) { Start-Sleep -Milliseconds 700 }
        }
        $idle = [math]::Round(100 - (($s | Measure-Object -Average).Average))
    } catch { }
    try { $st = @(Get-CimInstance Win32_StartupCommand -ErrorAction Stop).Count } catch { }
    try {
        $sd = $env:SystemDrive; if (-not $sd) { $sd = 'C:' }
        foreach ($v in @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' -ErrorAction Stop)) { if ("$($v.DeviceID)" -eq $sd) { $disk = [math]::Round($v.FreeSpace / 1GB) } }
    } catch { }
    try {
        $tz = @(Get-CimInstance -Namespace 'root/wmi' -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop)
        $k = ($tz | Measure-Object -Property CurrentTemperature -Maximum).Maximum
        if ($k -gt 2732) { $temp = [math]::Round(($k - 2732) / 10) }
    } catch { }
    $score = Get-HealthScore $free $idle $st $disk $temp
    $parts = @()
    if ($null -ne $free) { $parts += "memory $free% free" }
    if ($null -ne $idle) { $parts += "CPU $idle% idle" }
    if ($null -ne $st) { $parts += "$st start-up apps" }
    if ($null -ne $disk) { $parts += "$disk GB disk free" }
    if ($null -ne $temp) { $parts += "$temp C" } else { $parts += 'temperature not readable' }
    $txt = 'not readable'; if ($null -ne $score) { $txt = "$score/100 (" + ($parts -join ', ') + ')' }
    return [pscustomobject]@{ Score = $score; Text = $txt }
}
function Get-TuneStateLine {
    $f = ''; if ($env:ProgramData) { $f = Join-Path (Join-Path $env:ProgramData 'LiquidityEngine') 'pc_tune_state.json' }
    if (-not $f -or -not (Test-Path -LiteralPath $f)) { return 'not applied yet (CLEAN_PC.bat applies it outside trading hours)' }
    try { $o = (Get-Content -LiteralPath $f -Raw -ErrorAction Stop) | ConvertFrom-Json; return "on, $(@($o.changes).Count) changes saved $($o.saved) (undo: UNDO_PC_TUNE.bat)" } catch { return 'on (undo: UNDO_PC_TUNE.bat)' }
}
function Top-Programs([int]$N = 12) {
    try {
        Get-Process | Group-Object ProcessName | ForEach-Object { [pscustomobject]@{ Name = $_.Name; MB = [math]::Round((($_.Group | Measure-Object WorkingSet64 -Sum).Sum) / 1MB) } } |
            Sort-Object MB -Descending | Select-Object -First $N
    } catch { @() }
}
function Disabled-Bytes { $b = New-Object byte[] 12; $b[0] = 3; [BitConverter]::GetBytes((Get-Date).ToFileTime()).CopyTo($b, 4); return ,$b }
# StartupApproved values: byte 0 odd (3) = switched off in Task Manager, even (2) = on
function Test-StartupDisabled($Bytes) { $b = @($Bytes); return ($b.Count -gt 0 -and (([int]$b[0]) -band 1) -eq 1) }
function Enabled-Bytes { $b = New-Object byte[] 12; $b[0] = 2; return ,$b }
# protected sign-in entries (Obsidian: an older CLEAN_PC switched it off) found off are switched back on: [names]
function Restore-ProtectedStartup {
    $back = @()
    foreach ($k in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run',
                     'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder')) {
        $props = $null; try { $props = Get-ItemProperty -Path $k -ErrorAction Stop } catch { continue }
        foreach ($p in $props.PSObject.Properties) {
            if ($p.Name -like 'PS*') { continue }
            if (-not ($p.Name.ToLowerInvariant().Contains('obsidian'))) { continue }
            if (-not (Test-StartupDisabled $p.Value)) { continue }
            if (-not $DryRun) { try { New-ItemProperty -Path $k -Name $p.Name -PropertyType Binary -Value (Enabled-Bytes) -Force -ErrorAction Stop | Out-Null } catch { continue } }
            $back += $p.Name
        }
    }
    return ,$back
}
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

# ================================================================== NinjaTrader check (read-only: never closes or changes NinjaTrader)
function Get-NtFolders {
    $out = @()
    $cands = @($env:NINJATRADER_FOLDER)
    foreach ($docs in @([Environment]::GetFolderPath('MyDocuments'), $(if ($env:OneDrive) { Join-Path $env:OneDrive 'Documents' }))) {
        if ($docs) { $cands += (Join-Path $docs 'NinjaTrader 8') }
    }
    foreach ($nt in $cands) { if ($nt -and (Test-Path -LiteralPath $nt) -and ($out -notcontains $nt)) { $out += $nt } }
    return ,$out
}
# read a file NinjaTrader may have open, without locking it (FileShare ReadWrite + Delete)
function Read-Shared([string]$Path) {
    try {
        $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
        try { $sr = New-Object System.IO.StreamReader($fs); return $sr.ReadToEnd() } finally { $fs.Dispose() }
    } catch { return '' }
}
function Test-InOneDrive([string]$Path) {
    if (-not $Path) { return $false }
    $p = $Path.ToLowerInvariant()
    if ($env:OneDrive -and $p.StartsWith($env:OneDrive.ToLowerInvariant())) { return $true }
    return ($p.Contains('\onedrive') -or $p.Contains('/onedrive'))
}
# what one NinjaTrader 8 workspace file holds: charts (data series), days loaded, Tick Replay, indicators, the bot's LE_BarFeed
function Get-WorkspaceStats([string]$Xml) {
    $days = @(); foreach ($m in [regex]::Matches($Xml, '<DaysBack>\s*(\d+)\s*</DaysBack>')) { $days += [int]$m.Groups[1].Value }
    $tick = [regex]::Matches($Xml, '(?i)<IsTickReplay>\s*true\s*</IsTickReplay>').Count
    $ind = @(); foreach ($m in [regex]::Matches($Xml, 'NinjaTrader\.NinjaScript\.Indicators\.([A-Za-z_][\w\.]*)')) { $ind += $m.Groups[1].Value }
    $maxDays = 0; foreach ($d in $days) { if ($d -gt $maxDays) { $maxDays = $d } }
    return [pscustomobject]@{
        Series = $days.Count; Days = $days; MaxDays = $maxDays; TickReplay = $tick
        Indicators = @($ind | Select-Object -Unique); IndicatorCount = $ind.Count
        HasBarFeed = ($Xml -match 'LE_BarFeed')
    }
}
# plain-language advice for one workspace (the bot chart keeps 30 days: GO_LIVE_TONIGHT "Keep the NinjaTrader chart at 30 days loaded")
function Get-WorkspaceAdvice([string]$Name, $St) {
    $a = @()
    if ($St.TickReplay -gt 0) { $a += "$Name : Tick Replay is ON in $($St.TickReplay) data series (heavy on memory and CPU): chart > Data Series (Ctrl+F) > Tick Replay off" }
    if ($St.HasBarFeed) {
        if ($St.MaxDays -gt 0 -and $St.MaxDays -lt 30) { $a += "$Name : the bot chart (LE_BarFeed) loads $($St.MaxDays) days: keep it at 30 (Data Series > Days to load 30)" }
        $big = @($St.Days | Where-Object { $_ -gt 30 })
        if ($big.Count) { $a += "$Name : $($big.Count) chart(s) load more than 30 days (most $($St.MaxDays)): the bot chart needs 30, charts you only look at 3-5 days (Data Series > Days to load)" }
        if ($St.Series -gt 2) { $a += "$Name : the bot's workspace has $($St.Series) data series: keep only the MNQ chart with LE_BarFeed in it, move other charts to a second workspace you close while the bot trades" }
    } else {
        if ($St.MaxDays -gt 10) { $a += "$Name : a chart loads $($St.MaxDays) days: 3-5 days is plenty for looking (Data Series > Days to load)" }
    }
    if ($St.IndicatorCount -gt 8) { $a += "$Name : $($St.IndicatorCount) indicators ($((@($St.Indicators) | Select-Object -First 8) -join ', ')...): remove the ones you do not look at (chart > Indicators)" }
    return ,$a
}
function Dir-Bytes([string]$Dir) {
    if (-not (Test-Path -LiteralPath $Dir)) { return 0 }
    $fs = @(Get-ChildItem -LiteralPath $Dir -Recurse -File -Force -ErrorAction SilentlyContinue)
    if ($fs.Count -eq 0) { return 0 }
    return [double](($fs | Measure-Object -Property Length -Sum).Sum)
}
function Get-AtiState([string]$Nt) {
    $cfg = Read-Shared (Join-Path $Nt 'config.xml')
    $m = [regex]::Match($cfg, '(?i)<(?:IsAtiEnabled|AtiEnabled|IsAutomatedTradingInterfaceEnabled)>\s*(true|false)\s*<')
    if ($m.Success) { return $m.Groups[1].Value.ToLowerInvariant() }
    if ((Test-Path -LiteralPath (Join-Path $Nt 'incoming')) -and (Test-Path -LiteralPath (Join-Path $Nt 'outgoing'))) { return 'looks on' }
    return 'unknown'
}
function NinjaTrader-Check([bool]$Backup) {
    Head 'NinjaTrader check (read-only: NinjaTrader is never closed or changed)'
    $nt = @(Get-Process -Name 'NinjaTrader' -ErrorAction SilentlyContinue)
    if ($nt.Count) {
        $mb = [math]::Round((($nt | Measure-Object WorkingSet64 -Sum).Sum) / 1MB)
        Say '..' "NinjaTrader is running and uses $mb MB of memory (under ~1,500 MB is healthy with one or two charts)"
    } else { Say '..' 'NinjaTrader is not running' }
    $dirs = Get-NtFolders
    if ($dirs.Count -eq 0) { Say 'OK' 'No NinjaTrader 8 folder on this PC'; return }
    foreach ($d in $dirs) {
        Say '..' "Folder: $d"
        if (Test-InOneDrive $d) { Say 'SKIP' 'It is inside OneDrive: OneDrive can lock the bar and order files while it uploads them. OneDrive tray icon > Pause syncing while trading (NinjaTrader advises not to sync its folder).' }
        else { Say 'OK' 'Not synced by OneDrive' }
        $ati = Get-AtiState $d
        if ($ati -eq 'false') { Say 'FIX' 'ATI is OFF: Tools > Options > Automated trading interface > AT Interface (the bot needs it)' }
        elseif ($ati -eq 'unknown') { Say '..' 'ATI: not readable here; check Tools > Options > Automated trading interface > AT Interface is ticked' }
        else { Say 'OK' "ATI (automated trading interface): $ati" }
        $ws = Join-Path $d 'workspaces'
        $files = @(Get-ChildItem -LiteralPath $ws -Filter '*.xml' -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike '_*' })
        $advice = @()
        foreach ($f in $files) {
            $st = Get-WorkspaceStats (Read-Shared $f.FullName)
            Say '..' ("Workspace '{0}': {1} data series, most days loaded {2}, Tick Replay {3}, {4} indicators{5}" -f $f.BaseName, $st.Series, $st.MaxDays, $(if ($st.TickReplay) { 'ON' } else { 'off' }), $st.IndicatorCount, $(if ($st.HasBarFeed) { ', has the bot chart (LE_BarFeed)' } else { '' }))
            $advice += Get-WorkspaceAdvice $f.BaseName $st
        }
        if ($files.Count -gt 2) { $advice += "$($files.Count) workspaces saved: keep the bot's open, close the rest while the bot trades (File > Workspaces > Close)" }
        foreach ($a in $advice) { Say 'SKIP' $a }
        if ($files.Count -and -not $advice.Count) { Say 'OK' 'Workspaces look light' }
        $tickGB = [math]::Round((Dir-Bytes (Join-Path (Join-Path $d 'db') 'tick')) / 1GB, 1)
        $minGB = [math]::Round((Dir-Bytes (Join-Path (Join-Path $d 'db') 'minute')) / 1GB, 1)
        Say '..' "Historical data: tick $tickGB GB, minute $minGB GB"
        if ($tickGB -ge 2) { Say 'SKIP' 'Old tick data is big: Tools > Historical Data > Tick > delete months you do not need (the bot uses minute bars)' }
        if ($Backup -and $files.Count -and -not $DryRun) {
            try {
                $bk = Join-Path $LogDir ('nt_workspaces-' + (Get-Date -Format 'yyyyMMdd'))
                if (-not (Test-Path -LiteralPath $bk)) { New-Item -ItemType Directory -Path $bk -Force | Out-Null }
                foreach ($f in $files) { [System.IO.File]::WriteAllText((Join-Path $bk $f.Name), (Read-Shared $f.FullName)) }
                Say 'OK' "Workspaces backed up to $bk (copy one back into $ws with NinjaTrader closed to undo a change)"
            } catch { Say 'SKIP' "Workspace backup: $($_.Exception.Message)" }
        }
    }
    Say '..' 'By hand, with NinjaTrader open (all undo-able): 1) only the windows you use: File > Workspaces, close the others;'
    Say '..' '   2) charts you only look at: Data Series > Days to load 3-5 (the bot''s MNQ chart with LE_BarFeed stays at 30);'
    Say '..' '   3) Tick Replay off, unused indicators removed, fewer Market Analyzer rows and DOMs open.'
    Say '..' '   4) Tools > Options > Market data: untick "Show Tick Replay" (then no chart can turn it on again).'
    Say '..' '   5) once a month, after 4:05 PM ET with no charts open: Tools > Database Management > Repair DB (never "Reset DB").'
    Say '..' '   6) NinjaTrader 8 inside OneDrive: pause syncing while trading. Do NOT switch off OneDrive''s Documents backup'
    Say '..' '      without asking Claude: it leaves NinjaTrader''s folder in OneDrive and starts an empty one.'
    Say '..' '   Never change these files by hand while NinjaTrader is open; this check only reads them.'
}

# ================================================================== PC report (read-only)
function Get-Verdict([double]$RamGB, [bool]$Ssd, [int]$Cores) {
    $v = @()
    if ($RamGB -ge 15) { $v += 'memory plenty for NinjaTrader + the bot' } elseif ($RamGB -ge 7.5) { $v += 'memory OK for NinjaTrader + the bot with few charts' } else { $v += 'memory TOO SMALL for NinjaTrader + the bot (8 GB minimum, 16 GB good)' }
    if ($Ssd) { $v += 'SSD' } else { $v += 'no SSD found (a hard disk makes everything slow)' }
    if ($Cores -ge 4) { $v += "$Cores cores OK" } elseif ($Cores -gt 0) { $v += "only $Cores cores (4+ recommended)" }
    $good = ($RamGB -ge 7.5) -and $Ssd -and ($Cores -ge 4)
    $head = 'WEAK bot computer: '; if ($good) { $head = 'GOOD bot computer: ' }
    return ($head + ($v -join ', '))
}
function Get-PowerModeName([string]$Guid) {
    if ($Guid -match 'ded574b5-45a0-4f42-8737-46345c09c238') { return 'Best performance' }
    if ($Guid -match '961cc777-2547-4f9d-8174-7d86181b8a7a') { return 'Best power efficiency' }
    if ($Guid -match '^0{8}-') { return 'Balanced (recommended)' }
    return 'unknown'
}
function Get-PcReport {
    $L = @()
    $mode = 'bot PC'; if ($Standalone) { $mode = 'standalone (no bot folder)' }
    $L += "PC REPORT $(Get-Date -Format 'yyyy-MM-dd HH:mm')  ($env:COMPUTERNAME)  mode: $mode"
    $ram = 0.0; $ssd = $false; $cores = 0
    try { $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop; $L += "Computer : $($cs.Manufacturer) $($cs.Model)" } catch { $L += 'Computer : not readable' }
    try {
        $cpu = @(Get-CimInstance Win32_Processor -ErrorAction Stop)
        $cores = [int](($cpu | Measure-Object NumberOfCores -Sum).Sum)
        $thr = ($cpu | Measure-Object NumberOfLogicalProcessors -Sum).Sum
        $L += "CPU      : $("$($cpu[0].Name)".Trim()), $cores cores / $thr threads, max $($cpu[0].MaxClockSpeed) MHz, load now $($cpu[0].LoadPercentage)%"
    } catch { $L += 'CPU      : not readable' }
    try {
        $mods = @(Get-CimInstance Win32_PhysicalMemory -ErrorAction Stop)
        $ram = [math]::Round((($mods | Measure-Object Capacity -Sum).Sum) / 1GB, 1)
        $slots = 0; try { $slots = [int]((@(Get-CimInstance Win32_PhysicalMemoryArray -ErrorAction Stop) | Measure-Object MemoryDevices -Sum).Sum) } catch { }
        $speed = ($mods | ForEach-Object { if ($_.ConfiguredClockSpeed) { $_.ConfiguredClockSpeed } else { $_.Speed } } | Select-Object -First 1)
        $sizes = ($mods | ForEach-Object { "$([math]::Round($_.Capacity / 1GB))GB" }) -join ' + '
        $free = ''; if ($slots -gt $mods.Count) { $free = ' (a free slot: more memory can be added)' }
        $L += "Memory   : $ram GB ($sizes) at $speed MT/s, $($mods.Count) of $slots slots used$free"
    } catch { $L += 'Memory   : not readable' }
    try {
        foreach ($d in @(Get-PhysicalDisk -ErrorAction Stop)) {
            if ("$($d.MediaType)" -eq 'SSD' -or "$($d.BusType)" -eq 'NVMe') { $ssd = $true }
            $L += "Disk     : $($d.FriendlyName), $($d.MediaType) $($d.BusType), $([math]::Round($d.Size / 1GB)) GB"
        }
    } catch { $L += 'Disk     : type not readable' }
    try {
        foreach ($v in @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' -ErrorAction Stop)) {
            $L += "Drive    : $($v.DeviceID) $([math]::Round($v.FreeSpace / 1GB)) GB free of $([math]::Round($v.Size / 1GB)) GB"
        }
    } catch { }
    try {
        foreach ($g in @(Get-CimInstance Win32_VideoController -ErrorAction Stop)) {
            $L += "Graphics : $($g.Name), driver $($g.DriverVersion), $($g.CurrentHorizontalResolution)x$($g.CurrentVerticalResolution) $($g.CurrentRefreshRate) Hz"
        }
    } catch { $L += 'Graphics : not readable' }
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        $dv = ''; try { $dv = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction Stop).DisplayVersion } catch { }
        $up = ''; try { $up = ", on for $([math]::Round(((Get-Date) - $os.LastBootUpTime).TotalHours)) h" } catch { }
        $L += "Windows  : $($os.Caption) $dv (build $($os.BuildNumber))$up"
    } catch { $L += 'Windows  : not readable' }
    try {
        $plan = (& powercfg /getactivescheme 2>$null | Out-String).Trim()
        $pm = 'unknown'; try { $pm = Get-PowerModeName ((Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes' -ErrorAction Stop).ActiveOverlayAcPowerScheme) } catch { }
        $L += "Power    : $plan; plugged-in power mode: $pm"
    } catch { $L += 'Power    : not readable' }
    try { $b = @(Get-CimInstance Win32_Battery -ErrorAction Stop); if ($b.Count) { $L += "Battery  : $($b[0].EstimatedChargeRemaining)%" } } catch { }
    $m = Mem-Line; $L += "Now      : $($m.Text)"
    $L += 'Memory hogs: ' + ((Top-Programs 10 | ForEach-Object { "$($_.Name) $($_.MB) MB" }) -join ', ')
    try {
        $st = @(Get-CimInstance Win32_StartupCommand -ErrorAction Stop | Select-Object -First 15)
        $L += "Start at sign-in ($($st.Count)): " + (($st | ForEach-Object { $_.Name }) -join ', ')
    } catch { $L += 'Start at sign-in: not readable' }
    $L += 'Verdict  : ' + (Get-Verdict $ram $ssd $cores)
    $h = Measure-Health
    if ($script:HealthBefore) { $L += "Health   : before $($script:HealthBefore.Text)"; $L += "Health   : after  $($h.Text)" } else { $L += "Health   : $($h.Text)" }
    $L += 'Tune     : ' + (Get-TuneStateLine)
    return ,$L
}
function Write-PcReport {
    Head 'PC report'
    $lines = Get-PcReport
    foreach ($l in $lines) { Say '..' $l }
    $name = $env:COMPUTERNAME; if (-not $name) { $name = 'this-pc' }
    $file = Join-Path $Root ("PC_REPORT-$name.txt")
    try { Set-Content -LiteralPath $file -Value $lines -Encoding UTF8; Say 'OK' "PC report saved: $file (send it, or a photo of it, to Claude)" } catch { Say 'SKIP' "PC report not saved: $($_.Exception.Message)" }
}
# the cleaner for the main PC: a PC_KIT folder in OneDrive (it syncs) or on the Desktop (copy it to a USB stick)
function Copy-PcKit {
    if ($Standalone -or $DryRun) { return }
    try {
        $base = $env:OneDrive; if (-not $base -or -not (Test-Path -LiteralPath $base)) { $base = [Environment]::GetFolderPath('Desktop') }
        $kit = Join-Path $base 'PC_KIT'; $ks = Join-Path $kit 'scripts'
        if (-not (Test-Path -LiteralPath $ks)) { New-Item -ItemType Directory -Path $ks -Force | Out-Null }
        Copy-Item -LiteralPath (Join-Path $Root 'CLEAN_PC.bat') -Destination $kit -Force
        Copy-Item -LiteralPath $PSCommandPath -Destination $ks -Force
        foreach ($x in @('pc_tune.ps1', 'pc_keeper.ps1')) { $src = Join-Path $PSScriptRoot $x; if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination $ks -Force } }
        $ub = Join-Path $Root 'UNDO_PC_TUNE.bat'; if (Test-Path -LiteralPath $ub) { Copy-Item -LiteralPath $ub -Destination $kit -Force }
        Say 'OK' "Cleaner for your main PC: $kit (on the main PC double-click CLEAN_PC.bat in it)"
    } catch { Say 'SKIP' "PC_KIT not copied: $($_.Exception.Message)" }
}

# ================================================================== undo the deep tune
if ($Undo) {
    $tune = Join-Path $PSScriptRoot 'pc_tune.ps1'
    $back = Restore-ProtectedStartup
    if ($back.Count) { Say 'OK' ('Switched back on at sign-in: ' + ($back -join ', ') + ' (Obsidian stays on: the owner''s notes vault)') }
    if (-not (Test-Path -LiteralPath $tune)) { Say 'FIX' 'scripts\pc_tune.ps1 is missing: nothing to undo with'; exit 1 }
    & $tune -Undo -Log $Log -DryRun:$DryRun -Standalone:$Standalone
    exit $LASTEXITCODE
}

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
    # 12. v2 deep tune (recorded first, undo-able: UNDO_PC_TUNE.bat); before the slow steps
    $tune = Join-Path $PSScriptRoot 'pc_tune.ps1'
    if (-not (Test-Path -LiteralPath $tune)) { Say 'SKIP' 'Deep tune: scripts\pc_tune.ps1 is missing (run UPDATE.bat)' }
    elseif (Deep-Allowed) { & $tune -Log $Log -DryRun:$DryRun -Standalone:$Standalone -NoElevate }
    else { Say 'SKIP' 'Deep tune: too close to trading hours; next time after 4:05 PM ET' }
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

# ================================================================== report only (changes nothing)
if ($Report) {
    Head "PC REPORT + NINJATRADER CHECK: $(Get-Date -Format 'ddd yyyy-MM-dd HH:mm') (changes nothing)"
    Write-PcReport
    NinjaTrader-Check $false
    Say '..' "Full log: $Log"
    exit 0
}

# ================================================================== the light part (the signed-in user)
Head "CLEAN PC: $(Get-Date -Format 'ddd yyyy-MM-dd HH:mm')$(if ($DryRun) { ' - DRY RUN: shows the plan, changes nothing' })$(if ($Standalone) { ' - STANDALONE (no bot folder here: main PC mode)' })"
$before = Mem-Line
Say '..' "Before: $($before.Text)"
$script:HealthBefore = Measure-Health
Say '..' "Health score before: $($script:HealthBefore.Text)"
Say '..' ('Using the most memory: ' + ((Top-Programs 12 | ForEach-Object { "$($_.Name) $($_.MB) MB" }) -join ', '))

# 2. close what trading does not need (bot PC); the main PC (standalone) only lists them: they may be in use
if ($Standalone) { Head 'Programs that slow a trading PC (standalone: left running, only listed)' } else { Head 'Programs closed now (not needed for trading)' }
$closed = @()
foreach ($name in $CloseProcs) {
    $ps = @(Get-Process -Name $name -ErrorAction SilentlyContinue)
    if ($ps.Count -eq 0) { continue }
    $mb = [math]::Round((($ps | Measure-Object WorkingSet64 -Sum).Sum) / 1MB)
    if (-not $DryRun -and -not $Standalone) { $ps | Stop-Process -Force -ErrorAction SilentlyContinue }
    $closed += "$name ($mb MB)"
}
if ($closed.Count -and $Standalone) { Say '..' ('Running now (close them yourself while trading): ' + ($closed -join ', ')) }
elseif ($closed.Count) { Say 'OK' ('Closed: ' + ($closed -join ', ')) } else { Say 'OK' 'Nothing to close' }

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
$back = Restore-ProtectedStartup
if ($back.Count) { Say 'OK' ('Switched back on at sign-in (protected, an older CLEAN_PC had switched it off): ' + ($back -join ', ')) }
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

# NinjaTrader: read-only check + workspace backup
NinjaTrader-Check $true

# the deep part: elevated, outside trading hours
if (-not $LightOnly) {
    Head 'Deep clean (needs Administrator)'
    if (-not (Deep-Allowed)) {
        if ($Standalone) { Say 'SKIP' 'NinjaTrader is open in trading hours (weekdays 01:15-16:05 ET): the deep part waits. Run it again after 4:05 PM ET or with NinjaTrader closed.' }
        else { Say 'SKIP' 'Trading hours (weekdays 01:15-16:05 ET): the deep part waits so it never slows the bot. Double-click CLEAN_PC.bat again after 4:05 PM ET.' }
    } elseif ($DryRun) {
        Say '..' 'Would ask Windows for Administrator and run steps 6-12 (search indexing off, background Store apps off, Windows junk, unused preinstalled apps, the v2 deep tune, component store, Defender quick scan).'
    } else {
        # 9. preinstalled apps: removed for this user (here, not elevated: the apps belong to the signed-in user)
        $gone = @()
        $apps = $BloatApps
        if ($Standalone) { $apps = @($BloatApps | Where-Object { $_ -notmatch 'Xbox|Gaming' }) }      # the main PC keeps its gaming apps
        foreach ($a in $apps) {
            $pk = @(Get-AppxPackage -Name $a -ErrorAction SilentlyContinue)
            foreach ($p in $pk) { try { Remove-AppxPackage -Package $p.PackageFullName -ErrorAction Stop; $gone += $a.Split('.')[-1] } catch { } }
        }
        if ($gone.Count) { Say 'OK' ('Removed preinstalled apps: ' + (($gone | Select-Object -Unique) -join ', ') + ' (the Microsoft Store has them back if wanted)') } else { Say 'OK' 'No unused preinstalled apps left to remove' }
        Say '..' 'Windows asks "Do you want to allow this app to make changes?": click Yes. The deep part runs in a second window; this one waits for it.'
        try {
            $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-AdminPart', '-Log', "`"$Log`"")
            if ($Standalone) { $argList += '-Standalone' }
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
Write-PcReport
Copy-PcKit
Say '..' "Full log: $Log"
if ($Standalone) { Say '..' 'NinjaTrader was not touched. A restart finishes the Windows changes.' }
else { Say '..' 'NinjaTrader and the bot were not touched. A restart finishes the Windows changes: do it after 4 PM ET (the bot comes back by itself; open the MNQ chart with LE_BarFeed again if it does not reopen).' }
exit 0
