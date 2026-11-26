"""LIT Asia slot at real Asia costs (research/litasia/DESIGN.md, ce6b9322). PAPER RESEARCH ONLY.
    python -X utf8 research/litasia/asia.py -> research/litasia/results.json
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from tools import lit_more_entries as M  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402

OUT = os.path.join(HERE, "results.json")
TICK = 0.25
EXTRA = (0, 1, 2, 4)


def is_asia(entry_t):
    return M.sess_of(M.et_mod(entry_t)) == "Asia"


def tgt(x):
    return str(x or "").upper().startswith("TARGET") or str(x or "").upper() in ("TP", "BANK", "T")


def adj_T(T, k):
    out = []
    for t in T:
        if k and is_asia(t["entry_t"]):
            sides = 1 + (0 if tgt(t.get("exit")) else 1)
            t = {**t, "pnl": float(t["pnl"]) - k * sides * 0.5 * max(1, int(t.get("qty") or 1))}
        out.append(t)
    return out


def adj_U(U, k):
    out = []
    for u in U:
        if k and is_asia(u["entry_t"]):
            sides = 1 + (0 if tgt(u.get("exit")) else 1)
            c = k * sides * TICK
            u = {**u, "pts": float(u["pts"]) - c, "legs": [(f, float(x) - c) for f, x in (u.get("legs") or [(1.0, u["pts"])])]}
        out.append(u)
    return out


def view(T, U):
    o = F.score(T)
    lit = {s: {x: o[s].get(x) for x in ("n", "tpw", "win", "pf", "net", "per_month", "dd")} for s in ("H1", "H2", "2021-25")}
    e = BI.short(BI.score(U))
    ev = {s: {x: e[s].get(x) for x in ("net", "p10", "f10", "p20", "f20", "pass_med", "mc_p10", "mc_f10")} for s in ("H1", "H2")}
    return {"lit_size": lit, "eval": ev}


def main():
    base_T = M.run(M.LIVE)
    S2 = [[[1080, 120], [120, 1080]], 1]
    asia_T = M.run(M.P_of("full", 2, None, 1.0, {"per_session": S2, "second": {}, "kz": [[1080, 1440, {"max_rr": 3.0}], [0, 120, {"max_rr": 3.0}]]}))
    exits = sorted({str(t.get("exit")) for t in asia_T})
    res = {"made": "2026-11-26", "design": "research/litasia/DESIGN.md (ce6b9322)", "exit_kinds": exits,
           "n_asia_trades": {s: sum(1 for t in asia_T if is_asia(t["entry_t"]) and a <= t["day"] <= z) for s, (a, z) in
                             ((s, F.SPAN[s]) for s in ("H1", "H2", "2021-25"))},
           "base": view(base_T, M.units(base_T)), "asia": {}}
    UA = M.units(asia_T)
    for k in EXTRA:
        res["asia"][f"+{k}"] = view(adj_T(asia_T, k), adj_U(UA, k))
    b = res["base"]
    def d(k):
        a = res["asia"][f"+{k}"]
        return {"lit_net_gain": {s: round(a["lit_size"][s]["net"] - b["lit_size"][s]["net"]) for s in ("H1", "H2", "2021-25")},
                "eval_fail_2wk": {s: (b["eval"][s]["f10"], a["eval"][s]["f10"]) for s in ("H1", "H2")},
                "eval_pass_2wk": {s: (b["eval"][s]["p10"], a["eval"][s]["p10"]) for s in ("H1", "H2")}}
    res["deltas"] = {f"+{k}": d(k) for k in EXTRA}
    c = res["deltas"]["+2"]
    dead = (c["lit_net_gain"]["H1"] <= 0 or c["lit_net_gain"]["H2"] <= 0 or
            all(c["eval_fail_2wk"][s][1] > c["eval_fail_2wk"][s][0] for s in ("H1", "H2")))
    res["verdict"] = ("Asia slot dead: at +2 ticks it adds no money in a 2026 half or raises eval fails in both"
                      if dead else "2026-only lead; fails the owner's full bar on 2021-25 (no card)")
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("exits", exits, "asia trades", res["n_asia_trades"])
    for s in ("H1", "H2", "2021-25"):
        x = b["lit_size"][s]
        print(f"base {s}: {x['tpw']}/wk PF {x['pf']} ${x['net']} dd {x['dd']}")
    for k in EXTRA:
        a = res["asia"][f"+{k}"]
        print(f"asia +{k}t: " + " | ".join(f"{s} {a['lit_size'][s]['tpw']}/wk PF {a['lit_size'][s]['pf']} ${a['lit_size'][s]['net']}" for s in ("H1", "H2", "2021-25"))
              + " | eval " + " | ".join(f"{s} net ${a['eval'][s]['net']} 2wk {a['eval'][s]['p10']}/{a['eval'][s]['f10']}" for s in ("H1", "H2")))
    print("base eval", {s: (b['eval'][s]['net'], b['eval'][s]['p10'], b['eval'][s]['f10']) for s in ("H1", "H2")})
    print(json.dumps(res["deltas"]))
    print(res["verdict"])


if __name__ == "__main__":
    main()
