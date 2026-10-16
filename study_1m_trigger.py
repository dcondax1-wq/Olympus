"""Hybrid entry study: keep the 5m context (pools, sweeps, structure, targets) but confirm the trigger on the 1m close.

Part A - REAL 1m test (NQ only; the only true 1-minute NQ data we have):
  data/ltf/NQJ_1m.csv = the owner's TradingView CME_MINI_NQ1! 1m exports, RTH 2026-08-31 .. 2026-10-07 (27 sessions)
  + 2026-01-14/15 (no 5m context exists for January, so unusable). data/NQ_1m.csv contributes nothing: every
  5-minute-aligned row from 2026-08-24 on is a 5m bar written by a 5m import (data.load_ltf detects and drops them).
  NQ_5m.csv for that period is MNQ (TradingView 5m), which differs from NQ1! by ~0.3-0.4 pt per bar, so both arms run
  on ONE consistent base: NQ_5m with the prices of every RTH 5m bar that the 1m feed covers rebuilt from those 1m bars
  (volume left as is). Arm "5m trigger" = current engine; arm "1m trigger" = ifvg_tf "lower" with the 1m bars.
Part B - SYNTHETIC UPPER BOUND on all four periods (5m data only): every real 5m-trigger trade is re-priced with an
  earlier entry inside its trigger bar (bar open / body mid / one tick through the trigger level), same stop, same
  target, same exit price. It ignores the cost side (extra false triggers, earlier stop-outs inside the trigger bar,
  different exit management), so it is a ceiling on what earlier entries can add, never an estimate.

Run: python study_1m_trigger.py
"""
import datetime as dt
import os
import types
from multiprocessing import Pool

import numpy as np
import pandas as pd

from engine import backtest, data as edata
from engine.data import Bars, from_frame, load, load_ltf, resample
from engine.instruments import INSTRUMENTS
from engine.model import Engine

# ---- the CFD files were moved to data/_cfd_archive; resolve them there (read-only, nothing is moved)
ARCH = os.path.join(edata.DATA_DIR, "_cfd_archive")
_orig_load = edata.load


def _load(sym, tf):
    if not os.path.exists(os.path.join(edata.DATA_DIR, f"{sym}_{tf}.csv")) and os.path.exists(os.path.join(ARCH, f"{sym}_{tf}.csv")):
        keep, edata.DATA_DIR = edata.DATA_DIR, ARCH
        try:
            return _orig_load(sym, tf)
        finally:
            edata.DATA_DIR = keep
    return _orig_load(sym, tf)


backtest.load = _load
backtest.os = types.SimpleNamespace(path=types.SimpleNamespace(
    join=os.path.join, exists=lambda p: os.path.exists(p) or os.path.exists(os.path.join(ARCH, os.path.basename(p)))))

P = {"dd_aware": False, "daily_max_loss": 1e9}          # study_be convention (no drawdown-aware down-sizing)
SEGS = [("NQ fut 2026", "NQ", None, None), ("CFD Q4 2023", "NQX", None, "2023-12-31"),
        ("CFD 2024", "NQX", "2024-01-01", "2024-12-31"), ("CFD 2025", "NQX", "2025-01-01", "2025-12-31")]
SPEC = INSTRUMENTS["NQ"]


