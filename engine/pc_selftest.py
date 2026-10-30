"""PC self-test (2026-10-30, owner: "automatic in a few weeks"): a fast, curated subset of the repo's own test suites plus a
few checks, made to run ON the owner's Windows PC (the bot trades real MFFU evals there; the full suites only ever ran in
the Linux sandbox, and Windows-only failures have cost real money: wrong account names, file locks, OneDrive, a dirty
tracked file blocking updates).

  python -X utf8 -m engine.pc_selftest                run it now (the Start page's "Run self-test" does the same)
  python -X utf8 -m engine.pc_selftest --status       the last result (logs/selftest.json)
  python -X utf8 -m engine.pc_selftest --list         the suites and checks, with their measured time
  python -X utf8 -m engine.pc_selftest --only a,b     only those keys (debugging)

When it runs (read-only / advisory everywhere, except that it can hold an update back):
  (a) after every auto-update, before the server restarts (engine/autoupdate.run_update -> selftest_step, mode "update",
      after the update's own three tests). The update is held back (git reset --keep to the old commit, the new sha
      remembered as bad_sha until main moves again, push "Update held back: <first failing check>") when a check fails
      that passed on this PC before (a regression), or that has no earlier result. A check that already failed on the
      previous version (an environment problem on this PC, not the update) is reported and never holds: otherwise one
      Windows-only failure would hold every update for good.
  (b) every Sunday 15:30 ET (New York wall clock: DST-safe), before the 18:00 open (engine/pc_health.Watcher in server.py):
      one push when something fails, else a short "all green" push (kind selftest_ok, on / silent / off in the app).
  (c) on demand: the Start page ("Run self-test", POST /api/next/start/selftest) or this CLI.
  (d) once after a server start on a version with no result yet, outside 01:50-16:00 ET on a weekday: the baseline (a)
      compares with.
Each suite runs as its own child process at below-normal priority (Windows: BELOW_NORMAL + no console window; else nice
10), output to temp files (no pipe to hang on), the whole process tree killed on its timeout, with a sealed environment:
TMP / TEMP / TMPDIR = a fresh temp folder (deleted after), NINJATRADER_FOLDER = a temp folder (the real NinjaTrader
folder is never touched), no NINJATRADER_LIVE / account / allowlist, LE_SELFTEST_CHILD=1 (engine/push sends nothing real
and never calls the ntfy relay), LE_HEARTBEAT=0, LE_NO_AUTOSTART=1, LE_OPS_PUSH=0, LE_NARRATOR_PUSH=0, LE_AUTOUPDATE=0,
LE_PREWARM=0. Every suite here was measured in the sandbox for writes outside its temp dirs (none into data/, the
NinjaTrader folder, .env.local.ps1, second_model.json or live_model*.json) and for time (MEASURED_S); suites that replay
the live loop (minutes) or need a browser are left out. Nothing here arms, routes, starts or stops the bot.

Result: logs/selftest.json (the last run) + logs/selftest_history.jsonl (the last 60), both gitignored; the heartbeat
carries hb_block() ("selftest": t, version, mode, passed / failed counts, the first failures, duration, running).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, "logs")
LAST_PATH = os.path.join(LOG_DIR, "selftest.json")
HIST_PATH = os.path.join(LOG_DIR, "selftest_history.jsonl")
HIST_KEEP = 60
BUDGET_S = 240.0                # the whole run: suites still waiting after this are skipped (never failed)
CHILD_TIMEOUT_S = 420.0         # the Runner's limit on one whole `python -m engine.pc_selftest` child
HOLD_MARK = "SELFTEST-HOLD:"    # the update-mode line engine/autoupdate reads: "SELFTEST-HOLD: <label>: <why>"
MODES = ("manual", "update", "sunday", "baseline")


def _m(mod, *args):
    return ["-X", "utf8", "-m", mod, *args]


_IMPORT_SERVER = ("import server, engine.pc_health, engine.readiness; "
                  "print('[PASS] the bot server imports (%d routes)' % len(server.app.routes))")
# key, plain label (the phone push names it), argv after the python executable, timeout (s), update: run in mode "update"
# (False = already run by engine/autoupdate.TESTS right before, a hard gate there).
SUITES = (
    {"key": "server_import", "label": "Bot server starts (imports)", "argv": ["-X", "utf8", "-c", _IMPORT_SERVER], "timeout": 90},
    {"key": "nt_route", "label": "NinjaTrader order route (never-placed, flatten, roll)", "timeout": 90, "update": False,
     "argv": _m("engine.ninjatrader", "--selftest", "--quiet")},
    {"key": "sizing", "label": "Sizing rules", "argv": _m("engine.sizing"), "timeout": 60, "update": False},
    {"key": "no_yahoo", "label": "No Yahoo, stale feed blocks entries", "argv": _m("tests.test_no_yahoo"), "timeout": 150,
     "update": False},
    {"key": "guards", "label": "Entry guards", "argv": _m("tests.test_guards"), "timeout": 120},
    {"key": "heartbeat", "label": "Heartbeat push", "argv": _m("tests.test_heartbeat"), "timeout": 150},
    {"key": "eval_life", "label": "Eval pass / fail detection", "argv": _m("tests.test_eval_lifecycle"), "timeout": 120},
    {"key": "autoupdate", "label": "Auto-update and auto-resume", "argv": _m("tests.test_autorun"), "timeout": 150},
    {"key": "risk", "label": "Risk invariants", "argv": _m("tests.test_risk_invariants"), "timeout": 90},
    {"key": "start_api", "label": "Start page", "argv": _m("tests.test_start_api"), "timeout": 120},
    {"key": "calendar", "label": "CME holidays and early closes", "argv": _m("tests.test_holidays"), "timeout": 90},
    {"key": "sizing_caps", "label": "Size caps", "argv": _m("tests.test_sizing_caps"), "timeout": 90},
    {"key": "launch", "label": "Launch checklist", "argv": _m("tests.test_launch_checklist"), "timeout": 90},
    {"key": "nt_outgoing", "label": "NinjaTrader fills / positions", "argv": _m("tests.test_nt_outgoing"), "timeout": 90},
    {"key": "nt_accounts", "label": "Orders only to the bot's own accounts", "argv": _m("tests.test_nt_exec_audit"), "timeout": 90},
    {"key": "selfheal", "label": "Self-healing (file locks, reconnect, voids)", "argv": _m("tests.test_selfheal"), "timeout": 90},
    {"key": "ops", "label": "Health check and phone notices", "argv": _m("tests.test_ops"), "timeout": 90},
    {"key": "run_switch", "label": "Run switch", "argv": _m("tests.test_run_switch"), "timeout": 90},
    {"key": "new_accounts", "label": "New MFFU account names", "argv": _m("tests.test_new_accounts"), "timeout": 60},
    {"key": "start_bot", "label": "START BOT steps", "argv": _m("tests.test_go"), "timeout": 90},
    {"key": "roll_guard", "label": "Contract roll guard", "argv": _m("tests.test_nt_roll_guard"), "timeout": 60},
    {"key": "broker_balance", "label": "Real balance from NinjaTrader", "argv": _m("tests.test_broker_balance"), "timeout": 60},
    {"key": "mffu_rules", "label": "MFFU rules", "argv": _m("tests.test_mffu_rules"), "timeout": 60},
    {"key": "push", "label": "Phone push logic", "argv": _m("tests.test_push"), "timeout": 60},
    {"key": "eval_fix", "label": "Refused-order days voided", "argv": _m("tests.test_eval_fix"), "timeout": 60},
    {"key": "fsutil", "label": "Windows-safe state saves", "argv": _m("tests.test_fsutil"), "timeout": 30},
    {"key": "account_names", "label": "Account names", "argv": _m("tests.test_account_rename"), "timeout": 30},
)
# Measured and left out (sandbox, 2026-10-30): test_dst --quick 49 s (the timezone check below covers the PC side),
# test_acctb_not_placed and test_lit_oif > 400 s (live-loop replays; nt_route covers never-placed), test_win_scripts
# (PowerShell sandbox, > 60 s), test_accounts (rewrites tools/web_hub_snapshot.json), test_alerts_plus / test_eval_anchor
# (write logs/ops-*.log), test_lit_live / test_poll_speed (minutes), every Playwright / browser test.
CHECKS = (   # in this process (a child of the server or of the update): fast, read-only
    {"key": "timezone", "label": "New York time (tzdata, DST)"},
    {"key": "config", "label": "Strategy config files"},
    {"key": "update_ready", "label": "No local change blocks updates", "update": False},
)
# seconds each took in the sandbox, one at a time (4 cores, busy with other jobs, 2026-10-30; the Surface is slower)
MEASURED_S = {"server_import": 1.0, "nt_route": 0.8, "sizing": 0.3, "no_yahoo": 18.5, "guards": 9.5, "heartbeat": 14.6,
              "eval_life": 10.2, "autoupdate": 6.5, "risk": 3.0, "start_api": 2.5, "calendar": 2.2, "sizing_caps": 1.6,
              "launch": 1.6, "nt_outgoing": 1.3, "nt_accounts": 3.2, "selfheal": 1.3, "ops": 1.2, "run_switch": 1.1, "new_accounts": 1.1,
              "start_bot": 0.9, "roll_guard": 0.9, "broker_balance": 0.9, "mffu_rules": 0.8, "push": 0.8, "eval_fix": 0.7,
              "fsutil": 0.1, "account_names": 0.1}
WORKERS = 2                     # suites at once (each a below-normal-priority child; the bot is flat when this runs)


# ---------------------------------------------------------------------------------------------- small helpers
def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(float(t), ET)


def _scrub(text, n: int = 160) -> str:
    """One line for the phone: no file paths, never the live phrase (engine/ops_checks.scrub)."""
    try:
        from .ops_checks import scrub
        return scrub(text, n, paths=True)
    except Exception:
        return str(text or "").replace("\n", " ")[:n]


def version(cwd: str = ROOT) -> dict:
    """{"sha": short HEAD, "branch"} straight from git (no cache: a run right after a fast-forward). Never raises."""
    try:
        from .generated_files import git_exe
        kw = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {}
        r = subprocess.run([git_exe(), "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=20, **kw)
        b = subprocess.run([git_exe(), "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=20, **kw)
        sha = (r.stdout or "").strip()
        return {"sha": sha[:7] if r.returncode == 0 and sha else None, "branch": (b.stdout or "").strip() if b.returncode == 0 else None}
    except Exception:
        return {"sha": None, "branch": None}


def _read_json(path) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def last(path: str | None = None) -> dict:
    """The last result ({} before the first run). Never raises."""
    return _read_json(path or LAST_PATH)


def history(path: str | None = None) -> list:
    out = []
    try:
        with open(path or HIST_PATH, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                    if isinstance(r, dict):
                        out.append(r)
                except Exception:
                    continue
    except Exception:
        pass
    return out


def save(res: dict, last_path: str | None = None, hist_path: str | None = None, keep: int = HIST_KEEP):
    """logs/selftest.json (replace, retried on a Windows lock) + one line in logs/selftest_history.jsonl (last `keep`)."""
    last_path, hist_path = last_path or LAST_PATH, hist_path or HIST_PATH
    os.makedirs(os.path.dirname(last_path), exist_ok=True)
    tmp = last_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    from .fsutil import replace as _fs_replace
    _fs_replace(tmp, last_path)
    rows = history(hist_path)[-(keep - 1):] + [res]
    tmp = hist_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":"), default=str) + "\n")
    _fs_replace(tmp, hist_path)


def baseline(sha: str | None, rows: list | None = None) -> dict | None:
    """The newest earlier result to compare with: of version `sha` (the commit before the update) when given, else None.
    A held-back run never counts (it tested the rejected commit)."""
    if not sha or not re.fullmatch(r"[0-9a-f]{7,40}", str(sha)):
        return None
    sha7 = str(sha)[:7]
    rows = history() if rows is None else rows
    for r in reversed(rows):
        if r.get("version") == sha7 and not r.get("hold") and r.get("rows"):
            return r
    return None


def regressions(rows: list, base: dict | None) -> tuple[list, list]:
    """(regressed, known): failed rows that passed (or were missing) in the baseline, and rows that failed there too."""
    was = {r.get("key"): r.get("ok") for r in (base or {}).get("rows") or []}
    bad = [r for r in rows if r.get("ok") is False]
    known = [r for r in bad if was.get(r["key"]) is False]
    return [r for r in bad if r not in known], known


# ---------------------------------------------------------------------------------------------- one child process
def _kill_tree(p):
    try:
        from .heartbeat import _kill_tree as kt
        kt(p)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def _low_priority_kw() -> dict:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000) | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {"start_new_session": True, "preexec_fn": lambda: os.nice(10)}


def child_env(tmp: str, base: dict | None = None) -> dict:
    """The sealed environment of one suite (see the module doc). tmp: this suite's own temp folder."""
    env = dict(os.environ if base is None else base)
    for k in ("NINJATRADER_LIVE", "NINJATRADER_ACCOUNT", "NINJATRADER_ALLOW", "LE_START_CONFIRM", "LE_VAPID_PRIVATE",
              "LE_PUSH_SUBS", "LE_ALERTS_CHAT", "LE_PUSH_EXTRA"):
        env.pop(k, None)
    for k in list(env):
        if k.startswith("LE_PUSH_SUBS_"):
            env.pop(k, None)
    nt = os.path.join(tmp, "NinjaTrader 8")
    os.makedirs(nt, exist_ok=True)
    for k in ("LE_OPS_PUSH", "LE_NARRATOR_PUSH", "LE_AUTOUPDATE", "LE_CLOUD"):   # the suites set / expect their own
        env.pop(k, None)
    env.update({"TMP": tmp, "TEMP": tmp, "TMPDIR": tmp, "NINJATRADER_FOLDER": nt, "LE_SELFTEST_CHILD": "1",
                "LE_HEARTBEAT": "0", "LE_NO_AUTOSTART": "1", "LE_PREWARM": "0", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
                "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"})
    return env


