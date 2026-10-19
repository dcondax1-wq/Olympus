"""LIT (engine/lit.py) inside the live loop: the PC paper bot (engine/live.py) and the cloud monitor (tools/cloud_monitor.py)
call run() every poll when live_model.json says {"model": "lit", "lit": {...}}.

It rebuilds the LIT market (levels, swings, VIX band) on the recent bars and runs the same executor as the backtest
(engine/lit.py run_live = run_x with an open position / working limit at the end of the data), so live decisions and the
backtest cannot drift apart. Returns the shape the live loop already consumes (as engine.lab_adapter.run):
  state   model_state text, position (open trade, stop after breakeven), setups (working limits), active_pools (untaken
          levels + the VIX band for the chart), session boxes, price, day_trades, day_pnl
  trades  finished trades: entry_t, exit_t, dir, entry, exit_price, stop, target, qty, pnl, pnl_r, exit_reason, trigger 'LIT'
  events  signal (limit placed), entry, exit; texts never change once written (the alert de-dup key)
  days    daily P&L of the window

Window: the LIT levels include the previous month's high/low, so run() keeps the bars from the first trading day of the
previous month (minus a week) on; callers hand it the merged history (not the engine's 20-day window). On that window
the market is identical to the full-history one for the current day (tests/test_lit_live.py checks it on every 2026 day).

1m bars: the final LIT enters on a 1m CISD after the limit is tapped. one_min = a 1m DataFrame from the feed (Yahoo NQ=F
1m / stored data/NQ_1m.csv) or a cleaned engine.data.Bars (the research file). A day whose 1m bars do not cover it falls
back to 5m execution exactly as the backtest does. Paper only: this module never routes anything.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from engine import lit
from engine.data import Bars, from_frame

ET = ZoneInfo("America/New_York")
CUSHION_DAYS = 7
LIVE_TOL_1M = 1.0          # a feed's 1m bars may rebuild its 5m bar within 1 pt (rounding, late prints)
LBL = {"asia20": "Asia", "asia18": "Asia 18-00", "asia19": "Tokyo", "lon25": "London", "lon34": "London 03-04",
       "lon23": "Frankfurt", "ny89": "NY 08-09", "ny830": "NY 08:30", "ny930": "NY 09:30-10", "ny9301030": "NY 1st hour",
       "pre": "Premarket", "ny8_830": "NY 08-08:30"}
STRENGTH = {"pd": 3, "pw": 3, "pm": 3, "gap": 2, "asia": 2, "london": 2, "ny": 2, "pre": 2, "x_ny": 2, "buildup": 1}


def eval_odds(root: str | None = None) -> dict:
    """MFFU 50K eval odds of the live LIT from its stored 2026 run (research/runs/lit_live.json = live_model.json "lit" with
    the loss pack; lit_final.json before it existed), in eval_timing's fields. LIT has no cold-streak filter, so the
    verdict is always go: any session is as good a start as another in the backtest."""
    import json
    import os
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = {"model": "lit", "verdict": "go", "state": "lit", "since_flip": None, "funded_wk": None,
           "pass_2w": None, "fail_2w": None, "pass_1m": None, "fail_1m": None, "median_pass": None, "run": None}
    for rid in ("lit_live", "lit_final"):
        p = os.path.join(root, "research", "runs", rid + ".json")
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                sp = json.load(fh)["spans"]["2026"]
        except Exception:
            continue
        out.update(pass_2w=round(sp["p10"] / 100, 3), fail_2w=round(sp["f10"] / 100, 3), pass_1m=round(sp["p20"] / 100, 3),
                   fail_1m=round(sp["f20"] / 100, 3), median_pass=sp.get("pass_med"), pass_rate=sp.get("pass_rate"), run=rid,
                   reason=f"LIT has no cold-streak filter: any session is a fine start. Odds from the LIT 2026 backtest (run {rid}: "
                          f"tuned on Jan-Jun, Jul-Oct was weaker)")
        break
    else:
        out["reason"] = "LIT has no cold-streak filter; no stored LIT run for the odds"
    return out


def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def _hm(t):
    return _et(t).strftime("%H:%M")


def trading_date(t) -> dt.date:
    return (_et(t) + dt.timedelta(hours=6)).date()


def window_start(last_t: int) -> int:
    """Unix time from which the bars are kept: 18:00 ET opening the first trading day of the previous month, minus a week."""
    d = trading_date(last_t)
    prev_first = (d.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    start = dt.datetime.combine(prev_first - dt.timedelta(days=CUSHION_DAYS + 1), dt.time(18, 0), ET)
    return int(start.timestamp())


def _clean5(df: pd.DataFrame) -> pd.DataFrame:
    df = df[["time", "open", "high", "low", "close", "volume"]].sort_values("time").drop_duplicates("time", keep="last")
    return df[~((df["high"] == df["low"]) & (df["volume"] <= 0))]          # same hygiene as engine.data.load()


def feed_1m(df1: pd.DataFrame, t_from: int) -> Bars | None:
    """A feed's 1m bars as Bars: on the minute grid, de-duplicated, and a minute with no print inside a 5m window filled
    with a flat bar at the previous close (no trade = no move), so a quiet minute does not throw the window out."""
    if df1 is None or not len(df1):
        return None
    d = df1[["time", "open", "high", "low", "close", "volume"]].copy()
    d = d[(d["time"] >= t_from) & (d["time"] % 60 == 0)].sort_values("time").drop_duplicates("time", keep="last")
    if not len(d):
        return None
    d["b"] = d["time"] // 300 * 300
    rows = []
    for b, g in d.groupby("b", sort=True):
        if len(g) < 5:
            last_min = int(g["time"].max())
            have = set(int(x) for x in g["time"])
            prev = None
            for m in range(b, min(b + 300, last_min + 60), 60):
                if m in have:
                    prev = g[g["time"] == m].iloc[0]
                elif prev is not None:
                    c = float(prev["close"])
                    rows.append({"time": m, "open": c, "high": c, "low": c, "close": c, "volume": 0.0, "b": b})
    if rows:
        d = pd.concat([d, pd.DataFrame(rows)]).sort_values("time")
    return from_frame("NQ", "1m", d.drop(columns="b"))


def _slice_bars(b: Bars, t_from: int) -> Bars:
    a = int(np.searchsorted(b.t, t_from))
    return b.slice(a, len(b))


def run(df5: pd.DataFrame, params: dict | None = None, one_min=None, now: int | None = None, sym: str = "NQ",
        week_hist: list | None = None, learn: bool = False, es_df: pd.DataFrame | None = None,
        learn_after: int | None = None, forming: tuple | None = None, early: bool = False) -> dict:
    """week_hist: the caller's ledger of this week's finished trades ({"day", "exit", "exit_t"}) for the weekly stop
    ("wk_stop"): the cloud monitor's LIT ledger, the PC bot's routed exits; a day it does not cover counts the model's own
    trade (engine/lit.py week_stops).
    learn=True (the learning loop, engine/lit_learn.py): every trade that finished after learn_after (default: the last 3
    days) and the open position carry "learn" = the 50 causal features at entry + buckets + grade, and finished trades the
    hindsight facts "post" (journal + cause codes). es_df = ES 5m bars for the ES features (None: unknown). Off by default:
    the trades and every decision are identical either way.
    forming = (open time, open price) of the 1m bar forming now, when the feed shows it (Yahoo's last row, NinjaTrader's
    LE_BarFeed open file): state["enter_now"] (an entry decided on the 1m CISD close that just happened) is then sized from
    the backtest's own fill price (that bar's open + 1 tick) instead of an estimate from the CISD close.
    early=True (the PC bot, engine/live.py; needs `now`): a setup whose trigger is the last closed 5m bar is seen at once,
    while its entry bar is still forming (the backtest fills inside that bar; without this the loop only sees the setup
    when that bar closes, up to 5 min after the 1m CISD). The forming 5m bar is added to the market as a flat bar at its
    open (from the 1m feed, on the 5m basis): it is never a trigger, never an executor bar, and no level, swing or box
    a decision uses can come from it (tests/test_lit_live.py checks the trades stay the backtest's)."""
    P = {**lit.DEFAULTS, **(params or {})}
    df5 = _clean5(df5)
    if not len(df5):
        raise ValueError("LIT: no 5m bars")
    last_t = int(df5["time"].max())
    w = df5[df5["time"] >= window_start(last_t)]
    src = tol = None
    if P["tf"] == "1m" and one_min is not None:
        if isinstance(one_min, Bars):
            src, tol = _slice_bars(one_min, int(w["time"].min())), None          # research-clean bars: the backtest rule exactly
        else:
            src, tol = feed_1m(one_min, int(w["time"].min())), LIVE_TOL_1M
    n_closed = len(w)
    if early and now is not None:
        pv = _forming_5m(w, src, tol, forming, int(now))
        if pv is not None:
            w = pd.concat([w, pd.DataFrame([pv])], ignore_index=True)
    b5 = from_frame(sym, "5m", w)
    M = lit.Market(bars=b5, extra_boxes=P.get("extra_boxes") or [])
    M.n_closed = n_closed if len(b5) == n_closed + 1 else M.n
    C = lit.candidates(M, ref=P["ref"])
    B5 = lit.bars_5m(M) if M.n_closed == M.n else lit.closed_bars(lit.bars_5m(M), M.n_closed)
    B1 = None
    if src is not None and len(src):
        B1 = lit.bars_1m(M, src=src, tol=tol, tail=True)
    if P["tf"] == "1m" and B1 is not None and B1.full and not isinstance(one_min, Bars):
        # A feed keeps only recent 1m bars (Yahoo: 7 days). Days before the first one it fully covers are history: they are
        # not re-simulated on 5m (that would invent a different trade for a day that was traded on 1m), so they drop out.
        k1 = min(B1.full)
        C = [z for z in C if z["k"] >= k1]
    _set_next_open(B1, B5, forming, src if B1 is not None else None)
    R = lit.run_live(M, C, P, B1=B1, B5=B5, week_hist=week_hist)
    now = int(now) if now is not None else last_t + 300
    if learn:
        _attach_learn(M, C, R, P, es_df, learn_after if learn_after is not None else now - 3 * 86400)
    out = _shape(M, R, P, now, B1)
    out["state"]["lit"]["forming_5m"] = M.n_closed < M.n
    if R.get("learn_error"):
        out["learn_error"] = R["learn_error"]
    return out


def _forming_5m(w: pd.DataFrame, src, tol, forming, now: int):
    """The 5m bar forming at `now` as a flat bar at its open (5m basis), or None: its open from the 1m feed's bar at that
    time (closed) or the forming 1m bar's open (`forming`, when the 5m bar has just started); the 1m basis is checked on
    the last closed 5m bar (the rule of lit.bars_1m: all four prices off by one constant = shifted, within tol = same)."""
    t_last = int(w["time"].iloc[-1])
    t5 = t_last + 300
    if not (t5 <= now < t5 + 300) or src is None or not len(src):
        return None
    e = _et(t5)
    if 1020 <= e.hour * 60 + e.minute < 1080 or trading_date(t5) != trading_date(t_last):
        return None
    o1 = None
    j = int(np.searchsorted(src.t, t5))
    if j < len(src.t) and int(src.t[j]) == t5:
        o1 = float(src.o[j])
    elif forming and int(forming[0]) == t5:
        o1 = float(forming[1])
    if o1 is None:
        return None
    a = int(np.searchsorted(src.t, t_last))
    if a + 5 > len(src.t) or int(src.t[a]) != t_last or int(src.t[a + 4]) != t_last + 240:
        return None
    last = w.iloc[-1]
    dd = np.array([src.o[a] - last["open"], src.c[a + 4] - last["close"], src.h[a:a + 5].max() - last["high"],
                   src.l[a:a + 5].min() - last["low"]], dtype=float)
    if np.abs(dd - dd[0]).max() < 0.01:
        sh = float(dd[0]) if abs(dd[0]) >= 0.01 else 0.0
    elif tol is not None and np.abs(dd).max() <= tol:
        sh = 0.0
    else:
        return None
    px = round(o1 - sh, 2)
    return {"time": t5, "open": px, "high": px, "low": px, "close": px, "volume": 0.0}


def _set_next_open(B1, B5, forming, src):
    """The forming bar's open on the executor bars (lit.XBars.next_open), on the 5m basis of the 1m bars (bars_1m shifts a
    window whose 1m bars sit on another contract's basis)."""
    if not forming:
        return
    try:
        ft, fo = int(forming[0]), float(forming[1])
    except (TypeError, ValueError, IndexError):
        return
    sh = 0.0
    if B1 is not None and B1.n:
        if src is not None and len(src):
            j = int(np.searchsorted(src.t, B1.t[-1]))
            if j < len(src.t) and int(src.t[j]) == int(B1.t[-1]):
                sh = float(src.c[j]) - float(B1.c[-1])
        if ft == int(B1.t[-1]) + 60:
            B1.next_open = (ft, fo - sh)
    if B5 is not None and B5.n and ft % 300 == 0 and ft == int(B5.t[-1]) + 300:
        B5.next_open = (ft, fo - sh)


def _attach_learn(M, C, R, P, es_df, after):
    """The learning loop's inputs on the executor's trades (engine/lit_learn.py live_features / post_facts)."""
    try:
        from engine import lit_learn
        F = lit_learn.live_features(M, C, R["trades"], P, es_df=es_df, only_after=after)
        for t in R["trades"]:
            x = F.get((t["day"], int(t.get("i", -1)), int(t["dir"])))
            if x:
                t["learn"] = x
                if t["exit"] != "OPEN":
                    t["post"] = lit_learn.post_facts(M, {**t, "target_px": t.get("target_px")})
        if F.get("_error"):
            R["learn_error"] = F["_error"]
    except Exception as e:                       # never stops the live loop
        R["learn_error"] = f"{e.__class__.__name__}: {e}"


# ------------------------------------------------------------------------------------------------ output shape
def _side(d):
    return "LONG" if d == 1 else "SHORT"


def _sweep_names(names):
    out = []
    for n in names or []:
        base = n.rsplit("_", 1)[0] if n.endswith(("_h", "_l")) else n
        if base in LBL:
            out.append(f"{LBL[base]} {'high' if n.endswith('_h') else 'low'}")
        elif n in ("pdh", "pdl", "pwh", "pwl", "pmh", "pml"):
            out.append(n.upper())
        elif n in ("nwog", "ndog"):
            out.append(n.upper())
        elif n.startswith("bu_"):
            out.append("equal lows" if n.endswith("l") else "equal highs")
        else:
            out.append(n)
    return list(dict.fromkeys(out))


def _trade(t):
    reason = "TIME" if t["exit"] == "EOD" else t["exit"]        # the live loop flattens on TIME at 15:55
    return {"entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]), "entry": float(t["entry_px"]),
            "exit_price": float(t["exit_px"]), "stop": float(t["stop_px"]), "target": float(t["target_px"]), "qty": int(t["qty"]),
            "pnl": float(t["pnl"]), "pnl_r": float(t["r"]), "exit_reason": reason, "trigger": "LIT", "grade": "", "day": t["day"],
            "risk_pts": float(t["risk_pts"]), "risk_usd": float(t["risk_usd"]), "target_label": t.get("target_label"),
            "swept": _sweep_names(t.get("swept")), "sweep_ext": t.get("sweep_ext"), "tf": f"{t.get('tf', 5)}m",
            "mfe": t.get("mfe"), "bars_held": t.get("bars_held"), "entry_kind": "limit" if t.get("limit_fill") else "1m CISD",
            "size_mult": t.get("size_mult", 1.0), "size_why": t.get("size_why") or [],
            **({"adds": t["adds"], "pts": t.get("pts"), "qty_total": t.get("qty_total")} if t.get("adds") else {}),
            **({"exit_now": True} if t.get("exit_now") else {}),
            **({"mae": t.get("mae"), "learn": t["learn"], "post": t.get("post")} if t.get("learn") else {})}


def _levels(M, k, upto):
    """Untaken LIT levels of day k (known by bar `upto`, not traded through since), for the chart / README."""
    x = M.ctx[k]
    out = []
    for side, px, ki, nm, cls in M.levels(k):
        if ki > upto:
            continue
        a = max(ki + 1, x["s"] - 600)
        seg_h, seg_l = M.h[a:upto + 1], M.l[a:upto + 1]
        if side == "high" and len(seg_h) and seg_h.max() >= px:
            continue
        if side == "low" and len(seg_l) and seg_l.min() <= px:
            continue
        lab = _sweep_names([nm])[0] if nm not in ("bu_h", "bu_l") else ("EQH" if side == "high" else "EQL")
        out.append({"label": lab, "price": round(float(px), 2), "side": "H" if side == "high" else "L",
                    "strength": STRENGTH.get(cls, 1), "kind": cls})
    vm = x.get("vix_move")
    if vm:
        for d in (1, -1):
            out.append({"label": "VIX band (target)", "price": round(x["open18"] + d * vm, 2), "side": "H" if d == 1 else "L",
                        "strength": 2, "kind": "vix"})
    seen, uniq = set(), []
    for p in sorted(out, key=lambda p: -p["strength"]):
        key = (p["label"], p["price"])
        if key not in seen:
            seen.add(key); uniq.append(p)
    return uniq


def _nth_weekday(y, m, wd, n):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(wd - d.weekday()) % 7)
    if n > 0:
        return d + dt.timedelta(weeks=n - 1)
    last = dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)      # n = -1: last weekday wd of the month
    return last - dt.timedelta(days=(last.weekday() - wd) % 7)


