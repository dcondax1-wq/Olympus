"""PC heartbeat: the always-on PC (a Surface in a drawer, say) tells the cloud it is alive, so the cloud monitor can
alert the phone when it is not.

Every `every_s` seconds the PC server pushes one tiny commit (just heartbeat.json) to the `heartbeat` branch of the
repo, replacing the previous one (orphan commit, force push: no history grows). The cloud monitor (GitHub Actions) reads
that branch on every run and alerts when the bot said it was running but has been silent for 20 minutes in a session.

heartbeat.json: {"t": unix seconds, "running": bot running, "adapter": paper|ninjatrader|tradovate, "position": bool,
                 "model_state": str, "host": computer name, "every_s": N,
                 "acct": the Accounts page's view of the routed activity (engine/accounts.pc_activity: account name + SIM/LIVE,
                         open position, today's orders, last 60 closed routed trades, the eval's P&L per day; secret-free,
                         under 48 KB; older cloud monitors ignore it),
                 "health": is the bot really trading the eval (engine/accounts.pc_health: account name + LIVE/SIM, adapter
                           enabled or the DISABLED reason, armed, NINJATRADER_LIVE set (a bool), NinjaTrader connection,
                           feed source + age of the last 1m / 5m bar, last poll + errors, the LIT stage, setups seen today,
                           orders today, kill flag, uptime; secret-free, ~2 KB; the cloud's verdict: accounts.verdict),
                 "remote": the phone remote control (engine/remote_ctl.hb_field: on, "remote: last cmd X done at HH:MM ET",
                           a stop waiting for flat, the last fetch error),
                 "launch": the launch checklist (engine/launch_check.block: items green / red, each red with its fix command),
                 "ops": the owner's PC helpers (engine/ops_checks.hb_fields: last check red / yellow count + first fix,
                        last backup, free disk; ~200 bytes),
                 "blitz": the BLITZ scalper PAPER shadow (engine/blitz.compact: state text, today's paper trades, the simulated
                          25K eval, today's band; never routed; ~3 KB),
                 "account_c": BLITZ routed to its OWN account (engine/account_c.AccountC.hb_block: REAL / SIM / PAPER, eval,
                              performance scorecard, open trade, today's rows, P&L per day; ~4 KB; key absent when off),
                 "selftest": the PC self-test's last result (engine/pc_selftest.hb_block; key absent before the first run),
                 "pc_health": CPU / RAM / disk / NinjaTrader / bot memory / OneDrive / clock / poll lines, green / amber / red
                              (engine/pc_health.hb_block; key absent before the first sample),
                 "board": the Board (engine/board_events.hb_block: every account's stage / balance / room / to pass / locked, the
                          newest events, owner notes not answered; public, <= 6 KB; docs/BOARD.md)}
Every beat also writes the payload to logs/heartbeat_last.json (local, gitignored) for HEALTH_CHECK and the ops task.

No Yahoo (engine/pcbars.py, owner 2026-10-19): next to heartbeat.json the commit carries the PC's NinjaTrader bars,
bars_1m.csv.gz (last 3 days of 1m, every push) and bars_5m.csv.gz (last 40 days of 5m, rebuilt hourly; unchanged = the
same blob, nothing new to push), plus heartbeat.json "bars" (newest bar times, the forming 1m bar's open). The cloud monitor
and the fast-entry watcher trade the paper ledger on them instead of Yahoo. While a LIT setup is armed or a trade is open
in a session the PC pushes every FAST_EVERY_S seconds instead of every_s, so the cloud's watcher sees the entry soon.

On by default only when LE_HEARTBEAT=1 (scripts/run_bot.ps1 sets it; a dev shell does not push anything). Needs git
with push rights in the project folder (the owner's PC has them). Never raises into the server; failures are logged
at most once an hour.

Robust push (2026-10-26, after the Surface went silent 22:38 -> 05:20 ET on 2026-10-25/26; tests/test_heartbeat.py):
  * The commit is built and pushed from a private scratch git dir (SCRATCH = data/heartbeat_pub.git, gitignored), like the
    phone's live.json (engine/live_publish.py): the project's own .git (shallow, OneDrive, index.lock, a refused pull,
    a gc) is never written and can no longer block the push; ~1,000 loose objects a day no longer pile up in it.
  * Every git call has a hard timeout that also holds on Windows (run_cmd: output to temp files, the whole process tree
    killed; subprocess.run's own timeout waits forever there when git-remote-https / the credential manager hang), never
    prompts (GIT_TERMINAL_PROMPT=0, GCM_INTERACTIVE=never) and drops a stalled transfer (http.lowSpeedTime).
  * The push is --force-with-lease on refs/heads/heartbeat only (_BRANCH_RE: never main or any other branch) on the
    commit this PC pushed last (scratch ref LAST_REF); refused (another writer moved the branch: an old server still
    running, a second PC) or a one-off failure -> the branch tip is re-read (git ls-remote) and the push retried once
    with the lease on that tip. The branch stays one disposable orphan commit.
  * A watchdog thread (every WATCH_S) restarts the push thread when it died or one beat ran longer than STUCK_S, and
    notices when the whole process was frozen (PC asleep / suspended: its own tick took far longer than asked): it then
    pushes at once instead of waiting out the rest of the 5 minutes. After a failure the next try comes after RETRY_S.
  * health.hb in every heartbeat (and live.json): the last push result and error, failures in a row, restarts, the
    last frozen stretch. GET /api/health/ping "heartbeat" carries the same.
"""
from __future__ import annotations

