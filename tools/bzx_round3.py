"""BLITZ edge round 3 (coordinator 2026-10-30 13:00): C3 robustness and a momentum-regime day gate. Research only.
research/writeups/blitz-edge-2026-10-30b.md (round 3 section), runs bzx_c3_robust / bzx_regime_gate.

    python -X utf8 tools/bzx_round3.py seeds     # today / v2 / C3 / C1 / (a) size alone / (b) give-up alone on 20 MC seeds
    python -X utf8 tools/bzx_round3.py c3grid    # the neighbour grid; the H1-only selection rules are fixed and written
                                                 # to research/scalp/bzx_c3_pick.json BEFORE H2 / 2021-25 are computed
    python -X utf8 tools/bzx_round3.py placebo   # (a) and (b) alone on random directions (8 seeds)
    python -X utf8 tools/bzx_round3.py regime    # the momentum-regime gate (market-only day measure known before 11:00)
"""
from __future__ import annotations

import collections
import itertools
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import bzx_edge as X  # noqa: E402

A, N, K, BS = X.A, X.N, X.K, X.BS
OUT = X.OUT
FZ0, EZ0, EZ_LB = X.FZ0, X.EZ0, X.EZ_LB
C3 = {**FZ0, "q1": 1, "q2": 2, "q1b": 1, "q2b": 2, "rq": 0.25, "stuck_k": 1.0}
C1 = {**FZ0, "q1": 1, "q2": 3, "q1b": 2, "q2b": 3, "rq": 0.5}
CFG = {"today": (EZ0, FZ0, False), "v2": (EZ_LB, FZ0, True), "C3": (EZ_LB, C3, True), "C1": (EZ_LB, C1, True),
       "a: later-break funded size alone": (EZ_LB, {k: v for k, v in C3.items() if k != "stuck_k"}, True),
       "b: give-up at 1x alone": (EZ_LB, {**FZ0, "stuck_k": 1.0}, True)}
SPS = ("H1", "H2", "R")


def slot(ez, fz, lb, sp, seed, n=1000, TTx=None):
    T, S = X.SP[sp] if TTx is None else TTx[sp]
    Te = X.lb_trades(T) if lb else T
    return X.lifeX(Te, T, S, ez, fz, n=n, seed=seed)["life_pm"]


def _sj(a):
    name, sp, seed = a
    ez, fz, lb = CFG[name]
    return name, sp, seed, slot(ez, fz, lb, sp, seed)


def pool(fn, jobs):
    from multiprocessing import Pool
    with Pool(X.PROCS) as P:
        return P.map(fn, jobs, chunksize=4)


def cmd_seeds(seeds=range(23, 43)):
    t0 = time.time()
    X.prep()
    R = pool(_sj, [(nm, sp, s) for nm in CFG for sp in SPS for s in seeds])
    v = collections.defaultdict(dict)
    for nm, sp, s, x in R:
        v[(nm, sp)][s] = x
    out = {"seeds": list(seeds), "rows": {}}
    for nm in CFG:
        row = {}
        for sp in SPS:
            a = np.array([v[(nm, sp)][s] for s in seeds], float)
            d = a - np.array([v[("v2", sp)][s] for s in seeds], float)
            d0 = a - np.array([v[("today", sp)][s] for s in seeds], float)
            row[sp] = {"mean": round(float(a.mean())), "min": int(a.min()), "max": int(a.max()), "d_v2_mean": round(float(d.mean()), 1),
                       "d_v2_min": int(d.min()), "d_v2_max": int(d.max()), "seeds_better_than_v2": int((d > 0).sum()), "seeds_tied": int((d == 0).sum()),
                       "d_today_mean": round(float(d0.mean()), 1), "seeds_better_than_today": int((d0 > 0).sum())}
        out["rows"][nm] = row
        print(f"{nm:34s} " + " | ".join(f"{sp} ${row[sp]['mean']} (vs v2 {row[sp]['d_v2_mean']:+.1f}, {row[sp]['d_v2_min']:+d}..{row[sp]['d_v2_max']:+d}, "
                                          f"better {row[sp]['seeds_better_than_v2']}/20, vs today {row[sp]['d_today_mean']:+.1f})" for sp in SPS), flush=True)
    A.dump(out, os.path.join(OUT, "bzx_c3_seeds.json"))
    print(f"done {time.time() - t0:.0f}s")


