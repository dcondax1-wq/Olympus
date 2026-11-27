"""v5 'profile' runner: the 6 pre-registered variants (DESIGN.md) on the 51 in-sample real tick days. PAPER RESEARCH ONLY.

    python -X utf8 research/orderflow/v5/profile/run.py   -> results.json + the table
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core as C  # noqa: E402

IN_SAMPLE_LAST = "2026-11-26"


def main():
    D, usable = C.load_days()
    days = [d for d in usable if d <= IN_SAMPLE_LAST]
    print(f"days: {len(days)} usable {days[0]}..{days[-1]}")
    out, rows = {}, {}
    for vid in C.VARIANTS:
        cs = C.run_variant(D, days, vid)
        s = C.score(cs, days)
        s["ungated"] = C.ungated(cs)
        s["how_all"] = {}
        for x in cs:
            s["how_all"][x.get("how")] = s["how_all"].get(x.get("how"), 0) + 1
        out[vid], rows[vid] = s, cs
    adj = C.holm({v: out[v]["placebo_p"] for v in out})
    for v in out:
        out[v]["holm_p"] = adj[v]
        out[v]["verdict"] = C.verdict(out[v], adj[v])
    print(C.table([(v, out[v]) for v in out]))
    for v in out:
        print(v, "ungated", out[v]["ungated"], "| book fills", out[v]["how"], "| all", out[v]["how_all"],
              "| halves $", [h["usd"] for h in out[v]["halves"].values()], "| $500 risk", out[v]["usd500"])
    keep = ("day", "t_sig", "level", "L", "d", "absorbed", "stop", "tgt", "fill", "how", "why", "R", "usd", "usd500", "rr", "busy")
    json.dump({"days": days, "scores": out,
               "candidates": {v: [{k: x.get(k) for k in keep} for x in rows[v]] for v in rows}},
              open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
