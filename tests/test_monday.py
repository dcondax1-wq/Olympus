"""MONDAY SETUP + START BOT walked as Windows would run them, with fakes (night-mondaysim 2026-11-23). Nothing runs for real:
no UPDATE, no clock change, no bot start, no alert, never armed.

    python -X utf8 -m tests.test_monday        (~5 s)

a. engine/monday.run with a fake PC: the order (update, clock, start, alert), one plain line each, safe twice, an
   administrator window skips update + start, a refused clock still runs the rest.
b. UPDATE.bat's exit code read right: 1 = "[FIX] did not go through" (it used to exit 0 always: a failed update said OK),
   2 = updated with red health lines.
c. No traceback in the owner's window: monday.main and engine.go.main turn a crash / Ctrl+C / closed input into one plain line.
d. Paths with spaces, ( ) & and ' (OneDrive, "Bot (1)", O'Neil): cmd /d /c call "<path>" as one string; PowerShell
   single quotes doubled.
e. START BOT from MONDAY SETUP: --no-pull (step 1 already updated, with its never-in-a-trade guard).
f. The .bat files, statically: every python module / file / flag they call exists (argparse --help), the errorlevel checks
   and plain [FIX] lines, exit codes passed back, CRLF kept, no hardcoded machine paths, every path quoted.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import monday as M  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)) if info and not ok else ''}")
    RES.append(bool(ok))


class Fake:
    def __init__(self, admin=False, upd=0, heads=("aaaaaaa1", "aaaaaaa1"), task=(False, True), clock_rc=0, start_rc=0, alert_rc=0):
        self.admin, self.upd, self.heads, self.task, self.clock_rc = admin, upd, list(heads), list(task), clock_rc
        self.start_rc, self.alert_rc, self.calls = start_rc, alert_rc, []

    def is_admin(self): return self.admin
    def head(self): return self.heads.pop(0) if self.heads else None
    def update(self): self.calls.append("update"); return self.upd
    def clock_task(self): return self.task.pop(0) if len(self.task) > 1 else self.task[0]
    def fix_clock(self, elevated): self.calls.append(("clock", elevated)); return self.clock_rc
    def start(self): self.calls.append("start"); return self.start_rc
    def alert_test(self): self.calls.append("alert"); return self.alert_rc
    def keepalive(self): return {"on": ["Zlarior"], "off": []}
    def recovery(self): return ["[OK] the bot comes back by itself after a crash"]


def run(f):
    out = []
    r = M.run(f, out=out.append)
    return r, "\n".join(out)


def part_a():
    f = Fake()
    r, txt = run(f)
    check("a1. order: update, clock, start, alert; one line each, all OK", r["order"] == ["update", "clock", "start", "alert"]
          and [n for n, _o, _t in r["steps"]] == ["1/4 Update", "2/4 Clock", "3/4 Start", "4/4 Alert test"]
          and all(o for _n, o, _t in r["steps"]) and "Keep-alive ON for: Zlarior" in txt, (r, txt))
    f2 = Fake(task=(True,))
    r2, _ = run(f2)
    check("a2. twice: the clock task is there -> clock skipped ([OK] already fixed), nothing else changes", ("clock", False) not in f2.calls
          and r2["steps"][1][1] is True and "already fixed" in r2["steps"][1][2], r2)
    f3 = Fake(admin=True)
    r3, txt3 = run(f3)
    check("a3. administrator window: update + start skipped (the bot never runs elevated), clock elevated, alert sent",
          "update" not in f3.calls and "start" not in f3.calls and ("clock", True) in f3.calls and "alert" in f3.calls
          and "double-click MONDAY_SETUP.bat normally" in txt3, (f3.calls, txt3))
    f4 = Fake(task=(False, False), clock_rc=1)
    r4, txt4 = run(f4)
    check("a4. UAC 'No': clock [FIX] says FIX_CLOCK.bat > Run as administrator; start and alert still run",
          r4["steps"][1][1] is False and "FIX_CLOCK.bat" in r4["steps"][1][2] and "start" in f4.calls and "alert" in f4.calls, (r4, f4.calls))
    f5 = Fake(start_rc=1, alert_rc=1)
    r5, _ = run(f5)
    check("a5. start / alert failing: plain [FIX] lines, main would exit 1", r5["steps"][2][1] is False and r5["steps"][3][1] is False
          and M.main(run_fn=lambda: r5, out=lambda *_: None) == 1)


def part_b():
    r, _ = run(Fake(upd=1))
    check("b1. UPDATE.bat exit 1 (pull failed), same version -> '[FIX] did not go through' (not OK)", r["steps"][0][1] is False
          and "did not go through" in r["steps"][0][2], r["steps"][0])
    r, _ = run(Fake(upd=2))
    check("b2. exit 2 (updated, red health lines) -> OK with 'do those after the start'", r["steps"][0][1] is True
          and "red lines" in r["steps"][0][2], r["steps"][0])
    r, _ = run(Fake(upd=0, heads=("aaaaaaa1", "bbbbbbb2")))
    check("b3. new version -> 'now on the newest version (bbbbbbb)'", "bbbbbbb" in r["steps"][0][2], r["steps"][0])


def part_c():
    out = []
    log = os.path.join(ROOT, "logs", "monday_crash.log")
    had = os.path.exists(log)
    def boom():
        raise RuntimeError("x")
    rc = M.main(run_fn=boom, out=out.append)
    check("c1. monday.main: a crash = one plain [FIX] line + logs/monday_crash.log, exit 1, no traceback text",
          rc == 1 and len(out) == 1 and "[FIX] MONDAY SETUP hit a problem (RuntimeError)" in out[0] and "Traceback" not in out[0]
          and "monday_crash.log" in out[0], out)
    if not had and os.path.exists(log):
        os.remove(log)
    out = []
    def ctrl_c():
        raise KeyboardInterrupt
    check("c2. Ctrl+C / closed input: 'stopped before the end ... again'", M.main(run_fn=ctrl_c, out=out.append) == 1
          and "stopped before the end" in out[0], out)
    p = subprocess.run([sys.executable, "-X", "utf8", "-m", "engine.go", "--dry-run"], cwd=ROOT, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=120)
    both = p.stdout + p.stderr
    check("c3. START BOT (engine.go --dry-run) with its input closed: one plain [FIX] line, no traceback, exit 1",
          p.returncode == 1 and "[FIX] START BOT stopped before the end" in both and "Traceback" not in both, both[-400:])


def part_d():
    ugly = r"C:\Users\O'Neil\OneDrive - Personal\Bot (1) & co\UPDATE.bat"
    a = M.bat_cmd(ugly)
    check("d1. bat_cmd = cmd /d /c call <path>; on Windows ONE string with the whole path in quotes", a == ["cmd", "/d", "/c", "call", ugly]
          and M.cmd_line(a, nt=True) == 'cmd /d /c call "' + ugly + '"' and M.cmd_line(a, nt=False) == a)
    seen = {}
    real_run = subprocess.run
    def cap(cmd, **kw):
        seen["cmd"] = cmd
        class R: returncode = 0
        return R()
    old_root = M.ROOT
    try:
        M.subprocess.run = cap
        M.ROOT = r"C:\Users\O'Neil\OneDrive - Personal\Bot (1)"
        M.Real().fix_clock(False)
        ps = seen["cmd"][-1]
        check("d2. clock via UAC: the script path's ' doubled inside PowerShell's single quotes",
              "O''Neil" in ps and "Bot (1)" in ps and ps.count("'") % 2 == 0, ps)
        M.Real(py="python").start()
        check("e1. START BOT from MONDAY SETUP runs engine.go --no-pull (one update, with UPDATE.bat's trade guard)",
              seen["cmd"] == ["python", "-X", "utf8", "-m", "engine.go", "--no-pull"], seen["cmd"])
        M.Real().update()
        u = seen["cmd"]
        check("e2. the update step runs UPDATE.bat through cmd /d /c call (input NUL)", (isinstance(u, list) and u[:4] == ["cmd", "/d", "/c", "call"]
              and u[-1].endswith("UPDATE.bat")) or (isinstance(u, str) and u.startswith('cmd /d /c call "')), u)
    finally:
        M.subprocess.run = real_run
        M.ROOT = old_root
    from engine import trade_home as T
    ran = []
    T.run_bat("UPDATE.bat", run=lambda argv: ran.append(argv) or 0)
    check("d3. TRADING HOME runs its .bat files the same way (cmd /d /c call <path>)", ran and ran[0][:4] == ["cmd", "/d", "/c", "call"]
          and ran[0][-1].endswith("UPDATE.bat"), ran)


def _read(name):
    return open(os.path.join(ROOT, name), "rb").read().decode("utf-8")


def _help(mod):
    p = subprocess.run([sys.executable, "-X", "utf8", "-m", mod, "--help"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    return p.stdout + p.stderr


def part_f():
    bats = ["MONDAY_SETUP.bat", "START_BOT.bat", "UPDATE.bat", "FIX_CLOCK.bat", "tools/bat/TEST_ALERT.bat"]
    miss, bad_flags, helps = [], [], {}
    for b in bats:
        s = _read(b)
        for m in re.finditer(r'-m (engine\.[a-z_0-9]+)([^\r\n]*)', s):
            mod, rest = m.group(1), m.group(2)
            if not os.path.exists(os.path.join(ROOT, *mod.split(".")) + ".py"):
                miss.append(f"{b}: {mod}")
                continue
            for fl in re.findall(r'(--[a-z][a-z-]+)', rest):
                h = helps.setdefault(mod, _help(mod))
                if fl not in h:
                    bad_flags.append(f"{b}: {mod} {fl}")
        for m in re.finditer(r'%~dp0([A-Za-z_\\]+\.(?:py|ps1|bat))|%HERE%([A-Za-z_\\]+\.(?:py|ps1|bat))|\b(tools\\[a-z_]+\.py)', s):
            rel = next(g for g in m.groups() if g).replace("\\", "/")
            if not os.path.exists(os.path.join(ROOT, rel)):
                miss.append(f"{b}: {rel}")
    check("f1. every python module and file the 5 scripts call exists", not miss, miss)
    check("f2. every --flag they pass is in that module's argparse --help", not bad_flags, bad_flags)
    for mod, sub in (("tools/alerts_setup.py", "test"),):
        check(f"f3. {mod} accepts '{sub}'", f'cmd == "{sub}"' in open(os.path.join(ROOT, mod), encoding="utf-8").read())
    u = _read("UPDATE.bat").replace("\r\n", "\n")
    check("f4. UPDATE.bat passes its result back: RC=1 not updated / no Python, RC=2 red lines, 'endlocal & exit /b %RC%'",
          'if defined PULLFAIL set "RC=1"' in u and ':nopython\nset "RC=1"' in u and 'if "%RC%"=="0" set "RC=2"' in u
          and u.rstrip().endswith("endlocal & exit /b %RC%") and '--from-temp "%~dp0." & exit /b' in u)
    sb = _read("START_BOT.bat").replace("\r\n", "\n")
    check("f5. START_BOT.bat: Python missing = the plain install line; engine.go failing = a plain [FIX] line, never only a traceback",
          '"%PY%" --version >nul 2>&1\nif errorlevel 1 goto :nopython' in sb and "if errorlevel 1 echo  [FIX] START BOT stopped" in sb
          and ":nopython\necho  [FIX] Python not found" in sb and sb.index('-m engine.go %*') < sb.index("if errorlevel 1 echo  [FIX] START BOT"))
    ms = _read("MONDAY_SETUP.bat").replace("\r\n", "\n")
    check("f6. MONDAY_SETUP.bat: Python check, then engine.monday, then a closing [FIX] line on exit 1",
          ms.index("if errorlevel 1 goto :nopython") < ms.index("-m engine.monday") < ms.index("if errorlevel 1 echo  [FIX] A step above"))
    crlf = [b for b in bats if "\n" in _read(b).replace("\r\n", "") ]
    check("f7. CRLF line ends kept (cmd.exe reads LF-only .bat files wrong at labels)", not crlf, crlf)
    hard = [b for b in bats + ["engine/monday.py"] if re.search(r"(?i)/home/|/tmp/|C:\\\\Users\\\\[A-Za-z]|OneDrive\\\\", _read(b))]
    check("f8. no hardcoded machine or cloud paths in the scripts / engine/monday.py", not hard, hard)
    unq = []
    for b in bats:
        for ln in _read(b).splitlines():
            if ln.strip().lower().startswith("rem"):
                continue
            for m in re.finditer(r'(%~dp0|%HERE%|%TEMP%|%LE_HOME%)[^\s"]*', ln):
                i = m.start()
                if ln[:i].count('"') % 2 == 0:
                    unq.append(f"{b}: {ln.strip()[:80]}")
    check("f9. every path built from %~dp0 / %HERE% / %TEMP% / %LE_HOME% sits inside quotes (spaces in OneDrive folders)", not unq, unq)


def main():
    for fn in (part_a, part_b, part_c, part_d, part_f):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{fn.__name__} crashed: {e.__class__.__name__}: {e}", False)
    ok = sum(RES)
    print(f"\nmonday setup: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
