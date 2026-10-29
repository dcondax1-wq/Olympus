"""BLITZ on its own MFFU Builder 25K (account C): the rule search (research/writeups/blitz-25k.md). Research only.

Protocol (fixed before each grid is run): every variant runs as account C (never opposite LIT / ATLAS, closed first at their
opposite entry; tools/blitz25k_lib.account_c "lit+atlas"); 2026 on 1m bars, 2021-25 the same rule on 5m bars; costs $1.90 a
micro + 1 tick on every market / stop fill, limits only when traded through, same-bar tie = loss. A variant is PICKED on
2026 H1 only: the highest H1 t-stat of the average net R among variants with >= 3 trades a week and 2+ trades in >= 70% of
weeks; 2026 H2 and 2021-25 are the checks (a change is adopted only if it beats today's rule in H1, H2 AND 2021-25).

    python -X utf8 tools/blitz25k_grid.py baseline   # today's rule alone vs account C (positions / + LIT armed) -> b25_baseline.json
    python -X utf8 tools/blitz25k_grid.py stops      # stage 1: 45 stops (today's management) -> b25_stops.json
    python -X utf8 tools/blitz25k_grid.py mgmt       # stage 2: ~1,900 targets / management on 5 stops -> b25_grid_mgmt.json
                                                     #          (local only) + b25_mgmt.json (summary)
Each row: fixed $150 a trade (trades / week, % weeks with 2+, win %, avg R, t, PF, net $, $ / month, max DD, exits) and the
MFFU 25K eval (a fresh eval every session, 20 sessions: p10 / f10 / dec10 / p15 / f15 / pass_med / slow_pass) at today's
paper size (40% of the room, <= $600) and at 60% / <= $600.
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
warnings.filterwarnings("ignore")
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from tools import scalp_na_lib as N  # noqa: E402
from tools import blitz25k_lib as K  # noqa: E402

K.install_qty()                   # scalp_na_lib's eval / funded size with blitz25k_lib.qty (= its own qty unless "mult" / "tneed")

OUT = os.path.join(ROOT, "research", "scalp")
CMODE = "lit+atlas"
SIZES = {"f40": {"mode": "frac", "f": 0.4, "cap": 600.0}, "f60": {"mode": "frac", "f": 0.6, "cap": 600.0}}
EV_KEYS = ("p10", "f10", "dec10", "p15", "f15", "p20", "f20", "pass_med", "slow_pass")
MIN_TPW, MIN_WK2 = 3.0, 70.0


def prep(cmode=CMODE):
    """load bars, signals, structure, levels and the account-C arrays before forking workers."""
    for tf in (1, 5):
        B = N.bars(tf)
        K.base(B)
        K.structure(B)
        K.levels_ctx(B)
        if cmode:
            K.account_c(B, cmode)


def evaluate(v, cmode=CMODE, sizes=SIZES, placebo=None):
    TT = K.trades(v, cmode, placebo)
    L = K.lines(TT)
    row = {"v": v, "cmode": cmode}
    for sp, tf in K.SPANS:
        T, S = K.span(TT, sp, tf)
        x = dict(L[sp])
        for nm, z in sizes.items():
            e = N.eval_score(T, S, "25k", z, paths=False) if T else {}
            x[nm] = {k: e.get(k) for k in EV_KEYS}
        row[sp] = x
    return row


def vname(v):
    v = {**K.TODAY, **v}
    s = v["stop"] + (f"{v['k']}" if v["stop"] == "atr" else "") + (f" d{v['dmin']}-{v['dmax']}" if v["stop"] != "atr" and (v["dmin"] or v["dmax"] < 99) else "")
    if v["tgt"] == "liq":
        s += f" tgt-{v['liq']}{v['r_min']}-{v['r_max']}"
    elif v["tgt"]:
        s += f" tgt{v['tgt']}R"
    if v["part"] == "liq":
        s += f" part-liq{v['p_min']}" + ("+be" if v["part_be"] else "")
    elif v["part"]:
        s += f" part{v['part']}R" + ("+be" if v["part_be"] else "")
    s += f" hold{v['hold'] or 'flat'}"
    if v["trail"]:
        s += f" trail{v['trail']}@{v['tstart']}"
    if v["sw_trail"]:
        s += f" sw{'1m' if v['sw_trail'] == 1 else '5m'}@{v['sw_start']}"
    if v["choch"]:
        s += f" choch{'1m' if v['choch'] == 1 else '5m'}"
    if v["be"]:
        s += f" be{v['be']}"
    return s


def _job(v):
    try:
        r = evaluate(v)
    except Exception as e:                       # a broken variant must not kill the grid
        return {"v": v, "err": repr(e)}
    r["name"] = vname(v)
    return r


def run_grid(G, procs=3):
    from multiprocessing import Pool
    prep()
    t0 = time.time()
    with Pool(procs) as P:
        R = P.map(_job, G, chunksize=4)
    print(f"{len(R)} variants in {time.time() - t0:.0f}s", flush=True)
    return [r for r in R if "err" not in r], [r for r in R if "err" in r]


def ok_h1(r):
    return r["H1"]["tpw"] >= MIN_TPW and r["H1"]["wk2"] >= MIN_WK2


def show(r, base=None):
    s = []
    for sp in ("H1", "H2", "R"):
        x = r[sp]
        d = f"({x['avg_r'] - base[sp]['avg_r']:+.3f})" if base else ""
        s.append(f"{sp} {x['tpw']:4.1f}/wk R{x['avg_r']:+.3f}{d} t{x['t_r']:5.2f} PF{x['pf']:4.2f} ${x['per_month']:>5}/mo "
                 f"2w {x['f60']['p10']}/{x['f60']['f10']}")
    return f"{r['name'][:70]:70s} " + " | ".join(s)


def beats(r, b):
    """better than today's rule (b) in every span on avg R, $ / month and the 25K 2-week pass - fail (f60)."""
    out = {}
    for sp in ("H1", "H2", "R"):
        x, y = r[sp], b[sp]
        out[sp] = bool(x["avg_r"] > y["avg_r"] and x["per_month"] > y["per_month"]
                       and (x["f60"]["p10"] - x["f60"]["f10"]) > (y["f60"]["p10"] - y["f60"]["f10"]))
    out["all"] = all(out.values())
    return out


