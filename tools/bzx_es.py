"""BLITZ on ES (coordinator round 4, 2026-10-30): today's BLITZ rule run on CME ES1! 5m bars (data/ES_5m.csv, TradingView,
2025-04-13 .. 2026-10-16) exactly as the 2021-25 NQ 5m reference runs, priced as MES ($5 a point a micro, $1.90 a micro
round trip, 1 tick = 0.25 pt on market / stop fills), vs NQ BLITZ on the same 5m bars. Research only; nothing here is
imported by the engine. research/writeups/blitz-edge-2026-10-30b.md (round 4), runs bzx_es_*.

    python -X utf8 tools/bzx_es.py solo      # ES alone vs NQ (5m like-for-like, and NQ 1m for 2026): spans 2025 May-Dec, 2026 H1, H2
    python -X utf8 tools/bzx_es.py combo     # NQ + ES BLITZ on one 25K (only if ES holds)

Approximation: the BLITZ day stop (-3R a day) is counted inside the bar simulator with MNQ's $2 a point for the commission
share of R; for MES ($5 a point) that share is smaller, so the day stop can trigger a hair later. Everything priced in $ uses
MES $5 a point.
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import bzx_edge as X  # noqa: E402
from tools import scalp_mo_lib as M  # noqa: E402

A, N, K, BS = X.A, X.N, X.K, X.BS
OUT = X.OUT
ES_PV = 5.0
SPANS_ES = (("2025", "2025-05-01", "2025-12-31"), ("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-12-31"))
_EB = {}


def es_bars():
    """ES 5m bars in the research bar format (scalp_mo_lib._bars on data/ES_5m.csv: same ATR, VWAP, flat, day split)."""
    if "B" not in _EB:
        orig = M.pd.read_csv
        src = os.path.join(ROOT, "data", "ES_5m.csv")

        def rc(p, *a, **k):
            if str(p).endswith("NQ_5m.csv"):
                p = src
            return orig(p, *a, **k)
        M.pd.read_csv = rc
        try:
            B = M._bars(5, "2025-04-01", cut_t=2 ** 62)
        finally:
            M.pd.read_csv = orig
        _EB["B"] = B
    return _EB["B"]


def es_trades(cmode=None):
    """today's BLITZ rule on ES 5m (no anti-hedge partner on ES), priced as MES."""
    B = es_bars()
    old = K.PV
    K.PV = ES_PV
    try:
        T = K.run(B, {}, cmode)
    finally:
        K.PV = old
    return T


def sess(B, a, z):
    return [d for i, d in enumerate(B["dates"]) if a <= d <= z and B["flat_of_day"][i] >= 0]


def daily(T, S, usd=150.0):
    by = collections.defaultdict(float)
    for t in T:
        q = max(1, min(20, int(usd / t["risk_pm"])))
        by[t["day"]] += N.trade_pnl(t, q)[0]
    return np.array([by.get(d, 0.0) for d in S])


def view(T, S):
    o = N.stats(T, S, 150.0, 20)
    o["wk2"] = K.wk2([t for t in T if S[0] <= t["day"] <= S[-1]], S)
    return {k: o[k] for k in ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "avg_r", "med_stop")}


