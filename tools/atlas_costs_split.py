"""ATLAS split costs (2026-11-20, day-atlasedge, TOP25 idea #8): a late market entry (~10 ticks) priced apart from a resting
stop (1-3 ticks) and a target (0), on the LIVE setup (room 40% + 2 losses -> 1 micro). Design (committed before any run):
research/second/atlas_costs_split_design.md. Write-up: research/writeups/atlas-costs-split-2026-11-20.md. RESEARCH ONLY.

  python -X utf8 tools/atlas_costs_split.py run            # fixed view + funded 25K + 25K eval per scenario -> atlas_costs_split.json
  python -X utf8 tools/atlas_costs_split.py eval 10 2      # (internal) one scenario's 25K eval in its own process
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)

OUT = os.path.join(ROOT, "research", "second", "atlas_costs_split.json")
SCEN = [("E1/X1 backtest", 1, 1), ("E10/X10 stress (all studies)", 10, 10), ("E10/X1", 10, 1), ("E10/X2", 10, 2),
        ("E10/X3", 10, 3), ("E13/X1 measured entry", 13, 1)]
LIVE = {"stuck": 0.0, "pct": 0.4, "streak_shrink": 2}
ROOM60 = {"stuck": 0.0, "streak_shrink": 2}
STATES = {"now $1,401 room": 401.0, "morning $887 room": -113.0}


def units(ne, nx):
    from tools import atlas_fills as AF
    return [AF.priced(u, ne, nx) for u in AF.units()]


def eval_one(ne, nx):
    from tools import atlas_fills as AF
    from tools import atlas_v2 as V2
    orig = V2.A.account_units
    V2.A.account_units = lambda V: [AF.priced(u, ne, nx) for u in orig(V)]
    o = V2.score(dict(V2.A.BASE), mp=False)
    return {s: {k: o[s].get(k) for k in ("p10", "f10", "s10", "p15", "pass_med", "slow_pass", "tpw")} for s in o}


def run(n_paths=1000, log=print):
    from tools import atlas_edge as E
    from tools import atlas_health as AH
    t0 = time.time()
    out = {"date": "2026-11-20", "design": "research/second/atlas_costs_split_design.md", "live": LIVE, "rows": {}}
    for lab, ne, nx in SCEN:
        T = E.to_T(units(ne, nx))
        row = {"entry_ticks": ne, "stop_ticks": nx, "fixed": E.fixed(T), "funded": {}}
        for st, bal in STATES.items():
            AH.TODAY_BAL = bal
            E.BASES["LIVE"], E.BASES["R60"] = LIVE, ROOM60
            row["funded"][st] = {"live_40": E.funded(LIVE, T, n_paths)}
            if nx in (1, 2, 3) and ne == 10 and st.startswith("now"):
                row["funded"][st]["room60_streak"] = E.funded(ROOM60, T, n_paths)
        AH.TODAY_BAL = -113.0
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.abspath(__file__), "eval", str(ne), str(nx)], capture_output=True, text=True, cwd=ROOT)
        row["eval25k"] = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-300:]}
        out["rows"][lab] = row
        x, f, ev = row["fixed"], row["funded"]["now $1,401 room"]["live_40"], row["eval25k"]
        log(f"{lab:30s} fixed " + " | ".join(f"{s} {x[s]['tpw']}/wk PF {x[s]['pf']} ${x[s]['per_month']} dd {x[s]['max_dd']}" for s in ("H1", "H2", "2025", "2021-24")))
        log(f"{'':30s} funded(now) " + " | ".join(f"{s} ${f[s]['usd_m']} 1st {f[s]['first']} lost {f[s]['lost_6m']}%" for s in ("H1", "H2", "REF"))
            + "  eval " + " | ".join(f"{s} p10 {v.get('p10')} f10 {v.get('f10')} med {v.get('pass_med')}" for s, v in ev.items() if isinstance(v, dict))
            + f"  [{time.time() - t0:.0f}s]")
        if "room60_streak" in row["funded"]["now $1,401 room"]:
            g = row["funded"]["now $1,401 room"]["room60_streak"]
            log(f"{'':30s} room 60%+streak " + " | ".join(f"{s} ${g[s]['usd_m']} lost {g[s]['lost_6m']}%" for s in ("H1", "H2", "REF")))
    # sizing question (design): 60% vs 40% by the atlas_risk bar at E10/X1-X3, today's account
    verdict = {}
    for lab in ("E10/X1", "E10/X2", "E10/X3"):
        a = out["rows"][lab]["funded"]["now $1,401 room"]
        b40, b60 = a["live_40"], a["room60_streak"]
        why = []
        for s in ("H1", "H2"):
            if b60[s]["lost_6m"] > b40[s]["lost_6m"] - 0.5:
                why.append(f"{s} lost {b40[s]['lost_6m']}->{b60[s]['lost_6m']}")
            if b60[s]["usd_m"] < 0.9 * b40[s]["usd_m"]:
                why.append(f"{s} ${b40[s]['usd_m']}->${b60[s]['usd_m']}")
        if b60["REF"]["lost_6m"] > b40["REF"]["lost_6m"] + 0.5 or b60["REF"]["usd_m"] < b40["REF"]["usd_m"] - 10:
            why.append("REF worse")
        verdict[lab] = {"room60_better": not why, "why": why}
    out["sizing_verdict"] = verdict
    out["card"] = all(v["room60_better"] for v in verdict.values())
    out["took_s"] = round(time.time() - t0)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    log(f"sizing: 60% better than 40% at all three stop costs: {out['card']}  {verdict}")
    return out


if __name__ == "__main__":
    a = sys.argv[1:] or ["run"]
    if a[0] == "eval":
        print(json.dumps(eval_one(int(a[1]), int(a[2]))))
    else:
        run(int(a[1]) if len(a) > 1 else 1000)
