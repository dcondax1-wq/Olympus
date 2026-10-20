"""Bot Control center for the PC dashboard (web_next/js/next/botctl.js): one START button, an automatic preflight checklist,
the live status strip and the safety switches. Mounted by engine/next_api.py (router.include_router).

Every action goes through the SAME functions as the command line, and every live lock stays where it was:
  POST /api/next/botctl/start       {account, confirm?, present?}  = python -m engine.ninjatrader --start --account X [--confirm ...]
                                    (the same start body, the extra accounts of data/accounts.json merged in the same way, then
                                    server.py's start hook = POST /api/live/start: BOT.start + the autostart record with the phrase
                                    stripped). A Sim account starts with one click. A real account is refused here unless the
                                    owner typed the confirm phrase in the dialog (exact), ticked "I am at the PC" and the server
                                    runs with NINJATRADER_LIVE=1; the NinjaTrader adapter's own _live_gate then checks it again.
  POST /api/next/botctl/stop        = POST /api/live/stop (server hook: clears the autostart record)
  POST /api/next/botctl/autoupdate  {on}  = python -m engine.autoupdate --enable / --disable
  POST /api/next/botctl/autoresume  {on: false}  = --disable-auto-resume; {on: true, account, confirm} = --enable-auto-resume
                                    (engine/autoresume.enable: only a SHA-256 proof is stored), then a start when the bot is
                                    stopped, exactly as the CLI does
  POST /api/next/botctl/restart     restart server.py (exit code 75: scripts/run_bot.ps1 starts it again at once); refused
                                    while not flat or when no supervisor runs the server (LE_SUPERVISED=1, set by run_bot.ps1)
  POST /api/next/botctl/selftest    python -m engine.ninjatrader --selftest in a SUBPROCESS (it sets NINJATRADER_LIVE=1 inside
                                    its own process; never in the server's)
  The kill switch stays POST /api/live/kill (HOLD TO KILL: flattens, stops, clears autostart, turns auto-resume off).

Read-only:
  GET /api/next/botctl/status?account=X   status strip + preflight rows (green / red / amber, each red row with its one fix in
                                          plain words) + the accounts NinjaTrader reports + switches state + version
  GET /api/next/botctl/plan               today's LIT plan (engine/lit_brief.build on data/NQ_5m.csv + the bot's own bars)
  GET /api/next/botctl/switches           the adopt-candidates (t_check, scale_in, be_off) with their tested numbers from
                                          research/lit/adopt_combo.json and on/off from live_model.json. No way to switch them.

The confirm phrase: never stored, never logged, never echoed. Request bodies are read once; every response passes scrub(),
which drops any "confirm" / "phrase" key and replaces the phrase text wherever it would appear (e.g. an adapter refusal).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import Response

from . import accounts

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_ENV = "NINJATRADER_LIVE"
SUPERVISED_ENV = "LE_SUPERVISED"            # scripts/run_bot.ps1 sets it: a restart (exit 75) comes straight back
SELFTEST_MAX_AGE_S = 30 * 60
REDACT = "<the confirm phrase>"
router = APIRouter()
_lock = threading.Lock()
_cache: dict = {}

# server.py fills these (the same code paths as POST /api/live/start, /api/live/stop, the heartbeat thread, a restart)
HOOKS: dict = {"start": None, "stop": None, "heartbeat": None, "exit": None}
SELFTEST: dict = {"t": None, "ok": None, "running": False, "summary": None, "secs": None}


def _J(obj, status=200):
    return Response(json.dumps(scrub(obj), separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _bot():
    """The PC bot (tests replace this function)."""
    from .live import BOT
    return BOT


def _phrase() -> str:
    from .tradovate import LIVE_PHRASE
    return LIVE_PHRASE


def _lm() -> dict:
    try:
        with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _now(bot=None) -> int:
    try:
        return int(bot.clock()) if bot is not None else int(time.time())
    except Exception:
        return int(time.time())


def scrub(obj):
    """Any response / record of this module: no "confirm" / "phrase" key, the phrase text replaced wherever it appears."""
    ph = _phrase()
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if str(k).lower() not in ("confirm", "phrase")}
    if isinstance(obj, (list, tuple)):
        return [scrub(v) for v in obj]
    if isinstance(obj, str) and ph and ph in obj:
        return obj.replace(ph, REDACT)
    return obj


def is_sim(name) -> bool:
    from .ninjatrader import is_sim as _s
    return _s(name)


def _valid_name(name) -> bool:
    n = str(name or "").strip()
    return bool(n) and len(n) <= 64 and not any(c in n for c in ";|\r\n\t\"'<>")


# ------------------------------------------------------------------------------------------------ NinjaTrader probes
def nt_folder(bot=None) -> str:
    from .ninjatrader import default_folder
    cfg = getattr(bot, "cfg", None) or {}
    return cfg.get("nt_folder") or default_folder()


def _listing(path) -> list:
    try:
        return os.listdir(path)
    except OSError:
        return []


def folder_probe(folder: str, now=None) -> dict:
    """What is in Documents\\NinjaTrader 8: incoming / outgoing, leftovers NinjaTrader did not pick up, connection files."""
    now = time.time() if now is None else now
    inc, out = os.path.join(folder, "incoming"), os.path.join(folder, "outgoing")
    res = {"folder": accounts.clean_text(folder, 80), "exists": os.path.isdir(folder), "incoming": os.path.isdir(inc),
           "outgoing": os.path.isdir(out), "leftovers": 0, "oldest_leftover_s": None, "connections": {}, "positions": []}
    if res["incoming"]:
        ages = []
        for n in _listing(inc):
            if n.lower().startswith("oif"):
                try:
                    ages.append(now - os.path.getmtime(os.path.join(inc, n)))
                except OSError:
                    pass
        res["leftovers"] = len(ages)
        res["oldest_leftover_s"] = int(max(ages)) if ages else None
    if res["outgoing"]:
        for n in _listing(out):
            low = n.lower()
            if not low.endswith(".txt"):
                continue
            if low.endswith("_position.txt"):
                parts = n[:-len("_position.txt")].rsplit("_", 1)
                if len(parts) == 2 and _valid_name(parts[1]):
                    res["positions"].append({"instrument": accounts.clean_text(parts[0], 40), "account": parts[1]})
                continue
            try:
                with open(os.path.join(out, n), encoding="utf-8", errors="replace") as fh:
                    v = fh.read(64).strip().upper()
            except OSError:
                continue
            if v in ("CONNECTED", "DISCONNECTED"):
                res["connections"][accounts.clean_text(n[:-4], 40)] = v
    return res


def feed_probe(folder: str, now=None) -> dict:
    """LE_BarFeed's MNQ 5m + 1m files: {tf: {ok, age_s, last_t, why}} (NinjaTraderBars, the bot's own reader; no Yahoo)."""
    from .ninjatrader import NinjaTraderBars
    now = int(time.time() if now is None else now)
    feed = NinjaTraderBars(folder)
    out = {}
    for tf, secs in (("5m", 300), ("1m", 60)):
        try:
            df, why, _full = feed.recent_bars("NQ", tf, "1d", now=now)
        except TypeError:
            df, why, _full = feed.recent_bars("NQ", tf, "1d")
        except Exception as e:
            df, why = None, f"{e.__class__.__name__}: {e}"
        if df is None or not len(df):
            out[tf] = {"ok": False, "age_s": None, "last_t": None, "why": accounts.clean_text(why, 160)}
            continue
        last = int(df["time"].iloc[-1])
        out[tf] = {"ok": True, "age_s": max(0, now - last - secs), "last_t": last, "bars": int(len(df)),
                   "why": accounts.clean_text(why, 160)}
    return out


# ------------------------------------------------------------------------------------------------ accounts
def discover_accounts(bot=None, probe: dict | None = None) -> list:
    """Every account the owner can start on: Sim101 (always), the accounts NinjaTrader reports (outgoing position files), the
    one the bot runs on, NINJATRADER_ACCOUNT, the auto-resume opt-in and the extra accounts (data/accounts.json)."""
    rows: dict = {}

    def add(name, src, **kw):
        if not _valid_name(name):
            return
        name = str(name).strip()
        r = rows.setdefault(name, {"name": name, "sim": is_sim(name), "sources": [], "extra": False})
        if src not in r["sources"]:
            r["sources"].append(src)
        r.update({k: v for k, v in kw.items() if v is not None})

    add("Sim101", "default")
    for p in (probe or {}).get("positions") or []:
        add(p.get("account"), "NinjaTrader")
    cfg = getattr(bot, "cfg", None) or {}
    ad = getattr(bot, "adapter", None)
    if cfg.get("adapter") == "ninjatrader":
        add(getattr(ad, "account", None) or cfg.get("nt_account") or "Sim101", "running")
    if os.environ.get("NINJATRADER_ACCOUNT"):
        add(os.environ["NINJATRADER_ACCOUNT"], "NINJATRADER_ACCOUNT")
    try:
        from . import autoresume
        st = autoresume.status()
        if st.get("account"):
            add(st["account"], "auto-resume")
    except Exception:
        pass
    try:
        from . import multi_account
        for x in multi_account.load_file():
            if x.get("nt_account"):
                add(x["nt_account"], "extra account", extra=True, extra_id=accounts.clean_text(x.get("id"), 40),
                    extra_enabled=x.get("enabled", True) is not False, extra_name=accounts.clean_text(x.get("name"), 60))
    except Exception:
        pass
    out = list(rows.values())
    for r in out:
        r["label"] = "SIM" if r["sim"] else "LIVE"
        r["running"] = "running" in r["sources"] and bool(getattr(bot, "running", False))
    out.sort(key=lambda r: (not r["running"], r["extra"], not r["sim"], r["name"]))     # running, Sim, real, extras
    return out


# ------------------------------------------------------------------------------------------------ self-test (subprocess)
def _selftest_run():
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-m", "engine.ninjatrader", "--selftest", "--quiet"], cwd=ROOT,
                           capture_output=True, text=True, timeout=180, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        ok = p.returncode == 0
        tail = [ln for ln in (p.stdout or "").splitlines() if ln.strip()][-2:]
        summary = accounts.clean_text(" | ".join(tail) or ("all checks passed" if ok else (p.stderr or "failed")[-160:]), 200)
    except Exception as e:
        ok, summary = False, accounts.clean_text(f"{e.__class__.__name__}: {e}", 160)
    with _lock:
        SELFTEST.update(t=int(time.time()), ok=ok, running=False, summary=summary, secs=round(time.time() - t0, 1))


def selftest(start: bool = False, wait: bool = False) -> dict:
    """The cached self-test result; start=True runs it in the background (once at a time)."""
    th = None
    with _lock:
        if start and not SELFTEST["running"]:
            SELFTEST["running"] = True
            th = threading.Thread(target=_selftest_run, name="botctl-selftest", daemon=True)
    if th is not None:
        th.start()
        if wait:
            th.join(200)
    with _lock:
        return dict(SELFTEST)


# ------------------------------------------------------------------------------------------------ windows / clock
def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def entry_window(now, lm: dict | None = None) -> dict:
    """LIT entries 02:00-15:30 ET (live_model.json lit.window), Mon-Fri: open now, or when it opens next."""
    lm = lm if lm is not None else _lm()
    wins = ((lm.get("lit") or {}).get("window") or [[120, 930]])
    e = _et(now)
    mod = e.hour * 60 + e.minute
    for d in range(0, 8):
        day = (e + dt.timedelta(days=d)).date()
        if day.weekday() >= 5:
            continue
        for a, z in wins:
            a, z = int(a), int(z)
            if d == 0 and a <= mod < z:
                close = dt.datetime(day.year, day.month, day.day, z // 60, z % 60, tzinfo=ET)
                return {"open": True, "until_t": int(close.timestamp()), "text": f"open now, closes {z // 60:02d}:{z % 60:02d} ET",
                        "in_s": 0}
            if d == 0 and mod >= a:
                continue
            start = dt.datetime(day.year, day.month, day.day, a // 60, a % 60, tzinfo=ET)
            lbl = "today" if d == 0 else "tomorrow" if d == 1 else f"{start:%a}"
            return {"open": False, "next_t": int(start.timestamp()), "in_s": int(start.timestamp() - now),
                    "text": f"next {lbl} {a // 60:02d}:{a % 60:02d} ET"}
    return {"open": False, "text": "—"}


# ------------------------------------------------------------------------------------------------ eval / sizing
def eval_block(bot, now) -> dict | None:
    """The eval meter (balance, $ to target, room to the floor, sessions left) from the Accounts page's own view."""
    try:
        from . import pcdash_api
        ac = pcdash_api.account_view(bot, now=now, bars=False)
        ev = ac.get("eval") or None
        if not ev:
            return None
        keep = ("balance", "profit", "prior", "start", "to_target", "target_balance", "progress", "floor", "room", "mll", "locked",
                "session", "sessions", "status", "clock_text", "dll", "dll_used")
        out = {k: ev.get(k) for k in keep if k in ev}
        n, s = int(out.get("sessions") or 10), int(out.get("session") or 0)
        out["sessions_left"] = max(0, n - s) if s else None
        out["sizing"] = ac.get("sizing")
        return out
    except Exception as e:
        return {"error": accounts.clean_text(f"{e.__class__.__name__}: {e}", 120)}


