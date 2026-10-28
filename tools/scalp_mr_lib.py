"""Mean-reversion scalp research library (2026-10-28, owner: a third, high-frequency strategy on its own MFFU account).

Research only. Real CME NQ1! TradingView exports (data/NQ_1m.csv for 2026, data/NQ_5m.csv for 2021-25), times ET.

  from tools import scalp_mr_lib as L
  F = L.frame("1m")                 # bars + session features (VWAP bands, ATR, RSI, levels), no look-ahead
  sig = L.sig_vwap(F, k=2.0, ...)   # (dir, stop, target) arrays decided at a bar's CLOSE
  T = L.simulate(F, sig, rr=1.0, ...)   # one position at a time, market entry next bar open, costs + slippage
  L.stats(T, "2026-01-01", "2026-06-30")
  L.eval_sim(T, plan="25k")         # MFFU Builder eval rolled from every session (p10/f10/dec10/pass_med/slow_pass)

Fill model (honest by construction):
  entry   MARKET at the next bar's open + 1 tick against us (or a LIMIT that only fills when price trades THROUGH it by 1 tick)
  stop    stop price - 1 tick (or the bar's open if it gapped through), checked FIRST in every bar (worst case)
  target  LIMIT: filled only if the bar trades through it by 1 tick; no slippage
  time    MARKET at the bar's close - 1 tick (time stop, 15:55 flat)
  costs   $1.90 per micro round trip (0.95 pts per micro), MNQ $2 / pt.
A trade's net R = (pts - 0.95) / risk_pts, i.e. a fixed-$ risk scaled by the stop (integer micros come in eval_sim).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os

import numba as nb
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK = 0.25
PT_USD = 2.0              # MNQ
COMM = 1.90               # per micro round trip
COMM_PTS = COMM / PT_USD  # 0.95
_FR = {}

PLANS = {"25k": {"start": 25000.0, "target": 1500.0, "mll": 1000.0, "dll": 600.0, "lock": 100.0, "max_q": 20},
         "50k": {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "dll": 1000.0, "lock": 100.0, "max_q": 40}}


# ------------------------------------------------------------------------------------------------ data + features
def _rsi(c, n):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.where(d > 0, d, 0.0)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.where(d < 0, -d, 0.0)).ewm(alpha=1 / n, adjust=False).mean().values
    return 100 - 100 / (1 + up / np.maximum(dn, 1e-9))


def frame(tf="1m", start=None):
    key = (tf, start)
    if key in _FR:
        return _FR[key]
    path = os.path.join(ROOT, "data", f"NQ_{tf}.csv")
    d = pd.read_csv(path)
    if start:
        d = d[d.time >= pd.Timestamp(start, tz="America/New_York").timestamp()].reset_index(drop=True)
    et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
    d["et"] = et
    d["mod"] = et.dt.hour * 60 + et.dt.minute                       # minute of day (bar OPEN time)
    d["day"] = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")  # CME session: 18:00 belongs to the next day
    d["dow"] = (et + pd.Timedelta(hours=6)).dt.dayofweek
    bm = 1 if tf == "1m" else 5
    d["bm"] = bm
    o, h, l, c, v = (d[k].values.astype(float) for k in ("open", "high", "low", "close", "volume"))
    v = np.maximum(v, 1.0)
    tp = (h + l + c) / 3
    g = d.groupby("day", sort=False)
    # session VWAP (18:00 anchor)
    cv = g["volume"].cumsum().values.astype(float)
    d["_pv"] = tp * v; d["_pv2"] = tp * tp * v; d["_v"] = v
    cpv = d.groupby("day", sort=False)["_pv"].cumsum().values
    cpv2 = d.groupby("day", sort=False)["_pv2"].cumsum().values
    cvv = d.groupby("day", sort=False)["_v"].cumsum().values
    vw = cpv / cvv
    d["vwap"] = vw
    d["vsd"] = np.sqrt(np.maximum(cpv2 / cvv - vw * vw, 0))
    # RTH VWAP (09:30 anchor), NaN before 09:30
    rth = (d["mod"] >= 570) & (d["mod"] < 960)
    d["_rk"] = np.where(rth, d["day"], "x" + d["day"])
    a = d.groupby("_rk", sort=False)["_pv"].cumsum().values
    b = d.groupby("_rk", sort=False)["_pv2"].cumsum().values
    vv = d.groupby("_rk", sort=False)["_v"].cumsum().values
    rv = a / vv
    d["rvwap"] = np.where(rth, rv, np.nan)
    d["rvsd"] = np.where(rth, np.sqrt(np.maximum(b / vv - rv * rv, 0)), np.nan)
    # ATR / RSI / EMA (continuous)
    pc = np.concatenate([[c[0]], c[:-1]])
    trr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    d["atr"] = pd.Series(trr).ewm(alpha=1 / 14, adjust=False).mean().values
    for n in (2, 3, 7, 14):
        d[f"rsi{n}"] = _rsi(c, n)
    for n in (9, 20, 50, 200):
        d[f"ema{n}"] = pd.Series(c).ewm(span=n, adjust=False).mean().values
    # higher-TF trend proxy: EMA of closes over ~1h and ~4h (in bars of this tf)
    d["ema_1h"] = pd.Series(c).ewm(span=max(2, 60 // bm), adjust=False).mean().values
    d["ema_4h"] = pd.Series(c).ewm(span=max(2, 240 // bm), adjust=False).mean().values
    # levels known at the bar (fixed once their window has closed)
    def win_hl(mask, close_mod):
        hh = pd.Series(np.where(mask, h, np.nan)).groupby(d["day"].values).transform("max").values
        ll = pd.Series(np.where(mask, l, np.nan)).groupby(d["day"].values).transform("min").values
        known = d["mod"].values >= close_mod
        # after 18:00 the window of this session has not happened yet (Asia/London/OR) -> only known after close_mod same day
        known &= (d["mod"].values < 18 * 60)
        return np.where(known, hh, np.nan), np.where(known, ll, np.nan)
    m = d["mod"].values
    d["asia_h"], d["asia_l"] = win_hl((m >= 18 * 60) | (m < 120), 120)      # 18:00-02:00
    d["lon_h"], d["lon_l"] = win_hl((m >= 120) & (m < 300), 300)           # 02:00-05:00
    d["on_h"], d["on_l"] = win_hl((m >= 18 * 60) | (m < 570), 570)         # 18:00-09:30
    d["or_h"], d["or_l"] = win_hl((m >= 570) & (m < 585), 585)             # 09:30-09:45
    d["ib_h"], d["ib_l"] = win_hl((m >= 570) & (m < 630), 630)             # 09:30-10:30
    # prior day RTH high/low/close
    r = d[rth].groupby("day").agg(H=("high", "max"), L=("low", "min"), C=("close", "last"))
    days = list(dict.fromkeys(d["day"]))
    prev = {days[i]: days[i - 1] for i in range(1, len(days))}
    pdh = {k: r["H"].get(prev.get(k)) for k in days}
    pdl = {k: r["L"].get(prev.get(k)) for k in days}
    d["pdh"] = d["day"].map(pdh).astype(float)
    d["pdl"] = d["day"].map(pdl).astype(float)
    # running session high/low before this bar
    d["s_hi"] = g["high"].cummax().values
    d["s_lo"] = g["low"].cummin().values
    d.drop(columns=["_pv", "_pv2", "_v", "_rk"], inplace=True)
    _FR[key] = d
    return d


def arr(F, k):
    return F[k].values.astype(float)


# ------------------------------------------------------------------------------------------------ simulator
@nb.njit(cache=True)
def _sim(o, h, l, c, mod, dayi, sdir, sstop, stgt, slim, rr, maxbars, be_r, min_risk, max_risk, ent_lo, ent_hi, flat_mod,
         max_day, lim_bars, min_rr, slip, thru):
    n = len(o)
    out = np.full((n, 12), np.nan)
    k = 0
    i = 0
    cur_day = -1
    nday = 0
    while i < n - 2:
        if dayi[i] != cur_day:
            cur_day = dayi[i]; nday = 0
        d = sdir[i]
        inwin = (mod[i + 1] >= ent_lo and mod[i + 1] <= ent_hi) if ent_lo <= ent_hi else (mod[i + 1] >= ent_lo or mod[i + 1] <= ent_hi)
        if d == 0 or nday >= max_day or not inwin or dayi[i + 1] != dayi[i]:
            i += 1
            continue
        stop = sstop[i]
        # ---- entry
        j0 = i + 1
        is_lim = not np.isnan(slim[i])
        if is_lim:          # limit entry valid lim_bars bars
            lp = slim[i]
            filled = -1
            for j in range(i + 1, min(n, i + 1 + lim_bars)):
                if dayi[j] != dayi[i] or (mod[j] >= flat_mod and mod[j] < 1080):
                    break
                # (a bar that reaches the stop has traded through the limit first: filled, then stopped below)
                if (d == 1 and l[j] <= lp - thru) or (d == -1 and h[j] >= lp + thru):
                    filled = j
                    break
            if filled < 0:
                i += 1
                continue
            ent = lp
            j0 = filled
            if d == 1 and o[filled] < lp:
                ent = o[filled]
            if d == -1 and o[filled] > lp:
                ent = o[filled]
        else:
            ent = o[j0] + d * slip
        risk = (ent - stop) * d
        if risk < min_risk or risk > max_risk:
            i += 1
            continue
        if np.isnan(stgt[i]):
            tgt = ent + d * rr * risk
        else:
            tgt = stgt[i]
            if (tgt - ent) * d < min_rr * risk:
                i += 1
                continue
        # ---- manage
        be_done = False
        cur_stop = stop
        ex = np.nan; kind = 0; je = -1
        mfe = 0.0; mae = 0.0
        for j in range(j0, n):
            if dayi[j] != dayi[i] or (mod[j] >= flat_mod and mod[j] < 1080):      # flat: at the previous bar's close
                je = j - 1; ex = c[j - 1] - d * slip; kind = 3
                break
            # stop first
            if (d == 1 and l[j] <= cur_stop) or (d == -1 and h[j] >= cur_stop):
                px = cur_stop
                if j > j0 and ((d == 1 and o[j] < cur_stop) or (d == -1 and o[j] > cur_stop)):
                    px = o[j]
                ex = px - d * slip; je = j; kind = 2 if be_done else 1
                mae = max(mae, (ent - (l[j] if d == 1 else h[j])) * d)
                break
            fav = (h[j] - ent) if d == 1 else (ent - l[j])
            adv = (ent - l[j]) if d == 1 else (h[j] - ent)
            mae = max(mae, adv)
            if (not (is_lim and j == j0)) and ((d == 1 and h[j] >= tgt + TICK_) or (d == -1 and l[j] <= tgt - TICK_)):
                ex = tgt; je = j; kind = 0
                mfe = max(mfe, fav)
                break
            mfe = max(mfe, fav)
            if be_r > 0 and not be_done and fav >= be_r * risk:
                be_done = True
                cur_stop = ent + d * 0.5      # BE + 2 ticks (pays the costs roughly)
            if j - j0 + 1 >= maxbars:
                ex = c[j] - d * slip; je = j; kind = 4
                break
        if je < 0:
            break
        pts = (ex - ent) * d
        out[k, 0] = i; out[k, 1] = j0; out[k, 2] = je; out[k, 3] = d; out[k, 4] = ent; out[k, 5] = stop
        out[k, 6] = tgt; out[k, 7] = ex; out[k, 8] = kind; out[k, 9] = pts; out[k, 10] = risk; out[k, 11] = mae
        k += 1
        nday += 1
        i = max(je, i + 1)
    return out[:k]


TICK_ = TICK
KINDS = {0: "target", 1: "stop", 2: "be", 3: "flat", 4: "time"}


def simulate(F, sig, rr=1.0, maxbars=60, be_r=0.0, min_risk=3.0, max_risk=40.0, ent=(570, 900), flat=955, max_day=6,
             lim_bars=10, min_rr=0.5, slip=TICK, thru=TICK):
    sdir, sstop, stgt = sig[0], sig[1], sig[2]
    slim = sig[3] if len(sig) > 3 else np.full(len(sdir), np.nan)
    dayi = pd.factorize(F["day"])[0].astype(np.int64)
    out = _sim(arr(F, "open"), arr(F, "high"), arr(F, "low"), arr(F, "close"), F["mod"].values.astype(np.int64), dayi,
               sdir.astype(np.int64), sstop.astype(float), stgt.astype(float), slim.astype(float), float(rr), int(maxbars),
               float(be_r), float(min_risk), float(max_risk), int(ent[0]), int(ent[1]), int(flat), int(max_day), int(lim_bars),
               float(min_rr), float(slip), float(thru))
    T = pd.DataFrame(out, columns=["sig_i", "ent_i", "exit_i", "dir", "entry", "stop", "target", "exit", "kind", "pts", "risk",
                                   "mae"])
    for kk in ("sig_i", "ent_i", "exit_i", "dir", "kind"):
        T[kk] = T[kk].astype(int)
    T["day"] = F["day"].values[T["ent_i"].values]
    T["entry_t"] = F["time"].values[T["ent_i"].values]
    T["exit_t"] = F["time"].values[T["exit_i"].values] + 60 * int(F["bm"].iloc[0])
    T["r"] = (T["pts"] - COMM_PTS) / T["risk"]
    T["r_gross"] = (T["pts"] + 2 * TICK) / T["risk"]
    return T


# ------------------------------------------------------------------------------------------------ stats
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16"), "2026": ("2026-01-01", "2026-10-16"),
         "2021-25": ("2021-11-01", "2025-12-31"), "2025": ("2025-01-01", "2025-12-31"), "2021-24": ("2021-11-01", "2024-12-31")}


_ND = {}


def ndays(F, a, z):
    key = (id(F), a, z)
    if key in _ND:
        return _ND[key]
    s = F["day"]
    _ND[key] = int(((s >= a) & (s <= z) & (F["dow"] < 5)).groupby(s).any().sum())
    return _ND[key]


def _ndays_unused(F, a, z):
    s = F["day"]
    return int(((s >= a) & (s <= z) & (F["dow"] < 5)).groupby(s).any().sum())


def stats(T, F, span, risk_usd=100.0):
    a, z = SPANS[span] if isinstance(span, str) else span
    t = T[(T.day >= a) & (T.day <= z)]
    nd = max(ndays(F, a, z), 1)
    if not len(t):
        return {"n": 0, "tpw": 0}
    r = t["r"].values
    gp, gl = r[r > 0].sum(), -r[r < 0].sum()
    eq = np.cumsum(r); dd = float((eq - np.maximum.accumulate(np.concatenate([[0], eq]))[1:]).min())
    cost_r = (COMM_PTS + 2 * TICK) / t["risk"].values   # commission + the 2 ticks slippage of a market round trip
    return {"n": int(len(t)), "tpw": round(len(t) / nd * 5, 1), "win": round(100 * float((r > 0).mean()), 1),
            "avg_r": round(float(r.mean()), 3), "pf": round(float(gp / gl), 2) if gl else 99.0,
            "net_r": round(float(r.sum()), 1), "dd_r": round(dd, 1), "gross_r": round(float(t["r_gross"].sum()), 1),
            "cost_share": round(float(cost_r.sum() / max(t["r_gross"].clip(lower=0).sum(), 1e-9)), 2),
            "net_usd": round(float(r.sum()) * risk_usd), "usd_month": round(float(r.sum()) * risk_usd / nd * 21),
            "med_risk": round(float(t["risk"].median()), 2)}


# ------------------------------------------------------------------------------------------------ eval simulator
def size_q(risk_pts, budget, max_q):
    per = risk_pts * PT_USD + COMM + 2 * TICK * PT_USD
    return int(max(0, min(max_q, math.floor(budget / per))))


def dollar_trades(T, plan="25k", risk_usd=None, room_f=0.25, max_loss_day=None, max_day=99):
    """Static sizing (no eval state): $ per trade = qty * (pts*2 - 1.90)."""
    P = PLANS[plan]
    risk_usd = risk_usd or P["mll"] * 0.1
    q = np.array([size_q(x, risk_usd, P["max_q"]) for x in T["risk"].values])
    return q * (T["pts"].values * PT_USD - COMM), q


def eval_sim(T, F, span, plan="25k", risk_usd=None, room_f=0.25, dll_stop=None, day_profit_stop=None, horizon=40):
    """Start a fresh MFFU Builder eval on every session of the span and run it forward (trades only from that span on;
    stays OPEN if data ends). Size per trade = min(risk_usd, room_f * (balance - floor), DLL left) / (stop $ + costs).
    Daily: stop for the day once the day's P&L <= -soft DLL (MFFU soft loss) or a trade would risk past it.
    Intraday floor check uses each trade's worst point (mae)."""
    P = PLANS[plan]
    risk_usd = risk_usd if risk_usd is not None else 0.1 * P["mll"]
    dll = P["dll"] if dll_stop is None else dll_stop
    a, z = SPANS[span]
    days = sorted(set(F["day"][(F["day"] >= a) & (F["day"] <= z) & (F["dow"] < 5)]))
    tb = {}
    for rec in T[(T.day >= a) & (T.day <= z)][["day", "pts", "risk", "mae"]].itertuples(index=False):
        tb.setdefault(rec.day, []).append((rec.pts, rec.risk, rec.mae))
    res = []
    for s in range(len(days)):
        bal = P["start"]; floor = bal - P["mll"]; peak = bal; lock = P["start"] + P["lock"]
        out = ("OPEN", 0)
        for k, dday in enumerate(days[s:s + horizon]):
            dp = 0.0; failed = False
            for pts, risk, mae in tb.get(dday, []):
                if dp <= -dll or (day_profit_stop and dp >= day_profit_stop):
                    break
                room = bal + dp - floor
                bud = min(risk_usd, room_f * room, dll + dp)
                q = size_q(risk, bud, P["max_q"])
                if q <= 0:
                    continue
                if bal + dp - q * (mae * PT_USD) <= floor:
                    failed = True; dp -= (bal + dp - floor); break
                dp += q * (pts * PT_USD - COMM)
                if bal + dp <= floor:
                    failed = True; break
            bal += dp
            if failed or bal <= floor:
                out = ("FAIL", k + 1); break
            peak = max(peak, bal); floor = min(max(floor, peak - P["mll"]), lock)
            if bal - P["start"] >= P["target"]:
                out = ("PASS", k + 1); break
        res.append(out)
    n = len(res) or 1
    ps = [d for r, d in res if r == "PASS"]
    o = {}
    for H in (10, 15, 20):
        o[f"p{H}"] = round(100 * sum(1 for r, d in res if r == "PASS" and d <= H) / n, 1)
        o[f"f{H}"] = round(100 * sum(1 for r, d in res if r == "FAIL" and d <= H) / n, 1)
    o["dec10"] = round(o["p10"] + o["f10"], 1)
    o["pass_med"] = float(np.median(ps)) if ps else None
    o["slow_pass"] = round(100 * sum(1 for d in ps if d > 15) / len(ps), 1) if ps else None
    return o