def run_child(argv, timeout: float, cwd: str = ROOT, python: str = sys.executable, env=None) -> dict:
    """{"code", "out", "s", "timed_out"}; never raises (code -1 = could not start). Output through temp files, the whole
    process tree killed on the timeout (subprocess.run's timeout can wait forever on Windows: engine/heartbeat.run_cmd)."""
    t0 = time.monotonic()
    try:
        with tempfile.TemporaryFile() as fo:
            p = subprocess.Popen([python, *argv], cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=fo, stderr=subprocess.STDOUT,
                                 **_low_priority_kw())
            timed_out = False
            try:
                p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_tree(p)
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
            fo.seek(0)
            out = fo.read().decode("utf-8", "replace")
        code = p.returncode if p.returncode is not None else -9
        return {"code": -9 if timed_out else code, "out": out, "s": round(time.monotonic() - t0, 1), "timed_out": timed_out}
    except Exception as e:
        return {"code": -1, "out": f"{e.__class__.__name__}: {e}", "s": round(time.monotonic() - t0, 1), "timed_out": False}


_FAIL_RX = re.compile(r"^\s*\[FAIL\]\s*(.+)$", re.M)
_PASS_RX = re.compile(r"^\s*\[(?:PASS| OK )\]", re.M)


def why_failed(out: str, code: int, timed_out: bool = False, timeout: float | None = None) -> str:
    """One plain line: the first [FAIL] line, else the last error line, else the exit code."""
    if timed_out:
        return f"took longer than {timeout:g} s (stopped)" if timeout else "took too long (stopped)"
    m = _FAIL_RX.search(out or "")
    if m:
        return _scrub(m.group(1), 160)
    lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
    for ln in reversed(lines):
        if re.search(r"(Error|Exception|Traceback|FAIL)", ln):
            return _scrub(ln, 160)
    return f"exit code {code}" + (f": {_scrub(lines[-1], 120)}" if lines else "")


