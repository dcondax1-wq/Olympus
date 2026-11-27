"""v5 'trapped' OUT-OF-SAMPLE scorer: the frozen variants (frozen.json) on every usable pc_days day NOT in the 51 in-sample days.
PAPER RESEARCH ONLY. Same rules, same simulator (core.py -> levels/core.py), same table; Holm over the frozen variants only;
halves = the OOS days split by date. Levels may use earlier days as history (prior day / Globex), never as traded days.

    python -X utf8 research/orderflow/v5/trapped/oos.py [--json out.json] [--holdout N]
--holdout N: dry run that treats the LAST N in-sample days as 'new' (plumbing check only, not a result).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core as T  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--holdout", type=int, default=0)
    a = ap.parse_args(argv)
    F = json.load(open(os.path.join(HERE, "frozen.json")))
    ins = list(F["in_sample_days"])
    if a.holdout:
        ins = ins[:-a.holdout]
        print(f"DRY RUN: last {a.holdout} in-sample days treated as new (plumbing check, not a result)")
    ins = set(ins)
    D, usable = T.load_days()
    days = [d for d in usable if d not in ins]
    if not days:
        print(f"OOS: 0 new usable days (loaded {len(D)} files; in-sample {len(ins)}). Pull the new days first "
              f"(python tools/data_pull.py --latest --of), then run this again.")
        return 0
    print(f"OOS days: {len(days)} usable {days[0]}..{days[-1]} (in-sample excluded: {len(ins)})")
    out = {}
    for vid, fv in F["variants"].items():
        T.set_look(fv["look"])
        cs = T.run_variant(D, usable, days, fv["id"])
        out[vid] = T.score(cs, days)
        out[vid]["price_only"] = T.price_only(cs, days)
    adj = T.holm({v: out[v]["placebo_p"] for v in out})
    for v in out:
        out[v]["holm_p"] = adj[v]
        out[v]["verdict"] = T.verdict(out[v], adj[v])
    T.C.NAMES.update({v: F['variants'][v]['name'] for v in out})
    print(T.table([(v, out[v]) for v in out]))
    for v in out:
        ism = F["variants"][v]["in_sample"]
        print(f"{v} {F['variants'][v]['name']}: OOS {out[v]['trades']} trades {out[v]['mean_R']}R ${out[v]['net_usd']:+,.0f} -> {out[v]['verdict']}"
              f" | in-sample {ism['trades']} trades {ism['mean_R']}R ${ism['net_usd']:+,.0f} ({ism['verdict']})"
              f" | fills {out[v]['how']} | halves $ {[h['usd'] for h in out[v]['halves'].values()]} | price-only {out[v]['price_only']}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"days": days, "scores": out}, fh, indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
