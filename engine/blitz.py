"""BLITZ, the scalper (strategy 3): a PAPER SHADOW of the noise-area (NA) 1m momentum scalp with the prior-day range filter
(research/writeups/scalp-na-mffu.md, tools/scalp_na.py "prng>=0.8", research/scalp/na_best_trades.json; the unfiltered NA of
research/writeups/scalp-momentum.md is an option, off). Paper only: never routed to any account; nothing here imports a
broker / adapter / NinjaTrader module or writes an order file (tests/test_blitz.py checks it).

The rule, exactly as researched (tools/scalp_na_lib.signals / run = tools/scalp_mo.fam_na + tools/scalp_mo_lib._sim, 1m bars, ET):
  day filter  trade a day only if YESTERDAY's 09:30-16:00 range >= 0.8 x the mean of the last 14 such ranges (yesterday's
              included, as tools/scalp_na_lib._day_ctx; known before the open). Option "unfiltered" = the plain NA scalp.
  band        today's 09:30 open x (1 +/- sigma); sigma = for that minute of the day, the mean of |close / 09:30 open - 1| over
              the last 14 sessions (the current day never in it)
  checks      only at the 1m bar closes 11:00, 11:30, ..., 15:30 (bars opening 10:59 ... 15:29: the research window 10:30-15:30
              with checks every 30 bars counted from 09:30, so the first is 11:00): close above the upper band = LONG, below the
              lower = SHORT; when flat a later check can enter again; one position; max 6 trades a day; no new entry at -3R
  entry       market at the next bar's open + 1 tick
  stop        the signal close -/+ 1.5 x ATR(14) of 5-minute bars (Wilder, the last completed 5m bar); a stop fill is 1 tick worse
  exit        no fixed target (a 20R limit that never fills in practice); after +1R the stop trails 1.5R behind the best price;
              out at the close - 1 tick of the 30th bar after the entry bar (time) or of the day's last bar ending by 15:55 (flat)
  costs       $1.90 a micro round trip + 1 tick on every market and stop fill (inside the prices)

Two paper ledgers (both PAPER, never routed):
  25K eval    the research's eval size on a simulated MFFU Builder 25K (start $25,000, target +$1,500, $1,000 EOD trailing max
              loss locked at start + $100, $600 soft daily loss, 20 micros): 40% of the room to the trailing floor, capped at
              $600 and 0.9 x the soft daily loss left (unfiltered option: 30%, the scalp-momentum.md pick); a wide stop still gets
              1 micro while it fits half the room; a new eval ($63) from the next session after a pass / fail / stuck (room under
              2 x the median stop-out) = tools/scalp_na_lib.run_eval's back-to-back path, one eval at a time.
  50K + LIT   "BLITZ on a funded 50K next to LIT" (scalp-na-mffu.md rule 7, tools/scalp_na_combo.lit_money's BLITZ units): its own
              Engine where a candidate is dropped while LIT holds a trade or has a setup armed at the signal close; a trade is
              skipped when LIT is in a trade or ATLAS holds the other side at its entry, and closed at the open of the bar of
              LIT's entry (LIT FIRST) or of an opposite ATLAS entry (HEDGE), 1 tick worse; size = 20% of the room, <= $450 a
              trade, inside the $1,000 soft daily loss left (tools/div_stack.na_q), up to 6 a day, on a simulated funded Builder
              50K ($2,000 EOD trailing max loss locked at start + $100, $1,000 soft daily loss, 40 micros). Only BLITZ's own paper
              P&L is in that account (LIT's trades stay on LIT's real account and only block / pre-empt BLITZ); payouts are
              not simulated (the trading profit is the number to watch: research +$850 / +$690 a month in 2026 H1 / H2).
              LIT = the live bot's LIT run (trades, open position, armed setups); ATLAS = account B's open trade (when it runs)
              + the ATLAS members' paper trades (EMA, MACD, S/R).

Two executions of the same rule:
  backtest(df)   pure functions on a whole 1m frame (features -> signals -> execute), a port of the research code
  Engine         the live state machine: one closed 1m bar at a time (on_bar), no look-ahead, JSON state (a few KB). The day's
                 last bar before 15:55 is known at 15:54 or when a later bar / the clock (16:00 ET) shows it was the last.
  tests/test_blitz.py: both = research/scalp/na_best_trades.json trade for trade (330 trades, 2026), unfiltered = the 481 of
  research/scalp/mo_best_trades.json; the 50K ledger = the research's BLITZ units on LIT's account (LIT flat, LIT first,
  never opposite ATLAS) on the research's LIT / ATLAS trades.

Where it runs:
  PC     engine/live.py LiveBot._second_tick's paper job (engine/bg_worker.py job_second; a thread when the worker is off),
         after LIT's routing: pc_step(<bot state dir>/blitz_state.json, df1, now, res=LIT's run, second=the ATLAS paper run,
         atlas_open=account B's open trade) -> LiveBot.blitz, heartbeat "blitz" (compact), Live View's purple layer
         (engine/liveview_api.py "scalp"), the narrator (engine/narrator.py kind "blitz", PAPER, no phone push by default).
  cloud  tools/cloud_monitor.py: step(state "blitz", the PC's 1m bars, now, res=LIT's run, second=the ATLAS ledgers) every run
         (cold start warmed on data/NQ_1m.csv + the PC bars); pushes kind "second" titled "BLITZ PAPER ...", sent only with
         second_model.json "blitz": {"push": true} (absent = recorded, not sent). second_model.json "blitz": {"on": false}
         switches the shadow off, {"unfiltered": true} runs the plain NA scalp (read only here).

    python -X utf8 -m engine.blitz replay     # 2026 through the live Engine: H1 / H2 trades, $ and the paper 25K eval path
    python -X utf8 -m engine.blitz show       # the card of data/blitz_state.json (or the cloud state)
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import warnings
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
VERSION = 2
NAME = "BLITZ"
LABEL = "BLITZ (paper shadow)"
WRITEUP = "scalp-na-mffu"
PICK = "BLITZ"
INF = 1 << 62

# ---------------------------------------------------------------------------------------------------------------- the rule
TICK, PV, COMM = 0.25, 2.0, 1.90
RTH0 = 570                          # 09:30 ET: the reference open, the noise slots start here
RTH1 = 960                          # 16:00 ET: the prior-day range uses the bars opening 09:30 ... 15:59
LAST_IN = 954                       # open minute of the last bar that ends by 15:55 (the flat bar)
WIN = (630, 930)                    # research window [10:30, 15:30) of signal-bar open minutes
EVERY = 30                          # a check every 30 bars counted from 09:30
CHECKS = tuple(m for m in range(WIN[0], WIN[1]) if (m + 1 - RTH0) % EVERY == 0)   # 659 ... 929 = closes 11:00 ... 15:30
CHECK_IX = {m: k for k, m in enumerate(CHECKS)}
LOOKBACK = 14
VM = 1.0
STOP_ATR = 1.5
TRAIL_R, TRAIL_START = 1.5, 1.0
TGT_R = 20.0                        # research: trail exits get a 20R limit (never reached)
HOLD = 30                           # bars after the entry bar
MAXDAY = 6
DAY_STOP_R = 3.0
LAST_MOD = 930
PRNG_MIN = 0.8                      # the day filter: yesterday's RTH range >= 0.8 x the 14-range mean
PRNG_N, PRNG_MIN_N, PRNG_MIN_BARS = 14, 10, 5
CLOCK_GRACE_S = 300                 # no bar after the last one by 15:55 for 5 minutes past 15:55 = that bar was the day's last
LEDGER_KEEP = 400                   # paper trades kept per ledger in the state (~10 months at 9 a week)
WARM_DAYS = 35                      # cold start: this many calendar days of 1m bars build the band (14 sessions) and the ATR
RULE = {"vm": VM, "every": EVERY, "stop": "a5x1.5", "trail": TRAIL_R, "trail_start": TRAIL_START, "win": list(WIN), "hold_min": HOLD,
        "maxday": MAXDAY, "day_stop_r": DAY_STOP_R, "lookback": LOOKBACK, "filter": f"prng>={PRNG_MIN}"}

# ---------------------------------------------------------------------------------------------------------------- the paper accounts
PLAN = {"name": "MFFU Builder 25K", "start": 25000.0, "target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "maxq": 20,
        "price": 63.0, "f": 0.4, "cap": 600.0}
F_RAW = 0.3                         # the unfiltered NA's eval size (scalp-momentum.md); the filtered rule's is 0.4 (na_sizing pick)
STUCK_ROOM = 249.56                 # 2 x the median stop-out of one micro over 2026's 330 research trades (eval_score "stuck")
STUCK_ROOM_RAW = 243.20             # the same over the unfiltered 481
FUNDED50 = {"name": "MFFU Builder 50K funded, next to LIT", "start": 50000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0,
            "maxq": 40, "f": 0.2, "cap": 450.0, "slip": 0.25}
ATLAS_KEYS = ("ema_lon_vix", "macd_sweep", "sr_nyreclaim")
LIT_WAIT_S = 30 * 60                # LIT's 5m CISD limit works 30 minutes (live_model.json lit "wait" 6 bars)
# research/writeups/scalp-na-mffu.md (fixed $150 a trade; 25K eval 40% of the room, max $600; 50K next to LIT)
RESEARCH = {"H1": {"label": "2026 H1 (pick)", "pf": 1.63, "net": 5560, "per_month": 912, "tpw": 8.6, "p10": 31.1, "f10": 10.1,
                   "path_net": 7193, "b2b": "4/2", "lit50k_gain_pm": 301, "funded50k_trading_pm": 850},
            "H2": {"label": "2026 H2 (check)", "pf": 1.49, "net": 2143, "per_month": 577, "tpw": 7.0, "p10": 34.8, "f10": 2.9,
                   "path_net": 4726, "b2b": "3/2", "lit50k_gain_pm": 290, "funded50k_trading_pm": 690},
            "2021-25": {"label": "2021-25 (5m)", "pf": 1.06, "net": 4570, "per_month": 89, "tpw": 8.7, "p10": 16.8, "f10": 13.6,
                        "lit50k_gain_pm": 16}}
WHAT = ("BLITZ, the noise-area momentum scalp: on days after a wide day (yesterday's range >= 0.8 x its 14-day mean), a 1m close "
        "outside today's normal range around the 09:30 open (checked at 11:00, 11:30 ... 15:30) -> in its direction at the next "
        "open, stop 1.5 x the 5m ATR, trail 1.5R after +1R, out after 30 minutes or 15:55. Max 6 a day, -3R day stop. Two "
        "paper ledgers: a simulated Builder 25K eval, and a funded 50K next to LIT (only while LIT is flat). Never routed.")


def _nan(x) -> bool:
    return x is None or x != x


# ================================================================================================ switches (read only)
def cfg(path: str | None = None) -> dict:
    """second_model.json "blitz" (display / push / rule switches; absent = on, filtered, pushes off). Read only; never raises."""
    try:
        p = path or os.path.join(ROOT, "second_model.json")
        with open(p, encoding="utf-8") as fh:
            c = json.load(fh).get("blitz")
        return c if isinstance(c, dict) else {}
    except Exception:
        return {}


def enabled(c: dict | None = None) -> bool:
    c = cfg() if c is None else c
    return c.get("on", True) is not False


def push_on(c: dict | None = None) -> bool:
    c = cfg() if c is None else c
    return c.get("push") is True


def filtered_on(c: dict | None = None) -> bool:
    """The prior-day range filter (default on); second_model.json "blitz": {"unfiltered": true} = the plain NA scalp."""
    c = cfg() if c is None else c
    return c.get("unfiltered") is not True


# ================================================================================================ ET clock
_ETC: dict = {}


def et_parts(t: int) -> tuple:
    """(ET date "YYYY-MM-DD", ET minute of the day) of a bar open time (ET offsets are whole hours: cached per UTC hour)."""
    t = int(t)
    k = t // 3600
    v = _ETC.get(k)
    if v is None:
        e = _dt.datetime.fromtimestamp(k * 3600, ET)
        v = (e.strftime("%Y-%m-%d"), e.hour * 60 + e.minute)
        if len(_ETC) > 100_000:
            _ETC.clear()
        _ETC[k] = v
    return v[0], v[1] + (t % 3600) // 60


def et_date(t: int) -> str:
    return et_parts(t)[0]


def hm(t) -> str:
    try:
        return _dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M")
    except Exception:
        return "?"


def at_et(day: str, mod: int) -> int:
    d = _dt.date.fromisoformat(day)
    return int(_dt.datetime(d.year, d.month, d.day, mod // 60, mod % 60, tzinfo=ET).timestamp())


# ================================================================================================ one bar of an open trade
def manage(p: dict, o: float, h: float, l: float, c: float, first: bool, flat_bar: bool):
    """tools/scalp_mo_lib._sim's loop body for one bar of an open market-entry trade. p: {"dir", "fill", "stp", "tg", "risk",
    "ext", "mae", "nb" (bars since the entry bar)}; updated in place. Returns (exit price, kind) or None."""
    D = p["dir"]
    stp, tg, fill = p["stp"], p["tg"], p["fill"]
    if not first:
        if (D > 0 and o <= stp) or (D < 0 and o >= stp):              # gap through the stop
            xp = o - D * TICK
            p["mae"] = max(p["mae"], D * (fill - xp))
            return xp, "stop"
        if (D > 0 and o >= tg + TICK) or (D < 0 and o <= tg - TICK):
            return o, "target"
    adv = (fill - l) if D > 0 else (h - fill)
    hit_stop = (l <= stp) if D > 0 else (h >= stp)
    hit_tgt = (h >= tg + TICK) if D > 0 else (l <= tg - TICK)
    if hit_stop:
        xp = stp - D * TICK
        p["mae"] = max(p["mae"], D * (fill - xp))
        return xp, "stop"
    p["mae"] = max(p["mae"], adv)
    if hit_tgt:
        return tg, "target"
    if flat_bar:
        return c - D * TICK, "flat"
    if p["nb"] >= HOLD:
        return c - D * TICK, "time"
    ext = max(p["ext"], h) if D > 0 else min(p["ext"], l)
    p["ext"] = ext
    risk = p["risk"]
    if D * (ext - fill) >= TRAIL_START * risk:
        nt = ext - D * TRAIL_R * risk
        if D * (nt - stp) > 0:
            p["stp"] = nt
    return None


def trade_r(pts: float, risk: float) -> float:
    """R of one micro after costs (the research's daily-stop R and the trade file's r)."""
    return (pts * PV - COMM) / ((risk + TICK) * PV + COMM)


def per_micro(pts: float, risk: float, mae: float) -> dict:
    """tools/scalp_mo_lib.to_trades' $ per micro: pnl, risk (stop + 1 tick + commission), worst open loss."""
    return {"pnl_pm": pts * PV - COMM, "risk_pm": (risk + TICK) * PV + COMM, "mae_pm": -mae * PV - COMM}


