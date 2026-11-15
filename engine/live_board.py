"""Live board (2026-10-26, owner: "improve the dashboard with more features, useful data stuff"; read-only).

One pure function, build(inp), turns the blocks the PC heartbeat already carries (engine/heartbeat.Heartbeat.payload:
health, brain, second, acct, crit, live_pub ...) plus the accounts / goals / eval-odds blocks the dashboards already have
into the decision data both dashboards draw (shared renderer boardcore.js, byte-identical in tools/web_public/ and
web_next/js/next/):

  accounts   "Right now" per account (Zlarior 50K, ATLAS 25K): balance, room to the floor, $ to the target, today's
             P&L, what the strategy waits for (Bot Brain stage / each ATLAS member's state), the next entry windows as
             absolute times (the page counts down), the micros it would trade now at a typical stop (brain sizing; ATLAS:
             its last sizing when the bot exposes one), every guard blocking new entries with its one-line fix
  map        today's map: the LIT levels, the VIX-band objective up / down, the 18:00 open and the price, each with its
             distance in points and $ per micro (MNQ $2 a point)
  health     the bot health strip: poll time (warn above 5 s), feed age 1m / 5m, NinjaTrader, clock drift, last error,
             heartbeat age, phone live feed
  progress   this week's trades vs the goal (2-4 Zlarior, 3-4 ATLAS), eval session X of 10, 2-week pass / fail odds
             (research/lit/uprisk_eval.json row at the live switches; ATLAS research/second/atlas.json eval25k) and $ a
             month expected (2026 H2 backtest) vs actual
  trades     one trade log for both accounts (PC live trades + exits, paper rows marked), newest first; the pages add
             the trade pictures (engine/trade_chart.py) and the CSV export

Where it runs (never trades, never routes, never sizes, never writes a file):
  PC     GET /api/next/board (engine/board_api.py) from the running bot
  cloud  data.json / home.json "board" (tools/build_web_dashboard.py) from the PC heartbeat the cloud monitor read
  phone  live.json "board" (engine/live_publish.py, every 60 s from the PC), laid over data.json by live.js

  python -X utf8 -m engine.live_board [heartbeat.json]      prints the board of a heartbeat file (default: the branch's)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
VERSION = 1
USD_PT = 2.0                        # MNQ: $2 a point a micro
POLL_WARN_MS = 5000                 # owner 2026-10-26: a poll above 5 s is a warning
HB_STALE_S = 900                    # heartbeat older than 15 min: amber; the cloud's "Surface offline" is 30 min
FEED_WARN_S = 180                   # a 1m bar older than 3 min while the market is open
LIT_WINDOW = (120, 930)             # entries 02:00-15:30 ET
LIT_KEYS = ("lit",)
ATLAS_KEYS = ("ema_lon_vix", "macd_sweep", "sr_nyreclaim")
ATLAS_NAMES = {"ema_lon_vix": "EMA", "macd_sweep": "MACD", "sr_nyreclaim": "S/R"}
# the routed ATLAS members' own entry hours (engine/second.py states "window"; EMA skips Mondays, its "nomon" regime)
ATLAS_WINDOWS = {"ema_lon_vix": [(180, 570)], "macd_sweep": [(120, 300), (570, 660)], "sr_nyreclaim": [(570, 720)]}
ATLAS_NO_MONDAY = {"ema_lon_vix"}
SESSIONS_GOAL = 10
PLANS = {"lit": {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "dll": 1000.0, "max_micros": 40, "max_day": 1},
         "atlas": {"start": 25000.0, "target": 1500.0, "mll": 1000.0, "dll": 600.0, "max_micros": 20, "max_day": 2}}

# one-line fixes for the guards that block new entries (what the owner does, in plain words)
FIX = {
    "clock": "Windows: Settings > Time & language > Date & time > Sync now",
    "feed": "NinjaTrader: right-click the MNQ 5-minute chart > Reload NinjaScript (or re-add LE_BarFeed)",
    "nt": "NinjaTrader Control Center > Connections: connect your login",
    "startup": "Wait one poll; if it stays, the Runbook (section 2) has the fix for each reason",
    "kill": "Kill switch used today: the bot trades again from the next session",
    "stopped": "On the Surface: Bot Control > Start (or START_BOT.bat)",
    "silent": "Check the Surface is on, awake and online, with the bot window open",
    "news": "Nothing to do: entries resume on their own after the news window",
    "loss": "Nothing to do: the daily loss limit resets at the next session (18:00 ET)",
    "passed": "Eval passed: no new trades on it. Next step: the funded account (Goals page)",
    "failed": "Eval failed: no new trades on it. Buy a new eval when you are ready",
    "atlas_passed": "Eval passed: no new trades on it. Request the funded account at MFFU, then Start page > Accounts > Passed → funded "
                    "with its new Name",
    "funded_end": "Funded account done (lost or under $100 of room): no new trades on it. Buy a new 25K eval for ATLAS",
    "funded_grad": "5 sim payouts done: MFFU moves the account to live (you must be present); the bot does not trade it",
    "account": "Start & Accounts page on the PC: check this account's line",
    "pause": "You paused the bot: un-pause it on Bot Control",
    "error": "Bot log on the PC shows the full error; restart the bot if it repeats",
}


# ------------------------------------------------------------------------------------------------ small helpers
def _f(x, d=None):
    try:
        v = float(x)
        return v if v == v else d
    except (TypeError, ValueError):
        return d


def _i(x, d=None):
    v = _f(x)
    return d if v is None else int(v)


def _r(x, n=2):
    v = _f(x)
    return None if v is None else round(v, n)


def _clean(s, n=240) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    s = re.sub(r"([A-Za-z]:\\[^\s\"']+|/(?:home|Users|root)/[^\s\"']+)", "<path>", s)
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def _money(v, sign=False) -> str:
    v = _f(v, 0.0)
    s = f"${abs(v):,.0f}"
    return ("-" + s) if v < 0 else (("+" + s) if sign and v > 0 else s)


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def quiet_days(trade_ts, start, now) -> int | None:
    """MFFU's inactivity rule (7 calendar days with no trade can close an eval): calendar days (ET) from the last trade
    (unix seconds, or 'YYYY-MM-DD' days), or from the eval's start when it has none, to now. None when neither is known."""
    try:
        days = []
        for x in trade_ts or []:
            if isinstance(x, str) and len(x) >= 10:
                days.append(dt.date.fromisoformat(x[:10]))
            elif isinstance(x, (int, float)) and x > 0:
                days.append(_et(x).date())
        if start:
            s0 = dt.date.fromisoformat(str(start)[:10])
            days = [d for d in days if d >= s0] or [s0]
        if not days:
            return None
        return max(0, (_et(now).date() - max(days)).days)
    except Exception:
        return None


def trading_day(t) -> str:
    """CME trading day: 18:00 ET starts the next day's session (engine/accounts.trading_day)."""
    return (_et(t) + dt.timedelta(hours=6)).date().isoformat()


def _hm(m: int) -> str:
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _closed(day: str) -> bool:
    try:
        from . import guards
        return bool(guards.full_closure(day))
    except Exception:
        return False


