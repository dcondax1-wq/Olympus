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

  python -X utf8 -m tests.test_clean_pc          (about 20 s with pwsh)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARN = os.path.join(ROOT, "tests", "win_harness")
PS1 = os.path.join(ROOT, "scripts", "clean_pc.ps1")
BAT = os.path.join(ROOT, "CLEAN_PC.bat")
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
    for must in ("ninjatrader", "python", "onedrive", "claude", "git", "liquidity"):
        check(f"protected: {must}", must in protect)
    keep = ["ninjatrader", "python", "pythonw", "msedge", "onedrive", "claude", "git", "explorer", "powershell", "pwsh"]
    check("never closed: NinjaTrader, python, Edge, OneDrive, Claude, Git, Explorer, PowerShell", not set(keep) & set(close),
          set(keep) & set(close))
    check("switches: -Standalone, -Report, -DryRun", all(re.search(r"\[switch\]\$" + s, code) for s in ("Standalone", "Report", "DryRun")))
    check("NinjaTrader is only read (no Stop-Process / kill on NinjaTrader)",
          not re.search(r"(?i)(Stop-Process|taskkill)[^\n]*ninja", code))


# ============================================================================================== pwsh
def find_pwsh() -> str | None:
    p = os.environ.get("LE_PWSH") or shutil.which("pwsh") or ("/usr/local/bin/pwsh" if os.path.exists("/usr/local/bin/pwsh") else None)
    return p if p and os.path.exists(p) else None


def lint(pwsh: str):
    r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-File", os.path.join(HARN, "lint51.ps1"), PS1],
                       capture_output=True, text=True, timeout=120)
    found = [ln for ln in r.stdout.splitlines() if ln.strip()]
    check("5.1 lint: no PowerShell-7-only syntax, parameters or encodings", r.returncode == 0 and not found, found or r.stderr)


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
        if bot:
            os.makedirs(os.path.join(self.root, "engine"))
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

    def run(self, pwsh: str, args: list[str], et: str, strict: bool = False):
        env = dict(os.environ, TEMP=self.temp, TMP=self.temp, APPDATA=os.path.join(self.dir, "AppData"),
                   LOCALAPPDATA=os.path.join(self.dir, "LocalAppData"), HOME=os.path.join(self.dir, "home"),
                   OneDrive=os.path.join(self.dir, "OneDrive"), NINJATRADER_FOLDER=self.nt, COMPUTERNAME="TESTPC",
                   LE_T_ET=et, LE_T_STRICT="1" if strict else "0")
        script = os.path.join(self.root, "scripts", "clean_pc.ps1")
        cmd = (f". '{os.path.join(HARN, 'clean_pc_stubs.ps1')}'; & '{script}' {' '.join(args)}; "
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
        # a real run (stubs stand in for Windows): the kit for the main PC and the workspace backup appear, NinjaTrader's
        # own files are unchanged, the elevated part is only asked for (UAC stub)
        ws = os.path.join(bot.nt, "workspaces", "Main.xml")
        out, err = bot.run(pwsh, [], sat, strict)
        check(f"bot PC real run (stubbed): exit 0, no PowerShell error{tag}", "EXIT=0" in out and not err.strip(), err[-1200:] or out[-600:])
        kitd = os.path.join(bot.dir, "OneDrive", "PC_KIT")
        check(f"bot PC real run: PC_KIT in OneDrive (CLEAN_PC.bat + scripts/clean_pc.ps1){tag}",
              os.path.exists(os.path.join(kitd, "CLEAN_PC.bat")) and os.path.exists(os.path.join(kitd, "scripts", "clean_pc.ps1")), out[-800:])
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


def main() -> int:
    static()
    pwsh = find_pwsh()
    if pwsh:
        lint(pwsh)
        rules(pwsh)
        runs(pwsh, strict=False)
        runs(pwsh, strict=True)
    else:
        print("[SKIP] pwsh checks: pwsh not found (set LE_PWSH=<path> or install PowerShell 7)")
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


def test_clean_pc():                      # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
