"""Momentum / breakout / continuation SCALP research library (owner 2026-10-28: a third strategy on its own MFFU account).

Research only. Nothing here is imported by the engine.

  bars(tf)           CME NQ1! bars (tf 1 = data/NQ_1m.csv, 2026 only; tf 5 = data/NQ_5m.csv, 2021-11 .. 2026-10) as numpy
                     arrays + features (ET minute of day, day id, flat bar of each day, ATR, EMAs, RTH VWAP, 15m / 1h trend
                     from COMPLETED higher bars only)
  simulate(B, C, ..) bar-by-bar executor of candidate orders (numba): one position at a time, max trades a day, daily stop in
                     R, flat at 15:55. Fills:
                       market   next bar open + 1 tick
                       stop     at the level + 1 tick (or the gapped open + 1 tick)
                       limit    only when traded THROUGH by 1 tick, at the level (no slippage)
                       stop-out at the stop - 1 tick (or the gapped open - 1 tick); target = limit (traded through by 1 tick)
                       time / 15:55 exit = bar close - 1 tick
                     Same-bar ambiguity is always resolved against us: stop and target in one bar = stop; on the bar a stop or
                     limit entry fills, the stop counts if touched and the target only if the bar CLOSES beyond it.
  trades -> money    $2 a point a micro, $1.90 a micro round trip (slippage is inside the prices)
  eval_score(..)     MFFU Builder 25K / 50K eval simulator, a fresh eval on every session: risk per trade sized to the room
                     (f x room to the EOD trailing floor, $ cap, the soft daily loss left), max micros, intraday floor breach
                     on the trade's worst open loss, soft daily loss pauses the day. p10/f10, dec10, p15/f15, pass_med,
                     slow_pass and the back-to-back eval path ($, $/month, evals bought).
"""
from __future__ import annotations

import collections
import datetime as dt
import os
import pickle
import sys

import numpy as np
import pandas as pd
from numba import njit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
TICK = 0.25
PV = 2.0          # MNQ $ per point
COMM = 1.90       # $ per micro round trip
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "R": ("2021-11-01", "2025-12-31"),
         "2025": ("2025-01-01", "2025-12-31"), "2021-24": ("2021-11-01", "2024-12-31")}