# ------------------------------------------------------------------------------------------------ status strip
def strip_view(bot, now, health: dict | None = None, lm: dict | None = None) -> dict:
    h = health if health is not None else accounts.pc_health(bot, now)
    a, f, lit = h.get("account") or {}, h.get("feed") or {}, h.get("lit") or {}
    st = getattr(bot, "state", None) or {}
    pos = st.get("position") if isinstance(st.get("position"), dict) else None
    pv = None
    if pos:
        try:
            from . import pcdash_api
            p = pcdash_api._position_view(bot, pos, now) or {}
            d = int(p.get("dir") or 0)
            pv = {"side": "LONG" if d > 0 else "SHORT" if d < 0 else p.get("side"), "qty": p.get("qty"), "entry": p.get("entry"),
                  "stop": p.get("stop"), "target": p.get("target"), "be": bool(p.get("be")), "unrealized_usd": p.get("unrealized_usd"),
                  "unrealized_r": p.get("unrealized_r_now"), "entry_t": p.get("entry_t")}
        except Exception:
            pv = {"side": "?", "qty": pos.get("qty")}
    try:
        day_pnl = float(bot.day_pnl_routed()) if getattr(bot, "cfg", None) else 0.0
    except Exception:
        day_pnl = None
    hb = None
    fn = HOOKS.get("heartbeat")
    if callable(fn):
        try:
            s = fn() or {}
            last = s.get("last") or {}
            hb = {"enabled": bool(s.get("enabled")), "at": accounts._i(last.get("at")), "ok": last.get("ok"),
                  "age_s": (now - int(last["at"])) if last.get("at") else None,
                  "error": accounts.clean_text(last.get("error"), 120)}
        except Exception as e:
            hb = {"error": accounts.clean_text(f"{e.__class__.__name__}: {e}", 120)}
    return {"running": bool(getattr(bot, "running", False)), "kill": bool(getattr(bot, "kill", False)),
            "account": a.get("name"), "label": a.get("label"), "is_live": bool(a.get("is_live")), "adapter": a.get("adapter"),
            "enabled": a.get("enabled"), "disabled": a.get("disabled"),
            "position": pv, "day_pnl": day_pnl, "trades_today": (h.get("orders") or {}).get("entries_today"),
            "last_signal": lit.get("last_setup"), "stage": lit.get("stage"), "stage_text": lit.get("text"),
            "window": entry_window(now, lm), "feed": {"age_1m_s": f.get("age_1m_s"), "age_5m_s": f.get("age_5m_s"),
                                                      "stale": f.get("stale"), "blocked": f.get("entries_blocked"),
                                                      "market_open": f.get("market_open"), "source": f.get("used")},
            "heartbeat": hb, "started_at": accounts._i(getattr(bot, "started_at", None)),
            "uptime_s": (h.get("uptime") or {}).get("bot_s")}


