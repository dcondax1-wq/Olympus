"""Live data for the phone app, straight from the PC, every minute, free (owner 2026-10-21: "everything needs to refresh
and pull all the time").

Why this route. The phone app (https://demetrades2000-coder.github.io/nq-dashboard/) is a static GitHub Pages site in the
PUBLIC repo demetrades2000-coder/nq-dashboard, branch main, force-pushed by the cloud monitor
(.github/workflows/cloud-monitor.yml "Publish web dashboard", deploy key DASH_DEPLOY_KEY). The cloud runs only every ~30 min
in 01:30-16:40 ET (Actions minutes are nearly used up), so data.json is up to ~30 min old and nothing moves overnight.
  * Pushing to main every minute would start a Pages build every minute (soft limit 10 an hour) and the cloud's next force
    push would wipe the file: no.
  * The heartbeat branch lives in THIS (private) repo: the phone cannot read it without a token: no.
  * So the PC force-pushes ONE small file, live.json, as a single orphan commit to the branch `live` of the PUBLIC Pages repo
    (no Pages build: Pages serves main only; no history growth: every push replaces the commit, like the heartbeat). The
    phone reads it from GitHub's API (api.github.com .../contents/live.json?ref=live: CORS, fresh within ~60 s), and falls back
    to raw.githubusercontent.com when the API's 60-an-hour limit for its network runs out (tools/web_public/live.js).
  * Credentials: the PC's own git login (Git Credential Manager, the same one the heartbeat and the remote control use;
    the owner owns both repos). The push runs in a private scratch git dir (data/live_pub.git, gitignored) so the
    minute-by-minute objects never pile up in the project's .git (pruned every PRUNE_EVERY pushes).

What live.json holds (the phone app's Home essentials; secret-free, < 64 KB; the same shapes data.json uses, so the app just
lays it over data.json):
  {"v", "kind": "le-live", "t": unix seconds (the PC's check-in time), "every_s", "host",
   "pc": the heartbeat payload's view (running, adapter, position, model_state, model, health: verdict inputs, feed ages,
         NinjaTrader, auto-update / auto-resume, LIT stage + last setup; ops, remote) with present / age_s 0 / silent false,
   "pc_verdict": engine/accounts.verdict on it (TRADING YOUR EVAL / ON SIM / DISABLED / FEED STALE ...),
   "accounts": the PC accounts as engine/accounts.build_accounts makes them (eval $ to go / room / session, today's P&L,
               the open position with its stop / target, today's orders, the last trades),
   "price", "day_pnl", "last_signal", "model_state", "heartbeat": {"t", "ok"} (the last heartbeat push)}

Cadence: every FAST_S (60 s) while the bot runs, every SLOW_S (300 s) otherwise; never more often than MIN_GAP_S; after a
failed push it backs off (2, 4, 8 ... up to 30 min) and logs at most once an hour. A daemon thread: it never touches the
trading loop and never raises. On with the heartbeat (LE_HEARTBEAT=1, set by scripts/run_bot.ps1); LE_LIVE_PUBLISH=0 turns
it off, LE_LIVE_PUBLISH=1 forces it on. LE_LIVE_REPO overrides the target (a git URL), LE_LIVE_BRANCH the branch.

  python -m engine.live_publish --status      what it would publish and where (no push)
  python -m engine.live_publish --once        one push now (the owner's check that the PC may push to the Pages repo)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_REPO = "nq-dashboard"
BRANCH = "live"
FILE = "live.json"
SCRATCH = os.path.join(ROOT, "data", "live_pub.git")       # gitignored scratch git dir (objects pruned)
FAST_S = 60.0
SLOW_S = 300.0
MIN_GAP_S = 45.0
MAX_BACKOFF_S = 30 * 60.0
MAX_BYTES = 64 * 1024
PRUNE_EVERY = 30
KIND = "le-live"
_SECRET_KEY = re.compile(r"(password|passwd|^pass$|secret|token|webhook|api_?key|confirm|phrase|private|vapid|endpoint|^auth|cookie|"
                         r"push_pk|^subs$|credential)", re.I)
_PATHLIKE = re.compile(r"([A-Za-z]:\\[^\s\"']+|/(?:home|Users|root)/[^\s\"']+)")


def enabled(env=None) -> bool:
    env = os.environ if env is None else env
    v = env.get("LE_LIVE_PUBLISH")
    if v == "0":
        return False
    return v == "1" or env.get("LE_HEARTBEAT", "0") == "1"


def _git(args, cwd=None, git_dir=None, timeout=60, inp=None):
    cmd = ["git"] + (["--git-dir", git_dir] if git_dir else []) + list(args)
    return subprocess.run(cmd, cwd=cwd, input=inp, capture_output=True, timeout=timeout)


def _out(r) -> str:
    return (r.stdout or b"").decode(errors="replace").strip()


def target_url(cwd: str = ROOT, env=None) -> str | None:
    """The Pages repo's git URL, made from this repo's origin (same owner, same protocol, repo nq-dashboard).
    LE_LIVE_REPO overrides it. None when there is no GitHub origin."""
    env = os.environ if env is None else env
    if env.get("LE_LIVE_REPO"):
        return env["LE_LIVE_REPO"]
    try:
        u = _out(_git(["config", "--get", "remote.origin.url"], cwd=cwd, timeout=20))   # as written (git applies insteadOf itself)
    except Exception:
        return None
    m = re.match(r"^(https://(?:[^@/]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)([^/]+)/[^/]+?(?:\.git)?/?$", u)
    if not m:
        return None
    return f"{m.group(1)}{m.group(2)}/{PAGES_REPO}.git"


def owner_of(url: str | None) -> str | None:
    m = re.search(r"github\.com[:/]([^/]+)/", url or "")
    return m.group(1) if m else None


def phone_urls(url: str | None, branch: str = BRANCH) -> dict:
    """Where the phone reads it (tools/web_public/live.js builds the same two URLs from its own address)."""
    o = owner_of(url) or "demetrades2000-coder"
    return {"api": f"https://api.github.com/repos/{o}/{PAGES_REPO}/contents/{FILE}?ref={branch}",
            "raw": f"https://raw.githubusercontent.com/{o}/{PAGES_REPO}/{branch}/{FILE}"}


def _redact(s: str) -> str:
    return re.sub(r"https://[^@\s/]+@", "https://", _PATHLIKE.sub("<path>", s or ""))


# ---------------------------------------------------------------------------------------------------------------- payload
def scrub(obj, phrases=()):
    """Copy without credential-like keys, without any string holding a confirm phrase, local paths redacted."""
    if isinstance(obj, dict):
        return {k: scrub(v, phrases) for k, v in obj.items() if not _SECRET_KEY.search(str(k))}
    if isinstance(obj, (list, tuple)):
        return [scrub(v, phrases) for v in obj]
    if isinstance(obj, str):
        if any(p and p in obj for p in phrases):
            return "<redacted>"
        return _PATHLIKE.sub("<path>", obj)
    return obj


def _phrases():
    try:
        from .tradovate import LIVE_PHRASE
        return (LIVE_PHRASE,)
    except Exception:
        return ()


def _lm() -> dict:
    try:
        with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def build(hb_payload: dict, now=None, lm: dict | None = None, hb_last: dict | None = None, every_s: float = FAST_S) -> dict:
    """live.json from a heartbeat payload (engine/heartbeat.Heartbeat.payload). Never raises (a broken part is left out)."""
    now = int(now or time.time())
    hb = dict(hb_payload or {})
    pc = {k: hb.get(k) for k in ("running", "adapter", "position", "model_state", "host", "model", "health", "ops", "remote", "acct",
                                 "brain", "second", "ai", "launch")}   # brain: the Bot Brain's phone cut (< 16 KB); second: paper EMA / MACD
    pc.update(present=True, t=now, age_s=0, silent=False, every_s=int(every_s), live=True)
    out = {"v": 1, "kind": KIND, "t": now, "every_s": int(every_s), "host": hb.get("host"), "model_state": hb.get("model_state")}
    try:
        from . import accounts
        out["pc_verdict"] = accounts.verdict(pc, now)
        secs = accounts.build_accounts({"pc": pc, "last_run": now}, lm if lm is not None else _lm(), now)
        out["accounts"] = [a for a in secs if isinstance(a, dict) and a.get("source") != "cloud"]
        for a in out["accounts"]:
            a["trades"] = list(a.get("trades") or [])[-25:]
            a["days"] = list(a.get("days") or [])[-60:]
    except Exception as e:
        out["error"] = f"{e.__class__.__name__}: {str(e)[:120]}"
    acct = pc.pop("acct", None) or {}
    h = pc.get("health") if isinstance(pc.get("health"), dict) else {}
    out["price"] = (h.get("lit") or {}).get("price")
    out["last_signal"] = (h.get("lit") or {}).get("last_setup")
    out["day_pnl"] = acct.get("day_pnl") if isinstance(acct, dict) else None
    out["pc"] = pc
    if hb_last:
        out["heartbeat"] = {"t": hb_last.get("at"), "ok": bool(hb_last.get("ok"))}
    try:                                # the live board (engine/live_board.py): right now, map, health, progress, last trades
        from . import live_board
        bd = live_board.from_heartbeat({**hb, "live_pub": hb.get("live_pub")}, now=now, lm=lm, where="live", n_trades=12)
        if hb_last and hb_last.get("at"):
            hl = next((x for x in (bd.get("health") or {}).get("items") or [] if x.get("key") == "heartbeat"), None)
            if hl is not None:              # the last real heartbeat push, not this live.json's own time
                hl.update(t=int(hb_last["at"]), ok=bool(hb_last.get("ok")) and now - int(hb_last["at"]) < live_board.HB_STALE_S,
                          value=live_board.age_text(now - int(hb_last["at"])))
        out["board"] = bd
    except Exception as e:
        out["board"] = {"error": f"{e.__class__.__name__}: {str(e)[:120]}"}
    out = scrub(out, _phrases())
    return fit(out)


def fit(p: dict, max_bytes: int = MAX_BYTES) -> dict:
    """Trim trades, then orders, then days, then the ops / remote blocks until the JSON fits."""
    def size():
        return len(json.dumps(p, separators=(",", ":"), default=str))
    for key, keep in (("trades", 5), ("orders", 5), ("days", 15)):
        while size() > max_bytes and any(len(a.get(key) or []) > keep for a in p.get("accounts") or []):
            for a in p.get("accounts") or []:
                if len(a.get(key) or []) > keep:
                    a[key] = a[key][len(a[key]) // 2:]
            p["trimmed"] = True
    br = (p.get("pc") or {}).get("brain") if isinstance(p.get("pc"), dict) else None
    if isinstance(br, dict):                 # the Bot Brain: its log, then its levels, then the whole block
        for key, keep in (("log", 8), ("levels", 6)):
            while size() > max_bytes and len(br.get(key) or []) > keep:
                br[key] = br[key][:max(keep, len(br[key]) // 2)]
                p["trimmed"] = True
    bd = p.get("board") if isinstance(p.get("board"), dict) else None
    if bd and size() > max_bytes and len(bd.get("trades") or []) > 4:     # the live board: its trade list first
        bd["trades"] = bd["trades"][:4]
        p["trimmed"] = True
    for k in ("ai", "second", "ops", "remote", "brain"):
        if size() > max_bytes and isinstance(p.get("pc"), dict):
            p["pc"].pop(k, None)
            p["trimmed"] = True
    if bd and size() > max_bytes:                                           # last resort: no board (data.json keeps one)
        p.pop("board", None)
        p["trimmed"] = True
    return p


# ---------------------------------------------------------------------------------------------------------------- push
def _scratch(git_dir: str, cwd: str = ROOT) -> str | None:
    """Create the scratch bare repo once and copy this repo's local credential / ssh settings into it. Error text or None."""
    try:
        if not os.path.isdir(os.path.join(git_dir, "objects")):
            os.makedirs(os.path.dirname(git_dir), exist_ok=True)
            r = subprocess.run(["git", "init", "-q", "--bare", git_dir], capture_output=True, timeout=60)
            if r.returncode:
                return "git init failed"
            r = _git(["config", "--local", "--get-regexp", r"^(credential\..*|core\.sshcommand|http\..*proxy)$"], cwd=cwd, timeout=20)
            for ln in _out(r).splitlines():
                k, _, v = ln.partition(" ")
                if k and v:
                    _git(["config", "--add", k, v], git_dir=git_dir, timeout=20)
        return None
    except Exception as e:
        return f"{e.__class__.__name__}: {e}"


