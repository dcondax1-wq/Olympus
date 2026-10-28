"""BLITZ = the noise-area (NA) momentum scalp (research/writeups/scalp-momentum.md "na_scalp"), turned toward MFFU money
(owner 2026-10-28). research/writeups/scalp-na-mffu.md. Paper research only: no engine / live / dashboard file is touched.

Protocol (as scalp-momentum.md): every grid is fixed before it is run; a variant is PICKED on 2026 H1 (1m bars) only, by the
t-stat of its average net R with >= 5 trades a week; 2026 H2 (Jul-Oct 16, 1m) is the check; 2021-25 (the same rule on 5m
bars: the noise band and the check-bar closes are identical on 1m and 5m, only the fills are coarser) is the reference.
Costs: $1.90 a micro + 1 tick on every market / stop fill, limits only when traded through, same-bar tie = loss.

    python -X utf8 tools/scalp_na.py filters     # stage 1: filter families -> research/scalp/na_filters.json
    python -X utf8 tools/scalp_na.py exits       # stage 2: exits on the stage-1 pick -> research/scalp/na_exits.json
    python -X utf8 tools/scalp_na.py sizing      # stage 3: MFFU eval / funded sizing -> research/scalp/na_sizing.json
    python -X utf8 tools/scalp_na.py combos      # stage 4: with ATLAS (25K) and LIT (50K) -> research/scalp/na_combos.json
    python -X utf8 tools/scalp_na.py save        # runs scalp_na_* (tools/runlib) + research/scalp/na_best_trades.json
"""
from __future__ import annotations

import itertools
import json
import os
import sys
import time
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import scalp_na_lib as N  # noqa: E402

warnings.filterwarnings("ignore")
OUT = os.path.join(ROOT, "research", "scalp")
JUDGE = (("H1", 1), ("H2", 1), ("R", 5), ("2025", 5), ("2021-24", 5))
MIN_TPW = 5.0


# ================================================================================================ stage 1: filters
def _f(fn):
    return fn


