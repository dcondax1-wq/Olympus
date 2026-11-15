"""SETUP_EVERYTHING.bat + scripts/setup_everything.ps1 (docs/SETUP_EVERYTHING.md, owner 2026-11-14: "one double-click"): the code
update from the zip, the private phone link and the go-live flow in ONE window, in order, each step skipped when it is done.

Never the real network, the real bot or Windows. The bot server is a fake HTTP server on a free port (ping + the Launch card's
launch.json; the fake stop_bot.ps1 stops it, it comes back when the script logs START SERVER); tailscale is a fake shell script; the
child scripts (live_link.ps1, bots_back.ps1, stop_bot.ps1) are fakes that record their arguments; python's `-m engine.go` is a fake
that records its arguments, its stdin length and whether a confirm variable was set (never the text). The REAL python runs the REAL
tools/update_from_zip.py (code under test) against a fake bot folder and fake zips. Windows-only steps go to LE_SE_T_LOG, the clock is
LE_SE_T_NOW, the scheduled tasks LE_SE_T_TASKS. Temp folders only; nothing here runs tests.test_win_scripts.

  1. static   the .bat (CRLF, ASCII, labels, a %TEMP% copy first, the script or the zip bootstrap, the missing-zip line, pause), the
              .ps1 (ASCII, never the live phrase / a confirm / the live switch / an arm or start route / a transcript, engine.go called
              bare, bots_back.ps1 -NoResume, the YES gate text), the doc (one owner step), run_area pc, UPDATE_FROM_ZIP's final line
  2. check    tools/update_from_zip.py --check: 0 the folder has the code, 10 update due, 13 older zip, 3 bad zip, 2 no zip
  3. pwsh     (skipped without pwsh) 5.1 lint; the .bat's zip bootstrap line; the flows: first run (stop on Y, update, server back,
              link, the gate), second run (everything skipped), a YES on Saturday refused by the clock, Sunday YES (bots_back -NoResume
              then engine.go bare), already armed (no gate), a paper bot stopped after YES, the phrase typed at the gate (refused, never
              stored), missing zip, bad zip, an open trade, a declined stop, the market open, an older zip, no bot folder, the link
              failing (this window's words, LATER, Enter retries), the new copy of the script going on after the update

  python -X utf8 -m tests.test_setup_everything
"""
from __future__ import annotations

import datetime as dt
import hashlib
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.test_win_scripts import lint_bat  # noqa: E402  (a pure function: importing it runs nothing)

RES: list = []
PHRASE = "I ACCEPT LIVE RISK"
UTC = dt.timezone.utc
SAT = int(dt.datetime(2026, 11, 14, 19, 0, tzinfo=UTC).timestamp())          # Saturday 14:00 ET: market closed (weekend)
SUN_EARLY = int(dt.datetime(2026, 11, 15, 20, 0, tzinfo=UTC).timestamp())    # Sunday 15:00 ET: still the weekend
SUN = int(dt.datetime(2026, 11, 15, 23, 30, tzinfo=UTC).timestamp())         # Sunday 18:30 ET: the market is open
WED = int(dt.datetime(2026, 11, 11, 15, 0, tzinfo=UTC).timestamp())          # Wednesday 10:00 ET: market open
DNS = "olympus-pc.tail1234.ts.net"
URL = f"https://{DNS}/"
GATE = "Is it Sunday after 6 PM ET and are both evals active on MFFU? Type YES"


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[-1500:]})" if info and not cond else ""), flush=True)
    return bool(cond)


def rb(rel):
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return fh.read()


