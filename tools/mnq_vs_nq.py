"""MNQ feed vs NQ backtest for LIT (2026-10-26, research, read-only; follows A1 audit section 6).

LIT is tuned and backtested on TradingView CME NQ1! bars (data/NQ_5m.csv, data/NQ_1m.csv). The PC bot decides on the
NinjaTrader MNQ chart's bars (LE_BarFeed). This measures how much that changes, on every MNQ bar there is:
  * NinjaTrader MNQ 5m / 1m: the PC's own bars, collected from the `heartbeat` branch's history (tools/hb_bars.py ->
    research/feed/nt_mnq_*.csv.gz; 5m from 2026-09-17 18:00 ET, 1m from 2026-10-18 18:00 ET);
  * TradingView CME MNQ1! 5m: data/tv_mnq_5m_2026-10-16.csv (2026-08-23 18:00 -> 2026-10-16 07:10 ET; before the 09-14 roll
    on NQU26 prices: + the repo's roll gap, as merge_basis would).
Parts:
  1. bars: NinjaTrader MNQ vs NQ1!, TradingView MNQ1! vs NQ1!, NinjaTrader MNQ vs TradingView MNQ1! (OHLC differences,
     overnight vs RTH), NinjaTrader 1m -> 5m rebuild (the live 1m rule), bars NinjaTrader revised between pushes;
  2. LIT, the live loop (engine/lit_live.run at each session's close, live_model.json "lit"), on each feed over the same
     sessions: NQ1! only vs the live merge (NQ1! history + MNQ bars after their first bar). Execution on 5m bars on both
     sides (there are no MNQ 1m bars on any session NQ_1m.csv covers); the NQ 1m-executed replay of the same days is the
     reference (what the backtest books there);
  3. --noise N: the whole 2026 backtest (1m execution) on NQ bars with MNQ-sized noise: each 5m bar gets one (open, high,
     low, close) difference vector drawn from the measured NinjaTrader-MNQ-minus-NQ bars of the same session part, and
     its 1m bars are moved so they rebuild the new 5m bar (only the 1m extremes / first open / last close move: a lower
     bound on the 1m-level scatter). N draws -> the spread of trades and $ that MNQ-sized tick noise causes.

    python tools/hb_bars.py                      # refresh the NinjaTrader bars from the heartbeat history (needs gh)
    python -X utf8 tools/mnq_vs_nq.py            # parts 1-2 (~3 min) -> research/feed/mnq_vs_nq.json + _trades.csv
    python -X utf8 tools/mnq_vs_nq.py --noise 10 # + part 3 (~2 min a draw)
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import lit, lit_live, pcbars  # noqa: E402
from engine.data import from_frame, load, load_ltf  # noqa: E402
from tools import hb_bars  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "feed")
SIGF = ("limit_px", "stop_px", "target_px", "risk_pts")
PX = ("open", "high", "low", "close")


def et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def tdate(t) -> str:
    return str(lit_live.trading_date(int(t)))


def day_close(d: str) -> int:
    return int(dt.datetime.combine(dt.date.fromisoformat(d), dt.time(17, 0), ET).timestamp())


def part(t) -> str:
    """Session part of a bar (ET): rth 09:30-16:00, else overnight."""
    e = et(t)
    m = e.hour * 60 + e.minute
    return "rth" if 570 <= m < 960 else "overnight"


# ------------------------------------------------------------------------------------------------ data
def nq5():
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    return pcbars.tidy(lit_live._clean5(df))


def tv_mnq5():
    mq = pd.read_csv(os.path.join(ROOT, "data", "tv_mnq_5m_2026-10-16.csv"))
    mq.columns = [c.strip().lower() for c in mq.columns]
    mq = pcbars.tidy(mq[["time", "open", "high", "low", "close", "volume"]])
    roll = json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json")))["rolls"][-1]
    pre = mq["time"] < roll["switch_t"]
    for c in PX:
        mq.loc[pre, c] = mq.loc[pre, c] + roll["gap"]          # onto the repo's back-adjusted NQZ26 basis
    return mq.iloc[:-1].reset_index(drop=True), roll            # the last bar (10-16 07:10) is partial (volume 154)


def hybrid(base, parts):
    """base before parts[0] starts, then each part from its first bar until the next part's first bar (the live merge:
    NinjaTrader's bars win wherever they exist)."""
    out = [base[base["time"] < int(parts[0]["time"].min())]]
    for i, p in enumerate(parts):
        hi = int(parts[i + 1]["time"].min()) if i + 1 < len(parts) else None
        out.append(p if hi is None else p[p["time"] < hi])
    return pcbars.tidy(pd.concat(out))


