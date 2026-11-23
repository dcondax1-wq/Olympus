"""Every Windows Scheduled Task the bot's own scripts make, and the ONE-report-runner cleanup (night-tasks 2026-11-23).

Why: the public status topic showed TWO full pc_report runs every 15 minutes, 122 s apart (one at :00/:15/:30/:45 = the
task OlympusPCReport, one at :12:57/:27:57/...), doubling ntfy posts (250/day cap) and git pushes. The repo makes only ONE
15-minute pc_report task, so the second is a task the repo does not know (an old hand-made / old-folder one) or one of our
own tasks pointing at pc_report. This tool finds it on the PC and keeps exactly one.

  python -X utf8 -m tools.task_audit            list (read-only): every task that is ours by EXACT name, or runs pc_report.py
  python -X utf8 -m tools.task_audit --fix      the cleanup (idempotent), logs/task_cleanup.log says what it did:
      * a task that runs tools\\pc_report.py under one of OUR names other than OlympusPCReport -> removed (schtasks /Delete,
        exact name: it was made by our scripts and must not run the report)
      * OlympusPCReport pointing at another folder than this one -> installed again from this folder (scripts\\pc_report_task.ps1)
      * a task with a name our scripts never use that runs pc_report.py -> NOT touched (never anything that is not ours by
        name): one line with the exact command for the owner, and data/pc_report/tasks.json "foreign" (TRADE_HOME shows it)
Runs by itself once per bot-server start (engine/report_keeper.py; the server restarts after every update) and from
TRADE_HOME (5 Phone alerts, 3). Windows only; elsewhere it reports "not Windows" and changes nothing. Never arms,
starts, stops or routes anything. Tests: tests/test_task_audit.py (fake schtasks).
"""
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_TASK = "OlympusPCReport"
# every task name the repo's own scripts / .bat files create (exact; docs: research/handoff/2026-11-23/TASKS.md)
OUR_TASKS = {
    "OlympusPCReport": "scripts/pc_report_task.ps1 (BOTS_BACK.bat, report_keeper): tools/pc_report.py every 15 min + sign-in",
    "OlympusLiveSite": "scripts/live_link.ps1: tools/pc_publish.py --provider none every 15 min",
    "OlympusPublishNQ": "scripts/publish_nq.ps1: tools/pc_publish.py every 15 min",
    "LiquidityEngineOps": "scripts/install_ops_task.ps1: scripts/ops_tick.py every 5 min",
    "LiquidityEngine": "scripts/install_autostart.ps1: the bot server at sign-in / unlock",
    "LiquidityEngine-Keeper": "scripts/pc_tune.ps1: the keeper, daily + sign-in",
    "LiquidityEngine-WeeklyCare": "scripts/pc_tune.ps1: weekly PC care",
    "LiquidityEngine-IndexPause": "scripts/pc_care.ps1: search index pause",
    "LiquidityEngine-IndexResume": "scripts/pc_care.ps1: search index resume",
    "LiquidityEngineWake": "scripts/schedule_pc.ps1: Mon-Fri 01:30 ET wake",
    "LiquidityEngineSleep": "scripts/schedule_pc.ps1: Mon-Fri 16:35 ET hibernate",
    "OlympusWakeDaily": "tools/pc_always_on.py: daily wake",
    "OlympusClock": "scripts/fix_clock.ps1 (FIX_CLOCK.bat): w32tm /resync every 15 min + boot (SYSTEM)",
    "OlympusWeeklyBackup": "scripts/backup_task.ps1: weekly backup",
    "OlympusAgencyMail": "scripts/agency_mail_task.ps1: agency mail",
    "OlympusMoneyInbox": "MONEY_INBOX.bat: at sign-in",
    "LE Money Engine": "RUN_MONEY.bat (comment: made by hand): every 30 min",
    "Kalshi to Jarvis": "tools/kalshi_kit/install_windows.ps1",
}
LOG = os.path.join(ROOT, "logs", "task_cleanup.log")
STATE = os.path.join(ROOT, "data", "pc_report", "tasks.json")
TASK_PS1 = os.path.join(ROOT, "scripts", "pc_report_task.ps1")
# schtasks /Query /FO CSV /V columns by position (the header is localized on non-English Windows; the order is not)
I_NAME, I_RUN, I_START_IN, I_STATE, I_SCHED, I_START_T, I_REPEAT = 1, 8, 9, 11, 18, 19, 24


def _run(argv, timeout=60):
    try:
        kw = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {}
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, **kw)
        return r.returncode, r.stdout or ""
    except Exception as e:  # noqa: BLE001
        return -1, f"{e.__class__.__name__}"


def parse(csv_text: str) -> list:
    """`schtasks /Query /FO CSV /V` -> [{"path", "name", "run", "start_in", "state", "schedule", "start", "repeat"}]."""
    out, seen = [], set()
    for row in csv.reader(io.StringIO(csv_text or "")):
        if len(row) <= I_RUN or row[I_NAME] in ("TaskName", "") or row[I_NAME].lower() == "taskname":
            continue
        path = row[I_NAME].strip()
        g = (lambda i: row[i].strip() if len(row) > i else "")
        rec = {"path": path, "name": path.rsplit("\\", 1)[-1], "run": g(I_RUN), "start_in": g(I_START_IN), "state": g(I_STATE),
               "schedule": g(I_SCHED), "start": g(I_START_T), "repeat": g(I_REPEAT)}
        key = (rec["path"], rec["run"], rec["start"], rec["repeat"])     # one row per trigger in /V: keep each distinct one
        if key not in seen:
            seen.add(key)
            out.append(rec)
    return out


