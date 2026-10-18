"""Rules and model for tools/lit_select.py (grade / wait / size-by-grade, walk-forward logistic model). Run through
`python tools/lit_select.py rules|rank|model|save`. Pick on 2026 H1, check on H2; 2021-25 is a reference line. 1 CPU process."""
from __future__ import annotations

import collections
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import lit_select as S  # noqa: E402

OUTD = os.path.join(ROOT, "research", "lit")
SP = ("H1", "H1a", "H1b", "H2", "2026", "2021-25")
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
def funded(U, spans=("H1", "H1a", "H1b", "H2", "2026", "2021-25")):
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


# ================================================================================================ trader-grade anatomy
TG_PARTS = {
    "fresh trap (inducement <= 6 bars)": lambda f: f["idm_age"] <= 6,
    "quality liquidity (2+ levels or a major one)": lambda f: f["n_swept"] >= 2 or f["major"] == 1,
    "room to run (first obstacle >= 1.5R)": lambda f: f["obst_r"] >= 1.5,
    "clean clock (London morning, no release within 60 min)": lambda f: f["news_next"] > 60 and f["mod"] < 480,
}


def tg_variant(drop=None, a_min=4, b_min=2):
    def g(f):
        p = sum(int(fn(f)) for nm, fn in TG_PARTS.items() if nm != drop)
        return "A" if p >= a_min else "B" if p >= b_min else "C"
    return g


def anatomy():
    R = rows()
    out = {}
    for nm, fn in TG_PARTS.items():
        o = {}
        for s in ("H1", "H2", "2021-25"):
            RR = S.span_rows(R, s)
            o[s] = {"yes": S.cand_stats([r for r in RR if fn(r["f"])]), "no": S.cand_stats([r for r in RR if not fn(r["f"])])}
        out[nm] = o
        print(nm, json.dumps(o))
    # points distribution
    for s in ("H1", "H2", "2021-25"):
        RR = S.span_rows(R, s)
        for p in range(5):
            sel = [r for r in RR if sum(int(fn(r["f"])) for fn in TG_PARTS.values()) == p]
            print(s, "points", p, "cands", len(sel), S.cand_stats(sel))
    # neighbours of the grade: drop one part (A = all 3 left), A at 3+ points
    vv = collections.OrderedDict()
    for nm in TG_PARTS:
        vv[f"without '{nm}' (A = 3/3, B = 1-2)"] = tg_variant(drop=nm, a_min=3, b_min=1)
    vv["A at 3+ points, B 2, C 0-1"] = tg_variant(a_min=3, b_min=2)
    vv["A at 4, B 1-3, C 0"] = tg_variant(a_min=4, b_min=1)
    res = {}
    for nm, G in vv.items():
        o, U = run_rule(R, dict(size=lambda r, G=G: {"A": 1.5, "B": 1.0, "C": 0.5}[G(r["f"])]))
        res[nm] = compact(o)
        print(f"A1.5/B1/C0.5 with grade {nm}: H1 {o['H1']['net']:+,} (funded {o['H1']['funded_net']:+,}) H2 {o['H2']['net']:+,} "
              f"(funded {o['H2']['funded_net']:+,}) 2wk {o['H1']['p10']}/{o['H2']['p10']} | 2021-25 {o['2021-25']['net']:+,} PF {o['2021-25']['pf']}")
    json.dump({"parts": out, "neighbours": res}, open(os.path.join(OUTD, "select_anatomy.json"), "w"), indent=1, default=str)


# ================================================================================================ the model (walk-forward)
FEATS = S.NUMF + S.BINF


def _xy(RR, cols, med=None):
    X = np.array([[r["f"][c] for c in cols] for r in RR], dtype=float)
    if med is None:
        med = np.nanmedian(X, axis=0)
        med = np.where(np.isnan(med), 0.0, med)
    X = np.where(np.isnan(X), med, X)
    return X, med