def wr(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def code_lines(ps: str) -> list:
    """The .ps1 without its comment block and # comments."""
    body = ps.split("#>", 1)[-1]
    return [ln for ln in body.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def bat_boot_line(bat: str) -> str:
    m = re.search(r'^powershell -NoProfile -ExecutionPolicy Bypass -Command "([^"]*)"\r?$', bat, re.M)
    return m.group(1) if m else ""


# ============================================================================================== 1 static
def static():
    raw = rb("SETUP_EVERYTHING.bat")
    probs = lint_bat("SETUP_EVERYTHING.bat", raw)
    check("SETUP_EVERYTHING.bat: CRLF, ASCII, every goto target exists (tests/test_win_scripts.lint_bat)", not probs, probs)
    bat = raw.decode("ascii", "replace")
    lines = [ln for ln in bat.split("\r\n") if ln.strip() and not ln.lower().startswith("rem ")]
    first_cmd = [ln for ln in lines if not ln.startswith("@echo") and not ln.lower().startswith("setlocal")][:3]
    check("the .bat runs from a copy in %TEMP% before anything else (the update can rewrite it; one line: call the copy & exit /b)",
          first_cmd[0].lower().startswith('if /i "%~1"=="--from-temp" goto :main') and first_cmd[1].lower().startswith('copy /y "%~f0" "%temp%')
          and first_cmd[2].lower().startswith('call "%temp%') and first_cmd[2].rstrip().endswith("& exit /b"), first_cmd)
    check("the .bat: the script next to it when it is there, else taken out of the newest zip; -ExecutionPolicy Bypass; pauses at the end",
          'set "PS1=%HERE%\\scripts\\setup_everything.ps1"' in bat and 'if exist "%PS1%" goto :run' in bat
          and 'powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -BatDir "%HERE%" %ZARG%' in bat and bat.rstrip().endswith("pause\r\nendlocal"), bat[-400:])
    boot = bat_boot_line(bat)
    check("the .bat's zip bootstrap is one powershell -Command line with no double quote / percent sign inside (cmd would cut it)",
          boot and '"' not in boot and "%" not in boot and "scripts/setup_everything.ps1" in boot and "exit 2" in boot, boot[:200])
    nozip = [ln for ln in lines if ln.startswith("echo  [FIX] No code zip")]
    check("the .bat: no zip -> one line: what happened + the exact fix + 'send a photo of this window'",
          len(nozip) == 1 and "Downloads" in nozip[0] and "SETUP_EVERYTHING.bat again" in nozip[0] and "photo of this window" in nozip[0], nozip)
    check("the .bat never holds the live phrase, engine.go, the live switch or a confirm",
          not re.search(r"ACCEPT|engine\.go|NINJATRADER_LIVE|--confirm|LE_START_CONFIRM", "\n".join(lines), re.I), lines)

    psb = rb("scripts/setup_everything.ps1")
    check("setup_everything.ps1: ASCII only (Windows PowerShell 5.1 reads a file without a BOM as ANSI)", all(c < 128 for c in psb))
    ps = psb.decode("ascii", "replace")
    code = code_lines(ps)
    joined = "\n".join(code)
    check("setup_everything.ps1: the live phrase is nowhere in it (it cannot type what it does not hold)", not re.search(r"accept\s+live", ps, re.I))
    bad = [ln for ln in code if re.search(r"LE_START_CONFIRM|--confirm|NINJATRADER_LIVE|enable-auto-resume|/api/live/start|engine\.ninjatrader|"
                                         r"Start-Transcript|--arm\b|Set-Clipboard -Value \$a\b", ln)]
    bad += [ln for ln in code if "live_model" in ln and re.search(r"Set-Content|Add-Content|Out-File|Copy-Item|Move-Item|Remove-Item|Write(All)?Text|New-Item", ln)]
    check("setup_everything.ps1: no confirm variable / --confirm / live switch / auto-resume / start route / order route / transcript / live_model write",
          not bad, bad)
    go = [ln.strip() for ln in code if "engine.go" in ln]
    check("setup_everything.ps1: engine.go is called once, bare, attached to this window (no argument, pipe or redirect: the owner types)",
          go == ["& $py -X utf8 -m engine.go"], go)
    bbl = [ln.strip() for ln in code if "-File $bb" in ln or ("bots_back" in ln and "-File" in ln)]
    check("setup_everything.ps1: GO_LIVE_EVAL's part 1 = scripts\\bots_back.ps1 -NoResume (no paper resume before the phrase)",
          bbl == ["& $script:PsExe -NoProfile -ExecutionPolicy Bypass -File $bb -NoResume -Python $py"], bbl)
    reads = [ln.strip() for ln in code if "Read-Host" in ln]
    check("setup_everything.ps1: two Read-Host lines: the Ask helper (Y / YES / Enter; its answers go nowhere but an if) and the ONE hidden key prompt",
          reads == ["$a = Read-Host $Prompt", "$s = Read-Host -AsSecureString $Prompt"], reads)
    check("setup_everything.ps1: the pause screen asks exactly the owner's question", f"'   {GATE}'" in ps)
    i1, i2, i3 = joined.find("Header 'STEP 1 of 3'"), joined.find("Header 'STEP 2 of 3'"), joined.find("Header 'STEP 3 of 3'")
    check("setup_everything.ps1: the steps in order: new code, phone link, go live", 0 < i1 < i2 < i3, (i1, i2, i3))
    i1b = joined.find("Header 'STEP 1b of 3'")
    au = joined[i1b:i2]
    check("1b auto-update: its own step between step 1 (new code) and step 2 (phone link), listed on the intro and in the summary",
          0 < i1 < i1b < i2 and "'   1b Auto-update: from then on the PC gets new code by itself" in ps and '"   1b Auto-update   {0}" -f $script:S1b' in ps, (i1, i1b, i2))
    conn = [ln.strip() for ln in code if "engine.autoupdate" in ln and "--connect" in ln]
    check("1b: --connect is called once, bare and attached to this window (no pipe, capture or redirect: a GitHub sign-in may need the owner), with this port",
          conn == ["& $py -X utf8 -m engine.autoupdate --connect --port $Port"], conn)
    stat = [ln.strip() for ln in code if "engine.autoupdate" in ln and "--source-status" in ln]
    check("1b: the read-only --source-status probe first (its line kept for a SKIP), only then the connect; step 1 asks the same probe (Au-On)",
          len(stat) == 2 and "$probe = @(& $py -X utf8 -m engine.autoupdate --source-status 2>&1 | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })" in stat
          and "$null = @(& $script:Py -X utf8 -m engine.autoupdate --source-status 2>&1)" in stat and 0 < au.find("--source-status") < au.find("--connect"), stat)
    s1 = joined[i1:i1b]
    check("step 1: a PC that already updates itself (--source-status 0) never takes a zip again: one OK line, no zip looked for",
          "$selfUpdating = Au-On" in s1 and "if (-not $selfUpdating) { $zipPath = Find-Zip }" in s1 and s1.find("Au-On") < s1.find("Find-Zip")
          and "Say 'OK' 'This PC updates itself from the backup; no zip needed.'" in s1, s1[:600])
    check("1b: never a stop: no Done or exit in it; every code has its own one line (0 on, 20 unreachable, 21 not now, 22 no git, 1 put back, any other)",
          "Done " not in au and not re.search(r"\bexit\b", au) and all(f"$crc -eq {c}" in au for c in (0, 20, 21, 22, 1)) and "Auto-update stopped (code $crc" in au
          and "Could not reach the backup ($signIn in the window that opens, or check the internet). The zip way still works." in au, au[:300])
    check("1b: step 1's stop rules: never with an open trade, while the market is open only after a Y; Stop-Bot / Start-Server reused, the server started once after",
          "$ls.open" in au and "Market-Open (Et-Now)" in au and "(-not (Stop-Bot))" in au and "Ask '   The market is open now and the bot is stopped. Turn on auto-update anyway?" in au
          and "if ($script:ServerDown) { Start-Server; $script:ServerDown = $false }" in au and "$script:ServerDown = $stopped" in joined, au[-400:])
    check("1b: the sign-in names the account in update_source.json (read only), skipped when the folder's code has no auto-update yet",
          "'update_source.json'" in ps and "P $j 'account'" in ps and "This code has no auto-update yet (a newer code zip brings it). The zip way still works." in au)
    check("the .bat's header names the new step", "1b AUTO-UPDATE" in bat, bat[:900])
    i1c = joined.find("Header 'STEP 1c of 3'")
    st1c = joined[i1c:i2]
    check("1c dashboard: its own step between 1b and step 2, on the intro and in the summary; the site name in ONE place",
          0 < i1b < i1c < i2 and "'   1c Your dashboard site updates itself" in ps and '"   1c Dashboard     {0}" -f $script:S1c' in ps
          and ps.count("moonlit-scone-08afe5") == 1 and "$NetlifySite = 'moonlit-scone-08afe5'" in ps, (i1b, i1c, i2))
    keyl = [ln.strip() for ln in code if "$key" in ln]
    check("1c: ONE hidden prompt; the key goes only into pc_publish's stdin (never shown, logged, stored or put on a command line), then forgotten",
          keyl == ["$key = Ask-Secret '   Paste your Netlify key, or press Enter to skip'", "if (-not $key) {",
                   "$key | & $py -X utf8 $pubTool --setup netlify --site-name $NetlifySite --token-stdin", "$key = $null"]
          and joined.count("Ask-Secret '") == 1, keyl)
    check("1c: the two how-to lines (where the key is made) above the prompt",
          "'   The key: app.netlify.com > your picture > User settings > Applications > New access token > Generate > copy.'" in st1c
          and st1c.find("The key: app.netlify.com") < st1c.find("Ask-Secret"), st1c[:500])
    sched = [ln for ln in code if re.search(r"Register-ScheduledTask|New-ScheduledTask|schtasks", ln, re.I)]
    check("1c: the publish task is the PUBLISH_NQ.bat one (scripts\\publish_nq.ps1 reused as is), never a second copy of it here",
          "$pubTask = JP $Root 'scripts\\publish_nq.ps1'" in st1c and "& $script:PsExe -NoProfile -ExecutionPolicy Bypass -File $pubTask -Python $py" in st1c and not sched, sched)
    check("1c: never a stop (no Done / exit in it); skipped when the key is saved and the task is there; each setup answer has its line (0 3 4 5 other)",
          "Done " not in st1c and not re.search(r"\bexit\b", st1c) and "(Netlify-Saved) -and (Task-Exists 'OlympusPublishNQ')" in st1c
          and all(f"$prc -eq {c}" in st1c for c in (0, 3, 4, 5)) and "The key was not saved (code $prc" in st1c, st1c[-500:])
    aus = rb("engine/autoupdate.py").decode("utf-8")
    usrc = json.loads(rb("update_source.json").decode("utf-8"))
    check("1b against the REAL CLI: engine/autoupdate.py has --source-status / --connect / --port and the exit codes step 1b reads (0 1 20 21 22; 10); "
          "update_source.json names the account step 1b shows",
          all(f'"--{x}"' in aus for x in ("source-status", "connect", "port")) and "CONNECT_OK, CONNECT_FAIL, CONNECT_UNREACHABLE, CONNECT_NOT_NOW, CONNECT_NO_GIT = 0, 1, 20, 21, 22" in aus
          and "return 10," in aus and re.match(r"^[A-Za-z0-9][A-Za-z0-9._@+-]{0,79}$", str(usrc.get("account") or "")), usrc.get("account"))
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "engine.autoupdate", "--source-status"], cwd=ROOT, capture_output=True, text=True, timeout=120,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    check("1b against the REAL CLI: its read-only --source-status answers 0 or 10 with one [OK] / [..] line (here, in this repo)",
          r.returncode in (0, 10) and re.search(r"^\s*\[(OK|\.\.)\]\s+\S", r.stdout, re.M), (r.returncode, r.stdout[-300:], r.stderr[-300:]))
    fixes = [ln.strip() for ln in code if ln.strip().startswith("Fix ")]
    check("setup_everything.ps1: every failure is the one-line Fix (what + exact fix + photo), each with both parts",
          len(fixes) >= 12 and all(re.match(r"^Fix (['\"]).+\1 (['\"]).+\2$", f) for f in fixes)
          and "If it still fails, send a photo of this window." in ps, [f for f in fixes if not re.match(r"^Fix (['\"]).+\1 (['\"]).+\2$", f)])

    doc = rb("docs/SETUP_EVERYTHING.md").decode("utf-8")
    steps = re.search(r"## Your step\n(.*?)\n## ", doc, re.S)
    n = len(re.findall(r"^\d\. ", steps.group(1), re.M)) if steps else 0
    cmds = re.findall(r"`(python [^`]*|powershell [^`]*|pwsh [^`]*)`", steps.group(1)) if steps else []
    check("docs/SETUP_EVERYTHING.md: the single owner step on top (one numbered step, no copy-paste line), then a table",
          steps is not None and n == 1 and not cmds and "SETUP_EVERYTHING.bat" in steps.group(1) and "| " in doc, (n, cmds))
    from tests import run_area
    check("tests/run_area.py: setup_everything is in the pc area", "setup_everything" in run_area.AREAS["pc"], run_area.AREAS["pc"])
    upd = rb("tools/update_from_zip.py").decode("utf-8")
    from tools import update_from_zip as U
    check("UPDATE_FROM_ZIP's final line points to SETUP_EVERYTHING.bat / GO_LIVE_EVAL.bat, no longer START_BOT.bat",
          "SETUP_EVERYTHING.bat" in U.NEXT_WORDS and "GO_LIVE_EVAL.bat" in U.NEXT_WORDS and "START_BOT.bat when you are ready" not in upd, U.NEXT_WORDS)


# ============================================================================================== 2 update_from_zip --check
def make_world(base, zip_files, bot_files, zip_name="OLYMPUS_BACKUP_2026-11-14_abc1234.zip", sha="good", zip_dir=None):
    bot = os.path.join(base, "home", "nq-liquidity-engine")
    for rel, data in bot_files.items():
        wr(os.path.join(bot, rel.replace("/", os.sep)), data)
    d = zip_dir or os.path.join(base, "home", "Downloads")
    os.makedirs(d, exist_ok=True)
    zp = os.path.join(d, zip_name)
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, data in zip_files.items():
            z.writestr(rel, data)
    digest = hashlib.sha256(open(zp, "rb").read()).hexdigest()
    if sha == "good":
        wr(os.path.join(d, zip_name[:-4] + ".sha256.txt"), f"{digest}  {zip_name}  0.1 MB\n")
    elif sha == "bad":
        wr(os.path.join(d, zip_name[:-4] + ".sha256.txt"), f"{'0' * 64}  {zip_name}  0.1 MB\n")
    return bot, zp


def tree(folder, skip=("backups", "__pycache__")):
    out = {}
    for root, dirs, files in os.walk(folder):
        dirs[:] = [x for x in dirs if x not in skip]
        for f in files:
            p = os.path.join(root, f)
            out[os.path.relpath(p, folder).replace(os.sep, "/")] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def check_mode():
    base = tempfile.mkdtemp(prefix="se_chk_")
    try:
        code = {"engine/lit.py": "VERSION = 'new'\n", "server.py": "print('s')\n", "live_model.json": '{"strategy": "lit"}\n', "tools/x.py": "X = 2\n"}
        old = {"engine/lit.py": "VERSION = 'old'\n", "server.py": "print('s')\n", "live_model.json": '{"strategy": "lit"}\n', "logs/a.log": "x\n"}
        bot, zp = make_world(base, code, old)
        tool = os.path.join(ROOT, "tools", "update_from_zip.py")
        env = {**os.environ, "HOME": os.path.join(base, "home"), "USERPROFILE": os.path.join(base, "home")}

        def run(*args):
            r = subprocess.run([sys.executable, "-X", "utf8", tool, *args], capture_output=True, text=True, env=env, timeout=120)
            return r.returncode, r.stdout + r.stderr

        before = tree(bot)
        rc, out = run(zp, "--folder", bot, "--check")
        check("--check: an update is due -> exit 10, one line, nothing changed, no backup", rc == 10 and "an update is due (1 updated, 1 new" in out
              and tree(bot) == before and not os.path.exists(os.path.join(bot, "backups")), (rc, out))
        rc, out = run(zp, "--folder", bot, "--port", "1", "--now", str(SAT))
        check("... the update itself (exit 0) ...", rc == 0, out)
        rc, out = run(zp, "--folder", bot, "--check")
        check("--check after the update: this zip was applied (its SHA-256 in the update's record) -> exit 0", rc == 0 and "already has this code (applied" in out, (rc, out))
        wr(os.path.join(bot, "tools", "x.py"), "X = 3  # a fix made on the PC after the update\n")
        rc, out = run(zp, "--folder", bot, "--check")
        check("--check: a file fixed on the PC after the update -> still 'already applied' (exit 0): the same zip never reverts a later fix",
              rc == 0 and open(os.path.join(bot, "tools", "x.py")).read().startswith("X = 3"), (rc, out))
        rc, out = run("--folder", bot, "--undo", "--port", "1")
        rc2, out2 = run(zp, "--folder", bot, "--check")
        check("--check after UNDO_UPDATE: the update is due again (exit 10)", rc in (0, 1) and rc2 == 10, (rc, out, rc2, out2))
        rc, out = run(zp, "--folder", bot, "--port", "1", "--now", str(SAT))
        time.sleep(1.1)                                          # the next update gets its own backup stamp (seconds)
        zb = os.path.join(base, "home", "Downloads", "OLYMPUS_BACKUP_2026-11-14_bbb2222.zip")
        with zipfile.ZipFile(zb, "w") as z:
            for rel, data in {**code, "tools/x.py": "X = 4\n"}.items():
                z.writestr(rel, data)
        rc3, out3 = run(zb, "--folder", bot, "--port", "1", "--now", str(SAT))
        rc, out = run(zp, "--folder", bot, "--check")
        check("--check: a zip applied BEFORE a newer one (same day) -> exit 13, never put back over the newer one",
              rc3 == 0 and rc == 13 and "then the newer OLYMPUS_BACKUP_2026-11-14_bbb2222.zip" in out, (rc3, out3, rc, out))
        old_zip = os.path.join(base, "home", "Downloads", "OLYMPUS_BACKUP_2026-11-10_0ld0001.zip")
        with zipfile.ZipFile(old_zip, "w") as z:
            for rel, data in {**code, "engine/lit.py": "VERSION = 'older'\n"}.items():
                z.writestr(rel, data)
        rc, out = run(old_zip, "--folder", bot, "--check")
        check("--check: a zip dated before the folder's last update (2026-11-10 < 2026-11-14) -> exit 13, never put back over it",
              rc == 13 and "older than the code this folder already took" in out, (rc, out))
        bad = os.path.join(base, "home", "Downloads", "OLYMPUS_BACKUP_2026-11-15_bad0001.zip")
        with open(bad, "wb") as fh:
            fh.write(b"PK\x03\x04 not really a zip")
        rc, out = run(bad, "--folder", bot, "--check")
        check("--check: a damaged zip -> exit 3 with the reason", rc == 3 and "does not open" in out, (rc, out))
        rc, out = run(os.path.join(base, "nope.zip"), "--folder", bot, "--check")
        check("--check: no such zip -> exit 2", rc == 2 and "was not found" in out, (rc, out))
        busy = socket.socket()
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)                                           # "the bot server answers": the update itself would refuse (exit 11)
        try:
            before = tree(bot)
            rc, out = run(zb, "--folder", bot, "--check", "--port", str(busy.getsockname()[1]), "--now", str(WED))
            rc2, out2 = run(zb, "--folder", bot, "--port", str(busy.getsockname()[1]), "--now", str(WED))
        finally:
            busy.close()
        check("--check needs no stopped bot and no closed market (the bot answering, Wednesday 10:00 ET: exit 0; the update itself: 11)",
              rc == 0 and rc2 == 11 and tree(bot) == before, (rc, out, rc2, out2))
    finally:
        shutil.rmtree(base, ignore_errors=True)


