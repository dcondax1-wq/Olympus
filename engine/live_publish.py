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
   "price", "day_pnl", "last_signal", "model_state", "heartbeat": {"t", "ok"} (the last heartbeat push),
   "money": the Goals card's Road to $10K / Stingray 3LT (engine/money_goal.from_heartbeat, ~7 KB; dropped first if too big),
   "pc_health": the PC's CPU / RAM / disk / NinjaTrader lines for Jarvis's System view (pc_health_summary; absent before
                the PC's first health sample),
   "blitz": BLITZ on account C in the board's lit / atlas card shape (blitz_block; an "off" card while account C is off,
            null when it cannot be built; board.blitz itself stays present only while account C is on)}
Next to it in the same commit: liveview.json (< 240 KB), the phone's Live View (engine/liveview_api.phone_view: the
chart's 1m / 5m bars, the Zlarior / ATLAS / BLITZ layers, what each bot is thinking, the feed; tools/web_public/liveview.js),
holo.json (< 300 KB, the Holodeck's today: exact fills, trades, orders, thoughts; engine/holo_api.phone) and holo_hist.json
(< 400 KB, the last 10 trading days' trades; engine/holo_api.hist, cached 10 min).

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
    try:
        from . import nogithub
        if nogithub.active(env):         # GitHub-free mode (engine/nogithub.py)
            return False
    except Exception:
        pass
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
                                 "brain", "second", "ai", "launch", "mind", "learn")}   # brain: the Bot Brain's phone cut (< 16 KB); second: paper EMA / MACD; mind: engine/mind.compact (< 12 KB); learn: live learning's fill reviews (< 3 KB, Jarvis's "what did the bots learn")
    pc.update(present=True, t=now, age_s=0, silent=False, every_s=int(every_s), live=True)
    if isinstance(hb.get("account_c"), dict):           # BLITZ on its own account (engine/account_c.py): only when it is on
        pc["account_c"] = hb["account_c"]
    if isinstance(hb.get("fleet"), dict):               # the follower accounts (engine/fleet.py): only when configured
        pc["fleet"] = hb["fleet"]
    if isinstance(pc.get("health"), dict) and isinstance(pc["health"].get("poll"), dict) and "stages" in pc["health"]["poll"]:
        # the poll's stage table (engine/poll_timing.py) stays in the heartbeat: the phone shows only the poll time
        pc["health"] = {**pc["health"], "poll": {k: v for k, v in pc["health"]["poll"].items() if k != "stages"}}
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
    try:                                # the Brain page's per-bot glance (engine/brain_glance.py, < 1.7 KB; never BLITZ)
        from . import brain_glance
        bd0 = out.get("board") if isinstance(out.get("board"), dict) and "error" not in out["board"] else None
        g = brain_glance.build(hb, bd0, now=now)
        if g and not g.get("error"):
            pc["glance"] = g
    except Exception:
        pass
    bz = blitz_block(hb, now, out.get("board"))       # BLITZ on account C, same keys as board.lit / board.atlas (None on failure)
    if bz is not None and not bz.get("off") and isinstance(out.get("board"), dict) and "error" not in out["board"] \
            and not isinstance(out["board"].get("blitz"), dict):
        out["board"]["blitz"] = bz                        # board.blitz keeps its contract: present only while account C is on
    out["blitz"] = bz                                     # live.json "blitz": always there (an "off" card while account C is off)
    try:                                # Road to $10K / Stingray 3LT (engine/money_goal.py): the Goals card, fresher than data.json
        from . import money_goal
        out["money"] = money_goal.from_heartbeat(hb, now=now, accounts=out.get("accounts"))
    except Exception as e:
        out["money"] = {"error": f"{e.__class__.__name__}: {str(e)[:120]}"}
    ph = pc_health_summary(hb.get("pc_health"), now)     # CPU / RAM / disk / NinjaTrader lines for Jarvis's System view
    if ph is not None:
        out["pc_health"] = ph
    kr = kalshi_rewards_card(now)                        # the Kalshi page's "Rewards test (paper)" card (< 1 KB; absent when not running)
    if kr is not None:
        out["kalshi_rewards"] = kr
    out = scrub(out, _phrases())
    try:                                # hidden bots (engine/hidden_bots.py, dashboard_view.json; default ["blitz"]): off the phone
        from . import hidden_bots
        out = hidden_bots.publish(out)
    except Exception:
        pass
    return fit(out)