# ================================================================================================ C3 neighbour grid
RQ = (0.15, 0.2, 0.25, 0.3, 0.35)
SK = (0.75, 1.0, 1.25, 1.5)
QL = (2, 3)


def gz(rq, sk, q2):
    return {**FZ0, "q1": 1, "q2": q2, "q1b": 1, "q2b": q2, "rq": rq, "stuck_k": sk}


def _gj(a):
    key, sp, seed = a
    if key == "v2":
        return key, sp, seed, slot(EZ_LB, FZ0, True, sp, seed)
    rq, sk, q2 = key
    return key, sp, seed, slot(EZ_LB, gz(rq, sk, q2), True, sp, seed)


def cmd_c3grid(seeds=range(23, 33)):
    """Selection rules, fixed before any H2 / 2021-25 number of this grid is computed (H1 only, 10 seeds, vs v2 on the
    same seed):  A "plateau" = argmax over the grid of min(median d_H1) over the cell and its neighbours (rq +-1 step,
    give-up +-1 step, the other later-break micros);  B "worst seed" = argmax of min over seeds of d_H1;  C "median" =
    argmax of the median d_H1."""
    t0 = time.time()
    X.prep()
    keys = [(rq, sk, q2) for rq in RQ for sk in SK for q2 in QL]
    R = pool(_gj, [(k, "H1", s) for k in keys + ["v2"] for s in seeds])
    h1 = collections.defaultdict(dict)
    for k, sp, s, x in R:
        h1[k if k == "v2" else tuple(k)][s] = x
    med, worst = {}, {}
    for k in keys:
        d = np.array([h1[k][s] - h1["v2"][s] for s in seeds], float)
        med[k], worst[k] = float(np.median(d)), float(d.min())

    def nbrs(k):
        rq, sk, q2 = k
        i, j = RQ.index(rq), SK.index(sk)
        out = [k, (rq, sk, 5 - q2)]
        for di in (-1, 1):
            if 0 <= i + di < len(RQ):
                out.append((RQ[i + di], sk, q2))
        for dj in (-1, 1):
            if 0 <= j + dj < len(SK):
                out.append((rq, SK[j + dj], q2))
        return out
    plat = {k: min(med[x] for x in nbrs(k)) for k in keys}
    picks = {"A_plateau": max(keys, key=lambda k: (plat[k], med[k])), "B_worst_seed": max(keys, key=lambda k: (worst[k], med[k])),
             "C_median": max(keys, key=lambda k: (med[k], worst[k]))}
    rec = {"built": time.strftime("%Y-%m-%d %H:%M:%S"), "rule": cmd_c3grid.__doc__, "seeds": list(seeds),
           "picks": {r: {"rq": k[0], "stuck_k": k[1], "later_micros": k[2], "h1_median": med[k], "h1_worst": worst[k], "h1_plateau": plat[k]} for r, k in picks.items()},
           "c3_h1": {"median": med[(0.25, 1.0, 2)], "worst": worst[(0.25, 1.0, 2)], "plateau": plat[(0.25, 1.0, 2)]}}
    A.dump(rec, os.path.join(OUT, "bzx_c3_pick.json"))          # written BEFORE H2 / 2021-25 are computed
    print("H1-only picks (written before H2 / 2021-25):", json.dumps(rec["picks"]), "C3:", rec["c3_h1"], flush=True)
    for q2 in QL:
        print(f"H1 median d vs v2 (later {q2} micros); rows give-up {SK}, cols room share {RQ}")
        for sk in SK:
            print(f"   {sk:4}: " + " ".join(f"{med[(rq, sk, q2)]:+6.1f}" for rq in RQ))
    R2 = pool(_gj, [(k, sp, s) for k in keys + ["v2"] for sp in ("H2", "R") for s in seeds])
    oth = collections.defaultdict(lambda: collections.defaultdict(dict))
    for k, sp, s, x in R2:
        oth[sp][k if k == "v2" else tuple(k)][s] = x
    grid = []
    for k in keys:
        row = {"rq": k[0], "stuck_k": k[1], "later_micros": k[2], "H1_med": med[k], "H1_worst": worst[k], "H1_plateau": plat[k]}
        for sp in ("H2", "R"):
            d = np.array([oth[sp][k][s] - oth[sp]["v2"][s] for s in seeds], float)
            row[f"{sp}_med"], row[f"{sp}_worst"], row[f"{sp}_better"] = float(np.median(d)), float(d.min()), int((d > 0).sum())
        grid.append(row)
    rec["grid"] = grid
    for q2 in QL:
        for sp in ("H2", "R"):
            print(f"{sp} median d vs v2 (later {q2} micros); rows give-up {SK}, cols room share {RQ}")
            for sk in SK:
                print(f"   {sk:4}: " + " ".join(f"{next(r for r in grid if r['rq'] == rq and r['stuck_k'] == sk and r['later_micros'] == q2)[sp + '_med']:+6.1f}" for rq in RQ))
    for r_, k in picks.items():
        g = next(r for r in grid if (r["rq"], r["stuck_k"], r["later_micros"]) == k)
        print(f"pick {r_}: {k} -> H1 med {g['H1_med']:+.1f} worst {g['H1_worst']:+.0f} | H2 med {g['H2_med']:+.1f} worst {g['H2_worst']:+.0f} better {g['H2_better']}/10 | "
              f"R med {g['R_med']:+.1f} worst {g['R_worst']:+.0f} better {g['R_better']}/10", flush=True)
    nall = sum(1 for r in grid if r["H1_med"] > 0 and r["H2_med"] > 0 and r["R_med"] > 0)
    rec["n_all_median_positive"] = nall
    print(f"{nall} of {len(grid)} grid cells have a positive median gain in H1, H2 and 2021-25")
    A.dump(rec, os.path.join(OUT, "bzx_c3_grid.json"))
    print(f"done {time.time() - t0:.0f}s")