# ============================================================================================== 3 pwsh: the fake world
FAKE_TS = r"""#!/bin/sh
echo "TS $*" >> "$FAKE_TS_DIR/ts.log"
S="$FAKE_TS_DIR"
case "$*" in
  "status --json") cat "$S/status.json";;
  "serve status --json") if [ -f "$S/serve.json" ]; then cat "$S/serve.json"; else echo "{}"; fi;;
esac
exit 0
"""

# python: `-m engine.autoupdate` is the fake auto-update CLI (its own log, so the PY / calls counts stay as they were): --source-status
# answers 0 once a --connect worked (else FAKE_AU_STATUS, default 0), --connect refuses with 21 while the server port answers (as the
# real one) and records the port state, its folder and (FAKE_AU_READ=1) how much it read on stdin; `-m engine.go` is the fake START
# BOT (records its arguments, how much it read on stdin, a confirm variable: never the text); everything else
# (tools/update_from_zip.py) runs on the real python
FAKE_PY = r"""#!/bin/sh
case "$*" in
  *"-m engine.autoupdate"*)
    up=0
    "$SE_T_REALPY" -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('127.0.0.1', int(sys.argv[1]))) == 0 else 1)" "$SE_T_PORT" && up=1
    echo "AU $* up=$up cwd=$(pwd)" >> "$SE_T_AULOG"
    case "$*" in
      *--source-status*)
        if [ -f "$SE_T_DIR/au_on" ]; then echo "  [OK]    Auto-update is ON from dcondax1-wq/olympus (fake): the PC gets new code by itself."; exit 0; fi
        st="${FAKE_AU_STATUS:-0}"
        if [ -n "$FAKE_AU_LINE" ]; then echo "$FAKE_AU_LINE"
        elif [ "$st" = "0" ]; then echo "  [OK]    Auto-update is ON (fake)."
        else echo "  [..]    Auto-update from dcondax1-wq/olympus is not connected yet (fake)."; fi
        exit "$st";;
      *--connect*)
        if [ "$up" = "1" ]; then echo "  [SKIP] The bot server is running (fake): it has to be stopped first. Nothing changed."; exit 21; fi
        if [ "${FAKE_AU_READ:-0}" = "1" ]; then line=""; IFS= read -r line || true; echo "AU stdin_len=${#line}" >> "$SE_T_AULOG"; fi
        echo "  [..] fake connect: if a GitHub window opens, sign in as dcondax1-wq..."
        rc="${FAKE_AU_CONNECT:-0}"
        if [ "$rc" = "0" ]; then : > "$SE_T_DIR/au_on"; if [ -n "$FAKE_AU_NEWSE" ]; then cp "$FAKE_AU_NEWSE" scripts/setup_everything.ps1; fi; fi
        exit "$rc";;
    esac
    exit 2;;
esac
echo "PY $*" >> "$SE_T_PYLOG"
case "$*" in
  *"-m engine.go"*)
    if [ -n "$LE_START_CONFIRM" ]; then echo "engine.go CONFIRM_ENV_SET" >> "$SE_T_CALLS"; fi
    line=""
    IFS= read -r line || true
    echo "engine.go args=[$*] stdin_len=${#line}" >> "$SE_T_CALLS"
    echo "  fake START BOT: account names, Sim test, the phrase prompt"
    if [ "${FAKE_GO_ARMS:-0}" = "1" ]; then : > "$SE_T_DIR/armed.flag"; fi
    exit "${FAKE_GO_RC:-0}";;
esac
exec "$SE_T_REALPY" "$@"
"""

FAKE_LL = r"""Add-Content -LiteralPath $env:SE_T_CALLS -Value ("live_link.ps1 " + ($args -join ' '))
$mf = Join-Path $env:SE_T_DIR 'll_mode'
$mode = 'ok'
if (Test-Path -LiteralPath $mf) { $mode = (Get-Content -LiteralPath $mf -TotalCount 1).Trim() }
if ($mode -eq 'failonce') { Set-Content -LiteralPath $mf -Value 'ok'; $mode = 'fail' }
if ($mode -eq 'fail') {
    Write-Host '  [FIX] Tailscale is not installed. Its download page opens now: install it (free), sign in,' -ForegroundColor Red
    Write-Host '  [FIX] then double-click LIVE_LINK.bat again. Nothing else was changed.' -ForegroundColor Red
    exit 1
}
Copy-Item -LiteralPath (Join-Path $env:FAKE_TS_DIR 'serve_on.json') -Destination (Join-Path $env:FAKE_TS_DIR 'serve.json') -Force
New-Item -ItemType Directory -Force -Path $env:OLYMPUS_HOME | Out-Null
Set-Content -LiteralPath (Join-Path $env:OLYMPUS_HOME 'live_link.json') -Value ('{"url": "https://' + $env:SE_T_DNS + '/", "made_by": "LIVE_LINK.bat"}')
Write-Host ('  [OK] on: https://' + $env:SE_T_DNS + '/ -> http://127.0.0.1 (tailnet only, Funnel off)') -ForegroundColor Green
Write-Host '  [SKIP] the bot server does not answer right now. BOTS_BACK.bat starts it; the link works as soon as it runs.' -ForegroundColor Yellow
Write-Host '  YOUR LIVE DASHBOARD (only your own devices signed in to Tailscale can open it):' -ForegroundColor Cyan
Write-Host ('      https://' + $env:SE_T_DNS + '/ FAKE-CARD-LINE') -ForegroundColor Green
exit 0
"""

FAKE_BB = r"""Add-Content -LiteralPath $env:SE_T_CALLS -Value ("bots_back.ps1 " + ($args -join ' '))
New-Item -ItemType Directory -Force -Path $env:OLYMPUS_HOME | Out-Null
Set-Content -LiteralPath (Join-Path $env:OLYMPUS_HOME 'no_github') -Value 'GitHub-free bot mode (fake BOTS_BACK)'
$up = $false
try { $c = New-Object System.Net.Sockets.TcpClient; $c.Connect('127.0.0.1', [int]$env:SE_T_PORT); $up = $true; $c.Close() } catch { }
if (-not $up) {
    Add-Content -LiteralPath $env:LE_SE_T_LOG -Value 'START SERVER (bots_back.ps1)'
    for ($i = 0; $i -lt 100; $i++) {
        try { $c = New-Object System.Net.Sockets.TcpClient; $c.Connect('127.0.0.1', [int]$env:SE_T_PORT); $c.Close(); break } catch { Start-Sleep -Milliseconds 100 }
    }
}
Write-Host '  [OK] fake bots back: six lines'
if ($env:FAKE_BB_RC) { exit [int]$env:FAKE_BB_RC }
exit 0
"""

FAKE_STOP = r"""Add-Content -LiteralPath $env:SE_T_CALLS -Value ("stop_bot.ps1 " + ($args -join ' '))
Set-Content -LiteralPath (Join-Path $env:SE_T_DIR 'stop.flag') -Value 'stop'
Write-Host 'bot stopped via API (ok=True); auto-resume cleared'
"""


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class FakeBot:
    """The bot server: listening = up. GET /api/health/ping and /api/site/launch.json (the Launch card's rows). The fake stop_bot.ps1
    makes it stop listening; a new START SERVER line in the script's Windows log brings it back (the bot itself stopped)."""

    def __init__(self, box):
        self.box, self.port = box, free_port()
        self.running, self.mode, self.armed, self.position, self.launch = False, "PAPER", False, False, True
        self.srv, self.starts, self.stop_evt = None, 0, threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.thread.start()

    def rows(self):
        def row(i, label):
            mode = self.mode
            return {"id": i, "label": label, "mode": mode, "armed": self.armed and mode == "LIVE",
                    "state": ("LIVE, armed" if self.armed else "real account, NOT armed") if mode == "LIVE" else mode.lower(),
                    "running": self.running, "position": ({"side": "sell", "qty": 2, "entry": 25100.0, "stop": 25130.0} if self.position and i == "lit" else None)}
        return [row("lit", "Zlarior 50K"), row("atlas", "ATLAS 25K")]

    def handler(self):
        bot = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                flag = os.path.join(bot.box, "armed.flag")
                if os.path.exists(flag):                            # the fake START BOT armed both (it ran with the phrase)
                    os.remove(flag)
                    bot.running, bot.mode, bot.armed = True, "LIVE", True
                if self.path == "/api/health/ping":
                    body = {"ok": True, "bot_running": bot.running}
                elif self.path == "/api/site/launch.json" and bot.launch:
                    body = {"ok": True, "kind": "le-launch", "live": True, "running": bot.running, "bots": bot.rows()}
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        return H

    def up(self):
        with self.lock:
            if self.srv:
                return
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), self.handler())
            srv.daemon_threads = True
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self.srv = srv

    def down(self):
        with self.lock:
            if not self.srv:
                return
            self.srv.shutdown()
            self.srv.server_close()
            self.srv = None
            self.running = False                                    # a stopped server: the bot is stopped too

    def _watch(self):
        winlog = os.path.join(self.box, "win.log")
        while not self.stop_evt.is_set():
            sf = os.path.join(self.box, "stop.flag")
            if os.path.exists(sf):
                os.remove(sf)
                self.down()
            try:
                with open(winlog) as fh:
                    n = sum(1 for ln in fh if ln.startswith("START SERVER"))
            except OSError:
                n = 0
            if n > self.starts:
                self.starts = n
                self.up()
            time.sleep(0.03)

    def close(self):
        self.stop_evt.set()
        self.down()


