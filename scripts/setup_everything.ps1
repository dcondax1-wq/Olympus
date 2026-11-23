<#
SETUP EVERYTHING (double-click SETUP_EVERYTHING.bat). Owner 2026-11-14 ("one double-click"): this weekend's three PC jobs in
ONE window, in order, each one checked first and skipped when it is already done. docs\SETUP_EVERYTHING.md.

  1 NEW CODE    the newest OLYMPUS_BACKUP_*.zip (+ its .sha256.txt) in Downloads / on the Desktop (or the zip dragged onto the
                .bat) into the bot folder with tools\update_from_zip.py, taken out of that zip: --check first (skipped when the
                folder already has that code, or the zip is older), then the update. A running bot server is stopped first only
                after you type Y (scripts\stop_bot.ps1, the STOP_BOT.bat stop; never with an open trade) and started again after
                step 1b (one stop for both; the bot itself stays stopped). Then the bot folder's own copy of this script goes on
                (when it differs from the one running: the update brought a newer one, or the folder has a newer one than the zip).
                Skipped with one OK line when the folder already updates itself from the backup (--source-status 0): a zip
                would make its code differ from the backup and stop every auto-update (UPDATE.bat takes the newest code).
  1b AUTO-UPDATE (2026-11-14, docs\AUTO_UPDATE.md) the PC gets new code from the private backup repo by itself from then on:
                python -m engine.autoupdate --source-status first (read only: 0 already on -> skipped, 10 -> the connect; any
                other answer is a SKIP with its line), then --connect --port N, attached to this window (a GitHub sign-in window
                may open the first time: the "account" in update_source.json). The bot server is stopped for it (--connect
                refuses while it answers): never with an open trade, while the market is open only after a Y, a server step 1
                stopped is still stopped; it is started again right after. Every code but 0 (20 backup not reachable, 21 not
                now, 22 no git, 1 failed and put back) is one [SKIP] line, never a stop: steps 2 and 3 always go on. Skipped
                when the folder's code has no auto-update yet. A connect that brings another copy of this script hands over.
  1c DASHBOARD  (2026-11-15, optional) the dashboard site on Netlify ($NetlifySite, its one place) updates itself from this PC.
                Skipped when %USERPROFILE%\.olympus\netlify.json has a key and a site id and the PUBLISH_NQ task is there. Else
                ONE hidden prompt for the Netlify key (Enter skips; how to make one in two lines), tools\pc_publish.py --setup
                netlify --site-name finds the site with it (the key only on its stdin: never shown, logged, stored here or put
                on a command line), then scripts\publish_nq.ps1 (the tools\bat\PUBLISH_NQ.bat task, reused as is) sets up the 15-minute
                task and publishes once. Only the lite set leaves the PC, never a private file (pc_publish.deploy_set). A key
                already saved with the task missing: only the task. Every problem is one [SKIP] line, never a stop.
  2 PHONE LINK  the private Tailscale link to the dashboard (scripts\live_link.ps1); skipped when "tailscale serve" already points
                at the bot server and the site task is there. A failure says what to do, Enter tries again, LATER skips it.
                The link is shown big and put on the clipboard.
  3 GO LIVE     skipped when Zlarior (50K) and ATLAS (25K) already run live and armed (the bot's GET /api/site/launch.json).
                Else the pause screen: "Is it Sunday after 6 PM ET and are both evals active on MFFU? Type YES" (a YES before
                Sunday 18:00 ET is refused by the clock). Only then GO_LIVE_EVAL's flow: scripts\bots_back.ps1 -NoResume, then
                python -m engine.go, where YOU type the live phrase yourself. This script never types, reads, passes or stores
                the phrase and never arms anything by itself (a bot that runs unarmed is stopped first, after the YES).
  then the summary (one line per step).

  -BatDir DIR   the folder the .bat was double-clicked in (it may be the zip's temp folder)        -Zip FILE   this code zip
  -BotDir DIR   the bot folder (default: found: the .bat's folder, LE_BOT_DIR, the bot's tasks and Startup shortcut,
                %USERPROFILE%\nq-liquidity-engine, the Desktop, Documents ...)
  -Step1 WORDS  (internal) the copy of this script that ran first did step 1 (its result): steps 2 and 3 only
  -ServerWait / -ArmWait  seconds to wait for the bot server to answer again / for both evals to show armed (tests: short)
This script itself never edits live_model*.json or engine\ (the updater and the auto-update do, by their own rules), never
places an order, never touches NinjaTrader settings.
Tests: tests\test_setup_everything.py (pwsh; fakes for engine.go, engine.autoupdate, the child scripts, tailscale and the bot server;
LE_SE_T_LOG / LE_SE_T_TASKS / LE_SE_T_NOW stand in for the Windows-only steps and the clock).
#>
param(
    [string]$BatDir = "",
    [string]$Zip = "",
    [string]$BotDir = "",
    [string]$Python = "",
    [string]$Tailscale = "",
    [int]$Port = 0,
    [int]$ServerWait = 120,
    [int]$ArmWait = 60,
    [string]$Step1 = ""
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
trap {
    Write-Host ''
    Write-Host ("  [FIX] Something unexpected stopped this window ({0}). Double-click SETUP_EVERYTHING.bat again; if it stops here again, send a photo of this window to Claude." -f $_.Exception.Message) -ForegroundColor Red
    exit 1
}
# the owner's dashboard site on Netlify (step 1c: tools\pc_publish.py looks its id up with the key): its one place
$NetlifySite = 'moonlit-scone-08afe5'

# ------------------------------------------------------------------------------------------------ small helpers
function J2([string]$A, [string]$B) { return [System.IO.Path]::Combine($A, $B) }
function JP([string]$Base, [string]$Rel) {
    $p = $Base
    foreach ($s in ($Rel -split '[\\/]')) { if ($s) { $p = [System.IO.Path]::Combine($p, $s) } }
    return $p
}
function OnWindows { return ($env:OS -eq 'Windows_NT') }
function P($Obj, [string]$Name) {
    if ($null -eq $Obj) { return $null }
    $q = $Obj.PSObject.Properties[$Name]; if ($q) { return $q.Value }; return $null
}
function Say([string]$Kind, [string]$Text) {
    $c = 'Gray'
    if ($Kind -eq 'OK') { $c = 'Green' } elseif ($Kind -eq 'FIX') { $c = 'Red' } elseif ($Kind -eq 'SKIP' -or $Kind -eq 'WAIT') { $c = 'Yellow' }
    Write-Host ("  [{0}] {1}" -f $Kind, $Text) -ForegroundColor $c
}
function Fix([string]$What, [string]$Do) {
    # every failure: ONE line, what happened + the exact fix + the photo
    Write-Host ("  [FIX] {0}. {1}. If it still fails, send a photo of this window." -f $What, $Do) -ForegroundColor Red
}
function Band([string]$Text) {
    Write-Host '  ' -NoNewline
    Write-Host $Text.PadRight(72) -ForegroundColor White -BackgroundColor DarkBlue
}
function Header([string]$Num, [string]$Title) {
    $bar = '=' * 72
    Write-Host ''
    Write-Host "  $bar" -ForegroundColor Cyan
    Band ("   {0}  :  {1}" -f $Num, $Title.ToUpper())
    Write-Host "  $bar" -ForegroundColor Cyan
}
function TLog([string]$What) {
    # tests: a Windows-only step is written to LE_SE_T_LOG instead of being done
    if ($env:LE_SE_T_LOG) { Add-Content -LiteralPath $env:LE_SE_T_LOG -Value $What; return $true }
    return $false
}
function Ask([string]$Prompt) {
    Write-Host ''
    $a = Read-Host $Prompt
    if ($null -eq $a) { return '' }
    return ([string]$a).Trim()
}
function Ask-Secret([string]$Prompt) {
    # ONE hidden line (nothing shows while you paste). The answer is never shown, written, logged or put on a command line: the
    # caller pipes it to tools\pc_publish.py's stdin and forgets it. A redirected input (a pipe, the tests) has no console to
    # hide it on: there the line is read as it comes (nothing is echoed there either).
    Write-Host ''
    if ([Console]::IsInputRedirected) {
        Write-Host ($Prompt + ': ') -NoNewline
        $t = [Console]::In.ReadLine()
        Write-Host ''
        if ($null -eq $t) { return '' }
        return ([string]$t).Trim()
    }
    $s = Read-Host -AsSecureString $Prompt
    if ($null -eq $s -or $s.Length -eq 0) { return '' }
    try { return ([string](New-Object System.Net.NetworkCredential('', $s)).Password).Trim() } catch { return '' }
}
function File-Sha([string]$Path) {
    try { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash } catch { return '' }
}

# ------------------------------------------------------------------------------------------------ New York time, no tz database
function Utc-Now {
    if ($env:LE_SE_T_NOW) { return (New-Object DateTime -ArgumentList @(1970, 1, 1, 0, 0, 0)).AddSeconds([double]$env:LE_SE_T_NOW) }
    return [DateTime]::UtcNow
}
function Et-Now {
    # daylight time from the 2nd Sunday of March 07:00 UTC to the 1st Sunday of November 06:00 UTC (tools\update_from_zip.py et_now)
    $u = Utc-Now
    $mar = New-Object DateTime -ArgumentList @($u.Year, 3, 1, 7, 0, 0)
    $start = $mar.AddDays(((7 - [int]$mar.DayOfWeek) % 7) + 7)
    $nov = New-Object DateTime -ArgumentList @($u.Year, 11, 1, 6, 0, 0)
    $end = $nov.AddDays((7 - [int]$nov.DayOfWeek) % 7)
    $off = -5
    if ($u -ge $start -and $u -lt $end) { $off = -4 }
    return $u.AddHours($off)
}
function Et-Words($E) { return $E.ToString('dddd h:mm tt', [System.Globalization.CultureInfo]::InvariantCulture) }
function Market-Open($E) {
    # CME equity-index futures: Sunday 18:00 ET to Friday 17:00 ET, with a break 17:00-18:00 ET every day (tools\update_from_zip.py)
    $d = [int]$E.DayOfWeek
    $m = $E.Hour * 60 + $E.Minute
    if ($d -eq 6) { return $false }
    if ($d -eq 0) { return ($m -ge 18 * 60) }
    if ($d -eq 5) { return ($m -lt 17 * 60) }
    return (-not ($m -ge 17 * 60 -and $m -lt 18 * 60))
}
function Weekend-Closed($E) {
    # the futures market's weekend: Friday 17:00 ET to Sunday 18:00 ET (the evals go live at Sunday's 18:00 ET open)
    $d = [int]$E.DayOfWeek
    $m = $E.Hour * 60 + $E.Minute
    if ($d -eq 6) { return $true }
    if ($d -eq 0) { return ($m -lt 18 * 60) }
    if ($d -eq 5) { return ($m -ge 17 * 60) }
    return $false
}

# ------------------------------------------------------------------------------------------------ the bot folder, python, the zip
$Markers = @('engine\lit.py', 'live_model.json', 'server.py')
$LocalSigns = @('.git', 'logs', 'backups', 'data\start_bot.json', 'data\autostart.json', 'data\live_state.json', '.env.local.ps1')
function Is-BotCode([string]$D) {
    if (-not $D) { return $false }
    foreach ($m in $Markers) { if (-not (Test-Path -LiteralPath (JP $D $m))) { return $false } }
    return $true
}
function Is-BotFolder([string]$D) {
    # the bot's code AND the files only a folder the bot really ran in has (an unpacked zip has none of them)
    if (-not (Is-BotCode $D)) { return $false }
    foreach ($s in $LocalSigns) { if (Test-Path -LiteralPath (JP $D $s)) { return $true } }
    return $false
}
function Task-Exists([string]$Name) {
    if ($null -ne $env:LE_SE_T_TASKS) { return (@($env:LE_SE_T_TASKS -split ',') -contains $Name) }
    try { return [bool](Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) } catch { return $false }
}
function Task-Dir([string]$Name) {
    if ($null -ne $env:LE_SE_T_TASKS) { return $null }
    try { return [string]((Get-ScheduledTask -TaskName $Name -ErrorAction Stop).Actions | Select-Object -First 1).WorkingDirectory } catch { return $null }
}
function Home-Dir {
    $up = $env:USERPROFILE
    if (-not $up) { $up = $HOME }
    return $up
}
function First-Bot($Cands) {
    foreach ($d in $Cands) { if ($d -and (Is-BotFolder $d)) { return (Get-Item -LiteralPath $d).FullName } }
    return $null
}
function Find-BotFolder {
    if ($BotDir) { if (Is-BotCode $BotDir) { return (Get-Item -LiteralPath $BotDir).FullName }; return $null }
    # 1. where the .bat / this script is, LE_BOT_DIR
    $f = First-Bot @($BatDir, (Split-Path -Parent $PSScriptRoot), $env:LE_BOT_DIR)
    if ($f) { return $f }
    # 2. where the bot itself says it lives: its scheduled tasks and the Startup shortcut engine\go.py made
    $c = New-Object System.Collections.Generic.List[string]
    foreach ($t in @('OlympusPCReport', 'OlympusLiveSite', 'OlympusPublishNQ')) { $w = Task-Dir $t; if ($w) { $c.Add($w) } }
    if (OnWindows) {
        try {
            $lnk = J2 ([Environment]::GetFolderPath('Startup')) 'LE bot server.lnk'
            if (Test-Path -LiteralPath $lnk) { $c.Add([string](New-Object -ComObject WScript.Shell).CreateShortcut($lnk).WorkingDirectory) }
        } catch { }
    }
    $f = First-Bot $c
    if ($f) { return $f }
    # 3. the usual places, then a renamed folder right inside the home folder, the Desktop or Documents
    $up = Home-Dir
    $c = New-Object System.Collections.Generic.List[string]
    $bases = New-Object System.Collections.Generic.List[string]
    foreach ($b in @($up, (J2 $up 'Desktop'), (J2 $up 'Documents'), (JP $up 'OneDrive\Desktop'), (JP $up 'OneDrive\Documents'))) { $bases.Add($b) }
    try { foreach ($k in @('Desktop', 'MyDocuments')) { $f = [Environment]::GetFolderPath($k); if ($f) { $bases.Add($f) } } } catch { }
    foreach ($b in $bases) { $c.Add((J2 $b 'nq-liquidity-engine')) }
    $c.Add((JP $up 'Documents\GitHub\nq-liquidity-engine'))
    if (OnWindows) { $c.Add('C:\nq-liquidity-engine') }
    $f = First-Bot $c
    if ($f) { return $f }
    foreach ($b in $bases) {
        if (-not (Test-Path -LiteralPath $b -PathType Container)) { continue }
        foreach ($sub in @(Get-ChildItem -LiteralPath $b -Directory -ErrorAction SilentlyContinue)) {
            if (Is-BotFolder $sub.FullName) { return $sub.FullName }
        }
    }
    return $null
}
function Find-Python {
    if ($Python) { if (Test-Path -LiteralPath $Python) { return $Python }; return $null }
    if ($env:LE_PYTHON -and (Test-Path -LiteralPath $env:LE_PYTHON)) { return $env:LE_PYTHON }
    # from PATH: ask it for the real python.exe (the empty Microsoft Store alias does not run), else the py launcher (as bots_back.ps1)
    foreach ($cand in @(@('python'), @('py', '-3'))) {
        $cmd = Get-Command $cand[0] -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $cmd) { continue }
        $pre = @($cand | Select-Object -Skip 1)
        try { $exe = & $cmd.Source @pre -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1 } catch { $exe = $null }
        if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path -LiteralPath "$exe".Trim())) { return "$exe".Trim() }
    }
    return $null
}
function Zip-Places {
    $up = Home-Dir
    $p = New-Object System.Collections.Generic.List[string]
    foreach ($x in @($script:Root, $BatDir, (J2 $up 'Downloads'), (J2 $up 'Desktop'), (JP $up 'OneDrive\Downloads'), (JP $up 'OneDrive\Desktop'))) { if ($x) { $p.Add($x) } }
    try { $d = [Environment]::GetFolderPath('Desktop'); if ($d) { $p.Add($d) } } catch { }
    if (OnWindows) {
        try { $dl = (New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path; if ($dl) { $p.Add($dl) } } catch { }
    }
    return $p
}
function Find-Zip {
    if ($Zip) {
        if (Test-Path -LiteralPath $Zip -PathType Leaf) { return (Get-Item -LiteralPath $Zip).FullName }
        return $null
    }
    $all = @()
    foreach ($d in (Zip-Places)) {
        if ($d -and (Test-Path -LiteralPath $d -PathType Container)) {
            $all += @(Get-ChildItem -LiteralPath $d -Filter 'OLYMPUS_BACKUP_*.zip' -File -ErrorAction SilentlyContinue)
        }
    }
    if (-not $all.Count) { return $null }
    return ($all | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
}
function Sha-File([string]$ZipPath) {
    # the .sha256.txt next to the zip (a browser's second download is "name (1).zip": the " (1)" is ignored)
    $d = Split-Path -Parent $ZipPath
    $b = [System.IO.Path]::GetFileNameWithoutExtension($ZipPath)
    $plain = $b -replace ' \(\d+\)$', ''
    foreach ($n in @("$plain.sha256.txt", "$b.sha256.txt")) { $q = J2 $d $n; if (Test-Path -LiteralPath $q) { return $q } }
    foreach ($f in @(Get-ChildItem -LiteralPath $d -Filter '*.sha256*.txt' -File -ErrorAction SilentlyContinue)) {
        $t = ''
        try { $t = [string](Get-Content -LiteralPath $f.FullName -Raw -ErrorAction Stop) } catch { }
        if ($t.Contains("$plain.zip")) { return $f.FullName }
    }
    return $null
}
function Zip-Extract([string]$ZipPath, [string]$Member, [string]$Out) {
    # 'ok' | 'missing' (no such file in the zip) | 'bad' (the zip does not open)
    try { Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop } catch { }
    try {
        $z = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    } catch { return 'bad' }
    try {
        $e = $z.GetEntry($Member)
        if (-not $e) { return 'missing' }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Out) | Out-Null
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($e, $Out, $true)
        return 'ok'
    } catch {
        return 'bad'
    } finally {
        $z.Dispose()
    }
}

# ------------------------------------------------------------------------------------------------ the bot server (read only)
function Port-Open([int]$P) {
    $cl = New-Object System.Net.Sockets.TcpClient
    try {
        $ar = $cl.BeginConnect('127.0.0.1', $P, $null, $null)
        if (-not $ar.AsyncWaitHandle.WaitOne(1500)) { return $false }
        $cl.EndConnect($ar)
        return $true
    } catch {
        return $false
    } finally {
        $cl.Close()
    }
}
function Get-Json([string]$Path) {
    # a local GET of the bot server's JSON (only ever 127.0.0.1; a 404 / an error / not JSON = $null)
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port$Path" -UseBasicParsing -TimeoutSec 8 -ErrorAction Stop
        if ($r -is [string]) { return $null }
        return $r
    } catch {
        return $null
    }
}
function Launch-State {
    # what the phone's Launch card sees (tools\launch_card.py through GET /api/site/launch.json): who is live and armed, open trades
    $o = @{ up = $false; known = $false; both = $false; running = $false; open = $false; words = '' }
    if (-not (Port-Open $Port)) { return $o }
    $o.up = $true
    $pg = Get-Json '/api/health/ping'
    if ($pg -and (P $pg 'ok')) { $o.running = [bool](P $pg 'bot_running') }
    $lj = Get-Json '/api/site/launch.json'
    if ($lj -and [string](P $lj 'kind') -eq 'le-launch' -and (P $lj 'live')) {
        $o.known = $true
        $rows = @(P $lj 'bots')
        $live = @{}
        foreach ($r in $rows) { if ($r) { $live[[string](P $r 'id')] = ([string](P $r 'mode') -eq 'LIVE' -and (P $r 'armed') -eq $true) } }
        $o.both = ($o.running -and $live['lit'] -eq $true -and $live['atlas'] -eq $true)
        $o.open = [bool](@($rows | Where-Object { $_ -and (P $_ 'position') }).Count)
        $o.words = (@($rows | Where-Object { $_ } | ForEach-Object { '{0}: {1}' -f (P $_ 'label'), (P $_ 'state') }) -join ', ')
    }
    return $o
}
function Stop-Bot {
    # the STOP_BOT.bat stop (scripts\stop_bot.ps1): the bot stopped through its API (that also clears its auto-start record, so
    # nothing comes back by itself), then the server and its supervisor; then wait until the port is closed
    $sb = JP $script:Root 'scripts\stop_bot.ps1'
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $sb)
    if ($Port -ne 8766) { $a += @('-Port', "$Port") }
    & $script:PsExe @a | Out-Host
    $until = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $until) {
        if (-not (Port-Open $Port)) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return (-not (Port-Open $Port))
}
function Start-Server {
    # the bot server again, hidden, as tools\bat\BOTS_BACK.bat starts it (scripts\run_bot.ps1); the bot itself stays stopped (Stop-Bot cleared its
    # auto-start record). The phone link (step 2) shows the dashboard only while the server runs.
    $rb = JP $script:Root 'scripts\run_bot.ps1'
    if (-not (TLog "START SERVER $rb")) {
        try {
            Start-Process -FilePath $script:PsExe -WindowStyle Hidden -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', "`"$rb`"") | Out-Null
        } catch {
            Say 'SKIP' "The bot server could not be started again here ($($_.Exception.Message)): step 3 starts it."
            return
        }
    }
    Say '..' 'Starting the bot server again (hidden window; the bot itself stays stopped until step 3)...'
    $until = (Get-Date).AddSeconds($ServerWait)
    while ((Get-Date) -lt $until) {
        if (Port-Open $Port) { Say 'OK' 'The bot server runs again, with the new code (the bot itself is stopped).'; return }
        Start-Sleep -Milliseconds 1000
    }
    Say 'SKIP' 'The bot server has not answered yet: step 3 starts it.'
}

