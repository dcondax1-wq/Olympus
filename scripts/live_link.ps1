<#
LIVE LINK (double-click LIVE_LINK.bat). Owner 2026-11-12: "I want everything connected. I want an actual dashboard." The real,
always-current dashboard on the iPhone, free: the PC's own bot server (http://127.0.0.1:8766) reached privately through
Tailscale (free personal plan). docs\LIVE_DASHBOARD.md.

  1 APP      Tailscale for Windows installed (when it is not: its download page opens, then run this again)
  2 SIGN IN  signed in and connected (when not: "tailscale up" in the background, the sign-in page opens in the browser, this
             window waits up to 5 minutes)
  3 LINK     "tailscale serve --bg --yes http://127.0.0.1:8766": https://<this-pc>.<tailnet>.ts.net/ inside YOUR tailnet only
             (your own signed-in devices). Never Funnel: a Funnel on that address is switched off (serve does that), and the bot
             server refuses any Funnel request anyway. HTTPS certificates off in the tailnet: the admin page opens (one click).
  4 SERVER   the bot server answers and serves the phone site (/site/, engine\live_site.py). Read-only over the link: the
             server refuses every POST that comes through it (start, stop, arm, settings stay on the PC).
  5 SITE     the site rebuilt every 15 minutes: PUBLISH_NQ's task OlympusPublishNQ when it is there, else the build-only task
             OlympusLiveSite (tools\pc_publish.py --work data\live_site --provider none: builds, sends nothing anywhere)
  then the link to open on the iPhone (also on the clipboard and in %USERPROFILE%\.olympus\live_link.json)

  -KalshiUrl https://...   also show the Kalshi bot's feed from that address (publish.json "kalshi_feed_url", outside the repo)
  -DryRun    say what it would do, change nothing          -Remove   undo 3 and 5 (UNDO_LIVE_LINK.bat); Tailscale stays installed
It never starts, stops, arms or routes a bot, never places an order, never touches live_model*.json, engine\ or NinjaTrader.
Tests: tests\test_live_link.py (pwsh with a fake tailscale; LE_LL_T_LOG / LE_LL_T_PING / LE_LL_T_TASKS stand in for Windows-only steps).
#>
param(
    [switch]$DryRun,
    [switch]$Remove,
    [string]$Python = "",
    [string]$Tailscale = "",
    [string]$KalshiUrl = "",
    [int]$Port = 0,
    [int]$LoginWait = 300,
    [int]$PollMs = 2000
)

$ErrorActionPreference = 'Continue'
trap {
    Write-Host ''
    Write-Host '  [FIX] Something unexpected stopped this: take a photo of this window and send it to Claude.' -ForegroundColor Red
    exit 1
}
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
function J2([string]$A, [string]$B) { return [System.IO.Path]::Combine($A, $B) }
function Line([string]$Kind, [string]$Text) {
    $c = 'Gray'; if ($Kind -eq 'OK') { $c = 'Green' } elseif ($Kind -eq 'FIX') { $c = 'Red' } elseif ($Kind -eq 'SKIP') { $c = 'Yellow' }
    Write-Host ("  [{0}] {1}" -f $Kind, $Text) -ForegroundColor $c
}
function TLog([string]$What) {
    # tests: a Windows-only step is written to LE_LL_T_LOG instead of being done
    if ($env:LE_LL_T_LOG) { Add-Content -LiteralPath $env:LE_LL_T_LOG -Value $What; return $true }
    return $false
}
function P($Obj, [string]$Name) {
    if ($null -eq $Obj) { return $null }
    $p = $Obj.PSObject.Properties[$Name]; if ($p) { return $p.Value }; return $null
}
function Open-Url([string]$Url) {
    if (TLog "OPEN $Url") { return }
    try { Start-Process $Url } catch { }
}
function OnWindows { return ($env:OS -eq 'Windows_NT') }

if ($Port -le 0) { if ($env:PORT) { $Port = [int]$env:PORT } else { $Port = 8766 } }
$Target = "http://127.0.0.1:$Port"
$Home1 = $env:OLYMPUS_HOME
if (-not $Home1) {
    $up = $env:USERPROFILE; if (-not $up) { $up = $HOME }
    $Home1 = J2 $up '.olympus'
}
$LinkFile = J2 $Home1 'live_link.json'
$PubFile = J2 $Home1 'publish.json'
$TaskName = 'OlympusLiveSite'
$PublishTask = 'OlympusPublishNQ'
$Publisher = J2 (J2 $Root 'tools') 'pc_publish.py'
$DownloadUrl = 'https://tailscale.com/download/windows'
$DnsAdmin = 'https://login.tailscale.com/admin/dns'

