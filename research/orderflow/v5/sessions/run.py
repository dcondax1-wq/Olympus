"""v5 'sessions' in-sample run on the 51 days (DESIGN.md frozen first). PAPER RESEARCH ONLY.

    python -X utf8 research/orderflow/v5/sessions/run.py
Writes results.json + frozen.json (best 1-2 tested variants by verdict, Holm p, net $; picked by rule, not by hand).
"""
from __future__ import annotations

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core as C  # noqa: E402

IS_FIRST, IS_LAST = "2026-09-27", "2026-11-26"
RANK = {"YES-candidate": 0, "weak": 1, "NO": 2, "TOO FEW": 3}
VIDS = ["S1", "S2", "S3", "S4", "S5", "S6"]


def main():
    D, usable = C.load_days()
    days = [d for d in usable if IS_FIRST <= d <= IS_LAST]
    print(f"days: {len(days)} usable {days[0]}..{days[-1]} (files loaded {len(D)})")
    out, cands = {}, {}
    for vid in ["V0"] + VIDS:
        cs = C.run_variant(D, usable, days, vid)
        cands[vid] = cs
        out[vid] = C.score(cs, days)
    sw = copy.deepcopy(cands["S1"] + cands["S2"] + cands["S3"] + cands["S4"])
    out["SW"] = C.score(sw, days)
    adj = C.holm({v: out[v]["placebo_p"] for v in VIDS})
    for v in VIDS:
        out[v]["holm_p"] = adj[v]
        out[v]["verdict"] = C.verdict(out[v], adj[v])
    out["V0"]["verdict"] = out["SW"]["verdict"] = "descriptive"
    print(C.table([(v, out[v]) for v in ["V0"] + VIDS + ["SW"]]))
    for v in ["V0"] + VIDS + ["SW"]:
        s = out[v]
        print(v, "fills", s["how"], "exits", s["why"], "no-fill", s["no_fill"], "notabs R", s["notabs_mean_R"],
              "$500", s["usd500"], "risk pts", s["mean_risk_pts"], "halves $", {k: h["usd"] for k, h in s["halves"].items()},
              "\n   by window", s["by_window"], "\n   by level", s["by_level"])
    best = sorted(VIDS, key=lambda v: (RANK[out[v]["verdict"]], out[v]["holm_p"] if out[v]["holm_p"] is not None else 9,
                                       -out[v]["net_usd"]))
    pick = [best[0]] + ([best[1]] if RANK[out[best[1]]["verdict"]] <= 2 else [])
    frozen = {"family": "sessions", "design": "research/orderflow/v5/sessions/DESIGN.md", "frozen_on": "2026-11-27",
              "in_sample_days": days,
              "variants": {v: {"name": C.NAMES[v], "windows": list(C.VARIANTS[v][0]), "touch_mode": C.VARIANTS[v][1],
                               "window_defs": {w: {"signal_bar_open_mod": [C.WINDOWS[w][0], C.WINDOWS[w][1]],
                                                   "flat_bar_open_mod": C.WINDOWS[w][2], "levels": list(C.WINDOWS[w][3])}
                                               for w in C.VARIANTS[v][0]},
                               "in_sample": {k: out[v][k] for k in ("trades", "per_week", "win_pct", "mean_R", "pf", "net_usd",
                                                                    "max_dd_usd", "gap_R", "placebo_p", "holm_p", "verdict")}}
                           for v in pick},
              "rules": {"abs_zone_ticks": 8, "abs_share": C.ABS_SHARE, "min_bar_trades": 20, "rr": C.RR,
                        "level_priority": list(C.ORDER), "level_known_from_mod": C.KNOWN,
                        "entry": "E5 coarse: entry bar opens at/beyond level = fill at open; else >=1 tick through = fill at level (stop-only that bar); else stop in bar = no fill; else next open + 18 ticks",
                        "stop": "1 tick beyond signal bar extreme; stop fill 2 ticks worse", "target": "2R, needs 1 tick through",
                        "flat": "close of the window's flat bar - 2 ticks", "comm_rt": C.COMM, "one_position": True,
                        "pass_bar": "YES-candidate: >=20 trades, net>0, PF>=1.2, both halves meanR>0 and gap>0, placebo p<0.10, Holm<0.10"}}
    with open(os.path.join(HERE, "frozen.json"), "w") as fh:
        json.dump(frozen, fh, indent=1)
    slim = {v: [{k: x.get(k) for k in ("day", "t_sig", "win", "level", "L", "d", "absorbed", "busy", "how", "fill", "stop", "exit",
                                       "why", "R", "usd")} for x in cands[v]] for v in cands}
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump({"scores": out, "frozen": pick, "candidates": slim}, fh, indent=0, default=float)
    print("frozen:", pick)


if __name__ == "__main__":
    main()
