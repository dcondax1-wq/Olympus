"""BLITZ v2 step 1: anatomy of today's BLITZ trades (research/blitzv2/DESIGN.md). PAPER RESEARCH ONLY.
Diagnosis spans = 2021-24 (5m) + 2026 Jan-Jun (1m): the variants are chosen from these only. 2025 (5m), Jul-Nov 2026 (1m) are
looked at AFTER the variants are written down (they are the check).
    python -X utf8 research/blitzv2/anatomy.py  -> research/blitzv2/anatomy.json
"""
import collections, csv, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); os.chdir(ROOT)
from tools import blitz25k_lib as L, scalp_na_lib as N  # noqa: E402

VIX = {r["date"]: float(r["close"]) for r in csv.DictReader(open("data/VIX_1d.csv"))}
VD = sorted(VIX)


def vix_prior(day):
    import bisect
    i = bisect.bisect_left(VD, day) - 1
    return VIX[VD[i]] if i >= 0 else np.nan


def feats(B, T):
    """facts known at the signal bar close for each trade."""
    t2i = {int(t): i for i, t in enumerate(B["t"])}
    F0 = L._signals_win(B, "rth")
    sg = (F0["_up"] / np.where(np.isnan(F0["_up"]), 1, (F0["_up"] + F0["_lo"]) / 2) - 1)   # sigma
    X = N._day_ctx(B)
    h60 = L.htf_state(B, 60); h15 = L.htf_state(B, 15)
    # day open / prior RTH close
    rows = []
    nday = collections.Counter()
    for t in sorted(T, key=lambda t: t["entry_t"]):
        i = t2i[int(t["sig_t"])]
        d = t["dir"]; di = B["day"][i]
        o0 = (F0["_up"][i] + F0["_lo"][i]) / 2
        s_ = sg[i]
        nday[t["day"]] += 1
        # day so far: RTH bars of the day up to i
        s = i
        while s > 0 and B["day"][s - 1] == di and B["mod"][s - 1] >= 570:
            s -= 1
        hi, lo = B["h"][s:i + 1].max(), B["l"][s:i + 1].min()
        a5 = B["atr5"][i]
        rows.append({"day": t["day"], "y": t["day"][:4], "R": t["pnl_pm"] / t["risk_pm"], "dir": d,
                     "check": int(B["mod"][i] + B["tf"]), "nth": nday[t["day"]], "dow": int(B["dow"][i]),
                     "band_x": abs(B["c"][i] / o0 - 1) / s_ if s_ else np.nan,
                     "prng": float(X["prng_ratio"][di]) if not np.isnan(X["prng_ratio"][di]) else np.nan,
                     "vix": vix_prior(t["day"]), "h60": float(h60[i] * d), "h15": float(h15[i] * d),
                     "vwap": float(np.sign(d * (B["c"][i] - B["vwap"][i]))),
                     "pos_rng": float((B["c"][i] - lo) / (hi - lo)) if hi > lo else 0.5,        # where in the day's range
                     "rng_atr": float((hi - lo) / a5) if a5 else np.nan,
                     "stop_pct": float(t["risk_pts"] / B["c"][i] * 100), "exit": t["exit_kind"]})
    return rows


def bucket(rows, key, edges=None, labels=None):
    out = {}
    for r in rows:
        v = r[key]
        if edges is None:
            k = str(v)
        else:
            if v != v:
                continue
            k = labels[int(np.searchsorted(edges, v, side="right"))]
        out.setdefault(k, []).append(r["R"])
    return {k: {"n": len(v), "avgR": round(float(np.mean(v)), 3), "sumR": round(float(np.sum(v)), 1)} for k, v in sorted(out.items())}


def main():
    TT = L.trades()
    P = {"2021-24": (5, "2021-11-01", "2024-12-31"), "2026 H1": (1, "2026-01-01", "2026-06-30"),
         "2025 (check)": (5, "2025-01-01", "2025-12-31"), "2026 Jul-Nov (check)": (1, "2026-07-01", "2026-11-20")}
    res = {}
    for nm, (tf, a, z) in P.items():
        B = N.bars(tf)
        rows = [r for r in feats(B, [t for t in TT[tf] if a <= t["day"] <= z])]
        long_ = [r for r in rows]
        g = {}
        g["all"] = bucket(rows, "y")
        g["check"] = bucket(rows, "check")
        g["nth"] = bucket(rows, "nth", [1.5, 2.5], ["1st", "2nd", "3rd+"])
        g["dir"] = bucket(rows, "dir")
        g["band_x (distance beyond the anchor, in sigmas)"] = bucket(rows, "band_x", [1.25, 1.6, 2.2], ["1-1.25", "1.25-1.6", "1.6-2.2", "2.2+"])
        g["vix"] = bucket(rows, "vix", [16, 20, 25], ["<16", "16-20", "20-25", "25+"])
        g["prng"] = bucket(rows, "prng", [1.0, 1.3], ["0.8-1.0", "1.0-1.3", "1.3+"])
        g["h60 with trade"] = bucket(rows, "h60")
        g["h15 with trade"] = bucket(rows, "h15")
        g["vwap side"] = bucket(rows, "vwap")
        g["pos in day range (1 = at the high)"] = bucket(rows, "pos_rng", [0.2, 0.8], ["low 20%", "middle", "top 20%"])
        g["day range so far / ATR5"] = bucket(rows, "rng_atr", [6, 10, 15], ["<6", "6-10", "10-15", "15+"])
        g["stop % of price"] = bucket(rows, "stop_pct", [0.15, 0.25], ["<0.15%", "0.15-0.25%", "0.25%+"])
        g["dow"] = bucket(rows, "dow")
        g["exit"] = bucket(rows, "exit")
        res[nm] = g
    json.dump(res, open(os.path.join(HERE, "anatomy.json"), "w"), indent=1)
    for nm in ("2021-24", "2026 H1"):
        print("=====", nm)
        for k, v in res[nm].items():
            print(f"  {k}: " + "; ".join(f"{b} n{x['n']} {x['avgR']:+.3f}" for b, x in v.items()))


main()