function GitHub-Free {
    # engine\nogithub.py: LE_NO_GITHUB=1 or the file %USERPROFILE%\.olympus\no_github (tools\bat\BOTS_BACK.bat / tools\bat\PUBLISH_NQ.bat make it)
    if ($env:LE_NO_GITHUB) { return ($env:LE_NO_GITHUB -eq '1') }
    $h = $env:OLYMPUS_HOME
    if (-not $h) { $h = J2 (Home-Dir) '.olympus' }
    return (Test-Path -LiteralPath (J2 $h 'no_github'))
}

# ------------------------------------------------------------------------------------------------ auto-update (engine\autoupdate.py)
function Au-Ready {
    # the folder's code can do it: engine\autoupdate.py knows --source-status and update_source.json names the backup repo
    $au = JP $script:Root 'engine\autoupdate.py'
    if (-not (Test-Path -LiteralPath $au) -or -not (Test-Path -LiteralPath (JP $script:Root 'update_source.json'))) { return $false }
    try { return [bool](Select-String -LiteralPath $au -SimpleMatch -Pattern 'source-status' -Quiet) } catch { return $false }
}
function Au-On {
    # the folder already updates itself from the backup: its own --source-status (read only, no network) exits 0
    if (-not (Au-Ready)) { return $false }
    Set-Location -LiteralPath $script:Root
    $null = @(& $script:Py -X utf8 -m engine.autoupdate --source-status 2>&1)
    return ($LASTEXITCODE -eq 0)
}
function Au-Account {
    # update_source.json "account": the GitHub account the private backup repo lives on (the one to sign in as)
    try {
        $j = Get-Content -LiteralPath (JP $script:Root 'update_source.json') -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $a = ([string](P $j 'account')).Trim()
        if ($a -match '^[A-Za-z0-9][A-Za-z0-9._@+-]{0,79}$') { return $a }
    } catch { }
    return ''
}
# ------------------------------------------------------------------------------------------------ the dashboard site (step 1c)
function Netlify-Saved {
    # %USERPROFILE%\.olympus\netlify.json (tools\pc_publish.py --setup netlify) holds a key and a site id (the key is never shown)
    $h = $env:OLYMPUS_HOME
    if (-not $h) { $h = J2 (Home-Dir) '.olympus' }
    try {
        $j = Get-Content -LiteralPath (J2 $h 'netlify.json') -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $t = ([string](P $j 'token')).Trim()
        $i = ([string](P $j 'site_id')).Trim()
        return ($t.Length -gt 0 -and $i.Length -gt 0)
    } catch { return $false }
}
function Site-Ready {
    # this code can do it: tools\pc_publish.py knows --site-name and scripts\publish_nq.ps1 (the tools\bat\PUBLISH_NQ.bat task) is there
    $pp = JP $script:Root 'tools\pc_publish.py'
    if (-not (Test-Path -LiteralPath $pp) -or -not (Test-Path -LiteralPath (JP $script:Root 'scripts\publish_nq.ps1'))) { return $false }
    try { return [bool](Select-String -LiteralPath $pp -SimpleMatch -Pattern 'site-name' -Quiet) } catch { return $false }
}
function Hand-Over([string]$Why) {
    # the rest always runs on the bot folder's own copy of this script: when it differs from this one (an update or the connect
    # brought a newer one, or the folder already had another), it goes on and this copy stops here. A server this window stopped
    # is started first (the other copy does not know it was stopped).
    $new = JP $script:Root 'scripts\setup_everything.ps1'
    if (-not (Test-Path -LiteralPath $new) -or (File-Sha $new) -eq $SelfSha) { return }
    if ($script:ServerDown) { Start-Server; $script:ServerDown = $false }
    Say 'OK' $Why
    $na = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $new, '-Step1', $script:S1, '-BotDir', $script:Root, '-Port', "$Port", '-Python', $script:Py,
            '-ServerWait', "$ServerWait", '-ArmWait', "$ArmWait")
    if ($Tailscale) { $na += @('-Tailscale', $Tailscale) }
    & $script:PsExe @na
    exit $LASTEXITCODE
}