def path_money(T, F, span, plan="25k", risk_usd=None, room_f=0.25):
    """Continuous account money: static $ risk per trade (no eval state), soft DLL. Net $, $/month, max DD $."""
    P = PLANS[plan]
    risk_usd = risk_usd if risk_usd is not None else 0.1 * P["mll"]
    a, z = SPANS[span]
    t = T[(T.day >= a) & (T.day <= z)]
    nd = max(ndays(F, a, z), 1)
    pn = []; dp = 0.0; cur = None; costs = 0.0
    for rec in t[["day", "pts", "risk"]].itertuples(index=False):
        if rec.day != cur:
            cur = rec.day; dp = 0.0
        if dp <= -P["dll"]:
            continue
        q = size_q(rec.risk, min(risk_usd, P["dll"] + dp), P["max_q"])
        x = q * (rec.pts * PT_USD - COMM); dp += x; pn.append(x); costs += q * (COMM + 2 * TICK * PT_USD)
    pn = np.array(pn) if pn else np.zeros(1)
    eq = np.cumsum(pn); dd = float((eq - np.maximum.accumulate(np.concatenate([[0], eq]))[1:]).min())
    return {"net": round(float(pn.sum())), "per_month": round(float(pn.sum()) / nd * 21), "dd": round(dd),
            "costs": round(costs)}