KALSHI_REWARDS_PUB = os.path.join(ROOT, "data", "kalshi_rewards", "summary.json")
KALSHI_REWARDS_KEYS = ("v", "kind", "paper_only", "started", "updated", "days", "reward", "fill_pnl", "net", "fills", "markets",
                       "capital", "per100_day", "series")


def kalshi_rewards_card(now=None, path: str | None = None) -> dict | None:
    """The Kalshi rewards PAPER test's public summary (tools/kalshi_rewards_paper.py public_summary, written by its PC child into
    data/kalshi_rewards/summary.json): only its known keys, only when it is under 2 days old. None otherwise. Never raises."""
    try:
        with open(path or KALSHI_REWARDS_PUB, encoding="utf-8") as fh:
            d = json.load(fh)
        if not isinstance(d, dict) or d.get("kind") != "kalshi_rewards_pub" or d.get("paper_only") is not True:
            return None
        if int(now or time.time()) - os.path.getmtime(path or KALSHI_REWARDS_PUB) > 2 * 86400:
            return None
        out = {k: d.get(k) for k in KALSHI_REWARDS_KEYS if k in d}
        if isinstance(out.get("series"), dict):
            out["series"] = {str(k)[:24]: {"reward": (v or {}).get("reward"), "fill_pnl": (v or {}).get("fill_pnl")}
                             for k, v in list(out["series"].items())[:8] if isinstance(v, dict)}
        return out if len(json.dumps(out)) < 1500 else None
    except Exception:
        return None


PC_HEALTH_LEVEL = {"green": "ok", "amber": "warn", "red": "bad"}
PC_HEALTH_LABELS = {"cpu": "CPU", "ram": "Memory (RAM)", "disk": "Disk space", "nt": "NinjaTrader", "bot_mem": "Bot memory",
                    "onedrive": "OneDrive sync", "clock": "PC clock", "poll": "Bot poll time", "storage": "Storage", "pc_care": "PC care"}


def pc_health_summary(block, now=None) -> dict | None:
    """Jarvis's System view of the PC (owner 2026-11-02: "everything combined and simple"): the heartbeat's "pc_health" block
    (engine/pc_health.hb_block: CPU / RAM / disk / NinjaTrader / bot memory / OneDrive / clock / poll, green / amber / red)
    cut to what the phone shows: {"t", "age_s", "level" ok|warn|bad, "cpu", "ram" (percent or None), "lines": [{"key",
    "label", "level", "text"}] (at most 8, text <= 140 chars)}. Only what the heartbeat already carries (no new sampling;
    scrub() runs over it too). None when there is no block (the key is then left out). Never raises."""
    try:
        if not isinstance(block, dict) or not isinstance(block.get("lines"), list):
            return None
        now = int(now or time.time())
        lines, nums = [], {}
        src = [x for x in block["lines"] if isinstance(x, dict)]
        if any(x.get("key") == "storage" for x in src):          # 2026-11-04: Storage (free GB + folder sizes + the fix) replaces the plain Disk line
            src = [x for x in src if x.get("key") != "disk"]
        src.sort(key=lambda x: 0 if (x.get("key") == "pc_care" and x.get("level") != "green") else 1)   # PC care shows first when it found something
        for ln in src[:8]:
            if not ln.get("key"):
                continue
            key, txt = str(ln["key"])[:20], str(ln.get("text") or "")[:140]
            lines.append({"key": key, "label": PC_HEALTH_LABELS.get(key, key), "level": PC_HEALTH_LEVEL.get(ln.get("level"), "off"),
                          "text": txt})
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", txt) if key in ("cpu", "ram") else None
            if m:
                nums[key] = round(float(m.group(1)))
        try:
            t = int(float(block.get("t")))
        except (TypeError, ValueError):
            t = None
        lv = "bad" if any(x["level"] == "bad" for x in lines) else "warn" if any(x["level"] == "warn" for x in lines) else "ok"
        return {"t": t, "age_s": max(0, now - t) if t else None, "level": lv, "cpu": nums.get("cpu"), "ram": nums.get("ram"),
                "lines": lines}
    except Exception:
        return None


BLITZ_KEYS = ("id", "name", "plan", "method", "broker", "badge", "source", "configured", "stage", "status", "balance", "floor", "room",
              "room_frac", "mll", "to_target", "target_balance", "profit", "today_pnl", "week_pnl", "dll", "session", "sessions",
              "trades_today", "max_day", "max_micros", "waiting", "window", "micros", "position", "blocks", "paused")


