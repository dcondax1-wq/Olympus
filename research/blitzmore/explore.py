"""Exploratory reverse pick (DESIGN.md addendum): pick on 2021-24, check on 2025 / 2026 H1 / 2026 Jul-Nov. -> explore.json"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import blitzmore as M
from tools import scalp_na_lib as N
B1, B5 = N.bars(1), N.bars(5)
SR = N.sessions(B5, "R"); S1 = N.sessions(B1, "H1"); S2 = N.sessions(B1, "H2")
Y = {"2021-24": [d for d in SR if d < "2025-01-01"], "2025": [d for d in SR if d >= "2025-01-01"]}
def run(cfg):
    T1, T5 = M.usd(M.sim(B1, cfg)), M.usd(M.sim(B5, cfg)); tk = lambda T: [{**t, "pnl_pm": t["pnl_pm"] - 1.0} for t in T]; T1x, T5x = M.usd(tk(M.sim(B1, cfg))), M.usd(tk(M.sim(B5, cfg)))
    st = lambda T, S: N.stats(T, S, M.USD, 20)
    o = {"2021-24": st(T5, Y["2021-24"]), "2025": st(T5, Y["2025"]), "2021-25": st(T5, SR), "2026 H1": st(T1, S1), "2026 Jul-Nov20": st(T1, S2),
         "tick1_2021-25": st(T5x, SR)["pf"], "years": {y: N.stats(T5, [d for d in SR if d.startswith(y)], M.USD, 20)["per_month"] for y in M.BZ.YEARS}}
    for k, S, T in (("2021-25", SR, T5), ("2026 H1", S1, T1), ("2026 Jul-Nov20", S2, T1)):
        ev = M.MT.span_stats(T, S, S[0], S[-1])["evals"]
        o[k]["b25k"], o[k]["rapid25k"], o[k]["k50"] = ev["25K"], ev["Rapid25K"], ev["50K"]
    return o
res = {"today": run({})}
singles = {nm: run(v) for nm, v in M.V.items() if nm != "V0 today"}
top = sorted(singles, key=lambda n: -singles[n]["2021-24"]["per_month"])[:2]
res["singles_2021_24"] = {n: [singles[n]["2021-24"]["per_month"], singles[n]["2021-24"]["pf"]] for n in sorted(singles, key=lambda n: -singles[n]["2021-24"]["per_month"])}
cand = {n: singles[n] for n in top}
comb = {}
for n in top: comb.update(M.V[n])
nm = " + ".join(n.split()[0] for n in top)
cand[nm] = run(comb)
res["top"], res["cands"] = top, cand
b = res["today"]
for n, o in cand.items():
    ok = all(o[k]["per_month"] >= b[k]["per_month"] * (1 if b[k]["per_month"] > 0 else 0) - 0.1 * abs(b[k]["per_month"]) for k in ("2025", "2026 H1", "2026 Jul-Nov20"))
    o["holds"] = bool(ok and (o["2021-25"]["pf"] or 0) >= 1.15)
    print(n, "| 21-24 $/mo", o["2021-24"]["per_month"], "PF", o["2021-24"]["pf"], "| 2025", o["2025"]["per_month"], o["2025"]["pf"], "| H1", o["2026 H1"]["per_month"], o["2026 H1"]["pf"], "| JN", o["2026 Jul-Nov20"]["per_month"], o["2026 Jul-Nov20"]["pf"], "| 21-25 PF", o["2021-25"]["pf"], "tick1", o["tick1_2021-25"], "| holds", o["holds"])
print("today", b["2021-24"]["per_month"], b["2025"]["per_month"], b["2026 H1"]["per_month"], b["2026 Jul-Nov20"]["per_month"])
json.dump(res, open(os.path.join(HERE, "explore.json"), "w"), indent=1, default=float)
