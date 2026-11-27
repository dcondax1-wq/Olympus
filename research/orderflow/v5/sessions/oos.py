"""v5 'sessions' OUT-OF-SAMPLE scorer: the frozen variants (frozen.json) on every usable pc_days day NOT in the 51 in-sample days.
PAPER RESEARCH ONLY. Same rules, same simulator (core.py), same table; Holm over the frozen variants only; halves = the OOS days
split by date. In-sample days may serve as level history (prior day, Globex/Asia evening), never as traded days.

    python -X utf8 research/orderflow/v5/sessions/oos.py [--json out.json] [--mock-last N]
--mock-last N = plumbing check only: treat the last N in-sample days as 'new' (NOT out-of-sample, never report it as such).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core as C  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--mock-last", type=int, default=0)
    a = ap.parse_args(argv)
    F = json.load(open(os.path.join(HERE, "frozen.json")))
    ins = set(F["in_sample_days"])
    if a.mock_last:
        ins -= set(sorted(ins)[-a.mock_last:])
        print(f"MOCK: last {a.mock_last} in-sample days treated as new (plumbing check, NOT out-of-sample)")
    D, usable = C.load_days()
    days = [d for d in usable if d not in ins]
    if not days:
        print(f"OOS: 0 new usable days (loaded {len(D)} files; in-sample {len(ins)}). Pull the new days first "
              f"(python tools/data_pull.py --latest --of), then run this again.")
        return 0
    print(f"OOS days: {len(days)} usable {days[0]}..{days[-1]} (in-sample excluded: {len(ins)})")
    out = {}
    for vid in F["variants"]:
        assert list(C.VARIANTS[vid][0]) == F["variants"][vid]["windows"] and C.VARIANTS[vid][1] == F["variants"][vid]["touch_mode"]
        cs = C.run_variant(D, usable, days, vid)
        out[vid] = C.score(cs, days)
    adj = C.holm({v: out[v]["placebo_p"] for v in out})
    for v in out:
        out[v]["holm_p"] = adj[v]
        out[v]["verdict"] = C.verdict(out[v], adj[v])
    print(C.table([(v, out[v]) for v in out]))
    for v in out:
        ism = F["variants"][v]["in_sample"]
        s = out[v]
        print(f"{v} {C.NAMES[v]}: OOS {s['trades']} trades {s['mean_R']}R ${s['net_usd']:+,.0f} (1 micro), max DD ${s['max_dd_usd']:,.0f}"
              f" -> {s['verdict']} | in-sample {ism['trades']} trades {ism['mean_R']}R ${ism['net_usd']:+,.0f} ({ism['verdict']})"
              f" | fills {s['how']} | halves $ {[h['usd'] for h in s['halves'].values()]} | by window {s['by_window']}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"days": days, "mock": bool(a.mock_last), "scores": out}, fh, indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