def _early(day: str):
    try:
        from . import lit_live
        ec = lit_live.early_close(day)
        return int(ec) if isinstance(ec, (int, float)) else None
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ entry windows
def next_windows(now: int, ranges, n: int = 3, no_monday: bool = False, days: int = 12) -> list:
    """The next n entry windows [{"open_t", "close_t", "day", "label"}] as absolute times (ET minute ranges on trading
    weekdays; CME full closures skipped; an early close ends the window 15 min before the halt). The current window is
    included while it is open (open_t <= now < close_t)."""
    out = []
    d0 = _et(now).date()
    for i in range(days + 1):
        d = d0 + dt.timedelta(days=i)
        if d.weekday() >= 5 or (no_monday and d.weekday() == 0) or _closed(d.isoformat()):
            continue
        ec = _early(d.isoformat())
        for a, z in ranges:
            zz = min(z, ec - 15) if ec is not None else z
            if zz <= a:
                continue
            o = int(dt.datetime(d.year, d.month, d.day, a // 60, a % 60, tzinfo=ET).timestamp())
            c = int(dt.datetime(d.year, d.month, d.day, zz // 60, zz % 60, tzinfo=ET).timestamp())
            if c <= now:
                continue
            out.append({"open_t": o, "close_t": c, "day": d.isoformat(), "label": f"{d:%a} {_hm(a)}-{_hm(zz)} ET",
                        **({"early_close": _hm(ec)} if ec is not None else {})})
            if len(out) >= n:
                return out
    return out


def window_state(now: int, wins: list) -> dict:
    """{"open": bool, "open_t", "close_t", "text"} of the first window that has not closed yet."""
    w = next((x for x in wins if x["close_t"] > now), None)
    if not w:
        return {"open": False, "text": "no entry window in the next days"}
    if w["open_t"] <= now:
        return {"open": True, "open_t": w["open_t"], "close_t": w["close_t"], "text": f"entry window open until {_et(w['close_t']):%H:%M} ET"}
    return {"open": False, "open_t": w["open_t"], "close_t": w["close_t"], "text": f"next entry window {w['label']}"}


# ------------------------------------------------------------------------------------------------ blocks (guards)
def _fix_for(text: str) -> tuple[str, str]:
    """(kind, one-line fix) for a guard sentence."""
    t = str(text or "").lower()
    if "clock" in t:
        return "clock", FIX["clock"]
    if "feed" in t or "stale" in t or "bars" in t:
        return "feed", FIX["feed"]
    if "ninjatrader" in t and ("connect" in t or "down" in t):
        return "nt", FIX["nt"]
    if "startup" in t or "reconcil" in t or "disarmed" in t:
        return "startup", FIX["startup"]
    if "news" in t or "tier-1" in t:
        return "news", FIX["news"]
    if "daily loss" in t or "soft daily" in t:
        return "loss", FIX["loss"]
    if "kill" in t:
        return "kill", FIX["kill"]
    if "pause" in t or "flattened remotely" in t:
        return "pause", FIX["pause"]
    if "passed" in t:
        return "passed", FIX["passed"]
    if "failed" in t:
        return "failed", FIX["failed"]
    return "other", FIX["account"]


def _block(text, scope="both", kind=None, fix=None) -> dict:
    k, f = _fix_for(text)
    return {"text": _clean(text, 200), "kind": kind or k, "fix": fix or f, "scope": scope}


def global_blocks(pc: dict, now: int, where: str = "pc") -> list:
    """Guards that stop new entries on BOTH accounts (each account's own guards apply the same checks: clock, feed,
    startup reconcile, kill, the bot stopped / silent)."""
    h, br = _d(pc.get("health")), _d(pc.get("brain"))
    out, seen = [], set()

    def add(b):
        if b["kind"] in seen:
            return
        seen.add(b["kind"])
        out.append(b)

    if pc and pc.get("present") is not False:
        if pc.get("running") is False or (h and h.get("running") is False):
            add(_block("The bot is stopped: no new entries", kind="stopped", fix=FIX["stopped"]))
        elif pc.get("silent"):
            add(_block(f"No check-in from the PC for {round((_i(pc.get('age_s'), 0) or 0) / 60)} min", kind="silent", fix=FIX["silent"]))
    if pc.get("present") is False:
        add(_block("The PC has not reported yet (no heartbeat)", kind="silent", fix=FIX["silent"]))
    if h.get("kill") or pc.get("kill"):
        add(_block("Kill switch used today: no orders until the next session", kind="kill"))
    for g in _l(_d(br.get("guards")).get("blocking")):
        add(_block(g))
    f = _d(h.get("feed"))
    if f.get("entries_blocked") or f.get("stale"):
        add(_block(f.get("block") or "FEED STALE: NinjaTrader bars are old, new entries blocked", kind="feed"))
    nt = _d(h.get("nt"))
    if nt and nt.get("connected") is False and _d(h.get("account")).get("adapter") == "ninjatrader":
        add(_block("NinjaTrader is not connected", kind="nt"))
    for c in _l(pc.get("crit")):
        c = _d(c)
        if c.get("title"):
            add(_block(f"{c.get('title')}: {c.get('body') or ''}".strip(": ")))
    return out


# ------------------------------------------------------------------------------------------------ accounts
def _pc_account(accounts) -> dict:
    A = [a for a in _l(accounts) if isinstance(a, dict) and a.get("id") and not a.get("error")]
    pc = next((a for a in A if a.get("source") == "pc" and a.get("kind") in ("eval", "funded", None)), None)
    cl = next((a for a in A if a.get("source") == "cloud"), None)
    if pc and (_d(pc.get("conn")).get("connected") or _d(pc.get("eval")).get("anchor") or pc.get("trades")):
        return pc
    return cl or pc or {}


def _waiting_lit(br: dict, pc: dict) -> str:
    st = _d(br.get("stage"))
    w = st.get("waiting") or pc.get("model_state") or _d(_d(pc.get("health")).get("lit")).get("text") or ""
    w = re.sub(r"\s*BLOCKED:.*$", "", str(w)).strip()          # the blocks are listed apart, with their fix
    return _clean(w, 320)


def lit_now(pc: dict, accounts, now: int, brain: dict | None = None) -> dict:
    br = _d(brain if brain is not None else pc.get("brain"))
    a = _pc_account(accounts)
    ev = _d(a.get("eval"))
    P = PLANS["lit"]
    acct = _d(_d(pc.get("health")).get("account"))
    sz = _d(br.get("sizing"))
    sev = _d(sz.get("eval"))
    bal = _f(ev.get("balance"))
    room = _f(ev.get("room"), _f(sev.get("room")))
    out = {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "method": "LIT",
           "broker": a.get("broker_account") or acct.get("name"), "badge": a.get("badge") or acct.get("label"),
           "source": "PC bot" if a.get("source") == "pc" else "cloud paper" if a.get("source") == "cloud" else "none",
           "balance": bal, "floor": _f(ev.get("floor")), "room": room, "mll": _f(ev.get("mll"), P["mll"]),
           "to_target": _f(ev.get("to_target"), _f(sev.get("to_target"))), "target_balance": _f(ev.get("target_balance"), P["start"] + P["target"]),
           "profit": _f(ev.get("profit")), "today_pnl": _f(_d(a.get("pnl")).get("today"), _f(ev.get("today"))),
           "week_pnl": _f(_d(a.get("pnl")).get("week")), "status": ev.get("status") or sev.get("status") or "open",
           "session": _i(ev.get("session"), _i(sev.get("session"))), "sessions": _i(ev.get("sessions"), SESSIONS_GOAL),
           "dll": _f(ev.get("dll"), P["dll"]), "dll_used": _f(ev.get("dll_used")),
           "max_day": P["max_day"], "trades_today": _i(br.get("day_trades"), 0)}
    out["room_frac"] = None if room is None or not out["mll"] else round(max(0.0, min(1.0, room / out["mll"])), 4)
    st = _d(br.get("stage"))
    out["stage"] = {"key": st.get("key"), "label": st.get("label"), "n": st.get("n"), "of": len(_l(br.get("stages"))) or None,
                    "dir": st.get("dir")}
    out["stages"] = [[s[0], s[1]] for s in _l(br.get("stages")) if isinstance(s, (list, tuple)) and len(s) >= 2]
    out["waiting"] = _waiting_lit(br, pc)
    pa = _d(pc.get("acct"))                  # the PC's own ledger of the 50K: its trades (day) and the eval's start
    out["quiet_days"] = quiet_days([t.get("day") for t in _l(pa.get("trades")) if isinstance(t, dict)],
                                   _d(pa.get("eval")).get("start"), now) if pa else None
    rules = _d(br.get("rules"))
    if rules.get("monday_today"):
        out["rule_note"] = {"high": "Monday rule: Friday's high was taken, so shorts only today.",
                            "low": "Monday rule: Friday's low was taken, so longs only today."}.get(rules["monday_today"])
    wins = next_windows(now, [LIT_WINDOW])
    out["windows"] = wins
    out["window"] = {**window_state(now, wins), "hours": "02:00-15:30 ET"}
    if sz.get("qty") is not None:
        out["micros"] = {"qty": _i(sz.get("qty")), "risk_pts": _r(sz.get("risk_pts"), 1), "tgt_pts": _r(sz.get("tgt_pts"), 1),
                         "risk_usd": _r(sz.get("risk_usd"), 0), "win_usd": _r(sz.get("win_usd"), 0), "mode": sz.get("mode"),
                         "what": _clean(sz.get("what"), 160),
                         "steps": [{"label": _clean(s.get("label"), 40), "value": _clean(s.get("value"), 30)}
                                   for s in _l(sz.get("steps")) if isinstance(s, dict)][:9],
                         "typical": "no setup is live" in str(sz.get("what") or "")}
    else:
        out["micros"] = None
    pos = a.get("position") if isinstance(a.get("position"), dict) else None
    out["position"] = {k: pos.get(k) for k in ("side", "dir", "qty", "entry", "stop", "target", "be", "be_trigger", "entry_t", "unrealized_usd",
                                               "unrealized_r", "risk_usd", "target_usd") if pos.get(k) is not None} if pos else None
    today = trading_day(now)
    n_today = sum(1 for t in _l(a.get("trades")) if isinstance(t, dict) and str(t.get("day")) == today)
    if out["position"] and _i(out["position"].get("entry_t")) and trading_day(out["position"]["entry_t"]) == today \
            and not any(isinstance(t, dict) and _i(t.get("entry_t")) == _i(out["position"]["entry_t"]) for t in _l(a.get("trades"))):
        n_today += 1
    out["trades_today"] = max(out["trades_today"], n_today)
    blocks = []
    el = _d(_d(pc.get("health")).get("eval_life"))
    if out["status"] in ("passed", "failed"):
        blocks.append(_block(f"Eval {out['status']}", scope="lit", kind=out["status"]))
    elif el.get("trading") and el["trading"] not in ("trading", "open", None):
        blocks.append(_block(f"Eval: {el['trading']}", scope="lit"))
    if out["trades_today"] >= P["max_day"] and not out["position"]:
        out["done_today"] = True
    out["blocks"] = blocks
    # the real-account ledger the Today cards check (2026-10-28): the eval's booked days, its anchor and the last orders
    out["eval_start"] = ev.get("start")
    out["anchor"] = ev.get("anchor") if isinstance(ev.get("anchor"), dict) else None
    out["prior"] = _f(ev.get("prior"))
    out["days"] = [[str(d[0]), _r(d[1], 2)] for d in _l(a.get("days")) if isinstance(d, (list, tuple)) and len(d) >= 2][-30:]
    out["orders"] = _orders(a.get("orders"))
    return out


def _orders(rows, n: int = 20) -> list:
    """The last orders of an account, compact: refused ones carry NinjaTrader's (or the bot's) reason."""
    out = []
    for o in _l(rows)[-n:]:
        o = _d(o)
        if not o.get("side"):
            continue
        r = {"t": _i(o.get("t")), "side": o.get("side"), "qty": _i(o.get("qty")), "entry_t": _i(o.get("entry_t")),
             "ok": o.get("ok") if isinstance(o.get("ok"), bool) else (_d(o.get("result")).get("ok") if isinstance(o.get("result"), dict) else None),
             "reason": _clean(o.get("reason"), 30) if o.get("reason") else None, "pnl": _r(o.get("pnl"), 2),
             "error": _clean(o.get("error") or _d(o.get("result")).get("error"), 200) if (o.get("error") or _d(o.get("result")).get("error")) else None,
             "src": o.get("src") or o.get("strategy")}
        out.append({k: v for k, v in r.items() if v is not None})
    return out


def ledger_check(lit: dict, atlas: dict, real_rows: list, now: int | None = None) -> list:
    """Days the eval books $ on with no real trade listed (2026-10-28: a -$965.20 day of refused orders made a fake
    'eval near the floor: $140 left'). Each flag says how big it is and the room if it is a ledger error. Reports only."""
    out = []
    lit = _d(lit)
    days_traded = {str(r.get("day")) for r in _l(real_rows) if _d(r).get("acct") == "lit"}
    anc = _d(lit.get("anchor"))
    after = str(anc.get("as_of") or lit.get("eval_start") or "")
    for d, v in _l(lit.get("days")):
        if d == "0000-00-00" or (after and d <= after) or v is None or abs(v) < 1 or d in days_traded:
            continue
        room = _f(lit.get("room"))
        mll = _f(lit.get("mll"), PLANS["lit"]["mll"])
        alt = None if room is None else round(min(mll, room - v) if v < 0 else max(0.0, room - v), 2)
        out.append({"acct": "lit", "day": d, "usd": v, "room_if_error": alt,
                    "text": f"Zlarior's eval books {_money(v, sign=True)} on {d} but no real trade is listed that day. "
                            f"If NinjaTrader filled nothing that day this is a ledger error: room would be about {_money(alt)}, not "
                            f"{_money(room)}. Check the balance on the MFFU dashboard."})
    at = _d(atlas)
    today = [r for r in _l(real_rows) if _d(r).get("acct") == "atlas" and not r.get("open") and r.get("usd") is not None
             and str(r.get("day")) == trading_day(int(now or time.time()))]
    if today and at.get("today_pnl") is not None and abs(sum(float(r["usd"]) for r in today) - float(at["today_pnl"])) >= 1:
        s = sum(float(r["usd"]) for r in today)
        out.append({"acct": "atlas", "day": today[0]["day"], "usd": round(float(at["today_pnl"]) - s, 2),
                    "text": f"ATLAS books {_money(at['today_pnl'], sign=True)} today but its real trades add up to {_money(s, sign=True)}."})
    return out


def real_block(lit: dict, atlas: dict, trades_all: list, band: dict | None = None, now: int | None = None) -> dict:
    """Real (live account) trades only, the ledger check and Zlarior's backtest cone (2026 H2, eval sizing)."""
    rows = [r for r in _l(trades_all) if _d(r).get("src") == "live"]
    out = {"trades": rows, "checks": ledger_check(lit, atlas, rows, now)}
    try:
        from . import health_band as HB
        b = band if band is not None else HB.load()
        Bn = _d(_d(_d(b).get("bands")).get("H2"))
        if Bn.get("usd_eval"):
            n = max(15, (_i(_d(lit).get("session"), 0) or 0) + 5)
            out["cone"] = {**HB.cone(Bn, n, "usd_eval"), "src": f"2026 H2 backtest bootstrap ({Bn.get('from')} to {Bn.get('to')}), eval sizing"}
    except Exception:
        pass
    return out


def real_week(prog: dict | None, real_rows, lit: dict, atlas: dict) -> dict:
    """2026-10-28: once an account trades for real, its week strip counts REAL trades and real $ (the paper members'
    trades and $, e.g. a +$3,879 paper MACD trade at 7 micros, are not the account's). Edits prog in place; returns
    which accounts switched."""
    done = {}
    P = _d(prog)
    for key, acc in (("lit", lit), ("atlas", atlas)):
        k = _d(P.get(key))
        wk = _d(k.get("week"))
        start = str(_d(acc).get("eval_start") or "")
        if not wk or not start or not _d(acc).get("badge"):
            continue
        rows = [r for r in _l(real_rows) if _d(r).get("acct") == key and _d(r).get("src", "live") == "live"]
        days = _l(wk.get("days"))
        if not days:
            continue
        n_tot, usd_tot = 0, 0.0
        for d in days:
            if not isinstance(d, dict):
                continue
            mine = [r for r in rows if str(r.get("day")) == str(d.get("day"))]
            d["n"] = len(mine)
            d["usd"] = round(sum(float(r.get("usd") or 0) for r in mine if not r.get("open")), 2)
            n_tot += d["n"]
            usd_tot += d["usd"]
        lo, hi = _i(wk.get("lo"), 2), _i(wk.get("hi"), 4)
        wk.update(n=n_tot, usd=round(usd_tot, 2), src="real",
                  status="met" if lo <= n_tot <= hi else "over" if n_tot > hi else "on_pace",
                  sentence=f"{'Zlarior' if key == 'lit' else 'ATLAS'}: {n_tot} real trade{'' if n_tot == 1 else 's'} this week "
                           f"({_money(usd_tot, sign=True)}), goal {lo}-{hi}.")
        done[key] = n_tot
    return done


# BLITZ, the scalper, on its OWN account (engine/account_c.py; heartbeat "account_c", only when it is on): its checks
# are the 1m closes 11:00, 11:30 ... 15:30 ET on weekdays (entries at the next bar's open)
BLITZ_WINDOW = (659, 931)


def blitz_now(pc: dict, now: int) -> dict:
    """The "Right now" card of account C (same keys as the Zlarior / ATLAS cards): balance, room, $ to the target, today,
    what BLITZ waits for, the next check, the micros of its last entry, its position, the blocks (account off, daily loss,
    the performance contract's pause, eval over) and its scorecard. Only built when the heartbeat carries "account_c"."""
    c = _d(pc.get("account_c"))
    ev = _d(c.get("eval"))
    R = _d(c.get("rules"))
    mll = _f(R.get("mll"), 1000.0)
    bal, room = _f(ev.get("balance")), _f(ev.get("room"))
    funded = c.get("stage") == "funded"
    out = {"id": "blitz", "name": "BLITZ", "plan": c.get("plan_label") or "MFFU Builder 25K", "method": "noise-area 1m scalp",
           "broker": c.get("account"), "badge": c.get("kind"), "real": c.get("real"), "configured": bool(c), "source": "PC bot (account C)",
           "balance": bal, "floor": _f(ev.get("floor")), "room": room, "mll": mll, "to_target": _f(ev.get("to_target")),
           "target_balance": _f(ev.get("target"), _f(R.get("start"), 25000.0) + _f(R.get("target"), 1500.0)),
           "profit": _f(ev.get("profit")), "today_pnl": _f(c.get("day_pnl"), _f(ev.get("today"))), "status": ev.get("status") or "open",
           "session": _i(ev.get("session")), "sessions": None if funded else SESSIONS_GOAL, "dll": _f(ev.get("dll"), _f(R.get("dll"), 600.0)),
           "max_day": 6, "trades_today": _i(c.get("entries_today"), 0), "max_micros": _i(ev.get("max_micros"), 20),
           "eval_start": ev.get("start"), "orders": _orders(c.get("routed")), "stage": "funded" if funded else "eval",
           "scorecard": c.get("scorecard"), "paused": c.get("paused")}
    out["room_frac"] = None if room is None or not mll else round(max(0.0, min(1.0, room / mll)), 4)
    st = _d(c.get("state"))
    out["waiting"] = _clean(st.get("text"), 240) or "Waiting for the next check (11:00, 11:30 ... 15:30 ET)."
    wins = next_windows(now, [BLITZ_WINDOW], n=2)
    out["window"] = {**window_state(now, wins), "who": "BLITZ", "hours": "checks 11:00-15:30 ET"}
    ls = _d(c.get("size"))
    out["micros"] = ({"qty": _i(ls.get("qty")), "t": _i(ls.get("t")), "reasons": [_clean(x, 140) for x in _l(ls.get("reasons"))][-2:], "last": True}
                     if ls.get("qty") is not None else
                     {"qty": None, "last": False, "what": "Sized at each entry from its own stop (1.5 x the 5m ATR): 40% of the room to the "
                                                         "floor, at most $600 and 0.9 x the daily loss left, max 20 micros."})
    pos = c.get("open") if isinstance(c.get("open"), dict) else None
    out["position"] = {k: pos.get(k) for k in ("side", "dir", "qty", "entry", "stop", "target", "entry_t", "strategy", "time_exit_t")
                       if pos.get(k) is not None} if pos else None
    blocks = []
    if c.get("disabled"):
        blocks.append(_block(f"Account C off: {c['disabled']}", scope="blitz", kind="account"))
    if c.get("locked"):
        blocks.append(_block(f"Locked out today: {c['locked']}", scope="blitz"))
    if c.get("paused"):
        blocks.append(_block(f"BLITZ paused by its performance contract: {_d(c.get('paused')).get('why')}", scope="blitz", kind="paused",
                             fix="Read BLITZ_STRATEGY.md 'Kill switch'; resume only on purpose: python -X utf8 -m engine.account_c --resume"))
    if out["status"] in ("passed", "failed", "stuck", "lost", "graduated"):
        blocks.append(_block(f"{'Funded account' if funded else 'Eval'} {out['status']}", scope="blitz",
                             kind="passed" if out["status"] in ("passed", "graduated") else "failed",
                             fix="Request the funded account at MFFU, then Start page > BLITZ · 25K > Passed → funded (the bot never "
                                 "switches by itself)." if out["status"] == "passed" else None))
    out["blocks"] = blocks
    return out


def _member_line(k: str, s: dict, now: int) -> dict:
    st = _d(s.get("state"))
    wins = next_windows(now, ATLAS_WINDOWS.get(k, []), n=2, no_monday=k in ATLAS_NO_MONDAY)
    return {"key": k, "short": s.get("short") or ATLAS_NAMES.get(k, k), "label": s.get("label"), "stage": st.get("stage"),
            "text": _clean(st.get("text"), 200), "hours": st.get("window"), "route": bool(s.get("route")),
            "first_fail": _d(s.get("brain")).get("first_fail"), "windows": wins, "window": window_state(now, wins)}


def atlas_now(pc: dict, now: int, second: dict | None = None) -> dict:
    S = _d(second if second is not None else pc.get("second"))
    R = _d(S.get("route"))
    ab = _d(R.get("account_b"))
    ev = _d(ab.get("eval"))
    P = PLANS["atlas"]
    keys = [k for k in (ab.get("keys") or ATLAS_KEYS) if k in ATLAS_WINDOWS] or list(ATLAS_KEYS)
    strat = _d(S.get("strategies"))
    members = [_member_line(k, _d(strat.get(k)), now) for k in keys]
    bal = _f(ev.get("balance"))
    room = _f(ev.get("room"))
    out = {"id": "atlas", "name": "ATLAS", "plan": ab.get("plan_label") or "MFFU Builder 25K", "method": "EMA · MACD · S/R",
           "broker": ab.get("account"), "badge": ab.get("kind"), "configured": bool(ab),
           "source": "PC bot (account B)" if ab else "none",
           "balance": bal, "floor": _f(ev.get("floor")), "room": room, "mll": P["mll"],
           "to_target": _f(ev.get("to_target")), "target_balance": _f(ev.get("target"), P["start"] + P["target"]),
           "profit": _f(ev.get("profit")), "today_pnl": _f(ab.get("day_pnl"), _f(ev.get("today"))),
           "status": ev.get("status") or ("not set up" if not ab else "open"), "session": _i(ev.get("session")), "sessions": SESSIONS_GOAL,
           "dll": _f(ev.get("dll"), P["dll"]), "max_day": P["max_day"], "trades_today": _i(ab.get("entries_today"), 0),
           "max_micros": _i(ev.get("max_micros"), P["max_micros"]), "members": members,
           "eval_start": ev.get("start"), "orders": _orders(ab.get("routed")),
           "quiet_days": quiet_days([r.get("entry_t") for r in _l(ab.get("routed")) if isinstance(r, dict) and r.get("side") != "exit"
                                     and r.get("ok") is not False], ev.get("start"), now) if ab else None}
    out["room_frac"] = None if room is None else round(max(0.0, min(1.0, room / P["mll"])), 4)
    live_m = [m for m in members if m["stage"] not in (None, "off")]
    nxt = sorted([(m["window"].get("open_t") or 0, m) for m in members if m["window"].get("open_t")], key=lambda x: x[0])
    open_m = [m for m in members if m["window"].get("open")]
    if live_m:
        out["waiting"] = "; ".join(f"{m['short']}: {m['text']}" for m in live_m)
    elif nxt:
        m = nxt[0][1]
        out["waiting"] = f"All {len(members)} members are outside their hours. Next: {m['short']} at {_et(m['window']['open_t']):%a %H:%M} ET."
    else:
        out["waiting"] = "Waiting for the next session."
    first = open_m[0] if open_m else (nxt[0][1] if nxt else None)
    out["window"] = ({**first["window"], "who": first["short"], "hours": first["hours"]} if first else {"open": False, "text": "no entry window in the next days"})
    funded = ab.get("stage") == "funded"
    if funded:                  # ATLAS's funded account (engine/account_b.py stage "funded"): the payout tracker
        fd = _d(ab.get("funded"))
        out["stage"] = "funded"
        out["sessions"] = None
        out["funded"] = {k: fd.get(k) for k in ("status", "text", "buffer", "buffer_balance", "buffer_reached", "above_buffer",
                                                 "ask_at_balance", "to_ask", "buffer_frac", "cycle_profit", "cycle_days",
                                                 "cycle_days_need", "best_day", "best_day_pct", "cons_limit_pct", "cons_ok",
                                                 "more_days", "eligible_from", "eligible", "ready", "max_request", "to_you",
                                                 "payouts_n", "payouts_max", "paid_to_you", "lost", "graduated")}
        out["funded"]["text"] = _clean(fd.get("text"), 240)
        out["funded"]["why"] = [_clean(w, 140) for w in _l(fd.get("why"))][:4]
        out["eval_account"] = ab.get("eval_account")
    ls = _d(ab.get("size"))
    if ls.get("qty") is not None:
        out["micros"] = {"qty": _i(ls.get("qty")), "member": ATLAS_NAMES.get(ls.get("key"), ls.get("key")), "t": _i(ls.get("t")),
                         "reasons": [_clean(x, 120) for x in _l(ls.get("reasons"))][-3:], "last": True}
    elif funded:
        big = str(ab.get("plan") or "") == "builder50k"
        out["micros"] = {"qty": None, "last": False,
                         "what": f"Funded size at each entry from its own stop: 60% of the room to the floor, at most "
                                 f"{'$1,500' if big else '$750'}, a winner at most {'$2,000' if big else '$1,000'} (one max payout "
                                 f"request), the {_money(out['dll'])} daily loss, max {out['max_micros']} micros; no trade when 1 "
                                 "micro could reach the floor."}
    else:
        out["micros"] = {"qty": None, "last": False,
                         "what": f"Sized at each entry from its own stop: one winner covers what is left to the target, capped by the "
                                 f"room and the {_money(out['dll'])} daily loss, max {out['max_micros']} micros."}
    pos = ab.get("open") if isinstance(ab.get("open"), dict) else None
    out["position"] = {k: pos.get(k) for k in ("side", "dir", "qty", "entry", "stop", "target", "entry_t", "strategy", "key", "unrealized_usd")
                       if pos.get(k) is not None} if pos else None
    blocks = []
    if ab.get("disabled"):
        blocks.append(_block(f"Account B off: {ab['disabled']}", scope="atlas", kind="account"))
    if ab.get("locked"):
        blocks.append(_block(f"Locked out today: {ab['locked']}", scope="atlas"))
    if out["status"] in ("passed", "failed", "stuck") and not funded:
        blocks.append(_block(f"Eval {out['status']}", scope="atlas", kind="passed" if out["status"] == "passed" else "failed",
                             fix=FIX["atlas_passed"] if out["status"] == "passed" else None))
    if funded and out["status"] in ("lost", "stuck", "graduated"):
        blocks.append(_block(f"Funded account {out['status']}", scope="atlas", kind="passed" if out["status"] == "graduated" else "failed",
                             fix=FIX["funded_grad"] if out["status"] == "graduated" else FIX["funded_end"]))
    if not ab:
        blocks.append(_block("ATLAS account (account B) is not set up on the PC", scope="atlas", kind="account"))
    out["blocks"] = blocks
    return out


# ------------------------------------------------------------------------------------------------ today's map
def today_map(brain: dict | None, qty: int | None = None) -> dict:
    """The LIT levels, the VIX-band objective, the 18:00 open and the price, each with points and $ per micro."""
    br = _d(brain)
    px = _f(br.get("price"))
    vix = _d(_d(br.get("guards")).get("vix"))
    rows = []

    def row(label, price, kind, side=None, taken=None, note=None):
        p = _f(price)
        if p is None:
            return
        d = None if px is None else round(p - px, 2)
        rows.append({"label": _clean(label, 40), "price": round(p, 2), "kind": kind, "side": side, "taken": taken,
                     "dist": d, "usd_micro": None if d is None else round(abs(d) * USD_PT, 0),
                     "usd_size": None if d is None or not qty else round(abs(d) * USD_PT * int(qty), 0), **({"note": note} if note else {})})

    for lv in _l(br.get("levels")):
        lv = _d(lv)
        row(lv.get("label"), lv.get("price"), lv.get("kind") or "level", lv.get("side"), bool(lv.get("taken")),
            f"taken {lv['taken_hm']}" if lv.get("taken_hm") else None)
    if vix:
        row("VIX objective up", vix.get("up"), "target", "H", note="18:00 open + 1 VIX day move")
        row("VIX objective down", vix.get("dn"), "target", "L", note="18:00 open - 1 VIX day move")
        row("18:00 open", vix.get("open18"), "open")
    rows.sort(key=lambda r: -r["price"])
    above = [r for r in rows if r["dist"] is not None and r["dist"] > 0 and not r["taken"] and r["kind"] not in ("open", "target")]
    below = [r for r in rows if r["dist"] is not None and r["dist"] < 0 and not r["taken"] and r["kind"] not in ("open", "target")]
    atr = _f(br.get("atr"))
    rules = _d(br.get("rules"))
    return {"price": px, "atr": _r(atr, 2), "bar_hm": br.get("bar_hm"), "t": _i(br.get("t")), "usd_pt": USD_PT, "qty": qty,
            "vix": {k: _r(vix.get(k), 2) for k in ("vix", "vxn", "move", "open18", "up", "dn")} if vix else None,
            "sweep_pts": None if atr is None else round(float(rules.get("depth") or 0.5) * atr, 1),
            "nearest_above": above[-1] if above else None, "nearest_below": below[0] if below else None,
            "monday": rules.get("monday_today"), "levels": rows}


# ------------------------------------------------------------------------------------------------ health strip
def age_text(s) -> str:
    """50 s, 12 min, 3.4 h, 5 d."""
    s = max(0, int(s or 0))
    return f"{s} s" if s < 90 else f"{round(s / 60)} min" if s < 5400 else f"{s / 3600:.1f} h" if s < 172800 else f"{round(s / 86400)} d"


def _item(key, label, value, ok, detail="", fix="", t=None, warn=False) -> dict:
    return {"key": key, "label": label, "value": value, "ok": ok, "warn": bool(warn), "detail": _clean(detail, 200), "fix": fix,
            **({"t": int(t)} if t else {})}


def health_strip(pc: dict, now: int, hb: dict | None = None, clock: dict | None = None, blocks: list | None = None) -> dict:
    """The health items (ok True green / False red / None grey; warn = amber). Ages are given with the absolute time t
    so the page can keep counting."""
    h = _d(pc.get("health"))
    poll, f, nt = _d(h.get("poll")), _d(h.get("feed")), _d(h.get("nt"))
    br = _d(pc.get("brain"))
    running = pc.get("running") if pc.get("running") is not None else h.get("running")
    t_data = _i(pc.get("t"), now)
    items = []
    # 1. poll time
    pm = _i(poll.get("poll_ms"))
    if pm is None:
        items.append(_item("poll_ms", "Poll time", "—", None, "no poll timed yet"))
    else:
        slow = pm > POLL_WARN_MS
        items.append(_item("poll_ms", "Poll time", f"{pm / 1000:.1f} s", None if slow else True, f"the last bot poll took {pm / 1000:.1f} s"
                           + (f" (above {POLL_WARN_MS // 1000} s: late decisions; the PC is busy or a step is slow)" if slow else " (fine below 5 s)"),
                           FIX["error"] if slow else "", warn=slow))
    # 2. last poll age
    lt = _i(poll.get("last_ok_t")) or _i(poll.get("last_t"))
    if running is False:
        items.append(_item("loop", "Bot loop", "stopped", False, "the bot is stopped", FIX["stopped"]))
    elif lt:
        age = max(0, t_data - lt)
        items.append(_item("loop", "Last poll", age_text(age), age < 180 and not poll.get("consecutive_errors"),
                           f"{int(poll.get('consecutive_errors') or 0)} errors in a row" if poll.get("consecutive_errors") else "the loop runs", t=lt))
    # 3. feed 1m / 5m
    mo = f.get("market_open")
    for k, lab, tk, bar_s in (("age_1m_s", "Feed 1m", "last_1m_t", 60), ("age_5m_s", "Feed 5m", "last_5m_t", 300)):
        a = _i(f.get(k))
        bt = _i(f.get(tk))
        bt = None if bt is None else bt + bar_s                 # the bar's close: the age the bot reports counts from it
        if a is None:
            items.append(_item(k, lab, "—", None if not mo else False, "no bars yet" if mo else "market closed", FIX["feed"] if mo else ""))
            continue
        stale = bool(f.get("stale")) or (mo and a > (FEED_WARN_S if "1m" in lab else 600 + 120))
        items.append(_item(k, lab, age_text(a), (not stale) if mo is not False else None,
                           f"{f.get('used') or f.get('source') or 'feed'} bars, {age_text(a)} old" + ("" if mo is not False else " (market closed)"),
                           FIX["feed"] if stale else "", t=bt))
    # 4. NinjaTrader
    if nt:
        conns = _d(nt.get("connections"))
        items.append(_item("nt", "NinjaTrader", "connected" if nt.get("connected") else "not connected", bool(nt.get("connected")) and not nt.get("last_error"),
                           ", ".join(f"{k} {v}" for k, v in conns.items()) or (nt.get("last_error") or ""), "" if nt.get("connected") else FIX["nt"]))
    # 5. clock drift
    c = _d(clock)
    drift = _f(c.get("drift"), _f(_d(br.get("guards")).get("clock_drift_s")))
    mx = _f(c.get("max"), 5.0)
    if drift is None:
        items.append(_item("clock", "Clock drift", "—", None, "not checked yet (needs internet)"))
    else:
        bad = abs(drift) > mx or any(_d(b).get("kind") == "clock" for b in _l(blocks))     # the guard's own verdict wins
        near = not bad and abs(drift) >= 0.8 * mx
        items.append(_item("clock", "Clock drift", f"{abs(drift):.1f} s", not bad,
                           f"PC clock {abs(drift):.1f} s {'behind' if drift > 0 else 'ahead of'} internet time (entries stop above {mx:.0f} s)",
                           FIX["clock"] if bad or near else "", warn=near))
    # 6. last error
    le, let_ = poll.get("last_error"), _i(poll.get("last_error_t"))
    if le:
        recent = bool(poll.get("consecutive_errors")) or (let_ is not None and t_data - let_ < 900)
        items.append(_item("error", "Last error", _et(let_).strftime("%H:%M ET") if let_ else "yes", False if recent else None,
                           le if recent else f"{le} (an old one: the loop has run fine since)", FIX["error"] if recent else "", t=let_))
    else:
        items.append(_item("error", "Last error", "none", True, "no poll error since the start"))
    # 7. heartbeat age (the PC's 5-min check-in to the cloud / phone)
    hb = _d(hb)
    ht = _i(hb.get("t"))
    if ht:
        a = max(0, now - ht)
        items.append(_item("heartbeat", "Heartbeat", age_text(a), a < HB_STALE_S and hb.get("ok", True) is not False,
                           ("last check-in pushed" if hb.get("ok", True) is not False else "last push FAILED") + f" at {_et(ht):%H:%M} ET",
                           FIX["silent"] if a >= HB_STALE_S else "", t=ht))
    elif hb.get("enabled") is False:
        items.append(_item("heartbeat", "Heartbeat", "off", None, "heartbeat off on this PC (LE_HEARTBEAT=1 turns it on)"))
    # 8. phone live feed (live.json)
    lp = _d(pc.get("live_pub"))
    if lp.get("at"):
        a = max(0, now - int(lp["at"]))
        items.append(_item("live_pub", "Phone feed", age_text(a), bool(lp.get("ok")) and a < 600,
                           "phone live.json " + ("pushed" if lp.get("ok") else "push failed: " + str(lp.get("error") or "")), t=int(lp["at"])))
    bad = [x for x in items if x["ok"] is False]
    warn = [x for x in items if x["warn"] and x["ok"] is not False]
    level = "bad" if bad else "warn" if warn else "good"
    return {"items": items, "level": level, "poll_ms": pm, "poll_warn": bool(pm is not None and pm > POLL_WARN_MS),
            "text": (f"{len(bad)} red: " + ", ".join(x["label"] for x in bad)) if bad else
                    (f"{len(warn)} to watch: " + ", ".join(x["label"] for x in warn)) if warn else "all green"}


# ------------------------------------------------------------------------------------------------ week and eval progress
def lit_expected(band: dict | None = None) -> dict | None:
    """$ a month the 2026 H2 backtest made on the eval path (engine/health_band.py H2 usd_eval_per_session x 21)."""
    try:
        if band is None:
            from . import health_band as HB
            band = HB.load()
        B = _d(_d(_d(band).get("bands")).get("H2"))
        ps = _f(B.get("usd_eval_per_session"))
        if ps is None:
            return None
        return {"per_month": round(ps * 21, 0), "per_session": round(ps, 1), "trades_per_week": _r(B.get("trades_per_week"), 2),
                "src": f"2026 H2 backtest ({B.get('from')} to {B.get('to')}), eval sizing, run {_d(band).get('eval_run') or 'lit eval'}"}
    except Exception:
        return None


def atlas_expected(info: dict | None) -> dict | None:
    n = _d(_d(_d(info).get("numbers")).get("H2"))
    if _f(n.get("per_month")) is None:
        return None
    return {"per_month": _f(n["per_month"]), "trades_per_week": _r(n.get("tpw"), 2), "pf": _r(n.get("pf"), 2),
            "src": "2026 H2 backtest, research/second/atlas.json (Builder 25K, costs in)"}


def _odds(ev: dict | None, src: str) -> dict | None:
    ev = _d(ev)
    rows = {}
    for k, lab in (("H2", "2026 H2 (check)"), ("H1", "2026 H1 (picked)")):
        r = _d(ev.get(k))
        if r.get("p10") is None:
            continue
        rows[k] = {"label": lab, "p10": _r(r.get("p10"), 1), "f10": _r(r.get("f10"), 1), "pass_med": _r(r.get("pass_med"), 1),
                   **({"p20": _r(r.get("p20"), 1)} if r.get("p20") is not None else {})}
    return {"rows": rows, "src": src} if rows else None


def _pace(profit, sessions):
    p, s = _f(profit), _i(sessions)
    if p is None or not s:
        return None
    return round(p / s * 21, 0)


def progress(goals: dict | None, lit: dict, atlas: dict, odds_lit: dict | None = None, odds_src: str = "",
             atlas_info: dict | None = None, band: dict | None = None, lit_exp: dict | None = None) -> dict:
    G = _d(goals)
    W = _d(G.get("week"))
    M = _d(G.get("month"))
    out = {}
    for key, acc, wk, lohi in (("lit", lit, _d(W.get("lit")), (2, 4)), ("atlas", atlas, _d(W.get("atlas")), (3, 4))):
        ga = next((g for g in _l(G.get("accounts")) if isinstance(g, dict) and g.get("strategy") == ("LIT" if key == "lit" else "ATLAS")), {})
        sess = _i(acc.get("session"), _i(ga.get("sessions_used")))
        week = {"n": _i(wk.get("n"), 0), "lo": _i(wk.get("lo"), lohi[0]), "hi": _i(wk.get("hi"), lohi[1]), "status": wk.get("status") or "unknown",
                "usd": _f(wk.get("usd"), 0.0), "days": [{k: d.get(k) for k in ("day", "wd", "n", "usd", "future", "today")} for d in _l(wk.get("days"))],
                "sentence": (wk.get("sentence") or "").replace("LIT:", "Zlarior:")}
        if key == "lit":
            exp = lit_exp if lit_exp is not None else lit_expected(band)
            odds = _odds(odds_lit, odds_src or "research/lit/uprisk_eval.json (live two_week switches, MC 1,000 starts a half)")
        else:
            exp = atlas_expected(atlas_info)
            odds = _odds(_d(atlas_info).get("eval25k") or _d(atlas_info).get("eval_25k"), "research/second/atlas.json eval25k (MFFU Builder 25K)")
        actual = {"profit": acc.get("profit"), "sessions": sess, "per_month_pace": _pace(acc.get("profit"), sess)}
        if key == "lit" and M:
            actual.update(month=M.get("month"), month_usd=_f(M.get("usd")), month_trades=_i(M.get("trades")), month_sessions=_i(M.get("sessions")))
        out[key] = {"week": week, "session": sess, "sessions": SESSIONS_GOAL, "sessions_max": 15,
                    "sessions_left": _i(ga.get("sessions_left"), None if sess is None else max(0, SESSIONS_GOAL - sess)),
                    "days_traded": _i(ga.get("days_traded")), "min_days": _i(ga.get("min_days"), 2),
                    "odds": odds, "expected": exp, "actual": actual,
                    "sentence": ga.get("sentence") or ""}
    return out


# ------------------------------------------------------------------------------------------------ trade log
def _row(acct, src, t, key=None, member=None) -> dict | None:
    t = _d(t)
    et_ = _i(t.get("entry_t"))
    if not et_ and not t.get("day"):
        return None
    d = t.get("dir")
    side = t.get("side") or ("LONG" if _i(d, 1) == 1 else "SHORT")
    side = "LONG" if str(side).lower() in ("long", "buy") else "SHORT" if str(side).lower() in ("short", "sell") else side
    ex = t.get("exit_kind") or t.get("exit") or t.get("result")
    usd = _f(t.get("usd"), _f(t.get("pnl")))
    row = {"acct": acct, "src": src, "key": key or acct, "member": member, "day": str(t.get("day") or (trading_day(et_) if et_ else "")),
           "entry_t": et_, "exit_t": _i(t.get("exit_t")), "side": side, "qty": _i(t.get("qty")),
           "entry": _r(t.get("entry"), 2), "stop": _r(t.get("stop"), 2), "target": _r(t.get("target"), 2),
           "exit_px": _r(t.get("exit_px") if t.get("exit_px") is not None else t.get("exit") if isinstance(t.get("exit"), (int, float)) else None, 2),
           "exit": _clean(ex, 24) if ex is not None and not isinstance(ex, (int, float)) else None,
           "r": _r(t.get("r") if t.get("r") is not None else t.get("R"), 3), "usd": None if usd is None else round(usd, 2),
           "open": str(ex or "").upper() == "OPEN"}
    return {k: v for k, v in row.items() if v is not None}


def _pair_routed(rows) -> list:
    """Account B ledger rows (entry buy / sell + exit, by entry_t) -> closed / open trades."""
    ent, ex = {}, {}
    for r in _l(rows):
        r = _d(r)
        if r.get("entry_t") is None:
            continue
        k = int(r["entry_t"])
        if r.get("side") in ("buy", "sell"):
            ent[k] = r
        elif r.get("side") == "exit":
            ex[k] = r
    out = []
    for k, e in ent.items():
        x = ex.get(k)
        out.append({"entry_t": k, "exit_t": _i((x or {}).get("t")), "side": "LONG" if e.get("side") == "buy" else "SHORT",
                    "qty": e.get("qty"), "stop": e.get("stop"), "target": e.get("target"), "entry": e.get("entry"),
                    "exit_kind": (x or {}).get("reason") or ("OPEN" if not x else None), "pnl": (x or {}).get("pnl"),
                    "src": e.get("src") or e.get("strategy")})
    return out


def trade_log(accounts=None, second: dict | None = None, atlas_ledger=None, cloud_ledger=None, n: int = 60) -> list:
    """Both accounts' trades, newest first: Zlarior's PC trades (else the cloud paper ledger), ATLAS's account-B trades
    (filled with the member's own prices when the paper run has the same entry) and the ATLAS members' paper trades."""
    rows, seen = [], set()

    def add(r):
        if not r:
            return
        k = (r["acct"], r.get("entry_t"), r.get("day"), r.get("src") == "live")
        if k in seen:
            return
        seen.add(k)
        rows.append(r)

    A = [a for a in _l(accounts) if isinstance(a, dict) and a.get("id") and not a.get("error")]
    for a in A:
        if a.get("source") == "pc":
            for t in _l(a.get("trades")):
                add(_row("lit", "live", t, "lit"))
    for a in A:
        if a.get("source") == "cloud":
            for t in _l(a.get("trades")):
                add(_row("lit", "paper", t, "lit"))
    if not any(r["acct"] == "lit" and r["src"] == "paper" for r in rows):
        for v in _l(cloud_ledger):
            v = _d(v)
            if v.get("taken") is False or not v.get("day"):
                continue
            add(_row("lit", "paper", {**v, "exit_kind": v.get("exit"), "usd": v.get("usd"), "r": v.get("R")}, "lit"))
    # ATLAS: the paper members' trades by (key, entry_t), to fill the live rows' prices
    S = _d(second)
    strat = S.get("strategies")
    plist = []
    if isinstance(strat, dict):
        plist = [(k, _d(s)) for k, s in strat.items()]
    elif isinstance(strat, list):
        plist = [(_d(s).get("key"), _d(s)) for s in strat]
    paper = {}
    for k, s in plist:
        if k not in ATLAS_KEYS:
            continue
        for t in _l(s.get("trades")):
            if _d(t).get("entry_t") is not None:
                paper[(k, int(t["entry_t"]))] = t
    ab = _d(_d(S.get("route")).get("account_b")) or _d(S.get("account_b"))
    routed = list(_l(atlas_ledger)) or _l(ab.get("routed"))
    for t in _pair_routed(routed):
        k = t.get("src") if t.get("src") in ATLAS_KEYS else next((kk for kk in ATLAS_KEYS if (kk, t["entry_t"]) in paper), None)
        p = _d(paper.get((k, t["entry_t"]))) if k else {}
        merged = {**{kk: p.get(kk) for kk in ("entry", "stop", "target", "exit", "r", "day")}, **{kk: v for kk, v in t.items() if v is not None}}
        if t.get("exit_kind") is None and p.get("exit_kind"):
            merged["exit_kind"] = p["exit_kind"]
        add(_row("atlas", "live", merged, k or "atlas", ATLAS_NAMES.get(k, k)))
    for (k, et_), t in sorted(paper.items(), key=lambda x: x[0][1]):
        if any(r["acct"] == "atlas" and r["src"] == "live" and r.get("entry_t") == et_ for r in rows):
            continue
        add(_row("atlas", "paper", t, k, ATLAS_NAMES.get(k, k)))
    for a in A:                                       # BLITZ's own account (engine/account_c.py): only when it is on
        if a.get("source") == "pc_blitz":
            for t in _l(a.get("trades")):
                add(_row("blitz", "live", t, "blitz", "BLITZ"))
            p = a.get("position") if isinstance(a.get("position"), dict) else None
            if p and p.get("entry_t") is not None:
                add(_row("blitz", "live", {**p, "exit_kind": "OPEN"}, "blitz", "BLITZ"))
    rows.sort(key=lambda r: (r.get("entry_t") or 0, r.get("day") or ""), reverse=True)
    return rows[:n]


# ------------------------------------------------------------------------------------------------ the whole board
def build(inp: dict | None, now=None) -> dict:
    """inp = {"pc": heartbeat-shaped dict, "accounts": engine/accounts.build_accounts rows, "goals": engine/goals JSON,
    "odds_lit": the live-switch eval odds (H1 / H2 / 2021-25 rows), "odds_src", "atlas_info": engine/second.atlas_info(),
    "band": engine/health_band.load() (or "lit_expected"), "heartbeat": {"t", "ok", "enabled"} of the last push,
    "clock": {"drift", "max"} (PC: engine/guards._CLOCK), "atlas_ledger": account B's ledger rows (PC), "cloud_ledger":
    the cloud paper ledger (site), "second": the second-strategies block with trades (default pc["second"]), "brain":
    the brain to draw the map / waiting from (default pc["brain"]), "where": "pc" | "cloud" | "live", "n_trades"}.
    Never raises: a broken part becomes {"error"}."""
    inp = _d(inp)
    now = int(now or time.time())
    pc = _d(inp.get("pc"))
    out = {"v": VERSION, "kind": "le-board", "t": now, "data_t": _i(pc.get("t")), "where": inp.get("where") or "pc",
           "today": trading_day(now), "host": pc.get("host"), "running": pc.get("running")}

    def part(name, fn):
        try:
            out[name] = fn()
        except Exception as e:                       # a broken part never takes the board down
            out[name] = {"error": f"{e.__class__.__name__}: {_clean(e, 140)}"}

    brain = inp.get("brain") if isinstance(inp.get("brain"), dict) else pc.get("brain")
    second = inp.get("second") if isinstance(inp.get("second"), dict) else pc.get("second")
    part("lit", lambda: lit_now(pc, inp.get("accounts"), now, brain=brain))
    part("atlas", lambda: atlas_now(pc, now, second=_d(pc.get("second")) or _d(second)))
    part("blocks", lambda: global_blocks(pc, now, out["where"]))
    if _d(pc.get("account_c")):                       # BLITZ's own account (engine/account_c.py): a third card, only when on
        part("blitz", lambda: blitz_now(pc, now))
        out["accts"] = ["lit", "atlas", "blitz"]
    lit = out["lit"] if isinstance(out.get("lit"), dict) and not out["lit"].get("error") else {}
    atl = out["atlas"] if isinstance(out.get("atlas"), dict) and not out["atlas"].get("error") else {}
    part("map", lambda: today_map(brain, _d(lit.get("micros")).get("qty")))
    part("health", lambda: health_strip(pc, now, inp.get("heartbeat"), inp.get("clock"), out.get("blocks") if isinstance(out.get("blocks"), list) else None))
    part("progress", lambda: progress(inp.get("goals"), lit, atl, inp.get("odds_lit"), inp.get("odds_src") or "", inp.get("atlas_info"),
                                      inp.get("band"), inp.get("lit_expected")))
    part("trades", lambda: trade_log(inp.get("accounts"), second, inp.get("atlas_ledger"), inp.get("cloud_ledger"), int(inp.get("n_trades") or 60)))
    part("real", lambda: real_block(lit, atl, trade_log(inp.get("accounts"), second, inp.get("atlas_ledger"), None, 400), inp.get("band"), now))
    part("week_real", lambda: real_week(out.get("progress"), (out.get("real") or {}).get("trades"), lit, atl))
    # one sentence per account for the top of the page, most urgent first
    blocks = out["blocks"] if isinstance(out.get("blocks"), list) else []
    lines = []
    for b in blocks:
        lines.append({"level": "bad", "text": f"{b['text'].rstrip('.')}. Fix: {b['fix']}", "kind": b["kind"]})
    blz = out["blitz"] if isinstance(out.get("blitz"), dict) and not out["blitz"].get("error") else {}
    for a in (lit, atl, blz):
        for b in a.get("blocks") or []:
            lines.append({"level": "bad" if b["kind"] not in ("passed",) else "good", "text": f"{a['name']}: {b['text'].rstrip('.')}. {b['fix']}", "kind": b["kind"]})
    hl = _d(out.get("health"))
    if hl.get("poll_warn"):
        lines.append({"level": "warn", "text": f"Poll time {hl['poll_ms'] / 1000:.1f} s (above 5 s): decisions run late.", "kind": "poll"})
    out["lines"] = lines
    out["level"] = "bad" if any(x["level"] == "bad" for x in lines) else "warn" if lines else "good"
    return out


def _json_safe(o):
    return json.loads(json.dumps(o, default=str))


# ------------------------------------------------------------------------------------------------ the three callers
def odds_lit_live(lm: dict | None = None) -> tuple[dict | None, str]:
    """The 2-week odds at the live two_week switches (tools/build_web_dashboard._live_eval_odds)."""
    try:
        if lm is None:
            with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
                lm = json.load(fh)
        from tools.build_web_dashboard import _live_eval_odds
        o = _live_eval_odds(_d(lm).get("lit_sizing") or {})
        return (o or {}).get("eval"), (o or {}).get("source") or ""
    except Exception:
        return None, ""


def atlas_info_safe() -> dict | None:
    try:
        from . import second
        return second.atlas_info()
    except Exception:
        return None


def from_heartbeat(hb: dict, now=None, lm: dict | None = None, goals_data: dict | None = None, where: str = "live",
                   n_trades: int = 12, extra: dict | None = None) -> dict:
    """The board of a heartbeat payload (live.json on the PC, the CLI): accounts and goals built the way the cloud builds
    them, the research odds read from the repo."""
    now = int(now or time.time())
    pc = dict(_d(hb))
    pc.setdefault("present", True)
    if lm is None:
        try:
            with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
                lm = json.load(fh)
        except Exception:
            lm = {}
    accounts = []
    try:
        from . import accounts as A
        accounts = A.build_accounts({"pc": {**pc, "age_s": max(0, now - _i(pc.get("t"), now))}, "last_run": now}, lm, now)
    except Exception:
        accounts = []
    goals = None
    try:
        from . import goals as G
        sec = _d(pc.get("second"))
        # the parts of the second block engine/goals reads (ATLAS trades + account B), cut straight from the heartbeat
        # (engine/second.dashboard_block would also load the research tables: ~10x slower, every minute on the PC)
        lite = {"strategies": [{"key": k, "short": _d(s).get("short"), "trades": _l(_d(s).get("trades"))} for k, s in _d(sec.get("strategies")).items()],
                "route": sec.get("route")}
        goals = G.site_block(goals_data or {"accounts": accounts, "second": lite}, now=now)
    except Exception:
        goals = None
    odds, src = odds_lit_live(lm)
    inp = {"pc": pc, "accounts": accounts, "goals": goals, "odds_lit": odds, "odds_src": src, "atlas_info": atlas_info_safe(),
           "heartbeat": {"t": _i(pc.get("t")), "ok": True}, "where": where, "n_trades": n_trades, **_d(extra)}
    return _json_safe(build(inp, now))


def site_block(data: dict, state: dict | None = None, now=None) -> dict:
    """tools/build_web_dashboard.py: the board of data.json (live.pc = the PC heartbeat the cloud read; accounts, goals,
    second, extras.two_week; the cloud brain when the PC one is old).
    Hidden bots (engine/hidden_bots.py, dashboard_view.json, default ["blitz"]): this is the last helper the site build calls
    before it writes data.json and home.json, so it also takes them out of `data` itself (in place: home.json is made of the
    same parts) and stamps data["hidden_bots"]; the board it returns is scrubbed and stamped too."""
    now = int(now or time.time())
    from . import hidden_bots as _hb
    hide = _hb.hidden()
    if isinstance(data, dict):
        _hb.scrub_inplace(data, hide)
        _hb.stamp(data, hide)
    live = _d(_d(data).get("live"))
    pc = dict(_d(live.get("pc")))
    st = _d(state)
    if "crit" not in pc and isinstance(_d(st.get("pc")).get("crit"), list):
        pc["crit"] = st["pc"]["crit"]
    pb, cb = _d(pc.get("brain")), _d(live.get("brain"))
    fresh = pc.get("present") and _i(pc.get("t")) and now - _i(pc.get("t"), 0) < 20 * 60
    brain = pb if (pb and not pb.get("error") and (fresh or not cb)) else (cb or pb)
    tw = _d(_d(_d(data).get("extras")).get("two_week"))
    sec = _d(data.get("second"))
    inp = {"pc": pc, "accounts": data.get("accounts"), "goals": data.get("goals"), "odds_lit": tw.get("eval"),
           "odds_src": "research/lit/uprisk_eval.json (live two_week switches)" if tw.get("eval_cfg") else "research/runs/" + str(tw.get("run") or "lit_2wk_rec"),
           "atlas_info": _d(sec.get("atlas")) or atlas_info_safe(), "brain": brain, "second": {"strategies": sec.get("strategies"), "route": pc.get("second", {}).get("route") if isinstance(pc.get("second"), dict) else None},
           "heartbeat": {"t": _i(pc.get("t")), "ok": True}, "where": "cloud", "cloud_ledger": live.get("ledger"), "n_trades": 40}
    out = build(inp, now)
    out["brain_src"] = "PC bot" if brain is pb and pb else "cloud paper twin"
    return _hb.publish(_json_safe(out), hide)


def main(argv=None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        with open(argv[0], encoding="utf-8") as fh:
            hb = json.load(fh)
    else:
        import subprocess
        r = subprocess.run(["git", "show", "origin/heartbeat:heartbeat.json"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            print("no heartbeat: git fetch origin heartbeat first, or pass a heartbeat.json")
            return 1
        hb = json.loads(r.stdout)
    print(json.dumps(from_heartbeat(hb, now=int(hb.get("t") or time.time())), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