def find_pwsh():
    p = os.environ.get("LE_PWSH") or shutil.which("pwsh") or ("/usr/local/bin/pwsh" if os.path.exists("/usr/local/bin/pwsh") else None)
    return p if p and os.path.exists(p) else None


def ts_status(state="Running"):
    return {"BackendState": state, "Self": {"DNSName": DNS + ".", "UserID": 7}, "User": {"7": {"LoginName": "owner@example.com"}}, "CertDomains": [DNS]}


class Box:
    """A PC: a home folder (Downloads, .olympus), the bot folder at %USERPROFILE%\\nq-liquidity-engine, %TEMP% with the script as the .bat's
    zip bootstrap leaves it, the zip's own temp folder (only SETUP_EVERYTHING.bat in it), a fake tailscale, a fake bot server."""

    def __init__(self, bot_files=None, zip_files=None, zip_name="OLYMPUS_BACKUP_2026-11-14_abc1234.zip", sha="good", with_zip=True, bot_home=True,
                 zip_by_bat=False):
        self.dir = tempfile.mkdtemp(prefix="se_ps_")
        self.home = os.path.join(self.dir, "home")
        self.tmp = os.path.join(self.dir, "tmp")
        self.tsdir = os.path.join(self.dir, "ts")
        for d in (self.home, self.tmp, self.tsdir):
            os.makedirs(d, exist_ok=True)
        self.se = rb("scripts/setup_everything.ps1")
        zf = zip_files if zip_files is not None else self.zip_code()
        bf = bot_files if bot_files is not None else self.old_bot()
        if with_zip:
            self.bot, self.zip = make_world(self.dir, zf, bf if bot_home else {}, zip_name=zip_name, sha=sha)
        else:
            self.bot, self.zip = os.path.join(self.home, "nq-liquidity-engine"), None
            for rel, data in (bf if bot_home else {}).items():
                wr(os.path.join(self.bot, rel.replace("/", os.sep)), data)
        self.script = os.path.join(self.tmp, "le_setup_everything.ps1")
        wr(self.script, self.se)
        self.zipdir = os.path.join(self.tmp, "Temp1_" + zip_name)
        wr(os.path.join(self.zipdir, "SETUP_EVERYTHING.bat"), rb("SETUP_EVERYTHING.bat"))
        if zip_by_bat and self.zip:                                 # the zip (+ .sha256.txt) next to the .bat, none in Downloads
            for n in (zip_name, zip_name[:-4] + ".sha256.txt"):
                shutil.move(os.path.join(os.path.dirname(self.zip), n), os.path.join(self.zipdir, n))
            self.zip = os.path.join(self.zipdir, zip_name)
        self.ts = os.path.join(self.dir, "tailscale")
        wr(self.ts, FAKE_TS)
        os.chmod(self.ts, 0o755)
        self.py = os.path.join(self.dir, "python")
        wr(self.py, FAKE_PY)
        os.chmod(self.py, 0o755)
        self.status(ts_status())
        self.fake = FakeBot(self.dir)
        wr(os.path.join(self.tsdir, "serve_on.json"), json.dumps(
            {"TCP": {"443": {"HTTPS": True}}, "Web": {f"{DNS}:443": {"Handlers": {"/": {"Proxy": f"http://127.0.0.1:{self.fake.port}"}}}}}))
        self.calls, self.winlog, self.pylog, self.aulog, self.pplog = (os.path.join(self.dir, n) for n in ("calls.log", "win.log", "py.log", "au.log", "pp.log"))

    @staticmethod
    def zip_code():
        return {"engine/lit.py": "VERSION = 'new'\n", "server.py": "print('server')\n", "live_model.json": '{"strategy": "lit"}\n',
                "engine/go.py": "# START BOT (the tests answer python -m engine.go with a fake)\n", ".gitignore": "logs/\nbackups/\ndata/start_bot.json\n",
                "SETUP_EVERYTHING.bat": rb("SETUP_EVERYTHING.bat"), "scripts/setup_everything.ps1": rb("scripts/setup_everything.ps1"),
                "tools/update_from_zip.py": rb("tools/update_from_zip.py"), "scripts/live_link.ps1": FAKE_LL, "scripts/bots_back.ps1": FAKE_BB,
                "scripts/stop_bot.ps1": FAKE_STOP, "scripts/run_bot.ps1": "# never run by the tests (START SERVER goes to the log)\n"}

    @staticmethod
    def old_bot():
        return {"engine/lit.py": "VERSION = 'old'\n", "server.py": "print('server')\n", "live_model.json": '{"strategy": "lit"}\n',
                "engine/go.py": "# old START BOT\n", "scripts/stop_bot.ps1": FAKE_STOP, "scripts/run_bot.ps1": "# old\n",
                "logs/server-20261113.log": "server log\n", "data/start_bot.json": '{"lit": "MFFUEVBLDR50K", "atlas": "MFFUEVBLDR25K"}\n'}

    def status(self, st):
        wr(os.path.join(self.tsdir, "status.json"), json.dumps(st))

    def ll_mode(self, mode):
        wr(os.path.join(self.dir, "ll_mode"), mode + "\n")

    def run(self, pwsh, args=(), stdin="", now=SAT, tasks="", script=None, batdir=None, go_rc=0, go_arms=1, bb_rc=0, extra_env=None):
        env = {**os.environ, "HOME": self.home, "USERPROFILE": self.home, "TEMP": self.tmp, "OLYMPUS_HOME": os.path.join(self.home, ".olympus"),
               "LE_SE_T_LOG": self.winlog, "LE_SE_T_TASKS": tasks, "LE_SE_T_NOW": str(now), "SE_T_CALLS": self.calls, "SE_T_DIR": self.dir, "SE_T_AULOG": self.aulog,
               "SE_T_PPLOG": self.pplog,
               "SE_T_PORT": str(self.fake.port), "SE_T_REALPY": sys.executable, "SE_T_PYLOG": self.pylog, "SE_T_DNS": DNS, "FAKE_TS_DIR": self.tsdir,
               "FAKE_GO_RC": str(go_rc), "FAKE_GO_ARMS": str(go_arms), "FAKE_BB_RC": str(bb_rc), "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost",
               "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "POWERSHELL_TELEMETRY_OPTOUT": "1", "POWERSHELL_UPDATECHECK": "Off", **(extra_env or {})}
        for k in ("PORT", "LE_BOT_DIR", "LE_PYTHON", "LE_TAILSCALE", "LE_START_CONFIRM", "XDG_DESKTOP_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
            env.pop(k, None)
        a = ["-BatDir", batdir or self.zipdir, "-Python", self.py, "-Tailscale", self.ts, "-Port", str(self.fake.port), "-ServerWait", "15", "-ArmWait", "2", *args]
        r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-File", script or self.script, *a], input=stdin, capture_output=True, text=True, timeout=300, env=env)
        return r.returncode, r.stdout + r.stderr

    def lines(self, p):
        try:
            with open(p) as fh:
                return [ln.strip() for ln in fh if ln.strip()]
        except OSError:
            return []

    def clear(self):
        for p in (self.calls, self.winlog, self.pylog, self.aulog, self.pplog):
            open(p, "w").close()
        self.fake.starts = 0                                        # the START SERVER count starts again with the emptied log

    def manifests(self):
        d = os.path.join(self.bot, "backups", "update_from_zip")
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def cleanup(self):
        self.fake.close()
        shutil.rmtree(self.dir, ignore_errors=True)


def order(out, *marks):
    idx = [out.find(m) for m in marks]
    return all(i >= 0 for i in idx) and idx == sorted(idx)


def phrase_anywhere(folder):
    hits = []
    for root, _dirs, files in os.walk(folder):
        for f in files:
            try:
                with open(os.path.join(root, f), "rb") as fh:
                    if re.search(rb"accept\s+live\s+risk", fh.read(), re.I):
                        hits.append(os.path.relpath(os.path.join(root, f), folder))
            except OSError:
                pass
    return hits


# ============================================================================================== 3 pwsh: the runs
def bootstrap(pwsh):
    """The .bat's one powershell -Command line (only SETUP_EVERYTHING.bat is there: double-clicked inside the zip), really run."""
    boot = bat_boot_line(rb("SETUP_EVERYTHING.bat").decode("ascii"))
    base = tempfile.mkdtemp(prefix="se_boot_")
    try:
        home, tmp = os.path.join(base, "home"), os.path.join(base, "tmp")
        os.makedirs(os.path.join(home, "Downloads"))
        os.makedirs(tmp)
        env = {**os.environ, "USERPROFILE": home, "HOME": home, "TEMP": tmp}
        env.pop("LE_SE_ZIP", None)
        out = os.path.join(tmp, "le_setup_everything.ps1")

        def run(**kw):
            r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-Command", boot], capture_output=True, text=True, timeout=120, env={**env, **kw})
            return r.returncode, r.stdout + r.stderr

        rc, o = run()
        check("bootstrap: no code zip in Downloads / on the Desktop -> exit 2 (the .bat's [FIX] No code zip line), nothing written",
              rc == 2 and not os.path.exists(out), (rc, o))
        old = os.path.join(home, "Downloads", "OLYMPUS_BACKUP_2026-11-10_0ld0001.zip")
        with zipfile.ZipFile(old, "w") as z:
            z.writestr("engine/lit.py", "old\n")
        rc, o = run()
        check("bootstrap: the newest zip has no setup script (too old) -> exit 1 (the .bat's 'too old or damaged' line), nothing written",
              rc == 1 and not os.path.exists(out), (rc, o))
        time.sleep(0.05)
        new = os.path.join(home, "Downloads", "OLYMPUS_BACKUP_2026-11-14_abc1234.zip")
        with zipfile.ZipFile(new, "w") as z:
            z.writestr("scripts/setup_everything.ps1", rb("scripts/setup_everything.ps1"))
        os.utime(old, (time.time() - 3600, time.time() - 3600))
        rc, o = run()
        check("bootstrap: takes scripts/setup_everything.ps1 out of the NEWEST zip in Downloads into %TEMP%, byte for byte",
              rc == 0 and os.path.exists(out) and open(out, "rb").read() == rb("scripts/setup_everything.ps1"), (rc, o))
        os.remove(out)
        rc, o = run(LE_SE_ZIP=old)
        check("bootstrap: a zip dragged onto the .bat wins over the newest one (here: the old one -> exit 1)", rc == 1 and not os.path.exists(out), (rc, o))
        here = os.path.join(base, "botfolder")
        os.makedirs(here)
        shutil.move(new, os.path.join(here, os.path.basename(new)))
        rc, o = run(LE_SE_HERE=here)
        check("bootstrap: also a zip next to the .bat (the .bat and the zip copied into the bot folder)",
              rc == 0 and open(out, "rb").read() == rb("scripts/setup_everything.ps1"), (rc, o))
    finally:
        shutil.rmtree(base, ignore_errors=True)


def flows(pwsh):
    r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-File", os.path.join(ROOT, "tests", "win_harness", "lint51.ps1"),
                        os.path.join(ROOT, "scripts", "setup_everything.ps1")], capture_output=True, text=True, timeout=300)
    found = [ln for ln in r.stdout.splitlines() if ln.strip()]
    check("5.1 lint: no PowerShell-7-only syntax in setup_everything.ps1", r.returncode == 0 and not found, found or r.stderr)

    b = Box()
    try:
        # ---- the first run, Saturday 14:00 ET: the bot server runs a paper bot, the zip is new, the link is off
        b.fake.up()
        b.fake.running = True
        before = tree(b.bot)
        rc, out = b.run(pwsh, stdin="Y\n")
        calls, win, py = b.lines(b.calls), b.lines(b.winlog), b.lines(b.pylog)
        check("first run: exit 0; STEP 1, then STEP 2, then STEP 3, then the summary", rc == 0 and order(out, "STEP 1 of 3", "STEP 2 of 3", "STEP 3 of 3", "SUMMARY"), out[-3000:])
        check("first run: the bot folder found by itself (%USERPROFILE%\\nq-liquidity-engine) from the zip's temp folder; the zip + .sha256.txt found in Downloads",
              f"Bot folder:  {b.bot}" in out and f"Code zip:    {b.zip}" in out and "its checksum file is next to it" in out, out[:1500])
        check("first run: the running bot is stopped (scripts\\stop_bot.ps1) only after the Y, BEFORE the update",
              "Type Y then Enter to stop the bot now" in out and calls and calls[0].startswith("stop_bot.ps1")
              and order(out, "The bot is stopped.", "1. Zip"), (calls, out[-2500:]))
        check("first run: --check, then the update with the zip's own updater (python -I, --pip, this window's own last line)",
              len(py) == 2 and "--check" in py[0] and "-I -X utf8" in py[1] and "--pip" in py[1] and "this window goes on with the next step by itself." in out
              and open(os.path.join(b.bot, "engine", "lit.py")).read() == "VERSION = 'new'\n" and len(b.manifests()) == 1, (py, out[-2500:]))
        check("first run: the local-only files stay (logs, data\\start_bot.json), the new scripts arrived (live_link, bots_back, this script)",
              before["data/start_bot.json"] == tree(b.bot)["data/start_bot.json"] and all(os.path.exists(os.path.join(b.bot, "scripts", n))
              for n in ("live_link.ps1", "bots_back.ps1", "setup_everything.ps1")) and os.path.exists(os.path.join(b.bot, "SETUP_EVERYTHING.bat")), sorted(tree(b.bot)))
        check("first run: the server it stopped is started again (hidden run_bot.ps1), the bot itself stays stopped",
              win[:1] == [f"START SERVER {os.path.join(b.bot, 'scripts', 'run_bot.ps1')}"] and "runs again, with the new code" in out and not b.fake.running, (win, out[-2000:]))
        check("first run: the link is made by scripts\\live_link.ps1 (with this port / python / tailscale) after the update",
              len([c for c in calls if c.startswith("live_link.ps1")]) == 1 and f"-Port {b.fake.port}" in calls[1] and f"-Python {b.py}" in calls[1]
              and f"-Tailscale {b.ts}" in calls[1], calls)
        check("first run: live_link's lines in this window's words: 'Step 3 below starts it', its own card replaced by the big box",
              "Step 3 below starts it" in out and "BOTS_BACK.bat starts it" not in out and "FAKE-CARD-LINE" not in out, out[-3000:])
        check("first run: the link shown big (the boxed YOUR PHONE DASHBOARD LINK) and put on the clipboard; the iPhone steps",
              "YOUR PHONE DASHBOARD LINK" in out and URL in out and f"CLIP {URL}" in win and "Add to Home Screen" in out, (win, out[-2500:]))
        check("first run: the pause screen asks the owner's question (Saturday: 'not Sunday 6 PM yet'); no answer = nothing armed, no bots_back / engine.go",
              GATE in out and "It is not Sunday 6 PM New York time yet" in out and "Stopped here. Nothing is armed." in out and not [c for c in calls if c.startswith(("bots_back", "engine.go"))], (calls, out[-1500:]))
        check("first run: the summary says what happened to each step", re.search(r"1  New code\s+done: the new code is in", out)
              and re.search(r"2  Phone link\s+on: " + re.escape(URL), out) and re.search(r"3  Go live\s+not yet", out), out[-800:])
        check("first run, code without the dashboard setup yet: step 1c says so in one SKIP line and goes on, no prompt",
              "[SKIP] This code cannot set up the dashboard site yet (a newer code zip brings it)." in out and "Paste your Netlify key" not in out
              and re.search(r"1c Dashboard\s+skipped: this code cannot do it yet", out), out[-1500:])
        check("first run, code without auto-update yet: step 1b says so in one SKIP line and goes on (no probe, no connect), the summary names it",
              "[SKIP] This code has no auto-update yet (a newer code zip brings it). The zip way still works." in out and not b.lines(b.aulog)
              and re.search(r"1b Auto-update\s+skipped: this code has no auto-update yet", out) and order(out, "STEP 1b of 3", "STEP 2 of 3"), out[-1500:])

        # ---- the second run: everything done is skipped, nothing is asked
        b.clear()
        rc, out = b.run(pwsh, tasks="OlympusLiveSite")
        calls, win, py = b.lines(b.calls), b.lines(b.winlog), b.lines(b.pylog)
        check("second run: the zip is already applied -> step 1 skipped (only --check ran, no stop, no update, no second backup)",
              rc == 0 and "Already done: the bot folder already has the code of this zip." in out and len(py) == 1 and "--check" in py[0]
              and not [c for c in calls if c.startswith("stop_bot")] and len(b.manifests()) == 1, (py, calls, out[-2000:]))
        check("second run: the link is already on (tailscale serve -> the bot server, the site task there) -> live_link.ps1 not run, the link shown again",
              "Already done: the private link is on" in out and not [c for c in calls if c.startswith("live_link")] and f"CLIP {URL}" in win, (calls, out[-2000:]))
        check("second run: the gate is shown again (not armed yet), no answer -> nothing armed", GATE in out and not [c for c in calls if c.startswith(("bots_back", "engine.go"))], calls)

        # ---- a YES on Saturday / Sunday 15:00 is refused by the clock (the window waits for Sunday 18:00 ET)
        for when, word in ((SAT, "Saturday"), (SUN_EARLY, "Sunday 3:00 PM")):
            b.clear()
            rc, out = b.run(pwsh, stdin="YES\n", tasks="OlympusLiveSite", now=when)
            calls = b.lines(b.calls)
            check(f"YES before Sunday 18:00 ET ({word}): refused ('Not yet: it is {word}... the market opens Sunday 6:00 PM'), asked again, nothing started",
                  rc == 0 and "[WAIT] Not yet: it is" in out and word in out and "the market opens Sunday 6:00 PM" in out and out.count(GATE) == 2
                  and not [c for c in calls if c.startswith(("bots_back", "engine.go", "stop_bot"))], (calls, out[-1500:]))

        # ---- the phrase typed at the YES gate: not YES -> stopped, and it is stored nowhere
        b.clear()
        rc, out = b.run(pwsh, stdin=PHRASE + "\n", tasks="OlympusLiveSite", now=SUN)
        check("the live phrase typed at the YES gate: not YES -> stopped, nothing armed, nothing started",
              rc == 0 and "Stopped here. Nothing is armed." in out and not [c for c in b.lines(b.calls) if c.startswith(("bots_back", "engine.go"))], out[-1200:])

        # ---- Sunday 18:30 ET, YES: GO_LIVE_EVAL's flow, the owner types the phrase in START BOT
        b.clear()
        b.fake.running = True                                   # a paper bot is running: stopped first, after the YES
        rc, out = b.run(pwsh, stdin="YES\n", tasks="OlympusLiveSite", now=SUN)
        calls = b.lines(b.calls)
        go = [c for c in calls if c.startswith("engine.go")]
        check("Sunday 18:30 ET + YES: the paper bot stopped, then bots_back.ps1 -NoResume (with the python it found), then engine.go",
              rc == 0 and [c.split()[0] for c in calls] == ["stop_bot.ps1", "bots_back.ps1", "engine.go"] and calls[1] == f"bots_back.ps1 -NoResume -Python {b.py}"
              and "It is not Sunday 6 PM" not in out, (calls, out[-2500:]))
        check("engine.go is called bare (-X utf8 -m engine.go): no --confirm, no LE_START_CONFIRM, nothing typed into it by the script",
              go == ["engine.go args=[-X utf8 -m engine.go] stdin_len=0"] and "CONFIRM_ENV_SET" not in " ".join(calls), go)
        check("after START BOT: the Launch card shows both live and armed -> '[OK] Zlarior (50K) and ATLAS (25K) run live and armed', summary done",
              "Zlarior (50K) and ATLAS (25K) run live and armed" in out and re.search(r"3  Go live\s+done: both live and armed", out), out[-1500:])
        check("the order on screen: part 1 bots back, then part 2 START BOT where YOU type the phrase", order(out, "part 1 of 2: bots back", "part 2 of 2: START BOT. YOU type the live phrase yourself"), out[-2500:])

        # ---- already armed: step 3 skipped, no gate at all
        b.clear()
        rc, out = b.run(pwsh, tasks="OlympusLiveSite", now=SUN)
        check("already live and armed -> step 3 skipped ('Already done'), no gate, no stop, no bots_back, no engine.go",
              rc == 0 and "Already done: Zlarior (50K) and ATLAS (25K) run live and armed." in out and GATE not in out and not b.lines(b.calls), (b.lines(b.calls), out[-1500:]))

        # ---- START BOT fails / the owner types something else in it: not armed, the one-line fix
        b.fake.running, b.fake.mode, b.fake.armed = False, "PAPER", False
        b.clear()
        rc, out = b.run(pwsh, stdin="YES\n", tasks="OlympusLiveSite", now=SUN, go_rc=1, go_arms=0)
        check("START BOT stops (e.g. something else typed for the phrase): exit 1, 'The evals are not armed' + SETUP_EVERYTHING again + photo",
              rc == 1 and "The evals are not armed (the lines above say why)" in out and "If it still fails, send a photo of this window." in out
              and re.search(r"3  Go live\s+NOT done: not armed", out), out[-1500:])
        check("... GitHub-free mode already on, the server up, the bot stopped: nothing stopped, straight to part 1 and START BOT",
              [c.split()[0] for c in b.lines(b.calls)] == ["bots_back.ps1", "engine.go"], b.lines(b.calls))
        os.remove(os.path.join(b.home, ".olympus", "no_github"))
        b.clear()
        rc, out = b.run(pwsh, stdin="YES\n", tasks="OlympusLiveSite", now=SUN, go_rc=1, go_arms=0)
        check("GitHub-free mode NOT on yet and the server up: it is stopped first so part 1 starts it again GitHub-free (no 'STOP_BOT then BOTS_BACK' later)",
              [c.split()[0] for c in b.lines(b.calls)] == ["stop_bot.ps1", "bots_back.ps1", "engine.go"] and "comes back in GitHub-free mode" in out, (b.lines(b.calls), out[-1500:]))
        b.clear()
        rc, out = b.run(pwsh, stdin="YES\n", tasks="OlympusLiveSite", now=SUN, bb_rc=1)
        check("part 1 (bots_back) fails: exit 1, START BOT never runs, the one-line fix",
              rc == 1 and "Part 1 stopped" in out and not [c for c in b.lines(b.calls) if c.startswith("engine.go")], (b.lines(b.calls), out[-1200:]))
        hits = phrase_anywhere(b.dir)
        check("the live phrase is stored nowhere: no file in the whole PC folder (bot folder, home, %TEMP%, logs) holds it", not hits, hits)
    finally:
        b.cleanup()

    # ---- the new copy of this script goes on after the update (the .bat was double-clicked in the bot folder: an OLDER copy ran)
    b = Box()
    try:
        old_se = b.se.replace(b"$ErrorActionPreference = 'Continue'", b"$ErrorActionPreference = 'Continue'\n# OLD COPY (last week's zip)", 1)
        wr(os.path.join(b.bot, "scripts", "setup_everything.ps1"), old_se)
        wr(os.path.join(b.bot, "SETUP_EVERYTHING.bat"), rb("SETUP_EVERYTHING.bat"))
        rc, out = b.run(pwsh, script=os.path.join(b.bot, "scripts", "setup_everything.ps1"), batdir=b.bot + os.sep + ".")
        check("an older copy in the bot folder: it updates, then the NEW copy goes on with step 2 (-Step1 with the result), step 1 done once",
              rc == 0 and "brought a newer version of this window" in out and "Step 1 (above): done: the new code is in." in out
              and out.count("STEP 1 of 3") == 2 and out.count("STEP 2 of 3") == 1 and len(b.manifests()) == 1
              and open(os.path.join(b.bot, "scripts", "setup_everything.ps1"), "rb").read() == b.se, out[-2500:])
    finally:
        b.cleanup()

    # ---- failures: each one line (what + the fix + the photo), nothing changed
    b = Box(with_zip=False)
    try:
        before = tree(b.bot)
        rc, out = b.run(pwsh)
        check("missing zip (old bot folder, no zip in Downloads / on the Desktop): exit 1, the one line, nothing changed, nothing called",
              rc == 1 and "[FIX] No code zip (OLYMPUS_BACKUP_...zip) was found in Downloads or on the Desktop. Download the zip and its .sha256.txt into Downloads, "
              "then double-click SETUP_EVERYTHING.bat again. If it still fails, send a photo of this window." in out
              and tree(b.bot) == before and not b.lines(b.calls) and not b.lines(b.pylog), out[-1500:])
        wr(os.path.join(b.bot, "scripts", "setup_everything.ps1"), b.se)
        wr(os.path.join(b.bot, "tools", "update_from_zip.py"), rb("tools/update_from_zip.py"))
        wr(os.path.join(b.bot, "scripts", "live_link.ps1"), FAKE_LL)
        wr(os.path.join(b.bot, "scripts", "bots_back.ps1"), FAKE_BB)
        rc, out = b.run(pwsh, tasks="OlympusLiveSite")
        check("no zip but this code is already on the PC: step 1 says so and the window goes on (steps 2 and 3)",
              rc == 0 and "No code zip (OLYMPUS_BACKUP_...zip) in Downloads or on the Desktop: the code already on this PC is used." in out and "STEP 3 of 3" in out, out[-1500:])
    finally:
        b.cleanup()

    b = Box(sha="bad")
    try:
        before = tree(b.bot)
        b.fake.up()
        rc, out = b.run(pwsh)
        check("bad zip (SHA-256 does not match): exit 1, the updater's reason + the one-line fix, the bot not stopped, nothing changed",
              rc == 1 and "SHA-256 does NOT match" in out and "The code zip did not pass its check" in out and "photo of this window" in out
              and not b.lines(b.calls) and tree(b.bot) == before, out[-1500:])
    finally:
        b.cleanup()

    b = Box()
    try:
        b.fake.up()
        b.fake.running, b.fake.mode, b.fake.position = True, "LIVE", True
        before = tree(b.bot)
        rc, out = b.run(pwsh, stdin="Y\n")
        check("an open trade: the bot is never stopped for the update (exit 1, one line), nothing changed",
              rc == 1 and "A bot has an open trade right now, so it is not stopped for the update" in out and not b.lines(b.calls) and tree(b.bot) == before, out[-1500:])
        b.fake.position = False
        rc, out = b.run(pwsh, stdin="n\n")
        check("the stop question answered n: nothing changed, exit 0, the bot left running",
              rc == 0 and "Nothing was changed. Double-click SETUP_EVERYTHING.bat again when you are ready." in out and not b.lines(b.calls)
              and tree(b.bot) == before and b.fake.srv is not None, out[-1500:])
        b.clear()
        rc, out = b.run(pwsh, stdin="n\n", now=WED)
        check("the market open (Wed 10:00 ET) and the bot running: ONE question before anything is stopped; n -> the bot is left running, nothing changed",
              rc == 0 and out.count("Type Y then Enter to stop the bot and update now anyway") == 1 and "Update anyway?" not in out
              and not b.lines(b.calls) and b.fake.srv is not None and tree(b.bot) == before, (b.lines(b.calls), out[-1500:]))
        b.fake.down()
        b.clear()
        rc, out = b.run(pwsh, stdin="\n", now=WED)
        check("the market open (Wed 10:00 ET), the bot stopped: the update asks first; no Y -> nothing changed",
              rc == 0 and "The market is open now and the bot is stopped. Update anyway?" in out and tree(b.bot) == before, out[-1500:])
        b.clear()
        rc, out = b.run(pwsh, stdin="Y\n", now=WED)
        check("... Y -> the update with --allow-market-open; a server that was not running is NOT started (left as found)",
              "--allow-market-open" in " ".join(b.lines(b.pylog)) and open(os.path.join(b.bot, "engine", "lit.py")).read() == "VERSION = 'new'\n"
              and not [w for w in b.lines(b.winlog) if w.startswith("START SERVER")], (b.lines(b.pylog), out[-1500:]))
    finally:
        b.cleanup()

    b = Box()
    try:
        b.fake.up()
        b.fake.running = True
        rc, out = b.run(pwsh, stdin="Y\n", now=WED)
        py = b.lines(b.pylog)
        check("the market open and the bot running, Y: stopped, updated with --allow-market-open in one go, the server started again",
              rc == 0 and [c.split()[0] for c in b.lines(b.calls)[:1]] == ["stop_bot.ps1"] and len(py) >= 2 and "--allow-market-open" in py[1] and "Update anyway?" not in out
              and open(os.path.join(b.bot, "engine", "lit.py")).read() == "VERSION = 'new'\n" and b.lines(b.winlog)[:1][0].startswith("START SERVER"), (py, out[-1500:]))
    finally:
        b.cleanup()

    b = Box(zip_name="OLYMPUS_BACKUP_2026-11-01_0ld0001.zip")
    try:
        man = os.path.join(b.bot, "backups", "update_from_zip", "2026-11-14_090000", "manifest.json")
        wr(man, json.dumps({"zip": "OLYMPUS_BACKUP_2026-11-14_abc1234.zip", "done": True, "undone": False}))
        for rel, data in (("scripts/live_link.ps1", FAKE_LL), ("scripts/bots_back.ps1", FAKE_BB)):   # the newer code is already there
            wr(os.path.join(b.bot, rel.replace("/", os.sep)), data)
        before = tree(b.bot)
        rc, out = b.run(pwsh, tasks="OlympusLiveSite")
        check("an OLDER zip than the folder's last update: step 1 skipped, never put back over the newer code",
              rc == 0 and "Skipped: this zip is older than the code already on this PC." in out and tree(b.bot) == before, out[-1500:])
        newer = b.se.replace(b"$ErrorActionPreference = 'Continue'", b"$ErrorActionPreference = 'Continue'\n# NEWER COPY (the folder's own)", 1)
        wr(os.path.join(b.bot, "scripts", "setup_everything.ps1"), newer)
        rc, out = b.run(pwsh, tasks="OlympusLiveSite")
        check("... and the bot folder has its own (newer) copy of this script: that copy runs steps 2 and 3, told what step 1 found",
              rc == 0 and "The bot folder has its own copy of this window: it goes on from here." in out
              and "Step 1 (above): skipped: the zip is older than the code on this PC." in out and out.count("STEP 2 of 3") == 1
              and re.search(r"1  New code\s+skipped: the zip is older", out), out[-2000:])
    finally:
        b.cleanup()

    b = Box(zip_by_bat=True)
    try:
        rc, out = b.run(pwsh, tasks="OlympusLiveSite")
        check("the zip next to the .bat (none in Downloads): found there and applied",
              rc == 0 and f"Code zip:    {b.zip}" in out and open(os.path.join(b.bot, "engine", "lit.py")).read() == "VERSION = 'new'\n", out[-1500:])
    finally:
        b.cleanup()

    b = Box(bot_home=False)
    try:
        rc, out = b.run(pwsh)
        check("no bot folder anywhere: exit 1, one line (copy the .bat into the bot folder), nothing called",
              rc == 1 and "The bot folder was not found on this PC. Copy SETUP_EVERYTHING.bat out of the zip into the bot folder" in out
              and "photo of this window" in out and not b.lines(b.calls), out[-1200:])
    finally:
        b.cleanup()

    # ---- the link fails (Tailscale not installed): this window's words, LATER skips, Enter tries again
    b = Box()
    try:
        b.ll_mode("fail")
        rc, out = b.run(pwsh, stdin="LATER\n")
        calls = b.lines(b.calls)
        check("the link fails: live_link's FIX in this window's words ('press Enter in this window'), never 'double-click LIVE_LINK.bat'",
              "then press Enter in this window to try again" in out and "LIVE_LINK.bat again" not in out
              and "The phone link is not on yet (the red line above says why)" in out, out[-2000:])
        check("... LATER: step 2 left for later, the window goes on to step 3, the summary says it is not done",
              rc == 0 and len([c for c in calls if c.startswith("live_link")]) == 1 and "STEP 3 of 3" in out
              and re.search(r"2  Phone link\s+NOT done yet", out), (calls, out[-1200:]))
        b.clear()
        b.ll_mode("failonce")
        rc, out = b.run(pwsh, stdin="\n")
        calls = b.lines(b.calls)
        check("... Enter: tried again; the second try works -> the link shown big",
              rc == 0 and len([c for c in calls if c.startswith("live_link")]) == 2 and "YOUR PHONE DASHBOARD LINK" in out and URL in out, (calls, out[-1500:]))
    finally:
        b.cleanup()


