"""Report keeper + trade watch (night team C, 2026-11-16): the phone report runs even without its Windows task, never twice at
once, and the live-vs-backtest-twin pushes fire only on a real mismatch. Fake runner, temp folders: no network, no real task.

  python -X utf8 -m tests.test_report_keeper        # ~2 s
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import report_keeper as RK  # noqa: E402
from tools import pc_report as PR, trade_watch as TW  # noqa: E402

RES = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"))


class FakeRun:
    def __init__(self, query_rc=1, install_rc=0):
        self.calls, self.query_rc, self.install_rc = [], query_rc, install_rc

    def __call__(self, argv, timeout):
        self.calls.append(list(argv))
        if argv[0] == "schtasks":
            return self.query_rc, ""
        if argv[0].startswith("powershell"):
            return self.install_rc, ""
        return 0, "  [OK]  your phone alert topic: secret-topic-name"


def keeper_checks(tmp):
    now = 1_763_300_000
    work = os.path.join(tmp, "work")
    os.makedirs(work)
    logs = []
    fr = FakeRun(query_rc=1)
    k = RK.Keeper(work=work, run=fr, clock=lambda: now, is_windows=True, log=logs.append)
    r = k.tick(now)
    kinds = [c[0] if c[0] in ("schtasks",) or c[0].startswith("powershell") else c[-1] for c in fr.calls]
    check("a. task missing on Windows: queried, re-installed with scripts/pc_report_task.ps1", r.get("task") == "installed"
          and kinds[:2] == ["schtasks", "powershell.exe"] and RK.TASK_PS1 in fr.calls[1], fr.calls[:2])
    check("a. once per start: the alert topic made / tested (--test), the report run because it never ran (--quiet)",
          "--test" in kinds and "--quiet" in kinds and r.get("ran") is True, kinds)
    check("a. the topic is never logged (the --test output stays in the child)", not any("secret-topic" in x for x in logs), logs)
    # the task works: a fresh last.json -> the keeper runs nothing
    with open(os.path.join(work, "last.json"), "w") as fh:
        json.dump({"t": now - 300}, fh)
    n = len(fr.calls)
    r2 = k.tick(now + 60)
    check("b. the task runs (last report 6 min old): the keeper runs nothing and does not re-check the task", r2.get("ran") is False
          and len(fr.calls) == n and "task" not in r2, (r2, fr.calls[n:]))
    r3 = k.tick(now + RK.LATE_S + 400)
    check("b. the task stops (last report > 20 min old): the keeper runs the report itself", r3.get("ran") is True
          and fr.calls[-1][-1] == "--quiet", r3)
    fr2 = FakeRun(query_rc=0)
    k2 = RK.Keeper(work=work, run=fr2, clock=lambda: now, is_windows=True, log=logs.append)
    check("c. task there: not re-installed", k2.ensure_task() == "there" and not any(c[0].startswith("powershell") for c in fr2.calls))
    fr3 = FakeRun()
    k3 = RK.Keeper(work=work, run=fr3, clock=lambda: now, is_windows=False, log=logs.append)
    check("c. not Windows: no schtasks / powershell", k3.ensure_task() == "skip" and not fr3.calls)
    old = {x: os.environ.get(x) for x in ("LE_REPORT_KEEPER", "LE_NO_AUTOSTART", "LE_SELFTEST_CHILD")}
    try:
        os.environ["LE_NO_AUTOSTART"] = "1"
        check("c. a dev / test server (LE_NO_AUTOSTART=1) never starts the thread", RK.Keeper(work=work, run=FakeRun()).start() is False)
        os.environ.pop("LE_NO_AUTOSTART")
        os.environ["LE_REPORT_KEEPER"] = "0"
        check("c. LE_REPORT_KEEPER=0 = off", RK.Keeper(work=work, run=FakeRun()).start() is False)
    finally:
        for x, v in old.items():
            if v is None:
                os.environ.pop(x, None)
            else:
                os.environ[x] = v
    srv = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
    check("c. server.py starts the keeper with the other watchers", "REPORT_KEEPER = _rk.Keeper()" in srv and "REPORT_KEEPER.start()" in srv)


def lock_checks(tmp):
    work = os.path.join(tmp, "lockw")
    a = PR.run_lock(work)
    b = PR.run_lock(work)
    check("d. pc_report run lock: a second run while one is busy gets nothing (no double push)", a and b is None)
    PR.run_unlock(a)
    c = PR.run_lock(work)
    check("d. after the run the lock is free again", bool(c))
    os.utime(c, (time.time() - PR.LOCK_STALE_S - 60,) * 2)
    d = PR.run_lock(work)
    check("d. a crashed run's old lock (> 10 min) is taken over", bool(d))
    PR.run_unlock(d)


def watch_checks(tmp):
    now = int(time.time())
    root = os.path.join(tmp, "root")
    os.makedirs(os.path.join(root, "logs", "exec_audit"))
    t0 = now - 3600
    rows = [
        # same as the twin: nothing
        {"status": "matched", "day": "2026-11-16", "entry_t": t0, "side": "LONG", "bt_stop": 100.0, "live_stop": 100.0, "stop_diff_ticks": 0.0,
         "live_qty": 6, "bt_qty": 6, "max_slip_ticks": 1.0, "exit_t": t0 + 600},
        # a qty difference only (the sizer's choice): nothing
        {"status": "matched", "day": "2026-11-16", "entry_t": t0 + 100, "side": "LONG", "bt_stop": 100.0, "live_stop": 100.0,
         "stop_diff_ticks": 0.0, "live_qty": 4, "bt_qty": 9, "qty_diff": -5, "max_slip_ticks": 0.0, "exit_t": t0 + 700},
        # no stop in the ledger: push
        {"status": "matched", "day": "2026-11-16", "entry_t": t0 + 200, "side": "SHORT", "bt_stop": 120.0, "live_stop": None,
         "live_qty": 5, "bt_qty": 5, "exit_t": t0 + 800},
        # stop 10 ticks off the twin: push
        {"status": "matched", "day": "2026-11-16", "entry_t": t0 + 300, "side": "LONG", "bt_stop": 100.0, "live_stop": 102.5,
         "stop_diff_ticks": 10.0, "live_qty": 5, "bt_qty": 5, "exit_t": t0 + 900},
        # the twin traded, the bot did not, PC on: push (fill_audit's own rule)
        {"status": "missed", "day": "2026-11-16", "entry_t": t0 + 400, "side": "LONG", "pc_on": True, "reason": "feed stale",
         "missed_usd": 412.0, "bt_qty": 5},
        # missed while the PC was off: not pushed here
        {"status": "missed", "day": "2026-11-16", "entry_t": t0 + 500, "side": "LONG", "pc_on": False, "reason": "PC off", "missed_usd": 90.0},
        # an extra trade: not pushed
        {"status": "extra", "day": "2026-11-16", "entry_t": t0 + 600, "side": "LONG", "live_qty": 3},
        # a slipped fill (> 4 ticks): push
        {"status": "matched", "day": "2026-11-16", "entry_t": t0 + 700, "side": "LONG", "bt_stop": 100.0, "live_stop": 100.0, "stop_diff_ticks": 0.0,
         "entry_slip_ticks": 6.0, "max_slip_ticks": 6.0, "slip_usd": -15.0, "live_qty": 5, "bt_qty": 5, "exit_t": t0 + 1000},
        # an old one (3 days): never
        {"status": "matched", "day": "2026-11-13", "entry_t": now - 3 * 86400, "side": "LONG", "bt_stop": 1.0, "live_stop": None,
         "exit_t": now - 3 * 86400 + 60},
    ]
    with open(os.path.join(root, "logs", "exec_audit", "report.json"), "w") as fh:
        json.dump({"rows": rows}, fh)
    fl = TW.flags(root, now)
    keys = sorted(f["key"] for f in fl)
    want = sorted([f"watch:lit:{t0 + 200}:stop", f"watch:lit:{t0 + 300}:stop", f"watch:lit:{t0 + 400}:missed", f"watch:lit:{t0 + 700}:slip"])
    check("e. trade watch: pushes only a missing stop, a stop off the twin, a missed entry (PC on) and a slipped fill", keys == want, keys)
    check("e. a missed entry says the reason and the backtest $", any("feed stale" in f["body"] and "412" in f["body"] for f in fl),
          [f["body"] for f in fl])
    check("e. no report.json: no flags, no crash", TW.flags(os.path.join(tmp, "nothing"), now) == [])
    # through pc_report.events: once each, high priority, never on the first (seeding) run
    snap = {"t": now, "watch": fl, "live": None, "fills": []}
    st0, m0 = PR.events({}, snap)
    check("f. pc_report: the first run only records the mismatches (never a flood of old ones)", not [m for m in m0 if m["key"].startswith("watch:")])
    st1, m1 = PR.events({"seeded": True}, snap)
    w1 = [m for m in m1 if m["key"].startswith("watch:")]
    check("f. pc_report: each mismatch is one high-priority push", len(w1) == 4 and all(m["priority"] == "high" for m in w1), w1)
    st2, m2 = PR.events(st1, {**snap, "t": now + 900})
    check("f. pc_report: never twice", not [m for m in m2 if m["key"].startswith("watch:")])


def main():
    tmp = tempfile.mkdtemp(prefix="le_rk_")
    try:
        keeper_checks(tmp)
        lock_checks(tmp)
        watch_checks(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nreport keeper + trade watch: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