# ================================================================================================ random directions for (a) / (b)
PL = {}


def _pj(a):
    name, seed = a
    if seed not in PL:
        TTp = K.trades({}, "lit+atlas", placebo=seed)
        for tf in (1, 5):
            A.attach(N.bars(tf), TTp[tf])
        PL[seed] = {sp: K.span(TTp, sp, tf) for sp, tf in K.SPANS}
    ez, fz, lb = CFG[name]
    return name, seed, {sp: slot(ez, fz, lb, sp, 23, n=600, TTx=PL[seed]) for sp in SPS}


def cmd_placebo(seeds=range(8)):
    t0 = time.time()
    X.prep()
    names = ["v2", "a: later-break funded size alone", "b: give-up at 1x alone", "C3"]
    R = pool(_pj, [(nm, s) for s in seeds for nm in names])
    out = {}
    for nm in names:
        out[nm] = {sp: round(float(np.mean([r[2][sp] for r in R if r[0] == nm]))) for sp in SPS}
    for nm in names:
        print(f"random directions, {nm:34s} " + " | ".join(f"{sp} ${out[nm][sp]} ({out[nm][sp] - out['v2'][sp]:+d} vs v2)" for sp in SPS), flush=True)
    A.dump(out, os.path.join(OUT, "bzx_c3_placebo.json"))
    print(f"done {time.time() - t0:.0f}s")


def _pcj(a):
    kind, arg, fz = a
    if kind == "seed":
        return kind, arg, {sp: [slot(EZ_LB, FZ0, True, sp, arg), slot(EZ_LB, fz, True, sp, arg)] for sp in SPS}
    if kind == "shuf":
        r = X._fjob2(("shuf", EZ_LB, fz, 600, True, 23, 100 + arg))
        return kind, arg, {sp: r[sp]["slot"]["life_pm"] for sp in SPS}
    r = X._sjob(("pick", kind, arg, fz, 600))
    return kind, arg, (r["Y"] if kind == "year" else {sp: [r[sp]["base"], r[sp]["cand"]] for sp in SPS})


