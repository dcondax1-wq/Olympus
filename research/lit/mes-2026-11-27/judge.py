"""Judge (DESIGN.md rules) -> results.json. Run mes.py and mes.py v3 first."""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mes as M
nq = json.load(open(os.path.join(HERE, "results_nq.json"))); v3 = json.load(open(os.path.join(HERE, "results_v3.json")))["v3"]
TN = json.load(open(os.path.join(HERE, "trades_nq.json"))); T3 = json.load(open(os.path.join(HERE, "trades_v3.json")))
S = M.c.sessions()
h1 = [d for d in S if M.SPANS["H1"][0] <= d <= M.SPANS["H1"][1]]
def day(T):
    d = collections.Counter()
    for t in T: d[t["day"]] += t["pnl"]
    return d
live = day(TN["live"])
sets = {"V1_mes_same_risk": TN["V1_mes_same_risk"], "V2_mes_floor1": TN["V2_mes_floor1"], "V3_es_detect": T3["comb"]}
pv = {k: M.dv.perm_p([day(T)[d] - live[d] for d in h1]) for k, T in sets.items()}
order = sorted(pv, key=pv.get); holm = {}; run = 0.0
for i, k in enumerate(order):
    run = max(run, min(1.0, (len(order) - i) * pv[k])); holm[k] = round(run, 4)
out = {"design": "DESIGN.md", "k_es_nq_atr": v3["k"], "spans": {}, "judge": {}}
for k in sets:
    m = nq["variants"][k] if k in nq["variants"] else None
    spans = {}
    for sp in M.SPANS:
        if k == "V3_es_detect":
            a = v3["spans"][sp]["V3_es_detect"]; b = v3["spans"][sp]["live"]
        else:
            a, b = nq["variants"][k][sp], nq["variants"]["live"][sp]
        spans[sp] = {"variant": a, "live": b}
    out["spans"][k] = spans
    ok = {}
    for sp in ("H1", "JulNov", "2021-25"):
        a, b = spans[sp]["variant"], spans[sp]["live"]
        ok[sp] = bool(a["net"] > b["net"] and (a["pf"] or 0) >= (b["pf"] or 0) - 0.05 and a["dd"] >= 1.25 * b["dd"]
                      and (b["pass_rate"] is None or (a["pass_rate"] or 0) >= b["pass_rate"]))
    tpw = all(2 <= spans[sp]["variant"]["tpw"] <= 4 for sp in ("H1", "JulNov"))
    out["judge"][k] = {"split_ok": ok, "tpw_ok": tpw, "p_H1": round(pv[k], 4), "holm_p": holm[k],
                       "verdict": "PASS" if all(ok.values()) and tpw and holm[k] < 0.05 else ("candidate, not proven" if all(ok.values()) and tpw else "REJECTED")}
out["sensitivity"] = nq["sensitivity"]
json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)
for k, j in out["judge"].items(): print(k, j)
for k, v in out["sensitivity"].items(): print("sens", k, {sp: (v[sp]["net"], v[sp]["pf"]) for sp in ("H1", "JulNov", "2021-25")})
