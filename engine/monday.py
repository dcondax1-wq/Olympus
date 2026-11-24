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
Tests: python -X utf8 -m tests.test_monday (fakes; nothing runs; night-mondaysim 2026-11-23).
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOCK_TASK = "OlympusClock"


def _sys32(exe: str) -> str:
    return os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", exe)


def _ps_q(text: str) -> str:
    """A PowerShell single-quoted string body: ' doubled (a bot folder under a user name like O'Neil keeps working)."""
    return str(text).replace("'", "''")


def bat_cmd(path: str) -> list:
    """cmd.exe argv for a .bat whose path may hold spaces or ( ) & (OneDrive - Personal, "Bot (1)"): `cmd /c call "<path>"`.
    A bare `cmd /c "<path>"` loses its quotes when the path holds a special character (cmd's /c quote rule)."""
    return ["cmd", "/d", "/c", "call", path]


def cmd_line(argv, nt=None):
    """What subprocess gets for a bat_cmd() argv: on Windows ONE string with the path in quotes always (Python's own joining
    leaves a path with & or ( but no space unquoted, and cmd then splits it); elsewhere (tests) the list unchanged."""
    argv = list(argv)
    if (os.name == "nt" if nt is None else nt) and argv[:4] == ["cmd", "/d", "/c", "call"] and len(argv) == 5:
        return 'cmd /d /c call "' + str(argv[4]).replace('"', '') + '"'
    return argv


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
        return subprocess.run(cmd_line(bat_cmd(os.path.join(ROOT, "UPDATE.bat"))), cwd=ROOT, stdin=subprocess.DEVNULL).returncode

    def clock_task(self) -> bool:
        r = subprocess.run([_sys32("schtasks.exe"), "/query", "/tn", CLOCK_TASK], capture_output=True, text=True)
        return r.returncode == 0

    def fix_clock(self, elevated: bool) -> int:
        script = os.path.join(ROOT, "scripts", "fix_clock.ps1")
        if elevated:
            return subprocess.run([_ps_exe(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script], cwd=ROOT).returncode
        # one UAC "Yes" for the clock part only; "No" throws -> exit 1
        cmd = (f"try {{ $p = Start-Process -FilePath '{_ps_q(_ps_exe())}' -Verb RunAs -Wait -PassThru -ArgumentList "
               f"'-NoProfile -ExecutionPolicy Bypass -File \"{_ps_q(script)}\"'; exit $p.ExitCode }} catch {{ exit 1 }}")
        return subprocess.run([_ps_exe(), "-NoProfile", "-Command", cmd], cwd=ROOT).returncode

    def start(self) -> int:
        # --no-pull: step 1 just ran UPDATE.bat (with its never-in-a-trade guard); no second update inside START BOT
        return subprocess.run([self.py, "-X", "utf8", "-m", "engine.go", "--no-pull"], cwd=ROOT).returncode

    def alert_test(self) -> int:
        return subprocess.run([self.py, "-X", "utf8", os.path.join("tools", "alerts_setup.py"), "test"], cwd=ROOT).returncode

    def keepalive(self) -> dict:
        from . import go
        return go.keepalive_view()

    def recovery(self) -> list:
        from . import recovery
        return recovery.lines()

    def nt_boot(self) -> tuple:
        """(Startup shortcut present True/False/None, 'Connect on startup' True/False/None, Windows auto-sign-in True/False/None)."""
        sc = al = None
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            import pc_always_on as PA
            sc = bool(PA.startup_shortcut_present()) if os.name == "nt" else None
            if os.name == "nt":
                v = PA.reg_value(r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon", "AutoAdminLogon")
                al = None if v is None else str(v).strip() == "1"
        except Exception:  # noqa: BLE001
            pass
        try:
            from . import pc_checklist, self_heal
            ac = pc_checklist.nt_autoconnect(self_heal.nt_folder())
        except Exception:  # noqa: BLE001
            ac = None
        return sc, ac, al


def boot_lines(sc, ac, al) -> list:
    """MONDAY_SETUP's 'boot to trading' lines (day-zerotouch2): NinjaTrader opens at sign-in + connects by itself; Windows
    auto-sign-in is the owner's own choice (documented, never switched on by a script)."""
    out = []
    if sc is False:
        out.append("[FIX] NinjaTrader does not open at sign-in yet: START BOT makes the Startup shortcut (run MONDAY_SETUP again)")
    elif sc:
        out.append("[OK] NinjaTrader opens by itself when Windows signs in (Startup shortcut)")
    if ac is True:
        out.append("[OK] NinjaTrader connects by itself ('Connect on startup' is on)")
    elif ac is False:
        out.append("[FIX] NinjaTrader: Connections > Configure > your MFFU connection > tick 'Connect on startup' > OK (once)")
    else:
        out.append("[..] NinjaTrader 'Connect on startup': not readable here. Once: Connections > Configure > your MFFU connection > "
                   "tick 'Connect on startup' > OK (then a reboot needs no click)")
    if al is not True:
        out.append("[..] Windows auto-sign-in is YOUR choice (docs/PC_ALWAYS_ON.md, netplwiz): without it, after a reboot the PC waits "
                   "at the sign-in screen until you sign in; then everything else starts by itself")
    return out


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
        elif rc == 2:
            line("1/4 Update", True, "updated, but its health check printed red lines above: do those after the start")
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
            why = ""
            try:                                       # START BOT's own reason (engine/go.record_last, night-startmsg)
                from . import go as _go
                last = _go.last_start()
                if last and last.get("rc") == rc and last.get("why"):
                    why = " (" + str(last["why"]).rstrip(".")[:140] + ")"
            except Exception:  # noqa: BLE001
                pass
            line("3/4 Start", False, f"not started{why}: do the first [FIX] / NOT ARMED line above, then MONDAY_SETUP again." + kt)
    # 4. alert test
    res["order"].append("alert")
    rc = pc.alert_test()
    line("4/4 Alert test", rc == 0, "sent: check your phone buzzed" if rc == 0 else "did not send: TRADE_HOME.bat > 5 sets it up")
    try:
        rec = pc.recovery() or []
    except Exception:
        rec = []
    try:                                               # day-zerotouch2: boot to trading (NinjaTrader start + connect, sign-in)
        boot = boot_lines(*pc.nt_boot()) if hasattr(pc, "nt_boot") else []
    except Exception:  # noqa: BLE001
        boot = []
    res["boot"] = boot
    if rec or boot:
        out(" What comes back by itself:")
        for ln in rec + boot:
            out("   " + ln)
    return res


def main(argv=None, run_fn=None, out=print) -> int:
    """Never a traceback in the owner's window: Ctrl+C / a closed input = one plain line; anything else = one plain line +
    the details in logs/monday_crash.log (for Claude)."""
    try:
        r = (run_fn or run)()
    except (KeyboardInterrupt, EOFError):
        out("\n [FIX] MONDAY SETUP stopped before the end. Double-click MONDAY_SETUP.bat again: it skips what is done.")
        return 1
    except Exception as e:  # noqa: BLE001
        log = _crash_log(e)
        out(f"\n [FIX] MONDAY SETUP hit a problem ({e.__class__.__name__}). Double-click MONDAY_SETUP.bat again; if it "
            f"happens twice, send Claude a photo of this window{' (details in ' + log + ')' if log else ''}.")
        return 1
    return 0 if all(ok is not False for _n, ok, _t in r["steps"]) else 1


def _crash_log(e) -> str | None:
    try:
        import traceback
        d = os.path.join(ROOT, "logs")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "monday_crash.log")
        with open(p, "a", encoding="utf-8") as fh:
            fh.write("".join(traceback.format_exception(type(e), e, e.__traceback__)) + "\n")
        return os.path.join("logs", "monday_crash.log")
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":
    sys.exit(main())