def logit_fit(X, y, lam):
    """L2-penalised logistic regression (Newton steps), intercept unpenalised. X standardised by the caller."""
    n, p = X.shape
    Xa = np.c_[np.ones(n), X]
    w = np.zeros(p + 1)
    w[0] = math.log((y.mean() + 1e-6) / (1 - y.mean() + 1e-6))
    Lm = lam * np.eye(p + 1); Lm[0, 0] = 0.0
    for _ in range(50):
        z = Xa @ w
        pr = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
        g = Xa.T @ (pr - y) + Lm @ w
        Hs = Xa.T @ (Xa * (pr * (1 - pr))[:, None]) + Lm + 1e-9 * np.eye(p + 1)
        st = np.linalg.solve(Hs, g)
        w -= st
        if np.abs(st).max() < 1e-7:
            break
    return w


def logit_pred(w, X):
    return 1 / (1 + np.exp(-np.clip(np.c_[np.ones(len(X)), X] @ w, -30, 30)))


def stumps_fit(X, y, rounds=60, lr=0.1, min_leaf=12):
    """Gradient-boosted decision stumps (logistic loss), the shallowest boosting there is."""
    n, p = X.shape
    f0 = math.log((y.mean() + 1e-6) / (1 - y.mean() + 1e-6))
    F_ = np.full(n, f0)
    model = []
    qs = [np.unique(np.quantile(X[:, j], np.linspace(0.1, 0.9, 9))) for j in range(p)]
    for _ in range(rounds):
        pr = 1 / (1 + np.exp(-F_))
        g = y - pr; h = pr * (1 - pr)
        best = None
        for j in range(p):
            for th in qs[j]:
                L = X[:, j] <= th
                nl = L.sum()
                if nl < min_leaf or n - nl < min_leaf:
                    continue
                gl, gr = g[L].sum(), g[~L].sum(); hl, hr = h[L].sum() + 1.0, h[~L].sum() + 1.0
                gain = gl * gl / hl + gr * gr / hr
                if best is None or gain > best[0]:
                    best = (gain, j, th, gl / hl, gr / hr)
        if best is None:
            break
        _, j, th, vl, vr = best
        model.append((j, th, lr * vl, lr * vr))
        F_ += np.where(X[:, j] <= th, lr * vl, lr * vr)
    return (f0, model)


def stumps_pred(m, X):
    f0, model = m
    F_ = np.full(len(X), f0)
    for j, th, vl, vr in model:
        F_ += np.where(X[:, j] <= th, vl, vr)
    return 1 / (1 + np.exp(-F_))


def _month_cv_lam(RR, cols, lams=(1.0, 3.0, 10.0, 30.0, 100.0, 300.0)):
    """Leave-one-month-out log loss inside the training rows -> the L2 strength."""
    months = sorted({r["day"][:7] for r in RR})
    best = None
    for lam in lams:
        ll = []
        for m in months:
            tr = [r for r in RR if r["day"][:7] != m]; te = [r for r in RR if r["day"][:7] == m]
            if not te or len({r["u"]["r1"] > 0.5 for r in tr}) < 2:
                continue
            Xtr, med = _xy(tr, cols); mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
            ytr = np.array([r["u"]["r1"] > 0.5 for r in tr], float)
            w = logit_fit(np.clip((Xtr - mu) / sd, -4, 4), ytr, lam)
            Xte, _ = _xy(te, cols, med)
            p = np.clip(logit_pred(w, np.clip((Xte - mu) / sd, -4, 4)), 1e-4, 1 - 1e-4)
            yte = np.array([r["u"]["r1"] > 0.5 for r in te], float)
            ll += list(-(yte * np.log(p) + (1 - yte) * np.log(1 - p)))
        v = float(np.mean(ll))
        if best is None or v < best[0]:
            best = (v, lam)
    return best[1]


FOLDS = [("fold 1: train Jan-Apr 2026, test May-Jun", ("2026-01-01", "2026-04-30"), ("2026-05-01", "2026-06-30")),
         ("fold 2: train Jan-Jun 2026, test Jul-Oct", ("2026-01-01", "2026-06-30"), ("2026-07-01", "2026-12-31"))]


