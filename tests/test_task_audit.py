"""ONE report runner (night-tasks 2026-11-23, tools/task_audit.py + tools/pc_report.py's gap): the public status topic showed two
full pc_report runs every 15 min, 122 s apart. Fake schtasks only (no real Task Scheduler), temp folders only.

    python -X utf8 -m tests.test_task_audit        (~2 s)
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import pc_report as PR, task_audit as TA  # noqa: E402

RES = []
HERE = r"C:\Users\Owner\Olympus"
OLD = r"C:\Users\Owner\nq-liquidity-engine"
PYW = r"C:\Python313\pythonw.exe"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def row(name, run, start_in=HERE, start="12:00:00 AM", repeat="0 Hour(s), 15 Minute(s)"):
    r = [""] * 28
    r[0], r[1], r[2], r[3] = "PC", "\\" + name, "N/A", "Ready"
    r[8], r[9], r[11], r[18], r[19], r[24] = run, start_in, "Enabled", "Daily", start, repeat
    return r


def table(rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    hdr = ["HostName", "TaskName"] + [f"c{i}" for i in range(2, 28)]
    w.writerow(hdr)
    for r in rows:
        w.writerow(r)
    w.writerow(hdr)                    # schtasks repeats the header per task folder
    return buf.getvalue()


class FakeSchtasks:
    def __init__(self, rows, rc=0):
        self.rows, self.rc, self.calls = list(rows), rc, []

    def __call__(self, argv, timeout=60):
        self.calls.append(list(argv))
        if argv[:2] == ["schtasks", "/Query"]:
            return self.rc, table(self.rows)
        if argv[:2] == ["schtasks", "/Delete"]:
            path = argv[3]
            self.rows = [r for r in self.rows if r[1] != path]
            return 0, "SUCCESS"
        if argv[0].startswith("powershell"):
            return 0, "[OK]"
        return 1, ""


def rep(root=HERE):
    return f'{PYW} -X utf8 "{root}\\tools\\pc_report.py" --quiet --by task'


def audit_checks(tmp):
    log, state = os.path.join(tmp, "cleanup.log"), os.path.join(tmp, "tasks.json")
    clean = [row("OlympusPCReport", rep()), row("OlympusLiveSite", f'{PYW} -X utf8 "{HERE}\\tools\\pc_publish.py" --provider none'),
             row("LiquidityEngineOps", f'{PYW} -X utf8 "{HERE}\\scripts\\ops_tick.py"', repeat="0 Hour(s), 5 Minute(s)"),
             row("GoogleUpdateTaskMachineUA", r"C:\Program Files\Google\Update\GoogleUpdate.exe /ua")]
    fk = FakeSchtasks(clean)
    a = TA.audit(run=fk, is_windows=True, root=HERE)
    check("audit: our tasks listed by exact name (3), a Windows / other app task never listed, ONE task runs pc_report",
          a["ok"] and sorted(t["name"] for t in a["ours"]) == ["LiquidityEngineOps", "OlympusLiveSite", "OlympusPCReport"]
          and a["report_tasks"] == 1 and not a["remove"] and not a["foreign"] and not a["reinstall"], a)
    r = TA.fix(run=fk, is_windows=True, root=HERE, log_path=log, state_path=state)
    check("fix on a clean PC: nothing removed, nothing re-installed, no log line (idempotent)",
          r["removed"] == [] and not any(c[1] == "/Delete" for c in fk.calls if c[0] == "schtasks")
          and not any(c[0].startswith("powershell") for c in fk.calls) and not os.path.exists(log), fk.calls)
    # our own extra task (an older name of ours) running pc_report + a foreign one + the real one
    dup = clean + [row("OlympusPublishNQ", rep(), start="12:12:57 AM"),
                   row("My PC report", rep(), start="7:12:57 PM")]
    fk2 = FakeSchtasks(dup)
    r2 = TA.fix(run=fk2, is_windows=True, root=HERE, log_path=log, state_path=state)
    dels = [c for c in fk2.calls if c[:2] == ["schtasks", "/Delete"]]
    check("fix: OUR task name that runs pc_report (not OlympusPCReport) removed by its exact name; never OlympusPCReport",
          r2["removed"] == ["\\OlympusPublishNQ"] and dels == [["schtasks", "/Delete", "/TN", "\\OlympusPublishNQ", "/F"]], dels)
    txt = open(log).read()
    check("fix: a task NOT ours by name is left alone, named in the log with the exact command for the owner; tasks.json says it",
          "\\My PC report" not in [c[3] for c in dels] and "NOT ours by name" in txt and 'schtasks /Delete /TN "\\My PC report" /F' in txt
          and "removed our task \\OlympusPublishNQ" in txt
          and json.load(open(state))["foreign"][0]["name"] == "My PC report", txt)
    r3 = TA.fix(run=fk2, is_windows=True, root=HERE, log_path=log, state_path=state)
    check("fix again: idempotent (our extra is gone, nothing more deleted)", r3["removed"] == [] and len(
        [c for c in fk2.calls if c[:2] == ["schtasks", "/Delete"]]) == 1, r3["removed"])
    # OlympusPCReport still pointing at the old folder (the move to Olympus): installed again from this folder
    fk3 = FakeSchtasks([row("OlympusPCReport", rep(OLD), start_in=OLD)])
    r4 = TA.fix(run=fk3, is_windows=True, root=HERE, log_path=log, state_path=state)
    ps = [c for c in fk3.calls if c[0].startswith("powershell")]
    check("fix: OlympusPCReport pointing at another folder -> scripts\\pc_report_task.ps1 of THIS folder runs (re-install), "
          "nothing deleted", r4["reinstall"] is True and len(ps) == 1 and ps[0][-1].endswith("pc_report_task.ps1")
          and not any(c[:2] == ["schtasks", "/Delete"] for c in fk3.calls), fk3.calls) if os.path.exists(
        os.path.join(HERE, "scripts", "pc_report_task.ps1")) else check(
        "fix: OlympusPCReport pointing at another folder -> flagged for re-install", r4["reinstall"] is True, r4)
    off = TA.fix(run=FakeSchtasks(dup), is_windows=False, root=HERE, log_path=log, state_path=state)
    bad = TA.audit(run=FakeSchtasks(dup, rc=1), is_windows=True)
    check("not Windows / schtasks fails: nothing done, a plain reason", not off["ok"] and "not Windows" in off["why"]
          and not bad["ok"], (off, bad))
    check("the exact-name list covers every task name the repo's scripts register",
          all(n in TA.OUR_TASKS for n in ("OlympusPCReport", "OlympusLiveSite", "OlympusPublishNQ", "LiquidityEngine",
                                          "LiquidityEngineOps", "OlympusClock", "OlympusWeeklyBackup", "OlympusAgencyMail")))


def gap_checks(tmp):
    work = os.path.join(tmp, "work")
    os.makedirs(work)
    now = 1_795_404_477
    check("gap: no run yet -> not too soon", PR.too_soon(work, now) is None)
    PR.note_start(work, "?", True, now=now)
    PR.note_start(work, "task", False, now=now + 122, why="the last run started 122 s ago")
    check("gap: the second scheduler 122 s later is too soon (the pair seen on the public topic); the skipped try is logged "
          "with who and does not move the last start", PR.too_soon(work, now + 122) == 122 and PR.last_start(work)["t"] == now
          and PR.last_start(work)["by"] == "?", PR.last_start(work))
    check("gap: the next 15-minute run is not too soon", PR.too_soon(work, now + 900) is None)
    for i in range(PR.RUNS_KEEP + 10):
        PR.note_start(work, "task", True, now=now + 900 * (i + 1))
    n = len(open(os.path.join(work, "runs.jsonl")).read().splitlines())
    check(f"gap: runs.jsonl keeps the last {PR.RUNS_KEEP} lines", n == PR.RUNS_KEEP, n)
    # main(): a second full run within the gap exits 0 without running (run_once never called)
    keep, keep_after = PR.run_once, PR.after_run
    called = []
    PR.run_once = lambda **k: (called.append(1), {"card": {}, "errors": []})[1]
    PR.after_run = lambda quiet=True: None       # the real hooks write the PC's data/ and start paper loops: never in a test
    try:
        PR.note_start(work, "keeper", True)
        rc = PR.main(["--work", work, "--quiet", "--by", "task"])
        rc2 = PR.main(["--work", work, "--quiet", "--by", "task", "--force"])
    finally:
        PR.run_once, PR.after_run = keep, keep_after
    lines = [json.loads(x) for x in open(os.path.join(work, "runs.jsonl")).read().splitlines()]
    check("pc_report main: a 2nd full run within 5 min exits 0 and runs nothing; --force runs; each try logged with --by",
          rc == 0 and rc2 == 0 and called == [1] and lines[-2]["ran"] is False and lines[-2]["by"] == "task"
          and lines[-1]["ran"] is True and not os.path.exists(os.path.join(work, "run.lock")), (called, lines[-3:]))
    src = open(os.path.join(ROOT, "scripts", "pc_report_task.ps1"), encoding="utf-8").read()
    rk = open(os.path.join(ROOT, "engine", "report_keeper.py"), encoding="utf-8").read()
    check("the task says --by task, the keeper --by keeper (the PC's runs.jsonl names the extra scheduler)",
          '--quiet --by task"' in src and '"--by", "keeper"' in rk)


def keeper_checks(tmp):
    from engine import report_keeper as RK
    fk = FakeSchtasks([row("OlympusPCReport", rep(ROOT), start_in=ROOT), row("OlympusPublishNQ", rep(ROOT))])
    keep_log, keep_state = TA.LOG, TA.STATE
    TA.LOG, TA.STATE = os.path.join(tmp, "k.log"), os.path.join(tmp, "k.json")
    logs = []
    try:
        k = RK.Keeper(work=os.path.join(tmp, "kw"), run=fk, clock=lambda: 1_795_404_477, is_windows=True, log=logs.append)
        k.tick()
        n1 = len([c for c in fk.calls if c[:2] == ["schtasks", "/Delete"]])
        k.tick()
        n2 = len([c for c in fk.calls if c[:2] == ["schtasks", "/Delete"]])
    finally:
        TA.LOG, TA.STATE = keep_log, keep_state
    check("keeper: the cleanup runs once per server start (our extra report task removed, logged), not every tick",
          n1 == 1 and n2 == 1 and any("removed our task" in x for x in logs), (n1, n2, logs))


def home_checks():
    from engine import trade_home as TH
    L, P = TH.status_screen(now=0, bot={"running": True, "last_poll": 0}, accounts=[{"name": "MFFUEVX1", "plan": "x", "armed": True}],
                            keepalive={"a": True}, alerts=(True, False, True), clock=0.1,
                            tasks={"report_tasks": 2, "foreign": [{"name": "My PC report"}]})
    L2, P2 = TH.status_screen(now=0, bot={"running": True, "last_poll": 0}, accounts=[{"name": "MFFUEVX1", "plan": "x", "armed": True}],
                              keepalive={"a": True}, alerts=(True, False, True), clock=0.1, tasks={"report_tasks": 1})
    ran = []
    out = TH.alerts_action(lambda q="": "5", lambda argv: (ran.append(argv), 0)[1], {}, print)
    check("TRADE_HOME: two report tasks -> a status line + '5 then 5'; one task -> nothing; 5 > 5 runs tools.task_audit --fix (integration: 3 / 4 = Alerts bus ON / OFF from night-cleanup)",
          any("Reports" in x for x in L) and any(p[0] == "5" and "report" in p[1] for p in P)
          and not any("Reports" in x for x in L2) and ran and ran[0][-2:] == ["tools.task_audit", "--fix"] and out.startswith("[OK]"),
          (L, P, ran, out))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        audit_checks(tmp)
        gap_checks(tmp)
        keeper_checks(tmp)
    home_checks()
    n = sum(RES)
    print(f"task audit: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