def sessions_between(df, t0, t1):
    """Trading dates whose whole session lies inside [t0, t1] and that have bars in df."""
    days = sorted({tdate(t) for t in df["time"].values if t0 <= t <= t1})
    first = tdate(t0) if et(t0).hour != 18 else None              # a span starting mid-session drops that session
    return [d for d in days if d != first and day_close(d) <= t1 + 300]


# ------------------------------------------------------------------------------------------------ 1. bars
def bar_diff(a, b, la, lb):
    m = a.merge(b, on="time", suffixes=("_a", "_b"))
    out = {"pair": f"{la} minus {lb}", "bars": int(len(m)),
           "span": [f"{et(m['time'].min()):%Y-%m-%d %H:%M}", f"{et(m['time'].max()):%Y-%m-%d %H:%M}"] if len(m) else None}
    if not len(m):
        return out
    d_all = {c: (m[c + "_a"] - m[c + "_b"]).to_numpy() for c in PX}
    med = float(np.median(d_all["close"]))
    out["median_close_offset"] = med
    prt = np.array([part(t) for t in m["time"].values])
    for c in PX:
        d = d_all[c]
        row = {"exact_pct": round(float((np.abs(d) < 1e-9).mean() * 100), 1),
               "within_1tick_pct": round(float((np.abs(d) <= 0.25 + 1e-9).mean() * 100), 1),
               "within_1pt_pct": round(float((np.abs(d) <= 1.0 + 1e-9).mean() * 100), 1),
               "p1": float(np.percentile(d, 1)), "p99": float(np.percentile(d, 99)), "max_abs": float(np.abs(d).max()),
               "mean": round(float(d.mean()), 3)}
        for p_ in ("overnight", "rth"):
            dd = d[prt == p_]
            if len(dd):
                row[f"{p_}_within_1tick_pct"] = round(float((np.abs(dd) <= 0.25 + 1e-9).mean() * 100), 1)
        out[c] = row
    rng = (m["high_a"] - m["low_a"]) - (m["high_b"] - m["low_b"])
    out["range_a_minus_b_mean"] = round(float(rng.mean()), 3)
    out["wick_beyond_5pt"] = int(((m["high_a"] - m["high_b"]) > 5).sum() + ((m["low_b"] - m["low_a"]) > 5).sum())
    out["all_four_exact_pct"] = round(float(np.mean(np.all([np.abs(d_all[c]) < 1e-9 for c in PX], axis=0)) * 100), 1)
    out["shift_merge_basis"] = pcbars.basis_shift(b, a)
    return out


