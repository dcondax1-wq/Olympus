<#
PC keeper (the scheduled task LiquidityEngine-Keeper, added by scripts\pc_tune.ps1; every 15 minutes and at sign-in, no
window). Small and quick: NinjaTrader (and on the bot PC the bot's python) get AboveNormal priority so Windows serves them
first; heavy background apps get BelowNormal; when memory is 85%+ used it asks Windows to trim the memory of idle
background apps (their pages move to the standby list and come back if the app needs them). It never closes anything,
never touches NinjaTrader's or the bot's memory, never uses High or Realtime priority. Log: pc_keeper.log next to it
(the last 300 lines). Removed by tools\bat\UNDO_PC_TUNE.bat.

  powershell -NoProfile -ExecutionPolicy Bypass -File pc_keeper.ps1 [-Bot] [-DryRun]
#>
param(
    [switch]$Bot,
    [switch]$DryRun,
    [int]$TrimAtPct = 85
)
$ErrorActionPreference = 'SilentlyContinue'
$Up = @('NinjaTrader')
if ($Bot) { $Up += @('python', 'pythonw') }
# background apps that may wait (lowered, and trimmed when memory is short); never NinjaTrader, python, Defender, Windows itself
$Down = @('OneDrive', 'Teams', 'ms-teams', 'msteams', 'Discord', 'Spotify', 'Dropbox', 'GoogleDriveFS', 'PhoneExperienceHost', 'YourPhone',
          'Widgets', 'WidgetService', 'steam', 'steamwebhelper', 'EpicGamesLauncher', 'Grammarly.Desktop', 'GrammarlyHelper', 'Skype',
          'Zoom', 'Slack', 'Telegram', 'WhatsApp', 'Messenger', 'Overwolf', 'iCloudServices', 'iCloudDrive', 'AdobeCollabSync',
          'CCXProcess', 'Creative Cloud', 'AcroCEF', 'OfficeClickToRun')
$Never = @('ninjatrader', 'python', 'pythonw', 'obsidian', 'msmpeng', 'securityhealthservice', 'csrss', 'lsass', 'winlogon', 'dwm', 'explorer',
           'svchost', 'system', 'idle', 'powershell', 'pwsh', 'claude')
function Test-MayLower([string]$Name) {
    $n = $Name.ToLowerInvariant()
    foreach ($x in $Never) { if ($n -eq $x) { return $false } }
    foreach ($d in $Down) { if ($n -eq $d.ToLowerInvariant()) { return $true } }
    return $false
}
function Test-NeedTrim([double]$UsedPct, [int]$At) { return ($UsedPct -ge $At) }

$LogFile = Join-Path $PSScriptRoot 'pc_keeper.log'
$notes = @()
foreach ($n in $Up) {
    foreach ($p in @(Get-Process -Name $n -ErrorAction SilentlyContinue)) {
        if ("$($p.PriorityClass)" -eq 'Normal') { if (-not $DryRun) { try { $p.PriorityClass = 'AboveNormal' } catch { } }; $notes += "$n up" }
    }
}
$low = @()
foreach ($n in $Down) {
    if (-not (Test-MayLower $n)) { continue }
    foreach ($p in @(Get-Process -Name $n -ErrorAction SilentlyContinue)) {
        $low += $p
        if ("$($p.PriorityClass)" -eq 'Normal') { if (-not $DryRun) { try { $p.PriorityClass = 'BelowNormal' } catch { } }; $notes += "$n down" }
    }
}
$used = 0
try { $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop; $used = [math]::Round(100 * (1 - $os.FreePhysicalMemory / $os.TotalVisibleMemorySize)) } catch { }
if ((Test-NeedTrim $used $TrimAtPct) -and $low.Count -gt 0) {
    $freed = 0
    if (-not $DryRun) {
        try {
            if (-not ('LeKeeper.Mem' -as [type])) {
                Add-Type -Namespace LeKeeper -Name Mem -MemberDefinition '[DllImport("psapi.dll")] public static extern bool EmptyWorkingSet(System.IntPtr hProcess);' -ErrorAction Stop
            }
            foreach ($p in $low) { try { $b = $p.WorkingSet64; if ([LeKeeper.Mem]::EmptyWorkingSet($p.Handle)) { $p.Refresh(); $freed += ($b - $p.WorkingSet64) } } catch { } }
        } catch { $notes += 'trim not available' }
    }
    $notes += "memory $used% used: trimmed $($low.Count) background apps ($([math]::Round($freed / 1MB)) MB)"
}
if ($notes.Count) {
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm') + ' ' + ($notes -join ', ') + $(if ($DryRun) { ' (dry run)' } else { '' })
    Write-Host $line
    if (-not $DryRun) { try {
        $old = @(); if (Test-Path -LiteralPath $LogFile) { $old = @(Get-Content -LiteralPath $LogFile -Tail 299 -ErrorAction Stop) }
        Set-Content -LiteralPath $LogFile -Value (@($old) + $line) -Encoding UTF8
    } catch { } }
}
exit 0
