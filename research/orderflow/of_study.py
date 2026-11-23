"""Order-flow study (day-orderflow 2026-11-23). Rules fixed BEFORE the first run; see research/writeups/orderflow-2026-11-23.md.

We have NO tick / bid-ask / footprint data yet. Two modes:
  REAL   (data/ticks/*.parquet from engine/tickrec.py)  - delta = sum(size * aggressor side) per 5m bar, real footprint POC.
  PROXY  (5m OHLCV bars, 2021-10 .. 2026-11)           - delta ~ volume * CLV, CLV = (2*close - high - low) / (high - low).
         A bar-shape guess at delta, NOT order flow. It can reject an idea cheaply; it can never prove one.

The four setups (one meaning, both modes; d = +1 long, -1 short; LIT trades from tools/lit_losses.run() = the live LIT replay,
costs in; entry is at the OPEN of bar entry_i, so only bars < entry_i are used):
  S1 delta divergence at the LIT sweep: delta of the 3 bars ending at the sweep extreme (ext_i-2..ext_i) has the trade's sign
     (price made the new low but net buying, or the mirror) -> "div"; else "no div".
  S2 absorption at RTH session high / low (stand-alone, NQ 5m, 10:00-15:00 ET): the bar makes a new RTH high (low), volume >= 2x
     the mean of the prior 20 bars, delta against the push (proxy: CLV <= -0.2 at a high, >= +0.2 at a low). Fade at the next
     bar's open, stop 1 tick beyond the bar's extreme, target 2R, flat 15:55 ET, first signal of the day only. $500 risk per
     trade in micros (cap 40), $1.40 per micro round trip + 0.25 pt slippage each side.
  S3 stacked-imbalance continuation: needs bid x ask volume at each price (3+ stacked 300% diagonal imbalances). Bars cannot
     show it: NOT TESTED in proxy mode; in REAL mode it needs per-price bid/ask volume (footprint_levels) - coded below.
  S4 LIT confirmed vs refuted by delta: delta summed from the sweep extreme to the bar before entry (ext_i..entry_i-1) has the
     trade's sign -> "confirmed", else "refuted". The question: does skipping refuted trades raise net $ in all 3 spans?
Spans: 2021-25 (reference), 2026 H1 (Jan-Jun), 2026 H2 (Jul-Nov).

  python research/orderflow/of_study.py            -> research/orderflow/results.json + a printed table
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "orderflow", "results.json")
TICK, PV, COMM, SLIP = 0.25, 2.0, 1.40, 0.25
SPANS = [("2021-25", "2021-01-01", "2025-12-31"), ("2026 H1", "2026-01-01", "2026-06-30"), ("2026 H2", "2026-07-01", "2026-12-31")]


def proxy_delta(o, h, l, c, v):
    rng = h - l
    clv = np.where(rng > 0, (2 * c - h - l) / np.where(rng > 0, rng, 1), 0.0)
    return v * clv, clv


def stats(pnl, r=None, weeks=None):
    p = np.asarray(pnl, float)
    if not len(p):
        return {"n": 0}
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq).max())
    o = {"n": int(len(p)), "win%": round(100 * float((p > 0).mean()), 1), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
         "net$": round(float(p.sum())), "avg$": round(float(p.mean()), 1), "maxDD$": round(dd)}
    if r is not None:
        o["avgR"] = round(float(np.mean(r)), 3)
    if weeks:
        o["per_wk"] = round(len(p) / weeks, 2)
    return o


def span_of(day):
    for nm, a, b in SPANS:
        if a <= day <= b:
            return nm
    return None


def weeks(nm, days):
    ds = sorted(d for d in days if span_of(d) == nm)
    if not ds:
        return None
    return max(1.0, (pd.Timestamp(ds[-1]) - pd.Timestamp(ds[0])).days / 7)


# ------------------------------------------------------------------------------------------------ S1 + S4 on LIT trades
def lit_setups(delta_of_bar):
    from tools import lit_losses as L
    M, C, B1, B5 = L.base()
    T = L.run()
    rows = []
    for t in T:
        d, e, ei = t["dir"], t["ext_i"], t["entry_i"]
        s1 = float(np.sum(delta_of_bar(M, e - 2, e + 1)))
        s4 = float(np.sum(delta_of_bar(M, e, max(e + 1, ei))))
        rows.append({"day": t["day"], "pnl": t["pnl"], "r": t["r"], "div": s1 * d > 0, "conf": s4 * d > 0})
    days = [x["day"] for x in rows]
    res = {}
    for nm, _, _ in SPANS:
        R = [x for x in rows if span_of(x["day"]) == nm]
        w = weeks(nm, days)
        g = lambda f: stats([x["pnl"] for x in R if f(x)], [x["r"] for x in R if f(x)], w)  # noqa: E731
        res[nm] = {"all": g(lambda x: True),
                   "S1 div": g(lambda x: x["div"]), "S1 no div": g(lambda x: not x["div"]),
                   "S4 confirmed": g(lambda x: x["conf"]), "S4 refuted": g(lambda x: not x["conf"])}
    return res


# ------------------------------------------------------------------------------------------------ S2 stand-alone
def absorption(df, use_real=False):
    """df: 5m bars, columns time(open, unix s), open high low close volume [+ delta]."""
    t = pd.to_datetime(df.time, unit="s", utc=True).dt.tz_convert(ET)
    df = df.assign(day=t.dt.strftime("%Y-%m-%d").values, mod=(t.dt.hour * 60 + t.dt.minute).values).reset_index(drop=True)
    o, h, l, c, v = (df[k].values.astype(float) for k in ("open", "high", "low", "close", "volume"))
    if use_real:
        dl = df["delta"].values.astype(float)
        sig = np.where(v > 0, dl / np.maximum(v, 1), 0)          # delta share of volume
        th = 0.2
    else:
        _, sig = proxy_delta(o, h, l, c, v)
        th = 0.2
    vm = pd.Series(v).shift(1).rolling(20).mean().values
    trades = []
    for day, g in df.groupby("day", sort=True):
        idx = g.index[(g["mod"] >= 570) & (g["mod"] < 955)].values
        if len(idx) < 10:
            continue
        hi, lo = -np.inf, np.inf
        done = False
        for k in idx:
            mod = df.at[k, "mod"]
            newh, newl = h[k] > hi, l[k] < lo
            if not done and 600 <= mod < 900 and k + 1 <= idx[-1] and vm[k] > 0 and v[k] >= 2 * vm[k]:
                d = 0
                if newh and np.isfinite(hi) and sig[k] <= -th:
                    d = -1
                elif newl and np.isfinite(lo) and sig[k] >= th:
                    d = 1
                if d:
                    entry = o[k + 1] + SLIP * d
                    stop = (l[k] - TICK) if d == 1 else (h[k] + TICK)
                    risk = (entry - stop) * d
                    if risk > 0:
                        tgt = entry + 2 * risk * d
                        q = int(min(40, 500 // (risk * PV)))
                        if q >= 1:
                            px, kind = None, "EOD"
                            for j in idx[idx > k]:
                                if (d == 1 and l[j] <= stop) or (d == -1 and h[j] >= stop):
                                    px, kind = stop - SLIP * d, "STOP"; break
                                if (d == 1 and h[j] >= tgt) or (d == -1 and l[j] <= tgt):
                                    px, kind = tgt, "TGT"; break
                            if px is None:
                                px = c[idx[-1]] - SLIP * d
                            pnl = (px - entry) * d * PV * q - COMM * q
                            trades.append({"day": day, "dir": d, "pnl": round(pnl, 2), "r": (px - entry) * d / risk, "exit": kind})
                        done = True
            hi, lo = max(hi, h[k]), min(lo, l[k])
    days = [x["day"] for x in trades] or ["2021-01-01"]
    all_days = sorted(df.day.unique())
    res = {}
    for nm, _, _ in SPANS:
        R = [x for x in trades if span_of(x["day"]) == nm]
        res[nm] = stats([x["pnl"] for x in R], [x["r"] for x in R], weeks(nm, all_days))
    return res


# ------------------------------------------------------------------------------------------------ REAL-mode helpers
def footprint_levels(ticks, minutes=5):
    """bar x price -> bid volume (side -1) and ask volume (side +1): the input S3 needs."""
    tt = pd.to_datetime(ticks.t_ns, utc=True).dt.floor("%dmin" % minutes)
    x = ticks.assign(bar=tt.values)
    a = x[x.side > 0].groupby(["bar", "price"])["size"].sum().rename("ask_v")
    b = x[x.side < 0].groupby(["bar", "price"])["size"].sum().rename("bid_v")
    return pd.concat([a, b], axis=1).fillna(0).reset_index()


def stacked_imbalance(levels, ratio=3.0, stack=3):
    """+1 / -1 per bar when >= `stack` consecutive prices show ask_v(p) >= ratio * bid_v(p - 1 tick) (buy) or the mirror."""
    out = {}
    for bar, g in levels.groupby("bar"):
        g = g.set_index("price").sort_index()
        bidv = g.bid_v
        buy = sell = run_b = run_s = 0
        for p in g.index:
            below = bidv.get(p - TICK, 0)
            above_ask = g.ask_v.get(p + TICK, 0)
            run_b = run_b + 1 if g.at[p, "ask_v"] >= ratio * max(below, 1) else 0
            run_s = run_s + 1 if g.at[p, "bid_v"] >= ratio * max(above_ask, 1) else 0
            buy, sell = max(buy, run_b), max(sell, run_s)
        out[bar] = 1 if buy >= stack and sell < stack else (-1 if sell >= stack and buy < stack else 0)
    return out


def real_mode(days):
    """Same rules on recorded / imported ticks. Delta is matched to the LIT 5m bars by bar-open time (the tick files carry raw
    prices, the LIT bars are back-adjusted: delta and volume do not care, prices are only used inside the tick frame)."""
    from engine import tickrec
    fps, sis = [], {}
    for d in days:
        x = tickrec.read_day(d)
        if x is None:
            continue
        x = x[x.root == "NQ"]
        if x.empty:
            continue
        fps.append(tickrec.footprint(x, 5))
        sis.update(stacked_imbalance(footprint_levels(x, 5)))
    fp = pd.concat(fps).sort_index()
    fp = fp[~fp.index.duplicated()]
    dmap = {int(k.timestamp()): float(v) for k, v in fp.delta.items()}

    def real_bar(M, a, b):
        a = max(0, a)
        return np.array([dmap.get(int(t), np.nan) for t in M.t[a:b]])

    def lit_real():
        from tools import lit_losses as L
        M, C, B1, B5 = L.base()
        T = [t for t in L.run() if not np.isnan(np.sum(real_bar(M, t["ext_i"] - 2, max(t["ext_i"] + 1, t["entry_i"]))))]
        return T, M
    T, M = lit_real()
    rows = []
    for t in T:
        d, e, ei = t["dir"], t["ext_i"], t["entry_i"]
        rows.append({"day": t["day"], "pnl": t["pnl"], "r": t["r"],
                     "div": float(np.sum(real_bar(M, e - 2, e + 1))) * d > 0, "conf": float(np.sum(real_bar(M, e, max(e + 1, ei)))) * d > 0})
    res = {}
    alld = [x["day"] for x in rows]
    for nm, _, _ in SPANS:
        R = [x for x in rows if span_of(x["day"]) == nm]
        w = weeks(nm, alld)
        g = lambda f: stats([x["pnl"] for x in R if f(x)], [x["r"] for x in R if f(x)], w)  # noqa: E731
        res[nm] = {"all": g(lambda x: True), "S1 div": g(lambda x: x["div"]), "S1 no div": g(lambda x: not x["div"]),
                   "S4 confirmed": g(lambda x: x["conf"]), "S4 refuted": g(lambda x: not x["conf"])}
    bars = pd.DataFrame({"time": [int(k.timestamp()) for k in fp.index], "open": fp.open.values, "high": fp.high.values,
                         "low": fp.low.values, "close": fp.close.values, "volume": fp.volume.values, "delta": fp.delta.values})
    s3 = stacked_continuation(bars, sis)
    return {"LIT S1/S4 (real)": res, "S2 absorption (real)": absorption(bars, use_real=True), "S3 stacked imbalance (real)": s3}


def stacked_continuation(bars, sis):
    """S3: an RTH bar (10:00-15:00 ET) with a stacked imbalance (+1 / -1) that closes in its direction (close beyond open) ->
    enter that way at the next bar's open, stop 1 tick beyond the signal bar's far end, target 2R, flat 15:55, first per day."""
    t = pd.to_datetime(bars.time, unit="s", utc=True).dt.tz_convert(ET)
    b = bars.assign(day=t.dt.strftime("%Y-%m-%d").values, mod=(t.dt.hour * 60 + t.dt.minute).values,
                    si=[sis.get(pd.Timestamp(x, unit="s", tz="UTC"), 0) for x in bars.time]).reset_index(drop=True)
    trades = []
    for day, g in b.groupby("day"):
        idx = g.index[(g["mod"] >= 570) & (g["mod"] < 955)].values
        for k in idx:
            if not (600 <= b.at[k, "mod"] < 900) or k + 1 > idx[-1]:
                continue
            d = int(b.at[k, "si"])
            if d == 0 or (b.at[k, "close"] - b.at[k, "open"]) * d <= 0:
                continue
            entry = b.at[k + 1, "open"] + SLIP * d
            stop = (b.at[k, "low"] - TICK) if d == 1 else (b.at[k, "high"] + TICK)
            risk = (entry - stop) * d
            q = int(min(40, 500 // (risk * PV))) if risk > 0 else 0
            if q < 1:
                break
            tgt = entry + 2 * risk * d
            px = None
            for j in idx[idx > k]:
                if (d == 1 and b.at[j, "low"] <= stop) or (d == -1 and b.at[j, "high"] >= stop):
                    px = stop - SLIP * d; break
                if (d == 1 and b.at[j, "high"] >= tgt) or (d == -1 and b.at[j, "low"] <= tgt):
                    px = tgt; break
            if px is None:
                px = b.at[idx[-1], "close"] - SLIP * d
            trades.append({"day": day, "pnl": (px - entry) * d * PV * q - COMM * q, "r": (px - entry) * d / risk})
            break
    alld = sorted(b.day.unique())
    return {nm: stats([x["pnl"] for x in trades if span_of(x["day"]) == nm], [x["r"] for x in trades if span_of(x["day"]) == nm],
                      weeks(nm, alld)) for nm, _, _ in SPANS}


def main():
    from engine import tickrec
    have = tickrec.days_available()
    out = {"made": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "tick_days": len(have),
           "mode": "REAL" if len(have) >= 60 else "PROXY",
           "note": "PROXY = 5m bar-shape guess at delta (volume x close location). Not order flow; can reject, cannot prove."}
    out["tick_days_note"] = "%d tick days on disk; REAL mode needs >= 60" % len(have)
    bars = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    if out["mode"] == "REAL":
        out.update(real_mode(have))
    else:
        def pd_bar(M, a, b):
            a = max(0, a)
            dl, _ = proxy_delta(M.o[a:b], M.h[a:b], M.l[a:b], M.c[a:b], M.v[a:b])
            return dl
        out["LIT S1/S4 (proxy)"] = lit_setups(pd_bar)
        out["S2 absorption (proxy)"] = absorption(bars)
        out["S3 stacked imbalance"] = "NOT TESTED: needs bid x ask volume per price (tick data). Code ready: real_mode."
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    for k, v in out.items():
        if isinstance(v, dict):
            print("\n==", k)
            for sp, row in v.items():
                if isinstance(row, dict) and "n" not in row:
                    for g, s in row.items():
                        print("  %-8s %-13s %s" % (sp, g, s))
                else:
                    print("  %-8s %s" % (sp, row))
        else:
            print(k, ":", v)


if __name__ == "__main__":
    main()