# ------------------------------------------------------------------------------------------------ the phone link (read only checks)
function Find-Tailscale {
    if ($Tailscale) { if (Test-Path -LiteralPath $Tailscale) { return $Tailscale }; return $null }
    if ($env:LE_TAILSCALE) { if (Test-Path -LiteralPath $env:LE_TAILSCALE) { return $env:LE_TAILSCALE }; return $null }
    $cm = Get-Command tailscale -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cm) { return $cm.Source }
    foreach ($d in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ($d) { $q = J2 (J2 $d 'Tailscale') 'tailscale.exe'; if (Test-Path -LiteralPath $q) { return $q } }
    }
    return $null
}
function TS-Json([string]$Ts, [string[]]$ArgList) {
    try {
        $raw = (& $Ts @ArgList 2>$null | Out-String)
        if (-not $raw.Trim()) { return $null }
        return ($raw | ConvertFrom-Json -ErrorAction Stop)
    } catch { return $null }
}
function Our-Proxy([string]$P1) {
    $t = $P1.TrimEnd('/')
    return ($t -eq "http://127.0.0.1:$Port" -or $t -eq "http://localhost:$Port" -or $t -eq "127.0.0.1:$Port" -or $t -eq "localhost:$Port" -or $t -eq "$Port")
}
function Link-IfOn {
    # the https link when it is already on: Tailscale signed in and connected, "tailscale serve" points https://<pc>/ at the bot
    # server, no Funnel (the internet) on it, and a task keeps the site fresh (scripts\live_link.ps1 step 5)
    $ts = Find-Tailscale
    if (-not $ts) { return $null }
    $st = TS-Json $ts @('status', '--json')
    if ([string](P $st 'BackendState') -ne 'Running') { return $null }
    $dns = ([string](P (P $st 'Self') 'DNSName')).TrimEnd('.')
    if (-not $dns) { return $null }
    $sc = TS-Json $ts @('serve', 'status', '--json')
    $px = [string](P (P (P (P (P $sc 'Web') ("{0}:443" -f $dns)) 'Handlers') '/') 'Proxy')
    if (-not $px -or -not (Our-Proxy $px)) { return $null }
    if ([bool](P (P $sc 'AllowFunnel') ("{0}:443" -f $dns))) { return $null }
    if (-not ((Task-Exists 'OlympusPublishNQ') -or (Task-Exists 'OlympusLiveSite'))) { return $null }
    return "https://$dns/"
}
function Link-Saved {
    # the link scripts\live_link.ps1 saved (%USERPROFILE%\.olympus\live_link.json), else the one Tailscale says
    $h = $env:OLYMPUS_HOME
    if (-not $h) { $h = J2 (Home-Dir) '.olympus' }
    try {
        $j = Get-Content -LiteralPath (J2 $h 'live_link.json') -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $u = [string](P $j 'url')
        if ($u -match '^https://[^\s"]+$') { return $u }
    } catch { }
    $ts = Find-Tailscale
    if ($ts) {
        $dns = ([string](P (P (TS-Json $ts @('status', '--json')) 'Self') 'DNSName')).TrimEnd('.')
        if ($dns) { return "https://$dns/" }
    }
    return $null
}
function Show-Child([string]$T) {
    # live_link.ps1's lines, in THIS window's words (Enter here tries again; no other file to open)
    if ($script:HideRest) { return }
    if ($T -match 'YOUR LIVE DASHBOARD') { $script:HideRest = $true; return }   # its own card: the big box below replaces it
    $t = $T -replace 'double-click LIVE_LINK\.bat again', 'press Enter in this window to try again'
    $t = $t -replace 'run this again', 'press Enter in this window to try again'
    $t = $t -replace 'BOTS_BACK\.bat starts it', 'Step 3 below starts it'
    $t = $t -replace 'take a photo of this window and send it to Claude', 'send a photo of this window to Claude'
    $c = 'Gray'
    if ($t -match '\[OK\]') { $c = 'Green' } elseif ($t -match '\[FIX\]') { $c = 'Red' } elseif ($t -match '\[SKIP\]') { $c = 'Yellow' }
    Write-Host $t -ForegroundColor $c
}
function Run-LiveLink([string]$Ll) {
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Ll)
    if ($Port -ne 8766) { $a += @('-Port', "$Port") }
    if ($script:Py) { $a += @('-Python', $script:Py) }
    if ($Tailscale) { $a += @('-Tailscale', $Tailscale) }
    $script:HideRest = $false
    & $script:PsExe @a 2>&1 | ForEach-Object { Show-Child ([string]$_) }
    return $LASTEXITCODE
}
function Show-Link([string]$Url) {
    $w = [Math]::Max(60, $Url.Length + 12)
    Write-Host ''
    Write-Host ('  ' + ('#' * ($w + 4))) -ForegroundColor Green
    Write-Host ('  ##' + (' ' * $w) + '##') -ForegroundColor Green
    Write-Host ('  ##' + ('  YOUR PHONE DASHBOARD LINK (it is on the clipboard too):').PadRight($w) + '##') -ForegroundColor Green
    Write-Host ('  ##' + (' ' * $w) + '##') -ForegroundColor Green
    Write-Host '  ##' -ForegroundColor Green -NoNewline
    Write-Host ('      ' + $Url).PadRight($w) -ForegroundColor Black -BackgroundColor Green -NoNewline
    Write-Host '##' -ForegroundColor Green
    Write-Host ('  ##' + (' ' * $w) + '##') -ForegroundColor Green
    Write-Host ('  ' + ('#' * ($w + 4))) -ForegroundColor Green
    Write-Host ''
    Write-Host '  On the iPhone:  1. App Store: install Tailscale (free), sign in with the SAME account, allow the VPN.'
    Write-Host '                  2. Safari: open the link above.   3. Share > Add to Home Screen.'
    Write-Host '  Only your own devices signed in to Tailscale can open it. Read only: nothing there can trade.'
    if (-not (TLog "CLIP $Url")) { try { Set-Clipboard -Value $Url } catch { } }
}

