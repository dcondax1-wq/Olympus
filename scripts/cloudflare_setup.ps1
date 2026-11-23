<#
CLOUDFLARE SETUP (double-click tools\bat\CLOUDFLARE_SETUP.bat). Moves the phone site from Netlify to Cloudflare Pages in one go
(docs\HOSTING.md): 1. Node.js LTS (checked, installed with winget if missing), 2. asks for the Cloudflare API token (masked)
and the Account ID, 3. saves both as Windows USER variables CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID (never shown, never
written to a file), 4. tools\pc_publish.py --setup cloudflare --cf-project olympus-dash, then one --force publish, 5. prints the
new address. Any failure prints one [FIX] line; when the first publish fails, the old publisher settings come back (Netlify
keeps updating). Safe to run again: Enter keeps the saved key and id.
  -DryRun   says what it would do, changes nothing.
It never starts, stops, arms or routes the bot and never touches NinjaTrader or any order.
Tests: tests\test_cloudflare_setup.py (static: the key is never printed, never written to a file, never on a command line).
#>
param(
    [switch]$DryRun,
    [string]$Python = "",
    [string]$Project = "olympus-dash"
)

$ErrorActionPreference = 'Continue'
trap {
    Write-Host ''
    Write-Host '  [FIX] Something unexpected stopped this: take a photo of this window and send it to Claude.' -ForegroundColor Red
    exit 1
}

function Stop-WithFix([string]$Msg) {
    Write-Host ''
    Write-Host "  [FIX] $Msg" -ForegroundColor Red
    exit 1
}

function Update-PathNow {
    $m = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $u = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$m;$u"
    if ($env:ProgramFiles) {
        $nd = Join-Path $env:ProgramFiles 'nodejs'
        if (Test-Path -LiteralPath $nd) { $env:Path = "$nd;$env:Path" }
    }
}

$Root = Split-Path -Parent $PSScriptRoot
$Script = Join-Path (Join-Path $Root 'tools') 'pc_publish.py'
$Home1 = $env:OLYMPUS_HOME
if (-not $Home1) {
    $up = $env:USERPROFILE; if (-not $up) { $up = $HOME }
    $Home1 = Join-Path $up '.olympus'
}
$PubFile = Join-Path $Home1 'publish.json'
$PubBak = Join-Path $Home1 'publish.before_cloudflare.json'

Write-Host ''
Write-Host '  CLOUDFLARE SETUP: your phone site moves to Cloudflare Pages (free, no badge). About 3 minutes.'
Write-Host '  It never touches the bot, NinjaTrader or any order.'
Write-Host ''

if (-not $Python) {
    if ($env:LE_PYTHON) { $Python = $env:LE_PYTHON }
    else {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { $Python = $cmd.Source }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) {
    Stop-WithFix 'Python not found: install Python 3.12 (tick "Add python.exe to PATH"), then double-click tools\bat\CLOUDFLARE_SETUP.bat again.'
}
if (-not (Test-Path -LiteralPath $Script)) { Stop-WithFix "tools\pc_publish.py is missing in ${Root}: send a photo of this window to Claude." }

if ($DryRun) {
    Write-Host 'DRY RUN - nothing changed. Would:'
    Write-Host '  1 Node.js : check node / npx, else winget install OpenJS.NodeJS.LTS'
    Write-Host '  2 ask     : the Cloudflare API token (masked) and the Account ID'
    Write-Host '  3 save    : USER variables CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID (no file)'
    Write-Host "  4 run     : $Python -X utf8 $Script --setup cloudflare --cf-project $Project, then --force --strict"
    Write-Host "  5 show    : https://$Project.pages.dev (or the address Cloudflare gives)"
    exit 0
}

# ---- 1/4 Node.js ----------------------------------------------------------------------------------------------------
Write-Host '  1/4 Node.js (Cloudflare''s upload tool needs it)'
Update-PathNow
$npx = Get-Command npx -ErrorAction SilentlyContinue
if (-not $npx) {
    $wg = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $wg) {
        Stop-WithFix 'Node.js is missing and winget is not on this PC: install the LTS from nodejs.org (big green button), then double-click tools\bat\CLOUDFLARE_SETUP.bat again.'
    }
    Write-Host '      Installing Node.js LTS (free, about 1 minute; click Yes if Windows asks)...'
    & winget install --id OpenJS.NodeJS.LTS -e --silent --accept-source-agreements --accept-package-agreements
    Update-PathNow
    $npx = Get-Command npx -ErrorAction SilentlyContinue
    if (-not $npx) {
        Stop-WithFix 'Node.js did not install: restart the PC, then double-click tools\bat\CLOUDFLARE_SETUP.bat again (or install the LTS from nodejs.org).'
    }
}
$nodeV = ''
try { $nodeV = (& node --version) } catch { }
Write-Host "  [OK] Node.js $nodeV is ready."
Write-Host ''

