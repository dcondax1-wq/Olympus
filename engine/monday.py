"""MONDAY SETUP: the ONE weekly click (night-zerotouch 2026-11-22, owner: "make this automatic. I shouldn't need to do
anything"). MONDAY_SETUP.bat runs this; each step prints ONE plain line, in this order:

  1. Update        UPDATE.bat (the same update, its own guard: never during a trade; in trading time it skips itself)
  2. Clock         FIX_CLOCK once: skipped when Windows' task OlympusClock is already there; else Windows asks "Yes" for
                   administrator (UAC) for the clock part ONLY; "No" = everything else still runs, one line says how later
  3. Start         START BOT (engine.go): the owner types I ACCEPT LIVE RISK HIMSELF; that one phrase arms every configured
                   account AND switches the 7-day keep-alive on for exactly those (engine/keepalive.start_consent). A bot that
                   already runs is left alone (it only offers the phrase for an account whose keep-alive is still off)
  4. Alert test    TEST_ALERT's test (no trade)
  then the "What comes back by itself" list (engine/recovery.py).

Safe to run twice: the update is a no-op when current, the clock is skipped once set, START skips every step already done
and leaves a running bot alone, the alert test only sends a test. It never types, stores or defaults the phrase.
Run it with a normal double-click: the bot must NOT run as administrator (files it writes elevated would lock the normal
account out). Started as administrator anyway, it does the clock and the alert test only and says to double-click it again.
Tests: python -X utf8 -m tests.test_monday (fakes; nothing runs).
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOCK_TASK = "OlympusClock"


def _sys32(exe: str) -> str:
    return os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", exe)


def _ps_exe() -> str:
    return os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe")


class Real:
    """The PC's real actions (Windows). Tests pass a fake with the same methods."""

    def __init__(self, py=sys.executable):
        self.py = py

    def is_admin(self) -> bool:
        if os.name != "nt":
            return False
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def head(self):
        try:
            from . import go
            return go.head_sha()
        except Exception:
            return None

    def update(self) -> int:
        # stdin = NUL: UPDATE.bat's "Update anyway?" (trading time) answers no, and its pause returns at once
        return subprocess.run(["cmd", "/c", os.path.join(ROOT, "UPDATE.bat")], cwd=ROOT, stdin=subprocess.DEVNULL).returncode

    def clock_task(self) -> bool:
        r = subprocess.run([_sys32("schtasks.exe"), "/query", "/tn", CLOCK_TASK], capture_output=True, text=True)
        return r.returncode == 0

    def fix_clock(self, elevated: bool) -> int:
        script = os.path.join(ROOT, "scripts", "fix_clock.ps1")
        if elevated:
            return subprocess.run([_ps_exe(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script], cwd=ROOT).returncode
        # one UAC "Yes" for the clock part only; "No" throws -> exit 1
        cmd = (f"try {{ $p = Start-Process -FilePath '{_ps_exe()}' -Verb RunAs -Wait -PassThru -ArgumentList "
               f"'-NoProfile -ExecutionPolicy Bypass -File \"{script}\"'; exit $p.ExitCode }} catch {{ exit 1 }}")
        return subprocess.run([_ps_exe(), "-NoProfile", "-Command", cmd], cwd=ROOT).returncode

    def start(self) -> int:
        return subprocess.run([self.py, "-X", "utf8", "-m", "engine.go"], cwd=ROOT).returncode

    def alert_test(self) -> int:
        return subprocess.run([self.py, "-X", "utf8", os.path.join("tools", "alerts_setup.py"), "test"], cwd=ROOT).returncode

    def keepalive(self) -> dict:
        from . import go
        return go.keepalive_view()

    def recovery(self) -> list:
        from . import recovery
        return recovery.lines()


def run(pc=None, out=print) -> dict:
    """The four steps in order, one line each, then the recovery list. Returns {"steps": [(name, ok, line)], "order": [...]}."""
    pc = pc or Real()
    res = {"steps": [], "order": []}

    def line(name, ok, text):
        res["steps"].append((name, ok, text))
        out(f"\n {'[OK] ' if ok else '[FIX]' if ok is False else '[..] '} {name}: {text}\n")

    admin = pc.is_admin()
    out("\n ==== MONDAY SETUP: update, clock, start, alert test ====")
    if admin:
        out(" (This window runs as administrator: only the clock and the alert test run here. The bot must not run as\n"
            "  administrator: when it is done, double-click MONDAY_SETUP.bat normally for the update and the start.)")
    # 1. update
    if admin:
        line("1/4 Update", None, "skipped in an administrator window (double-click MONDAY_SETUP.bat normally)")
    else:
        res["order"].append("update")
        before = pc.head()
        rc = pc.update()
        after = pc.head()
        if before and after and before != after:
            line("1/4 Update", True, f"now on the newest version ({after[:7]})")
        elif rc == 0:
            line("1/4 Update", True, "already the newest version (or the update said why it waits, above)")
        else:
            line("1/4 Update", False, "did not go through; the old version keeps running. Send Claude a photo of the window")
    # 2. clock
    if pc.clock_task():
        line("2/4 Clock", True, "already fixed (Windows syncs it every 15 minutes by itself)")
    else:
        res["order"].append("clock")
        rc = pc.fix_clock(admin)
        if rc == 0 and pc.clock_task():
            line("2/4 Clock", True, "fixed for good (Windows now syncs it every 15 minutes)")
        else:
            line("2/4 Clock", False, "not fixed (Windows did not get administrator). Later: right-click FIX_CLOCK.bat > "
                                     "Run as administrator. Everything else still runs")
    # 3. start (the owner types the phrase himself, in START BOT's own prompt)
    if admin:
        line("3/4 Start", None, "skipped in an administrator window (double-click MONDAY_SETUP.bat normally)")
    else:
        res["order"].append("start")
        rc = pc.start()
        try:
            ka = pc.keepalive() or {}
        except Exception:
            ka = {}
        kt = (f" Keep-alive ON for: {', '.join(ka['on'])}." if ka.get("on") else " Keep-alive is OFF.") + \
             (f" Still off: {', '.join(ka['off'])}." if ka.get("on") and ka.get("off") else "")
        if rc == 0:
            line("3/4 Start", True, "the bot runs (see WHAT HAPPENED above for each account)." + kt)
        else:
            line("3/4 Start", False, "not started: do the first [FIX] / NOT ARMED line above, then MONDAY_SETUP again." + kt)
    # 4. alert test
    res["order"].append("alert")
    rc = pc.alert_test()
    line("4/4 Alert test", rc == 0, "sent: check your phone buzzed" if rc == 0 else "did not send: TRADE_HOME.bat > 5 sets it up")
    try:
        rec = pc.recovery() or []
    except Exception:
        rec = []
    if rec:
        out(" What comes back by itself:")
        for ln in rec:
            out("   " + ln)
    return res


def main(argv=None) -> int:
    r = run()
    return 0 if all(ok is not False for _n, ok, _t in r["steps"]) else 1


if __name__ == "__main__":
    sys.exit(main())