# ------------------------------------------------------------------------------------------------ preflight
def _row(rid, label, ok, detail="", fix="", group="broker"):
    """ok: True green, False red (blocks Start), None amber (info / warning, does not block)."""
    return {"id": rid, "label": label, "ok": ok, "detail": accounts.clean_text(detail, 200) if detail else "",
            "fix": accounts.clean_text(fix, 220) if fix else "", "group": group}


def _ago(s):
    if s is None:
        return "—"
    s = int(s)
    return f"{s} s" if s < 90 else f"{s // 60} min" if s < 5400 else f"{s / 3600:.1f} h" if s < 172800 else f"{s // 86400} d"


def preflight(bot, account: str, now: int, lm: dict | None = None, env=None, probe=None, feed=None, st=None) -> dict:
    """The checklist the owner sees before Start, for one account. Red rows block Start (the button stays off)."""
    env = os.environ if env is None else env
    lm = lm if lm is not None else _lm()
    account = str(account or "Sim101").strip()
    sim = is_sim(account)
    from .live import market_open
    mopen = market_open(now)
    probe = probe if probe is not None else folder_probe(nt_folder(bot), now)
    feed = feed if feed is not None else feed_probe(nt_folder(bot), now)
    st = st if st is not None else selftest()
    rows = []
    # strategy
    model = (getattr(bot, "cfg", None) or {}).get("model") or lm.get("model")
    rows.append(_row("strategy", "Strategy = LIT", model == "lit", f"live_model.json model: {lm.get('model')}"
                     + (f", the running bot: {model}" if model != lm.get("model") else ""),
                     "live_model.json must say \"model\": \"lit\" (the locked strategy); the old engine is the shadow only", "bot"))
    rows.append(_row("account", "Account name", _valid_name(account), f"{account} · {'Sim (practice money)' if sim else 'REAL account (your eval)'}",
                     "pick the account exactly as NinjaTrader's Accounts tab shows its Name", "bot"))
    # NinjaTrader
    rows.append(_row("folder", "NinjaTrader folder found", probe["exists"],
                     "Documents\\NinjaTrader 8 found" if probe["exists"] else "not found (Documents\\NinjaTrader 8 or NINJATRADER_FOLDER)",
                     "install / open NinjaTrader 8 once on this Windows user (Documents\\NinjaTrader 8), or set NINJATRADER_FOLDER"))
    ati = probe["incoming"] and probe["outgoing"]
    stuck = probe["leftovers"] and (probe["oldest_leftover_s"] or 0) > 30
    rows.append(_row("ati", "ATI reachable (incoming / outgoing)", bool(ati and not stuck),
                     ("incoming + outgoing found" if ati else f"incoming {'ok' if probe['incoming'] else 'MISSING'}, outgoing {'ok' if probe['outgoing'] else 'MISSING'}")
                     + (f"; {probe['leftovers']} order file(s) not picked up for {_ago(probe['oldest_leftover_s'])}" if probe["leftovers"] else ""),
                     "in NinjaTrader: Tools > Options > Automated trading interface > tick 'AT Interface', then restart NinjaTrader"
                     if not stuck else "NinjaTrader is not reading order files: turn the AT Interface on and keep NinjaTrader open"))
    conns = probe["connections"]
    up = [k for k, v in conns.items() if v == "CONNECTED"]
    rows.append(_row("connection", "Connection CONNECTED", bool(up),
                     (", ".join(f"{k} {v}" for k, v in conns.items()) or "no connection file yet"),
                     "in NinjaTrader: Connections > connect your MFFU / Tradovate login (or the Sim connection for Sim101)"))
    known = any(p["account"] == account for p in probe["positions"])
    if not sim:
        rows.append(_row("acct_seen", "NinjaTrader reports this account", True if known else None,
                         "position file found in outgoing" if known else "no position file for it yet (normal before its first trade)",
                         "check the Name in NinjaTrader's Accounts tab: it must match exactly"))
    # feed (no Yahoo)
    noy = lm.get("no_yahoo", True) is not False
    rows.append(_row("noyahoo", "No Yahoo (NinjaTrader bars only)", bool(noy), "live_model.json no_yahoo: " + str(lm.get("no_yahoo")),
                     "live_model.json \"no_yahoo\": true (owner 2026-10-19)", "feed"))
    for tf, lim in (("5m", 420), ("1m", 180)):
        fb = feed.get(tf) or {}
        if not fb.get("ok"):
            rows.append(_row(f"feed{tf}", f"Bar feed {tf} fresh", False, fb.get("why") or "no file",
                             f"put LE_BarFeed on an MNQ {'5-minute' if tf == '5m' else '1-minute'} chart in NinjaTrader (ninjatrader/SETUP.md) "
                             "and load at least 30 days", "feed"))
            continue
        age = fb.get("age_s")
        fresh = age is not None and age <= lim
        rows.append(_row(f"feed{tf}", f"Bar feed {tf} fresh", True if fresh else (False if mopen else None),
                         f"last bar {_ago(age)} old" + ("" if mopen else " · market closed (fresh again at the open)"),
                         "keep the MNQ chart with LE_BarFeed open in NinjaTrader; a stale feed blocks new entries (FEED STALE)", "feed"))
    # self-test
    if st.get("ok") is None:
        rows.append(_row("selftest", "Self-test", None, "running…" if st.get("running") else "not run yet",
                         "press Run self-test (about 2 s)", "bot"))
    else:
        age = now - int(st["t"]) if st.get("t") else None
        rows.append(_row("selftest", "Self-test pass", bool(st["ok"]),
                         f"{st.get('summary') or ''} · {_ago(age)} ago" if age is not None else (st.get("summary") or ""),
                         "the NinjaTrader route self-test failed: do not start, update the bot (git pull) and run it again", "bot"))
    # live lock
    lock = env.get(LIVE_ENV, "") == "1"
    if sim:
        rows.append(_row("livelock", "NINJATRADER_LIVE (real accounts only)", True, "not needed for a Sim account"
                         + (" · set on this server" if lock else " · not set (real accounts are refused)"), "", "safety"))
    else:
        rows.append(_row("livelock", "NINJATRADER_LIVE set", lock, "set to 1 for this server" if lock else "not set: a real account is refused",
                         "only when you trade the eval yourself: set NINJATRADER_LIVE in .env.local.ps1 as docs/GO_LIVE_TONIGHT.md shows, "
                         "then restart run_bot.ps1",
                         "safety"))
    kill = bool(getattr(bot, "kill", False))
    rows.append(_row("kill", "Kill flag clear", not kill, "kill switch used today: orders stay blocked" if kill else "clear",
                     "the kill switch was used today: the bot routes nothing until tomorrow's session (or delete data/live_state.json "
                     "after you checked NinjaTrader is flat)", "safety"))
    running = bool(getattr(bot, "running", False))
    # running is not a fault: the page shows STOP instead of START (amber = "stop first to switch account")
    rows.append(_row("running", "Bot state", None if running else True, "running: STOP first to switch account" if running else "stopped, ready to start",
                     "", "bot"))
    # info rows (amber/green, never block)
    ls = lm.get("lit_sizing") or {}
    ev = eval_block(bot, now) or {}
    rows.append(_row("sizing", "Sizing mode", True,
                     f"{ls.get('mode', '—')} · eval session {ev.get('session') or '—'} of {ev.get('sessions') or ls.get('two_week_until') or 10}"
                     + (f" · ${ev['to_target']:,.0f} to go" if isinstance(ev.get("to_target"), (int, float)) else "")
                     + (f" · room ${ev['room']:,.0f}" if isinstance(ev.get("room"), (int, float)) else ""), "", "info"))
    au = {}
    try:
        from . import autoupdate
        au = autoupdate.status()
    except Exception:
        pass
    ar = {}
    try:
        from . import autoresume
        ar = autoresume.status()
    except Exception:
        pass
    rows.append(_row("auto", "Auto-update / auto-resume", True,
                     f"auto-update {'ON' if au.get('on') else 'off'} · auto-resume {'ON for ' + str(ar.get('account')) if ar.get('on') else 'off'}"
                     + (" (Sim accounts always resume by themselves)" if sim else ""), "", "info"))
    rows.append(_row("version", "Version", True if au.get("sha") else None,
                     f"{au.get('sha') or 'unknown'} on {au.get('branch') or '?'}", "", "info"))
    blocking = [r for r in rows if r["ok"] is False]
    return {"account": account, "sim": sim, "rows": rows, "ok": not blocking, "red": len(blocking),
            "amber": sum(1 for r in rows if r["ok"] is None), "green": sum(1 for r in rows if r["ok"] is True),
            "market_open": mopen, "needs_phrase": not sim, "live_lock": lock}


