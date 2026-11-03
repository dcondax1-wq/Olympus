"""CLEAN_PC.bat + scripts/clean_pc.ps1 (the PC cleaner for the Surface and, standalone, the owner's main PC).

1. Static, always: the .bat has CRLF line endings and runs scripts\\clean_pc.ps1; the .ps1 is ASCII (Windows PowerShell
   5.1 reads a BOM-less file as ANSI); the lists never close or switch off NinjaTrader, python, Edge, OneDrive, Git, Claude.
2. With pwsh (PowerShell 7; LE_PWSH=<path> or pwsh on PATH, else skipped):
   - the 5.1 lint (tests/win_harness/lint51.ps1);
   - the rules, AST-loaded (tests/win_harness/clean_pc_rules.ps1): trading window 01:15-16:05 ET, the deep part (main PC
     without NinjaTrader any time), protected names, bot-folder detection, NinjaTrader workspace reading and advice,
     the PC report verdict;
   - real runs in a sandbox copy with Windows stubs (tests/win_harness/clean_pc_stubs.ps1): bot PC -DryRun in trading
     hours, main PC (standalone) -DryRun, -Report, the elevated part -DryRun on a Saturday and in trading hours, each
     also under Set-StrictMode -Version 2. Every run must end with exit 0, no PowerShell error, nothing changed
     (no HARNESS-CHANGE line, an old Temp file still there).

3. The v2 deep tune (scripts/pc_tune.ps1, scripts/pc_keeper.ps1, UNDO_PC_TUNE.bat), with pwsh:
   - rules, AST-loaded (tests/win_harness/pc_tune_rules.ps1): never a security / update / network service, Defender
     excludes only data folders, the PC kind and heat cap, SysMain / page file by RAM, the guard, the keeper never lowers
     NinjaTrader or python, the health score;
   - runs against a fake Windows whose changes really land in a JSON world (tests/win_harness/pc_tune_world.ps1):
     -DryRun and trading hours change nothing; apply changes what it should; a second apply keeps the first before-values;
     -Undo -DryRun changes nothing; -Undo puts the world back EXACTLY as it was; a failed undo step stays in the undo
     file (exit 1); the main PC (desktop, standalone) keeps Xbox / SysMain, gets no CPU cap and no bot folders excluded;
     the weekly care refuses in trading hours; the keeper dry run; CLEAN_PC -Undo hands over to the tune's undo.

  python -X utf8 -m tests.test_clean_pc          (about 1-2 min with pwsh)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import copy
import json
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARN = os.path.join(ROOT, "tests", "win_harness")
PS1 = os.path.join(ROOT, "scripts", "clean_pc.ps1")
BAT = os.path.join(ROOT, "CLEAN_PC.bat")
TUNE = os.path.join(ROOT, "scripts", "pc_tune.ps1")
KEEPER = os.path.join(ROOT, "scripts", "pc_keeper.ps1")
UNDO_BAT = os.path.join(ROOT, "UNDO_PC_TUNE.bat")
ADMIN_EXPR = ("([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole("
              "[Security.Principal.WindowsBuiltInRole]::Administrator)")
RES: list[bool] = []

WORKSPACE = """<NinjaTrader><Chart><Bars><Instrument>MNQ 12-26</Instrument><DaysBack>30</DaysBack>
<IsTickReplay>false</IsTickReplay></Bars><Indicator type="NinjaTrader.NinjaScript.Indicators.LE_BarFeed" /></Chart>
<Chart><Bars><Instrument>NQ 12-26</Instrument><DaysBack>90</DaysBack><IsTickReplay>true</IsTickReplay></Bars></Chart></NinjaTrader>
"""


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:1500]})" if detail and not cond else ""))
    return bool(cond)


def ps_list(code: str, var: str) -> list[str]:
    m = re.search(r"^\$" + var + r"\s*=\s*@\((.*?)\)\s*$", code, re.S | re.M)
    return re.findall(r"'([^']*)'", m.group(1)) if m else []


# ============================================================================================== static
def static():
    bat = open(BAT, "rb").read()
    check("CLEAN_PC.bat: CRLF line endings", b"\n" not in bat.replace(b"\r\n", b"") and bat.endswith(b"\r\n"))
    check("CLEAN_PC.bat: runs scripts\\clean_pc.ps1 and pauses on the same line",
          re.search(rb"powershell .*scripts\\clean_pc\.ps1\".*& pause", bat) is not None)
    raw = open(PS1, "rb").read()
    try:
        raw.decode("ascii")
        ok = True
    except UnicodeDecodeError:
        ok = raw.startswith(b"\xef\xbb\xbf")
    check("clean_pc.ps1: ASCII (or UTF-8 with BOM)", ok)
    code = raw.decode("utf-8", "replace")
    protect = ps_list(code, "Protect")
    close = [c.lower() for c in ps_list(code, "CloseProcs")]
    startup = ps_list(code, "StartupOff")
    check("lists read (Protect, CloseProcs, StartupOff)", protect and close and startup, (len(protect), len(close), len(startup)))
    check("Obsidian (the owner's vault, 2026-11-03): never closed, never switched off at sign-in",
          "obsidian" not in close and "obsidian" not in [x.lower() for x in startup])
    for must in ("ninjatrader", "python", "onedrive", "claude", "git", "liquidity", "obsidian"):
        check(f"protected: {must}", must in protect)
    keep = ["ninjatrader", "python", "pythonw", "msedge", "onedrive", "claude", "git", "explorer", "powershell", "pwsh", "obsidian"]
    check("never closed: NinjaTrader, python, Edge, OneDrive, Claude, Git, Explorer, PowerShell", not set(keep) & set(close),
          set(keep) & set(close))
    check("switches: -Standalone, -Report, -DryRun", all(re.search(r"\[switch\]\$" + s, code) for s in ("Standalone", "Report", "DryRun")))
    check("NinjaTrader is only read (no Stop-Process / kill on NinjaTrader)",
          not re.search(r"(?i)(Stop-Process|taskkill)[^\n]*ninja", code))
    check("clean_pc.ps1: -Undo switch hands over to pc_tune.ps1 -Undo", re.search(r"\[switch\]\$Undo", code)
          and re.search(r"& \$tune -Undo", code))
    ub = open(UNDO_BAT, "rb").read()
    check("UNDO_PC_TUNE.bat: CRLF line endings, ASCII", b"\n" not in ub.replace(b"\r\n", b"") and ub.endswith(b"\r\n")
          and all(c < 128 for c in ub))
    check("UNDO_PC_TUNE.bat: runs scripts\\clean_pc.ps1 -Undo (Obsidian back on + the tune's undo), pauses on the same line",
          re.search(rb"powershell .*-ExecutionPolicy Bypass .*scripts\\clean_pc\.ps1\" -Undo & echo\. & pause", ub) is not None
          and b"/dev/" not in ub)
    for f in (TUNE, KEEPER):
        raw = open(f, "rb").read()
        check(f"{os.path.basename(f)}: ASCII", all(c < 128 for c in raw))
        txt = raw.decode("ascii", "replace")
        body = re.sub(r"<#.*?#>", "", txt, flags=re.S)
        check(f"{os.path.basename(f)}: never closes NinjaTrader or python (no Stop-Process / taskkill at all)",
              not re.search(r"(?i)\b(Stop-Process|taskkill)\b", body))
        check(f"{os.path.basename(f)}: no download, no third-party binary (no Invoke-WebRequest / RestMethod / BITS / curl)",
              not re.search(r"(?i)(Invoke-WebRequest|Invoke-RestMethod|Start-BitsTransfer|DownloadFile|\bcurl\b|\bwget\b)", body))
        check(f"{os.path.basename(f)}: never Realtime or High priority", not re.search(r"(?i)'(RealTime|High)'", body))
    tune = open(TUNE, encoding="ascii").read()
    check("pc_tune.ps1: switches -Undo, -DryRun, -Maintenance, -Standalone",
          all(re.search(r"\[switch\]\$" + x, tune) for x in ("Undo", "DryRun", "Maintenance", "Standalone")))
    check("pc_tune.ps1: every change is recorded (Add-Change) before it is made",
          tune.count("Add-Change ") >= 12 and "function Add-Change" in tune)
    check("pc_tune.ps1: never writes into NinjaTrader's folder (only reads it; Defender exclusions point at it)",
          not re.search(r"(?i)(Set-Content|Copy-Item|Remove-Item|Move-Item|Out-File)[^\n]*\$nt", tune))


# ============================================================================================== pwsh
def find_pwsh() -> str | None:
    p = os.environ.get("LE_PWSH") or shutil.which("pwsh") or ("/usr/local/bin/pwsh" if os.path.exists("/usr/local/bin/pwsh") else None)
    return p if p and os.path.exists(p) else None


def lint(pwsh: str):
    r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-File", os.path.join(HARN, "lint51.ps1"), PS1, TUNE, KEEPER],
                       capture_output=True, text=True, timeout=120)
    found = [ln for ln in r.stdout.splitlines() if ln.strip()]
    check("5.1 lint: no PowerShell-7-only syntax, parameters or encodings", r.returncode == 0 and not found, found or r.stderr)


def tune_rules(pwsh: str):
    r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-File", os.path.join(HARN, "pc_tune_rules.ps1"), "-Tune", TUNE,
                        "-Keeper", KEEPER, "-Clean", PS1], capture_output=True, text=True, timeout=120)
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS ", "FAIL "))]
    check("tune rules ran (AST-loaded functions)", r.returncode == 0 and len(lines) >= 40 and not r.stderr.strip(),
          (r.returncode, len(lines), r.stderr[-800:], r.stdout[-800:]))
    for ln in lines:
        check("tune rule: " + ln[5:], ln.startswith("PASS "))


def rules(pwsh: str):
    tmp = tempfile.mkdtemp(prefix="le_clean_rules_")
    try:
        r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-File", os.path.join(HARN, "clean_pc_rules.ps1"), "-Script", PS1, "-Tmp", tmp],
                           capture_output=True, text=True, timeout=120)
        lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS ", "FAIL "))]
        check("rules ran (AST-loaded functions)", r.returncode == 0 and len(lines) >= 40 and not r.stderr.strip(),
              (r.returncode, len(lines), r.stderr[-800:]))
        for ln in lines:
            check("rule: " + ln[5:], ln.startswith("PASS "))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class Box:
    """A sandbox: the bot folder (server.py + engine/ninjatrader.py) or a bare PC_KIT folder, fake Temp / AppData /
    a NinjaTrader 8 folder inside a fake OneDrive with one workspace."""

    def __init__(self, bot: bool):
        self.dir = tempfile.mkdtemp(prefix="le_clean_")
        self.root = os.path.join(self.dir, "LiquidityEngine" if bot else "PC_KIT")
        os.makedirs(os.path.join(self.root, "scripts"))
        shutil.copy(PS1, os.path.join(self.root, "scripts", "clean_pc.ps1"))
        shutil.copy(BAT, os.path.join(self.root, "CLEAN_PC.bat"))
        shutil.copy(UNDO_BAT, os.path.join(self.root, "UNDO_PC_TUNE.bat"))
        shutil.copy(KEEPER, os.path.join(self.root, "scripts", "pc_keeper.ps1"))
        # the Administrator test is a static .NET call no stub can replace: it reads LE_T_ELEVATED here
        src = open(TUNE, encoding="utf-8").read().replace(ADMIN_EXPR, "($env:LE_T_ELEVATED -eq '1')")
        open(os.path.join(self.root, "scripts", "pc_tune.ps1"), "w", encoding="utf-8").write(src)
        if bot:
            os.makedirs(os.path.join(self.root, "engine"))
            os.makedirs(os.path.join(self.root, "data"))
            open(os.path.join(self.root, "server.py"), "w").write("#\n")
            open(os.path.join(self.root, "engine", "ninjatrader.py"), "w").write("#\n")
        self.temp = os.path.join(self.dir, "Temp")
        os.makedirs(self.temp)
        self.old = os.path.join(self.temp, "old.tmp")
        open(self.old, "w").write("x" * 1000)
        old_t = time.time() - 30 * 86400
        os.utime(self.old, (old_t, old_t))
        self.nt = os.path.join(self.dir, "OneDrive", "Documents", "NinjaTrader 8")
        for sub in ("workspaces", "incoming", "outgoing", "log", os.path.join("db", "tick"), os.path.join("db", "minute")):
            os.makedirs(os.path.join(self.nt, sub))
        open(os.path.join(self.nt, "workspaces", "Main.xml"), "w").write(WORKSPACE)
        open(os.path.join(self.nt, "workspaces", "_Workspaces.xml"), "w").write("<Workspaces />")
        oldlog = os.path.join(self.nt, "log", "log.20260101.00001.txt")
        open(oldlog, "w").write("x")
        os.utime(oldlog, (old_t, old_t))
        self.oldlog = oldlog
        for d in ("AppData", "LocalAppData", "home"):
            os.makedirs(os.path.join(self.dir, d))

    def run(self, pwsh: str, args: list[str], et: str, strict: bool = False, world: str | None = None,
            script: str = "clean_pc.ps1", elevated: bool = False):
        env = dict(os.environ, TEMP=self.temp, ProgramData=os.path.join(self.dir, "ProgramData"),
                   LE_T_ELEVATED="1" if elevated else "0", LE_T_WORLD=world or "", TMP=self.temp, APPDATA=os.path.join(self.dir, "AppData"),
                   LOCALAPPDATA=os.path.join(self.dir, "LocalAppData"), HOME=os.path.join(self.dir, "home"),
                   OneDrive=os.path.join(self.dir, "OneDrive"), NINJATRADER_FOLDER=self.nt, COMPUTERNAME="TESTPC",
                   LE_T_ET=et, LE_T_STRICT="1" if strict else "0")
        script = os.path.join(self.root, "scripts", script)
        stubs = os.path.join(HARN, "pc_tune_world.ps1" if world else "clean_pc_stubs.ps1")
        cmd = (f". '{stubs}'; & '{script}' {' '.join(args)}; "
               "[Console]::WriteLine('EXIT=' + $LASTEXITCODE)")
        r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-NonInteractive", "-Command", cmd], capture_output=True, text=True,
                           timeout=180, env=env, cwd=self.dir)
        return r.stdout, r.stderr

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def runs(pwsh: str, strict: bool):
    tag = " [StrictMode 2]" if strict else ""
    mon10, mon17, sat = "2026-11-02 10:00", "2026-11-02 17:00", "2026-11-07 10:00"

    def common(name, out, err, box):
        check(f"{name}: exit 0{tag}", "EXIT=0" in out, out[-600:])
        check(f"{name}: no PowerShell error{tag}", not err.strip(), err[-1200:])
        check(f"{name}: changed nothing (no delete / close / service / app change){tag}", "HARNESS-CHANGE" not in out and "HARNESS-REG" not in out,
              [ln for ln in out.splitlines() if "HARNESS-" in ln][:5])
        check(f"{name}: the old Temp file and the old NinjaTrader log are still there{tag}",
              os.path.exists(box.old) and os.path.exists(box.oldlog))

    bot = Box(bot=True)
    try:
        out, err = bot.run(pwsh, ["-DryRun"], mon10, strict)
        common("bot PC -DryRun, Mon 10:00 ET", out, err, bot)
        check(f"bot PC: not standalone{tag}", "STANDALONE" not in out)
        check(f"bot PC: deep part waits in trading hours{tag}", "the deep part waits so it never slows the bot" in out, out[-1500:])
        check(f"bot PC: health score before and after, the tune state in the report{tag}", "Health score before: " in out
              and re.search(r"Health   : after  \d+/100", out) and "Tune     : not applied yet" in out, out[-1500:])
        check(f"bot PC: the old Temp file is counted{tag}", re.search(r"Your Temp folder: 1 files", out), out)
        check(f"bot PC: NinjaTrader check ran{tag}", "NinjaTrader check" in out and "Workspace 'Main'" in out, out)
        check(f"bot PC: NinjaTrader folder in OneDrive is flagged{tag}", "It is inside OneDrive" in out)
        check(f"bot PC: Tick Replay and 90 days flagged, the 30-day bot chart left alone{tag}",
              "Tick Replay is ON" in out and "(most 90)" in out and "keep it at 30" not in out, out)
        check(f"bot PC: ATI looks on (incoming / outgoing folders){tag}", "ATI (automated trading interface): looks on" in out)
        rep = os.path.join(bot.root, "PC_REPORT-TESTPC.txt")
        check(f"bot PC: PC report written{tag}", os.path.exists(rep))
        if os.path.exists(rep):
            txt = open(rep, encoding="utf-8-sig").read()
            for k in ("CPU      : Intel(R) Core(TM) i5-1035G4", "Memory   : 4 GB", "1 of 1 slots", "NVMe", "Graphics : Intel",
                      "Windows  : Microsoft Windows 11 Home", "Power    :", "Start at sign-in (2)", "Verdict  : WEAK"):
                check(f"PC report has '{k}'{tag}", k in txt, txt)
        check(f"bot PC -DryRun: no PC_KIT copied, no workspace backup{tag}",
              not os.path.exists(os.path.join(bot.dir, "OneDrive", "PC_KIT")) and
              not any(n.startswith("nt_workspaces") for n in os.listdir(os.path.join(bot.root, "logs"))))
        out, err = bot.run(pwsh, ["-AdminPart", "-DryRun"], mon10, strict)
        common("bot PC deep part -DryRun, Mon 10:00 ET", out, err, bot)
        check(f"bot PC deep part: refuses in trading hours{tag}", "the deep part waits" in out and "Windows Search" not in out, out)
        out, err = bot.run(pwsh, ["-AdminPart", "-DryRun"], sat, strict)
        common("bot PC deep part -DryRun, Saturday", out, err, bot)
        check(f"bot PC deep part: runs on Saturday (dry run){tag}", "Windows Search indexing off" in out and "Defender" in out, out)
        check(f"bot PC deep part: the v2 deep tune plans (surface: CPU cap, no change){tag}", "DEEP TUNE v2: surface, bot PC" in out
              and "CPU capped at 2800 MHz" in out and "Would add the task LiquidityEngine-Keeper" in out, out[-2500:])
        # a real run (stubs stand in for Windows): the kit for the main PC and the workspace backup appear, NinjaTrader's
        # own files are unchanged, the elevated part is only asked for (UAC stub)
        ws = os.path.join(bot.nt, "workspaces", "Main.xml")
        out, err = bot.run(pwsh, [], sat, strict)
        check(f"bot PC real run (stubbed): exit 0, no PowerShell error{tag}", "EXIT=0" in out and not err.strip(), err[-1200:] or out[-600:])
        kitd = os.path.join(bot.dir, "OneDrive", "PC_KIT")
        check(f"bot PC real run: PC_KIT in OneDrive (CLEAN_PC.bat + scripts/clean_pc.ps1){tag}",
              os.path.exists(os.path.join(kitd, "CLEAN_PC.bat")) and os.path.exists(os.path.join(kitd, "scripts", "clean_pc.ps1")), out[-800:])
        check(f"bot PC real run: PC_KIT also has the deep tune (pc_tune.ps1, pc_keeper.ps1, UNDO_PC_TUNE.bat){tag}",
              all(os.path.exists(os.path.join(kitd, *x)) for x in (("scripts", "pc_tune.ps1"), ("scripts", "pc_keeper.ps1"), ("UNDO_PC_TUNE.bat",))))
        bk = [n for n in os.listdir(os.path.join(bot.root, "logs")) if n.startswith("nt_workspaces")]
        check(f"bot PC real run: workspaces backed up{tag}", bk and os.path.exists(os.path.join(bot.root, "logs", bk[0], "Main.xml")))
        check(f"bot PC real run: NinjaTrader's workspace unchanged{tag}", open(ws).read() == WORKSPACE)
        check(f"bot PC real run: the deep part is started elevated (UAC){tag}", "HARNESS-CHANGE Start-Process powershell.exe" in out, out[-800:])
    finally:
        bot.cleanup()

    kit = Box(bot=False)
    try:
        out, err = kit.run(pwsh, ["-DryRun"], mon10, strict)
        common("main PC (no bot folder) -DryRun, Mon 10:00 ET", out, err, kit)
        check(f"main PC: standalone detected{tag}", "STANDALONE" in out, out[:600])
        check(f"main PC: deep part allowed (no NinjaTrader open){tag}", "Would ask Windows for Administrator" in out, out[-1500:])
        check(f"main PC: report says standalone{tag}",
              "standalone (no bot folder)" in open(os.path.join(kit.root, "PC_REPORT-TESTPC.txt"), encoding="utf-8-sig").read())
        out, err = kit.run(pwsh, ["-Report"], mon10, strict)
        common("main PC -Report", out, err, kit)
        check(f"-Report: report + NinjaTrader check, no cleaning{tag}",
              "PC REPORT + NINJATRADER CHECK" in out and "NinjaTrader check" in out and "Junk files" not in out and "Start at sign-in" in out, out)
        out, err = kit.run(pwsh, ["-Standalone", "-DryRun", "-LightOnly"], mon17, strict)
        common("-Standalone -LightOnly", out, err, kit)
        check(f"-LightOnly: no deep part{tag}", "Deep clean" not in out)
    finally:
        kit.cleanup()


# ============================================================================================== the deep tune, in a fake world
PLAN = "a1e5c0de-7a0e-4e51-9000-000000000001"
BALANCED, HIGH, ULTIMATE = "381b4222-f694-41f0-9621-a68e2a2b1d4b", "8c5e7fda-e8bf-4a96-9a85-cf8d6e58fbd0", "e9a42b02-d5df-448d-aa00-03f14749eb61"
EDGE = "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge"
NEVER = ["WinDefend", "mpssvc", "wuauserv", "Dnscache", "Dhcp", "WlanSvc", "BFE", "TabletInputService"]


def new_world(surface: bool) -> dict:
    svc = {n: {"start": "Automatic", "status": "Running"} for n in
           ["DiagTrack", "dmwappushservice", "MapsBroker", "Fax", "WMPNetworkSvc", "XblAuthManager", "XblGameSave",
            "XboxNetApiSvc", "XboxGipSvc", "SysMain", "Spooler"] + NEVER}
    svc["RemoteRegistry"] = {"start": "Disabled", "status": "Stopped"}          # already off: no change recorded
    svc["MapsBroker"] = {"start": "Manual", "status": "Stopped"}
    return {
        "reg": {f"{EDGE}|SleepingTabsEnabled": {"v": 0, "t": "DWord"}},       # the owner had sleeping tabs off: undo puts 0 back
        "svc": svc, "neverTouch": NEVER,
        "power": {"active": BALANCED, "schemes": [BALANCED, HIGH], "canDup": [BALANCED, HIGH] if surface else [BALANCED, HIGH, ULTIMATE], "ac": {}},
        "mm": False, "pf": {"auto": False, "max": 2048},
        "mp": ["C:\\Tools\\existing"], "failMpRemove": False,
        "pc": {"model": "Surface Pro 7" if surface else "OptiPlex 7070", "type": 2 if surface else 1, "ramGB": 3.6 if surface else 16},
        "printers": ["Microsoft Print to PDF"],
        "nics": ["Ethernet", "Wi-Fi"],
        "netadv": {"Ethernet|Energy Efficient Ethernet": {"v": "Enabled", "valid": ["Disabled", "Enabled"]},
                   "Ethernet|Jumbo Packet": {"v": "Disabled", "valid": ["Disabled", "9014"]}},
        "netpm": {"Wi-Fi": "Enabled", "Ethernet": "Disabled"},
        "tasks": {"Office Startup Boost": {"path": "\\Microsoft\\Office\\", "state": "Ready"}},
    }


def tune_runs(pwsh: str, strict: bool):
    tag = " [StrictMode 2]" if strict else ""
    mon10, sat = "2026-11-02 10:00", "2026-11-07 10:00"
    box = Box(bot=True)
    wpath = os.path.join(box.dir, "world.json")
    state = os.path.join(box.dir, "ProgramData", "LiquidityEngine", "pc_tune_state.json")

    def put(w):
        json.dump(w, open(wpath, "w"))

    def get():
        return json.load(open(wpath))

    def run(args, et=sat, script="pc_tune.ps1"):
        out, err = box.run(pwsh, args, et, strict, world=wpath, script=script, elevated=True)
        return out, err

    try:
        w0 = new_world(surface=True)
        put(copy.deepcopy(w0))
        out, err = run(["-DryRun"])
        check(f"tune -DryRun (Saturday): exit 0, no error, world unchanged, no undo file{tag}", "EXIT=0" in out and not err.strip()
              and get() == w0 and "HARNESS-CHANGE" not in out and not os.path.exists(state), err[-800:] or out[-1500:])
        out, err = run([], et=mon10)
        check(f"tune in trading hours (Mon 10:00 ET, bot PC): waits, world unchanged{tag}", "EXIT=0" in out and not err.strip()
              and "deep tune waits" in out and get() == w0 and not os.path.exists(state), err[-800:] or out[-800:])
        out, err = run([])
        w1 = get()
        check(f"tune apply (Saturday): exit 0, no PowerShell error{tag}", "EXIT=0" in out and not err.strip(), err[-1500:] or out[-1500:])
        check(f"tune apply: undo file written{tag}", os.path.exists(state))
        st = json.load(open(state, encoding="utf-8-sig")) if os.path.exists(state) else {"changes": []}
        n1 = len(st["changes"])
        check(f"tune apply: power plan made from Balanced and switched on, CPU capped at 2800 MHz, PCIe left alone (surface){tag}",
              w1["power"]["active"] == PLAN and PLAN in w1["power"]["schemes"]
              and w1["power"]["ac"].get(f"{PLAN}|54533251-82be-4824-96c1-47b60b740d00|75b0ae3f-bce0-45a7-8c89-c9611c25e100") == 2800
              and w1["power"]["ac"].get(f"{PLAN}|238c9fa8-0aad-41ed-83f4-97be242c8f20|29f6c1db-86da-48c5-9fdb-f2b67b1f44da") == 0
              and not any("ee12f906" in k for k in w1["power"]["ac"]), w1["power"])
        off = sorted(k for k, v in w1["svc"].items() if v["start"] == "Disabled")
        check(f"tune apply: telemetry, Xbox, SysMain (4 GB SSD), Spooler (no printer) off{tag}",
              set(off) >= {"DiagTrack", "dmwappushservice", "MapsBroker", "XblAuthManager", "XboxGipSvc", "SysMain", "Spooler", "Fax"}, off)
        check(f"tune apply: no never-list service touched{tag}", all(w1["svc"][n] == w0["svc"][n] for n in NEVER))
        exp = {os.path.join(box.nt, "db"), os.path.join(box.nt, "log"), os.path.join(box.root, "data"), os.path.join(box.root, "logs")}
        check(f"tune apply: Defender skips only NinjaTrader db/log and the bot's data/logs (trace absent: not added){tag}",
              set(w1["mp"]) == exp | {"C:\\Tools\\existing"}, w1["mp"])
        check(f"tune apply: compressed memory on, page file back to system managed (it was 2 GB by hand){tag}",
              w1["mm"] is True and w1["pf"]["auto"] is True)
        check(f"tune apply: Ethernet energy saving off, Wi-Fi not turned off to save power, other settings left{tag}",
              w1["netadv"]["Ethernet|Energy Efficient Ethernet"]["v"] == "Disabled" and w1["netadv"]["Ethernet|Jumbo Packet"]["v"] == "Disabled"
              and w1["netpm"]["Wi-Fi"] == "Disabled", (w1["netadv"], w1["netpm"]))
        check(f"tune apply: Edge startup boost off, sleeping tabs on (5 min), efficiency mode (surface){tag}",
              w1["reg"].get(f"{EDGE}|StartupBoostEnabled", {}).get("v") == 0 and w1["reg"][f"{EDGE}|SleepingTabsEnabled"]["v"] == 1
              and w1["reg"].get(f"{EDGE}|SleepingTabsTimeout", {}).get("v") == 300 and f"{EDGE}|EfficiencyMode" in w1["reg"])
        check(f"tune apply: Office startup boost task off{tag}", w1["tasks"]["Office Startup Boost"]["state"] == "Disabled")
        k = w1["tasks"].get("LiquidityEngine-Keeper", {})
        c = w1["tasks"].get("LiquidityEngine-WeeklyCare", {})
        check(f"tune apply: keeper task (no window, as the user, -Bot) + weekly care task (SYSTEM, -Maintenance){tag}",
              k.get("logon") == "S4U" and "-Bot" in k.get("args", "") and "logon" in k.get("triggers", [])
              and c.get("user") == "SYSTEM" and "-Maintenance" in c.get("args", "") and "-BotPc" in c.get("args", ""), (k, c))
        pd = os.path.join(box.dir, "ProgramData", "LiquidityEngine")
        check(f"tune apply: keeper and tune copied to ProgramData for the tasks{tag}",
              os.path.exists(os.path.join(pd, "pc_keeper.ps1")) and os.path.exists(os.path.join(pd, "scripts", "pc_tune.ps1")))
        check(f"tune apply: RemoteRegistry was already off: no change recorded{tag}",
              not any(ch.get("Id") == "svc|RemoteRegistry" for ch in st["changes"]))
        check(f"tune apply: the log explains the Defender trade-off{tag}", "Trade-off:" in out)
        # a second apply: nothing new recorded, the first before-values kept (power Before is still Balanced)
        out, err = run([])
        st2 = json.load(open(state, encoding="utf-8-sig"))
        pw = [ch for ch in st2["changes"] if ch["Id"] == "power|plan"]
        check(f"tune apply twice: exit 0, same changes, first before-values kept{tag}", "EXIT=0" in out and not err.strip()
              and len(st2["changes"]) == n1 and pw and pw[0]["Before"] == BALANCED, (len(st2["changes"]), n1, pw, err[-600:]))
        # undo
        w_before_undo = get()
        out, err = run(["-Undo", "-DryRun"], et=mon10)
        check(f"undo -DryRun: lists, changes nothing{tag}", "EXIT=0" in out and not err.strip() and get() == w_before_undo
              and "Would undo" in out and os.path.exists(state), err[-600:])
        out, err = run(["-Undo"], et=mon10)
        check(f"undo (allowed any time): exit 0, no error{tag}", "EXIT=0" in out and not err.strip(), err[-1500:] or out[-1500:])
        wu = get()
        diff = [k for k in w0 if w0[k] != wu.get(k)]
        check(f"undo: the world is back EXACTLY as before the tune{tag}", wu == w0, {k: (w0[k], wu.get(k)) for k in diff})
        check(f"undo: undo file archived, ProgramData copies removed{tag}", not os.path.exists(state)
              and any(n.startswith("pc_tune_state-undone-") for n in os.listdir(pd))
              and not os.path.exists(os.path.join(pd, "pc_keeper.ps1")) and not os.path.exists(os.path.join(pd, "scripts", "pc_tune.ps1")))
        out, err = run(["-Undo"], et=mon10)
        check(f"undo again: nothing to undo, exit 0{tag}", "EXIT=0" in out and "Nothing to undo" in out and not err.strip())
        # a failing undo step stays in the undo file, exit 1
        put(copy.deepcopy(w0))
        run([])
        w = get(); w["failMpRemove"] = True; put(w)
        out, err = run(["-Undo"])
        st3 = json.load(open(state, encoding="utf-8-sig")) if os.path.exists(state) else {"changes": []}
        check(f"undo with a failing step: exit 1, the failed ones stay in the undo file, the rest undone{tag}",
              "EXIT=1" in out and st3["changes"] and all(ch["Kind"] == "mpexcl" for ch in st3["changes"])
              and get()["power"]["active"] == BALANCED, (out[-800:], st3))
        w = get(); w["failMpRemove"] = False; put(w)
        out, err = run(["-Undo"])
        check(f"undo retried: exit 0, Defender back as before{tag}", "EXIT=0" in out and get()["mp"] == w0["mp"], out[-600:])
        # CLEAN_PC -Undo hands over, and switches Obsidian back on at sign-in if an older CLEAN_PC had switched it off
        sa = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\StartupApproved\\Run"
        w = get(); w["reg"][f"{sa}|Obsidian"] = {"v": [3, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8], "t": "Binary"}
        w["reg"][f"{sa}|Discord"] = {"v": [3, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8], "t": "Binary"}; put(w)
        out, err = run(["-Undo"], et=mon10, script="clean_pc.ps1")
        check(f"CLEAN_PC -Undo hands over to the tune's undo{tag}", "EXIT=0" in out and "UNDO DEEP TUNE" in out and not err.strip(), err[-600:] or out[-600:])
        r = get()["reg"]
        check(f"CLEAN_PC -Undo: Obsidian back on at sign-in, Discord left off{tag}",
              r[f"{sa}|Obsidian"]["v"][0] == 2 and r[f"{sa}|Discord"]["v"][0] == 3 and "Obsidian" in out, (r.get(f"{sa}|Obsidian"), out[-600:]))
        out, err = run(["-Undo", "-DryRun"], et=mon10, script="clean_pc.ps1")
        check(f"CLEAN_PC -Undo -DryRun: changes nothing{tag}", "EXIT=0" in out and "HARNESS-CHANGE" not in out and not err.strip(), out[-600:])
        # weekly care: trading hours refuse, Saturday dry run plans
        out, err = run(["-Maintenance"], et=mon10)
        check(f"weekly care in trading hours (bot PC): nothing done{tag}", "EXIT=0" in out and "nothing done" in out and "HARNESS-CHANGE" not in out
              and not err.strip(), err[-600:] or out[-600:])
        out, err = run(["-Maintenance", "-DryRun"])
        check(f"weekly care -DryRun Saturday: plans DISM + Defender, changes nothing{tag}", "EXIT=0" in out and "Would run a Defender quick scan" in out
              and "HARNESS-CHANGE" not in out and not err.strip(), err[-600:] or out[-600:])
        out, err = run(["-DryRun"], script="pc_keeper.ps1")
        check(f"keeper -DryRun: exit 0, no error{tag}", "EXIT=0" in out and not err.strip(), err[-600:])
    finally:
        box.cleanup()

    kit = Box(bot=False)
    wpath = os.path.join(kit.dir, "world.json")
    try:
        w0 = new_world(surface=False)
        json.dump(w0, open(wpath, "w"))
        out, err = kit.run(pwsh, [], mon10, strict, world=wpath, script="pc_tune.ps1", elevated=True)
        w1 = json.load(open(wpath))
        check(f"main PC tune (no NinjaTrader open, Mon 10:00): runs, exit 0{tag}", "EXIT=0" in out and not err.strip()
              and "main PC (business mode)" in out, err[-1500:] or out[-1500:])
        check(f"main PC: desktop plan from Ultimate, no CPU cap, PCIe power saving off{tag}",
              w1["power"]["active"] == PLAN and not any("75b0ae3f" in k for k in w1["power"]["ac"])
              and any("ee12f906" in k for k in w1["power"]["ac"]) and "Ultimate" in out, w1["power"])
        check(f"main PC: Xbox services and SysMain (16 GB) kept, telemetry off{tag}",
              w1["svc"]["XblAuthManager"]["start"] == "Automatic" and w1["svc"]["SysMain"]["start"] == "Automatic"
              and w1["svc"]["DiagTrack"]["start"] == "Disabled")
        check(f"main PC: Defender skips only NinjaTrader's folders (no bot folder){tag}",
              set(w1["mp"]) == {os.path.join(kit.nt, "db"), os.path.join(kit.nt, "log"), "C:\\Tools\\existing"}, w1["mp"])
        k = w1["tasks"].get("LiquidityEngine-Keeper", {})
        c = w1["tasks"].get("LiquidityEngine-WeeklyCare", {})
        check(f"main PC: keeper without -Bot, weekly care with -Standalone{tag}", k and "-Bot" not in k.get("args", "")
              and "-Standalone" in c.get("args", "") and "-BotPc" not in c.get("args", ""), (k, c))
        # the weekly care's copy lives in ProgramData (no bot folder next to it): -BotPc keeps the strict bot guard
        out, err = kit.run(pwsh, ["-Maintenance", "-BotPc"], mon10, strict, world=wpath, script="pc_tune.ps1", elevated=True)
        check(f"weekly care copy with -BotPc (no bot folder, no NinjaTrader, Mon 10:00): still waits{tag}",
              "EXIT=0" in out and "nothing done" in out and "HARNESS-CHANGE" not in out and not err.strip(), err[-600:] or out[-600:])
        out, err = kit.run(pwsh, ["-Undo"], mon10, strict, world=wpath, script="pc_tune.ps1", elevated=True)
        check(f"main PC undo: world back exactly{tag}", "EXIT=0" in out and json.load(open(wpath)) == w0, out[-1000:])
    finally:
        kit.cleanup()


def main() -> int:
    static()
    pwsh = find_pwsh()
    if pwsh:
        lint(pwsh)
        rules(pwsh)
        tune_rules(pwsh)
        runs(pwsh, strict=False)
        runs(pwsh, strict=True)
        tune_runs(pwsh, strict=False)
        tune_runs(pwsh, strict=True)
    else:
        print("[SKIP] pwsh checks: pwsh not found (set LE_PWSH=<path> or install PowerShell 7)")
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


def test_clean_pc():                      # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