def rebuild_1m(df1, df5):
    """The live 1m rule on NinjaTrader's own bars: of the 5m bars the 1m file covers, how many have all five 1m bars and
    rebuild exactly / within lit_live.LIVE_TOL_1M."""
    g = df1.assign(b=df1["time"] // 300 * 300).groupby("b")
    agg = g.agg(n=("time", "size"), o=("open", "first"), h=("high", "max"), l=("low", "min"), c=("close", "last"))
    m = df5.merge(agg, left_on="time", right_index=True)
    full = m[m["n"] == 5]
    dd = np.abs(np.c_[full["o"] - full["open"], full["h"] - full["high"], full["l"] - full["low"], full["c"] - full["close"]])
    return {"bars_5m": int(len(m)), "with_5_minutes": int(len(full)), "missing_minute_pct": round(100 * (1 - len(full) / len(m)), 1) if len(m) else None,
            "exact_pct": round(float((dd.max(axis=1) < 1e-9).mean() * 100), 1) if len(full) else None,
            "within_tol_pct": round(float((dd.max(axis=1) <= lit_live.LIVE_TOL_1M + 1e-9).mean() * 100), 1) if len(full) else None}


# ------------------------------------------------------------------------------------------------ 2. LIT replays
def replay(df5, days, P, b1=None):
    """engine/lit_live.run at each session's close on the bars closed by then: {day: (signals, trades)}."""
    T = df5["time"].to_numpy()
    out = {}
    for d in days:
        now = day_close(d)
        cut = df5.iloc[:int(np.searchsorted(T + 300, now, side="right"))]
        one = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right"))) if b1 is not None else None
        keep = {}
        res = lit_live.run(cut, P, one_min=one, now=now, keep=keep)
        sig = [s for s in keep["R"]["signals"] if s["day"] == d]
        tr = [t for t in res["trades"] if t["day"] == d]
        out[d] = (sig, tr)
    return out


def stats(trades, n_sess):
    p = np.array([t["pnl"] for t in trades] or [0.0])
    gl = -p[p < 0].sum()
    return {"trades": len(trades), "per_week": round(len(trades) / (n_sess / 5), 2) if n_sess else None,
            "win_pct": round(100 * float((p > 0).mean()), 1) if trades else None,
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum()), 2),
            "per_month": round(float(p.sum()) / n_sess * 21, 0) if n_sess else None}


def tkey(t):
    return (int(t["entry_t"]), int(t["dir"]))


def compare(ra, rb, la, lb, days):
    sig = collections.Counter()
    sig_rows, trows = [], []
    dpx = {f: [] for f in SIGF}
    for d in days:
        sa = {(s["t"], s["dir"]): s for s in ra[d][0]}
        sb = {(s["t"], s["dir"]): s for s in rb[d][0]}
        for k in sorted(set(sa) | set(sb)):
            a, b = sa.get(k), sb.get(k)
            if a and b:
                diff = {f: round(float(b[f]) - float(a[f]), 2) for f in SIGF if abs(float(b[f]) - float(a[f])) > 1e-9}
                for f in SIGF:
                    dpx[f].append(abs(float(b[f]) - float(a[f])))
                kind = "same" if not diff else "same setup, prices differ"
            else:
                diff, kind = {}, f"{la} only" if a else f"{lb} only"
            sig[kind] += 1
            sig_rows.append({"day": d, "t": f"{et(k[0]):%H:%M}", "dir": k[1], "kind": kind, "diff": diff})
        ta = {tkey(t): t for t in ra[d][1]}
        tb = {tkey(t): t for t in rb[d][1]}
        if not ta and not tb:
            continue
        a = next(iter(ta.values()), None)
        b = next(iter(tb.values()), None)
        same_entry = bool(a and b and tkey(a) == tkey(b))
        kind = ("same trade" if same_entry and a["exit_reason"] == b["exit_reason"] and a["qty"] == b["qty"] else
                "same entry, exit or size differs" if same_entry else
                "different entry" if a and b else f"{la} only" if a else f"{lb} only")
        trows.append({"day": d, "kind": kind,
                      la: a and {"t": f"{et(a['entry_t']):%H:%M}", "dir": a["dir"], "entry": a["entry"], "stop": a["stop"],
                                 "qty": a["qty"], "exit": a["exit_reason"], "usd": round(a["pnl"], 2)},
                      lb: b and {"t": f"{et(b['entry_t']):%H:%M}", "dir": b["dir"], "entry": b["entry"], "stop": b["stop"],
                                 "qty": b["qty"], "exit": b["exit_reason"], "usd": round(b["pnl"], 2)},
                      "usd_diff": round((b["pnl"] if b else 0.0) - (a["pnl"] if a else 0.0), 2)})
    n = len(days)
    TA = [t for d in days for t in ra[d][1]]
    TB = [t for d in days for t in rb[d][1]]
    union = sum(sig.values())
    one_only = sig[f"{la} only"] + sig[f"{lb} only"]
    tk = collections.Counter(r["kind"] for r in trows)
    return {"a": la, "b": lb, "sessions": n, "first": days[0], "last": days[-1],
            "signals": dict(sig), "signals_union": union,
            "signals_one_feed_only_pct": round(100 * one_only / union, 1) if union else None,
            "signals_changed_pct": round(100 * (union - sig["same"]) / union, 1) if union else None,
            "same_setup_price_diff_median": {f: round(float(np.median(v)), 2) for f, v in dpx.items() if v},
            "same_setup_price_diff_p90": {f: round(float(np.percentile(v, 90)), 2) for f, v in dpx.items() if v},
            "trade_days": len(trows), "trade_kinds": dict(tk),
            "trade_days_differ_pct": round(100 * (len(trows) - tk["same trade"]) / len(trows), 1) if trows else None,
            "same_trade_usd_abs_diff": round(sum(abs(r["usd_diff"]) for r in trows if r["kind"] == "same trade"), 2),
            la: stats(TA, n), lb: stats(TB, n),
            "usd_diff": round(sum(t["pnl"] for t in TB) - sum(t["pnl"] for t in TA), 2),
            "usd_diff_per_month": round((sum(t["pnl"] for t in TB) - sum(t["pnl"] for t in TA)) / n * 21, 0) if n else None,
            "signal_rows": sig_rows, "trade_rows": trows}


