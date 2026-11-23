"""tools/bat/CLOUDFLARE_SETUP.bat + scripts/cloudflare_setup.ps1: the one double-click move of the phone site to Cloudflare Pages
(docs/HOSTING.md). Static only (no Windows, no pwsh, no network):

  1. bat       CRLF, ASCII, runs scripts\\cloudflare_setup.ps1 and pauses; never names the key variable, no setx, no redirect
  2. key       read masked (Read-Host -AsSecureString), saved only as USER variables ([Environment]::SetEnvironmentVariable
               ..'User'), set for this session through $env:; never printed, never in a [FIX] line, never on a command line,
               never in a double-quoted string; nothing in the script writes a file except the publish.json backup outside the repo
  3. steps     Node check / winget install, --setup cloudflare --cf-project olympus-dash then --force --strict, the address,
               "Add it to your home screen", every exit 1 through the [FIX] helper or the trap
  4. ps51      ASCII, no PowerShell 7-only syntax (??, ?., &&, ||, ternary, -AsPlainText)
  5. docs      docs/HOSTING.md and the help page say "Double-click tools/bat/CLOUDFLARE_SETUP.bat"; the 3-step token creation stays
  6. url       tools/pc_publish.cf_prod_url: <project>.pages.dev, or the suffixed subdomain Cloudflare gave

  python -X utf8 -m tests.test_cloudflare_setup
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES: list = []

BAT = os.path.join(ROOT, "tools/bat/CLOUDFLARE_SETUP.bat")
PS1 = os.path.join(ROOT, "scripts", "cloudflare_setup.ps1")
SECRET_VARS = ("$CfKey", "$OldKey", "$sec", "$bstr", "$env:CLOUDFLARE_API_TOKEN")
PRINTERS = re.compile(r"(?i)\b(Write-Host|Write-Output|Write-Verbose|Write-Debug|Write-Warning|Write-Information|Write-Error|echo|Out-Host"
                      r"|Out-String|Stop-WithFix|Start-Process|Set-Clipboard)\b")
WRITERS = re.compile(r"(?i)\b(Out-File|Set-Content|Add-Content|Tee-Object|Export-\w+|Start-Transcript|New-Item|WriteAll\w*|AppendAll\w*"
                     r"|StreamWriter|setx)\b")


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:500]})" if info and not cond else ""), flush=True)
    return bool(cond)


def code_lines(text: str) -> list:
    """The script's code lines: the <# #> header and # comments dropped."""
    out, in_block = [], False
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("<#"):
            in_block = True
        if in_block:
            if "#>" in s:
                in_block = False
            continue
        if s.startswith("#") or not s:
            continue
        out.append(ln)
    return out


def strip_strings(ln: str) -> str:
    return re.sub(r"'[^']*'", "''", re.sub(r'"[^"]*"', '""', ln))


def part_bat():
    raw = open(BAT, "rb").read()
    check("1a. tools/bat/CLOUDFLARE_SETUP.bat: CRLF line endings, ASCII", b"\n" not in raw.replace(b"\r\n", b"") and raw.endswith(b"\r\n")
          and all(b < 128 for b in raw))
    txt = raw.decode("ascii")
    check("1b. runs scripts\\cloudflare_setup.ps1 (5.1 powershell, -ExecutionPolicy Bypass) and pauses on the same line",
          re.search(r'powershell -NoProfile -ExecutionPolicy Bypass -File "%LE_HOME%scripts\\cloudflare_setup\.ps1".*& pause', txt) is not None)
    check("1c. the .bat never names or expands the key variable, no setx (a command line shows in the process list)",
          "CLOUDFLARE_API_TOKEN" not in txt and "setx" not in txt.lower())
    reds = [m.group(0) for m in re.finditer(r"\d?>>?\s*\S+", txt) if not re.match(r"\d?>>?\s*nul\b", m.group(0), re.I)
            and not m.group(0).startswith("2>&1")]
    check("1d. the .bat writes no file (only >nul)", not reds, reds)
    check("1e. no Python, git or NinjaTrader touched directly by the .bat", not re.search(r"(?i)\bpython\b|\bgit\b|ninja", txt.split(":nops")[0]
                                                                                      .split("setlocal")[1]))


