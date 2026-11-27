"""Grades + conviction sizing (DESIGN.md, pre-registered e0f72071). PAPER RESEARCH ONLY. -> results.json"""
import collections, json, math, os, sys, time
import numpy as np
import pandas as pd


class _Sp:
    def __init__(self, c):
        self.correlation = c


def spearmanr(a, b):
    a = pd.Series(np.asarray(a, float)).rank().values; b = pd.Series(np.asarray(b, float)).rank().values
    if a.std() == 0 or b.std() == 0:
        return _Sp(0.0)
    return _Sp(float(np.corrcoef(a, b)[0, 1]))
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")):
    sys.path.insert(0, p)
import logging; logging.getLogger("engine.sizing").setLevel(logging.ERROR)
import combo_account as C
from engine import lit

PER = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16"), "REF": ("2021-11-01", "2025-12-31")}
NUM = {"Z": ["stop_pts", "stop_atr", "rr", "atr_regime", "vix", "trend_d", "trend_h", "range_adr", "news_min", "depth", "disp", "idm"],
       "A": ["stop_pts", "stop_atr", "rr", "atr_regime", "vix", "trend_d", "trend_h", "range_adr", "news_min"],
       "B": ["stop_pts", "stop_atr", "atr_regime", "vix", "trend_d", "trend_h", "range_adr", "news_min"]}
CAT = {"Z": ["sess", "dow"], "A": ["sess", "dow", "src"], "B": ["sess", "dow"]}
PRIOR = {"trend_d": 1, "trend_h": 1, "rr": 1, "stop_atr": -1, "vixband": 1, "newsfar": 1, "calm": 1, "depth": 1, "disp": 1, "idm": 1}
MAPS = {"M1": {"A+": 1.5, "A": 1.25, "B": 1.0, "C": 0.5}, "M2": {"A+": 1.5, "A": 1.0, "B": 1.0, "C": 0.0},
        "M3": {"A+": 2.0, "A": 1.5, "B": 1.0, "C": 0.5}}
BOTS = {"Z": "LIT", "A": "ATLAS", "B": "BLITZ"}
NSH = 5000


def per(day):
    for k, (a, b) in PER.items():
        if a <= day <= b:
            return k
    return None


def pct_fn(ref):
    ref = np.sort(np.asarray(ref, float))
    return lambda x: np.searchsorted(ref, x, side="right") / max(len(ref), 1)


def fit(F, bot):
    H = [f for f in F if f["per"] == "H1"]
    R = np.array([f["R"] for f in H])
    parts = []
    for nm in NUM[bot]:
        v = np.array([f[nm] if f[nm] is not None and not (isinstance(f[nm], float) and math.isnan(f[nm])) else np.nan for f in H], float)
        med = float(np.nanmedian(v)) if np.isfinite(v).any() else 0.0
        v = np.where(np.isfinite(v), v, med)
        rho = spearmanr(v, R).correlation if np.std(v) > 0 else 0.0
        sg = 1.0 if (rho or 0) >= 0 else -1.0
        parts.append(("num", nm, med, pct_fn(v), sg, round(float(rho or 0), 3)))
    for nm in CAT[bot]:
        g = collections.defaultdict(list)
        for f, r in zip(H, R):
            g[f[nm]].append(r)
        enc = {k: len(x) * np.mean(x) / (len(x) + 10) for k, x in g.items()}
        parts.append(("cat", nm, enc, pct_fn(list(enc.values()) or [0]), 1.0, None))
    return parts


def prior_parts(F, bot):
    H = [f for f in F if f["per"] == "H1"]
    def facts(f):
        x = {"trend_d": f["trend_d"], "trend_h": f["trend_h"], "stop_atr": f["stop_atr"],
             "vixband": 1 if f["vix"] and 15 <= f["vix"] <= 25 else 0, "newsfar": 1 if f["news_min"] > 30 else 0,
             "calm": 1 if (f["range_adr"] == f["range_adr"] and f["range_adr"] < 1) else 0}
        if bot != "B":
            x["rr"] = f["rr"] or 0.0
        if bot == "Z":
            x.update(depth=f["depth"] or 0, disp=f["disp"] or 0, idm=f["idm"] or 0)
        return x
    ks = list(facts(H[0]).keys())
    ref = {k: pct_fn([facts(f)[k] for f in H]) for k in ks}
    return lambda f: float(np.mean([PRIOR[k] * (ref[k](facts(f)[k]) - 0.5) for k in ks]))


def score_fn(parts):
    def sc(f):
        xs = []
        for kind, nm, a, pf, sg, _ in parts:
            if kind == "num":
                v = f[nm]
                v = a if v is None or (isinstance(v, float) and math.isnan(v)) else v
                xs.append(sg * (pf(v) - 0.5))
            else:
                xs.append(pf(a.get(f[nm], 0.0)) - 0.5)
        return float(np.mean(xs))
    return sc


def grade_of(cuts):
    return lambda s: "C" if s < cuts[0] else "B" if s < cuts[1] else "A" if s < cuts[2] else "A+"


def base_q(f):
    if f["s"] == "Z":
        return max(1, lit.qty_for(f["risk"]))
    usd = 500.0 if f["s"] == "A" else 300.0
    return max(1, int(usd / (f["risk"] * C.PV + C.COMM)))


def qm(q0, m):
    return 0 if m <= 0 else max(1, int(math.floor(q0 * m + 1e-9)))