def run_suite(s: dict, tmp_root: str, cwd: str = ROOT, python: str = sys.executable, runner=None) -> dict:
    """One suite in its own sealed child. runner(argv, timeout, cwd, python, env) -> run_child's dict (tests)."""
    tmp = tempfile.mkdtemp(prefix=f"{s['key']}_", dir=tmp_root)
    try:
        r = (runner or run_child)(list(s["argv"]), float(s.get("timeout") or 120), cwd, python, child_env(tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out = r.get("out") or ""
    ok = r.get("code") == 0
    row = {"key": s["key"], "label": s["label"], "ok": ok, "s": r.get("s"), "n_pass": len(_PASS_RX.findall(out)),
           "n_fail": len(_FAIL_RX.findall(out))}
    if not ok:
        row["why"] = why_failed(out, r.get("code"), r.get("timed_out"), s.get("timeout"))
    return row


# ---------------------------------------------------------------------------------------------- in-process checks
def check_timezone() -> tuple[bool, str]:
    """Every live time decision is New York wall clock: zoneinfo must know America/New_York on this PC (Windows has no
    system tz database: the tzdata package from requirements.txt), with the right offsets on both sides of the clock
    changes (2026-11-01 back to EST, 2027-03-14 forward to EDT)."""
    try:
        tz = ZoneInfo("America/New_York")
    except Exception as e:
        return False, f"no New York time zone ({e.__class__.__name__}): pip install tzdata"
    want = ((dt.datetime(2026, 11, 1, 5, 59, tzinfo=dt.timezone.utc), -4), (dt.datetime(2026, 11, 1, 6, 0, tzinfo=dt.timezone.utc), -5),
            (dt.datetime(2027, 3, 14, 6, 59, tzinfo=dt.timezone.utc), -5), (dt.datetime(2027, 3, 14, 7, 0, tzinfo=dt.timezone.utc), -4))
    for t, h in want:
        off = t.astimezone(tz).utcoffset().total_seconds() / 3600
        if off != h:
            return False, f"{t:%Y-%m-%d %H:%M} UTC is UTC{off:+.0f} in New York here (expected UTC{h:+d}): update tzdata"
    return True, "America/New_York, EDT/EST switch dates right"


def check_config(root: str = ROOT) -> tuple[bool, str]:
    """The tracked strategy files parse, live_model.json "lit" = live_model_lit.json "lit" (CLAUDE.md: change both),
    no_yahoo is on, second_model.json ships account_b null (ATLAS's account lives in data/account_b.json)."""
    def rd(name):
        with open(os.path.join(root, name), encoding="utf-8") as fh:
            return json.load(fh)
    try:
        lm, ll, sm = rd("live_model.json"), rd("live_model_lit.json"), rd("second_model.json")
        rd("live_model_engine.json")
    except Exception as e:
        return False, f"a config file does not parse: {e.__class__.__name__}: {_scrub(e, 120)}"
    if lm.get("model") != "lit":
        return False, f"live_model.json model is {lm.get('model')!r}, not 'lit'"
    if lm.get("lit") != ll.get("lit"):
        return False, "live_model.json and live_model_lit.json have different LIT rules"
    if lm.get("no_yahoo") is not True:
        return False, "live_model.json no_yahoo is not true"
    if sm.get("account_b") is not None:
        return False, "second_model.json carries an account (it must ship account_b null)"
    return True, "live_model.json = live_model_lit.json, no_yahoo on"


def check_update_ready(root: str = ROOT, git=None) -> tuple[bool, str]:
    """A hand edit to a tracked file blocks every update (engine/autoupdate.fast_forward); bot-made files do not."""
    from . import generated_files as G
    if git is None:
        kw = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {}

        def git(*a):
            r = subprocess.run([G.git_exe(), *a], cwd=root, capture_output=True, text=True, timeout=30, **kw)
            return r.returncode, (r.stdout or "") + (r.stderr or "")
    c, out = git("status", "--porcelain", "--untracked-files=no")
    if c != 0:
        return False, f"git status failed: {_scrub(out, 120)}"
    _gen, other = G.split_dirty(out)
    other = [p for p in other if p != "second_model.json"]     # engine/account_b.migrate_local moves that one by itself
    if other:
        return False, "changed on this PC (blocks the auto-update): " + ", ".join(other[:4])
    return True, "clean"


def run_check(c: dict) -> dict:
    t0 = time.monotonic()
    fn = {"timezone": check_timezone, "config": check_config, "update_ready": check_update_ready}[c["key"]]
    try:
        ok, why = fn()
    except Exception as e:
        ok, why = False, f"{e.__class__.__name__}: {_scrub(e, 120)}"
    row = {"key": c["key"], "label": c["label"], "ok": bool(ok), "s": round(time.monotonic() - t0, 1), "n_pass": int(bool(ok)),
           "n_fail": int(not ok)}
    if not ok:
        row["why"] = why
    return row


# ---------------------------------------------------------------------------------------------- the whole run
def plan(mode: str, only=None) -> list:
    """The checks then the suites this mode runs (update: not the three the update itself just ran, no dirty check)."""
    items = [("check", c) for c in CHECKS] + [("suite", s) for s in SUITES]
    if mode == "update":
        items = [(k, x) for k, x in items if x.get("update", True)]
    if only:
        items = [(k, x) for k, x in items if x["key"] in set(only)]
    return items


def run(mode: str = "manual", base: str | None = None, only=None, budget_s: float = BUDGET_S, runner=None, check_fn=None,
        clock=time.time, ver=None, log=None, workers: int = WORKERS) -> dict:
    """Every check and suite of `mode` -> the result dict (not saved here). The checks run here first, then the suites,
    `workers` at a time; a suite not started within budget_s is skipped (ok None, never a failure). runner / check_fn /
    ver: tests."""
    mode = mode if mode in MODES else "manual"
    log = log or (lambda t: None)
    t0 = clock()
    m0 = time.monotonic()
    v = ver if ver is not None else version()
    tmp_root = tempfile.mkdtemp(prefix="le_selftest_")
    items = plan(mode, only)
    rows: list = [None] * len(items)
    lock = threading.Lock()

    def note(i, row):
        rows[i] = row
        with lock:
            log(f"  [{'PASS' if row['ok'] else 'SKIP' if row['ok'] is None else 'FAIL'}] {row['label']} ({row.get('s')} s)"
                + (f": {row.get('why')}" if row["ok"] is not True else ""))

    def one(i, x):
        if time.monotonic() - m0 > budget_s:
            note(i, {"key": x["key"], "label": x["label"], "ok": None, "s": 0, "why": f"skipped: over the {budget_s:g} s budget"})
            return
        try:
            note(i, run_suite(x, tmp_root, runner=runner))
        except Exception as e:                       # never: run_suite does not raise; a row either way
            note(i, {"key": x["key"], "label": x["label"], "ok": False, "s": 0, "why": f"{e.__class__.__name__}: {_scrub(e, 120)}"})
    try:
        for i, (kind, x) in enumerate(items):
            if kind == "check":
                note(i, (check_fn or run_check)(x))
        todo = [(i, x) for i, (kind, x) in enumerate(items) if kind == "suite"]
        if workers <= 1:
            for i, x in todo:
                one(i, x)
        else:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="selftest") as ex:
                list(ex.map(lambda ix: one(*ix), todo))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    rows = [r for r in rows if r is not None]
    passed = sum(1 for r in rows if r["ok"] is True)
    failed = [r for r in rows if r["ok"] is False]
    b = baseline(base) if mode == "update" else None
    reg, known = regressions(rows, b)
    hold = mode == "update" and bool(reg)
    res = {"v": 1, "t": int(clock()), "t0": int(t0), "mode": mode, "version": v.get("sha"), "branch": v.get("branch"),
           "host": platform.node(), "passed": passed, "failed": len(failed), "skipped": sum(1 for r in rows if r["ok"] is None),
           "total": len(rows), "ok": not failed, "hold": hold, "hold_on": (reg[0]["label"] if hold else None),
           "first": [{"key": r["key"], "label": r["label"], "why": r.get("why")} for r in (reg + known)[:3]] if mode == "update"
           else [{"key": r["key"], "label": r["label"], "why": r.get("why")} for r in failed[:3]],
           "known": [r["key"] for r in known], "base_version": (b or {}).get("version"),
           "dur_s": round(time.monotonic() - m0, 1), "rows": rows}
    if mode == "update":
        res["also"] = "the update's own tests (NinjaTrader route, sizing, no Yahoo) passed right before"
    return res


def summary_line(res: dict) -> str:
    """One plain line: 'all 17 green in 74 s (abc1234)' / '2 of 17 failed: Start page (...), ...'."""
    if not res:
        return "not run yet"
    n, f = int(res.get("total") or 0), int(res.get("failed") or 0)
    ver = f" ({res.get('version')})" if res.get("version") else ""
    if not f:
        sk = int(res.get("skipped") or 0)
        return f"all {n - sk} green in {res.get('dur_s')} s{ver}" + (f", {sk} skipped (time budget)" if sk else "")
    first = ", ".join(f"{x['label']}" for x in res.get("first") or [])
    return f"{f} of {n} failed: {first}{ver}"


def hb_block(path: str | None = None, runner=None) -> dict | None:
    """The heartbeat's "selftest" block (~600 bytes); None before the first run and while nothing runs. Never raises."""
    try:
        r = last(path)
        rn = (runner or RUNNER).status()
        if not r and not rn.get("running"):
            return None
        return {"t": r.get("t"), "mode": r.get("mode"), "version": r.get("version"), "ok": r.get("ok"), "hold": r.get("hold"),
                "passed": r.get("passed"), "failed": r.get("failed"), "skipped": r.get("skipped"), "total": r.get("total"),
                "dur_s": r.get("dur_s"), "first": [{"label": x.get("label"), "why": _scrub(x.get("why"), 120)} for x in (r.get("first") or [])[:3]],
                "known": (r.get("known") or [])[:6], "say": summary_line(r) if r else None, **({"running": rn} if rn.get("running") else {})}
    except Exception:
        return None


# ---------------------------------------------------------------------------------------------- background runner
class Runner:
    """One `python -m engine.pc_selftest --mode <m>` child at a time, at below-normal priority, never in the poll (the
    server's Watcher and the Start page share RUNNER). start() returns at once; on_done(result) runs in the wait thread."""

    def __init__(self, cwd: str = ROOT, python: str = sys.executable, last_path: str | None = None, spawn=None):
        self.cwd, self.python, self.last_path = cwd, python, last_path
        self.spawn = spawn                     # tests: spawn(argv) -> {"code", ...} (synchronous)
        self._lock = threading.Lock()
        self.mode = None
        self.since = None
        self.last_done = None

    def busy(self) -> bool:
        return self.mode is not None

    def status(self) -> dict:
        return {"running": self.busy(), "mode": self.mode, "since": self.since, "last_done": self.last_done}

    def start(self, mode: str = "manual", on_done=None, wait: bool = False) -> dict:
        with self._lock:
            if self.mode is not None:
                return {"ok": False, "started": False, "running": True, "mode": self.mode, "say": f"a self-test is already running ({self.mode})"}
            self.mode, self.since = mode, int(time.time())

        t_start = time.time()

        def work():
            try:
                argv = ["-X", "utf8", "-m", "engine.pc_selftest", "--mode", mode, "--quiet"]
                if self.spawn is not None:
                    r = self.spawn(argv) or {}
                else:
                    r = run_child(argv, CHILD_TIMEOUT_S, self.cwd, self.python, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                res = last(self.last_path)
                if float(res.get("t") or 0) < t_start - 2:       # no new result: the child never got to save one
                    res = {"error": "the self-test stopped before its result: " + why_failed(r.get("out") or "", r.get("code"),
                                                                                        r.get("timed_out"), CHILD_TIMEOUT_S),
                           "mode": mode, "t": int(time.time())}
            except Exception as e:
                res = {"error": f"{e.__class__.__name__}: {e}"[:200], "mode": mode, "t": int(time.time())}
            finally:
                with self._lock:
                    self.mode = None
                    self.last_done = int(time.time())
            if on_done is not None:
                try:
                    on_done(res)
                except Exception:
                    pass
        if wait:
            work()
        else:
            threading.Thread(target=work, name=f"selftest-{mode}", daemon=True).start()
        return {"ok": True, "started": True, "mode": mode, "say": "Self-test started (1-3 minutes, low priority)"}


RUNNER = Runner()


# ---------------------------------------------------------------------------------------------- the phone pushes
def notice(res: dict, mode: str | None = None, now=None) -> dict | None:
    """The push for a finished run (None = nothing to say): sunday -> fail (kind selftest) or all green (kind selftest_ok);
    baseline -> only failures, once per version + failing set; manual (the Start page shows it) and update (engine/
    autoupdate pushes "Update held back") -> None."""
    if not res:
        return None
    mode = mode or res.get("mode")
    now = now or res.get("t") or time.time()
    day = _et(now).date().isoformat()
    ver = res.get("version") or "?"
    if mode not in ("sunday", "baseline"):
        return None
    try:
        from . import push
    except Exception:
        return None
    if res.get("error"):                     # the run itself broke (could not start, crashed, timed out)
        if mode != "sunday":
            return None
        return push.text_payload("PC", "selftest", "PC self-test could not run", _scrub(f"{res['error']}. Trading is not changed; "
                                 "run it from the Start page or tell Claude.", 400), key=f"selftest:sunday:{day}:error",
                                 t=int(now), url="#/accounts")
    if res.get("failed"):
        first = (res.get("first") or [{}])[0]
        title = f"PC self-test: {res['failed']} failed ({first.get('label')})"
        body = (f"{summary_line(res)}. First: {first.get('label')}: {first.get('why')}. Trading is not changed; the "
                "Start page shows every line. Tell Claude if it stays red.")
        fails = ",".join(sorted(r.get("key") for r in res.get("rows") or [] if r.get("ok") is False))
        key = f"selftest:{mode}:{day if mode == 'sunday' else ver}:{fails}"[:120]
        p = push.text_payload("PC", "selftest", title, _scrub(body, 560), key=key, t=int(now), url="#/accounts")
        return p
    if mode == "sunday":
        p = push.text_payload("PC", "selftest_ok", "PC self-test all green", f"{summary_line(res)}. Ready for the 18:00 open.",
                              key=f"selftest:green:{day}", t=int(now), url="#/accounts")
        return p
    return None


# ---------------------------------------------------------------------------------------------- CLI
def _render(res: dict) -> str:
    out = [f"PC self-test ({res.get('mode')}, version {res.get('version')}): {summary_line(res)}"]
    for r in res.get("rows") or []:
        tag = "PASS" if r["ok"] else "SKIP" if r["ok"] is None else "FAIL"
        out.append(f"  [{tag}] {r['label']:<42} {r.get('s', 0):>6} s" + (f"  {r.get('why')}" if r["ok"] is not True else ""))
    if res.get("known"):
        out.append(f"  (failing before this update too, not held: {', '.join(res['known'])})")
    return "\n".join(out)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.pc_selftest", description="PC self-test (read-only; never arms or routes)")
    ap.add_argument("--mode", default="manual", choices=MODES)
    ap.add_argument("--base", default=None, help="update mode: the commit before the update (its result is the baseline)")
    ap.add_argument("--only", default=None, help="comma-separated keys")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    if a.status:
        r = last()
        print(json.dumps(r, indent=1) if a.json else (_render(r) if r else "No self-test result yet."))
        return 0
    if a.list:
        for kind, x in plan("manual"):
            print(f"  {kind:<6} {x['key']:<14} {x['label']:<42} ~{MEASURED_S.get(x['key'], '?')} s here"
                  + ("" if x.get("update", True) else "   (not in update mode: the update runs it itself)"))
        return 0
    log = (lambda t: None) if a.quiet else (lambda t: print(t, flush=True))
    try:                                  # below-normal priority for this process too (it runs the in-process checks)
        if os.name == "nt":
            import psutil
            psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            os.nice(5)
    except Exception:
        pass
    res = run(a.mode, base=a.base, only=[k.strip() for k in a.only.split(",")] if a.only else None, log=log)
    if not a.no_save:
        try:
            save(res)
        except Exception as e:
            print(f"(result not saved: {e.__class__.__name__}: {e})", flush=True)
    print(json.dumps(res, indent=1) if a.json else _render(res), flush=True)
    if a.mode == "update":
        if res["hold"]:
            first = (res.get("first") or [{}])[0]
            print(f"{HOLD_MARK} {first.get('label')}: {first.get('why')}", flush=True)
            return 1
        return 0
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