# ============================================================================================== 3 pwsh: step 1b, auto-update
AU_FILES = {"engine/autoupdate.py": "# fake engine.autoupdate: the tests' fake python answers --source-status / --connect\n",
            "update_source.json": json.dumps({"v": 1, "remote": "olympus", "url": "https://dcondax1-wq@github.com/dcondax1-wq/olympus.git",
                                              "branch": "pc", "account": "dcondax1-wq"}) + "\n"}
AU_ON = "[OK] Auto-update is ON: from now on the PC gets new code by itself (only when no trade is open, never during trading hours)."
AU_STATUS = "-X utf8 -m engine.autoupdate --source-status"


def au_calls(b):
    """[(arguments, server port answered, folder)] of the fake engine.autoupdate calls."""
    out = []
    for ln in b.lines(b.aulog):
        m = re.match(r"AU (.*) up=(\d) cwd=(.*)$", ln)
        if m:
            out.append((m.group(1), m.group(2) == "1", os.path.realpath(m.group(3))))
    return out


def connects(b):
    return [c for c in au_calls(b) if "--connect" in c[0]]


def starts(b):
    return [w for w in b.lines(b.winlog) if w.startswith("START SERVER")]


def au_flows(pwsh):
    zf = {**Box.zip_code(), **AU_FILES}
    due = {"FAKE_AU_STATUS": "10"}
    # ---- the first run, Saturday, a paper bot running, auto-update due: ONE Y stops the server for the update AND the connect
    b = Box(zip_files=zf)
    try:
        b.fake.up()
        b.fake.running = True
        rc, out = b.run(pwsh, stdin="Y\n", extra_env=due)
        au = au_calls(b)
        check("1b first run: --source-status, then --connect --port N in the bot folder while the server is DOWN (step 1's stop reused: one Y in all)",
              rc == 0 and [a for a, _u, _c in au] == [AU_STATUS, f"-X utf8 -m engine.autoupdate --connect --port {b.fake.port}"]
              and not au[1][1] and au[1][2] == os.path.realpath(b.bot) and out.count("Type Y then Enter") == 1, (au, out[-2500:]))
        check("1b first run: the connect's own lines show in this window (attached), then '[OK] Auto-update is ON: from now on the PC gets new code by itself...'",
              "fake connect: if a GitHub window opens, sign in as dcondax1-wq" in out and AU_ON in out and "the first time a GitHub window may open: sign in as dcondax1-wq" in out
              and order(out, "STEP 1 of 3", "1. Zip", "STEP 1b of 3", "fake connect", AU_ON, "STEP 2 of 3"), out[-2500:])
        check("1b first run: the server is started again ONCE, after the connect (the bot itself stays stopped)",
              len(starts(b)) == 1 and order(out, "fake connect", "Starting the bot server again") and not b.fake.running and b.fake.srv is not None, (b.lines(b.winlog), out[-2000:]))
        check("1b first run: the summary lists the new step ('1b Auto-update   ON: the PC gets new code by itself'), between 1 and 2",
              re.search(r"1b Auto-update\s+ON: the PC gets new code by itself", out) and order(out[out.rfind("SUMMARY"):], "1  New code", "1b Auto-update", "2  Phone link"), out[-900:])
        b.clear()
        rc, out = b.run(pwsh, tasks="OlympusLiveSite")
        check("1b second run: --source-status says 0 -> 'Already on: the PC updates itself', no connect, nothing stopped, nothing asked",
              rc == 0 and "[OK] Already on: the PC updates itself" in out and [a for a, _u, _c in au_calls(b)] == [AU_STATUS, AU_STATUS] and "Type Y then Enter to stop" not in out
              and not [c for c in b.lines(b.calls) if c.startswith("stop_bot")] and re.search(r"1b Auto-update\s+already on", out), (au_calls(b), out[-1500:]))
        check("... and step 1 there: 'This PC updates itself from the backup; no zip needed.' (no zip check, no update, no new backup)",
              "[OK] This PC updates itself from the backup; no zip needed." in out and not b.lines(b.pylog) and len(b.manifests()) == 1
              and re.search(r"1  New code\s+skipped: this PC updates itself from the backup \(no zip needed\)", out), (b.lines(b.pylog), out[-1500:]))
        time.sleep(0.05)
        newer = os.path.join(b.home, "Downloads", "OLYMPUS_BACKUP_2026-11-15_def5678.zip")
        with zipfile.ZipFile(newer, "w") as z:
            for rel, data in {**zf, "engine/lit.py": "VERSION = 'newer, from a later zip'\n"}.items():
                z.writestr(rel, data)
        before = tree(b.bot)
        b.clear()
        rc, out = b.run(pwsh, tasks="OlympusLiveSite")
        check("a NEWER zip in Downloads on a PC that updates itself: still skipped (it would stop every auto-update), the folder unchanged",
              rc == 0 and "This PC updates itself from the backup; no zip needed." in out and tree(b.bot) == before and not b.lines(b.pylog)
              and "STEP 3 of 3" in out, out[-1500:])
    finally:
        b.cleanup()

    # ---- every other answer of --connect: ONE [SKIP] line, never a stop (the server is down and it is Saturday: nothing to ask)
    b = Box(zip_files=zf)
    try:
        words = {"20": ("[SKIP] Could not reach the backup (sign in as dcondax1-wq in the window that opens, or check the internet). The zip way still works.",
                        "not on yet: the backup could not be reached"),
                 "21": ("[SKIP] Not now: the bot server is running or a trade is open. Nothing was changed;", "not now: the bot server was running"),
                 "22": ("[SKIP] Git is not installed on this PC, so it cannot update itself: install Git for Windows (free, git-scm.com)", "not on: Git is not installed"),
                 "1": ("[SKIP] Auto-update could not be turned on, so everything was put back as it was (the lines above say why). The zip way still works.",
                       "not on: it failed and everything was put back"),
                 "7": ("[SKIP] Auto-update stopped (code 7; the lines above say why). The zip way still works.", "not on: it stopped (code 7)")}
        for code, (line, summ) in words.items():
            b.clear()
            rc, out = b.run(pwsh, tasks="OlympusLiveSite", extra_env={**due, "FAKE_AU_CONNECT": code})
            check(f"1b --connect exit {code}: one line ('{line[7:62]}...'), the window goes on with steps 2 and 3, the summary says it",
                  rc == 0 and line in out and order(out, line, "STEP 2 of 3", "STEP 3 of 3") and AU_ON not in out and len(connects(b)) == 1
                  and re.search(r"1b Auto-update\s+" + re.escape(summ), out), out[-1800:])
        b.clear()
        rc, out = b.run(pwsh, tasks="OlympusLiveSite", extra_env={"FAKE_AU_STATUS": "3", "FAKE_AU_LINE": "  [FIX]  Something odd (fake)"})
        check("1b: --source-status answers something else (3): one SKIP with its line, no connect, the window goes on",
              rc == 0 and "[SKIP] Auto-update not checked: Something odd (fake). The zip way still works." in out and not connects(b) and "STEP 3 of 3" in out, out[-1500:])

        # ---- the bot running, step 1 already done: step 1b asks its own Y (market closed); n -> skipped; Y -> stopped, connected, started
        b.fake.up()
        b.fake.running = True
        b.clear()
        rc, out = b.run(pwsh, stdin="n\n", tasks="OlympusLiveSite", extra_env=due)
        check("1b, the bot running and step 1 already done: ONE question ('Type Y then Enter to stop the bot now'); n -> skipped, nothing stopped, no connect",
              rc == 0 and out.count("Type Y then Enter to stop the bot now (anything else: skipped, nothing is changed)") == 1 and "you kept the bot running" in out
              and not connects(b) and not [c for c in b.lines(b.calls) if c.startswith("stop_bot")] and b.fake.srv is not None and b.fake.running, out[-1800:])
        b.clear()
        rc, out = b.run(pwsh, stdin="Y\n", tasks="OlympusLiveSite", extra_env=due)
        check("1b ... Y -> stopped (scripts\\stop_bot.ps1), --connect with the server down, the server started again once, auto-update ON",
              rc == 0 and [c for c in b.lines(b.calls) if c.startswith("stop_bot")] and len(connects(b)) == 1 and not connects(b)[0][1] and len(starts(b)) == 1 and AU_ON in out
              and order(out, "The bot is stopped.", "fake connect", "Starting the bot server again"), (au_calls(b), out[-2000:]))
    finally:
        b.cleanup()

    # ---- an open trade: never stopped; the market open: asked first
    b = Box(zip_files=zf)
    try:
        b.run(pwsh, tasks="OlympusLiveSite", extra_env={**due, "FAKE_AU_CONNECT": "20"})        # the zip goes in first (server down)
        b.fake.up()
        b.fake.running, b.fake.mode, b.fake.position = True, "LIVE", True
        b.clear()
        rc, out = b.run(pwsh, tasks="OlympusLiveSite", extra_env=due)
        check("1b with an open trade: the bot is never stopped, no connect, one SKIP line, the window goes on",
              rc == 0 and "A bot has an open trade right now, so the bot is not stopped: auto-update waits" in out and not connects(b)
              and not [c for c in b.lines(b.calls) if c.startswith("stop_bot")] and re.search(r"1b Auto-update\s+not yet: a trade was open", out) and "STEP 3 of 3" in out, out[-1500:])
        b.fake.position = False
        b.fake.down()
        b.clear()
        rc, out = b.run(pwsh, stdin="\n", now=WED, tasks="OlympusLiveSite", extra_env=due)
        check("1b, the market open (Wed 10:00 ET) and the bot stopped: 'Turn on auto-update anyway?' first; no Y -> skipped, no connect",
              rc == 0 and "The market is open now and the bot is stopped. Turn on auto-update anyway? Type Y then Enter" in out
              and "Auto-update is not turned on: the market is open." in out and not connects(b), out[-1500:])
        b.clear()
        rc, out = b.run(pwsh, stdin="Y\n", now=WED, tasks="OlympusLiveSite", extra_env=due)
        check("1b ... Y -> connected; a server that was not running is not started (left as found)", rc == 0 and AU_ON in out and len(connects(b)) == 1 and not starts(b), out[-1500:])
    finally:
        b.cleanup()
    b = Box(zip_files=zf)
    try:
        b.fake.up()
        b.fake.running = True
        rc, out = b.run(pwsh, stdin="Y\n", now=WED, extra_env=due)
        check("1b, the market open and the bot running on the first run: step 1's ONE question covers both (no second question), stopped once, connected, started once",
              rc == 0 and out.count("Type Y then Enter") == 1 and "Turn on auto-update anyway?" not in out and AU_ON in out and len(starts(b)) == 1
              and len([c for c in b.lines(b.calls) if c.startswith("stop_bot")]) == 1, out[-2000:])
        b.fake.down()
        b.clear()
        os.remove(os.path.join(b.dir, "au_on"))
        b.fake.up()
        b.fake.running = True
        rc, out = b.run(pwsh, stdin="Y\n", now=WED, tasks="OlympusLiveSite", extra_env=due)
        check("1b, the market open and the bot running, step 1 already done: ONE question ('...stop the bot and turn on auto-update now anyway'), Y -> no second question",
              rc == 0 and out.count("Type Y then Enter to stop the bot and turn on auto-update now anyway") == 1 and "Turn on auto-update anyway?" not in out
              and AU_ON in out and len(starts(b)) == 1, out[-2000:])
    finally:
        b.cleanup()

    # ---- the connect brought another copy of this script: the server first, then that copy goes on
    b = Box(zip_files=zf)
    try:
        newer = os.path.join(b.dir, "newer_setup_everything.ps1")
        wr(newer, b.se.replace(b"$ErrorActionPreference = 'Continue'", b"$ErrorActionPreference = 'Continue'\n# NEWER COPY (the backup's)", 1))
        b.fake.up()
        b.fake.running = True
        rc, out = b.run(pwsh, stdin="Y\n", extra_env={**due, "FAKE_AU_NEWSE": newer})
        check("1b: the connect brought another copy of this script: the server started first, then that copy goes on (it says already on; steps 2 and 3 once)",
              rc == 0 and "Auto-update brought a newer version of this window: it goes on from here." in out and out.count("STEP 2 of 3") == 1 and out.count("STEP 1b of 3") == 2
              and "Step 1 (above): done: the new code is in." in out and "[OK] Already on: the PC updates itself" in out and len(starts(b)) == 1
              and order(out, "fake connect", "Starting the bot server again", "Auto-update brought a newer version") and re.search(r"1b Auto-update\s+already on", out), out[-2500:])
    finally:
        b.cleanup()

    # ---- attached to this window: what the owner types reaches --connect (Git's sign-in may ask in the console)
    b = Box(zip_files=zf)
    try:
        rc, out = b.run(pwsh, stdin="typed-by-the-owner\n", tasks="OlympusLiveSite", extra_env={**due, "FAKE_AU_READ": "1"})
        lens = [ln for ln in b.lines(b.aulog) if ln.startswith("AU stdin_len=")]
        check("1b: --connect reads this window's keyboard (attached, not piped): it got the line typed for it", rc == 0 and lens == ["AU stdin_len=18"], (lens, out[-1500:]))
    finally:
        b.cleanup()


