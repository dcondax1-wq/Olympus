<#
PC GUARD (night-pcguard 2026-11-23, owner: "Windows can't kill a trade"). Run by scripts\fix_clock.ps1 in the SAME
administrator window (FIX_CLOCK.bat / MONDAY_SETUP: one Yes for administrator, never a second one). It
  1. Windows Update: active hours 01:00-17:00 New York time in this PC's own clock (16 h; Windows allows up to 18 h), the
     automatic active-hours guess off, and NoAutoRebootWithLoggedOnUsers = 1 (no restart while you are signed in). It
     tells you to restart Windows yourself on Saturday instead.
  2. Power, the CURRENT plan only, plugged in (AC) only: never sleep, never hibernate, the disk never sleeps, USB selective
     suspend off; every physical network adapter: "allow the computer to turn off this device" and selective suspend off
     (-NoRestart: the adapter is not reset now, so NinjaTrader keeps its connection; it applies at the next restart).
  3. A check only (changes nothing): the Startup shortcuts that start NinjaTrader and the bot at sign-in are there.
  4. -Off (FIX_CLOCK_OFF.bat) puts back exactly what it changed, from the values it saved before the first change
     (%ProgramData%\Olympus\pc_guard_prev.json, writable by administrators only). A value that was not there is removed.
Never touches Defender, the firewall, accounts, BitLocker or anything else. Every program by its full System32 path.
Safe to run twice (the saved "before" values are kept from the first run). One [OK] / [FIX] line per item.
Writes data\pc_guard.json (on / off + one word per item, no secrets) for the Start page, readiness and TRADE_HOME.
Tests: tests\test_pc_guard.py (LE_PG_T_DIR=<folder>: a fake machine.json stands in for the registry, powercfg and the
adapters; nothing real is read or written). Windows PowerShell 5.1, ASCII only.
#>
param([switch]$Off)
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$Sys32 = [Environment]::GetFolderPath('System')
$Powercfg = Join-Path $Sys32 'powercfg.exe'
$Fake = $env:LE_PG_T_DIR
if ($Fake) {
    $StateDir = $Fake
    $StatusPath = Join-Path $Fake 'status.json'
} else {
    $StateDir = Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'Olympus'
    $StatusPath = Join-Path (Join-Path $Root 'data') 'pc_guard.json'
}
$PrevPath = Join-Path $StateDir 'pc_guard_prev.json'
$WU = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'
$WUP = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
$AU = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
# powercfg sub-group / setting GUIDs (the same on every Windows language)
$PW = @(
    @('sleep', '238c9fa8-0aad-41ed-83f4-97be242c8f20', '29f6c1db-86da-48c5-9fdb-f2b67b1f44da', 'never sleep when plugged in'),
    @('hibernate', '238c9fa8-0aad-41ed-83f4-97be242c8f20', '9d7815a6-7ee4-497e-8888-515a05f02364', 'never hibernate when plugged in'),
    @('disk', '0012ee47-9041-4b5d-9b77-535fba8b1442', '6738e2c4-e8a5-4a42-b16a-e040e769756e', 'the disk never sleeps when plugged in'),
    @('usb', '2a737441-1930-4402-8d77-b2bebba308a3', '48e6b7a6-50f5-4782-a5d4-53bb8f07e226', 'USB selective suspend off when plugged in')
)
$NicProps = @('AllowComputerToTurnOffDevice', 'SelectiveSuspend')
$script:Fix = 0

function Say([string]$tag, [string]$t) { Write-Host ('  [' + $tag + '] ' + $t); if ($tag -eq 'FIX') { $script:Fix++ } }

# ------------------------------------------------------------------ the machine (real, or the tests' fake machine.json)
function Load-Fake {
    $p = Join-Path $Fake 'machine.json'
    if (Test-Path -LiteralPath $p) { return (Get-Content -LiteralPath $p -Raw | ConvertFrom-Json) }
    return (New-Object PSObject)
}
function Save-Fake($m) { $m | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Fake 'machine.json') -Encoding ASCII }
function Fake-Get([string]$k) {
    $m = Load-Fake
    $pr = $m.PSObject.Properties[$k]
    if ($pr) { return $pr.Value }
    return $null
}
function Fake-Set([string]$k, $v) {
    $m = Load-Fake
    $m | Add-Member -NotePropertyName $k -NotePropertyValue $v -Force
    Save-Fake $m
}
function Fake-Remove([string]$k) {
    $m = Load-Fake
    $m.PSObject.Properties.Remove($k)
    Save-Fake $m
}

