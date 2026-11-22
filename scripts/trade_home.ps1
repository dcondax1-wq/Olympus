<#
TRADING HOME launcher (TRADE_HOME.bat). Finds Python (LE_PYTHON, else python) and opens the menu in engine\trade_home.py.
It never types, stores or passes a live phrase: START BOT and the keep-alive step ask the owner in their own windows.
Windows PowerShell 5.1 safe, ASCII only.
#>
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
$py = 'python'
if ($env:LE_PYTHON) { $py = $env:LE_PYTHON }
$env:PYTHONIOENCODING = 'utf-8'

$ok = $false
try { & $py --version *> $null; if ($LASTEXITCODE -eq 0) { $ok = $true } } catch { }
if (-not $ok) {
    Write-Host '  [FIX] Python not found. Install Python 3.12 from python.org and tick "Add python.exe to PATH".'
    exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $Root 'engine\trade_home.py'))) {
    Write-Host '  [FIX] engine\trade_home.py is missing: double-click UPDATE.bat, then try again.'
    exit 1
}
& $py -X utf8 -m engine.trade_home @args
exit $LASTEXITCODE