def cmd_solo():
    t0 = time.time()
    X.prep()
    Be = es_bars()
    Te = es_trades()
    B5, B1 = N.bars(5), N.bars(1)
    Tn5 = X.TT[5]                                   # NQ 5m BLITZ as account C (the 2021-25 reference run)
    Tn5a = K.run(B5, {}, None)                      # NQ 5m BLITZ alone (no anti-hedge), like ES
    Tn1 = X.TT[1]                                   # NQ 1m BLITZ as account C (the 2026 live rule)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "data": {"es": f"{Be['dates'][0]}..{Be['dates'][-1]} 5m"}, "spans": {}}
    for nm, a, z in SPANS_ES:
        S = sess(Be, a, z)
        Sn = sess(B5, a, z)
        row = {"sessions": len(S), "es": view([t for t in Te if a <= t["day"] <= z], S),
               "nq5_account_c": view([t for t in Tn5 if a <= t["day"] <= z], Sn), "nq5_alone": view([t for t in Tn5a if a <= t["day"] <= z], Sn)}
        if nm != "2025":
            S1 = sess(B1, a, z)
            row["nq1_account_c"] = view([t for t in Tn1 if a <= t["day"] <= z], S1)
        common = [d for d in S if d in set(Sn)]
        de = daily([t for t in Te if a <= t["day"] <= z], common)
        dn = daily([t for t in Tn5 if a <= t["day"] <= z], common)
        both = (de != 0) & (dn != 0)
        row["corr_daily_nq5"] = round(float(np.corrcoef(de, dn)[0, 1]), 2)
        row["corr_daily_nq5_both_traded"] = round(float(np.corrcoef(de[both], dn[both])[0, 1]), 2) if both.sum() > 5 else None
        row["days_both_traded"] = int(both.sum())
        row["same_dir_share"] = None
        if nm != "2025":
            dn1 = daily([t for t in Tn1 if a <= t["day"] <= z], common)
            row["corr_daily_nq1"] = round(float(np.corrcoef(de, dn1)[0, 1]), 2)
        # direction agreement on days both traded (first trade's side)
        fe = {t["day"]: t["dir"] for t in sorted(Te, key=lambda x: x["entry_t"]) if a <= t["day"] <= z and t["day"] not in ()}
        fn = {}
        for t in sorted(Tn5, key=lambda x: x["entry_t"]):
            if a <= t["day"] <= z and t["day"] not in fn:
                fn[t["day"]] = t["dir"]
        fe2 = {}
        for t in sorted(Te, key=lambda x: x["entry_t"]):
            if a <= t["day"] <= z and t["day"] not in fe2:
                fe2[t["day"]] = t["dir"]
        bd = [d for d in fe2 if d in fn]
        row["same_dir_share"] = round(float(np.mean([fe2[d] == fn[d] for d in bd])), 2) if bd else None
        out["spans"][nm] = row
        print(nm, json.dumps(row), flush=True)
    # how much of the gap is costs: the same ES and NQ trades before commission and the 1-tick fills (an upper bound: both
    # fills given back) - PF and avg R per span
    for nm, a, z in SPANS_ES:
        for lab, T, pv in (("es", Te, ES_PV), ("nq5_account_c", Tn5, 2.0)):
            Ts = [t for t in T if a <= t["day"] <= z]
            add = N.COMM + 2 * 0.25 * pv
            g = np.array([(t["pnl_pm"] + add) / t["risk_pm"] for t in Ts])
            c_share = float(np.median([add / t["risk_pm"] for t in Ts]))
            out["spans"][nm][f"{lab}_gross"] = {"pf": round(float(g[g > 0].sum() / -g[g < 0].sum()), 2), "avg_r": round(float(g.mean()), 3),
                                                "cost_share_of_1R": round(c_share, 3)}
        print(nm, "before costs:", out["spans"][nm]["es_gross"], "NQ 5m:", out["spans"][nm]["nq5_account_c_gross"], flush=True)
    out["es_stop_pts_median"] = float(np.median([t["risk_pts"] for t in Te]))
    out["es_risk_pm_median"] = float(np.median([t["risk_pm"] for t in Te]))
    print("ES median stop", out["es_stop_pts_median"], "pts, 1-micro risk $", round(out["es_risk_pm_median"], 2))
    A.dump(out, os.path.join(OUT, "bzx_es_solo.json"))
    # the run library: ES trades at $150 (MES), 2025 May - 2026 Oct 16
    from tools import runlib as rl
    Ts = X.store_trades([t for t in Te if t["day"] >= "2025-05-01"])
    for t in Ts:
        t["trigger"] = "blitz_es"
    sp = out["spans"]
    v = ("Today's BLITZ rule on CME ES1! 5m bars (MES $5 a point, $1.90 a micro, 1 tick fills), at $150 a trade - 2025 May-Dec / 2026 H1 / 2026 H2: "
         + " / ".join(f"PF {sp[n]['es']['pf']}, ${sp[n]['es']['per_month']} a month, {sp[n]['es']['tpw']} a week" for n, _, _ in SPANS_ES)
         + "; NQ BLITZ on the same 5m bars: " + " / ".join(f"PF {sp[n]['nq5_account_c']['pf']}, ${sp[n]['nq5_account_c']['per_month']}" for n, _, _ in SPANS_ES)
         + ". Daily P&L correlation with NQ BLITZ " + " / ".join(str(sp[n]["corr_daily_nq5"]) for n, _, _ in SPANS_ES)
         + f" (same side on {', '.join(str(sp[n]['same_dir_share']) for n, _, _ in SPANS_ES)} of the days both trade). Before costs ES is PF "
         + " / ".join(str(sp[n]["es_gross"]["pf"]) for n, _, _ in SPANS_ES)
         + ". ES fails (PF < 1.1 in every span), so the NQ + ES 25K was not built. Short history (18 months): a caveat. Rejected.")
    rl.save("bzx_es_solo", "BLITZ on ES (MES, 5m) as a second market - rejected (PF 0.94 / 1.03 / 0.82, correlated 0.6 with NQ BLITZ)", "other",
            "Coordinator round 4: does BLITZ work on ES as a second market for the same 25K?",
            params={**K.TODAY, "market": "ES1! 5m, MES $5 a point"}, sizing={"usd_per_trade": 150.0}, trades=Ts,
            scored=rl.score(Ts, sess(Be, "2025-05-01", "2026-12-31")), status="rejected", verdict=v, notes="tools/bzx_es.py solo",
            writeup="blitz-edge-2026-10-30b", tags=["scalp", "blitz", "es", "bzx", "second-market"])
    print("-> run bzx_es_solo:", v)
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    {"solo": cmd_solo}[a[0]]()