def fit_fold(R, tr_span, te_span, kind="logit", with_past=False, cols=FEATS):
    a, z = tr_span
    tr = [r for r in R if r["u"] is not None and a <= r["day"] <= z]
    if with_past:
        tr = [r for r in R if r["u"] is not None and r["day"] < "2026"] + tr
    Xtr, med = _xy(tr, cols); mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    Ztr = np.clip((Xtr - mu) / sd, -4, 4)
    ytr = np.array([r["u"]["r1"] > 0.5 for r in tr], float)
    te = [r for r in R if te_span[0] <= r["day"] <= te_span[1]]              # every candidate of the test span (filled or not)
    Zte = np.clip((_xy(te, cols, med)[0] - mu) / sd, -4, 4)
    if kind == "logit":
        lam = _month_cv_lam(tr, cols)
        w = logit_fit(Ztr, ytr, lam)
        p_tr, p_te = logit_pred(w, Ztr), logit_pred(w, Zte)
        info = {"lam": lam, "coef": {c: round(float(v), 3) for c, v in zip(cols, w[1:])}}
    else:
        m = stumps_fit(Ztr, ytr)
        p_tr, p_te = stumps_pred(m, Ztr), stumps_pred(m, Zte)
        cnt = collections.Counter(cols[j] for j, *_ in m[1])
        info = {"splits": dict(cnt.most_common(10))}
    return {"train_n": len(tr), "train_wins": int(ytr.sum()), "p_tr": p_tr, "te": te, "p_te": p_te, "info": info}


def calib(te, p, bins=4):
    rr = [(pp, r["u"]["r1"]) for r, pp in zip(te, p) if r["u"] is not None]
    if not rr:
        return []
    ps = np.array([a for a, b in rr]); ys = np.array([b for a, b in rr])
    qs = np.quantile(ps, np.linspace(0, 1, bins + 1))
    out = []
    for b in range(bins):
        m = (ps >= qs[b]) & (ps <= qs[b + 1]) if b == bins - 1 else (ps >= qs[b]) & (ps < qs[b + 1])
        if m.sum():
            out.append({"p_from": round(float(qs[b]), 3), "p_to": round(float(qs[b + 1]), 3), "n": int(m.sum()),
                        "pred_win": round(100 * float(ps[m].mean()), 1), "real_win": round(100 * float((ys[m] > 0.5).mean()), 1),
                        "avg_r": round(float(ys[m].mean()), 2)})
    return out


def auc(te, p):
    rr = [(pp, r["u"]["r1"] > 0.5) for r, pp in zip(te, p) if r["u"] is not None]
    pos = [a for a, b in rr if b]; neg = [a for a, b in rr if not b]
    if not pos or not neg:
        return None
    return round(float(np.mean([(x > y) + 0.5 * (x == y) for x in pos for y in neg])), 3)


