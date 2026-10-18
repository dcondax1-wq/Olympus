"""Rules and model for tools/lit_select.py (grade / wait / size-by-grade, walk-forward logistic model). Run through
`python tools/lit_select.py rules|rank|model|save`. Pick on 2026 H1, check on H2; 2021-25 is a reference line. 1 CPU process."""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import lit_select as S  # noqa: E402

OUTD = os.path.join(ROOT, "research", "lit")
SP = ("H1", "H2", "2026", "2021-25")
KEYS = ("funded_net", "funded_pf", "funded_dd", "w_r", "n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "dec10", "p15", "f15", "p20", "f20", "pass_rate",
        "pass_med", "slow_pass", "b2b", "med_q", "med_risk", "tot_r", "avg_r")


def rows():
    return S.build()["rows"]


def compact(o):
    return {s: {k: o[s].get(k) for k in KEYS} for s in o}


# ================================================================================================ grades
def trader_grade(f):
    """The trader's grade, written from LIT practice before looking at outcomes: 1 point each for
      a fresh trap      the inducement swing was made <= 6 bars (30 min) before the sweep
      quality liquidity 2+ levels taken by the sweep, or a daily/weekly/monthly level or opening gap
      room to run      the first opposing level is >= 1.5R away (or none before the VIX band)
      clean clock      no high-impact release in the next 60 minutes, and the entry is in the London morning (02:00-08:00)
    A = 4, B = 2-3, C = 0-1."""
    p = int(f["idm_age"] <= 6) + int(f["n_swept"] >= 2 or f["major"] == 1) + int(f["obst_r"] >= 1.5) + \
        int(f["news_next"] > 60 and f["mod"] < 480)
    return "A" if p >= 4 else "B" if p >= 2 else "C"


def rank(spans=("H1",), quiet=False):
    """Every feature split on the H1 candidates (each setup alone, unit size): the good side's win % and avg R vs the rest.
    Ranked by the z-score of the win-rate difference, with the good side's avg R also higher and n >= 25 on both sides."""
    R = [r for r in S.span_rows(rows(), "H1") if r["u"] is not None]
    out = []
    for nm in S.NUMF + S.BINF:
        v = np.array([r["f"][nm] for r in R]); y = np.array([r["u"]["r1"] for r in R])
        ok = ~np.isnan(v)
        if ok.sum() < 60:
            continue
        v, y = v[ok], y[ok]
        if nm in S.BINF:
            tests = [(f"{nm} = 1", v >= 0.5), (f"{nm} = 0", v < 0.5)]
        else:
            q1, q2 = np.quantile(v, [1 / 3, 2 / 3])
            tests = [(f"{nm} <= {q1:.3g}", v <= q1), (f"{nm} >= {q2:.3g}", v >= q2), (f"{nm} in ({q1:.3g}, {q2:.3g})", (v > q1) & (v < q2)),
                     (f"{nm} > {q1:.3g}", v > q1), (f"{nm} < {q2:.3g}", v < q2)]
        for lab, m in tests:
            if m.sum() < 25 or (~m).sum() < 25:
                continue
            w1, w0 = (y[m] > 0.5).mean(), (y[~m] > 0.5).mean()
            pp = (y > 0.5).mean()
            se = np.sqrt(pp * (1 - pp) * (1 / m.sum() + 1 / (~m).sum())) or 1e-9
            out.append({"feature": nm, "rule": lab, "n": int(m.sum()), "win": round(100 * w1, 1), "win_rest": round(100 * w0, 1),
                        "avg_r": round(float(y[m].mean()), 3), "avg_r_rest": round(float(y[~m].mean()), 3), "z": round(float((w1 - w0) / se), 2)})
    out = [o for o in out if o["avg_r"] > o["avg_r_rest"]]
    out.sort(key=lambda o: -o["z"])
    if not quiet:
        for o in out[:25]:
            print(f"{o['rule']:34s} n={o['n']:3d} win {o['win']:5.1f} vs {o['win_rest']:5.1f}  avgR {o['avg_r']:+.2f} vs {o['avg_r_rest']:+.2f}  z {o['z']}")
    return out