# ------------------------------------------------------------------------------------------------ summary and exit
$script:S1 = 'not checked'
$script:S1b = 'not checked'
$script:S1c = 'not checked'
$script:S2 = 'not checked'
$script:S3 = 'not checked'
$script:ServerDown = $false          # step 1 stopped the bot server: started again after step 1b (one stop for both)
$script:MarketOk = $false            # you said Y to changing code while the market is open (step 1): step 1b does not ask again
function Summary {
    Write-Host ''
    Write-Host ('  ' + ('=' * 26) + ' SUMMARY ' + ('=' * 26)) -ForegroundColor Cyan
    Write-Host ("   1  New code      {0}" -f $script:S1)
    Write-Host ("   1b Auto-update   {0}" -f $script:S1b)
    Write-Host ("   1c Dashboard     {0}" -f $script:S1c)
    Write-Host ("   2  Phone link    {0}" -f $script:S2)
    Write-Host ("   3  Go live       {0}" -f $script:S3)
    Write-Host ''
}
function Done([int]$Code) { Summary; exit $Code }

# ================================================================================================ start
$script:PsExe = $null
try { $script:PsExe = (Get-Process -Id $PID).Path } catch { }
if (-not $script:PsExe) { $script:PsExe = 'powershell.exe' }
if ($Port -le 0) { if ($env:PORT) { $Port = [int]$env:PORT } else { $Port = 8766 } }
$TempDir = $env:TEMP
if (-not $TempDir) { $TempDir = [System.IO.Path]::GetTempPath() }
$SelfSha = File-Sha $PSCommandPath
$env:PYTHONIOENCODING = 'utf-8'
$nowArgs = @()
if ($env:LE_SE_T_NOW) { $nowArgs = @('--now', $env:LE_SE_T_NOW) }