# ---- 2/4 the key and the account id ---------------------------------------------------------------------------------
Write-Host '  2/4 Your Cloudflare key (made on dash.cloudflare.com > Profile > API Tokens, docs\HOSTING.md)'
$OldKey = [Environment]::GetEnvironmentVariable('CLOUDFLARE_API_TOKEN', 'User')
$OldAcct = [Environment]::GetEnvironmentVariable('CLOUDFLARE_ACCOUNT_ID', 'User')
if ($OldKey) { Write-Host '      A key is already saved on this PC: just press Enter to keep it.' }
Write-Host '      Paste the API token (right-click pastes; you only see * ), then press Enter.'
$sec = Read-Host -AsSecureString '      Token'
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try { $CfKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
$CfKey = ([string]$CfKey).Trim()
if ($CfKey -match '^bearer\s+') { $CfKey = ($CfKey -replace '^bearer\s+', '').Trim() }
if (-not $CfKey -and $OldKey) { $CfKey = $OldKey }
if (-not $CfKey) { Stop-WithFix 'No token was pasted: copy it on Cloudflare (Create Token > Create), then double-click tools\bat\CLOUDFLARE_SETUP.bat again. Nothing was saved.' }
if ($CfKey -match '\s' -or $CfKey.Length -lt 20) {
    Stop-WithFix 'That is not a Cloudflare API token (it is one long word, about 40 letters and digits): copy it again, then double-click tools\bat\CLOUDFLARE_SETUP.bat again. Nothing was saved.'
}

if ($OldAcct) { Write-Host '      An Account ID is already saved: just press Enter to keep it.' }
Write-Host '      Paste the Account ID (32 letters and digits; Cloudflare > Workers & Pages, right side), then press Enter.'
$CfAcct = ([string](Read-Host '      Account ID')).Trim()
if (-not $CfAcct -and $OldAcct) { $CfAcct = $OldAcct }
if ($CfAcct -notmatch '^[0-9a-fA-F]{32}$') {
    Stop-WithFix 'That is not the Account ID (it is 32 letters a-f and digits): copy it from Workers & Pages (right side), then double-click tools\bat\CLOUDFLARE_SETUP.bat again. Nothing was saved.'
}
Write-Host ''

# ---- 3/4 save them as Windows user variables (no file, never printed) ----------------------------------------------
Write-Host '  3/4 Saving them in your Windows user settings'
try {
    [Environment]::SetEnvironmentVariable('CLOUDFLARE_API_TOKEN', $CfKey, 'User')
    [Environment]::SetEnvironmentVariable('CLOUDFLARE_ACCOUNT_ID', $CfAcct, 'User')
} catch {
    Stop-WithFix 'Windows would not save the settings: restart the PC, then double-click tools\bat\CLOUDFLARE_SETUP.bat again.'
}
$env:CLOUDFLARE_API_TOKEN = $CfKey
$env:CLOUDFLARE_ACCOUNT_ID = $CfAcct
$CfKey = $null
Write-Host '  [OK] Saved (only in Windows, not in any file; never shown).'
Write-Host ''

# ---- 4/4 switch the publisher to Cloudflare and publish once --------------------------------------------------------
Write-Host '  4/4 Switching the phone site to Cloudflare and publishing (the first time takes 1-3 minutes)...'
$hadPub = Test-Path -LiteralPath $PubFile
if ($hadPub) { Copy-Item -LiteralPath $PubFile -Destination $PubBak -Force -ErrorAction SilentlyContinue }
$out1 = @(& $Python -X utf8 $Script --setup cloudflare --cf-project $Project 2>&1 | ForEach-Object { "$_" })
$rc1 = $LASTEXITCODE
if ($rc1 -ne 0) {
    $why = ($out1 | Where-Object { $_ -match '\[FIX\]' } | Select-Object -First 1)
    if ($why) { Stop-WithFix (($why -replace '^.*\[FIX\]\s*', '')) }
    Stop-WithFix 'The switch to Cloudflare did not work: take a photo of this window and send it to Claude.'
}

$out2 = @(& $Python -X utf8 $Script --force --strict 2>&1 | ForEach-Object { "$_" })
$rc2 = $LASTEXITCODE
$out2 | ForEach-Object { Write-Host "      $_" }
if ($rc2 -ne 0) {
    if ($hadPub -and (Test-Path -LiteralPath $PubBak)) { Copy-Item -LiteralPath $PubBak -Destination $PubFile -Force -ErrorAction SilentlyContinue }
    elseif (-not $hadPub) { Remove-Item -LiteralPath $PubFile -Force -ErrorAction SilentlyContinue }
    $kept = ' Nothing else changed: your old site keeps updating.'
    $prob = ($out2 | Where-Object { $_ -match 'PUBLISH 6/6 problem:' } | Select-Object -First 1)
    $prob = [string]$prob
    if ($prob -match 'refused the key') { Stop-WithFix ('Cloudflare refused the key: make a new token (Custom token > Account / Cloudflare Pages / Edit), then double-click tools\bat\CLOUDFLARE_SETUP.bat again.' + $kept) }
    if ($prob -match 'account id') { Stop-WithFix ('Cloudflare needs the Account ID: double-click tools\bat\CLOUDFLARE_SETUP.bat again and paste it.' + $kept) }
    if ($prob -match 'npx|Node') { Stop-WithFix ('Node.js is not ready: restart the PC, then double-click tools\bat\CLOUDFLARE_SETUP.bat again.' + $kept) }
    if ($prob -match 'still running') { Stop-WithFix ('Another publish was running: wait 2 minutes, then double-click tools\bat\CLOUDFLARE_SETUP.bat again.' + $kept) }
    if ($prob -match 'in time|reach|connect|network') { Stop-WithFix ('Cloudflare could not be reached: check the internet, then double-click tools\bat\CLOUDFLARE_SETUP.bat again.' + $kept) }
    Stop-WithFix ('The first Cloudflare publish failed (see the PUBLISH lines above): take a photo of this window and send it to Claude.' + $kept)
}
if (Test-Path -LiteralPath $PubBak) { Remove-Item -LiteralPath $PubBak -Force -ErrorAction SilentlyContinue }

$url = "https://$Project.pages.dev"
foreach ($l in $out2) { if ($l -match '^PUBLISH 2/6.*?(https://[a-z0-9-]+\.pages\.dev)') { $url = $Matches[1] } }
Write-Host ''
Write-Host "  DONE. Your phone site is now:  $url" -ForegroundColor Green
Write-Host '  Add it to your home screen: open it in Safari on the iPhone > Share > Add to Home Screen.'
$task = $null
try { $task = Get-ScheduledTask -TaskName 'OlympusPublishNQ' -ErrorAction SilentlyContinue } catch { }
if ($task) { Write-Host '  It updates by itself every 15 minutes (the PUBLISH NQ task).' }
else { Write-Host '  To keep it updating every 15 minutes: double-click tools\bat\PUBLISH_NQ.bat once.' }
exit 0