def cmd_pickcheck():
    """the H1-rule pick of the C3 grid (bzx_c3_pick.json): 20 seeds, random directions (8), shuffled first / later labels
    (20), +1 / +2 ticks, 1 bar late, 2021-25 by year; and one step beyond the grid (room share 0.5)."""
    t0 = time.time()
    X.prep()
    p = json.load(open(os.path.join(OUT, "bzx_c3_pick.json")))["picks"]["A_plateau"]
    fz = gz(p["rq"], p["stuck_k"], p["later_micros"])
    out = {"fz": fz, "beyond": {}}
    jobs = [("seed", s, fz) for s in range(23, 43)] + [("placebo", s, fz) for s in range(8)] + [("shuf", k, fz) for k in range(20)]
    jobs += [("slip", 1, fz), ("slip", 2, fz), ("late", 1, fz)] + [("year", y, fz) for y in ("2022", "2023", "2024", "2025")]
    beyond = gz(0.5, p["stuck_k"], p["later_micros"])
    jobs += [("seed", s, beyond) for s in range(23, 28)]
    R = pool(_pcj, jobs)
    n_pick = 20 + 8 + 20 + 3 + 4
    Rp, Rb = R[:n_pick], R[n_pick:]
    sd = [r[2] for r in Rp if r[0] == "seed"]
    out["seeds"] = {sp: {"d_mean": round(float(np.mean([x[sp][1] - x[sp][0] for x in sd])), 1), "d_min": min(x[sp][1] - x[sp][0] for x in sd),
                         "better": sum(x[sp][1] > x[sp][0] for x in sd)} for sp in SPS}
    pl = [r[2] for r in Rp if r[0] == "placebo"]
    out["placebo"] = {sp: {"base": round(float(np.mean([x[sp][0] for x in pl]))), "pick": round(float(np.mean([x[sp][1] for x in pl])))} for sp in SPS}
    sh = [r[2] for r in Rp if r[0] == "shuf"]
    real600 = X._fjob2(("real", EZ_LB, fz, 600, True, 23, None))
    out["shuffled_labels"] = {sp: {"mean": round(float(np.mean([x[sp] for x in sh]))), "real": real600[sp]["slot"]["life_pm"],
                                   "share_ge": round(float(np.mean([x[sp] >= real600[sp]["slot"]["life_pm"] for x in sh])), 2)} for sp in SPS}
    for r in Rp:
        if r[0] in ("slip", "late"):
            out[f"{r[0]}{r[1]}"] = r[2]
        if r[0] == "year":
            out[f"y{r[1]}"] = [r[2]["base"], r[2]["cand"]]
    bd = [r[2] for r in Rb]
    out["beyond"] = {sp: {"d_mean": round(float(np.mean([x[sp][1] - x[sp][0] for x in bd])), 1), "better": sum(x[sp][1] > x[sp][0] for x in bd)} for sp in SPS}
    out["eval"] = {sp: X.eval_scorex(X.lb_trades(T), S, EZ_LB) for sp, (T, S) in X.SP.items()}
    out["funded_only"] = {sp: {"pick": X.funded_scorex(T, S, fz), "today": X.funded_scorex(T, S, FZ0)} for sp, (T, S) in X.SP.items()}
    for k, v in out.items():
        print(k, json.dumps(v), flush=True)
    A.dump(out, os.path.join(OUT, "bzx_c3_pickcheck.json"))
    print(f"done {time.time() - t0:.0f}s")