def blitz_block(hb_payload: dict | None, now=None, board: dict | None = None) -> dict | None:
    """BLITZ on its own account (account C) for the phone: the keys the board's lit / atlas cards carry (plan, badge,
    status, today_pnl, week_pnl, room, to_target, floor, ...). Read-only, built only from what the PC bot already put in
    its heartbeat payload (the "account_c" block, engine/account_c.AccountC.hb_block, or the board's own BLITZ card when
    it has one): no file, no network, nothing on the trading path (the publisher's own thread). Account C off (no
    "account_c") -> an "off" card (off=True, status "off"). Any failure -> None, never an exception."""
    try:
        import datetime as _dt
        now = int(now or time.time())
        bd = board if isinstance(board, dict) else {}
        card = bd.get("blitz") if isinstance(bd.get("blitz"), dict) and not bd["blitz"].get("error") else None
        c = (hb_payload or {}).get("account_c")
        if card is None and isinstance(c, dict) and c and not c.get("error"):
            from . import live_board
            card = live_board.blitz_now({"account_c": c}, now)
        if card is not None:
            out = {k: card.get(k) for k in BLITZ_KEYS}
            days = c.get("days") if isinstance(c, dict) else None           # account C's {day: closed $} (AccountC.days)
            if isinstance(days, list):
                days = {str(d[0]): d[1] for d in days if isinstance(d, (list, tuple)) and len(d) >= 2}
            if out.get("week_pnl") is None and isinstance(days, dict):       # this week's booked days (Mon .. today, ET)
                from . import live_board
                d0 = _dt.date.fromisoformat(live_board.trading_day(now))
                mon = (d0 - _dt.timedelta(days=d0.weekday())).isoformat()
                wk = [float(v) for d, v in days.items() if str(d) >= mon and v is not None]
                out["week_pnl"] = round(sum(wk), 2) if wk else None
            out["off"] = False
            return out
        err = c.get("error") if isinstance(c, dict) else None
        return {"id": "blitz", "name": "BLITZ", "plan": "MFFU Builder 25K", "method": "noise-area 1m scalp", "badge": "OFF",
                "source": "none", "configured": False, "off": True, "stage": "eval", "status": "error" if err else "off",
                "balance": None, "floor": None, "room": None, "room_frac": None, "mll": 1000.0, "to_target": None,
                "target_balance": 26500.0, "profit": None, "today_pnl": None, "week_pnl": None, "dll": 600.0, "session": None,
                "sessions": None, "trades_today": 0, "max_day": 6, "max_micros": 20, "micros": None, "position": None, "blocks": [],
                "paused": None,
                "waiting": (f"Account C could not report: {str(err)[:120]}" if err else
                            "Account C is off on the PC: BLITZ trades paper only until its own 25K is set up "
                            "(python -X utf8 -m engine.account_c, or the Start page).")}
    except Exception:
        return None


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
    for k in ("mind", "learn", "fleet", "ai", "second", "ops", "remote", "brain"):     # mind first: liveview.json carries it too; fleet: the PC page has it
        if size() > max_bytes and isinstance(p.get("pc"), dict):
            p["pc"].pop(k, None)
            p["trimmed"] = True
    if "pc_health" in p and size() > max_bytes:                             # Jarvis's PC lines (~1 KB)
        p.pop("pc_health", None)
        p["trimmed"] = True
    if "money" in p and size() > max_bytes:                               # the Goals money card (data.json keeps one)
        p.pop("money", None)
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


_EXTRA_NAME = re.compile(r"^[a-z0-9_-]+\.json$")