def model():
    R = rows()
    rep = {}
    for kind, past in (("logit", False), ("stumps", False), ("logit", True)):
        tag = f"{kind}{' + 2021-25 in training' if past else ''}"
        rep[tag] = {}
        P_te = {}
        for nm, trs, tes in FOLDS:
            o = fit_fold(R, trs, tes, kind, past)
            for r, pp in zip(o["te"], o["p_te"]):
                P_te[r["key"]] = float(pp)
            thr = {q: float(np.quantile(o["p_tr"], q)) for q in (0.25, 0.5, 0.75)}
            rep[tag][nm] = {"train_n": o["train_n"], "train_wins": o["train_wins"], "auc_test": auc(o["te"], o["p_te"]),
                            "calibration": calib(o["te"], o["p_te"]), "info": o["info"], "thr": thr,
                            "mean_p_train": float(np.mean(o["p_tr"]))}
            print(tag, nm, "train", o["train_n"], "wins", o["train_wins"], "AUC test", rep[tag][nm]["auc_test"], o["info"].get("lam"))
            for c in rep[tag][nm]["calibration"]:
                print("   ", c)
        rep[tag]["_p"] = P_te
    # importances in plain words: the fold-2 logistic coefficients (standardised)
    co = rep["logit"][FOLDS[1][0]]["info"]["coef"]
    print("fold 2 logit coefficients (per 1 sd):", sorted(co.items(), key=lambda kv: -abs(kv[1]))[:12])
    # rules from the model (thresholds from the training predictions of each fold only)
    res = collections.OrderedDict()
    base_o, _ = run_rule(R, {})
    res["base"] = compact(base_o)
    for tag in rep:
        P_te = rep[tag]["_p"]
        TH = {}
        for nm, trs, tes in FOLDS:
            for r in R:
                if tes[0] <= r["day"] <= tes[1]:
                    TH[r["key"]] = (rep[tag][nm]["thr"], rep[tag][nm]["mean_p_train"])
        pk = lambda r: P_te.get(r["key"])

        def lo(q):
            return lambda r: (pk(r) is not None and pk(r) < TH[r["key"]][0][q])

        def hi(q):
            return lambda r: (pk(r) is not None and pk(r) >= TH[r["key"]][0][q])
        V = collections.OrderedDict()
        V["skip the bottom quarter (wait)"] = dict(skip=lo(0.25))
        V["size: top quarter 1.5x, bottom quarter 0.5x"] = dict(size=lambda r: 1.5 if hi(0.75)(r) else 0.5 if lo(0.25)(r) else 1.0)
        V["size: top quarter 1.25x, bottom quarter 0.5x"] = dict(size=lambda r: 1.25 if hi(0.75)(r) else 0.5 if lo(0.25)(r) else 1.0)
        V["size: p / mean p, 0.5x-1.5x"] = dict(size=lambda r: 1.0 if pk(r) is None else float(np.clip(pk(r) / TH[r["key"]][1], 0.5, 1.5)))
        V["2 a day, the 2nd only in the top quarter"] = dict(max_per_day=2, second=hi(0.75))
        for nm, sp in V.items():
            o, U = run_rule(R, sp)
            res[f"{tag}: {nm}"] = compact(o)
            print(f"{tag}: {nm}\n  H1b {_short(o, base_o, 'H1b')} \n  H2  {_short(o, base_o, 'H2')}", flush=True)
    for t in rep:
        rep[t].pop("_p")
    json.dump({"model": rep, "rules": res}, open(os.path.join(OUTD, "select_model.json"), "w"), indent=1, default=str)


def _short(o, b, s):
    x, y = o[s], b[s]
    return (f"n {x['n']} {x['tpw']}/wk win {x['win']} PF {x['pf']} net {x['net']:+,} (d {x['net'] - y['net']:+,}) funded "
            f"{x['funded_net']:+,} (d {x['funded_net'] - y['funded_net']:+,}) 2wk {x['p10']}/{x['f10']} (base {y['p10']}/{y['f10']}) "
            f"1mo {x['p20']}/{x['f20']} pr {x['pass_rate']}")


# ================================================================================================ one-feature size rules (pick on H1)
def single():
    """The top H1 splits of rank() as size rules: good side x up (risk cap $900), the rest x down. Picked on H1, checked on H2."""
    R = rows()
    base_o, _ = run_rule(R, {})
    top = rank(quiet=True)[:15]
    # the trap-age family by hand (a trader's single most quoted LIT filter: a fresh inducement)
    fam = [{"rule": f"idm_age <= {a}"} for a in (3, 5, 6, 8, 10, 12)]
    res = collections.OrderedDict()
    for o in top + fam:
        rule = o["rule"]
        for up, dn in ((1.5, 1.0), (1.25, 1.0), (1.0, 0.5), (1.5, 0.5), (1.25, 0.75)):
            sp = dict(size=lambda r, rule=rule, up=up, dn=dn: up if _test(rule, r["f"]) else dn)
            oo, U = run_rule(R, sp)
            nm = f"{rule}: {up:g}x / else {dn:g}x"
            res[nm] = compact(oo)
            d1 = oo["H1"]["funded_net"] - base_o["H1"]["funded_net"]; d2 = oo["H2"]["funded_net"] - base_o["H2"]["funded_net"]
            e1 = oo["H1"]["net"] - base_o["H1"]["net"]; e2 = oo["H2"]["net"] - base_o["H2"]["net"]
            print(f"{nm:42s} funded dH1 {d1:+7,} dH2 {d2:+7,} | eval-path dH1 {e1:+7,} dH2 {e2:+7,} | 2wk p/f H1 {oo['H1']['p10']}/{oo['H1']['f10']} "
                  f"H2 {oo['H2']['p10']}/{oo['H2']['f10']} | 2021-25 funded {oo['2021-25']['funded_net']:+,}", flush=True)
    json.dump(res, open(os.path.join(OUTD, "select_single.json"), "w"), indent=1, default=str)


