"""Holidays / roll / FOMC windows for LIT and ATLAS (2026-11-21). PAPER RESEARCH ONLY. Design: research/holidays/DESIGN.md.

    python -X utf8 research/holidays/holidays.py [--n 600]   -> research/holidays/results.json
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "regime_guard"))
import guard as G  # noqa: E402  (trades, fixed $ view, LIT eval, ATLAS funded engines)

OUT = os.path.join(HERE, "results.json")
FIX = G.FIX


def thanksgiving(y):
    d = dt.date(y, 11, 1)
    first_thu = d + dt.timedelta(days=(3 - d.weekday()) % 7)
    return first_thu + dt.timedelta(days=21)


def roll_date(y, m):
    d = dt.date(y, m, 1)
    third_fri = d + dt.timedelta(days=(4 - d.weekday()) % 7 + 14)
    return third_fri - dt.timedelta(days=8)


def week_of(d):
    mon = d - dt.timedelta(days=d.weekday())
    return {(mon + dt.timedelta(days=i)).isoformat() for i in range(5)}


def windows(S):
    tg, rw, hs = set(), set(), set()
    for y in range(2021, 2027):
        tg |= week_of(thanksgiving(y))
        for m in (3, 6, 9, 12):
            rw |= week_of(roll_date(y, m))
    for d in S:
        md = d[5:]
        if md >= "12-15" or md <= "01-05":
            hs.add(d)
    fomc = set()
    with open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8") as fh:
        for ln in fh:
            p = ln.split(",")
            if len(p) > 2 and "FOMC rate decision" in p[2]:
                fomc.add(p[0])
    return {"thanksgiving": tg, "roll_week": rw, "holiday_stretch": hs, "fomc_day": fomc}


def describe(T, days_in, S):
    out = {}
    for sp, (a, z) in FIX.items():
        for lab, inside in (("window", True), ("normal", False)):
            tt = [t for t in T if a <= t["day"] <= z and ((t["day"] in days_in) == inside)]
            ds = [d for d in S if a <= d <= z and ((d in days_in) == inside)]
            p = []
            by = collections.defaultdict(float)
            for t in tt:
                x, q = G.tusd(t)
                if q > 0:
                    p.append(x)
                    by[t["day"]] += x
            p = np.array(p)
            gl = -p[p < 0].sum() if len(p) else 0
            dv = list(by.values())
            out[f"{sp}_{lab}"] = {"days": len(ds), "trades": int(len(p)), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
                                  "usd_per_trade": round(float(p.mean()), 1) if len(p) else None, "net": round(float(p.sum())),
                                  "worst_day": round(min(dv), 0) if dv else None,
                                  "big_loss_days_pct": round(100.0 * sum(1 for x in dv if x <= -600) / len(dv), 1) if dv else None}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    a = ap.parse_args(argv)
    import uprisk as U
    import builder_levers as BL
    import atlas_health as AH
    t0 = time.time()
    S, BY, lit, atl = G.trades()
    W = windows(S)
    PE = {sp: U.mc_paths(S, sp, a.n, length=60, seed=7) for sp in ("H1", "H2", "REF")}
    PF = {sp: U.mc_paths(S, sp, a.n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    RS = AH.real_starts(S)
    R = {"windows": {k: sorted(v)[:3] + ["..."] for k, v in W.items()}, "bots": {}}
    for bot, T in (("LIT", lit), ("ATLAS", atl)):
        F0 = {}
        base_fx = G.fixed(T, S, lambda t: 1.0)
        base_acct = G.lit_eval(S, BY, F0, None, 1.0, PE) if bot == "LIT" else G.atlas_funded(atl, S, F0, None, 1.0, PF, RS)[0]
        rows = {"base": {"fixed": base_fx, "acct": base_acct}}
        for wn, days in W.items():
            desc = describe(T, days, S)
            rows[wn] = {"describe": desc}
            if bot == "LIT" and wn == "roll_week":
                rows[wn]["note"] = "rule already rejected (S2 edge 2026-11-15): described only"
                continue
            F = {d: {wn: True} for d in days}
            for act, m in (("out", 0.0), ("half", 0.5)):
                w = (lambda t, m=m, days=days: m if t["day"] in days else 1.0)
                fx = G.fixed(T, S, w)
                acct = G.lit_eval(S, BY, F, wn, m, PE) if bot == "LIT" else G.atlas_funded(atl, S, F, wn, m, PF, RS)[0]
                why = []
                for sp in FIX:
                    if desc[f"{sp}_window"]["trades"] == 0:
                        why.append(f"no {sp} trades in the window: untestable there")
                    if not fx[sp]["net"] > base_fx[sp]["net"]:
                        why.append(f"$ {sp} {base_fx[sp]['net']} -> {fx[sp]['net']}")
                    if bot == "LIT":
                        if acct[sp]["p60"] < base_acct[sp]["p60"] - 2 or acct[sp]["f60"] > base_acct[sp]["f60"]:
                            why.append(f"eval {sp} pass/fail {base_acct[sp]['p60']}/{base_acct[sp]['f60']} -> {acct[sp]['p60']}/{acct[sp]['f60']}")
                    else:
                        if acct[sp]["dead_6m"] > base_acct[sp]["dead_6m"] or acct[sp]["per_month"] < base_acct[sp]["per_month"] - 10:
                            why.append(f"funded {sp} ${base_acct[sp]['per_month']}/{base_acct[sp]['dead_6m']}% -> ${acct[sp]['per_month']}/{acct[sp]['dead_6m']}%")
                for sp in ("H1", "H2"):
                    if fx[sp]["tpw"] < 2.0:
                        why.append(f"{sp} {fx[sp]['tpw']}/wk")
                rows[wn][act] = {"fixed": fx, "acct": acct, "pass": not why, "why": why}
                print(f"{bot} {wn:16s} {act:4s} " + " ".join(f"{sp} ${base_fx[sp]['net']}->${fx[sp]['net']}" for sp in FIX) +
                      f" | {'PASS' if not why else why[0]} [{time.time() - t0:.0f}s]", flush=True)
        R["bots"][bot] = rows
    R["passers"] = [f"{b} {w} {a}" for b, rr in R["bots"].items() for w, r in rr.items() if isinstance(r, dict)
                    for a in ("out", "half") if isinstance(r.get(a), dict) and r[a]["pass"]]
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=1, default=float)
    print("passers:", R["passers"])


if __name__ == "__main__":
    main()