PLANS = {"25k": {"target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "maxq": 20, "price": 63.0},
         "50k": {"target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "maxq": 40, "price": 91.80}}


# ================================================================================================ bars
def _ema(x, n):
    a = 2.0 / (n + 1)
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


_ema = njit(cache=True)(_ema)


def _htf(t, c, minutes, n):
    """EMA(n) of COMPLETED higher-timeframe closes, aligned to each bar (the value known at the bar's close only when
    the higher bar also closed at or before it: we use the previous completed higher bar)."""
    g = (t // (minutes * 60)).astype(np.int64)
    # last close of each group
    last = np.r_[g[1:] != g[:-1], True]
    gc = c[last]
    gg = g[last]
    e = _ema(gc.astype(np.float64), n)
    # slope = e - previous e
    sl = np.r_[0.0, np.diff(e)]
    pos = np.searchsorted(gg, g, side="left") - 1        # previous completed group (strictly before the bar's group)
    # a bar that is the last bar of its group: its group is complete at its close -> use it
    pos2 = np.where(last, pos + 1, pos)
    ok = pos2 >= 0
    ev = np.where(ok, e[np.clip(pos2, 0, None)], np.nan)
    sv = np.where(ok, sl[np.clip(pos2, 0, None)], np.nan)
    cv = np.where(ok, gc[np.clip(pos2, 0, None)], np.nan)
    return ev, sv, cv


_MEMO = {}


def _atr5(t, h, l, c):
    """Wilder-14 ATR of 5-minute bars built from 1m bars, value of the last COMPLETED 5m bar at each 1m close."""
    g = t // 300
    last = np.r_[g[1:] != g[:-1], True]
    first = np.r_[True, g[1:] != g[:-1]]
    gid = np.cumsum(first) - 1
    ng = gid[-1] + 1
    H = np.full(ng, -np.inf); Lo = np.full(ng, np.inf)
    np.maximum.at(H, gid, h); np.minimum.at(Lo, gid, l)
    C = c[last]
    pc = np.r_[C[0], C[:-1]]
    tr = np.maximum(H - Lo, np.maximum(abs(H - pc), abs(Lo - pc)))
    a = np.empty(ng); a[0] = tr[0]
    for i in range(1, ng):
        a[i] = a[i - 1] + (tr[i] - a[i - 1]) / 14.0
    pos = np.where(last, gid, gid - 1)
    return np.where(pos >= 0, a[np.clip(pos, 0, None)], tr[0])


def bars(tf=5, start="2021-11-01"):
    if (tf, start) not in _MEMO:
        _MEMO[(tf, start)] = _bars(tf, start)
    return _MEMO[(tf, start)]


def _bars(tf, start, cut_t=None):
    """cut_t: only bars that START before cut_t (look-ahead check; no cache)."""
    path = os.path.join(CACHE, f"scalp_mo_bars_{tf}.pkl")
    src = os.path.join(ROOT, "data", "NQ_1m.csv" if tf == 1 else "NQ_5m.csv")
    if cut_t is None and os.path.exists(path) and os.path.getmtime(path) > os.path.getmtime(src):
        return pickle.load(open(path, "rb"))
    d = pd.read_csv(src)
    if cut_t is not None:
        d = d[d.time < cut_t].reset_index(drop=True)
    et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
    d["date"] = et.dt.strftime("%Y-%m-%d")
    d["mod"] = et.dt.hour * 60 + et.dt.minute
    d["dow"] = et.dt.dayofweek
    d = d[d.date >= start].reset_index(drop=True)
    B = {k: d[k].to_numpy(np.float64) for k in ("open", "high", "low", "close", "volume")}
    B["o"], B["h"], B["l"], B["c"], B["v"] = B.pop("open"), B.pop("high"), B.pop("low"), B.pop("close"), B.pop("volume")
    B["t"] = d.time.to_numpy(np.int64)
    B["mod"] = d["mod"].to_numpy(np.int64)
    B["dow"] = d["dow"].to_numpy(np.int64)
    B["tf"] = tf
    dates = d.date.to_numpy()
    ud, did = np.unique(dates, return_inverse=True)
    B["dates"] = ud
    B["day"] = did.astype(np.int64)
    # flat bar: last bar of the day whose END is <= 15:55
    n = len(d)
    flat = np.full(len(ud), -1, np.int64)
    endm = B["mod"] + tf
    for i in range(n):
        if endm[i] <= 955:
            flat[did[i]] = i
    if cut_t is not None and n and flat[-1] < 0:
        flat[-1] = n - 1          # cut mode: the cut day may trade up to the cut (its open trades are ignored by the check)
    B["flat_of_day"] = flat
    B["flat"] = flat[did]
    # ATR (Wilder 14) on true range, intraday continuous
    c, h, l = B["c"], B["h"], B["l"]
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    B["tr"] = tr
    atr = np.empty(n)
    atr[0] = tr[0]
    for i in range(1, n):
        atr[i] = atr[i - 1] + (tr[i] - atr[i - 1]) / 14.0
    B["atr"] = atr
    B["atr5"] = atr if tf == 5 else _atr5(B["t"], h, l, c)
    for k in (9, 21, 50):
        B[f"ema{k}"] = _ema(c, k)
    for m, nm in ((15, "m15"), (60, "h1")):
        for k in (20, 50):
            e, s, cc = _htf(B["t"], c, m, k)
            B[f"{nm}_ema{k}"], B[f"{nm}_sl{k}"] = e, s
        B[f"{nm}_c"] = cc
    # RTH VWAP from 09:30 (nan before)
    tp = (h + l + c) / 3.0
    v = np.maximum(B["v"], 1.0)
    vw = np.full(n, np.nan)
    cpv = cv = 0.0
    lastday = -1
    for i in range(n):
        if did[i] != lastday:
            lastday = did[i]; cpv = cv = 0.0
        if B["mod"][i] >= 570:
            cpv += tp[i] * v[i]; cv += v[i]
            vw[i] = cpv / cv
    B["vwap"] = vw
    if cut_t is None:
        os.makedirs(CACHE, exist_ok=True)
        pickle.dump(B, open(path, "wb"))
    return B


def day_open_idx(B, mod0):
    """Index of the first bar at or after minute mod0 for every day (-1 if none before the flat bar)."""
    out = np.full(len(B["dates"]), -1, np.int64)
    m, dd = B["mod"], B["day"]
    sel = np.where(m >= mod0)[0]
    for i in sel:
        if out[dd[i]] < 0 and i <= B["flat_of_day"][dd[i]]:
            out[dd[i]] = i
    return out


# ================================================================================================ executor
# candidate columns: sig (bar idx; order works from sig+1), dir, kind (0 market, 1 stop, 2 limit), level, expiry (bars),
#   stop (abs price), tgt_r, tgt_abs (nan = use tgt_r), hold (bars after the fill), be_r (nan off), trail_r (nan off),
#   trail_start_r, prio
@njit(cache=True)
def _sim(o, h, l, c, flat, day, sig, dr, kind, level, expiry, stop0, tgt_r, tgt_abs, hold, be_r, be_off, trail_r, trail_start,
         maxday, day_stop_r, max_loss, day_tp_r, tick, last_mod_ok, mod):
    n = len(sig)
    out = np.zeros((n, 14))
    k = 0
    busy = -1
    cur_day = -1
    dn = 0
    dR = 0.0
    dl = 0
    for q in range(n):
        s = sig[q]
        d = day[s]
        if d != cur_day:
            cur_day = d; dn = 0; dR = 0.0; dl = 0
        if s < busy:
            continue
        if dn >= maxday or dR <= -day_stop_r or dl >= max_loss or dR >= day_tp_r:
            continue
        fe = flat[s]
        if s + 1 > fe or mod[s] > last_mod_ok:
            continue
        D = dr[q]
        st = stop0[q]
        lv = level[q]
        j = -1
        fill = 0.0
        jend = min(s + expiry[q], fe)
        cancel_at = jend
        if kind[q] == 0:
            j = s + 1
            fill = o[j] + D * tick
        else:
            # target used for limit cancel
            for jj in range(s + 1, jend + 1):
                if kind[q] == 1:
                    if D > 0:
                        if o[jj] >= lv:
                            j = jj; fill = o[jj] + tick; break
                        if h[jj] >= lv:
                            j = jj; fill = lv + tick; break
                        if l[jj] <= st:
                            cancel_at = jj; break
                    else:
                        if o[jj] <= lv:
                            j = jj; fill = o[jj] - tick; break
                        if l[jj] <= lv:
                            j = jj; fill = lv - tick; break
                        if h[jj] >= st:
                            cancel_at = jj; break
                else:
                    rk = abs(lv - st)
                    tg = tgt_abs[q] if not np.isnan(tgt_abs[q]) else lv + D * tgt_r[q] * rk
                    if D > 0:
                        if o[jj] <= lv - tick:
                            j = jj; fill = o[jj]; break
                        if l[jj] <= lv - tick:
                            j = jj; fill = lv; break
                        if h[jj] >= tg or l[jj] <= st:
                            cancel_at = jj; break
                    else:
                        if o[jj] >= lv + tick:
                            j = jj; fill = o[jj]; break
                        if h[jj] >= lv + tick:
                            j = jj; fill = lv; break
                        if l[jj] <= tg or h[jj] >= st:
                            cancel_at = jj; break
        if j < 0:
            busy = cancel_at
            continue
        risk = D * (fill - st)
        if risk < tick:
            busy = j
            continue
        tg = tgt_abs[q] if not np.isnan(tgt_abs[q]) else fill + D * tgt_r[q] * risk
        if D * (tg - fill) <= 0:
            busy = j
            continue
        stp = st
        ext = fill
        mae = 0.0
        xk = -1
        xp = 0.0
        xkind = 0
        for i in range(j, fe + 1):
            first = i == j
            if not first:
                # gap through the stop
                if (D > 0 and o[i] <= stp) or (D < 0 and o[i] >= stp):
                    xp = o[i] - D * tick; xk = i; xkind = 1
                    mae = max(mae, D * (fill - xp))
                    break
                if (D > 0 and o[i] >= tg + tick) or (D < 0 and o[i] <= tg - tick):
                    xp = o[i]; xk = i; xkind = 2
                    break
            adv = (fill - l[i]) if D > 0 else (h[i] - fill)
            hit_stop = (l[i] <= stp) if D > 0 else (h[i] >= stp)
            if first and kind[q] != 0:
                hit_tgt = (c[i] >= tg + tick) if D > 0 else (c[i] <= tg - tick)
            else:
                hit_tgt = (h[i] >= tg + tick) if D > 0 else (l[i] <= tg - tick)
            if hit_stop:
                xp = stp - D * tick; xk = i; xkind = 1
                mae = max(mae, D * (fill - xp))
                break
            mae = max(mae, adv)
            if hit_tgt:
                xp = tg; xk = i; xkind = 2
                break
            if i >= fe:
                xp = c[i] - D * tick; xk = i; xkind = 4
                break
            if i - j >= hold[q]:
                xp = c[i] - D * tick; xk = i; xkind = 3
                break
            # end of bar management
            if D > 0:
                ext = max(ext, h[i])
            else:
                ext = min(ext, l[i])
            mfe = D * (ext - fill)
            if not np.isnan(be_r[q]) and mfe >= be_r[q] * risk:
                nb = fill + D * be_off
                if D * (nb - stp) > 0:
                    stp = nb
            if not np.isnan(trail_r[q]) and mfe >= trail_start[q] * risk:
                nt = ext - D * trail_r[q] * risk
                if D * (nt - stp) > 0:
                    stp = nt
        pts = D * (xp - fill)
        out[k, 0] = s; out[k, 1] = j; out[k, 2] = xk; out[k, 3] = D; out[k, 4] = fill; out[k, 5] = st
        out[k, 6] = tg; out[k, 7] = xp; out[k, 8] = xkind; out[k, 9] = pts; out[k, 10] = risk; out[k, 11] = mae
        out[k, 12] = kind[q]; out[k, 13] = q
        k += 1
        busy = xk  # a new order can be placed at the close of the exit bar
        dn += 1
        r = (pts * 2.0 - 1.9) / ((risk + tick) * 2.0 + 1.9)
        dR += r
        if pts < 0:
            dl += 1
    return out[:k]


CAND_COLS = ("sig", "dir", "kind", "level", "expiry", "stop", "tgt_r", "tgt_abs", "hold", "be_r", "trail_r", "trail_start", "prio")
XK = {1: "stop", 2: "target", 3: "time", 4: "flat"}


def cands(rows):
    """rows: dict of arrays (CAND_COLS; missing ones get defaults) -> sorted structured dict."""
    n = len(rows["sig"])
    df = {"sig": np.asarray(rows["sig"], np.int64), "dir": np.asarray(rows["dir"], np.float64)}
    dflt = {"kind": 0, "level": np.nan, "expiry": 1, "stop": np.nan, "tgt_r": 1.0, "tgt_abs": np.nan, "hold": 10 ** 6,
            "be_r": np.nan, "trail_r": np.nan, "trail_start": 0.0, "prio": 0}
    for k, v in dflt.items():
        x = rows.get(k, v)
        df[k] = np.broadcast_to(np.asarray(x, np.float64), (n,)).copy()
    order = np.lexsort((df["prio"], df["sig"]))
    return {k: v[order] for k, v in df.items()}


def simulate(B, C, maxday=3, day_stop_r=2.0, max_loss=99, day_tp_r=99.0, be_off=0.25, last_mod=930):
    if len(C["sig"]) == 0:
        return np.zeros((0, 14))
    return _sim(B["o"], B["h"], B["l"], B["c"], B["flat"], B["day"], C["sig"], C["dir"], C["kind"].astype(np.int64), C["level"],
                C["expiry"].astype(np.int64), C["stop"], C["tgt_r"], C["tgt_abs"], C["hold"].astype(np.int64), C["be_r"], float(be_off),
                C["trail_r"], C["trail_start"], int(maxday), float(day_stop_r), int(max_loss), float(day_tp_r), TICK, int(last_mod),
                B["mod"])


def to_trades(B, X):
    """executor rows -> trade dicts (per micro $: pnl_pm, risk_pm, mae_pm)."""
    T = []
    for r in X:
        s, j, k = int(r[0]), int(r[1]), int(r[2])
        pts, risk, mae = float(r[9]), float(r[10]), float(r[11])
        T.append({"day": B["dates"][B["day"][j]], "sig_t": int(B["t"][s]), "entry_t": int(B["t"][j]),
                  "exit_t": int(B["t"][k]) + 60 * B["tf"], "dir": int(r[3]), "entry": float(r[4]), "stop": float(r[5]),
                  "target": float(r[6]), "exit": float(r[7]), "exit_kind": XK.get(int(r[8]), "?"), "pts": round(pts, 2),
                  "risk_pts": round(risk, 2), "mae_pts": round(mae, 2), "kind": int(r[12]), "bars": k - j + 1,
                  "pnl_pm": pts * PV - COMM, "risk_pm": (risk + TICK) * PV + COMM, "mae_pm": -mae * PV - COMM})
    return T


# ================================================================================================ scoring
def sessions(B, span):
    a, z = SPANS[span]
    return [d for d in B["dates"] if a <= d <= z and B["flat_of_day"][list(B["dates"]).index(d)] >= 0] if False else \
        [d for i, d in enumerate(B["dates"]) if a <= d <= z and B["flat_of_day"][i] >= 0]


def stats(T, S, risk_usd=100.0, maxq=20):
    """Fixed-$ risk per trade (int(risk_usd / risk_pm), min 1, max maxq): trades/week, win, avg R, PF, net, $/month, DD,
    cost share."""
    Ts = [t for t in T if S[0] <= t["day"] <= S[-1]] if S else []
    nS = len(S)
    if not Ts:
        return {"n": 0, "tpw": 0.0}
    q = np.array([max(1, min(maxq, int(risk_usd / t["risk_pm"]))) for t in Ts])
    pnl = np.array([t["pnl_pm"] for t in Ts]) * q
    R = np.array([t["pnl_pm"] / t["risk_pm"] for t in Ts])
    gross = np.array([t["pts"] * PV for t in Ts]) * q
    slip = np.array([TICK * PV * (2 if t["exit_kind"] != "target" else 1) * (1 if t["kind"] != 2 else 0.5) for t in Ts]) * q
    costs = COMM * q.sum() + slip.sum()
    gl = -pnl[pnl < 0].sum()
    eq = np.cumsum(pnl)
    dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
    weeks = collections.Counter(dt.date.fromisoformat(t["day"]).isocalendar()[:2] for t in Ts)
    allw = {dt.date.fromisoformat(d).isocalendar()[:2] for d in S}
    return {"n": len(Ts), "tpw": round(len(Ts) / (nS / 5), 2), "wk5": round(100 * sum(1 for w in allw if weeks.get(w, 0) >= 5) / len(allw), 1),
            "win": round(100 * float((pnl > 0).mean()), 1), "avg_r": round(float(R.mean()), 3),
            "pf": round(float(pnl[pnl > 0].sum() / gl), 2) if gl else 99.0, "net": round(float(pnl.sum())),
            "per_month": round(float(pnl.sum()) / (nS / 21)), "dd": round(dd), "risk_usd": risk_usd,
            "cost_share": round(100 * float(costs / max(abs(gross.sum() + slip.sum()), 1e-9)), 1),
            "gross_pts": round(float(sum(t["pts"] for t in Ts)), 1), "med_stop": float(np.median([t["risk_pts"] for t in Ts])),
            "t_r": round(float(R.mean() / (R.std(ddof=1) / np.sqrt(len(R)))) if len(R) > 2 and R.std() > 0 else 0.0, 2)}


def _qty(t, room, day_pnl, P, f, cap):
    dll_left = P["dll"] + day_pnl
    budget = min(cap, f * room, 0.9 * dll_left)
    if budget <= 0:
        return 0
    q = int(min(P["maxq"], budget // t["risk_pm"]))
    if q == 0 and t["risk_pm"] <= min(0.5 * room, 0.9 * dll_left):
        q = 1          # a wide-stop trade still gets 1 micro while it fits half the room and the soft daily loss
    return q


def run_eval(days, by, P, f, cap, horizon=20, keep=None, stuck=60.0):
    bal = peak = 0.0
    floor = -P["mll"]
    for kk, d in enumerate(days[:horizon]):
        dp = 0.0
        for t in by.get(d, ()):
            room = bal + dp - floor
            q = _qty(t, room, dp, P, f, cap)
            if q <= 0:
                continue
            if bal + dp + q * t["mae_pm"] <= floor:
                if keep is not None:
                    keep.append({**t, "qty": q, "pnl": round(floor - bal - dp, 2)})
                return "FAIL", kk + 1
            dp += q * t["pnl_pm"]
            if keep is not None:
                keep.append({**t, "qty": q, "pnl": round(q * t["pnl_pm"], 2)})
            if bal + dp >= P["target"]:
                return "PASS", kk + 1
            if dp <= -P["dll"]:
                break
        bal += dp
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - P["mll"]), P["lock"])
        if bal - floor < stuck:
            return "STUCK", kk + 1
    return "OPEN", min(len(days), horizon)


def eval_score(T, S, plan="25k", f=0.25, cap=300.0):
    P = PLANS[plan]
    by = collections.defaultdict(list)
    for t in T:
        by[t["day"]].append(t)
    # stuck: the room no longer fits 2 x the strategy's median stop-out (1 micro), the account is dead (buy a new one)
    stuck = 2.0 * float(np.median([t["risk_pm"] for t in T])) if T else 60.0
    res = [(run_eval(S[i:i + 20], by, P, f, cap, stuck=stuck), len(S) - i) for i in range(len(S))]
    o = {}
    for H in (10, 15, 20):
        R = [r for r, av in res if av >= H]
        N = len(R) or 1
        o[f"p{H}"] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= H) / N, 1)
        o[f"f{H}"] = round(100.0 * sum(1 for r in R if r[0] in ("FAIL", "STUCK") and r[1] <= H) / N, 1)
    o["dec10"] = round(o["p10"] + o["f10"], 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS"]
    o["pass_med"] = float(np.median(pas)) if pas else None
    o["slow_pass"] = round(100.0 * sum(1 for x in pas if x > 15) / len(pas), 1) if pas else None
    # back-to-back path: a new eval after each pass / fail (no reset), $ of every trade on the path
    k, K, n = 0, [], collections.Counter()
    while k < len(S):
        r, used = run_eval(S[k:], by, P, f, cap, len(S) - k, keep=K, stuck=stuck)
        n[r] += 1
        if r == "OPEN":
            break
        k += used
    p = np.array([x["pnl"] for x in K]) if K else np.zeros(1)
    eq = np.cumsum(p)
    bought = n["PASS"] + n["FAIL"] + n["STUCK"] + (1 if n["OPEN"] else 0)
    o.update(path_net=round(float(p.sum())), path_pm=round(float(p.sum()) / (len(S) / 21)),
             path_dd=round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())),
             b2b=f"{n['PASS']}/{n['FAIL'] + n['STUCK']}", evals_bought=bought,
             passes_pm=round(n["PASS"] / (len(S) / 21), 2), fees=round(bought * P["price"], 2),
             med_qty=float(np.median([x["qty"] for x in K])) if K else 0)
    o["path_net_less_fees"] = round(o["path_net"] - o["fees"])
    return o


def full_score(T, B, spans=("H1", "H2", "R"), plan="25k", f=0.25, cap=300.0, risk_usd=100.0):
    out = {}
    for sp in spans:
        S = sessions(B, sp)
        if not S:
            continue
        st = stats(T, S, risk_usd, PLANS[plan]["maxq"])
        if st["n"]:
            st.update(eval_score([t for t in T if S[0] <= t["day"] <= S[-1]], S, plan, f, cap))
        out[sp] = st
    return out


def runlib_trades(T, qty_usd=100.0, maxq=20):
    """Trades in the tools/runlib.save format (fixed $ risk)."""
    out = []
    for t in T:
        q = max(1, min(maxq, int(qty_usd / t["risk_pm"])))
        out.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": t["pnl_pm"] / t["risk_pm"],
                    "pnl": round(q * t["pnl_pm"], 2), "risk_pts": t["risk_pts"], "qty": q, "risk_usd": round(q * t["risk_pm"], 2),
                    "half": 0, "exit": t["exit_kind"], "trigger": t.get("trigger", ""), "mfe": None, "mae": t["mae_pts"],
                    "bars_held": t["bars"], "regime": None, "mult": 1.0, "low": q * t["mae_pm"]})
    return out


