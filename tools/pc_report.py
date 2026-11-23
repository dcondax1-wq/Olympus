"""PC report: the bots' reporting to the phone without GitHub (owner 2026-11-12, "we need to get these bots running again").
Runs ON THE MAIN PC every 15 minutes (Task Scheduler task "OlympusPCReport", installed by BOTS_BACK.bat), stdlib only on top of
the repo's own engine code (read-only use: engine/live_publish.build, engine/go.market_open). Free: ntfy.sh, no account.

  1. read     the bot's own last heartbeat on this PC (logs/pc_hb/heartbeat.json in GitHub-free mode, else the copy the bot keeps
              in logs/heartbeat_last.json), whether the bot server answers (http://127.0.0.1:8766), NinjaTrader and the bar feed.
  2. status   the live.json the phone already reads (engine/live_publish.build: kind "le-live", pc, pc_verdict, board.lit /
              atlas / blitz, accounts), cut to a LITE copy under 4 KB, posted to the public ntfy status topic of
              tools/web_public/status_feed.json (the site reads it with tools/web_public/pc_feed.js). Split (2026-11-18): the core
              (kind "le-live": heartbeat t, verdict, cards, accounts) every run; the extras (brd, life, mf, pc.glance,
              kalshi_rewards, ...) in up to 2 "le-live-ext" posts just before it, every 2nd run or when their news changed;
              readers merge them (pc_feed.js / tools/pc_feed.py). PUBLIC: no PC name, no login,
              broker account ids cut to the last 4 digits, no folder, no email (public(), tools/site_privacy.py, docs/PRIVACY.md). Its "t" is the bot's own
              heartbeat time (never "now"), so an old report always looks old; "reporter" says what this PC saw just now.
  3. alerts   phone pushes on YOUR private ntfy topic (made here once, kept in %USERPROFILE%\\.olympus\\ntfy.json, never in the
              repo), $ first (engine/notify.py, notify_settings.json: per type on / off, quiet hours): trade opened
              "Zlarior 50K SHORT opened | risk $368 | target +$1,432", closed "Zlarior 50K closed +$605 | day +$605 | room $1,750"
              per account (Zlarior 50K, ATLAS 25K, BLITZ 25K; entry: side, micros, entry /
              stop / target, $ risk at the stop and its share of the drawdown left; exit: how it ended, +/- $ and R, drawdown
              left, today's $; a trade that opened and closed between two runs gets one push with both), FEED STALE, bot down,
              NinjaTrader closed, and "back to normal". Once per event; a problem repeats at most every 3 hours. The first run
              only records what is already there. The fill check (tools/fill_check.py, read-only: the bots' own state files):
              each NinjaTrader trade's real fill against the live loop's plan; a flag (wrong size, no stop at NinjaTrader,
              slippage over 2 ticks, bracket price off, costs above plan, an entry that never filled) is one high-priority
              push at any hour, and the trade's own push ends with "Fill check OK" or the flags.
              Olympus first (2026-11-19, docs/NOTIFICATIONS.md): when a phone turned on notifications in Olympus, each alert goes to
              it as Web Push (engine/push.app_send, the PC's own key; the core post carries that key as "wp"); the ntfy copy only
              when no phone took it, so one phone never gets the same alert twice.
  4. chart    the NQ page's live chart (owner 2026-11-18): the latest NQ 5-minute bars from this PC's NinjaTrader (LE_BarFeed's files)
              + every open trade and today's closed trades per account (by label, never an id), one small post of kind "le-bars"
              on its own public topic (the status topic + "-bars"): at most 24 a day (hourly candles in the bots' hours on runs
              without an ext post, at once after an entry / exit / stop move; bars_step, BARS_* below).
Nothing here starts, stops, arms or routes anything; no order, no live_model*.json, no engine/ file is changed. Every failure is
soft (logged, exit 0). Tests: tests/test_bots_back.py (fake http, fake files, never the real network).

  python tools/pc_report.py              one run (read, status, alerts) and the six-line card
  python tools/pc_report.py --card       only the six-line card (reads, sends nothing)
  python tools/pc_report.py --dry-run    one run that sends nothing: prints what it would send
  python tools/pc_report.py --setup      make your alert topic when there is none, print it
  python tools/pc_report.py --test       send one test push to your alert topic
  python tools/pc_report.py --bars       only the NQ chart post (from the last run's live.json; same pacing; for a 5-minute task)
Local files (gitignored): data/pc_report/ (last.json, state.json, status.json, status_ext.json, live.json, bars.json, report_log.jsonl).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

WORK_DEFAULT = os.path.join(ROOT, "data", "pc_report")
STATUS_FEED = os.path.join(ROOT, "tools", "web_public", "status_feed.json")
NTFY_DEFAULT = "https://ntfy.sh"
PORT_DEFAULT = int(os.environ.get("PORT") or 8766)
KALSHI_RW_LITE = ("kind", "paper_only", "updated", "days", "reward", "fill_pnl", "net", "fills", "markets", "per100_day")   # the card's keys
MAX_STATUS_BYTES = 3800          # ntfy turns a message over 4,096 bytes into a file attachment: stay under it, with room for the
                                 # signature + public key (_signed: ~190 bytes, day-security2 2026-11-20; was 3900)
# the split (owner 2026-11-18): the core "le-live" post every run, the extras in "le-live-ext" posts (tools/pc_feed.py merges them)
EXT_KIND = "le-live-ext"
EXT_PARTS = 2                    # at most 2 ext posts a run (ntfy.sh free: a few hundred messages a day per IP)
EXT_EVERY_S = 2640               # the ext goes every 3rd 15-minute run (44 min), or at once when its news changed (ext_hash). Was every 2nd (29 min) until
                                 # 2026-11-20: 96 core + 96 ext + 24 chart posts a day left no room under ntfy's 250 for the other programs and the alerts
EXT_ORDER = ("rd", "brd", "life", "mf", "k7", "board_trades", "at", "fq", "zl", "learn", "lab", "glance", "kalshi_rewards", "kalshi_k1", "kalshi_live", "ap")   # "at": engine/feed_trades
EXT_LAST = ("glog",)   # red-team 2026-11-21: the Brain's long thought stream takes only the room every other block left (cut 5/3, then out)
# "zl": ZEUS learned, the nightly line (engine/zeus_learn.read_tiny, <= 220 bytes) -> the ZEUS page's "ZEUS learned" card
CORE_KEYS = ("eh", "v", "kind", "lite", "src", "t", "every_s", "host", "model_state", "price", "day_pnl", "pc_verdict", "pc", "reporter",
             "board", "accounts", "trimmed", "wp", "ar", "pulse")   # wp: the phone app's push set-up (engine/push.app_block: public keys, ~230 bytes)
# ar: {glance bot id: [on, armed]} in the CORE (split(): the glance itself rides the ext, up to 44 min old); pulse: the time of a state-change post (engine/state_pulse.py)
BRD_BYTES = 1200
HB_STALE_S = 900                 # the bot beats every 5 min: older than 15 min = the bot is not reporting
BAR_STALE_S = 300                # the last 1-minute bar older than 5 min while the market is open = FEED STALE
REMIND_S = 3 * 3600
OLD_EVENT_S = 6 * 3600           # a trade older than this when first seen is recorded, not pushed (the PC was off)
SEEN_KEEP = 400
LOG_KEEP = 500
HTTP_TIMEOUT_S = 15
UA = "olympus-pc-report/1"
CARD_KEYS = ("id", "name", "plan", "method", "badge", "source", "configured", "balance", "floor", "room", "mll", "to_target",
             "target_balance", "profit", "today_pnl", "week_pnl", "status", "session", "sessions", "dll", "dll_used", "trades_today",
             "max_day", "room_frac", "paused", "off")
POS_KEYS = ("side", "qty", "entry", "stop", "target", "be", "entry_t", "unrealized_r")
TRADE_KEYS = ("acct", "src", "key", "member", "day", "entry_t", "exit_t", "side", "qty", "exit", "r", "usd", "open")   # src: paper rows stay paper
WORDS = ("amber", "anchor", "apple", "arrow", "aspen", "atlas", "autumn", "badger", "bamboo", "banjo", "basil", "beacon", "birch",
         "bison", "blaze", "breeze", "brook", "cactus", "camel", "canyon", "cedar", "cobalt", "comet", "coral", "cotton", "crane",
         "crystal", "dahlia", "delta", "desert", "dolphin", "dove", "eagle", "ember", "falcon", "fern", "fjord", "flint", "forest",
         "fox", "galaxy", "garnet", "glacier", "granite", "harbor", "hazel", "heron", "hickory", "honey", "indigo", "iris", "island",
         "ivory", "jade", "jasmine", "juniper", "kayak", "kestrel", "lagoon", "lantern", "lemon", "lily", "lotus", "lynx", "maple",
         "marble", "meadow", "mesa", "meteor", "mint", "moose", "nectar", "nova", "oak", "ocean", "olive", "onyx", "orchid", "otter",
         "panda", "pearl", "pepper", "pine", "planet", "plum", "polar", "poppy", "prairie", "quartz", "rain", "raven", "reef",
         "ridge", "river", "robin", "ruby", "saffron", "sage", "salmon", "sapphire", "sequoia", "shadow", "sierra", "silver",
         "sparrow", "spruce", "storm", "summit", "sunset", "swan", "thunder", "tiger", "topaz", "tulip", "tundra", "velvet",
         "violet", "walnut", "willow", "winter", "wolf", "zephyr")


# ------------------------------------------------------------------------------------------------ small helpers
def now_s() -> int:
    return int(time.time())


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def write_json(path, obj, compact=False):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        if compact:
            json.dump(obj, fh, separators=(",", ":"), default=str, ensure_ascii=False)
        else:
            json.dump(obj, fh, indent=1, default=str, ensure_ascii=False)
    os.replace(tmp, path)


def num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def money(x) -> str:
    v = num(x)
    if v is None:
        return "-"
    return ("-" if v < 0 else "") + "${:,.0f}".format(abs(v))


def signed_money(x) -> str:
    v = num(x)
    if v is None:
        return "-"
    return ("+" if v >= 0 else "-") + "${:,.0f}".format(abs(v))


def ago(sec) -> str:
    s = num(sec)
    if s is None:
        return "never"
    s = max(0, int(s))
    if s < 90:
        return "just now"
    if s < 5400:
        return f"{s // 60} min ago"
    if s < 172800:
        return f"{s // 3600} h ago"
    return f"{s // 86400} days ago"


def span(sec) -> str:
    """'40 s', '7 min', '3 h', '5 days' (a duration, no 'ago')."""
    s = num(sec)
    if s is None:
        return "?"
    s = max(0, int(s))
    if s < 90:
        return f"{s} s"
    if s < 5400:
        return f"{s // 60} min"
    if s < 172800:
        return f"{s // 3600} h"
    return f"{s // 86400} days"


def et_text(t) -> str:
    """'Thu 10:12 ET' (zoneinfo with the tzdata package from requirements.txt; UTC when it is missing)."""
    v = num(t)
    if v is None:
        return "-"
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(v, ZoneInfo("America/New_York")).strftime("%a %H:%M ET")
    except Exception:
        return dt.datetime.fromtimestamp(v, dt.timezone.utc).strftime("%a %H:%M UTC")


def ascii_only(s) -> str:
    """HTTP header values (the ntfy Title) must be plain ASCII."""
    return str(s or "").encode("ascii", "replace").decode("ascii").replace("?", "-")[:120]


def olympus_dir(env=None) -> str:
    try:
        from engine import nogithub
        return nogithub.olympus_dir(env)
    except Exception:
        env = os.environ if env is None else env
        return env.get("OLYMPUS_HOME") or os.path.join(env.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


def inside_repo(path: str) -> bool:
    try:
        a, b = os.path.realpath(path), os.path.realpath(ROOT)
        return os.path.commonpath([a, b]) == b
    except ValueError:
        return False


# ------------------------------------------------------------------------------------------------ config (outside the repo)
def make_topic(rng=None) -> str:
    """Your private alert topic: three words and four digits, easy to type on the phone ('nq-amber-falcon-river-7291').
    About 36 bits: unguessable in practice for a paper bot's alerts (anyone who knows it can read and post to it)."""
    rng = rng or secrets.SystemRandom()
    return "nq-" + "-".join(rng.choice(WORDS) for _ in range(3)) + "-" + "".join(str(rng.randrange(10)) for _ in range(4))


def status_feed(path: str | None = None) -> dict:
    """The public status channel the site reads: {"ntfy", "topic"} from tools/web_public/status_feed.json."""
    d = read_json(path or STATUS_FEED, {}) or {}
    return {"ntfy": str(d.get("ntfy") or NTFY_DEFAULT).rstrip("/"), "topic": str(d.get("topic") or "").strip()}


def load_cfg(env=None, feed_path: str | None = None) -> dict:
    """{"ntfy", "topic" (alerts, private), "status_topic" (public), "path", "on"}. Never raises."""
    d = olympus_dir(env)
    p = os.path.join(d, "ntfy.json")
    c = read_json(p, {}) or {}
    feed = status_feed(feed_path)
    return {"ntfy": str(c.get("ntfy") or feed["ntfy"] or NTFY_DEFAULT).rstrip("/"), "topic": str(c.get("topic") or "").strip(),
            "status_topic": str(c.get("status_topic") or feed["topic"] or "").strip(), "path": p,
            "on": c.get("on", True) is not False, "tested": c.get("tested"), "dir": d}


def ensure_topic(env=None, rng=None, feed_path: str | None = None) -> dict:
    cfg = load_cfg(env, feed_path)
    if cfg["topic"]:
        return cfg
    if inside_repo(cfg["dir"]):
        raise RuntimeError("the ntfy settings folder must be outside the repo")
    os.makedirs(cfg["dir"], exist_ok=True)
    cur = read_json(cfg["path"], {}) or {}
    cur.update(topic=make_topic(rng), ntfy=cur.get("ntfy") or NTFY_DEFAULT, made=now_s())
    write_json(cfg["path"], cur)
    try:
        os.chmod(cfg["path"], 0o600)
    except OSError:
        pass
    return load_cfg(env, feed_path)


def mark_tested(cfg: dict):
    cur = read_json(cfg["path"], {}) or {}
    cur["tested"] = {"topic": cfg.get("topic"), "t": now_s()}
    write_json(cfg["path"], cur)