function Find-Tailscale {
    if ($Tailscale) { if (Test-Path -LiteralPath $Tailscale) { return $Tailscale }; return $null }
    if ($env:LE_TAILSCALE) { if (Test-Path -LiteralPath $env:LE_TAILSCALE) { return $env:LE_TAILSCALE }; return $null }
    $c = Get-Command tailscale -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { return $c.Source }
    foreach ($d in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ($d) { $p = J2 (J2 $d 'Tailscale') 'tailscale.exe'; if (Test-Path -LiteralPath $p) { return $p } }
    }
    return $null
}
function TS-Json([string[]]$ArgList) {
    try {
        $raw = (& $script:Ts @ArgList 2>$null | Out-String)
        if (-not $raw.Trim()) { return $null }
        return ($raw | ConvertFrom-Json -ErrorAction Stop)
    } catch { return $null }
}
function Dns-Of($St) {
    $d = [string](P (P $St 'Self') 'DNSName')
    return $d.TrimEnd('.')
}
function Serve-Proxy($Sc, [string]$Dns) {
    # the proxy target of https://<dns>/ in the serve config ("" when none)
    $web = P (P $Sc 'Web') ("{0}:443" -f $Dns)
    return [string](P (P (P $web 'Handlers') '/') 'Proxy')
}
function Funnel-On($Sc, [string]$Dns) {
    return [bool](P (P $Sc 'AllowFunnel') ("{0}:443" -f $Dns))
}
function Our-Proxy([string]$P1) {
    $t = $P1.TrimEnd('/')
    return ($t -eq $Target -or $t -eq "http://localhost:$Port" -or $t -eq "127.0.0.1:$Port" -or $t -eq "localhost:$Port" -or $t -eq "$Port")
}
function Find-Python {
    if ($Python) { return $Python }
    if ($env:LE_PYTHON) { return $env:LE_PYTHON }
    $cmd = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { return $cmd.Source }
    return $null
}
function Task-Exists([string]$Name) {
    if ($null -ne $env:LE_LL_T_TASKS) { return (@($env:LE_LL_T_TASKS -split ',') -contains $Name) }
    try { return [bool](Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) } catch { return $false }
}
function Get-Url([string]$Url) {
    # (status, body) of a local GET; tests: LE_LL_T_PING = 1 (answers, new code) | old (answers, no /site) | 0 (down)
    if ($env:LE_LL_T_PING) {
        if ($env:LE_LL_T_PING -eq '0') { return @(0, '') }
        if ($Url -like '*/api/site/status' -and $env:LE_LL_T_PING -eq 'old') { return @(404, '') }
        return @(200, '{"ok": true}')
    }
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        return @([int]$r.StatusCode, [string]$r.Content)
    } catch {
        $code = 0
        try { $code = [int]$_.Exception.Response.StatusCode } catch { }
        return @($code, '')
    }
}
function Write-Utf8([string]$Path, [string]$Text) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding $false))
}

Write-Host ''
Write-Host '  LIVE LINK - your live dashboard on the iPhone (private, free)' -ForegroundColor Cyan
Write-Host ''

if ($KalshiUrl -and -not ($KalshiUrl -match '^https://[^\s"]+$')) {
    Line 'FIX' 'The Kalshi feed address must start with https:// - nothing was changed.'
    exit 1
}

# ------------------------------------------------------------------------------------------------ dry run
if ($DryRun) {
    Write-Host '  DRY RUN - nothing changed. Would:'
    if ($Remove) {
        Write-Host "    1 turn the private link off: tailscale serve --https=443 off (only when it points at $Target)"
        Write-Host "    2 remove the task $TaskName and $LinkFile (Tailscale itself stays installed and signed in)"
        exit 0
    }
    Write-Host "    1 check Tailscale is installed (else open $DownloadUrl)"
    Write-Host '    2 check it is signed in and connected (else tailscale up + the sign-in page)'
    Write-Host "    3 tailscale serve --bg --yes $Target   (tailnet only, never Funnel)"
    Write-Host "    4 check the bot server answers at $Target and serves /site/"
    Write-Host "    5 a fresh site every 15 min: $PublishTask if present, else the build-only task $TaskName"
    if ($KalshiUrl) { Write-Host "    + Kalshi feed address -> $PubFile (kalshi_feed_url)" }
    Write-Host "    then print the link, put it on the clipboard and in $LinkFile"
    exit 0
}

