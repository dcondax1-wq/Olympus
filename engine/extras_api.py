"""Dashboard extras: glossary + server-side weekly review aggregation.

Mounted by server.py with  app.include_router(router).  Everything here works offline from the
bars already on disk: the weekly review runs a light backtest (default params) and caches it per
data-file mtime, so the Weekly Review page can render even before the browser has a backtest in memory.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import threading
from collections import OrderedDict, defaultdict
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import Response

from . import backtest
from .data import DATA_DIR

router = APIRouter()
_ET = ZoneInfo("America/New_York")
_cache: OrderedDict = OrderedDict()
_lock = threading.Lock()

# ------------------------------------------------------------------ glossary (also baked into palette.js as a fallback)
GLOSSARY = [
    {"term": "IFVG", "name": "Inversion fair value gap",
     "short": "A fair value gap that price closes through, flipping it from support to resistance (or back). The bot's entry trigger after a sweep.",
     "long": "A fair value gap (FVG) is a three-candle imbalance: the wicks of candle 1 and candle 3 do not overlap, leaving a gap in the middle candle. "
             "When price later closes completely through that gap, the gap is said to invert: a bullish FVG that was support becomes resistance, and vice versa. "
             "After a liquidity sweep, the first IFVG that closes back inside the range confirms the reversal and sets the entry zone. Stops go beyond the sweep extreme (or beyond the IFVG)."},
    {"term": "CISD", "name": "Change in state of delivery",
     "short": "A close through the opening price of the last opposing candle series. The fallback trigger when the reversal leg has no FVG.",
     "long": "After a sweep, look at the run of candles that made the raid (the delivery). A close through the open of the first candle of that run is a change in the state of delivery: "
             "the market stopped delivering in the raid direction. The bot only uses CISD as a trigger when the leg printed no fair value gap to invert."},
    {"term": "Sweep", "name": "Liquidity sweep / raid",
     "short": "Price trades through a resting pool of stops (a prior high or low) and fails to continue. Nothing is armed until a pool has been swept.",
     "long": "Obvious highs and lows collect stop orders: buy stops above highs (buy-side liquidity, BSL) and sell stops below lows (sell-side liquidity, SSL). "
             "A sweep is a wick or short excursion through such a level that fills those stops and then reverses. The model treats the sweep extreme as the protected point: "
             "the reversal is only valid while price stays on the right side of it."},
    {"term": "DOL", "name": "Draw on liquidity",
     "short": "The pool price is most likely heading to next; the bot's profit target.",
     "long": "After a sweep on one side, the market usually rotates toward untaken liquidity on the other side: the prior-day high/low, session highs/lows, or a 1H swing. "
             "The bot targets the next quality pool (target mode dol_next) and skips the trade if that pool is closer than the minimum R."},
    {"term": "LRL / HRL", "name": "Low / high resistance liquidity",
     "short": "LRL is a clean, untested level that price slices through easily; HRL has been defended before and takes more effort to break.",
     "long": "A low-resistance level has been formed once and not revisited, so there is little order flow in the way: price tends to run through it quickly to the stops behind it. "
             "A high-resistance level was defended on previous tests, so a raid through it is more likely to be a true sweep and reverse. The confluence score weights pool quality with w_lrl."},
    {"term": "Giveback", "name": "Giveback exit rule",
     "short": "Once a trade reached +0.5R and then closes back below entry, the bot exits instead of waiting for the full stop.",
     "long": "An in-trade exit signal. Reaching +0.5R and then surrendering the whole move is the signature of a failed reversal; leaving at the first close back through entry "
             "turns a -1R loser into roughly a scratch. It was the only exit signal that improved every tested period, so it is a fixed rule rather than a learned one."},
    {"term": "FVG", "name": "Fair value gap",
     "short": "A three-candle imbalance where candle 1 and candle 3 do not overlap; price often returns to fill it.",
     "long": "Impulsive candles leave a gap between the wick of the candle before and the wick of the candle after. That gap is inefficiently traded price. "
             "The model tracks FVGs on 1D/4H/1H/15m to read order flow (respected gap = continuation, inverted gap = flip)."},
    {"term": "Killzone", "name": "Killzone",
     "short": "High-volume windows where sweeps and reversals are most reliable: London 02:00-05:00, NY AM 09:30-11:30, NY PM 13:30-15:30 ET.",
     "long": "Entries are only allowed inside the configured entry windows (default: NY AM and NY PM killzones). Sweeps from 08:00 ET can arm a setup for the killzone."},
    {"term": "MLL", "name": "Trailing maximum loss limit",
     "short": "The prop-firm drawdown line. Trails end-of-day balance highs by $2,000 and locks once the account is $100 above start.",
     "long": "MFFU Builder 50K: the account fails if balance (or intraday low) touches start minus $2,000, trailing upward with new end-of-day highs until it locks at start + $100. "
             "The Command Center shows the cushion above this line."},
    {"term": "Premium / discount", "name": "Premium and discount",
     "short": "Position of price inside the 1H dealing range: above the midpoint is premium (favour shorts), below is discount (favour longs).",
     "long": "The dealing range is the last 1H swing low to swing high. Longs score higher when the sweep lands in discount, shorts when it lands in premium. This edge held on both sides of the split in NQ and ES."},
    {"term": "SMT", "name": "Smart-money technique divergence",
     "short": "NQ sweeps a level while ES (or vice versa) does not: one index made the raid, the other refused.",
     "long": "A correlated-market divergence at a liquidity pool. A sweep confirmed by SMT is scored higher (w_smt)."},
    {"term": "Consistency rule", "name": "50% consistency rule",
     "short": "No single day may be more than 50% of total profit when you request a payout.",
     "long": "MFFU Builder funded accounts require best day <= 50% of the cycle's profit. The Command Center gauge tracks best day / total profit from the backtest; stop-after-win and the daily cap protect it."},
]


# ------------------------------------------------------------------ helpers
def _np(o):
    if hasattr(o, "item"):
        return o.item()
    if hasattr(o, "tolist"):
        return o.tolist()
    return str(o)


def _J(obj, status=200):
    return Response(json.dumps(obj, default=_np, separators=(",", ":")), media_type="application/json", status_code=status)


def _cached(key, fn):
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    val = fn()
    with _lock:
        _cache[key] = val
        while len(_cache) > 12:
            _cache.popitem(last=False)
    return val


def _iso_week(date_str: str) -> str:
    y, w, _ = dt.date.fromisoformat(date_str).isocalendar()
    return f"{y}-W{w:02d}"


def _monday(date_str: str) -> dt.date:
    d = dt.date.fromisoformat(date_str)
    return d - dt.timedelta(days=d.weekday())


def _entry_minute(t: dict) -> int:
    x = dt.datetime.fromtimestamp(t["entry_t"], _ET)
    return x.hour * 60 + x.minute


SLIM = ("entry_t", "exit_t", "day", "dir", "pnl", "pnl_r", "grade", "exit_reason", "trigger", "target_label",
        "regime", "exit_signal", "mfe", "mae", "qty_label", "pools", "score", "model")


def _slim(t: dict) -> dict:
    return {k: t.get(k) for k in SLIM if k in t}


def _r(v, d=2):
    return None if v is None else round(float(v), d)


# ------------------------------------------------------------------ weekly aggregation
def week_review(res: dict) -> dict:
    """Group a backtest result by ISO week. Mirrors web/js/page-review.js so both paths agree."""
    trades = sorted(res.get("trades", []), key=lambda t: t["entry_t"])
    days = res.get("days", [])
    xs = {x["key"]: x for x in res.get("exit_signals", [])}
    weeks: dict = OrderedDict()

    def wk(date_str):
        k = _iso_week(date_str)
        if k not in weeks:
            mon = _monday(date_str)
            weeks[k] = {"key": k, "start": mon.isoformat(), "end": (mon + dt.timedelta(days=4)).isoformat(), "trades": [], "days": []}
        return weeks[k]

    for d in days:
        wk(d["date"])["days"].append({"date": d["date"], "pnl": d.get("pnl", 0.0), "trades": d.get("trades", 0),
                                      "balance": d.get("balance"), "mll": d.get("mll"), "regime": d.get("regime")})
    for t in trades:
        wk(t["day"])["trades"].append(_slim(t))

    out = []
    prev = None
    for k in sorted(weeks):
        w = weeks[k]
        tr = w["trades"]
        n = len(tr)
        wins = [t for t in tr if t["pnl"] > 0]
        losers = [t for t in tr if t["pnl"] <= 0]
        pnl = sum(t["pnl"] for t in tr)
        rs = [t["pnl_r"] for t in tr]
        exits, grades = defaultdict(int), defaultdict(int)
        for t in tr:
            exits[t.get("exit_reason") or "?"] += 1
            grades[t.get("grade") or "?"] += 1
        best = max(tr, key=lambda t: t["pnl"]) if tr else None
        worst = min(tr, key=lambda t: t["pnl"]) if tr else None
        dp = [d["pnl"] for d in w["days"]]
        row = {
            "key": k, "start": w["start"], "end": w["end"], "n": n, "wins": len(wins), "losses": len(losers),
            "win_rate": _r(len(wins) / n * 100, 1) if n else None, "sum_r": _r(sum(rs)), "avg_r": _r(sum(rs) / n, 3) if n else None,
            "pnl": _r(pnl), "best": best, "worst": worst, "exits": dict(exits), "grades": dict(grades),
            "best_day": _r(max(dp)) if dp else None, "worst_day": _r(min(dp)) if dp else None, "active_days": sum(1 for d in w["days"] if d["trades"]),
            "days": w["days"], "trades": tr,
        }
        row["takeaways"] = takeaways(row, prev, xs)
        out.append(row)
        prev = row
    return {"sym": res.get("sym"), "tf": res.get("tf"), "weeks": out, "exit_signals": res.get("exit_signals", []),
            "days": [{"date": d["date"], "pnl": d.get("pnl", 0.0), "trades": d.get("trades", 0), "balance": d.get("balance"), "mll": d.get("mll"), "regime": d.get("regime")} for d in days],
            "trades": [_slim(t) for t in trades], "stats": res.get("stats", {}), "plan": res.get("plan")}


def takeaways(w: dict, prev: dict | None, xs: dict) -> list:
    tr = w["trades"]
    out = []
    if not tr:
        out.append("No trades this week: every candidate was filtered or no pool was swept inside a killzone.")
        return out
    losers = [t for t in tr if t["pnl"] <= 0]
    early_l = [t for t in losers if 570 <= _entry_minute(t) < 615]
    if losers and early_l:
        out.append(f"{len(early_l)} of {len(losers)} loser{'s' if len(losers) != 1 else ''} {'were' if len(early_l) != 1 else 'was a'} first-45-minute "
                   f"entr{'ies' if len(early_l) != 1 else 'y'} (09:30-10:15), the window the discovery scan flagged as weakest.")
    gb = [t for t in tr if "giveback" in str(t.get("exit_reason", "")).lower() or t.get("exit_signal") == "giveback"]
    if gb:
        g = xs.get("giveback", {})
        avg = g.get("avg_gain")
        saved = (avg if avg is not None else 0.6) * len(gb)
        out.append(f"Giveback fired {len(gb)} time{'s' if len(gb) != 1 else ''} and saved an estimated {saved:+.1f}R versus riding those trades to the stop.")
    gi = defaultdict(list)
    for t in tr:
        gi[t.get("grade") or "?"].append(t["pnl_r"])
    top = [g for g in ("A+", "A") if gi.get(g)]
    low = [g for g in ("C", "D") if gi.get(g)]
    if top and low:
        a = sum(x for g in top for x in gi[g]) / sum(len(gi[g]) for g in top)
        c = sum(x for g in low for x in gi[g]) / sum(len(gi[g]) for g in low)
        out.append(f"{'/'.join(top)} grades averaged {a:+.2f}R; {'/'.join(low)} grades averaged {c:+.2f}R. "
                   + ("The grade did its job." if a > c else "The grade did not separate them this week."))
    longs = [t for t in tr if t["dir"] == 1]
    shorts = [t for t in tr if t["dir"] == -1]
    if longs and shorts:
        lp, sp = sum(t["pnl"] for t in longs), sum(t["pnl"] for t in shorts)
        side = "Longs" if lp > sp else "Shorts"
        out.append(f"{side} carried the week: longs {lp:+,.0f} over {len(longs)}, shorts {sp:+,.0f} over {len(shorts)}.")
    trend = [t for t in tr if t.get("regime") == "trending"]
    if trend:
        tp = sum(t["pnl_r"] for t in trend) / len(trend)
        out.append(f"{len(trend)} trade{'s' if len(trend) != 1 else ''} came on trending days at half size, averaging {tp:+.2f}R.")
    if w["pnl"] and w["pnl"] > 0 and w["best_day"]:
        share = w["best_day"] / w["pnl"] * 100
        if share > 50:
            out.append(f"Best day was {share:.0f}% of the week's profit, above the 50% consistency line; a payout week would need more even days.")
    if w["worst_day"] is not None and w["worst_day"] <= -800:
        out.append(f"Worst day {w['worst_day']:+,.0f} came within reach of the $1,000 daily soft stop.")
    if prev and prev["n"]:
        d = (w["avg_r"] or 0) - (prev["avg_r"] or 0)
        out.append(f"Expectancy {'improved' if d >= 0 else 'slipped'} {abs(d):.2f}R per trade versus the prior week ({prev['pnl']:+,.0f}).")
    return out


# ------------------------------------------------------------------ endpoints
@router.get("/api/extras/glossary")
def api_glossary():
    return _J({"terms": GLOSSARY})


@router.get("/api/extras/week")
def api_week(sym: str = "NQ", tf: str = "5m", plan: str = "builder_50k"):
    path = os.path.join(DATA_DIR, f"{sym}_{tf}.csv")
    if not os.path.exists(path):
        return _J({"error": f"no data for {sym} {tf}"}, 400)
    mt = os.path.getmtime(path)
    key = hashlib.md5(json.dumps(["week", sym, tf, plan, mt]).encode()).hexdigest()
    try:
        return _J(_cached(key, lambda: week_review(backtest.run(sym, tf, {}, plan, light=True))))
    except Exception as e:
        return _J({"error": str(e)}, 400)