def part_key(lines):
    js = "\n".join(lines)
    check("2a. the key is read masked: Read-Host -AsSecureString, turned into text through a BSTR that is zeroed",
          "Read-Host -AsSecureString" in js and "ZeroFreeBSTR" in js and "ConvertFrom-SecureString" not in js)
    check("2b. saved only as Windows USER variables, both names, and set for this session",
          "[Environment]::SetEnvironmentVariable('CLOUDFLARE_API_TOKEN', $CfKey, 'User')" in js
          and "[Environment]::SetEnvironmentVariable('CLOUDFLARE_ACCOUNT_ID', $CfAcct, 'User')" in js
          and "$env:CLOUDFLARE_API_TOKEN = $CfKey" in js and "'Machine')" not in js.replace("GetEnvironmentVariable('Path', 'Machine')", ""))
    bad_print = [ln.strip() for ln in lines for m in [PRINTERS.search(ln)] if m
                 and any(v.lower() in ln[m.start():].lower() for v in SECRET_VARS)]      # what the printer gets, not an if (...) before it
    check("2c. no line that prints (Write-Host / echo / [FIX] / clipboard ...) names a variable that holds the key", not bad_print, bad_print)
    dq = [ln.strip() for ln in lines for s in re.findall(r'"[^"]*"', ln) if any(v.lower() in s.lower() for v in SECRET_VARS)]
    check("2d. the key variables never sit inside a double-quoted (expanding) string", not dq, dq)
    bare = [ln.strip() for ln in lines if re.fullmatch(r"\s*\(?\s*\$(CfKey|OldKey|sec|bstr|env:CLOUDFLARE_API_TOKEN)\s*\)?\s*", ln)]
    check("2e. no bare key expression (that would print it)", not bare, bare)
    cmd = [ln.strip() for ln in lines if re.search(r"^\s*(\$\w+\s*=\s*@?\(?\s*)?&\s", ln)
           and any(v.lower() in ln.lower() for v in SECRET_VARS)]
    check("2f. the key is never on a command line (python / winget / node get it only through the environment)", not cmd, cmd)
    wr = [ln.strip() for ln in lines if WRITERS.search(strip_strings(ln))]
    check("2g. nothing writes a file or a transcript (no Out-File / Set-Content / Tee-Object / Start-Transcript / setx ...)", not wr, wr)
    redir = [ln.strip() for ln in lines if re.search(r">", strip_strings(ln).replace("2>&1", ""))]
    check("2h. no > redirection to a file anywhere", not redir, redir)
    cp = [ln.strip() for ln in lines if re.search(r"(?i)\b(Copy-Item|Move-Item|Remove-Item)\b", ln)]
    check("2i. the only file touched is publish.json and its backup, in the settings folder outside the repo (OLYMPUS_HOME / USERPROFILE)",
          cp and all(re.search(r"\$Pub(File|Bak)", ln) for ln in cp)
          and "$PubFile = Join-Path $Home1 'publish.json'" in js and "$Home1 = $env:OLYMPUS_HOME" in js
          and not re.search(r"\$Home1\s*=.*\$Root", js), cp)
    check("2j. the key variable is cleared after use", "$CfKey = $null" in js)