def push(payload: dict, url: str, branch: str = BRANCH, git_dir: str = SCRATCH, cwd: str = ROOT, prune: bool = False,
         extra: dict | None = None, file: str = FILE) -> dict:
    """Write payload as live.json (or `file`; plus extra = {"name.json": payload}, e.g. liveview.json) in one orphan commit
    and force-push it to url/branch (replaces the branch: no history). Returns {"ok", "error"|"commit", "bytes",
    "extra_bytes"}. Never raises."""
    try:
        if not url:
            return {"ok": False, "error": "no target repo (origin is not on GitHub; set LE_LIVE_REPO)"}
        err = _scratch(git_dir, cwd)
        if err:
            return {"ok": False, "error": err}
        files = {file: payload}
        for name, pl in (extra or {}).items():
            if name != file and pl is not None and _EXTRA_NAME.match(str(name)):
                files[name] = pl
        entries, sizes = [], {}
        for name in sorted(files):
            body = json.dumps(files[name], separators=(",", ":"), default=str).encode("utf-8")
            r = _git(["hash-object", "-w", "--stdin"], git_dir=git_dir, inp=body)
            blob = _out(r)
            if r.returncode or len(blob) < 40:
                return {"ok": False, "error": "hash-object failed" + ("" if name == file else f" ({name})")}
            entries.append(f"100644 blob {blob}\t{name}\n")
            sizes[name] = len(body)
        r = _git(["mktree"], git_dir=git_dir, inp="".join(entries).encode())
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
        from .heartbeat import _NET_CFG, run_cmd      # (2026-11-03) a hung git-remote-https can never block this thread
        r = run_cmd(["git", *_NET_CFG, "--git-dir", git_dir, "push", "-q", "--force", url, f"{commit}:refs/heads/{branch}"],
                    timeout=90, env={**env, "GCM_INTERACTIVE": "never"})
        if r.returncode:
            return {"ok": False, "error": _redact((r.stderr or b"").decode(errors="replace").strip()[-200:]) or "push failed"}
        if prune:                                    # the old live commits are unreachable: drop them (only this scratch dir)
            _git(["update-ref", "refs/heads/last", commit], git_dir=git_dir, timeout=20)
            _git(["prune", "--expire=now"], git_dir=git_dir, timeout=120)
        return {"ok": True, "commit": commit[:10], "bytes": sizes[file],
                "extra_bytes": {k: v for k, v in sizes.items() if k != file}}
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
        self.extra_ms: dict = {}          # ms each extra file took to build (liveview / holo / holo_hist), last publish
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

    def extra(self) -> dict:
        """The other files of the live commit: liveview.json, the phone's Live View (engine/liveview_api.phone_view:
        the chart, the three strategy layers, what each bot is thinking, the feed), and the Holodeck's holo.json (today:
        exact fills, trades, orders, thoughts, levels; engine/holo_api.phone, reusing this minute's Live View answer) +
        holo_hist.json (the last 10 trading days' trades, cached: rebuilt at most every 10 min or when a trade closes).
        Built here, on the publisher's own thread (never the trading loop); self.extra_ms keeps what each one took.
        A file that cannot be built is left out."""
        out, ms, lv = {}, {}, None
        now = int(self.clock())
        try:
            from . import liveview_api
            t0 = time.perf_counter()
            lv = liveview_api.phone_view(self.bot, now)
            out[liveview_api.PHONE_FILE] = scrub(lv, _phrases())
            ms["liveview"] = int((time.perf_counter() - t0) * 1000)
        except Exception:
            pass
        try:
            from . import holo_api
            t0 = time.perf_counter()
            out[holo_api.PHONE_FILE] = scrub(holo_api.phone(self.bot, now, lv=lv), _phrases())
            ms["holo"] = int((time.perf_counter() - t0) * 1000)
            t0 = time.perf_counter()
            out[holo_api.HIST_FILE] = scrub(holo_api.hist(self.bot, now), _phrases())
            ms["holo_hist"] = int((time.perf_counter() - t0) * 1000)
        except Exception:
            pass
        self.extra_ms = ms
        try:                            # hidden bots (engine/hidden_bots.py): off the Live View / Holodeck files too
            from . import hidden_bots
            hide = hidden_bots.hidden()
            out = {k: hidden_bots.publish(v, hide) for k, v in out.items()}
        except Exception:
            pass
        return out

    def publish(self, force: bool = False) -> dict:
        """One push (rate-limited: never within MIN_GAP_S of the last attempt unless force). Never raises."""
        now = self.clock()
        if not force and now - self.last_push_t < MIN_GAP_S:
            return {"ok": False, "skipped": "rate limit", "next_in_s": int(MIN_GAP_S - (now - self.last_push_t))}
        self.last_push_t = now
        try:
            pl = self.payload()
            res = self.push_fn(pl, self.url, git_dir=self.git_dir, prune=(self.pushes % PRUNE_EVERY == PRUNE_EVERY - 1),
                               extra=self.extra())
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
                "every_s": self.every_s(), "last": self.last, "fails": self.fails, "extra_ms": dict(self.extra_ms),
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
