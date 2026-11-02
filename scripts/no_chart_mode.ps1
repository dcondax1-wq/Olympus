# NO CHART MODE (2026-11-02): copies the LE_Feed add-on (bars with no chart) and the updated LE_BarFeed indicator into
# NinjaTrader 8's NinjaScript folders. Read-only for trading: it copies two files and touches nothing else.
# After it: in NinjaTrader, Control Center > New > NinjaScript Editor > press F5 (once). ninjatrader\SETUP.md "No-chart mode".
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$docs = [Environment]::GetFolderPath('MyDocuments')
$nt = Join-Path $docs 'NinjaTrader 8'
if (-not (Test-Path -LiteralPath $nt)) {
    $od = Join-Path $env:USERPROFILE 'OneDrive\Documents\NinjaTrader 8'
    if (Test-Path -LiteralPath $od) { $nt = $od }
}
if (-not (Test-Path -LiteralPath $nt)) {
    Write-Host " [FIX] NinjaTrader 8 folder not found in Documents. Open NinjaTrader once, then run this again."
    exit 1
}
$copies = @(
    @{ src = (Join-Path $root 'ninjatrader\LE_Feed.cs');    dst = (Join-Path $nt 'bin\Custom\AddOns') },
    @{ src = (Join-Path $root 'ninjatrader\LE_BarFeed.cs'); dst = (Join-Path $nt 'bin\Custom\Indicators') }
)
foreach ($c in $copies) {
    if (-not (Test-Path -LiteralPath $c.dst)) { New-Item -ItemType Directory -Path $c.dst -Force | Out-Null }
    $to = Join-Path $c.dst (Split-Path -Leaf $c.src)
    if (Test-Path -LiteralPath $to) { Copy-Item -LiteralPath $to -Destination ($to + '.bak') -Force }
    Copy-Item -LiteralPath $c.src -Destination $to -Force
    Write-Host " [OK] $(Split-Path -Leaf $c.src) -> $($c.dst)"
}
Write-Host ""
Write-Host " Now in NinjaTrader: Control Center > New > NinjaScript Editor > press F5 (the bottom says it compiled)."
Write-Host " Then Connections > Configure > your MFFU connection > tick 'Connect on startup' > OK. You can close the MNQ chart."
Write-Host " If F5 shows red errors: send Claude a photo. Your old copies were kept as .bak, so nothing is lost."
