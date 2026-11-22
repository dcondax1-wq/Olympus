"""Fleet plan sensitivity (labelled post-hoc, after the pre-registered pick): MFFU's Risk team may move a Rapid account live at
its discretion (its own example: approved at $7,000 total profit) -> every MFFU sim stops. Rows: the 3 picks + L1 + L2 at $300,
with (a) no Risk-team move (the pick's model), (b) a move once one Rapid has paid $7,000, (c) we close a Rapid at $6,500 paid.
    python -X utf8 research/fleet/sens.py -> research/fleet/sens.json"""
import json, os, sys
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fleet as F

ROWS = [("L2 FundedNext 50K, then Rapid EOD 50K", 150), ("L3 Rapid EOD 50K + FundedNext 50K alternating", 300),
        ("L3 Rapid EOD 50K + FundedNext 50K alternating", 500), ("L1 Rapid EOD 50K, then Rapid 25K", 300),
        ("L2 FundedNext 50K, then Rapid EOD 50K", 300)]
MODES = {"no move": None, "Risk team moves at $7,000 paid": ("move", 7000.0), "close each Rapid at $6,500 paid": ("close", 6500.0)}
_P = {}


def job(a):
    l, b, m, span = a
    if span not in _P:
        _P[span] = F.U.mc_paths(F.SOA.data()["S"], span, 1000, length=F.LEN, seed=23)
    rows = [F.run_path(seq, F.LISTS[l], b, "S0", "P4", MODES[m]) for seq in _P[span]]
    return a, F.summarize(rows)


if __name__ == "__main__":
    grid = [(l, b, m, s) for l, b in ROWS for m in MODES for s in F.R.SPANS]
    out = {}
    with Pool(4) as pool:
        for (l, b, m, s), r in pool.imap_unordered(job, grid):
            out.setdefault(f"{l} | ${b}/mo | S0 | P4 | {m}", {})[s] = r
            print(l, b, m, s, r["net6"], r["p10_6"], r["live6"], r["net12"], r["corvette_med_months"], r["corvette_12m"], flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sens.json"), "w"), indent=1, default=float)
