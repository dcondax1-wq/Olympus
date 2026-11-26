"""REPORT KEEPER (night team C, 2026-11-16): the phone report keeps going even when its Windows task is missing.

Why: on 2026-11-15 the bots ran LIVE ARMED all evening, but the public ntfy status topic (tools/web_public/status_feed.json)
got nothing for 12+ hours and no trade pushes went out. The 15-minute report (tools/pc_report.py) only runs from the Windows
task "OlympusPCReport", and only tools/bat/BOTS_BACK.bat (or SETUP_EVERYTHING step 3, which it skips when both evals are already armed)
installs that task. Nothing re-installed it, nothing noticed it was missing.

What it does (a daemon thread of the bot server, started with the other watchers in server.py; read-only towards the bot):
  1. once per server start, on Windows: is the task OlympusPCReport there (schtasks /Query)? If not, it installs it the same
     way tools/bat/BOTS_BACK.bat does (scripts/pc_report_task.ps1, hidden window). So the next bot start or auto-update heals it.
  2. once per server start: `tools/pc_report.py --test` (makes your private alert topic when there is none and sends the one
     test push; a no-op when that topic was already tested). Its output is never logged (the topic stays private).
  3. every 5 minutes: when the report's own last run (data/pc_report/last.json "t") is older than LATE_S or missing, it runs
     the report itself (`tools/pc_report.py --quiet`, a hidden below-normal child). pc_report's run lock means the task and
     the keeper never send twice; when the task works, the keeper never runs anything.
  4. once per server start, on Windows: tools/task_audit.fix (night-tasks 2026-11-23: two schedulers posted the report
     every 15 min, 122 s apart): exactly one task runs the report; pc_report itself skips a full run within 5 min of the last.
Never arms, starts, stops or routes anything; never reads the private ntfy settings itself. Every failure is soft (one log line).
Off: LE_REPORT_KEEPER=0, a dev / test server (LE_NO_AUTOSTART=1), the self-test's children (LE_SELFTEST_CHILD=1).
Tests: tests/test_report_keeper.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "data", "pc_report")
REPORT = os.path.join(ROOT, "tools", "pc_report.py")
TASK_PS1 = os.path.join(ROOT, "scripts", "pc_report_task.ps1")
TASK_NAME = "OlympusPCReport"
FIRST_S = 120.0                  # after the server start (the bot's first heartbeat is written by then)
EVERY_S = 300.0
LATE_S = 20 * 60                 # the task runs every 15 minutes: older than this = the task is not doing its job
RUN_TIMEOUT_S = 300


def _kw() -> dict:
    if os.name != "nt":
        return {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    return {"creationflags": flags}


def default_run(argv, timeout):
    """(returncode, stdout) of a hidden child; never raises."""
    try:
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=timeout, **_kw())
        return r.returncode, r.stdout or ""
    except Exception as e:
        return -1, f"{e.__class__.__name__}"


def _python() -> str:
    exe = sys.executable or "python"
    if os.name == "nt" and os.path.basename(exe).lower() == "pythonw.exe":
        alt = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.exists(alt):
            return alt
    return exe


class Keeper:
    def __init__(self, work: str = WORK, run=None, clock=time.time, is_windows: bool | None = None, log=None):
        self.work, self.run, self.clock = work, run or default_run, clock
        self.windows = (os.name == "nt") if is_windows is None else is_windows
        self.log = log or (lambda t: print(t, flush=True))
        self.task_checked = False
        self.tested = False
        self.cleaned = False
        self.last: dict = {}
        self._stop = threading.Event()
        self._thread = None

    # ------------------------------------------------------------------ pieces
    def report_age(self, now=None):
        now = int(now or self.clock())
        try:
            with open(os.path.join(self.work, "last.json"), "r", encoding="utf-8") as fh:
                t = int(float((json.load(fh) or {}).get("t") or 0))
        except Exception:
            t = 0
        return (now - t) if t else None

    def ensure_task(self) -> str:
        """'there' | 'installed' | 'failed' | 'skip' (not Windows / no script). Once per server start."""
        self.task_checked = True
        if not self.windows:
            return "skip"
        rc, _ = self.run(["schtasks", "/Query", "/TN", TASK_NAME], 20)
        if rc == 0:
            return "there"
        if not os.path.exists(TASK_PS1):
            return "skip"
        rc, out = self.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", TASK_PS1,
                            "-Python", _python()], 120)
        ok = rc == 0
        self.log(f"[report keeper] the phone report task {TASK_NAME} was missing: {'re-installed' if ok else 'could not re-install it (the keeper runs the report itself)'}")
        return "installed" if ok else "failed"

    def ensure_topic(self) -> bool:
        """pc_report --test once per server start: makes the private alert topic if there is none, one test push the first
        time. Its output (it names the topic) is never logged."""
        self.tested = True
        rc, _ = self.run([_python(), "-X", "utf8", REPORT, "--test"], 60)
        return rc == 0

    def run_report(self) -> bool:
        rc, _ = self.run([_python(), "-X", "utf8", REPORT, "--by", "keeper", "--quiet"], RUN_TIMEOUT_S)
        return rc == 0

    def clean_tasks(self) -> dict:
        """Once per server start (the server restarts after every update): tools/task_audit.fix, ONE task runs the report
        (our own extra report tasks removed by exact name, a foreign one only named in logs/task_cleanup.log). Soft."""
        self.cleaned = True
        if not self.windows:
            return {"ok": False, "why": "not Windows"}
        try:
            from tools import task_audit
            r = task_audit.fix(run=self.run, is_windows=True, python=_python())
            for ln in r.get("lines") or []:
                self.log(f"[report keeper] {ln}")
            return r
        except Exception as e:
            return {"ok": False, "why": f"{e.__class__.__name__}"}

    # ------------------------------------------------------------------ one tick
    def tick(self, now=None) -> dict:
        now = int(now or self.clock())
        res = {"t": now}
        try:
            if not self.task_checked:
                res["task"] = self.ensure_task()
            if not self.cleaned:
                res["tasks"] = (self.clean_tasks() or {}).get("report_tasks")
            if not self.tested:
                res["topic"] = self.ensure_topic()
            age = self.report_age(now)
            res["age_s"] = age
            if age is None or age > LATE_S:
                res["ran"] = self.run_report()
                if not self.last.get("ran_once"):
                    self.log(f"[report keeper] the 15-minute phone report was {'never run' if age is None else f'{age // 60} min late'}: "
                             f"the bot server ran it {'(sent)' if res['ran'] else '(failed softly)'}")
                res["ran_once"] = True
            else:
                res["ran"] = False
                res["ran_once"] = self.last.get("ran_once", False)
        except Exception as e:
            res["error"] = f"{e.__class__.__name__}: {e}"
        self.last = res
        return res

    # ------------------------------------------------------------------ thread
    def _loop(self):
        if self._stop.wait(FIRST_S):
            return
        while True:
            self.tick()
            if self._stop.wait(EVERY_S):
                return

    def start(self):
        if os.environ.get("LE_REPORT_KEEPER") == "0" or os.environ.get("LE_NO_AUTOSTART") == "1" \
                or os.environ.get("LE_SELFTEST_CHILD") == "1":
            return False
        if self._thread and self._thread.is_alive():
            return True
        from . import pc_identity                    # day-noleak 2026-11-26: a sandbox's keeper posted a real status
        if not pc_identity.may_post("report keeper", log=self.log):
            return False
        self._thread = threading.Thread(target=self._loop, name="report-keeper", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()

    def status(self) -> dict:
        return dict(self.last)