import json
import os
import platform
import re
import signal
import subprocess
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCH = "heartbeat"
SILENT_AFTER_S = 20 * 60
LAST_PATH = os.path.join(ROOT, "logs", "heartbeat_last.json")   # the last payload, for engine/ops_checks (logs/ is gitignored)
FAST_EVERY_S = 60
FAST_STAGES = ("limit", "cisd1m", "trade")       # engine/accounts._lit_stage: a setup armed, or in a trade
SCRATCH_REL = os.path.join("data", "heartbeat_pub.git")   # private git dir the heartbeat pushes from (gitignored)
LAST_REF = "refs/hb/last"                        # in the scratch dir: the commit this PC pushed last (the lease's value)
GIT_TIMEOUT_S = 30.0                             # every local git call / ls-remote: hard limit (process tree killed)
PUSH_TIMEOUT_S = 75.0                            # one git push: hard limit
STUCK_S = 600.0                                  # a beat running longer than this = stuck: the watchdog restarts the thread
WATCH_S = 60.0                                   # the watchdog's tick
FROZEN_S = 180.0                                 # a tick this much longer than asked = the process was frozen (PC asleep)
RETRY_S = 60.0                                   # after a failed push the next try comes after at most this
# the account behind origin is gone (suspended 2026-11-08): the heartbeat stops trying GitHub for the rest of this process and
# writes locally (engine/nogithub.local_push), the same as GitHub-free mode; before, it failed 22x a day with a red health line
GONE_RE = re.compile(r"suspended|repository not found|returned error: 403|account (is )?(disabled|locked)", re.I)
FAIL_NOTICE_S = 30 * 60                          # a refused GitHub login for this long -> one phone push a day (2026-10-29)
AUTH_RE = re.compile(r"authentication failed|could not read username|terminal prompts disabled|invalid username or password|"
                     r"permission denied|\b40[13]\b|bad credentials|logon failed|credential", re.I)
LOCK_WAIT_S = 90.0                               # a second caller (the remote control's "status") waits this long for a beat
PRUNE_EVERY = 50                                 # scratch dir: drop the unreachable old heartbeat objects every N pushes
STALE_LOCK_S = 600.0                             # scratch dir only: a *.lock older than this is left over from a killed git
_BRANCH_RE = re.compile(r"^heartbeat([-_.][A-Za-z0-9._-]+)?$")   # the heartbeat only ever pushes its own status branch
_MOVED = ("stale info", "rejected", "fetch first", "non-fast-forward")
_LAST_PUSHED: dict = {}                          # (url, branch) -> the commit this process pushed last (lease fallback)
_PUSHES = [0]


def enabled() -> bool:
    return os.environ.get("LE_HEARTBEAT", "0") == "1"


def _git(args, cwd, inp=None, timeout=60):
    return subprocess.run(["git", *args], cwd=cwd, input=inp, capture_output=True, text=True, timeout=timeout)


# ------------------------------------------------------------------------------------------------ git with a real timeout
class Ran:
    """What run_cmd returns (the fields of subprocess.CompletedProcess the heartbeat uses, bytes)."""

    def __init__(self, returncode, stdout=b"", stderr=b"", timed_out=False, took_ms=0):
        self.returncode, self.stdout, self.stderr, self.timed_out, self.took_ms = returncode, stdout, stderr, timed_out, took_ms

    @property
    def out(self) -> str:
        return (self.stdout or b"").decode(errors="replace").strip()

    @property
    def err(self) -> str:
        return (self.stderr or b"").decode(errors="replace").strip()