def filter_specs():
    """(family, name, mask_fn) - fixed before the run. mask_fn(F) -> bool array over the NA candidates."""
    G = [("base", "none", None)]
    for x in (16, 18, 20, 22, 24, 26):
        G.append(("vxn", f"vxn>={x}", (lambda x: lambda F: F["vxn"] >= x)(x)))
    for x in (14, 16, 18, 20, 22):
        G.append(("vix", f"vix>={x}", (lambda x: lambda F: F["vix"] >= x)(x)))
    for x in (0.9, 0.95, 1.0, 1.05):
        G.append(("vxn_rel", f"vxn_rel>={x}", (lambda x: lambda F: F["vxn_rel"] >= x)(x)))
    for x in (30, 35, 40):
        G.append(("vxn_cap", f"vxn<{x}", (lambda x: lambda F: F["vxn"] < x)(x)))
    for x in (0.8, 1.0, 1.2):
        G.append(("trend_day", f"fh_ratio>={x}", (lambda x: lambda F: F["fh_ratio"] >= x)(x)))
    for x in (0.35, 0.5, 0.65):
        G.append(("trend_day", f"fh_with>={x}", (lambda x: lambda F: F["fh_with"] >= x)(x)))
    for x, y in ((1.0, 0.5), (1.0, 0.65), (0.8, 0.65)):
        G.append(("trend_day", f"fh_ratio>={x}&fh_with>={y}", (lambda x, y: lambda F: (F["fh_ratio"] >= x) & (F["fh_with"] >= y))(x, y)))
    G += [("lit", "not_against_lit", lambda F: F["lit_with"] >= 0), ("lit", "with_lit_only", lambda F: F["lit_with"] > 0),
          ("lit", "no_lit_day", lambda F: F["lit_day"] == 0), ("lit", "lit_flat", lambda F: (F["lit_open"] == 0) & (F["lit_arm"] == 0)),
          ("lit", "with_lit_or_none", lambda F: (F["lit_with"] > 0) | (F["lit_day"] == 0)),
          ("lit_bias", "draw_not_against", lambda F: F["draw_with"] >= 0), ("lit_bias", "draw_with", lambda F: F["draw_with"] > 0),
          ("lit_bias", "amd_not_against", lambda F: F["amd_with"] >= 0), ("lit_bias", "amd_with", lambda F: F["amd_with"] > 0),
          ("lit_bias", "or_dpd_amd_not_against", lambda F: ~((F["draw_with"] < 0) | (F["amd_with"] < 0)) | (F["draw_with"] > 0) | (F["amd_with"] > 0)),
          ("es", "es_with", lambda F: ~(F["es_with"] < 0)), ("es", "es_out", lambda F: ~(F["es_out"] == 0)),
          ("es", "es_rel>-0.3", lambda F: ~(F["es_rel"] < -0.3)), ("es", "es_rel<0.3", lambda F: ~(F["es_rel"] > 0.3)),
          ("vwap", "vwap_with", lambda F: F["vwap_with"] > 0), ("htf", "h1_with", lambda F: F["h1_with"] > 0),
          ("htf", "m15_with", lambda F: F["m15_with"] > 0), ("htf", "h1&m15_with", lambda F: (F["h1_with"] > 0) & (F["m15_with"] > 0))]
    for a, b in itertools.product((630, 660, 690, 720), (840, 870, 900, 931)):
        if (a, b) != (630, 931):
            G.append(("time", f"win{a}-{b}", (lambda a, b: lambda F: (F["mod"] >= a) & (F["mod"] < b))(a, b)))
    G += [("time", "no_lunch_1200-1330", lambda F: ~((F["mod"] > 720) & (F["mod"] < 810))),
          ("time", "no_1330-1400", lambda F: F["mod"] != 840), ("time", "no_1030", lambda F: F["mod"] != 630),
          ("time", "no_1530", lambda F: F["mod"] != 930)]
    for x in (0.1, 0.25, 0.5):
        G.append(("gap", f"|gap|>={x}", (lambda x: lambda F: np.abs(F["gap"]) >= x)(x)))
        G.append(("gap", f"|gap|<{x}", (lambda x: lambda F: np.abs(F["gap"]) < x)(x)))
    G += [("gap", "gap_with", lambda F: F["gap_with"] > 0), ("gap", "gap_not_against", lambda F: F["gap_with"] >= 0),
          ("gap", "gap_with_or_small", lambda F: (F["gap_with"] > 0) | (np.abs(F["gap"]) < 0.25))]
    G += [("news", "no_news_day", lambda F: F["news"] == 0), ("news", "news_only", lambda F: F["news"] == 1),
          ("news", "no_fomc_day", lambda F: F["fomc"] == 0), ("news", "no_fomc_after_1400", lambda F: ~((F["fomc"] == 1) & (F["mod"] >= 840)))]
    for x in (1.1, 1.25, 1.5):
        G.append(("excess", f"exc>={x}", (lambda x: lambda F: F["exc"] >= x)(x)))
    for x in (2.0, 2.5, 3.0):
        G.append(("excess", f"exc<{x}", (lambda x: lambda F: F["exc"] < x)(x)))
    for x in (0.8, 1.0):
        G.append(("prior_range", f"prng>={x}", (lambda x: lambda F: F["prng_ratio"] >= x)(x)))
    G += [("nth", "skip_first", lambda F: F["nth"] > 1), ("nth", "first3", lambda F: F["nth"] <= 3)]
    for dd in range(5):
        G.append(("dow", f"no_dow{dd}", (lambda dd: lambda F: F["dow"] != dd)(dd)))
    return G


def judge(p=None, mask_fn=None, risk=150.0):
    o, TT = N.lines(p, mask_fn, JUDGE, risk)
    return o, TT


def row_line(name, o, base=None):
    s = []
    for sp in ("H1", "H2", "R"):
        x = o[sp]
        d = f" ({x['avg_r'] - base[sp]['avg_r']:+.3f})" if base else ""
        s.append(f"{sp} {x['tpw']:5.1f}/wk R{x['avg_r']:+.3f}{d} PF{x['pf']:4.2f} ${x['net']:>6} t{x['t_r']:5.2f}")
    return f"{name:34s} " + " | ".join(s)


def cmd_filters():
    t0 = time.time()
    base, _ = judge()
    R = []
    for fam, nm, fn in filter_specs():
        o, _ = judge(None, fn)
        R.append({"fam": fam, "name": nm, **{sp: o[sp] for sp, _ in JUDGE}})
    print(f"{len(R)} filters in {time.time() - t0:.0f}s")
    _report(R, base, "filters")
    json.dump({"base": base, "rows": R}, open(os.path.join(OUT, "na_filters.json"), "w"), default=float)
    return R


