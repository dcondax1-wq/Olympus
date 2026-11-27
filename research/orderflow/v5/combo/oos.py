"""v5 'combo' OUT-OF-SAMPLE scorer: the frozen variants (frozen.json) on every usable pc_days day NOT in the 51 in-sample
days. Same code, same rules, same table; Holm over the frozen variants only. PAPER RESEARCH ONLY.

    python -X utf8 research/orderflow/v5/combo/oos.py            # all new days
    python -X utf8 research/orderflow/v5/combo/oos.py --mock 10  # plumbing check only: the last 10 in-sample days
Writes oos_results.json (not with --mock).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", type=int, default=0)
    a = ap.parse_args()
    F = json.load(open(os.path.join(HERE, "frozen.json")))
    ins = set(F["in_sample_days"])
    vids = list(F["variants"])
    D, usable = C.LV.load_days()
    days = sorted(ins)[-a.mock:] if a.mock else [d for d in usable if d not in ins]
    if not days:
        print("no out-of-sample days yet (pull the new tick days into data/pc_days first)")
        return
    print(f"OOS days: {len(days)} ({days[0]}..{days[-1]}){' MOCK' if a.mock else ''}; frozen {vids}")
    ctx = C.Context(D)
    cands = C.candidates(D, usable, days, ctx)
    out = {"C0": C.score(cands, days, None)}
    for v in vids:
        out[v] = C.score(cands, days, F["variants"][v]["flag"])
    adj = C.holm({v: out[v]["placebo_p"] for v in vids})
    for v in vids:
        out[v]["holm_p"] = adj[v]
        out[v]["verdict"] = C.verdict(out[v], adj[v])
    out["C0"]["verdict"] = "control (not scored)"
    print(C.table([(v, out[v]) for v in ["C0"] + vids]))
    for v in vids:
        ins_ = F["variants"][v]["in_sample"]
        print(f"{v} in-sample: {ins_['trades']} trades, {ins_['mean_R']}R, gap {ins_['gap_R']}, p {ins_['placebo_p']} -> "
              f"OOS: {out[v]['trades']} trades, {out[v]['mean_R']}R, gap {out[v]['gap_R']}, p {out[v]['placebo_p']}, "
              f"Holm {out[v]['holm_p']}: {out[v]['verdict']}")
    if not a.mock:
        with open(os.path.join(HERE, "oos_results.json"), "w") as fh:
            json.dump({"days": days, "scores": out}, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