if (-not $Step1) {
    Write-Host ''
    Write-Host ('  ' + ('#' * 72)) -ForegroundColor Cyan
    Band '     OLYMPUS: SETUP EVERYTHING  -  one window, three steps, in order'
    Write-Host ('  ' + ('#' * 72)) -ForegroundColor Cyan
    Write-Host '   1  New code from the zip'
    Write-Host '   1b Auto-update: from then on the PC gets new code by itself (a GitHub sign-in the first time)'
    Write-Host '   1c Your dashboard site updates itself (paste a Netlify key once, or press Enter to skip)'
    Write-Host '   2  Your phone dashboard (private link)'
    Write-Host '   3  Go live on the evals (Sunday after 6 PM New York time: you type YES, then the live phrase yourself)'
    Write-Host '   A step that is already done is skipped. Safe to double-click again any time.'
}
Write-Host ''

$script:Root = Find-BotFolder
if (-not $script:Root) {
    Fix 'The bot folder was not found on this PC' 'Copy SETUP_EVERYTHING.bat out of the zip into the bot folder (the folder with START_BOT.bat in it) and double-click it there'
    Done 1
}
$Root = $script:Root
Set-Location -LiteralPath $Root
try { [Environment]::CurrentDirectory = $Root } catch { }
Write-Host "   Bot folder:  $Root"
Write-Host ("   New York:    {0}" -f (Et-Words (Et-Now)))
$script:Py = Find-Python
if (-not $script:Py) {
    Fix 'Python was not found on this PC' 'Double-click tools\bat\ONE_TIME_SETUP.bat in the bot folder once, then double-click SETUP_EVERYTHING.bat again'
    Done 1
}
$py = $script:Py

