<#
KALSHI KEY SETUP (double-click KALSHI_KEY_SETUP.bat). Saves the owner's Kalshi API key OUTSIDE the bot folder, once:
  1. finds the key file Kalshi just downloaded (Downloads / Desktop / OneDrive / iCloud Drive, so a key made on the iPhone and saved
     to iCloud Drive works too: the newest small .txt / .pem / .key that holds a private key), MOVES it to %USERPROFILE%\.olympus\kalshi\kalshi_key.pem (OLYMPUS_HOME\kalshi when set) and locks that folder
     to this Windows user (icacls); the downloaded copy is gone after the move
  2. asks for the Key ID Kalshi shows next to the key (pasted, hidden as you paste) and saves it in the same folder (key_id.txt)
  3. one signed READ (the balance) with python -m engine.kalshi_live --check-key: [OK] or one [FIX] line
It never shows the key, never puts it on a command line, never writes it inside the bot folder, never arms anything and never
places an order. Going live is a separate step: KALSHI_LIVE.bat, where YOU type the phrase. Safe to run again (Enter keeps
the saved Key ID; no new download keeps the saved key).
  -DryRun   says what it would do, changes nothing.
Tests: tests\test_kalshi_live.py part h (static: the key is never printed, never on a command line, never in the repo).
#>
param(
    [switch]$DryRun,
    [string]$Python = ""
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

$Root = Split-Path -Parent $PSScriptRoot
$Home1 = $env:OLYMPUS_HOME
if (-not $Home1) {
    $up = $env:USERPROFILE; if (-not $up) { $up = $HOME }
    $Home1 = Join-Path $up '.olympus'
}
$KeyDir = Join-Path $Home1 'kalshi'
$KeyFile = Join-Path $KeyDir 'kalshi_key.pem'
$IdFile = Join-Path $KeyDir 'key_id.txt'

Write-Host ''
Write-Host '  KALSHI KEY SETUP: saves your Kalshi API key on this PC, outside the bot folder. About 1 minute.'
Write-Host '  It never trades, never arms anything and never shows the key.'
Write-Host ''

if (-not $Python) {
    if ($env:LE_PYTHON) { $Python = $env:LE_PYTHON }
    else {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { $Python = $cmd.Source }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) {
    Stop-WithFix 'Python not found: install Python 3.12 (tick "Add python.exe to PATH"), then double-click KALSHI_KEY_SETUP.bat again.'
}
if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $Root 'engine') 'kalshi_live.py'))) {
    Stop-WithFix 'This bot folder has old code (engine\kalshi_live.py is missing): update it first (UPDATE.bat), then try again.'
}