# ================================================================================================ momentum-regime day gate
def regime_measures(windows=(20, 40)):
    """day-level momentum regime from the MARKET only (CME NQ 5m bars, every session 2021-11 .. 2026-10), known before the
    day's open (uses the prior N sessions only):
      ac<N>  pooled lag-1 autocorrelation of the 13 RTH 30-minute returns (pairs within a day)
      vr<N>  variance ratio: mean((sum of a day's 30-min returns)^2) / (13 x mean(30-min return^2))  (> 1 = moves persist)
      ft<N>  share of the days with a noise-band break at the 11:00 / 11:30 / 12:00 check whose 16:00 close went further the
             break's way (the band = the BLITZ noise band, 1.0 x sigma; every check, traded or not; >= 5 such days)
    -> {name: {date: value}}"""
    B = N.bars(5)
    m, o, c, dd = B["mod"], B["o"], B["c"], B["day"]
    dates = list(B["dates"])
    starts = np.r_[0, np.where(np.diff(dd) != 0)[0] + 1]
    ends = np.r_[starts[1:], len(dd)]
    F = N.signals(B, 1.0, 30, (630, 930), 1.5)
    first_brk = {}
    for q in range(len(F["sig"])):
        if F["mod"][q] in (660, 690, 720):
            di = int(F["day"][q])
            if di not in first_brk:
                first_brk[di] = (int(F["sig"][q]), float(F["dir"][q]))
    rets, follow = {}, {}
    for s, e in zip(starts, ends):
        di = int(dd[s])
        idx = np.arange(s, e)
        mm = m[idx]
        op = idx[mm == 570]
        if not len(op):
            continue
        marks = [570 + 30 * k - 5 for k in range(1, 14)]
        pos = {int(m[i]): i for i in idx}
        if not all(x in pos for x in marks):
            continue
        cl = np.array([c[pos[x]] for x in marks])
        px = np.r_[o[op[0]], cl]
        rets[di] = np.diff(np.log(px))
        if di in first_brk:
            i, d = first_brk[di]
            follow[di] = 1.0 if d * (cl[-1] - c[i]) > 0 else 0.0
    out = {}
    days = sorted(set(int(x) for x in dd))
    rdays = [x for x in days if x in rets]                      # complete RTH sessions (Sunday-evening dates have none)
    for Nw in windows:
        ac, vr, ft = {}, {}, {}
        for k, di in enumerate(rdays):
            prev = rdays[max(0, k - Nw):k]
            if len(prev) < Nw:
                continue
            R = np.array([rets[x] for x in prev])
            a, b = R[:, :-1].ravel(), R[:, 1:].ravel()
            ac[dates[di]] = float(np.corrcoef(a, b)[0, 1])
            vr[dates[di]] = float(np.mean(R.sum(1) ** 2) / (13.0 * np.mean(R ** 2)))
            fp = [follow[x] for x in prev if x in follow]
            if len(fp) >= 5:
                ft[dates[di]] = float(np.mean(fp))
        out[f"ac{Nw}"], out[f"vr{Nw}"], out[f"ft{Nw}"] = ac, vr, ft
    return out


def gate_view(T, S, keep, usd=150.0):
    """$150 a trade (integer micros) on the kept trades + trades / week, % weeks 2+, PF, net, $ / month, max DD."""
    Tk = [t for t, k in zip(T, keep) if k]
    Ts = X.store_trades(Tk)
    p = np.array([t["pnl"] for t in Ts]) if Ts else np.zeros(1)
    eq = np.cumsum(p)
    gl = -p[p < 0].sum()
    return {"n": len(Ts), "tpw": round(len(Ts) / (len(S) / 5), 2), "wk2": K.wk2(Tk, S), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else 99.0,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(S) / 21)),
            "dd": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())), "share_on": round(float(np.mean(keep)), 3) if len(keep) else None}


def half_view(T, S, keep, usd=150.0):
    m = np.where(np.asarray(keep, bool), 1.0, 0.5)
    v = A.rview(T, S, m, usd=usd)
    return {k: v[k] for k in ("n", "tpw", "pf", "net", "per_month", "dd", "r_per_risk")}


