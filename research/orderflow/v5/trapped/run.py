"""v5 'trapped' in-sample run on the 51 days (DESIGN.md frozen first). PAPER RESEARCH ONLY.

    python -X utf8 research/orderflow/v5/trapped/run.py
Writes results.json + frozen.json (best 1-2 variants by verdict, Holm p, net $; picked by rule, not by hand).
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core as T  # noqa: E402

IS_FIRST, IS_LAST = "2026-09-27", "2026-11-26"
RANK = {"YES-candidate": 0, "weak": 1, "NO": 2, "TOO FEW": 3}
VIDS = ["T1", "T2", "T3", "C1", "C2", "C3"]
RULES = {"breakout_bar_mod": [T.B0, T.B1], "decision_bar_mod": [T.F0, T.F1], "orb_from_mod": T.ORB_FROM,
         "label_thresholds_by_look": T.LOOKS, "xd_min_contracts": T.XD_MIN, "fade_within_bars": T.FADE_N,
         "sx_cooldown_bars": T.SX_COOL, "key_levels": T.KEY_ORDER, "rr": T.C.RR, "flat_mod": T.C.LAST,
         "entry": "E5 coarse: decision at F close; F+1 opens at/beyond L our way = fill at open; else >=1 tick through L = fill at L (stop-only that bar); else stop in F+1 = no fill; else F+2 open + 18 ticks against",
         "stop": "FADE: 1 tick beyond the excursion extreme of B..F; HOLD: 1 tick beyond the other side of B..F; stop fill 2 ticks worse",
         "target": "2R, needs 1 tick through", "comm_rt": T.C.COMM, "one_position": True,
         "pass_bar": "YES-candidate: >=20 trades, net>0, PF>=1.2, both halves meanR>0 and gap>0, placebo p<0.10, Holm<0.10"}


def run_look(D, usable, days, look):
    T.set_look(look)
    out, cands = {}, {}
    for vid in VIDS:
        cs = T.run_variant(D, usable, days, vid)
        cands[vid] = cs
        out[vid] = T.score(cs, days)
        out[vid]["price_only"] = T.price_only(cs, days)
    adj = T.holm({v: out[v]["placebo_p"] for v in VIDS})
    for v in VIDS:
        out[v]["holm_p"] = adj[v]
        out[v]["verdict"] = T.verdict(out[v], adj[v])
    print(f"\n=== look {look} (BD {T.TH['bd']}, XD {T.TH['xd']}) ===")
    print(T.table([(v, out[v]) for v in VIDS]))
    for v in VIDS:
        print(v, "fills", out[v]["how"], "no-fill", out[v]["no_fill"], "no-label meanR", out[v]["notabs_mean_R"],
              "$500-risk", out[v]["usd500"], "halves $", {k: h["usd"] for k, h in out[v]["halves"].items()},
              "price-only", out[v]["price_only"])
    slim = {v: [{k: x.get(k) for k in ("day", "t_brk", "t_sig", "level", "L", "dir", "d", "absorbed", "bd_share", "vx", "dx",
                                         "busy", "how", "fill", "stop", "exit", "why", "R", "usd")} for x in cands[v]] for v in cands}
    best = sorted(VIDS, key=lambda v: (RANK[out[v]["verdict"]], out[v]["holm_p"] if out[v]["holm_p"] is not None else 9,
                                       -out[v]["net_usd"]))
    with open(os.path.join(HERE, "results.json" if look == 1 else f"results_look{look}.json"), "w") as fh:
        json.dump({"look": look, "thresholds": dict(T.TH), "scores": out, "rank": best, "candidates": slim}, fh, indent=0, default=float)
    return out, best


def main():
    D, usable = T.load_days()
    days = [d for d in usable if IS_FIRST <= d <= IS_LAST]
    print(f"days: {len(days)} usable {days[0]}..{days[-1]} (files loaded {len(D)})")
    o1, b1 = run_look(D, usable, days, 1)
    o2, b2 = run_look(D, usable, days, 2)
    pick = [(1, b1[0])]                                                  # DESIGN_look2 freeze rule
    pick.append((2, b2[0]) if RANK[o2[b2[0]]["verdict"]] < RANK["TOO FEW"] else (1, b1[1]))
    keys = ("trades", "per_week", "win_pct", "mean_R", "pf", "net_usd", "max_dd_usd", "gap_R", "placebo_p", "holm_p", "verdict")
    frozen = {"family": "trapped", "design": "research/orderflow/v5/trapped/DESIGN.md + DESIGN_look2.md", "frozen_on": "2026-11-27",
              "in_sample_days": days,
              "variants": {f"{v}@look{lk}": {"id": v, "look": lk, "thresholds": T.LOOKS[lk], "name": T.NAMES[v],
                                             "pattern": T.VARIANTS[v][0], "levels": T.VARIANTS[v][1], "label": T.VARIANTS[v][2],
                                             "in_sample": {k: (o1 if lk == 1 else o2)[v][k] for k in keys}} for lk, v in pick},
              "rules": RULES}
    with open(os.path.join(HERE, "frozen.json"), "w") as fh:
        json.dump(frozen, fh, indent=1)
    print("frozen:", list(frozen["variants"]))


if __name__ == "__main__":
    main()
