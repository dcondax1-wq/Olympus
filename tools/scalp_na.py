"""BLITZ = the noise-area (NA) momentum scalp (research/writeups/scalp-momentum.md "na_scalp"), turned toward MFFU money
(owner 2026-10-28). research/writeups/scalp-na-mffu.md. Paper research only: no engine / live / dashboard file is touched.

Protocol (as scalp-momentum.md): every grid is fixed before it is run; a variant is PICKED on 2026 H1 (1m bars) only, by the
t-stat of its average net R with >= 5 trades a week; 2026 H2 (Jul-Oct 16, 1m) is the check; 2021-25 (the same rule on 5m
bars: the noise band and the check-bar closes are identical on 1m and 5m, only the fills are coarser) is the reference.
Costs: $1.90 a micro + 1 tick on every market / stop fill, limits only when traded through, same-bar tie = loss.

    python -X utf8 tools/scalp_na.py filters     # stage 1: 93 filters -> research/scalp/na_filters.json
    python -X utf8 tools/scalp_na.py filters2    # stage 1b: the pick's neighbourhood + one more filter -> na_filters2.json
    python -X utf8 tools/scalp_na.py exits       # stage 2: 4,800 exits on the pick -> na_grid_exits.json (local) + na_exits.json
    python -X utf8 tools/scalp_na.py sizing      # stage 3: MFFU 25K / 50K eval + funded sizing -> na_sizing.json
    python -X utf8 tools/scalp_na.py life        # stage 3b: whole account slots (eval -> funded -> payouts) -> na_life.json
    python -X utf8 tools/scalp_na.py checks      # random-direction placebo + look-ahead on cut data -> na_checks.json
    python -X utf8 tools/scalp_na.py save        # runs scalp_na_* (tools/runlib) + research/scalp/na_best_trades.json
  stage 4 (with ATLAS / LIT): tools/scalp_na_combo.py
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
    json.dump({"pick1": b1, "rows": R}, open(os.path.join(OUT, "na_grid_exits.json"), "w"), default=float)
    cmd_exits_small()
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


def blitz_trades(p=None, part=False, names=(PICK1[1],), placebo=None, late=0):
    """BLITZ trades per timeframe: {1: [...], 5: [...]} (2026 on 1m, 2021-25 on 5m)."""
    P = {**N.BASE, **PICK_P, **(p or {})}
    if part:
        P.update(part_r=1.0, part_f=0.5)
    m = mask_of(list(names))
    out = {}
    for tf in (1, 5):
        B = N.bars(tf)
        F = N.signals(B, P["vm"], P["every"], tuple(P["win"]), P["stopk"])
        out[tf] = N.run(B, P, m(F) if m else None, F, placebo=placebo, late=late)
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


# ================================================================================================ honesty checks
def cmd_checks(seeds=40):
    """Random-direction placebo (same candidate bars, coin-flip side, same stop distance) and look-ahead (signals + fills on
    data cut at 13:00 on 6 random 2026 days == the full-data trades that closed before the cut)."""
    from tools import scalp_mo_lib as L
    m = mask_of([PICK1[1]])
    out = {"placebo": {}, "lookahead": {}}
    for tf, spans in ((1, ("H1", "H2")), (5, ("R", "2025", "2021-24"))):
        B = N.bars(tf)
        F = N.signals(B)
        T = N.run(B, None, m(F), F)
        for sp in spans:
            S = N.sessions(B, sp)
            real = float(np.mean([N.r_of(t) for t in N.span_trades(T, S)]))
            pl = []
            for sd in range(seeds):
                Tp = N.run(B, None, m(F), F, placebo=sd)
                pl.append(float(np.mean([N.r_of(t) for t in N.span_trades(Tp, S)])))
            a = np.array(pl)
            out["placebo"][sp] = {"real_r": round(real, 3), "placebo_r": round(float(a.mean()), 3), "placebo_p95": round(float(np.percentile(a, 95)), 3),
                                  "p": round(float((a >= real).mean()), 3), "seeds": seeds}
            print(f"placebo {sp:7s}: real avg R {real:+.3f} vs random directions {a.mean():+.3f} (95th pct {np.percentile(a, 95):+.3f}), p = {(a >= real).mean():.3f}")
    B = N.bars(1)
    F = N.signals(B)
    full = N.run(B, None, m(F), F)
    rng = np.random.default_rng(1)
    days = N.sessions(B, "H1") + N.sessions(B, "H2")
    bad = 0
    for d in rng.choice(days, 6, replace=False):
        i = int(np.where(B["dates"] == d)[0][0])
        idx = np.where(B["day"] == i)[0]
        cut_t = int(B["t"][idx[(B["mod"][idx] >= 780)][0]])
        Bc = L._bars(1, "2021-11-01", cut_t=cut_t)
        Fc = N.signals(Bc)
        Tc = N.run(Bc, None, m(Fc), Fc)
        a = {(t["entry_t"], t["dir"], t["entry"], t["exit"]) for t in full if t["exit_t"] <= cut_t and t["day"] >= "2026-01-01"}
        b = {(t["entry_t"], t["dir"], t["entry"], t["exit"]) for t in Tc if t["exit_t"] <= cut_t and t["day"] >= "2026-01-01"}
        diff = len(a ^ b)
        bad += diff
        print(f"  look-ahead cut {d} 13:00: {len(a)} closed trades, {diff} differ")
        out["lookahead"][str(d)] = [len(a), diff]
    out["lookahead_diff"] = bad
    json.dump(out, open(os.path.join(OUT, "na_checks.json"), "w"), default=float)
    return out


def cmd_exits_small():
    """research/scalp/na_exits.json = a summary of the exit grid (the full grid is research/scalp/na_grid_exits.json, gitignored)."""
    src = os.path.join(OUT, "na_grid_exits.json")
    d = json.load(open(src))
    R, b1 = d["rows"], d["pick1"]
    ok = sorted([r for r in R if r["H1"]["tpw"] >= MIN_TPW], key=lambda r: -r["H1"]["t_r"])
    imp = [r for r in ok if r["H1"]["avg_r"] > b1["H1"]["avg_r"]]
    keep = ("n", "tpw", "avg_r", "pf", "net", "per_month", "dd", "t_r")
    slim = lambda r: {"name": r["name"], "p": r["p"], **{sp: {k: r[sp][k] for k in keep} for sp in ("H1", "H2", "R")}}
    json.dump({"note": "summary; full grid in na_grid_exits.json (local only)", "variants": len(R), "today_exit": slim(b1),
               "improve_h1": len(imp), "improve_h1_and_h2": sum(1 for r in imp if r["H2"]["avg_r"] > b1["H2"]["avg_r"]),
               "improve_h1_and_r": sum(1 for r in imp if r["R"]["avg_r"] > b1["R"]["avg_r"]),
               "improve_all3": sum(1 for r in imp if r["H2"]["avg_r"] > b1["H2"]["avg_r"] and r["R"]["avg_r"] > b1["R"]["avg_r"]),
               "top30_h1": [slim(r) for r in ok[:30]]}, open(os.path.join(OUT, "na_exits.json"), "w"), indent=0, default=float)


# ================================================================================================ store
RULE_TEXT = ("BLITZ = the noise-area momentum scalp (scalp-momentum.md na_scalp) + one filter: trade only when the PRIOR day's "
             "09:30-16:00 range is at least 0.8 x its 14-day mean. Checks at the 1m closes of 11:00, 11:30 ... 15:30 ET: a close above "
             "the 09:30 open x (1 + sigma) buys, below open x (1 - sigma) sells (sigma = mean |close / 09:30 open - 1| at that minute "
             "over the last 14 sessions); market at the next open (+1 tick); stop 1.5 x the 14-bar ATR of 5m bars; after +1R the stop "
             "trails 1.5R behind the best price; out after 30 minutes or at 15:55; one position, max 6 a day, -3R day stop.")


def store_trades(T, usd, maxq=20, trig="blitz"):
    from tools import scalp_mo_lib as L
    tr = L.runlib_trades(T, usd, maxq)
    for t in tr:
        t["trigger"] = trig
    return tr


def unit_trades(U, usd, trig):
    """second_mix-style units (pts per micro, risk pts) -> runlib rows at a fixed $ risk."""
    out = []
    for u in U:
        rp = (u["risk"] + 0.25) * 2.0 + 1.9
        q = max(1, min(40, int(usd / rp)))
        pnl = q * (u["pts"] * 2.0 - 1.9)
        out.append({"day": u["day"], "entry_t": u["entry_t"], "exit_t": u["exit_t"], "dir": u["dir"], "r": round(pnl / (q * rp), 3), "pnl": round(pnl, 2),
                    "risk_pts": u["risk"], "qty": q, "risk_usd": round(q * rp, 2), "half": 0, "exit": u["exit"], "trigger": trig, "mfe": None,
                    "mae": None, "bars_held": None, "regime": None, "mult": 1.0, "low": round(q * (u["w1"] * 2.0 - 1.9), 2)})
    return out


def _sessions_all():
    S5, S1 = N.sessions(N.bars(5), "R"), N.sessions(N.bars(1), "H1") + N.sessions(N.bars(1), "H2")
    return sorted(set(S5) | set(S1))


def cmd_save():
    from tools import runlib as rl
    from tools import scalp_na_combo as C
    sess = _sessions_all()
    TT = blitz_trades()
    T = [t for t in TT[5] if t["day"] < "2026-01-01"] + [t for t in TT[1] if t["day"] >= "2026-01-01"]
    tr = store_trades(T, 150.0)
    J = lambda n: json.load(open(os.path.join(OUT, n)))
    f2 = J("na_filters2.json")["pick1"]
    sz = J("na_sizing.json")["picks"]
    lf = J("na_life.json")["picks"]
    ck = J("na_checks.json")["placebo"]
    line = lambda sp: f"{f2[sp]['tpw']}/wk PF {f2[sp]['pf']} net ${f2[sp]['net']:,} (${f2[sp]['per_month']}/mo) DD ${f2[sp]['dd']:,} avg R {f2[sp]['avg_r']:+.3f}"
    e25, e50 = sz["25k"]["balanced"], sz["50k"]["balanced"]
    ev = lambda r, sp: f"{r[sp]['p10']}/{r[sp]['f10']}"
    v1 = (f"At $150 a trade: 2026 H1 (pick) {line('H1')}; H2 (check) {line('H2')}; 2021-25 (5m) {line('R')}. Random directions lose "
          f"(p {ck['H1']['p']} / {ck['H2']['p']} / {ck['R']['p']}). MFFU 2-week pass/fail 25K ({e25['name']}) H1 {ev(e25, 'H1')}, H2 {ev(e25, 'H2')}, "
          f"2021-25 {ev(e25, 'R')}; 50K ({e50['name']}) {ev(e50, 'H1')}, {ev(e50, 'H2')}, {ev(e50, 'R')}. Own-account slot (eval -> funded, net of "
          f"evals): 25K best H1 ${lf['25k']['H1']['life_pm']}/mo, H2 ${lf['25k']['H2']['life_pm']}, 2021-25 ${lf['25k']['R']['life_pm']}; 50K "
          f"${lf['50k']['H1']['life_pm']} / ${lf['50k']['H2']['life_pm']} / ${lf['50k']['R']['life_pm']}.")
    rl.save("scalp_na_blitz", "BLITZ: noise-area momentum scalp + prior-day range filter (1m 2026, 5m 2021-25), $150 a trade", "other",
            "Owner 2026-10-28: turn the NA scalp into a scalper that pays on MFFU", params={**N.BASE, "filter": PICK1[1], "rule": RULE_TEXT},
            sizing={"fixed_usd": 150.0, "eval_25k": e25["name"], "eval_50k": e50["name"]}, trades=tr, scored=rl.score(tr, sess), status="promising",
            verdict=v1, notes="tools/scalp_na.py (tools/scalp_na_lib.py executor = scalp_mo_lib fills, checked trade for trade)",
            writeup="scalp-na-mffu", tags=["scalp", "momentum", "blitz", "third-strategy"])
    print("saved scalp_na_blitz", flush=True)
    # BLITZ on LIT's funded 50K (only while LIT is flat, never opposite ATLAS, flattened at a LIT entry)
    C.lit_by(C.PICK_LIT["nc"])
    byn = C._AU[("litm", None, None, True, False, 0, 0.0)]
    U = [dict(t, entry_t=t["et"], exit_t=t["xt"]) for d in sorted(byn) for t in byn[d]]
    lc = J("na_combo_lit_checks.json")
    tr2 = unit_trades(U, 450.0, "blitz_on_lit")
    v2 = (f"LIT's MFFU Builder 50K slot (eval -> funded -> payouts, 6-month MC, net of evals): LIT alone H1 ${lc['base']['H1']['slot_pm']}/mo, "
          f"H2 ${lc['base']['H2']['slot_pm']}, 2021-25 ${lc['base']['REF']['slot_pm']}; + BLITZ once funded (20% of the room, <= $450 a trade, "
          f"only while LIT is flat) ${lc['pick']['H1']['slot_pm']} / ${lc['pick']['H2']['slot_pm']} / ${lc['pick']['REF']['slot_pm']} "
          f"(paired +${lc['paired_H1']['mean']} / +${lc['paired_H2']['mean']} / +${lc['paired_REF']['mean']} a month, better in "
          f"{lc['paired_H1']['better']}% / {lc['paired_H2']['better']}% of paths); LIT's eval odds unchanged. Real 2026 path: "
          f"${lc['real_2026']['lit']['net']:,} -> ${lc['real_2026']['lit_blitz']['net']:,}. Stored trades: BLITZ as it trades there, at $450 a trade.")
    rl.save("scalp_na_blitz_lit50k", "BLITZ as an add-on on LIT's funded Builder 50K (only while LIT is flat)", "other",
            "Owner 2026-10-28: does BLITZ add money next to LIT without breaking the one-position / no-hedge rules?",
            params={"rule": RULE_TEXT, "add_on": C.PICK_LIT}, sizing={"funded": {"f": 0.2, "cap": 450.0}, "eval": None}, trades=tr2,
            scored=rl.score(tr2, sess), status="promising", verdict=v2,
            notes="tools/scalp_na_combo.py lit_grid / lit_checks / lit_why (tools/uprisk.py + tools/div_stack.py engines)",
            writeup="scalp-na-mffu", tags=["scalp", "blitz", "lit", "funded"])
    print("saved scalp_na_blitz_lit50k", flush=True)
    # ATLAS + BLITZ (rejected): the back-to-back eval path of account B per span
    from tools import atlas as A
    from tools import second_mix as M
    from tools import second_account_b as AB
    import copy
    o_all, T3 = {}, []
    C.atlas_score(0.2, 300.0, 6, True, spans=("H1",))
    V = copy.deepcopy(A.BASE)
    V["members"] = V["members"] + ["NA"]
    M.units()["NA"] = C._AU[("NA", True)]
    orig_q, orig_ru = A.q_variant, A.member_units
    A.q_variant = lambda t, st, V_: C.na_qty(t, st, 0.2, 300.0, 20, 600.0) if t.get("src") == "NA" else orig_q(t, st, V_)
    A.member_units = lambda name, V_: M.units()["NA"] if name == "NA" else orig_ru(name, V_)
    try:
        Ua = A.account_units(V)
        with A.Plan(V) as pl:
            inner = M.play_day
            M.play_day = lambda L_, day, bal, floor, session, rule, pre=False, max_day=2, lost=None, litcfg=None, dll=None, reserve=True, extra=None: \
                inner(L_, day, bal, floor, session, rule, pre, 6, lost, litcfg, dll, reserve, extra)
            for sp in ("H1", "H2", "2025", "2021-24"):
                o, P = AB.score(Ua, "atlas", sp, pl.safe_rule)
                o_all[sp] = o
                T3 += [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"],
                        "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0, "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"],
                        "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"], "trigger": t["src"], "mfe": None, "mae": None,
                        "bars_held": None, "regime": "", "mult": None, "low": t["low"]} for t in P]
    finally:
        A.q_variant, A.member_units = orig_q, orig_ru
        M.units().pop("NA", None)
    ca = J("na_combo_atlas.json")[0]
    v3 = ("ATLAS today vs + BLITZ (20% of the room, <= $300, max 6 trades a day, ATLAS first): 2-week pass/dead "
          + ", ".join(f"{sp} {ca[sp]['p10']}/{ca[sp]['dead10']} -> {o_all[sp]['p10']}/{o_all[sp]['dead10']}" for sp in ("H1", "H2", "2025", "2021-24"))
          + "; funded (live rule) about +$27/mo in each 2026 half, -$5 in 2021-25, stuck H2 8% -> 13%. Rejected: more dead evals in 2021-25, "
            "needs max 6 a day on account B.")
    rl.save("scalp_na_atlas_member", "ATLAS + BLITZ as a 4th member on the Builder 25K (rejected)", "other",
            "Owner 2026-10-28: should BLITZ join ATLAS's 25K?", params={"members": V["members"], "na": {"f": 0.2, "cap": 300.0}, "max_day": 6, "atlas_priority": True},
            sizing={"plan": "builder25k"}, trades=T3, scored=rl.score(T3, [d for d in M.units()["sessions"] if d >= "2021-01-01"]), status="rejected",
            verdict=v3, notes="tools/scalp_na_combo.py atlas (tools/atlas.py real account-B scorer); stored trades = the back-to-back eval path per span",
            writeup="scalp-na-mffu", tags=["scalp", "blitz", "atlas", "account_b"])
    print("saved scalp_na_atlas_member", flush=True)
    best_trades(TT[1])


def best_trades(T1):
    import datetime as dt
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    f = lambda x: dt.datetime.fromtimestamp(x, et).strftime("%Y-%m-%d %H:%M")
    rows = [{"entry_t": f(t["entry_t"]), "exit_t": f(t["exit_t"]), "dir": "long" if t["dir"] > 0 else "short", "entry": t["entry"],
             "stop": round(t["stop"], 2), "exit": t["exit"], "exit_kind": t["exit_kind"], "pts": t["pts"], "risk_pts": t["risk_pts"],
             "r": round(N.r_of(t), 3)} for t in T1]
    json.dump({"name": "BLITZ", "rule": RULE_TEXT, "params": {**N.BASE, "filter": PICK1[1]}, "tf": "1m",
               "note": "entry_t = open of the fill bar, exit_t = end of the exit bar (ET); prices include 1 tick on market and stop fills; "
                       "$ = pts x $2 x micros - $1.90 a micro.", "trades": rows},
              open(os.path.join(OUT, "na_best_trades.json"), "w"), indent=0)
    print("na_best_trades.json:", len(rows), "trades")


# ================================================================================================ main
if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "filters"
    {"filters": cmd_filters, "filters2": cmd_filters2, "exits": cmd_exits, "sizing": cmd_sizing, "life": cmd_life, "checks": cmd_checks, "exits_small": cmd_exits_small, "save": cmd_save}[cmd]()