def cmd_regime(n_shuf=20):
    """the momentum-regime gate. Pick rules fixed BEFORE any H2 / 2021-25 number (H1 only, skip mode = no BLITZ trade on an
    'off' day): G1 = the gate with the highest H1 $ / month at $150 among gates with >= 2 trades / week in H1 (ties: the
    looser one); G2 = the strictest gate (the highest H1 percentile cut) whose H1 $ / month is >= 95% of the ungated H1 and
    >= 2 trades / week (ties: G1's order). Gates: ac / vr / ft x 20 / 40 sessions x 'on' at >= the 20 / 35 / 50 / 65 / 80th
    percentile of the measure over 2026 H1 BLITZ trade days."""
    t0 = time.time()
    X.prep()
    M = regime_measures()
    SPv = X.SP
    H1T = SPv["H1"][0]
    gates = []
    for nm, pc in itertools.product(sorted(M), (20, 35, 50, 65, 80)):
        vals = [M[nm].get(t["day"]) for t in H1T]
        vals = np.array([v for v in vals if v is not None], float)
        gates.append({"measure": nm, "pct": pc, "cut": float(np.percentile(vals, pc))})
    keepf = lambda T, g: [(M[g["measure"]].get(t["day"]) is None) or (M[g["measure"]][t["day"]] >= g["cut"]) for t in T]
    base = {sp: gate_view(T, S, [True] * len(T)) for sp, (T, S) in SPv.items()}
    T1, S1 = SPv["H1"]
    for g in gates:
        g["H1"] = gate_view(T1, S1, keepf(T1, g))
    ok = [g for g in gates if g["H1"]["tpw"] >= 2.0]
    g1 = max(ok, key=lambda g: (g["H1"]["per_month"], -g["pct"]))
    ok2 = [g for g in ok if g["H1"]["per_month"] >= 0.95 * base["H1"]["per_month"]]
    g2 = max(ok2, key=lambda g: (g["pct"], g["H1"]["per_month"])) if ok2 else None
    rec = {"built": time.strftime("%Y-%m-%d %H:%M:%S"), "rule": cmd_regime.__doc__, "G1": {k: g1[k] for k in ("measure", "pct", "cut", "H1")},
           "G2": {k: g2[k] for k in ("measure", "pct", "cut", "H1")} if g2 else None, "base_H1": base["H1"]}
    A.dump(rec, os.path.join(OUT, "bzx_regime_pick.json"))     # written BEFORE H2 / 2021-25 are computed
    print("H1-only picks (written before H2 / 2021-25):", json.dumps(rec, default=str)[:900], flush=True)
    # every gate on every span (skip and half size)
    for g in gates:
        for sp, (T, S) in SPv.items():
            kp = keepf(T, g)
            g[sp] = gate_view(T, S, kp)
            g[sp + "_half"] = half_view(T, S, kp)
    bh = {sp: half_view(T, S, [True] * len(T)) for sp, (T, S) in SPv.items()}
    print("base", json.dumps(base), flush=True)
    print(f"{'gate':22s} " + " | ".join(f"{sp}: on% tpw PF $/mo (half $/mo)" for sp in SPS))
    for g in gates:
        print(f"{g['measure']:5s} >= p{g['pct']:<2d} {g['cut']:+.4f} " + " | ".join(
            f"{sp} {g[sp]['share_on']} {g[sp]['tpw']} {g[sp]['pf']} ${g[sp]['per_month']} (${g[sp + '_half']['per_month']})" for sp in SPS), flush=True)
    good = [g for g in gates if all(g[sp]["per_month"] > base[sp]["per_month"] for sp in SPS)]
    good_h = [g for g in gates if all(g[sp + "_half"]["per_month"] > bh[sp]["per_month"] for sp in SPS)]
    print(f"skip gates better in $ in H1, H2 and 2021-25: {len(good)} of {len(gates)}; half-size gates: {len(good_h)} of {len(gates)}")
    # shuffled-day control: the measure's values permuted across the span's dates (20 seeds), the same cut
    rng = np.random.default_rng(31)
    ctrl = {}
    for gk, g in (("G1", g1), ("G2", g2)):
        if g is None:
            continue
        res = collections.defaultdict(list)
        cnt = []
        for k in range(n_shuf):
            Mp = {}
            for nm in M:
                ds = list(M[nm].keys())
                vs = rng.permutation(list(M[nm].values()))
                Mp[nm] = dict(zip(ds, vs))
            kf = lambda T, gg: [(Mp[gg["measure"]].get(t["day"]) is None) or (Mp[gg["measure"]][t["day"]] >= gg["cut"]) for t in T]
            for sp, (T, S) in SPv.items():
                res[sp].append(gate_view(T, S, kf(T, g))["per_month"])
            cnt.append(sum(1 for gg in gates if all(gate_view(T, S, kf(T, gg))["per_month"] > base[sp]["per_month"] for sp, (T, S) in SPv.items())))
        ctrl[gk] = {sp: {"real": g[sp]["per_month"], "shuf_mean": round(float(np.mean(res[sp]))), "share_ge": round(float(np.mean(np.array(res[sp]) >= g[sp]["per_month"])), 2)}
                    for sp in SPS}
        ctrl[gk]["grid_count_shuffled_mean"] = round(float(np.mean(cnt)), 1)
        print(gk, g["measure"], g["pct"], "shuffled days:", json.dumps(ctrl[gk]), flush=True)
    # per year (2021-25) + eval / slot for the picks
    T5, S5 = SPv["R"]
    yrs = {}
    for gk, g in (("G1", g1), ("G2", g2)):
        if g is None:
            continue
        yrs[gk] = {}
        for y in ("2021", "2022", "2023", "2024", "2025"):
            Ty = [t for t in T5 if t["day"][:4] == y]
            Sy = [d for d in S5 if d[:4] == y]
            yrs[gk][y] = {"base": gate_view(Ty, Sy, [True] * len(Ty)), "gate": gate_view(Ty, Sy, keepf(Ty, g))}
        print(gk, "years:", {y: (v["base"]["per_month"], v["gate"]["per_month"], v["gate"]["tpw"]) for y, v in yrs[gk].items()}, flush=True)
    evs = {}
    for gk, g in (("none", None), ("G1", g1), ("G2", g2)):
        if gk != "none" and g is None:
            continue
        evs[gk] = {}
        for sp, (T, S) in SPv.items():
            Tk = T if g is None else [t for t, k in zip(T, keepf(T, g)) if k]
            evs[gk][sp] = {"ev": X.eval_scorex(X.lb_trades(Tk), S, EZ_LB), "slot_v2": X.lifeX(X.lb_trades(Tk), Tk, S, EZ_LB, FZ0, n=1000)["life_pm"]}
        print(gk, "eval / slot (v2 eval, today's funded):", json.dumps({sp: (evs[gk][sp]["ev"]["p10"], evs[gk][sp]["ev"]["f10"], evs[gk][sp]["slot_v2"]) for sp in SPS}), flush=True)
    rec.update(gates=gates, base=base, base_half=bh, n_good_skip=len(good), n_good_half=len(good_h), control=ctrl, years=yrs, eval_slot=evs)
    A.dump(rec, os.path.join(OUT, "bzx_regime.json"))
    print(f"done {time.time() - t0:.0f}s")