def _easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    return dt.date(y, month, (h + l_ - 7 * m + 114) % 31 + 1)


def early_close(day: str) -> int | None:
    """ET minute at which CME equity futures halt early on this trading date (US holidays 13:00 = 12:00 CT; the day after
    Thanksgiving and Christmas Eve 13:15 = 12:15 CT, CME product calendar per the LIT report ch.28; Good Friday 09:15 when
    it trades at all), else None. Closes a paper position the backtest closes at the day's last bar, and moves the
    NinjaTrader adapter's flat time / entry cutoff before the halt (engine/ninjatrader.py)."""
    d = dt.date.fromisoformat(day)
    y = d.year
    jul4 = dt.date(y, 7, 4)
    jul4 = jul4 + dt.timedelta(days=1) if jul4.weekday() == 6 else jul4 - dt.timedelta(days=1) if jul4.weekday() == 5 else jul4
    jun19 = dt.date(y, 6, 19)
    jun19 = jun19 + dt.timedelta(days=1) if jun19.weekday() == 6 else jun19 - dt.timedelta(days=1) if jun19.weekday() == 5 else jun19
    hol = {_nth_weekday(y, 1, 0, 3), _nth_weekday(y, 2, 0, 3), _nth_weekday(y, 5, 0, -1), jun19, jul4, _nth_weekday(y, 9, 0, 1),
           _nth_weekday(y, 11, 3, 4), _nth_weekday(y, 11, 3, 4) + dt.timedelta(days=1), dt.date(y, 12, 24)}
    if d == _nth_weekday(y, 11, 3, 4) + dt.timedelta(days=1) or d == dt.date(y, 12, 24):
        return 13 * 60 + 15
    if d in hol:
        return 13 * 60
    if d == _easter(y) - dt.timedelta(days=2):
        return 9 * 60 + 15
    return None