# ------------------------------------------------------------------------------------------------ 3. noise study
def noise_vectors(a, b):
    """(part -> array of (do, dh, dl, dc)) of bars a minus b."""
    m = a.merge(b, on="time", suffixes=("_a", "_b"))
    v = np.c_[[m[c + "_a"] - m[c + "_b"] for c in PX]].T
    prt = np.array([part(t) for t in m["time"].values])
    return {p_: v[prt == p_] for p_ in ("overnight", "rth")}


def perturb(df5, df1, vec, rng):
    """df5 + one drawn MNQ-minus-NQ vector per bar (by session part), and df1 moved so it rebuilds every new 5m bar
    (windows without exactly five 1m bars: 1m left alone, the backtest runs those days on 5m anyway)."""
    df5 = df5.copy()
    prt = np.array([part(t) for t in df5["time"].values])
    dv = np.zeros((len(df5), 4))
    for p_ in ("overnight", "rth"):
        ix = np.flatnonzero(prt == p_)
        dv[ix] = vec[p_][rng.integers(0, len(vec[p_]), len(ix))]
    o = df5["open"].to_numpy() + dv[:, 0]
    h = df5["high"].to_numpy() + dv[:, 1]
    lo = df5["low"].to_numpy() + dv[:, 2]
    c = df5["close"].to_numpy() + dv[:, 3]
    h = np.maximum.reduce([h, o, c])
    lo = np.minimum.reduce([lo, o, c])
    df5["open"], df5["high"], df5["low"], df5["close"] = o, h, lo, c
    if df1 is None:
        return df5, None
    d1 = df1.copy()
    w = d1["time"].to_numpy() // 300 * 300
    j = np.searchsorted(df5["time"].to_numpy(), w)
    j = np.minimum(j, len(df5) - 1)
    ok = df5["time"].to_numpy()[j] == w
    cnt = pd.Series(w).map(pd.Series(w).value_counts()).to_numpy()
    ok &= cnt == 5
    O1, H1, L1, C1 = (d1[c_].to_numpy().copy() for c_ in PX)
    first = np.r_[True, w[1:] != w[:-1]]
    last = np.r_[w[1:] != w[:-1], True]
    jo = j[ok]
    H5, L5, O5, C5 = h[jo], lo[jo], o[jo], c[jo]
    idx = np.flatnonzero(ok)
    for A in (O1, H1, L1, C1):                           # every 1m price inside the new 5m range
        A[idx] = np.clip(A[idx], L5, H5)
    # the bar that held the old extreme carries the new one
    g = pd.DataFrame({"w": w[idx], "h": d1["high"].to_numpy()[idx], "l": d1["low"].to_numpy()[idx], "i": idx})
    ih = g.loc[g.groupby("w")["h"].idxmax(), "i"].to_numpy()
    il = g.loc[g.groupby("w")["l"].idxmin(), "i"].to_numpy()
    H1[ih] = h[j[ih]]
    L1[il] = lo[j[il]]
    O1[idx[first[idx]]] = O5[first[idx]]                 # the window's open / close are the new 5m bar's
    C1[idx[last[idx]]] = C5[last[idx]]
    H1[idx] = np.maximum.reduce([H1[idx], O1[idx], C1[idx]])    # inside the new 5m range, so the window still rebuilds
    L1[idx] = np.minimum.reduce([L1[idx], O1[idx], C1[idx]])
    d1["open"], d1["high"], d1["low"], d1["close"] = O1, H1, L1, C1
    return df5, d1