$script:Ts = Find-Tailscale

# ------------------------------------------------------------------------------------------------ undo
if ($Remove) {
    Write-Host '  UNDO: the private link and its site task (Tailscale stays installed and signed in)'
    if ($script:Ts) {
        $st = TS-Json @('status', '--json')
        $dns = Dns-Of $st
        $sc = TS-Json @('serve', 'status', '--json')
        $px = Serve-Proxy $sc $dns
        if ($dns -and $px -and (Our-Proxy $px)) {
            & $script:Ts serve --https=443 off | Out-Host
            Line 'OK' "private link https://$dns/ turned off"
        } elseif ($px) {
            Line 'SKIP' "https://$dns/ points at $px (not the bot server): left as it was"
        } else {
            Line 'OK' 'no private link was on'
        }
    } else {
        Line 'OK' 'Tailscale is not installed: no link to turn off'
    }
    if (Task-Exists $TaskName) {
        if (-not (TLog "TASK REMOVE $TaskName")) { try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch { } }
        Line 'OK' "task $TaskName removed"
    } else {
        Line 'OK' "no task $TaskName"
    }
    if (Test-Path -LiteralPath $LinkFile) { Remove-Item -LiteralPath $LinkFile -Force -ErrorAction SilentlyContinue }
    Line 'OK' 'done. The bots were not touched.'
    exit 0
}

# ------------------------------------------------------------------------------------------------ 1 the app
Write-Host '  1/5 Tailscale app'
if (-not $script:Ts) {
    Line 'FIX' 'Tailscale is not installed. Its download page opens now: install it (free), sign in,'
    Line 'FIX' 'then double-click LIVE_LINK.bat again. Nothing else was changed.'
    Open-Url $DownloadUrl
    exit 1
}
Line 'OK' "installed ($script:Ts)"

# ------------------------------------------------------------------------------------------------ 2 signed in
Write-Host '  2/5 signed in'
$st = TS-Json @('status', '--json')
$state = [string](P $st 'BackendState')
if ($state -ne 'Running') {
    if ($state) { Line 'SKIP' "Tailscale says $state : connecting (a sign-in page opens in your browser if it needs you)" }
    else { Line 'SKIP' 'Tailscale does not answer yet: starting it (a sign-in page opens in your browser if it needs you)' }
    $proc = $null
    try {
        if (OnWindows) { $proc = Start-Process -FilePath $script:Ts -ArgumentList 'up' -PassThru -WindowStyle Hidden }
        else { $proc = Start-Process -FilePath $script:Ts -ArgumentList 'up' -PassThru }
    } catch { }
    $opened = ''
    $until = (Get-Date).AddSeconds($LoginWait)
    while ((Get-Date) -lt $until) {
        Start-Sleep -Milliseconds $PollMs
        $st = TS-Json @('status', '--json')
        $state = [string](P $st 'BackendState')
        if ($state -eq 'Running') { break }
        $auth = [string](P $st 'AuthURL')
        if ($auth -and $auth -ne $opened -and $auth -match '^https://') {
            Open-Url $auth; $opened = $auth
            Line 'SKIP' 'the Tailscale sign-in page opened: sign in with the SAME account you will use on the iPhone. Waiting...'
        }
        if ($state -eq 'NeedsMachineAuth' -and -not $opened) {
            Open-Url 'https://login.tailscale.com/admin/machines'; $opened = 'machines'
            Line 'SKIP' 'this PC waits for approval: approve it on the page that opened. Waiting...'
        }
    }
    if ($proc) { try { if (-not $proc.HasExited) { $proc.Kill() } } catch { } }
    if ($state -ne 'Running') {
        Line 'FIX' 'Tailscale is not signed in yet. Open Tailscale from the Start menu, sign in, then double-click LIVE_LINK.bat again.'
        exit 1
    }
}
$dns = Dns-Of $st
$who = [string](P (P (P $st 'User') ([string](P (P $st 'Self') 'UserID'))) 'LoginName')
if ($who) { Line 'OK' "signed in as $who and connected" } else { Line 'OK' 'signed in and connected' }
if (-not $dns) {
    Line 'FIX' 'MagicDNS is off in your tailnet. Its page opens: turn MagicDNS on, then double-click LIVE_LINK.bat again.'
    Open-Url $DnsAdmin
    exit 1
}