def save_trades(T, F, path):
    rows = []
    for r in T.itertuples(index=False):
        rows.append({"day": r.day, "entry_t": str(pd.Timestamp(int(r.entry_t), unit="s", tz="UTC").tz_convert("America/New_York")),
                     "exit_t": str(pd.Timestamp(int(r.exit_t), unit="s", tz="UTC").tz_convert("America/New_York")),
                     "dir": "long" if r.dir == 1 else "short", "entry": r.entry, "stop": r.stop, "target": round(r.target, 2),
                     "exit": round(r.exit, 2), "exit_kind": KINDS[int(r.kind)], "pts": round(r.pts, 2), "risk_pts": round(r.risk, 2),
                     "r_net": round(r.r, 3)})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(rows, open(path, "w"), indent=0)
    return len(rows)


def map_5m_to_1m(F5, sig5, F1):
    """A 5m signal decided at its bar close (t5 + 300 s) lands on the 1m bar whose close is that moment (open t5 + 240),
    so the trade is executed and managed on 1m bars (finer intrabar path, honest check of a 5m rule)."""
    n1 = len(F1)
    pos = pd.Series(np.arange(n1), index=F1["time"].values)
    tgt_t = F5["time"].values + 240
    idx = pos.reindex(tgt_t).values
    out = [np.zeros(n1, np.int64)] + [np.full(n1, np.nan) for _ in range(len(sig5) - 1)]
    ok = ~np.isnan(idx)
    ii = idx[ok].astype(int)
    for a, b in zip(out, sig5):
        a[ii] = b[ok]
    return tuple(out)