def _kill_tree(p):
    """Stop a process and everything it started (git push -> git-remote-https -> the credential manager)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           stdin=subprocess.DEVNULL, timeout=15)
        else:
            os.killpg(p.pid, signal.SIGKILL)       # start_new_session: the group id is the child's pid
    except Exception:
        pass
    try:
        p.kill()
    except Exception:
        pass


def run_cmd(cmd, cwd=None, inp: bytes | None = None, timeout: float = GIT_TIMEOUT_S, env=None) -> Ran:
    """subprocess.run with a timeout that also holds on Windows. There, subprocess.run(timeout=) kills git.exe and then
    waits WITHOUT a limit for its output pipes to close, which never happens while git-remote-https.exe or the credential
    manager (they inherit the pipe) hang: the heartbeat thread blocked for good. Here stdin / stdout / stderr are temp
    files (no pipe to wait on) and a timeout kills the whole process tree. Never raises (returncode -1 = could not start)."""
    t0 = time.monotonic()
    try:
        with tempfile.TemporaryFile() as fin, tempfile.TemporaryFile() as fo, tempfile.TemporaryFile() as fe:
            if inp is not None:
                fin.write(inp)
                fin.flush()
                fin.seek(0)
            kw = {} if os.name == "nt" else {"start_new_session": True}
            p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=fin if inp is not None else subprocess.DEVNULL, stdout=fo,
                                 stderr=fe, **kw)
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
            fe.seek(0)
            out, err = fo.read(), fe.read()
        took = int((time.monotonic() - t0) * 1000)
        if timed_out:
            err = (err or b"") + f"\ntimed out after {timeout:g} s (git and its helpers stopped)".encode()
            return Ran(p.returncode if p.returncode not in (None, 0) else -9, out, err, True, took)
        return Ran(p.returncode, out, err, False, took)
    except Exception as e:
        return Ran(-1, b"", f"{e.__class__.__name__}: {e}".encode(), False, int((time.monotonic() - t0) * 1000))


def _redact(s: str) -> str:
    """No credentials in an error text (https://user:token@host -> https://host)."""
    return re.sub(r"(https?://)[^@\s/]+@", r"\1", s or "")


def _tail(r: Ran, n: int = 200) -> str:
    lines = [ln for ln in r.err.splitlines() if ln.strip() and "push negotiation failed" not in ln
             and "expected 'acknowledgments'" not in ln]
    return _redact("\n".join(lines))[-n:]


def _git_env(extra: dict | None = None) -> dict:
    """Never prompt (a hidden prompt in a server window is a silent hang): no terminal prompt, no credential-manager
    window. A login that needs the owner fails with its error instead, and health.hb / the ops check show it."""
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", **(extra or {})}


_COMMIT_ENV = {"GIT_AUTHOR_NAME": "liquidity-engine-pc", "GIT_AUTHOR_EMAIL": "pc@liquidity-engine.local",
               "GIT_COMMITTER_NAME": "liquidity-engine-pc", "GIT_COMMITTER_EMAIL": "pc@liquidity-engine.local"}
_NET_CFG = ["-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=30", "-c", "push.negotiate=false",
            "-c", "credential.interactive=never"]


def scratch_dir(cwd: str = ROOT) -> str:
    return os.path.join(cwd, SCRATCH_REL)


def _clear_stale_locks(git_dir: str, now: float | None = None, older_s: float = STALE_LOCK_S) -> list:
    """*.lock files a killed git left in the PRIVATE scratch dir (nobody else uses it). Never the project's .git."""
    now = time.time() if now is None else now
    gone = []
    for base, _dirs, names in os.walk(git_dir):
        for n in names:
            if n.endswith(".lock"):
                p = os.path.join(base, n)
                try:
                    if now - os.path.getmtime(p) > older_s:
                        os.remove(p)
                        gone.append(os.path.relpath(p, git_dir))
                except OSError:
                    pass
    return gone


def _scratch(git_dir: str, cwd: str) -> str | None:
    """Create the scratch bare repo once (with this repo's local credential / ssh / proxy / url settings). Error or None."""
    try:
        if not os.path.isdir(os.path.join(git_dir, "objects")):
            os.makedirs(os.path.dirname(git_dir), exist_ok=True)
            r = run_cmd(["git", "init", "-q", "--bare", git_dir])
            if r.returncode:
                return "git init of the heartbeat's scratch dir failed: " + _tail(r, 120)
            r = run_cmd(["git", "config", "--local", "--get-regexp", r"^(credential\..*|core\.sshcommand|http\..*|url\..*)$"],
                        cwd=cwd)
            for ln in r.out.splitlines():
                k, _, v = ln.partition(" ")
                if k and v:
                    run_cmd(["git", "--git-dir", git_dir, "config", "--add", k, v])
        _clear_stale_locks(git_dir)
        return None
    except Exception as e:
        return f"{e.__class__.__name__}: {e}"


def remote_url(cwd: str = ROOT, remote: str = "origin") -> str | None:
    """The push URL of `remote` in the repo at cwd (insteadOf applied by git), or `remote` itself when it is a URL / path."""
    if any(c in remote for c in "/\\:"):
        return remote
    r = run_cmd(["git", "remote", "get-url", "--push", remote], cwd=cwd)
    u = r.out.splitlines()[0].strip() if not r.returncode and r.out else ""
    if not u:
        return None
    if "://" not in u and not re.match(r"^[^/\\]+@[^/\\]+:", u) and not os.path.isabs(u) and os.path.exists(os.path.join(cwd, u)):
        u = os.path.abspath(os.path.join(cwd, u))      # a relative local path: relative to the project, not the scratch dir
    return u


def remote_tip(url: str, branch: str = BRANCH, git_dir: str | None = None, cwd: str | None = None) -> tuple:
    """(tip sha, None) of refs/heads/<branch> on the remote ("" = no such branch), or (None, error). git ls-remote: no
    objects are downloaded and nothing local is written."""
    r = run_cmd(["git", *_NET_CFG, *(["--git-dir", git_dir] if git_dir else []), "ls-remote", url, f"refs/heads/{branch}"],
                cwd=cwd, timeout=GIT_TIMEOUT_S, env=_git_env())
    if r.returncode:
        return None, _tail(r) or "ls-remote failed"
    for ln in r.out.splitlines():
        sha, _, ref = ln.partition("\t")
        if ref.strip() == f"refs/heads/{branch}" and re.fullmatch(r"[0-9a-f]{40,64}", sha.strip()):
            return sha.strip(), None
    return "", None


def _blob(data: bytes, cwd, git_dir=None) -> str | None:
    """git hash-object -w of raw bytes (binary stdin: no newline translation on Windows). The id, or None."""
    r = run_cmd(["git", *(["--git-dir", git_dir] if git_dir else []), "hash-object", "-w", "--stdin"], cwd=cwd, inp=data)
    out = r.out
    return out if not r.returncode and len(out) >= 40 else None


def _lease_push(gd: list, cwd, url: str, branch: str, commit: str, expect: str, timeout: float) -> Ran:
    return run_cmd(["git", *_NET_CFG, *gd, "push", "-q", f"--force-with-lease=refs/heads/{branch}:{expect}", url,
                    f"{commit}:refs/heads/{branch}"], cwd=cwd, timeout=timeout, env=_git_env())


def push(payload: dict, cwd: str = ROOT, remote: str = "origin", branch: str = BRANCH, files: dict | None = None,
         git_dir: str | None = None, timeout: float = PUSH_TIMEOUT_S) -> dict:
    """Write payload as heartbeat.json (+ `files`: {name: bytes}, e.g. the PC's NinjaTrader bars) in an orphan commit and
    push it over refs/heads/<branch> of `remote` (the remote's name in the repo at cwd, or a URL), from the private scratch
    git dir (git_dir, default <cwd>/data/heartbeat_pub.git; falls back to the repo at cwd, plumbing only, when it cannot
    be made). --force-with-lease on the commit pushed last; refused or failed once -> re-read the tip, retry once.
    Only ever the heartbeat branch. Returns {"ok", "commit" | "error", "attempts", "retried", "took_ms"}. Never raises."""
    t0 = time.monotonic()
    att = 0

    def done(ok, **kw):
        return {"ok": ok, **kw, "attempts": att, "took_ms": int((time.monotonic() - t0) * 1000)}
    try:
        if not _BRANCH_RE.match(str(branch or "")):
            return done(False, error=f"refused: the heartbeat only pushes its own status branch '{BRANCH}', never '{branch}'")
        url = remote_url(cwd, remote)
        if not url:
            return done(False, error=f"no push URL for remote '{remote}'")
        gdir = git_dir or scratch_dir(cwd)
        err = _scratch(gdir, cwd)
        gd = [] if err else ["--git-dir", gdir]       # scratch unusable: the old way (plumbing in the project repo)
        body = json.dumps(payload, separators=(",", ":"))
        blob = _blob(body.encode("utf-8"), cwd, gdir if not err else None)
        if not blob:
            return done(False, error="hash-object failed" + (f" ({err})" if err else ""))
        entries = [f"100644 blob {blob}\theartbeat.json\n"]
        for name, data in sorted((files or {}).items()):
            if not data or "/" in name or "\t" in name or "\n" in name:
                continue
            b = _blob(bytes(data), cwd, gdir if not err else None)
            if not b:
                return done(False, error=f"hash-object failed ({name})")
            entries.append(f"100644 blob {b}\t{name}\n")
        # bytes, not text: on Windows text-mode stdin turns "\n" into "\r\n" and the file was named "heartbeat.json\r"
        r = run_cmd(["git", *gd, "mktree"], cwd=cwd, inp="".join(entries).encode())
        if r.returncode or not r.out:
            return done(False, error=_tail(r) or "mktree failed")
        tree = r.out
        # never signed (a signing prompt would hang the beat); "-c" works on every git version
        r = run_cmd(["git", "-c", "commit.gpgsign=false", *gd, "commit-tree", tree, "-m", f"heartbeat {payload.get('t')}"], cwd=cwd,
                    env=_git_env(_COMMIT_ENV))
        if r.returncode or not r.out:
            return done(False, error=_tail(r) or "commit-tree failed")
        commit = r.out
        key = (url, branch)
        expect = _LAST_PUSHED.get(key)
        if expect is None and not err:
            rr = run_cmd(["git", *gd, "rev-parse", "--verify", "-q", LAST_REF], cwd=cwd)
            expect = rr.out if not rr.returncode and rr.out else None
        retried = None
        if expect is None:                     # first push of this PC (or the scratch dir is new): lease on the tip now
            expect, terr = remote_tip(url, branch, gdir if not err else None, cwd)
            if expect is None:
                return done(False, error=f"remote not reachable: {terr}")
        att += 1
        r = _lease_push(gd, cwd, url, branch, commit, expect, timeout)
        if r.returncode:
            first = _tail(r)
            moved = any(m in first for m in _MOVED)
            tip, terr = remote_tip(url, branch, gdir if not err else None, cwd)
            if tip is None:
                return done(False, error=first or "push failed", probe=f"ls-remote: {terr}")
            retried = ("the branch had moved (another writer): pushed over its tip" if moved else
                       f"retried after: {first[-120:]}")
            att += 1
            r = _lease_push(gd, cwd, url, branch, commit, tip, timeout)
            if r.returncode:
                return done(False, error=_tail(r) or first or "push failed", first_error=first, retried=retried)
        _LAST_PUSHED[key] = commit
        if not err:
            run_cmd(["git", *gd, "update-ref", LAST_REF, commit], cwd=cwd)
            _PUSHES[0] += 1
            if _PUSHES[0] % PRUNE_EVERY == 0:      # the replaced heartbeats are unreachable: drop them (scratch dir only)
                run_cmd(["git", *gd, "prune", "--expire=now"], cwd=cwd, timeout=120)
        return done(True, commit=commit[:10], **({"retried": retried} if retried else {}),
                    **({"scratch_error": err} if err else {}))
    except Exception as e:
        return done(False, error=f"{e.__class__.__name__}: {e}")


def read_file(name: str, cwd: str = ROOT, ref: str = "FETCH_HEAD") -> bytes | None:
    """The raw bytes of one file of the fetched heartbeat commit (None when it is not there)."""
    try:
        r = subprocess.run(["git", "show", f"{ref}:{name}"], cwd=cwd, capture_output=True, timeout=60)
        return r.stdout if not r.returncode and r.stdout else None
    except Exception:
        return None


def read(cwd: str = ROOT, remote: str = "origin", branch: str = BRANCH, now: float | None = None, files=()) -> dict:
    """Cloud side: fetch the branch and parse heartbeat.json. {"present": bool, "age_s", "silent": bool, ...payload}.
    files = names to read from the same commit too (raw bytes in hb["files"]; never stored in state.json)."""
    now = time.time() if now is None else now
    try:
        r = _git(["fetch", "-q", "--depth", "1", remote, branch], cwd, timeout=90)
        if r.returncode:
            return {"present": False, "reason": "no heartbeat branch"}
        r = _git(["show", f"FETCH_HEAD:heartbeat.json"], cwd)
        if r.returncode:
            # older Windows PCs wrote the name as "heartbeat.json\r" (text-mode stdin): read that blob by its id
            t = _git(["ls-tree", "FETCH_HEAD"], cwd)
            ids = [ln.split()[2] for ln in (t.stdout or "").splitlines()
                   if len(ln.split()) >= 4 and "heartbeat.json" in ln.split("\t", 1)[-1]]
            r = _git(["cat-file", "-p", ids[0]], cwd) if ids else r
        if r.returncode:
            return {"present": False, "reason": "no heartbeat.json"}
        hb = json.loads(r.stdout)
    except Exception as e:
        return {"present": False, "reason": f"{e.__class__.__name__}: {e}"}
    if files:
        hb["files"] = {n: read_file(n, cwd) for n in files}
    age = max(0.0, now - float(hb.get("t") or 0))
    every = float(hb.get("every_s") or 300)
    hb.update(present=True, age_s=int(age), silent=bool(hb.get("running")) and age > max(SILENT_AFTER_S, 3 * every))
    return hb


def _push_pk():
    try:
        from engine import push
        return push.pc_public_key()
    except Exception:
        return None


def _health(bot):
    """The "health" block (engine/accounts.pc_health). Never raises; None when unavailable."""
    try:
        from engine import accounts
        return accounts.pc_health(bot)
    except Exception:
        return None


def _nt_log(bot):
    """NinjaTrader's own log lines about the bot's orders (engine/nt_log.py). Never raises."""
    try:
        from engine import nt_log
        return nt_log.hb_block(bot)
    except Exception:
        return None


def _ops():
    """The owner's PC helpers' last result (engine/ops_checks.hb_fields: checks red / yellow, last backup, free disk)."""
    try:
        from . import ops_checks
        return ops_checks.hb_fields()
    except Exception:
        return None


def save_last(payload: dict, res: dict, path: str = LAST_PATH):
    """The last payload + push result, for HEALTH_CHECK / the ops task (engine/ops_checks reads it). Never raises."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"saved_t": int(time.time()), "push": {"at": int(time.time()), **(res or {})}, "payload": payload}, fh,
                      separators=(",", ":"), default=str)
        from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
        _fs_replace(tmp, path)
    except Exception:
        pass


def _launch(bot, health):
    """The launch checklist block (engine/launch_check.block: anchor, allowlist, account B, startup reconcile, NinjaTrader,
    feed, Sim roundtrips, armed, bot up from 01:55 ET). Never raises; None when unavailable."""
    try:
        from . import launch_check
        return launch_check.block(bot, health if isinstance(health, dict) else None)
    except Exception:
        return None


def _acct(bot):
    """The Accounts page block (engine/accounts.pc_activity). Never raises; None when unavailable."""
    try:
        from engine import accounts
        return accounts.pc_activity(bot)
    except Exception:
        return None


def _remote():
    """The remote-control block (engine/remote_ctl.hb_field: "remote: last cmd X done at HH:MM ET"). Never raises."""
    try:
        from . import remote_ctl
        return remote_ctl.hb_field()
    except Exception:
        return None


def _live_pub():
    """The phone live.json push's last result (engine/live_publish.hb_field). Never raises."""
    try:
        from . import live_publish
        return live_publish.hb_field()
    except Exception:
        return None


def _brain(bot, max_bytes: int = 16_000):
    """The heartbeat's "brain" block: engine/brain.compact of the bot's last Bot Brain (stage, what it waits for, nearest
    levels, today's setups with their checks, sizing, management, guards, the last 30 log lines). Never raises."""
    try:
        b = getattr(bot, "brain", None)
        if not b:
            return None
        from engine import brain
        return brain.compact(b, max_bytes=max_bytes)
    except Exception:
        return None


def _second(bot):
    """The heartbeat's "second" block: today's state + last paper trades of the second strategies (engine/second.compact
    of LiveBot.second). Paper only. Never raises."""
    try:
        s = getattr(bot, "second", None)
        ri = bot.second_route_info() if callable(getattr(bot, "second_route_info", None)) else None
        if not s:
            # nothing computed yet by the paper thread: the routed strategies still show ("ROUTED on <account>")
            return {"t": None, "paper": not (ri or {}).get("keys"), "strategies": {}, "route": ri} if ri else None
        from engine import second
        out = second.compact(s, route=ri)
        av = getattr(bot, "atlas_v2", None)          # ATLAS v2 PAPER shadow (engine/atlas_v2.compact; never routed)
        if out is not None and isinstance(av, dict) and av.get("ev"):
            try:
                from engine import atlas_v2
                out["atlas_v2"] = atlas_v2.compact(av)
            except Exception:
                pass
        return out
    except Exception:
        return None


def _blitz(bot):
    """The heartbeat's "blitz" block: the BLITZ scalper PAPER shadow (engine/blitz.compact of LiveBot.blitz: state text, today's
    paper trades, the paper 25K eval, today's band). Paper only, never routed. None before its first run. Never raises."""
    try:
        s = getattr(bot, "blitz", None)
        if not isinstance(s, dict):
            return None
        from engine import blitz
        return blitz.compact(s)
    except Exception:
        return None


def _mind(bot):
    """The heartbeat's "mind" block: engine/mind.compact of Mind's last cached block (regime, plans, similar setups, reviews,
    proposals; < 12 KB). None before Mind's first compute (the payload then stays as before). Never raises."""
    try:
        from engine import mind
        return mind.compact(mind.MIND.cached(), max_bytes=12_000)
    except Exception:
        return None


def _selftest():
    """The PC self-test's last result (engine/pc_selftest.hb_block: t, version, mode, passed / failed, the first failures,
    duration, running; ~600 bytes). None before the first run (the key is then left out). Never raises."""
    try:
        from . import pc_selftest
        return pc_selftest.hb_block()
    except Exception:
        return None


def _pc_health():
    """The PC health watchdog (engine/pc_health.hb_block: CPU / RAM / disk / NinjaTrader / bot memory / OneDrive / clock /
    poll, each green / amber / red; ~1.5 KB). None before its first sample. Never raises."""
    try:
        from . import pc_health
        return pc_health.hb_block()
    except Exception:
        return None


def _opt(key, val) -> dict:
    """{key: val} when val is not None, else {} (a block that is off adds no key: the payload stays byte for byte as before)."""
    return {key: val} if val is not None else {}


def _account_c(bot):
    """The heartbeat's "account_c" block: BLITZ on its own account (engine/account_c.AccountC.hb_block: eval, scorecard, open
    trade, today's routed rows, P&L per day, closed trades). None when account C is off: the key is then left out (the
    payload is exactly as before). Never raises."""
    try:
        ac = getattr(bot, "acct_c", None)
        if ac is None:
            return None
        return ac.hb_block()
    except Exception as e:
        return {"error": f"{e.__class__.__name__}: {e}"[:200]}


def _fleet(bot):
    """The heartbeat's "fleet" block: the follower accounts (engine/fleet.Fleet.hb_block, < 6 KB: firm, plan, stage, balance,
    room, today, open, slippage, warnings). None when the fleet is off (no data/fleet.json): the key is then left out (the
    payload is exactly as before). Never raises."""
    try:
        fl = getattr(bot, "fleet", None)
        if fl is None:
            return None
        return fl.hb_block()
    except Exception as e:
        return {"error": f"{e.__class__.__name__}: {e}"[:200]}


def _life(bot):
    """The "life" block (engine/lifecycle.hb_block, < 1.5 KB): each routed account's MFFU stage + the last 3 events. None
    before the bot saw an account (the key is then left out). Never raises."""
    try:
        from engine import lifecycle
        return lifecycle.hb_block(bot)
    except Exception:
        return None


def _exec():
    """The "exec" block (engine/fill_audit.heartbeat_block: slippage / missed / extra $ against the backtest). Never raises."""
    try:
        from engine import fill_audit
        return fill_audit.heartbeat_block()
    except Exception:
        return None


def _learn():
    """The "learn" block (engine/live_learning.heartbeat_block: the learned execution costs + the last trade reviews). Never raises."""
    try:
        from engine import live_learning
        return live_learning.heartbeat_block()
    except Exception:
        return None


def _money():
    """The "money" block (engine/money_goal.heartbeat_block: the owner's savings / jobs / Kalshi figures and goal targets
    from data/goals_money.json; only the targets when "show on the phone" is off; None before the first save). Never raises."""
    try:
        from engine import money_goal
        return money_goal.heartbeat_block()
    except Exception:
        return None


def _ai(bot):
    """The AI-watch block (engine/ai_watch.hb_block). Never raises."""
    try:
        from . import ai_watch
        return ai_watch.hb_block(bot)
    except Exception:
        return None


def _board(bot):
    """The Board (engine/board_events.hb_block: account rows, newest events, open owner notes; privacy-passed, <= 6 KB; also notes
    bot_started / bot_stopped). Never raises."""
    try:
        from . import board_events
        return board_events.hb_block(bot)
    except Exception:
        return None


def _alerts_plus(bot):
    """{"rules", "crit"} (engine/alerts_plus.hb_block). Never raises."""
    try:
        from . import alerts_plus
        return alerts_plus.hb_block(bot)
    except Exception:
        return {"rules": None, "crit": []}


def _hm(t) -> str:
    try:
        from zoneinfo import ZoneInfo
        import datetime as _dt
        return _dt.datetime.fromtimestamp(float(t), ZoneInfo("America/New_York")).strftime("%a %H:%M")
    except Exception:
        return str(int(t or 0))


def _dur(s) -> str:
    s = int(max(0, s or 0))
    return f"{s // 3600} h {s % 3600 // 60} min" if s >= 3600 else f"{s // 60} min"


def _default_notify(title, body, key):
    from . import autoupdate
    autoupdate.notify(title, body, key=key)


class Heartbeat:
    """Daemon thread on the PC server: pushes a heartbeat every `every_s` seconds while the server runs, plus a watchdog
    thread that restarts it when it died or hung and pushes at once after the PC was asleep (see the module doc)."""

    def __init__(self, bot, every_s: float = 300.0, log=print, last_path: str = LAST_PATH, push_fn=None, clock=time.time,
                 watch_s: float = WATCH_S, stuck_s: float = STUCK_S, frozen_s: float = FROZEN_S, retry_s: float = RETRY_S,
                 lock_wait_s: float = LOCK_WAIT_S, notify_fn=None):
        self.bot, self.every_s, self.log, self.last_path = bot, every_s, log, last_path
        # the phone push when the GitHub login is refused (engine/autoupdate.notify: the PC's own Web Push, which needs
        # no GitHub push): on with the real push; a test's fake push_fn gets it only with its own notify_fn
        self.notify_fn = notify_fn if notify_fn is not None else (_default_notify if push_fn is None else None)
        self._fail_notified = None
        if push_fn is None:                  # GitHub-free mode (engine/nogithub.py): same payload and bars, written to logs/pc_hb/
            try:
                from . import nogithub as _ng
                if _ng.active():
                    push_fn, self.notify_fn = _ng.local_push, None
            except Exception:
                pass
        self.push_fn = push_fn or push
        self.clock = clock
        self.watch_s, self.stuck_s, self.frozen_s, self.retry_s, self.lock_wait_s = watch_s, stuck_s, frozen_s, retry_s, lock_wait_s
        self.last: dict = {}
        self._stop = threading.Event()
        self._wake = threading.Event()       # set = beat now (after the PC woke up, or stop())
        self._thread = None
        self._watch_thread = None
        self._gen = 0                        # push-thread generation: a replaced (hung) thread exits when it wakes up
        self._lock = threading.Lock()        # one beat at a time (the thread + the remote control's "status")
        self._beat = None                    # the beat running now: {"t0", "phase", "gen"}
        self._started = False
        self._err_at = 0.0
        self._bars = None                    # engine.pcbars.PCBars, when no_yahoo is on
        self.loop_t = None                   # the push loop's last sign of life
        self.fails = 0                       # failed pushes in a row
        self.last_ok_t = None
        self.last_error = None
        self.last_error_t = None
        self.fail_since = None
        self.restarts = 0
        self.restart = None                  # {"t", "why"}: the watchdog's last restart
        self.frozen = None                   # {"from", "to", "s"}: the last stretch the process was frozen (PC asleep)
        self.frozen_n = 0

    def _say(self, text):
        try:
            self.log(text)
        except Exception:                    # a closed console must never kill the heartbeat
            pass

    def bar_files(self) -> dict:
        """The PC's NinjaTrader bars for the cloud (no_yahoo, engine/pcbars.py); {} when off or unavailable. Never raises."""
        try:
            from . import pcbars
            if not pcbars.no_yahoo(getattr(self.bot, "cfg", None) or None):
                return {}
            cfg = getattr(self.bot, "cfg", None) or {}
            if self._bars is None:
                self._bars = pcbars.PCBars(sym=cfg.get("sym") or "NQ", root=cfg.get("nt_archive") or pcbars.ARCHIVE_DIR)
            return self._bars.files(self.bot)
        except Exception as e:
            if time.time() - self._err_at > 3600:
                self._err_at = time.time()
                self._say(f"[heartbeat] bars not attached: {e.__class__.__name__}: {e}")
            return {}

    def health_block(self) -> dict:
        """health.hb: is the heartbeat itself healthy (~300 bytes, secret-free)."""
        last = self.last or {}
        b = self._beat
        return {"ok": last.get("ok"), "at": last.get("at"), "last_ok_t": self.last_ok_t, "fails": self.fails,
                "fail_since": self.fail_since, "last_error": _redact(str(self.last_error or ""))[:160] or None,
                "last_error_t": self.last_error_t, "retried": (str(last.get("retried"))[:80] if last.get("retried") else None),
                "took_ms": last.get("took_ms"), "thread": bool(self._thread and self._thread.is_alive()),
                "watchdog": bool(self._watch_thread and self._watch_thread.is_alive()), "restarts": self.restarts,
                "restart": self.restart, "frozen": self.frozen, "frozen_n": self.frozen_n,
                "beat_s": int(self.clock() - b["t0"]) if b else None}

    def payload(self) -> dict:
        st = getattr(self.bot, "state", None) or {}
        cfg = getattr(self.bot, "cfg", None) or {}
        health = _health(self.bot)
        if isinstance(health, dict):
            health = {**health, "hb": self.health_block()}     # the heartbeat's own health (last push error, restarts, sleep)
        strat = st.get("strategy") if isinstance(st, dict) else None
        return {"t": int(time.time()), "running": bool(getattr(self.bot, "running", False)), "adapter": cfg.get("adapter", "paper"),
                "position": bool(st.get("position")), "model_state": st.get("model_state"), "host": platform.node(),
                "model": (strat.get("model") if isinstance(strat, dict) else None) or cfg.get("model"),
                "push_pk": _push_pk(),          # phone notifications: the cloud seals the notification key to this (engine/push.py)
                "every_s": int(self.every_s), "acct": _acct(self.bot), "health": health, "ops": _ops(),
                "launch": _launch(self.bot, health),   # the launch checklist (engine/launch_check.py; read-only, ~2 KB)
                "exec": _exec(),                # execution quality summary (engine/fill_audit.py), None before the first audit
                "learn": _learn(),              # live learning (engine/live_learning.py): learned costs + trade reviews, None before
                "money": _money(),              # Road to $10K / Stingray 3LT: the owner's figures (engine/money_goal.py, ~2 KB)
                "remote": _remote(),            # phone remote control (engine/remote_ctl.py): the last command and its result
                "live_pub": _live_pub(),        # the phone's live.json push (engine/live_publish.py): last result, None before it
                "brain": _brain(self.bot),       # the Bot Brain, phone cut (engine/brain.compact; None before the first LIT poll)
                "second": _second(self.bot),     # second strategies, PAPER (engine/second.compact; None when off / before the first)
                "blitz": _blitz(self.bot),       # BLITZ scalper PAPER shadow (engine/blitz.compact; never routed; None before the first)
                "ai": _ai(self.bot),             # AI watch: anomalies, drift, loss caps, rule changes (engine/ai_watch.hb_block)
                "nt_log": _nt_log(self.bot),     # NinjaTrader's Log-tab lines about our orders (engine/nt_log.py; <= ~10 KB)
                **_alerts_plus(self.bot),       # "rules" (PC-vs-cloud fingerprint) + "crit" (critical conditions, engine/alerts_plus.py)
                **_opt("account_c", _account_c(self.bot)),   # BLITZ's own account (engine/account_c.py): only when it is on
                **_opt("fleet", _fleet(self.bot)),           # the follower accounts (engine/fleet.py): only when configured
                **_opt("life", _life(self.bot)),             # MFFU stage per account (engine/lifecycle.py): once one is seen
                **_opt("mind", _mind(self.bot)),             # Mind (engine/mind.py, read-only): only once it has computed
                **_opt("selftest", _selftest()),             # PC self-test (engine/pc_selftest.py): only after its first run
                **_opt("pc_health", _pc_health()),           # PC health watchdog (engine/pc_health.py): once it has sampled
                **_opt("board", _board(self.bot))}           # the Board (engine/board_events.hb_block): public, <= 6 KB

    def beat(self) -> dict:
        """One heartbeat: bars + payload + push, the result kept in self.last / logs/heartbeat_last.json. One at a time (a
        second caller waits up to lock_wait_s, then skips). Never raises."""
        lock = self._lock
        if not lock.acquire(timeout=self.lock_wait_s):
            return {"ok": False, "skipped": "a heartbeat push is already running"}
        me = {"t0": self.clock(), "phase": "bars", "gen": self._gen}
        self._beat = me
        pl = {}
        try:
            try:
                files = self.bar_files()
                me["phase"] = "payload"
                pl = self.payload()
                if files:
                    try:
                        from . import pcbars
                        pl["bars"] = pcbars.PCBars.meta(files, self.bot)
                    except Exception:
                        pass
                me["phase"] = "push"
                res = self.push_fn(pl, files=files)
                if not isinstance(res, dict):
                    res = {"ok": False, "error": f"push returned {type(res).__name__}"}
            except Exception as e:
                res = {"ok": False, "error": f"beat failed: {e.__class__.__name__}: {e}"}
            me["phase"] = "after"
            try:                                    # the Status page's uptime samples (engine/uptime.py, logs/uptime_pc.json)
                from . import uptime
                uptime.pc_hook(pl)
            except Exception:
                pass
            self._note(res)
            save_last(pl, res, self.last_path)
            return res
        finally:
            if self._beat is me:
                self._beat = None
            lock.release()

    def _note(self, res: dict):
        now = self.clock()
        self.last = {"at": int(now), **res}
        if res.get("ok"):
            if self.fails:
                self._say(f"[heartbeat] push works again after {self.fails} failed tries"
                          + (f" (silent since {_hm(self.fail_since)} ET)" if self.fail_since else ""))
            self.fails, self.fail_since, self.last_ok_t = 0, None, int(now)
            return
        if res.get("skipped"):
            return
        self.fails += 1
        self.fail_since = self.fail_since or (self.last_ok_t or int(now))
        self.last_error, self.last_error_t = _redact(str(res.get("error") or "push failed")), int(now)
        if self.push_fn is push and GONE_RE.search(self.last_error):
            try:
                from . import nogithub as _ng
                self.push_fn, self.notify_fn = _ng.local_push, None
                self._say("[heartbeat] GitHub account gone (suspended): the heartbeat is written on this PC from now on "
                          "(logs/pc_hb, GitHub-free mode); phone reports go by ntfy")
                return
            except Exception:
                pass
        if now - self._err_at > 3600:
            self._err_at = now
            self._say(f"[heartbeat] push failed (try {self.fails}, next in {int(self.next_wait())} s): {self.last_error}")
        self._fail_notice(now)

    def _fail_notice(self, now):
        """GitHub refused the PC's login for FAIL_NOTICE_S (an expired token / credential): the cloud and the phone app
        see no heartbeat and say "Surface offline" while the bot trades on. One phone push a day with the one fix.
        A network error is not pushed (the PC could not push the phone either; the cloud's alarm covers it)."""
        try:
            if self.notify_fn is None or not self.fail_since or now - self.fail_since < FAIL_NOTICE_S:
                return
            err = str(self.last_error or "")
            if not AUTH_RE.search(err):
                return
            import datetime as _dt
            from zoneinfo import ZoneInfo
            day = _dt.datetime.fromtimestamp(int(now), ZoneInfo("America/New_York")).date().isoformat()
            if self._fail_notified == day:
                return
            self._fail_notified = day
            self.notify_fn("Surface can't upload to GitHub",
                           f"GitHub refused the Surface's login since {_hm(self.fail_since)} ET ({err[:80]}). The phone app and "
                           "the cloud see no heartbeat; the bot keeps trading. Fix after 16:00 ET: double-click UPDATE.bat in "
                           "the bot folder and sign in to GitHub when Windows asks.", f"hb:auth:{day}")
            self._say(f"[heartbeat] GitHub login refused for {int((now - self.fail_since) // 60)} min: phone notified")
        except Exception:
            pass

    def wait_s(self) -> float:
        """every_s, or FAST_EVERY_S while a LIT setup is armed / a trade is open in a session (the cloud watcher's bars)."""
        try:
            from . import accounts
            from .live import market_open
            if getattr(self.bot, "running", False) and market_open(time.time()) and \
                    accounts._lit_stage(getattr(self.bot, "state", None) or {}).get("stage") in FAST_STAGES:
                return float(min(self.every_s, FAST_EVERY_S))
        except Exception:
            pass
        return float(self.every_s)

    def next_wait(self) -> float:
        """wait_s(), or at most retry_s after a failed push (back within a minute once the network / PC is back)."""
        w = self.wait_s()
        return float(min(w, self.retry_s)) if self.fails else w

    # ---- the push thread
    def _run(self, gen: int | None = None):
        gen = self._gen if gen is None else gen
        while not self._stop.is_set() and gen == self._gen:
            self.loop_t = self.clock()
            try:
                self.beat()
            except Exception as e:                  # beat() never raises; the loop survives even if it did
                self._note({"ok": False, "error": f"beat crashed: {e.__class__.__name__}: {e}"})
            if gen != self._gen or self._stop.is_set():
                return                              # replaced by the watchdog while this beat hung: the new thread goes on
            w = self.next_wait()
            t0 = self.clock()
            self.loop_t = t0
            self._wake.wait(w)
            self._wake.clear()
            t1 = self.clock()
            if t1 - t0 > w + self.frozen_s:          # the wait took far longer than asked: the process was frozen
                self._note_frozen(t0 + w, t1)

    def _spawn(self):
        self._thread = threading.Thread(target=self._run, args=(self._gen,), name=f"heartbeat-{self._gen}", daemon=True)
        self._thread.start()

    # ---- the watchdog
    def _note_frozen(self, a: float, b: float):
        """The whole process stood still from a to b (PC asleep / suspended): record it, shift the hang clocks by it."""
        gap = b - a
        if self.frozen and abs(self.frozen.get("to", 0) - b) < self.watch_s * 2:
            self.frozen["from"] = int(min(self.frozen["from"], a))
            self.frozen["s"] = int(self.frozen["to"] - self.frozen["from"])
            return
        self.frozen = {"from": int(a), "to": int(b), "s": int(gap)}
        self.frozen_n += 1
        bt = self._beat
        if bt:
            bt["t0"] += gap                         # a beat interrupted by the sleep is not a hung beat
        if self.loop_t:
            self.loop_t += gap
        self._say(f"[heartbeat] the PC was asleep or this process frozen for {_dur(gap)} ({_hm(a)} -> {_hm(b)} ET): "
                  "pushing now")

    def check(self, now: float | None = None) -> str | None:
        """Restart the push thread when it has stopped or one beat ran longer than stuck_s. The reason, or None."""
        if self._stop.is_set() or not self._started:
            return None
        now = self.clock() if now is None else now
        b = self._beat
        why = None
        if self._thread is None or not self._thread.is_alive():
            why = "the push thread had stopped"
        elif b and now - b["t0"] > self.stuck_s:
            why = f"one push hung {int(now - b['t0'])} s (in '{b.get('phase')}')"
        elif not b and self.loop_t and now - self.loop_t > self.wait_s() + self.stuck_s:
            why = f"the push loop stood still {int(now - self.loop_t)} s"
        if why:
            self._restart(why, now)
        return why

    def _restart(self, why: str, now: float | None = None):
        self._gen += 1
        self._lock = threading.Lock()               # a hung beat keeps the old lock; the new thread gets its own
        self._beat = None
        self.restarts += 1
        self.restart = {"t": int(self.clock() if now is None else now), "why": why}
        self._say(f"[heartbeat] watchdog: {why}; push thread restarted (restart {self.restarts})")
        self._spawn()

    def watch_tick(self, last: float, now: float) -> float:
        """One watchdog tick (last = the previous tick's time). Returns now. Never raises."""
        try:
            if now - last > self.watch_s + self.frozen_s:
                self._note_frozen(last, now)
                self._wake.set()                    # beat at once: the cloud sees the PC back within a minute
            else:
                self.check(now)
        except Exception:
            pass
        return now

    def _watch(self):
        last = self.clock()
        while not self._stop.is_set():
            self._stop.wait(self.watch_s)
            if self._stop.is_set():
                return
            last = self.watch_tick(last, self.clock())

    def start(self):
        if not enabled():
            self._say("[heartbeat] off (set LE_HEARTBEAT=1 on the always-on PC)")
            return False
        self._started = True
        if self._thread is None or not self._thread.is_alive():
            self._spawn()
        if self._watch_thread is None or not self._watch_thread.is_alive():
            self._watch_thread = threading.Thread(target=self._watch, name="heartbeat-watchdog", daemon=True)
            self._watch_thread.start()
        return True

    def stop(self):
        self._stop.set()
        self._wake.set()

    def status(self) -> dict:
        return {"enabled": enabled(), "every_s": self.every_s, "last": self.last,
                "thread_alive": bool(self._thread and self._thread.is_alive()), "health": self.health_block()}


def selftest() -> bool:
    """Push to a temporary bare repo and read it back (no network)."""
    import shutil
    import tempfile
    d = tempfile.mkdtemp(prefix="le_hb_")
    try:
        bare, work = os.path.join(d, "bare.git"), os.path.join(d, "work")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
        subprocess.run(["git", "init", "-q", work], check=True)
        subprocess.run(["git", "-C", work, "remote", "add", "origin", bare], check=True)
        now = time.time()
        p = push({"t": int(now), "running": True, "adapter": "ninjatrader", "position": False, "every_s": 300}, cwd=work)
        assert p["ok"], p
        hb = read(cwd=work, now=now + 60)
        assert hb["present"] and not hb["silent"] and hb["adapter"] == "ninjatrader", hb
        hb2 = read(cwd=work, now=now + 30 * 60)
        assert hb2["silent"], hb2
        p2 = push({"t": int(now), "running": False, "every_s": 300}, cwd=work)
        assert p2["ok"] and not read(cwd=work, now=now + 30 * 60)["silent"]
        n = subprocess.run(["git", "-C", bare, "rev-list", "--count", BRANCH], capture_output=True, text=True).stdout.strip()
        assert n == "1", f"history grew: {n}"
        raw = bytes(range(256)) + b"\r\n\n"
        p3 = push({"t": int(now), "running": True, "every_s": 300}, cwd=work, files={"bars_1m.csv.gz": raw})
        hb3 = read(cwd=work, now=now + 60, files=("bars_1m.csv.gz", "missing.bin"))
        assert p3["ok"] and hb3["files"]["bars_1m.csv.gz"] == raw and hb3["files"]["missing.bin"] is None, hb3.get("files")
        print("heartbeat selftest OK: push, read, silent after 20 min, stopped bot never silent, no history growth, "
              "binary bar files round-trip byte for byte")
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)
