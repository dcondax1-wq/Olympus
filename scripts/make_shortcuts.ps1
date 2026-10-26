<#
Desktop icons for the owner: LE UPDATE, LE DASHBOARD, LE HEALTH CHECK, LE STOP BOT (each opens the .bat of the same name
in the project folder). Safe to run again: it replaces the four icons it made.

  powershell -ExecutionPolicy Bypass -File .\scripts\make_shortcuts.ps1          (SETUP_SHORTCUTS.bat runs this)
  powershell -ExecutionPolicy Bypass -File .\scripts\make_shortcuts.ps1 -DryRun  (show what it would make)
  powershell -ExecutionPolicy Bypass -File .\scripts\make_shortcuts.ps1 -Remove  (delete the four icons)
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
    @{ Name = 'LE START BOT';    File = 'START_BOT.bat';       Icon = 137; Tip = 'Start Zlarior + ATLAS: update, setup, Sim test, then you type the live phrase' },
    @{ Name = 'LE UPDATE';       File = 'UPDATE.bat';          Icon = 238; Tip = 'Update the bot: stop, git pull, pip install, restart, self-test' },
    @{ Name = 'LE DASHBOARD';    File = 'START_DASHBOARD.bat'; Icon = 13;  Tip = 'Open the dashboard (starts the bot server if needed)' },
    @{ Name = 'LE HEALTH CHECK'; File = 'HEALTH_CHECK.bat';    Icon = 23;  Tip = 'Green / red checks with the fix for each' },
    @{ Name = 'LE STOP BOT';     File = 'STOP_BOT.bat';        Icon = 27;  Tip = 'Stop the bot and the dashboard (asks first)' }
)

$shell = $null
if (-not $DryRun -and -not $Remove) { $shell = New-Object -ComObject WScript.Shell }

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