# ================================================================================================ pure functions (whole frame)
def frame(df) -> dict:
    """A 1m bar frame (time, open, high, low, close; bar open times, closed bars) -> arrays + ET date / minute / flat bar."""
    import pandas as pd
    d = df.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)
    et = pd.to_datetime(d["time"].astype("int64"), unit="s", utc=True).dt.tz_convert("America/New_York")
    B = {"t": d["time"].to_numpy(np.int64), "o": d["open"].to_numpy(np.float64), "h": d["high"].to_numpy(np.float64),
         "l": d["low"].to_numpy(np.float64), "c": d["close"].to_numpy(np.float64),
         "mod": (et.dt.hour * 60 + et.dt.minute).to_numpy(np.int64)}
    dates = et.dt.strftime("%Y-%m-%d").to_numpy()
    ud, did = np.unique(dates, return_inverse=True)
    B["dates"], B["day"] = ud, did.astype(np.int64)
    flat = np.full(len(ud), -1, np.int64)
    for i in np.where(B["mod"] <= LAST_IN)[0]:
        flat[did[i]] = i
    B["flat_of_day"] = flat
    B["flat"] = flat[did] if len(did) else np.zeros(0, np.int64)
    return B


def atr5(B) -> np.ndarray:
    """Wilder-14 ATR of 5-minute bars built from the 1m bars, the value of the last COMPLETED 5m bar at each 1m close
    (= tools/scalp_mo_lib._atr5)."""
    t, h, l, c = B["t"], B["h"], B["l"], B["c"]
    if not len(t):
        return np.zeros(0)
    g = t // 300
    last = np.r_[g[1:] != g[:-1], True]
    first = np.r_[True, g[1:] != g[:-1]]
    gid = np.cumsum(first) - 1
    ng = gid[-1] + 1
    H = np.full(ng, -np.inf)
    Lo = np.full(ng, np.inf)
    np.maximum.at(H, gid, h)
    np.minimum.at(Lo, gid, l)
    C = c[last]
    pc = np.r_[C[0], C[:-1]]
    tr = np.maximum(H - Lo, np.maximum(abs(H - pc), abs(Lo - pc)))
    a = np.empty(ng)
    a[0] = tr[0]
    for i in range(1, ng):
        a[i] = a[i - 1] + (tr[i] - a[i - 1]) / 14.0
    pos = np.where(last, gid, gid - 1)
    return np.where(pos >= 0, a[np.clip(pos, 0, None)], tr[0])


def _days(B) -> list:
    d = B["day"]
    starts = np.r_[0, np.where(np.diff(d) != 0)[0] + 1] if len(d) else []
    out = []
    for s in starts:
        di = d[s]
        f = B["flat_of_day"][di]
        if f >= 0:
            out.append((int(di), int(s), int(f)))
    return out