def _report(R, base, label):
    ok = [r for r in R if r["H1"]["tpw"] >= MIN_TPW]
    print(f"\n== {label}: {len(ok)} of {len(R)} with >= {MIN_TPW}/wk in H1; sorted by the H1 t-stat (pick), H2 / 2021-25 = check")
    ok.sort(key=lambda r: -r["H1"]["t_r"])
    for r in ok[:25]:
        print(row_line(f"{r['fam']}:{r['name']}", r, base))
    # how often does an H1 improvement carry over
    imp = [r for r in ok if r["H1"]["avg_r"] > base["H1"]["avg_r"] and r["name"] != "none"]
    h2 = sum(1 for r in imp if r["H2"]["avg_r"] > base["H2"]["avg_r"])
    rr = sum(1 for r in imp if r["R"]["avg_r"] > base["R"]["avg_r"])
    both = sum(1 for r in imp if r["H2"]["avg_r"] > base["H2"]["avg_r"] and r["R"]["avg_r"] > base["R"]["avg_r"])
    print(f"   {len(imp)} improve H1 avg R; of them {h2} also improve H2, {rr} improve 2021-25, {both} both")
    fams = sorted({r["fam"] for r in R})
    print("   per family (best H1 t-stat):")
    for f in fams:
        rs = [r for r in ok if r["fam"] == f]
        if rs:
            b = max(rs, key=lambda r: r["H1"]["t_r"])
            print("   " + row_line(f"{f}:{b['name']}", b, base))


def pick(R, base):
    ok = [r for r in R if r["H1"]["tpw"] >= MIN_TPW and r["name"] != "none"]
    return max(ok, key=lambda r: r["H1"]["t_r"])


def neighbours(key, vals, extra=None):
    """the pick's threshold neighbourhood: every value is judged (not picked)."""
    out = []
    for v in vals:
        fn = (lambda v: lambda F: (F[key] >= v) & (extra(F) if extra else True))(v)
        o, _ = judge(None, fn)
        out.append({"name": f"{key}>={v}", **{sp: o[sp] for sp, _ in JUDGE}})
    return out


PICK1 = ("prior_range", "prng>=0.8")


def mask_of(names):
    """AND of named filters from filter_specs."""
    G = {nm: fn for _, nm, fn in filter_specs() if fn}
    fns = [G[n] for n in names]
    return (lambda F: np.logical_and.reduce([f(F) for f in fns])) if fns else None


def cmd_filters2():
    """stage 1b: the stage-1 pick AND one more filter (picked on H1 again) + the pick's neighbourhood."""
    base, _ = judge()
    p1 = mask_of([PICK1[1]])
    b1, _ = judge(None, p1)
    print(row_line("PICK1 " + PICK1[1], b1, base))
    NB = neighbours("prng_ratio", (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2))
    print("neighbourhood of the pick (prior-day RTH range / 14-day mean):")
    for r in NB:
        print("  " + row_line(r["name"], r, base))
    R = []
    for fam, nm, fn in filter_specs():
        if fn is None or fam == "prior_range":
            continue
        o, _ = judge(None, (lambda fn: lambda F: p1(F) & fn(F))(fn))
        R.append({"fam": fam, "name": "prng>=0.8 & " + nm, **{sp: o[sp] for sp, _ in JUDGE}})
    _report(R, b1, "pick1 + one more filter (deltas vs pick1)")
    json.dump({"base": base, "pick1": b1, "neigh": NB, "rows": R}, open(os.path.join(OUT, "na_filters2.json"), "w"), default=float)


# ================================================================================================ stage 2: exits
def exit_specs():
    trails = [(None, 1.0)] + [(tr, ts) for tr in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0) for ts in (0.5, 0.75, 1.0, 1.5)]
    parts = [(None, False), (1.0, False), (1.0, True)]
    G = []
    for (tr, ts), hold, (pr, pbe), be, sk in itertools.product(trails, (20, 25, 30, 35, 40, 45), parts, (None, 1.0), (1.25, 1.5, 1.75, 2.0)):
        for ext in ((0, 1, 3) if hold == 30 else (0,)):
            G.append({"trail": tr, "tstart": ts, "hold": hold, "part_r": pr, "part_be": pbe, "be": be, "stopk": sk, "ext": ext})
    return G