# ----------------------------------------------------------------------------------------- part A data
def consistent_nq():
    """NQ 5m base whose RTH bars covered by true 1m are rebuilt from those 1m bars, matching 1h, and the 1m bars."""
    base = load("NQ", "5m")
    ltf, src = load_ltf("NQ", base)
    m = pd.DataFrame({"t": ltf.t, "o": ltf.o, "h": ltf.h, "l": ltf.l, "c": ltf.c})
    m["b"] = m.t // 300 * 300
    g = m.groupby("b").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), n=("t", "size"))
    g = g[g.n == 5]
    df = pd.DataFrame({"time": base.t, "open": base.o, "high": base.h, "low": base.l, "close": base.c, "volume": base.v}).set_index("time")
    hit = df.index.isin(g.index)
    df.loc[hit, ["open", "high", "low", "close"]] = g.loc[df.index[hit], ["o", "h", "l", "c"]].values
    b2 = from_frame("NQ", "5m", df.reset_index())
    h1 = load("NQ", "1h")
    h1df = pd.DataFrame({"time": h1.t, "open": h1.o, "high": h1.h, "low": h1.l, "close": h1.c, "volume": h1.v}).set_index("time")
    r = resample(b2, "1h")
    rdf = pd.DataFrame({"time": r.t, "open": r.o, "high": r.h, "low": r.l, "close": r.c, "volume": r.v}).set_index("time")
    rdf = rdf[rdf.index >= int(g.index.min()) // 3600 * 3600]
    h1df = pd.concat([h1df[~h1df.index.isin(rdf.index)], rdf]).sort_index()
    days = sorted(set(ltf.date_str) & set(b2.date_str))
    return b2, from_frame("NQ", "1h", h1df.reset_index()), ltf, src, days, int(hit.sum())


def _day_of(t):
    return (dt.datetime.fromtimestamp(t, dt.timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo("America/New_York"))
            + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def job(name):
    if name in ("A5", "A1"):
        b2, h1, ltf, src, days, nrep = consistent_nq()
        partner = load("ES", "5m")
        prm = dict(P) if name == "A5" else {**P, "ifvg_tf": "lower"}
        eng = Engine(b2, htf=h1, partner=partner, params=prm, ltf=ltf if name == "A1" else None).run()
        res = eng.result()
        close5 = dict(zip(b2.t.tolist(), b2.c.tolist()))
        for t in res["trades"]:
            t["day"] = _day_of(t["entry_t"])
            lvl = t["zone"][1] if t["dir"] == 1 else t["zone"][0]
            t["level"] = lvl
            t["false_1m"] = bool(t.get("trigger_tf") == "1m" and (close5[t["signal_t"]] - lvl) * t["dir"] <= 0)
        cand = sum(1 for e in res["events"] if "(1m)" in e["text"] and e["type"] in ("skip", "news")) + \
            sum(1 for s in res["signals"] if s.get("tf") == "1m")
        return name, {"trades": res["trades"], "days": days, "ltf": res.get("ltf"), "src": src, "replaced": nrep,
                      "cand_1m": cand, "ndays_all": len(res["days"])}
    if name == "AR":         # default code path: backtest.run on the raw NQ_5m (MNQ) base -> many 5m fallbacks
        r = backtest.run("NQ", "5m", {**P, "ifvg_tf": "lower"}, light=True)
        return name, {"trades": r["trades"], "ltf": r.get("ltf")}
    sym = name[1:]
    r = backtest.run(sym, "5m", P, light=True)
    b = _load(sym, "5m")
    tix = {int(t): k for k, t in enumerate(b.t)}
    for t in r["trades"]:
        k = tix[int(t["signal_t"])]
        t["sig_o"], t["sig_c"] = float(b.o[k]), float(b.c[k])
    return name, {"trades": r["trades"], "days": [d["date"] for d in r["days"]]}


# ----------------------------------------------------------------------------------------- stats
def stats(tr, ndays):
    if not tr:
        return {"n": 0}
    pnl = np.array([t["pnl"] for t in tr])
    g, l = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    eq = np.cumsum(pnl)
    return {"n": len(tr), "wk": len(tr) / max(ndays / 5, 1e-9), "avg_r": float(np.mean([t["pnl_r"] for t in tr])),
            "net": float(pnl.sum()), "pf": float(g / l) if l else 99.0, "risk": float(np.mean([t["risk_pts"] for t in tr])),
            "win": float((pnl > 0).mean()), "dd": float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()),
            "false": sum(1 for t in tr if t.get("false_1m")), "false_lost": sum(1 for t in tr if t.get("false_1m") and t["pnl"] <= 0),
            "n1m": sum(1 for t in tr if t.get("trigger_tf") == "1m")}


def fmt(s):
    if not s.get("n"):
        return "  0 trades"
    return (f"{s['n']:3d}t {s['wk']:.1f}/wk  avgR {s['avg_r']:+.2f}  net ${s['net']:+7.0f}  PF {s['pf']:5.2f}  "
            f"risk {s['risk']:5.1f}pt  win {s['win'] * 100:3.0f}%  maxDD ${s['dd']:6.0f}  "
            f"1m-trig {s['n1m']:2d}  false {s['false']:2d} ({s['false_lost']} lost)")


def synth(tr):
    """Upper bound: same trades re-priced with an earlier entry in the trigger bar. R net of commission per micro."""
    tick, slip = SPEC["tick"], SPEC["tick"]
    cm = SPEC["micro_comm_rt"] / SPEC["micro_pv"]               # commission in points per micro round turn
    out = {k: [] for k in ("actual", "open", "mid", "level")}
    risk = {k: [] for k in out}
    for t in tr:
        d, e, stop = t["dir"], t["entry"], t["stop0"]
        q = sum(x["qty"] for x in t["exits"]) or 1
        xpx = sum(x["price"] * x["qty"] for x in t["exits"]) / q          # volume-weighted exit price
        cands = {"actual": e, "open": t["sig_o"] + d * slip, "mid": (t["sig_o"] + t["sig_c"]) / 2 + d * slip,
                 "level": t["level"] + d * (tick + slip)}
        for k, ep in cands.items():
            ep = e if (ep - e) * d > 0 else ep                            # never worse than the real 5m entry
            r_pts = (ep - stop) * d
            if r_pts < SPEC["min_stop"]:
                r_pts = SPEC["min_stop"]                                   # engine widens to the minimum stop
            out[k].append(((xpx - ep) * d - cm) / r_pts)
            risk[k].append(r_pts)
    res = {}
    for k in out:
        r = np.array(out[k])
        g, l = r[r > 0].sum(), -r[r < 0].sum()
        usd = sum(rr * t["risk_pts"] * sum(x["qty"] for x in t["exits"]) * SPEC["micro_pv"] for rr, t in zip(r, tr))
        res[k] = {"avg_r": float(r.mean()), "sum_r": float(r.sum()), "pf": float(g / l) if l else 99.0,
                  "risk": float(np.mean(risk[k])), "usd": float(usd)}
    return res


if __name__ == "__main__":
    with Pool(5) as pool:
        R = dict(pool.map(job, ["A5", "A1", "AR", "BNQ", "BNQX"]))

    # ------------------------------------------------------------------ part A
    a5, a1 = R["A5"], R["A1"]
    days = a5["days"]
    win = lambda tr, ds: [t for t in tr if t["day"] in ds]
    last7 = days[-7:]
    print("=" * 150)
    print("PART A - REAL 1m TEST, NQ, sessions with true 1-minute data:", f"{days[0]} .. {days[-1]} ({len(days)} sessions)")
    print(f"  1m sources: {a1['src']}")
    print(f"  consistent base: {a1['replaced']} RTH 5m bars rebuilt from the NQ1! 1m feed; engine ltf: {a1['ltf']['mode']} "
          f"(inconsistent windows: {a1['ltf']['inconsistent']})")
    print(f"  1m candidate triggers (taken + passed by filters): {a1['cand_1m']}")
    for lab, ds in ((f"all {len(days)} sessions", set(days)), (f"last 7 sessions ({last7[0]}..{last7[-1]})", set(last7))):
        print(f"  -- {lab}")
        print(f"     5m trigger (current) : {fmt(stats(win(a5['trades'], ds), len(ds)))}")
        print(f"     1m trigger (hybrid)  : {fmt(stats(win(a1['trades'], ds), len(ds)))}")
    ar = R["AR"]
    print(f"  reference - default code path backtest.run(ifvg_tf='lower') on raw NQ_5m (MNQ) base: {ar['ltf']['mode']}; "
          f"inconsistent windows {ar['ltf']['inconsistent']}")
    print(f"     1m trigger raw base  : {fmt(stats(win(ar['trades'], set(days)), len(days)))}")
    pre5 = [t for t in a5["trades"] if t["day"] < days[0]]
    pre1 = [t for t in a1["trades"] if t["day"] < days[0]]
    same = [(x["entry_t"], x["pnl"]) for x in pre5] == [(x["entry_t"], x["pnl"]) for x in pre1]
    print(f"  sanity: trades before the 1m window identical in both arms: {same} ({len(pre5)} trades)")

    # paired view: same setup (same day and direction, entries within 20 minutes) taken by both arms
    t5, t1 = win(a5["trades"], set(days)), win(a1["trades"], set(days))
    for lab, tr in (("5m trigger", t5), ("1m trigger", t1)):
        r = np.array([t["pnl_r"] for t in tr])
        print(f"  {lab}: avg R {r.mean():+.2f} +/- {r.std(ddof=1) / np.sqrt(len(r)):.2f} (1 standard error, n={len(r)})")
    mins = [int((t["entry_t"] - t["signal_t"]) // 60) - 1 for t in t1 if t.get("trigger_tf") == "1m"]
    print(f"  minute of the 5m bar in which the 1m trigger closed (0 = first minute, 4 = same close as the 5m bar): "
          f"{dict(sorted(pd.Series(mins).value_counts().to_dict().items()))}")
    print("\n  trade by trade (ET entry time, trigger, risk pts, result R) - same setup paired when day/dir match within 20 min")
    used = set()
    rows = []
    for x in t1:
        y = next((k for k, z in enumerate(t5) if k not in used and z["day"] == x["day"] and z["dir"] == x["dir"]
                  and abs(z["entry_t"] - x["entry_t"]) <= 1200), None)
        if y is not None:
            used.add(y)
        rows.append((x, t5[y] if y is not None else None))
    rows += [(None, z) for k, z in enumerate(t5) if k not in used]
    et = __import__("zoneinfo").ZoneInfo("America/New_York")
    hm = lambda t: dt.datetime.fromtimestamp(t["entry_t"], et).strftime("%H:%M")
    rows.sort(key=lambda r: (r[0] or r[1])["entry_t"])
    pr, dr, ep = [], [], []
    for x, z in rows:
        d0 = (x or z)["day"]
        sd = "L" if (x or z)["dir"] == 1 else "S"
        s1 = f"{hm(x)} {x['trigger']:4s}/{x.get('trigger_tf') or '5m'} {x['risk_pts']:5.1f}pt {x['pnl_r']:+5.2f}R{' FALSE' if x['false_1m'] else '      '}" if x else " " * 41
        s5 = f"{hm(z)} {z['trigger']:4s} {z['risk_pts']:5.1f}pt {z['pnl_r']:+5.2f}R" if z else ""
        tag = "same setup" if x and z else ("1m only" if x else "5m only")
        print(f"   {d0} {sd} | 1m arm: {s1} | 5m arm: {s5:28s} | {tag}")
        if x and z:
            pr.append(x["risk_pts"] / z["risk_pts"])
            dr.append(x["pnl_r"] - z["pnl_r"])
            ep.append((z["entry"] - x["entry"]) * x["dir"])
    if pr:
        print(f"  paired setups: {len(pr)}  entry better by {np.mean(ep):+.1f} pts on average (median {np.median(ep):+.1f})  "
              f"risk 1m/5m = {np.mean(pr):.2f}x  mean R change {np.mean(dr):+.2f}R  "
              f"(1m better on {sum(1 for v in dr if v > 0.05)}, worse on {sum(1 for v in dr if v < -0.05)})")
    only1 = [x for x, z in rows if x and not z]
    only5 = [z for x, z in rows if z and not x]
    print(f"  1m-only trades: {len(only1)}  sum {sum(t['pnl_r'] for t in only1):+.2f}R  (false triggers among them: "
          f"{sum(1 for t in only1 if t['false_1m'])}, their sum {sum(t['pnl_r'] for t in only1 if t['false_1m']):+.2f}R)")
    print(f"  5m-only trades: {len(only5)}  sum {sum(t['pnl_r'] for t in only5):+.2f}R")

    # ------------------------------------------------------------------ part B
    print("\n" + "=" * 150)
    print("PART B - SYNTHETIC UPPER BOUND (5m data only): the same 5m-trigger trades with the entry moved earlier inside the")
    print("trigger bar, same stop / target / exit price. A CEILING - it ignores extra false triggers and earlier stop-outs.")
    print(f"{'period':14s} {'n':>4s} | {'actual 5m':>26s} | {'entry @ bar open':>26s} | {'entry @ body mid':>26s} | {'1 tick through level':>26s}")
    for lab, sym, a, z in SEGS:
        src = R["B" + sym]
        tr = [t for t in src["trades"] if (not a or t["day"] >= a) and (not z or t["day"] <= z)]
        for t in tr:
            t["level"] = t["zone"][1] if t["dir"] == 1 else t["zone"][0]
        s = synth(tr)
        cell = lambda k: f"{s[k]['avg_r']:+.2f}R pf{s[k]['pf']:5.2f} {s[k]['risk']:4.1f}pt"
        print(f"{lab:14s} {len(tr):4d} | {cell('actual'):>26s} | {cell('open'):>26s} | {cell('mid'):>26s} | {cell('level'):>26s}")
        print(f"{'':14s} {'':4s} | {'$ at same $ risk:':>17s} {s['actual']['usd']:+7.0f} | {s['open']['usd']:+25.0f} | "
              f"{s['mid']['usd']:+25.0f} | {s['level']['usd']:+25.0f}")