def noise(B, lookback: int = LOOKBACK) -> tuple:
    """(sigma, 09:30 open) at every bar (= tools/scalp_mo._noise on 1m bars): sigma of the minute of the day = the mean of
    |close / 09:30 open - 1| at that minute over the prior `lookback` sessions; nan before 14 sessions exist."""
    c, m = B["c"], B["mod"]
    slots = np.arange(RTH0, 960, 1)
    hist = []
    sig = np.full(len(c), np.nan)
    op = np.full(len(c), np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        for di, s, f in _days(B):
            idx = np.arange(s, f + 1)
            r = idx[m[idx] >= RTH0]
            if len(r) == 0:
                continue
            o0 = B["o"][r[0]]
            mv = np.full(len(slots), np.nan)
            pos = (m[r] - RTH0).astype(int)
            ok = pos < len(slots)
            mv[pos[ok]] = np.abs(c[r[ok]] / o0 - 1)
            if len(hist) >= lookback:
                sg = np.nanmean(np.array(hist[-lookback:]), axis=0)
                sig[r[ok]] = sg[pos[ok]]
                op[r] = o0
            hist.append(mv)
    return sig, op


def prior_range(B) -> np.ndarray:
    """Per day id: yesterday's 09:30-16:00 range / the mean of the last 14 such ranges (yesterday's included), nan with fewer
    than 10 ranges or a day with fewer than 5 RTH bars (= tools/scalp_na_lib._day_ctx "prng_ratio")."""
    m, h, l = B["mod"], B["h"], B["l"]
    out = np.full(len(B["dates"]), np.nan)
    if not len(m):
        return out
    starts = np.r_[0, np.where(np.diff(B["day"]) != 0)[0] + 1]
    ends = np.r_[starts[1:], len(B["day"])]
    rngs, last = [], None
    for s, e in zip(starts, ends):
        di = int(B["day"][s])
        mm = m[s:e]
        rth = np.where((mm >= RTH0) & (mm < RTH1))[0] + s
        if len(rth) < PRNG_MIN_BARS:
            continue
        hi, lo = float(h[rth].max()), float(l[rth].min())
        if len(rngs) >= PRNG_MIN_N:
            out[di] = (last[0] - last[1]) / float(np.mean(rngs[-PRNG_N:])) if last is not None else np.nan
        rngs.append(hi - lo)
        last = (hi, lo)
    return out


def features(B) -> dict:
    sig, op = noise(B)
    return {"atr5": atr5(B), "sigma": sig, "o0": op, "up": op * (1 + VM * sig), "lo": op * (1 - VM * sig), "prng": prior_range(B)}


def signals(B, F, filtered: bool = True) -> list:
    """[(signal bar index, dir, stop)] in bar order: a check-bar close above the upper band (LONG) / below the lower (SHORT);
    filtered: only on days whose prior-day range ratio is >= 0.8 (removed before the executor, as the research's mask)."""
    c, m = B["c"], B["mod"]
    out = []
    for i in np.where((m >= WIN[0]) & (m < WIN[1]) & ~np.isnan(F["sigma"]))[0]:
        if (m[i] + 1 - RTH0) % EVERY:
            continue
        if filtered and not F["prng"][B["day"][i]] >= PRNG_MIN:
            continue
        for D in (1, -1):
            if (D > 0 and not c[i] > F["up"][i]) or (D < 0 and not c[i] < F["lo"][i]):
                continue
            out.append((int(i), D, float(c[i] - D * STOP_ATR * F["atr5"][i])))
    return out


def execute(B, sigs: list) -> list:
    """tools/scalp_mo_lib._sim for BLITZ's market entries: one position, max 6 a day, -3R day stop, flat 15:55. -> trades."""
    o, h, l, c, mod, day, flat = B["o"], B["h"], B["l"], B["c"], B["mod"], B["day"], B["flat"]
    out, busy, cur, dn, dR = [], -1, -1, 0, 0.0
    for s, D, st in sigs:
        if day[s] != cur:
            cur, dn, dR = day[s], 0, 0.0
        if s < busy or dn >= MAXDAY or dR <= -DAY_STOP_R:
            continue
        fe = int(flat[s])
        if s + 1 > fe or mod[s] > LAST_MOD:
            continue
        j = s + 1
        fill = float(o[j]) + D * TICK
        risk = D * (fill - st)
        if risk < TICK:
            busy = j
            continue
        p = {"dir": D, "fill": fill, "stp": st, "tg": fill + D * TGT_R * risk, "risk": risk, "ext": fill, "mae": 0.0, "nb": 0}
        x, i = None, j
        for i in range(j, fe + 1):
            p["nb"] = i - j
            x = manage(p, float(o[i]), float(h[i]), float(l[i]), float(c[i]), i == j, i >= fe)
            if x is not None:
                break
        xp, kind = x
        pts = D * (xp - fill)
        out.append(_trade_row(B["dates"][day[j]], int(B["t"][s]), int(B["t"][j]), int(B["t"][i]), D, fill, st, xp, kind, pts, risk,
                              p["mae"], i - j + 1))
        busy = i
        dn += 1
        dR += trade_r(pts, risk)
    return out


def _trade_row(day, sig_t, entry_t, exit_bar_t, D, fill, st, xp, kind, pts, risk, mae, bars) -> dict:
    return {"day": day, "sig_t": int(sig_t), "entry_t": int(entry_t), "exit_t": int(exit_bar_t) + 60, "dir": int(D), "entry": fill,
            "stop": st, "exit": xp, "exit_kind": kind, "pts": pts, "risk_pts": risk, "mae_pts": mae, "bars": int(bars),
            "r": trade_r(pts, risk), **per_micro(pts, risk, mae)}


def backtest(df, filtered: bool = True) -> list:
    """The whole rule on a 1m frame (pure, look-ahead-free by construction: every value at a bar uses bars up to it)."""
    B = frame(df)
    return execute(B, signals(B, features(B), filtered))


# ================================================================================================ the live state machine
def _empty_day() -> dict:
    return {"date": None, "closed": False, "session": False, "rth": False, "o0": None, "mv": [None] * len(CHECKS),
            "last_in": None, "sig": None, "dn": 0, "dR": 0.0, "rhi": None, "rlo": None, "rn": 0, "prng": None}


def new_engine(filtered: bool = True) -> dict:
    return {"v": VERSION, "filter": bool(filtered), "last_t": None, "bars": 0, "hist": [], "rngs": [], **_empty_day(),
            "atr": {"g": None, "h": None, "l": None, "c": None, "done": True, "a": None, "pc": None},
            "pos": None, "pend": None, "last_exit": None}


def _sigma(hist: list):
    """Today's sigma at each check (np.nanmean over the last 14 sessions, as the research), None = not enough history."""
    if len(hist) < LOOKBACK:
        return None
    a = np.array([[np.nan if _nan(x) else float(x) for x in row] for row in hist[-LOOKBACK:]], dtype=np.float64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        sg = np.nanmean(a, axis=0)
    return [None if v != v else float(v) for v in sg]


class Engine:
    """BLITZ on one closed 1m bar at a time (no look-ahead). state = new_engine() / a saved one (JSON-able, a few KB).
    on_bar(..., gate=) / on_clock() return events: signal, skip, entry, exit, relabel (a time exit on the day's last bar
    before 15:55 is a flat exit), day_end. gate(signal close time, dir) -> reason | None drops a candidate before the
    executor (the research's mask: the 50K ledger's "LIT holds a trade / has a setup armed")."""

    def __init__(self, state: dict | None = None, filtered: bool | None = None):
        ok = isinstance(state, dict) and state.get("v") == VERSION and "atr" in state
        if ok and filtered is not None and bool(state.get("filter")) != bool(filtered):
            ok = False                                 # the rule changed (filtered <-> unfiltered): start over
        self.s = state if ok else new_engine(True if filtered is None else filtered)

    # ---- the 5m ATR (Wilder 14), groups of t // 300
    def _atr_close(self):
        A = self.s["atr"]
        if A["done"] or A["g"] is None:
            return
        H, L, C = A["h"], A["l"], A["c"]
        pc = C if A["pc"] is None else A["pc"]
        tr = max(H - L, max(abs(H - pc), abs(L - pc)))
        A["a"] = tr if A["a"] is None else A["a"] + (tr - A["a"]) / 14.0
        A["pc"] = C
        A["done"] = True

    def _atr_bar(self, t, h, l, c):
        A = self.s["atr"]
        g = t // 300
        if A["g"] != g:
            self._atr_close()
            A.update(g=g, h=h, l=l, c=c, done=False)
        else:
            A["h"], A["l"], A["c"] = max(A["h"], h), min(A["l"], l), c
        if t % 300 == 240:                    # the 5th minute closes the 5m bar
            self._atr_close()

    # ---- the day
    def _close_day(self, why: str) -> list:
        """The day's part up to 15:55 is over: its last bar was the flat bar. Flatten a trade there, drop a signal made on it."""
        S = self.s
        if S["closed"] or S["date"] is None:
            return []
        S["closed"] = True
        ev = []
        if S["pend"]:
            p = S["pend"]
            ev.append({"ev": "skip", "t": p["t"], "dir": p["dir"], "why": "the signal bar was the day's last bar before 15:55: no entry"})
            S["pend"] = None
        if S["pos"] and S["last_in"]:
            t_i, c_i = S["last_in"]
            ev += self._exit(t_i, c_i - S["pos"]["dir"] * TICK, "flat")
        le = S.get("last_exit")
        if le and le.get("kind") == "time" and S["last_in"] and int(le["bar_t"]) == int(S["last_in"][0]):
            le["kind"] = "flat"                       # research: the day's last bar ends a trade as "flat", not "time"
            ev.append({"ev": "relabel", "entry_t": le["entry_t"], "kind": "flat", "why": why})
        if S["rth"]:                                  # the day joins the noise history (its check minutes are final now)
            S["hist"] = (S["hist"] + [list(S["mv"])])[-LOOKBACK:]
        ev.append({"ev": "day_end", "date": S["date"], "session": bool(S["session"]), "dn": S["dn"], "dR": round(S["dR"], 4)})
        return ev

    def _end_date(self) -> list:
        S = self.s
        ev = self._close_day("a new day started")
        if S["date"] is not None and int(S.get("rn") or 0) >= PRNG_MIN_BARS:   # the day's 09:30-16:00 range is final now
            S["rngs"] = (list(S.get("rngs") or []) + [S["rhi"] - S["rlo"]])[-PRNG_N:]
        return ev

    def _new_date(self, date: str):
        S = self.s
        S.update(_empty_day())
        S["date"] = date
        S["sig"] = _sigma(S["hist"])
        rg = list(S.get("rngs") or [])
        S["prng"] = (rg[-1] / float(np.mean(rg[-PRNG_N:]))) if len(rg) >= PRNG_MIN_N else None
        S["last_exit"] = None

    def day_ok(self) -> bool:
        """Today passes the day filter (always True for the unfiltered rule)."""
        S = self.s
        if not S.get("filter"):
            return True
        return S.get("prng") is not None and S["prng"] >= PRNG_MIN and int(S.get("rn") or 0) >= PRNG_MIN_BARS

    # ---- trades
    def _exit(self, bar_t, xp, kind) -> list:
        S = self.s
        p = S["pos"]
        D = p["dir"]
        pts = D * (xp - p["fill"])
        S["dn"] += 1
        S["dR"] += trade_r(pts, p["risk"])
        S["pos"] = None
        S["last_exit"] = {"entry_t": p["entry_t"], "bar_t": int(bar_t), "kind": kind}
        return [{"ev": "exit", "entry_t": p["entry_t"], "sig_t": p["sig_t"], "dir": D, "entry": p["fill"], "stop": p["stop0"],
                 "exit_bar_t": int(bar_t), "exit_t": int(bar_t) + 60, "exit": xp, "kind": kind, "pts": pts, "risk": p["risk"],
                 "mae": p["mae"], "bars": int(p["nb"]) + 1, "r": trade_r(pts, p["risk"]), "date": S["date"],
                 **per_micro(pts, p["risk"], p["mae"])}]

    def on_bar(self, t, o, h, l, c, gate=None) -> list:
        S = self.s
        t = int(t)
        if S["last_t"] is not None and t <= int(S["last_t"]):
            return []
        o, h, l, c = float(o), float(h), float(l), float(c)
        date, mod = et_parts(t)
        ev = []
        if date != S["date"]:
            ev += self._end_date()
            self._new_date(date)
        elif mod > LAST_IN and not S["closed"]:
            ev += self._close_day("a bar after 15:55 arrived")
        S["last_t"] = t
        S["bars"] = int(S.get("bars") or 0) + 1
        self._atr_bar(t, h, l, c)
        if RTH0 <= mod < RTH1:                        # the day's 09:30-16:00 range (the next day's filter)
            S["rn"] = int(S.get("rn") or 0) + 1
            S["rhi"] = h if S.get("rhi") is None else max(S["rhi"], h)
            S["rlo"] = l if S.get("rlo") is None else min(S["rlo"], l)
        in_day = mod <= LAST_IN and not S["closed"]
        if not in_day:
            return ev
        S["session"] = True
        S["last_in"] = [t, c]
        if mod >= RTH0:
            S["rth"] = True
            if S["o0"] is None:
                S["o0"] = o
            k = CHECK_IX.get(mod)
            if k is not None:
                S["mv"][k] = abs(c / S["o0"] - 1)
        # the entry of the signal made at the previous bar's close: market at this bar's open + 1 tick
        if S["pend"]:
            pd_ = S["pend"]
            S["pend"] = None
            D, st = pd_["dir"], pd_["stop"]
            fill = o + D * TICK
            risk = D * (fill - st)
            if risk < TICK:
                ev.append({"ev": "skip", "t": pd_["t"], "dir": D, "why": f"the open {o:,.2f} gapped past the stop: no entry"})
            else:
                S["pos"] = {"dir": D, "fill": fill, "stp": st, "stop0": st, "tg": fill + D * TGT_R * risk, "risk": risk, "ext": fill,
                            "mae": 0.0, "nb": 0, "entry_t": t, "sig_t": pd_["t"]}
                ev.append({"ev": "entry", "entry_t": t, "sig_t": pd_["t"], "dir": D, "entry": fill, "stop": st, "risk": risk,
                           "date": date, "band": pd_.get("band"), "close": pd_.get("close"), "atr5": pd_.get("atr5")})
        # the open trade on this bar
        if S["pos"]:
            p = S["pos"]
            x = manage(p, o, h, l, c, t == p["entry_t"], mod == LAST_IN)
            if x is not None:
                ev += self._exit(t, x[0], x[1])
            else:
                p["nb"] += 1
        # the check at this bar's close
        k = CHECK_IX.get(mod)
        if k is not None and S["sig"] is not None and S["o0"] is not None and not _nan(S["sig"][k]) and self.day_ok():
            sg = S["sig"][k]
            up, lo = S["o0"] * (1 + VM * sg), S["o0"] * (1 - VM * sg)
            D = 1 if c > up else -1 if c < lo else 0
            if D:
                a5 = S["atr"]["a"]
                masked = gate(t + 60, D) if gate is not None else None
                why = masked or ("in a trade" if S["pos"] else f"{MAXDAY} trades today already" if S["dn"] >= MAXDAY
                                 else f"day stop: {S['dR']:+.2f}R today" if S["dR"] <= -DAY_STOP_R else None)
                band = up if D > 0 else lo
                sgl = {"ev": "signal", "t": t, "close_t": t + 60, "dir": D, "close": c, "band": band, "up": up, "lo": lo,
                       "sigma": sg, "o0": S["o0"], "atr5": a5, "taken": why is None, "why": why, "masked": bool(masked), "date": date}
                if why is None:
                    st = c - D * STOP_ATR * a5
                    sgl["stop"] = st
                    S["pend"] = {"t": t, "dir": D, "stop": st, "band": band, "close": c, "atr5": a5}
                ev.append(sgl)
        if mod == LAST_IN:
            ev += self._close_day("15:54 bar closed")
        return ev

    def on_clock(self, now: int) -> list:
        """No bar after the day's last one by 15:55 for CLOCK_GRACE_S past 15:55 (a half day, a missing bar): that bar was the
        flat bar (the research's last bar ending by 15:55)."""
        S = self.s
        if S["date"] is None or S["closed"] or not S["last_in"]:
            return []
        if int(now) >= at_et(S["date"], LAST_IN + 1) + CLOCK_GRACE_S:
            return self._close_day("no bar by 16:00 ET")
        return []

    # ---- views
    def band_now(self) -> dict | None:
        """Today's band at every check (None before 14 sessions / before 09:30)."""
        S = self.s
        if S["sig"] is None:
            return {"ready": False, "sessions": len(S["hist"]), "need": LOOKBACK}
        o0 = S["o0"]
        rows = []
        for k, m in enumerate(CHECKS):
            sg = S["sig"][k]
            t_close = at_et(S["date"], m + 1) if S["date"] else None
            rows.append({"mod": m, "hm": f"{(m + 1) // 60:02d}:{(m + 1) % 60:02d}", "t": t_close, "sigma": sg,
                         "up": None if (o0 is None or _nan(sg)) else o0 * (1 + VM * sg),
                         "lo": None if (o0 is None or _nan(sg)) else o0 * (1 - VM * sg),
                         "pts": None if (o0 is None or _nan(sg)) else o0 * sg})
        return {"ready": True, "o0": o0, "date": S["date"], "checks": rows, "prng": S.get("prng"), "day_ok": self.day_ok(),
                "filter": bool(S.get("filter"))}


# ================================================================================================ LIT / ATLAS context (50K ledger)
def _armed_merge(res: dict | None, now: int, prev: list | None) -> list:
    """LIT's armed windows [a, z, dir] from a lit_live run (state setups + signals) merged with the ones earlier polls saw (a
    signal no longer in the run keeps its last window) = engine/atlas_v2.lit_inputs' windows."""
    W = {(int(x[2]), int(x[0])): [int(x[0]), int(x[1]), int(x[2])] for x in prev or [] if isinstance(x, (list, tuple)) and len(x) >= 3}
    st = (res or {}).get("state") or {}
    T = []
    for t in (res or {}).get("trades") or []:
        if t.get("entry_t") is not None and t.get("dir") is not None:
            T.append((int(t["entry_t"]), 1 if int(t["dir"]) > 0 else -1))
    for p in (st.get("position"), st.get("enter_now")):
        if isinstance(p, dict) and p.get("entry_t") is not None:
            T.append((int(p["entry_t"]), 1 if int(p.get("dir") or 1) > 0 else -1))
    exp = {}
    for side, s in (st.get("setups") or {}).items():
        if isinstance(s, dict) and s.get("arm_t") is not None:
            exp[(1 if side == "long" else -1, int(s["arm_t"]))] = max(int(s.get("expires_t") or 0), int(now))
    for s in (res or {}).get("signals") or []:
        if not isinstance(s, dict) or s.get("t") is None or s.get("dir") is None:
            continue
        d, a = (1 if int(s["dir"]) > 0 else -1), int(s["t"])
        stt = s.get("status")
        if stt in ("pending", "entering") or (d, a) in exp:
            z = max(exp.get((d, a), 0), int(now))
        elif stt == "filled":
            z = min((e for e, dd in T if dd == d and e >= a), default=a + LIT_WAIT_S)
        else:
            z = a + LIT_WAIT_S
        W[(d, a)] = [a, int(z), d]
    for (d, a), z in exp.items():
        if (d, a) not in W:
            W[(d, a)] = [a, int(z), d]
    return sorted(W.values(), key=lambda x: x[0])[-200:]


def _rows_of(block: dict | None, key: str) -> list:
    s = ((block or {}).get("strategies") or {}).get(key) or {}
    rows = list(s.get("trades") or [])
    led = s.get("ledger")
    if isinstance(led, dict):
        rows += list(led.values())
    elif isinstance(led, list):
        rows += led
    return [r for r in rows if isinstance(r, dict)]


def context(S: dict, res: dict | None = None, second: dict | None = None, atlas_open=None, now: int | None = None) -> dict:
    """{"lit": [(entry, exit | None, dir)], "armed": [(a, z)], "atlas": [(entry, exit | None, dir)]} from the live bot's LIT run
    (res), the ATLAS members' paper run / ledgers (second) and account B's open trade (atlas_open: {"entry_t", "dir"}).
    Keeps LIT's armed windows in S["lit_armed"]."""
    now = int(now or S.get("t") or 0)
    lit = {}
    for t in (res or {}).get("trades") or []:
        if t.get("entry_t") is not None and t.get("dir") is not None:
            lit[int(t["entry_t"])] = (int(t["entry_t"]), int(t["exit_t"]) if t.get("exit_t") else None, 1 if int(t["dir"]) > 0 else -1)
    st = (res or {}).get("state") or {}
    for p in (st.get("position"), st.get("enter_now")):
        if isinstance(p, dict) and p.get("entry_t") is not None and int(p["entry_t"]) not in lit:
            lit[int(p["entry_t"])] = (int(p["entry_t"]), None, 1 if int(p.get("dir") or 1) > 0 else -1)
    if res is not None:
        S["lit_armed"] = _armed_merge(res, now, S.get("lit_armed"))
    atlas = {}
    for k in ATLAS_KEYS:
        for r in _rows_of(second, k):
            if r.get("entry_t") is None or r.get("dir") is None:
                continue
            fin = r.get("exit_kind") not in (None, "", "OPEN") and r.get("exit_t")
            atlas[(k, int(r["entry_t"]))] = (int(r["entry_t"]), int(r["exit_t"]) if fin else None, 1 if int(r["dir"]) > 0 else -1)
    if isinstance(atlas_open, dict) and atlas_open.get("entry_t") is not None:
        atlas[("B", int(atlas_open["entry_t"]))] = (int(atlas_open["entry_t"]), None, 1 if int(atlas_open.get("dir") or 1) > 0 else -1)
    return {"lit": sorted(lit.values()), "armed": [(int(a), int(z)) for a, z, _ in S.get("lit_armed") or []],
            "atlas": sorted(atlas.values())}


class Ctx:
    """The 50K ledger's blockers, indexed by ET date: gate at the signal close, skip at the entry, cut inside a trade."""

    def __init__(self, ctx: dict | None):
        self.by = {}
        for k in ("lit", "atlas"):
            for x in (ctx or {}).get(k) or []:
                self.by.setdefault((k, et_date(x[0])), []).append((int(x[0]), INF if x[1] is None else int(x[1]), int(x[2])))
        for a, z in (ctx or {}).get("armed") or []:
            self.by.setdefault(("armed", et_date(a)), []).append((int(a), int(z)))

    def _get(self, k, t):
        return self.by.get((k, et_date(t)), ())

    def gate(self, t: int, D: int):
        """At the signal close: LIT in a trade / LIT setup armed -> the candidate does not exist on LIT's account."""
        if any(e <= t < x for e, x, _ in self._get("lit", t)):
            return "LIT in a trade"
        if any(a <= t < z for a, z in self._get("armed", t)):
            return "LIT setup armed"
        return None

    def skip(self, t: int, D: int):
        """At the entry bar's open: LIT in a trade, or ATLAS holding the other side -> not traded."""
        if any(e <= t < x for e, x, _ in self._get("lit", t)):
            return "LIT in a trade"
        if any(e <= t < x and d != D for e, x, d in self._get("atlas", t)):
            return "ATLAS holds the other side"
        return None

    def cut(self, entry_t: int, t: int, D: int):
        """("LIT FIRST" | "HEDGE", time) when LIT / an opposite ATLAS trade entered after the entry and at or before bar t."""
        a = min((e for e, _, _ in self._get("lit", entry_t) if entry_t < e <= t), default=None)
        if a is not None:
            return "LIT FIRST", a
        a = min((e for e, _, d in self._get("atlas", entry_t) if d != D and entry_t < e <= t), default=None)
        return ("HEDGE", a) if a is not None else None


# ================================================================================================ the paper shadow (ledgers + accounts)
def _new_eval(n: int) -> dict:
    return {"n": n, "start": None, "bal": 0.0, "peak": 0.0, "floor": -PLAN["mll"], "sess": 0, "day": None, "dp": 0.0, "halt": None,
            "end_day": None}


def _new_acct(n: int) -> dict:
    return {"n": n, "start": None, "bal": 0.0, "peak": 0.0, "floor": -FUNDED50["mll"], "sess": 0, "day": None, "cum": 0.0, "halt": None,
            "end_day": None}


def new_state(now: int, first_run: int | None = None, stuck: float | None = None, filtered: bool = True) -> dict:
    fr = int(first_run if first_run is not None else now)
    return {"v": VERSION, "paper": True, "never_routed": True, "name": NAME, "label": LABEL, "first_run": fr, "start_day": et_date(fr),
            "t": int(now), "filter": bool(filtered), "stuck": float(stuck if stuck is not None else (STUCK_ROOM if filtered else STUCK_ROOM_RAW)),
            "plan_f": PLAN["f"] if filtered else F_RAW, "eng": new_engine(filtered), "eng50": new_engine(filtered),
            "ledger": [], "skipped": [], "signals": [], "ev": _new_eval(1), "evals": [], "events": [], "open": None,
            "ledger50": [], "skipped50": [], "acct50": _new_acct(1), "accts50": [], "open50": None, "lit_armed": [],
            "bars_t": None, "warm": None}


def qty(risk_pm: float, room: float, day_pnl: float, f: float | None = None) -> int:
    """The research eval size (tools/scalp_na_lib.qty "frac"): f x the room (40%; 30% unfiltered), <= $600, <= 0.9 x the soft
    daily loss left, 20 micros; 1 micro while the trade fits half the room and the daily loss left."""
    dll_left = PLAN["dll"] + day_pnl
    budget = min(PLAN["cap"], (PLAN["f"] if f is None else f) * room, 0.9 * dll_left)
    if budget <= 0:
        return 0
    q = int(min(PLAN["maxq"], budget // risk_pm))
    if q == 0 and risk_pm <= min(0.5 * room, 0.9 * dll_left):
        q = 1
    return q


def qty50(risk: float, room: float, cum: float) -> int:
    """BLITZ on the funded 50K (tools/div_stack.na_q, nc {"f": 0.2, "cap": 450}): min(20% of the room, $450, the soft daily loss
    left) / (stop + 2 ticks + commission), <= 40 micros; no minimum."""
    usd = min(FUNDED50["f"] * max(0.0, room), FUNDED50["cap"])
    usd = min(usd, max(0.0, FUNDED50["dll"] + cum))
    loss1 = (risk + FUNDED50["slip"] * 2) * PV + COMM
    return max(0, min(int(FUNDED50["maxq"]), int(usd / loss1 + 1e-9)))


def _end_eval(S: dict, result: str, day: str, now: int):
    ev = S["ev"]
    prof = float(ev["bal"]) + float(ev["dp"])
    S["evals"] = (S.get("evals") or [])[-59:] + [{"n": ev["n"], "start": ev["start"], "end": day, "sessions": ev["sess"], "result": result,
                                                   "profit": round(prof, 2), "usd": round(sum(float(r.get("usd") or 0) for r in S["ledger"]
                                                                                              if r.get("eval") == ev["n"]), 2)}]
    S["events"] = (S.get("events") or [])[-40:] + [{"t": int(now), "kind": "eval", "n": ev["n"], "result": result, "day": day,
                                                    "profit": round(prof, 2), "sessions": ev["sess"]}]


def _open_session(S: dict, day: str):
    ev = S["ev"]
    if ev["halt"] in ("PASS", "FAIL", "STUCK") and ev["end_day"] is not None and day > ev["end_day"]:
        S["ev"] = ev = _new_eval(int(ev["n"]) + 1)              # a new eval from the session after the last one ended
    if ev["day"] == day:
        return
    ev.update(day=day, sess=int(ev["sess"]) + 1, dp=0.0, halt=None if ev["halt"] == "DLL" else ev["halt"])
    if ev["start"] is None:
        ev["start"] = day


def _eval_entry(S: dict, x: dict) -> tuple:
    """(micros, why) for a new paper trade on the eval."""
    day = x["date"]
    ev = S["ev"]
    if ev["halt"] in ("PASS", "FAIL", "STUCK") and ev["end_day"] == day:
        return 0, f"eval {ev['n']} ended today ({ev['halt']}): the next one starts next session"
    _open_session(S, day)
    ev = S["ev"]
    if ev["halt"] == "DLL":
        return 0, f"soft daily loss ${PLAN['dll']:,.0f} reached today"
    room = float(ev["bal"]) + float(ev["dp"]) - float(ev["floor"])
    q = qty(per_micro(0.0, x["risk"], 0.0)["risk_pm"], room, float(ev["dp"]), float(S.get("plan_f") or PLAN["f"]))
    return q, (None if q > 0 else f"size 0 (room ${room:,.0f})")


def _eval_exit(S: dict, row: dict, x: dict, now: int):
    ev = S["ev"]
    q = int(row.get("qty") or 0)
    if q <= 0 or row.get("eval") != ev["n"]:
        row["usd"] = 0.0
        return
    if float(ev["bal"]) + float(ev["dp"]) + q * x["mae_pm"] <= float(ev["floor"]):
        pnl = float(ev["floor"]) - float(ev["bal"]) - float(ev["dp"])
        row.update(usd=round(pnl, 2), note=f"eval {ev['n']} FAILED on this trade (worst open loss reached the trailing floor)")
        ev["dp"] = float(ev["dp"]) + pnl
        _end_eval(S, "FAIL", x["date"], now)
        ev.update(halt="FAIL", end_day=x["date"])
        return
    ev["dp"] = float(ev["dp"]) + q * x["pnl_pm"]
    row["usd"] = round(q * x["pnl_pm"], 2)
    if float(ev["bal"]) + float(ev["dp"]) >= PLAN["target"]:
        row["note"] = f"eval {ev['n']} PASSED on this trade"
        _end_eval(S, "PASS", x["date"], now)
        ev.update(halt="PASS", end_day=x["date"])
    elif float(ev["dp"]) <= -PLAN["dll"]:
        ev["halt"] = "DLL"


def _eval_day_end(S: dict, day: str, now: int):
    """End of a session (tools/scalp_mo_lib.run_eval's end of day: fail / trail the floor / stuck)."""
    if day < S["start_day"]:
        return
    ev = S["ev"]
    if ev["halt"] in ("PASS", "FAIL", "STUCK") and ev["end_day"] == day:
        return
    _open_session(S, day)
    ev = S["ev"]
    ev["bal"] = float(ev["bal"]) + float(ev["dp"])
    ev["dp"] = 0.0
    if ev["bal"] <= float(ev["floor"]):
        _end_eval(S, "FAIL", day, now)
        ev.update(halt="FAIL", end_day=day)
        return
    ev["peak"] = max(float(ev["peak"]), ev["bal"])
    ev["floor"] = min(max(float(ev["floor"]), ev["peak"] - PLAN["mll"]), PLAN["lock"])
    if ev["bal"] - float(ev["floor"]) < float(S.get("stuck") or STUCK_ROOM):
        _end_eval(S, "STUCK", day, now)
        ev.update(halt="STUCK", end_day=day)
        return
    ev["halt"] = None


# ---- the funded 50K next to LIT
def _acct_open(S: dict, day: str):
    a = S["acct50"]
    if a["halt"] == "LOST" and a["end_day"] is not None and day > a["end_day"]:
        S["acct50"] = a = _new_acct(int(a["n"]) + 1)            # a new paper funded account from the next session
    if a["day"] == day:
        return
    a.update(day=day, sess=int(a["sess"]) + 1, cum=0.0, halt=None if a["halt"] == "DLL" else a["halt"])
    if a["start"] is None:
        a["start"] = day


def _acct_entry(S: dict, x: dict) -> tuple:
    day = x["date"]
    a = S["acct50"]
    if a["halt"] == "LOST" and a["end_day"] == day:
        return 0, f"paper funded account {a['n']} lost today: a new one next session"
    _acct_open(S, day)
    a = S["acct50"]
    if a["halt"] == "DLL" or float(a["cum"]) <= -FUNDED50["dll"]:
        return 0, f"soft daily loss ${FUNDED50['dll']:,.0f} reached today"
    room = round(float(a["bal"]) + float(a["cum"]) - float(a["floor"]), 2)
    q = qty50(round(float(x["risk"]), 2), room, float(a["cum"]))
    S["_last50"] = {"room": room, "cum": round(float(a["cum"]), 2)}
    return q, (None if q > 0 else f"size 0 (room ${room:,.0f})")


def _acct_book(S: dict, row: dict, pts: float, w1: float, day: str, now: int):
    """tools/uprisk.Funded.step's trade booking: the soft daily loss caps the loss, a worst open loss at the floor loses the
    account."""
    a = S["acct50"]
    q = int(row.get("qty") or 0)
    if q <= 0 or row.get("acct") != a["n"]:
        row["usd"] = 0.0
        return
    cum, bal, floor = float(a["cum"]), float(a["bal"]), float(a["floor"])
    pnl = pts * PV * q - COMM * q
    low = min(0.0, w1 * PV * q - COMM * q, pnl)
    if cum + low <= -FUNDED50["dll"]:
        pnl = -FUNDED50["dll"] - cum - FUNDED50["slip"] * PV * q
        low = pnl
        row["note"] = f"soft daily loss ${FUNDED50['dll']:,.0f} reached on this trade"
    if bal + cum + low <= floor:
        lossd = floor - bal - cum
        row.update(usd=round(lossd, 2), note=f"paper funded account {a['n']} LOST on this trade (worst open loss at the floor)")
        a["cum"] = cum + lossd
        S["accts50"] = (S.get("accts50") or [])[-29:] + [{"n": a["n"], "start": a["start"], "end": day, "sessions": a["sess"], "result": "LOST",
                                                          "profit": round(float(a["bal"]) + float(a["cum"]), 2)}]
        S["events"] = (S.get("events") or [])[-40:] + [{"t": int(now), "kind": "acct50", "n": a["n"], "result": "LOST", "day": day,
                                                        "profit": round(float(a["bal"]) + float(a["cum"]), 2), "sessions": a["sess"]}]
        a.update(halt="LOST", end_day=day)
        return
    a["cum"] = cum + pnl
    row["usd"] = round(pnl, 2)
    if a["cum"] <= -FUNDED50["dll"]:
        a["halt"] = "DLL"


def _acct_day_end(S: dict, day: str):
    if day < S["start_day"]:
        return
    a = S["acct50"]
    if a["halt"] == "LOST" and a["end_day"] == day:
        return
    _acct_open(S, day)
    a = S["acct50"]
    a["bal"] = float(a["bal"]) + float(a["cum"])
    a["cum"] = 0.0
    a["peak"] = max(float(a["peak"]), a["bal"])
    a["floor"] = min(max(float(a["floor"]), a["peak"] - FUNDED50["mll"]), FUNDED50["lock"])
    a["halt"] = None


def _side(d) -> str:
    return "LONG" if int(d) > 0 else "SHORT"


def _fixed_q(risk_pm: float, usd: float = 150.0, maxq: int = 20) -> int:
    """The research table's fixed $150 a trade (int($150 / risk per micro), 1..20)."""
    return max(1, min(maxq, int(usd / risk_pm)))


def _trim(S: dict, key: str):
    keep = int(S.get("keep") or LEDGER_KEEP)
    if len(S[key]) > keep:
        S[key] = S[key][-keep:]


def handle(S: dict, events: list, now: int, bar_close: int | None = None):
    """The 25K eval ledger on the 25K Engine's events (decided at `now`)."""
    fr = int(S["first_run"])
    for x in events:
        k = x["ev"]
        if k == "signal":
            if int(x["t"]) >= fr - 86400:
                S["signals"] = (S.get("signals") or [])[-59:] + [{kk: x.get(kk) for kk in ("t", "close_t", "date", "dir", "close", "band",
                                                                                         "up", "lo", "sigma", "stop", "taken", "why")}]
        elif k == "skip":
            S["skipped"] = (S.get("skipped") or [])[-59:] + [{"t": x["t"], "dir": x["dir"], "why": x["why"]}]
        elif k == "entry":
            if int(x["entry_t"]) < fr or x["date"] < S["start_day"]:
                continue                                       # before the shadow started (warm-up): not on the paper ledger
            q, why = _eval_entry(S, x)
            ev = S["ev"]
            risk_pm = per_micro(0.0, x["risk"], 0.0)["risk_pm"]
            lag = int(now) - (int(x["entry_t"]) + 60)
            S["ledger"].append({"id": f"BLZ:{int(x['entry_t'])}", "day": x["date"], "sig_t": int(x["sig_t"]), "entry_t": int(x["entry_t"]),
                                "dir": int(x["dir"]), "side": _side(x["dir"]), "entry": x["entry"], "stop": x["stop"], "stop_now": x["stop"],
                                "risk_pts": x["risk"], "qty": int(q), "risk_usd": round(q * risk_pm, 2), "eval": ev["n"], "session": ev["sess"],
                                "skip": why, "band": x.get("band"), "close": x.get("close"), "atr5": x.get("atr5"),
                                "time_exit_t": int(x["entry_t"]) + 60 * (HOLD + 1), "exit_t": None, "exit_kind": "OPEN", "exit": None,
                                "usd": None, "r": None, "decided_t": int(now), "late": lag > 120})
            S["open"] = f"BLZ:{int(x['entry_t'])}"
        elif k == "exit":
            row = next((r for r in reversed(S["ledger"]) if r["entry_t"] == int(x["entry_t"])), None)
            if row is None:
                continue
            row.update(exit_t=int(x["exit_t"]), exit=x["exit"], exit_kind=x["kind"], pts=x["pts"], r=round(x["r"], 4), mae_pts=x["mae"],
                       bars=x["bars"], booked_t=int(now), r_usd150=round(_fixed_q(x["risk_pm"]) * x["pnl_pm"], 2))
            _eval_exit(S, row, x, now)
            S["open"] = None
        elif k == "relabel":
            row = next((r for r in reversed(S["ledger"]) if r["entry_t"] == int(x["entry_t"])), None)
            if row is not None:
                row["exit_kind"] = x["kind"]
        elif k == "day_end":
            if x.get("session"):
                _eval_day_end(S, x["date"], now)
    _trim(S, "ledger")


def _row50(S: dict):
    oid = S.get("open50")
    return next((r for r in reversed(S["ledger50"]) if r["id"] == oid), None) if oid else None


def cut50(S: dict, C: Ctx, t: int, o: float, now: int):
    """Before bar t: the open 50K trade is closed at this bar's open (1 tick worse) when LIT entered after it (LIT first) or ATLAS
    entered the other way (HEDGE) at or before t = tools/scalp_na_combo.cut_on / yield_to (second_mix.cut_at)."""
    row = _row50(S)
    if row is None or row.get("exit_kind") != "OPEN" or t <= int(row["entry_t"]):
        return
    c = C.cut(int(row["entry_t"]), t, int(row["dir"]))
    if c is None:
        return
    kind, at = c
    D = int(row["dir"])
    pts = round(D * (o - float(row["entry"])), 2) - FUNDED50["slip"]
    w1 = min(0.0, float(row.get("worst") or 0.0), pts)
    row.update(exit_t=int(at), exit_bar_t=int(t), exit=float(row["entry"]) + D * pts, exit_kind=kind, pts=pts, w1=w1,
               r=round(trade_r(pts, float(row["risk_pts"])), 4), booked_t=int(now),
               why_cut="LIT entered: closed at the open (LIT first)" if kind == "LIT FIRST" else "ATLAS entered the other way: closed at the open")
    _acct_book(S, row, pts, w1, row["day"], now)
    S["open50"] = None


def handle50(S: dict, events: list, now: int, C: Ctx, bar: tuple | None):
    """The funded-50K-next-to-LIT ledger on the 50K Engine's events (its candidates already masked by LIT at the signal).
    bar = the 1m bar just fed (its low / high update the open trade's worst open points), None for the clock."""
    fr = int(S["first_run"])
    for x in events:
        k = x["ev"]
        if k == "signal":
            if x.get("masked") and int(x["t"]) >= fr - 86400:
                S["skipped50"] = (S.get("skipped50") or [])[-59:] + [{"t": int(x["t"]), "close_t": x.get("close_t"), "dir": x["dir"],
                                                                       "close": x.get("close"), "why": x["why"], "date": x.get("date")}]
        elif k == "entry":
            if int(x["entry_t"]) < fr or x["date"] < S["start_day"]:
                continue
            blocked = C.skip(int(x["entry_t"]), int(x["dir"]))   # LIT in a trade / ATLAS the other way: not a trade at all
            q, why = 0, blocked
            S.pop("_last50", None)
            if blocked is None:
                q, why = _acct_entry(S, x)                       # the account may still give it 0 micros (size, daily loss)
            else:
                _acct_open(S, x["date"])
            a = S["acct50"]
            risk = float(x["risk"])
            S["ledger50"].append({"id": f"B50:{int(x['entry_t'])}", "day": x["date"], "sig_t": int(x["sig_t"]), "entry_t": int(x["entry_t"]),
                                  "dir": int(x["dir"]), "side": _side(x["dir"]), "entry": x["entry"], "stop": x["stop"], "stop_now": x["stop"],
                                  "risk_pts": risk, "qty": int(q), "risk_usd": round(q * ((round(risk, 2) + 2 * FUNDED50["slip"]) * PV + COMM), 2),
                                  "acct": a["n"], "session": a["sess"], "skip": why, "worst": 0.0,
                                  "time_exit_t": int(x["entry_t"]) + 60 * (HOLD + 1), "exit_t": None,
                                  "exit_kind": "SKIP" if blocked else "OPEN", "exit": None, "usd": None if not blocked else 0.0, "r": None,
                                  "decided_t": int(now), "late": int(now) - (int(x["entry_t"]) + 60) > 120,
                                  **(S.pop("_last50", None) or {})})
            if not blocked:
                S["open50"] = f"B50:{int(x['entry_t'])}"
        elif k == "exit":
            row = next((r for r in reversed(S["ledger50"]) if r["entry_t"] == int(x["entry_t"])), None)
            if row is None or row.get("exit_kind") != "OPEN":
                continue                                       # skipped, or already closed by LIT / ATLAS (the engine's trade ran on)
            risk = float(row["risk_pts"])
            w1 = max(-(risk + FUNDED50["slip"]), min(0.0, -float(x["mae"]), float(x["pts"])))
            row.update(exit_t=int(x["exit_t"]), exit_bar_t=int(x["exit_bar_t"]), exit=x["exit"], exit_kind=x["kind"], pts=x["pts"], w1=w1,
                       r=round(x["r"], 4), mae_pts=x["mae"], bars=x["bars"], booked_t=int(now))
            _acct_book(S, row, float(x["pts"]), w1, row["day"], now)
            S["open50"] = None
        elif k == "relabel":
            row = next((r for r in reversed(S["ledger50"]) if r["entry_t"] == int(x["entry_t"])), None)
            if row is not None and row.get("exit_kind") == "time":
                row["exit_kind"] = x["kind"]
        elif k == "day_end":
            if x.get("session"):
                _acct_day_end(S, x["date"])
    # the open trade's worst open points so far (the entry bar included) for a cut at a later bar's open
    row = _row50(S) if bar is not None else None
    if row is not None and row.get("exit_kind") == "OPEN" and int(bar[0]) >= int(row["entry_t"]):
        t_b, o_b, h_b, l_b, c_b = bar
        D = int(row["dir"])
        lo = (l_b - float(row["entry"])) if D > 0 else (float(row["entry"]) - h_b)
        row["worst"] = max(min(float(row.get("worst") or 0.0), round(lo, 2)), -(round(float(row["risk_pts"]), 2) + FUNDED50["slip"]))
    _trim(S, "ledger50")


def _open_view(S: dict) -> None:
    """The open rows' live fields from the engines (trailed stop, best price, bars held)."""
    for eng, key, ledger in (("eng", "open", "ledger"), ("eng50", "open50", "ledger50")):
        p = (S.get(eng) or {}).get("pos")
        if not p or not S.get(key):
            continue
        row = next((r for r in reversed(S.get(ledger) or []) if r["id"] == S[key]), None)
        if row is not None and int(row["entry_t"]) == int(p["entry_t"]):
            row.update(stop_now=p["stp"], best=p["ext"], bars=int(p["nb"]) + 1, trail_on=bool(p["stp"] != p["stop0"]))


def _bars_of(df, after: int | None = None, upto: int | None = None):
    """(t, o, h, l, c) arrays of the bars with after < time <= upto (bar open times), sorted; only those rows are copied."""
    if df is None or not len(df):
        return None
    tc = df["time"].to_numpy()
    if len(tc) > 1 and not (np.diff(tc) > 0).all():
        df = df.sort_values("time").drop_duplicates("time", keep="last")
        tc = df["time"].to_numpy()
    i0 = 0 if after is None else int(np.searchsorted(tc, int(after), side="right"))
    i1 = len(tc) if upto is None else int(np.searchsorted(tc, int(upto), side="right"))
    d = df.iloc[i0:i1]
    return (d["time"].to_numpy(np.int64), d["open"].to_numpy(np.float64), d["high"].to_numpy(np.float64), d["low"].to_numpy(np.float64),
            d["close"].to_numpy(np.float64))


def history_frame(path: str | None = None, since: int | None = None):
    """data/NQ_1m.csv (the TradingView CME export) for a cold start where the live feed holds too few days (cloud)."""
    import pandas as pd
    p = path or os.path.join(ROOT, "data", "NQ_1m.csv")
    try:
        d = pd.read_csv(p)
    except Exception:
        return None
    if since is not None:
        d = d[d["time"] >= int(since)]
    return d.reset_index(drop=True)


def feed(S: dict, E: Engine, E50: Engine, C: Ctx, t: int, o: float, h: float, l: float, c: float, now: int):
    """One closed 1m bar through both ledgers (the 50K cut check runs at the bar's open, before the bar)."""
    cut50(S, C, t, o, now)
    evs = E.on_bar(t, o, h, l, c)
    if evs:
        handle(S, evs, now)
    evs = E50.on_bar(t, o, h, l, c, gate=C.gate)
    handle50(S, evs, now, C, (t, o, h, l, c))


def step(prev: dict | None, df1, now: int, first_run: int | None = None, hist=None, stuck: float | None = None, res: dict | None = None,
         second: dict | None = None, atlas_open=None, ctx: dict | None = None, filtered: bool | None = None) -> dict:
    """One poll (PC and cloud): feed the closed 1m bars after the last one seen (a cold start: the last WARM_DAYS days, of
    `hist` + df1, as warm-up: trades before the first run are not booked), then the clock. res / second / atlas_open = the
    live bot's LIT run, the ATLAS paper run, account B's open trade (the 50K ledger's blockers); ctx replaces them (tests).
    Never routes. Raises only on a programming error (callers catch)."""
    now = int(now)
    filtered = filtered_on() if filtered is None else bool(filtered)
    if isinstance(prev, dict) and prev.get("v") == VERSION and isinstance(prev.get("eng"), dict) and bool(prev.get("filter")) == filtered:
        S = json.loads(json.dumps(prev))                     # a failing step never leaves a half-updated state behind
        S.pop("error", None)
    else:
        S = new_state(now, first_run, stuck, filtered)
    E, E50 = Engine(S["eng"], filtered), Engine(S["eng50"], filtered)
    C = Ctx(ctx if ctx is not None else context(S, res, second, atlas_open, now))
    if E.s["last_t"] is None:                                # cold start: the last WARM_DAYS days warm the band and the ATR
        import pandas as pd
        frames = [f[["time", "open", "high", "low", "close"]] for f in (hist, df1) if f is not None and len(f)]
        bars = None
        if frames:
            m = pd.concat(frames).drop_duplicates("time", keep="last").sort_values("time")
            m = m[m["time"] >= now - WARM_DAYS * 86400]
            bars = _bars_of(m, None, now - 60)
            S["warm"] = {"from": int(m["time"].min()) if len(m) else None, "bars": int(len(m))}
    else:
        bars = _bars_of(df1, int(E.s["last_t"]), now - 60)   # the closed bars (t + 60 <= now) after the last one seen
    if bars is not None and len(bars[0]):
        t, o, h, l, c = bars
        for i in range(len(t)):
            feed(S, E, E50, C, int(t[i]), o[i], h[i], l[i], c[i], now)
        S["bars_t"] = int(t[-1])
    evs = E.on_clock(now)
    if evs:
        handle(S, evs, now)
    evs = E50.on_clock(now)
    if evs:
        handle50(S, evs, now, C, None)
    S["eng"], S["eng50"] = E.s, E50.s
    S["t"] = now
    _open_view(S)
    return S


# ================================================================================================ views
def eval_view(S: dict | None) -> dict:
    st = PLAN["start"]
    if not S:
        return {"status": "not started", "plan": PLAN["name"], "start_balance": st, "target": st + PLAN["target"]}
    ev = S["ev"]
    halted = ev["halt"] in ("PASS", "FAIL", "STUCK")
    bal = float(ev["bal"]) + float(ev["dp"])
    room = bal - float(ev["floor"])
    f = float(S.get("plan_f") or PLAN["f"])
    status = {"PASS": "passed today: a new eval from the next session", "FAIL": "failed: a new eval from the next session",
              "STUCK": "stuck (room too small): a new eval from the next session", "DLL": "soft daily loss reached: done today"}.get(ev["halt"], "open")
    return {"n": ev["n"], "start": ev["start"], "session": ev["sess"], "day": ev["day"], "plan": PLAN["name"], "start_balance": st,
            "balance": round(st + bal, 2), "profit": round(bal, 2), "today": round(float(ev["dp"]), 2) if not halted else None,
            "floor": round(st + float(ev["floor"]), 2), "room": round(room, 2), "target": st + PLAN["target"],
            "to_target": round(max(0.0, PLAN["target"] - bal), 2), "progress": round(max(0.0, min(1.0, bal / PLAN["target"])), 3),
            "status": status, "dll": PLAN["dll"], "price": PLAN["price"], "size": f"{f:.0%} of the room, max $600 a trade, 20 micros"}


def acct50_view(S: dict | None) -> dict:
    st = FUNDED50["start"]
    if not S or not S.get("acct50"):
        return {"status": "not started", "plan": FUNDED50["name"], "start_balance": st}
    a = S["acct50"]
    bal = float(a["bal"]) + float(a["cum"])
    status = {"LOST": "lost (worst open loss at the floor): a new paper funded account from the next session",
              "DLL": "soft daily loss reached: done today"}.get(a["halt"], "open")
    return {"n": a["n"], "start": a["start"], "session": a["sess"], "day": a["day"], "plan": FUNDED50["name"], "start_balance": st,
            "balance": round(st + bal, 2), "profit": round(bal, 2), "today": round(float(a["cum"]), 2),
            "floor": round(st + float(a["floor"]), 2), "room": round(bal - float(a["floor"]), 2), "status": status, "dll": FUNDED50["dll"],
            "size": "20% of the room, max $450 a trade, 40 micros, up to 6 a day; only while LIT is flat",
            "note": "BLITZ's own paper P&L only (LIT's trades stay on LIT's account and only block / pre-empt BLITZ); payouts not simulated"}


def _months(S: dict) -> float | None:
    if S and S.get("start_day") and S.get("t"):
        return max(1.0 / 21.0, ((_dt.date.fromisoformat(et_date(S["t"])) - _dt.date.fromisoformat(S["start_day"])).days + 1) / 30.4)
    return None


def money(S: dict | None) -> dict:
    rows = [r for r in (S or {}).get("ledger", []) if r.get("exit_kind") not in (None, "OPEN")]
    sized = [r for r in rows if int(r.get("qty") or 0) > 0]
    E = (S or {}).get("evals") or []
    bought = len(E) + 1 if S else 0
    usd = round(sum(float(r.get("usd") or 0) for r in sized), 2)
    months = _months(S)
    gw = sum(float(r["r_usd150"]) for r in rows if float(r.get("r_usd150") or 0) > 0)
    gl = -sum(float(r["r_usd150"]) for r in rows if float(r.get("r_usd150") or 0) < 0)
    return {"n": len(rows), "on_eval": len(sized), "usd": usd, "wins": sum(1 for r in rows if float(r.get("r") or 0) > 0),
            "avg_r": round(sum(float(r.get("r") or 0) for r in rows) / len(rows), 3) if rows else None,
            "usd150": round(sum(float(r.get("r_usd150") or 0) for r in rows), 2), "pf150": round(gw / gl, 2) if gl else None,
            "evals_bought": bought, "fees": round(PLAN["price"] * bought, 2), "net_less_fees": round(usd - PLAN["price"] * bought, 2),
            "per_month": round((usd - PLAN["price"] * bought) / months) if months else None,
            "passes": sum(1 for e in E if e["result"] == "PASS"), "fails": sum(1 for e in E if e["result"] == "FAIL"),
            "stuck": sum(1 for e in E if e["result"] == "STUCK"), "days": len({r["day"] for r in rows})}


def money50(S: dict | None) -> dict:
    rows = [r for r in (S or {}).get("ledger50", []) if r.get("exit_kind") not in (None, "OPEN", "SKIP")]
    sized = [r for r in rows if int(r.get("qty") or 0) > 0]
    usd = round(sum(float(r.get("usd") or 0) for r in sized), 2)
    months = _months(S)
    gw = sum(float(r["usd"]) for r in sized if float(r.get("usd") or 0) > 0)
    gl = -sum(float(r["usd"]) for r in sized if float(r.get("usd") or 0) < 0)
    allr = (S or {}).get("ledger50", [])
    return {"n": len(rows), "sized": len(sized), "usd": usd, "pf": round(gw / gl, 2) if gl else None,
            "per_month": round(usd / months) if months else None, "wins": sum(1 for r in sized if float(r.get("usd") or 0) > 0),
            "skipped": sum(1 for r in allr if r.get("exit_kind") == "SKIP"), "lit_first": sum(1 for r in rows if r.get("exit_kind") == "LIT FIRST"),
            "hedge": sum(1 for r in rows if r.get("exit_kind") == "HEDGE"),
            "masked": len([x for x in (S or {}).get("skipped50") or []]), "lost": len((S or {}).get("accts50") or [])}


def today_rows(S: dict | None, day: str | None = None, ledger: str = "ledger") -> list:
    if not S:
        return []
    day = day or et_date(S.get("t") or 0)
    return [r for r in S.get(ledger) or [] if r.get("day") == day]


def state_text(S: dict | None, now: int | None = None) -> dict:
    """{"stage", "text"}: what BLITZ is doing now, in plain words."""
    if not S:
        return {"stage": "off", "text": "BLITZ has not run yet: it runs after each Zlarior poll while the bot runs (paper)."}
    if S.get("error"):
        return {"stage": "error", "text": f"BLITZ paper shadow error: {S['error']}"[:200]}
    now = int(now or S.get("t") or 0)
    E = S.get("eng") or {}
    if E.get("last_t") is None:
        return {"stage": "waiting", "text": "Waiting for 1m bars (NinjaTrader feed) to start the paper shadow."}
    if now - int(E["last_t"]) > 15 * 60 and _in_hours(now):
        return {"stage": "stale", "text": f"No new 1m bar since {hm(int(E['last_t']) + 60)} ET: no paper entries until the bars are back."}
    if len(E.get("hist") or []) < LOOKBACK and E.get("sig") is None:
        return {"stage": "warming", "text": f"Warming up: {len(E.get('hist') or [])} of {LOOKBACK} sessions of 1m bars for the noise band."}
    p = E.get("pos")
    if p:
        row = next((r for r in reversed(S.get("ledger") or []) if r.get("entry_t") == p["entry_t"]), None)
        r50 = next((r for r in reversed(S.get("ledger50") or []) if r.get("entry_t") == p["entry_t"]), None)
        q = f"{row['qty']} MNQ on the 25K eval" if row and int(row.get("qty") or 0) > 0 else "no 25K eval size"
        q50 = (f", {r50['qty']} MNQ on the 50K next to LIT" if r50 and r50.get("exit_kind") == "OPEN" and int(r50.get("qty") or 0) > 0
               else f", 50K: {r50.get('skip') or r50.get('exit_kind')}" if r50 else ", 50K: not taken (LIT busy)")
        trail = "trailing 1.5R behind the best price" if p["stp"] != p["stop0"] else f"trail starts at +1R ({p['fill'] + p['dir'] * p['risk']:,.2f})"
        return {"stage": "trade", "text": f"PAPER {_side(p['dir'])} from {p['fill']:,.2f} ({q}{q50}), stop {p['stp']:,.2f} ({trail}); out by "
                                         f"{hm(int(p['entry_t']) + 60 * (HOLD + 1))} ET at the latest."}
    mod = et_parts(now)[1]
    date = et_date(now)
    wk = _dt.date.fromisoformat(date).weekday() < 5
    if E.get("date") == date and E.get("dn", 0) >= MAXDAY:
        return {"stage": "done", "text": f"Done for today: {MAXDAY} paper trades."}
    if E.get("date") == date and float(E.get("dR") or 0) <= -DAY_STOP_R:
        return {"stage": "done", "text": f"Done for today: day stop at {float(E['dR']):+.2f}R."}
    nxt = next((m for m in CHECKS if m + 1 > mod), None) if wk else None
    if nxt is None or not wk:
        return {"stage": "closed", "text": "No more checks today; the next at 11:00 ET on the next trading day."}
    if E.get("date") == date and E.get("filter") and not Engine(E).day_ok():
        pr = E.get("prng")
        return {"stage": "filtered", "text": "No BLITZ trades today: yesterday's 09:30-16:00 range was "
                                            + (f"{pr:.2f} x" if pr is not None else "unknown vs") + f" its 14-day mean (needs >= {PRNG_MIN})."}
    b = Engine(E).band_now() if E.get("date") == date else None
    if E.get("date") == date and E.get("o0") is not None and b and b.get("ready"):
        k = CHECK_IX[nxt]
        r = b["checks"][k]
        if r.get("up") is not None:
            return {"stage": "watching", "text": f"Next check {r['hm']} ET: a 1m close above {r['up']:,.2f} = PAPER LONG, below "
                                                f"{r['lo']:,.2f} = PAPER SHORT (09:30 open {E['o0']:,.2f} +/- {r['pts']:,.1f} pts)."}
    return {"stage": "waiting", "text": "Waiting for the 09:30 open; checks at 11:00, 11:30 ... 15:30 ET (paper)."}


def _in_hours(now: int) -> bool:
    d, mod = et_parts(now)
    return _dt.date.fromisoformat(d).weekday() < 5 and RTH0 <= mod <= LAST_IN


KEEP = ("id", "day", "entry_t", "dir", "side", "qty", "entry", "stop", "stop_now", "exit_t", "exit", "exit_kind", "usd", "r", "skip", "late",
        "time_exit_t")


def compact(S: dict | None, n: int = 8) -> dict | None:
    """The heartbeat block "blitz" (PC): state text, today's paper trades of both ledgers, the paper 25K eval and the paper
    funded 50K, today's band and signals. Small."""
    if not S:
        return None
    if S.get("error") and not S.get("eng"):
        return {"v": VERSION, "label": LABEL, "paper": True, "never_routed": True, "error": S["error"]}
    day = et_date(S.get("t") or 0)
    E = S.get("eng") or {}
    b = Engine(E).band_now() if E.get("date") == day else None
    op = next((r for r in reversed(S.get("ledger") or []) if r["id"] == S.get("open")), None) if S.get("open") else None
    op50 = _row50(S) if S.get("ledger50") is not None else None
    return {"v": VERSION, "t": S.get("t"), "first_run": S.get("first_run"), "label": LABEL, "name": NAME, "paper": True, "never_routed": True,
            "filter": bool(S.get("filter")), "state": state_text(S), "eval": eval_view(S), "money": money(S),
            "open": {k: op.get(k) for k in KEEP + ("best", "bars", "eval")} if op else None,
            "today": [{k: r.get(k) for k in KEEP + ("eval",)} for r in today_rows(S, day)][-n:],
            "funded50": {"label": "BLITZ on a funded 50K next to LIT (PAPER)", "account": acct50_view(S), "money": money50(S),
                         "open": {k: op50.get(k) for k in KEEP + ("acct", "best", "bars")} if op50 else None,
                         "today": [{k: r.get(k) for k in KEEP + ("acct",)} for r in today_rows(S, day, "ledger50")][-n:],
                         "skipped": [x for x in (S.get("skipped50") or []) if x.get("date") == day][-6:],
                         "accounts": (S.get("accts50") or [])[-4:]},
            "signals": [x for x in (S.get("signals") or []) if x.get("date") == day][-10:],
            "band": _band_compact(b), "evals": (S.get("evals") or [])[-6:], "error": S.get("error")}


def _band_compact(b: dict | None):
    if not b or not b.get("ready"):
        return b
    r2 = lambda v: None if v is None else round(float(v), 2)
    return {"o0": r2(b.get("o0")), "date": b.get("date"), "prng": None if b.get("prng") is None else round(float(b["prng"]), 3),
            "day_ok": b.get("day_ok"), "filter": b.get("filter"),
            "checks": [{"hm": r["hm"], "t": r["t"], "up": r2(r["up"]), "lo": r2(r["lo"])} for r in b["checks"]]}


def card(S: dict | None = None, pc: dict | None = None) -> dict:
    """The dashboard card (read-only): the full state (cloud) or the PC heartbeat's compact, the newer one."""
    S = S if isinstance(S, dict) and S.get("eng") else None
    pc = pc if isinstance(pc, dict) and pc.get("eval") else None
    use_pc = bool(pc) and (not S or int(pc.get("t") or 0) > int(S.get("t") or 0) + 3600)
    out = {"label": LABEL, "name": NAME, "paper": True, "never_routed": True, "what": WHAT, "research": RESEARCH, "writeup": WRITEUP,
           "source": "PC" if use_pc else ("cloud" if S else None)}
    ks = ("state", "eval", "money", "open", "today", "funded50", "signals", "band", "evals", "t", "first_run", "filter")
    if use_pc:
        out.update({k: pc.get(k) for k in ks})
    elif S:
        c = compact(S, n=40)
        out.update({k: c.get(k) for k in ks})
        out["trades"] = [r for r in S.get("ledger") or []][-40:]
        out["trades50"] = [r for r in S.get("ledger50") or []][-40:]
    else:
        out.update(state=state_text(None), eval=eval_view(None), money=money(None), today=[], evals=[])
    return out


def notices(S: dict | None, since: int, money_fmt=None) -> list:
    """Push payloads (kind "second", "BLITZ PAPER ...") for each new paper entry / exit / eval end after `since` (cloud)."""
    from . import push
    fm = money_fmt or (lambda x: ("+" if x >= 0 else "-") + f"${abs(x):,.0f}")
    out = []
    for r in (S or {}).get("ledger") or []:
        dt_ = int(r.get("decided_t") or r["entry_t"])
        r50 = next((x for x in (S.get("ledger50") or []) if x.get("entry_t") == r["entry_t"]), None)
        s50 = (f"; 50K next to LIT: {r50['qty']} MNQ" if r50 and int(r50.get("qty") or 0) > 0 else
               f"; 50K next to LIT: {r50.get('skip')}" if r50 and r50.get("skip") else "; 50K next to LIT: not taken (LIT busy)")
        if dt_ >= since:
            sz = f"{r['qty']} MNQ on the 25K eval" if int(r.get("qty") or 0) > 0 else f"no 25K eval size ({r.get('skip')})"
            p = push.text_payload("Cloud", "second", f"BLITZ PAPER {r['side']}",
                                  f"Paper entry {sz}{s50} at {float(r['entry']):,.2f}, stop {float(r['stop']):,.2f} (1.5 x 5m ATR), out by "
                                  f"{hm(r['time_exit_t'])} ET. Paper shadow, never traded.", key=f"blitz:fill:{r['entry_t']}", t=dt_, url="#/atlas")
            out.append({**p, "side": r["side"], "entry": r["entry"], "stop": r["stop"], "qty": r["qty"], "setup": LABEL})
        bt = int(r.get("booked_t") or 0)
        if r.get("exit_kind") not in (None, "OPEN") and bt >= since:
            u50 = f"; 50K {fm(float(r50.get('usd') or 0))}" if r50 and int(r50.get("qty") or 0) > 0 and r50.get("usd") is not None else ""
            p = push.text_payload("Cloud", "second", f"BLITZ PAPER {r['side']} {str(r['exit_kind']).upper()}",
                                  f"{fm(float(r.get('usd') or 0))} on the paper 25K eval{u50} ({float(r.get('r') or 0):+.2f}R). Shadow, never traded.",
                                  key=f"blitz:out:{r['entry_t']}", t=bt, url="#/atlas")
            out.append({**p, "side": r["side"], "usd": r.get("usd"), "exit": r.get("exit_kind"), "setup": LABEL})
    for e in (S or {}).get("events") or []:
        if e.get("kind") == "eval" and int(e.get("t") or 0) >= since:
            out.append(push.text_payload("Cloud", "second", f"BLITZ PAPER eval {e['n']} {e['result']}",
                                         f"Paper 25K eval {e['n']}: {e['result']} after {e['sessions']} sessions ({fm(float(e['profit']))}); "
                                         "a new paper eval from the next session.", key=f"blitz:eval:{e['n']}:{e['result']}",
                                         t=int(e["t"]), url="#/atlas"))
    return sorted(out, key=lambda n: n["t"])


def readme_lines(S: dict | None) -> list:
    if not S or not S.get("eng"):
        return []
    ev, m, st, a, m5 = eval_view(S), money(S), state_text(S), acct50_view(S), money50(S)
    return ["", f"### {LABEL}",
            "The noise-area 1m scalp with the prior-day range filter (research/writeups/scalp-na-mffu.md). Paper only, never routed.",
            f"- Now: {st['text']}",
            f"- 25K eval {ev.get('n')}: session {ev.get('session')}, balance ${ev.get('balance', 0):,.0f}, room ${ev.get('room', 0):,.0f}, "
            f"${ev.get('to_target', 0):,.0f} to pass. {m['n']} paper trades ({m['on_eval']} sized), ${m['usd']:+,.0f} on the eval, "
            f"${m['net_less_fees']:+,.0f} after {m['evals_bought']} x $63; passes {m['passes']}, fails {m['fails']}, stuck {m['stuck']}.",
            f"- Funded 50K next to LIT (paper, only while LIT is flat): balance ${a.get('balance', 0):,.0f}, {m5['sized']} trades, "
            f"${m5['usd']:+,.0f} (${m5['per_month'] or 0:+,}/month), {m5['skipped']} skipped, {m5['lit_first']} closed for LIT, "
            f"{m5['hedge']} for ATLAS, {m5['lost']} accounts lost."]


# ================================================================================================ PC
_MEM: dict = {}


def pc_path(bot_state_path: str | None) -> str:
    d = os.path.dirname(bot_state_path) if bot_state_path else os.path.join(ROOT, "data")
    return os.path.join(d, "blitz_state.json")


def pc_step(path: str, df1, now: int, res: dict | None = None, second: dict | None = None, atlas_open=None) -> dict | None:
    """The PC bot's paper job (engine/bg_worker.py job_second / LiveBot._second_tick's thread): one step, saved to `path`
    (kept in memory between polls while the file is the one written last). Never raises."""
    try:
        if not enabled():
            return None
        prev = None
        sig = None
        try:
            st_ = os.stat(path)
            sig = (st_.st_mtime_ns, st_.st_size)
        except OSError:
            pass
        m = _MEM.get(path)
        if m is not None and sig is not None and m[0] == sig:
            prev = m[1]
        elif sig is not None:
            with open(path, encoding="utf-8") as fh:
                prev = json.load(fh)
        S = step(prev, df1, now, res=res, second=second, atlas_open=atlas_open)
        p = prev or {}
        if not prev or (S.get("eng") or {}).get("last_t") != (p.get("eng") or {}).get("last_t") or S.get("ledger") != p.get("ledger") \
                or S.get("ledger50") != p.get("ledger50") or S.get("lit_armed") != p.get("lit_armed") or now - int(p.get("saved_t") or 0) > 600:
            S["saved_t"] = int(now)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(S, fh, separators=(",", ":"), default=str)
            os.replace(tmp, path)
            st_ = os.stat(path)
            _MEM[path] = ((st_.st_mtime_ns, st_.st_size), S)
        return S
    except Exception as e:
        return {"v": VERSION, "paper": True, "never_routed": True, "label": LABEL, "error": f"{e.__class__.__name__}: {e}"[:300]}


# ================================================================================================ CLI
def replay_2026(path: str | None = None, first_run: str = "2026-01-01", stuck: float | None = None, filtered: bool = True,
                ctx: dict | None = None) -> dict:
    """2026 (data/NQ_1m.csv) through both live Engines + ledgers, bar by bar, the shadow started at `first_run` 00:00 ET.
    ctx = the 50K ledger's LIT / ATLAS blockers (None = none)."""
    import pandas as pd
    df = pd.read_csv(path or os.path.join(ROOT, "data", "NQ_1m.csv"))
    fr = at_et(first_run, 0)
    S = new_state(fr, fr, stuck, filtered)
    S["keep"] = 10 ** 6
    E, E50 = Engine(S["eng"], filtered), Engine(S["eng50"], filtered)
    C = Ctx(ctx)
    t, o, h, l, c = _bars_of(df)
    for i in range(len(t)):
        feed(S, E, E50, C, int(t[i]), o[i], h[i], l[i], c[i], int(t[i]) + 60)
    S["eng"], S["eng50"], S["t"] = E.s, E50.s, int(t[-1]) + 60
    return S


def main(argv=None):
    import sys
    a = (argv if argv is not None else sys.argv[1:]) or ["show"]
    if a[0] == "replay":
        for nm, fr, z in (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-12-31")):
            S = replay_2026(first_run=fr, filtered="--unfiltered" not in a)
            S["ledger"] = [r for r in S["ledger"] if r["day"] <= z]
            m = money(S)
            print(f"{nm}: {m['n']} trades, avg {m['avg_r']}R, $150 a trade ${m['usd150']:+,.0f} (PF {m['pf150']}); paper 25K eval "
                  f"${m['usd']:+,.0f}, passes {m['passes']} fails {m['fails']} stuck {m['stuck']}, ${m['net_less_fees']:+,.0f} after fees")
        return 0
    p = os.path.join(ROOT, "data", "blitz_state.json")
    st = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    if st is None:
        cp = os.path.join(ROOT, "data", "cloud_state.json")
        st = json.load(open(cp, encoding="utf-8")).get("blitz") if os.path.exists(cp) else None
    print(json.dumps(card(st), indent=1, default=str)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