# ================================================================================================ baseline + account C
def cmd_baseline():
    prep(None)
    rows = {}
    for cm in (None, "lit", "atlas", "lit+atlas", "lit+atlas+armed"):
        r = evaluate({}, cm)
        r["name"] = f"today's rule, {cm or 'alone'}"
        rows[cm or "alone"] = r
        print(show(r), flush=True)
    # what the anti-hedge rule does to the trades: skipped / cut
    TT_a, TT_c = K.trades({}, None), K.trades({}, CMODE)
    for sp, tf in K.SPANS:
        A, _ = K.span(TT_a, sp, tf)
        C, _ = K.span(TT_c, sp, tf)
        ka = {(t["entry_t"], t["dir"]) for t in A}
        kc = {(t["entry_t"], t["dir"]) for t in C}
        rows[f"diff_{sp}"] = {"alone": len(A), "account_c": len(C), "dropped": len(ka - kc), "new": len(kc - ka),
                              "hedge_cut": sum(1 for t in C if t["exit_kind"] == "hedge")}
        print(sp, rows[f"diff_{sp}"])
    json.dump(rows, open(os.path.join(OUT, "b25_baseline.json"), "w"), default=float, indent=1)
    return rows


# ================================================================================================ stage 1: stops
def stop_specs():
    G = [{"stop": "atr", "k": k} for k in (1.0, 1.25, 1.5, 1.75, 2.0)]
    G += [{"stop": "sw5", "dmin": a, "dmax": b} for a, b in itertools.product((0.0, 0.5, 0.75, 1.0), (1.5, 2.0, 3.0, 99.0))]
    G += [{"stop": "sw1", "dmin": a, "dmax": b} for a, b in itertools.product((0.5, 0.75, 1.0), (2.0, 99.0))]
    G += [{"stop": f"low{n}", "dmin": a, "dmax": b} for n, a, b in itertools.product((15, 30, 60), (0.0, 0.5, 1.0), (2.0, 99.0))]
    return G


