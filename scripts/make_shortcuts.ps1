<#
Desktop icons for the owner (2026-10-26: "start from the dashboard only"): two icons.
  LE START     opens the dashboard's Start page (START_DASHBOARD.bat starts the bot server first when it is not running);
               the page's one "Start trading" button does every step (update, NinjaTrader, live bars, Sim test, start)
  LE STOP BOT  stops the bot and the dashboard (asks first)
The older icons it made before (LE START BOT, LE UPDATE, LE DASHBOARD, LE HEALTH CHECK) are removed: the Start page does
what they did. The .bat files stay in the project folder. Safe to run again: it replaces what it made.

  powershell -ExecutionPolicy Bypass -File .\scripts\make_shortcuts.ps1          (SETUP_SHORTCUTS.bat runs this)
  powershell -ExecutionPolicy Bypass -File .\scripts\make_shortcuts.ps1 -DryRun  (show what it would make)
  powershell -ExecutionPolicy Bypass -File .\scripts\make_shortcuts.ps1 -Remove  (delete the icons)
#>
param(
    [switch]$DryRun,
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath('Desktop')      # follows a OneDrive-moved desktop
$Icons = Join-Path $env:SystemRoot 'System32\shell32.dll'

$items = @(
    @{ Name = 'LE START';    File = 'START_DASHBOARD.bat'; Icon = 137; Tip = 'Open the Start page: one Start trading button does every step' },
    @{ Name = 'LE STOP BOT'; File = 'STOP_BOT.bat';        Icon = 27;  Tip = 'Stop the bot and the dashboard (asks first)' }
)
$retired = @('LE START BOT', 'LE UPDATE', 'LE DASHBOARD', 'LE HEALTH CHECK')

$shell = $null
if (-not $DryRun -and -not $Remove) { $shell = New-Object -ComObject WScript.Shell }

foreach ($name in $retired) {
    $old = Join-Path $Desktop ($name + '.lnk')
    if (-not (Test-Path -LiteralPath $old)) { continue }
    if ($DryRun) { Write-Host "would remove the old icon $name"; continue }
    Remove-Item -LiteralPath $old -ErrorAction SilentlyContinue
    Write-Host "removed the old icon $name (the Start page does it now)"
}

foreach ($it in $items) {
    $target = Join-Path $Root $it.File
    $lnk = Join-Path $Desktop ($it.Name + '.lnk')
    if ($Remove) {
        if ($DryRun) { Write-Host "would delete $lnk" }
        else { Remove-Item -LiteralPath $lnk -ErrorAction SilentlyContinue; Write-Host "removed $($it.Name)" }
        continue
    }
    if (-not (Test-Path -LiteralPath $target)) {
        Write-Host "[FIX] $($it.File) not found in $Root (run UPDATE first)"
        continue
    }
    if ($DryRun) {
        Write-Host "would create $lnk -> $target"
        continue
    }
    $s = $shell.CreateShortcut($lnk)
    $s.TargetPath = $target
    $s.WorkingDirectory = $Root
    $s.IconLocation = "$Icons,$($it.Icon)"
    $s.Description = $it.Tip
    $s.Save()
    Write-Host "[OK]  $($it.Name) is on the desktop"
}
