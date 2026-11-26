"""The 3 rejected variants with the regime rule on the real engines (research/regime2026/DESIGN.md). PAPER RESEARCH ONLY.
Rule = regime.py's pick winner (S1_RV; it did NOT pass the pre-registered "reliable" test: labelled so).
    python -X utf8 research/regime2026/engines.py -> research/regime2026/engines.json
"""
from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, HERE, os.path.join(ROOT, "research", "atlas2"), os.path.join(ROOT, "research", "litasia"),
          os.path.join(ROOT, "tools"), os.path.join(ROOT, "research", "plans")):
    sys.path.insert(0, p)
import regime as RG  # noqa: E402

OUT = os.path.join(HERE, "engines.json")
TR = os.path.join(HERE, "atlas_gated.json.gz")
RULE = json.load(open(RG.OUT, encoding="utf-8"))["winner"]["rule"]


def atlas_sets():
    import atlas2 as A2
    V0 = json.load(gzip.open(A2.TRADES, "rt", encoding="utf-8"))["V0"]
    R = RG.rules(RG.daily(), 1)
    s = R[RULE]
    on = lambda d: bool(s.get(d, False))                                   # noqa: E731
    simple = [{"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "R": float(t["R_c"])} for t in V0]
    own = RG.own(simple)
    out = {"today": V0, "A_own_and_regime": [t for t in V0 if own[int(t["entry_t"])] and on(t["day"])],
           "B_regime": [t for t in V0 if on(t["day"])]}
    json.dump(out, gzip.open(TR, "wt", encoding="utf-8"), default=float)
    res = {}
    for k, T in out.items():
        res[k] = {"trades": len(T), **A2.table(T)}
    return res


def engines_one(v):
    import atlas2 as A2
    A2.TRADES, A2.HERE = TR, HERE
    return A2.cmd_engines(v)


def rapid_asia():
    import numpy as np  # noqa: F401
    import eval_only as EO
    import rank as R
    U, RL, AR, SOA = R.U, R.RL, R.AR, R.SOA
    U.SPAN["Y26"] = ("2026-01-01", "2026-10-16")
    AR.rapid_patch(AR.T_at(10))
    D = SOA.data(); S = D["S"]
    L_ledger = [list(x) for x in D["LIT"]]
    S2 = [[[1080, 120], [120, 1080]], 1]
    asia_T = EO.AS.M.run(EO.AS.M.P_of("full", 2, None, 1.0, {"per_session": S2, "second": {},
                                                               "kz": [[1080, 1440, {"max_rr": 3.0}], [0, 120, {"max_rr": 3.0}]]}))
    s = RG.rules(RG.daily(), 1)[RULE]
    LA = EO.by_session(EO.conv(asia_T, 2), S)
    gated = [LA[i] if bool(s.get(d, False)) else L_ledger[i] for i, d in enumerate(S)]   # ON: the Asia day; OFF: today's day
    plan, mix = "mffu_rapid_eod_25k", ("LIT", "ATLAS")
    sp = R.spec(plan)
    PE = {m: EO.paths(S, m, 1000, 60, 7) for m in EO.MARKETS}
    PF = {m: EO.paths(S, m, 1000, R.LEN, 23) for m in EO.MARKETS}
    BYf = EO.with_lit(L_ledger, mix, True)
    rows = {}
    for lab, L in (("today", L_ledger), ("eval_asia_ungated+2t", LA), (f"eval_asia_{RULE}+2t", gated)):
        BYe = EO.with_lit(L, mix)
        s2 = {**sp, "BYe": BYe, "BYf": BYf}
        rows[lab] = {m: {**EO.eval_stats(s2, PE[m]), **{k: v for k, v in R.slot_run(s2, PF[m]).items() if k in ("net_6m", "p_lost", "evals")}}
                     for m in EO.MARKETS}
        print(lab, {m: (rows[lab][m]["p21"], rows[lab][m]["f21"], rows[lab][m]["net_6m"]) for m in EO.MARKETS}, flush=True)
    return rows


def main():
    a = sys.argv[1:]
    if a and a[0] == "engines":
        engines_one(a[1]); return
    res = {"rule": RULE, "rule_reliable_by_preregistration": False, "atlas_fixed": atlas_sets(), "atlas_engines": {}}
    for k in ("today", "A_own_and_regime", "B_regime"):
        subprocess.run([sys.executable, "-X", "utf8", os.path.abspath(__file__), "engines", k], check=True)
        p = os.path.join(HERE, f"_eng_{k}.json")
        res["atlas_engines"][k] = json.load(open(p, encoding="utf-8")); os.remove(p)
    res["rapid_asia"] = rapid_asia()
    F, E = res["atlas_fixed"], res["atlas_engines"]
    def ok_atlas(k):
        return (F[k]["2021-25"]["net"] >= F["today"]["2021-25"]["net"] and
                E[k]["funded_25k"]["funded"]["REF"]["per_month"] >= E["today"]["funded_25k"]["funded"]["REF"]["per_month"])
    ra = res["rapid_asia"]; g = f"eval_asia_{RULE}+2t"
    ok_c = ra[g]["REF"]["f21"] <= ra["today"]["REF"]["f21"] and ra[g]["REF"]["p21"] >= ra["today"]["REF"]["p21"]
    res["gate"] = {"A": ok_atlas("A_own_and_regime"), "B": ok_atlas("B_regime"), "C": ok_c}
    res["verdict"] = ("CARD" if all(res["gate"].values()) and res["rule_reliable_by_preregistration"] else
                      "no card: " + ("the rule failed the pre-registered reliability test; " ) +
                      ", ".join(f"{k} {'ok' if v else 'fails'} on 2021-25" for k, v in res["gate"].items()))
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    for k, x in F.items():
        print(k, x["trades"], " | ".join(f"{sp} {x[sp]['tpw']}/wk PF {x[sp]['pf']} ${x[sp]['net']} dd {x[sp]['max_dd']}" for sp in ("2021-25", "2026 H1", "2026 Jul-Oct")))
    for k, e in E.items():
        f = e["funded_25k"]["funded"]; r = e["rapid_25k"]["on"]; b = e["builder"]["mffu_builder_50k"]
        print(k, "funded", [f[s]["per_month"] for s in f], "lost", [f[s]["lost_6m"] for s in f], "rapid", [r[s]["net_m"] for s in r],
              "50k", [(b[s]["eval"]["pass"], b[s]["slot"]["net_6m"]) for s in b])
    print(res["gate"], res["verdict"])


if __name__ == "__main__":
    main()