def _session_over(day: str, now: int, last_close: int | None = None) -> bool:
    """The trading day `day` has ended by `now`: 17:00 ET of that date, or an early-close holiday's halt once the feed has
    stopped at it (last bar closed by the halt, now 5+ minutes past it)."""
    date = dt.date.fromisoformat(day)
    if now >= int(dt.datetime.combine(date, dt.time(17, 0), ET).timestamp()):
        return True
    ec = early_close(day)
    if ec is None or last_close is None:
        return False
    halt = int(dt.datetime.combine(date, dt.time(ec // 60, ec % 60), ET).timestamp())
    return last_close <= halt and now >= halt + 300


def _close_at_session_end(t):
    """A position still open when its session is over (CME early close on a holiday, before the 15:55 flat): closed at
    the last bar's close minus 1 tick, as the backtest does when the next session's bars arrive."""
    d, q = int(t["dir"]), int(t["qty"])
    exit_px = float(t["exit_px"]) - d * lit.SLIP
    pnl = (d * (exit_px - float(t["entry_px"])) * lit.PV - lit.COMM) * q
    pnl += sum((d * (exit_px - float(a["px"])) * lit.PV - lit.COMM) * int(a["qty"]) for a in (t.get("adds") or []))   # scale_in
    x = dict(t)
    if t.get("adds"):                    # scale_in: the points of the entry and of each add at the session-end price
        x["pts"] = round(d * (exit_px - float(t["entry_px"])), 4)
        x["adds"] = [dict(a, pts=round(d * (exit_px - float(a["px"])), 4)) for a in t["adds"]]
    x.update(exit="EOD", exit_px=round(exit_px, 2), pnl=round(pnl, 2), r=round(pnl / (float(t["risk_pts"]) * lit.PV * q), 3),
             exit_t=int(t["last_t"]) + 60 * int(t.get("tf", 5)))
    return x


def _closed(now):
    e = _et(now)
    m = e.hour * 60 + e.minute
    wd = e.weekday()
    return wd == 5 or (wd == 6 and m < 1080) or (wd == 4 and m >= 1020) or (1020 <= m < 1080)


def _enter_now(t):
    """lit.run_live "enter_now" in the position's shape: the entry decided on the 1m CISD close, for the live loop to route
    at market at once (engine/live.py); entry = the backtest's fill (the forming bar's open + 1 tick), or est = True when
    the feed did not show that open yet (CISD close + 1 tick: the micros may then differ from the model's by a few)."""
    return {"entry_t": int(t["entry_t"]), "cisd_t": int(t["cisd_t"]), "dir": int(t["dir"]), "qty": int(t["qty"]),
            "stop": float(t["stop_px"]), "stop0": float(t["stop_px"]), "target": float(t["target_px"]), "entry": float(t["entry_px"]),
            "est": bool(t.get("est")), "setup": "LIT", "trigger": "LIT", "risk_pts": float(t["risk_pts"]), "be": False,
            "target_label": t.get("target_label"), "size_mult": t.get("size_mult", 1.0), "size_why": t.get("size_why") or [],
            "tf": f"{t.get('tf', 1)}m"}


def _shape(M, R, P, now, B1):
    trades, events, position = [], [], None
    nc = getattr(M, "n_closed", M.n)          # early mode: M ends with the forming 5m bar, which is not shown as a bar
    en = (R.get("enter_now") or [None])[0]
    enter_now = _enter_now(en) if en and not _session_over(en["day"], now, int(M.t[nc - 1]) + 300) else None
    for s in R["signals"]:
        events.append({"t": s["t"], "type": "signal", "dir": s["dir"],
                       "text": f"LIT {_side(s['dir'])} setup: swept {', '.join(_sweep_names(s['swept']))} (extreme {s['sweep_ext']:,.2f}); "
                               f"limit {s['limit_px']:,.2f} stop {s['stop_px']:,.2f} ({s['risk_pts']:.2f} pts) target "
                               f"{s['target_px']:,.2f} ({s['rr']:.2f}R, {s['target_label']})"})
    for t in R["trades"]:
        side = _side(t["dir"])
        kind = "limit" if t.get("limit_fill") else "1m CISD"
        events.append({"t": int(t["entry_t"]), "type": "entry", "dir": int(t["dir"]),
                       "text": f"{side} LIT @ {t['entry_px']:,.2f} stop {t['stop_px']:,.2f} target {t['target_px']:,.2f} qty {t['qty']} "
                               f"({kind} entry, {t.get('tf', 5)}m bars)"
                               + (f" - {'; '.join(t['size_why'])}" if t.get("size_why") else "")})
        if t["exit"] == "OPEN" and _session_over(t["day"], now, int(M.t[nc - 1]) + 300):
            t = _close_at_session_end(t)       # early-close holiday: the backtest exits at the day's last bar
        if t["exit"] == "OPEN":
            position = {"entry_t": int(t["entry_t"]), "dir": int(t["dir"]), "qty": int(t["qty"]), "stop": float(t["stop_now"]),
                        "stop0": float(t["stop_px"]), "target": float(t["target_px"]), "entry": float(t["entry_px"]), "setup": "LIT",
                        "trigger": "LIT", "risk_pts": float(t["risk_pts"]), "be": bool(t.get("be_done")),
                        "unrealized": float(t["pnl"]), "unrealized_r": float(t["r"]), "target_label": t.get("target_label"),
                        "size_mult": t.get("size_mult", 1.0), "size_why": t.get("size_why") or [],
                        **({"adds": t["adds"]} if t.get("adds") else {}),
                        **({"add_now": t["add_now"]} if t.get("add_now") else {}),
                        **({"learn": t["learn"]} if t.get("learn") else {})}
            continue
        tr = _trade(t)
        trades.append(tr)
        events.append({"t": tr["exit_t"], "type": "exit",
                       "text": f"EXIT {tr['exit_reason']} {side} LIT | {tr['pnl_r']:+.2f}R | ${tr['pnl']:+,.0f}"})
    events.sort(key=lambda e: (e["t"], e["type"]))
    days = {}
    for t in trades:
        d = days.setdefault(t["day"], {"date": t["day"], "pnl": 0.0, "trades": 0})
        d["pnl"] += t["pnl"]; d["trades"] += 1
    k = len(M.days) - 1
    today = M.days[k][0]
    last = nc - 1
    price = float(M.c[last])
    x = M.ctx[k]
    setups = {}
    for p in R["pending"]:
        setups["long" if p["dir"] == 1 else "short"] = {
            "arm_t": int(p["sig_t"]), "ext": None, "limit": p["limit_px"], "stop": p["stop_px"], "target": p.get("target_px"),
            "expires_t": int(p["expires_t"]), "tapped_t": p.get("tapped_t"), "pools": _sweep_names(p.get("swept")),
            "waiting": "1m CISD" if p.get("tapped_t") else "limit fill"}
    sig_by_t = {s["t"]: s for s in R["signals"]}
    for s in setups.values():
        sg = sig_by_t.get(s["arm_t"])
        s["ext"] = sg["sweep_ext"] if sg else s["stop"]
    sess = {}
    for nm, lab in (("asia20", "Asia 20-00"), ("lon34", "London 03-04"), ("ny89", "NY 08-09"), ("pre", "Premarket")):
        if nm in x and x[nm][2] <= last:
            sess[lab] = [round(x[nm][0], 2), round(x[nm][1], 2)]
    if "pdh" in x:
        sess["Prev day"] = [round(x["pdh"], 2), round(x["pdl"], 2)]
    day_tr = [t for t in trades if t["day"] == today]
    e = _et(now)
    mod = e.hour * 60 + e.minute
    win_a = min(a for a, _ in P["window"]); win_z = max(z for _, z in P["window"])
    if _closed(now):
        ms = "LIT: market closed (next session 18:00 ET; entries 02:00-15:30 ET)"
    elif position:
        ms = (f"LIT: IN TRADE {_side(position['dir'])} @ {position['entry']:,.2f} | stop {position['stop']:,.2f}"
              f"{' (breakeven)' if position['be'] else ''} | target {position['target']:,.2f}")
    elif enter_now:
        ms = (f"LIT: ENTERING {_side(enter_now['dir'])} at market now (1m CISD closed {_hm(enter_now['entry_t'])} ET) | "
              f"{enter_now['qty']} micros | stop {enter_now['stop']:,.2f} | target {enter_now['target']:,.2f}")
    elif len(day_tr) >= P["max_per_day"] and str(trading_date(now)) == today:
        t = day_tr[-1]
        ms = f"LIT: done for today ({t['exit_reason']} {t['pnl_r']:+.2f}R, ${t['pnl']:+,.0f}); 1 trade a day"
    elif setups:
        s = next(iter(setups.values())); side = next(iter(setups))
        if s.get("tapped_t"):
            ms = f"LIT: {side.upper()} limit {s['limit']:,.2f} tapped at {_hm(s['tapped_t'])}, waiting for a 1m CISD (stop {s['stop']:,.2f})"
        else:
            ms = (f"LIT: {side.upper()} limit armed at {s['limit']:,.2f} until {_hm(s['expires_t'])} ET "
                  f"(stop {s['stop']:,.2f}, target {s['target']:,.2f})")
    elif win_z <= mod < 1080:
        ms = f"LIT: entry window closed ({win_a // 60:02d}:{win_a % 60:02d}-{win_z // 60:02d}:{win_z % 60:02d} ET); flat by 15:55"
    elif mod >= 1080 or mod < win_a:
        ms = "LIT: waiting for London sweep (entries from 02:00 ET)"
    else:
        ms = "LIT: watching for a sweep + inducement + CISD (entries until 15:30 ET)"
    mon = lit.monday_state(M, k, last) if P.get("monday") else None
    if mon in ("high", "low") and not position and not (len(day_tr) >= P["max_per_day"] and str(trading_date(now)) == today):
        ms += f" | Monday rule: Friday's {mon} taken, {'shorts' if mon == 'high' else 'longs'} only"
    rules = {"monday": {"on": bool(P.get("monday")), "today": mon,
                        "text": (None if mon is None else
                                 "Monday: Friday's high taken - shorts only" if mon == "high" else
                                 "Monday: Friday's low taken - longs only" if mon == "low" else
                                 "Monday: Friday's high and low both taken - no side rule" if mon == "both" else
                                 "Monday: Friday's high/low not taken yet - both sides")},
             "weekly_stop": None}
    if R.get("week"):
        w = R["week"]
        rules["weekly_stop"] = {**w, "on": True,
                                "text": (f"weekly stop ON: {w['stops']} stop-outs this week, {w['mult']:g}x size for the rest of the week"
                                         if w["mult"] < 1 else f"{w['stops']} of {w['after']} stop-outs this week: full size")}
    state = {"model": "lit", "model_state": ms, "lit_rules": rules, "position": position, "enter_now": enter_now, "setups": setups,
             "active_pools": _levels(M, k, last),
             "session": sess, "price": price, "t": int(M.t[last]), "day_trades": len(day_tr),
             "day_pnl": round(sum(t["pnl"] for t in day_tr), 2),
             "lit": {"today": today, "open18": x.get("open18"), "vix": round(x["vix"], 2) if x.get("vix") else None, "vix_move": round(x["vix_move"], 2) if x.get("vix_move") else None,
                     "window": P["window"], "one_min_day": bool(B1 is not None and k in (B1.full or set())),
                     "signals_today": [s for s in R["signals"] if s["day"] == today], "bars": int(M.n)}}
    return {"state": state, "trades": trades, "events": events, "signals": R["signals"],
            "days": sorted(days.values(), key=lambda d: d["date"]), "shadows": [], "pools": [], "model": "lit", "params": P}
