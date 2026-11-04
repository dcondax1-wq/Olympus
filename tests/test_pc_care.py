"""PC_CARE.bat + scripts/pc_care.ps1 (owner 2026-11-04: both PCs looked after from one icon; the Surface overheats, has a dark screen and
little memory; the main PC runs the bot and NinjaTrader 8 around the clock).

1. Static, always: the .bat (CRLF, ASCII, local script first, site download when it is alone), the site copies in tools/web_public/pc/
   identical to the repo files, the script is ASCII, switches, no PowerShell-7 syntax, nothing is closed / downloaded / deleted, no
   machine-wide (HKLM) write, UNDO_PC_TUNE.bat undoes it, the bot-health `pc_care` line (engine/pc_health + the phone summary).
2. With pwsh (PowerShell 7 on Linux; LE_PWSH=<path> or pwsh on PATH, else skipped): a token-level 5.1 lint, then the real script runs
   against a FAKE WINDOWS (tests/win_harness/pc_care_stubs.ps1 on top of pc_tune_world.ps1: registry, services, power plans with AC and
   DC values, scheduled tasks, CIM health facts, a UAC that really runs the elevated child). The changes really land in a JSON world, so:
     - -DryRun: the table, the world is byte-for-byte unchanged, no undo file, no health file
     - a full run on the MAIN PC: never sleeps / hibernates, screen off 10 min, USB suspend off, high performance; the suggested startup
       apps (Teams, Spotify ...) are switched off, security / OneDrive / NinjaTrader / unknown ones are NOT; background apps, effects,
       the search-indexing pause (two tasks) land; ends with "BOT PC HEALTHY: YES"; logs\\pc_care.json is written
     - the SURFACE role (no bot folder): CPU 75%, fan first, adaptive brightness off, battery saver does not dim, dark-screen steps shown
     - role auto-detect (bot folder = main, Surface model / small laptop = surface, -Role forces)
     - the health line is honest: temperature "not shown by Windows" when it is not readable, "85 C" when it is; warns on a long uptime,
       tight memory, low disk, a PC that can sleep, NinjaTrader / the bot down in market hours (and only then)
     - UAC (not Administrator) runs the elevated child once; declined = the account part done, power plan untouched, says why
     - -Undo puts the world back EXACTLY (also after running twice; also when the old plan is gone); a failed step stays in the undo file
     - a setting this PC does not have (cooling policy) is reported and skipped; the rest still lands
     - StrictMode 2 repeats the main runs

  python -X utf8 -m tests.test_pc_care          (about 1-2 min with pwsh)
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARN = os.path.join(ROOT, "tests", "win_harness")
PS1 = os.path.join(ROOT, "scripts", "pc_care.ps1")
BAT = os.path.join(ROOT, "PC_CARE.bat")
UNDO_BAT = os.path.join(ROOT, "UNDO_PC_TUNE.bat")
WEB = os.path.join(ROOT, "tools", "web_public", "pc")
STUBS = os.path.join(HARN, "pc_care_stubs.ps1")
RES: list[bool] = []

BAL, HIGH = "381b4222-f694-41f0-9621-a68e2a2b1d4b", "8c5e7fda-e8bf-4a96-9a85-cf8d6e58fbd0"
PLAN = "a1e5c0de-7a0e-4e51-9000-0000000000c1"
CUR = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\"
RUN, APPROVED = CUR + "Run", CUR + "Explorer\\StartupApproved\\Run"
SLEEP, HIBER, VIDEO, USB, CPUMAX, COOL, ADAPT, BRIGHT = ("29f6c1db-86da-48c5-9fdb-f2b67b1f44da", "9d7815a6-7ee4-497e-8888-515a05f02364",
    "3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226", "bc5038f7-23e0-4960-96da-33abaf5935ec",
    "94d3a615-a899-4ac5-ae2b-e4d8f634367f", "fbd9aa66-9553-4097-ba44-ed6e9d65eab8", "aded5e82-b909-4619-9949-f5d71dac0bcb")
ADMIN_EXPR = ("([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole("
              "[Security.Principal.WindowsBuiltInRole]::Administrator)")


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:1500]})" if detail and not cond else ""))
    return bool(cond)


def rb(path):
    with open(path, "rb") as fh:
        return fh.read()


# ============================================================================================== static
def static():
    bat = rb(BAT)
    check("PC_CARE.bat: CRLF line endings, ASCII", b"\n" not in bat.replace(b"\r\n", b"") and bat.endswith(b"\r\n") and all(c < 128 for c in bat))
    check("PC_CARE.bat: runs scripts\\pc_care.ps1 first and pauses on the same line",
          re.search(rb'if exist "%~dp0scripts\\pc_care\.ps1" goto :local', bat)
          and re.search(rb'-ExecutionPolicy Bypass -File "%~dp0scripts\\pc_care\.ps1" %\* & echo\. & pause & exit /b', bat) is not None)
    check("PC_CARE.bat: alone (downloaded from the site) it fetches pc/pc_care.ps1 with -UseBasicParsing and runs it",
          b"https://demetrades2000-coder.github.io/nq-dashboard/pc/pc_care.ps1" in bat and b"-UseBasicParsing" in bat and bat.count(b"-ExecutionPolicy Bypass") == 3)
    check("site copy tools/web_public/pc/PC_CARE.bat is the same file as PC_CARE.bat", os.path.exists(os.path.join(WEB, "PC_CARE.bat")) and rb(os.path.join(WEB, "PC_CARE.bat")) == bat)
    check("site copy tools/web_public/pc/pc_care.ps1 is the same file as scripts/pc_care.ps1", os.path.exists(os.path.join(WEB, "pc_care.ps1")) and rb(os.path.join(WEB, "pc_care.ps1")) == rb(PS1))
    page = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
    check("the pc/ page has the PC_CARE download button next to the storage one (href PC_CARE.bat, download), with a plain explanation",
          'href="PC_CARE.bat" download' in page and 'href="CLEAN_STORAGE.bat" download' in page and 'id="care"' in page and "UNDO_PC_TUNE.bat" in page)
    raw = rb(PS1)
    try:
        raw.decode("ascii")
        ok = True
    except UnicodeDecodeError:
        ok = raw.startswith(b"\xef\xbb\xbf")
    check("pc_care.ps1: ASCII (or UTF-8 with BOM)", ok)
    code = raw.decode("utf-8", "replace")
    body = re.sub(r"<#.*?#>", "", code, flags=re.S)
    check("switches: -DryRun, -Undo, -Yes, -CheckOnly, -Role (auto), -SystemPart", all(re.search(r"\[switch\]\$" + s, code) for s in ("DryRun", "Undo", "Yes", "CheckOnly", "SystemPart"))
          and re.search(r"\[string\]\$Role = 'auto'", code))
    check("nothing is closed: no Stop-Process / taskkill / .Kill()", not re.search(r"(?i)\b(Stop-Process|taskkill|\.Kill\()", body))
    check("nothing is downloaded or uploaded by PC Care itself", not re.search(r"(?i)(Invoke-WebRequest|Invoke-RestMethod|Start-BitsTransfer|DownloadFile|\bcurl\b|\bwget\b)", body))
    check("nothing is deleted: no Remove-Item (Remove-ItemProperty / Unregister-ScheduledTask / powercfg /delete only for its own changes)",
          not re.search(r"Remove-Item(?!Property)|\[System\.IO\.(File|Directory)\]::Delete|Remove-Variable", body))
    stops = re.findall(r"Stop-Service\s+-Name\s+'?([A-Za-z]+)", body)
    check("the only service it stops is WSearch (Windows search indexing); no service start type is changed", set(stops) <= {"WSearch"} and "Set-Service" not in body and "Disable-Service" not in body, stops)
    check("no machine-wide registry write (HKLM is only read for the startup list), no Defender / firewall / network change",
          not [ln for ln in body.splitlines() if "Care-Reg" in ln and "HKLM" in ln] and not re.search(r"(?i)(Add-MpPreference|Set-MpPreference|netsh|Set-NetAdapter|Set-NetFirewall)", body))
    check("a change is recorded (Add-Change) before it is made; the undo file keeps the FIRST before-value",
          body.count("Add-Change ") >= 5 and "function Add-Change" in body and re.search(r"function Add-Change.*?Find-Change", body, re.S))
    m = re.search(r"\$StartupKeepRx = '(.*?)'\n", body)
    keep = m.group(1) if m else ""
    for must in ("security", "defender", "ninja", "onedrive", "liquidity", "python", "obsidian", "claude", "surface", "intel"):
        check(f"startup apps: '{must}' is on the never-offer list", must in keep, keep[:200])
    check("startup apps are switched with the Task Manager switch (StartupApproved\\Run), the Run entry itself is never deleted", "StartupApproved\\Run" in body and not re.search(r"Remove-ItemProperty[^\n]*Run\b", body))
    ub = rb(UNDO_BAT)
    check("UNDO_PC_TUNE.bat: undoes PC Care first (scripts\\pc_care.ps1 -Undo, else the copy in %LOCALAPPDATA%\\LiquidityEngine), then the deep tune; CRLF, ASCII",
          b"\n" not in ub.replace(b"\r\n", b"") and all(c < 128 for c in ub) and ub.index(b"pc_care.ps1") < ub.index(b"clean_pc.ps1")
          and b'scripts\\pc_care.ps1" -Undo & goto :tune' in ub and b"%LOCALAPPDATA%\\LiquidityEngine\\pc_care.ps1" in ub and b"\r\n:tune\r\n" in ub
          and re.search(rb"powershell .*-ExecutionPolicy Bypass .*scripts\\clean_pc\.ps1\" -Undo & echo\. & pause", ub) is not None)


# ============================================================================================== the health line (engine/pc_health + phone)
def health():
    sys.path.insert(0, ROOT)
    from engine import pc_health as H, live_publish as LP
    lv = lambda ls, k: next((x["level"] for x in ls if x["key"] == k), None)  # noqa: E731
    tx = lambda ls, k: next((x["text"] for x in ls if x["key"] == k), "")  # noqa: E731
    ls = H.lines({"pc_care": {"level": "ok", "text": "BOT PC HEALTHY: YES", "age_days": 2.0}})
    check("health: pc_care ok and fresh = green, label 'PC care', the PC_CARE text", lv(ls, "pc_care") == "green" and "BOT PC HEALTHY: YES" in tx(ls, "pc_care")
          and next(x["label"] for x in ls if x["key"] == "pc_care") == "PC care", ls)
    ls = H.lines({"pc_care": {"level": "warn", "text": "BOT PC HEALTHY: NO, look at: Memory", "age_days": 1.0}})
    check("health: pc_care warn = amber (never red: no push comes from it)", lv(ls, "pc_care") == "amber", ls)
    ls = H.lines({"pc_care": {"level": "bad", "text": "x", "age_days": 1.0}})
    check("health: even a 'bad' PC Care result is only amber", lv(ls, "pc_care") == "amber")
    ls = H.lines({"pc_care": {"level": "ok", "text": "BOT PC HEALTHY: YES", "age_days": 60.0}})
    check("health: older than 45 days = amber with 'run PC_CARE.bat'", lv(ls, "pc_care") == "amber" and "run PC_CARE.bat" in tx(ls, "pc_care"), ls)
    check("health: no pc_care facts = no line (the old block is unchanged)", lv(H.lines({"disk_free_gb": 40}), "pc_care") is None and H.lines({}) == [])
    b = {"t": 1, "level": "red", "lines": [{"key": "disk", "label": "Disk space", "level": "red", "text": "1.2 GB free"}, {"key": "pc_care", "label": "PC care", "level": "amber", "text": "x"}]}
    n = H.red_notices(b, b, {}, time.time()) if os.environ.get("LE_PC_HEALTH_PUSH") != "0" else [1]
    check("health: a pc_care line never makes a push of its own (one push for the red disk)", len(n) == 1, n)
    d = tempfile.mkdtemp(prefix="le_t_care_")
    try:
        os.makedirs(os.path.join(d, "logs"))
        s = H.Sampler(None, ps=None, root=d, is_windows=False, t0=time.time())
        check("health: Sampler without logs/pc_care.json = no pc_care fact", "pc_care" not in s.facts(time.time()))
        with open(os.path.join(d, "logs", "pc_care.json"), "w") as fh:
            json.dump({"v": 1, "t": int(time.time()) - 3 * 86400, "level": "ok", "text": "BOT PC HEALTHY: YES", "role": "main"}, fh)
        s = H.Sampler(None, ps=None, root=d, is_windows=False, t0=time.time())
        f = s.facts(time.time())
        check("health: Sampler reads logs/pc_care.json (level, text, age in days)", f.get("pc_care", {}).get("text") == "BOT PC HEALTHY: YES" and 2.9 < f["pc_care"]["age_days"] < 3.1, f.get("pc_care"))
        blk = s.block(time.time())
        check("health: the block carries the PC care line and `skipped` does not list it", any(x["key"] == "pc_care" for x in blk["lines"]) and "pc_care" not in blk["skipped"], blk)
        open(os.path.join(d, "logs", "pc_care.json"), "w").write("{broken")
        s2 = H.Sampler(None, ps=None, root=d, is_windows=False, t0=time.time())
        check("health: a broken pc_care.json never raises (no line)", "pc_care" not in s2.facts(time.time()))
        hb = {"t": blk["t"], "level": blk["level"], "lines": blk["lines"], "skipped": blk["skipped"]}
        summ = LP.pc_health_summary(hb, blk["t"])
        check("phone summary (Jarvis / Argus): the PC care line is there with the label 'PC care'", summ and any(x["key"] == "pc_care" and x["label"] == "PC care" and x["level"] == "ok" for x in summ["lines"]), summ)
        many = {"t": 1, "lines": [{"key": k, "level": "green", "text": k} for k in ("cpu", "ram", "storage", "nt", "bot_mem", "onedrive", "clock", "poll")]
                + [{"key": "pc_care", "level": "amber", "text": "BOT PC HEALTHY: NO, look at: Memory"}]}
        s3 = LP.pc_health_summary(many, 5)
        check("phone summary: 8 lines at most, and a PC care line that found something comes first", s3 and len(s3["lines"]) <= 8 and s3["lines"][0]["key"] == "pc_care" and s3["level"] == "warn", s3)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ============================================================================================== pwsh
def find_pwsh():
    p = os.environ.get("LE_PWSH") or shutil.which("pwsh") or ("/usr/local/bin/pwsh" if os.path.exists("/usr/local/bin/pwsh") else None)
    return p if p and os.path.exists(p) else None


def lint(pwsh):
    r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-File", os.path.join(HARN, "lint51.ps1"), PS1], capture_output=True, text=True, timeout=300)
    found = [ln for ln in r.stdout.splitlines() if ln.strip()]
    check("pc_care.ps1: 5.1 lint (parser tokens + AST): no PowerShell-7-only syntax, cmdlet parameters or encodings", r.returncode == 0 and not found, found or r.stderr)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def new_world(surface: bool, startup: bool = True) -> dict:
    reg = {CUR + "Themes\\Personalize|EnableTransparency": {"v": 1, "t": "DWord"}}
    if startup:
        for n, c in (("Teams", "C:\\Users\\o\\AppData\\Local\\Microsoft\\Teams\\Update.exe --processStart Teams.exe"), ("Spotify", "C:\\Users\\o\\AppData\\Roaming\\Spotify\\Spotify.exe --autostart"),
                     ("Discord", "C:\\Users\\o\\AppData\\Local\\Discord\\Update.exe --processStart Discord.exe"), ("OneDrive", "C:\\Users\\o\\AppData\\Local\\Microsoft\\OneDrive\\OneDrive.exe /background"),
                     ("NinjaTrader", "C:\\Program Files\\NinjaTrader 8\\bin\\NinjaTrader.exe"), ("LiquidityEngineBot", "C:\\bot\\START_BOT.bat"),
                     ("MysteryTool", "C:\\Tools\\mystery.exe"), ("Obsidian", "C:\\Users\\o\\AppData\\Local\\Obsidian\\Obsidian.exe")):
            reg[f"{RUN}|{n}"] = {"v": c, "t": "String"}
        reg[f"HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run|SecurityHealth"] = {"v": "C:\\Windows\\System32\\SecurityHealthSystray.exe", "t": "String"}
        reg[f"HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run|SupportAssist"] = {"v": "C:\\Dell\\SupportAssist.exe", "t": "String"}
        reg[f"{APPROVED}|Discord"] = {"v": [3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "t": "Binary"}       # the owner already switched Discord off
        reg[f"{APPROVED}|Spotify"] = {"v": [2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "t": "Binary"}       # explicitly on: undo must put the 2 back
    return {
        "reg": reg, "svc": {"WSearch": {"start": "Automatic", "status": "Running"}}, "neverTouch": ["WinDefend", "mpssvc", "BFE", "Dhcp"],
        "power": {"active": BAL, "schemes": [BAL, HIGH], "canDup": [BAL, HIGH], "ac": {}, "dc": {}, "unsupported": [],
                  "defaults": {SLEEP: {"ac": 1800, "dc": 900}, HIBER: {"ac": 0, "dc": 0}, VIDEO: {"ac": 300, "dc": 120}, CPUMAX: {"ac": 100, "dc": 100},
                               COOL: {"ac": 1, "dc": 0}, ADAPT: {"ac": 1, "dc": 1}, BRIGHT: {"ac": 60, "dc": 40}}},
        "mm": True, "pf": {"auto": True, "max": 0}, "mp": [], "failMpRemove": False,
        "pc": {"model": "Surface Pro 7" if surface else "OptiPlex 7070", "type": 2 if surface else 1, "ramGB": 3.6 if surface else 16},
        "printers": [], "nics": [], "netadv": {}, "netpm": {}, "tasks": {},
        "health": {"uptimeDays": 2, "ramUsedPct": 50},
        "battery": {"pct": 80, "plugged": True} if surface else None,
    }


class Box:
    """A sandbox PC: with a bot folder (server.py + engine/ninjatrader.py) or without (a Surface / a bare download)."""

    def __init__(self, bot: bool, surface: bool = False, **world_kw):
        self.dir = tempfile.mkdtemp(prefix="le_care_")
        self.bot = bot
        self.root = os.path.join(self.dir, "LiquidityEngine" if bot else "Downloads")
        os.makedirs(os.path.join(self.root, "scripts"))
        shutil.copy(PS1, os.path.join(self.root, "scripts", "pc_care.ps1"))
        if bot:
            os.makedirs(os.path.join(self.root, "engine"))
            open(os.path.join(self.root, "server.py"), "w").write("#\n")
            open(os.path.join(self.root, "engine", "ninjatrader.py"), "w").write("#\n")
        for d in ("LocalAppData", "ProgramData", "Temp", "home"):
            os.makedirs(os.path.join(self.dir, d))
        self.wpath = os.path.join(self.dir, "world.json")
        self.w0 = new_world(surface, **world_kw)
        self.put(copy.deepcopy(self.w0))

    def put(self, w):
        json.dump(w, open(self.wpath, "w"))

    def get(self):
        return json.load(open(self.wpath))

    def json_path(self):
        if self.bot:
            return os.path.join(self.root, "logs", "pc_care.json")
        return os.path.join(self.dir, "LocalAppData", "LiquidityEngine", "pc_care.json")

    def care_json(self):
        p = self.json_path()
        return json.load(open(p)) if os.path.exists(p) else None

    def state_files(self):
        return [p for p in (os.path.join(self.dir, "LocalAppData", "LiquidityEngine", "pc_care_user.json"),
                            os.path.join(self.dir, "ProgramData", "LiquidityEngine", "pc_care_state.json")) if os.path.exists(p)]

    def run(self, pwsh, args, elevated=True, answer="y", uac="yes", et="2026-11-07 10:00", strict=False, free_gb="120", port=None):
        env = dict(os.environ, LOCALAPPDATA=os.path.join(self.dir, "LocalAppData"), ProgramData=os.path.join(self.dir, "ProgramData"), TEMP=os.path.join(self.dir, "Temp"),
                   TMP=os.path.join(self.dir, "Temp"), USERPROFILE=os.path.join(self.dir, "home"), HOME=os.path.join(self.dir, "home"), SystemDrive=self.dir,
                   COMPUTERNAME="TESTPC", PORT=str(port or free_port()), LE_T_WORLD=self.wpath, LE_T_ELEVATED="1" if elevated else "0", LE_T_ANSWER=answer,
                   LE_T_UAC=uac, LE_T_STUBS=STUBS, LE_T_PWSH=find_pwsh() or "pwsh", LE_T_ET=et, LE_T_STRICT="1" if strict else "0", LE_T_FREE_GB=free_gb)
        env.pop("LE_BOT_DIR", None)
        cmd = f". '{STUBS}'; & '{os.path.join(self.root, 'scripts', 'pc_care.ps1')}' {' '.join(args)}; [Console]::WriteLine('EXIT=' + $LASTEXITCODE)"
        r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-NonInteractive", "-Command", cmd], capture_output=True, text=True, timeout=300, env=env, cwd=self.dir)
        return r.stdout, r.stderr

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def runs(pwsh, strict: bool):
    tag = " [StrictMode 2]" if strict else ""

    def common(name, out, err):
        return check(f"{name}: exit 0, no PowerShell error{tag}", "EXIT=0" in out and not err.strip(), (err or out)[-1500:])

    approved = lambda w, n: (w["reg"].get(f"{APPROVED}|{n}") or {}).get("v")  # noqa: E731
    off = [3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    # ---------------------------------------------------------------- 1. -DryRun on the main PC
    b = Box(bot=True)
    try:
        out, err = b.run(pwsh, ["-DryRun"], strict=strict)
        common("DryRun (main PC)", out, err)
        check(f"DryRun: the world is exactly as before, nothing was changed, no undo file, no health file{tag}",
              b.get() == b.w0 and "HARNESS-CHANGE" not in out and not b.state_files() and b.care_json() is None, out[-600:])
        check(f"DryRun: says MAIN PC and shows the plain table (sleep, hibernate, screen, USB, CPU, plan, startup, background, effects, search){tag}",
              "MAIN PC" in out and all(k in out for k in ("Sleep (plugged in)", "Hibernate (plugged in)", "Screen turns off after", "USB selective suspend", "CPU top speed",
                                                           "Power plan", "Startup apps", "Background apps (Store)", "Visual effects", "Search indexing", "Now", "After PC_CARE")), out[:2500])
        check(f"DryRun: the Now column is read from the active plan (sleep 30 min -> never){tag}", re.search(r"Sleep \(plugged in\)\s+30 min\s+never", out) is not None, out[:1800])
        check(f"DryRun: the startup list gives every app a verdict: Teams / Spotify suggested OFF, OneDrive / NinjaTrader / Obsidian / the bot kept, unknown kept, Discord already off{tag}",
              re.search(r"Teams\s+starts\s+suggest OFF", out) and re.search(r"Spotify\s+starts\s+suggest OFF", out) and re.search(r"OneDrive\s+starts\s+keep \(needed\)", out)
              and re.search(r"NinjaTrader\s+starts\s+keep \(needed\)", out) and re.search(r"Obsidian\s+starts\s+keep \(needed\)", out) and re.search(r"LiquidityEngineBot\s+starts\s+keep \(needed\)", out)
              and re.search(r"MysteryTool\s+starts\s+keep \(not recognised\)", out) and re.search(r"Discord\s+already off", out) and re.search(r"SupportAssist\s+all users\s+left alone", out), out[:4000])
        check(f"DryRun: ends with the health line (this fake PC can still sleep: it says so) and 'DRY RUN: nothing was changed'{tag}",
              "BOT PC HEALTHY: NO, look at: Sleep when plugged in" in out and "DRY RUN: nothing was changed" in out, out[-900:])
        check(f"DryRun: the search pause is shown on this PC's clock for 01:15-16:05 ET{tag}", re.search(r"paused weekdays \d\d:\d\d-\d\d:\d\d \(01:15-16:05 ET\)", out))
    finally:
        b.cleanup()

    # ---------------------------------------------------------------- 2. a full run on the main PC (Administrator, Monday 10:00 ET = market hours)
    b = Box(bot=True)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(2)
    try:
        wd = b.get()
        out, err = b.run(pwsh, [], strict=strict, et="2026-11-02 10:00", port=sock.getsockname()[1])      # the "bot" answers on its port; NinjaTrader is not running
        common("full run (main PC, Administrator, Monday 10:00 ET)", out, err)
        w = b.get()
        ac = w["power"]["ac"]
        key = lambda sub_set: next((v for k, v in ac.items() if k.startswith(PLAN + "|") and k.endswith("|" + sub_set)), None)  # noqa: E731
        check(f"main PC: plan 'PC Care' made from High performance and ACTIVE; the old plan is kept{tag}", w["power"]["active"] == PLAN and PLAN in w["power"]["schemes"] and BAL in w["power"]["schemes"], w["power"])
        check(f"main PC: plugged in it never sleeps (0), never hibernates (0), screen off after 10 min (600 s), USB suspend off, CPU top speed 100%{tag}",
              key(SLEEP) == 0 and key(HIBER) == 0 and key(VIDEO) == 600 and key(USB) == 0 and key(CPUMAX) == 100, ac)
        check(f"main PC: the Surface-only settings (fan policy, adaptive brightness) are NOT set{tag}", key(COOL) is None and key(ADAPT) is None and not w["power"]["dc"])
        check(f"main PC: Teams and Spotify no longer start at sign-in (the Task Manager switch: 3 first byte); Run entries are all still there{tag}",
              approved(w, "Teams") == off and approved(w, "Spotify") == off and all(f"{RUN}|{n}" in w["reg"] for n in ("Teams", "Spotify", "OneDrive", "NinjaTrader", "MysteryTool")))
        check(f"main PC: OneDrive, NinjaTrader, the bot, Obsidian, the unknown tool and the machine-wide entries were NOT touched{tag}",
              all(f"{APPROVED}|{n}" not in w["reg"] for n in ("OneDrive", "NinjaTrader", "LiquidityEngineBot", "Obsidian", "MysteryTool", "SecurityHealth", "SupportAssist")))
        check(f"main PC: Discord (already off) is unchanged{tag}", approved(w, "Discord") == off)
        check(f"main PC: background apps off, transparency off (it was 1), visual effects best performance, window animation off{tag}",
              w["reg"][CUR + "BackgroundAccessApplications|GlobalUserDisabled"]["v"] == 1 and w["reg"][CUR + "Themes\\Personalize|EnableTransparency"]["v"] == 0
              and w["reg"][CUR + "Explorer\\VisualEffects|VisualFXSetting"]["v"] == 2 and w["reg"]["HKCU:\\Control Panel\\Desktop\\WindowMetrics|MinAnimate"]["v"] == "0")
        check(f"main PC: no machine-wide (HKLM) registry value was written{tag}", not [k for k in w["reg"] if k.startswith("HKLM:") and w["reg"][k] != wd["reg"].get(k)])
        check(f"main PC: two search-indexing tasks (SYSTEM, weekdays) and, because it is market time, WSearch is stopped{tag}",
              set(w["tasks"]) == {"LiquidityEngine-IndexPause", "LiquidityEngine-IndexResume"} and "Stop-Service -Name WSearch" in w["tasks"]["LiquidityEngine-IndexPause"]["args"]
              and "Start-Service -Name WSearch" in w["tasks"]["LiquidityEngine-IndexResume"]["args"] and w["svc"]["WSearch"]["status"] == "Stopped"
              and w["tasks"]["LiquidityEngine-IndexPause"]["user"] == "SYSTEM", w["tasks"])
        check(f"main PC: no service start type changed, nothing else in the world touched (Defender, network, memory, page file){tag}",
              w["svc"]["WSearch"]["start"] == "Automatic" and w["mp"] == [] and w["netadv"] == {} and w["mm"] == wd["mm"] and w["pf"] == wd["pf"])
        check(f"main PC: Administrator already -> no UAC question{tag}", "HARNESS-UAC" not in out)
        check(f"main PC: ends with a 'BOT PC HEALTHY' line (in market hours NinjaTrader not running is the warning){tag}", "BOT PC HEALTHY" in out, out[-1500:])
        cj = b.care_json()
        check(f"main PC: logs\\pc_care.json written: role main, a text, t, level (NinjaTrader not running in market hours -> warn){tag}", cj and cj["role"] == "main" and cj["v"] == 1 and cj["text"].startswith("BOT PC HEALTHY")
              and cj["level"] in ("ok", "warn") and abs(cj["t"] - time.time()) < 600 and cj["ran"] == "care", cj)
        check(f"main PC: undo files exist (account + Windows part), and a copy of the script sits next to the account undo file for UNDO_PC_TUNE.bat{tag}",
              len(b.state_files()) == 2 and os.path.exists(os.path.join(b.dir, "LocalAppData", "LiquidityEngine", "pc_care.ps1")), b.state_files())
        # the same run again: nothing new, the first before-values are kept; undo = EXACTLY the old world
        out2, err2 = b.run(pwsh, [], strict=strict, et="2026-11-02 10:00", port=sock.getsockname()[1])
        common("second full run (same PC)", out2, err2)
        check(f"second run: sees what is done already ('already'), the world has the same values{tag}", "(already)" in out2 and b.get()["power"]["active"] == PLAN)
        out3, err3 = b.run(pwsh, ["-Undo"], strict=strict, et="2026-11-02 10:00")
        common("-Undo after running twice", out3, err3)
        check(f"UNDO: the world is back EXACTLY as before (plan, startup switches incl. Spotify's explicit 2, registry, tasks, WSearch running){tag}", b.get() == b.w0,
              {k: (b.w0[k], b.get().get(k)) for k in b.w0 if b.get().get(k) != b.w0[k]})
        check(f"UNDO: the undo files are moved away (a second undo has nothing to do){tag}", not b.state_files())
        out4, err4 = b.run(pwsh, ["-Undo"], strict=strict)
        check(f"UNDO again: 'Nothing to undo', exit 0, world unchanged{tag}", "EXIT=0" in out4 and "Nothing to undo" in out4 and b.get() == b.w0)
    finally:
        sock.close()
        b.cleanup()

    # ---------------------------------------------------------------- 3. the health check is honest (-CheckOnly changes nothing)
    b = Box(bot=True)
    try:
        w = b.get()
        w["health"] = {"uptimeDays": 12, "ramUsedPct": 93, "tempC": 85, "perfPct": 55}
        b.put(w)
        w1 = b.get()
        out, err = b.run(pwsh, ["-CheckOnly"], strict=strict, free_gb="9")
        common("-CheckOnly (hot, tight, long uptime, low disk, PC can sleep)", out, err)
        check(f"-CheckOnly: nothing in the world changes{tag}", b.get() == w1 and "HARNESS-CHANGE" not in out and not b.state_files())
        check(f"health: reads 85 C (from the ACPI thermal zone), 12 days up, 93% memory, 9 GB free, sleep 30 min -> 'BOT PC HEALTHY: NO' naming each{tag}",
              "85 C" in out and "ACPI thermal zone" in out and "12 days" in out and "93%" in out and "9 GB" in out and "30 min" in out and "BOT PC HEALTHY: NO, look at:" in out
              and all(k in out.split("BOT PC HEALTHY: NO, look at:")[1] for k in ("Time since the last restart", "Memory (RAM) in use", "Disk space free", "Sleep when plugged in", "Temperature")), out[-2500:])
        cj = b.care_json()
        check(f"health: pc_care.json written with ran=check and level warn{tag}", cj and cj["ran"] == "check" and cj["level"] == "warn" and "NO" in cj["text"], cj)
        w["health"] = {"uptimeDays": 1, "ramUsedPct": 97}
        b.put(w)
        out, err = b.run(pwsh, ["-CheckOnly"], strict=strict, free_gb="1")
        check(f"health: 97% memory and 1 GB free = bad (red); the JSON level is bad{tag}", (b.care_json() or {}).get("level") == "bad" and "[FIX] BOT PC HEALTHY: NO" in out, out[-1200:])
        w["health"] = {"uptimeDays": 1, "ramUsedPct": 40}
        b.put(w)
        out, err = b.run(pwsh, ["-CheckOnly"], strict=strict)
        check(f"health: temperature not readable -> honest line 'not shown by Windows' (and it does not make the PC unhealthy){tag}", "not shown by Windows" in out and "HWiNFO" in out and "Temperature" in out)
        out, err = b.run(pwsh, ["-CheckOnly"], strict=strict, et="2026-11-02 10:00")
        check(f"health: market hours (Mon 10:00 ET) with no NinjaTrader and no bot answering = warnings naming both{tag}", "BOT PC HEALTHY: NO" in out and "NinjaTrader 8" in out.split("look at:")[1] and "Bot server" in out.split("look at:")[1], out[-1500:])
        out, err = b.run(pwsh, ["-CheckOnly"], strict=strict, et="2026-11-07 10:00")
        check(f"health: Saturday = NinjaTrader / bot down is just information, sleep line shows the old 30 min as a warning only{tag}", "NinjaTrader 8" in out and "look at: Sleep when plugged in" in out, out[-1500:])
    finally:
        b.cleanup()

    # ---------------------------------------------------------------- 4. UAC: not Administrator -> the child runs once; declined -> account part only
    b = Box(bot=True)
    try:
        out, err = b.run(pwsh, [], elevated=False, strict=strict, et="2026-11-07 10:00")
        common("full run as a normal user (Windows asks once)", out, err)
        w = b.get()
        check(f"UAC: asked once, the elevated part ran (CHILD lines), the power plan and the two tasks landed{tag}", out.count("HARNESS-UAC") == 1 and "CHILD| " in out and w["power"]["active"] == PLAN
              and len(w["tasks"]) == 2 and "WINDOWS PART (Administrator)" in out, out[-2500:])
        check(f"UAC: the account part (startup, effects) ran in the normal window and the Saturday run did NOT stop WSearch{tag}", approved(w, "Teams") == off and w["svc"]["WSearch"]["status"] == "Running")
        out, err = b.run(pwsh, ["-Undo"], elevated=False, strict=strict)
        common("-Undo as a normal user", out, err)
        check(f"UAC: undo asks once for the Windows part and puts the world back exactly{tag}", out.count("HARNESS-UAC") == 1 and b.get() == b.w0, {k: (b.w0[k], b.get().get(k)) for k in b.w0 if b.get().get(k) != b.w0[k]})
    finally:
        b.cleanup()
    b = Box(bot=True)
    try:
        out, err = b.run(pwsh, [], elevated=False, uac="no", strict=strict)
        common("UAC declined", out, err)
        w = b.get()
        check(f"UAC declined: account part done, power plan and tasks NOT made, it says why{tag}", approved(w, "Teams") == off and w["power"]["active"] == BAL and not w["tasks"]
              and "Administrator was declined" in out, out[-1500:])
    finally:
        b.cleanup()

    # ---------------------------------------------------------------- 5. the questions: N stops everything; unsupported settings are skipped; a failed undo step stays
    b = Box(bot=True)
    try:
        out, err = b.run(pwsh, [], strict=strict, answer="n")
        common("main question answered N", out, err)
        check(f"N: 'Stopped: nothing was changed', the world is identical, no undo file; the health line is still written{tag}", "Stopped: nothing was changed" in out and b.get() == b.w0
              and not b.state_files() and (b.care_json() or {}).get("ran") == "check", out[-800:])
    finally:
        b.cleanup()
    b = Box(bot=True)
    try:
        w = b.get()
        w["power"]["unsupported"] = [USB]
        b.put(w)
        out, err = b.run(pwsh, [], strict=strict)
        common("a power setting this PC does not have", out, err)
        w = b.get()
        check(f"unsupported USB setting: reported 'does not have that setting', the other settings still land{tag}", "USB selective suspend: this PC does not have that setting" in out
              and w["power"]["active"] == PLAN and any(k.endswith("|" + SLEEP) for k in w["power"]["ac"]), out[-1800:])
    finally:
        b.cleanup()
    b = Box(bot=True)
    try:
        w = b.get()
        w["power"]["schemes"] = [BAL, HIGH, "dead0000-0000-0000-0000-00000000beef"]
        w["power"]["active"] = "dead0000-0000-0000-0000-00000000beef"          # the owner's own plan is active when PC Care starts
        b.put(w)
        w0 = copy.deepcopy(w)
        b.run(pwsh, [], strict=strict)
        w = b.get()
        w["power"]["schemes"] = [BAL, HIGH, PLAN]                               # ... and that plan is gone when the undo runs
        b.put(w)
        out, err = b.run(pwsh, ["-Undo"], strict=strict)
        common("-Undo when the old plan is gone", out, err)
        w = b.get()
        check(f"undo: the old power plan is gone -> falls back to Balanced and still removes 'PC Care'{tag}", w["power"]["active"] == BAL and PLAN not in w["power"]["schemes"], w["power"])
    finally:
        b.cleanup()
    b = Box(bot=True)
    try:
        b.run(pwsh, [], strict=strict)
        w = b.get()
        w["power"]["schemes"] = [HIGH, PLAN]                                    # Balanced AND the old plan vanished: the undo of the plan cannot work
        b.put(w)
        out, err = b.run(pwsh, ["-Undo"], strict=strict)
        sysf = os.path.join(b.dir, "ProgramData", "LiquidityEngine", "pc_care_state.json")
        left = json.load(open(sysf)) if os.path.exists(sysf) else {}
        check(f"undo: a step that cannot be undone is said in plain words, exit 1, and STAYS in the undo file for the next try{tag}",
              "EXIT=1" in out and "could not be undone" in out and "Not undone: power" in out and any(c["Kind"] == "power" for c in left.get("changes", [])), out[-1500:])
        check(f"undo: the steps that could be undone were (tasks gone, startup switches back){tag}", not b.get()["tasks"] and approved(b.get(), "Teams") is None)
    finally:
        b.cleanup()

    # ---------------------------------------------------------------- 6. the Surface (no bot folder)
    b = Box(bot=False, surface=True)
    try:
        out, err = b.run(pwsh, ["-DryRun"], strict=strict)
        common("DryRun (Surface, no bot folder)", out, err)
        check(f"Surface: role found by itself (SURFACE), dark-screen steps shown, 'No bot folder here'{tag}", "SURFACE" in out and "No bot folder here" in out and "content adaptive brightness" in out
              and "Settings > System > Display > Brightness" in out and b.get() == b.w0, out[:2500])
        out, err = b.run(pwsh, [], strict=strict)
        common("full run (Surface)", out, err)
        w = b.get()
        ac, dc = w["power"]["ac"], w["power"]["dc"]
        g = lambda d, s: next((v for k, v in d.items() if k.startswith(PLAN + "|") and k.endswith("|" + s)), None)  # noqa: E731
        check(f"Surface: plan made from BALANCED (not High), CPU top speed 75% on AC and battery, fan first (1) on both{tag}", w["power"]["active"] == PLAN and g(ac, CPUMAX) == 75 and g(dc, CPUMAX) == 75
              and g(ac, COOL) == 1 and g(dc, COOL) == 1, (ac, dc))
        check(f"Surface: adaptive brightness off (AC and battery), brightness 100% plugged in, screen off 10 min (battery 5), battery saver does not dim{tag}",
              g(ac, ADAPT) == 0 and g(dc, ADAPT) == 0 and g(ac, BRIGHT) == 100 and g(ac, VIDEO) == 600 and g(dc, VIDEO) == 300
              and g(ac, "13d09884-f74e-474a-a852-b6bde8ad03a8") == 100 and g(dc, "13d09884-f74e-474a-a852-b6bde8ad03a8") == 100)
        check(f"Surface: no 'never sleeps' (it is a laptop; sleep / hibernate untouched), and the main-PC USB / PCI settings are not set{tag}", g(ac, SLEEP) is None and g(ac, HIBER) is None and g(ac, USB) is None)
        check(f"Surface: the health line says 'THIS PC (Surface) HEALTHY', the battery is shown, and it ends with the by-hand reminder for the dark screen{tag}",
              "THIS PC (Surface) HEALTHY: YES" in out and "80% plugged in" in out and "do the two tick boxes above by hand" in out, out[-1800:])
        cj = b.care_json()
        check(f"Surface: the health file goes to %LOCALAPPDATA%\\LiquidityEngine (no bot folder), role surface, level ok{tag}", cj and cj["role"] == "surface" and cj["level"] == "ok", cj)
        out, err = b.run(pwsh, ["-Undo"], strict=strict)
        common("-Undo (Surface)", out, err)
        check(f"Surface UNDO: the world is back exactly (both AC and DC values gone with the plan){tag}", b.get() == b.w0, {k: (b.w0[k], b.get().get(k)) for k in b.w0 if b.get().get(k) != b.w0[k]})
    finally:
        b.cleanup()
    if strict:
        return

    # ---------------------------------------------------------------- 7. role detection and -Role
    def role_of(kw, args, laptop=False):
        bx = Box(**kw)
        try:
            if laptop:
                w = bx.get()
                w["pc"] = {"model": "ThinkPad E14", "type": 2, "ramGB": 8}
                bx.put(w)
            out, err = bx.run(pwsh, ["-DryRun"] + args, strict=strict)
            return ("SURFACE" if "SURFACE (cooler" in out else "MAIN" if "MAIN PC (runs" in out else "?") if "EXIT=0" in out else "ERR " + err[-200:]
        finally:
            bx.cleanup()
    check("role: the bot folder present = MAIN PC", role_of(dict(bot=True), []) == "MAIN")
    check("role: the bot folder on a machine called Surface is still the MAIN PC (the bot is the rule)", role_of(dict(bot=True, surface=True), []) == "MAIN")
    check("role: no bot folder + a Surface model = SURFACE", role_of(dict(bot=False, surface=True), []) == "SURFACE")
    check("role: no bot folder + a small laptop (8 GB, not called Surface) = SURFACE", role_of(dict(bot=False), [], laptop=True) == "SURFACE")
    check("role: no bot folder + a desktop = MAIN PC (the main PC run from a download)", role_of(dict(bot=False), []) == "MAIN")
    check("role: -Role surface forces it on the bot PC; -Role main forces it on a Surface", role_of(dict(bot=True), ["-Role", "surface"]) == "SURFACE" and role_of(dict(bot=False, surface=True), ["-Role", "main"]) == "MAIN")

    # ---------------------------------------------------------------- 8. a Surface in the middle of market hours / downloaded alone has no bot to check
    b = Box(bot=False, surface=True)
    try:
        out, err = b.run(pwsh, ["-CheckOnly"], strict=strict, et="2026-11-02 10:00")
        check("Surface in market hours: no NinjaTrader / bot warnings (those are checks for the main PC only)", "THIS PC (Surface) HEALTHY: YES" in out and "Bot server" not in out)
    finally:
        b.cleanup()


def main() -> int:
    static()
    health()
    pwsh = find_pwsh()
    if pwsh:
        lint(pwsh)
        runs(pwsh, strict=False)
        runs(pwsh, strict=True)
    else:
        print("[SKIP] pwsh checks: pwsh not found (set LE_PWSH=<path> or install PowerShell 7)")
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


def test_pc_care():                         # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