def ename(p):
    t = f"trail{p['trail']}@{p['tstart']}" if p["trail"] else "notrail"
    pr = f"part{p['part_r']}{'+BE' if p['part_be'] else ''}" if p["part_r"] else "nopart"
    return f"{t} hold{p['hold']} {pr} be{p['be']} stop{p['stopk']} ext{p['ext']}"


def _ejob(p):
    o, _ = judge(p, mask_of([PICK1[1]]))
    return {"name": ename(p), "p": p, **{sp: o[sp] for sp, _ in JUDGE}}


def cmd_exits(procs=4):
    from multiprocessing import Pool
    t0 = time.time()
    G = exit_specs()
    for tf in (1, 5):          # warm the signal caches before forking
        B = N.bars(tf)
        for sk in (1.25, 1.5, 1.75, 2.0):
            N.signals(B, 1.0, 30, (630, 930), sk)
    with Pool(procs) as P:
        R = P.map(_ejob, G, chunksize=20)
    print(f"{len(R)} exit variants in {time.time() - t0:.0f}s")
    b1 = next(r for r in R if r["p"] == {**{k: N.BASE[k] for k in ("trail", "tstart", "hold", "part_r", "part_be", "be", "stopk", "ext")}})
    for r in R:
        r["fam"] = "exit"
    _report(R, b1, "exits on pick1 (deltas vs pick1 with today's exit)")
    json.dump({"pick1": b1, "rows": R}, open(os.path.join(OUT, "na_exits.json"), "w"), default=float)
    best = pick(R, b1)
    print("PICK2:", best["name"])
    # one-step neighbours of the pick
    ax = {"trail": (None, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0), "tstart": (0.5, 0.75, 1.0, 1.5), "hold": (20, 25, 30, 35, 40, 45),
          "stopk": (1.25, 1.5, 1.75, 2.0), "ext": (0, 1, 3)}
    idx = {json.dumps(r["p"], sort_keys=True): r for r in R}
    print("one-step neighbours of PICK2:")
    for k, vals in ax.items():
        v0 = best["p"][k]
        if v0 not in vals:
            continue
        i = vals.index(v0)
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                q = {**best["p"], k: vals[j]}
                r = idx.get(json.dumps(q, sort_keys=True))
                if r:
                    print("  " + row_line(f"{k}={vals[j]}", r, b1))
    for q in ({**best["p"], "part_r": None, "part_be": False}, {**best["p"], "part_r": 1.0, "part_be": False},
              {**best["p"], "part_r": 1.0, "part_be": True}, {**best["p"], "be": None}, {**best["p"], "be": 1.0}):
        r = idx.get(json.dumps(q, sort_keys=True))
        if r and r is not best:
            print("  " + row_line(r["name"], r, b1))
    return R


# ================================================================================================ stage 3: MFFU sizing
PICK_P = {}                                   # stage-2 verdict: today's exit (no exit change held in H2)
CAPS = {"25k": (150.0, 300.0, 450.0, 600.0), "50k": (300.0, 600.0, 900.0, 1200.0)}
DTP = {"25k": (None, 200.0, 400.0, 600.0), "50k": (None, 400.0, 800.0, 1200.0)}
SPANS3 = (("H1", 1), ("H2", 1), ("R", 5), ("2025", 5), ("2021-24", 5))


def blitz_trades(p=None, part=False, names=(PICK1[1],), placebo=None):
    """BLITZ trades per timeframe: {1: [...], 5: [...]} (2026 on 1m, 2021-25 on 5m)."""
    P = {**N.BASE, **PICK_P, **(p or {})}
    if part:
        P.update(part_r=1.0, part_f=0.5)
    m = mask_of(list(names))
    out = {}
    for tf in (1, 5):
        B = N.bars(tf)
        F = N.signals(B, P["vm"], P["every"], tuple(P["win"]), P["stopk"])
        out[tf] = N.run(B, P, m(F) if m else None, F, placebo=placebo)
    return out


def eval_specs(plan):
    G = []
    for f, c in itertools.product((0.15, 0.2, 0.3, 0.4, 0.5, 0.6), CAPS[plan]):
        G.append({"mode": "frac", "f": f, "cap": c})
    for k, f, c in itertools.product((2.0, 3.0, 4.0), (0.3, 0.5), CAPS[plan][2:]):
        G.append({"mode": "need", "f": f, "cap": c, "k": k})
    return [{**g, "day_tp": tp} for g in G for tp in DTP[plan]]