def cmd_stops():
    R, E = run_grid(stop_specs())
    base = next(r for r in R if r["v"] == {"stop": "atr", "k": 1.5})
    print("errors", E[:2])
    ok = sorted([r for r in R if ok_h1(r)], key=lambda r: -r["H1"]["t_r"])
    print(f"\n== stops ({len(ok)} of {len(R)} with >= {MIN_TPW}/wk), sorted by the H1 t-stat (pick); H2 / 2021-25 = check")
    for r in ok:
        print(show(r, base))
    json.dump({"base": base, "rows": R}, open(os.path.join(OUT, "b25_stops.json"), "w"), default=float)
    return R


# ================================================================================================ stage 2: targets / management
def mgmt_specs(stops):
    G = []
    for sv in stops:
        # (a) the clock family (today's shape)
        for hold, tr, pa in itertools.product((30, 45, 60), ((1.5, 1.0), (1.0, 1.0), (1.0, 0.5), (None, 1.0)), (None, 1.0, "liq")):
            G.append({**sv, "hold": hold, "trail": tr[0], "tstart": tr[1], "part": pa, "p_min": 0.5, "part_be": False})
        # (b) the structure-target family: target at the next opposing liquidity
        for (liq, rmin), rmax, hold, pa, tr in itertools.product((("all", 1.0), ("all", 1.5), ("all", 2.0), ("eq", 1.0), ("eq", 1.5), ("eq", 2.0)),
                                                                 (4.0, 99.0), (60, 0), (None, 0.5, 1.0), ((None, 1.0), (1.5, 1.0))):
            v = {**sv, "tgt": "liq", "liq": liq, "r_min": rmin, "r_max": rmax, "hold": hold, "trail": tr[0], "tstart": tr[1]}
            if pa is not None:
                v.update(part="liq", p_min=pa, part_be=True)
            G.append(v)
        # (c) structure management ("like a person"): no clock (or 2 hours), the stop follows each new protected swing,
        #     out on a change of character against the trade, optional liquidity target / partial
        for hold, sw, ch, tg, pa in itertools.product((0, 120), ((1, 0.5), (1, 1.0), (2, 0.0), (2, 0.5), (2, 1.0), (0, 1.0)), (0, 1, 2),
                                                      (None, ("eq", 1.5), ("all", 2.0)), (False, True)):
            if sw[0] == 0 and ch == 0:
                continue
            v = {**sv, "hold": hold, "trail": None, "sw_trail": sw[0], "sw_start": sw[1], "choch": ch}
            if tg:
                v.update(tgt="liq", liq=tg[0], r_min=tg[1], r_max=99.0)
            if pa:
                v.update(part="liq", p_min=0.5, part_be=True)
            G.append(v)
    return G


def cmd_mgmt(extra_stops=2):
    S1 = json.load(open(os.path.join(OUT, "b25_stops.json")))
    ok = sorted([r for r in S1["rows"] if ok_h1(r) and r["v"]["stop"] != "atr"], key=lambda r: -r["H1"]["t_r"])
    stops = [{"stop": "atr", "k": 1.5}, {"stop": "atr", "k": 1.0}, {"stop": "atr", "k": 2.0}] + [r["v"] for r in ok[:extra_stops]]
    print("stops:", stops, flush=True)
    G = mgmt_specs(stops)
    R, E = run_grid(G)
    print("errors", len(E), E[:2])
    base = evaluate({})
    base["name"] = "today"
    ok = sorted([r for r in R if ok_h1(r)], key=lambda r: -r["H1"]["t_r"])
    print(f"\n== management ({len(ok)} of {len(R)} with >= {MIN_TPW}/wk & {MIN_WK2}% weeks 2+), top 30 by the H1 t-stat")
    print(show(base))
    for r in ok[:30]:
        print(show(r, base))
    byev = sorted([r for r in R if ok_h1(r)], key=lambda r: -(r["H1"]["f60"]["p10"] - r["H1"]["f60"]["f10"]))
    print("\n== top 15 by the H1 25K 2-week pass - fail (60% of the room)")
    for r in byev[:15]:
        print(show(r, base))
    nb = [r for r in R if beats(r, base)["all"]]
    print(f"\n{len(nb)} of {len(R)} beat today's rule in H1, H2 and 2021-25 (avg R, $/mo, 25K 2-week pass-fail)")
    for r in sorted(nb, key=lambda r: -r["H1"]["t_r"])[:20]:
        print(show(r, base))
    fam = {}
    for r in R:
        f = "clock" if r["v"].get("sw_trail", 0) == 0 and r["v"].get("choch", 0) == 0 and r["v"].get("tgt") is None else (
            "target" if r["v"].get("sw_trail", 0) == 0 and r["v"].get("choch", 0) == 0 else "structure")
        fam.setdefault(f, []).append(r)
    summ = {f: {"n": len(rs), "beat_h1": sum(1 for r in rs if beats(r, base)["H1"]), "beat_h1_h2": sum(1 for r in rs if beats(r, base)["H1"] and beats(r, base)["H2"]),
                "beat_all": sum(1 for r in rs if beats(r, base)["all"])} for f, rs in fam.items()}
    print("families:", summ)
    json.dump({"base": base, "rows": R}, open(os.path.join(OUT, "b25_grid_mgmt.json"), "w"), default=float)
    top = {"base": base, "stops": stops, "families": summ, "top_h1_t": ok[:40], "top_h1_eval": byev[:20],
           "beat_all": sorted(nb, key=lambda r: -r["H1"]["t_r"])[:40], "pick": ok[0] if ok else None}
    json.dump(top, open(os.path.join(OUT, "b25_mgmt.json"), "w"), default=float)
    return R