def part_steps(lines):
    js = "\n".join(lines)
    check("3a. Node.js: npx checked first, else winget install OpenJS.NodeJS.LTS (exact id, no prompts), the PATH re-read, checked again",
          js.index("Get-Command npx") < js.index("winget install --id OpenJS.NodeJS.LTS -e --silent --accept-source-agreements --accept-package-agreements")
          and "Update-PathNow" in js and js.count("Get-Command npx") >= 2)
    i_set = js.find("& $Python -X utf8 $Script --setup cloudflare --cf-project $Project 2>&1")
    i_pub = js.find("& $Python -X utf8 $Script --force --strict 2>&1")
    i_env = js.find("$env:CLOUDFLARE_API_TOKEN = $CfKey")
    check("3b. --setup cloudflare --cf-project olympus-dash, then a --force --strict publish, both after the key is in this session",
          '[string]$Project = "olympus-dash"' in js and 0 < i_env < i_set < i_pub
          and "--cf-account" not in js and "--token" not in js)
    check("3c. the address (PUBLISH 2/6 line, else <project>.pages.dev) and 'Add it to your home screen'",
          "https://$Project.pages.dev" in js and "PUBLISH 2/6" in js and "Add it to your home screen" in js)
    rest = [ln.strip() for ln in lines if re.search(r"\bexit 1\b", ln)]
    check("3d. every failure exit is the [FIX] helper or the trap (one plain [FIX] line)",
          len(rest) == 2 and "[FIX] $Msg" in js and "[FIX] Something unexpected" in js, rest)
    check("3e. a failed first publish puts the old publisher settings back (the old site keeps updating)",
          "Copy-Item -LiteralPath $PubBak -Destination $PubFile" in js and "keeps updating" in js)
    fixes = re.findall(r"Stop-WithFix\s*\(?'([^']*)'", js)
    check("3f. the [FIX] messages are plain and say what to do (each names the next action)",
          len(fixes) >= 8 and all(len(f) < 260 and re.search(r"(?i)double-click|send|restart|wait|install", f) for f in fixes), fixes)
    check("3g. never starts, stops or arms the bot (no START_BOT / engine. / server.py / arm)",
          not re.search(r"(?i)START_BOT|engine\.|server\.py|\barm\b|ninjatrader\.exe", js))
    check("3h. a -DryRun that changes nothing", "if ($DryRun)" in js and js.index("if ($DryRun)") < js.index("SetEnvironmentVariable"))


def part_ps51(text, lines):
    check("4a. scripts/cloudflare_setup.ps1 is ASCII (Windows PowerShell 5.1 reads a BOM-less file as ANSI)", all(ord(c) < 128 for c in text))
    code = [strip_strings(ln) for ln in lines]
    bad = [ln.strip() for ln in code if re.search(r"\?\?|\?\.|&&|\|\||\s\?\s[^:]*\s:\s|-AsPlainText|-Parallel|\bclean\s*\{", ln)]
    check("4b. no PowerShell 7-only syntax", not bad, bad)
    opens, closes = sum(ln.count("{") for ln in code), sum(ln.count("}") for ln in code)
    check("4c. braces balance", opens == closes, (opens, closes))


def part_docs():
    host = open(os.path.join(ROOT, "docs", "HOSTING.md"), encoding="utf-8").read()
    sec = host.split("## Move to Cloudflare Pages", 1)[-1].split("\nHow it works", 1)[0]
    check("5a. docs/HOSTING.md: 'Double-click tools/bat/CLOUDFLARE_SETUP.bat', the token creation kept, no env-variable dialog / winget step left",
          "Double-click tools/bat/CLOUDFLARE_SETUP.bat" in sec and "Custom token" in sec and "Cloudflare Pages* / *Edit" in sec
          and "rundll32" not in sec and "Never paste the key" in sec)
    hp = os.path.join(ROOT, "tools", "web_public", "hub", "help.json")
    if os.path.isfile(hp):
        it = {i["id"]: i for i in json.load(open(hp, encoding="utf-8"))["items"]}.get("cloudflare") or {}
        st = " ".join(it.get("steps") or [])
        check("5b. the help page entry: Double-click tools/bat/CLOUDFLARE_SETUP.bat, the copy line is in docs/HOSTING.md",
              "tools/bat/CLOUDFLARE_SETUP.bat" in st and it.get("copy", "\0") in host and "olympus-dash.pages.dev" in st and "Never paste the key" in st)


def part_url():
    from tools import pc_publish as PP
    check("6. cf_prod_url: the project's address, or the suffixed subdomain from the deploy address",
          PP.cf_prod_url("olympus-dash") == "https://olympus-dash.pages.dev"
          and PP.cf_prod_url("olympus-dash", "https://a1b2c3d4.olympus-dash.pages.dev") == "https://olympus-dash.pages.dev"
          and PP.cf_prod_url("olympus-dash", "https://a1b2c3d4.olympus-dash-3x1.pages.dev") == "https://olympus-dash-3x1.pages.dev"
          and PP.cf_prod_url("olympus-dash", "https://olympus-dash.pages.dev") == "https://olympus-dash.pages.dev")


def main() -> int:
    text = open(PS1, encoding="utf-8").read()
    lines = code_lines(text)
    part_bat()
    part_key(lines)
    part_steps(lines)
    part_ps51(text, lines)
    part_docs()
    part_url()
    n_ok = sum(RES)
    print(f"\ncloudflare_setup: {n_ok}/{len(RES)} passed")
    return 0 if n_ok == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