def fund_specs(plan):
    G = [{"mode": "frac", "f": f, "cap": c} for f, c in itertools.product((0.1, 0.2, 0.3, 0.45, 0.6), CAPS[plan])]
    return [{**g, "day_tp": tp} for g in G for tp in DTP[plan]]


def szname(z):
    s = f"{z['mode']} f{z['f']} cap{int(z['cap'])}" + (f" k{z['k']}" if z.get("k") else "")
    return s + (f" dtp{int(z['day_tp'])}" if z.get("day_tp") else "")


def _span_T(TT, sp, tf):
    B = N.bars(tf)
    S = N.sessions(B, sp)
    return N.span_trades(TT[tf], S), S


def _szjob(a):
    plan, kind, z, part = a
    TT = BT[part]
    out = {"plan": plan, "kind": kind, "z": z, "part": part, "name": szname(z) + (" part1R" if part else "")}
    for sp, tf in SPANS3:
        T, S = _span_T(TT, sp, tf)
        if kind == "eval":
            out[sp] = N.eval_score(T, S, plan, z)
        else:
            out[sp] = N.funded_score(T, S, plan, z)
    return out


BT = {}


def cmd_sizing(procs=4):
    from multiprocessing import Pool
    t0 = time.time()
    BT[False], BT[True] = blitz_trades(), blitz_trades(part=True)
    jobs = [(plan, kind, z, part) for plan in ("25k", "50k") for kind, specs in (("eval", eval_specs), ("fund", fund_specs))
            for z in specs(plan) for part in (False, True)]
    with Pool(procs) as P:
        R = P.map(_szjob, jobs, chunksize=8)
    print(f"{len(R)} sizing variants in {time.time() - t0:.0f}s", flush=True)
    res = {"rows": R, "picks": {}}
    for plan in ("25k", "50k"):
        E = [r for r in R if r["plan"] == plan and r["kind"] == "eval"]
        Fd = [r for r in R if r["plan"] == plan and r["kind"] == "fund"]
        bal = max(E, key=lambda r: (r["H1"]["p10"] - r["H1"]["f10"], r["H1"]["path_net"]))
        mx = max(E, key=lambda r: (r["H1"]["p10"], -r["H1"]["f10"]))
        fd = max(Fd, key=lambda r: (r["H1"].get("fund_pm", -1), -r["H1"].get("fund_lost", 100)))
        res["picks"][plan] = {"balanced": bal, "maximizer": mx, "funded": fd}
        print(f"\n== Builder {plan.upper()}: eval picks on H1 (balanced = max p10 - f10, maximizer = max p10); funded pick = max H1 $/mo")
        for lab, r in (("balanced", bal), ("maximizer", mx)):
            print(f"  {lab:9s} {r['name']}")
            for sp, _ in SPANS3:
                e = r[sp]
                print(f"     {sp:7s} p10 {e['p10']:5.1f} f10 {e['f10']:5.1f} dec10 {e['dec10']:5.1f} p15 {e['p15']:5.1f} f15 {e['f15']:5.1f} "
                      f"p20 {e['p20']:5.1f} f20 {e['f20']:5.1f} med {e['pass_med']} slow {e['slow_pass']} path ${e['path_net']} "
                      f"({e['b2b']} P/F, {e['passes_pm']} passes/mo) qty {e['med_qty']}")
        print(f"  funded    {fd['name']}")
        for sp, _ in SPANS3:
            e = fd[sp]
            print(f"     {sp:7s} ${e.get('fund_pm')}/mo to the owner, {e.get('fund_pay_pm')} payouts/mo, lost {e.get('fund_lost')}% stuck {e.get('fund_stuck')}%")
        # does the daily-target stop help? (same size, with vs without)
        for kind, rows in (("eval", E), ("fund", Fd)):
            key = (lambda r: r["H1"]["p10"] - r["H1"]["f10"]) if kind == "eval" else (lambda r: r["H1"].get("fund_pm", 0))
            for sp in ("H1", "H2", "R"):
                key_sp = (lambda r: r[sp]["p10"] - r[sp]["f10"]) if kind == "eval" else (lambda r: r[sp].get("fund_pm", 0))
                base = {(json.dumps({k: v for k, v in r["z"].items() if k != "day_tp"}, sort_keys=True), r["part"]): r for r in rows if not r["z"].get("day_tp")}
                win = tot = 0
                for r in rows:
                    if not r["z"].get("day_tp"):
                        continue
                    b = base[(json.dumps({k: v for k, v in r["z"].items() if k != "day_tp"}, sort_keys=True), r["part"])]
                    tot += 1
                    win += key_sp(r) > key_sp(b)
                print(f"  daily-target stop better than none ({kind}, {sp}): {win}/{tot}")
            for sp in ("H1", "H2", "R"):
                key_sp = (lambda r: r[sp]["p10"] - r[sp]["f10"]) if kind == "eval" else (lambda r: r[sp].get("fund_pm", 0))
                base = {json.dumps(r["z"], sort_keys=True): r for r in rows if not r["part"]}
                win = tot = 0
                for r in rows:
                    if r["part"]:
                        b = base[json.dumps(r["z"], sort_keys=True)]
                        tot += 1
                        win += key_sp(r) > key_sp(b)
                print(f"  partial +1R better than none ({kind}, {sp}): {win}/{tot}")
    json.dump(res, open(os.path.join(OUT, "na_sizing.json"), "w"), default=float)
    return res


