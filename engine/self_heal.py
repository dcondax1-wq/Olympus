r"""SELF-HEAL: the PC doctor's hands (night-selfheal 2026-11-20). docs/SELF_HEAL.md.

Owner 2026-11-20: "Bug fixes/errors: any errors in our overall system. Fix, and have something that will auto fix." and "Save room
for my PC, we need everything to run perfect." The PC doctor (tools/pc_doctor.py) only LOOKS; this fixes the KNOWN faults by itself,
each with one safe remedy, a dry run first, an allow-list of paths, a log line, and ONE board event + IMPORTANT phone alert only when
it could NOT fix something (at most once a day per fault). It runs from the 15-minute PC report task (tools/pc_report.py main ->
maybe_run: at most once an hour, the weekly clean once a week or at once when the disk is low). Never in the live loop, never in
the bot server, never on a trade: it never starts, stops, arms or routes the bot and never writes an order.

  fault        what it looks for                                         the one remedy
  git_lock     a git lock (.git/index.lock, HEAD.lock, refs/**.lock ...)  deleted when 10+ min old and no git is running
               in this folder's .git or the bot's scratch git dirs        (a crashed git leaves it; every later git then fails)
               (data/*_pub.git) left by a killed git
  update       the update source's newest code (the ref the auto-update   * an untracked file in the way: the same bytes as the
               fetched) cannot fast-forward:                                update's -> removed; else moved to logs/self_heal/keep-*/
               "untracked working tree files would be overwritten"        * a bot-made (engine/generated_files) file the last update
               or a bot-made file the last update named                     named: copied to keep-*/, then git checkout HEAD -- it
                                                                          both snapshot first (a commit at refs/olympus/self-heal)
               a hand edit of any other tracked file                      never touched: the alert names the file
  disk         free space on the bot's drive under 10 GB                  the weekly clean at once; still under 2 GB: alert
  oif          a bot order file (oif_le_*) in NinjaTrader's incoming\     withdrawn (deleted; a copy in logs/self_heal/oif/): it must
               for 2+ min (NinjaTrader was off), or in le_outbox\          never run late. The adapter's own rule
                                                                            (engine/ninjatrader._sweep_stale_oifs) when no bot runs
  pid          logs/supervisor.pid naming a process that is gone or not   deleted (STOP_BOT would wait for, then stop, that pid)
               PowerShell (a crash / restart)
  server       the bot server does not answer while data/autostart.json   nothing automatic (the supervisor run_bot.ps1 restarts a
               says the bot should run                                      crashed server itself): board event, the step BOTS_BACK.bat;
                                                                            the 15-minute report already pushes "bot down"
  pip          a package of requirements.txt is not installed             pip install of the missing ones only, outside 01:50-16:00 ET
                                                                            on a weekday and with no trade open
  clock        the bot's clock probe (logs/pc_health.json) 2+ s off       w32tm /resync (engine/go.sync_clock); refused: alert

Weekly clean (the PC side of tools/disk_clean.py; CLEAN_STORAGE.bat stays the big manual one): only files that rebuild or are
rotation output, by age: dated logs (a YYYYMMDD / YYYY-MM-DD name) and logs/*.gz after 30 days (the order audit
ninjatrader_oif*.gz: 365), OLYMPUS_BACKUP_*.zip code zips after 14 days (the newest 2 stay), backups/le-*.zip after 14 days (the
newest 3 stay), reports/tmp after 7 days, research/runs/_cache after 14 days, __pycache__ files of a deleted .py or of another
Python version, NinjaTrader's own log\\ and trace\\ text files after 14 days, test / browser leftovers in TEMP after 2 days.
NEVER: data/, live_model*.json, second_model.json, notes, .env*, logs/connect-* and logs/self_heal/keep-* (owner copies), any
file git tracks except the documented generated files, NinjaTrader's db / workspaces / templates, anything outside these folders.
Sizes (logs, data, research, runs, zips, __pycache__, .git, NinjaTrader) go to the PC report as one ext line ("sh").

  python -X utf8 -m engine.self_heal               dry run: what it would fix now (changes nothing)
  python -X utf8 -m engine.self_heal --apply       fix now (what the hourly run does)
  python -X utf8 -m engine.self_heal --clean       dry run of the weekly clean, with sizes; --clean --apply frees it
  python -X utf8 -m engine.self_heal --sizes       what grows in the bot folder
  python -X utf8 -m engine.self_heal --status      the last run
LE_SELF_HEAL=0 = off. It runs by itself on Windows only (LE_SELF_HEAL=1 forces it elsewhere), never in a PC self-test's child. Files: logs/self_heal/ (gitignored):
state.json, tiny.json (the ext line), heal-YYYYMM.log, keep-*/ and oif/ (copies). Tests: tests/test_self_heal_pc.py (temp folders).
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GB = 1024 ** 3
EVERY_S = 55 * 60                           # the hourly run (the report task runs every 15 min)
CLEAN_EVERY_S = 7 * 86400                   # the weekly clean
CLEAN_LOW_EVERY_S = 6 * 3600                # with a low disk: again at most every 6 h
LOCK_AGE_S = 10 * 60                        # a git lock older than this with no git running = left by a killed git
OIF_AGE_S = 120                             # a bot order file NinjaTrader left this long: withdrawn (the adapter's ack wait is <= 30 s)
DISK_LOW_GB = 10.0                          # as engine/ops_checks (amber < 10 GB)
DISK_RED_GB = 2.0                           # after the clean still below: alert
CLOCK_MAX_S = 2.0                           # engine/pc_health clock_amber_s
HEALTH_FRESH_S = 2 * 3600
ALERT_EVERY_S = 24 * 3600                   # one alert per fault per day
KEEP_HIST = 60
PORT = int(os.environ.get("PORT") or 8766)
# the ages of the weekly clean (days)
AGES = {"dated_log": 30, "gz": 30, "audit_gz": 365, "code_zip": 14, "backup_zip": 14, "reports_tmp": 7, "run_cache": 14,
        "nt_log": 14, "temp": 2}
KEEP_NEWEST = {"code_zip": 2, "backup_zip": 3}
GIT_LOCKS = ("index.lock", "HEAD.lock", "config.lock", "packed-refs.lock", "shallow.lock", "ORIG_HEAD.lock", "FETCH_HEAD.lock")
SCRATCH_GIT = ("data/live_pub.git", "data/kalshi_pub.git", "data/heartbeat_pub.git", "data/datapipe_pub.git")
# never touched by any remedy (forward slashes, fnmatch on the path relative to the bot folder)
NEVER = ("data/*", "live_model*.json", "second_model.json", "notify_settings.json", ".env*", "*.env", "logs/connect-*",
         "logs/self_heal/keep-*", "*notes*", "*NOTES*", "STATE.md", "update_source.json")
DATED = re.compile(r"(20\d\d[-_]?[01]\d[-_]?[0-3]\d)")
TEMP_TEST = re.compile(r"^(le_|lesh_|pcst_|selftest_|board_test_|nqbot_dryrun_|playwright_chromiumdev_profile-|playwright-artifacts-|"
                       r"e2e_|privacy-|lite_test|jhome|fleet_dry_)")
LOG_DIR_REL = os.path.join("logs", "self_heal")
SAY_OFF = (lambda *_a, **_k: None)


# ------------------------------------------------------------------------------------------------ small helpers
def _rel(root: str, p: str) -> str:
    try:
        return os.path.relpath(p, root).replace("\\", "/")
    except ValueError:                       # another drive (Windows)
        return p.replace("\\", "/")


def never(rel: str) -> bool:
    r = rel.replace("\\", "/")
    while r.startswith("./"):
        r = r[2:]
    return r.startswith("../") or r == ".." or os.path.isabs(r) or any(fnmatch.fnmatchcase(r, g) for g in NEVER)


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _write_json(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, separators=(",", ":"), default=str)
        try:
            from .fsutil import replace as _rep          # retried on a Windows / OneDrive lock
            _rep(tmp, path)
        except Exception:
            os.replace(tmp, path)
    except Exception:
        pass


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(float(t), ET)


def in_trading(now) -> bool:
    """Weekday 01:50-16:00 ET (engine/autoupdate blackout: LIT trades 02:00-15:55): no pip there."""
    e = _et(now)
    m = e.hour * 60 + e.minute
    return e.weekday() < 5 and 110 <= m < 960


def gb(n) -> float:
    return round((n or 0) / GB, 2)


def _age(p, now) -> float:
    try:
        return now - os.path.getmtime(p)
    except OSError:
        return -1.0


def _size(p) -> int:
    try:
        if os.path.isfile(p) or os.path.islink(p):
            return os.lstat(p).st_size
    except OSError:
        return 0
    t = 0
    for d, _ds, fs in os.walk(p):
        for f in fs:
            try:
                t += os.lstat(os.path.join(d, f)).st_size
            except OSError:
                pass
    return t


def du(path: str, budget_s: float = 4.0, skip=()) -> tuple:
    """(bytes, complete) of a folder, a walk capped at budget_s (a capped walk is a lower bound)."""
    t0, n, done = time.time(), 0, True
    if not os.path.isdir(path):
        return (_size(path) if os.path.exists(path) else 0), True
    for d, ds, fs in os.walk(path):
        if skip:
            ds[:] = [x for x in ds if x not in skip]
        for f in fs:
            try:
                n += os.lstat(os.path.join(d, f)).st_size
            except OSError:
                pass
        if time.time() - t0 > budget_s:
            done = False
            break
    return n, done


# ------------------------------------------------------------------------------------------------ the facts (fakeable)
def _git_exe() -> str:
    try:
        from . import generated_files
        return generated_files.git_exe()
    except Exception:
        return "git"


def make_git(root: str):
    def git(*args, timeout=60, env=None):
        try:
            r = subprocess.run([_git_exe(), "-C", root, *args], capture_output=True, text=True, timeout=timeout,
                               env={**os.environ, **env} if env else None,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
            return r.returncode, (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            return 127, f"{e.__class__.__name__}: {e}"
    return git


def proc_names() -> list:
    """[(pid, lower name)] of the running processes; [] when unknown (psutil, else tasklist / ps)."""
    try:
        import psutil
        out = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                out.append((int(p.info["pid"]), str(p.info.get("name") or "").lower()))
            except Exception:
                continue
        return out
    except Exception:
        pass
    try:
        if os.name == "nt":
            r = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=30,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            out = []
            for ln in (r.stdout or "").splitlines():
                parts = [x.strip('"') for x in ln.split('","')]
                if len(parts) >= 2 and parts[1].strip('"').isdigit():
                    out.append((int(parts[1].strip('"')), parts[0].strip('"').lower()))
            return out
        r = subprocess.run(["ps", "-eo", "pid=,comm="], capture_output=True, text=True, timeout=30)
        out = []
        for ln in (r.stdout or "").splitlines():
            a = ln.strip().split(None, 1)
            if len(a) == 2 and a[0].isdigit():
                out.append((int(a[0]), os.path.basename(a[1]).lower()))
        return out
    except Exception:
        return []


def ping_server(port: int = PORT, timeout: float = 4.0, tries: int = 2) -> bool:
    """The bot server answers /api/health/ping (two tries 3 s apart: a busy moment is not "down")."""
    for i in range(tries):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/health/ping", headers={"User-Agent": "olympus-self-heal/1"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        if i + 1 < tries:
            time.sleep(3)
    return False


def nt_folder(env=None) -> str | None:
    env = os.environ if env is None else env
    if env.get("NINJATRADER_FOLDER"):
        return env["NINJATRADER_FOLDER"]
    try:
        from .ninjatrader import default_folder
        f = default_folder()
        return f if f and os.path.isdir(f) else None
    except Exception:
        return None


class Ctx:
    """Everything a remedy reads or runs, injectable for the tests (temp folders, fake git / processes / pip / clock)."""

    def __init__(self, root: str = ROOT, now=None, apply: bool = False, env=None, git=None, procs=None, ping=None, run=None,
                 nt=..., temp=None, pkgs=None, sync_clock=None, flat=None, is_windows=None, say=SAY_OFF):
        self.root = root
        self.now = time.time() if now is None else float(now)
        self.apply = apply
        self.env = os.environ if env is None else env
        self.git = git or make_git(root)
        self._procs = procs
        self.ping = ping or (lambda: ping_server())
        self.run = run or subprocess.run
        self.nt = nt_folder(self.env) if nt is ... else nt
        self.temp = temp if temp is not None else (self.env.get("TEMP") or self.env.get("TMP") or None)
        self.pkgs = pkgs                     # fake installed packages {name_lower: version}; None = importlib.metadata
        self.sync_clock = sync_clock
        self.flat = flat                     # fn() -> None (flat) or why not
        self.is_windows = (os.name == "nt") if is_windows is None else is_windows
        self.say = say
        self.stamp = _et(self.now).strftime("%Y%m%d-%H%M")
        self.home = os.path.join(root, LOG_DIR_REL)
        self.moved: list = []                # fix_update: [(rel, copy path or None)] it moved / removed (restore_untracked)

    def procs(self) -> list:
        if self._procs is None:
            self._procs = proc_names()
        return self._procs() if callable(self._procs) else self._procs

    def keep_dir(self) -> str:
        return os.path.join(self.home, f"keep-{self.stamp}")


def item(fault, key, status, text, step="", paths=None, freed=0) -> dict:
    """status: fixed | would | need | info. need = could NOT fix (the only kind that alerts)."""
    return {"fault": fault, "key": key, "status": status, "text": text, "step": step, "paths": list(paths or [])[:8], "freed": int(freed or 0)}


def _act(ctx, label, fn) -> bool:
    """Run one change when ctx.apply; the log line either way. True = done (or would be, on a dry run)."""
    if not ctx.apply:
        ctx.say(f"  [dry] would {label}")
        return True
    try:
        fn()
        ctx.say(f"  [fix] {label}")
        return True
    except Exception as e:
        ctx.say(f"  [..]  could not {label}: {e.__class__.__name__}")
        return False


def _copy_keep(ctx, src: str, rel: str) -> str:
    dst = os.path.join(ctx.keep_dir(), rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return dst


# ------------------------------------------------------------------------------------------------ 1. git locks
def git_dirs(root: str) -> list:
    """This folder's git dir (.git, or the gitdir a .git file names) + the bot's scratch git dirs that exist."""
    out = []
    g = os.path.join(root, ".git")
    if os.path.isfile(g):
        try:
            with open(g, encoding="utf-8") as fh:
                ln = fh.read().strip()
            if ln.startswith("gitdir:"):
                p = ln.split(":", 1)[1].strip()
                g = p if os.path.isabs(p) else os.path.normpath(os.path.join(root, p))
        except OSError:
            g = None
    if g and os.path.isdir(g):
        out.append(g)
    for s in SCRATCH_GIT:
        p = os.path.join(root, *s.split("/"))
        if os.path.isdir(p):
            out.append(p)
    return out


def git_running(ctx) -> bool:
    return any(n.split(".")[0] in ("git", "git-remote-https", "git-remote-http", "git-lfs") for _pid, n in ctx.procs())


def find_git_locks(root: str) -> list:
    out = []
    for g in git_dirs(root):
        for n in GIT_LOCKS:
            p = os.path.join(g, n)
            if os.path.isfile(p):
                out.append(p)
        refs = os.path.join(g, "refs")
        for d, _ds, fs in os.walk(refs):
            for f in fs:
                if f.endswith(".lock"):
                    out.append(os.path.join(d, f))
    return out


def fix_git_locks(ctx) -> list:
    locks = [p for p in find_git_locks(ctx.root) if _age(p, ctx.now) >= LOCK_AGE_S]
    if not locks:
        return []
    names = [_rel(ctx.root, p) for p in locks]
    if git_running(ctx):
        return [item("git_lock", "git_lock", "info", f"{len(locks)} old git lock(s) ({', '.join(names[:3])}) but git is running now: "
                     "left for the next run", paths=names)]
    ok = all(_act(ctx, f"delete the stale git lock {n} ({_age(p, ctx.now) / 60:.0f} min old, no git running)", lambda p=p: os.remove(p))
             for p, n in zip(locks, names))
    if ok:
        return [item("git_lock", "git_lock", "fixed" if ctx.apply else "would",
                     f"{'removed' if ctx.apply else 'would remove'} {len(locks)} stale git lock(s) left by a killed git: {', '.join(names[:3])}",
                     paths=names)]
    return [item("git_lock", "git_lock", "need", f"a stale git lock could not be deleted: {', '.join(names[:3])} (another program holds it?)",
                 "restart the PC once, then double-click UPDATE.bat", names)]


# ------------------------------------------------------------------------------------------------ 2. the auto-update's blockers
def _sha(out: str):
    m = re.search(r"\b[0-9a-f]{40}\b", out or "")
    return m.group(0) if m else None


def update_ref(ctx) -> str | None:
    """The ref the auto-update fast-forwards to (update_source.json: <remote>/<branch>, else origin/main), when it exists here."""
    try:
        from . import autoupdate
        src = autoupdate.source(ctx.root, env=ctx.env)
        ref = f"{src['remote']}/{src['branch']}"
    except Exception:
        ref = "origin/main"
    c, out = ctx.git("rev-parse", "--verify", "-q", ref)
    return ref if c == 0 and _sha(out) else None


def _last_update(ctx) -> dict:
    return (_read_json(os.path.join(ctx.root, "data", "autoupdate.json"), {}) or {}).get("last") or {}


SNAP_REF = "refs/olympus/self-heal"           # every file the update remedy moves or resets, as git objects (never lost)
_WHO = {"GIT_AUTHOR_NAME": "olympus-self-heal", "GIT_AUTHOR_EMAIL": "self-heal@localhost",
        "GIT_COMMITTER_NAME": "olympus-self-heal", "GIT_COMMITTER_EMAIL": "self-heal@localhost"}


def snapshot(ctx, rels) -> str | None:
    """A commit of these files exactly as they are on disk (a temp index: nothing else in the repo changes), chained at
    SNAP_REF; the same kind of snapshot engine/autoupdate makes before a connect. Put one back:
    git checkout refs/olympus/self-heal -- <file>. None = failed (then the remedy does not run)."""
    rels = [r for r in rels if os.path.isfile(os.path.join(ctx.root, *r.split("/")))]
    if not rels:
        return None
    os.makedirs(ctx.home, exist_ok=True)
    idx = os.path.join(ctx.home, "snap.idx")
    try:
        os.remove(idx)
    except OSError:
        pass
    env = {"GIT_INDEX_FILE": idx}
    try:
        c, prev = ctx.git("rev-parse", "--verify", "-q", SNAP_REF)
        prev = _sha(prev) if c == 0 else None
        if prev:
            ctx.git("read-tree", prev, env=env)          # keep the earlier snapshots' files too
        c, out = ctx.git("update-index", "--add", "--", *rels, env=env)
        if c != 0:
            return None
        c, out = ctx.git("write-tree", env=env)
        tree = _sha(out) if c == 0 else None
        if not tree:
            return None
        c, out = ctx.git("commit-tree", tree, *(["-p", prev] if prev else []), "-m", f"OLYMPUS self-heal {ctx.stamp}: {', '.join(rels[:6])}",
                         env=_WHO)
        commit = _sha(out) if c == 0 else None
        if not commit or ctx.git("update-ref", SNAP_REF, commit)[0] != 0:
            return None
        return commit
    finally:
        try:
            os.remove(idx)
        except OSError:
            pass


def fix_update(ctx, untracked: str = "apply", generated: bool = True, new: str | None = None) -> list:
    """The two blockers a self-heal can clear without touching the owner's work: an untracked file the update brings, and a bot-made
    file the last update named as in the way. A hand edit of any other tracked file is only reported (need).
    untracked: "apply" (move / remove them; engine/autoupdate.fast_forward calls it so right before its `git merge --ff-only`, and
    puts them back with restore_untracked when the merge still fails) | "report" (the hourly run, redteam 2026-11-20: only names
    them; removing a file the running bot may import an hour or a trading day before the update that brings it back could break
    the bot) | "off". generated: part b (the last update's named bot-made files). new: the commit the update moves to (else the
    update source's ref). Moved / removed files are listed in ctx.moved [(rel, copy path or None)]."""
    if new is None:
        ref = update_ref(ctx)
        if not ref:
            return []
        c2, new = ctx.git("rev-parse", ref)
        new = _sha(new) if c2 == 0 else None
    c, head = ctx.git("rev-parse", "HEAD")
    head = _sha(head) if c == 0 else None
    if not head or not new or head == new:
        return []
    if ctx.git("merge-base", "--is-ancestor", head, new)[0] != 0:
        return []                                         # not a fast-forward: the auto-update says why itself
    out = []
    # a. untracked files the update adds (git refuses: "untracked working tree files would be overwritten by merge")
    c, added = ctx.git("diff", "--name-only", "--diff-filter=A", head, new)
    added = [p.strip() for p in added.splitlines() if p.strip()] if c == 0 else []
    in_way = []
    for i in range(0, len(added), 200) if untracked != "off" else ():
        c, un = ctx.git("ls-files", "--others", "--exclude-standard", "--", *added[i:i + 200])
        in_way += [p.strip() for p in un.splitlines() if p.strip()] if c == 0 else []
    fixed, need, later = [], [], []
    moved = ctx.moved
    for rel in in_way:
        p = os.path.join(ctx.root, *rel.split("/"))
        if not os.path.isfile(p):
            continue
        if never(rel):
            need.append(rel)
            continue
        if untracked != "apply":
            later.append(rel)                             # the next update clears it right before its merge
            continue
        c, mine = ctx.git("hash-object", "--", rel)
        c2, theirs = ctx.git("rev-parse", f"{new}:{rel}")
        same = c == 0 and c2 == 0 and _sha(mine) and _sha(mine) == _sha(theirs)
        if same:
            def rm(p=p, rel=rel):
                os.remove(p)
                moved.append((rel, None))
            done = _act(ctx, f"remove {rel}: the update brings the very same file (git would refuse to overwrite it)", rm)
        else:
            def move(p=p, rel=rel):
                if not snapshot(ctx, [rel]):
                    raise RuntimeError("snapshot failed: the file stays")
                cp = _copy_keep(ctx, p, rel)
                os.remove(p)
                moved.append((rel, cp))
            done = _act(ctx, f"move {rel} to {_rel(ctx.root, ctx.keep_dir())}/ (the update brings its own copy; yours is kept there)", move)
        (fixed if done else need).append(rel)
    if fixed:
        out.append(item("update", "update_untracked", "fixed" if ctx.apply else "would",
                        f"{'cleared' if ctx.apply else 'would clear'} {len(fixed)} untracked file(s) in the update's way: {', '.join(fixed[:3])}"
                        + (f" (copies in {_rel(ctx.root, ctx.keep_dir())})" if ctx.apply else ""), paths=fixed))
    if later:
        out.append(item("update", "update_untracked", "info",
                        f"{len(later)} untracked file(s) in the update's way ({', '.join(later[:3])}): the next auto-update clears them "
                        "right before its merge (copies kept)", paths=later))
    # b. a bot-made tracked file the LAST update named as in the way (a write between the update's reset and its merge)
    from . import generated_files
    reason = str(_last_update(ctx).get("reason") or "")
    gen, other = [], []                                   # (the autoupdate's own call: it handles its dirty files itself)
    if generated:
        c, st = ctx.git("status", "--porcelain", "--untracked-files=no")
        gen, other = generated_files.split_dirty(st) if c == 0 else ([], [])
    named = [p for p in gen if p in reason] if generated and ("overwritten" in reason or "refused" in reason or "local changes" in reason) else []
    need += [p for p in named if re.search(r"journal|trade", p, re.I)]      # a trade journal is never reset by the self-heal
    named = [p for p in named if not re.search(r"journal|trade", p, re.I)]
    if named:
        def reset():
            if not snapshot(ctx, named):
                raise RuntimeError("snapshot failed: the files stay")
            for rel in named:
                src = os.path.join(ctx.root, *rel.split("/"))
                if os.path.isfile(src):
                    _copy_keep(ctx, src, rel)
            c3, o3 = generated_files.discard(ctx.git, named)
            if c3 != 0:
                raise RuntimeError(o3[-120:])
        if _act(ctx, f"put {len(named)} bot-made file(s) back to HEAD (copies kept): {', '.join(named[:3])}", reset):
            out.append(item("update", "update_generated", "fixed" if ctx.apply else "would",
                            f"{'reset' if ctx.apply else 'would reset'} {len(named)} bot-made file(s) the last update tripped on: {', '.join(named[:3])}",
                            paths=named))
        else:
            need += named
    # c. a hand edit of a tracked file blocks every update (engine/autoupdate.fast_forward): never touched, named once a day
    try:
        from .autoupdate import TRACKED_LOCAL
    except Exception:
        TRACKED_LOCAL = "second_model.json"
    for rel in other:
        if rel == TRACKED_LOCAL:
            continue                                      # the auto-update moves ATLAS's block out of it itself
        c, mine = ctx.git("hash-object", "--", rel)
        c2, theirs = ctx.git("rev-parse", f"{new}:{rel}")
        if c == 0 and c2 == 0 and _sha(mine) and _sha(mine) == _sha(theirs):
            continue                                      # already the new version (checked out by hand): the update takes it
        need.append(rel)
    if need:
        out.append(item("update", "update_blocked", "need",
                        f"the auto-update is held back by a local change it may not touch: {', '.join(need[:3])}",
                        "send Claude this line: 'update blocked by " + ", ".join(need[:2]) + "' (keep or drop the change)", need))
    return out


def restore_untracked(ctx, new: str | None = None) -> list:
    """Put back the untracked files fix_update moved / removed (ctx.moved), when the merge they were moved for still failed:
    the copy kept in keep-*/, else (a removed identical file) the update's own blob. -> the paths put back. Never raises."""
    back = []
    for rel, cp in list(getattr(ctx, "moved", None) or []):
        p = os.path.join(ctx.root, *rel.split("/"))
        try:
            if os.path.exists(p):
                continue
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if cp and os.path.isfile(cp):
                shutil.copy2(cp, p)
            elif new:
                c, _o = ctx.git("cat-file", "-e", f"{new}:{rel}")
                if c != 0:
                    continue
                r = subprocess.run([_git_exe(), "-C", ctx.root, "show", f"{new}:{rel}"], capture_output=True, timeout=60,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
                if r.returncode != 0:
                    continue
                with open(p, "wb") as fh:
                    fh.write(r.stdout)
            else:
                continue
            back.append(rel)
        except Exception:  # noqa: BLE001
            continue
    ctx.moved = []
    return back


def before_merge(root: str, git, new: str, log=None, now=None):
    """engine/autoupdate.fast_forward's hook, right before `git merge --ff-only <new>` (night-selfheal's proposal, landed by the
    redteam 2026-11-20): the untracked files the update brings are cleared (same bytes: removed; other bytes: snapshot + copy in
    logs/self_heal/keep-*/, then removed). The update already checked flat / the hours. -> (ctx, items); the caller passes ctx to
    restore_untracked when the merge still fails. Never raises: (None, []) on any problem (the merge then says why itself)."""
    try:
        ctx = Ctx(root=root, now=now, apply=True, git=lambda *a, timeout=60, env=None: git(*a, timeout=timeout, env=env),
                  say=log or SAY_OFF, flat=lambda: None, procs=[], ping=lambda: True, nt=None, temp="", pkgs={})
        items = fix_update(ctx, untracked="apply", generated=False, new=new)
        return ctx, items
    except Exception:  # noqa: BLE001
        return None, []


GATED = ("update", "pid", "clock")              # never while a trade may be open (redteam 2026-11-20); update also never 01:50-16:00


def trade_open(ctx) -> str | None:
    """Why a trade may be open now (None = flat): LIT's own files (engine/autoupdate.files_flat_reason) + every NinjaTrader state
    file of the bot (data/ninjatrader_state*.json: LIT, ATLAS, account C, the extra accounts, the Rapid lanes). Unreadable = not flat."""
    if ctx.flat is not None:
        return ctx.flat()
    try:
        why = _flat_reason(ctx.root, ctx.now)
    except Exception as e:  # noqa: BLE001
        return f"cannot tell if flat ({e.__class__.__name__})"
    if why:
        return why
    import glob
    for p in sorted(glob.glob(os.path.join(ctx.root, "data", "ninjatrader_state*.json"))):
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
        except FileNotFoundError:
            continue
        except Exception:  # noqa: BLE001
            return f"{os.path.basename(p)} unreadable"
        for lg in (d.get("legs") if isinstance(d, dict) else None) or []:
            if isinstance(lg, dict) and lg.get("status") in OPEN_LEGS:
                return f"an open NinjaTrader bracket ({os.path.basename(p)})"
    return None


OPEN_LEGS = ("entry_sent", "pending", "cancel_pending", "protected", "unprotected", "closing")   # engine/ninjatrader.OPEN_STATUSES


# ------------------------------------------------------------------------------------------------ 3. NinjaTrader order files
def fix_oif(ctx) -> list:
    if not ctx.nt or not os.path.isdir(ctx.nt):
        return []
    stuck = []
    for sub in ("incoming", "le_outbox"):
        d = os.path.join(ctx.nt, sub)
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for n in names:
            p = os.path.join(d, n)
            if n.startswith("oif_le_") and os.path.isfile(p) and _age(p, ctx.now) >= OIF_AGE_S:
                stuck.append((sub, n, p))
    if not stuck:
        return []
    keep = os.path.join(ctx.home, "oif")
    done, left = [], []
    for sub, n, p in stuck:
        def withdraw(p=p, n=n, sub=sub):
            os.makedirs(keep, exist_ok=True)
            shutil.copy2(p, os.path.join(keep, f"{ctx.stamp}-{sub}-{n}"))
            os.remove(p)
        (done if _act(ctx, f"withdraw the bot order file {sub}\\{n} ({_age(p, ctx.now) / 60:.0f} min unprocessed: it must never run late)",
                      withdraw) else left).append(f"{sub}/{n}")
    out = []
    if done:
        out.append(item("oif", "oif", "fixed" if ctx.apply else "would",
                        f"{'withdrew' if ctx.apply else 'would withdraw'} {len(done)} bot order file(s) NinjaTrader never processed "
                        "(it was off): they can never run late", paths=done))
    if left:
        out.append(item("oif", "oif_stuck", "need", f"{len(left)} old bot order file(s) could not be removed from NinjaTrader's folder",
                        "close NinjaTrader, delete the oif_le_ files in Documents\\NinjaTrader 8\\incoming, start it again", left))
    return out


# ------------------------------------------------------------------------------------------------ 4. stale pid / lock files
SUP_NAMES = ("powershell", "pwsh")


def fix_pids(ctx) -> list:
    p = os.path.join(ctx.root, "logs", "supervisor.pid")
    if not os.path.isfile(p):
        return []
    try:
        with open(p, encoding="ascii", errors="replace") as fh:
            pid = int((fh.read().strip().splitlines() or ["0"])[0] or 0)
    except (OSError, ValueError):
        pid = 0
    procs = ctx.procs()
    if not procs:
        return []                                         # cannot see the processes: never guess
    name = next((n for q, n in procs if q == pid), None)
    if name is not None and name.split(".")[0] in SUP_NAMES:
        return []                                         # the supervisor runs
    why = "is not running" if name is None else f"is now another program ({name})"
    if _act(ctx, f"delete logs/supervisor.pid: pid {pid} {why} (a crash or restart left it; STOP_BOT would wait for that pid)",
            lambda: os.remove(p)):
        return [item("pid", "pid", "fixed" if ctx.apply else "would", f"{'removed' if ctx.apply else 'would remove'} a stale "
                     f"supervisor.pid (pid {pid} {why})", paths=["logs/supervisor.pid"])]
    return [item("pid", "pid", "need", "a stale logs/supervisor.pid could not be deleted", "restart the PC once", ["logs/supervisor.pid"])]


# ------------------------------------------------------------------------------------------------ 5. the bot server
def fix_server(ctx) -> list:
    if not os.path.isfile(os.path.join(ctx.root, "data", "autostart.json")):
        return []                                         # stopped on purpose (/api/live/stop deletes it): nothing to say
    if ctx.ping():
        return []
    return [item("server", "server", "need", "the bot server does not answer while it should run (data/autostart.json is there); "
                 "the supervisor restarts a crashed server by itself, this one stayed down",
                 "double-click BOTS_BACK.bat (a real account is never armed by it: you type the live phrase yourself)")]


# ------------------------------------------------------------------------------------------------ 6. Python packages
_REQ = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*([<>=!~].*)?$")


def requirements(root: str) -> list:
    """[(name, spec line)] of requirements.txt (comments, options and markers left out)."""
    out = []
    try:
        with open(os.path.join(root, "requirements.txt"), encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.split("#", 1)[0].split(";", 1)[0].strip()
                if not ln or ln.startswith("-"):
                    continue
                m = _REQ.match(ln)
                if m:
                    out.append((m.group(1), ln.replace(" ", "")))
    except OSError:
        pass
    return out


def missing_packages(ctx) -> list:
    out = []
    for name, spec in requirements(ctx.root):
        if ctx.pkgs is not None:
            if name.lower().replace("_", "-") not in ctx.pkgs:
                out.append(spec)
            continue
        try:
            from importlib import metadata
            metadata.version(name)
        except Exception:
            out.append(spec)
    return out


def fix_pip(ctx) -> list:
    miss = missing_packages(ctx)
    if not miss:
        return []
    if in_trading(ctx.now):
        return [item("pip", "pip", "info", f"{len(miss)} package(s) missing ({', '.join(miss[:3])}): installed after 16:00 ET", paths=miss)]
    why = None
    try:
        why = trade_open(ctx)
    except Exception:
        why = None
    if why:
        return [item("pip", "pip", "info", f"{len(miss)} package(s) missing ({', '.join(miss[:3])}): waiting until no trade is open ({why})", paths=miss)]
    res = {}

    def install():
        r = ctx.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", *miss], capture_output=True, text=True,
                    timeout=400, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        res["code"], res["out"] = r.returncode, ((r.stdout or "") + (r.stderr or ""))[-200:]
        if r.returncode != 0:
            raise RuntimeError(res["out"])
    if _act(ctx, f"pip install the missing package(s): {' '.join(miss)}", install):
        return [item("pip", "pip", "fixed" if ctx.apply else "would", f"{'installed' if ctx.apply else 'would install'} {len(miss)} missing "
                     f"package(s): {', '.join(miss[:4])}", paths=miss)]
    return [item("pip", "pip", "need", f"pip could not install {', '.join(miss[:3])} ({str(res.get('out') or '')[-80:].strip()})",
                 "python -m pip install -r requirements.txt", miss)]


def _flat_reason(root, now):
    from .autoupdate import files_flat_reason
    return files_flat_reason(root, now)


# ------------------------------------------------------------------------------------------------ 7. the clock
def clock_drift(root: str, now) -> float | None:
    blk = _read_json(os.path.join(root, "logs", "pc_health.json"), {}) or {}
    try:
        if now - float(blk.get("t") or 0) > HEALTH_FRESH_S:
            return None
    except (TypeError, ValueError):
        return None
    for ln in blk.get("lines") or []:
        if isinstance(ln, dict) and ln.get("key") == "clock" and ln.get("value") is not None:
            try:
                return float(ln["value"])
            except (TypeError, ValueError):
                return None
    return None


def fix_clock(ctx) -> list:
    d = clock_drift(ctx.root, ctx.now)
    if d is None or abs(d) <= CLOCK_MAX_S:
        return []
    words = f"the PC clock is {abs(d):.1f} s {'behind' if d > 0 else 'ahead of'} internet time"
    if not ctx.is_windows and ctx.sync_clock is None:
        return [item("clock", "clock", "info", words + " (clock sync is Windows only)")]
    res = {}

    def sync():
        fn = ctx.sync_clock
        if fn is None:
            from .go import sync_clock as fn
        r = fn()
        res.update(r or {})
        if not (r or {}).get("ok"):
            raise RuntimeError(str((r or {}).get("error") or "refused")[:120])
    if _act(ctx, f"sync the clock (w32tm /resync): {words}", sync):
        return [item("clock", "clock", "fixed" if ctx.apply else "would", f"{'synced' if ctx.apply else 'would sync'} the clock ({words})")]
    return [item("clock", "clock", "need", words + f"; Windows did not sync it ({str(res.get('error') or '')[:90]})",
                 "Windows Settings > Time & language > Date & time > Sync now")]


# ------------------------------------------------------------------------------------------------ 8. the weekly clean + sizes
def _dated_old(name: str, now, days: int) -> bool:
    m = DATED.search(name)
    if not m:
        return False
    s = re.sub(r"[-_]", "", m.group(1))
    try:
        d = dt.datetime.strptime(s, "%Y%m%d").replace(tzinfo=ET)
    except ValueError:
        return False
    return (now - d.timestamp()) > days * 86400


def _pyc_orphan(path: str) -> bool:
    """A __pycache__ file of a .py that no longer exists, or of another Python version (cpython-312 under 3.13)."""
    name = os.path.basename(path)
    parts = name.split(".")
    if len(parts) < 3 or not name.endswith((".pyc", ".pyo")):
        return False
    vtag = parts[-3] if parts[-2].startswith("opt-") and len(parts) >= 4 else parts[-2]
    if vtag != sys.implementation.cache_tag:
        return True
    src = os.path.join(os.path.dirname(os.path.dirname(path)), parts[0] + ".py")
    return not os.path.exists(src)


def clean_plan(ctx) -> list:
    """[(kind, path, bytes)]: what the weekly clean removes. Only the allow-listed kinds below; NEVER() paths are skipped."""
    root, now, out = ctx.root, ctx.now, []

    def add(kind, p):
        rel = _rel(root, p)
        if not rel.startswith("..") and never(rel):
            return
        out.append((kind, p, _size(p)))
    logs = os.path.join(root, "logs")
    if os.path.isdir(logs):
        for d, ds, fs in os.walk(logs):
            rel_d = _rel(root, d)
            ds[:] = [x for x in ds if not never(f"{rel_d}/{x}")]
            for f in fs:
                p = os.path.join(d, f)
                if f.endswith(".gz"):
                    days = AGES["audit_gz"] if f.startswith("ninjatrader_oif") else AGES["gz"]
                    if _age(p, now) > days * 86400:
                        add("old log", p)
                elif f.endswith((".log", ".txt", ".jsonl", ".out", ".err")) and _dated_old(f, now, AGES["dated_log"]) \
                        and _age(p, now) > AGES["dated_log"] * 86400:
                    add("old log", p)
    for kind, pattern, folder in (("code_zip", r"(?i)^OLYMPUS_BACKUP_.*\.zip$", root),
                                  ("backup_zip", r"^le-(backup|pre-restore)-.*\.zip$", os.path.join(root, "backups"))):
        try:
            zs = sorted((os.path.join(folder, n) for n in os.listdir(folder) if re.match(pattern, n)), key=lambda p: -os.path.getmtime(p))
        except OSError:
            zs = []
        for p in zs[KEEP_NEWEST[kind]:]:
            if _age(p, now) > AGES[kind] * 86400:
                add("old zip", p)
                sha = re.sub(r"\.zip$", ".sha256.txt", p)
                if sha != p and os.path.isfile(sha):
                    add("old zip", sha)
    for kind, rel, days in (("reports/tmp", ("reports", "tmp"), AGES["reports_tmp"]), ("run cache", ("research", "runs", "_cache"), AGES["run_cache"])):
        d0 = os.path.join(root, *rel)
        if os.path.isdir(d0):
            for d, _ds, fs in os.walk(d0):
                for f in fs:
                    p = os.path.join(d, f)
                    if _age(p, now) > days * 86400:
                        add(kind, p)
    skip = {".git", "data", "logs", "backups", "node_modules", ".venv", "venv", "env", "site-packages", ".claude"}
    for d, ds, fs in os.walk(root):
        ds[:] = [x for x in ds if x not in skip and not x.endswith(".git")]
        if os.path.basename(d) == "__pycache__":
            for f in fs:
                p = os.path.join(d, f)
                if _pyc_orphan(p) and _age(p, now) > 3600:
                    add("__pycache__", p)
    if ctx.nt and os.path.isdir(ctx.nt):
        for sub in ("log", "trace"):
            d = os.path.join(ctx.nt, sub)
            try:
                names = os.listdir(d)
            except OSError:
                continue
            for n in names:
                p = os.path.join(d, n)
                if n.lower().endswith((".txt", ".log")) and os.path.isfile(p) and _age(p, now) > AGES["nt_log"] * 86400:
                    out.append(("NinjaTrader log", p, _size(p)))
    if ctx.temp and os.path.isdir(ctx.temp):
        try:
            names = os.listdir(ctx.temp)
        except OSError:
            names = []
        for n in names:
            p = os.path.join(ctx.temp, n)
            if TEMP_TEST.match(n) and not os.path.islink(p) and _newest(p) < now - AGES["temp"] * 86400:
                out.append(("test leftovers", p, _size(p)))
    return out


def _newest(p) -> float:
    try:
        t = os.lstat(p).st_mtime
    except OSError:
        return time.time()
    if os.path.isdir(p):
        for d, ds, fs in os.walk(p):
            for n in ds + fs:
                try:
                    t = max(t, os.lstat(os.path.join(d, n)).st_mtime)
                except OSError:
                    pass
    return t


def clean(ctx) -> dict:
    """The weekly clean: {"n", "bytes", "kinds": {kind: bytes}, "errors"}; a dry run removes nothing."""
    plan = clean_plan(ctx)
    res = {"n": 0, "bytes": 0, "kinds": {}, "errors": 0, "apply": ctx.apply}
    for kind, p, n in plan:
        if ctx.apply:
            try:
                if os.path.isdir(p) and not os.path.islink(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
            except OSError:
                res["errors"] += 1
                continue
        res["n"] += 1
        res["bytes"] += n
        res["kinds"][kind] = res["kinds"].get(kind, 0) + n
    for d in (os.path.join(ctx.root, "reports", "tmp"), os.path.join(ctx.root, "research", "runs", "_cache")):
        if ctx.apply and os.path.isdir(d):              # empty sub-folders left behind
            for dd, ds, fs in sorted(os.walk(d), key=lambda x: -len(x[0])):
                if dd != d and not ds and not fs:
                    try:
                        os.rmdir(dd)
                    except OSError:
                        pass
    return res


SIZE_KEYS = (("logs", ("logs",)), ("data", ("data",)), ("bars", ("data", "nt_bars")), ("research", ("research",)),
             ("runs", ("research", "runs")), ("git", (".git",)))


def sizes(ctx, budget_s: float = 4.0) -> dict:
    """GB of what grows in the bot folder (each walk capped at budget_s; '+' = at least)."""
    out = {}
    for key, rel in SIZE_KEYS:
        n, ok = du(os.path.join(ctx.root, *rel), budget_s)
        out[key] = gb(n) if ok else f"{gb(n)}+"
    zips = 0
    for folder, rx in ((ctx.root, r"(?i)\.zip$"), (os.path.join(ctx.root, "backups"), r"(?i)\.zip$")):
        try:
            zips += sum(_size(os.path.join(folder, n)) for n in os.listdir(folder) if re.search(rx, n))
        except OSError:
            pass
    out["zips"] = gb(zips)
    pyc = 0
    skip = {".git", "data", "logs", "backups", "node_modules", ".venv", "venv"}
    t0 = time.time()
    for d, ds, fs in os.walk(ctx.root):
        ds[:] = [x for x in ds if x not in skip and not x.endswith(".git")]
        if os.path.basename(d) == "__pycache__":
            pyc += sum(_size(os.path.join(d, f)) for f in fs)
        if time.time() - t0 > budget_s:
            break
    out["pycache"] = gb(pyc)
    tot, ok = du(ctx.root, budget_s * 3)
    out["bot"] = gb(tot) if ok else f"{gb(tot)}+"
    if ctx.nt and os.path.isdir(ctx.nt):
        n, ok = du(ctx.nt, budget_s)                        # NinjaTrader's own folder, its db (history cache) included: measured, never cleaned
        out["nt"] = gb(n) if ok else f"{gb(n)}+"
    try:
        out["free"] = round(shutil.disk_usage(ctx.root).free / GB, 1)
    except OSError:
        pass
    return out


def free_gb(root) -> float | None:
    try:
        return shutil.disk_usage(root).free / GB
    except OSError:
        return None


def fix_disk(ctx, state: dict, force_clean=False, disk_free=None) -> tuple:
    """(items, clean result or None): the weekly clean when due (outside trading hours), at once when the disk is low."""
    free = free_gb(ctx.root) if disk_free is None else disk_free
    low = free is not None and free < DISK_LOW_GB
    last = float(state.get("clean_t") or 0)
    due = force_clean or (ctx.now - last >= CLEAN_EVERY_S and not in_trading(ctx.now)) or (low and ctx.now - last >= CLEAN_LOW_EVERY_S)
    if not due:
        if low and free < DISK_RED_GB:
            return [item("disk", "disk", "need", f"only {free:.1f} GB free on the bot's drive (the clean ran {((ctx.now - last) / 3600):.0f} h ago)",
                         "double-click CLEAN_STORAGE.bat (dry run first; it also clears Windows' own junk)")], None
        return [], None
    res = clean(ctx)
    res["sizes"] = sizes(ctx)
    after = free_gb(ctx.root) if disk_free is None else (disk_free + (res["bytes"] / GB if ctx.apply else 0))
    items = []
    if res["n"]:
        items.append(item("disk", "clean", "fixed" if ctx.apply else "would", f"weekly clean: {'freed' if ctx.apply else 'would free'} "
                          f"{res['bytes'] / GB:.2f} GB in {res['n']} old file(s) ("
                          + ", ".join(f"{k} {v / GB:.2f}" for k, v in sorted(res["kinds"].items(), key=lambda x: -x[1])[:3]) + ")",
                          freed=res["bytes"]))
    if after is not None and after < DISK_RED_GB:
        items.append(item("disk", "disk", "need", f"only {after:.1f} GB free on the bot's drive after the clean",
                          "double-click CLEAN_STORAGE.bat (dry run first; it also clears Windows' own junk)"))
    return items, res


# ------------------------------------------------------------------------------------------------ one run
REMEDIES = (("git_lock", fix_git_locks), ("update", fix_update), ("oif", fix_oif), ("pid", fix_pids), ("server", fix_server),
            ("pip", fix_pip), ("clock", fix_clock))


def run(ctx, state: dict | None = None, force_clean: bool = False, only=None, disk_free=None) -> dict:
    """Every remedy once (dry run unless ctx.apply). Never raises: a remedy that crashes is one 'info' item."""
    state = {} if state is None else state
    items = []
    busy = None
    for name, fn in REMEDIES:
        if only and name not in only:
            continue
        try:
            if name in GATED:
                if name == "update" and in_trading(ctx.now):
                    continue                              # the update itself waits for 16:00 ET: nothing to clear before it
                if busy is None:
                    busy = trade_open(ctx) or ""
                if busy:
                    items.append(item(name, name, "info", f"not now: {busy} (never touched while a trade may be open)"))
                    continue
            items += (fix_update(ctx, untracked="report") if name == "update" else fn(ctx)) or []
        except Exception as e:  # noqa: BLE001
            items.append(item(name, name, "info", f"check failed softly ({e.__class__.__name__}: {str(e)[:80]})"))
    cl = None
    if not only or "disk" in only:
        try:
            its, cl = fix_disk(ctx, state, force_clean=force_clean, disk_free=disk_free)
            items += its
        except Exception as e:  # noqa: BLE001
            items.append(item("disk", "disk", "info", f"check failed softly ({e.__class__.__name__}: {str(e)[:80]})"))
    return {"t": int(ctx.now), "apply": ctx.apply, "items": items, "clean": cl,
            "fixed": [i for i in items if i["status"] == "fixed"], "need": [i for i in items if i["status"] == "need"]}


def tiny(state: dict, now) -> dict:
    """The PC report's ext line "sh" (<= ~300 bytes, public: no folder, no name): ok, fixed this week, needs you, sizes."""
    hist = [h for h in state.get("hist") or [] if isinstance(h, dict) and now - float(h.get("t") or 0) <= 7 * 86400]
    fixed = sum(int(h.get("fixed") or 0) for h in hist)
    need = list(state.get("need") or [])[:4]
    sz = state.get("sizes") or {}
    big = sorted(((k, v) for k, v in sz.items() if k in ("logs", "data", "runs", "zips", "pycache", "research", "nt") and isinstance(v, (int, float))),
                 key=lambda x: -x[1])[:3]
    free = state.get("free")
    words = {"update_blocked": "the update is blocked", "server": "the bot server is down", "disk": "the disk is nearly full",
             "pip": "a package will not install", "clock": "the clock will not sync", "git_lock": "a git lock is stuck",
             "oif_stuck": "an old order file is stuck", "pid": "a pid file is stuck"}
    line = ("Self-heal: " + ("needs you: " + ", ".join(words.get(k, k) for k in need) if need else "all fine") + f" · fixed {fixed} this week"
            + (f" · {free:.0f} GB free" if isinstance(free, (int, float)) else "")
            + (f" · bot folder {sz.get('bot')} GB" if sz.get("bot") is not None else "")
            + (" (" + ", ".join(f"{k} {v:.2f}" for k, v in big) + ")" if big else "")
            + (f" · last clean freed {float(state.get('freed') or 0):.2f} GB" if state.get("clean_t") else ""))
    return {"t": int(state.get("t") or now), "ok": not need, "fixed": fixed, "need": need,
            "free": round(free) if isinstance(free, (int, float)) else None, "bot": sz.get("bot"), "big": [[k, v] for k, v in big],
            "freed": round(float(state.get("freed") or 0) / 1, 2) if state.get("clean_t") else None, "line": line[:240]}


def read_tiny(root: str = ROOT, now=None) -> dict | None:
    """The ext line from logs/self_heal/tiny.json; None when missing or older than 3 days (the PC report then sends none)."""
    now = time.time() if now is None else now
    d = _read_json(os.path.join(root, LOG_DIR_REL, "tiny.json"), None)
    try:
        return d if isinstance(d, dict) and now - float(d.get("t") or 0) <= 3 * 86400 else None
    except (TypeError, ValueError):
        return None


def _log(ctx, lines):
    try:
        os.makedirs(ctx.home, exist_ok=True)
        with open(os.path.join(ctx.home, f"heal-{_et(ctx.now):%Y%m}.log"), "a", encoding="utf-8") as fh:
            for ln in lines:
                fh.write(f"{_et(ctx.now):%Y-%m-%d %H:%M} ET  {ln}\n")
    except OSError:
        pass


def alert(ctx, it: dict, board=None, push=None) -> dict:
    """ONE board event + one IMPORTANT phone push for a fault it could not fix (the caller dedupes per day)."""
    text = f"Self-heal could not fix: {it['text']}" + (f". Next: {it['step']}" if it.get("step") else "")
    res = {"board": False, "push": False}
    try:
        if board is None:
            from . import board_events
            board = board_events.emit
        res["board"] = bool(board("self_heal", "pc", text[:290], {"fault": it["fault"], "key": it["key"]}))
    except Exception:
        pass
    if it["fault"] == "server":
        return res                                       # the 15-minute report already pushes "bot down": never twice
    m = {"key": f"heal:{it['key']}", "kind": "pc_health", "title": "PC self-heal: needs you", "body": text[:500], "priority": "high",
         "tags": "warning", "t": int(ctx.now)}
    try:
        if push is None:
            push = _push
        res["push"] = bool(push(m))
    except Exception:
        pass
    return res


def _push(m: dict) -> bool:
    """The phone app first (engine/push), else the private ntfy topic (tools/pc_report): the report's own way."""
    try:
        from tools import pc_report as PR
    except Exception:
        return False
    try:
        if PR._app_push(m):
            return True
    except Exception:
        pass
    cfg = PR.load_cfg()
    if not cfg.get("topic") or not cfg.get("on"):
        return False
    ok, _why = PR.ntfy_post(cfg["ntfy"], cfg["topic"], m["body"], title=m["title"], priority=m.get("priority"), tags=m.get("tags"))
    return bool(ok)


def heal(ctx, force_clean: bool = False, board=None, push=None, disk_free=None) -> dict:
    """One full run with state: run(), the log, tiny.json, and the alerts for what it could not fix (once a day per fault)."""
    sp = os.path.join(ctx.home, "state.json")
    state = _read_json(sp, {}) or {}
    res = run(ctx, state, force_clean=force_clean, disk_free=disk_free)
    lines = [f"{'APPLY' if ctx.apply else 'DRY'} {i['status'].upper():5} {i['fault']:8} {i['text']}" for i in res["items"]] or \
        [f"{'APPLY' if ctx.apply else 'DRY'} all fine"]
    if not ctx.apply:
        return res
    _log(ctx, lines)
    sent = dict(state.get("sent") or {})
    for it in res["need"]:
        if ctx.now - float(sent.get(it["key"]) or 0) >= ALERT_EVERY_S:
            res.setdefault("alerts", []).append({"key": it["key"], **alert(ctx, it, board=board, push=push)})
            sent[it["key"]] = int(ctx.now)
    state["sent"] = {k: v for k, v in sent.items() if ctx.now - float(v) < 7 * 86400}
    state["t"] = int(ctx.now)
    state["need"] = [i["key"] for i in res["need"]]
    state["last"] = [{k: i[k] for k in ("fault", "status", "text")} for i in res["items"]][:12]
    state["hist"] = ([h for h in state.get("hist") or [] if isinstance(h, dict)] + [{"t": int(ctx.now), "fixed": len(res["fixed"]),
                                                                                         "need": len(res["need"])}])[-KEEP_HIST:]
    if res.get("clean") is not None:
        state["clean_t"] = int(ctx.now)
        state["freed"] = res["clean"]["bytes"] / GB
        state["sizes"] = res["clean"].get("sizes") or state.get("sizes")
    f = free_gb(ctx.root) if disk_free is None else disk_free
    state["free"] = round(f, 1) if f is not None else None
    _write_json(sp, state)
    _write_json(os.path.join(ctx.home, "tiny.json"), tiny(state, ctx.now))
    return res


def _lock(d: str, now) -> str | None:
    """One self-heal at a time: the lock file's path, or None while another run holds it (a lock over 30 min old is a crash's)."""
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "run.lock")
    for _ in range(2):
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as fh:
                fh.write(str(int(now)))
            return p
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(p) <= 1800:
                    return None
                os.remove(p)
            except OSError:
                return None
        except OSError:
            return None
    return None


def maybe_run(say=print, now=None, root: str = ROOT, env=None, ctx=None) -> dict | None:
    """The 15-minute report's hook (tools/pc_report.py main): at most once an hour, Windows only (LE_SELF_HEAL=1 forces it,
    =0 turns it off). Never raises."""
    try:
        env = os.environ if env is None else env
        sw = str(env.get("LE_SELF_HEAL", "")).strip()
        if sw == "0" or (os.name != "nt" and sw != "1" and ctx is None) or (env.get("LE_SELFTEST_CHILD") == "1" and ctx is None):
            return None                                   # off, not the Windows PC, or a PC self-test's child (sealed temp folders)
        now = time.time() if now is None else now
        st = _read_json(os.path.join(root, LOG_DIR_REL, "state.json"), {}) or {}
        if now - float(st.get("t") or 0) < EVERY_S:
            return None
        lk = _lock(os.path.join(root, LOG_DIR_REL), now)
        if lk is None:
            return None                                   # the 15-minute task and the report keeper started one at the same time
        try:
            ctx = ctx or Ctx(root=root, now=now, apply=True, env=env)
            res = heal(ctx)
        finally:
            try:
                os.remove(lk)
            except OSError:
                pass
        if res["fixed"] or res["need"]:
            say(f"  [{'..' if res['need'] else 'OK'}]  self-heal: fixed {len(res['fixed'])}" + (f", needs you: {res['need'][0]['text'][:90]}" if res["need"] else ""))
        return res
    except Exception as e:  # noqa: BLE001
        try:
            say(f"  [..]  self-heal failed softly: {e.__class__.__name__}")
        except Exception:
            pass
        return None


def status(root: str = ROOT, now=None) -> dict:
    now = time.time() if now is None else now
    st = _read_json(os.path.join(root, LOG_DIR_REL, "state.json"), {}) or {}
    return {"ran": int(st["t"]) if st.get("t") else None, "need": st.get("need") or [], "last": st.get("last") or [],
            "tiny": tiny(st, now) if st else None}


def card(res: dict) -> str:
    out = []
    for i in res["items"]:
        tag = {"fixed": "FIXED", "would": "WOULD", "need": "NEEDS YOU", "info": ".."}.get(i["status"], i["status"])
        out.append(f"  [{tag}] {i['fault']:<8} {i['text']}")
        if i["status"] == "need" and i.get("step"):
            out.append(f"           -> {i['step']}")
    if not res["items"]:
        out.append("  [OK] nothing to fix: git, the update, NinjaTrader's order files, pid files, the bot server, packages, clock, disk")
    if not res["apply"] and any(i["status"] == "would" for i in res["items"]):
        out.append("  Dry run: nothing was changed. To fix it now: python -X utf8 -m engine.self_heal --apply")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -X utf8 -m engine.self_heal", description="SELF-HEAL: fix the PC's known faults (dry run first)")
    ap.add_argument("--apply", action="store_true", help="fix now (without it: a dry run that changes nothing)")
    ap.add_argument("--clean", action="store_true", help="the weekly clean now (dry run unless --apply)")
    ap.add_argument("--sizes", action="store_true", help="what grows in the bot folder")
    ap.add_argument("--status", action="store_true", help="the last run")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.status:
        s = status()
        print(json.dumps(s, indent=1) if a.json else (s["tiny"] or {}).get("line") or "self-heal never ran on this PC")
        return 0
    ctx = Ctx(apply=a.apply, say=print)
    if a.sizes:
        s = sizes(ctx)
        print(json.dumps(s, indent=1) if a.json else "  " + " · ".join(f"{k} {v} GB" for k, v in s.items()))
        return 0
    if a.clean:
        ctx.say = SAY_OFF
        r = clean(ctx)
        for kind, n in sorted(r["kinds"].items(), key=lambda x: -x[1]):
            print(f"  {'freed' if a.apply else 'would free'} {n / GB:6.2f} GB  {kind}")
        print(f"  {'freed' if a.apply else 'would free'} {r['bytes'] / GB:.2f} GB in {r['n']} file(s)" + ("" if a.apply else " (dry run: add --apply)"))
        return 0
    res = heal(ctx) if a.apply else run(ctx, _read_json(os.path.join(ctx.home, "state.json"), {}) or {})
    print(json.dumps(res, indent=1, default=str) if a.json else card(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