def money(F, mults, ss_n):
    pn = np.array([(f["pts"] * C.PV - C.COMM) * qm(f["q0"], m) for f, m in zip(F, mults)])
    tr = int(sum(1 for m in mults if m > 0))
    gl = -pn[pn < 0].sum()
    eq = np.cumsum(pn); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(pn) else 0.0
    return {"n": tr, "tpw": round(tr / (ss_n / 5), 2), "pf": round(float(pn[pn > 0].sum() / gl), 2) if gl else None,
            "net": round(float(pn.sum())), "per_month": round(float(pn.sum()) / (ss_n / 21)), "dd": round(dd)}


def main():
    t0 = time.time()
    F = json.load(open(os.path.join(HERE, "features.json")))
    S = C.sessions()
    nsess = {k: sum(1 for d in S if a <= d <= b) for k, (a, b) in PER.items()}
    for f in F:
        f["per"] = per(f["day"]); f["q0"] = base_q(f)
    F = [f for f in F if f["per"]]
    out = {"design": "DESIGN.md e0f72071", "bots": {}, "poseidon": "NOT GRADABLE: no Jan-Jun 2026 tick data (real ticks from Sep 2026, ~40 lane A trades); forward gate only"}
    MULT = {}
    pvals = {}
    rng = np.random.default_rng(11)
    for bot in BOTS:
        FB = sorted([f for f in F if f["s"] == bot], key=lambda f: f["et"])
        parts = fit(FB, bot)
        graders = {"G1": score_fn(parts), "G2": prior_parts(FB, bot)}
        ob = {"rho_H1": {p[1]: p[5] for p in parts if p[0] == "num"}, "graders": {}}
        for gn, sc in graders.items():
            for f in FB:
                f["sc_" + gn] = sc(f)
            h1 = [f["sc_" + gn] for f in FB if f["per"] == "H1"]
            cuts = np.percentile(h1, [25, 60, 85])
            gof = grade_of(cuts)
            for f in FB:
                f["g_" + gn] = gof(f["sc_" + gn])
            og = {"sep": {}, "by_grade": {}, "maps": {}}
            for pk in PER:
                P = [f for f in FB if f["per"] == pk]
                s = np.array([f["sc_" + gn] for f in P]); r = np.array([f["R"] for f in P])
                rho = spearmanr(s, r).correlation
                sh = np.array([spearmanr(rng.permutation(s), r).correlation for _ in range(1000)])
                og["sep"][pk] = {"rho": round(float(rho), 3), "p": round(float((1 + (sh >= rho).sum()) / 1001), 4)}
                og["by_grade"][pk] = {g: {"n": int(sum(1 for f in P if f["g_" + gn] == g)),
                                          "meanR": round(float(np.mean([f["R"] for f in P if f["g_" + gn] == g] or [0])), 3)}
                                      for g in ("A+", "A", "B", "C")}
            for mn, mp in MAPS.items():
                vid = f"{BOTS[bot]}/{gn}/{mn}"
                om = {}
                for pk in PER:
                    P = [f for f in FB if f["per"] == pk]
                    mul = [mp[f["g_" + gn]] for f in P]
                    flat = float(np.mean(mul))
                    live = money(P, [1.0] * len(P), nsess[pk])
                    var = money(P, mul, nsess[pk])
                    ctl = money(P, [flat] * len(P), nsess[pk])
                    om[pk] = {"live": live, "variant": var, "flat_control": {**ctl, "mult": round(flat, 3)}}
                    if pk == "H2":
                        g_arr = np.array([f["g_" + gn] for f in P])
                        obs = var["net"]
                        cnt = 0
                        base = np.array([(f["pts"] * C.PV - C.COMM) for f in P]); q0 = np.array([f["q0"] for f in P])
                        mvals = np.array([mp[g] for g in g_arr])
                        for _ in range(NSH):
                            mm = rng.permutation(mvals)
                            q = np.where(mm <= 0, 0, np.maximum(1, np.floor(q0 * mm + 1e-9)))
                            cnt += (base * q).sum() >= obs
                        pvals[vid] = (1 + cnt) / (NSH + 1)
                        om["p_H2_shuffle"] = round(pvals[vid], 4)
                og["maps"][mn] = om
                for f in FB:
                    MULT.setdefault(f"{gn}/{mn}", {})[(f["s"], f["et"])] = mp[f["g_" + gn]]
            ob["graders"][gn] = og
        out["bots"][BOTS[bot]] = ob
        print(BOTS[bot], "done", round(time.time() - t0), flush=True)
    # Holm over 18
    order = sorted(pvals, key=pvals.get); rm = 0.0; holm = {}
    for i, v in enumerate(order):
        rm = max(rm, min(1.0, (len(order) - i) * pvals[v])); holm[v] = round(rm, 4)
    for bot in out["bots"].values():
        pass
    verdicts = {}
    for vid in pvals:
        b, gn, mn = vid.split("/")
        om = out["bots"][b]["graders"][gn]["maps"][mn]
        L = lambda pk: om[pk]["live"]["net"]; V = lambda pk: om[pk]["variant"]["net"]; Cc = lambda pk: om[pk]["flat_control"]["net"]  # noqa
        ok = (V("H1") > L("H1") and V("H2") > L("H2") and V("REF") >= L("REF") - max(500, 0.05 * abs(L("REF")))
              and V("H1") > Cc("H1") and V("H2") > Cc("H2") and holm[vid] < 0.05)
        verdicts[vid] = {"holm_p": holm[vid], "raw_pass": bool(ok)}
    out["verdicts"] = verdicts
    json.dump(out, open(os.path.join(HERE, "results_raw.json"), "w"), indent=1, default=float)
    # accounts: LIT + ATLAS on the Builder 50K (combo live row), 6 grader x map pairs applied to Z and A
    import pickle
    pickle.dump(MULT, open(os.path.join(os.environ.get("SCR", "/tmp"), "grades_mult.pkl"), "wb"))
    print("raw done", round(time.time() - t0))


if __name__ == "__main__":
    main()
