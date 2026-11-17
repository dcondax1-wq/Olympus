"""LIT regime SIZING (2026-11-17, night-gex). RESEARCH ONLY: engine/ and live_model*.json untouched.
Write-up: research/writeups/lit-regime-sizing-2026-11-17.md.

Question: does LIT's R a trade depend on the DAILY regime known before the session, and if so does a size rule (x1.25 in the good
regime, x0.75 in the bad one, same $ caps and MFFU room rules) pay on the eval path and the funded account?

Trades: the live LIT trades (tools/lit_edge.trades = run lit_live, 631 trades, 120 in 2026), R a trade at the LIT size rule
(costs in: $1.90 a micro, 1 tick on market fills / stops). Regime of a trade = the readings of the last close STRICTLY BEFORE
the trade's session date (CBOE / SqueezeMetrics close of the prior trading day, known by 16:15 ET, before the 18:00 open):
  gex_pos    SqueezeMetrics SPX gamma exposure > 0 (data/GEX_1d.csv)
  gex_lvl    GEX in $bn (level, not the 1-year percentile already tested in lit-market-context.md)
  vix        VIX close (data/VIX_1d.csv)
  vix_chg    VIX 1-day % change
  spread     VXN - VIX (Nasdaq vol premium over SPX vol; data/VXN_1d.csv) - new
  ts3        VIX / VIX3M (data/CBOE_vol_1d.csv; > 1 = backwardation) - ends 2026-09-17
  rng_pct    the prior NQ session's high-low range as a percentile of the 252 sessions before it (NQ1! 1m bars) - new
Buckets: 2 (H1 median) or 3 (H1 terciles) per feature, cut points from the 2026 Jan-Jun trades only; pairs = 2 x 2 (medians).
Pick on H1 (Jan-Jun 2026), check on H2 (Jul-Oct 2026), 2021-25 shown (5m days; VIX / VXN start 2021-10-15/18).

Scoring of a size rule: tools/lit_edge.evaluate (LIT size rule; the live eval path two_week room_f 0.4 kept to session 80,
Builder 50K; funded Builder 50K Monte Carlo at the live funded sizing) + a 200-draw placebo (the same multipliers shuffled).

    python -X utf8 tools/lit_regime_size.py            # -> research/lit/regime_size.json (116 bucket cells + 8 size rules, ~14 min)
    python -X utf8 tools/lit_regime_size.py pct        # VIX / spread as a trailing-252-session percentile -> regime_size_pct.json
"""
from __future__ import annotations

import bisect
import csv
import itertools
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import lit_edge as E  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402

ROOM, UNTIL = 0.4, 80
A.CFG = {**A.CFG, "two_week": {**A.CFG["two_week"], "room_f": ROOM}, "two_week_until": UNTIL}
OUT = os.path.join(ROOT, "research", "lit", "regime_size.json")
SP = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}
FEATS = ["gex_pos", "gex_lvl", "vix", "vix_chg", "spread", "ts3", "rng_pct"]


def _series(fn, col):
    out = {}
    for r in csv.DictReader(open(os.path.join(ROOT, "data", fn), encoding="utf-8")):
        v = r.get(col)
        if v not in (None, ""):
            out[r["date"][:10]] = float(v)
    ks = sorted(out)
    return ks, out


def coverage(sessions):
    """Per file: first / last date and the NQ sessions inside that range with no reading (gaps)."""
    rep = {}
    for fn, col in (("GEX_1d.csv", "gex"), ("VIX_1d.csv", "close"), ("VXN_1d.csv", "close"), ("CBOE_vol_1d.csv", "vix3m"),
                    ("CBOE_vol_1d.csv", "vix1d")):
        ks, S = _series(fn, col)
        a, z = ks[0], ks[-1]
        miss = [d for d in sessions if a <= d <= z and d not in S]
        rep[f"{fn}:{col}"] = {"first": a, "last": z, "n": len(ks), "nq_sessions_missing": len(miss), "missing": miss[:20],
                              "nq_after_last": sum(1 for d in sessions if d > z)}
    return rep


def regimes(sessions, rng_by_day):
    gk, G = _series("GEX_1d.csv", "gex")
    vk, V = _series("VIX_1d.csv", "close")
    nk, N = _series("VXN_1d.csv", "close")
    tk, T3 = _series("CBOE_vol_1d.csv", "vix3m")

    def prior(ks, S, d, lag=1, max_age=5):
        i = bisect.bisect_left(ks, d) - lag
        if i < 0:
            return None, None
        k = ks[i]
        return S[k], k

    out = {}
    rk = sorted(rng_by_day)
    for d in sessions:
        o = {}
        g, gd = prior(gk, G, d)
        if g is not None and _age(gd, d) <= 5:
            o["gex_pos"] = 1.0 if g > 0 else 0.0
            o["gex_lvl"] = g / 1e9
        v1, vd = prior(vk, V, d)
        v0, _ = prior(vk, V, d, 2)
        if v1 is not None and _age(vd, d) <= 5:
            o["vix"] = v1
            if v0:
                o["vix_chg"] = 100.0 * (v1 / v0 - 1.0)
            n1, nd = prior(nk, N, d)
            if n1 is not None and nd == vd:
                o["spread"] = n1 - v1
            t3, td = prior(tk, T3, d)
            if t3 is not None and td == vd:
                o["ts3"] = v1 / t3
        i = bisect.bisect_left(rk, d) - 1
        if i >= 60:
            x = rng_by_day[rk[i]]
            past = [rng_by_day[rk[j]] for j in range(max(0, i - 252), i)]
            o["rng_pct"] = float(np.mean(np.array(past) <= x))
        out[d] = o
    return out