function Get-RegVal([string]$path, [string]$name) {
    if ($Fake) { return (Fake-Get ('reg|' + $path + '|' + $name)) }
    try { return (Get-ItemProperty -LiteralPath $path -Name $name -ErrorAction Stop).$name } catch { return $null }
}
function Set-RegDword([string]$path, [string]$name, [int]$v) {
    if ($Fake) { Fake-Set ('reg|' + $path + '|' + $name) $v; return $true }
    try {
        if (-not (Test-Path -LiteralPath $path)) { New-Item -Path $path -Force -ErrorAction Stop | Out-Null }
        New-ItemProperty -LiteralPath $path -Name $name -Value $v -PropertyType DWord -Force -ErrorAction Stop | Out-Null
        return $true
    } catch { return $false }
}
function Remove-RegVal([string]$path, [string]$name) {
    if ($Fake) { Fake-Remove ('reg|' + $path + '|' + $name); return $true }
    try { Remove-ItemProperty -LiteralPath $path -Name $name -ErrorAction Stop; return $true } catch { return $false }
}

function Get-Scheme {
    if ($Fake) { return (Fake-Get 'scheme') }
    try {
        $o = & $Powercfg /getactivescheme 2>&1 | Out-String
        $m = [regex]::Match($o, '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
        if ($m.Success) { return $m.Value }
    } catch { }
    return $null
}
# the AC index of one setting in one plan; $null = this PC does not have that setting
function Get-PowerIdx([string]$scheme, [string]$sub, [string]$set) {
    if ($Fake) { return (Fake-Get ('pw|' + $sub + '|' + $set)) }
    try {
        $o = & $Powercfg /query $scheme $sub $set 2>&1 | Out-String
        $ms = [regex]::Matches($o, ':\s*0x([0-9a-fA-F]+)\s*$', 'Multiline')
        # the last two hex lines are "Current AC Power Setting Index" then "Current DC ..." (the words differ per language)
        if ($ms.Count -ge 2) { return [Convert]::ToInt32($ms[$ms.Count - 2].Groups[1].Value, 16) }
    } catch { }
    return $null
}
function Set-PowerIdx([string]$scheme, [string]$sub, [string]$set, [int]$v) {
    if ($Fake) { Fake-Set ('pw|' + $sub + '|' + $set) $v; return $true }
    try {
        & $Powercfg /setacvalueindex $scheme $sub $set $v 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { return $false }
        & $Powercfg /setactive $scheme 2>&1 | Out-Null
        return $true
    } catch { return $false }
}

function Get-Nics {
    if ($Fake) {
        $out = @()
        $n = Fake-Get 'nics'
        if ($n) { foreach ($x in @($n)) { $out += [string]$x } }
        return $out
    }
    try { return @(Get-NetAdapter -Physical -ErrorAction Stop | ForEach-Object { $_.Name }) } catch { return @() }
}
function Get-NicPm([string]$nic, [string]$prop) {
    if ($Fake) { return (Fake-Get ('nic|' + $nic + '|' + $prop)) }
    try { return [string]((Get-NetAdapterPowerManagement -Name $nic -ErrorAction Stop).$prop) } catch { return $null }
}
function Set-NicPm([string]$nic, [string]$prop, [string]$v) {
    if ($Fake) { Fake-Set ('nic|' + $nic + '|' + $prop) $v; return $true }
    try {
        $a = @{ Name = $nic; NoRestart = $true; ErrorAction = 'Stop' }
        $a[$prop] = $v
        Set-NetAdapterPowerManagement @a
        return $true
    } catch { return $false }
}

function Get-StartupFiles {
    if ($Fake) {
        $out = @()
        $n = Fake-Get 'startup'
        if ($n) { foreach ($x in @($n)) { $out += [string]$x } }
        return $out
    }
    try {
        $st = [Environment]::GetFolderPath('Startup')
        return @(Get-ChildItem -LiteralPath $st -Filter '*.lnk' -ErrorAction Stop | ForEach-Object { $_.Name })
    } catch { return @() }
}
function Test-BotTask {
    if ($Fake) { return [bool](Fake-Get 'task|LiquidityEngine') }
    return [bool](Get-ScheduledTask -TaskName 'LiquidityEngine' -ErrorAction SilentlyContinue)
}

# the local hour of a New York hour today (Windows' own time-zone rules; the tests set LE_PG_T_TZ = local minus ET, hours)
function Local-Hour([int]$etHour) {
    if ($Fake) { return ((($etHour + [int]$env:LE_PG_T_TZ) % 24) + 24) % 24 }
    try {
        $tz = [TimeZoneInfo]::FindSystemTimeZoneById('Eastern Standard Time')
        $etNow = [TimeZoneInfo]::ConvertTime([DateTime]::UtcNow, $tz)
        $et = New-Object DateTime ($etNow.Year, $etNow.Month, $etNow.Day, $etHour, 0, 0)
        return [TimeZoneInfo]::ConvertTime($et, $tz, [TimeZoneInfo]::Local).Hour
    } catch { return $etHour }
}

# ------------------------------------------------------------------ the saved "before" values
function Load-Prev {
    if (Test-Path -LiteralPath $PrevPath) {
        try { return (Get-Content -LiteralPath $PrevPath -Raw | ConvertFrom-Json) } catch { }
    }
    return $null
}
function Save-Prev($items) {
    try {
        if (-not (Test-Path -LiteralPath $StateDir)) { New-Item -ItemType Directory -Path $StateDir -Force | Out-Null }
        $o = [pscustomobject]@{ v = 1; saved = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'); items = $items }
        $o | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $PrevPath -Encoding ASCII
        return $true
    } catch { return $false }
}
function Save-Status([bool]$on, $words) {
    try {
        $d = Split-Path -Parent $StatusPath
        if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
        $o = [pscustomobject]@{ v = 1; on = $on; t = [int64][DateTimeOffset]::UtcNow.ToUnixTimeSeconds(); fix = $script:Fix; items = $words }
        $o | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $StatusPath -Encoding ASCII
    } catch { }
}

# one saved item: key -> @{ kind; a; b; c; had; value }; kept from the FIRST run (a second run never saves our own values)
$prevObj = Load-Prev
$prev = @{}
if ($prevObj -and $prevObj.items) { foreach ($p in $prevObj.items.PSObject.Properties) { $prev[$p.Name] = $p.Value } }
$newPrev = @{}
foreach ($k in $prev.Keys) { $newPrev[$k] = $prev[$k] }
function Remember([string]$key, [string]$kind, [string]$a, [string]$b, [string]$c, $value) {
    if ($newPrev.ContainsKey($key)) { return }
    $newPrev[$key] = [pscustomobject]@{ kind = $kind; a = $a; b = $b; c = $c; had = ($null -ne $value); value = $value }
}

Write-Host ''
if ($Off) {
    Write-Host '  ==== PC GUARD: undo ===='
    if ($prev.Count -eq 0) {
        Say 'OK' 'Nothing to undo: the PC guard never changed this PC (or it was undone already).'
        Save-Status $false @{}
        exit 0
    }
    foreach ($k in @($prev.Keys | Sort-Object)) {
        $it = $prev[$k]
        $ok = $false
        if ($it.kind -eq 'reg') {
            if ($it.had) { $ok = Set-RegDword $it.a $it.b ([int]$it.value) } else { $ok = Remove-RegVal $it.a $it.b }
        } elseif ($it.kind -eq 'power') {
            if ($it.had) { $ok = Set-PowerIdx $it.c $it.a $it.b ([int]$it.value) } else { $ok = $true }
        } elseif ($it.kind -eq 'nic') {
            if ($it.had) { $ok = Set-NicPm $it.a $it.b ([string]$it.value) } else { $ok = $true }
        }
        if ($ok) { $newPrev.Remove($k) } else { Say 'FIX' ('Could not put back ' + $k + ': run FIX_CLOCK_OFF.bat again as administrator.') }
    }
    if ($newPrev.Count -eq 0) {
        if (Test-Path -LiteralPath $PrevPath) { Remove-Item -LiteralPath $PrevPath -Force -ErrorAction SilentlyContinue }
        Say 'OK' 'PC guard undone: Windows Update, sleep, disk, USB and network adapter settings are back to what they were.'
        Save-Status $false @{}
        exit 0
    }
    [void](Save-Prev $newPrev)
    exit 1
}

Write-Host '  ==== PC GUARD: Windows cannot kill a trade ===='
$words = @{}

# 1. Windows Update: active hours over the trading day, no restart while you are signed in
$hs = Local-Hour 1
$he = Local-Hour 17
$want = @(
    @($WU, 'ActiveHoursStart', $hs), @($WU, 'ActiveHoursEnd', $he), @($WU, 'SmartActiveHoursState', 0),
    @($WUP, 'SetActiveHours', 1), @($WUP, 'ActiveHoursStart', $hs), @($WUP, 'ActiveHoursEnd', $he),
    @($AU, 'NoAutoRebootWithLoggedOnUsers', 1)
)
$wuOk = $true
foreach ($w in $want) {
    $cur = Get-RegVal $w[0] $w[1]
    if ($null -ne $cur -and [string]$cur -eq [string]$w[2]) { continue }
    Remember ('reg|' + $w[0] + '|' + $w[1]) 'reg' $w[0] $w[1] '' $cur
    [void](Save-Prev $newPrev)                       # saved BEFORE the change: an interrupted run can still be undone
    if (-not (Set-RegDword $w[0] $w[1] ([int]$w[2]))) { $wuOk = $false }
}
if ($wuOk) {
    Say 'OK' ('Windows Update: active hours {0:00}:00-{1:00}:00 on this PC (01:00-17:00 New York), no restart while you are signed in' -f $hs, $he)
    $words['update'] = 'on'
} else {
    Say 'FIX' 'Windows Update: a setting could not be written. Send a photo of this window to Claude.'
    $words['update'] = 'fix'
}
Say 'OK' 'Restart Windows yourself on Saturday (Start > Power > Update and restart): updates install then, never mid-trade.'

# 2. power: the current plan, plugged in only
$scheme = Get-Scheme
if (-not $scheme) {
    Say 'FIX' 'Power plan: could not read the current plan (powercfg). Send a photo of this window to Claude.'
    $words['power'] = 'fix'
} else {
    $pOk = $true
    foreach ($p in $PW) {
        $cur = Get-PowerIdx $scheme $p[1] $p[2]
        if ($null -eq $cur) { Say 'OK' ('Power: ' + $p[3] + ' (not on this PC: nothing to change)'); continue }
        if ([int]$cur -eq 0) { Say 'OK' ('Power: ' + $p[3]); continue }
        Remember ('power|' + $p[0]) 'power' $p[1] $p[2] $scheme $cur
        [void](Save-Prev $newPrev)
        if (Set-PowerIdx $scheme $p[1] $p[2] 0) { Say 'OK' ('Power: ' + $p[3]) } else { Say 'FIX' ('Power: could not set "' + $p[3] + '"'); $pOk = $false }
    }
    if ($pOk) { $words['power'] = 'on' } else { $words['power'] = 'fix' }
}
$nOk = $true
$nics = @(Get-Nics)
foreach ($n in $nics) {
    foreach ($prop in $NicProps) {
        $cur = Get-NicPm $n $prop
        if ($cur -ne 'Enabled') { continue }               # Disabled already, or Unsupported on this adapter
        Remember ('nic|' + $n + '|' + $prop) 'nic' $n $prop '' $cur
        [void](Save-Prev $newPrev)
        if (-not (Set-NicPm $n $prop 'Disabled')) { $nOk = $false }
    }
}
if ($nics.Count -eq 0) { Say 'OK' 'Network adapter: none found to change' }
elseif ($nOk) { Say 'OK' ('Network adapter(s) ' + ($nics -join ', ') + ': Windows never turns them off to save power (applies at the next restart)') }
else { Say 'FIX' 'Network adapter: a power setting could not be changed. Send a photo of this window to Claude.' }
if ($nOk) { $words['nic'] = 'on' } else { $words['nic'] = 'fix' }

# 3. check only: NinjaTrader and the bot start at sign-in
$st = @(Get-StartupFiles)
$hasBot = ($st -contains 'LE bot server.lnk') -or (Test-BotTask)
$hasNt = [bool]($st | Where-Object { $_ -like '*NinjaTrader*' })
if ($hasBot) { Say 'OK' 'The bot starts at sign-in (Startup shortcut "LE bot server")' } else { Say 'FIX' 'The bot does NOT start at sign-in: double-click START_BOT.bat once (it adds the Startup shortcuts).' }
if ($hasNt) { Say 'OK' 'NinjaTrader starts at sign-in (Startup shortcut)' } else { Say 'FIX' 'NinjaTrader does NOT start at sign-in: double-click START_BOT.bat once (it adds the Startup shortcuts).' }
if ($hasBot) { $words['bot_startup'] = 'ok' } else { $words['bot_startup'] = 'missing' }
if ($hasNt) { $words['nt_startup'] = 'ok' } else { $words['nt_startup'] = 'missing' }

$on = ($words['update'] -eq 'on') -and ($words['power'] -eq 'on') -and ($words['nic'] -eq 'on')
Save-Status $on $words
if ($on) { Say 'OK' 'PC guard ON. Undo any time: right-click FIX_CLOCK_OFF.bat > Run as administrator.'; exit 0 }
exit 1