# ============================================================================================== 3 pwsh: step 1c, the dashboard site
KEY = "nfp_OwnerKey0123456789abcdefABCDEFxyz"
# tools/pc_publish.py stand-in (the window runs it on the real python): records its arguments and the LENGTH of the key it got on
# stdin and whether it was the typed one (never the key itself); FAKE_PP_RC answers; 0 saves a netlify.json without the key
FAKE_PP = r'''# fake tools/pc_publish.py --setup netlify --site-name NAME --token-stdin (tests/test_setup_everything.py)
import json, os, sys
key = sys.stdin.readline().strip()
with open(os.environ["SE_T_PPLOG"], "a") as fh:
    fh.write(json.dumps({"args": sys.argv[1:], "key_len": len(key), "key_ok": key == os.environ.get("SE_T_KEY")}) + "\n")
rc = int(os.environ.get("FAKE_PP_RC") or 0)
if rc == 0:
    d = os.environ["OLYMPUS_HOME"]
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "netlify.json"), "w") as fh:
        json.dump({"site_id": "6a1f0c2e-1111-4222-8333-944455556666", "token": "saved-by-the-fake", "site_name": "moonlit-scone-08afe5"}, fh)
    print("[OK] publisher set to netlify. Site: https://moonlit-scone-08afe5.netlify.app. (fake)")
else:
    print("[FIX] the fake setup said no (%d)" % rc)
sys.exit(rc)
'''
FAKE_PUB = r"""Add-Content -LiteralPath $env:SE_T_CALLS -Value ("publish_nq.ps1 " + ($args -join ' '))
Write-Host '[OK]  task OlympusPublishNQ: publishes every 15 minutes while you are signed in (fake)'
if ($env:FAKE_PUB_RC) { exit [int]$env:FAKE_PUB_RC }
exit 0
"""
SITE_FILES = {"tools/pc_publish.py": FAKE_PP, "scripts/publish_nq.ps1": FAKE_PUB}