def _age(a, b):
    import datetime as dt
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def span_of(day):
    for s, (a, z) in SP.items():
        if a <= day <= z:
            return s
    return None


def tstat(x):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return 0.0
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))))


def bucket_stats(L, Rg, fn, labels):
    """R a trade per bucket and span. fn(regime dict) -> bucket index or None."""
    res = {}
    for sp in SP:
        rows = [(fn(Rg.get(l["day"], {})), l["r"], l["pnl"]) for l in L if span_of(l["day"]) == sp]
        res[sp] = {}
        for b, lab in enumerate(labels):
            r = [x[1] for x in rows if x[0] == b]
            p = [x[2] for x in rows if x[0] == b]
            res[sp][lab] = {"n": len(r), "avgR": round(float(np.mean(r)), 3) if r else None, "net": round(sum(p)),
                            "t": round(tstat(r), 2)}
        res[sp]["none"] = sum(1 for x in rows if x[0] is None)
    return res


def h1_cuts(L, Rg, f, qs):
    v = [Rg.get(l["day"], {}).get(f) for l in L if span_of(l["day"]) == "H1"]
    v = [x for x in v if x is not None]
    return [float(np.quantile(v, q)) for q in qs]


def cell_defs(L, Rg):
    """Every bucket definition: singles (2 and 3 buckets) and pairs (2 x 2). -> list of (name, fn, labels)."""
    D = []
    single = {}
    for f in FEATS:
        if f == "gex_pos":
            fn = (lambda f: lambda r: None if r.get(f) is None else int(r[f]))(f)
            D.append((f"{f}", fn, ["neg", "pos"]))
            single[f] = (fn, 2, ["neg", "pos"], None)
            continue
        m, = h1_cuts(L, Rg, f, [0.5])
        fn2 = (lambda f, m: lambda r: None if r.get(f) is None else int(r[f] > m))(f, m)
        D.append((f"{f}|med {m:.3g}", fn2, ["lo", "hi"]))
        single[f] = (fn2, 2, ["lo", "hi"], m)
        a, b = h1_cuts(L, Rg, f, [1 / 3, 2 / 3])
        fn3 = (lambda f, a, b: lambda r: None if r.get(f) is None else 0 if r[f] <= a else 1 if r[f] <= b else 2)(f, a, b)
        D.append((f"{f}|terc {a:.3g}/{b:.3g}", fn3, ["lo", "mid", "hi"]))
    for f1, f2 in itertools.combinations(FEATS, 2):
        g1, _, l1, _ = single[f1]
        g2, _, l2, _ = single[f2]
        fn = (lambda g1, g2: lambda r: None if g1(r) is None or g2(r) is None else 2 * g1(r) + g2(r))(g1, g2)
        labs = [f"{f1}:{a}/{f2}:{b}" for a in l1 for b in l2]
        D.append((f"{f1} x {f2}", fn, labs))
    return D


def candidates(defs, stats):
    """On H1 only: for each definition, the best and the worst bucket (n >= 12 in H1); the rule = x1.25 best / x0.75 worst."""
    out = []
    for name, fn, labs in defs:
        h1 = stats[name]["H1"]
        ok = [(lab, h1[lab]) for lab in labs if h1[lab]["n"] >= 12]
        if len(ok) < 2:
            continue
        best = max(ok, key=lambda x: x[1]["avgR"])
        worst = min(ok, key=lambda x: x[1]["avgR"])
        gap = best[1]["avgR"] - worst[1]["avgR"]
        out.append({"def": name, "good": best[0], "bad": worst[0], "gap_h1": round(gap, 3)})
    return sorted(out, key=lambda x: -x["gap_h1"])


def holds(c, stats):
    """Direction check: good bucket beats bad bucket in H2 and in 2021-25 (avg R)."""
    o = {}
    for sp in ("H2", "2021-25"):
        g, b = stats[c["def"]][sp][c["good"]], stats[c["def"]][sp][c["bad"]]
        o[sp] = None if not g["n"] or not b["n"] else round(g["avgR"] - b["avgR"], 3)
        o[sp + "_n"] = (g["n"], b["n"])
    return o


