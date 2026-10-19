"""Read-only API for the PC dashboard's live pages (web_next/js/next/pcpages.js): the PC bot's own account, position, orders
and status, plus the phone app's extras (Eval HQ, Edge, P&L calendar, MFFU rules) in the same data shapes.

Mounted by engine/next_api.py (router.include_router), so server.py needs no change. Every route only READS: the bot
(engine/live.BOT: cfg, state, ledger, log, health, bars), data/live_state.json (through engine/accounts.pc_activity), the LIT
learning journal and the repo's research files. Nothing here starts, arms, routes or stops anything.

  GET /api/next/pc/status         Today's status header: verdict (TRADING YOUR EVAL / ON SIM / PAPER ONLY / DISABLED / FEED
                                  STALE, engine/accounts.verdict on the bot's own health block), account, feed age, last
                                  poll, LIT stage, setups seen today, eval clock
  GET /api/next/pc/account        the eval account card (balance incl. lit_sizing.eval_prior_pnl, trailing floor, room,
                                  progress to +$3,000, session N of 10, daily loss used), the open position (stop now, BE
                                  line, unrealized $, time in trade) with the bot's own 5m / 1m bars, today's order
                                  timeline (refused rows flagged), routed trades, P&L per day, equity curve, stats
  GET /api/next/pc/trade/{entry_t} one routed trade with its chart: the replay chart id when the LIT replay has the same
                                  trade, else bars around it (the bot's feed, then data/NQ_5m.csv / NQ_1m.csv)
  GET /api/next/extras            tools/build_web_dashboard._extras(): every LIT replay trade (compact rows), the level-type
                                  leaderboard, two_week eval odds (run lit_2wk_rec), eventual pass, Monte Carlo, MFFU rules
"""
from __future__ import annotations

import json
import os
import threading
import time

from fastapi import APIRouter
from fastapi.responses import Response

from . import accounts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
LAB = os.path.join(ROOT, "research", "lab")
RUNS = os.path.join(ROOT, "research", "runs")
LIT_DOCS = os.path.join(ROOT, "research", "lit")
PV = 2.0                                   # MNQ: $2 a point (the bot trades NQ signals with MNQ micros)
router = APIRouter()
_lock = threading.Lock()
_cache: dict = {}


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _bot():
    """The PC bot (tests replace this function)."""
    from .live import BOT
    return BOT


def _now() -> int:
    return int(time.time())


def _bot_now(bot) -> int:
    try:
        return int(bot.clock())
    except Exception:
        return _now()


def _lm() -> dict:
    try:
        with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