# ------------------------------------------------------------------------------------------------ 3 the private https link
Write-Host '  3/5 private https link (your devices only)'
$certs = @(P $st 'CertDomains')
if (-not ($certs | Where-Object { $_ })) {
    Line 'SKIP' 'HTTPS is off in your tailnet. Its page opens: click "Enable HTTPS" (under HTTPS Certificates).'
    Line 'SKIP' 'If Tailscale prints a link below, that is the same page. This window carries on by itself.'
    Open-Url $DnsAdmin
}
$sc = TS-Json @('serve', 'status', '--json')
$px = Serve-Proxy $sc $dns
$fun = Funnel-On $sc $dns
if ($px -and (Our-Proxy $px) -and -not $fun) {
    Line 'OK' "already on: https://$dns/ -> $Target"
} else {
    if ($px -and -not (Our-Proxy $px)) { Line 'SKIP' "https://$dns/ pointed at ${px}: it now points at the bot server" }
    if ($fun) { Line 'SKIP' 'Funnel (the public internet) was on for this address: switching it OFF' }
    & $script:Ts serve --bg --yes $Target | Out-Host
    $sc = TS-Json @('serve', 'status', '--json')
    $px = Serve-Proxy $sc $dns
    if (-not ($px -and (Our-Proxy $px))) {
        Line 'FIX' 'The private link did not switch on. If a page opened, click Enable HTTPS there, then double-click LIVE_LINK.bat again.'
        exit 1
    }
    if (Funnel-On $sc $dns) {
        & $script:Ts funnel --https=443 off | Out-Host
        $sc = TS-Json @('serve', 'status', '--json')
        if (Funnel-On $sc $dns) { Line 'FIX' 'Funnel is still on for this address: turn it off in the Tailscale app, then run this again.'; exit 1 }
    }
    Line 'OK' "on: https://$dns/ -> $Target (tailnet only, Funnel off)"
}
$others = @()
$af = P $sc 'AllowFunnel'
if ($af) { foreach ($pp in $af.PSObject.Properties) { if ($pp.Value) { $others += $pp.Name } } }
if ($others.Count) { Line 'SKIP' ("Funnel is on for {0} (not this link; the bot server refuses Funnel requests anyway)" -f ($others -join ', ')) }

# ------------------------------------------------------------------------------------------------ 4 the bot server
Write-Host '  4/5 bot server'
$ping = Get-Url "$Target/api/health/ping"
if ($ping[0] -ne 200) {
    Line 'SKIP' "the bot server does not answer at $Target right now. BOTS_BACK.bat starts it; the link works as soon as it runs."
} else {
    $ss = Get-Url "$Target/api/site/status"
    if ($ss[0] -eq 200) { Line 'OK' 'answers and serves the phone site (read only over the link)' }
    else { Line 'SKIP' 'answers, but runs older code without the phone site: restart it once when flat (STOP_BOT.bat, then BOTS_BACK.bat)' }
}

