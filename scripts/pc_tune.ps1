<#
PC_TUNE v2 "deep tune" (2026-11-03, owner: "a deeper code for both of my computers ... really improve performance to run
trading and business stuff"). tools\bat\CLEAN_PC.bat runs it in its Administrator part (outside trading hours); tools\bat\UNDO_PC_TUNE.bat puts
everything back. Every change is written to a state file BEFORE it is made, with the value it had, so -Undo restores
exactly what was there: %ProgramData%\LiquidityEngine\pc_tune_state.json. The log says what changed and why.
NinjaTrader and python are never closed, NinjaTrader's files are never changed, nothing is downloaded.

Two kinds of PC (found by itself; -Kind surface|desktop forces it):
  surface  = a hot, small PC (a Surface, or a laptop with 8 GB or less): cooler first
  desktop  = the main PC: full speed when plugged in
and two roles: the bot PC (the bot folder is here) or STANDALONE (the main PC from the PC_KIT folder: business mode).

What it changes (each one undone by -Undo):
  1. Power plan "Liquidity Engine trading" (a copy; the old plan stays and comes back on undo), plugged-in only:
     never sleeps / hibernates, disk never sleeps, USB selective suspend off, Wi-Fi power saving off;
     desktop: based on Ultimate / High performance, PCI Express link power saving off;
     surface: based on Balanced, the CPU's top speed capped at 2,800 MHz (-MaxMHz): far less heat, nearly the same speed
     under load (a hot Surface throttles below that anyway). Not "max processor state 85%": below 100% switches turbo
     off, and this Surface's base clock is 1.1 GHz.
  2. Services a trading PC does not need (list below, each with the reason); Print Spooler only when no printer.
     Never a security, update or network service ($NeverServices).
  3. Memory: compressed memory kept ON; SysMain (Superfetch) off when the PC has 6 GB or less on an SSD (it fills scarce
     memory with guesses); the page file goes back to "system managed" only if someone made it too small.
  4. Microsoft Defender: real-time scanning skips ONLY NinjaTrader 8's db, log and trace folders and the bot's data and
     logs folders (their many small writes stall behind the scanner). Trade-off: files dropped there are not scanned on
     write; the weekly scan still covers the rest of the PC. Nothing else is excluded, no process is excluded.
  5. Network: the network card's energy-saving (Energy Efficient / Green Ethernet) off, "Allow the computer to turn off this
     device to save power" off. Not done, on purpose: Nagle / TcpAckFrequency tweaks (NinjaTrader's data is not small-
     packet chatter: folklore) and DNS changes (only the first lookup uses DNS).
  6. Browsers: Edge startup boost and background running off, sleeping tabs on (surface: efficiency mode on);
     Chrome (if installed) background running off, Memory Saver on; the Office startup-boost task off.
  7. Windows: Storage Sense on (temp files, recycle bin after 30 days; Downloads and OneDrive files never touched);
     bot PC: Game Bar background recording off.
  8. Two scheduled tasks:
     LiquidityEngine-Keeper     every 15 min + at sign-in, hidden: NinjaTrader (and the bot's python) AboveNormal
                                priority, heavy background apps BelowNormal; when memory is 85%+ used it trims idle
                                background apps' memory (scripts\pc_keeper.ps1). Never closes anything.
     LiquidityEngine-WeeklyCare Sunday 11:00: Windows temp, component store clean-up, Defender quick scan, at low
                                priority; refuses to run weekdays 01:15-16:05 ET (bot PC: always; main PC: while
                                NinjaTrader is open).

  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\pc_tune.ps1 -DryRun     (the plan, changes nothing)
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\pc_tune.ps1             (apply; asks for Administrator)
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\pc_tune.ps1 -Undo       (tools\bat\UNDO_PC_TUNE.bat runs this)
#>
param(
    [switch]$DryRun,
    [switch]$Undo,
    [switch]$Maintenance,     # the weekly task (LiquidityEngine-WeeklyCare)
    [switch]$Standalone,      # main PC: no bot folder (auto when server.py / engine\ninjatrader.py are missing)
    [switch]$BotPc,           # the weekly task's copy (in ProgramData, no bot folder next to it) on the bot PC: strict guard
    [string]$Kind = 'auto',   # auto | surface | desktop
    [int]$MaxMHz = -1,        # surface heat cap in MHz when plugged in; -1 = auto (2800 on a surface, none on a desktop), 0 = no cap
    [switch]$NoElevate,       # internal: already asked once
    [string]$Log = ''
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
function Test-BotFolder([string]$Dir) {
    if (-not $Dir) { return $false }
    return ((Test-Path -LiteralPath (Join-Path $Dir 'server.py')) -and (Test-Path -LiteralPath (Join-Path (Join-Path $Dir 'engine') 'ninjatrader.py')))
}
if (-not (Test-BotFolder $Root)) { $Standalone = $true }
if ($BotPc) { $Standalone = $false }
$LogDir = Join-Path $Root 'logs'
if (-not (Test-Path -LiteralPath $LogDir)) { try { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null } catch { } }
if (-not $Log) { $Log = Join-Path $LogDir ("pc_tune-" + (Get-Date -Format 'yyyyMMdd-HHmm') + ".txt") }
$StateDir = Join-Path $LogDir 'pc_tune'
if ($env:ProgramData) { $StateDir = Join-Path $env:ProgramData 'LiquidityEngine' }
$StateFile = Join-Path $StateDir 'pc_tune_state.json'
$PlanGuid = 'a1e5c0de-7a0e-4e51-9000-000000000001'
$PlanName = 'Liquidity Engine trading'
$KeeperTask = 'LiquidityEngine-Keeper'
$CareTask = 'LiquidityEngine-WeeklyCare'

function Say([string]$K, [string]$Text) {
    $line = "  [$K] $Text"
    $color = 'Gray'
    if ($K -eq 'OK') { $color = 'Green' } elseif ($K -eq 'FIX') { $color = 'Red' } elseif ($K -eq 'SKIP') { $color = 'Yellow' }
    Write-Host $line -ForegroundColor $color
    try { Add-Content -LiteralPath $Log -Value $line -Encoding UTF8 } catch { }
}
function Head([string]$Text) { Write-Host ""; Write-Host $Text -ForegroundColor Cyan; try { Add-Content -LiteralPath $Log -Value ("`r`n" + $Text) -Encoding UTF8 } catch { } }
function P($Obj, [string]$Name) {
    if ($null -eq $Obj) { return $null }
    if ($Obj -is [hashtable]) { return $Obj[$Name] }
    $p = $Obj.PSObject.Properties[$Name]; if ($p) { return $p.Value }; return $null
}

# ------------------------------------------------------------------ what it may and may never switch off
# Name, the reason, where: 'all' = both PCs, 'bot' = only the bot PC (the main PC keeps its Xbox services)
$TuneServices = @(
    @{ Name = 'DiagTrack'; Where = 'all'; Why = 'Connected User Experiences and Telemetry: uploads usage data to Microsoft in bursts of CPU, disk and network' }
    @{ Name = 'dmwappushservice'; Where = 'all'; Why = 'WAP push message routing: only feeds the telemetry service' }
    @{ Name = 'MapsBroker'; Where = 'all'; Why = 'Downloaded Maps Manager: offline maps nobody uses here' }
    @{ Name = 'RetailDemo'; Where = 'all'; Why = 'Retail Demo: shop display mode' }
    @{ Name = 'Fax'; Where = 'all'; Why = 'Fax: no fax modem' }
    @{ Name = 'WMPNetworkSvc'; Where = 'all'; Why = 'Windows Media Player network sharing: not used' }
    @{ Name = 'RemoteRegistry'; Where = 'all'; Why = 'Remote Registry: lets other PCs edit this registry; off is also safer' }
    @{ Name = 'XblAuthManager'; Where = 'bot'; Why = 'Xbox Live sign-in: no games on the bot PC' }
    @{ Name = 'XblGameSave'; Where = 'bot'; Why = 'Xbox Live game saves: no games on the bot PC' }
    @{ Name = 'XboxNetApiSvc'; Where = 'bot'; Why = 'Xbox Live networking: no games on the bot PC' }
    @{ Name = 'XboxGipSvc'; Where = 'bot'; Why = 'Xbox accessories (controllers): none on the bot PC' }
)
$NeverServices = @('WinDefend', 'WdNisSvc', 'SecurityHealthService', 'Sense', 'mpssvc', 'BFE', 'wuauserv', 'UsoSvc', 'BITS', 'CryptSvc',
                   'Dnscache', 'Dhcp', 'NlaSvc', 'nsi', 'netprofm', 'Netman', 'WlanSvc', 'Wcmsvc', 'WinHttpAutoProxySvc', 'iphlpsvc',
                   'LanmanWorkstation', 'EventLog', 'Schedule', 'RpcSs', 'RpcEptMapper', 'DcomLaunch', 'Power', 'ProfSvc', 'W32Time',
                   'Audiosrv', 'AudioEndpointBuilder', 'TabletInputService', 'TextInputManagementService', 'Themes', 'UserManager',
                   'Winmgmt', 'TrustedInstaller', 'msiserver', 'StateRepository', 'AppXSvc', 'ClipSVC', 'wscsvc', 'SamSs', 'gpsvc',
                   'OneSyncSvc', 'TokenBroker', 'vmcompute', 'hns')
function Test-ServiceAllowed([string]$Name) {
    foreach ($n in $NeverServices) { if ($n -eq $Name) { return $false } }
    foreach ($s in $TuneServices) { if ($s.Name -eq $Name) { return $true } }
    return ($Name -eq 'SysMain' -or $Name -eq 'Spooler')
}
# Defender: only these sub-folders of NinjaTrader 8 (its own database, logs, trace) and of the bot folder
$NtExclude = @('db', 'log', 'trace')
$BotExclude = @('data', 'logs')
# power settings, plugged-in (AC) only; Surface = also on a hot surface-kind PC
$PowerAC = @(
    @{ Sub = '238c9fa8-0aad-41ed-83f4-97be242c8f20'; Set = '29f6c1db-86da-48c5-9fdb-f2b67b1f44da'; Val = 0; Surface = $true; What = 'never sleeps' }
    @{ Sub = '238c9fa8-0aad-41ed-83f4-97be242c8f20'; Set = '9d7815a6-7ee4-497e-8888-515a05f02364'; Val = 0; Surface = $true; What = 'never hibernates' }
    @{ Sub = '0012ee47-9041-4b5d-9b77-535fba8b1442'; Set = '6738e2c4-e8a5-4a42-b16a-e040e769756e'; Val = 0; Surface = $true; What = 'disk never sleeps' }
    @{ Sub = '2a737441-1930-4402-8d77-b2bebba308a3'; Set = '48e6b7a6-50f5-4782-a5d4-53bb8f07e226'; Val = 0; Surface = $true; What = 'USB selective suspend off' }
    @{ Sub = '19cab44c-1406-4e15-8d6c-e2e2a6327e25'; Set = '12bbebe6-58d6-4636-95bb-3217ef867c1a'; Val = 0; Surface = $true; What = 'Wi-Fi power saving off' }
    @{ Sub = '501a4d13-42af-4429-9fd1-a8218c268e20'; Set = 'ee12f906-d277-404b-b6da-e5fa1a576df5'; Val = 0; Surface = $false; What = 'PCI Express link power saving off' }
)
$ProcSub = '54533251-82be-4824-96c1-47b60b740d00'
$ProcFreqMax = @('75b0ae3f-bce0-45a7-8c89-c9611c25e100', '75b0ae3f-bce0-45a7-8c89-c9611c25e101')     # all cores; the 2nd class on hybrid CPUs
$BaseBalanced = '381b4222-f694-41f0-9621-a68e2a2b1d4b'
$BaseHigh = '8c5e7fda-e8bf-4a96-9a85-cf8d6e58fbd0'
$BaseUltimate = 'e9a42b02-d5df-448d-aa00-03f14749eb61'

# ------------------------------------------------------------------ the clock guard (the same rule as clean_pc.ps1)
function Get-ET {
    if ($env:LE_T_ET) { return [DateTime]::Parse($env:LE_T_ET, [Globalization.CultureInfo]::InvariantCulture) }
    try { return [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Eastern Standard Time') } catch { return [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'America/New_York') } }
function Is-TradingWindow([DateTime]$Et) {
    if ($Et.DayOfWeek -eq 'Saturday' -or $Et.DayOfWeek -eq 'Sunday') { return $false }
    $m = $Et.Hour * 60 + $Et.Minute
    return ($m -ge 75 -and $m -lt 965)          # 01:15 - 16:05 ET
}
function Nt-Running { return (@(Get-Process -Name 'NinjaTrader' -ErrorAction SilentlyContinue).Count -gt 0) }
function Test-DeepAllowed([DateTime]$Et, [bool]$IsStandalone, [bool]$NtOpen) {
    if ($IsStandalone -and -not $NtOpen) { return $true }
    return -not (Is-TradingWindow $Et)
}
function Deep-Allowed { return (Test-DeepAllowed (Get-ET) ([bool]$Standalone) (Nt-Running)) }

# ------------------------------------------------------------------ which kind of PC
function Get-TuneKind([string]$Model, $PcSystemType, [double]$RamGB) {
    if ("$Model" -match '(?i)surface') { return 'surface' }
    if (("$PcSystemType" -eq '2') -and $RamGB -gt 0 -and $RamGB -le 8.5) { return 'surface' }      # a small laptop runs hot too
    return 'desktop'
}
function Get-AutoMHz([string]$TuneKind) { if ($TuneKind -eq 'surface') { return 2800 }; return 0 }
function Get-SysMainAdvice([double]$RamGB, [bool]$Ssd) { return ($RamGB -gt 0 -and $RamGB -le 6.5 -and $Ssd) }
# the page file is too small when it is not system managed and its largest size is under 4 GB (or there is none)
function Test-PagefileTooSmall([bool]$Auto, [int]$MaxMB) { if ($Auto) { return $false }; return ($MaxMB -lt 4096) }

# ------------------------------------------------------------------ the state file (written before every change)
$Changes = New-Object System.Collections.ArrayList
function Load-State {
    $Changes.Clear()
    if (-not (Test-Path -LiteralPath $StateFile)) { return }
    try {
        $o = (Get-Content -LiteralPath $StateFile -Raw -ErrorAction Stop) | ConvertFrom-Json
        foreach ($c in @(P $o 'changes')) { if ($null -ne $c) { [void]$Changes.Add($c) } }
    } catch { Say 'FIX' "The undo file could not be read: $StateFile ($($_.Exception.Message))" }
}
function Save-State {
    if ($DryRun) { return }
    try {
        if (-not (Test-Path -LiteralPath $StateDir)) { New-Item -ItemType Directory -Path $StateDir -Force | Out-Null }
        $o = [pscustomobject]@{ v = 2; computer = "$env:COMPUTERNAME"; saved = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'); changes = @($Changes) }
        Set-Content -LiteralPath $StateFile -Value ($o | ConvertTo-Json -Depth 6) -Encoding UTF8
    } catch { Say 'FIX' "The undo file could not be written: $($_.Exception.Message)" }
}
function Find-Change([string]$Id) { foreach ($c in $Changes) { if ((P $c 'Id') -eq $Id) { return $c } }; return $null }
# keeps the FIRST before-value: running the tune twice never loses what Windows had originally
function Add-Change([string]$Id, [string]$ChangeKind, [hashtable]$F) {
    if ($null -ne (Find-Change $Id)) { return }
    $o = [ordered]@{ Id = $Id; Kind = $ChangeKind; Target = ''; Name = ''; Type = ''; Before = $null; Existed = $false; Note = ''; At = (Get-Date -Format 'yyyy-MM-dd HH:mm') }
    foreach ($k in $F.Keys) { $o[$k] = $F[$k] }
    [void]$Changes.Add([pscustomobject]$o)
    Save-State
}

# ------------------------------------------------------------------ change helpers (each records, then changes)
function Reg-Read([string]$Key, [string]$Name) {
    try {
        $it = Get-ItemProperty -Path $Key -Name $Name -ErrorAction Stop
        $v = P $it $Name
        if ($null -eq $v) { throw 'no value' }
        $t = 'DWord'; try { $t = [string]((Get-Item -Path $Key -ErrorAction Stop).GetValueKind($Name)) } catch { }
        return [pscustomobject]@{ Existed = $true; Value = $v; Type = $t }
    } catch { return [pscustomobject]@{ Existed = $false; Value = $null; Type = '' } }
}
function Tune-Reg([string]$Key, [string]$Name, $Value, [string]$Type, [string]$What) {
    $cur = Reg-Read $Key $Name
    if ($cur.Existed -and ("$($cur.Value)" -eq "$Value")) { Say 'OK' "$What (already)"; return }
    if ($DryRun) { Say '..' "Would: $What"; return }
    Add-Change "reg|$Key|$Name" 'reg' @{ Target = $Key; Name = $Name; Type = $(if ($cur.Existed) { $cur.Type } else { $Type }); Before = $(if ($cur.Existed) { "$($cur.Value)" } else { $null }); Existed = $cur.Existed }
    try {
        if (-not (Test-Path -Path $Key)) { New-Item -Path $Key -Force -ErrorAction Stop | Out-Null }
        New-ItemProperty -Path $Key -Name $Name -Value $Value -PropertyType $Type -Force -ErrorAction Stop | Out-Null
        Say 'OK' $What
    } catch { Say 'SKIP' "$What : $($_.Exception.Message)" }
}
function Tune-Service([string]$Name, [string]$Why) {
    if (-not (Test-ServiceAllowed $Name)) { Say 'SKIP' "$Name is never switched off by this script"; return }
    $s = $null; try { $s = Get-Service -Name $Name -ErrorAction Stop } catch { }
    if ($null -eq $s) { Say '..' "$Name : not on this PC"; return }
    $st = "$(P $s 'StartType')"; if (-not $st) { $st = 'Manual' }
    if ($st -eq 'Disabled') { Say 'OK' "$Name already off ($Why)"; return }
    if ($DryRun) { Say '..' "Would switch off $Name (now $st): $Why"; return }
    Add-Change "svc|$Name" 'service' @{ Target = $Name; Before = $st; Existed = ("$(P $s 'Status')" -eq 'Running'); Note = $Why }
    try {
        Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue
        Set-Service -Name $Name -StartupType Disabled -ErrorAction Stop
        Say 'OK' "$Name off (was $st): $Why"
    } catch { Say 'SKIP' "$Name : $($_.Exception.Message)" }
}
function Run-Powercfg([string[]]$A) {
    $global:LASTEXITCODE = 0
    $o = ''; try { $o = (& powercfg @A 2>$null | Out-String) } catch { $o = ''; $global:LASTEXITCODE = 1 }
    return [pscustomobject]@{ Code = $LASTEXITCODE; Out = "$o" }
}
function Get-Guid([string]$Text) { $m = [regex]::Match("$Text", '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'); if ($m.Success) { return $m.Value.ToLowerInvariant() }; return '' }

# ------------------------------------------------------------------ what the PC is
function Get-PcFacts {
    $model = ''; $pst = $null; $ram = 0.0; $ssd = $false; $maxMHz = 0
    try { $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop; $model = "$(P $cs 'Model')"; $pst = P $cs 'PCSystemType'; $ram = [math]::Round([double](P $cs 'TotalPhysicalMemory') / 1GB, 1) } catch { }
    try { foreach ($d in @(Get-PhysicalDisk -ErrorAction Stop)) { if ("$(P $d 'MediaType')" -eq 'SSD' -or "$(P $d 'BusType')" -eq 'NVMe') { $ssd = $true } } } catch { }
    try { $maxMHz = [int](P (@(Get-CimInstance Win32_Processor -ErrorAction Stop)[0]) 'MaxClockSpeed') } catch { }
    return [pscustomobject]@{ Model = $model; PcSystemType = $pst; RamGB = $ram; Ssd = $ssd; BaseMHz = $maxMHz }
}
function Get-NtFolders {
    $out = @()
    $cands = @($env:NINJATRADER_FOLDER)
    foreach ($docs in @([Environment]::GetFolderPath('MyDocuments'), $(if ($env:OneDrive) { Join-Path $env:OneDrive 'Documents' }))) {
        if ($docs) { $cands += (Join-Path $docs 'NinjaTrader 8') }
    }
    foreach ($nt in $cands) { if ($nt -and (Test-Path -LiteralPath $nt) -and ($out -notcontains $nt)) { $out += $nt } }
    return ,$out
}
function Get-ExclusionPaths([bool]$IsStandalone) {
    $want = @()
    foreach ($nt in (Get-NtFolders)) { foreach ($s in $NtExclude) { $p = Join-Path $nt $s; if (Test-Path -LiteralPath $p) { $want += $p } } }
    if (-not $IsStandalone) { foreach ($s in $BotExclude) { $p = Join-Path $Root $s; if (Test-Path -LiteralPath $p) { $want += $p } } }
    return ,$want
}
function Has-RealPrinter {
    try {
        $pr = @(Get-Printer -ErrorAction Stop | Where-Object { "$(P $_ 'Name')" -notmatch '(?i)Microsoft Print to PDF|XPS Document Writer|OneNote|^Fax$|Send To' })
        return [bool]($pr.Count -gt 0)
    } catch { return $true }       # not readable: assume there is one (the spooler stays)
}

# ================================================================== the tune
function Invoke-Tune {
    $f = Get-PcFacts
    $tk = $Kind; if ($tk -ne 'surface' -and $tk -ne 'desktop') { $tk = Get-TuneKind $f.Model $f.PcSystemType $f.RamGB }
    $mhz = $MaxMHz; if ($mhz -lt 0) { $mhz = Get-AutoMHz $tk }
    $role = 'bot PC'; if ($Standalone) { $role = 'main PC (business mode)' }
    Head "DEEP TUNE v2: $tk, $role, $($f.RamGB) GB$(if ($DryRun) { ' - DRY RUN: the plan, nothing changed' })"
    Say '..' "Undo file: $StateFile (tools\bat\UNDO_PC_TUNE.bat puts every change below back)"
    Load-State

    # 1. power plan
    Head 'Power plan (plugged in)'
    $ra = Run-Powercfg @('/getactivescheme'); $active = Get-Guid $ra.Out
    $rl = Run-Powercfg @('/list'); $exists = ($rl.Out -match [regex]::Escape($PlanGuid))
    if ($DryRun) {
        Say '..' "Would make the plan '$PlanName' (now active: $active) and switch to it: $((@($PowerAC | Where-Object { $tk -ne 'surface' -or $_.Surface } | ForEach-Object { $_.What })) -join ', ')$(if ($mhz -gt 0) { ", CPU capped at $mhz MHz (cooler)" })"
    } else {
        $ok = $true
        if (-not $exists) {
            $bases = @($BaseBalanced); if ($tk -ne 'surface') { $bases = @($BaseUltimate, $BaseHigh, $BaseBalanced) }
            Add-Change 'power|plan' 'power' @{ Target = $PlanGuid; Before = $active; Existed = $false }
            $made = $false
            foreach ($b in $bases) { $r = Run-Powercfg @('/duplicatescheme', $b, $PlanGuid); if ($r.Code -eq 0) { $made = $true; Say 'OK' "Plan made from $(if ($b -eq $BaseBalanced) { 'Balanced' } elseif ($b -eq $BaseHigh) { 'High performance' } else { 'Ultimate performance' })"; break } }
            if (-not $made) { Say 'SKIP' 'Power plan: Windows did not make a copy (nothing changed)'; $ok = $false }
            else { [void](Run-Powercfg @('/changename', $PlanGuid, $PlanName, 'Liquidity Engine: 24/5 trading. Undo: tools\bat\UNDO_PC_TUNE.bat')) }
        } else {
            Add-Change 'power|plan' 'power' @{ Target = $PlanGuid; Before = $active; Existed = $true }
        }
        if ($ok) {
            $done = @()
            foreach ($s in $PowerAC) {
                if ($tk -eq 'surface' -and -not $s.Surface) { continue }
                $r = Run-Powercfg @('/setacvalueindex', $PlanGuid, $s.Sub, $s.Set, "$($s.Val)"); if ($r.Code -eq 0) { $done += $s.What }
            }
            if ($mhz -gt 0) {
                $c = 0; foreach ($fs in $ProcFreqMax) { $r = Run-Powercfg @('/setacvalueindex', $PlanGuid, $ProcSub, $fs, "$mhz"); if ($r.Code -eq 0) { $c++ } }
                if ($c) { $done += "CPU capped at $mhz MHz (less heat; -MaxMHz 0 removes the cap)" }
            }
            $r = Run-Powercfg @('/setactive', $PlanGuid)
            if ($r.Code -eq 0) { Say 'OK' ("'$PlanName' is on: " + ($done -join ', ') + '. On battery it acts like the plan it was copied from.') }
            else { Say 'SKIP' "Power plan made but not switched on (code $($r.Code))" }
        }
    }

    # 2. services
    Head 'Background services a trading PC does not need'
    foreach ($s in $TuneServices) {
        if ($s.Where -eq 'bot' -and $Standalone) { continue }
        Tune-Service $s.Name $s.Why
    }
    if (Has-RealPrinter) { Say 'OK' 'Print Spooler kept (a printer is set up, or it could not be checked)' }
    else { Tune-Service 'Spooler' 'Print Spooler: no printer is set up (it comes back on undo; turn it on to add a printer)' }

    # 3. memory
    Head 'Memory'
    try {
        $mm = Get-MMAgent -ErrorAction Stop
        if ([bool](P $mm 'MemoryCompression')) { Say 'OK' 'Compressed memory is on (keep it: on a small PC it holds ~30% more before the disk is used)' }
        elseif ($DryRun) { Say '..' 'Would turn compressed memory on' }
        else { Add-Change 'mm|compression' 'mmagent' @{ Target = 'MemoryCompression'; Before = 'False' }; Enable-MMAgent -MemoryCompression -ErrorAction Stop; Say 'OK' 'Compressed memory turned on (after a restart)' }
    } catch { Say 'SKIP' 'Compressed memory: not readable here (nothing changed)' }
    if (Get-SysMainAdvice $f.RamGB $f.Ssd) { Tune-Service 'SysMain' "SysMain (Superfetch): with $($f.RamGB) GB on an SSD it fills scarce memory with guesses; apps open fast from the SSD anyway" }
    else { Say 'OK' "SysMain (Superfetch) kept: with $($f.RamGB) GB it helps programs open faster" }
    try {
        $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
        $autoV = P $cs 'AutomaticManagedPagefile'
        if ($null -eq $autoV) { throw 'not readable' }
        $auto = [bool]$autoV
        $maxMB = 0; try { foreach ($pf in @(Get-CimInstance Win32_PageFileSetting -ErrorAction Stop)) { if ([int](P $pf 'MaximumSize') -gt $maxMB) { $maxMB = [int](P $pf 'MaximumSize') } } } catch { }
        if ($auto) { Say 'OK' 'Page file: system managed (right for this PC; left as is)' }
        elseif (-not (Test-PagefileTooSmall $auto $maxMB)) { Say 'OK' "Page file: set by hand to up to $maxMB MB (big enough; left as is)" }
        elseif ($DryRun) { Say '..' "Would set the page file back to system managed (now set by hand, at most $maxMB MB: too small with $($f.RamGB) GB)" }
        else {
            Add-Change 'pagefile|auto' 'pagefile' @{ Target = 'AutomaticManagedPagefile'; Before = 'False'; Note = "$maxMB" }
            Set-CimInstance -InputObject $cs -Property @{ AutomaticManagedPagefile = $true } -ErrorAction Stop
            Say 'OK' "Page file back to system managed (was at most $maxMB MB: NinjaTrader could run out of memory). After a restart."
        }
    } catch { Say 'SKIP' 'Page file: not readable here (nothing changed)' }

    # 4. Defender exclusions
    Head 'Microsoft Defender (only NinjaTrader''s and the bot''s data folders skip real-time scanning)'
    try {
        $mp = Get-MpPreference -ErrorAction Stop
        $have = @(P $mp 'ExclusionPath')
        $want = Get-ExclusionPaths ([bool]$Standalone)
        if ($want.Count -eq 0) { Say 'OK' 'No NinjaTrader or bot data folders here: nothing excluded' }
        foreach ($p in $want) {
            if ($have -contains $p) { Say 'OK' "Already skipped: $p"; continue }
            if ($DryRun) { Say '..' "Would skip: $p"; continue }
            Add-Change "mp|$p" 'mpexcl' @{ Target = $p }
            try { Add-MpPreference -ExclusionPath $p -ErrorAction Stop; Say 'OK' "Real-time scan skips: $p" } catch { Say 'SKIP' "$p : $($_.Exception.Message)" }
        }
        Say '..' 'Trade-off: NinjaTrader writes thousands of small bar / log files and the bot writes its state every minute; the scanner'
        Say '..' '   checking each write stalls them. A file dropped in these folders is not scanned when written; the weekly quick scan'
        Say '..' '   and everything else stay on. No program is excluded, only these folders.'
    } catch { Say 'SKIP' "Defender settings not readable (another antivirus, or Defender off): nothing excluded" }

    # 5. network
    Head 'Network (low latency)'
    try {
        $ads = @(Get-NetAdapter -Physical -ErrorAction Stop)
        if ($ads.Count -eq 0) { Say '..' 'No network card found' }
        foreach ($a in $ads) {
            $an = "$(P $a 'Name')"
            try {
                foreach ($pr in @(Get-NetAdapterAdvancedProperty -Name $an -ErrorAction Stop)) {
                    $dn = "$(P $pr 'DisplayName')"
                    if ($dn -notmatch '(?i)energy.?efficient ethernet|green ethernet|advanced eee|^eee$|power saving mode|ultra low power') { continue }
                    $off = @(P $pr 'ValidDisplayValues') | Where-Object { "$_" -match '^(?i)(disabled|off)$' } | Select-Object -First 1
                    $cur = "$(P $pr 'DisplayValue')"
                    if (-not $off) { continue }
                    if ($cur -eq "$off") { Say 'OK' "$an : $dn already off"; continue }
                    if ($DryRun) { Say '..' "Would turn off $an : $dn (now $cur)"; continue }
                    Add-Change "netadv|$an|$dn" 'netadv' @{ Target = $an; Name = $dn; Before = $cur }
                    try { Set-NetAdapterAdvancedProperty -Name $an -DisplayName $dn -DisplayValue "$off" -ErrorAction Stop; Say 'OK' "$an : $dn off (no wake-up delay on the line)" } catch { Say 'SKIP' "$an $dn : $($_.Exception.Message)" }
                }
            } catch { }
            try {
                $pm = Get-NetAdapterPowerManagement -Name $an -ErrorAction Stop
                $cur = "$(P $pm 'AllowComputerToTurnOffDevice')"
                if ($cur -eq 'Enabled') {
                    if ($DryRun) { Say '..' "Would stop Windows turning $an off to save power" }
                    else {
                        Add-Change "netpm|$an" 'netpm' @{ Target = $an; Before = $cur }
                        try { Set-NetAdapterPowerManagement -Name $an -AllowComputerToTurnOffDevice Disabled -ErrorAction Stop; Say 'OK' "$an : Windows no longer turns it off to save power" } catch { Say 'SKIP' "$an power: $($_.Exception.Message)" }
                    }
                } elseif ($cur) { Say 'OK' "$an : not turned off to save power" }
            } catch { }
        }
    } catch { Say 'SKIP' 'Network cards: not readable here' }
    Say '..' 'Not changed on purpose: Nagle / TcpAckFrequency (folklore for NinjaTrader feeds), DNS (only the first lookup uses it).'

    # 6. browsers + Office
    Head 'Browsers and Office'
    $edge = 'HKLM:\SOFTWARE\Policies\Microsoft\Edge'
    Tune-Reg $edge 'StartupBoostEnabled' 0 'DWord' 'Edge startup boost off (Edge no longer pre-loads at sign-in)'
    Tune-Reg $edge 'BackgroundModeEnabled' 0 'DWord' 'Edge stops running in the background after its last window closes'
    Tune-Reg $edge 'SleepingTabsEnabled' 1 'DWord' 'Edge sleeping tabs on'
    $sleep = 900; if ($tk -eq 'surface') { $sleep = 300 }
    Tune-Reg $edge 'SleepingTabsTimeout' $sleep 'DWord' "Edge puts background tabs to sleep after $([int]($sleep / 60)) minutes"
    if ($tk -eq 'surface') { Tune-Reg $edge 'EfficiencyMode' 0 'DWord' 'Edge efficiency mode always on (less CPU for background tabs)' }
    $chrome = $false
    foreach ($pf in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA)) { if ($pf -and (Test-Path -LiteralPath (Join-Path $pf 'Google\Chrome\Application\chrome.exe'))) { $chrome = $true } }
    if ($chrome) {
        $cr = 'HKLM:\SOFTWARE\Policies\Google\Chrome'
        Tune-Reg $cr 'BackgroundModeEnabled' 0 'DWord' 'Chrome stops running in the background after its last window closes'
        Tune-Reg $cr 'HighEfficiencyModeEnabled' 1 'DWord' 'Chrome Memory Saver on (frees memory from tabs you are not using)'
    } else { Say '..' 'Chrome not installed: nothing to change' }
    Say '..' 'Edge / Chrome may now say "managed by your organization": that is these settings (tools\bat\UNDO_PC_TUNE.bat removes them).'
    try {
        foreach ($t in @(Get-ScheduledTask -TaskPath '\Microsoft\Office\' -ErrorAction Stop | Where-Object { "$(P $_ 'TaskName')" -like 'Office Startup Boost*' -and "$(P $_ 'State')" -ne 'Disabled' })) {
            $tn = "$(P $t 'TaskName')"
            if ($DryRun) { Say '..' "Would switch off the task $tn (Office pre-loading at sign-in)"; continue }
            Add-Change "taskoff|$tn" 'taskoff' @{ Target = '\Microsoft\Office\'; Name = $tn }
            try { Disable-ScheduledTask -TaskPath '\Microsoft\Office\' -TaskName $tn -ErrorAction Stop | Out-Null; Say 'OK' "Office startup boost off ($tn)" } catch { Say 'SKIP' "$tn : $($_.Exception.Message)" }
        }
    } catch { Say '..' 'Office startup boost: not installed' }
    Say '..' 'Teams and other chat apps at sign-in: CLEAN_PC switches those off (Task Manager > Startup apps turns one back on).'

    # 7. Windows
    Head 'Windows'
    $ss = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy'
    Tune-Reg $ss '01' 1 'DWord' 'Storage Sense on'
    Tune-Reg $ss '2048' 7 'DWord' 'Storage Sense runs every week'
    Tune-Reg $ss '04' 1 'DWord' 'Storage Sense deletes temp files apps no longer use'
    Tune-Reg $ss '08' 1 'DWord' 'Storage Sense empties the recycle bin...'
    Tune-Reg $ss '256' 30 'DWord' '...of files deleted 30+ days ago (Downloads and OneDrive files are never touched)'
    if (-not $Standalone) {
        Tune-Reg 'HKCU:\System\GameConfigStore' 'GameDVR_Enabled' 0 'DWord' 'Game Bar background recording off'
        Tune-Reg 'HKCU:\Software\Microsoft\Windows\CurrentVersion\GameDVR' 'AppCaptureEnabled' 0 'DWord' 'Game Bar capture off'
    }

    # 8. scheduled tasks
    Head 'Scheduled helpers'
    Install-Helpers $tk
    if (-not $DryRun) { Save-State; Say 'OK' "$($Changes.Count) changes recorded in $StateFile" }
}

function Copy-Ours([string]$Src, [string]$Dst) {
    $existed = Test-Path -LiteralPath $Dst
    Add-Change "file|$Dst" 'file' @{ Target = $Dst; Existed = $existed }
    $d = Split-Path -Parent $Dst
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
    Copy-Item -LiteralPath $Src -Destination $Dst -Force -ErrorAction Stop
}
function Install-Helpers([string]$TuneKind) {
    $keeperSrc = Join-Path $PSScriptRoot 'pc_keeper.ps1'
    $home2 = $StateDir
    $keeper = Join-Path $home2 'pc_keeper.ps1'
    $care = Join-Path (Join-Path $home2 'scripts') 'pc_tune.ps1'
    $ps = 'powershell.exe'
    if ($env:WINDIR) { $ps = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe' }
    $user = "$env:USERDOMAIN\$env:USERNAME"
    $kArgs = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$keeper`""
    if (-not $Standalone) { $kArgs += ' -Bot' }
    $cArgs = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$care`" -Maintenance -Kind $TuneKind"
    if ($Standalone) { $cArgs += ' -Standalone' } else { $cArgs += ' -BotPc' }
    if ($DryRun) {
        Say '..' "Would add the task $KeeperTask (every 15 min + at sign-in, hidden): NinjaTrader$(if (-not $Standalone) { ' and the bot''s python' }) AboveNormal priority, background apps BelowNormal, trims idle background apps when memory is 85%+ used"
        Say '..' "Would add the task $CareTask (Sunday 11:00): Windows temp, component store clean-up, Defender quick scan; never weekdays 01:15-16:05 ET while trading"
        return
    }
    if (-not (Test-Path -LiteralPath $keeperSrc)) { Say 'SKIP' "pc_keeper.ps1 missing next to pc_tune.ps1: the priority helper was not added"; return }
    try {
        Copy-Ours $keeperSrc $keeper
        Copy-Ours $PSCommandPath $care
        $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3) -Priority 7
        $daily = New-ScheduledTaskTrigger -Daily -At '00:00'
        $every = New-ScheduledTaskTrigger -Once -At '00:00' -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 1)
        $daily.Repetition = $every.Repetition
        $logon = New-ScheduledTaskTrigger -AtLogOn -User $user
        $act = New-ScheduledTaskAction -Execute $ps -Argument $kArgs
        $existed = [bool](Get-ScheduledTask -TaskName $KeeperTask -ErrorAction SilentlyContinue)
        Add-Change "task|$KeeperTask" 'task' @{ Target = $KeeperTask; Existed = $existed }
        if ($existed) { Unregister-ScheduledTask -TaskName $KeeperTask -Confirm:$false -ErrorAction SilentlyContinue }
        $desc = 'Liquidity Engine: NinjaTrader / the bot first, background apps last. Never closes anything. Undo: tools\bat\UNDO_PC_TUNE.bat'
        try {       # S4U: runs as you with no window at all
            $pr = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Limited
            Register-ScheduledTask -TaskName $KeeperTask -InputObject (New-ScheduledTask -Action $act -Trigger @($daily, $logon) -Settings $set -Principal $pr -Description $desc) -ErrorAction Stop | Out-Null
        } catch {
            $pr = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
            Register-ScheduledTask -TaskName $KeeperTask -InputObject (New-ScheduledTask -Action $act -Trigger @($daily, $logon) -Settings $set -Principal $pr -Description $desc) -ErrorAction Stop | Out-Null
        }
        Say 'OK' "${KeeperTask}: every 15 min, NinjaTrader$(if (-not $Standalone) { ' + the bot' }) first, background apps last (never closes anything)"
    } catch { Say 'SKIP' "$KeeperTask not added: $($_.Exception.Message)" }
    try {
        $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 3) -Priority 7
        $tr = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '11:00'
        $act = New-ScheduledTaskAction -Execute $ps -Argument $cArgs
        $pr = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
        $existed = [bool](Get-ScheduledTask -TaskName $CareTask -ErrorAction SilentlyContinue)
        Add-Change "task|$CareTask" 'task' @{ Target = $CareTask; Existed = $existed }
        if ($existed) { Unregister-ScheduledTask -TaskName $CareTask -Confirm:$false -ErrorAction SilentlyContinue }
        Register-ScheduledTask -TaskName $CareTask -InputObject (New-ScheduledTask -Action $act -Trigger $tr -Settings $set -Principal $pr -Description 'Liquidity Engine weekly care (Sunday). Never weekdays 01:15-16:05 ET while trading. Undo: tools\bat\UNDO_PC_TUNE.bat') -ErrorAction Stop | Out-Null
        Say 'OK' "${CareTask}: Sundays 11:00 (Windows temp, component store, Defender quick scan, low priority)"
    } catch { Say 'SKIP' "$CareTask not added: $($_.Exception.Message)" }
}

# ================================================================== undo
function Undo-One($C) {
    $k = "$(P $C 'Kind')"; $t = "$(P $C 'Target')"; $n = "$(P $C 'Name')"; $b = P $C 'Before'; $ex = [bool](P $C 'Existed')
    switch ($k) {
        'reg' {
            if ($ex) {
                $ty = "$(P $C 'Type')"; if (-not $ty) { $ty = 'DWord' }
                $v = $b; if ($ty -eq 'DWord') { $v = [int]$b } elseif ($ty -eq 'QWord') { $v = [long]$b }
                if (-not (Test-Path -Path $t)) { New-Item -Path $t -Force -ErrorAction Stop | Out-Null }
                New-ItemProperty -Path $t -Name $n -Value $v -PropertyType $ty -Force -ErrorAction Stop | Out-Null
                return "$t\$n back to $b"
            }
            Remove-ItemProperty -Path $t -Name $n -ErrorAction Stop
            return "$t\$n removed (it was not set before)"
        }
        'service' {
            Set-Service -Name $t -StartupType $b -ErrorAction Stop
            if ($ex) { Start-Service -Name $t -ErrorAction SilentlyContinue }
            return "$t back to $b"
        }
        'power' {
            $r = Run-Powercfg @('/setactive', $b); if ($r.Code -ne 0) { throw "powercfg /setactive ${b}: code $($r.Code)" }
            if (-not $ex) { [void](Run-Powercfg @('/delete', $t)) }
            return "power plan back to $b$(if (-not $ex) { "; '$PlanName' deleted" })"
        }
        'mpexcl' { Remove-MpPreference -ExclusionPath $t -ErrorAction Stop; return "Defender scans $t again" }
        'mmagent' { if ("$b" -eq 'False') { Disable-MMAgent -MemoryCompression -ErrorAction Stop }; return 'compressed memory as before' }
        'pagefile' {
            $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
            Set-CimInstance -InputObject $cs -Property @{ AutomaticManagedPagefile = $false } -ErrorAction Stop
            return "page file back to set by hand (it was at most $(P $C 'Note') MB; check System > Advanced > Performance > Virtual memory)"
        }
        'netadv' { Set-NetAdapterAdvancedProperty -Name $t -DisplayName $n -DisplayValue "$b" -ErrorAction Stop; return "$t : $n back to $b" }
        'netpm' { Set-NetAdapterPowerManagement -Name $t -AllowComputerToTurnOffDevice $b -ErrorAction Stop; return "$t : power saving back to $b" }
        'taskoff' { Enable-ScheduledTask -TaskPath $t -TaskName $n -ErrorAction Stop | Out-Null; return "task $n back on" }
        'task' { if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $t -Confirm:$false -ErrorAction Stop }; return "task $t removed" }
        'file' { if (Test-Path -LiteralPath $t) { Remove-Item -LiteralPath $t -Force -ErrorAction Stop }; return "$t removed" }
        default { throw "unknown change kind '$k'" }
    }
}
function Invoke-Undo {
    Head "UNDO DEEP TUNE$(if ($DryRun) { ' - DRY RUN: shows what would be put back' })"
    Load-State
    if ($Changes.Count -eq 0) { Say 'OK' "Nothing to undo (no $StateFile)"; return 0 }
    $left = New-Object System.Collections.ArrayList
    $all = @($Changes); [array]::Reverse($all)
    foreach ($c in $all) {
        if ($DryRun) { Say '..' ("Would undo: {0} {1} {2} (before: {3})" -f (P $c 'Kind'), (P $c 'Target'), (P $c 'Name'), (P $c 'Before')); continue }
        try { Say 'OK' (Undo-One $c) } catch { Say 'SKIP' ("Not undone: {0} {1} {2}: {3}" -f (P $c 'Kind'), (P $c 'Target'), (P $c 'Name'), $_.Exception.Message); [void]$left.Insert(0, $c) }
    }
    if ($DryRun) { return 0 }
    $Changes.Clear(); foreach ($c in $left) { [void]$Changes.Add($c) }
    if ($left.Count -eq 0) {
        try { Move-Item -LiteralPath $StateFile -Destination (Join-Path $StateDir ('pc_tune_state-undone-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')) -Force -ErrorAction Stop } catch { }
        Say 'OK' 'Everything the deep tune changed is back as it was. Restart the PC after 4:05 PM ET to finish.'
        return 0
    }
    Save-State
    Say 'FIX' "$($left.Count) change(s) could not be undone (above); they stay in $StateFile. Run tools\bat\UNDO_PC_TUNE.bat again, or send this window to Claude."
    return 1
}

# ================================================================== the weekly care (scheduled task, SYSTEM)
function Remove-OldFiles([string]$Dir, [int]$Days) {
    $n = 0; $bytes = 0
    if (-not $Dir -or -not (Test-Path -LiteralPath $Dir)) { return @(0, 0) }
    $cut = (Get-Date).AddDays(-$Days)
    Get-ChildItem -LiteralPath $Dir -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt $cut } | ForEach-Object {
        $len = $_.Length
        if ($DryRun) { $n++; $bytes += $len } else { try { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop; $n++; $bytes += $len } catch { } }
    }
    return @($n, $bytes)
}
function Invoke-Maintenance {
    Head "WEEKLY CARE $(Get-Date -Format 'ddd yyyy-MM-dd HH:mm')$(if ($DryRun) { ' - DRY RUN' })"
    if (-not (Deep-Allowed)) { Say 'SKIP' 'Trading hours (weekdays 01:15-16:05 ET): nothing done; next Sunday.'; return 0 }
    try { [System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'BelowNormal' } catch { }
    $r = Remove-OldFiles "$env:WINDIR\Temp" 2; Say 'OK' "Windows Temp: $($r[0]) files, $([math]::Round($r[1] / 1MB)) MB"
    if (-not (Deep-Allowed)) { Say 'SKIP' 'Trading hours started: stopped'; return 0 }
    if ($DryRun) { Say '..' 'Would run the component store clean-up (DISM /StartComponentCleanup)' }
    else { & dism.exe /Online /Cleanup-Image /StartComponentCleanup /Quiet | Out-Null; Say 'OK' "Component store clean-up: code $LASTEXITCODE" }
    if (-not (Deep-Allowed)) { Say 'SKIP' 'Trading hours started: stopped'; return 0 }
    if ($DryRun) { Say '..' 'Would run a Defender quick scan' }
    else { try { Start-MpScan -ScanType QuickScan -ErrorAction Stop; Say 'OK' 'Defender quick scan done' } catch { Say 'SKIP' "Defender quick scan: $($_.Exception.Message)" } }
    return 0
}

# ================================================================== main
$isAdmin = $false
try { $isAdmin = [bool]([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) } catch { $isAdmin = $false }

if ($Maintenance) { exit (Invoke-Maintenance) }

if (-not $Undo -and -not (Deep-Allowed)) {
    Head 'DEEP TUNE'
    Say 'SKIP' 'Trading hours (weekdays 01:15-16:05 ET): the deep tune waits so it never slows the bot. Run tools\bat\CLEAN_PC.bat after 4:05 PM ET.'
    exit 0
}
if (-not $DryRun -and -not $isAdmin) {
    if ($NoElevate) { Say 'FIX' 'Needs Administrator: Windows did not give it. Double-click the .bat again and click Yes.'; exit 1 }
    Say '..' 'Windows asks "Do you want to allow this app to make changes?": click Yes.'
    try {
        $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-NoElevate', '-Log', "`"$Log`"", '-Kind', $Kind, '-MaxMHz', "$MaxMHz")
        if ($Undo) { $argList += '-Undo' }
        if ($Standalone) { $argList += '-Standalone' }
        $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $argList -Verb RunAs -PassThru -Wait
        $code = 1; if ($p) { $code = $p.ExitCode }
        if ($code -eq 0) { Say 'OK' "Done (the lines are in $Log)" } else { Say 'SKIP' "Ended with code $code (see $Log)" }
        exit $code
    } catch { Say 'SKIP' 'Administrator was declined: nothing changed. Double-click again and click Yes.'; exit 1 }
}
if ($Undo) { exit (Invoke-Undo) }
Invoke-Tune
exit 0