# ================================================================================================ finalists: size-neutral check, permutation test, runs
def trap_size(age, up=1.25, dn=0.75):
    return dict(size=lambda r: up if r["f"]["idm_age"] <= age else dn)


def grade_size(a=1.5, b=1.0, c=0.5, G=None):
    G = G or trader_grade
    return dict(size=lambda r: {"A": a, "B": b, "C": c}[G(r["f"])])


FINAL = collections.OrderedDict([
    ("lit_sel_trap8_size", ("Fresh trap sizing: 1.25x when the inducement swing is <= 8 bars (40 min) old, else 0.75x", trap_size(8),
                            "adopt-candidate")),
    ("lit_sel_trap6_size", ("Fresh trap sizing: 1.25x when the inducement swing is <= 6 bars (30 min) old, else 0.75x", trap_size(6),
                            "promising")),
    ("lit_sel_grade_size", ("Trader's A/B/C grade (fresh trap, quality liquidity, room to run, clean clock): A 1.5x / B 1x / C 0.5x, "
                            "a size-up never risks more than $900", grade_size(), "promising")),
    ("lit_sel_grade_skipc", ("Trader's grade: skip a C setup and keep the day free for a later one (wait for a better setup)",
                             dict(skip=lambda r: trader_grade(r["f"]) == "C"), "rejected")),
    ("lit_sel_data_grade", ("Data-mined grade (top 4 H1 splits: sweep depth 1.6-2.7 ATR, inducement < 0.39 ATR above the level, "
                            "CISD leg >= 5 bars, Asia range 0.39-0.52 VIX moves): A 1.5x / B 1x / C 0.5x", None, "rejected")),
    ("lit_sel_model_size", ("Walk-forward logistic model (50 features, L2 by month CV): top quarter 1.25x, bottom quarter 0.5x",
                            None, "rejected")),
])


def _perm(R, U, spans=("H1", "H2"), n=400, seed=3):
    """Shuffle the rule's size multipliers among the same trades of each half (the path is kept): share of shuffles whose
    funded net is >= the rule's. Small = the rule's sizes sit on better trades than chance (selection, not leverage)."""
    rng = np.random.default_rng(seed)
    out = {}
    for s in spans:
        a, z = S.SPAN[s]
        TT = [dict(t) for t in U if a <= t["day"] <= z]
        act = sum(t["pnl"] for t in S.TL.sized(TT, S.EVAL_RULE))
        gm = np.array([t["g_m"] for t in TT])
        cnt = 0
        for _ in range(n):
            pm = rng.permutation(gm)
            for t, m in zip(TT, pm):
                t["g_m"] = float(m)
            cnt += sum(t["pnl"] for t in S.TL.sized(TT, S.EVAL_RULE)) >= act - 1e-6
        R_ = np.array([t["r1"] for t in TT]); W = gm
        out[s] = {"p": round(cnt / n, 3), "avg_r": round(float(R_.mean()), 3), "avg_r_w": round(float((R_ * W).sum() / W.sum()), 3),
                  "mean_mult": round(float(W.mean()), 3)}
    return out