def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(str(p or "").strip().strip('"'))).replace("/", "\\")


def runs_report(rec: dict) -> bool:
    return "pc_report.py" in str(rec.get("run") or "").lower().replace("/", "\\")


def _folder_ok(rec: dict, root: str) -> bool:
    r = _norm(root).lower()
    return r in _norm(rec.get("run")).lower() or r == _norm(rec.get("start_in")).lower()


def plan(rows: list, root: str = ROOT) -> dict:
    """{"ours": [...], "remove": [paths], "reinstall": bool, "foreign": [recs], "report_tasks": n}: what --fix does."""
    ours = [r for r in rows if r["name"] in OUR_TASKS]
    rep = [r for r in rows if runs_report(r)]
    remove = sorted({r["path"] for r in rep if r["name"] in OUR_TASKS and r["name"] != REPORT_TASK})
    foreign = [r for r in rep if r["name"] not in OUR_TASKS]
    main = [r for r in rep if r["name"] == REPORT_TASK]
    reinstall = bool(main) and not any(_folder_ok(r, root) for r in main)
    return {"ours": ours, "remove": remove, "reinstall": reinstall, "foreign": foreign,
            "report_tasks": len({r["path"] for r in rep}), "has_report_task": bool(main)}


def _log(lines: list, path: str | None = None) -> None:
    try:
        p = path or LOG
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            for ln in lines:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {ln}\n")
    except Exception:  # noqa: BLE001
        pass


def _save_state(p: dict, path: str | None = None) -> None:
    try:
        fp = path or STATE
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        rec = {"t": int(time.time()), "report_tasks": p["report_tasks"], "removed": p.get("removed") or [],
               "foreign": [{"name": r["name"], "start": r["start"], "repeat": r["repeat"]} for r in p["foreign"]]}
        tmp = fp + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1)
        from engine.fsutil import replace as _rep
        _rep(tmp, fp)
    except Exception:  # noqa: BLE001
        pass


def audit(run=None, is_windows=None, root: str = ROOT) -> dict:
    """Read-only: the plan from the PC's task list. {"ok": False, "why"} off Windows / when schtasks fails."""
    run = run or _run
    if not ((os.name == "nt") if is_windows is None else is_windows):
        return {"ok": False, "why": "not Windows: nothing to check"}
    rc, out = run(["schtasks", "/Query", "/FO", "CSV", "/V"], 60)
    if rc != 0:
        return {"ok": False, "why": "schtasks /Query failed"}
    return {"ok": True, **plan(parse(out), root)}


def fix(run=None, is_windows=None, root: str = ROOT, log_path: str | None = None, state_path: str | None = None,
        python: str | None = None) -> dict:
    """The cleanup. Removes only OUR exact task names that run the report (never OlympusPCReport itself, never a name our
    scripts do not use), re-installs OlympusPCReport from this folder when it points elsewhere. Idempotent; logged."""
    run = run or _run
    a = audit(run, is_windows, root)
    if not a.get("ok"):
        return a
    lines, removed = [], []
    for path in a["remove"]:
        rc, _ = run(["schtasks", "/Delete", "/TN", path, "/F"], 60)
        if rc == 0:
            removed.append(path)
        lines.append(f"{'removed' if rc == 0 else 'could NOT remove'} our task {path}: it ran tools\\pc_report.py besides "
                     f"{REPORT_TASK} (two reports every 15 min)")
    if a["reinstall"] and os.path.exists(os.path.join(root, "scripts", "pc_report_task.ps1")):
        rc, _ = run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File",
                     os.path.join(root, "scripts", "pc_report_task.ps1")] + (["-Python", python] if python else []), 120)
        lines.append(f"{REPORT_TASK} pointed at another folder: {'installed again from ' + root if rc == 0 else 'could NOT re-install'}")
    for r in a["foreign"]:
        lines.append(f"NOT ours by name, left alone: task {r['path']!r} also runs tools\\pc_report.py (starts {r['start'] or '?'}, "
                     f"every {r['repeat'] or '?'}). If you made it: schtasks /Delete /TN \"{r['path']}\" /F")
    if lines:
        _log(lines, log_path)
    out = {**a, "removed": removed, "lines": lines}
    _save_state(out, state_path)
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    r = fix() if "--fix" in argv else audit()
    if not r.get("ok"):
        print(f"  [..] {r.get('why')}")
        return 0
    for t in r["ours"]:
        print(f"  {t['name']:<28} {t['state'] or '':<9} start {t['start'] or '-':<10} every {t['repeat'] or '-':<14} {OUR_TASKS[t['name']]}")
    for t in r["foreign"]:
        print(f"  [!!] {t['path']} (not ours) runs the report: {t['run'][:120]}")
    print(f"  pc_report runs from {r['report_tasks']} task(s)" + ("" if r["report_tasks"] <= 1 else ": should be 1"))
    for ln in r.get("lines") or []:
        print(f"  {ln}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