# ================================================================================================ stage 4: new windows / entries
def idea_specs():
    G = []
    for wins in (("od",), ("od30",), ("ldn",), ("od", "rth"), ("od30", "rth"), ("ldn", "rth"), ("ldn", "od30", "rth")):
        for filt in ("prng>=0.8", "none"):
            G.append({"wins": wins, "filter": filt})
    for lim, w in itertools.product((0.25, 0.5, 0.75, "band"), (5, 10, 20)):
        G.append({"lim": lim, "lim_w": w})
    # "learn market structure": the 15m / 1h break-of-structure state (last close beyond a confirmed swing) - trade only with it,
    # not against it, or half size against it (a size change instead of a skip)
    for mode, mins in itertools.product(("with", "not_against", "size"), (15, 60)):
        G.append({"sfilter": (mode, mins)})
    return G


def cmd_ideas():
    """new ideas only: the opening drive (09:45-10:30 checks), London continuation (a band from the 03:00 open, checks
    04:00-08:30), each alone and added to today's window; a retest entry (limit x 5m-ATR back toward the band, or at the band,
    working 5-20 minutes, the same stop price) instead of the market entry. Plus: is a trade after a green start of the day
    better (intraday anti-martingale sizing)?"""
    R, E = run_grid(idea_specs())
    base = evaluate({})
    base["name"] = "today"
    for r in R:
        v = r["v"]
        r["name"] = (f"window {'+'.join(v['wins'])} {v['filter']}" if "wins" in v else
                     (f"HTF structure {v['sfilter'][0]} {v['sfilter'][1]}m" if "sfilter" in v else f"retest entry {v['lim']} x ATR5, {v['lim_w']} min"))
    print(show(base))
    for r in R:
        print(show(r, base))
    nb = [r["name"] for r in R if beats(r, base)["all"]]
    print(f"{len(nb)} of {len(R)} beat today's rule in H1, H2 and 2021-25: {nb}")
    # same-day sequence: avg R of a day's 1st trade / after a green start / after a red start (today's rule, account C)
    import collections
    TT = K.trades({}, CMODE)
    seq = {}
    for sp, tf in K.SPANS:
        T, _ = K.span(TT, sp, tf)
        by = collections.defaultdict(list)
        for t in T:
            by[t["day"]].append(t)
        g = collections.defaultdict(list)
        for ts in by.values():
            cum = 0.0
            for k_, t in enumerate(ts):
                r_ = t["pnl_pm"] / t["risk_pm"]
                g["first" if k_ == 0 else ("after_green" if cum > 0 else "after_red")].append(r_)
                cum += r_
        seq[sp] = {k_: {"n": len(v_), "avg_r": round(float(np.mean(v_)), 3), "t": round(float(np.mean(v_) / (np.std(v_) / np.sqrt(len(v_)))), 2)}
                   for k_, v_ in g.items()}
    print("same-day sequence:", seq)
    json.dump({"base": base, "rows": R, "beat_all": nb, "sequence": seq}, open(os.path.join(OUT, "b25_ideas.json"), "w"), default=float)