def _model_spec(R):
    P_te, TH = {}, {}
    for nm, trs, tes in FOLDS:
        o = fit_fold(R, trs, tes, "logit", False)
        thr = {q: float(np.quantile(o["p_tr"], q)) for q in (0.25, 0.75)}
        for r, pp in zip(o["te"], o["p_te"]):
            P_te[r["key"]] = float(pp); TH[r["key"]] = thr

    def size(r):
        p = P_te.get(r["key"])
        if p is None:
            return 1.0
        return 1.25 if p >= TH[r["key"]][0.75] else 0.5 if p < TH[r["key"]][0.25] else 1.0
    return dict(size=size)


def finalists(save=False):
    R = rows()
    base_o, base_U = run_rule(R, {})
    out = {"base": compact(base_o)}
    print("BASE")
    for s in SP:
        print("  " + S.line(base_o, s), "| funded", base_o[s]["funded_net"])
    for rid, (title, spec, status) in FINAL.items():
        if rid == "lit_sel_data_grade":
            spec = grade_size(G=make_data_grade(data_grade_spec()))
        if rid == "lit_sel_model_size":
            spec = _model_spec(R)
        o, U = run_rule(R, spec)
        pm = _perm(R, U) if spec.get("size") and not spec.get("skip") else None
        out[rid] = {"title": title, "o": compact(o), "perm": pm}
        print(f"\n{rid}: {title}")
        for s in SP:
            print("  " + S.line(o, s), "| funded", o[s]["funded_net"], f"(d {o[s]['funded_net'] - base_o[s]['funded_net']:+,})")
        if pm:
            print("  shuffle test:", pm)
        if save:
            _save(rid, title, spec, status, o, base_o, pm)
    json.dump(out, open(os.path.join(OUTD, "select_final.json"), "w"), indent=1, default=str)


def _save(rid, title, spec, status, o, b, pm):
    R = rows()
    U = S.replay(R, skip=spec.get("skip"), size=spec.get("size"), max_per_day=spec.get("max_per_day", 1), second=spec.get("second"))
    T = S.evals_x(U, "2026")[1] + S.evals_x(U, "2021-25")[1]
    T = [{k: v for k, v in t.items() if k not in ("legs", "_row")} for t in T]
    Sc = S.rl.score(T, S.SESS)

    def h(s):
        x = o[s]
        return (f"n={x['n']} {x['tpw']}/wk win {x['win']}% PF {x['pf']} net {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,}; "
                f"eval 2wk {x['p10']}/{x['f10']} (dec10 {x['dec10']}), 3wk {x['p15']}/{x['f15']}, 1mo {x['p20']}/{x['f20']}, pass rate "
                f"{x['pass_rate']}%, median {x['pass_med']} sessions, slow_pass {x['slow_pass']}%; same trades at $800/25 without the room "
                f"cap {x['funded_net']:+,} (base {b[s]['funded_net']:+,})")
    verdict = (f"2026 H1 (pick) {h('H1')}. 2026 H2 (check) {h('H2')}. 2021-25 reference only {h('2021-25')}. "
               f"Base (LIT live, eval sizing) H1 {b['H1']['net']:+,} / H2 {b['H2']['net']:+,}."
               + (f" Shuffle test (sizes moved to random trades of the same half): p H1 {pm['H1']['p']} / H2 {pm['H2']['p']}." if pm else ""))
    S.rl.save(rid, title, "other", "Owner order 2026-10-18: higher win rates / smarter trades - pick and size LIT setups like an "
              "experienced trader (trade selection).", params={**S.LIVE, "size": list(S.EVAL_RULE), "room_k": S.ROOM_K,
                                                                  "risk_cap_sized_up": S.RISK_CAP, "rule": title},
              trades=T, scored=Sc, status=status, verdict=verdict,
              notes="tools/lit_select.py + tools/lit_select_rules.py (wrap engine/lit.py and tools/lit_tightstop.py, not edited). "
                    "Candidate replay == run lit_live trade for trade; eval sizing $800 up to 25 pts + 60% room cap + weekly stop; "
                    "$ and DD from back-to-back MFFU 50K evals, eval odds from a fresh eval on every session; MFFU $1,000 soft daily "
                    "loss modelled.", writeup="lit-trade-selection", tags=["lit", "lit_select"])
    print("  saved", rid)