# ------------------------------------------------------------------------------------------------ status (one call)
def status_view(bot, account: str | None = None, now: int | None = None, env=None, lm=None) -> dict:
    now = int(now or _now(bot))
    lm = lm if lm is not None else _lm()
    folder = nt_folder(bot)
    probe = folder_probe(folder, now)
    feed = feed_probe(folder, now)
    st = selftest()
    if st.get("ok") is None and not st.get("running") or (st.get("t") and now - int(st["t"]) > SELFTEST_MAX_AGE_S and not st.get("running")):
        st = selftest(start=True)           # automatic: the preflight runs the self-test by itself (subprocess, ~2 s)
    accts = discover_accounts(bot, probe)
    cfg = getattr(bot, "cfg", None) or {}
    if not account:
        cur = next((r for r in accts if r["running"]), None)
        account = cur["name"] if cur else (cfg.get("nt_account") or "Sim101")
    health = accounts.pc_health(bot, now)
    au, ar = {}, {}
    try:
        from . import autoupdate
        au = autoupdate.status()
    except Exception as e:
        au = {"error": accounts.clean_text(e, 120)}
    try:
        from . import autoresume
        ar = autoresume.status()
    except Exception as e:
        ar = {"error": accounts.clean_text(e, 120)}
    return {"t": now, "strip": strip_view(bot, now, health, lm), "preflight": preflight(bot, account, now, lm, env, probe, feed, st),
            "accounts": accts, "ninjatrader": {"folder": probe["folder"], "connections": probe["connections"], "feed": feed},
            "selftest": st, "eval": eval_block(bot, now),
            "auto": {"update": {"on": bool(au.get("on")), "sha": au.get("sha"), "branch": au.get("branch"), "result": au.get("result"),
                                "reason": accounts.clean_text(au.get("reason"), 160), "last_check_t": au.get("last_check_t")},
                     "resume": {"on": bool(ar.get("on")), "account": ar.get("account"), "off_reason": accounts.clean_text(ar.get("off_reason"), 120),
                                "last_t": ar.get("last_t"), "last_result": ar.get("last_result")}},
            "restart": {"supervised": os.environ.get(SUPERVISED_ENV) == "1", "flat": _flat_reason(bot) is None,
                        "why_not": _restart_block(bot)},
            "health_auto": health.get("auto")}