def pp_calls(b):
    return [json.loads(ln) for ln in b.lines(b.pplog)]


def pub_calls(b):
    return [c for c in b.lines(b.calls) if c.startswith("publish_nq.ps1")]


def text_anywhere(folder, needle: str):
    hits = []
    for root, _dirs, files in os.walk(folder):
        for f in files:
            try:
                with open(os.path.join(root, f), "rb") as fh:
                    if needle.encode() in fh.read():
                        hits.append(os.path.relpath(os.path.join(root, f), folder))
            except OSError:
                pass
    return hits


def site_flows(pwsh):
    zf = {**Box.zip_code(), **SITE_FILES}
    with_key = {"SE_T_KEY": KEY}
    b = Box(zip_files=zf)
    try:
        rc, out = b.run(pwsh, stdin=KEY + "\n", extra_env=with_key)
        pp = pp_calls(b)
        check("1c first run: the two how-to lines, ONE hidden prompt, then pc_publish --setup netlify --site-name moonlit-scone-08afe5 --token-stdin, the key on its stdin",
              rc == 0 and "The key: app.netlify.com > your picture > User settings > Applications > New access token > Generate > copy." in out
              and "Paste your Netlify key, or press Enter to skip" in out and len(pp) == 1
              and pp[0]["args"] == ["--setup", "netlify", "--site-name", "moonlit-scone-08afe5", "--token-stdin"] and pp[0]["key_ok"] and pp[0]["key_len"] == len(KEY)
              and order(out, "STEP 1b of 3", "STEP 1c of 3", "Paste your Netlify key", "STEP 2 of 3"), (pp, out[-2500:]))
        check("1c first run: then the PUBLISH_NQ task (scripts\\publish_nq.ps1 -Python <python>, reused as is), '[OK] Your dashboard site updates itself now', the summary says on",
              pub_calls(b) == [f"publish_nq.ps1 -Python {b.py}"] and "[OK] Your dashboard site updates itself now: moonlit-scone-08afe5.netlify.app" in out
              and re.search(r"1c Dashboard\s+on: the dashboard site updates itself", out) and order(out, "Netlify key saved", "the publish task of PUBLISH_NQ.bat"), (b.lines(b.calls), out[-1500:]))
        logs = b.lines(b.pylog) + b.lines(b.calls) + b.lines(b.winlog) + b.lines(b.aulog)
        check("1c: the key is NOWHERE: not on screen, not in any command line (python / child-script logs), not in any file of the whole PC folder",
              KEY not in out and not [ln for ln in logs if KEY in ln] and not text_anywhere(b.dir, KEY), text_anywhere(b.dir, KEY))
        b.clear()
        rc, out = b.run(pwsh, tasks="OlympusLiveSite,OlympusPublishNQ")
        check("1c second run: the key saved and the task there -> 'Already on', no prompt, no setup, no task call",
              rc == 0 and "[OK] Already on: this PC puts your dashboard site on Netlify by itself" in out and "Paste your Netlify key" not in out
              and not pp_calls(b) and not pub_calls(b) and re.search(r"1c Dashboard\s+already on", out), out[-1500:])
        b.clear()
        rc, out = b.run(pwsh, tasks="OlympusLiveSite")
        check("1c: the key saved but the PUBLISH_NQ task missing: no prompt, only the task (publish_nq.ps1)",
              rc == 0 and "Paste your Netlify key" not in out and not pp_calls(b) and pub_calls(b) == [f"publish_nq.ps1 -Python {b.py}"]
              and "[OK] Your dashboard site updates itself now" in out, out[-1500:])
    finally:
        b.cleanup()

    b = Box(zip_files=zf)
    try:
        rc, out = b.run(pwsh, stdin="\n", tasks="OlympusLiveSite")
        check("1c: Enter (no key) -> one SKIP line, nothing saved, no setup, no task; the window goes on",
              rc == 0 and "[SKIP] No key pasted: the dashboard site does not update itself yet" in out and not pp_calls(b) and not pub_calls(b)
              and "STEP 3 of 3" in out and re.search(r"1c Dashboard\s+skipped: no key pasted", out), out[-1500:])
        for code, line, summ in (("3", "Netlify refused that key", "not on: Netlify refused the key"),
                                 ("4", "has no site called moonlit-scone-08afe5", "not on: no site moonlit-scone-08afe5 on that Netlify account"),
                                 ("5", "Could not reach Netlify (check the internet)", "not on: Netlify could not be reached"),
                                 ("9", "The key was not saved (code 9", "not on: the key was not saved (code 9)")):
            b.clear()
            rc, out = b.run(pwsh, stdin=KEY + "\n", tasks="OlympusLiveSite", extra_env={**with_key, "FAKE_PP_RC": code})
            check(f"1c: pc_publish --setup exit {code}: one SKIP line ('{line}'), no task set up, the window goes on, the key not on screen",
                  rc == 0 and line in out and len(pp_calls(b)) == 1 and not pub_calls(b) and "STEP 3 of 3" in out and KEY not in out
                  and re.search(r"1c Dashboard\s+" + re.escape(summ), out), out[-1500:])
        b.clear()
        rc, out = b.run(pwsh, stdin=KEY + "\n", tasks="OlympusLiveSite", extra_env={**with_key, "FAKE_PUB_RC": "1"})
        check("1c: the key saved but the task could not be set up: one SKIP line (PUBLISH_NQ.bat once), the window goes on",
              rc == 0 and "[SKIP] The publish task was not set up" in out and "STEP 3 of 3" in out
              and re.search(r"1c Dashboard\s+not on yet: the publish task was not set up", out), out[-1500:])
    finally:
        b.cleanup()


def main() -> int:
    static()
    check_mode()
    pwsh = find_pwsh()
    if pwsh:
        bootstrap(pwsh)
        flows(pwsh)
        au_flows(pwsh)
        site_flows(pwsh)
    else:
        print("[SKIP] pwsh not found: the PowerShell runs were skipped")
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


def test_setup_everything():                 # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
