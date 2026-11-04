"""BLITZ on a funded MFFU Builder 25K, funded stage only (job 29, 2026-11-04): the funded study for the BLITZ trades, like lit_funded for LIT.
Uses the existing funded-life model (tools/scalp_na_lib.Funded via tools/blitz25k_size.funded_score and .life): BLITZ as account C (never opposite
LIT / ATLAS), the funded size of research/scalp/blitz_25k_pick.json (10% of the room, <= $150 a trade, no new trade after +$400 on the day),
$ a month to the owner (80%) over 3-month funded accounts started every 3rd session (every start runs to the end of the half), plus the whole
slot (eval -> funded -> payouts, net of every eval, 6-month Monte Carlo) for comparison. Pick Jan-Jun, check Jul-Oct, 2021-25 reference.

    python -X utf8 tools/blitz_funded_study.py     # -> research/scalp/blitz_funded_study.json
`funded_only` = 3-month funded accounts started every 3rd session (22 starts in Jan-Jun, only 6 in Jul-Oct: too few); `funded_mc` = 1,000 six-month
Monte Carlo paths (5-session blocks of the span), the figure the pages show.
Research only; nothing live.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import ab_edge as AB  # noqa: E402
from tools import blitz_funded_fix as FX  # noqa: E402

OUT = os.path.join(ROOT, "research", "scalp", "blitz_funded_study.json")


def main():
    N, K, BS = AB.blitz_libs()
    TT = AB.blitz_trades()
    SP = AB.spans_of(TT)
    out = {"what": "BLITZ funded-stage-only study on a Builder 25K (account C trades, funded size 10% of the room <= $150, day stop +$400)",
           "funded_size": AB.PICK_FZ, "eval_size": AB.PICK_EZ, "spans": {}}
    for sp, (T, S) in SP.items():
        key = {"H1": "H1", "H2": "H2", "R": "2021-25"}[sp]
        f = BS.funded_score(T, S, AB.PICK_FZ)
        slot = AB.slot25(T, S, n=1000)
        mc = FX.funded_mc(N, BS, T, S, dict(AB.PICK_FZ)) if sp != "R" else None       # 1,000 paths x 126 sessions: the figure the pages show
        out["spans"][key] = {"funded_only": f, "funded_mc": mc, "slot": slot, "trades": len(T), "sessions": len(S)}
        print(key, f, mc, slot, flush=True)
    json.dump(out, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