def data_grade_spec():
    """The data grade: the top 4 H1 splits from rank(), one per feature and family, each a point; A = 3-4, B = 1-2? No: thresholds
    from the H1 point distribution (A = the top ~quarter of points, C = 0 points)."""
    fam = {"idm_age": "trap", "idm_dist": "trap", "idm_n": "trap", "mod": "clock", "lv_taken": "clock", "sess": "clock",
           "sweep_lon": "clock", "news_next": "clock", "news_day": "clock", "stop_pts": "stop", "stop_atr": "stop", "depth": "sweep",
           "n_swept": "sweep", "major": "sweep", "bu_only": "sweep", "box": "sweep", "rr": "room", "obst_r": "room",
           "last3_r": "recent", "last5_w": "recent", "prev_win": "recent", "wk_stops": "recent"}
    picked, fams = [], set()
    for o in rank(quiet=True):
        fm = fam.get(o["feature"], o["feature"])
        if fm in fams:
            continue
        picked.append(o); fams.add(fm)
        if len(picked) == 4:
            break
    return picked


def _test(rule, f):
    """Evaluate a rank() rule string on features f."""
    import re
    m = re.match(r"(\w+) (<=|>=|=|>|<|in) (.+)", rule)
    nm, op, val = m.group(1), m.group(2), m.group(3)
    v = f[nm]
    if np.isnan(v):
        return False
    if op == "=":
        return v >= 0.5 if val == "1" else v < 0.5
    if op == "in":
        a, b = (float(x) for x in val.strip("()").split(","))
        return a < v < b
    x = float(val)
    return {"<=": v <= x, ">=": v >= x, ">": v > x, "<": v < x}[op]


def make_data_grade(spec):
    def g(f):
        p = sum(_test(o["rule"], f) for o in spec)
        return "A" if p >= 3 else "B" if p >= 1 else "C"
    return g


# ================================================================================================ the rule grid
def rule_grid(G, tag):
    """Wait / skip / size-by-grade / second-trade rules for grade function G(features) -> A/B/C."""
    gr = lambda r: G(r["f"])
    V = collections.OrderedDict()
    V[f"{tag}: skip C (wait for a better setup)"] = dict(skip=lambda r: gr(r) == "C")
    V[f"{tag}: A only"] = dict(skip=lambda r: gr(r) != "A")
    for a, b, c in ((1.5, 1.0, 0.5), (1.25, 1.0, 0.5), (1.5, 1.0, 1.0), (1.25, 1.0, 1.0), (1.0, 1.0, 0.5), (1.5, 1.0, 0.75)):
        V[f"{tag}: size A {a:g} / B {b:g} / C {c:g}"] = dict(size=lambda r, a=a, b=b, c=c: {"A": a, "B": b, "C": c}[gr(r)])
    V[f"{tag}: skip C, A 1.5x"] = dict(skip=lambda r: gr(r) == "C", size=lambda r: 1.5 if gr(r) == "A" else 1.0)
    V[f"{tag}: 2 a day, the 2nd only if A"] = dict(max_per_day=2, second=lambda r: gr(r) == "A")
    V[f"{tag}: 2 a day, the 2nd only if A, C 0.5x"] = dict(max_per_day=2, second=lambda r: gr(r) == "A",
                                                          size=lambda r: 0.5 if gr(r) == "C" else 1.0)
    return V


def run_rule(R, spec):
    U = S.replay(R, skip=spec.get("skip"), size=spec.get("size"), max_per_day=spec.get("max_per_day", 1), second=spec.get("second"))
    o = S.score(U)
    fu = funded(U)
    for s in o:
        o[s]["funded_net"] = fu[s]["net"]; o[s]["funded_pf"] = fu[s]["pf"]; o[s]["funded_dd"] = fu[s]["dd"]; o[s]["w_r"] = fu[s]["w_r"]
    return o, U