# ------------------------------------------------------------------------------------------------ bars
def pack(rows, secs: int):
    """[[t,o,h,l,c], ...] -> tradechart.js packed bars {t0, s, p0, dt[], o[], h[], l[], c[]} (price = (p0 + v) / 4)."""
    rows = [r for r in rows or [] if r and r[0] is not None]
    if not rows:
        return None
    t0 = int(rows[0][0])
    p0 = int(min(float(r[3]) for r in rows) * 4)
    q = lambda v: int(round(float(v) * 4)) - p0          # noqa: E731
    return {"t0": t0, "s": int(secs), "p0": p0, "dt": [int((int(r[0]) - t0) // secs) for r in rows],
            "o": [q(r[1]) for r in rows], "h": [q(r[2]) for r in rows], "l": [q(r[3]) for r in rows], "c": [q(r[4]) for r in rows]}


def _rows_from_records(recs):
    out = []
    for b in recs or []:
        try:
            out.append([int(b["time"]), float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _rows_from_frame(df):
    if df is None or not len(df):
        return []
    return [[int(t), float(o), float(h), float(l), float(c)]
            for t, o, h, l, c in zip(df["time"], df["open"], df["high"], df["low"], df["close"])]


def bot_bars(bot, t_from: int, t_to: int | None = None):
    """The bot's own feed between t_from and t_to: 5m (bars_tail, the last ~400 closed 5m bars) and 1m (the LIT 1m store,
    up to 12 days), as [[t,o,h,l,c], ...]."""
    b5 = [r for r in _rows_from_records(getattr(bot, "bars_tail", None)) if r[0] >= t_from and (t_to is None or r[0] <= t_to)]
    st = getattr(bot, "_lit_1m_store", None)
    b1 = []
    if st is not None:
        try:
            b1 = _rows_from_frame(st[(st["time"] >= t_from) & ((st["time"] <= t_to) if t_to is not None else True)])
        except Exception:
            b1 = []
    return b5, b1


def _csv(sym: str, tf: str):
    """data/<sym>_<tf>.csv as a frame, cached per mtime (loaded only when a past trade is not in the bot's feed)."""
    path = os.path.join(DATA, f"{sym}_{tf}.csv")
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return None
    with _lock:
        hit = _cache.get(path)
        if hit and hit[0] == mt:
            return hit[1]
    import pandas as pd
    try:
        df = pd.read_csv(path, usecols=["time", "open", "high", "low", "close"])
    except Exception:
        return None
    with _lock:
        _cache[path] = (mt, df)
    return df


def file_bars(sym: str, t_from: int, t_to: int):
    out = {}
    for tf in ("5m", "1m"):
        df = _csv(sym, tf)
        out[tf] = [] if df is None else _rows_from_frame(df[(df["time"] >= t_from) & (df["time"] <= t_to)])
    return out["5m"], out["1m"]


def _session_from(day: str) -> int:
    """18:00 ET of the calendar day before trading day `day` (the LIT session start)."""
    import datetime as dt
    from zoneinfo import ZoneInfo
    d = dt.date.fromisoformat(day[:10]) - dt.timedelta(days=1)
    return int(dt.datetime(d.year, d.month, d.day, 18, 0, tzinfo=ZoneInfo("America/New_York")).timestamp())


# ------------------------------------------------------------------------------------------------ replay chart index
def _chart_index():
    try:
        from .next_api import _chart_index as ix
        return ix() or {}
    except Exception:
        return {}


def _chart_id(day, entry_t):
    if not day or not entry_t:
        return None
    return _chart_index().get((str(day), int(entry_t)))


# ------------------------------------------------------------------------------------------------ status
def _pc_block(bot, now):
    cfg = getattr(bot, "cfg", None) or {}
    return {"present": True, "t": now, "every_s": 60, "running": bool(getattr(bot, "running", False)),
            "adapter": cfg.get("adapter"), "health": accounts.pc_health(bot, now)}


def status_view(bot, now: int | None = None) -> dict:
    now = int(now or _bot_now(bot))
    pc = _pc_block(bot, now)
    h = pc["health"]
    v = accounts.verdict(pc, now)
    st = getattr(bot, "state", None) or {}
    lit = st.get("lit") or {}
    sigs = [accounts._signal_row(s) for s in (lit.get("signals_today") or []) if isinstance(s, dict)]
    pend = []
    for side, s in (st.get("setups") or {}).items():
        pend.append({"side": side.upper(), "limit": accounts._f(s.get("limit")), "stop": accounts._f(s.get("stop")),
                     "target": accounts._f(s.get("target")), "waiting": s.get("waiting"), "expires_t": accounts._i(s.get("expires_t")),
                     "pools": [accounts.clean_text(x, 40) for x in (s.get("pools") or [])][:4]})
    rules = st.get("lit_rules") or {}
    return {"t": now, "verdict": v, "health": h, "model_state": accounts.clean_text(st.get("model_state"), 200),
            "setups_today": sigs, "pending": pend, "eval_clock": st.get("eval_2wk"),
            "rules": {k: (rules.get(k) or {}).get("text") for k in ("monday", "weekly_stop")},
            "price": accounts._f(st.get("price")), "bar_t": accounts._i(st.get("t")),
            "started_at": accounts._i(getattr(bot, "started_at", None))}


@router.get("/api/next/pc/status")
def pc_status():
    try:
        return _J(status_view(_bot()))
    except Exception as e:                                       # never 500 the Today page
        return _J({"error": f"{e.__class__.__name__}: {accounts.clean_text(e, 120)}"}, 500)


# ------------------------------------------------------------------------------------------------ account
_LOG_KINDS = ("risk", "order", "kill", "error")


def _timeline(bot, orders, today):
    """Today's orders (ledger rows) + the bot's risk / kill / error log rows (an entry not routed, a refused modify)."""
    rows = []
    for o in orders:
        side = o.get("side")
        kind = {"buy": "entry", "sell": "entry", "modify": "stop", "exit": "exit"}.get(side, side)
        refused = o.get("ok") is False
        if side in ("buy", "sell"):
            text = f"{'BUY' if side == 'buy' else 'SELL'} {o.get('qty')} sent" + (f", filled {o['filled']} @ {o['fill_px']:,.2f}" if o.get("fill_px") else "")
            if o.get("stop") is not None:
                text += f" | bracket stop {o['stop']:,.2f}" + (f" target {o['target']:,.2f}" if o.get("target") is not None else "")
            if o.get("bracket") is False:
                text += " | bracket NOT confirmed"
        elif side == "modify":
            text = f"stop moved to {o['stop']:,.2f}" if o.get("stop") is not None else "stop move"
            if o.get("reason"):
                text += f" ({o['reason']})"
        elif side == "exit":
            text = f"exit {o.get('reason') or ''} {o.get('qty') or ''}".strip() + (f" | ${o['pnl']:+,.2f}" if o.get("pnl") is not None else "")
        else:
            text = str(side)
        if o.get("error"):
            text += f" | {o['error']}"
        elif o.get("note"):
            text += f" | {o['note']}"
        rows.append({"t": o.get("t"), "kind": kind, "side": side, "text": text, "refused": refused, "ok": o.get("ok"),
                     "entry_t": o.get("entry_t")})
    for r in list(getattr(bot, "log", None) or []):
        if r.get("type") not in _LOG_KINDS or not r.get("t") or accounts.trading_day(r["t"]) != today:
            continue
        if r.get("type") == "order":                             # the ledger rows above already show every order
            continue
        txt = accounts.clean_text(r.get("text"), 200)
        rows.append({"t": int(r["t"]), "kind": r["type"], "text": txt,
                     "refused": r["type"] in ("kill", "error") or "NOT routed" in (txt or "") or "refused" in (txt or "").lower()})
    rows.sort(key=lambda x: x.get("t") or 0)
    return rows


def _position_view(bot, pos, now):
    if not pos:
        return None
    st = getattr(bot, "state", None) or {}
    p = dict(pos)
    price = accounts._f(st.get("price"))
    d = int(p.get("dir") or (1 if p.get("side") == "LONG" else -1))
    entry, stop0, qty = p.get("entry"), p.get("stop0") or p.get("stop"), p.get("qty")
    p["price"] = price
    if entry is not None and price is not None:
        pts = (float(price) - float(entry)) * d
        p["unrealized_pts"] = round(pts, 2)
        p["unrealized_usd"] = round(pts * PV * float(qty or 0), 2)
        risk = abs(float(entry) - float(stop0)) if stop0 is not None else None
        p["unrealized_r_now"] = round(pts / risk, 3) if risk else None
        p["be_trigger"] = round(float(entry) + d * risk, 2) if risk else None      # breakeven moves the stop at +1R
        if stop0 is not None and qty:
            p["risk_usd"] = round(risk * PV * float(qty), 2)
        if p.get("target") is not None and qty:
            p["target_usd"] = round(abs(float(p["target"]) - float(entry)) * PV * float(qty), 2)
    if p.get("entry_t"):
        p["time_in_s"] = max(0, now - int(p["entry_t"]))
        p["day"] = accounts.trading_day(p["entry_t"])
    return p


@router.get("/api/next/pc/account")
def pc_account(bars: int = 1):
    try:
        return _J(account_view(_bot(), bars=bool(bars)))
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {accounts.clean_text(e, 120)}"}, 500)


def account_view(bot, now: int | None = None, lm: dict | None = None, bars: bool = True, journal_path=None) -> dict:
    now = int(now or _bot_now(bot))
    lm = _lm() if lm is None else lm
    today = accounts.trading_day(now)
    acct = accounts.pc_activity(bot, now=now, journal_path=journal_path, max_trades=400, max_orders=200)
    if acct.get("error"):
        return {"t": now, "error": acct["error"]}
    ls = lm.get("lit_sizing") or {}
    ev = acct.setdefault("eval", {})
    days = ev.setdefault("days", {})
    if "0000-00-00" not in days and ls.get("eval_prior_pnl"):
        days["0000-00-00"] = float(ls["eval_prior_pnl"])      # the eval's P&L before eval_start (owner: -$100)
    if not ev.get("start"):
        ev["start"] = ls.get("eval_start")
    meta = (accounts.accounts_cfg(lm) or accounts.DEFAULT_ACCOUNTS)[0]
    sec = accounts._pc_section(meta, {"present": True, "t": now, "acct": acct, "running": acct.get("running"),
                                      "adapter": (acct.get("account") or {}).get("adapter")}, lm, today, now)
    # every routed trade (not only the eval's) for the trade list; the eval card uses sec["trades"]
    all_trades = list(acct.get("trades") or [])
    for t in all_trades:
        cid = _chart_id(t.get("day"), t.get("entry_t"))
        if cid:
            t["chart"] = cid
    eq, cum = [], float(days.get("0000-00-00", 0.0))
    eq.append(["start", round(cum, 2)])
    for d, v in sorted((k, v) for k, v in days.items() if k != "0000-00-00"):
        cum += float(v)
        eq.append([d, round(cum, 2)])
    pos = _position_view(bot, sec.get("position"), now)
    # the badge from the bot's health block (accounts._acct_kind calls every non-paper NinjaTrader account SIM; pc_health
    # tells a real account from Sim101 / Playback by its name, the same rule as the Today status header)
    hacct = (accounts.pc_health(bot, now) or {}).get("account") or {}
    if hacct.get("label"):
        sec["badge"] = hacct["label"]
    if pos is not None:
        be_rows = [o for o in acct.get("orders") or [] if o.get("side") == "modify" and o.get("ok") and o.get("entry_t") == pos.get("entry_t")]
        if be_rows:
            pos["be_t"] = be_rows[-1].get("t")
    out = {"t": now, "today": today, "account": {k: sec.get(k) for k in ("id", "name", "firm", "plan", "kind", "badge", "broker_account",
                                                                        "adapter", "kill", "running")},
           "eval": sec.get("eval"), "pnl": sec.get("pnl"), "stats": sec.get("stats"), "position": pos,
           "orders": _timeline(bot, acct.get("orders") or [], today), "trades": all_trades[::-1],
           "eval_trades": len(sec.get("trades") or []), "days": sec.get("days"), "equity": eq,
           "sizing": {"mode": ls.get("mode"), "eval_start": ls.get("eval_start"), "eval_prior_pnl": ls.get("eval_prior_pnl"),
                      "two_week_until": ls.get("two_week_until"), "after_mode": ls.get("after_mode")},
           "model_state": accounts.clean_text((getattr(bot, "state", None) or {}).get("model_state"), 200)}
    if acct.get("accounts"):                     # extra accounts (engine/multi_account.py): one compact row each
        rows = []
        for sub in acct["accounts"]:
            try:
                m = {"id": sub.get("id"), "name": sub.get("name"), "firm": sub.get("firm"), "plan": sub.get("plan"),
                     "kind": sub.get("kind") or "eval", "source": "pc"}
                s2 = accounts._pc_section(m, {"present": True, "t": now, "acct": sub, "running": sub.get("running")}, {}, today, now)
                rows.append({k: s2.get(k) for k in ("id", "name", "firm", "plan", "badge", "broker_account", "position", "eval", "pnl", "stats")}
                            | {"mode": sub.get("mode"), "locked": sub.get("locked"), "enabled": sub.get("enabled"),
                               "disabled": (sub.get("account") or {}).get("disabled"), "size": sub.get("size"),
                               "orders": len(sub.get("orders") or [])})
            except Exception as e:
                rows.append({"id": sub.get("id"), "name": sub.get("name"), "error": accounts.clean_text(f"{e.__class__.__name__}: {e}", 120)})
        out["accounts"] = rows
    if bars:
        t_from = _session_from(today)
        if pos and pos.get("entry_t"):
            t_from = min(t_from, int(pos["entry_t"]) - 3 * 3600)
        b5, b1 = bot_bars(bot, t_from)
        out["bars5"] = b5[-300:]
        out["bars1"] = pack(b1[-480:], 60)
    return out


@router.get("/api/next/pc/trade/{entry_t}")
def pc_trade(entry_t: int):
    try:
        d = trade_view(_bot(), int(entry_t))
        return _J(d, 404 if d.get("error") else 200)
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {accounts.clean_text(e, 120)}"}, 500)


def trade_view(bot, entry_t: int, journal_path=None) -> dict:
    now = _bot_now(bot)
    acct = accounts.pc_activity(bot, now=now, journal_path=journal_path, max_trades=400)
    tr = next((t for t in acct.get("trades") or [] if accounts._i(t.get("entry_t")) == entry_t), None)
    if not tr:
        return {"error": f"no routed trade at {entry_t}"}
    cid = _chart_id(tr.get("day"), entry_t)
    out = {"trade": tr, "chart": cid}
    if cid:
        return out
    t_from = max(_session_from(tr.get("day") or accounts.trading_day(entry_t)), entry_t - 6 * 3600)
    t_to = int(tr.get("exit_t") or entry_t) + 3600
    b5, b1 = bot_bars(bot, t_from, t_to)
    src = "bot feed"
    if not b5 or b5[0][0] > entry_t - 1800:
        f5, f1 = file_bars("NQ", t_from, t_to)
        if f5:
            b5, src = f5, "data/NQ_5m.csv"
        if f1 and (not b1 or b1[0][0] > entry_t - 600):
            b1 = f1
    out.update({"bars5": b5, "bars1": pack(b1, 60), "bars_source": src})
    return out


# ------------------------------------------------------------------------------------------------ phone extras
_EXTRA_INPUTS = [os.path.join(LAB, "backtest_live.json"), os.path.join(RUNS, "lit_live.json"), os.path.join(RUNS, "lit_2wk_rec.json"),
                 os.path.join(LIT_DOCS, "eventual.json"), os.path.join(LAB, "montecarlo.json"), os.path.join(LIT_DOCS, "mffu_rules.json"),
                 os.path.join(ROOT, "live_model.json")]


def extras_view() -> dict:
    """tools/build_web_dashboard._extras() (the phone's data.json "extras"), cached until one of its input files changes."""
    key = tuple(os.path.getmtime(p) if os.path.exists(p) else 0 for p in _EXTRA_INPUTS)
    with _lock:
        hit = _cache.get("_extras")
        if hit and hit[0] == key:
            return hit[1]
    import contextlib
    import io
    from tools import build_web_dashboard as bwd
    lm = _lm()
    bt = bwd._load(os.path.join(LAB, "backtest_live.json"), {}) or {}
    with contextlib.redirect_stdout(io.StringIO()):
        x = bwd._extras({}, lm, bt)
    x = x or {"error": "extras unavailable"}
    with _lock:
        _cache["_extras"] = (key, x)
    return x


@router.get("/api/next/extras")
def extras():
    try:
        x = extras_view()
        return _J(x, 500 if x.get("error") else 200)
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {accounts.clean_text(e, 120)}"}, 500)