def main():
    c = E.ctx()
    M = c["M"]
    rng_by_day = {str(d): float(M.h[s:e].max() - M.l[s:e].min()) for d, s, e in M.days}
    sessions = sorted(rng_by_day)
    cov = coverage(sessions)
    Rg = regimes(sessions, rng_by_day)
    U = E.trades()
    o0, _, L = E.evaluate(U=U, fund=True)
    base = E.short(o0)
    dmap = {d: k for k, (d, s, e) in enumerate(M.days)}
    # trade-level coverage
    tcov = {sp: {f: sum(1 for l in L if span_of(l["day"]) == sp and Rg.get(l["day"], {}).get(f) is not None) for f in FEATS}
            | {"trades": sum(1 for l in L if span_of(l["day"]) == sp)} for sp in SP}
    defs = cell_defs(L, Rg)
    stats = {name: bucket_stats(L, Rg, fn, labs) for name, fn, labs in defs}
    n_cells = sum(len(labs) for _, _, labs in defs)
    cands = candidates(defs, stats)
    for cd in cands:
        cd["check"] = holds(cd, stats)
    passing = [cd for cd in cands if (cd["check"]["H2"] or -1) > 0 and (cd["check"]["2021-25"] or -1) > 0]
    # size rules: top 6 H1 gaps + every direction-holding one (capped at 12), x1.25 good / x0.75 bad
    pick = []
    for cd in cands[:6] + passing:
        if cd not in pick:
            pick.append(cd)
    pick = pick[:12]
    fn_of = {name: fn for name, fn, _ in defs}
    lab_of = {name: labs for name, _, labs in defs}
    rules = []
    for cd in pick:
        fn, labs = fn_of[cd["def"]], lab_of[cd["def"]]
        gi, bi = labs.index(cd["good"]), labs.index(cd["bad"])
        for up, dn in ((1.25, 0.75),):
            def mfn(t, row, fn=fn, gi=gi, bi=bi, up=up, dn=dn):
                b = fn(Rg.get(t["day"], {}))
                return up if b == gi else dn if b == bi else 1.0
            UU = [{**u, "m": mfn(u, None)} for u in U]
            o, _, LL = E.evaluate(U=UU, fund=True)
            s = E.short(o, o0)
            s["placebo"] = E.placebo(UU, L, n=200)
            s["gate"] = E.gate(s)
            s["rule"] = f"{cd['def']}: {cd['good']} x{up}, {cd['bad']} x{dn}"
            s["n_up"] = {sp: sum(1 for u in UU if span_of(u["day"]) == sp and u["m"] > 1) for sp in SP}
            s["n_dn"] = {sp: sum(1 for u in UU if span_of(u["day"]) == sp and u["m"] < 1) for sp in SP}
            rules.append(s)
            print(E.line(s["rule"], s), "| d_fund", s.get("d_fund"), "| placebo", s["placebo"], "| gate", s["gate"], flush=True)
    res = {"coverage": cov, "trade_coverage": tcov, "base": base, "n_defs": len(defs), "n_cells": n_cells,
           "stats": stats, "candidates": cands, "direction_holds": [cd["def"] + " " + cd["good"] + ">" + cd["bad"] for cd in passing],
           "rules": rules}
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1)
    print("defs", len(defs), "cells", n_cells, "candidates", len(cands), "direction holds", len(passing))
    for cd in cands[:25]:
        print(cd)


def pct():
    """Adaptive cut: VIX and VXN-VIX as a percentile of the 252 sessions before (H2 sits outside H1's absolute cuts)."""
    c = E.ctx()
    M = c["M"]
    rng = {str(d): float(M.h[s:e].max() - M.l[s:e].min()) for d, s, e in M.days}
    ses = sorted(rng)
    Rg = regimes(ses, rng)
    for f in ("vix", "spread"):
        vals = [(d, Rg[d].get(f)) for d in ses]
        for i, (d, v) in enumerate(vals):
            past = [x for _, x in vals[max(0, i - 252):i] if x is not None]
            if v is not None and len(past) >= 60:
                Rg[d][f + "_p"] = float(np.mean(np.array(past) <= v))
    L = E.lit_size(E.trades())
    hi = lambda r, k: None if r.get(k) is None else int(r[k] > 0.5)
    defs = [("vix_p", lambda r: hi(r, "vix_p"), ["lo", "hi"]), ("spread_p", lambda r: hi(r, "spread_p"), ["lo", "hi"]),
            ("vix_p x spread_p", lambda r: None if hi(r, "vix_p") is None or hi(r, "spread_p") is None
             else 2 * hi(r, "vix_p") + hi(r, "spread_p"), ["vlo/slo", "vlo/shi", "vhi/slo", "vhi/shi"])]
    out = {n: bucket_stats(L, Rg, fn, labs) for n, fn, labs in defs}
    json.dump(out, open(OUT.replace(".json", "_pct.json"), "w", encoding="utf-8"), indent=1)
    for n in out:
        for sp in SP:
            print(n, sp, {b: (v["n"], v["avgR"]) for b, v in out[n][sp].items() if b != "none"})


if __name__ == "__main__":
    pct() if sys.argv[1:] == ["pct"] else main()