# ================================================================================================ funded (after a pass)
FUNDED = {"25k": {"mll": 1000.0, "lock": 100.0, "dll": 600.0, "buffer": 1100.0, "pay_min": 250.0, "pay_max": 1000.0, "split": 0.8,
                  "cons": 0.5, "cycle_days": 2, "first_wait": 2, "max_payouts": 5, "maxq": 20},
          "50k": {"mll": 2000.0, "lock": 100.0, "dll": 1000.0, "buffer": 2100.0, "pay_min": 500.0, "pay_max": 2000.0, "split": 0.8,
                  "cons": 0.5, "cycle_days": 2, "first_wait": 2, "max_payouts": 5, "maxq": 40}}


def run_funded(days, by, plan, f, cap, stuck):
    """MFFU Builder sim-funded account (research/lit/mffu_rules.json limits, as tools/second_account_b.run_funded): EOD trailing
    max loss to start + $100, payouts of bal - buffer ($min..$max, 80%) after 2 traded days a cycle and the 50% best-day rule,
    5 payouts. Size = f x room (cap, soft daily loss left). Returns $ to the owner, payouts, lost / stuck day."""
    F = FUNDED[plan]
    P = {"dll": F["dll"], "maxq": F["maxq"]}
    bal = peak = 0.0
    floor = -F["mll"]
    paid, n_pay, last_bal, cyc = 0.0, 0, 0.0, []
    for k, d in enumerate(days):
        dp = 0.0
        traded = False
        for t in by.get(d, ()):
            room = bal + dp - floor
            q = _qty(t, room, dp, P, f, cap)
            if q <= 0:
                continue
            if bal + dp + q * t["mae_pm"] <= floor:
                return {"paid": paid, "n": n_pay, "lost": k + 1}
            dp += q * t["pnl_pm"]; traded = True
            if dp <= -F["dll"]:
                break
        bal += dp
        if bal <= floor:
            return {"paid": paid, "n": n_pay, "lost": k + 1}
        peak = max(peak, bal)
        floor = min(max(floor, peak - F["mll"]), F["lock"])
        if bal - floor < stuck:
            return {"paid": paid, "n": n_pay, "lost": None, "stuck": k + 1}
        if traded:
            cyc.append(dp)
        if k + 1 < F["first_wait"] or len(cyc) < F["cycle_days"]:
            continue
        prof = bal - last_bal
        if prof <= 0 or max(cyc) > F["cons"] * prof:
            continue
        amt = min(bal - F["buffer"], F["pay_max"])
        if amt < F["pay_min"]:
            continue
        paid += amt * F["split"]; n_pay += 1; bal -= amt; last_bal, cyc = bal, []
        if n_pay >= F["max_payouts"]:
            break
    return {"paid": paid, "n": n_pay, "lost": None}


def funded_score(T, S, plan="25k", f=0.3, cap=300.0, horizon=63, step=3):
    by = collections.defaultdict(list)
    for t in T:
        by[t["day"]].append(t)
    stuck = 2.0 * float(np.median([t["risk_pm"] for t in T])) if T else 60.0
    starts = [i for i in range(0, len(S), step) if i + horizon <= len(S)]
    if not starts:      # short span (2026 halves): every start, the account runs to the end of the span (scaled per month)
        starts = list(range(0, max(1, len(S) - 21), step))
    R = [(run_funded(S[i:i + horizon], by, plan, f, cap, stuck), min(horizon, len(S) - i)) for i in starts]
    if not R:
        return {}
    pm = [r["paid"] / (n / 21.0) for r, n in R]
    return {"fund_pm": round(float(np.mean(pm))), "fund_pay_pm": round(float(np.mean([r["n"] / (n / 21.0) for r, n in R])), 2),
            "fund_lost": round(100.0 * sum(1 for r, _ in R if r["lost"]) / len(R), 1),
            "fund_stuck": round(100.0 * sum(1 for r, _ in R if r.get("stuck")) / len(R), 1), "fund_starts": len(R)}