def cmd_save():
    from tools import runlib as rl
    X.prep()
    J = lambda n: json.load(open(os.path.join(OUT, n), encoding="utf-8"))
    SD, GR, PC, PL, RG = J("bzx_c3_seeds.json"), J("bzx_c3_grid.json"), J("bzx_c3_pickcheck.json"), J("bzx_c3_placebo.json"), J("bzx_regime.json")
    B1, B5 = N.bars(1), N.bars(5)
    sess = sorted(set(N.sessions(B5, "R")) | set(N.sessions(B1, "H1")) | set(N.sessions(B1, "H2")))
    allT = X.SP["R"][0] + X.SP["H1"][0] + X.SP["H2"][0]
    tags = ["scalp", "blitz", "account_c", "25k", "bzx"]
    wu = "blitz-edge-2026-10-30b"
    r = SD["rows"]
    f = lambda nm: " / ".join(f"{r[nm][sp]['d_v2_mean']:+.1f} ({r[nm][sp]['seeds_better_than_v2']}/20)" for sp in SPS)
    p = GR["picks"]["A_plateau"]
    v = (f"20 Monte Carlo seeds, slot $ a month vs v2 (H1 / H2 / 2021-25, seeds better): C3 {f('C3')}; C1 {f('C1')}; (a) the later-break funded size alone "
         f"{f('a: later-break funded size alone')}; (b) the give-up line at 1x alone {f('b: give-up at 1x alone')}. Random directions: (b) alone "
         f"{PL['b: give-up at 1x alone']['H1'] - PL['v2']['H1']:+d} / {PL['b: give-up at 1x alone']['H2'] - PL['v2']['H2']:+d} / "
         f"{PL['b: give-up at 1x alone']['R'] - PL['v2']['R']:+d} = fee saving, not edge. H1-only selection rules (plateau / worst seed / median, written "
         f"before H2 / 2021-25) all pick room share {p['rq']}, give-up {p['stuck_k']}x, later {p['later_micros']} micros (not C3): 20 seeds "
         f"{PC['seeds']['H1']['d_mean']:+} / {PC['seeds']['H2']['d_mean']:+} / {PC['seeds']['R']['d_mean']:+} (20/20 each), but +1 tick 2021-25 "
         f"{PC['slip1']['R'][1] - PC['slip1']['R'][0]:+d}, 1 bar late H2 {PC['late1']['H2'][1] - PC['late1']['H2'][0]:+d}, 2024 {PC['y2024'][1] - PC['y2024'][0]:+d}, "
         f"room share 0.5 next door H2 {PC['beyond']['H2']['d_mean']:+} (0/5), shuffled labels beat it in H2 ({PC['shuffled_labels']['H2']['share_ge']}). "
         f"Not an adopt-candidate.")
    mt = lambda t: 2.0 if X.is_later(t) else 1.0
    rl.save("bzx_c3_robust", "BLITZ funded 25K: C3 robustness (20 seeds, neighbour grid, H1-only selection, size vs give-up line) - promising, not adopted",
            "risk", "Coordinator round 3: can the funded later-break size + give-up line become an adopt-candidate?",
            params={**K.TODAY}, sizing={"usd_per_trade": 150.0, "x": "2 on a later break, 1 on a first break", "eval_25k": EZ_LB, "funded_c3": C3,
                                        "funded_rule_pick": gz(p["rq"], p["stuck_k"], p["later_micros"])},
            trades=X.store_trades(allT, mt), scored=rl.score(X.store_trades(allT, mt), sess), status="promising", verdict=v,
            notes="tools/bzx_round3.py seeds / c3grid / placebo / pickcheck", writeup=wu, tags=tags + ["funded", "sizing"])
    g = RG["G1"]
    gg = next(x for x in RG["gates"] if x["measure"] == g["measure"] and x["pct"] == g["pct"])
    M = regime_measures()
    keep = lambda t: 1.0 if (M[g["measure"]].get(t["day"]) is None or M[g["measure"]][t["day"]] >= g["cut"]) else 0.0
    v = (f"Momentum-regime day gate from the market only (30-min return autocorrelation, variance ratio, 11:00-12:00 band-break follow-through to the "
         f"close; 20 / 40 sessions; known before the open): 0 of 30 skip gates and 0 of 30 half-size gates beat today in $ in H1, H2 and 2021-25. "
         f"H1-only pick {g['measure']} >= H1 p{g['pct']}: $ a month at $150 {gg['H1']['per_month']} / {gg['H2']['per_month']} / {gg['R']['per_month']} "
         f"(today {RG['base']['H1']['per_month']} / {RG['base']['H2']['per_month']} / {RG['base']['R']['per_month']}), trades a week "
         f"{gg['H1']['tpw']} / {gg['H2']['tpw']} / {gg['R']['tpw']}; shuffled days do better in 2021-25 ({RG['control']['G1']['R']['share_ge']}). "
         f"2026 H2 reads as a LOW-momentum market on these measures, yet BLITZ made PF 1.62 there: the market regime does not explain BLITZ's 2026 vs "
         f"2021-25 gap. Rejected.")
    rl.save("bzx_regime_gate", "BLITZ momentum-regime day gate (market autocorrelation / variance ratio / break follow-through) - rejected", "filters",
            "Coordinator round 3: trade BLITZ only when intraday moves persist (a market-only regime known before 11:00)?",
            params={**K.TODAY, "gate": {k: g[k] for k in ("measure", "pct", "cut")}}, sizing={"usd_per_trade": 150.0},
            trades=X.store_trades(allT, keep), scored=rl.score(X.store_trades(allT, keep), sess), status="rejected", verdict=v,
            notes="tools/bzx_round3.py regime", writeup=wu, tags=tags + ["filters", "regime"])
    print("-> runs bzx_c3_robust, bzx_regime_gate")


if __name__ == "__main__":
    a = sys.argv[1:]
    {"seeds": cmd_seeds, "c3grid": cmd_c3grid, "placebo": cmd_placebo, "pickcheck": cmd_pickcheck, "regime": cmd_regime, "save": cmd_save}[a[0]]()