# ================================================================================================ honesty checks of today's rule as account C
def cmd_checks(seeds=40):
    """random directions (same signal bars, coin-flip side, stop mirrored at the same distance), 1-2 extra ticks a side, 1-2
    bars late, the LIT armed rule; how often an H1 improvement of the rule grid carried over to H2 / 2021-25."""
    prep()
    out = {}
    base = evaluate({})
    real = {sp: base[sp]["avg_r"] for sp in ("H1", "H2", "R")}
    pl = [evaluate({}, placebo=s, sizes={}) for s in range(seeds)]
    out["placebo"] = {sp: {"real": real[sp], "mean": round(float(np.mean([p[sp]["avg_r"] for p in pl])), 3),
                           "p": round((1 + sum(1 for p in pl if p[sp]["avg_r"] >= real[sp])) / (seeds + 1), 3)} for sp in ("H1", "H2", "R")}
    print("random directions:", out["placebo"], flush=True)
    st = {}
    for nm, v in (("1 bar late", {"late": 1}), ("2 bars late", {"late": 2})):
        r = evaluate(v)
        st[nm] = {sp: {"avg_r": r[sp]["avg_r"], "pf": r[sp]["pf"], "per_month": r[sp]["per_month"], "f40": r[sp]["f40"]} for sp in ("H1", "H2", "R")}
    # extra slippage: every trade's points minus 2 x extra ticks (entry + exit), the worst open point worse by one
    TT = K.trades({}, CMODE)
    for xt in (1, 2):
        T2 = {tf: [{**t, "pts": t["pts"] - 2 * xt * K.TICK, "pnl_pm": t["pnl_pm"] - 2 * xt * K.TICK * K.PV, "mae_pm": t["mae_pm"] - xt * K.TICK * K.PV}
                   for t in TT[tf]] for tf in TT}
        L = K.lines(T2)
        st[f"+{xt} tick a side"] = {}
        for sp, tf in K.SPANS:
            T, S = K.span(T2, sp, tf)
            st[f"+{xt} tick a side"][sp] = {"avg_r": L[sp]["avg_r"], "pf": L[sp]["pf"], "per_month": L[sp]["per_month"],
                                            "f40": {k_: v_ for k_, v_ in N.eval_score(T, S, "25k", SIZES["f40"], paths=False).items() if k_ in EV_KEYS}}
    out["stress"] = st
    for nm, x in st.items():
        print(nm, {sp: (x[sp]["avg_r"], x[sp]["pf"], x[sp]["per_month"], x[sp]["f40"]["p10"], x[sp]["f40"]["f10"]) for sp in x}, flush=True)
    # carry-over of the rule grid (stage 2): of the variants better than today in H1 (avg R and $ / month), how many also in H2 / 2021-25
    G = json.load(open(os.path.join(OUT, "b25_grid_mgmt.json")))
    b = G["base"]
    better = lambda r, sp: r[sp]["avg_r"] > b[sp]["avg_r"] and r[sp]["per_month"] > b[sp]["per_month"]
    h1 = [r for r in G["rows"] if better(r, "H1")]
    out["carry"] = {"n": len(G["rows"]), "better_h1": len(h1), "and_h2": sum(1 for r in h1 if better(r, "H2")),
                    "and_r": sum(1 for r in h1 if better(r, "R")), "and_both": sum(1 for r in h1 if better(r, "H2") and better(r, "R")),
                    "better_all_incl_eval": sum(1 for r in G["rows"] if beats(r, b)["all"])}
    print("carry-over:", out["carry"])
    json.dump(out, open(os.path.join(OUT, "b25_checks.json"), "w"), default=float, indent=1)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"baseline": cmd_baseline, "stops": cmd_stops, "mgmt": cmd_mgmt, "ideas": cmd_ideas, "checks": cmd_checks}[a[0] if a else "baseline"]()