# ================================================================================================ stage 3b: the whole slot ($ to the owner)
LSPANS = (("H1", 1), ("H2", 1), ("R", 5))


def _lifejob(a):
    plan, ez, fz, part, n = a
    TT = BT[part]
    out = {"plan": plan, "ez": ez, "fz": fz, "part": part, "name": f"eval[{szname(ez)}] funded[{szname(fz)}]" + (" part1R" if part else "")}
    for sp, tf in LSPANS:
        T, S = _span_T(TT, sp, tf)
        out[sp] = N.life(T, S, plan, ez, fz, n=n)
    return out


def life_specs(plan):
    ev = [{"mode": "frac", "f": f, "cap": c} for f, c in itertools.product((0.2, 0.3, 0.4, 0.6), CAPS[plan][1:])]
    fd = [{"mode": "frac", "f": f, "cap": c} for f, c in itertools.product((0.1, 0.2, 0.3, 0.45), CAPS[plan])]
    fd = [{**z, "day_tp": tp} for z in fd for tp in (None, DTP[plan][2])]
    return ev, fd


def cmd_life(procs=4, n=400):
    from multiprocessing import Pool
    t0 = time.time()
    BT[False], BT[True] = blitz_trades(), blitz_trades(part=True)
    jobs = []
    for plan in ("25k", "50k"):
        ev, fd = life_specs(plan)
        jobs += [(plan, e, f, part, n) for e in ev for f in fd for part in (False, True)]
    with Pool(procs) as P:
        R = P.map(_lifejob, jobs, chunksize=4)
    print(f"{len(R)} slot variants in {time.time() - t0:.0f}s", flush=True)
    res = {"rows": R, "picks": {}}
    for plan in ("25k", "50k"):
        rows = [r for r in R if r["plan"] == plan]
        rows.sort(key=lambda r: -r["H1"]["life_pm"])
        res["picks"][plan] = rows[0]
        print(f"\n== Builder {plan.upper()} slot (eval -> funded -> payouts, 6-month MC paths, $ / month to the owner net of evals); "
              f"sorted by H1 (pick), H2 / 2021-25 = check")
        for r in rows[:12]:
            print(f"  {r['name']:78s} " + " | ".join(f"{sp} ${r[sp]['life_pm']:>5}/mo p10 ${r[sp]['life_p10']:>5} lose {r[sp]['life_lose']:4.1f}% "
                                                     f"funded {r[sp]['funded_per_6m']:4.2f}/6m 1st pay {r[sp]['first_pay_med']}" for sp, _ in LSPANS))
        pos = sum(1 for r in rows if all(r[sp]["life_pm"] > 0 for sp, _ in LSPANS))
        print(f"  {pos}/{len(rows)} slot variants make money in H1, H2 and 2021-25")
    json.dump(res, open(os.path.join(OUT, "na_life.json"), "w"), default=float)
    return res


# ================================================================================================ main
if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "filters"
    {"filters": cmd_filters, "filters2": cmd_filters2, "exits": cmd_exits, "sizing": cmd_sizing, "life": cmd_life}[cmd]()
