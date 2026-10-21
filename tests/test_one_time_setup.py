"""ONE_TIME_SETUP.bat + scripts/one_time_setup.ps1 (the owner's last visit to the Surface), static checks like
tests/test_ops.py (PowerShell can't run here: the files are parsed and grepped): every step a-i is present and in order,
the script elevates itself with a UAC prompt for the power / Windows Update / logon-task part only, the confirm phrase is
read hidden (SecureString), never written, echoed or logged, and Enter falls back to Sim101; the live switch is never
written by the script; the docs carry the one-liner and are linked.

  python -X utf8 -m tests.test_one_time_setup
"""
from __future__ import annotations

import os
import re
import sys

from engine.tradovate import LIVE_PHRASE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def code_only(ps: str) -> str:
    """The PowerShell without the <# #> help block and # comments (strings kept)."""
    ps = re.sub(r"<#.*?#>", "", ps, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)#(?![^'\"]*['\"][^'\"]*$).*$", "", ln) for ln in ps.splitlines())


def main() -> int:
    files = ["ONE_TIME_SETUP.bat", "scripts/one_time_setup.ps1", "docs/ONE_TIME_SETUP.md"]
    missing = [f for f in files if not os.path.exists(os.path.join(ROOT, f))]
    check("files exist: ONE_TIME_SETUP.bat, scripts/one_time_setup.ps1, docs/ONE_TIME_SETUP.md", not missing, missing)
    if missing:
        return 1
    bat, ps, doc = read("ONE_TIME_SETUP.bat"), read("scripts/one_time_setup.ps1"), read("docs/ONE_TIME_SETUP.md")
    code = code_only(ps)

    # ------------------------------------------------------------------ the .bat (same rules as tests/test_ops.py)
    probs = []
    labels = {m.lower() for m in re.findall(r"^:(\w+)", bat, re.M)}
    gotos = {m.lower() for m in re.findall(r"goto :?(\w+)", bat, re.I)} - {"eof"}
    if gotos - labels:
        probs.append(f"goto without label {gotos - labels}")
    if not bat.lstrip().lower().startswith("@echo off"):
        probs.append("no @echo off")
    if 'cd /d "%~dp0"' not in bat:
        probs.append("does not cd to its folder")
    for ln in bat.splitlines():
        t = ln.strip()
        if t.lower().startswith("rem") or t.startswith("::"):
            continue
        if t.count("(") != t.count(")") or t.count('"') % 2:
            probs.append(f"unbalanced in: {t[:60]}")
    for bad in ("api/live/start", "--confirm", "--enable-auto-resume", "NINJATRADER_LIVE", "/api/live/arm"):
        if bad.lower() in bat.lower():
            probs.append(f"contains {bad}")
    check("bat: @echo off, cd to its folder, labels, balanced quotes, nothing live in it", not probs, probs)
    check("bat: runs scripts\\one_time_setup.ps1 with -ExecutionPolicy Bypass and pauses at the end",
          '-ExecutionPolicy Bypass -File "%~dp0scripts\\one_time_setup.ps1"' in bat and "\npause" in bat.replace("\r", ""))
    check(".gitattributes keeps .bat files CRLF", "*.bat text eol=crlf" in read(".gitattributes"))

    # ------------------------------------------------------------------ the .ps1: balanced, param block, -DryRun
    body = re.sub(r"<#.*?#>", "", ps, flags=re.S)
    body = re.sub(r"'[^'\n]*'", "''", body)
    body = re.sub(r'"(?:[^"`\n]|`.)*"', '""', body)
    body = "\n".join(ln.split("#", 1)[0] for ln in body.splitlines())
    bal = [f"{o}{c} {body.count(o)}/{body.count(c)}" for o, c in ("{}", "()", "[]") if body.count(o) != body.count(c)]
    check("ps1: balanced braces / parens / brackets", not bal, bal)
    check("ps1: param block with -DryRun, $ErrorActionPreference", "param(" in ps and "[switch]$DryRun" in ps and "$ErrorActionPreference" in ps)
    check("ps1: PowerShell 5.1 safe (no ?? / ?. / ternary / && chains)", not re.search(r"\?\?|\?\.|\s&&\s|\s\|\|\s", code), re.findall(r".{20}(?:\?\?|\?\.|&&).{20}", code))
    bad_vars = re.findall(r'"[^"\n]*\$[A-Za-z_]\w*:[ \s][^"\n]*"', code)
    check("ps1: no \"$var: text\" (PowerShell reads $var: as a drive)", not bad_vars, bad_vars)

    # ------------------------------------------------------------------ every step present, in order
    marks = [
        ("a stop", "stop_bot.ps1"), ("a pull", "git pull --ff-only origin main"), ("a pip", "pip install -r requirements.txt"),
        ("b power", "standby-timeout-ac"), ("c update", "PauseUpdatesExpiryTime"),
        ("d bot task", "install_autostart.ps1"), ("d ops task", "install_ops_task.ps1"), ("d NinjaTrader", "Find-NinjaTrader"),
        ("e shortcuts", "make_shortcuts.ps1"), ("f autoupdate", "-m engine.autoupdate --enable"),
        ("g run_bot", "run_bot.ps1"), ("g wait", "--wait-server"), ("g start", "-m engine.ninjatrader --start --account $acct --confirm $phrase"),
        ("g auto-resume", "--enable-auto-resume --account $acct --confirm $phrase"),
        ("h health", "-m engine.ops_checks |"), ("i autologon", "sysinternals/downloads/autologon"), ("i remote desktop", "remotedesktop.google.com/access"),
    ]
    main_part = ps[ps.find('Step "a. Stop the bot'):]                 # the normal part after the -DryRun plan
    pos = {k: main_part.find(v) for k, v in marks if k[0] not in "bc"}
    miss = [k for k, v in marks if v not in ps]
    check("every step a-i is in the script", not miss, miss)
    order = [pos[k] for k, _ in marks if k in pos]
    check("steps a, d, e, f, g, h, i run in that order", all(i >= 0 for i in order) and order == sorted(order), list(zip(pos, order)))
    adm = ps[ps.find("function Invoke-AdminPart"):ps.find("if ($AdminPart) {")]
    check("b: no sleep / hibernate on AC, lid = do nothing on AC, USB selective suspend off",
          all(x in adm for x in ("'standby-timeout-ac', '0'", "'hibernate-timeout-ac', '0'", "'LIDACTION', '0'", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226")))
    check("c: active hours 00:00-18:00 ET (converted to this PC's clock), pause, no auto-restart while signed in",
          "ConvertTimeToUtc($d0, $etZone)" in adm and "$d0.AddHours(18)" in adm and "ActiveHoursStart" in adm
          and "AddDays(35)" in adm and "NoAutoRebootWithLoggedOnUsers" in adm)
    check("d: the logon tasks run as the signed-in owner (-User), not as the Administrator", adm.count("'-User', $User") == 2
          and "-ForUser `\"$Me`\"" in ps)
    for f in ("scripts/install_autostart.ps1", "scripts/install_ops_task.ps1"):
        s = read(f)
        check(f"{f}: takes -User (default the current user), still RunLevel Limited",
              '[string]$User = ""' in s and 'if (-not $User) { $User = "$env:USERDOMAIN\\$env:USERNAME" }' in s and "RunLevel Limited" in s)

    # ------------------------------------------------------------------ self-elevation (UAC) for b, c, d-tasks only
    check("self-elevation: Start-Process -Verb RunAs -Wait on this same script with -AdminPart, explained to the owner",
          "Start-Process -FilePath $PsExe -Verb RunAs -Wait" in ps and "-AdminPart" in ps and "$PSCommandPath" in ps
          and "Click YES" in ps and "Why: only an Administrator" in ps)
    check("self-elevation: checks for Administrator first, falls back to the unelevated tasks when UAC is refused",
          "WindowsBuiltInRole]::Administrator" in ps and "Trying the bot logon task without Administrator rights" in ps)
    ap = ps[ps.find("if ($AdminPart) {"):ps.find("the normal part (runs as you)")]
    check("the elevated part only does b, c and the logon tasks, then exits (no bot start, no phrase)",
          "Invoke-AdminPart" in ap and "exit 0" in ap and "Read-Host" not in adm + ap and "engine.ninjatrader" not in adm + ap)

    # ------------------------------------------------------------------ the phrase: hidden, in memory only, Sim101 fallback
    check("the live phrase is written in none of the files", not [f for f in files + ["tests/test_one_time_setup.py"] if LIVE_PHRASE in read(f)])
    check("phrase read hidden: Read-Host -AsSecureString, BSTR freed (ZeroFreeBSTR), variable cleared",
          "Read-Host -AsSecureString" in ps and "ZeroFreeBSTR" in ps and "$phrase = $null" in ps and "Remove-Variable phrase" in ps)
    uses = [ln.strip() for ln in code.splitlines() if "$phrase" in ln]
    leaks = [u for u in uses if re.search(r"Write-|Say-|Add-Content|Set-Content|Out-File|Tee-|Start-Transcript|\"[^\"]*\$phrase", u)]
    check("the phrase only goes to the two CLI calls (never printed, logged or saved)", not leaks and "Start-Transcript" not in ps, leaks)
    check("phrase calls: --start then --enable-auto-resume", ps.find("--start --account $acct --confirm $phrase") < ps.find("--enable-auto-resume --account $acct"))
    check("Enter (empty account or empty phrase) -> Sim101, and it says so", "just Enter = practice on Sim101" in ps
          and "if (-not $phrase) { break }" in ps and "--start --account Sim101" in ps and "runs on Sim101 (practice" in ps)
    check("a wrong phrase gets one retry, then Sim101", "$try -le 2" in ps)
    check("the script never writes the live switch (it only checks it and points to GO_LIVE step 10)",
          not re.search(r"NINJATRADER_\S*\s*=", code) and not re.search(r"(Add|Set)-Content[^\n]*envFile", code)
          and "GO_LIVE_TONIGHT.md step 10" in ps)
    check("never arms through the API or runs golive", not re.search(r"api/live/(arm|start)|engine\.golive", code))
    check("summary log has only the OK / FIX lines (logs/one_time_setup.log)", "one_time_setup.log" in ps
          and "-Value (@(\"ONE_TIME_SETUP $Stamp\") + $Summary)" in ps)

    # ------------------------------------------------------------------ green / red, plain words, NinjaTrader + manual steps
    check("green [OK] and red [FIX] lines", "-ForegroundColor Green" in ps and "-ForegroundColor Red" in ps and "[OK]" in ps and "[FIX]" in ps)
    check("NinjaTrader: found (process, Program Files, uninstall keys), Startup shortcut, started if not running; 3 clicks printed",
          "Get-Process -Name NinjaTrader" in ps and "NinjaTrader 8\\bin\\NinjaTrader.exe" in ps and "Uninstall" in ps
          and "GetFolderPath('Startup')" in ps and "Connect on startup" in ps)
    check("branch: switches to main only without local changes, else explains", "git status --porcelain --untracked-files=no" in ps
          and "git checkout main" in ps and "files changed by hand" in ps)
    check("trade open / trading time: asks before stopping (ops_checks --update-guard)", "--update-guard" in ps)
    check("Autologon: printed steps, no password stored by the script", "Autologon64.exe" in ps and "DefaultPassword" not in ps
          and "Winlogon" not in ps)

    # ------------------------------------------------------------------ docs
    check("docs: the one-liner does git pull and runs ONE_TIME_SETUP.bat", re.search(r"git pull --ff-only origin main; \.\\ONE_TIME_SETUP\.bat", doc)
          and "Get-ScheduledTask LiquidityEngine" in doc)
    check("docs: UAC Yes, hidden phrase, Enter = Sim101, NinjaTrader 3 clicks, Autologon, Chrome Remote Desktop",
          all(x in doc for x in ("Yes", "hidden", "Sim101", "Connect on startup", "Autologon", "remotedesktop.google.com")))
    check("linked from docs/DAILY_CHECKLIST.md and README.md", "docs/ONE_TIME_SETUP.md" in read("docs/DAILY_CHECKLIST.md")
          and "docs/ONE_TIME_SETUP.md" in read("README.md"))

    n = len(RES)
    print(f"one-time setup: {sum(RES)}/{n} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
