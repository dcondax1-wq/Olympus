"""v5 'levels' in-sample run on the 51 days (DESIGN.md frozen first). PAPER RESEARCH ONLY.

    python -X utf8 research/orderflow/v5/levels/run.py
Writes results.json + frozen.json (best 1-2 variants by verdict, Holm p, net $; picked by rule, not by hand).
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core as C  # noqa: E402

IS_FIRST, IS_LAST = "2026-09-27", "2026-11-26"
RANK = {"YES-candidate": 0, "weak": 1, "NO": 2, "TOO FEW": 3}


def main():
    D, usable = C.load_days()
    days = [d for d in usable if IS_FIRST <= d <= IS_LAST]
    print(f"days: {len(days)} usable {days[0]}..{days[-1]} (files loaded {len(D)})")
    out, cands = {}, {}
    for vid in ["V0", "L1", "L2", "L3", "L4", "L5", "L6"]:
        cs = C.run_variant(D, usable, days, vid)
        cands[vid] = cs
        out[vid] = C.score(cs, days)
    adj = C.holm({v: out[v]["placebo_p"] for v in VIDS})
    for v in VIDS:
        out[v]["holm_p"] = adj[v]
        out[v]["verdict"] = C.verdict(out[v], adj[v])
    out["V0"]["verdict"] = "control (not scored)"
    print(C.table([(v, out[v]) for v in ["V0"] + VIDS]))
    for v in ["V0"] + VIDS:
        print(v, "fills", out[v]["how"], "no-fill", out[v]["no_fill"], "notabs meanR", out[v]["notabs_mean_R"],
              "$500-risk", out[v]["usd500"], "halves $", {k: h["usd"] for k, h in out[v]["halves"].items()})
    best = sorted(VIDS, key=lambda v: (RANK[out[v]["verdict"]], out[v]["holm_p"] if out[v]["holm_p"] is not None else 9,
                                       -out[v]["net_usd"]))
    pick = [best[0]] + ([best[1]] if RANK[out[best[1]]["verdict"]] <= 2 else [])
    frozen = {"family": "levels", "design": "research/orderflow/v5/levels/DESIGN.md", "frozen_on": "2026-11-27",
              "in_sample_days": days, "variants": {v: {"name": C.NAMES[v], "level_types": C.VARIANTS[v],
                                                       "in_sample": {k: out[v][k] for k in ("trades", "per_week", "win_pct", "mean_R", "pf", "net_usd", "max_dd_usd", "gap_R", "placebo_p", "holm_p", "verdict")}}
                                                   for v in pick},
              "rules": {"abs_zone_ticks": C.ZONE, "abs_share": C.ABS_SHARE, "window_mod": [C.W0, C.W1], "flat_mod": C.LAST,
                        "rr": C.RR, "entry": "E5 coarse: open beyond level = fill at open; else >=1 tick through = fill at level (stop-only that bar); else stop in bar = no fill; else next open + 18 ticks",
                        "stop": "1 tick beyond signal bar extreme; stop fill 2 ticks worse", "target": "2R, needs 1 tick through",
                        "comm_rt": C.COMM, "gx_min_vol": C.GX_MIN_VOL, "np_n": C.NP_N, "level_rule": "two-sided rejection (DESIGN)",
                        "one_position": True, "pass_bar": "YES-candidate: >=20 trades, net>0, PF>=1.2, both halves meanR>0 and gap>0, placebo p<0.10, Holm<0.10"}}
    with open(os.path.join(HERE, "frozen.json"), "w") as fh:
        json.dump(frozen, fh, indent=1)
    slim = {v: [{k: x.get(k) for k in ("day", "t_sig", "level", "L", "d", "absorbed", "busy", "how", "fill", "stop", "exit", "why", "R", "usd")}
                for x in cands[v]] for v in cands}
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump({"scores": out, "frozen": pick, "candidates": slim}, fh, indent=0, default=float)
    print("frozen:", pick)


VIDS = ["L1", "L2", "L3", "L4", "L5", "L6"]

if __name__ == "__main__":
    main()