# ================================================================================================ 1 new code
Header 'STEP 1 of 3' 'New code from the zip'
$updated = $false
if ($Step1) {
    Say 'OK' ("Step 1 (above): {0}." -f $Step1)
    $script:S1 = $Step1
} else {
    # a folder the auto-update already runs (--source-status 0) never takes a zip again: it would make the code differ from the
    # backup and stop every auto-update (UPDATE.bat takes the newest code from the backup)
    $selfUpdating = Au-On
    $zipPath = $null
    if (-not $selfUpdating) { $zipPath = Find-Zip }
    if ($selfUpdating) {
        Say 'OK' 'This PC updates itself from the backup; no zip needed.'
        $script:S1 = 'skipped: this PC updates itself from the backup (no zip needed)'
    } elseif (-not $zipPath) {
        if ($Zip) {
            Fix "The zip $Zip was not found" 'Drag the code zip from Downloads onto SETUP_EVERYTHING.bat, or just double-click SETUP_EVERYTHING.bat'
            Done 1
        }
        if ((Test-Path -LiteralPath (JP $Root 'scripts\setup_everything.ps1')) -and (Test-Path -LiteralPath (JP $Root 'tools\update_from_zip.py'))) {
            Say 'SKIP' 'No code zip (OLYMPUS_BACKUP_...zip) in Downloads or on the Desktop: the code already on this PC is used.'
            $script:S1 = 'skipped: no new zip in Downloads (the code on this PC is used)'
        } else {
            Fix 'No code zip (OLYMPUS_BACKUP_...zip) was found in Downloads or on the Desktop' 'Download the zip and its .sha256.txt into Downloads, then double-click SETUP_EVERYTHING.bat again'
            $script:S1 = 'NOT done: no code zip found'
            Done 1
        }
    } else {
        Write-Host "   Code zip:    $zipPath"
        $shaFile = Sha-File $zipPath
        if ($shaFile) { Say 'OK' ("its checksum file is next to it ({0})" -f (Split-Path -Leaf $shaFile)) }
        else { Say 'SKIP' 'no .sha256.txt next to the zip: the zip''s own checksums are checked instead' }
        $tool = J2 (J2 $TempDir 'le_setup_everything') 'update_from_zip.py'
        $ex = Zip-Extract $zipPath 'tools/update_from_zip.py' $tool
        if ($ex -eq 'bad') {
            Fix 'The code zip does not open (the download is damaged)' 'Download the zip and its .sha256.txt again into Downloads, then double-click SETUP_EVERYTHING.bat again'
            $script:S1 = 'NOT done: the zip is damaged'
            Done 1
        }
        if ($ex -eq 'missing') {
            Fix 'This zip is not the bot''s code zip, or it is too old (no tools\update_from_zip.py in it)' 'Download the newest OLYMPUS_BACKUP zip and its .sha256.txt into Downloads, then double-click SETUP_EVERYTHING.bat again'
            $script:S1 = 'NOT done: not the right zip'
            Done 1
        }
        Say '..' 'checking the zip against the bot folder (a big zip can take a minute)...'
        & $py -I -X utf8 $tool $zipPath --folder $Root --check
        $rc = $LASTEXITCODE
        if ($rc -eq 0) {
            Say 'OK' 'Already done: the bot folder already has the code of this zip.'
            $script:S1 = 'already done'
        } elseif ($rc -eq 13) {
            Say 'OK' 'Skipped: this zip is older than the code already on this PC.'
            $script:S1 = 'skipped: the zip is older than the code on this PC'
        } elseif ($rc -ne 10) {
            if ($rc -eq 3) { Fix 'The code zip did not pass its check (the line above says why; nothing was changed)' 'Download the zip and its .sha256.txt again into Downloads, then double-click SETUP_EVERYTHING.bat again' }
            else { Fix "The zip check stopped (code $rc; the line above says why; nothing was changed)" 'Do what that line says, then double-click SETUP_EVERYTHING.bat again' }
            $script:S1 = 'NOT done: the zip check failed'
            Done 1
        } else {
            # an update is due: the bot server must be stopped for it (UPDATE_FROM_ZIP refuses while it answers), and while the market
            # is open only with a Y. Both are asked BEFORE anything is stopped (one question), so a "no" leaves the bot as it was.
            $stopped = $false
            $mOpen = Market-Open (Et-Now)
            $okMarket = $false
            if (Port-Open $Port) {
                $ls = Launch-State
                if ($ls.open) {
                    Fix 'A bot has an open trade right now, so it is not stopped for the update' 'Wait until the trade is closed (the bot is flat by 15:55 ET), then double-click SETUP_EVERYTHING.bat again'
                    $script:S1 = 'NOT done: a trade is open'
                    Done 1
                }
                Write-Host ''
                Write-Host '   The bot server is running. The new code can only go in while it is stopped.' -ForegroundColor Yellow
                if ($ls.words) { Write-Host "   Now: $($ls.words)" -ForegroundColor Yellow }
                Write-Host '   It is started again right after the update; the bot itself stays stopped until step 3.' -ForegroundColor Yellow
                if ($mOpen) {
                    Write-Host ("   The market is open now ({0} in New York): the bot misses trades until step 3 starts it again." -f (Et-Words (Et-Now))) -ForegroundColor Yellow
                    $a = Ask '   Type Y then Enter to stop the bot and update now anyway (anything else: nothing is changed)'
                } else {
                    $a = Ask '   Type Y then Enter to stop the bot now (anything else: nothing is changed)'
                }
                if ($a.ToUpper() -ne 'Y') {
                    Say 'OK' 'Nothing was changed. Double-click SETUP_EVERYTHING.bat again when you are ready.'
                    $script:S1 = 'NOT done: you kept the bot running'
                    Done 0
                }
                $okMarket = $mOpen
                if (-not (Stop-Bot)) {
                    Fix 'The bot server did not stop' 'Restart the PC, then double-click SETUP_EVERYTHING.bat again'
                    $script:S1 = 'NOT done: the bot did not stop'
                    Done 1
                }
                Say 'OK' 'The bot is stopped.'
                $stopped = $true
            }
            if ($mOpen -and -not $okMarket) {
                $a = Ask '   The market is open now and the bot is stopped. Update anyway? Type Y then Enter'
                if ($a.ToUpper() -ne 'Y') {
                    Say 'OK' 'Nothing was changed. Double-click SETUP_EVERYTHING.bat again after 17:00 ET or at the weekend.'
                    $script:S1 = 'NOT done: the market was open'
                    Done 0
                }
                $okMarket = $true
            }
            $ua = @('-I', '-X', 'utf8', $tool, $zipPath, '--folder', $Root, '--pip', '--port', "$Port", '--next', 'this window goes on with the next step by itself.') + $nowArgs
            if ($okMarket) { $ua += '--allow-market-open' }
            Say '..' 'updating the bot folder (a big zip can take a few minutes; do not close this window)...'
            & $py @ua
            $rc = $LASTEXITCODE
            if ($rc -eq 12) {                               # the updater's own clock says open (a clock edge): ask as UPDATE_FROM_ZIP.bat does
                $a = Ask '   The market is open now and the bot is stopped. Update anyway? Type Y then Enter'
                if ($a.ToUpper() -eq 'Y') {
                    & $py @ua '--allow-market-open'
                    $rc = $LASTEXITCODE
                } else {
                    Say 'OK' 'Nothing was changed. Double-click SETUP_EVERYTHING.bat again after 17:00 ET or at the weekend.'
                    if ($stopped) { Start-Server }
                    $script:S1 = 'NOT done: the market was open'
                    Done 0
                }
            }
            if ($rc -ne 0) {
                Fix 'The update did not go through (the lines above say why)' 'Do what the [FIX] or [STOP] line above says, then double-click SETUP_EVERYTHING.bat again'
                if ($stopped) { Start-Server }
                $script:S1 = 'NOT done: the update failed'
                Done 1
            }
            $script:S1 = 'done: the new code is in'
            $updated = $true
            $script:ServerDown = $stopped              # started again after step 1b (one stop for both), or before a hand-over
            $script:MarketOk = $okMarket
        }
    }
    # the rest always runs on the bot folder's own copy of this script (the update just brought a newer one, or the folder
    # already had a newer one than the zip): it goes on from step 1b and this copy stops here
    if ($updated) { Hand-Over 'The update brought a newer version of this window: it goes on from here.' }
    else { Hand-Over 'The bot folder has its own copy of this window: it goes on from here.' }
}

