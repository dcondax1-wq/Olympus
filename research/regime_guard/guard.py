"""Regime guard (2026-11-20, round 2 of day-newstrat): can a causal pre-session signal size LIT / ATLAS down in a 2021-25-like
market without giving up 2026's money? PAPER RESEARCH ONLY: reads stored trades + daily bars, writes
research/regime_guard/results.json. Rules: research/regime_guard/RULES.md (pre-registered, not changed after results).

    python -X utf8 research/regime_guard/guard.py [--n 600]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import logging
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")):
    sys.path.insert(0, p)
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
OUT = os.path.join(HERE, "results.json")
PV, COMM, SLIP = 2.0, 1.90, 0.25
USD = {"LIT": 350.0, "ATLAS": 250.0}
FIX = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16"), "REF": ("2021-11-01", "2025-12-31")}
SIGS = ("G1 VRP", "G2 quiet", "G3 chop", "G4 vote")


# ------------------------------------------------------------------------------------------------ the signals
def daily_flags():
    """day -> {signal: bad?} from bars closed before the day (NQ1! daily) and the prior CBOE VIX close."""
    d = pd.read_csv(os.path.join(ROOT, "data", "NQ_1d.csv"))
    d["date"] = pd.to_datetime(d.time, unit="s", utc=True).dt.strftime("%Y-%m-%d")
    v = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv"))
    vix = dict(zip(v.iloc[:, 0].astype(str), v.iloc[:, 4].astype(float)))
    vdates = sorted(vix)
    c, h, l = d.close.to_numpy(), d.high.to_numpy(), d.low.to_numpy()
    dates = d.date.tolist()
    lr = np.r_[np.nan, np.diff(np.log(c))]
    tr = np.r_[h[0] - l[0], np.maximum(h[1:], c[:-1]) - np.minimum(l[1:], c[:-1])]
    rows = []                                   # value known AFTER close k (used for the next session)
    for k in range(len(c)):
        if k < 21:
            rows.append(None)
            continue
        rv = float(np.std(lr[k - 19:k + 1], ddof=1) * np.sqrt(252) * 100)
        atr = float(tr[k - 19:k + 1].mean() / c[k])
        er = float(abs(c[k] - c[k - 20]) / np.abs(np.diff(c[k - 20:k + 1])).sum())
        rows.append({"rv": rv, "atr": atr, "er": er, "date": dates[k]})
    out = {}
    hist_atr, hist_er = [], []
    import bisect
    for k in range(len(c) - 1):
        r = rows[k]
        if r is None:
            continue
        hist_atr.append(r["atr"]); hist_er.append(r["er"])
        day = dates[k + 1]                      # the next session uses close k
        vi = bisect.bisect_left(vdates, day) - 1
        vx = vix[vdates[vi]] if vi >= 0 else None
        f = {"G1 VRP": bool(vx is not None and r["rv"] > vx)}
        if len(hist_atr) >= 60:
            ha, he = np.array(hist_atr[-252:]), np.array(hist_er[-252:])
            f["G2 quiet"] = bool((ha < r["atr"]).mean() < 1 / 3)
            f["G3 chop"] = bool((he < r["er"]).mean() < 1 / 3)
        else:
            f["G2 quiet"] = f["G3 chop"] = False
        f["G4 vote"] = sum(f[x] for x in ("G1 VRP", "G2 quiet", "G3 chop")) >= 2
        out[day] = {**f, "rv": round(r["rv"], 2), "vix": vx, "atr": round(r["atr"] * 100, 3), "er": round(r["er"], 3)}
    # the last bar's values for the session after the data ends are not needed
    return out


# ------------------------------------------------------------------------------------------------ trades
def trades():
    import account4_sim as A4
    import atlas_health as AH
    S, BY = A4.load()
    lit = [dict(t, strat="LIT") for ts in BY for t in ts]
    atl = [dict(t, strat="ATLAS") for t in AH.stream()]
    return S, BY, lit, atl


def tusd(t, w=1.0):
    q = int(USD[t["strat"]] * w // ((t["risk"] + SLIP) * PV + COMM))
    return q * (t["pts"] * PV - COMM) if q > 0 else 0.0, q


def span(day):
    for k, (a, z) in FIX.items():
        if a <= day <= z:
            return k


def fixed(T, S, w):
    out = {}
    for sp, (a, z) in FIX.items():
        days = [d for d in S if a <= d <= z]
        L = [(t, *tusd(t, w(t))) for t in T if a <= t["day"] <= z]
        p = np.array([x for _, x, q in L if q > 0], float)
        by = collections.defaultdict(float)
        for t, x, q in L:
            by[t["day"]] += x
        eq = np.cumsum([by.get(d, 0.0) for d in days])
        gl = -p[p < 0].sum()
        out[sp] = {"n": int(len(p)), "tpw": round(len(p) / (len(days) / 5), 2), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
                   "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(days) / 21)),
                   "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())) if len(eq) else 0}
    return out


def edge(T, F, sig):
    """avg fixed-$ R of trades on bad vs other days, per span."""
    o = {}
    for sp, (a, z) in FIX.items():
        b, g = [], []
        for t in T:
            if a <= t["day"] <= z:
                x, q = tusd(t)
                if q <= 0:
                    continue
                r = x / USD[t["strat"]]
                (b if F.get(t["day"], {}).get(sig) else g).append(r)
        o[sp] = {"bad_n": len(b), "bad_r": round(float(np.mean(b)), 3) if b else None, "ok_n": len(g),
                 "ok_r": round(float(np.mean(g)), 3) if g else None}
    return o


# ------------------------------------------------------------------------------------------------ accounts
def lit_eval(S, BY, F, sig, mult, PE):
    import account4_sim as A4
    E, _ = A4.rules("mffu_builder_50k")
    cfg = A4.ecfg(E)
    BY2 = []
    for d, ts in zip(S, BY):
        bad = sig and F.get(d, {}).get(sig)
        if not bad or mult == 1.0:
            BY2.append(ts)
        elif mult == 0.0:
            BY2.append([])
        else:
            BY2.append([{**t, "risk": t["risk"] / mult} for t in ts])   # half size: the live sizer gives ~half the micros
    return {sp: A4.eval_stats(BY2, PE[sp], E, cfg, 91.80) for sp in ("H1", "H2", "REF")}


def atlas_funded(atl, S, F, sig, mult, PF, RS):
    import atlas_health as AH
    w = {t["entry_t"]: (mult if sig and F.get(t["day"], {}).get(sig) else 1.0) for t in atl}
    r = AH.score({"fam": "base"}, atl, S, PF, RS, w=w)
    return {sp: r["funded"][sp] for sp in ("H1", "H2", "REF")}, {sp: r["real"][sp] for sp in ("H1", "H2", "REF")}


def gate(row, base):
    why = []
    sh = row["bad_share"]
    if not all(sh["REF"] > sh[s] for s in ("H1", "H2")):
        why.append(f"separation: bad days REF {sh['REF']}% vs H1 {sh['H1']}% / H2 {sh['H2']}%")
    for b in ("LIT", "ATLAS"):
        e = row["edge"][b]
        for sp in FIX:
            if e[sp]["bad_r"] is None or e[sp]["ok_r"] is None or not e[sp]["bad_r"] < e[sp]["ok_r"]:
                why.append(f"edge {b} {sp}: bad {e[sp]['bad_r']}R vs ok {e[sp]['ok_r']}R")
        f, f0 = row["fixed"][b], base["fixed"][b]
        if not f["REF"]["net"] > f0["REF"]["net"]:
            why.append(f"$ {b} 2021-25 {f0['REF']['net']} -> {f['REF']['net']}")
        for sp in ("H1", "H2"):
            if f[sp]["net"] < f0[sp]["net"] - 0.10 * abs(f0[sp]["net"]):
                why.append(f"$ {b} {sp} {f0[sp]['net']} -> {f[sp]['net']}")
            if f[sp]["tpw"] < 2.0:
                why.append(f"trades {b} {sp} {f[sp]['tpw']}/wk")
    a, a0 = row["atlas_funded"], base["atlas_funded"]
    if not a["REF"]["dead_6m"] < a0["REF"]["dead_6m"]:
        why.append(f"ATLAS funded dead 2021-25 {a0['REF']['dead_6m']} -> {a['REF']['dead_6m']}%")
    for sp in ("H1", "H2"):
        if a[sp]["dead_6m"] > a0[sp]["dead_6m"]:
            why.append(f"ATLAS funded dead {sp} {a0[sp]['dead_6m']} -> {a[sp]['dead_6m']}%")
        if a[sp]["per_month"] < a0[sp]["per_month"] - 10:
            why.append(f"ATLAS funded {sp} ${a0[sp]['per_month']} -> ${a[sp]['per_month']}/mo")
    l, l0 = row["lit_eval"], base["lit_eval"]
    for sp in ("H1", "H2"):
        if l[sp]["p60"] < l0[sp]["p60"] - 2:
            why.append(f"LIT eval pass {sp} {l0[sp]['p60']} -> {l[sp]['p60']}%")
    if not l["REF"]["f60"] < l0["REF"]["f60"]:
        why.append(f"LIT eval fail 2021-25 {l0['REF']['f60']} -> {l['REF']['f60']}%")
    return why


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    a = ap.parse_args(argv)
    import uprisk as U
    import builder_levers as BL
    import atlas_health as AH
    t0 = time.time()
    F = daily_flags()
    S, BY, lit, atl = trades()
    PE = {sp: U.mc_paths(S, sp, a.n, length=60, seed=7) for sp in ("H1", "H2", "REF")}
    PF = {sp: U.mc_paths(S, sp, a.n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    RS = AH.real_starts(S)
    out = {"built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "n": a.n, "rows": {}}
    versions = [("today", None, 1.0)] + [(f"{s} {nm}", s, m) for s in SIGS for nm, m in (("half", 0.5), ("out", 0.0))]
    base = None
    for name, sig, mult in versions:
        w = (lambda t, s=sig, m=mult: m if s and F.get(t["day"], {}).get(s) else 1.0)
        row = {"sig": sig, "mult": mult,
               "bad_share": {sp: round(100.0 * np.mean([bool(sig and F.get(d, {}).get(sig)) for d in S if lo <= d <= hi]), 1)
                             for sp, (lo, hi) in FIX.items()},
               "fixed": {"LIT": fixed(lit, S, w), "ATLAS": fixed(atl, S, w)},
               "edge": {"LIT": edge(lit, F, sig), "ATLAS": edge(atl, F, sig)} if sig else None,
               "lit_eval": lit_eval(S, BY, F, sig, mult, PE)}
        row["atlas_funded"], row["atlas_real"] = atlas_funded(atl, S, F, sig, mult, PF, RS)
        if base is None:
            base = row
            row["why"] = []
        else:
            row["why"] = gate(row, base)
        row["pass"] = sig is not None and not row["why"]
        out["rows"][name] = row
        fl, fa = row["fixed"]["LIT"], row["fixed"]["ATLAS"]
        print(f"{name:14s} bad% {row['bad_share']} | LIT $ " + " ".join(f"{sp} {fl[sp]['net']}" for sp in FIX) +
              " | ATLAS $ " + " ".join(f"{sp} {fa[sp]['net']}" for sp in FIX) +
              " | ATLAS dead " + " ".join(f"{sp} {row['atlas_funded'][sp]['dead_6m']}" for sp in FIX) +
              " | LIT eval p/f " + " ".join(f"{sp} {row['lit_eval'][sp]['p60']}/{row['lit_eval'][sp]['f60']}" for sp in FIX) +
              f" | {'PASS' if row['pass'] else len(row['why'])} [{time.time() - t0:.0f}s]", flush=True)
    out["passers"] = [k for k, r in out["rows"].items() if r["pass"]]
    out["took_s"] = round(time.time() - t0)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    print("passers:", out["passers"])
    return out


if __name__ == "__main__":
    main()