# ------------------------------------------------------------------------------------------------ actions
def start_body(account: str, confirm: str = "", folder: str | None = None, data: str = "ninjatrader") -> dict:
    """The exact body `python -m engine.ninjatrader --start --account X [--confirm ...]` posts to /api/live/start."""
    body = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "present": True, "poll_sec": 60,
            "data_source": data, "nt_account": account}
    if folder:
        body["nt_folder"] = folder
    if confirm:
        body["confirm"] = confirm
    try:                                             # extra accounts (data/accounts.json), as the CLI merges them
        from . import multi_account
        body = multi_account.merge_into_start(body, confirm)
    except Exception:
        pass
    return body


def check_start(bot, account: str, confirm: str, present: bool, env=None) -> str | None:
    """None = may go to the start route; else the plain-words refusal. Never weaker than the adapter's own gate."""
    env = os.environ if env is None else env
    if not _valid_name(account):
        return "pick an account (its exact NinjaTrader Name)"
    if getattr(bot, "running", False):
        return "the bot is already running: press STOP first"
    if is_sim(account):
        return None
    if not (confirm or "").strip():
        return f"{account} is a REAL account: type the confirm phrase in the dialog to start it"
    if (confirm or "").strip() != _phrase():
        return "the confirm phrase is not exact: nothing was started"
    if not present:
        return "tick 'I am at the PC and watching' (MFFU: live trading only with you present)"
    if env.get(LIVE_ENV, "") != "1":
        return f"{LIVE_ENV}=1 is not set for this server: add it to .env.local.ps1 and restart run_bot.ps1"
    return None


def do_start(bot, account: str, confirm: str = "", present: bool = False, env=None) -> dict:
    account = str(account or "").strip()
    err = check_start(bot, account, confirm, present, env)
    if err:
        return {"ok": False, "error": err, "refused": True}
    body = start_body(account, confirm if not is_sim(account) else "", folder=(getattr(bot, "cfg", None) or {}).get("nt_folder"))
    if not is_sim(account):
        body["present"] = bool(present)
    fn = HOOKS.get("start")
    try:
        res = fn(body) if callable(fn) else bot.start(body)
    except Exception as e:
        res = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
    finally:
        body.pop("confirm", None)
        for x in body.get("accounts") or []:
            if isinstance(x, dict):
                x.pop("confirm", None)
    res = dict(res or {})
    res.update(account=account, sim=is_sim(account),
               extras=[accounts.clean_text(x.get("id") or x.get("nt_account"), 40) for x in body.get("accounts") or [] if isinstance(x, dict)])
    ad = getattr(bot, "adapter", None)
    if res.get("ok") and getattr(ad, "disabled", None):
        res["warning"] = f"started, but orders are DISABLED: {ad.disabled}"
    return res


def do_stop(bot) -> dict:
    fn = HOOKS.get("stop")
    try:
        return dict((fn() if callable(fn) else bot.stop()) or {"ok": True})
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


def set_autoupdate(on: bool) -> dict:
    """python -m engine.autoupdate --enable / --disable."""
    from . import autoupdate
    s = autoupdate.load_state()
    s["enabled"] = bool(on)
    s["changed_at"] = int(time.time())
    autoupdate.save_state(s)
    try:
        autoupdate.file_log(f"auto-update turned {'ON' if on else 'OFF'} by the owner (dashboard)")
    except Exception:
        pass
    return {"ok": True, "on": autoupdate.is_enabled(s)}


def set_autoresume(bot, on: bool, account: str = "", confirm: str = "") -> dict:
    """--disable-auto-resume, or --enable-auto-resume --account X --confirm ... (then start now when stopped, as the CLI)."""
    from . import autoresume
    if not on:
        was = autoresume.disable("owner: dashboard")
        return {"ok": True, "on": False, "was_on": bool(was)}
    account = str(account or "").strip()
    body = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "present": True, "poll_sec": 60,
            "data_source": "ninjatrader", "nt_account": account}
    try:
        rec = autoresume.enable(account, confirm, body)
    except ValueError as e:
        return {"ok": False, "error": f"auto-resume NOT enabled: {e}"}
    out = {"ok": True, "on": True, "account": rec.get("account"), "accepted_on": rec.get("accepted_on")}
    if not getattr(bot, "running", False):
        out["start"] = do_start(bot, account, confirm, present=True)
    else:
        out["start"] = {"ok": True, "note": "the bot is already running: nothing else to do (it was not restarted)"}
    return out


def _flat_reason(bot):
    try:
        from . import autoupdate
        return autoupdate.bot_flat_reason(bot)
    except Exception as e:
        return f"cannot tell if flat ({e.__class__.__name__})"


def _restart_block(bot) -> str | None:
    if os.environ.get(SUPERVISED_ENV) != "1":
        return "this server is not run by scripts\\run_bot.ps1, so it would not come back: restart run_bot.ps1 by hand"
    r = _flat_reason(bot)
    if r:
        return f"not flat ({r}): restart after the trade / setup is done"
    return None


def do_restart(bot) -> dict:
    why = _restart_block(bot)
    if why:
        return {"ok": False, "error": why}
    from .autoupdate import RESTART_CODE
    fn = HOOKS.get("exit") or (lambda code: os._exit(code))
    threading.Timer(1.0, lambda: fn(RESTART_CODE)).start()
    return {"ok": True, "note": "server restarting: back in ~10 s (a Sim bot resumes by itself; a real account only with auto-resume on)"}


# ------------------------------------------------------------------------------------------------ strategy switches (read-only)
SWITCHES = [
    {"key": "t_check", "combo": "t15", "name": "15-minute check", "param": "t_check",
     "what": "15 minutes after the entry, cut a trade that is under +0.3R and never reached +0.5R",
     "note": "the PC route sent the cut ~3 min late in a replay: fix before switching on", "writeup": "lit-loss-learning.md"},
    {"key": "scale_in", "combo": "scale", "name": "Scale-in after breakeven", "param": "scale_in",
     "what": "add one more position (same size) on a pull-back after the stop is at breakeven",
     "note": "needs the NinjaTrader add-order route", "writeup": "lit-big-ideas.md"},
    {"key": "be_off", "combo": "be_off", "name": "Breakeven + costs", "param": "be_off",
     "what": "the breakeven stop sits 1.25 pts beyond entry so a BE exit pays its commission",
     "note": "small candidate", "writeup": "lit-adv-management.md"},
]