# ------------------------------------------------------------------------------------------------ 5 a fresh site
Write-Host '  5/5 fresh site every 15 minutes'
if (Task-Exists $PublishTask) {
    Line 'OK' "rebuilt by $PublishTask (PUBLISH_NQ.bat) every 15 minutes"
} else {
    $py = Find-Python
    if (-not $py -or -not (Test-Path -LiteralPath $py)) {
        Line 'SKIP' 'python not found: the live numbers work, the rest of the site is not rebuilt (install Python 3.12, run this again)'
    } elseif (-not (Test-Path -LiteralPath $Publisher)) {
        Line 'SKIP' 'tools\pc_publish.py is missing: the live numbers work, the rest of the site is not rebuilt'
    } else {
        $pyw = J2 (Split-Path -Parent $py) 'pythonw.exe'
        if (-not (Test-Path -LiteralPath $pyw)) { $pyw = $py }
        $argLine = "-X utf8 `"$Publisher`" --work `"$(J2 (J2 $Root 'data') 'live_site')`" --provider none --min-interval 10"
        $made = TLog "TASK REGISTER $TaskName every 15 min: $pyw $argLine"
        if (-not $made) {
            try {
                $user = "$env:USERDOMAIN\$env:USERNAME"
                $action = New-ScheduledTaskAction -Execute $pyw -Argument $argLine -WorkingDirectory $Root
                $every = New-ScheduledTaskTrigger -Once -At '00:00' -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 1)
                $daily = New-ScheduledTaskTrigger -Daily -At '00:00'
                $daily.Repetition = $every.Repetition
                $logon = New-ScheduledTaskTrigger -AtLogOn -User $user
                $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
                    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew -Priority 7
                $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
                $task = New-ScheduledTask -Action $action -Trigger @($daily, $logon) -Settings $settings -Principal $principal `
                    -Description "OLYMPUS: rebuild the phone site on this PC for the private live link (builds only, sends nothing). Installed from $Root"
                if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
                Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
                $made = $true
            } catch {
                Line 'SKIP' "could not create the task $TaskName ($($_.Exception.Message)): the live numbers still work"
            }
        }
        if ($made) {
            Line 'OK' "task ${TaskName}: rebuilds the site every 15 minutes (builds only, sends nothing anywhere)"
            if (-not (TLog "START BUILD $pyw $argLine")) {
                try { Start-Process -FilePath $pyw -ArgumentList $argLine -WorkingDirectory $Root -WindowStyle Hidden | Out-Null } catch { }
            }
            Line 'OK' 'first build started in the background: the full site is there in a few minutes'
        }
    }
}

# ------------------------------------------------------------------------------------------------ Kalshi
if ($KalshiUrl) {
    try {
        $pub = $null
        if (Test-Path -LiteralPath $PubFile) { $pub = Get-Content -LiteralPath $PubFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
        if (-not $pub) { $pub = New-Object PSObject }
        $pub | Add-Member -NotePropertyName 'kalshi_feed_url' -NotePropertyValue $KalshiUrl -Force
        Write-Utf8 $PubFile ($pub | ConvertTo-Json -Depth 6)
        Line 'OK' "Kalshi: the feed is read from $KalshiUrl (saved outside the repo)"
    } catch { Line 'SKIP' "Kalshi: could not save the address ($($_.Exception.Message))" }
} else {
    $pub = $null
    try { if (Test-Path -LiteralPath $PubFile) { $pub = Get-Content -LiteralPath $PubFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop } } catch { }
    $kf = [string](P $pub 'kalshi_file'); $ku = [string](P $pub 'kalshi_feed_url')
    if (-not $kf -and (Test-Path -LiteralPath (J2 (J2 $Home1 'kalshi_feed') 'kalshi.json'))) { $kf = 'kalshi_feed\kalshi.json' }
    if ($kf) { Line 'OK' "Kalshi: shown from $kf" }
    elseif ($ku) { Line 'OK' "Kalshi: shown from $ku" }
    else { Line 'SKIP' 'Kalshi: not shown until the VM publishes its feed (then: LIVE_LINK.bat -KalshiUrl <its https address>)' }
}

# ------------------------------------------------------------------------------------------------ the link
$url = "https://$dns/"
try {
    $rec = New-Object PSObject -Property @{ url = $url; port = $Port; t = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds(); made_by = 'LIVE_LINK.bat' }
    Write-Utf8 $LinkFile ($rec | ConvertTo-Json)
} catch { }
if (-not (TLog "CLIP $url")) { try { Set-Clipboard -Value $url } catch { } }
Write-Host ''
Write-Host '  YOUR LIVE DASHBOARD (only your own devices signed in to Tailscale can open it):' -ForegroundColor Cyan
Write-Host ''
Write-Host "      $url" -ForegroundColor Green
Write-Host ''
Write-Host '  On the iPhone: Tailscale app on and signed in (same account), open that address in Safari,'
Write-Host '  then Share > Add to Home Screen. It is on this PC''s clipboard too. Read only: nothing there can trade.'
Write-Host '  Undo: UNDO_LIVE_LINK.bat'
exit 0