# ================================================================================================ 1b auto-update
Header 'STEP 1b of 3' 'Auto-update: new code by itself from now on'
$acct = Au-Account
$signIn = "sign in as $acct"
if (-not $acct) { $signIn = 'sign in with the backup repo''s GitHub account' }
$auStopped = $false
$connected = $false
Set-Location -LiteralPath $Root
if (-not (Au-Ready)) {
    Say 'SKIP' 'This code has no auto-update yet (a newer code zip brings it). The zip way still works.'
    $script:S1b = 'skipped: this code has no auto-update yet'
} else {
    $probe = @(& $py -X utf8 -m engine.autoupdate --source-status 2>&1 | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
    $prc = $LASTEXITCODE
    $pline = ''
    if ($probe.Count) { $pline = ($probe[-1] -replace '^\[[A-Za-z.]+\]\s*', '') }
    if ($prc -eq 0) {
        Say 'OK' 'Already on: the PC updates itself (only when no trade is open, never during trading hours).'
        $script:S1b = 'already on: the PC updates itself'
    } elseif ($prc -ne 10) {
        if (-not $pline) { $pline = "the check stopped (code $prc)" }
        if ($pline -notmatch '[.!?]$') { $pline += '.' }
        Say 'SKIP' ("Auto-update not checked: {0} The zip way still works." -f $pline)
        $script:S1b = 'skipped: it could not be checked'
    } else {
        # the connect is due. It needs the bot server stopped (--connect refuses while it answers): never with an open trade, while
        # the market is open only after a Y (as step 1). A server step 1 stopped is still stopped here; started again below, once.
        $go = $true
        $mOpen = Market-Open (Et-Now)
        if (Port-Open $Port) {
            $ls = Launch-State
            if ($ls.open) {
                Say 'SKIP' 'A bot has an open trade right now, so the bot is not stopped: auto-update waits (double-click SETUP_EVERYTHING.bat again when the trade is closed). The zip way still works.'
                $script:S1b = 'not yet: a trade was open'
                $go = $false
            } else {
                Write-Host ''
                Write-Host '   The bot server is running. Auto-update can only be turned on while it is stopped (a minute or two).' -ForegroundColor Yellow
                if ($ls.words) { Write-Host "   Now: $($ls.words)" -ForegroundColor Yellow }
                Write-Host '   It is started again right after; the bot itself stays stopped until step 3.' -ForegroundColor Yellow
                if ($mOpen) {
                    Write-Host ("   The market is open now ({0} in New York): the bot misses trades until step 3 starts it again." -f (Et-Words (Et-Now))) -ForegroundColor Yellow
                    $a = Ask '   Type Y then Enter to stop the bot and turn on auto-update now anyway (anything else: skipped, nothing is changed)'
                } else {
                    $a = Ask '   Type Y then Enter to stop the bot now (anything else: skipped, nothing is changed)'
                }
                if ($a.ToUpper() -ne 'Y') {
                    Say 'SKIP' 'Auto-update is not turned on: you kept the bot running. Double-click SETUP_EVERYTHING.bat again when you are ready. The zip way still works.'
                    $script:S1b = 'not yet: you kept the bot running'
                    $go = $false
                } elseif (-not (Stop-Bot)) {
                    Say 'SKIP' 'The bot server did not stop, so auto-update waits (restart the PC, then double-click SETUP_EVERYTHING.bat again). The zip way still works.'
                    $script:S1b = 'not yet: the bot server did not stop'
                    $go = $false
                } else {
                    Say 'OK' 'The bot is stopped.'
                    $auStopped = $true
                    if ($mOpen) { $script:MarketOk = $true }
                }
            }
        }
        if ($go -and $mOpen -and -not $script:MarketOk) {
            $a = Ask '   The market is open now and the bot is stopped. Turn on auto-update anyway? Type Y then Enter'
            if ($a.ToUpper() -ne 'Y') {
                Say 'SKIP' 'Auto-update is not turned on: the market is open. Double-click SETUP_EVERYTHING.bat again after 17:00 ET or at the weekend. The zip way still works.'
                $script:S1b = 'not yet: the market was open'
                $go = $false
            }
        }
        if ($go) {
            Say '..' "turning on auto-update (the first time a GitHub window may open: $signIn; do not close this window)..."
            Set-Location -LiteralPath $Root
            & $py -X utf8 -m engine.autoupdate --connect --port $Port
            $crc = $LASTEXITCODE
            if ($crc -eq 0) {
                Say 'OK' 'Auto-update is ON: from now on the PC gets new code by itself (only when no trade is open, never during trading hours).'
                $script:S1b = 'ON: the PC gets new code by itself'
                $connected = $true
            } elseif ($crc -eq 20) {
                Say 'SKIP' "Could not reach the backup ($signIn in the window that opens, or check the internet). The zip way still works."
                $script:S1b = 'not on yet: the backup could not be reached (double-click SETUP_EVERYTHING.bat again to try again)'
            } elseif ($crc -eq 21) {
                Say 'SKIP' 'Not now: the bot server is running or a trade is open. Nothing was changed; double-click SETUP_EVERYTHING.bat again later. The zip way still works.'
                $script:S1b = 'not now: the bot server was running or a trade was open'
            } elseif ($crc -eq 22) {
                Say 'SKIP' 'Git is not installed on this PC, so it cannot update itself: install Git for Windows (free, git-scm.com), then double-click SETUP_EVERYTHING.bat again. Nothing was changed; the zip way still works.'
                $script:S1b = 'not on: Git is not installed'
            } elseif ($crc -eq 1) {
                Say 'SKIP' 'Auto-update could not be turned on, so everything was put back as it was (the lines above say why). The zip way still works.'
                $script:S1b = 'not on: it failed and everything was put back'
            } else {
                Say 'SKIP' "Auto-update stopped (code $crc; the lines above say why). The zip way still works."
                $script:S1b = "not on: it stopped (code $crc)"
            }
        }
    }
}
if ($auStopped) { $script:ServerDown = $true }
if ($connected) { Hand-Over 'Auto-update brought a newer version of this window: it goes on from here.' }
if ($script:ServerDown) { Start-Server; $script:ServerDown = $false }

# ================================================================================================ 1c the dashboard site updates itself
# optional: the Netlify key once (ONE hidden prompt), then tools\pc_publish.py --setup netlify --site-name finds the site with it, and
# the tools\bat\PUBLISH_NQ.bat task (scripts\publish_nq.ps1, reused as is) puts the lite, private-free site there by itself. Never a stop.
Header 'STEP 1c of 3' 'Your dashboard site updates itself'
$pubTool = JP $Root 'tools\pc_publish.py'
$pubTask = JP $Root 'scripts\publish_nq.ps1'
if ($env:LE_SE_QUICK -eq '1') {
    # tools\bat\QUICK_ARM.bat (owner 2026-11-15, "make it easier"): no question here; SETUP_EVERYTHING.bat later adds the key
    Say 'SKIP' 'Quick mode: the dashboard key is for later (double-click SETUP_EVERYTHING.bat any evening).'
    $script:S1c = 'skipped: quick mode'
} elseif (-not (Site-Ready)) {
    Say 'SKIP' 'This code cannot set up the dashboard site yet (a newer code zip brings it).'
    $script:S1c = 'skipped: this code cannot do it yet'
} elseif ((Netlify-Saved) -and (Task-Exists 'OlympusPublishNQ')) {
    Say 'OK' 'Already on: this PC puts your dashboard site on Netlify by itself (at most once a day).'
    $script:S1c = 'already on: the dashboard site updates itself'
} else {
    $saved = Netlify-Saved
    if (-not $saved) {
        Write-Host "   Your dashboard site ($NetlifySite.netlify.app) can update itself from this PC: no more zips to upload by hand."
        Write-Host '   The key: app.netlify.com > your picture > User settings > Applications > New access token > Generate > copy.'
        $key = Ask-Secret '   Paste your Netlify key, or press Enter to skip'
        if (-not $key) {
            Say 'SKIP' 'No key pasted: the dashboard site does not update itself yet (double-click SETUP_EVERYTHING.bat again to add the key).'
            $script:S1c = 'skipped: no key pasted'
        } else {
            Set-Location -LiteralPath $Root
            $key | & $py -X utf8 $pubTool --setup netlify --site-name $NetlifySite --token-stdin
            $prc = $LASTEXITCODE
            $key = $null
            if ($prc -eq 0) {
                Say 'OK' "Netlify key saved (outside the bot folder, never shown); your site $NetlifySite was found."
                $saved = $true
            } elseif ($prc -eq 3) {
                Say 'SKIP' 'Netlify refused that key (make a new one as the line above says); nothing was saved. Double-click SETUP_EVERYTHING.bat again to paste it.'
                $script:S1c = 'not on: Netlify refused the key'
            } elseif ($prc -eq 4) {
                Say 'SKIP' "That key's Netlify account has no site called $NetlifySite (make the key while signed in to the account the site is on); nothing was saved."
                $script:S1c = "not on: no site $NetlifySite on that Netlify account"
            } elseif ($prc -eq 5) {
                Say 'SKIP' 'Could not reach Netlify (check the internet); nothing was saved. Double-click SETUP_EVERYTHING.bat again later.'
                $script:S1c = 'not on: Netlify could not be reached'
            } else {
                Say 'SKIP' "The key was not saved (code $prc; the line above says why)."
                $script:S1c = "not on: the key was not saved (code $prc)"
            }
        }
    }
    if ($saved) {
        Write-Host ''
        Write-Host '   ----- the publish task of tools\bat\PUBLISH_NQ.bat: every 15 minutes, at most one Netlify upload a day; the first one now -----' -ForegroundColor Cyan
        & $script:PsExe -NoProfile -ExecutionPolicy Bypass -File $pubTask -Python $py
        if ($LASTEXITCODE -eq 0) {
            Say 'OK' "Your dashboard site updates itself now: $NetlifySite.netlify.app gets this PC's newest numbers (at most once a day)."
            $script:S1c = 'on: the dashboard site updates itself'
        } else {
            Say 'SKIP' 'The publish task was not set up (the lines above say why): double-click tools\bat\PUBLISH_NQ.bat once, or SETUP_EVERYTHING.bat again.'
            $script:S1c = 'not on yet: the publish task was not set up'
        }
    }
}

# ================================================================================================ 2 the phone link
Header 'STEP 2 of 3' 'Your phone dashboard (private link)'
$url = Link-IfOn
if ($env:LE_SE_QUICK -eq '1' -and -not $url) {
    Say 'SKIP' 'Quick mode: the phone link is for later (double-click SETUP_EVERYTHING.bat any evening).'
    $script:S2 = 'skipped: quick mode'
} elseif ($url) {
    Say 'OK' 'Already done: the private link is on (only your own devices can open it).'
    $script:S2 = "already on: $url"
} else {
    $ll = JP $Root 'scripts\live_link.ps1'
    if (-not (Test-Path -LiteralPath $ll)) {
        Fix 'This bot folder has no scripts\live_link.ps1 (old code)' 'Download the newest code zip into Downloads, then double-click SETUP_EVERYTHING.bat again'
        $script:S2 = 'NOT done: old code'
    } else {
        $tries = 0
        while ($true) {
            $tries++
            $rc = Run-LiveLink $ll
            if ($rc -eq 0) {
                $url = Link-Saved
                break
            }
            if ($tries -ge 5) {
                Fix 'The phone link is still not on after 5 tries' 'Restart the PC, then double-click SETUP_EVERYTHING.bat again (steps that are done are skipped)'
                break
            }
            Fix 'The phone link is not on yet (the red line above says why)' 'Do what it says, then press Enter here to try again, or type LATER to do it another time'
            $a = Ask '   Press Enter to try again, or type LATER'
            if ($a.ToUpper() -eq 'LATER') { break }
        }
        if ($url) { $script:S2 = "on: $url" }
        else { $script:S2 = 'NOT done yet: double-click SETUP_EVERYTHING.bat again to finish it' }
    }
}
if ($url) {
    Show-Link $url
    if (-not (Port-Open $Port)) { Say 'SKIP' 'The link opens the dashboard once the bot server runs: step 3 starts it.' }
}

# ================================================================================================ 3 go live
Header 'STEP 3 of 3' 'Go live on the evals (Sunday after 6 PM New York time)'
$ls = Launch-State
if ($ls.both) {
    Say 'OK' 'Already done: Zlarior (50K) and ATLAS (25K) run live and armed.'
    $script:S3 = 'already done: both live and armed'
    Done 0
}
$bb = JP $Root 'scripts\bots_back.ps1'
if (-not (Test-Path -LiteralPath $bb) -or -not (Test-Path -LiteralPath (JP $Root 'engine\go.py'))) {
    Fix 'This bot folder has old code (no scripts\bots_back.ps1)' 'Download the newest code zip into Downloads, then double-click SETUP_EVERYTHING.bat again'
    $script:S3 = 'NOT done: old code'
    Done 1
}
Write-Host ("   Now in New York: {0}" -f (Et-Words (Et-Now)))
if ($ls.words) { Write-Host "   The bot now: $($ls.words)" }
Write-Host '   Before you type YES: open the MFFU dashboard and check that BOTH evals (the 50K and the 25K) show as active.'
if ($ls.running) { Write-Host '   The bot runs right now without both evals armed: after YES it is stopped and started again for the evals.' }
if (Weekend-Closed (Et-Now)) {
    Write-Host '   It is not Sunday 6 PM New York time yet: type YES after that (leave this window open), or double-click SETUP_EVERYTHING.bat again then.' -ForegroundColor Yellow
}
while ($true) {
    Write-Host ''
    Write-Host '   Is it Sunday after 6 PM ET and are both evals active on MFFU? Type YES' -ForegroundColor Yellow
    $a = Ask '   Type YES then Enter (anything else stops here, nothing is armed)'
    if ($a.ToUpper() -ne 'YES') {
        Say 'OK' 'Stopped here. Nothing is armed. On Sunday after 6 PM ET double-click SETUP_EVERYTHING.bat again: the steps that are done are skipped.'
        $script:S3 = 'not yet: on Sunday after 6 PM ET double-click SETUP_EVERYTHING.bat again'
        Done 0
    }
    $E = Et-Now
    if (Weekend-Closed $E) {
        Say 'WAIT' ("Not yet: it is {0} in New York; the market opens Sunday 6:00 PM New York time. Leave this window open and type YES after that." -f (Et-Words $E))
        continue
    }
    break
}
$ls = Launch-State
if ($ls.both) {
    Say 'OK' 'Already done in the meantime: Zlarior (50K) and ATLAS (25K) run live and armed.'
    $script:S3 = 'already done: both live and armed'
    Done 0
}
if ($ls.open) {
    Fix 'A bot has an open trade right now, so nothing is restarted' 'Wait until the trade is closed, then double-click SETUP_EVERYTHING.bat again'
    $script:S3 = 'NOT done: a trade is open'
    Done 1
}
$fresh = -not (GitHub-Free)
if ($ls.up -and ($ls.running -or $fresh)) {
    # a bot that runs unarmed would make START BOT say "already running"; a server started before GitHub-free mode keeps trying
    # GitHub: both are stopped here, part 1 starts the server again (GitHub-free) and START BOT starts the bot on the evals
    if ($ls.running) { Say '..' 'Stopping the bot that runs without both evals armed (it starts again for the evals)...' }
    else { Say '..' 'Restarting the bot server so it comes back in GitHub-free mode (part 1 below starts it again)...' }
    if (-not (Stop-Bot)) {
        Fix 'The bot did not stop' 'Restart the PC, then double-click SETUP_EVERYTHING.bat again'
        $script:S3 = 'NOT done: the bot did not stop'
        Done 1
    }
}
Write-Host ''
Write-Host '   ----- part 1 of 2: bots back (GitHub off, NinjaTrader, the bot server, phone alerts) -----' -ForegroundColor Cyan
& $script:PsExe -NoProfile -ExecutionPolicy Bypass -File $bb -NoResume -Python $py
if ($LASTEXITCODE -ne 0) {
    Fix 'Part 1 stopped (the red line above says why). Nothing is armed' 'Do what it says, then double-click SETUP_EVERYTHING.bat again'
    $script:S3 = 'NOT done: part 1 stopped'
    Done 1
}
Write-Host ''
Write-Host '   ----- part 2 of 2: START BOT. YOU type the live phrase yourself when it asks. -----' -ForegroundColor Cyan
Set-Location -LiteralPath $Root
& $py -X utf8 -m engine.go
$rcg = $LASTEXITCODE
$ls = Launch-State
if ($rcg -eq 0 -and -not $ls.both) {
    $until = (Get-Date).AddSeconds($ArmWait)           # the Launch card reads the bot's numbers every 15 s
    while (-not $ls.both -and (Get-Date) -lt $until) { Start-Sleep -Seconds 5; $ls = Launch-State }
}
if ($ls.both) {
    Say 'OK' 'Zlarior (50K) and ATLAS (25K) run live and armed. Leave the PC on and NinjaTrader open; entries start 02:00 ET.'
    $script:S3 = 'done: both live and armed (you typed the phrase)'
    Done 0
}
if ($rcg -eq 0) {
    Say 'SKIP' 'START BOT finished, but the bot does not report both evals armed yet: look at the Launch card on the phone in a few minutes.'
    $script:S3 = 'started: check the Launch card'
    Done 0
}
Fix 'The evals are not armed (the lines above say why)' 'Fix what they say, then double-click SETUP_EVERYTHING.bat again: the steps that are done are skipped'
$script:S3 = 'NOT done: not armed'
Done 1