def push(payload: dict, url: str, branch: str = BRANCH, git_dir: str = SCRATCH, cwd: str = ROOT, prune: bool = False) -> dict:
    """Write payload as live.json in one orphan commit and force-push it to url/branch (replaces the branch: no history).
    Returns {"ok", "error"|"commit", "bytes"}. Never raises."""
    try:
        if not url:
            return {"ok": False, "error": "no target repo (origin is not on GitHub; set LE_LIVE_REPO)"}
        err = _scratch(git_dir, cwd)
        if err:
            return {"ok": False, "error": err}
        body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
        r = _git(["hash-object", "-w", "--stdin"], git_dir=git_dir, inp=body)
        blob = _out(r)
        if r.returncode or len(blob) < 40:
            return {"ok": False, "error": "hash-object failed"}
        r = _git(["mktree"], git_dir=git_dir, inp=f"100644 blob {blob}\t{FILE}\n".encode())
        tree = _out(r)
        if r.returncode or not tree:
            return {"ok": False, "error": "mktree failed"}
        env = {**os.environ, "GIT_AUTHOR_NAME": "liquidity-engine-pc", "GIT_AUTHOR_EMAIL": "pc@liquidity-engine.local",
               "GIT_COMMITTER_NAME": "liquidity-engine-pc", "GIT_COMMITTER_EMAIL": "pc@liquidity-engine.local",
               "GIT_TERMINAL_PROMPT": "0"}
        r = subprocess.run(["git", "--git-dir", git_dir, "commit-tree", tree, "-m", f"live {payload.get('t')}"],
                           capture_output=True, timeout=60, env=env)
        commit = _out(r)
        if r.returncode or not commit:
            return {"ok": False, "error": "commit-tree failed"}
        r = subprocess.run(["git", "--git-dir", git_dir, "push", "-q", "--force", url, f"{commit}:refs/heads/{branch}"],
                           capture_output=True, timeout=90, env=env)
        if r.returncode:
            return {"ok": False, "error": _redact((r.stderr or b"").decode(errors="replace").strip()[-200:]) or "push failed"}
        if prune:                                    # the old live commits are unreachable: drop them (only this scratch dir)
            _git(["update-ref", "refs/heads/last", commit], git_dir=git_dir, timeout=20)
            _git(["prune", "--expire=now"], git_dir=git_dir, timeout=120)
        return {"ok": True, "commit": commit[:10], "bytes": len(body)}
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


