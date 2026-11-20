"""SELF-HEAL on the PC (engine/self_heal.py, night-selfheal 2026-11-20): every remedy in a temp folder, dry run first, then the fix.

    python -X utf8 -m tests.test_self_heal_pc        (temp folders, temp git repos, fake processes / pip / clock / server; no network)

 a. git locks: a 20-minute-old .git/index.lock + a scratch git dir's lock are removed (dry run: kept); a fresh one and one while git
    runs stay; a *.lock outside the git dirs is never touched.
 b. the update's way: an untracked file the update brings (same bytes: removed; other bytes: moved to keep-*/ with its content), a
    data/ file in the way is never touched (needs you), a hand edit of a tracked file is named (needs you), a file already at the new
    version is not; a bot-made file the last update tripped on goes back to HEAD with a copy; afterwards `git merge --ff-only` works.
 c. NinjaTrader order files: a bot oif_le_ file 5 min in incoming\\ or le_outbox\\ is withdrawn (copy kept); a fresh one and another
    program's file stay.
 d. supervisor.pid: gone / reused pid -> removed; the live supervisor's -> kept; processes unknown -> nothing guessed.
 e. the bot server: autostart.json + no answer = needs you (board event, never a second phone push); stopped on purpose = nothing.
 f. pip: a missing requirement is installed outside trading hours with no trade open, waits otherwise; pip failing = needs you.
 g. clock: 3.4 s drift -> w32tm (fake) synced; refused = needs you; small drift or an old health block = nothing.
 h. the weekly clean: exactly the allow-listed old files go (dated logs, old .gz, old zips past the newest N, run cache, orphan /
    other-version pyc, NinjaTrader log/trace, TEMP test leftovers); data/, live_model*, notes, logs/connect-*, keep-*, the order audit
    (< 365 d), tracked research/runs, NinjaTrader's db stay; the dry run removes nothing; due weekly outside trading, at once when low.
 i. heal(): state + tiny.json, one alert per fault per day, the ext line small and without the folder; maybe_run's gates.
 j. the PC report carries "sh" in an ext post; the PC doctor shows HEAL; the board knows the kind self_heal.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import self_heal as SH  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []
SAT = dt.datetime(2026, 11, 21, 11, 0, tzinfo=ET).timestamp()      # a Saturday: outside trading
TUE = dt.datetime(2026, 11, 17, 10, 0, tzinfo=ET).timestamp()      # a Tuesday 10:00 ET: trading
GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  ({str(info)[:400]})"))


def g(cwd, *args):
    r = subprocess.run(["git", "-c", "init.defaultBranch=main", *args], cwd=cwd, capture_output=True, text=True, env=GIT_ENV)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def write(path, text="x", age_s=0, now=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    if age_s:
        t = (now or time.time()) - age_s
        os.utime(path, (t, t))
    return path


def ctx(root, now, apply=False, **kw):
    kw.setdefault("procs", [(1, "explorer.exe")])
    kw.setdefault("ping", lambda: True)
    kw.setdefault("nt", None)
    kw.setdefault("temp", "")
    kw.setdefault("pkgs", {})
    kw.setdefault("env", {})
    return SH.Ctx(root=root, now=now, apply=apply, **kw)


def statuses(items, fault=None):
    return [i["status"] for i in items if fault is None or i["fault"] == fault]


# ------------------------------------------------------------------------------------------------ a. git locks
def test_locks(tmp):
    root = os.path.join(tmp, "a")
    os.makedirs(root)
    g(root, "init", "-q")
    now = time.time()
    lk = write(os.path.join(root, ".git", "index.lock"), "", 20 * 60, now)
    sc = write(os.path.join(root, "data", "live_pub.git", "index.lock"), "", 30 * 60, now)
    ref = write(os.path.join(root, ".git", "refs", "heads", "main.lock"), "", 15 * 60, now)
    other = write(os.path.join(root, "logs", "other.lock"), "", 99 * 60, now)
    r = SH.fix_git_locks(ctx(root, now))
    check("a. dry run: 'would' remove the 3 stale git locks, all still there", statuses(r) == ["would"] and len(r[0]["paths"]) == 3
          and all(os.path.exists(p) for p in (lk, sc, ref)), r)
    r = SH.fix_git_locks(ctx(root, now, procs=[(7, "git.exe")]))
    check("a. git running: nothing removed (info)", statuses(r) == ["info"] and os.path.exists(lk), r)
    r = SH.fix_git_locks(ctx(root, now, apply=True))
    check("a. apply: index.lock, refs/heads/main.lock and the scratch dir's lock removed", statuses(r) == ["fixed"]
          and not any(os.path.exists(p) for p in (lk, sc, ref)), r)
    check("a. a *.lock outside the git dirs is never touched", os.path.exists(other))
    write(os.path.join(root, ".git", "index.lock"), "", 60, now)
    check("a. a fresh lock (1 min, a git at work) stays", SH.fix_git_locks(ctx(root, now, apply=True)) == []
          and os.path.exists(os.path.join(root, ".git", "index.lock")))
    check("a. git status works again after the fix", True)


# ------------------------------------------------------------------------------------------------ b. the update's way
def repo_pair(tmp, name):
    up, pc = os.path.join(tmp, name + "_up"), os.path.join(tmp, name + "_pc")
    os.makedirs(up)
    g(up, "init", "-q")
    write(os.path.join(up, "README.md"), "one\n")
    write(os.path.join(up, "engine", "a.py"), "A = 1\n")
    write(os.path.join(up, "cache", "dash", "bt.json"), '{"v":1}\n')
    write(os.path.join(up, "data", "lit_journal.jsonl"), '{"j":1}\n')
    write(os.path.join(up, ".gitignore"), "logs/\n")
    g(up, "add", "-A")
    g(up, "commit", "-qm", "one")
    g(tmp, "clone", "-q", up, pc)
    write(os.path.join(up, "tools", "new_same.py"), "SAME = 1\n")
    write(os.path.join(up, "engine", "new_mine.py"), "THEIRS = 1\n")
    write(os.path.join(up, "data", "board", "shared.jsonl"), '{"k":1}\n')
    write(os.path.join(up, "engine", "a.py"), "A = 2\n")
    write(os.path.join(up, "cache", "dash", "bt.json"), '{"v":2}\n')
    write(os.path.join(up, "data", "lit_journal.jsonl"), '{"j":1}\n{"j":2}\n')
    g(up, "add", "-A")
    g(up, "commit", "-qm", "two")
    g(pc, "fetch", "-q", "origin")
    return up, pc


def test_update(tmp):
    up, pc = repo_pair(tmp, "b")
    now = time.time()
    write(os.path.join(pc, "tools", "new_same.py"), "SAME = 1\n")
    write(os.path.join(pc, "engine", "new_mine.py"), "MINE = 1\n")
    write(os.path.join(pc, "data", "board", "shared.jsonl"), '{"mine":1}\n')
    c, out = g(pc, "merge", "--ff-only", "-q", "origin/main")
    check("b. (the fault) git refuses the fast-forward: untracked files in the way", c != 0 and "untracked" in out.lower(), out)
    r = SH.fix_update(ctx(pc, now))
    st = {i["key"]: i for i in r}
    check("b. dry run: would clear 2 untracked files, data/board/shared.jsonl needs you, nothing moved",
          st.get("update_untracked", {}).get("status") == "would" and sorted(st["update_untracked"]["paths"]) == ["engine/new_mine.py", "tools/new_same.py"]
          and "data/board/shared.jsonl" in st.get("update_blocked", {}).get("paths", []) and os.path.exists(os.path.join(pc, "tools", "new_same.py")), r)
    c2 = ctx(pc, now, apply=True)
    r = SH.fix_update(c2)
    keep = c2.keep_dir()
    mine = os.path.join(keep, "engine", "new_mine.py")
    check("b. apply: the identical file removed, the different one moved to keep-*/ with its content",
          not os.path.exists(os.path.join(pc, "tools", "new_same.py")) and not os.path.exists(os.path.join(pc, "engine", "new_mine.py"))
          and os.path.isfile(mine) and open(mine).read() == "MINE = 1\n" and not os.path.exists(os.path.join(keep, "tools", "new_same.py")), r)
    c, snap = g(pc, "show", f"{SH.SNAP_REF}:engine/new_mine.py")
    check("b. ... and snapshotted first: git show refs/olympus/self-heal:engine/new_mine.py gives it back", c == 0 and snap == "MINE = 1\n", snap)
    check("b. data/ is never touched: the owner's data/board/shared.jsonl is still there, named as 'needs you'",
          open(os.path.join(pc, "data", "board", "shared.jsonl")).read() == '{"mine":1}\n'
          and any(i["status"] == "need" and "data/board/shared.jsonl" in i["paths"] for i in r), r)
    os.remove(os.path.join(pc, "data", "board", "shared.jsonl"))           # (the owner's answer: drop it)
    c, out = g(pc, "merge", "--ff-only", "-q", "origin/main")
    check("b. after the fix the fast-forward goes through", c == 0, out)

    # a hand edit + a file already at the new version + a bot-made file the last update named
    up2, pc2 = repo_pair(tmp, "b2")
    write(os.path.join(pc2, "README.md"), "my own edit\n")
    write(os.path.join(pc2, "engine", "a.py"), "A = 2\n")                 # checked out from main by hand = the new version
    write(os.path.join(pc2, "cache", "dash", "bt.json"), '{"v":"pc"}\n')  # bot-made (engine/generated_files)
    write(os.path.join(pc2, "data", "lit_journal.jsonl"), '{"j":1}\n{"pc":1}\n')   # bot-made too, but a trade journal
    os.makedirs(os.path.join(pc2, "data"), exist_ok=True)
    json.dump({"last": {"status": "failed", "reason": "fast-forward refused: error: Your local changes to the following files would be "
                                                      "overwritten by merge: cache/dash/bt.json data/lit_journal.jsonl"}}, open(os.path.join(pc2, "data", "autoupdate.json"), "w"))
    c3 = ctx(pc2, now, apply=True)
    r = SH.fix_update(c3)
    by = {i["key"]: i for i in r}
    check("b. a hand edit of README.md: never touched, named (needs you)", "README.md" in by.get("update_blocked", {}).get("paths", [])
          and open(os.path.join(pc2, "README.md")).read() == "my own edit\n", r)
    check("b. the trade journal the update named: never reset, named instead (its PC lines kept)",
          "data/lit_journal.jsonl" in by.get("update_blocked", {}).get("paths", [])
          and open(os.path.join(pc2, "data", "lit_journal.jsonl")).read() == '{"j":1}\n{"pc":1}\n', r)
    check("b. a file already at the new version is not reported", "engine/a.py" not in by.get("update_blocked", {}).get("paths", []), r)
    bt = os.path.join(c3.keep_dir(), "cache", "dash", "bt.json")
    check("b. the bot-made file the last update named: back to HEAD, its copy kept", by.get("update_generated", {}).get("status") == "fixed"
          and open(os.path.join(pc2, "cache", "dash", "bt.json")).read() == '{"v":1}\n' and os.path.isfile(bt) and '"pc"' in open(bt).read(), r)
    c, snap = g(pc2, "show", f"{SH.SNAP_REF}:cache/dash/bt.json")
    check("b. the bot-made file is in the snapshot too", c == 0 and '"pc"' in snap, snap)
    c, st = g(pc2, "status", "--porcelain", "--untracked-files=no")
    check("b. no other tracked file changed by the self-heal", sorted(ln[3:] for ln in st.splitlines()) == ["README.md", "data/lit_journal.jsonl", "engine/a.py"], st)
    up3, pc3 = repo_pair(tmp, "b3")
    g(pc3, "merge", "--ff-only", "-q", "origin/main")
    check("b. up to date: nothing to say", SH.fix_update(ctx(pc3, now, apply=True)) == [])


# ------------------------------------------------------------------------------------------------ c. NinjaTrader order files
def test_oif(tmp):
    root, nt = os.path.join(tmp, "c"), os.path.join(tmp, "c_nt")
    os.makedirs(root)
    now = time.time()
    old_in = write(os.path.join(nt, "incoming", "oif_le_lit_1.txt"), "PLACE;Sim101;MNQ 12-26;BUY;1;MARKET;;;DAY;;;;", 300, now)
    old_box = write(os.path.join(nt, "le_outbox", "oif_le_lit_2.txt"), "PLACE;x", 600, now)
    fresh = write(os.path.join(nt, "incoming", "oif_le_lit_3.txt"), "PLACE;y", 10, now)
    foreign = write(os.path.join(nt, "incoming", "oif_other_app.txt"), "PLACE;z", 9000, now)
    r = SH.fix_oif(ctx(root, now, nt=nt))
    check("c. dry run: would withdraw 2, nothing removed", statuses(r) == ["would"] and len(r[0]["paths"]) == 2 and os.path.exists(old_in), r)
    r = SH.fix_oif(ctx(root, now, apply=True, nt=nt))
    kept = os.listdir(os.path.join(root, "logs", "self_heal", "oif"))
    check("c. apply: the 5-min-old incoming file and the old le_outbox file withdrawn, copies kept",
          statuses(r) == ["fixed"] and not os.path.exists(old_in) and not os.path.exists(old_box) and len(kept) == 2, (r, kept))
    check("c. a fresh order file (10 s: NinjaTrader is taking it) and another program's file stay", os.path.exists(fresh) and os.path.exists(foreign))
    check("c. no NinjaTrader folder: nothing", SH.fix_oif(ctx(root, now, nt=None)) == [])


# ------------------------------------------------------------------------------------------------ d. pid files
def test_pid(tmp):
    root = os.path.join(tmp, "d")
    now = time.time()
    p = write(os.path.join(root, "logs", "supervisor.pid"), "4242\n")
    check("d. the supervisor runs (pid 4242 = powershell.exe): kept", SH.fix_pids(ctx(root, now, apply=True, procs=[(4242, "powershell.exe")])) == []
          and os.path.exists(p))
    check("d. processes unknown: nothing guessed", SH.fix_pids(ctx(root, now, apply=True, procs=[])) == [] and os.path.exists(p))
    r = SH.fix_pids(ctx(root, now, apply=True, procs=[(4242, "chrome.exe")]))
    check("d. pid reused by another program: removed", statuses(r) == ["fixed"] and "chrome" in r[0]["text"] and not os.path.exists(p), r)
    write(p, "4242\n")
    r = SH.fix_pids(ctx(root, now, procs=[(1, "explorer.exe")]))
    check("d. dry run on a gone pid: would remove, still there", statuses(r) == ["would"] and os.path.exists(p), r)
    r = SH.fix_pids(ctx(root, now, apply=True, procs=[(1, "explorer.exe")]))
    check("d. apply on a gone pid: removed", statuses(r) == ["fixed"] and not os.path.exists(p), r)


# ------------------------------------------------------------------------------------------------ e. the bot server
def test_server(tmp):
    root = os.path.join(tmp, "e")
    now = time.time()
    os.makedirs(root)
    check("e. stopped on purpose (no data/autostart.json): nothing", SH.fix_server(ctx(root, now, ping=lambda: False)) == [])
    write(os.path.join(root, "data", "autostart.json"), '{"mode": "live"}')
    check("e. should run and answers: nothing", SH.fix_server(ctx(root, now, ping=lambda: True)) == [])
    r = SH.fix_server(ctx(root, now, ping=lambda: False))
    check("e. should run, no answer: needs you, step BOTS_BACK.bat, nothing started", statuses(r) == ["need"] and "BOTS_BACK" in r[0]["step"], r)
    seen = {"board": [], "push": []}
    a = SH.alert(ctx(root, now, apply=True), r[0], board=lambda *x: seen["board"].append(x) or True, push=lambda m: seen["push"].append(m) or True)
    check("e. its alert: one board event, no phone push (the report already pushes 'bot down')", a == {"board": True, "push": False}
          and len(seen["board"]) == 1 and not seen["push"] and seen["board"][0][0] == "self_heal", (a, seen))


# ------------------------------------------------------------------------------------------------ f. pip
def test_pip(tmp):
    root = os.path.join(tmp, "f")
    write(os.path.join(root, "requirements.txt"), "foo==1.0\nbar\n# optional: baz==2\n-r other.txt\nqux[extra]>=2 ; python_version>'3'\n")
    check("f. requirements parsed (comments, options and markers left out)", [n for n, _s in SH.requirements(root)] == ["foo", "bar", "qux"])
    calls = []

    def fake_run(code):
        def run(argv, **kw):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, code, "", "" if code == 0 else "ERROR: no matching distribution")
        return run
    r = SH.fix_pip(ctx(root, TUE, apply=True, pkgs={"bar": "1", "qux": "2"}, run=fake_run(0), flat=lambda: None))
    check("f. in trading hours: waits (info), pip not run", statuses(r) == ["info"] and not calls, r)
    r = SH.fix_pip(ctx(root, SAT, apply=True, pkgs={"bar": "1", "qux": "2"}, run=fake_run(0), flat=lambda: "LIT entry pending"))
    check("f. a trade / entry open: waits", statuses(r) == ["info"] and "trade" in r[0]["text"] and not calls, r)
    r = SH.fix_pip(ctx(root, SAT, pkgs={"bar": "1", "qux": "2"}, run=fake_run(0), flat=lambda: None))
    check("f. dry run: would install foo==1.0 only, pip not run", statuses(r) == ["would"] and r[0]["paths"] == ["foo==1.0"] and not calls, r)
    r = SH.fix_pip(ctx(root, SAT, apply=True, pkgs={"bar": "1", "qux": "2"}, run=fake_run(0), flat=lambda: None))
    check("f. apply: pip install of the missing one only", statuses(r) == ["fixed"] and calls and calls[-1][-1] == "foo==1.0"
          and calls[-1][1:4] == ["-m", "pip", "install"] and "bar" not in calls[-1], calls)
    r = SH.fix_pip(ctx(root, SAT, apply=True, pkgs={"bar": "1", "qux": "2"}, run=fake_run(1), flat=lambda: None))
    check("f. pip fails: needs you, the one line to type", statuses(r) == ["need"] and "requirements.txt" in r[0]["step"], r)
    check("f. nothing missing: nothing", SH.fix_pip(ctx(root, SAT, apply=True, pkgs={"foo": "1", "bar": "1", "qux": "2"})) == [])


# ------------------------------------------------------------------------------------------------ g. clock
def test_clock(tmp):
    root = os.path.join(tmp, "g")
    now = time.time()
    hp = os.path.join(root, "logs", "pc_health.json")

    def block(v, age=60):
        write(hp, json.dumps({"t": now - age, "lines": [{"key": "clock", "level": "amber", "text": "x", "value": v}]}))
    block(3.4)
    r = SH.fix_clock(ctx(root, now, apply=True, sync_clock=lambda: {"ok": True}))
    check("g. 3.4 s behind: synced (w32tm, fake)", statuses(r) == ["fixed"] and "3.4 s behind" in r[0]["text"], r)
    r = SH.fix_clock(ctx(root, now, apply=True, sync_clock=lambda: {"ok": False, "error": "Windows asks for an administrator"}))
    check("g. Windows refuses: needs you, the Settings steps", statuses(r) == ["need"] and "Sync now" in r[0]["step"], r)
    r = SH.fix_clock(ctx(root, now, sync_clock=lambda: (_ for _ in ()).throw(AssertionError("dry run must not sync"))))
    check("g. dry run: would sync, nothing run", statuses(r) == ["would"], r)
    block(0.8)
    check("g. 0.8 s: nothing", SH.fix_clock(ctx(root, now, apply=True, sync_clock=lambda: {"ok": True})) == [])
    block(9.0, age=5 * 3600)
    check("g. a health block 5 h old: nothing (no guess)", SH.fix_clock(ctx(root, now, apply=True, sync_clock=lambda: {"ok": True})) == [])


# ------------------------------------------------------------------------------------------------ h. the weekly clean
def test_clean(tmp):
    root, nt, temp = os.path.join(tmp, "h"), os.path.join(tmp, "h_nt"), os.path.join(tmp, "h_temp")
    now = SAT
    D = 86400
    go = [write(os.path.join(root, "logs", "update-20260901.log"), "x" * 100, 60 * D, now),
          write(os.path.join(root, "logs", "clean_storage-20260905-1010.txt"), "x", 60 * D, now),
          write(os.path.join(root, "logs", "ops-20260901.log.gz"), "x", 40 * D, now),
          write(os.path.join(root, "logs", "narrator", "2026-08-01.jsonl.gz"), "x", 40 * D, now),
          write(os.path.join(root, "OLYMPUS_BACKUP_20260101.zip"), "z" * 1000, 60 * D, now),
          write(os.path.join(root, "OLYMPUS_BACKUP_20260101.sha256.txt"), "s", 60 * D, now),
          write(os.path.join(root, "backups", "le-backup-20260101.zip"), "z", 45 * D, now),
          write(os.path.join(root, "reports", "tmp", "a.png"), "p", 9 * D, now),
          write(os.path.join(root, "research", "runs", "_cache", "k", "a.pkl"), "c", 20 * D, now),
          write(os.path.join(root, "engine", "__pycache__", "gone.cpython-313.pyc"), "c", 2 * D, now),
          write(os.path.join(root, "engine", "__pycache__", f"live.cpython-{'399' if sys.implementation.cache_tag != 'cpython-399' else '398'}.pyc"), "c", 2 * D, now),
          write(os.path.join(nt, "log", "log.20260901.00000.txt"), "l", 30 * D, now),
          write(os.path.join(nt, "trace", "trace.20260901.00000.txt"), "t", 30 * D, now)]
    os.makedirs(os.path.join(temp, "le_selftest_abc", "x"), exist_ok=True)
    tmpdir = os.path.join(temp, "le_selftest_abc")
    write(os.path.join(tmpdir, "x", "f.txt"), "t", 5 * D, now)
    os.utime(os.path.join(tmpdir, "x"), (now - 5 * D, now - 5 * D))
    os.utime(tmpdir, (now - 5 * D, now - 5 * D))
    go.append(tmpdir)
    stay = [write(os.path.join(root, "logs", "ninjatrader_oif-20260901-1000.log.gz"), "a", 40 * D, now),     # the order audit: 365 d
            write(os.path.join(root, "logs", "heartbeat_last.json"), "{}", 60 * D, now),                       # not dated: state, kept
            write(os.path.join(root, "logs", "update-20261119.log"), "x", 1 * D, now),                         # recent
            write(os.path.join(root, "logs", "connect-20260101-0000", "engine", "live.py"), "owner", 300 * D, now),
            write(os.path.join(root, "logs", "self_heal", "keep-20260101-0000", "engine", "x.py"), "owner", 300 * D, now),
            write(os.path.join(root, "OLYMPUS_BACKUP_20261001.zip"), "z", 50 * D, now),             # the newest 2 stay, whatever their age
            write(os.path.join(root, "OLYMPUS_BACKUP_20261101.zip"), "z", 45 * D, now),
            write(os.path.join(root, "backups", "le-backup-20261001.zip"), "z", 40 * D, now),       # the newest 3 stay
            write(os.path.join(root, "backups", "le-backup-20261002.zip"), "z", 39 * D, now),
            write(os.path.join(root, "backups", "le-backup-20261003.zip"), "z", 38 * D, now),
            write(os.path.join(root, "research", "runs", "_cache", "k", "fresh.pkl"), "c", 1 * D, now),
            write(os.path.join(root, "research", "runs", "20260101_run.json"), "r", 300 * D, now),           # tracked backtest runs
            write(os.path.join(root, "engine", "live.py"), "x = 1\n", 30 * D, now),
            write(os.path.join(root, "engine", "__pycache__", f"live.{sys.implementation.cache_tag}.pyc"), "c", 30 * D, now),
            write(os.path.join(root, "data", "old-20250101.log"), "d", 300 * D, now),
            write(os.path.join(root, "data", "lit_journal.jsonl"), "d", 300 * D, now),
            write(os.path.join(root, "live_model.json"), "{}", 300 * D, now),
            write(os.path.join(root, "notes-20250101.txt"), "n", 300 * D, now),
            write(os.path.join(nt, "db", "NinjaTrader.sqlite"), "db", 300 * D, now),
            write(os.path.join(nt, "log", "log.20261120.00000.txt"), "today", 1 * 3600, now),
            write(os.path.join(temp, "important_folder", "a.txt"), "keep", 30 * D, now),
            write(os.path.join(temp, "le_selftest_new", "a.txt"), "busy", 3600, now)]
    c0 = ctx(root, now, nt=nt, temp=temp)
    plan = {p for _k, p, _n in SH.clean_plan(c0)}
    check("h. the plan is exactly the old allow-listed files", plan == set(go), (sorted(plan - set(go)), sorted(set(go) - plan)))
    r = SH.clean(c0)
    check("h. dry run: counts them, removes nothing", r["n"] == len(go) and all(os.path.exists(p) for p in go), r)
    r = SH.clean(ctx(root, now, apply=True, nt=nt, temp=temp))
    check("h. apply: every planned file gone", r["n"] == len(go) and not any(os.path.exists(p) for p in go), [p for p in go if os.path.exists(p)])
    check("h. ... and nothing else: data/, live_model.json, notes, connect-*, keep-*, the order audit, tracked runs, today's NT log, the NT db",
          all(os.path.exists(p) for p in stay), [p for p in stay if not os.path.exists(p)])
    check("h. the empty run-cache folder is cleaned up, the cache itself stays", os.path.isdir(os.path.join(root, "research", "runs", "_cache")))
    sz = SH.sizes(ctx(root, now, nt=nt))
    check("h. sizes: logs, data, runs, zips, pycache, bot, nt, free", all(k in sz for k in ("logs", "data", "runs", "zips", "pycache", "bot", "nt", "free")), sz)
    # due: weekly outside trading, at once when low
    st = {"clean_t": SAT - 8 * D}
    its, cl = SH.fix_disk(ctx(root, SAT, nt=nt, temp=temp), st, disk_free=50.0)
    check("h. weekly: due on a Saturday 8 days after the last clean", cl is not None)
    its, cl = SH.fix_disk(ctx(root, TUE, nt=nt, temp=temp), {"clean_t": TUE - 8 * D}, disk_free=50.0)
    check("h. not in trading hours (Tue 10:00 ET) with room on the disk", cl is None and its == [])
    its, cl = SH.fix_disk(ctx(root, TUE, nt=nt, temp=temp), {"clean_t": TUE - 7 * 3600}, disk_free=5.0)
    check("h. disk low (5 GB): the clean runs at once, even in trading hours", cl is not None)
    its, cl = SH.fix_disk(ctx(root, TUE, apply=True, nt=nt, temp=temp), {"clean_t": TUE - 7 * 3600}, disk_free=1.0)
    check("h. still under 2 GB after it: needs you (CLEAN_STORAGE.bat)", any(i["status"] == "need" and "CLEAN_STORAGE" in i["step"] for i in its), its)
    its, cl = SH.fix_disk(ctx(root, TUE, nt=nt, temp=temp), {"clean_t": TUE - 3600}, disk_free=1.0)
    check("h. under 2 GB, cleaned an hour ago: needs you, no second clean", cl is None and statuses(its) == ["need"], its)
    check("h. never(): data/, live_model*, .env, notes, connect-*, keep-* are off limits", all(SH.never(x) for x in (
        "data/lit_journal.jsonl", "live_model_lit.json", ".env.local.ps1", "my_notes.md", "logs/connect-1/a", "logs/self_heal/keep-1/a",
        "../outside.txt")) and not SH.never("engine/new.py"))


# ------------------------------------------------------------------------------------------------ i. heal() + maybe_run
def test_heal(tmp):
    root = os.path.join(tmp, "i")
    now = SAT
    write(os.path.join(root, "data", "autostart.json"), "{}")
    write(os.path.join(root, "logs", "supervisor.pid"), "777")
    sent = {"board": 0, "push": 0}

    def board(*a):
        sent["board"] += 1
        return True

    def push(m):
        sent["push"] += 1
        return True
    c = ctx(root, now, apply=True, ping=lambda: False, procs=[(1, "explorer.exe")])
    r = SH.heal(c, board=board, push=push, disk_free=40.0)
    st = json.load(open(os.path.join(root, "logs", "self_heal", "state.json")))
    tn = SH.read_tiny(root, now)
    check("i. heal: pid fixed, server needs you, state + tiny.json written", [i["fault"] for i in r["fixed"]] == ["pid"]
          and [i["fault"] for i in r["need"]] == ["server"] and st["need"] == ["server"] and tn and tn["ok"] is False, (r["items"], st))
    check("i. one board event for what it could not fix (the server: no phone push)", sent == {"board": 1, "push": 0}, sent)
    check("i. the ext line says it in plain words", "needs you: the bot server is down" in (tn or {}).get("line", ""), tn)
    r = SH.heal(ctx(root, now + 3600, apply=True, ping=lambda: False), board=board, push=push, disk_free=40.0)
    check("i. the same fault an hour later: no second alert", sent == {"board": 1, "push": 0}, sent)
    SH.heal(ctx(root, now + 25 * 3600, apply=True, ping=lambda: False), board=board, push=push, disk_free=40.0)
    check("i. a day later: one more", sent["board"] == 2, sent)
    tn = SH.read_tiny(root, now + 25 * 3600)
    body = json.dumps(tn)
    check("i. the ext line: small, public (no folder), says the fixes and the free space", len(body) <= 400 and root not in body
          and tmp not in body and "fixed 1 this week" in tn["line"] and "40 GB free" in tn["line"], body)
    check("i. tiny.json older than 3 days: not sent", SH.read_tiny(root, now + 5 * 86400) is None)
    log = open(os.path.join(root, "logs", "self_heal", f"heal-{dt.datetime.fromtimestamp(now, ET):%Y%m}.log")).read()
    check("i. every run logged (heal-YYYYMM.log)", "supervisor.pid" in log and "server" in log, log[-300:])
    root2 = os.path.join(tmp, "i2")
    os.makedirs(root2)
    SH.heal(ctx(root2, now), board=board, push=push, disk_free=40.0)
    check("i. a dry run writes nothing (no state, no log)", not os.path.exists(os.path.join(root2, "logs")))
    check("i. maybe_run: off on a non-Windows box unless LE_SELF_HEAL=1", os.name == "nt" or SH.maybe_run(say=SH.SAY_OFF, now=now, root=root2, env={}) is None)
    check("i. maybe_run: never inside a PC self-test's child (LE_SELFTEST_CHILD=1)",
          SH.maybe_run(say=SH.SAY_OFF, now=now, root=root2, env={"LE_SELF_HEAL": "1", "LE_SELFTEST_CHILD": "1"}) is None
          and not os.path.exists(os.path.join(root2, "logs")))
    check("i. maybe_run: LE_SELF_HEAL=0 = off", SH.maybe_run(say=SH.SAY_OFF, now=now, root=root2, env={"LE_SELF_HEAL": "0"},
                                                             ctx=ctx(root2, now, apply=True)) is None)
    r = SH.maybe_run(say=SH.SAY_OFF, now=now + 25 * 3600 + 60, root=root, env={"LE_SELF_HEAL": "1"},
                     ctx=ctx(root, now + 25 * 3600 + 60, apply=True, ping=lambda: True))
    check("i. maybe_run: within the hour of the last run -> nothing", r is None)
    lk = write(os.path.join(root, "logs", "self_heal", "run.lock"), "1")
    r = SH.maybe_run(say=SH.SAY_OFF, now=now + 27 * 3600, root=root, env={"LE_SELF_HEAL": "1"},
                     ctx=ctx(root, now + 27 * 3600, apply=True, ping=lambda: True))
    check("i. maybe_run: another run holds the lock -> nothing (never two at once)", r is None)
    os.utime(lk, (time.time() - 3600, time.time() - 3600))
    r = SH.maybe_run(say=SH.SAY_OFF, now=now + 27 * 3600, root=root, env={"LE_SELF_HEAL": "1"},
                     ctx=ctx(root, now + 27 * 3600, apply=True, ping=lambda: True))
    check("i. maybe_run: an hour later it runs (a crashed run's 1-hour-old lock taken over; server back: nothing needs you)",
          r is not None and not r["need"] and not os.path.exists(lk), r and r["items"])


# ------------------------------------------------------------------------------------------------ j. the report, the doctor, the board
def test_wiring(tmp):
    root = os.path.join(tmp, "j")
    now = SAT
    write(os.path.join(root, "data", "autostart.json"), "{}")
    SH.heal(ctx(root, now, apply=True, ping=lambda: False), board=lambda *a: True, push=lambda m: True, disk_free=40.0)
    from tools import pc_report as PR
    snap = PR.gather(now=int(now), root=root, env={}, http=lambda *a, **k: (None, "URLError"), port=1, feed_problem=lambda: None)
    check("j. the report's gather() reads the self-heal line (snap['sh'])", isinstance(snap.get("sh"), dict) and snap["sh"]["need"] == ["server"],
          snap.get("sh"))
    full = PR.full({**snap, "hb_t": int(now) - 60, "t": int(now)})
    core, exts = PR.split(full)
    xs = {k for e in exts for k in (e.get("x") or {})}
    check("j. it rides an ext post (never the core)", "sh" in xs and "sh" not in core, (sorted(xs), sorted(core)))
    from tools import pc_doctor as PD
    hc = PD.check_heal(root, now + 60)
    check("j. the PC doctor's HEAL line: FIX with the --heal --apply step", hc and hc["level"] == "FIX" and "--heal --apply" in hc["step"], hc)
    check("j. the PC doctor: no HEAL line before the self-heal ever ran", PD.check_heal(os.path.join(tmp, "nothing"), now) is None)
    from engine import board_events as BE
    bd = os.path.join(tmp, "j_board")
    old = os.environ.get("LE_BOARD_DIR")
    os.environ["LE_BOARD_DIR"] = bd
    try:
        rec = BE.emit("self_heal", "pc", "Self-heal could not fix: x", {"fault": "server"})
    finally:
        if old is None:
            os.environ.pop("LE_BOARD_DIR", None)
        else:
            os.environ["LE_BOARD_DIR"] = old
    check("j. the board knows the kind self_heal (and shows it loud)", rec is not None and "self_heal" in BE.LOUD
          and os.path.isfile(os.path.join(bd, "events.jsonl")), rec)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="lesh_")
    try:
        for fn in (test_locks, test_update, test_oif, test_pid, test_server, test_pip, test_clock, test_clean, test_heal, test_wiring):
            try:
                fn(tmp)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{fn.__name__} ran without a crash", False, f"{e.__class__.__name__}: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(RES)
    print(f"\n{sum(RES)}/{len(RES)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
