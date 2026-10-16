<#
Removes the "LiquidityEngine" scheduled task created by install_autostart.ps1. Does not stop a running server
(use stop_bot.ps1 for that).   -DryRun prints what would be removed.
#>
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
$TaskName = 'LiquidityEngine'
$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $t) { Write-Host "Task $TaskName is not installed; nothing to do"; exit 0 }
$acts = ($t.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join ' | '
if ($DryRun) {
    Write-Host "DRY RUN - would remove task $TaskName (state $($t.State)): $acts"
    exit 0
}
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "REMOVED scheduled task $TaskName ($acts)"
Write-Host "A server already running keeps running; stop it with scripts\stop_bot.ps1"
