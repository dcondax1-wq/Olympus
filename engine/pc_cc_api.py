"""Read-only API of the PC dashboard's Command center, Goals fallback, Runbook, Audit evidence, ATLAS setups and the small
"All features" tools (web_next/js/next/cc.js). Mounted by engine/next_api.py (router.include_router).

Every route only READS: the PC bot (engine/live.BOT: cfg, state, ledger, log, health, adapter, acct_b), the account
allowlist file, the guards' clock probe result, the heartbeat status hook, live_model.json and the repo's research files
(research/handoff/2026-10-25/). Nothing here starts, arms, routes, sizes or stops anything, and no route writes a file.

  GET /api/next/cc/home          both accounts side by side (LIT 50K, ATLAS 25K): progress to target, room to floor,
                                 today, open position, what the bot waits for, health lights (feed, NinjaTrader, clock,
                                 STARTUP RECONCILED, allowlist, duplicate-process lock, heartbeat, kill, poll), the day
                                 (session phase, early close, full closure, DST change, news today), the last log rows,
                                 the launch checklist (engine/launch_check.py, "launch")
  GET /api/next/cc/calendar      the next 14 trading days: early close, closed, DST change, weekday
  GET /api/next/cc/handoff       the audit folder's files (name, size, kind) + the README headline
  GET /api/next/cc/doc?name=     one text file of that folder (md / csv / txt / json, <= 600 KB; a name, never a path)
  GET /api/next/cc/setups        PERFORMANCE_BY_SETUP.csv rows (ATLAS per setup, H1 / H2 / ref)
  GET /api/next/cc/atlas_trades  ATLAS_TRADE_LEDGER.csv rows of one book (default the live-like BASELINE rows)
  GET /api/next/cc/runbook       STARTUP_AND_RECOVERY_RUNBOOK.md split in sections, the EMERGENCY page apart
  GET /api/next/cc/data_files    data/*.csv freshness (bars the bot and the backtests read)
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import threading
import time
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import Response

from . import accounts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDOFF = os.path.join(ROOT, "research", "handoff", "2026-10-25")
ET = ZoneInfo("America/New_York")
TEXT_EXT = (".md", ".csv", ".txt", ".json")
MAX_DOC = 600_000
# the 2026-10-25 launch numbers (engine/launch_prep.py defaults): shown when the bot has no anchor yet
ANCHOR = {"balance": 49710.80, "floor": 48168.20, "as_of": "2026-10-23", "target_balance": 53000.0}
B25 = {"start": 25000.0, "target": 1500.0, "mll": 1000.0, "dll": 600.0, "max_micros": 20, "price": 63.00}
router = APIRouter()
_lock = threading.Lock()
_cache: dict = {}


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _bot():
    """The PC bot (tests replace this function)."""
    from .live import BOT
    return BOT


def _now(bot) -> int:
    try:
        return int(bot.clock())
    except Exception:
        return int(time.time())


def _lm() -> dict:
    try:
        with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:                       # every block degrades on its own; the page never 500s
        return default if default is not None else {"error": accounts.clean_text(f"{e.__class__.__name__}: {e}", 160)}


# --------------------------------------------------------------------------------------------- the day
def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def phase(now: int) -> dict:
    """Where the ET clock is in the LIT day: entries 02:00-15:30, manage to 15:55, flat, CME break 17:00-18:00."""
    e = _et(now)
    m = e.hour * 60 + e.minute
    wd = e.weekday()                             # Mon 0 .. Sun 6
    closed = wd == 5 or (wd == 4 and m >= 17 * 60) or (wd == 6 and m < 18 * 60)
    if closed:
        return {"code": "weekend", "label": "Weekend: market closed", "next": "Sunday 18:00 ET Globex open", "entries": False}
    rows = [(0, 120, "overnight", "Overnight / Asia: the bot marks levels, no entries", "02:00 entry window opens"),
            (120, 930, "window", "Entry window open (02:00-15:30)", "15:30 last entry"),
            (930, 955, "manage", "No new entries: managing an open trade only", "15:55 flat"),
            (955, 1020, "flat", "Flat for the day (15:55)", "17:00 CME break"),
            (1020, 1080, "break", "CME daily break 17:00-18:00", "18:00 new session"),
            (1080, 1440, "evening", "New session (18:00): Asia, levels building", "02:00 entry window opens")]
    for a, b, code, label, nxt in rows:
        if a <= m < b:
            left = b - m
            return {"code": code, "label": label, "next": nxt, "entries": code == "window", "min_left": left}
    return {"code": "?", "label": "", "next": "", "entries": False}


def dst_change(day: dt.date) -> dict | None:
    """The next US clock change within 14 days (2nd Sunday of March, 1st Sunday of November)."""
    for y in (day.year, day.year + 1):
        mar = dt.date(y, 3, 8)
        mar += dt.timedelta(days=(6 - mar.weekday()) % 7)
        nov = dt.date(y, 11, 1)
        nov += dt.timedelta(days=(6 - nov.weekday()) % 7)
        for d, kind in ((mar, "spring forward (clocks +1 h)"), (nov, "fall back (clocks -1 h)")):
            if 0 <= (d - day).days <= 14:
                return {"date": d.isoformat(), "days": (d - day).days, "kind": kind,
                        "text": f"US clocks change {d.strftime('%a %b')} {d.day}: {kind}. The bot runs on ET, so its times stay the "
                                "same; check the PC clock shows the new time and the clock light stays green."}
    return None


def day_info(day: str) -> dict:
    from . import guards, lit_live
    out = {"day": day, "weekday": dt.date.fromisoformat(day).strftime("%A")}
    out["closed"] = bool(_safe(lambda: guards.full_closure(day), False))
    ec = _safe(lambda: lit_live.early_close(day), None)
    out["early_close"] = None if not isinstance(ec, int) else f"{ec // 60:02d}:{ec % 60:02d}"
    return out


def calendar(now: int, n: int = 14) -> list:
    d = dt.date.fromisoformat(accounts.trading_day(now))
    rows = []
    while len(rows) < n:
        if d.weekday() < 5:
            r = day_info(d.isoformat())
            dc = dst_change(d - dt.timedelta(days=1))
            # the change is on a Sunday: Monday's session (it opens Sunday 18:00 ET) is the first one on the new time
            r["dst"] = dc["kind"] if dc and dc["days"] == 0 else None
            rows.append(r)
        d += dt.timedelta(days=1)
    return rows


# --------------------------------------------------------------------------------------------- health lights
def _light(key, label, ok, detail, fix=""):
    """ok: True green, False red, None grey / amber (not applicable or unknown)."""
    return {"key": key, "label": label, "ok": ok, "detail": accounts.clean_text(detail, 200), "fix": fix}


def lights(bot, now: int, h: dict) -> list:
    from . import guards, ninjatrader
    cfg = getattr(bot, "cfg", None) or {}
    ad = getattr(bot, "adapter", None)
    is_nt = (cfg.get("adapter") or getattr(ad, "name", None)) == "ninjatrader"
    running = bool(getattr(bot, "running", False))
    f, nt, acc, poll = h.get("feed") or {}, h.get("nt") or {}, h.get("account") or {}, h.get("poll") or {}
    out = []
    # 1. feed
    if not running:
        out.append(_light("feed", "Bar feed", None, "bot stopped"))
    elif f.get("stale") or f.get("entries_blocked"):
        out.append(_light("feed", "Bar feed", False, f.get("block") or "FEED STALE: new entries blocked",
                          "Open the MNQ chart with LE_BarFeed in NinjaTrader (NinjaTrader page)."))
    else:
        a1, a5 = f.get("age_1m_s"), f.get("age_5m_s")
        out.append(_light("feed", "Bar feed", True if a5 is not None else (None if not f.get("market_open") else False),
                          f"{f.get('used') or f.get('source')}: 1m {'?' if a1 is None else f'{int(a1)} s'} · 5m {'?' if a5 is None else f'{int(a5)} s'} old"
                          + ("" if f.get("market_open", True) else " (market closed)")))
    # 2. NinjaTrader connection
    if not is_nt:
        out.append(_light("nt", "NinjaTrader", None, f"adapter {cfg.get('adapter') or 'paper'} (no NinjaTrader)"))
    else:
        conns = nt.get("connections") or {}
        out.append(_light("nt", "NinjaTrader", bool(nt.get("connected")) and not nt.get("last_error"),
                          ", ".join(f"{k} {v}" for k, v in conns.items()) or ("connected" if nt.get("connected") else "no connection file"),
                          "" if nt.get("connected") else "NinjaTrader Control Center > Connections: connect your login."))
    # 3. clock
    c = guards._CLOCK
    drift = c.get("drift")
    if drift is None:
        out.append(_light("clock", "PC clock", None, "not checked yet (needs internet; checked every 15 min while the bot runs)"))
    else:
        mx = float(c.get("max") or 5.0)
        out.append(_light("clock", "PC clock", abs(drift) <= mx, f"{abs(drift):.1f} s {'behind' if drift > 0 else 'ahead'} of internet time (max {mx:.0f} s)",
                          "" if abs(drift) <= mx else "Double-click FIX_CLOCK.bat once, right-click > Run as administrator."))
    # 4. startup reconcile
    st = (getattr(bot, "health", None) or {}).get("startup") or {}
    if not is_nt:
        out.append(_light("startup", "Startup reconcile", None, "only for the NinjaTrader route"))
    elif getattr(bot, "_startup_ok", None) or st.get("ok"):
        since = getattr(bot, "_startup_ok", None) or st.get("since")
        out.append(_light("startup", "Startup reconcile", True, "STARTUP RECONCILED" + (f" at {_et(since).strftime('%H:%M')} ET" if since else "")))
    elif st.get("problems"):
        out.append(_light("startup", "Startup reconcile", False, "STARTUP DISARMED: " + "; ".join(st["problems"])[:180],
                          "Runbook section 2 has the fix for each reason."))
    else:
        out.append(_light("startup", "Startup reconcile", None if not running else None, "waiting for the first check" if running else "bot stopped"))
    # 5. allowlist
    name = acc.get("name")
    allowed = _safe(lambda: sorted(ninjatrader.allowed_accounts()), [])
    sim = _safe(lambda: ninjatrader.is_sim(name), False) if name else False
    if not is_nt:
        out.append(_light("allow", "Account allowlist", None, f"{len(allowed)} account(s) listed"))
    elif sim:
        out.append(_light("allow", "Account allowlist", True, f"{name} is a Sim account (never needs the allowlist)"))
    else:
        ok = name in allowed
        out.append(_light("allow", "Account allowlist", ok, f"{name} {'is' if ok else 'is NOT'} listed ({len(allowed)} listed)",
                          "" if ok else f'python -m engine.ninjatrader --allow-account "{name}"'))
    # 6. duplicate-process lock
    dis = str(getattr(ad, "disabled", None) or "")
    if not is_nt or ad is None:
        out.append(_light("lock", "One bot per account", None, "no NinjaTrader adapter running"))
    elif "another bot process" in dis:
        out.append(_light("lock", "One bot per account", False, dis[:180], "scripts\\stop_bot.ps1, wait 10 s, start once."))
    else:
        held = bool(getattr(ad, "_lock_key", None))
        out.append(_light("lock", "One bot per account", True if held else None,
                          "this process holds the account lock" if held else "lock not taken (folder missing or lock off)"))
    # 7. heartbeat to the phone / cloud
    hb = _safe(lambda: _heartbeat(), {})
    if not hb or hb.get("error"):
        out.append(_light("heartbeat", "Phone heartbeat", None, "status unknown"))
    else:
        last = hb.get("last") or {}
        lt = last.get("t") if isinstance(last, dict) else None
        ok = bool(hb.get("enabled")) and (lt is None or now - int(lt) < 900) and (not isinstance(last, dict) or last.get("ok", True))
        out.append(_light("heartbeat", "Phone heartbeat", ok if hb.get("enabled") else None,
                          ("on" if hb.get("enabled") else "off (LE_HEARTBEAT=1 turns it on)")
                          + (f", last push {_et(lt).strftime('%H:%M')} ET" if lt else "")))
    # 8. kill switch, 9. polling
    out.append(_light("kill", "Kill switch", not bool(getattr(bot, "kill", False)),
                      "KILLED today: no orders until tomorrow" if getattr(bot, "kill", False) else "off"))
    age = poll.get("age_s")
    out.append(_light("poll", "Bot loop", (age is not None and age < 180 and not poll.get("consecutive_errors")) if running else None,
                      ("stopped" if not running else f"last poll {int(age)} s ago" if age is not None else "no poll yet")
                      + (f", {poll.get('consecutive_errors')} errors in a row" if poll.get("consecutive_errors") else "")
                      + (f"; {poll_line(poll.get('stages'))}" if running and poll.get("stages") else "")))
    return out


def poll_line(ps) -> str:
    """One line from health.poll.stages: '32.3 s a poll (CPU 2.1 s); slowest: adapter tick 29.8 s, LIT model 1.2 s'."""
    if not isinstance(ps, dict) or not ps.get("total_ms"):
        return ""
    top = sorted((s for s in ps.get("stages") or [] if " > " not in str(s.get("name"))), key=lambda s: -(s.get("ms") or 0))[:3]
    th = [t for t in ps.get("threads") or [] if (t.get("cpu_ms") or 0) >= 500][:1]
    lit = ps.get("lit_ms")
    return ((f"LIT decided and routed {lit / 1000:.1f} s into the poll; " if isinstance(lit, (int, float)) else "")
            + f"{ps['total_ms'] / 1000:.1f} s a poll (CPU {(ps.get('cpu_ms') or 0) / 1000:.1f} s); slowest: "
            + ", ".join(f"{s['name']} {(s.get('ms') or 0) / 1000:.1f} s" for s in top)
            + (f"; busy meanwhile: {th[0]['name']} {th[0]['cpu_ms'] / 1000:.1f} s CPU" if th else ""))


def _heartbeat():
    from . import botctl
    fn = (getattr(botctl, "HOOKS", None) or {}).get("heartbeat")
    return fn() if callable(fn) else {}


# --------------------------------------------------------------------------------------------- accounts
def _lit_card(bot, now, lm) -> dict:
    from . import pcdash_api
    a = pcdash_api.account_view(bot, now, lm=lm, bars=False)
    if a.get("error"):
        return {"error": a["error"], "name": "LIT · MFFU Builder 50K"}
    ev = a.get("eval") or {}
    anc = (a.get("sizing") or {}).get("eval_anchor") or ev.get("anchor")
    acct = a.get("account") or {}
    trades = a.get("trades") or []
    today = a.get("today")
    return {"id": "lit", "strategy": "LIT", "name": "LIT · MFFU Builder 50K", "plan": acct.get("plan") or "Builder 50K",
            "badge": acct.get("badge"), "broker_account": acct.get("broker_account"),
            "balance": ev.get("balance"), "profit": ev.get("profit"), "target_balance": ev.get("target_balance"),
            "to_target": ev.get("to_target"), "floor": ev.get("floor"), "room": ev.get("room"), "progress": ev.get("progress"),
            "session": ev.get("session"), "sessions": ev.get("sessions") or 10, "status": ev.get("status"),
            "dll": ev.get("dll"), "dll_used": ev.get("dll_used"), "clock_text": ev.get("clock_text"), "anchor": anc,
            "today_pnl": (a.get("pnl") or {}).get("today"), "week_pnl": (a.get("pnl") or {}).get("week"),
            "trades_today": sum(1 for t in trades if t.get("day") == today), "max_trades_day": 1,
            "position": a.get("position"), "equity": (a.get("equity") or [])[-40:],
            "trades": [{k: t.get(k) for k in ("day", "side", "qty", "pnl", "r", "exit", "entry_t")} for t in trades[:8]],
            "launch_anchor": ANCHOR}


def _atlas_card(bot, now) -> dict:
    ab = getattr(bot, "acct_b", None)
    base = {"id": "atlas", "strategy": "ATLAS", "name": "ATLAS · MFFU Builder 25K", "plan": "Builder 25K", "rules": B25, "max_trades_day": 2}
    if ab is None:
        return {**base, "configured": False, "status": "not set up",
                "note": 'Account B is not on yet. Tonight: python -m engine.launch_prep --atlas "<25K Name>" (never arms).',
                "balance": B25["start"], "profit": 0.0, "target_balance": B25["start"] + B25["target"], "to_target": B25["target"],
                "floor": B25["start"] - B25["mll"], "room": B25["mll"], "progress": 0.0, "session": None, "sessions": 10}
    info = ab.info(now)
    ev = info.get("eval") or {}
    tgt = float(ev.get("target") or (B25["start"] + B25["target"]))
    start = float(ev.get("start_balance") or B25["start"])
    prof = ev.get("profit")
    return {**base, "configured": True, "badge": info.get("kind"), "broker_account": info.get("account"),
            "plan": info.get("plan_label") or base["plan"], "enabled": info.get("enabled"), "disabled": info.get("disabled"),
            "balance": ev.get("balance"), "profit": prof, "target_balance": tgt, "to_target": ev.get("to_target"),
            "floor": ev.get("floor"), "room": ev.get("room"), "session": ev.get("session"), "sessions": 10,
            "progress": None if prof is None else max(0.0, min(1.0, float(prof) / max(1.0, tgt - start))),
            "status": ev.get("status"), "dll": ev.get("dll"), "today_pnl": info.get("day_pnl"),
            "trades_today": info.get("entries_today"), "max_trades_day": 2, "position": info.get("open"),
            "locked": info.get("locked"), "keys": info.get("keys"),
            "trades": [{k: r.get(k) for k in ("t", "side", "qty", "pnl", "reason", "strategy")} for r in (info.get("routed") or [])][-8:][::-1]}


def _blitz_card(bot, now) -> dict | None:
    """BLITZ on its own 25K (account C, engine/account_c.py): the third account card, the same keys as ATLAS's. None = off
    (then home_view has no "blitz" key: exactly as before)."""
    ac = getattr(bot, "acct_c", None)
    if ac is None:
        return None
    info = ac.info(now)
    ev = info.get("eval") or {}
    tgt = float(ev.get("target") or (B25["start"] + B25["target"]))
    start = float(ev.get("start_balance") or B25["start"])
    prof = ev.get("profit")
    sc = info.get("scorecard") or {}
    return {"id": "blitz", "strategy": "BLITZ", "name": "BLITZ · MFFU Builder 25K", "plan": info.get("plan_label") or "Builder 25K",
            "rules": B25, "max_trades_day": 6, "configured": True, "badge": info.get("kind"), "real": info.get("real"),
            "broker_account": info.get("account"), "enabled": info.get("enabled"), "disabled": info.get("disabled"),
            "balance": ev.get("balance"), "profit": prof, "target_balance": tgt, "to_target": ev.get("to_target"),
            "floor": ev.get("floor"), "room": ev.get("room"), "session": ev.get("session"), "sessions": 10,
            "progress": None if prof is None else max(0.0, min(1.0, float(prof) / max(1.0, tgt - start))),
            "status": ev.get("status"), "dll": ev.get("dll"), "today_pnl": info.get("day_pnl"), "trades_today": info.get("entries_today"),
            "position": info.get("open"), "locked": info.get("locked"), "paused": info.get("paused"), "state": info.get("state"),
            "scorecard": {k: sc.get(k) for k in ("n", "win_pct", "avg_r", "pf_r", "usd", "lose_days", "status", "why", "floor")},
            "trades": [{k: r.get(k) for k in ("t", "side", "qty", "pnl", "reason", "strategy")} for r in (info.get("routed") or [])
                       if r.get("side") in ("buy", "sell", "exit")][-8:][::-1]}


def waiting(bot, st_view: dict) -> dict:
    """One plain sentence: what the bot is waiting for now."""
    h = st_view.get("health") or {}
    lit = h.get("lit") or {}
    pend = st_view.get("pending") or []
    text = st_view.get("model_state") or lit.get("text") or ""
    if not getattr(bot, "running", False):
        say = "The bot is stopped. Start it on Bot Control when NinjaTrader is open."
    elif getattr(bot, "kill", False):
        say = "Kill switch used today: nothing until tomorrow's session."
    elif lit.get("stage") == "trade":
        say = "In a trade: waiting for the target, the stop, breakeven at 1R or the 15:55 flat."
    elif pend:
        p = pend[0]
        say = f"Limit {p.get('side')} at {p.get('limit')} is waiting to fill" + (f" ({p.get('waiting')})" if p.get("waiting") else "") + "."
    elif lit.get("stage") == "done":
        say = "Done for today (1 trade a day). Next chance: the next session."
    else:
        say = "Watching the LIT levels: waiting for a sweep, then inducement, displacement and a 5m CISD."
    return {"say": say, "model_state": accounts.clean_text(text, 200), "stage": lit.get("stage"), "pending": pend,
            "setups_today": st_view.get("setups_today") or []}


def recent_log(bot, n=12) -> list:
    rows = []
    for r in list(getattr(bot, "log", None) or [])[:200]:
        if r.get("type") in ("risk", "order", "kill", "error", "system"):
            rows.append({"t": accounts._i(r.get("t")), "type": r.get("type"), "text": accounts.clean_text(r.get("text"), 220)})
    rows.sort(key=lambda r: -(r["t"] or 0))
    return rows[:n]


def _launch(bot, h, now):
    """The launch checklist (engine/launch_check.py): the same items the phone shows, read from the bot itself."""
    from . import launch_check
    return launch_check.block(bot, h if isinstance(h, dict) and not h.get("error") else None, now)


def home_view(bot, now: int | None = None) -> dict:
    from . import botctl, pcdash_api
    now = int(now or _now(bot))
    lm = _lm()
    st = _safe(lambda: pcdash_api.status_view(bot, now), {})
    h = st.get("health") or {}
    today = accounts.trading_day(now)
    d = day_info(today)
    d["phase"] = phase(now)
    d["dst"] = dst_change(dt.date.fromisoformat(today))
    news = _safe(lambda: botctl.news_view(now), {"events": []})
    d["news"] = {"events": (news.get("events") or [])[:10], "text": news.get("text")}
    return {"t": now, "today": today, "et": _et(now).strftime("%a %b %d %H:%M:%S ET"),
            "verdict": st.get("verdict"), "running": bool(getattr(bot, "running", False)),
            "lit": _safe(lambda: _lit_card(bot, now, lm)), "atlas": _safe(lambda: _atlas_card(bot, now)),
            "lights": _safe(lambda: lights(bot, now, h), []), "waiting": _safe(lambda: waiting(bot, st)),
            "launch": _safe(lambda: _launch(bot, h, now)),
            "day": d, "log": _safe(lambda: recent_log(bot), []),
            "version": (h.get("auto") or {}).get("version"), "branch": (h.get("auto") or {}).get("branch"),
            "uptime": h.get("uptime"), "price": st.get("price"), "eval_clock": st.get("eval_clock"),
            **({"blitz": _safe(lambda: _blitz_card(bot, now))} if getattr(bot, "acct_c", None) is not None else {})}


@router.get("/api/next/cc/home")
def r_home():
    try:
        return _J(home_view(_bot()))
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {accounts.clean_text(e, 160)}"}, 500)


@router.get("/api/next/cc/calendar")
def r_calendar(days: int = 14):
    bot = _bot()
    return _J({"rows": calendar(_now(bot), max(1, min(40, int(days))))})


# --------------------------------------------------------------------------------------------- audit files
def _file_kind(n):
    n = n.lower()
    return "csv" if n.endswith(".csv") else "md" if n.endswith(".md") else "json" if n.endswith(".json") else \
        "txt" if n.endswith(".txt") else "py" if n.endswith(".py") else "other"


def handoff_list(folder: str = HANDOFF) -> dict:
    files = []
    if os.path.isdir(folder):
        for root, _dirs, names in os.walk(folder):
            for n in sorted(names):
                p = os.path.join(root, n)
                rel = os.path.relpath(p, folder).replace(os.sep, "/")
                try:
                    files.append({"name": rel, "size": os.path.getsize(p), "kind": _file_kind(n), "mtime": int(os.path.getmtime(p))})
                except OSError:
                    pass
    head = ""
    rd = os.path.join(folder, "README.md")
    if os.path.exists(rd):
        with open(rd, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                if ln.startswith("## A."):
                    head = ln[3:].strip()
                    break
    return {"folder": os.path.relpath(folder, ROOT).replace(os.sep, "/"), "files": files, "verdict": head}


def doc_path(name: str, folder: str = HANDOFF) -> str | None:
    """A file of the audit folder by its listed name only: no absolute path, no '..', text types only."""
    name = str(name or "").replace("\\", "/").strip()
    if not name or name.startswith("/") or ".." in name.split("/") or not name.lower().endswith(TEXT_EXT):
        return None
    p = os.path.realpath(os.path.join(folder, name))
    base = os.path.realpath(folder)
    if not p.startswith(base + os.sep) or not os.path.isfile(p):
        return None
    return p


@router.get("/api/next/cc/handoff")
def r_handoff():
    return _J(handoff_list())


@router.get("/api/next/cc/doc")
def r_doc(name: str = "README.md"):
    p = doc_path(name)
    if not p:
        return _J({"error": "unknown file (only the audit folder's .md / .csv / .txt / .json files)"}, 404)
    with open(p, encoding="utf-8", errors="replace") as fh:
        text = fh.read(MAX_DOC + 1)
    return _J({"name": name, "kind": _file_kind(name), "text": text[:MAX_DOC], "truncated": len(text) > MAX_DOC,
               "mtime": int(os.path.getmtime(p))})


def _csv_rows(path: str) -> list:
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return []
    with _lock:
        hit = _cache.get(path)
        if hit and hit[0] == mt:
            return hit[1]
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        rows = list(csv.DictReader(fh))
    with _lock:
        _cache[path] = (mt, rows)
    return rows


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return v


def setups_view(folder: str = HANDOFF) -> dict:
    rows = _csv_rows(os.path.join(folder, "PERFORMANCE_BY_SETUP.csv"))
    out = []
    for r in rows:
        out.append({k: (_num(v) if k not in ("setup_id", "book", "span", "label", "evals_pass_fail_stuck_open") else v) for k, v in r.items()})
    return {"rows": out, "source": "research/handoff/2026-10-25/PERFORMANCE_BY_SETUP.csv",
            "spans": sorted({r.get("span") for r in out if r.get("span")}), "books": sorted({r.get("book") for r in out if r.get("book")})}


@router.get("/api/next/cc/setups")
def r_setups():
    return _J(setups_view())


@router.get("/api/next/cc/atlas_trades")
def r_atlas_trades(book: str = "", year: str = "2026"):
    rows = _csv_rows(os.path.join(HANDOFF, "ATLAS_TRADE_LEDGER.csv"))
    books = sorted({r.get("book") for r in rows if r.get("book")})
    want = book or next((b for b in books if "PATH" in b.upper() or "ROUTED" in b.upper()), books[0] if books else "")
    keep = ("day", "dir", "r", "pnl", "risk_pts", "qty", "exit", "trigger", "setup_id", "entry_et", "exit_et", "entry_px", "stop_px",
            "target_px", "exit_px")
    sel = [{k: (_num(r.get(k)) if k in ("dir", "r", "pnl", "risk_pts", "qty", "entry_px", "stop_px", "target_px", "exit_px") else r.get(k))
            for k in keep} for r in rows if r.get("book") == want and (year == "all" or str(r.get("day", "")).startswith(year))]
    return _J({"book": want, "books": books, "year": year, "rows": sel[::-1]})


# --------------------------------------------------------------------------------------------- runbook
def runbook_view(folder: str = HANDOFF) -> dict:
    p = os.path.join(folder, "STARTUP_AND_RECOVERY_RUNBOOK.md")
    if not os.path.exists(p):
        return {"error": "STARTUP_AND_RECOVERY_RUNBOOK.md not found", "sections": []}
    with open(p, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    secs, cur = [], {"title": "Intro", "body": []}
    for ln in text.splitlines():
        if ln.startswith("## "):
            if cur["body"] or cur["title"] != "Intro":
                secs.append(cur)
            cur = {"title": ln[3:].strip(), "body": []}
        elif ln.startswith("# "):
            continue
        else:
            cur["body"].append(ln)
    secs.append(cur)
    for s in secs:
        s["body"] = "\n".join(s["body"]).strip().strip("-").strip()
        s["emergency"] = "EMERGENCY" in s["title"].upper()
    cmds = sorted(set(re.findall(r"`((?:python|powershell)[^`]+)`", text)))
    return {"source": "research/handoff/2026-10-25/STARTUP_AND_RECOVERY_RUNBOOK.md", "sections": secs, "commands": cmds,
            "mtime": int(os.path.getmtime(p))}


@router.get("/api/next/cc/runbook")
def r_runbook():
    return _J(runbook_view())


# --------------------------------------------------------------------------------------------- data files
def data_files(now: int | None = None) -> list:
    now = int(now or time.time())
    d = os.path.join(ROOT, "data")
    out = []
    for n in ("NQ_5m.csv", "NQ_1m.csv", "ES_5m.csv", "ES_1m.csv", "VIX_1d.csv", "VXN_1d.csv"):
        p = os.path.join(d, n)
        if os.path.exists(p):
            out.append({"name": n, "size": os.path.getsize(p), "age_s": now - int(os.path.getmtime(p))})
        else:
            out.append({"name": n, "missing": True})
    nb = os.path.join(d, "nt_bars")
    if os.path.isdir(nb):
        fs = [os.path.join(nb, f) for f in os.listdir(nb)]
        fs = [f for f in fs if os.path.isfile(f)]
        if fs:
            newest = max(fs, key=os.path.getmtime)
            out.append({"name": "nt_bars/ (NinjaTrader archive)", "files": len(fs), "age_s": now - int(os.path.getmtime(newest))})
    return out


@router.get("/api/next/cc/data_files")
def r_data_files():
    return _J({"rows": data_files()})