# ---------------------------------------------------------------------------------------------------------------- thread
LAST: dict = {}          # the last push result, for the heartbeat's "live_pub" field (engine/heartbeat.py)


def hb_field(last: dict | None = None, fails: int = 0) -> dict | None:
    """{"at", "ok", "error" (short, redacted), "fails"}: the phone's health card shows a failing live feed with its reason."""
    last = LAST if last is None else last
    if not last:
        return None
    return {"at": last.get("at"), "ok": bool(last.get("ok")), "fails": int(last.get("fails", fails) or 0),
            "error": _redact(str(last.get("error") or ""))[:120] or None}


class Publisher:
    """Daemon thread on the PC server: builds live.json from the heartbeat payload and pushes it every minute."""

    def __init__(self, bot, heartbeat=None, log=print, clock=time.time, push_fn=None, url=None, git_dir: str = SCRATCH):
        self.bot, self.hb, self.log, self.clock = bot, heartbeat, log, clock
        self.push_fn = push_fn or push
        self._url = url
        self.git_dir = git_dir
        self.last: dict = {}
        self.last_push_t = 0.0
        self.fails = 0
        self.pushes = 0
        self._err_at = 0.0
        self._stop = threading.Event()
        self._thread = None

    @property
    def url(self):
        if self._url is None:
            self._url = target_url() or ""
        return self._url

    def every_s(self) -> float:
        return FAST_S if getattr(self.bot, "running", False) else SLOW_S

    def next_wait(self) -> float:
        """Seconds to the next try: the cadence, or the failure backoff."""
        if self.fails:
            return min(MAX_BACKOFF_S, 60.0 * (2 ** min(self.fails, 6)))
        return self.every_s()

    def payload(self) -> dict:
        hbp = {}
        try:
            if self.hb is not None:
                hbp = self.hb.payload()
        except Exception:
            hbp = {}
        return build(hbp, self.clock(), hb_last=getattr(self.hb, "last", None), every_s=self.every_s())

    def publish(self, force: bool = False) -> dict:
        """One push (rate-limited: never within MIN_GAP_S of the last attempt unless force). Never raises."""
        now = self.clock()
        if not force and now - self.last_push_t < MIN_GAP_S:
            return {"ok": False, "skipped": "rate limit", "next_in_s": int(MIN_GAP_S - (now - self.last_push_t))}
        self.last_push_t = now
        try:
            pl = self.payload()
            res = self.push_fn(pl, self.url, git_dir=self.git_dir, prune=(self.pushes % PRUNE_EVERY == PRUNE_EVERY - 1))
        except Exception as e:
            res = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
        self.last = {"at": int(now), **res}
        LAST.clear()
        LAST.update(hb_field(self.last, self.fails + (0 if res.get("ok") else 1)))
        if res.get("ok"):
            self.pushes += 1
            if self.fails:
                self.log(f"[live] push works again ({res.get('bytes')} bytes)")
            self.fails = 0
        else:
            self.fails += 1
            if now - self._err_at > 3600:
                self._err_at = now
                self.log(f"[live] phone live.json push failed (retry in {int(self.next_wait())} s): {res.get('error')}")
        return res

    def _run(self):
        while not self._stop.is_set():
            try:
                self.publish()
            except Exception:
                pass
            self._stop.wait(self.next_wait())

    def start(self):
        if not enabled():
            self.log("[live] phone live.json off (on with LE_HEARTBEAT=1 or LE_LIVE_PUBLISH=1)")
            return False
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="live-publish", daemon=True)
            self._thread.start()
        return True

    def stop(self):
        self._stop.set()

    def status(self) -> dict:
        return {"enabled": enabled(), "target": _redact(self.url or ""), "branch": BRANCH, "phone": phone_urls(self.url),
                "every_s": self.every_s(), "last": self.last, "fails": self.fails,
                "thread_alive": bool(self._thread and self._thread.is_alive())}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.live_publish")
    ap.add_argument("--once", action="store_true", help="push live.json once now (no bot: stopped-bot view)")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args(argv)
    from types import SimpleNamespace
    bot = SimpleNamespace(running=False, cfg={}, state={})
    from .heartbeat import Heartbeat
    pub = Publisher(bot, Heartbeat(bot))
    if a.once:
        r = pub.publish(force=True)
        print("live.json push:", "OK" if r.get("ok") else "FAILED", r.get("error") or f"{r.get('bytes')} bytes")
        print("phone reads:", phone_urls(pub.url)["api"])
        return 0 if r.get("ok") else 1
    print(json.dumps({**pub.status(), "bytes": len(json.dumps(pub.payload()))}, indent=1))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