def backtest_2026(df5, df1, P):
    """engine/lit.py run_x on 2026 (1m execution, the research 1m rule) on the given frames."""
    from tools import lit_final as F
    P = {**lit.DEFAULTS, **P}
    M = lit.Market(bars=from_frame("NQ", "5m", df5), extra_boxes=P.get("extra_boxes") or [])
    C = lit.candidates(M, ref=P["ref"])
    B1 = None
    if df1 is not None and P["tf"] == "1m":
        B1 = lit.bars_1m(M, src=from_frame("NQ", "1m", df1))
    sess = [d for d in F.SESS if d >= "2026-01-01"]
    return lit.run_x(M, C, P, sess, B1=B1, B5=lit.bars_5m(M)), sess


def noise_study(n, P, vec, seed=7):
    t0 = time.time()
    lo = int(dt.datetime(2025, 11, 1, 18, 0, tzinfo=ET).timestamp())
    df5 = pcbars.tidy(pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv")))
    df5 = df5[df5["time"] >= lo].reset_index(drop=True)
    df5 = df5[~((df5["high"] == df5["low"]) & (df5["volume"] <= 0))].reset_index(drop=True)
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    df1 = pd.DataFrame({"time": b1.t, "open": b1.o, "high": b1.h, "low": b1.l, "close": b1.c, "volume": 0.0})
    df1 = df1[df1["time"] >= lo].reset_index(drop=True)
    base, sess = backtest_2026(df5, df1, P)
    half = lambda T, a, z: [t for t in T if a <= t["day"] <= z]       # noqa: E731
    H = {"2026": ("2026-01-01", "2026-12-31"), "H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31")}
    ns = {k: len([d for d in sess if a <= d <= z]) for k, (a, z) in H.items()}

    from tools import lit_final as F
    EV = ("wk2", "dd", "p10", "f10", "dec10", "pass_med", "p20", "f20")

    def summ(T):
        """stats + the MFFU 50K eval speed at the LIT size rule (tools/lit_final.score: p10 / f10 = pass / fail within 10
        sessions, dec10, pass_med, p20 / f20 within a month, % weeks with 2+ trades, max DD)."""
        sc = F.score([t for t in T if t["day"] >= "2026-01-01"], spans=tuple(H))
        return {k: {**stats(half(T, a, z), ns[k]), **{e: sc[k].get(e) for e in EV}} for k, (a, z) in H.items()}
    bk = {tkey(t): t for t in base}
    out = {"base": summ(base), "draws": [], "sessions": ns}
    rng = np.random.default_rng(seed)
    kept = []                                            # every draw's trades (the median draw is stored as a run)
    for i in range(n):
        p5, p1 = perturb(df5, df1, vec, rng)
        T, _ = backtest_2026(p5, p1, P)
        kept.append(T)
        tk = {tkey(t): t for t in T}
        same = [k for k in tk if k in bk]
        same_x = sum(1 for k in same if tk[k]["exit"] == bk[k]["exit"] and abs(tk[k]["pnl"] - bk[k]["pnl"]) < 0.5)
        days_b = {t["day"]: t for t in base}
        days_t = {t["day"]: t for t in T}
        dd = set(days_b) | set(days_t)
        diff_days = sum(1 for d in dd if not (d in days_b and d in days_t and tkey(days_b[d]) == tkey(days_t[d])))
        out["draws"].append({"draw": i, **{k: v for k, v in summ(T).items()}, "trades_same_entry": len(same),
                             "trades_same_entry_exit_usd": same_x, "trade_days_union": len(dd),
                             "trade_days_entry_differs": diff_days})
        print(f"  noise draw {i}: 2026 {out['draws'][-1]['2026']['trades']} trades net {out['draws'][-1]['2026']['net']:,.0f}"
              f" H2 {out['draws'][-1]['H2']['net']:,.0f} | same entry {len(same)}/{len(base)} | {time.time() - t0:.0f}s", flush=True)
    D = out["draws"]
    if D:
        for k in H:
            nets = np.array([x[k]["net"] for x in D])
            out[f"{k}_net"] = {"base": out["base"][k]["net"], "median": round(float(np.median(nets))),
                               "p10": round(float(np.percentile(nets, 10))), "p90": round(float(np.percentile(nets, 90))),
                               "min": round(float(nets.min())), "max": round(float(nets.max())),
                               "median_diff_per_month": round(float(np.median(nets) - out["base"][k]["net"]) / ns[k] * 21),
                               "below_base_pct": round(100 * float(np.mean(nets < out["base"][k]["net"])))}
            out[f"{k}_median"] = {e: (round(float(np.median([x[k][e] for x in D if x[k].get(e) is not None])), 2)
                                      if any(x[k].get(e) is not None for x in D) else None)
                                  for e in ("trades", "per_week", "pf", "per_month") + EV}
        out["entry_differs_days_pct_median"] = round(float(np.median([100 * x["trade_days_entry_differs"] / x["trade_days_union"] for x in D])), 1)
        out["same_trade_pct_median"] = round(float(np.median([100 * x["trades_same_entry_exit_usd"] / max(1, len(base)) for x in D])), 1)
        nets = [x["2026"]["net"] for x in D]
        out["median_draw"] = int(np.argsort(nets)[len(nets) // 2])
        out["_trades_median"] = kept[out["median_draw"]]
        out["_sess"] = sess
    out["seconds"] = round(time.time() - t0)
    return out


def save_runs(rep, live_trades):
    """research/runs (tools/runlib.py, status info): the median MNQ-noise draw of the 2026 backtest, and the live-merge
    MNQ feed replay of Aug 24 - Oct 16 (5m execution) next to the NQ replay of the same sessions."""
    from tools import runlib as rl
    nz = (rep.get("noise") or {}).get("mnq")
    W = "research/writeups/mnq-vs-nq-feed.md"
    if nz and nz.get("_trades_median"):
        T = nz["_trades_median"]
        S = rl.score(T, nz["_sess"])
        n = nz["2026_net"]
        rl.save("lit_feed_mnq_noise", "LIT 2026 on NQ bars with MNQ-sized tick noise (median of "
                f"{len(nz['draws'])} draws)", "other", "How much of LIT's 2026 result depends on NQ1!'s exact ticks (the live "
                "bot decides on MNQ bars)?", params={"noise": "NinjaTrader MNQ minus NQ1! 5m vectors by session part", "seed": 7},
                trades=T, scored=S, status="info", writeup=W,
                verdict=(f"2026 median ${n['median']:,} (p10 ${n['p10']:,} / p90 ${n['p90']:,}) vs ${n['base']:,} on NQ1!; "
                         f"H2 median ${nz['H2_net']['median']:,} vs ${nz['H2_net']['base']:,}"),
                notes="tools/mnq_vs_nq.py --noise; research/feed/mnq_vs_nq.json", tags=["feed", "mnq"])
    for rid, lab, T, days in live_trades:
        if T:
            rl.save(rid, lab, "other", "LIT on the MNQ feed vs NQ1!, the same sessions (5m execution)", trades=T,
                    scored=rl.score(T, days), status="info", writeup=W,
                    notes="tools/mnq_vs_nq.py; research/feed/mnq_vs_nq.json", tags=["feed", "mnq"])


# ------------------------------------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--noise", type=int, default=0, help="noise draws on the whole 2026 backtest (part 3)")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--save-runs", action="store_true", help="store the runs in research/runs (tools/runlib.py)")
    a = ap.parse_args(argv)
    t0 = time.time()
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    NQ = nq5()
    TV, roll = tv_mnq5()
    NT5, NT1 = hb_bars.load("5m"), hb_bars.load("1m")
    if not len(NT5):
        print("no NinjaTrader bars: run python tools/hb_bars.py first")
        return 1
    rep = {"label": "MNQ feed vs NQ backtest (LIT)", "made": dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"),
           "data": {"nq_5m": "data/NQ_5m.csv (TradingView CME NQ1!, back-adjusted to NQZ26)",
                    "tv_mnq_5m": f"data/tv_mnq_5m_2026-10-16.csv (TradingView CME MNQ1!; + {roll['gap']} before "
                                 f"{roll['switch_et']})",
                    "nt_mnq_5m": f"research/feed/nt_mnq_5m.csv.gz (NinjaTrader MNQ 12-26, PC heartbeat; {len(NT5)} bars "
                                 f"{et(NT5['time'].min()):%Y-%m-%d %H:%M} -> {et(NT5['time'].max()):%Y-%m-%d %H:%M} ET)",
                    "nt_mnq_1m": f"research/feed/nt_mnq_1m.csv.gz ({len(NT1)} bars "
                                 f"{et(NT1['time'].min()):%Y-%m-%d %H:%M} -> {et(NT1['time'].max()):%Y-%m-%d %H:%M} ET)",
                    "nq_1m_last": f"{et(load_ltf('NQ', load('NQ', '5m'))[0].t[-1]):%Y-%m-%d %H:%M} ET"}}
    try:
        rep["nt_revisions"] = {tf: json.load(open(os.path.join(OUT, "nt_mnq_meta.json")))["files"][tf]["revised_between_commits"]
                               for tf in ("1m", "5m")}
    except Exception:
        pass
    # ---- 1. bars
    rep["bars"] = [bar_diff(NT5, NQ, "NinjaTrader MNQ", "NQ1!"), bar_diff(TV, NQ, "TradingView MNQ1!", "NQ1!"),
                   bar_diff(NT5, TV, "NinjaTrader MNQ", "TradingView MNQ1!")]
    rep["nt_1m_rebuild"] = rebuild_1m(NT1, NT5)
    for b in rep["bars"]:
        print(f"{b['pair']}: {b['bars']} bars, high within 1 tick {b['high']['within_1tick_pct']}%, close {b['close']['within_1tick_pct']}%"
              f", all four exact {b['all_four_exact_pct']}%", flush=True)
    print("NinjaTrader 1m -> 5m:", rep["nt_1m_rebuild"], flush=True)
    # ---- 2. LIT on each feed
    P5 = {**P, "tf": "5m"}
    lo = int(dt.datetime(2026, 6, 1, 18, 0, tzinfo=ET).timestamp())
    base = NQ[NQ["time"] >= lo].reset_index(drop=True)
    nq_end = int(NQ["time"].max())
    feeds = {"mnq_live": hybrid(base, [TV, NT5]), "mnq_tv": hybrid(base, [TV]), "mnq_nt": hybrid(base, [NT5])}
    days = {"mnq_live": sessions_between(TV, int(TV["time"].min()), nq_end),
            "mnq_tv": sessions_between(TV, int(TV["time"].min()), int(TV["time"].max())),
            "mnq_nt": sessions_between(NT5, int(NT5["time"].min()), nq_end)}
    alld = sorted(set().union(*days.values()))
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    b1 = b1.slice(int(np.searchsorted(b1.t, int(base["time"].min()))), len(b1))
    print(f"replaying {len(alld)} sessions {alld[0]} .. {alld[-1]} on NQ (5m and 1m execution) ...", flush=True)
    r_nq5 = replay(base, alld, P5)
    r_nq1 = replay(base, alld, P, b1=b1)
    rep["lit"] = {}
    rows = []
    as_run = lambda T: [{**t, "r": t.get("pnl_r"), "exit": t.get("exit_reason"),                # noqa: E731
                         "half": float(t.get("size_mult") or 1.0) < 1.0} for t in T]
    live_runs = []
    for nm, fr in feeds.items():
        r = replay(fr, days[nm], P5)
        c = compare(r_nq5, r, "nq", nm, days[nm])
        if nm == "mnq_live":
            live_runs = [("lit_feed_mnq_live_5m", "LIT on the live MNQ feed (TradingView MNQ1! then NinjaTrader MNQ), Aug 24 - "
                          "Oct 16 2026, 5m execution", as_run([t for d in days[nm] for t in r[d][1]]), days[nm]),
                         ("lit_feed_nq_same_5m", "LIT on NQ1!, the same sessions (Aug 24 - Oct 16 2026), 5m execution",
                          as_run([t for d in days[nm] for t in r_nq5[d][1]]), days[nm])]
        c["nq_1m_exec"] = stats([t for d in days[nm] for t in r_nq1[d][1]], len(days[nm]))
        rep["lit"][nm] = c
        rows += [{"feed": nm, **{k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in x.items()}} for x in c["trade_rows"]]
        print(f"{nm}: {c['sessions']} sessions {c['first']}..{c['last']} | signals {c['signals']} ({c['signals_one_feed_only_pct']}% "
              f"one feed only) | trade days {c['trade_days']} {c['trade_kinds']} | net nq {c['nq']['net']:,.0f} vs {nm} "
              f"{c[nm]['net']:,.0f} ({c['usd_diff_per_month']:+,.0f}/mo) | NQ 1m exec {c['nq_1m_exec']['net']:,.0f}", flush=True)
    # ---- 3. noise
    if a.noise:
        # three noise sets: the measured MNQ-minus-NQ bars; the same vectors negated (NQ-minus-MNQ: the same size of noise,
        # the range bias the other way: narrower bars); NinjaTrader-MNQ-minus-TradingView-MNQ1! (two vendors' bars of one
        # contract: the smallest difference a data source makes)
        m = noise_vectors(NT5, NQ)
        sets = {"mnq": m, "mnq_negated": {k: -v for k, v in m.items()}, "vendor": noise_vectors(NT5, TV)}
        rep["noise"] = {}
        for nm, vec in sets.items():
            print(f"noise study '{nm}': {a.noise} draws on the 2026 backtest (1m execution) ...", flush=True)
            rep["noise"][nm] = {"vectors": {k: int(len(v)) for k, v in vec.items()}, **noise_study(a.noise, P, vec)}
    if a.save_runs:
        save_runs(rep, live_runs)
        print("runs stored: lit_feed_mnq_noise, lit_feed_mnq_live_5m, lit_feed_nq_same_5m (research/runs)", flush=True)
    for nz in (rep.get("noise") or {}).values():
        nz.pop("_trades_median", None)
        nz.pop("_sess", None)
    rep["seconds"] = round(time.time() - t0)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "mnq_vs_nq.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, default=str)
    pd.DataFrame(rows).to_csv(os.path.join(a.out, "mnq_vs_nq_trades.csv"), index=False)
    print(f"-> {os.path.join(a.out, 'mnq_vs_nq.json')} ({rep['seconds']} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