def grade_mix(R, G):
    """Candidate-level outcome by grade (each setup alone), per span."""
    out = {}
    for s in ("H1", "H2", "2021-25"):
        RR = [r for r in S.span_rows(R, s)]
        out[s] = {g: {**S.cand_stats([r for r in RR if G(r["f"]) == g]), "cands": sum(1 for r in RR if G(r["f"]) == g)} for g in "ABC"}
    return out


def taken_mix(U, G):
    out = {}
    for s in ("H1", "H2", "2021-25"):
        a, z = S.SPAN[s]
        TT = [t for t in U if a <= t["day"] <= z]
        o = {}
        for g in "ABC":
            rr = np.array([t["r1"] for t in TT if G(t["_row"]["f"]) == g])
            o[g] = {"n": len(rr), "win": round(100 * float((rr > 0.5).mean()), 1) if len(rr) else None,
                    "avg_r": round(float(rr.mean()), 3) if len(rr) else None}
        out[s] = o
    return out


def rules():
    R = rows()
    res = collections.OrderedDict()
    base_o, base_U = run_rule(R, {})
    res["LIT live, eval sizing (base)"] = {"o": compact(base_o)}
    print("BASE")
    for s in SP:
        print("  " + S.line(base_o, s), "| funded", base_o[s]["funded_net"], "wR", base_o[s]["w_r"])
    spec = data_grade_spec()
    print("data grade (picked on H1):", [o["rule"] for o in spec])
    grades = {"trader": trader_grade, "data": make_data_grade(spec)}
    mix = {}
    for tag, G in grades.items():
        mix[tag] = {"candidates": grade_mix(R, G), "taken_live": taken_mix(base_U, G)}
        print(tag, "grade, candidates alone:", json.dumps(mix[tag]["candidates"]))
        print(tag, "grade, live trades:", json.dumps(mix[tag]["taken_live"]))
        for nm, sp in rule_grid(G, tag).items():
            o, U = run_rule(R, sp)
            res[nm] = {"o": compact(o)}
            b = base_o
            print(f"{nm}\n  " + "\n  ".join(S.line(o, s) for s in SP) +
                  f"\n  dNet H1 {o['H1']['net'] - b['H1']['net']:+,} H2 {o['H2']['net'] - b['H2']['net']:+,} "
                  f"| d2wk pass H1 {o['H1']['p10'] - b['H1']['p10']:+.1f} H2 {o['H2']['p10'] - b['H2']['p10']:+.1f}"
                  f"| funded dNet H1 {o['H1']['funded_net'] - b['H1']['funded_net']:+,} H2 {o['H2']['funded_net'] - b['H2']['funded_net']:+,}"
                  f" wR {o['H1']['w_r']} / {o['H2']['w_r']} (base {b['H1']['w_r']} / {b['H2']['w_r']})", flush=True)
    json.dump({"base": res["LIT live, eval sizing (base)"], "rules": res, "data_grade": spec, "mix": mix},
              open(os.path.join(OUTD, "select_results.json"), "w"), indent=1, default=str)


# ================================================================================================ money lines that do not depend on the eval path
def funded(U, spans=("H1", "H2", "2026", "2021-25")):
    """The same trades at the eval base size ($800 up to 25 pts, weekly stop, grade multiplier) with no room cap: $ that do not
    depend on when back-to-back evals pass or fail. Plus R-units: sum of (R x grade multiplier)."""
    T = S.TL.sized(U, S.EVAL_RULE)
    out = {}
    for s in spans:
        st = S.TL.stats(T, s)
        a, z = S.SPAN[s]
        st["w_r"] = round(sum(t["r1"] * t.get("g_m", 1.0) * t.get("wk_m", 1.0) for t in U if a <= t["day"] <= z), 1)
        out[s] = {k: st.get(k) for k in ("n", "net", "per_month", "pf", "dd", "w_r")}
    return out


def fline(o, s):
    x = o[s]
    return f"{s}: funded net {x['net']:+,} PF {x['pf']} DD {x['dd']:,} weighted R {x['w_r']}"