def switches_view(lm: dict | None = None) -> dict:
    lm = lm if lm is not None else _lm()
    lit = lm.get("lit") or {}
    path = os.path.join(ROOT, "research", "lit", "adopt_combo.json")
    try:
        with open(path, encoding="utf-8") as fh:
            combo = json.load(fh)
    except Exception:
        combo = {}
    keep = ("n", "tpw", "win", "pf", "net", "per_month", "dd", "p10", "f10", "pass_rate")

    def nums(c):
        lr = (c or {}).get("lit_rule") or {}
        ev = (c or {}).get("eval") or {}
        return {"rule": {k: {x: (lr.get(k) or {}).get(x) for x in keep} for k in ("H1", "H2", "2026", "2021-25") if lr.get(k)},
                "eval": {k: {x: (ev.get(k) or {}).get(x) for x in ("pf", "net", "per_month", "dd", "p10", "f10", "pass_med")} for k in ("H1", "H2") if ev.get(k)}}
    rows = []
    for s in SWITCHES:
        c = combo.get(s["combo"]) or {}
        rows.append({**{k: s[k] for k in ("key", "name", "what", "note", "writeup")}, "on": lit.get(s["param"]) not in (None, False, 0, {}),
                     "params": c.get("params"), **nums(c)})
    return {"base": nums(combo.get("base")), "switches": rows,
            "combos": {k: nums(combo.get(k)) for k in ("t15_be_off", "all3") if combo.get(k)},
            "source": "research/lit/adopt_combo.json", "read_only": True,
            "how": "switching one on is a change to live_model.json \"lit\" after the research checks; this panel only shows them"}


# ------------------------------------------------------------------------------------------------ today's LIT plan
def _plan_bars(bot):
    import pandas as pd
    path = os.path.join(ROOT, "data", "NQ_5m.csv")
    try:
        mt = os.path.getmtime(path)
    except OSError:
        mt = None
    df = None
    if mt is not None:
        with _lock:
            hit = _cache.get("csv5")
        if hit and hit[0] == mt:
            df = hit[1]
        else:
            try:
                df = pd.read_csv(path, usecols=["time", "open", "high", "low", "close", "volume"])
                df = df[df["time"] >= int(df["time"].max()) - 75 * 86400].reset_index(drop=True)
            except Exception:
                df = None
            with _lock:
                _cache["csv5"] = (mt, df)
    tail = getattr(bot, "bars_tail", None) or []
    if tail:
        try:
            t = pd.DataFrame(tail)[["time", "open", "high", "low", "close"]]
            t["volume"] = 0
            from . import pcbars
            df, _sh = pcbars.merge_basis(df if df is not None else t.iloc[0:0], t)
        except Exception:
            pass
    return df