# ---- 1/3 the key file Kalshi downloaded ----------------------------------------------------------------------------------
Write-Host '  1/3 The key file (kalshi.com > Account > Profile Settings > API Keys > Create New API Key downloads it)'
$dirs = @()
$dl = $null
try { $dl = (New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path } catch { }
$h = $env:USERPROFILE
foreach ($d in @($dl, (Join-Path $h 'Downloads'), (Join-Path $h 'Desktop'), (Join-Path $h 'OneDrive\Downloads'), (Join-Path $h 'OneDrive\Desktop'),
                 (Join-Path $h 'iCloudDrive'), (Join-Path $h 'iCloudDrive\Downloads'), [Environment]::GetFolderPath('Desktop'), $Root)) {
    if ($d -and (Test-Path -LiteralPath $d) -and ($dirs -notcontains $d)) { $dirs += $d }
}
$found = @()
foreach ($d in $dirs) {
    foreach ($f in @(Get-ChildItem -LiteralPath $d -File -ErrorAction SilentlyContinue | Where-Object {
                $_.Length -lt 20000 -and $_.Extension -match '^\.(txt|pem|key)$' })) {
        $head = ''
        try { $head = [IO.File]::ReadAllText($f.FullName) } catch { }
        if ($head -match '-----BEGIN [A-Z ]*PRIVATE KEY-----') { $found += $f }
        $head = $null
    }
}
$haveOld = Test-Path -LiteralPath $KeyFile
$pick = $null
if ($found.Count) { $pick = ($found | Sort-Object LastWriteTime | Select-Object -Last 1) }
if (-not $pick -and -not $haveOld) {
    Stop-WithFix 'No Kalshi key file found in Downloads or on the Desktop. On this PC open kalshi.com > your account > Profile Settings > API Keys > Create New API Key; it downloads a .txt file. Then double-click KALSHI_KEY_SETUP.bat again. Nothing was saved.'
}
if ($DryRun) {
    Write-Host 'DRY RUN - nothing changed. Would:'
    if ($pick) { Write-Host "  1 move    : the key file $($pick.Name) to $KeyFile (folder locked to this Windows user)" }
    else { Write-Host '  1 keep    : the key already saved' }
    Write-Host "  2 ask     : the Key ID (hidden), saved to $IdFile"
    Write-Host "  3 check   : $Python -X utf8 -m engine.kalshi_live --check-key (one signed read of the balance)"
    exit 0
}
try {
    New-Item -ItemType Directory -Force -Path $KeyDir | Out-Null
} catch {
    Stop-WithFix "Windows would not make the folder ${KeyDir}: restart the PC, then double-click KALSHI_KEY_SETUP.bat again."
}
if ($pick) {
    try {
        Move-Item -LiteralPath $pick.FullName -Destination $KeyFile -Force
    } catch {
        Stop-WithFix 'Windows would not move the key file (is it open in another window?): close it, then double-click KALSHI_KEY_SETUP.bat again.'
    }
    Write-Host "  [OK] Key file $($pick.Name) moved out of Downloads into your private folder (it is not in the bot folder)."
    if ($found.Count -gt 1) { Write-Host "       ($($found.Count - 1) older key file(s) left where they were: delete them by hand.)" }
} else {
    Write-Host '  [OK] No new download: the key already saved on this PC stays.'
}
try {
    & icacls "$KeyDir" /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)F" 2>&1 | Out-Null
} catch { }
Write-Host ''

# ---- 2/3 the Key ID ------------------------------------------------------------------------------------------------------
Write-Host '  2/3 The Key ID (Kalshi shows it next to the key: letters, digits and dashes)'
$oldId = ''
if (Test-Path -LiteralPath $IdFile) { $oldId = ([string](Get-Content -LiteralPath $IdFile -Raw -ErrorAction SilentlyContinue)).Trim() }
if ($oldId) { Write-Host '      A Key ID is already saved: just press Enter to keep it.' }
Write-Host '      Paste the Key ID (right-click pastes; you only see * ), then press Enter.'
$sec = Read-Host -AsSecureString '      Key ID'
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try { $kid = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
$kid = ([string]$kid).Trim()
if (-not $kid -and $oldId) { $kid = $oldId }
if ($kid -notmatch '^[0-9A-Za-z-]{16,80}$') {
    Stop-WithFix 'That is not a Kalshi Key ID (letters, digits and dashes, shown next to the key on kalshi.com): copy it again, then double-click KALSHI_KEY_SETUP.bat again. The key file stays saved.'
}
try {
    [IO.File]::WriteAllText($IdFile, $kid)
} catch {
    Stop-WithFix 'Windows would not save the Key ID: restart the PC, then double-click KALSHI_KEY_SETUP.bat again.'
}
$kid = $null
Write-Host '  [OK] Saved in your private folder (never shown, never in the bot folder).'
Write-Host ''

# ---- 3/3 one signed read: does Kalshi accept the key? -------------------------------------------------------------------
Write-Host '  3/3 Checking the key with Kalshi (one read of your balance; nothing is traded)...'
$out = @(& $Python -X utf8 -m engine.kalshi_live --check-key 2>&1 | ForEach-Object { "$_" })
$rc = $LASTEXITCODE
$out | Where-Object { $_ -match '\[(OK|FIX)\]' } | ForEach-Object { Write-Host "      $_" }
if ($rc -ne 0) {
    Stop-WithFix 'Kalshi did not accept the key (see the line above). Make a new key on kalshi.com (API Keys > Create New API Key), then double-click KALSHI_KEY_SETUP.bat again.'
}
Write-Host ''
Write-Host '  DONE. Kalshi stays OFF (paused) until you go live yourself:' -ForegroundColor Green
Write-Host '  double-click KALSHI_LIVE.bat and type the phrase it shows. Stop any time: KALSHI_STOP.bat or the phone''s ZEUS Safety page.'
exit 0
