"""Run the 4 pre-registered stop-cap variants of DESIGN.md vs live (research only) -> results.json."""
import bisect, collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c
lit, lf = c.lit, c.lf
HERE = os.path.dirname(os.path.abspath(__file__))
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "JulOct": ("2026-07-01", "2026-10-14"), "2021-25": ("2021-01-01", "2025-12-31"),
         "Drought": ("2026-10-15", "2026-11-26"), "2026all": ("2026-01-01", "2026-11-26")}
_q0 = lit.qty_for


def qty_floor(risk_pts, *a, **k):
    q = _q0(risk_pts, *a, **k)
    return max(q, 1) if 80.0 < risk_pts <= 150.0 else q


vd, vc = lit._vix("VIX")


def vix_prev(day):
    i = bisect.bisect_left(vd, day) - 1
    return float(vc[i]) if i >= 0 else None


def risk_of(z, P):
    return min(float(z["ref_d"]), z["trig_c"]) - (z["ext_d"] - P["stop_buf"])


CAPS = {
    "V1_pts120": lambda z: 120.0,
    "V2_atr_floor": lambda z: min(150.0, max(80.0, 3.0 * z["atr_ext"])),
    "V3_vix_band": lambda z: 120.0 if (vix_prev(z["day"]) or 0) >= 22 else 80.0,
    "V4_atr_only": lambda z: min(150.0, max(40.0, 3.2 * z["atr_ext"])),
}


def run_variant(name, P, S):
    M, C = lf.market(P["ref"], P["extra_boxes"])
    if name == "live":
        lit.qty_for = _q0
        return lit.run_x(M, C, P, S, B1=lf.bars(M, "1m"), B5=lf.bars(M, "5m"))
    cap = CAPS[name]
    CC = [z for z in C if risk_of(z, P) <= cap(z)]
    lit.qty_for = qty_floor
    try:
        return lit.run_x(M, CC, {**P, "max_stop": 150.0}, S, B1=lf.bars(M, "1m"), B5=lf.bars(M, "5m"))
    finally:
        lit.qty_for = _q0


def metrics(T, ss):
    wk = len(ss) / 5
    p = np.array([t["pnl"] for t in T] or [0.0])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if T else 0.0
    byday = collections.defaultdict(lambda: [0.0, 0.0])
    for t in sorted(T, key=lambda t: t["entry_t"]):
        b = byday[t["day"]]; b[1] = min(b[1], b[0] + t["low"]); b[0] += t["pnl"]
    days = [{"pnl": byday[d][0], "low": byday[d][1]} for d in ss]
    months = len(ss) / 21.0
    return {"n": len(T), "tpw": round(len(T) / wk, 2), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / months), "dd": round(dd),
            "win": round(100 * float((p > 0).mean()), 1) if T else None, "pass_rate": lf.pass_rate(days) if T else None,
            "wide": sum(1 for t in T if t["risk_pts"] > 80), "wide_net": round(sum(t["pnl"] for t in T if t["risk_pts"] > 80))}


def perm_p(diff, n=10000, seed=7):
    rng = np.random.default_rng(seed)
    d = np.asarray(diff, float); obs = d.sum()
    if not np.any(d):
        return 1.0
    sims = (rng.choice([-1.0, 1.0], size=(n, len(d))) * d).sum(1)
    return float((1 + (sims >= obs).sum()) / (n + 1))


def main():
    P = {**lit.DEFAULTS, **c.live_P()}
    S = c.sessions()
    names = ["live"] + list(CAPS)
    R = {nm: run_variant(nm, P, S) for nm in names}
    out = {"design": "DESIGN.md (committed before this run)", "variants": {}}
    for nm in names:
        T = R[nm]
        out["variants"][nm] = {sp: metrics([t for t in T if a <= t["day"] <= b], [d for d in S if a <= d <= b])
                               for sp, (a, b) in SPANS.items()}
    # judge
    h1 = [d for d in S if SPANS["H1"][0] <= d <= SPANS["H1"][1]]
    dayp = {nm: collections.Counter() for nm in names}
    for nm in names:
        for t in R[nm]:
            dayp[nm][t["day"]] += t["pnl"]
    pv = {nm: perm_p([dayp[nm][d] - dayp["live"][d] for d in h1]) for nm in CAPS}
    order = sorted(pv, key=pv.get); holm = {}; run_max = 0.0
    for i, nm in enumerate(order):
        run_max = max(run_max, min(1.0, (len(order) - i) * pv[nm])); holm[nm] = round(run_max, 4)
    L = out["variants"]["live"]
    for nm in CAPS:
        V = out["variants"][nm]; ok = {}
        for sp in ("H1", "JulOct", "2021-25"):
            a, b = V[sp], L[sp]
            ok[sp] = bool(a["net"] > b["net"] and (a["pf"] or 0) >= (b["pf"] or 0) - 0.05 and a["dd"] >= 1.25 * b["dd"])
        tpw_ok = all(2 <= V[sp]["tpw"] <= 4 for sp in ("H1", "JulOct"))
        out["variants"][nm]["judge"] = {"split_ok": ok, "tpw_ok": tpw_ok, "p_H1": round(pv[nm], 4), "holm_p": holm[nm],
                                        "verdict": "PASS" if all(ok.values()) and tpw_ok and holm[nm] < 0.05 else
                                        ("candidate, not proven" if all(ok.values()) and tpw_ok else "REJECTED")}
    json.dump(out, open(os.path.join(HERE, "variants.json"), "w"), indent=1)
    for nm in names:
        print(nm, json.dumps(out["variants"][nm]))


if __name__ == "__main__":
    main()
