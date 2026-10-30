"""PC self-test (engine/pc_selftest.py) + its auto-update hold-back (engine/autoupdate.selftest_step) + the Start page
endpoints. Temp files only: the real data/, logs/selftest*.json, .env.local.ps1, second_model.json and live_model*.json
are checked unchanged at the end.

  python -X utf8 -m tests.test_pc_selftest          (~10 s; one real mini-run of 4 fast suites in sealed children)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import autoupdate as au, pc_selftest as P  # noqa: E402

RES = []
REAL = [os.path.join(ROOT, p) for p in (".env.local.ps1", "second_model.json", "live_model.json", "live_model_lit.json",
                                         "data/start_bot.json", "data/autostart.json", "data/autopilot.jsonl", "data/push_pc_key.json",
                                         "data/push_sent.json", "logs/selftest.json", "logs/selftest_history.jsonl")]


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


def digest(paths):
    out = {}
    for p in paths:
        try:
            with open(p, "rb") as fh:
                out[p] = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            out[p] = None
    return out


def fake_runner(results):
    """runner(argv, timeout, cwd, python, env) -> {"code", "out", "s", "timed_out"} by suite module name."""
    seen = []

    def run(argv, timeout, cwd, python, env):
        mod = next((a for a in argv if a.startswith(("tests.", "engine."))), "-c")
        seen.append((mod, env))
        r = results.get(mod, {"code": 0, "out": "[PASS] a\n[PASS] b\n"})
        return {"code": r["code"], "out": r.get("out", ""), "s": 0.1, "timed_out": bool(r.get("timed_out"))}
    run.seen = seen
    return run


def ok_checks(c):
    return {"key": c["key"], "label": c["label"], "ok": True, "s": 0.0, "n_pass": 1, "n_fail": 0}


V = {"sha": "bbbbbbb", "branch": "main"}


def t_static():
    keys = [s["key"] for s in P.SUITES] + [c["key"] for c in P.CHECKS]
    check("suite / check keys are unique", len(keys) == len(set(keys)), keys)
    mods = [next(a for a in s["argv"] if a.startswith(("tests.", "engine."))) for s in P.SUITES if "-m" in s["argv"]]
    missing = [m for m in mods if not os.path.exists(os.path.join(ROOT, *m.split(".")) + ".py")]
    check("every suite's module exists in the repo", not missing, missing)
    slow = {"tests.test_dst", "tests.test_acctb_not_placed", "tests.test_lit_oif", "tests.test_win_scripts", "tests.test_lit_live",
            "tests.test_poll_speed", "tests.test_accounts", "tests.test_alerts_plus", "tests.test_eval_anchor"}
    check("the measured slow / file-writing suites are left out", not slow & set(mods), slow & set(mods))
    total = sum(P.MEASURED_S.get(s["key"], 999) for s in P.SUITES)
    check(f"measured total {total:.0f} s here (one at a time), every suite measured", total < 120 and all(s["key"] in P.MEASURED_S for s in P.SUITES), total)
    up = [x["key"] for _k, x in P.plan("update")]
    check("update mode: not the three the update ran itself, not the dirty check",
          not {"nt_route", "sizing", "no_yahoo", "update_ready"} & set(up) and "server_import" in up and "start_api" in up, up)
    check("the three the update ran itself are still in the Sunday / manual run",
          {"nt_route", "sizing", "no_yahoo", "update_ready"} <= {x["key"] for _k, x in P.plan("sunday")})
    check("autoupdate.SELFTEST runs pc_selftest in update mode with the old commit as the baseline",
          au.SELFTEST[:5] == ["-X", "utf8", "-m", "engine.pc_selftest", "--mode"] and "update" in au.SELFTEST and "{old}" in au.SELFTEST
          and au.HOLD_MARK == P.HOLD_MARK)
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("results live in logs/ (gitignored: a dirty tracked file never blocks an update)", "\nlogs/\n" in gi
          and P.LAST_PATH.startswith(os.path.join(ROOT, "logs")) and P.HIST_PATH.startswith(os.path.join(ROOT, "logs")))


def t_env():
    tmp = tempfile.mkdtemp(prefix="le_t_env_")
    try:
        base = {"NINJATRADER_LIVE": "1", "NINJATRADER_ACCOUNT": "MFFUEVBLDR1", "NINJATRADER_ALLOW": "MFFUEVBLDR1", "LE_VAPID_PRIVATE": "x",
                "LE_PUSH_SUBS": "y", "LE_PUSH_SUBS_2": "z", "LE_START_CONFIRM": "phrase", "LE_OPS_PUSH": "0", "LE_CLOUD": "1", "PATH": "/bin"}
        e = P.child_env(tmp, base)
        check("sealed env: no live switch, account, allowlist, push keys, phrase",
              not any(k in e for k in ("NINJATRADER_LIVE", "NINJATRADER_ACCOUNT", "NINJATRADER_ALLOW", "LE_VAPID_PRIVATE", "LE_PUSH_SUBS",
                                       "LE_PUSH_SUBS_2", "LE_START_CONFIRM", "LE_CLOUD")), e)
        check("sealed env: temp TMP / TEMP / TMPDIR and NinjaTrader folder, LE_SELFTEST_CHILD=1, no heartbeat / autostart",
              e["TMP"] == e["TEMP"] == e["TMPDIR"] == tmp and e["NINJATRADER_FOLDER"].startswith(tmp) and os.path.isdir(e["NINJATRADER_FOLDER"])
              and e["LE_SELFTEST_CHILD"] == "1" and e["LE_HEARTBEAT"] == "0" and e["LE_NO_AUTOSTART"] == "1" and e["PATH"] == "/bin", e)
        # a sealed child: engine/push never sends, never calls the relay, keeps its files in the temp folder
        code = ("import os,sys; from engine import push as p; t=os.environ['TMP'];"
                "ok=[p.SEALED, p.PC_KEY_PATH.startswith(t), p.SENT_PATH.startswith(t), p.CONFIG_PATH.startswith(t), p.SYNC_CACHE_PATH.startswith(t)];"
                "c={'private':'k','public':'p','subs':[{'endpoint':'https://x/1','keys':{}}],'source':'t','error':None};"
                "ok.append(p.send({'title':'t','body':'b','key':'k'}, cfg=c).get('skipped','').startswith('PC self-test'));"
                "ok.append(p.send({'title':'t','body':'b','key':'k'}, cfg=c, sender=lambda *a: 201).get('sent')==1);"
                "r=p.Relay(base='http://127.0.0.1:9', topic='x'); ok.append(r.post({'le':'sent'}) is False and 'RuntimeError' in str(r.error));"
                "ok.append(p.pc_sync(force=True)=={'private':None,'subs':[]});"
                "print(ok); sys.exit(0 if all(ok) else 1)")
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=ROOT, env=e, capture_output=True, text=True, timeout=60)
        check("sealed child: no real push / relay / GitHub fetch, push files in its temp folder (a fake sender still works)",
              r.returncode == 0, (r.stdout + r.stderr)[-400:])
        e2 = dict(os.environ)
        e2.pop("LE_SELFTEST_CHILD", None)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", "from engine import push as p; print(p.SEALED, p.PC_KEY_PATH)"], cwd=ROOT,
                           env=e2, capture_output=True, text=True, timeout=60)
        check("normal process: push unchanged (data/push_pc_key.json)", r.stdout.startswith("False") and "push_pc_key.json" in r.stdout
              and os.path.join("data", "push_pc_key.json") in r.stdout, r.stdout + r.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_run():
    fr = fake_runner({})
    r = P.run("manual", runner=fr, check_fn=ok_checks, ver=V, workers=2)
    n = len(P.plan("manual"))
    check(f"all green: {n} rows, passed {n}, ok, nothing held", r["ok"] and r["passed"] == n and r["failed"] == 0 and not r["hold"]
          and r["total"] == n and r["version"] == "bbbbbbb", {k: r[k] for k in ("ok", "passed", "failed", "total")})
    check("rows keep the plan order (checks, then suites) with 2 workers",
          [x["key"] for x in r["rows"]] == [x["key"] for _k, x in P.plan("manual")])
    check("every suite ran in its own sealed temp folder (LE_SELFTEST_CHILD, NINJATRADER_FOLDER, TMP)",
          len(fr.seen) == len(P.SUITES) and all(e.get("LE_SELFTEST_CHILD") == "1" and e["NINJATRADER_FOLDER"].startswith(e["TMP"])
                                                for _m, e in fr.seen)
          and len({e["TMP"] for _m, e in fr.seen}) == len(fr.seen) and not any(os.path.exists(e["TMP"]) for _m, e in fr.seen))
    check("summary line", P.summary_line(r).startswith(f"all {n} green in"), P.summary_line(r))
    fr = fake_runner({"tests.test_start_api": {"code": 1, "out": "[PASS] x\n[FAIL] go refused for phone C:\\Users\\me\\x.json -> 200\n"},
                      "tests.test_guards": {"code": 1, "out": "Traceback\nZeroDivisionError: division by zero\n"},
                      "tests.test_push": {"code": -9, "out": "", "timed_out": True}})
    r = P.run("sunday", runner=fr, check_fn=ok_checks, ver=V, workers=1)
    f = {x["key"]: x for x in r["first"]}
    check("failures: counted, first three named in plan order", r["failed"] == 3 and not r["ok"] and [x["key"] for x in r["first"]]
          == [k for k in ("guards", "start_api", "push")], r["first"])
    check("why: the first [FAIL] line (no file path), else the error line, else 'took longer'",
          f["start_api"]["why"].startswith("go refused for phone") and "Users" not in f["start_api"]["why"]
          and "ZeroDivisionError" in f["guards"]["why"] and "took longer than" in f["push"]["why"], f)
    check("sunday mode never holds anything", r["hold"] is False)
    r = P.run("manual", runner=fake_runner({}), check_fn=ok_checks, ver=V, budget_s=0, workers=2)
    check("over the time budget: suites skipped (ok None), never failed", r["failed"] == 0 and r["skipped"] == len(P.SUITES) and r["ok"]
          and "skipped" in P.summary_line(r), P.summary_line(r))
    r = P.run("manual", only=["fsutil", "config"], runner=fake_runner({}), ver=V)
    check("--only runs just those", [x["key"] for x in r["rows"]] == ["config", "fsutil"], r["rows"])


def t_regression():
    def row(k, ok):
        return {"key": k, "label": k.upper(), "ok": ok}
    base = {"version": "aaaaaaa", "hold": False, "rows": [row("a", True), row("b", False), row("c", True)]}
    held = {"version": "aaaaaaa", "hold": True, "rows": [row("a", True), row("b", True), row("c", True)]}
    other = {"version": "ccccccc", "hold": False, "rows": [row("a", True), row("b", True), row("c", True)]}
    check("baseline: the newest non-held result of the old commit", P.baseline("aaaaaaa" + "0" * 33, [base, held, other]) is base)
    check("baseline: none for an unknown / missing / non-sha base", P.baseline("ddddddd", [base]) is None and P.baseline(None, [base]) is None
          and P.baseline("{old}", [base]) is None)
    reg, known = P.regressions([row("a", False), row("b", False), row("c", True), row("new", False)], base)
    check("regression: a passed before and fails now; b failed before too (known); a new check failing counts",
          [r["key"] for r in reg] == ["a", "new"] and [r["key"] for r in known] == ["b"], (reg, known))
    reg, known = P.regressions([row("a", False)], None)
    check("no baseline: every failure is a regression (held, the safe side)", [r["key"] for r in reg] == ["a"] and not known)
    # end to end through run(): update mode + a baseline in the history
    tmp = tempfile.mkdtemp(prefix="le_t_reg_")
    old = (P.LAST_PATH, P.HIST_PATH)
    try:
        P.LAST_PATH, P.HIST_PATH = os.path.join(tmp, "selftest.json"), os.path.join(tmp, "hist.jsonl")
        rows = [{"key": x["key"], "label": x["label"], "ok": x["key"] != "heartbeat"} for _k, x in P.plan("update")]
        P.save({"version": "aaaaaaa", "hold": False, "rows": rows, "t": 1})
        fr = fake_runner({"tests.test_heartbeat": {"code": 1, "out": "[FAIL] push timed out\n"}})
        r = P.run("update", base="a" * 40, runner=fr, check_fn=ok_checks, ver=V)
        check("update: a check that failed on the old version too is reported, not held", not r["hold"] and r["known"] == ["heartbeat"]
              and r["base_version"] == "aaaaaaa" and r["failed"] == 1, r)
        fr = fake_runner({"tests.test_start_api": {"code": 1, "out": "[FAIL] status 500\n"}})
        r = P.run("update", base="a" * 40, runner=fr, check_fn=ok_checks, ver=V)
        check("update: a check that passed on the old version and fails now holds the update",
              r["hold"] and r["hold_on"] == "Start page" and r["first"][0]["key"] == "start_api", r)
        P.save(r)
        r2 = P.run("update", base="b" * 40, runner=fake_runner({"tests.test_start_api": {"code": 1, "out": "[FAIL] x\n"}}),
                   check_fn=ok_checks, ver={"sha": "ccccccc"})
        check("a held-back run is never a baseline (the next update is judged against the last good one)", r2["hold"], r2)
        for i in range(P.HIST_KEEP + 5):
            P.save({"version": "x", "i": i})
        h = P.history()
        check(f"history keeps the last {P.HIST_KEEP}", len(h) == P.HIST_KEEP and h[-1]["i"] == P.HIST_KEEP + 4, len(h))
        check("last() = the newest result", P.last()["i"] == P.HIST_KEEP + 4)
        # the CLI in update mode: exit 1 + the HOLD line only on a hold
        saved_run = P.run
        P.run = lambda *a, **k: {**r, "rows": r["rows"]}
        try:
            import contextlib
            import io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = P.main(["--mode", "update", "--no-save", "--quiet"])
            out = buf.getvalue()
            check("CLI update mode: held -> exit 1 and 'SELFTEST-HOLD: Start page: ...' (what the auto-update reads)",
                  code == 1 and "SELFTEST-HOLD: Start page: status 500" in out, out[-300:])
            P.run = lambda *a, **k: {**r, "hold": False, "hold_on": None}
            with contextlib.redirect_stdout(io.StringIO()):
                code = P.main(["--mode", "update", "--no-save", "--quiet"])
            check("CLI update mode: failures without a regression -> exit 0 (the update goes on)", code == 0)
            P.run = lambda *a, **k: {**r, "hold": False, "mode": "manual"}
            with contextlib.redirect_stdout(io.StringIO()):
                code = P.main(["--mode", "manual", "--no-save", "--quiet"])
            check("CLI manual mode: any failure -> exit 1", code == 1)
        finally:
            P.run = saved_run
    finally:
        P.LAST_PATH, P.HIST_PATH = old
        shutil.rmtree(tmp, ignore_errors=True)


class FakeShell(au.Shell):
    """Scripted git / python for run_update (as tests/test_autorun.py), cwd = a temp checkout with or without
    engine/pc_selftest.py."""

    def __init__(self, cwd, selftest=(0, "PC self-test: all green")):
        super().__init__(cwd=cwd)
        self.calls, self.head, self.remote, self.selftest = [], "a" * 40, "b" * 40, selftest

    def git(self, *args, timeout=120):
        self.calls.append(("git",) + args)
        a = list(args)
        if a[:2] == ["rev-parse", "--abbrev-ref"]:
            return 0, "main\n"
        if a == ["rev-parse", "HEAD"]:
            return 0, self.head + "\n"
        if a[:1] == ["rev-parse"]:
            return 0, self.remote + "\n"
        if a[:1] in (["status"], ["fetch"]):
            return 0, ""
        if a[:1] == ["merge-base"]:
            return 0, ""
        if a[:1] == ["diff"]:
            return 0, "engine/x.py"
        if a[:1] == ["merge"]:
            self.head = a[-1]
            return 0, ""
        if a[:2] == ["reset", "--keep"]:
            self.head = a[2]
            return 0, ""
        return 1, "unexpected"

    def py(self, args, timeout=600):
        self.calls.append(("py",) + tuple(args))
        if "engine.pc_selftest" in args:
            return self.selftest
        return 0, "PASS"


def t_autoupdate():
    import datetime as dt
    from zoneinfo import ZoneInfo
    evening = dt.datetime(2026, 10, 20, 20, 0, tzinfo=ZoneInfo("America/New_York")).timestamp()
    ON = {"enabled": True}
    tmp = tempfile.mkdtemp(prefix="le_t_au_")
    try:
        with_st = os.path.join(tmp, "with")
        os.makedirs(os.path.join(with_st, "engine"))
        open(os.path.join(with_st, "engine", "pc_selftest.py"), "w").write("# placeholder\n")
        sh = FakeShell(with_st)
        r = au.run_update(sh, "start", evening, None, state=ON, env={})
        st = [c for c in sh.calls if c[0] == "py" and "engine.pc_selftest" in c]
        check("update: after the 3 tests the PC self-test runs once, in update mode, with the old commit as --base",
              r["status"] == "updated" and r["restart"] and len(st) == 1 and "update" in st[0] and "a" * 40 in st[0] and "{old}" not in st[0], (r, st))
        sh = FakeShell(with_st, selftest=(1, "  [FAIL] Start page  0.4 s  status 500\nSELFTEST-HOLD: Start page: status 500\n"))
        r = au.run_update(sh, "start", evening, None, state=ON, env={})
        check("update: a self-test regression rolls back (git reset --keep <old>), marks the sha bad, no restart",
              r["status"] == "rolled_back" and r["alert"] and r.get("bad_sha") == "b" * 40 and sh.head == "a" * 40 and not r["restart"]
              and r.get("held") == "Start page" and "status 500" in r["reason"], r)
        sent = []
        saved = au.notify
        au.notify = lambda title, body, key, sync=False: sent.append((title, body, key))
        try:
            au.alert_for(r)
        finally:
            au.notify = saved
        check("push: 'Update held back: Start page' (still on the old commit, the new one waits for a newer main)",
              sent and sent[0][0] == "Update held back: Start page" and "Still on aaaaaaa" in sent[0][1] and "bbbbbbb" in sent[0][1], sent)
        sp = os.path.join(tmp, "autoupdate.json")
        s = au.record(r, state=dict(ON), path=sp)
        check("record: bad_sha + held kept; status() shows it", s.get("bad_sha") == "b" * 40 and s["last"].get("held") == "Start page"
              and au.status(sp).get("held") == "Start page")
        r2 = au.run_update(FakeShell(with_st), "start", evening, None, state=au.load_state(sp), env={})
        check("the held-back sha is not retried until main moves (existing bad_sha rule)", r2["status"] == "skipped"
              and "failed its tests before" in r2["reason"], r2)
        sh = FakeShell(with_st, selftest=(1, "Traceback ...\nImportError: cannot import name x\n"))
        r = au.run_update(sh, "start", evening, None, state=ON, env={})
        check("a crashing self-test (no HOLD line) holds too, named 'the PC self-test'", r["status"] == "rolled_back"
              and r.get("held") == "the PC self-test", r)
        sh = FakeShell(os.path.join(tmp, "without"))
        r = au.run_update(sh, "start", evening, None, state=ON, env={})
        check("a checkout without engine/pc_selftest.py: not run (an older main), exactly the 3 tests as before",
              r["status"] == "updated" and not any("engine.pc_selftest" in c for c in sh.calls if c[0] == "py")
              and sum(1 for c in sh.calls if c[0] == "py") == 3, sh.calls)
        sh = FakeShell(with_st, selftest=(1, "SELFTEST-HOLD: X: y\n"))
        r = au.run_update(sh, "start", evening, None, state=ON, env={}, selftest=False)
        check("run_update(selftest=False) skips it", r["status"] == "updated")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_runner_notice():
    tmp = tempfile.mkdtemp(prefix="le_t_rn_")
    try:
        lp = os.path.join(tmp, "selftest.json")
        done = []

        def spawn(argv):
            P.save({"t": int(__import__("time").time()), "mode": argv[argv.index("--mode") + 1], "ok": True, "failed": 0,
                    "total": 3, "passed": 3, "dur_s": 1.0, "version": "abc1234"}, last_path=lp, hist_path=os.path.join(tmp, "h.jsonl"))
            return {"code": 0, "out": ""}
        rn = P.Runner(last_path=lp, spawn=spawn)
        r = rn.start("sunday", on_done=done.append, wait=True)
        check("runner: starts the child in the given mode, on_done gets the new result", r["started"] and done and done[0]["mode"] == "sunday"
              and not rn.busy(), (r, done))
        rn.mode = "manual"
        r = rn.start("sunday")
        check("runner: one at a time (a second start is refused while one runs)", not r["started"] and r["running"], r)
        rn.mode = None
        rn2 = P.Runner(last_path=lp, spawn=lambda argv: {"code": 1, "out": "Traceback\nModuleNotFoundError: No module named 'x'\n"})
        got = []
        rn2.start("sunday", on_done=got.append, wait=True)
        check("runner: a child that never saved a result -> error result (not the stale one)", got and "ModuleNotFoundError" in got[0].get("error", ""), got)
        n = P.notice(got[0], "sunday", now=1793570000)
        check("notice: a Sunday run that could not run -> one push (kind selftest)", n and n["kind"] == "selftest" and "could not run" in n["title"], n)
        hb = P.hb_block(path=lp, runner=rn)
        check("heartbeat block: version, counts, say, small", hb and hb["version"] == "abc1234" and hb["passed"] == 3 and hb["say"].startswith("all")
              and len(json.dumps(hb)) < 1500, hb)
        check("heartbeat block: None before the first run", P.hb_block(path=os.path.join(tmp, "none.json"), runner=P.Runner(last_path=lp)) is None)
        fail = {"mode": "sunday", "t": 1793570000, "failed": 2, "total": 27, "passed": 25, "version": "abc1234", "dur_s": 80,
                "first": [{"key": "start_api", "label": "Start page", "why": "status 500"}],
                "rows": [{"key": "start_api", "ok": False}, {"key": "guards", "ok": False}]}
        n = P.notice(fail, "sunday")
        check("notice sunday fail: kind selftest, names the first check, trading not changed", n["kind"] == "selftest"
              and "Start page" in n["title"] and "Trading is not changed" in n["body"] and n["key"].startswith("selftest:sunday:"), n)
        g = P.notice({**fail, "failed": 0, "first": [], "ok": True}, "sunday")
        check("notice sunday green: kind selftest_ok (on / silent / off in the app), short", g["kind"] == "selftest_ok"
              and g["title"] == "PC self-test all green" and len(g["body"]) < 200, g)
        b = P.notice(fail, "baseline")
        check("notice baseline: failures pushed once per version + failing set; green -> nothing",
              b["key"] == "selftest:baseline:abc1234:guards,start_api" and P.notice({**fail, "failed": 0}, "baseline") is None, b)
        check("notice manual / update: none (the page shows it; the update pushes 'held back')",
              P.notice(fail, "manual") is None and P.notice(fail, "update") is None)
        from engine import alerts_plus as ap
        check("push kinds selftest / selftest_ok / pc_health / readiness have app levels (on / silent / off)",
              all(k in ap.KINDS for k in ("selftest", "selftest_ok", "pc_health", "readiness"))
              and ap.apply_level({"kind": "selftest_ok"}, {"selftest_ok": "off"}) is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_api():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from engine import cloud_guard as CG, start_api as S
    calls = []

    class R:
        def start(self, mode="manual", on_done=None, wait=False):
            calls.append(mode)
            return {"ok": True, "started": True, "mode": mode}

        def status(self):
            return {"running": bool(calls), "mode": "manual" if calls else None}
    saved = P.RUNNER
    tmp = tempfile.mkdtemp(prefix="le_t_api_")
    old_last = P.LAST_PATH
    from engine import go as G
    old_cfg = G.CFG
    try:
        P.RUNNER = R()
        P.LAST_PATH = os.path.join(tmp, "selftest.json")
        G.CFG = os.path.join(tmp, "start_bot.json")
        app = FastAPI()
        app.include_router(S.router)
        local = TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50001))
        phone = TestClient(app, base_url="http://192.168.1.20:8766", client=("192.168.1.50", 50003))
        g = local.get("/api/next/start/selftest").json()
        check("GET selftest: no result yet -> 'not run yet', not running", g["last"] is None and g["say"] == "not run yet"
              and g["running"]["running"] is False, g)
        r = phone.post("/api/next/start/selftest")
        check("POST selftest from the phone: 403, nothing started", r.status_code == 403 and not calls, r.text)
        r = local.post("/api/next/start/selftest")
        check("POST selftest on the PC: starts a manual run", r.status_code == 200 and calls == ["manual"] and r.json()["started"], r.text)
        check("POST selftest is a START write (cloud-blocked, local only)", "/api/next/start/selftest" in CG.START_WRITES
              and "/api/next/start/selftest" in CG.CLOUD_BLOCKED)
        check("POST selftest is not an autopilot step (no tap written)", not os.path.exists(os.path.join(tmp, "autopilot.jsonl")))
        P.save({"t": 5, "mode": "manual", "ok": True, "failed": 0, "total": 4, "passed": 4, "dur_s": 2, "version": "abc1234",
                "rows": []}, last_path=P.LAST_PATH, hist_path=os.path.join(tmp, "h.jsonl"))
        g = local.get("/api/next/start/selftest").json()
        check("GET selftest: the last result + its line", g["last"]["version"] == "abc1234" and g["say"].startswith("all 4 green"), g)
        js = open(os.path.join(ROOT, "web_next", "js", "next", "start.js"), encoding="utf-8").read()
        check("Start page: a 'Run self-test' line in its own two functions (status carries the line)",
              "function selftestLine(d)" in js and "function wireSelftest(el)" in js and "post('selftest')" in js
              and "${selftestLine(d)}" in js and "wireSelftest(el);" in js, "")
        st = open(os.path.join(ROOT, "engine", "start_api.py"), encoding="utf-8").read()
        check("status carries the self-test line (no extra fetch on the page)", 'st["selftest"] = _selftest_brief()' in st)
    finally:
        P.RUNNER = saved
        P.LAST_PATH = old_last
        G.CFG = old_cfg
        shutil.rmtree(tmp, ignore_errors=True)


def t_real_mini():
    """A real run of four fast suites + the checks in sealed children (no save)."""
    r = P.run("manual", only=["timezone", "config", "fsutil", "account_names", "server_import"])
    bad = [(x["key"], x.get("why")) for x in r["rows"] if not x["ok"]]
    check(f"real mini-run: timezone, config, fsutil, account names, server import pass ({r['dur_s']} s)", not bad and r["passed"] == 5, bad)
    ok, why = P.check_update_ready(git=lambda *a: (0, " M engine/live.py\n M data/VIX_1d.csv\n M second_model.json\n"))
    check("update_ready: a hand edit blocks (named), bot-made files and second_model.json do not", not ok and "engine/live.py" in why
          and "VIX" not in why and "second_model" not in why, why)
    ok, _ = P.check_update_ready(git=lambda *a: (0, " M data/VIX_1d.csv\n M cache/dash/x.json\n"))
    check("update_ready: only bot-made files -> clean", ok)


def main():
    before = digest(REAL)
    for t in (t_static, t_env, t_run, t_regression, t_autoupdate, t_runner_notice, t_api, t_real_mini):
        try:
            t()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check(f"{t.__name__} raised {e.__class__.__name__}: {e}", False)
    check("the real data/, logs/selftest*, .env.local.ps1, second_model.json, live_model*.json did not change", digest(REAL) == before)
    n = sum(RES)
    print(f"pc selftest: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