# ------------------------------------------------------------------------------------------------ network (one place, fakeable)
def default_http(method, url, body=None, headers=None, timeout=HTTP_TIMEOUT_S):
    """-> (status, text). Never raises."""
    if os.environ.get("LE_PR_NO_NET") == "1":
        return 0, "network off (LE_PR_NO_NET=1)"
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("User-Agent", UA)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(20000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, e.__class__.__name__


# ---- STATUS SIGN ---- (tools/status_sign.py, day-security2 2026-11-20): every PUBLIC post (status core, ext, chart bars) carries the
# PC's ECDSA signature, so the site and Claude's board can tell the PC's posts from a stranger's. Trade alerts (private topic, phone
# app) are never touched. Anything wrong (no `cryptography`, no key, a write error, too big) = the body goes out exactly as before.
SIGN_MAX_BYTES = 4000            # a signed post stays a message (ntfy: 4,096); over it the post goes unsigned, as before
SIGN_STATE = {"why": None}       # the last reason a public post went unsigned (shown in the run record), None = signed


def _signed(body, core: bool = False, real: bool = True) -> str:
    """The exact text + ,"sg":"..."}; the core also carries "svk" (the public key, so it can be pinned once from the PC's own
    posts). real=False (a test's fake http): only with LE_STATUS_SIGN_KEY set, never the PC's own key. Never raises."""
    b = str(body)
    try:
        if os.environ.get("LE_STATUS_SIGN", "1") == "0":
            SIGN_STATE["why"] = "off (LE_STATUS_SIGN=0)"
            return b
        if not real and not os.environ.get("LE_STATUS_SIGN_KEY"):
            return b
        from tools import status_sign as _ss
        k = _ss.load_key()
        if not k and real and not os.environ.get("LE_STATUS_SIGN_KEY"):
            _ss.ensure_key()                         # once: <home>/.olympus/status_sign.json (0600); prints only the public key
            k = _ss.load_key()
        if not k or not (b.startswith("{") and b.endswith("}")):
            SIGN_STATE["why"] = "no key" if not k else "not a JSON object"
            return b
        t = b
        if core:
            t = b[:-1] + ',"svk":"' + _ss.vk_of(k) + '"}'
        out = _ss.sign_text(t, k)
        if len(out.encode("utf-8")) > SIGN_MAX_BYTES:
            out = _ss.sign_text(b, k)                # without svk (the ext / an earlier core carried it)
        if len(out.encode("utf-8")) > SIGN_MAX_BYTES:
            SIGN_STATE["why"] = "too big to sign"
            return b
        SIGN_STATE["why"] = None
        pin = _ss.feed_vk() if real else None
        if pin and _ss.vk_of(k) != pin:
            # redteam 2026-11-21: a new key (new PC / Windows profile) under a pinned vk: every post is signed but the phone and
            # board.py drop them all. Still posted; the run record says why (rec["unsigned"]).
            SIGN_STATE["why"] = "this PC's key is not the pinned vk: the phone drops these posts (re-pin: python tools/status_sign.py check)"
        return out
    except Exception as e:  # noqa: BLE001
        SIGN_STATE["why"] = e.__class__.__name__
        return b


def ntfy_post(base, topic, body, title=None, priority=None, tags=None, http=None) -> tuple:
    """POST a message to an ntfy topic. -> (ok, why)."""
    if not topic:
        return False, "no topic"
    h = {"Content-Type": "text/plain; charset=utf-8"}
    if title:
        h["Title"] = ascii_only(title)
    if priority:
        h["Priority"] = str(priority)
    if tags:
        h["Tags"] = ascii_only(tags)
    st, txt = (http or default_http)("POST", f"{base.rstrip('/')}/{topic}", str(body).encode("utf-8"), h)
    if 200 <= int(st or 0) < 300:
        return True, "ok"
    if st == 429:
        return False, "ntfy.sh rate limit (too many messages today): next run tries again"
    return False, f"ntfy answered {st or 'nothing'} {str(txt)[:60]}".strip()


def ntfy_quota(base, http=None) -> dict | None:
    """ntfy.sh's OWN count for this PC's internet address today (GET <base>/v1/account, anonymous: limits.messages, stats.messages /
    messages_remaining). Every program on the PC that posts to ntfy (the report, trade alerts, Kalshi, the data feed, learning, self-heal ...)
    is in it, which this file's own counter cannot see. A GET is not a message. None when ntfy does not say. Never raises."""
    try:
        st, txt = (http or default_http)("GET", f"{str(base or NTFY_DEFAULT).rstrip('/')}/v1/account", None, {"Accept": "application/json"}, 8)
        if int(st or 0) != 200:
            return None
        j = json.loads(txt)
        stats, lim = _d(j.get("stats")), _d(j.get("limits"))
        used, left = num(stats.get("messages")), num(stats.get("messages_remaining"))
        if used is None or left is None:
            return None
        return {"used": int(used), "remaining": int(left), "limit": int(num(lim.get("messages")) or used + left), "reset_at": num(stats.get("reset_at"))}
    except Exception:  # noqa: BLE001
        return None


def quota_holds(q: dict | None, n_posts: int) -> bool:
    """True when n_posts more (+ this run's core status post) would eat into the reserve kept for trade alerts, by ntfy's own count."""
    return bool(q) and int(q.get("remaining") or 0) - int(n_posts) - 1 < TRADE_ALERT_RESERVE


def server_up(port=PORT_DEFAULT, http=None) -> bool:
    st, txt = (http or default_http)("GET", f"http://127.0.0.1:{port}/api/health/ping", None, None, 4)
    if st != 200:
        return False
    try:
        return bool(json.loads(txt).get("ok"))
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------ what the PC sees
def read_heartbeat(root: str = ROOT) -> tuple:
    """(payload or None, last push {"at", "ok"} or None, source "pc_hb" | "last" | None): the newest of the two copies."""
    cands = []
    local = read_json(os.path.join(root, "logs", "pc_hb", "heartbeat.json"), None)
    if isinstance(local, dict) and num(local.get("t")):
        cands.append((num(local["t"]), local, "pc_hb"))
    last = read_json(os.path.join(root, "logs", "heartbeat_last.json"), {}) or {}
    pl = last.get("payload") if isinstance(last, dict) else None
    if isinstance(pl, dict) and num(pl.get("t")):
        cands.append((num(pl["t"]), pl, "last"))
    push = last.get("push") if isinstance(last, dict) and isinstance(last.get("push"), dict) else None
    if not cands:
        return None, push, None
    _t, pl, src = max(cands, key=lambda x: x[0])
    return pl, push, src


LOCAL_LIVE_TIMEOUT_S = 4
LOCAL_LIVE_MAX = 256 * 1024


def local_live(port=PORT_DEFAULT, http=None) -> dict | None:
    """The bot server's own live.json (GET 127.0.0.1:<port>/api/site/live.json: engine/live_publish.build of the running bot), or None
    (not 200, not JSON, not kind "le-live", no t). 4 s timeout. Never raises."""
    url = f"http://127.0.0.1:{port}/api/site/live.json"
    try:
        if http is not None:
            st, txt = http("GET", url, None, None, LOCAL_LIVE_TIMEOUT_S)
        else:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", UA)
            with urllib.request.urlopen(req, timeout=LOCAL_LIVE_TIMEOUT_S) as r:
                st, txt = r.status, r.read(LOCAL_LIVE_MAX).decode("utf-8", "replace")
        if int(st or 0) != 200:
            return None
        j = json.loads(txt)
        return j if isinstance(j, dict) and j.get("kind") == "le-live" and num(j.get("t")) else None
    except Exception:  # noqa: BLE001
        return None


def nt_running(env=None):
    """True / False on Windows (tasklist), None elsewhere. LE_PR_T_NT=1|0 for tests."""
    env = os.environ if env is None else env
    if env.get("LE_PR_T_NT") in ("0", "1"):
        return env["LE_PR_T_NT"] == "1"
    if os.name != "nt":
        return None
    try:
        import subprocess
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq NinjaTrader.exe", "/NH"], capture_output=True, text=True, timeout=20)
        return "NinjaTrader.exe" in (r.stdout or "")
    except Exception:
        return None


def market_open(now=None, env=None) -> bool:
    env = os.environ if env is None else env
    if env.get("LE_PR_T_MARKET") in ("0", "1"):
        return env["LE_PR_T_MARKET"] == "1"
    try:
        from engine import go
        from zoneinfo import ZoneInfo
        t = dt.datetime.fromtimestamp(now or time.time(), ZoneInfo("America/New_York"))
        return bool(go.market_open(t))
    except Exception:
        return True


def entry_hours(now=None) -> bool:
    """Weekday 01:50-15:30 ET: the bots' entry hours (a stopped bot then matters). Never on a CME holiday closure or after an
    early halt (redteam 2026-11-20: a bot stopped on Christmas or Thanksgiving afternoon was a "Bot stopped" alarm)."""
    try:
        from zoneinfo import ZoneInfo
        t = dt.datetime.fromtimestamp(now or time.time(), ZoneInfo("America/New_York"))
        if not (t.weekday() < 5 and 110 <= t.hour * 60 + t.minute <= 930):
            return False
        try:
            from engine.cme_calendar import halted
            return not halted(t.timestamp())
        except Exception:
            return True
    except Exception:
        return False


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def mode_of(hb: dict | None) -> str | None:
    """'paper' | 'Sim' | 'LIVE' from the heartbeat (the bot's own account block). None without a heartbeat."""
    if not isinstance(hb, dict):
        return None
    acct = _d(_d(hb.get("health")).get("account"))
    if (hb.get("adapter") or acct.get("adapter")) in (None, "paper"):
        return "paper"
    return "LIVE" if acct.get("is_live") else "Sim"


def gather(now=None, root: str = ROOT, env=None, http=None, port=PORT_DEFAULT, feed_problem=None) -> dict:
    """One look at the PC. Never raises. feed_problem() -> None (fresh) or why (tests pass a fake; default
    engine/go.feed_problem reads LE_BarFeed's files)."""
    now = int(now or time.time())
    hb, push, src = read_heartbeat(root)
    hb_t = int(num(_d(hb).get("t")) or 0) or None
    snap = {"t": now, "hb": hb, "hb_t": hb_t, "hb_age": (now - hb_t) if hb_t else None, "hb_src": src, "hb_push": push,
            "server": server_up(port, http), "nt": nt_running(env), "market_open": market_open(now, env),
            "entry_hours": entry_hours(now), "mode": mode_of(hb)}
    feed = _d(_d(_d(hb).get("health")).get("feed"))
    bar_age = num(feed.get("age_1m_s"))
    snap["bar_age"] = (bar_age + snap["hb_age"]) if (bar_age is not None and snap["hb_age"] is not None) else None
    snap["feed_flag"] = bool(feed.get("stale")) or bool(feed.get("entries_blocked") and "stale" in str(feed.get("block") or "").lower())
    fresh_hb = snap["hb_age"] is not None and snap["hb_age"] <= HB_STALE_S
    snap["local_feed"] = None
    if not fresh_hb:                       # no fresh word from the bot: look at LE_BarFeed's own files
        try:
            if feed_problem is None:
                from engine import go
                feed_problem = go.feed_problem
            snap["local_feed"] = feed_problem() or "fresh"
        except Exception as e:
            snap["local_feed"] = f"not readable ({e.__class__.__name__})"
    snap["live"] = None
    if hb:
        try:
            from engine import live_publish
            snap["live"] = live_publish.build(hb, now=hb_t or now, hb_last=push, every_s=num(hb.get("every_s")) or 300)
        except Exception as e:
            snap["live_error"] = f"{e.__class__.__name__}: {str(e)[:120]}"
    if snap["server"]:
        try:                                # audit D3 (2026-11-22): the running bot's own live.json (rebuilt every ~15 s) when it is newer
            lv = local_live(port, http)     # than the 5-minute heartbeat file; hb_t / hb_age stay the heartbeat's (the PC-silent rules)
            if lv and (num(lv.get("t")) or 0) > (hb_t or 0):
                snap["live"], snap["live_t"] = lv, int(num(lv["t"]))
        except Exception:  # noqa: BLE001
            pass
    snap["alerts_pc"] = _telegram_on(root)
    snap["alert_bus"] = _bus_active()       # Telegram / Discord through engine/alert_bus (ALERTS_SETUP.bat): a route of its own
    try:                                    # self-heal (engine/self_heal.py, night-selfheal): fixed / needs you + what grows on disk, <= 300 bytes
        from engine import self_heal as _sh
        snap["sh"] = _sh.read_tiny(root, now)
    except Exception:
        snap["sh"] = None
    try:                                    # real fills vs the live loop's plan (tools/fill_check.py, read-only: the bots' own files)
        from tools import fill_check
        snap["fills"] = fill_check.reviews(root, now)
    except Exception as e:
        snap["fills"] = []
        snap["fills_error"] = f"{e.__class__.__name__}: {str(e)[:120]}"
    try:                                    # live vs the backtest twin (tools/trade_watch.py, read-only: fill_audit's report.json)
        from tools import trade_watch
        snap["watch"] = trade_watch.flags(root, now)
    except Exception as e:
        snap["watch"] = []
        snap["watch_error"] = f"{e.__class__.__name__}: {str(e)[:120]}"
    try:                                    # night-risk: ZEUS circuit breaker (live vs twin ADVICE) + the runaway-order throttle trips
        from engine import circuit_breaker, msg_throttle
        snap["risk"] = circuit_breaker.flags(root, now) + msg_throttle.flags(root, now)
    except Exception as e:
        snap["risk"] = []
        snap["risk_error"] = f"{e.__class__.__name__}: {str(e)[:120]}"
    try:                                    # the Kalshi rewards PAPER card (tools/kalshi_rewards_paper.py public summary, < 1 KB)
        from engine import live_publish as _lpk
        snap["kalshi_rewards"] = _lpk.kalshi_rewards_card(now, os.path.join(root, "data", "kalshi_rewards", "summary.json"))
    except Exception:
        snap["kalshi_rewards"] = None
    try:                                    # the Kalshi K1 rules PAPER card (tools/kalshi_paper.py public summary, <= 200 bytes)
        from tools import kalshi_paper as _kp
        snap["kalshi_k1"] = _kp.read_card(os.path.join(root, "data", "kalshi_k1", "summary.json"), now)
    except Exception:
        snap["kalshi_k1"] = None
    try:                                    # the Kalshi K8 live/paper card (engine/kalshi_live.read_card, <= 200 bytes; None / off = not sent)
        from engine import kalshi_live as _kl
        snap["kalshi_live"] = _kl.read_card(now)
    except Exception:
        snap["kalshi_live"] = None
    try:                                    # ZEUS edge light (tools/edge_pc.py: the PC's daily edge_health --pc result, <= 120 bytes)
        from tools import edge_pc as _ep
        snap["eh"] = _ep.read_tiny(os.path.join(root, "data", "edge", "tiny.json"), now=now)
    except Exception:
        snap["eh"] = None
    try:                                    # ZEUS learned (engine/zeus_learn.py: the nightly line, <= 220 bytes, the ZEUS page card)
        from engine import zeus_learn as _zl
        snap["zl"] = _zl.read_tiny(os.path.join(root, "logs", "learn", "tiny.json"), now=now)
    except Exception:
        snap["zl"] = None
    try:                                    # the website money pipeline (agency/pipeline.py: counts + $ only, no names/phones/ids), refreshed each report
        from agency import pipeline as _ap
        try:
            _ap.write_card(_ap.build_card())
        except Exception:
            pass
        snap["ap"] = _ap.read_card()
    except Exception:
        snap["ap"] = None
    try:                                    # READY / NOT READY (engine/readiness, day-ready 2026-11-22): the last verdict, <= 200 bytes, plain words, no ids
        from engine import readiness as _rd
        snap["rd"] = _rd.rd(_rd.read_last(os.path.join(root, "data", "ready_last.json"), now=now))
    except Exception:
        snap["rd"] = None
    return snap


def _bus_active() -> bool:
    try:
        from engine import alert_bus as _ab
        return bool(_ab.active())
    except Exception:  # noqa: BLE001
        return False


def _telegram_on(root) -> bool:
    c = read_json(os.path.join(root, "data", "alerts.json"), {}) or {}
    return bool((c.get("telegram_token") and c.get("telegram_chat")) or c.get("discord_webhook"))


# ------------------------------------------------------------------------------------------------ the lite status (site shape)
def _card(c) -> dict | None:
    if not isinstance(c, dict) or c.get("error"):
        return None
    out = {k: c.get(k) for k in CARD_KEYS if c.get(k) is not None}
    w = c.get("window")
    if isinstance(w, dict):
        out["window"] = {"open": bool(w.get("open")), "text": str(w.get("text") or "")[:60]}
    p = c.get("position")
    if isinstance(p, dict):
        out["position"] = {k: p.get(k) for k in POS_KEYS if p.get(k) is not None}
    if isinstance(c.get("waiting"), str):
        out["waiting"] = c["waiting"][:80]
    return out


def _size(o) -> int:
    return len(json.dumps(o, separators=(",", ":"), default=str, ensure_ascii=False).encode("utf-8"))


def conditions(snap: dict) -> dict:
    """{code: plain sentence} of what is wrong right now (only what matters at this hour)."""
    out = {}
    mo, hb_age = snap.get("market_open"), snap.get("hb_age")
    # a real eval is never resumed by BOTS_BACK.bat (paper / Sim only): GO_LIVE_EVAL.bat brings it back and you type the phrase
    back = ("Double-click GO_LIVE_EVAL.bat on the PC (it brings the bot back; you type the phrase)." if snap.get("mode") == "LIVE"
            else "Double-click BOTS_BACK.bat on the PC.")
    if mo and not snap.get("server"):
        out["bot_down"] = "The bot server on the PC is not answering. " + back
    elif mo and (hb_age is None or hb_age > HB_STALE_S):
        out["bot_down"] = ("The bot has not reported for " + (span(hb_age) if hb_age is not None else "a long time") + ". " + back)
    elif snap.get("entry_hours") and snap.get("hb") is not None and not _d(snap["hb"]).get("running"):
        out["bot_stopped"] = "The bot server runs but the bot is stopped in entry hours. " + back
    if mo and snap.get("nt") is False:
        out["nt_down"] = "NinjaTrader is not running on the PC: open it and log in."
    elif mo and "bot_down" not in out and (snap.get("feed_flag") or (snap.get("bar_age") is not None and snap["bar_age"] > BAR_STALE_S)):
        out["feed_stale"] = ("FEED STALE: no fresh NinjaTrader bars" + (f" (last 1-minute bar {span(snap['bar_age'])} old)"
                             if snap.get("bar_age") is not None else "") + ", no new entries. Re-add LE_BarFeed on the MNQ 5-minute chart.")
    return out


def verdict_now(snap: dict, base: dict | None) -> dict | None:
    """The heartbeat's verdict, cut; DOWN / FEED when the reporter sees worse right now (its own t)."""
    v = {k: (base or {}).get(k) for k in ("code", "label", "level", "reason", "in_session", "hb_age_s", "t")} if isinstance(base, dict) else None
    if v and isinstance(v.get("reason"), str):
        v["reason"] = v["reason"][:140]
    cond = conditions(snap)
    if "bot_down" in cond:
        return {"code": "DOWN", "label": "BOT DOWN", "level": "bad", "reason": cond["bot_down"][:140], "t": snap["t"]}
    if "nt_down" in cond or "feed_stale" in cond:
        return {"code": "FEED", "label": "FEED STALE", "level": "bad", "reason": (cond.get("nt_down") or cond["feed_stale"])[:140], "t": snap["t"]}
    return v


def full(snap: dict) -> dict:
    """Everything the site may read from the PC, uncut and before the privacy pass: the core (kind "le-live", lite True, t = the
    bot's own heartbeat time or None, pc, pc_verdict, board.lit / atlas / blitz cards + lines + the last trades, accounts without
    trade lists, reporter = what this PC saw at reporter.t) and the extra blocks that ride in the ext post (EXT_TOP + pc.glance):
    brd (engine/board_events.status_block), life (engine/lifecycle hb block, cut), mf (engine/mffu_view.compact), kalshi_rewards."""
    L = snap.get("live") if isinstance(snap.get("live"), dict) else {}
    pc = _d(L.get("pc"))
    bd = _d(L.get("board"))
    hb = _d(snap.get("hb"))
    out = {"v": 1, "kind": "le-live", "lite": True, "src": "pc_report", "t": snap.get("live_t") or snap.get("hb_t"), "every_s": L.get("every_s") or hb.get("every_s"),
           "host": L.get("host") or hb.get("host"), "model_state": L.get("model_state"), "price": L.get("price"), "day_pnl": L.get("day_pnl"),
           "pc_verdict": verdict_now(snap, L.get("pc_verdict")),
           "pc": {k: pc.get(k) for k in ("running", "adapter", "position", "model_state", "host", "model", "present", "t", "age_s", "silent", "every_s",
                                         "glance")
                  if pc.get(k) is not None} if pc else {"present": False},
           "reporter": {"t": snap["t"], "server": bool(snap.get("server")), "nt": snap.get("nt"), "market_open": snap.get("market_open"),
                        "mode": snap.get("mode"), "hb_src": snap.get("hb_src"), "problems": sorted(conditions(snap))}}
    if bd and not bd.get("error"):
        b = {k: bd.get(k) for k in ("v", "kind", "t", "data_t", "where", "today", "host", "running", "level") if bd.get(k) is not None}
        for key in ("lit", "atlas", "blitz"):
            c = _card(bd.get(key))
            if c:
                b[key] = c
        b["lines"] = [{"level": x.get("level"), "text": str(x.get("text") or "")[:120]} for x in (bd.get("lines") or [])[:3] if isinstance(x, dict)]
        b["trades"] = [{k: t.get(k) for k in TRADE_KEYS if t.get(k) is not None} for t in (bd.get("trades") or [])[:3] if isinstance(t, dict)]
        out["board"] = b
    accts = []
    for a in L.get("accounts") or []:
        if not isinstance(a, dict) or not a.get("id"):
            continue
        ev = {k: _d(a.get("eval")).get(k) for k in ("start_balance", "balance", "profit", "to_target", "target_balance", "floor", "room", "mll",
                                                     "dll", "dll_used", "today", "session", "status") if _d(a.get("eval")).get(k) is not None}
        accts.append({"id": a["id"], "name": a.get("name"), "plan": a.get("plan"), "kind": a.get("kind"), "source": a.get("source"),
                      "badge": a.get("badge"), "conn": {k: _d(a.get("conn")).get(k) for k in ("present", "t", "running", "connected", "host")},
                      "eval": ev, "pnl": a.get("pnl"), "running": a.get("running"), "trades": [], "days": [],
                      # audit D2: Trading Home holds an account that is off / locked / not armed (optional: an old PC sends none)
                      **{k: a.get(k) for k in ("enabled", "locked", "armed") if a.get(k) is not None}})
    if accts:
        out["accounts"] = accts
    try:                                           # the Board's cut (engine/board_events.status_block: events + account rows); the ext
        from engine import board_events            # post has room for more events than the old single post (700 bytes)
        out["brd"] = board_events.status_block(max_bytes=BRD_BYTES)
    except Exception:  # noqa: BLE001
        pass
    try:                                           # the Brain page's longer thought stream (engine/brain_glance.logs: 8 lines a bot)
        from engine import brain_glance
        gl = brain_glance.logs(hb)
        if gl:
            out["glog"] = gl
    except Exception:  # noqa: BLE001
        pass
    life = _life(hb.get("life"))
    if life:
        out["life"] = life
    if isinstance(snap.get("sh"), dict):     # self-heal's one line (engine/self_heal.read_tiny): rides an ext post, after EXT_ORDER
        out["sh"] = snap["sh"]
    try:                                           # the MFFU-style account page (engine/mffu_view.py: start, days, trades, best day, equity)
        from engine import mffu_view
        mf = mffu_view.compact(L)
        if mf:
            out["mf"] = mf
    except Exception:  # noqa: BLE001
        pass
    try:                                           # the MFFU 7-day clock per account (engine/clock7: last fill, MFFU's last day,
        from engine import clock7                  # keep-alive on / off) for the NQ page's clock card and Jarvis; no "t" (the
        k7 = clock7.build(out.get("mf"), hb.get("keepalive"), snap.get("t"))   # post's own t dates it; ext_hash stays still)
        if k7:
            out["k7"] = {"a": [{k: v for k, v in r.items() if v is not None} for r in k7["a"]]}
    except Exception:  # noqa: BLE001
        pass
    try:                                           # every real account's last trades (engine/feed_trades: the Trading page's LIVE rows)
        from engine import feed_trades
        at = feed_trades.compact(L)
        if at:
            out["at"] = at
    except Exception:  # noqa: BLE001
        pass
    try:                                           # fills vs plan (engine/feed_fills, night-botgap): the journal's "Fills vs plan" card
        from engine import feed_fills
        fq = feed_fills.compact(hb.get("exec"), snap.get("fills"), snap.get("t"))
        if fq:
            out["fq"] = fq
    except Exception:  # noqa: BLE001
        pass
    if isinstance(snap.get("kalshi_rewards"), dict):   # the Kalshi page's "Rewards test (paper)" card (tools/kalshi_rewards_paper.py)
        # only what the card reads (~180 bytes, no per-series rows); it rides an ext post (EXT_ORDER)
        out["kalshi_rewards"] = {k: snap["kalshi_rewards"].get(k) for k in KALSHI_RW_LITE if snap["kalshi_rewards"].get(k) is not None}
    if isinstance(snap.get("kalshi_k1"), dict):        # the Kalshi page's "K1 rules (paper)" card (tools/kalshi_paper.py), <= 200 bytes, ext post
        out["kalshi_k1"] = snap["kalshi_k1"]
    if isinstance(snap.get("kalshi_live"), dict) and snap["kalshi_live"].get("st") != "off":   # Kalshi K8 live/paper card, <= 200 bytes
        out["kalshi_live"] = snap["kalshi_live"]
    if isinstance(snap.get("eh"), dict):     # the ZEUS edge chip (tools/edge_pc.read_tiny, <= 120 bytes; tools/web_public/edge_chip.js)
        out["eh"] = snap["eh"]
    if isinstance(snap.get("zl"), dict):     # ZEUS learned (engine/zeus_learn.read_tiny, <= 220 bytes): rides an ext post (EXT_ORDER)
        out["zl"] = snap["zl"]
    if isinstance(snap.get("rd"), dict):     # READY / NOT READY verdict (engine/readiness.rd, <= 200 bytes; no time inside: the ext hash stays still)
        out["rd"] = snap["rd"]
    if isinstance(snap.get("ap"), dict):     # the Money pipeline card (agency/pipeline.read_card): rides an ext post (EXT_ORDER)
        out["ap"] = snap["ap"]
    try:                                     # Olympus phone notifications (2026-11-19): the PC's PUBLIC push key + box key + its phones'
        from engine import push as _push     # short ids (engine/push.app_block); the phone subscribes with them. Core, never cut.
        if _push.app_block_ok(snap.get("wp")):
            out["wp"] = snap["wp"]
    except Exception:  # noqa: BLE001
        pass
    for k in ("learn", "lab"):                     # the learning loop / ZEUS Lab notes when the reporter's snapshot has them
        if isinstance(snap.get(k), dict):
            out[k] = snap[k]
    if snap.get("pulse"):                          # a state-change post (engine/state_pulse.py): when, so readers know it is one
        out["pulse"] = int(snap["pulse"])
    return {k: v for k, v in out.items() if v is not None}


def _life(b) -> dict | None:
    """The heartbeat "life" block (engine/lifecycle.Book.hb_block), cut for the public topic: stage per account, last 2 events.
    Account keys go through the privacy pass too (an extra account's key can hold an id)."""
    b = _d(b)
    if not b.get("acc") and not b.get("ev"):
        return None
    try:
        from tools import site_privacy
        ck = site_privacy.clean_string
    except Exception:  # noqa: BLE001
        return None
    acc = {ck(str(k))[:24]: {x: _d(r).get(x) for x in ("label", "stage", "since", "bal") if _d(r).get(x) is not None}
           for k, r in _d(b.get("acc")).items()}
    ev = [{x: _d(e).get(x) for x in ("t", "stage", "title") if _d(e).get(x) is not None} for e in (b.get("ev") or [])[-2:] if isinstance(e, dict)]
    return {"acc": acc, "ev": ev}


def _fit_core(out: dict, max_bytes: int) -> dict:
    """The core post under max_bytes: board lines, waiting texts, windows go first; the accounts block only after them."""
    steps = [lambda o: _d(o.get("board")).pop("lines", None),
             lambda o: [_d(_d(o.get("board")).get(k)).pop("waiting", None) for k in ("lit", "atlas", "blitz")],
             lambda o: [_d(_d(o.get("board")).get(k)).pop("window", None) for k in ("atlas", "blitz")],
             lambda o: o.pop("eh", None),            # the edge chip (tiny) goes before the accounts block
             lambda o: o.pop("accounts", None)]
    for st in steps:
        if _size(out) <= max_bytes:
            break
        st(out)
        out["trimmed"] = True
    if _size(out) > max_bytes:                     # last resort: the essentials only
        bb = _d(out.get("board"))
        out = {"v": 1, "kind": "le-live", "lite": True, "src": "pc_report", "t": out.get("t"), "trimmed": True, "pc": out.get("pc"),
               "pc_verdict": {k: _d(out.get("pc_verdict")).get(k) for k in ("code", "label", "level")},
               "reporter": out.get("reporter"), **({"wp": out["wp"]} if out.get("wp") else {}),
               **({"ar": out["ar"]} if out.get("ar") else {}), **({"pulse": out["pulse"]} if out.get("pulse") else {}),
               "board": {"t": bb.get("t"), "data_t": bb.get("data_t"),
                         **{k: {x: _d(bb.get(k)).get(x) for x in ("id", "name", "room", "mll", "balance", "today_pnl", "status")}
                            for k in ("lit", "atlas", "blitz") if bb.get(k)}}}
    return out


def _cuts(key: str) -> list:
    """Ways to make one ext block smaller, least loss first (the last one = leave it out)."""
    def glance(n):
        def f(v):
            from engine import brain_glance
            brain_glance.fit(v, n)
        return f
    def k7cut(v):                          # the 7-day clock: the plan's act day and the cautious deadline go first
        for r in (v.get("a") or []) if isinstance(v, dict) else []:
            if isinstance(r, dict):
                r.pop("act", None)
                r.pop("dl", None)
    def glog(n):
        def f(v):
            from engine import brain_glance
            brain_glance.cut_logs(v, n)
        return f
    def eq(n):
        def f(v):
            from engine import mffu_view
            mffu_view.cut_eq(v, n)
        return f
    def ev(n):
        return lambda v: v.__setitem__("ev", (v.get("ev") or [])[:n]) if isinstance(v, dict) else None
    def first(n):
        return lambda v: v.__delitem__(slice(n, None)) if isinstance(v, list) else None
    def at(n):
        def f(v):
            from engine import feed_trades
            feed_trades.cut(v, n)
        return f
    def fq(n):
        def f(v):
            from engine import feed_fills
            feed_fills.cut(v, n)
        return f
    def k8(*keys):                     # day-kalshi 2026-11-20: the K8 card's extras go before the whole Kalshi block would be cut
        def f(v):
            if isinstance(v, dict) and isinstance(v.get("k8"), dict):
                for key in keys:
                    v["k8"].pop(key, None)
        return f
    return {"kalshi_live": [k8("lg", "ls"), k8("e", "dy", "kk", "al", "pn")], "glance": [glance(1000), glance(600)], "glog": [glog(5), glog(3)], "k7": [k7cut], "mf": [eq(4), eq(0)], "brd": [ev(3), ev(1), ev(0)], "life": [ev(0)],
            "board_trades": [first(1)], "at": [at(2), at(1)], "fq": [fq(2), fq(0)]}.get(key, [])


def split(out: dict, max_bytes: int = MAX_STATUS_BYTES, parts: int | None = None) -> tuple:
    """full() -> (core, [ext ...]), each post under max_bytes, each through the privacy pass. The ext blocks go in EXT_ORDER into
    at most EXT_PARTS posts; a block too big for any is cut (_cuts), then left out ("cut" lists it)."""
    parts = EXT_PARTS if parts is None else parts
    core = json.loads(json.dumps(out, default=str))
    x = {k: core.pop(k) for k in list(core) if k not in CORE_KEYS}
    g = _d(core.get("pc")).pop("glance", None)
    if g:
        x["glance"] = g
        ar = armed_core(g)
        if ar:                                     # night-truth / audit D1: on + armed per bot ride every core post (~60 bytes)
            core["ar"] = ar
    tr = _d(core.get("board")).pop("trades", None)  # the last 3 trades: history, not the heartbeat (pc_feed lays them back in board)
    if tr:
        x["board_trades"] = tr
    core = _fit_core(core, max_bytes)
    base = {"v": 1, "kind": EXT_KIND, "src": "pc_report", "t": out.get("t"), "rt": _d(out.get("reporter")).get("t")}
    packs, cut = [{}], []
    order = ([k for k in EXT_ORDER if k in x] + sorted(k for k in x if k not in EXT_ORDER + EXT_LAST)
             + [k for k in EXT_LAST if k in x])
    for k in order:
        v, steps, placed = x[k], _cuts(k), False
        while not placed:
            for i, p in enumerate(packs):
                if _size({**base, "part": 9, "of": 9, "x": {**p, k: v}}) <= max_bytes:
                    p[k], placed = v, True
                    break
            if not placed and len(packs) < parts and _size({**base, "part": 9, "of": 9, "x": {k: v}}) <= max_bytes:
                packs.append({k: v})
                placed = True
            if not placed:
                if not steps:
                    cut.append(k)
                    break
                steps.pop(0)(v)
                if k not in cut:
                    cut.append(k)
    packs = [p for p in packs if p]
    exts = [{**base, "part": i, "of": len(packs), "x": p} for i, p in enumerate(packs)]
    if cut and exts:
        exts[-1]["cut"] = cut
    pub = public(core)
    wp = core.get("wp")
    if isinstance(pub, dict) and isinstance(wp, dict):
        try:                                       # public keys and hex ids only (app_block_ok): posted as made, never re-masked
            from engine import push as _push
            if _push.app_block_ok(wp):
                pub["wp"] = wp
        except Exception:  # noqa: BLE001
            pass
    return pub, [public(e) for e in exts]


def armed_core(glance) -> dict:
    """{bot id: [on 1/0, armed 1/0]} of the brain glance (engine/brain_glance: its armed rule), for the core post's "ar"."""
    out = {}
    for b in _d(glance).get("bots") or []:
        if isinstance(b, dict) and b.get("id"):
            out[str(b["id"])[:16]] = [int(bool(b.get("on"))), int(bool(b.get("armed")))]
    return out


def lite(snap: dict, max_bytes: int = MAX_STATUS_BYTES) -> dict:
    """The core post (kind "le-live") the site reads (tools/web_public/live.js LIVE.apply, board.js, truth.js), under max_bytes.
    It goes to a PUBLIC topic: public() takes out the PC name, logins, broker account ids and folders (tests.test_public_build_privacy e)."""
    return split(full(snap), max_bytes)[0]


def posts(snap: dict, max_bytes: int = MAX_STATUS_BYTES) -> tuple:
    """(core, [ext ...]) of one run: what run_once posts (exts first, then the core). tools/pc_feed.merge puts them together."""
    return split(full(snap), max_bytes)


def merged(snap: dict, max_bytes: int = MAX_STATUS_BYTES) -> dict:
    """What a reader sees after this run's posts (tools/pc_feed.merge of the core and its ext): the old single-post shape."""
    from tools import pc_feed
    core, exts = posts(snap, max_bytes)
    return pc_feed.merge(core, exts)


LIVE_KEYS = ("usd", "r", "R", "pnl", "unrealized_usd", "usd_now", "now_usd", "mfe", "mae", "last", "px")


def _news_of(k, v):
    """One ext block as news: an OPEN trade's live $ / R (they move every run while it is open) left out, so only an entry, an exit, a moved
    stop / target or a new day moves the hash (engine/mffu_view.py: "only what changes when a trade closes or a day ends"). The live $ still
    rides in the posted block and in the core (nqdash3 2026-11-20: an open ATLAS short made every 15-minute run an ext run)."""
    if k == "at" and isinstance(v, dict):                     # engine/feed_trades: tr = [entry_t, exit_t, dir, qty, entry, stop, target, kind, usd, r]
        a = []
        for row in v.get("a") or []:
            if isinstance(row, dict):
                row = {**row, "tr": [(x[:8] if isinstance(x, list) and len(x) >= 2 and x[1] is None else x) for x in row.get("tr") or []]}
            a.append(row)
        return {**{x: y for x, y in v.items() if x != "t"}, "a": a}
    if k == "board_trades" and isinstance(v, list):
        return [({x: y for x, y in t.items() if x not in LIVE_KEYS} if isinstance(t, dict) and (t.get("open") is True or str(t.get("exit") or "").upper() == "OPEN") else t)
                for t in v]
    if isinstance(v, dict):
        drop = CLOCK_KEYS | (ACCRUAL_KEYS.get(k) or set())
        return {a: b for a, b in v.items() if a not in drop}
    return v


# 2026-11-20 09:45 ET (the PC went silent: ntfy's per-IP day cap spent): the Kalshi blocks carry a clock ("updated" / "u") and paper sums that
# grow every 15 minutes, so every run was an ext run (2 posts) all night and morning. A clock is never news; a paper accrual is not either
# (a new fill is: "fills" / "fill_pnl" stay in). The ext still refreshes every 2nd run (EXT_EVERY_S) with the newest numbers.
CLOCK_KEYS = {"t", "updated", "u", "built", "rt"}
ACCRUAL_KEYS = {"kalshi_rewards": {"days", "net", "reward", "per100_day", "fill_pnl"}, "kalshi_k1": {"days"}, "kalshi_live": {"days"},
                "sh": {"free", "line"}}       # paper marks, free disk space: never news on their own


def ext_hash(exts) -> str:
    """The ext's news (block times, the brain glance and an open trade's live $ / R left out: _news_of): a new hash = post the ext now, not at
    the next EXT_EVERY_S."""
    import hashlib
    keep = [{k: _news_of(k, v) for k, v in _d(e.get("x")).items() if k not in ("glance", "glog")} for e in exts or []]
    # audit D1 (2026-11-22): a bot turning on / off, armed / disarmed or its "why not armed" is news (the Brain page waited up to 44 min);
    # the glance's other fields (levels, logs, texts, $) still are not
    keep.append([[b.get("id"), bool(b.get("on")), bool(b.get("armed")), b.get("nar")]
                 for e in exts or [] for b in (_d(_d(e.get("x")).get("glance")).get("bots") or []) if isinstance(b, dict)])
    return hashlib.sha1(json.dumps(keep, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def public(out: dict) -> dict:
    """The PUBLIC topic's privacy pass (tools/site_privacy.public_status, docs/PRIVACY.md): no PC name, no login, no broker account
    id (last 4 digits only), no personal folder, no email. If it cannot run, only the bare status goes out, never the raw cut."""
    try:
        from tools import site_privacy
        return site_privacy.public_status(out)
    except Exception:  # noqa: BLE001
        return {k: out[k] for k in ("v", "kind", "lite", "src", "t", "every_s", "trimmed") if k in out}


# ------------------------------------------------------------------------------------------------ the NQ page's live chart (le-bars)
# Owner 2026-11-18, "Live chart + our trades: NQ chart with every entry, stop and target drawn on it" (tools/web_public/nq/nqchart.js).
# Its own small post, kind "le-bars", on its OWN public topic (the status topic + "-bars"; status_feed.json "bars_topic" overrides): the
# core / ext posts, their 3,900-byte caps, their since=latest and the 70-minute window every page polls stay exactly as they were.
#   bars    LE_BarFeed's <ROOT>_5m.csv (the chart the bot decides on: engine/ninjatrader.NinjaTraderBars.root_for, MNQ first) + the 5m
#           bar still forming, built from <ROOT>_1m.csv; the bot's own archive data/nt_bars/NQ_5m.csv when that folder has none.
#           Packed small: p0 = the first open in ticks, then 4 tick deltas a bar (open - previous close, high - open, open - low,
#           close - open); t0 + 5 minutes a bar ("g" lists the bars that start elsewhere: the 17:00 halt). The oldest go first.
#   trades  every open trade and the day's closed trades of the real MFFU accounts (engine/feed_trades rules: never BLITZ, never the
#           cloud paper twin), each named by its label (tools/live_trades.ACCOUNTS: Zlarior 50K, Zlarior 25K #2, ATLAS funded 25K,
#           Rapid 25K), never by an id or digits: side, micros, entry, stop, target, times, exit price, $.
# The budget (lead 2026-11-18): ntfy.sh's free tier takes ~250 messages a UTC day per IP (reset 00:00 UTC, measured) and the status
# posts already use ~210, so the chart adds AT MOST BARS_DAY_MAX = 24 posts a UTC day, trade levels before candles:
#   trade levels  an entry, an exit or a stop / target move (the trades block changed): posted on that run (>= 5 min after the last
#                 chart post), in any open-market hour, up to the whole 24
#   candles       only in the bots' hours (weekday 01:50-16:10 ET), about hourly (59 min after the last chart post), only on a run that
#                 sent no ext post (it rides the 15-minute cycle: a run never sends more than an ext run does), at most 18 a day
#                 (BARS_DAY_MAX - BARS_TRADE_RESERVE: 6 always left for the trade levels)
#   never         market closed, nothing changed, bars stale, after a 429 that UTC day, once this PC counted NTFY_DAY_CAP -
#                 BARS_DAY_MAX posts that day (core + ext + pushes + chart)
# A full day: 15 hourly candle posts + 2-6 trade-level posts = ~17-21 (tests.test_pc_bars b simulates whole days). Posted AFTER the
# core and the pushes, so it never takes their room. Every step is soft: a failure here never touches the other posts.
BARS_KIND = "le-bars"
BARS_TOPIC_SUFFIX = "-bars"
BARS_STATE = "bars.json"         # data/pc_report/bars.json: the last chart post + today's post counts (gitignored with the folder)
BARS_TF = 300                    # 5-minute bars
BARS_MAX = 180                   # 15 hours: the bots' whole day (LIT from 02:00 ET) at 15:55 ET; under 3,900 bytes the oldest go first
BARS_MIN = 12                    # fewer bars than this: no post
BARS_TAIL_BYTES = 96 * 1024      # only the end of a bar file is read (~2,000 lines)
BARS_TICK = 0.25                 # NQ / MNQ
BARS_GAP_CANDLES_S = 3540        # candles: about hourly (the 4th 15-minute run), in the bots' hours only
BARS_BUSY_GRACE_S = 900          # nqdash3 2026-11-20: an open trade changes the ext's news every run (its live $ in "at"), so every run was a
                                 # busy run and the candles never went (04:15 -> none at 05:15 / 05:30 / 05:45 with ATLAS short open). Once the
                                 # candles are 74 min old they go on a busy run too (one extra post that run; the daily caps still hold)
BARS_GAP_TRADE_S = 300           # a trade opened / closed / moved: at once, but never twice in 5 minutes
NTFY_DAY_CAP = 250               # ntfy.sh free: messages a UTC day per IP (measured 2026-11-18; the status posts use ~210)
BARS_DAY_MAX = 24                # chart posts a UTC day, all kinds (lead 2026-11-18: "at most ~24 a day")
BARS_TRADE_RESERVE = 6           # of those, always left for the trade levels: candles stop at 18 a day
BARS_DAY_ALL_MAX = NTFY_DAY_CAP - BARS_DAY_MAX   # 226: no chart post once this PC counted this many posts today (the status first)
# Trade alerts first (owner 2026-11-20: entry + exit pushes "exactly when a trade is taken and closed"): the instant entry / exit
# alerts (engine/notify.instant_entry / instant_exit, from the bot's own process) count in this PC's day too (engine/notify.ntfy_today),
# and the extra status posts + the chart stop TRADE_ALERT_RESERVE posts before ntfy's cap, so those posts never use up the last room
# a trade alert needs (the core status post still goes every run: it is the PC's sign of life).
TRADE_ALERT_RESERVE = 12


def instant_today(now) -> int:
    """This UTC day's instant trade alerts on ntfy (engine/notify.ntfy_today). 0 when unknown. Never raises."""
    try:
        from engine import notify as _n
        return int(_n.ntfy_today(now))
    except Exception:  # noqa: BLE001
        return 0


def day_used(work: str, now) -> int:
    """This PC's ntfy posts this UTC day: the report's own (bars.json "all") + the instant trade alerts. Never raises."""
    try:
        st = read_json(os.path.join(work, BARS_STATE), {}) or {}
        cnt = _d(_d(st.get("days") if isinstance(st, dict) else {}).get(_utc_day(now)))
        return int(num(cnt.get("all")) or 0) + instant_today(now)
    except Exception:  # noqa: BLE001
        return 0
BARS_STALE_S = 900               # the newest price older than this while the market is open: no post (the core says FEED STALE)
BARS_TRADES = 12                 # closed trades in one post at most (the newest)


def _utc_day(t) -> str:
    return dt.datetime.fromtimestamp(int(t), dt.timezone.utc).strftime("%Y-%m-%d")


def _cme_day(t) -> str:
    """The CME trading day of a unix time: 18:00 ET opens the next day (the engine's rule, engine/ninjatrader._trading_day)."""
    try:
        from zoneinfo import ZoneInfo
        d = dt.datetime.fromtimestamp(float(t), ZoneInfo("America/New_York")) + dt.timedelta(hours=6)
    except Exception:  # noqa: BLE001  (no tzdata: New York winter time)
        d = dt.datetime.fromtimestamp(float(t), dt.timezone.utc) + dt.timedelta(hours=1)
    return d.strftime("%Y-%m-%d")


def bars_hours(now=None) -> bool:
    """Weekday 01:50-16:10 ET: the bots' day (entries from 01:50, flat by 15:55, the last exits and the day's close)."""
    try:
        from zoneinfo import ZoneInfo
        t = dt.datetime.fromtimestamp(now or time.time(), ZoneInfo("America/New_York"))
        return t.weekday() < 5 and 110 <= t.hour * 60 + t.minute <= 970
    except Exception:  # noqa: BLE001
        return True


def bars_topic(cfg: dict | None = None, feed_path: str | None = None) -> str:
    """The public chart topic: status_feed.json "bars_topic", else the status topic + "-bars" ("" without a status topic)."""
    feed = read_json(feed_path or STATUS_FEED, {}) or {}
    t = str(_d(feed).get("bars_topic") or "").strip()
    if t and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", t):
        return t
    st = str(_d(cfg).get("status_topic") or status_feed(feed_path)["topic"] or "").strip()
    return st + BARS_TOPIC_SUFFIX if re.fullmatch(r"[A-Za-z0-9_-]{1,59}", st) else ""


def read_bar_tail(path, max_rows: int = 2000, tail_bytes: int = BARS_TAIL_BYTES) -> list:
    """[(t, open, high, low, close)] of the newest rows of a bar CSV, oldest first: LE_BarFeed's "time,open,high,low,close,volume"
    (no header, time = the bar's OPEN in unix seconds) or the bot's archive (the same with a header). Stdlib only, the file's end
    only; a header, a junk line and a torn last line (no newline yet: NinjaTrader is still writing it) are skipped; one row a time
    (the last wins); high / low widened to hold open and close. Never raises."""
    rows = {}
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - tail_bytes))
            text = fh.read().decode("utf-8", "replace")
    except (OSError, TypeError, ValueError):
        return []
    lines = text.split("\n")
    if size > tail_bytes:
        lines = lines[1:]                          # the first line was cut by the seek
    if not text.endswith(("\n", "\r")):
        lines = lines[:-1]                         # torn: the next run has it whole
    for ln in lines:
        parts = ln.strip().split(",")
        if len(parts) < 5:
            continue
        try:
            t = int(float(parts[0]))
            o, h, l, c = (float(x) for x in parts[1:5])
        except ValueError:
            continue
        if t <= 0 or not all(0 < v < 1e7 for v in (o, h, l, c)):
            continue
        rows[t] = (t, o, max(h, o, c, l), min(l, o, c, h), c)
    return [rows[t] for t in sorted(rows)][-max(1, int(max_rows)):]


def bar_files(root: str = ROOT, nt_folder: str | None = None) -> dict:
    """Where the chart's bars come from: {"m5", "m1": paths or None, "sym": the chart's contract ("MNQ 12-26") or root, "src": "nt"
    (LE_BarFeed's files in Documents\\NinjaTrader 8\\le_feed) | "archive" (the bot's data/nt_bars/) | None}. nt_folder: the NinjaTrader
    8 folder (None = the real one, engine/ninjatrader.default_folder; "" = never, for a test with its own root). Never raises."""
    out = {"m5": None, "m1": None, "sym": None, "src": None}
    if nt_folder != "":
        try:
            from engine import ninjatrader as NT
            feed = NT.NinjaTraderBars(folder=nt_folder or None)
            m5, m1 = feed.file_for("NQ", 5), feed.file_for("NQ", 1)
            if m5 or m1:
                out.update(m5=m5, m1=m1, src="nt")
                try:
                    out["sym"] = feed.chart_instrument("NQ") or feed.root_for("NQ")
                except Exception:  # noqa: BLE001
                    out["sym"] = feed.root_for("NQ")
                return out
        except Exception:  # noqa: BLE001
            pass
    arch = os.path.join(root, "data", "nt_bars")
    m5, m1 = os.path.join(arch, "NQ_5m.csv"), os.path.join(arch, "NQ_1m.csv")
    if os.path.isfile(m5) or os.path.isfile(m1):
        out.update(m5=m5 if os.path.isfile(m5) else None, m1=m1 if os.path.isfile(m1) else None, src="archive", sym="NQ")
    return out


def chart_bars(m5: list, m1: list, now: int, tf: int = BARS_TF) -> tuple:
    """(bars, forming, data_t): the closed 5-minute bars, then the ones the 1-minute bars after them build (the newest still forming
    while now is inside it); a 1-minute-only chart builds them all (as engine/ninjatrader does). data_t = the newest price's time (the
    last 1m bar's close, else the last 5m bar's), never later than now."""
    bars = list(m5 or [])
    end = bars[-1][0] + tf if bars else None
    rest = [r for r in (m1 or []) if end is None or r[0] >= end]
    agg = {}
    if rest:
        base = end if end is not None else rest[0][0] // tf * tf
        for t, o, h, l, c in rest:
            k = base + (t - base) // tf * tf
            a = agg.get(k)
            agg[k] = (k, a[1], max(a[2], h), min(a[3], l), c) if a else (k, o, h, l, c)
    built = [agg[k] for k in sorted(agg)]
    forming = bool(built) and now < built[-1][0] + tf
    data_t = rest[-1][0] + 60 if built else (bars[-1][0] + tf if bars else None)
    return bars + built, forming, (min(int(data_t), int(now)) if data_t else None)


def _side(x) -> int:
    s = str(_d(x).get("side") or "").strip().upper()
    if s.startswith("S"):
        return -1
    if s.startswith(("L", "B")):
        return 1
    d = num(_d(x).get("dir"))
    return -1 if d is not None and d < 0 else 1


def _px2(v):
    x = num(v)
    return None if x is None else round(x, 2)


def _qty(v):
    x = num(v)
    return int(round(x)) if x else None


def _chart_accounts(L: dict) -> list:
    """[(key, label, bot, badge, account row or None)]: the real MFFU accounts of the PC's live.json (engine/feed_trades rules: eval /
    funded from the PC, never BLITZ, never the cloud paper twin), named by tools/live_trades.ACCOUNTS (an account it does not know:
    "Account 1 25K", key "x1"), never by its id. ATLAS from the board (account B's routed trades) when no account row is ATLAS's."""
    try:
        from tools import live_trades as LT
        key_of, names = LT.acct_key, {k: (v[0], v[1]) for k, v in LT.ACCOUNTS.items()}
    except Exception:  # noqa: BLE001
        key_of, names = (lambda a, b=None: None), {}
    try:
        from engine import feed_trades as FT
        real = FT._real
    except Exception:  # noqa: BLE001
        def real(a):
            return bool(a.get("id")) and a.get("kind") in ("eval", "funded") and a.get("source") not in ("cloud", "pc_blitz")
    out, extra = [], 0
    for a in _d(L).get("accounts") or []:
        a = _d(a)
        try:
            if not real(a):
                continue
        except Exception:  # noqa: BLE001
            continue
        k = key_of(a.get("id"))
        if not k:
            continue
        if k in names:
            label, bot = names[k]
        else:
            extra += 1
            m = re.search(r"(\d+K)", str(a.get("plan") or ""))
            k, label, bot = f"x{extra}", f"Account {extra}" + (f" {m.group(1)}" if m else ""), None
        if any(r[0] == k for r in out):
            continue
        bot = bot or ("ATLAS" if "atlas" in str(a.get("strategy") or "").lower() else "LIT")
        if k in ("rapid25", "rapid2"):              # a Rapid is named by its size (the 1st / 2nd Rapid may be a 25K or a 50K)
            m = re.search(r"(25|50)K", f"{a.get('plan') or ''} {a.get('name') or ''}")
            if m:
                label = f"Rapid {m.group(1)}K"
        out.append((k, label, bot, _badge(a.get("badge")), a))
    r1 = next((r for r in out if r[0] == "rapid25"), None)
    out = [(r[0], r[1] + " #2", *r[2:]) if r[0] == "rapid2" and r1 is not None and r1[1] == r[1] else r for r in out]
    if not any(r[0] == "atlas25f" for r in out):
        bd = _d(_d(L).get("board"))
        card = _d(bd.get("atlas"))
        rows = [t for t in bd.get("trades") or [] if _d(t).get("acct") == "atlas" and _d(t).get("src") == "live"]
        if rows or num(_d(card.get("position")).get("entry_t")):
            label, bot = names.get("atlas25f", ("ATLAS funded 25K", "ATLAS"))
            out.append(("atlas25f", label, bot or "ATLAS", _badge(card.get("badge")), None))
    return out


def _badge(b) -> str | None:
    """LIVE / SIM / PAPER (the account's own word), nothing else: a free-text badge never reaches the public post."""
    b = str(b or "").strip().upper()
    return ("LIVE" if b == "LIVE ACCOUNT" else b) if b in ("LIVE", "LIVE ACCOUNT", "SIM", "PAPER") else None


def _open_row(k, p) -> dict | None:
    p = _d(p)
    et_ = num(p.get("entry_t"))
    if not et_ or str(p.get("exit") or p.get("exit_kind") or "").upper() not in ("", "OPEN") or num(p.get("exit_t")):
        return None
    row = {"k": k, "s": _side(p), "q": _qty(p.get("qty")), "t": int(et_), "e": _px2(p.get("entry")), "sl": _px2(p.get("stop")),
           "tp": _px2(p.get("target"))}
    if p.get("be"):
        row["be"] = 1
    return {a: b for a, b in row.items() if b is not None}


def _closed_row(k, t) -> dict | None:
    t = _d(t)
    et_ = num(t.get("entry_t"))
    why = t.get("exit") if isinstance(t.get("exit"), str) else t.get("exit_kind")
    if not et_ or t.get("open") is True or str(why or "").upper() == "OPEN":
        return None
    xt = num(t.get("exit_t"))
    xp = t.get("exit_px") if t.get("exit_px") is not None else t.get("exit") if isinstance(t.get("exit"), (int, float)) else None
    usd = num(t.get("pnl")) if t.get("pnl") is not None else num(t.get("usd"))
    r = num(t.get("r") if t.get("r") is not None else t.get("R"))
    row = {"k": k, "s": _side(t), "q": _qty(t.get("qty")), "t": int(et_), "e": _px2(t.get("entry")), "xt": int(xt) if xt else None,
           "x": _px2(xp), "usd": None if usd is None else round(usd, 2), "r": None if r is None else round(r, 2),
           "why": re.sub(r"[^A-Z0-9_ -]", "", str(why or "").upper())[:12] or None, "day": str(t.get("day") or "")[:10] or None}
    return {a: b for a, b in row.items() if b is not None}


def chart_trades(L: dict, now: int, since=None, n_closed: int = BARS_TRADES) -> tuple:
    """({key: [label, bot, badge]}, open, closed) for the chart: every open trade of each real account (its position, or an open
    routed ATLAS trade) and its closed trades of today's CME day or exited since `since` (the first bar), the newest n_closed,
    oldest first. One row a trade (an open position that is also a closed row is closed). Never raises."""
    accts, opens, closed = {}, [], []
    try:
        L = _d(L)
        today = _cme_day(now)
        bd = _d(L.get("board"))
        for k, label, bot, badge, a in _chart_accounts(L):
            if a is not None:
                pos, rows = [a.get("position")], list(a.get("trades") or [])
            else:                                      # ATLAS's account B from the board
                pos = [_d(bd.get("atlas")).get("position")]
                rows = [t for t in bd.get("trades") or [] if _d(t).get("acct") == "atlas" and _d(t).get("src") == "live"]
                pos += [t for t in rows if _d(t).get("open") is True]
            cl = {}
            for t in rows:
                r = _closed_row(k, t)
                if not r:
                    continue
                last = r.get("xt") or r["t"]
                if (r.get("day") or _cme_day(last)) == today or _cme_day(last) == today or (since and last >= since):
                    r.pop("day", None)
                    cl[r["t"]] = r
            op = {}
            for p in pos:
                r = _open_row(k, p)
                if r and r["t"] not in cl and r["t"] not in op:
                    op[r["t"]] = r
            if cl or op:
                accts[k] = [label, bot] + ([badge] if badge else [])
                closed += cl.values()
                opens += op.values()
        closed = sorted(closed, key=lambda r: (r.get("xt") or r["t"], r["t"]))[-max(0, int(n_closed)):]
        opens = sorted(opens, key=lambda r: r["t"])
        used = {r["k"] for r in opens + closed}
        accts = {k: v for k, v in accts.items() if k in used}
    except Exception:  # noqa: BLE001
        return {}, [], []
    return accts, opens, closed


def _bar_size(o) -> int:
    return len(json.dumps(o, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def pack_bars(bars, opens=(), closed=(), accts=None, now=None, data_t=None, sym=None, forming=False, day=None, trades_t=None,
              max_bytes: int = MAX_STATUS_BYTES) -> dict | None:
    """The "le-bars" post (through the privacy pass) under max_bytes, or None (no bars / cannot fit):
      {"v": 1, "kind": "le-bars", "src": "pc_report", "t": the newest price's time, "rt": when the PC looked, "tt": the trades' time
       (the bot's heartbeat), "sym", "tf": 300, "tick": 0.25, "t0": the first bar's open time, "p0": its open in ticks, "n": bars,
       "b": [o - prev close, high - o, o - low, close - o] x n in ticks (the first bar's prev close = p0), "g": [[i, t], ...] the bars
       that do not start tf after the one before, "f": 1 the last bar is still forming, "day": today's CME day,
       "ac": {key: [label, bot, badge]}, "open": [{k, s (1 long / -1 short), q, t, e, sl, tp, be}],
       "closed": [{k, s, q, t, e, xt, x, usd, r, why}]}
    The oldest bars go first (never below BARS_MIN); then the oldest closed trades ("cut": how many)."""
    try:
        bars = [b for b in (bars or []) if b and len(b) >= 5][-BARS_MAX:]
        if len(bars) < BARS_MIN:
            return None
        now = int(now or time.time())
        accts, opens, closed = dict(accts or {}), list(opens or []), list(closed or [])
        today = day or _cme_day(now)

        def build(bs, cl, cut=0):
            p0 = round(bs[0][1] / BARS_TICK)
            flat, gaps, prev_c, prev_t = [], [], p0, None
            for i, (t, o, h, l, c) in enumerate(x[:5] for x in bs):
                O, H, Lo, C = (round(v / BARS_TICK) for v in (o, h, l, c))
                flat += [O - prev_c, max(0, H - O), max(0, O - Lo), C - O]
                if prev_t is not None and int(t) != prev_t + BARS_TF:
                    gaps.append([i, int(t)])
                prev_c, prev_t = C, int(t)
            # a closed trade that ended before the first bar is only kept when it is today's
            cl = [r for r in cl if (r.get("xt") or r["t"]) >= int(bs[0][0]) or _cme_day(r.get("xt") or r["t"]) == today]
            used = {r["k"] for r in opens + cl}
            post = {"v": 1, "kind": BARS_KIND, "src": "pc_report", "t": int(data_t or int(bs[-1][0]) + BARS_TF), "rt": now,
                    "tt": int(trades_t) if num(trades_t) else None, "sym": str(sym)[:24] if sym else None, "tf": BARS_TF,
                    "tick": BARS_TICK, "t0": int(bs[0][0]), "p0": p0, "n": len(bs), "b": flat, "g": gaps or None,
                    "f": 1 if forming else None, "day": today, "ac": {k: v for k, v in accts.items() if k in used} or None,
                    "open": opens or None, "closed": cl or None, "cut": cut or None}
            return {k: v for k, v in post.items() if v is not None}

        lo, hi = BARS_MIN, len(bars)                   # the most bars that fit (binary search on the newest kept)
        if _bar_size(build(bars, closed)) > max_bytes:
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if _bar_size(build(bars[-mid:], closed)) <= max_bytes:
                    lo = mid
                else:
                    hi = mid - 1
            bars = bars[-lo:]
        cut = 0
        while _bar_size(build(bars, closed, cut)) > max_bytes and closed:
            closed, cut = closed[1:], cut + 1          # still too big at BARS_MIN bars: the oldest closed trades go
        post = public(build(bars, closed, cut))
        while _bar_size(post) > max_bytes and len(bars) > BARS_MIN:
            bars = bars[1:]                            # the privacy pass made it longer (it never should): one bar more
            post = public(build(bars, closed, cut))
        ok = _bar_size(post) <= max_bytes and post.get("kind") == BARS_KIND and post.get("n") and isinstance(post.get("b"), list)
        return post if ok else None
    except Exception:  # noqa: BLE001
        return None


def unpack_bars(post) -> list:
    """[(t, open, high, low, close)] of a "le-bars" post, oldest first ([] for anything else). The reader's side, for the tests and
    tools; tools/web_public/nq/nqbars.js unpack() is its JS twin."""
    try:
        p = _d(post)
        if p.get("kind") != BARS_KIND:
            return []
        tf, tick, n, b = int(p.get("tf") or BARS_TF), float(p.get("tick") or BARS_TICK), int(p["n"]), list(p["b"])
        if n <= 0 or len(b) != 4 * n:
            return []
        gaps = {int(i): int(t) for i, t in p.get("g") or []}
        out, prev_c, t = [], int(p["p0"]), int(p["t0"])
        for i in range(n):
            do, dh, dl, dc = (int(x) for x in b[4 * i:4 * i + 4])
            if i:
                t = gaps.get(i, t + tf)
            o = prev_c + do
            out.append((t, o * tick, (o + dh) * tick, (o - dl) * tick, (o + dc) * tick))
            prev_c = o + dc
        return out
    except Exception:  # noqa: BLE001
        return []


def bars_post(L: dict | None, now: int, root: str = ROOT, nt_folder: str | None = None) -> dict | None:
    """The chart post of right now: the PC's NinjaTrader bars (bar_files) + the trades of the PC's live.json L, through the privacy
    pass, under MAX_STATUS_BYTES. None without enough bars. Never raises."""
    try:
        f = bar_files(root, nt_folder)
        m5 = read_bar_tail(f["m5"], BARS_MAX + 12) if f["m5"] else []
        m1 = read_bar_tail(f["m1"], BARS_MAX * 5 + 12) if f["m1"] else []
        bars, forming, data_t = chart_bars(m5, m1, int(now))
        bars = bars[-BARS_MAX:]
        if len(bars) < BARS_MIN:
            return None
        accts, opens, closed = chart_trades(L or {}, int(now), since=bars[0][0])
        return pack_bars(bars, opens, closed, accts, now=now, data_t=data_t, sym=f["sym"], forming=forming, day=_cme_day(now),
                         trades_t=_d(L).get("t"))
    except Exception:  # noqa: BLE001
        return None


def _bars_hashes(post) -> tuple:
    import hashlib

    def h(o):
        return hashlib.sha1(json.dumps(o, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    p = _d(post)
    return h([p.get(k) for k in ("t0", "p0", "n", "b", "g", "f", "sym")]), h([p.get(k) for k in ("ac", "open", "closed")])


def bars_due(state: dict | None, post: dict | None, now: int, market_open_now: bool, busy_run: bool = False, remaining=None) -> tuple:
    """(due, why): whether the chart post goes now (the budget in the block comment above; why "a trade changed" = a trade-level
    post, "hourly candles" = a candle post). busy_run: this run already sent an ext post (candles wait; trade levels never do)."""
    st = _d(state)
    if not market_open_now:
        return False, "market closed"
    day = _utc_day(now)
    cnt = _d(_d(st.get("days")).get(day))
    if st.get("blocked") == day:
        return False, "ntfy.sh limit reached today (429): back tomorrow"
    if int(num(cnt.get("bars")) or 0) >= BARS_DAY_MAX:
        return False, f"{BARS_DAY_MAX} chart posts today (the daily share)"
    if int(num(cnt.get("all")) or 0) + int(num(cnt.get("inst")) or 0) >= min(BARS_DAY_ALL_MAX, NTFY_DAY_CAP - TRADE_ALERT_RESERVE):
        return False, f"{min(BARS_DAY_ALL_MAX, NTFY_DAY_CAP - TRADE_ALERT_RESERVE)} posts today: the status and the pushes first"
    if remaining is not None and int(remaining) - 1 < TRADE_ALERT_RESERVE:
        return False, f"ntfy says {int(remaining)} posts left today: the rest is kept for trade alerts"
    if not post:
        return False, "no NinjaTrader bars on this PC"
    age = int(now) - int(num(post.get("t")) or 0)
    if age > BARS_STALE_S:
        return False, f"the newest bar is {span(age)} old"
    hb, ht = _bars_hashes(post)
    if hb == st.get("hb") and ht == st.get("ht"):
        return False, "unchanged"
    gap = int(now) - int(num(st.get("t")) or 0)
    if ht != st.get("ht"):                          # trade levels first: an entry, an exit, a moved stop / target
        return (True, "a trade changed") if gap >= BARS_GAP_TRADE_S else (False, f"a trade changed: next in {span(BARS_GAP_TRADE_S - gap)}")
    if not bars_hours(now):
        return False, "candles only in the bots' hours (01:50-16:10 ET)"
    if int(num(cnt.get("candles")) or 0) >= BARS_DAY_MAX - BARS_TRADE_RESERVE:
        return False, f"{BARS_DAY_MAX - BARS_TRADE_RESERVE} candle posts today (the rest is kept for trade levels)"
    if gap < BARS_GAP_CANDLES_S:
        return False, f"candles next in {span(BARS_GAP_CANDLES_S - gap)}"
    if busy_run and gap < BARS_GAP_CANDLES_S + BARS_BUSY_GRACE_S:
        return False, "this run sent the ext post: the candles go on the next run"
    return True, "hourly candles"


def _nt_folder(root: str, env=None):
    """The NinjaTrader folder the chart reads: LE_PR_T_NTDIR (tests), else the real one only for the real repo (a test's own root
    never reads this PC's NinjaTrader files)."""
    env = os.environ if env is None else env
    if env.get("LE_PR_T_NTDIR") is not None:
        return env["LE_PR_T_NTDIR"]
    try:
        return None if os.path.realpath(root) == os.path.realpath(ROOT) else ""
    except (OSError, ValueError):
        return ""


def bars_step(work: str, cfg: dict, L: dict | None, now: int, market_open_now: bool, dry: bool = False, http=None, say=print,
              root: str = ROOT, nt_folder: str | None = None, other_posts: int = 0, limited: bool = False,
              feed_path: str | None = None, busy_run: bool = False, remaining=None) -> dict:
    """One chart turn of a report run: count this run's other posts, build the post, post it to the chart topic when due (bars_due;
    busy_run = this run sent an ext post), keep the state (data/pc_report/bars.json: the last post, per UTC day the counts "all" (every
    post of this PC), "bars" (chart posts), "candles" (the candle-only ones)). -> {"posted", "why", "bytes", "n"}. Never raises; never
    writes in a dry run."""
    res = {"posted": False, "why": ""}
    try:
        p = os.path.join(work, BARS_STATE)
        st = read_json(p, {}) or {}
        st = st if isinstance(st, dict) else {}
        day, keep = _utc_day(now), _utc_day(int(now) - 3 * 86400)
        days = {k: dict(v) for k, v in _d(st.get("days")).items() if isinstance(v, dict) and str(k) >= keep}
        cnt = days.setdefault(day, {})
        cnt["all"] = int(num(cnt.get("all")) or 0) + max(0, int(other_posts or 0))
        inst = instant_today(now)                    # the bot's instant trade alerts today (they keep their room)
        if inst:
            cnt["inst"] = inst
        st["days"] = days
        if limited:                                    # the core or a push met ntfy's daily cap this run: no chart today
            st["blocked"] = day
        topic = bars_topic(cfg, feed_path)
        if not topic:
            res["why"] = "no status topic"
        else:
            post = bars_post(L, int(now), root, nt_folder) if market_open_now else None
            due, why = bars_due(st, post, int(now), market_open_now, busy_run=bool(busy_run), remaining=remaining)
            res["why"] = why
            if due:
                body = json.dumps(post, separators=(",", ":"), ensure_ascii=False)
                res.update(bytes=len(body.encode("utf-8")), n=post.get("n"))
                if dry:
                    say(f"[dry] chart bars ({post.get('n')} bars, {len(post.get('open') or [])} open, {len(post.get('closed') or [])} closed, "
                        f"{res['bytes']} bytes) -> {cfg.get('ntfy')}/{topic}")
                else:
                    ok, w = ntfy_post(cfg.get("ntfy") or NTFY_DEFAULT, topic, _signed(body, real=http is None), priority="min", http=http)
                    if ok:
                        hb, ht = _bars_hashes(post)
                        st.update(t=int(now), hb=hb, ht=ht, n=post.get("n"), bytes=res["bytes"])
                        cnt["bars"] = int(num(cnt.get("bars")) or 0) + 1
                        if why == "hourly candles":
                            cnt["candles"] = int(num(cnt.get("candles")) or 0) + 1
                        cnt["all"] += 1
                        res["posted"] = True
                        res["kind"] = "trades" if why == "a trade changed" else "candles"
                    else:
                        res["why"] = "chart: " + w
                        if "rate limit" in w:
                            st["blocked"] = day
        if not dry:
            write_json(p, st)
    except Exception as e:  # noqa: BLE001
        res["why"] = f"chart failed softly: {e.__class__.__name__}"
    return res


# ------------------------------------------------------------------------------------------------ alerts (events)
BOT_NAME = {"lit": "LIT", "atlas": "ATLAS", "blitz": "BLITZ"}


def _mode_note(snap) -> str:
    m = snap.get("mode")
    return {"paper": "Paper.", "Sim": "Sim account.", "LIVE": "Real account (you armed it)."}.get(m, "")


USD_PT = 2.0                     # MNQ: $2 a point a micro (every bot trades MNQ micros)
COMM_MICRO = 1.90                # engine/sizing.LIVE_COMM: the bot's commission a micro round trip
PUSH_NAME = {"lit": "Zlarior", "atlas": "ATLAS", "blitz": "BLITZ"}


def _label(acct, card=None) -> str:
    """'Zlarior 50K', 'ATLAS 25K', 'BLITZ 25K' (the size from the card's plan), else the bot's name."""
    import re
    m = re.search(r"(\d+K)", str(_d(card).get("plan") or ""))
    name = PUSH_NAME.get(acct, str(acct).upper())
    return f"{name} {m.group(1)}" if m else name


def _kind_note(acct, card, snap) -> str:
    """Which account the trade is on: Zlarior from the bot's own account block, ATLAS / BLITZ from their card's badge."""
    if acct == "lit":
        return _mode_note(snap or {})
    c = _d(card)
    b = str(c.get("badge") or "").upper()
    if c.get("real") or b == "LIVE":
        return "Real account."
    if b == "SIM":
        return "Sim account."
    return "Paper." if c.get("configured") is not False else "Paper (no account set up)."


def _pts(a, b):
    x, y = num(a), num(b)
    return None if x is None or y is None else abs(x - y)


def _px(v) -> str:
    x = num(v)
    return "-" if x is None else f"{x:,.2f}"


def risk_usd(p) -> float | None:
    """$ the trade loses at its stop, costs in: micros x stop distance x $2 + $1.90 a micro."""
    q, pts = num(_d(p).get("qty")), _pts(_d(p).get("entry"), _d(p).get("stop"))
    if not q or pts is None:
        return None
    return round(q * (pts * USD_PT + COMM_MICRO), 2)


def _r_of(t) -> float | None:
    r = num(t.get("r"))
    if r is not None:
        return r
    rk = risk_usd(t)
    u = num(t.get("usd"))
    return round(u / rk, 2) if (rk and u is not None) else None


def target_usd(p) -> float | None:
    """$ the trade makes at its target, costs in: micros x target distance x $2 - $1.90 a micro."""
    q, pts = num(_d(p).get("qty")), _pts(_d(p).get("target"), _d(p).get("entry"))
    if not q or pts is None:
        return None
    return round(q * (pts * USD_PT - COMM_MICRO), 2)


def _entry_text(p, card, closed=False) -> str:
    """'SHORT 6 micros at 25,100.25, stop 25,130.00 (29.75 pts), target 24,980.00 (120.25 pts). Risk $368 if stopped (costs
    in), 32% of the $1,145 room left.' (an open position without a stop says so; the fill check pushes it apart)"""
    q = p.get("qty")
    sp, tp = _pts(p.get("entry"), p.get("stop")), _pts(p.get("target"), p.get("entry"))
    rk = risk_usd(p)
    room = num(_d(card).get("room"))
    side = str(p.get("side") or "").upper()
    return (f"{side} {q if q is not None else '?'} micros at {_px(p.get('entry'))}"
            + (f", stop {_px(p.get('stop'))} ({sp:.2f} pts)" if sp is not None else "" if closed else ", NO STOP in the report")
            + (f", target {_px(p.get('target'))} ({tp:.2f} pts)" if tp is not None else "") + ". "
            + (f"Risk {money(rk)} if stopped (costs in)" + (f", {rk / room * 100:.0f}% of the {money(room)} room left" if room else "") + "."
               if rk is not None else ""))


def _exit_text(t, card) -> str:
    """'TARGET at 24,980.00, +$1,203 (+3.4R), Thu 10:42 ET. Room left $2,000 of $2,000.'"""
    c = _d(card)
    r = _r_of(t)
    return (f"{str(t.get('exit') or 'exit').upper()}" + (f" at {_px(t.get('exit_px'))}" if num(t.get("exit_px")) is not None else "")
            + f", {signed_money(t.get('usd'))}" + (f" ({r:+.1f}R)" if r is not None else "") + f", {et_text(t.get('exit_t') or t.get('entry_t'))}. "
            + (f"Room left {money(c.get('room'))} of {money(c.get('mll'))}." if num(c.get("room")) is not None else ""))


def _open_event(acct, p, snap=None, card=None) -> dict:
    """The entry push, $ first (owner 2026-11-17): 'Zlarior 50K SHORT opened | risk $368 | target +$1,432', then the prices,
    the risk's share of the room left and the account in the body."""
    side = str(p.get("side") or "").upper()
    rk, tg = risk_usd(p), target_usd(p)
    title = " | ".join([f"{_label(acct, card)} {side} opened".replace("  ", " ")] + ([f"risk {money(rk)}"] if rk is not None else [])
                       + ([f"target {signed_money(tg)}"] if tg is not None else []))
    body = f"{_entry_text(p, card)} {et_text(p.get('entry_t'))}. {_kind_note(acct, card, snap)}"
    return {"key": f"open:{acct}:{int(num(p['entry_t']))}", "t": int(num(p["entry_t"])), "acct": acct, "entry_t": int(num(p["entry_t"])),
            "title": title, "body": " ".join(body.split())}


def _close_event(acct, t, snap=None, card=None) -> dict:
    """The exit push, $ first: 'Zlarior 50K closed +$605 | day +$605 | room $1,750' (the trade's $, the account's $ today, the
    room left), how it ended and R in the body. "both" is the one push for a trade that opened and closed between two report
    runs (its entry and its exit in one message)."""
    c = _d(card)
    side = str(t.get("side") or "").upper()
    kind = _kind_note(acct, card, snap)
    title = " | ".join([f"{_label(acct, card)} closed {signed_money(t.get('usd'))}"]
                       + ([f"day {signed_money(c.get('today_pnl'))}"] if num(c.get("today_pnl")) is not None else [])
                       + ([f"room {money(c.get('room'))}"] if num(c.get("room")) is not None else []))
    body = f"{side} {t.get('qty') or ''} micros: {_exit_text(t, card)} {kind}"
    both = f"Opened {et_text(t.get('entry_t'))}: {_entry_text(t, card, closed=True)} Closed: {_exit_text(t, card)} {kind}"
    et_ = int(num(t["entry_t"]))
    return {"key": f"close:{acct}:{et_}", "t": int(num(t.get("exit_t")) or et_), "acct": acct, "entry_t": et_, "pair": f"open:{acct}:{et_}",
            "title": title, "body": " ".join(body.split()), "both": " ".join(both.split())}


def _fill_note(review) -> str:
    """The fill check in one sentence for a trade push ('Fill check OK: 6 of 6 filled, 1 tick worse than the plan, stop in
    place.'); '' for a paper trade or before the check knows the fill."""
    if not isinstance(review, dict):
        return ""
    try:
        from tools import fill_check
        return fill_check.short(review)
    except Exception:
        return ""


def _trade_events(snap: dict) -> list:
    """[{key, t, title, body, ...}] for every trade of each account the PC knows: opens (board.<bot>.position, open trades) and
    closes, each close after its own open (events() sends one push with both when the trade opened and closed between two
    report runs). An account's paper shadow rows (ATLAS's members while account B trades) are not its trades: left out."""
    bd = _d(_d(snap.get("live")).get("board"))
    out = []
    for key in ("lit", "atlas", "blitz"):
        p = _d(_d(bd.get(key)).get("position"))
        if num(p.get("entry_t")):
            out.append(_open_event(key, p, snap, bd.get(key)))
    for t in bd.get("trades") or []:
        if not isinstance(t, dict) or not num(t.get("entry_t")):
            continue
        acct = str(t.get("acct") or t.get("key") or "lit")
        card = _d(bd.get(acct))
        if t.get("src") == "paper" and (acct == "lit" or card.get("configured")):
            continue
        out.append(_open_event(acct, t, snap, card))
        if not t.get("open"):
            out.append(_close_event(acct, t, snap, card))
    return out


COND_TITLE = {"bot_down": "Bot down", "bot_stopped": "Bot stopped", "nt_down": "NinjaTrader closed", "feed_stale": "FEED STALE"}
COND_BACK = {"bot_down": "The bot reports again.", "bot_stopped": "The bot runs again.", "nt_down": "NinjaTrader runs again.",
             "feed_stale": "NinjaTrader bars are fresh again."}


def events(state: dict, snap: dict) -> tuple:
    """(new state, [push messages]). state: {"seen": {key: t}, "cond": {code: {"since", "alert_t"}}, "seeded": bool}."""
    st = {"seen": dict(_d(state.get("seen"))), "cond": {k: dict(v) for k, v in _d(state.get("cond")).items() if isinstance(v, dict)},
          "seeded": bool(state.get("seeded"))}
    now = snap["t"]
    msgs = []
    revs = [r for r in snap.get("fills") or [] if isinstance(r, dict) and r.get("acct") and num(r.get("entry_t"))]
    rv_of = {(r["acct"], int(num(r["entry_t"]))): r for r in revs}
    evs = _trade_events(snap)
    closing = {e["pair"] for e in evs if e.get("pair") and e["key"] not in st["seen"]}
    for ev in evs:
        key, t = ev["key"], ev["t"]
        if key in st["seen"]:
            continue
        st["seen"][key] = now
        if key.startswith("open:") and ("close:" + key[len("open:"):] in st["seen"] or key in closing):
            continue                    # closed before (no late "opened"), or closing in this run: its close push says both
        if st["seeded"] and now - t <= OLD_EVENT_S:
            both = bool(ev.get("pair")) and ev["pair"] in closing and st["seen"].get(ev["pair"]) == now
            note = _fill_note(rv_of.get((ev.get("acct"), ev.get("entry_t"))))
            msgs.append({"key": key, "keys": [key] + ([ev["pair"]] if both else []), "title": ev["title"],
                         "body": ((ev["both"] if both else ev["body"]) + (" " + note if note else "")).strip(),
                         "priority": "high" if key.startswith("open") else "default",
                         "tags": "chart_with_upwards_trend" if key.startswith("open") else "checkered_flag", "ev_t": t})
    # real fill vs plan (tools/fill_check.py): every flag of a NinjaTrader trade, once, high priority at any hour (a real account)
    for r in revs:
        try:                            # one odd review never stops the run (the status and the other alerts still go out)
            by = {}
            for f in r.get("flags") or []:
                if isinstance(f, dict):
                    by.setdefault(f.get("code") or "flag", []).append(f)
            et_ = int(num(r["entry_t"]))
            for code, fs in by.items():
                key = f"fill:{r['acct']}:{et_}:{code}"
                if key in st["seen"]:
                    continue
                st["seen"][key] = now
                last_t = max(et_, int(num(_d(r.get("real")).get("exit_t")) or 0))
                if not st["seeded"] or now - last_t > OLD_EVENT_S:
                    continue
                try:
                    from tools import fill_check
                    title, body = fill_check.push_text(r, {**fs[0], "text": " ".join(str(x.get("text") or "") for x in fs)})
                except Exception:
                    title, body = f"{r.get('label') or r['acct']} fill check: {code}", " ".join(str(x.get("text") or "") for x in fs)
                msgs.append({"key": key, "title": title, "body": body, "priority": "high" if r.get("kind") == "LIVE" else "default",
                             "tags": "rotating_light"})
        except Exception:
            continue
    # live vs the backtest twin (tools/trade_watch.py): a missed entry, a slipped fill, a missing / misplaced stop; once, high
    for w in (snap.get("watch") or []) + (snap.get("risk") or []):     # risk: engine/circuit_breaker + engine/msg_throttle
        try:
            key = str(w["key"])
            if key in st["seen"]:
                continue
            st["seen"][key] = now
            if not st["seeded"] or now - int(num(w.get("t")) or 0) > OLD_EVENT_S:
                continue
            msgs.append({"key": key, "title": str(w.get("title") or "Trade watch")[:120], "body": str(w.get("body") or "")[:600],
                         "priority": "high", "tags": "rotating_light"})
        except Exception:
            continue
    # MFFU account lifecycle (engine/lifecycle.py, the heartbeat "life" block): PASSED / LOCKED / FAILED / LOST / PAYOUT READY,
    # once each, at any hour (the account is stood down; the owner sends Claude the new account name)
    for e in _d(_d(snap.get("hb")).get("life")).get("ev") or []:
        try:
            key = str(e["push"])
            if key in st["seen"]:
                continue
            st["seen"][key] = now
            if not st["seeded"] or now - int(num(e.get("t")) or 0) > OLD_EVENT_S:
                continue
            pay = e.get("stage") == "payout_ready"
            msgs.append({"key": key, "title": str(e.get("title") or "Account")[:120], "body": str(e.get("body") or "")[:600],
                         "priority": "default" if pay else "high", "tags": "moneybag" if pay else "rotating_light"})
        except Exception:
            continue
    cond = conditions(snap)
    for code, text in cond.items():
        c = st["cond"].get(code)
        if c is None:
            st["cond"][code] = {"since": now, "alert_t": now}
            msgs.append({"key": f"cond:{code}:{now}", "title": COND_TITLE.get(code, code), "body": text, "priority": "high", "tags": "warning"})
        elif snap.get("market_open") and now - int(c.get("alert_t") or 0) >= REMIND_S and code != "bot_stopped":
            c["alert_t"] = now
            msgs.append({"key": f"cond:{code}:{now}", "title": COND_TITLE.get(code, code) + " (still)",
                         "body": text + f" Since {et_text(c.get('since'))}.", "priority": "high", "tags": "warning"})
    for code in [k for k in st["cond"] if k not in cond]:
        st["cond"].pop(code, None)
        msgs.append({"key": f"back:{code}:{now}", "title": "Back to normal", "body": COND_BACK.get(code, "Back to normal."),
                     "priority": "default", "tags": "white_check_mark"})
    # the guard pushes (tools/pc_guard.py, read-only): contract roll, eval drawdown, daily loss, quiet bot, 16:05 day summary.
    # Not on the very first run (that one only records what is already there).
    st["guard"] = dict(_d(state.get("guard")))
    if st["seeded"]:
        try:
            from tools import pc_guard
            st["guard"], gm = pc_guard.guard(st["guard"], {**snap, "cond": cond})    # cond: the 01:45 ready push names them
            msgs += gm
        except Exception:
            pass
    if not st["seeded"]:                # the first run: what is already there is only recorded, never pushed
        st["seeded"] = True
        msgs = [m for m in msgs if m["key"].startswith("cond:")]
    if len(st["seen"]) > SEEN_KEEP:
        for k in sorted(st["seen"], key=st["seen"].get)[: len(st["seen"]) - SEEN_KEEP]:
            st["seen"].pop(k, None)
    # notify_settings.json (engine/notify.py): a type switched off is dropped (its key stays seen: it never comes later), in
    # quiet hours a trade / ordinary push arrives without sound; PC silent, room low and problems keep ringing
    try:
        from engine import notify
        msgs = notify.apply(msgs, now)
    except Exception:
        pass
    return st, msgs


# ------------------------------------------------------------------------------------------------ the six-line card
def card(snap: dict, cfg: dict | None = None, last: dict | None = None) -> list:
    """[(kind OK|FIX|SKIP|.., label, text)] x6 + the NEXT sentence as the 7th item (kind NEXT)."""
    cfg = cfg or {}
    last = last or {}
    hb, L = _d(snap.get("hb")), _d(snap.get("live"))
    bd = _d(L.get("board"))
    cond = conditions(snap)
    mo = snap.get("market_open")
    rows = []
    # 1 BOTS
    if not snap.get("server"):
        rows.append(("FIX" if mo else "..", "BOTS", "the bot server is not answering" + ("" if mo else " (market closed)")))
    elif not hb:
        rows.append(("SKIP", "BOTS", "the server answers but the bot has not reported yet (give it 5 minutes)"))
    else:
        mode = snap.get("mode") or "?"
        run = bool(hb.get("running"))
        others = []
        for key in ("atlas", "blitz"):
            c = _d(bd.get(key))
            st = str(c.get("status") or "")
            badge = str(c.get("badge") or "paper").upper()
            others.append(f"{BOT_NAME[key]} " + ("not set up" if st in ("not set up", "off", "") else
                                                  {"SIM": "on Sim", "PAPER": "paper", "LIVE": "LIVE"}.get(badge, badge.lower())))
        txt = ("LIT running" if run else "LIT STOPPED") + f" ({'LIVE, armed by you' if mode == 'LIVE' else mode})" + "; " + "; ".join(others)
        if snap.get("hb_age") is not None and snap["hb_age"] > HB_STALE_S:
            rows.append(("FIX" if mo else "..", "BOTS", f"last report {ago(snap['hb_age'])}: {txt}"))
        elif not run:
            rows.append(("FIX" if snap.get("entry_hours") else "SKIP", "BOTS", txt))
        else:
            rows.append(("OK", "BOTS", txt))
    # 2 FEED
    if snap.get("nt") is False:
        rows.append(("FIX" if mo else "..", "FEED", "NinjaTrader is not running" + ("" if mo else " (market closed)")))
    elif "feed_stale" in cond:
        rows.append(("FIX", "FEED", cond["feed_stale"].split(". Re-add")[0]))
    elif snap.get("bar_age") is not None and snap.get("hb_age") is not None and snap["hb_age"] <= HB_STALE_S:
        rows.append(("OK" if mo else "..", "FEED", f"last 1-minute bar {span(snap['bar_age'])} old" + ("" if mo else " (market closed)")))
    elif snap.get("local_feed"):
        lf = snap["local_feed"]
        rows.append(("OK" if lf == "fresh" else ("FIX" if mo else ".."), "FEED", "LE_BarFeed bars fresh" if lf == "fresh" else f"LE_BarFeed: {str(lf)[:90]}"))
    else:
        rows.append(("..", "FEED", "unknown (no report from the bot)"))
    # 3 TRADE
    pos = next(((k, _d(bd.get(k)).get("position")) for k in ("lit", "atlas", "blitz") if isinstance(_d(bd.get(k)).get("position"), dict)), None)
    closed = [t for t in bd.get("trades") or [] if isinstance(t, dict) and not t.get("open")]
    closed.sort(key=lambda t: num(t.get("exit_t")) or num(t.get("entry_t")) or 0, reverse=True)
    if pos:
        p = pos[1]
        rows.append(("OK", "TRADE", f"{BOT_NAME.get(pos[0])} in a trade: {p.get('side')} {p.get('qty') or ''} at {p.get('entry')}, since {et_text(p.get('entry_t'))}"))
    elif closed:
        t = closed[0]
        r = num(t.get("r"))
        rows.append(("OK", "TRADE", f"last: {BOT_NAME.get(t.get('acct'), str(t.get('acct') or '').upper())} {t.get('side') or ''} "
                     f"{t.get('exit') or ''} {signed_money(t.get('usd'))}" + (f" ({r:+.1f}R)" if r is not None else "") + f", {et_text(t.get('exit_t'))}"))
    else:
        rows.append(("..", "TRADE", "no trade on record yet" if hb else "unknown (no report from the bot)"))
    # 4 ROOM (drawdown left)
    parts = []
    for key in ("lit", "atlas", "blitz"):
        c = _d(bd.get(key))
        if num(c.get("room")) is not None:
            parts.append(f"{BOT_NAME[key]} {money(c['room'])} of {money(c.get('mll'))}")
    low = any((num(_d(bd.get(k)).get("room")) or 1e9) < 0.25 * (num(_d(bd.get(k)).get("mll")) or 0) for k in ("lit", "atlas", "blitz"))
    rows.append((("SKIP" if low else "OK") if parts else "..", "ROOM", ("drawdown left: " + ", ".join(parts)) if parts else "unknown (no report from the bot)"))
    # 5 REPORT
    rp = []
    if cfg.get("topic"):
        lp = _d(last.get("alerts_last"))
        rp.append(f"phone alerts on ntfy topic {cfg['topic']}" + (f" (last push {ago(snap['t'] - lp['t'])})" if num(lp.get("t")) else ""))
    if num(last.get("status_t")):
        rp.append(f"site status sent {ago(snap['t'] - int(last['status_t']))}")
    gh = _github_off()
    if gh and snap.get("server") and snap.get("hb_src") == "last" and snap.get("hb_age") is not None and snap["hb_age"] <= HB_STALE_S:
        rp.append("GitHub-free mode set, the running bot still tries GitHub (restart it once when flat)")
    else:
        rp.append("GitHub off" if gh else "GitHub pushes still on (double-click BOTS_BACK.bat)")
    if snap.get("alerts_pc"):
        rp.append("Telegram on")
    if snap.get("alert_bus"):
        rp.append("alerts via Telegram / Discord first (alert bus)")
    if "wp" in snap and not cfg.get("topic") and not _d(snap.get("wp")).get("d") and not snap.get("alert_bus"):     # a real run knows the phones (engine/push.app_block)
        rp.insert(0, "NO PHONE ALERT ROUTE: no Olympus phone and no ntfy alert topic, so trade alerts reach nobody "
                     "(check: python -X utf8 -m engine.alert_check)")
    rep_ok = bool(cfg.get("topic")) and last.get("ok") is not False
    rows.append(("OK" if rep_ok else "SKIP", "REPORT", "; ".join(rp)))
    # 6 NEXT window
    w = _d(_d(bd.get("lit")).get("window"))
    rows.append(("OK" if w.get("text") else "..", "WINDOW", f"LIT {w['text']}" if w.get("text") else "next entry window: weekdays 02:00-15:30 ET"))
    fixes = [r for r in rows if r[0] == "FIX"]
    nxt = {"BOTS": "Double-click BOTS_BACK.bat again; if it stays red, double-click HEALTH_CHECK.bat and send Claude a photo.",
           "FEED": "In NinjaTrader: log in, open the MNQ 5-minute chart, right-click > Indicators > LE_BarFeed > Add.",
           "TRADE": "", "ROOM": "", "REPORT": "", "WINDOW": ""}
    if fixes:
        rows.append(("NEXT", "NEXT", nxt.get(fixes[0][1]) or "Send Claude a photo of this window."))
    elif not cfg.get("topic"):
        rows.append(("NEXT", "NEXT", "Double-click BOTS_BACK.bat once to make your phone alert topic."))
    else:
        rows.append(("NEXT", "NEXT", "nothing to do."))
    return rows


def _github_off() -> bool:
    try:
        from engine import nogithub
        return nogithub.active()
    except Exception:
        return False


def card_text(rows) -> str:
    out = []
    for kind, label, text in rows:
        out.append(f"  NEXT: {text}" if kind == "NEXT" else f"  [{kind}] {label:<6} {text}")
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ one run
def log_line(work, rec):
    try:
        p = os.path.join(work, "report_log.jsonl")
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, separators=(",", ":"), default=str) + "\n")
        with open(p, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) > LOG_KEEP * 1.2:
            with open(p, "w", encoding="utf-8") as fh:
                fh.writelines(lines[-LOG_KEEP:])
    except Exception:
        pass


LOCK_STALE_S = 600


def run_lock(work: str, now=None):
    """One report at a time (the 15-minute task and the bot server's keeper, engine/report_keeper.py, can both start one):
    the lock file's path when taken, None when another run holds it. A lock older than LOCK_STALE_S (a crashed run) is taken over."""
    now = int(now or time.time())
    os.makedirs(work, exist_ok=True)
    p = os.path.join(work, "run.lock")
    for _ in range(2):
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as fh:
                fh.write(str(now))
            return p
        except FileExistsError:
            try:
                if now - int(os.path.getmtime(p)) <= LOCK_STALE_S:
                    return None
                os.remove(p)
            except OSError:
                return None
        except OSError:
            return None
    return None


def run_unlock(p):
    if p:
        try:
            os.remove(p)
        except OSError:
            pass


_NO_BUS = object()


def _forget(new_state: dict, m: dict) -> None:
    """An alert that did not go: forget it so the next run tries again (conditions keep their state; a trade key is retried)."""
    if m["key"].startswith(("open:", "close:", "fill:", "watch:")):
        for k in m.get("keys") or [m["key"]]:
            new_state["seen"].pop(k, None)
    elif m["key"].startswith("guard:"):
        _d(_d(new_state.get("guard")).get("sent")).pop(m["key"], None)


def _bus_alerts(msgs, rec: dict, snap: dict, new_state: dict):
    """engine/alert_bus (owner 2026-11-21): the report's alerts go Telegram / Discord first (ntfy's private topic and the phone
    app are its fallbacks), so they never use the ntfy room the status posts need. None = the bus is off / not set up: the
    old loop runs, exactly. Waits up to 90 s for the deliveries (this is a 15-minute script, not the trading loop)."""
    try:
        from engine import alert_bus as AB
        if not AB.active():
            return None
    except Exception:  # noqa: BLE001
        return None
    done: dict = {}
    for m in msgs:
        r = AB.send(AB.from_report(m), on_done=lambda res, k=m["key"]: done.__setitem__(k, res))
        if r in ("dup", "sent"):
            done.setdefault(m["key"], {"ok": True, "receipts": {"bus": r}})
    AB.drain(90)
    for m in msgs:
        res = done.get(m["key"]) or {}
        if res.get("ok"):
            rec["sent_n"] = int(rec.get("sent_n") or 0) + 1
            rec["alerts_last"] = {"t": snap["t"], "title": m["title"], "via": ",".join(_d(res.get("receipts")))}
        else:
            rec["errors"].append("alert: the alert bus could not deliver it (data/alert_bus.jsonl)")
            _forget(new_state, m)
    return True


def _app_push(m: dict) -> bool:
    """One report alert to the phone app (Olympus, engine/push.app_send with the PC's own key): True = a phone took it."""
    try:
        from engine import push as _push
        return bool(_push.app_send(_push.report_payload(m)).get("sent"))
    except Exception:  # noqa: BLE001
        return False


def _kind(m: dict) -> str:
    try:
        from engine import notify as _n
        return m.get("kind") or _n.kind_of(m.get("key"))
    except Exception:  # noqa: BLE001
        k = str(m.get("key") or "")
        return "trade_opened" if k.startswith("open:") else "trade_closed" if k.startswith("close:") else "other"


def _trade_alert(m: dict) -> bool:
    """A report alert about a trade's entry or result ("open:<acct>:<t>" / "close:<acct>:<t>"): it goes to ntfy too (2026-11-20)."""
    return _kind(m) in ("trade_opened", "trade_closed")


def _dual_alert(m: dict) -> bool:
    """An alert for BOTH phone routes (engine/notify.dual, 2026-11-20): a trade's entry / result, PASSED / FAILED / LOCKED / payout
    ready / a quiet eval (account_status), room low (when turned on), problems (bot down, NinjaTrader closed, FEED STALE, a fill
    check, a missed entry). Every other alert, "Back to normal" included: the phone app first, ntfy only when no phone took it."""
    try:
        from engine import notify as _n
        return _n.dual(_kind(m), m.get("key"))
    except Exception:  # noqa: BLE001
        return _trade_alert(m)


def _routes_mode() -> str:
    """notify_settings.json trade_routes: "both" (default) | "olympus" | "ntfy" (engine/notify.trade_routes). Never raises."""
    try:
        from engine import notify as _n
        return _n.trade_routes()
    except Exception:  # noqa: BLE001
        return "both"


def _app_had(m: dict) -> bool:
    """The bot's instant path already put this trade alert on the phone app and ntfy did not take it (engine/notify.instant_record
    app_only): the report sends only its ntfy copy (engine/notify.report_copy == "ntfy"). Per account: ATLAS's alert never counts for
    LIT's row on the same bar. The report's one "lit" row is titled the 50K, so only the 50K's own app-only alert earns that copy; an
    extra LIT account's (the 25K #2, the Rapid's LIT lane) makes notify.apply drop the row instead (skeptic 2026-11-20: it came back
    on ntfy as a false "Zlarior 50K opened / closed" with the 50K's day $ and room)."""
    try:
        from engine import notify as _n
        return _n.report_copy(m, kind=_kind(m)) == "ntfy"
    except Exception:  # noqa: BLE001
        return False


def _alert_app(m: dict, app_push, rec: dict, t) -> bool:
    """One report alert to the phone app (run_once): True = a phone took it. Never raises."""
    try:
        ok = bool(app_push(m))
    except Exception:  # noqa: BLE001
        ok = False
    if ok:
        rec["app_sent"] = int(rec.get("app_sent") or 0) + 1
        rec["alerts_last"] = {"t": t, "title": m["title"], "via": "app"}
    return ok


def _alert_ntfy(m: dict, cfg: dict, rec: dict, t, http=None) -> bool:
    """One report alert to the private ntfy topic (run_once): True = ntfy took it; a refusal goes to rec["errors"]."""
    ok, why = ntfy_post(cfg["ntfy"], cfg["topic"], m["body"], title=m["title"], priority=m.get("priority"), tags=m.get("tags"), http=http)
    if ok:
        rec["alerts_last"] = {"t": t, "title": m["title"]}
    else:
        rec["errors"].append("alert: " + why)
    return ok


# An app-had trade copy (the phone app got it at once, ntfy refused) is retried on ntfy every 15 minutes only while the trade event
# is this recent: after ntfy's day cap a late copy would land hours later, after the reset (skeptic 2026-11-20).
APP_HAD_RETRY_S = 2 * 3600


def run_once(work: str = WORK_DEFAULT, dry: bool = False, http=None, env=None, now=None, root: str = ROOT, port=PORT_DEFAULT,
             feed_problem=None, say=print, feed_path: str | None = None, app_push=None) -> dict:
    """One run. app_push(msg) -> True when the phone app took that alert (tests); None = the real one when this PC has a phone
    (only on a real run: a test's fake http never reaches the PC's own push files)."""
    os.makedirs(work, exist_ok=True)
    cfg = load_cfg(env, feed_path)
    snap = gather(now, root=root, env=env, http=http, port=port, feed_problem=feed_problem)
    if app_push is None and http is None:           # Olympus phone notifications, the real run: the PC's own push key (made once)
        try:                                        # + its phones ride the core post (wp); the alerts go to the phones first
            from engine import push as _push
            snap["wp"] = _push.app_block()
            if _d(snap.get("wp")).get("d"):
                app_push = _app_push
        except Exception:  # noqa: BLE001
            pass
    last = read_json(os.path.join(work, "last.json"), {}) or {}
    rec = {"t": snap["t"], "ok": True, "hb_t": snap.get("hb_t"), "server": snap.get("server"), "problems": sorted(conditions(snap)),
           "status_t": last.get("status_t"), "alerts_last": last.get("alerts_last"), "errors": [],
           # the Launch card (tools/launch_card.report_state) reads only this file: whether alerts go out, never the topic itself
           "alerts_on": bool(cfg["topic"]) and bool(cfg["on"])}
    if "wp" in snap:                                # the routes a trade alert has (2026-11-20): Olympus phones + the private ntfy topic
        rec["alert_routes"] = {"phones": len(_d(snap.get("wp")).get("d") or []), "ntfy": rec["alerts_on"]}
    status, exts = posts(snap)
    try:                                    # the trade alerts' account names (engine/mffu_view.push_name, engine/notify.entry_message)
        from engine import mffu_view
        mffu_view.save_names(mffu_view.compact(snap.get("live")), path=os.path.join(work, "names.json"))
    except Exception:
        pass
    posted = ext_n = 0                              # this run's public posts / ext posts (the chart's daily ntfy share counts them)
    for k in ("ext_t", "ext_h"):
        rec[k] = last.get(k)
    if snap.get("live"):
        write_json(os.path.join(work, "live.json"), snap["live"], compact=True)
    # status -> the public status topic (the site): the ext post(s) first when due, then the core (so since=latest is the core)
    if cfg["status_topic"] and status.get("t"):
        h = ext_hash(exts)
        due = bool(exts) and (h != last.get("ext_h") or not num(last.get("ext_t")) or snap["t"] - float(last["ext_t"]) >= EXT_EVERY_S)
        quota = None if dry else ntfy_quota(cfg["ntfy"], http=http)
        rec["ntfy_quota"] = quota
        if due and not dry and (day_used(work, snap["t"]) + len(exts) > NTFY_DAY_CAP - TRADE_ALERT_RESERVE or quota_holds(quota, len(exts))):
            due = False                               # the last room of ntfy's day stays for the trade alerts (this file's count OR ntfy's own)
            rec["ext_held"] = "ntfy budget: the last posts of the day are kept for trade alerts"
        for e in exts if due else []:
            body = json.dumps(e, separators=(",", ":"), default=str, ensure_ascii=False)
            if dry:
                say(f"[dry] status ext {e.get('part')} ({len(body.encode('utf-8'))} bytes: {', '.join(_d(e.get('x')))}) -> {cfg['ntfy']}/{cfg['status_topic']}")
                continue
            ok, why = ntfy_post(cfg["ntfy"], cfg["status_topic"], _signed(body, real=http is None), priority="min", http=http)
            if not ok:
                rec["errors"].append("status ext: " + why)
                due = False
                break
            posted += 1
            ext_n += 1
        if due and not dry:
            rec["ext_t"], rec["ext_h"] = snap["t"], h
        if num(rec.get("ext_t")):
            status["xt"] = int(rec["ext_t"])         # when the extras last went (readers merge the newest ext with this core)
        body = json.dumps(status, separators=(",", ":"), default=str, ensure_ascii=False)
        sig = core_sig(status)
        rec["core_sig"] = sig
        repeat = (not due and num(last.get("status_t")) and snap["t"] - float(last["status_t"]) < CORE_MIN_GAP_S
                  and last.get("core_sig") == sig)
        if dry:
            say(f"[dry] status ({len(body.encode('utf-8'))} bytes) -> {cfg['ntfy']}/{cfg['status_topic']}"
                + (" [would be skipped: same state posted under 5 min ago]" if repeat else ""))
        elif repeat:                                  # night-truth 2026-11-22: a 2nd run minutes after the last post (two tasks on the PC:
            rec["core_skipped"] = "same state posted under 5 min ago"   # posts came in pairs ~2 min apart) saves ntfy's day
        else:
            ok, why = ntfy_post(cfg["ntfy"], cfg["status_topic"], _signed(body, core=True, real=http is None), priority="min", http=http)
            if SIGN_STATE.get("why") and SIGN_STATE["why"] != "off (LE_STATUS_SIGN=0)":
                rec["unsigned"] = SIGN_STATE["why"]  # posted all the same; the run record says why it went unsigned
            if ok:
                rec["status_t"] = snap["t"]
                posted += 1
            else:
                rec["errors"].append("status: " + why)
    elif not status.get("t"):
        rec["errors"].append("status: the bot has never reported on this PC (nothing to show)")
    write_json(os.path.join(work, "status.json"), status, compact=True)
    write_json(os.path.join(work, "status_ext.json"), exts, compact=True)
    # alerts -> your private topic
    state = read_json(os.path.join(work, "state.json"), {}) or {}
    new_state, msgs = events(state, snap)
    sent = nposted = 0                              # every delivery / the alert posts that used ntfy's day (the chart's share)
    mode = _routes_mode()
    ntfy_on = bool(cfg["topic"]) and bool(cfg["on"])
    # engine/alert_bus (day-alerts 2026-11-21): set up = Telegram / Discord first (ntfy + the app its fallbacks); off = this loop, exactly
    bus_ok = _bus_alerts(msgs, rec, snap, new_state) if (not dry and http is None and app_push is not _NO_BUS) else None
    for m in (msgs if bus_ok is None else []):
        # 2026-11-20: a trade's entry / result and the important alerts (_dual_alert: PASSED / FAILED / LOCKED / payout ready, room
        # low, problems, PC silent) go to the phone app AND to ntfy (a push service's "accepted" is not proof the phone showed it);
        # every other alert: the phone app first, the ntfy copy only when no phone took it (as before). notify_settings.json
        # trade_routes "olympus" / "ntfy" puts one route first for those too (the other stays the fallback).
        dual = _dual_alert(m)
        both = dual and mode == "both"
        ntfy_first = dual and mode == "ntfy"
        trade = _trade_alert(m)
        had = trade and _app_had(m)                 # the instant path already put this trade on the phone app
        if dry:
            if app_push is not None:
                order = ("ntfy first, else the phone app (Olympus)" if ntfy_first else
                         f"the phone app (Olympus) {'and' if both else 'else'} ntfy")
                say(f"[dry] push -> {order} ({cfg['topic'] or 'no topic'}): {m['title']}: {m['body']}")
            elif ntfy_on:
                say(f"[dry] push -> {cfg['topic']}: {m['title']}: {m['body']}")
            continue
        took = had                                  # the phone app has it (at once, or in this run)
        nt = None                                   # ntfy: True / False, None = not tried
        if ntfy_first:
            nt = _alert_ntfy(m, cfg, rec, snap["t"], http) if ntfy_on else None
            if not nt and not had and app_push is not None:
                took = _alert_app(m, app_push, rec, snap["t"])
                sent += int(took)
        else:
            if not had and app_push is not None:
                took = _alert_app(m, app_push, rec, snap["t"])
                sent += int(took)
            if ntfy_on and (both or not took):
                nt = _alert_ntfy(m, cfg, rec, snap["t"], http)
        if nt:
            sent += 1
            nposted += 1
        if nt is False and (not took or (had and (both or ntfy_first) and snap["t"] - int(num(m.get("ev_t")) or snap["t"]) <= APP_HAD_RETRY_S)):
            # not on ntfy: forget it so the next run tries again (conditions keep their state; a trade key is retried). Once one
            # route took it in this run there is no retry (it would reach the phone app twice); an app-had trade copy is retried for
            # its ntfy copy only, for APP_HAD_RETRY_S
            if m["key"].startswith(("open:", "close:", "fill:", "watch:")):
                for k in m.get("keys") or [m["key"]]:
                    new_state["seen"].pop(k, None)
            elif m["key"].startswith("guard:"):
                _d(_d(new_state.get("guard")).get("sent")).pop(m["key"], None)
    if not dry:
        write_json(os.path.join(work, "state.json"), new_state)
    # the NQ page's live chart (le-bars, its own topic): after the core and the pushes, so it never takes their room; soft, and its
    # own problems stay in rec["bars"] (never in errors: the report itself is fine without it)
    try:
        rec["bars"] = bars_step(work, cfg, snap.get("live") if isinstance(snap.get("live"), dict) else {}, snap["t"],
                                bool(snap.get("market_open")), dry=dry, http=http, say=say, root=root, nt_folder=_nt_folder(root, env),
                                other_posts=0 if dry else posted + nposted, limited=any("rate limit" in str(e) for e in rec["errors"]),
                                feed_path=feed_path, busy_run=ext_n > 0, remaining=(rec.get("ntfy_quota") or {}).get("remaining"))
    except Exception as e:  # noqa: BLE001
        rec["bars"] = {"posted": False, "why": f"chart failed softly: {e.__class__.__name__}"}
    rec.update(sent=sent + int(rec.pop("sent_n", 0) or 0), queued=len(msgs), ok=not rec["errors"])
    if not dry:
        write_json(os.path.join(work, "last.json"), rec)
        log_line(work, {k: rec.get(k) for k in ("t", "ok", "hb_t", "server", "problems", "sent", "errors")})
    rec["card"] = card(snap, cfg, rec)
    return rec


CORE_MIN_GAP_S = 300             # a core post with the same state (core_sig) as one under 5 min old is not sent again


def core_sig(status: dict) -> str:
    """The state a reader acts on in a core post (running, verdict, problems, armed, badges, positions, trades today, account
    status), without the times and the $ that move every minute. Same sig = nothing new for the phone."""
    st = _d(status)
    bd = _d(st.get("board"))
    pc = _d(st.get("pc"))
    rp = _d(st.get("reporter"))
    key = {"run": pc.get("running"), "pos": pc.get("position"), "v": _d(st.get("pc_verdict")).get("code"),
           "srv": rp.get("server"), "nt": rp.get("nt"), "pr": rp.get("problems"), "ar": st.get("ar"),
           "c": [[k, _d(bd.get(k)).get("badge"), _d(bd.get(k)).get("status"), _d(bd.get(k)).get("trades_today"),
                  bool(_d(bd.get(k)).get("position"))] for k in ("lit", "atlas")],
           "a": [[_d(a).get("id"), _d(a).get("badge"), _d(a).get("running"), _d(_d(a).get("eval")).get("status"),
                  bool(_d(a).get("position"))] for a in (st.get("accounts") or [])]}
    import hashlib
    return hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


def count_posts(work: str, now, n: int = 1, kind: str = "pulse") -> None:
    """n more posts of this PC today in data/pc_report/bars.json (days[utc day]["all"] + [kind]): the chart's and the ext's
    daily share (day_used) see them. Never raises."""
    try:
        p = os.path.join(work, BARS_STATE)
        st = read_json(p, {}) or {}
        st = st if isinstance(st, dict) else {}
        days = {k: dict(v) for k, v in _d(st.get("days")).items() if isinstance(v, dict)}
        cnt = days.setdefault(_utc_day(now), {})
        cnt["all"] = int(num(cnt.get("all")) or 0) + int(n)
        cnt[kind] = int(num(cnt.get(kind)) or 0) + int(n)
        st["days"] = days
        write_json(p, st)
    except Exception:  # noqa: BLE001
        pass


def pulse_once(work: str = WORK_DEFAULT, why: str = "", dry: bool = False, http=None, env=None, now=None, root: str = ROOT,
               port=PORT_DEFAULT, feed_problem=None, say=print, feed_path: str | None = None) -> dict:
    """A state-change post (engine/state_pulse.py, `--pulse`): ONLY the core status post, at once; no ext, no chart, no alerts
    (the trade alerts go at once from the bot itself), last.json "t" untouched (the 15-minute cadence and the keeper go on as
    before). Held, never sent, when this PC already sent state_pulse.DAY_MAX pulses today or ntfy's day is down to the trade
    alert reserve (this PC's count or ntfy's own). -> {"posted", "held", "bytes"}"""
    from engine import state_pulse as SP
    res = {"posted": False, "held": None}
    cfg = load_cfg(env, feed_path)
    if not cfg["status_topic"]:
        res["held"] = "no status topic"
        return res
    t = int(now or time.time())
    pst = SP.read_state(work)
    if SP.day_count(pst, t) >= SP.DAY_MAX:
        res["held"] = f"ntfy budget: {SP.DAY_MAX} pulses today already"
        return res
    if not dry and day_used(work, t) + 1 > NTFY_DAY_CAP - TRADE_ALERT_RESERVE:
        res["held"] = "ntfy budget: the last posts of the day are kept for trade alerts"
        return res
    quota = None if dry else ntfy_quota(cfg["ntfy"], http=http)
    if quota_holds(quota, 0):
        res["held"] = "ntfy budget (ntfy's own count): the last posts of the day are kept for trade alerts"
        return res
    snap = gather(t, root=root, env=env, http=http, port=port, feed_problem=feed_problem)
    snap["pulse"] = snap["t"]
    if http is None:
        try:                                        # the phone app's push set-up rides every core post (as in run_once)
            from engine import push as _push
            snap["wp"] = _push.app_block()
        except Exception:  # noqa: BLE001
            pass
    status, _exts = posts(snap)
    last = read_json(os.path.join(work, "last.json"), {}) or {}
    if num(last.get("ext_t")):
        status["xt"] = int(last["ext_t"])
    if not status.get("t"):
        res["held"] = "the bot has never reported on this PC"
        return res
    body = json.dumps(status, separators=(",", ":"), default=str, ensure_ascii=False)
    res["bytes"] = len(body.encode("utf-8"))
    if dry:
        say(f"[dry] pulse status ({res['bytes']} bytes, {why or 'a change'}) -> {cfg['ntfy']}/{cfg['status_topic']}")
        return res
    ok, w = ntfy_post(cfg["ntfy"], cfg["status_topic"], _signed(body, core=True, real=http is None), priority="min", http=http)
    if not ok:
        res["held"] = "status: " + w
        return res
    res["posted"] = True
    SP.write_state({**SP.count_one(SP.read_state(work), t), "post_t": t, "post_why": str(why)[:120]}, work)
    count_posts(work, t, 1, "pulse")
    last.update(status_t=snap["t"], core_sig=core_sig(status), pulse_t=snap["t"])   # "t" (the run's time) is kept: the cadence
    write_json(os.path.join(work, "last.json"), last)
    write_json(os.path.join(work, "status.json"), status, compact=True)
    return res


def send_test(cfg: dict, http=None) -> tuple:
    return ntfy_post(cfg["ntfy"], cfg["topic"], "Reporting is back: this phone gets the bots' alerts from the PC (trade opened / closed, "
                     "FEED STALE, bot down).", title="Bots back: test", priority="default", tags="white_check_mark", http=http)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Report the PC bots to the phone without GitHub (ntfy.sh, free).")
    ap.add_argument("--work", default=WORK_DEFAULT)
    ap.add_argument("--port", type=int, default=PORT_DEFAULT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--card", action="store_true")
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="no card (the scheduled task)")
    ap.add_argument("--again", action="store_true", help="with --test: send the test push again")
    ap.add_argument("--bars", action="store_true", help="only the NQ chart post (le-bars), from the last run's live.json")
    ap.add_argument("--pulse", action="store_true", help="only the core status post, at once (a bot state change: engine/state_pulse.py)")
    ap.add_argument("--why", default="", help="with --pulse: what changed (plain words, for the record)")
    a = ap.parse_args(argv)
    if a.pulse:                        # exit 3 = another report run is busy: the pulse tries again after its debounce
        lk = None if a.dry_run else run_lock(a.work)
        if not a.dry_run and lk is None:
            return 3
        try:
            r = pulse_once(work=a.work, why=a.why, dry=a.dry_run, port=a.port, say=(lambda *_: None) if a.quiet else print)
        finally:
            run_unlock(lk)
        if not a.quiet:
            print("  [OK]  pulse posted" if r.get("posted") else f"  [..]  pulse not posted: {r.get('held')}")
        return 0
    if a.setup or a.test:
        try:
            cfg = ensure_topic()
        except Exception as e:
            print(f"  [FIX] could not save the alert topic: {e.__class__.__name__}: {e}")
            return 0
        print(f"  [OK]  your phone alert topic: {cfg['topic']}   (saved in {cfg['path']}, outside the repo)")
        if a.test:
            if (cfg.get("tested") or {}).get("topic") == cfg["topic"] and not a.again:
                print("  [OK]  test push was sent before for this topic (nothing sent now)")
                return 0
            ok, why = send_test(cfg)
            print("  [OK]  test push sent: it shows on the phone once you subscribed to the topic" if ok else f"  [SKIP] test push not sent: {why}")
            if ok:
                mark_tested(cfg)
        return 0
    if a.card:
        cfg = load_cfg()
        snap = gather(port=a.port)
        print(card_text(card(snap, cfg, read_json(os.path.join(a.work, "last.json"), {}) or {})))
        return 0
    if a.bars:                         # the chart post alone (a cheap 5-minute caller): the same pacing and daily share as a full run
        lk = None if a.dry_run else run_lock(a.work)
        if not a.dry_run and lk is None:
            return 0
        try:
            now = now_s()
            r = bars_step(a.work, load_cfg(), read_json(os.path.join(a.work, "live.json"), {}) or {}, now, market_open(now),
                          dry=a.dry_run, say=(lambda *_: None) if a.quiet else print)
        finally:
            run_unlock(lk)
        if not a.quiet:
            print(f"  [{'OK' if r.get('posted') else '..'}]  NQ chart: " + (f"posted {r.get('n')} bars ({r.get('bytes')} bytes)"
                                                                         if r.get("posted") else r.get("why") or "nothing to do"))
        return 0
    lk = None if a.dry_run else run_lock(a.work)
    if not a.dry_run and lk is None:
        if not a.quiet:
            print("  [OK]  another report run is busy right now (the 15-minute task or the bot server): nothing to do")
        return 0
    if not a.dry_run:                  # the real report run: the morning brief may post its one Board event (tools/morning_brief.py)
        os.environ["LE_PC_REPORT"] = "1"
    try:
        rec = run_once(work=a.work, dry=a.dry_run, port=a.port)
    finally:
        run_unlock(lk)
    if not a.quiet:
        print(card_text(rec["card"]))
        for e in rec.get("errors") or []:
            print(f"  [..] {e}")
    # the Sunday money report (tools/weekly_money_report.py): once a week, Sunday from 17:00 ET, on your private topic; soft, never stops this run
    if not a.dry_run:
        try:
            from tools import weekly_money_report as _wmr
            _wmr.maybe_run(say=(lambda *_: None) if a.quiet else print)
        except Exception:
            pass
        # your day (tools/calendar_sync.py, docs/CONNECT_DAY.md): your calendars -> data/day/day.json every 15 minutes, only once
        # you connected one (CONNECT_DAY.bat); private, read by the phone through the PC's own link; soft, never stops this run
        try:
            from tools import calendar_sync as _cal
            _cal.maybe_run(say=(lambda *_: None) if a.quiet else print)
        except Exception:
            pass
        # the Me hub (tools/me_hub.py, docs/ME_HUB.md): home WiFi / devices / this PC, the Apple Watch days, data/me/me.json for the phone's
        # Me hub (private, the PC's own link only) and its reminders (cards due, dates, car, a new device) on your private topic; soft
        try:
            from tools import me_hub as _me
            _me.maybe_run(say=(lambda *_: None) if a.quiet else print)
        except Exception:
            pass
        # nightly learning (engine/learn_loop.py, docs/LEARN_LOOP.md): after 17:00 ET on weekdays and at the weekend, once a day, only
        # when flat; a detached below-normal child that backtests + runs queued experiments. Research only, never a live setting; soft
        try:
            from engine import learn_loop as _ll
            _ll.maybe_run(say=(lambda *_: None) if a.quiet else print)
        except Exception:
            pass
        # Obsidian living sync (tools/obsidian_sync.py, docs/OBSIDIAN_SYNC.md): the bots' day, trades + pictures, research, business,
        # STATE into <vault>/OLYMPUS/Sync, only once you set a vault (data/obsidian_sync.json); at most every 10 min; soft
        try:
            from tools import obsidian_sync as _obs
            _obs.maybe_run(say=(lambda *_: None) if a.quiet else print)
        except Exception:
            pass
        # ZEUS edge light (tools/edge_pc.py): once a day after 17:00 ET a detached low-priority `tools/edge_health.py --pc` (LIT on the
        # PC's own bars, ~30 s) -> data/edge/tiny.json = the status "eh" above. Research only, never a bot setting; LE_EDGE=0 = off; soft
        try:
            from tools import edge_pc as _ep
            _ep.maybe_run(say=(lambda *_: None) if a.quiet else print)
        except Exception:
            pass
        # Kalshi rewards PAPER test (tools/kalshi_rewards_paper.py, owner 2026-11-17): keeps one detached low-priority child running
        # (public Kalshi data, GET only, never an order); ledger + public summary in data/kalshi_rewards/; LE_KALSHI_REWARDS=0 = off; soft
        try:
            from tools import kalshi_rewards_paper as _krp
            _krp.maybe_run(say=(lambda *_: None) if a.quiet else print)
        except Exception:
            pass
        # Kalshi K1 rules PAPER test (tools/kalshi_paper.py: weather lock + NQ hourly model; public data, GET only, never an order);
        # same pattern: one detached child, ledger + public summary in data/kalshi_k1/; LE_KALSHI_K1=0 = off; soft
        try:
            from tools import kalshi_paper as _kp1
            _kp1.maybe_run(say=(lambda *_: None) if a.quiet else print)
        except Exception:
            pass
        # Kalshi K8 clock bot (engine/kalshi_clock.py + engine/kalshi_live.py): keeps the paper loop running and brings the LIVE
        # loop back after a PC restart ONLY while the owner's typed phrase is on record; OFF by default; never touches the futures bot
        try:
            from engine import kalshi_live as _klv
            _klv.maybe_run(say=(lambda *_: None) if a.quiet else print)
        except Exception:
            pass
        # self-heal (engine/self_heal.py, docs/SELF_HEAL.md), LAST: it may run pip for a few minutes. At most once an hour the known PC
        # faults get their logged remedy (stale git lock, a file in the update's way, stuck order files, stale pid, missing packages,
        # clock) + the weekly disk clean; one alert only when it could NOT fix something. Never starts, stops, arms or routes the bot; LE_SELF_HEAL=0 = off; soft
        try:
            from engine import self_heal as _sh
            _sh.maybe_run(say=(lambda *_: None) if a.quiet else print)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as e:                         # the scheduled task never shows a crash
        print("PC report failed softly:", f"{e.__class__.__name__}: {str(e)[:200]}")
        sys.exit(0)