def plan_view(bot, now: int | None = None) -> dict:
    """Today's LIT plan from engine/lit_brief.build (levels watched, which were swept, what is armed), cached per bar."""
    now = int(now or _now(bot))
    lm = _lm()
    df = _plan_bars(bot)
    if df is None or not len(df):
        return {"error": "no 5m bars (data/NQ_5m.csv / the bot's feed)"}
    last = int(df["time"].max())
    key = (last, now // 60)
    with _lock:
        hit = _cache.get("plan")
    if hit and hit[0] == key:
        return hit[1]
    from . import lit_brief
    st = getattr(bot, "state", None) or {}
    live = {"state": st, "signals": [s for s in ((st.get("lit") or {}).get("signals_today") or []) if isinstance(s, dict)]}
    prev = (hit[1].get("_brief") if hit else None)
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        b = lit_brief.build(df, min(now, last + 300), params=lm.get("lit"), live=live, prev=prev, ev=st.get("eval"),
                            clock=st.get("eval_2wk"), lit_sizing=lm.get("lit_sizing"), model_params=lm.get("params"))
    mo = b.get("morning") or {}
    levels = []
    for lv in mo.get("levels") or []:
        levels.append({k: lv.get(k) for k in ("name", "label", "side", "price", "kind", "taken", "taken_t", "depth_atr", "depth_pts")})
    nowb = b.get("now") or {}
    price = nowb.get("price") or mo.get("price")
    swept = [lv for lv in levels if lv.get("taken")]
    watched = [lv for lv in levels if not lv.get("taken")]
    if price:
        watched.sort(key=lambda lv: abs(float(lv["price"]) - float(price)))
    setups = []
    for side, s in (st.get("setups") or {}).items():
        if isinstance(s, dict):
            setups.append({"side": str(side).upper(), "limit": accounts._f(s.get("limit")), "stop": accounts._f(s.get("stop")),
                           "target": accounts._f(s.get("target")), "expires_t": accounts._i(s.get("expires_t")),
                           "tapped": bool(s.get("tapped_t"))})
    log = [{k: r.get(k) for k in ("t", "kind", "text", "level")} for r in (b.get("log") or [])[:14]]
    out = {"t": now, "day": b.get("day"), "at": b.get("at"), "waiting": b.get("waiting"), "price": price,
           "plan": mo.get("plan"), "band": mo.get("band"), "monday": mo.get("monday"), "weekly": mo.get("weekly") or mo.get("wk"),
           "news_text": mo.get("news_text"), "size": mo.get("size"), "watched": watched[:10], "swept": swept, "armed": setups,
           "now": {k: nowb.get(k) for k in ("text", "price", "above", "below", "waits") if k in nowb}, "log": log,
           "bars_to": last, "source": "data/NQ_5m.csv + the bot's 5m feed", "_brief": b}
    with _lock:
        _cache["plan"] = (key, out)
    return out


# ------------------------------------------------------------------------------------------------ routes
async def _body(req: Request) -> dict:
    try:
        b = await req.json()
        return b if isinstance(b, dict) else {}
    except Exception:
        return {}


@router.get("/api/next/botctl/status")
def r_status(account: str = ""):
    try:
        return _J(status_view(_bot(), account=account or None))
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {accounts.clean_text(e, 120)}"}, 500)


@router.get("/api/next/botctl/plan")
def r_plan():
    try:
        d = plan_view(_bot())
        d = {k: v for k, v in d.items() if k != "_brief"}
        return _J(d, 200)
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {accounts.clean_text(e, 120)}"}, 500)


@router.get("/api/next/botctl/switches")
def r_switches():
    try:
        return _J(switches_view())
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {accounts.clean_text(e, 120)}"}, 500)


@router.post("/api/next/botctl/selftest")
def r_selftest():
    return _J(selftest(start=True))


@router.post("/api/next/botctl/start")
async def r_start(req: Request):
    b = await _body(req)
    confirm = str(b.pop("confirm", "") or "")
    try:
        res = do_start(_bot(), str(b.get("account") or ""), confirm, bool(b.get("present")))
    finally:
        confirm = ""                                     # noqa: F841  (the phrase lives only for this call)
        b.clear()
    return _J(res, 200 if res.get("ok") else 400)


@router.post("/api/next/botctl/stop")
def r_stop():
    return _J(do_stop(_bot()))


@router.post("/api/next/botctl/autoupdate")
async def r_autoupdate(req: Request):
    b = await _body(req)
    try:
        return _J(set_autoupdate(bool(b.get("on"))))
    except Exception as e:
        return _J({"ok": False, "error": f"{e.__class__.__name__}: {accounts.clean_text(e, 120)}"}, 500)


@router.post("/api/next/botctl/autoresume")
async def r_autoresume(req: Request):
    b = await _body(req)
    confirm = str(b.pop("confirm", "") or "")
    try:
        res = set_autoresume(_bot(), bool(b.get("on")), str(b.get("account") or ""), confirm)
    except Exception as e:
        res = {"ok": False, "error": f"{e.__class__.__name__}: {accounts.clean_text(e, 120)}"}
    finally:
        confirm = ""                                     # noqa: F841
        b.clear()
    return _J(res, 200 if res.get("ok") else 400)


@router.post("/api/next/botctl/restart")
def r_restart():
    res = do_restart(_bot())
    return _J(res, 200 if res.get("ok") else 400)


# ------------------------------------------------------------------------------------------------ insights (read-only)
# Killzones the owner watches (95 of 120 LIT trades of 2026 enter 02:00-08:00 ET); entries stop 15:30, flat 15:55 ET.
KILLZONES = [{"id": "london", "label": "London / pre-NY", "from": 120, "to": 480},
             {"id": "nyam", "label": "NY AM", "from": 480, "to": 720},
             {"id": "nypm", "label": "NY PM", "from": 720, "to": 930}]
CUTOFFS = [{"id": "cutoff", "label": "Entry cutoff", "at": 930}, {"id": "flat", "label": "Flat", "at": 955}]


def _today_log(bot, today, kinds=None, n=60):
    out = []
    for r in list(getattr(bot, "log", None) or []):
        t = r.get("t")
        if not t or accounts.trading_day(t) != today or (kinds and r.get("type") not in kinds):
            continue
        out.append({"t": int(t), "type": r.get("type"), "text": accounts.clean_text(r.get("text"), 220)})
        if len(out) >= n:
            break
    return out


def rule_checklist(bot, plan: dict | None, now: int) -> list:
    """Which LIT steps are met right now (the bot reports sweep + inducement + displacement + CISD together once its 5m CISD
    closes, so those light up with today's first setup)."""
    st = getattr(bot, "state", None) or {}
    sigs = [s for s in ((st.get("lit") or {}).get("signals_today") or []) if isinstance(s, dict)]
    setups = [s for s in (st.get("setups") or {}).values() if isinstance(s, dict)]
    today = accounts.trading_day(now)
    swept = [lv for lv in (plan or {}).get("swept") or [] if lv.get("taken_t") and accounts.trading_day(lv["taken_t"]) == today]
    deep = [lv for lv in swept if (lv.get("depth_atr") or 0) >= 0.5]
    pos = bool(st.get("position"))
    done = int(st.get("day_trades") or 0) >= 1
    last = sigs[-1] if sigs else None
    tapped = any(s.get("tapped_t") for s in setups)
    return [
        {"id": "sweep", "label": "Sweep of a LIT level (>= 0.5 ATR deep)", "met": bool(deep) or bool(sigs),
         "detail": ", ".join(f"{lv['label']} {lv.get('depth_atr') or 0:.2f} ATR" for lv in (deep or swept)[:4]) or "no level taken deep enough yet"},
        {"id": "inducement", "label": "Inducement swing taken first (<= 1 ATR, <= 36 bars)", "met": bool(sigs),
         "detail": "with today's setup" if sigs else "comes with the 5m CISD"},
        {"id": "displacement", "label": "Displacement body >= 0.8 ATR", "met": bool(sigs), "detail": "with today's setup" if sigs else "comes with the 5m CISD"},
        {"id": "cisd", "label": "5m CISD close", "met": bool(sigs),
         "detail": (f"{'LONG' if (last or {}).get('dir', 0) > 0 else 'SHORT'} at {accounts._f(last.get('limit_px'))}" if last else "waiting")},
        {"id": "limit", "label": "Limit armed at the CISD level (30 min)", "met": bool(setups) or pos or done,
         "detail": (f"{len(setups)} armed" if setups else "filled / done" if (pos or done) else "none")},
        {"id": "cisd1m", "label": "1m CISD within 20 bars, then entry", "met": pos or done or tapped,
         "detail": "in trade" if pos else "done for today" if done else ("tapped, waiting for the 1m CISD" if tapped else "—")},
    ]


def why_no_trade(bot, plan, checklist, now, lm=None) -> dict:
    """Plain words: why there is no trade (yet) today, from the live model state, health and the risk log."""
    st = getattr(bot, "state", None) or {}
    h = accounts.pc_health(bot, now)
    f, a = h.get("feed") or {}, h.get("account") or {}
    from .live import market_open
    win = entry_window(now, lm)
    ms = accounts.clean_text(st.get("model_state"), 200)
    if st.get("position"):
        return {"trading": True, "headline": "In a trade now", "reasons": [], "model_state": ms}
    if int(st.get("day_trades") or 0) >= 1:
        return {"trading": True, "headline": "Today's one trade is done (1 trade a day)", "reasons": [], "model_state": ms}
    reasons = []
    if not getattr(bot, "running", False):
        reasons.append({"ok": False, "text": "The bot is stopped: press START"})
    if getattr(bot, "kill", False):
        reasons.append({"ok": False, "text": "The kill switch was used today: no orders until tomorrow"})
    if a.get("enabled") is False:
        reasons.append({"ok": False, "text": f"Orders disabled: {a.get('disabled')}"})
    if not market_open(now):
        reasons.append({"ok": None, "text": "The market is closed"})
    elif not win.get("open"):
        reasons.append({"ok": None, "text": f"Outside the LIT entry window (02:00-15:30 ET): {win.get('text')}"})
    if f.get("entries_blocked") or f.get("stale") or f.get("block") or f.get("nt_down"):
        reasons.append({"ok": False, "text": f"FEED STALE: {f.get('block') or f.get('nt_down') or 'NinjaTrader bars old'}: new entries blocked"})
    for r in checklist:
        if not r["met"]:
            reasons.append({"ok": None, "text": f"Not yet: {r['label']} ({r['detail']})"})
            break
    for r in _today_log(bot, accounts.trading_day(now), kinds=("risk",), n=40):
        if "NOT" in (r["text"] or ""):
            reasons.append({"ok": False, "text": r["text"], "t": r["t"]})
    head = next((r["text"] for r in reasons if r["ok"] is False), None) or next((r["text"] for r in reasons), "Watching the levels")
    return {"trading": False, "headline": head, "reasons": reasons[:10], "model_state": ms}


def radar(plan: dict | None, now: int) -> dict:
    price = (plan or {}).get("price")
    rows = []
    for lv in (plan or {}).get("watched") or []:
        try:
            d = float(lv["price"]) - float(price)
        except (TypeError, ValueError, KeyError):
            continue
        rows.append({"label": lv.get("label"), "price": lv.get("price"), "side": lv.get("side"), "kind": lv.get("kind"),
                     "dist_pts": round(d, 2), "above": d > 0})
    e = _et(now)
    mod = e.hour * 60 + e.minute
    wd = e.weekday()
    if e.hour >= 18:                     # 18:00 ET opens the next trading day: count down to tomorrow's killzones
        mod -= 1440
        wd = (wd + 1) % 7
    nxt = None
    if wd < 5:
        for z in KILLZONES:
            if z["from"] <= mod < z["to"]:
                nxt = {**z, "now": True, "ends_in_s": (z["to"] - mod) * 60 - e.second}
                break
            if mod < z["from"]:
                nxt = {**z, "now": False, "starts_in_s": (z["from"] - mod) * 60 - e.second}
                break
    return {"price": price, "levels": rows[:8], "killzone": nxt}


def news_view(now: int) -> dict:
    from . import lit_brief
    day = str(_et(now).date())
    hub = None
    try:
        with open(os.path.join(ROOT, "data", "news", "hub.json"), encoding="utf-8") as fh:
            hub = json.load(fh)
    except Exception:
        hub = None
    try:
        ev, src = lit_brief.news_today(day, hub)
    except Exception as e:
        return {"day": day, "events": [], "error": accounts.clean_text(e, 120)}
    for x in ev:
        x["tier1"] = any(w in str(x.get("title", "")).lower() for w in lit_brief.NEWS_KW)
    return {"day": day, "events": ev, "source": src, "text": lit_brief.news_text(ev)}


def alerts_log(n=30) -> dict:
    """Every phone push this server sent (engine/push.py's PC notifier, in memory), else the de-dup keys on disk."""
    rows = []
    try:
        from . import push
        nt = (getattr(push, "_PC", None) or {}).get("notifier")
        for r in list(getattr(nt, "log", None) or [])[::-1][:n]:
            rows.append({"t": accounts._i(r.get("t")), "title": accounts.clean_text(r.get("title"), 120), "kind": r.get("kind"),
                         "key": accounts.clean_text(r.get("key"), 80), "src": "this server"})
        if not rows:
            try:
                with open(push.SENT_PATH, encoding="utf-8") as fh:
                    sent = json.load(fh) or {}
            except Exception:
                sent = {}
            for k, t in sorted(sent.items(), key=lambda kv: -float(kv[1] or 0))[:n]:
                rows.append({"t": int(float(t or 0)), "title": None, "kind": str(k).split(":")[0], "key": accounts.clean_text(k, 80),
                             "src": "push_sent.json"})
    except Exception as e:
        return {"rows": rows, "error": accounts.clean_text(f"{e.__class__.__name__}: {e}", 120)}
    return {"rows": rows}


def health_timeline(bot, now, n=40) -> list:
    out = []
    for r in list(getattr(bot, "log", None) or [])[:400]:
        if r.get("type") not in ("system", "warn", "risk", "error", "kill") or not r.get("t") or now - int(r["t"]) > 3 * 86400:
            continue
        txt = accounts.clean_text(r.get("text"), 200) or ""
        low = txt.lower()
        kind = ("feed" if any(w in low for w in ("stale", "feed", "bars missing")) else
                "start" if any(w in low for w in ("started", "stopped", "autostart", "resumed")) else
                "update" if "update" in low else r.get("type"))
        out.append({"t": int(r["t"]), "kind": kind, "text": txt})
        if len(out) >= n:
            break
    fn = HOOKS.get("heartbeat")
    if callable(fn):
        try:
            last = (fn() or {}).get("last") or {}
            if last.get("at"):
                out.append({"t": int(last["at"]), "kind": "heartbeat",
                            "text": "heartbeat pushed" if last.get("ok") else f"heartbeat push failed: {accounts.clean_text(last.get('error'), 120)}"})
        except Exception:
            pass
    try:
        from . import autoupdate
        u = autoupdate.status()
        if u.get("last_check_t"):
            out.append({"t": int(u["last_check_t"]), "kind": "update", "text": f"auto-update check: {u.get('result')} {u.get('reason') or ''}".strip()})
        if u.get("updated_at"):
            out.append({"t": int(u["updated_at"]), "kind": "update", "text": f"updated to {u.get('sha')}"})
    except Exception:
        pass
    try:
        up = (accounts.pc_health(bot, now).get("uptime") or {}).get("server_s")
        if up is not None:
            out.append({"t": int(now - up), "kind": "start", "text": "server started"})
    except Exception:
        pass
    out.sort(key=lambda r: -r["t"])
    return out[:n]


def changelog(n=15) -> dict:
    """The last commits of this checkout (since the last auto-update when it recorded one), plain titles; cached 10 min."""
    with _lock:
        hit = _cache.get("changelog")
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    since = None
    try:
        from . import autoupdate
        s = autoupdate.load_state()
        since = (s.get("last") or {}).get("old")
    except Exception:
        pass
    rows = []
    try:
        args = ["git", "log", f"-{n}", "--no-merges", "--format=%h%x09%ct%x09%s"]
        if since:
            args.append(f"{since}..HEAD")
        p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=20)
        for ln in (p.stdout or "").splitlines():
            parts = ln.split("\t", 2)
            if len(parts) == 3:
                title = parts[2]
                for pre in ("WIP checkpoint: ", "LIT: "):
                    if title.startswith(pre):
                        title = title[len(pre):]
                rows.append({"sha": parts[0], "t": int(parts[1]), "title": accounts.clean_text(title, 160),
                             "wip": parts[2].startswith("WIP")})
    except Exception as e:
        rows = [{"error": accounts.clean_text(f"{e.__class__.__name__}: {e}", 120)}]
    try:
        from . import autoupdate
        ver = autoupdate.version()
    except Exception:
        ver = {}
    out = {"version": ver, "since": since, "commits": rows}
    with _lock:
        _cache["changelog"] = (time.time(), out)
    return out


def insights_view(bot, now: int | None = None) -> dict:
    now = int(now or _now(bot))
    lm = _lm()
    try:
        plan = plan_view(bot, now)
    except Exception as e:
        plan = {"error": accounts.clean_text(f"{e.__class__.__name__}: {e}", 120)}
    chk = rule_checklist(bot, None if plan.get("error") else plan, now)
    return {"t": now, "checklist": chk, "why": why_no_trade(bot, plan, chk, now, lm), "radar": radar(plan, now),
            "killzones": KILLZONES, "cutoffs": CUTOFFS, "news": news_view(now), "alerts": alerts_log(),
            "timeline": health_timeline(bot, now), "changelog": changelog()}


@router.get("/api/next/botctl/insights")
def r_insights():
    try:
        return _J(insights_view(_bot()))
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {accounts.clean_text(e, 120)}"}, 500)
