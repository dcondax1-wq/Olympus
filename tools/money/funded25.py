"""ATLAS's FUNDED Builder 25K: ATLAS alone vs LIT + ATLAS $250 on the same account (owner 2026-11-17, night-bot).

The owner's 25K eval showed $26,946.10 on 2026-11-17 (target $26,500: passed, MFFU locked it). So this scores the funded 25K
(engine/funded_life builder25k = MFFU: $1,000 EOD trailing, payouts above the $1,100 buffer, $250 min / $1,000 max, 80%,
50% consistency, 2 traded days a cycle, 5 payouts) from a fresh funded start, 6 months, with the same tooling as
research/writeups/builder-levers-2026-11-16.md (tools/money/builder_levers.py: GF, funded_run, the same Monte Carlo paths,
costs) and the live one-account rule the switch uses (engine/lit25.py):
  * never two positions on the account, never hedged: an ATLAS entry while LIT holds a trade (either side) is skipped;
  * LIT first: LIT entering (either side) while ATLAS holds closes ATLAS at market at LIT's entry (second_mix.cut_at, 1 tick);
  * ATLAS keeps one position, max 2 a day; LIT's opposite ARMED setups still block ATLAS (tools/atlas.no_hedge_real).

Mixes (funded only; a lost account is not re-bought here):
  ATLAS alone (today)        ATLAS at the 25K funded preset (60% of the room, <= $750, a winner <= $1,000)
  LIT + ATLAS $250           LIT at the 25K funded preset + ATLAS min($250, 30% of the room, the day left)
  LIT + ATLAS (both preset)  reference: both at the preset

    python -X utf8 tools/money/funded25.py [--n 600]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import builder_levers as BL  # noqa: E402

SA, U, np = BL.SA, BL.U, BL.np
OUT = os.path.join(BL.ROOT, "research", "lab", "builder_funded25.json")


def atlas_shared():
    """ATLAS's trades on an account LIT also trades (any-side rule above), one position, max 2 a day."""
    from tools import atlas as A
    from tools import second_mix as M
    D = SA.data()
    lit = collections.defaultdict(list)
    for i, d in enumerate(D["S"]):
        for t in D["LIT"][i]:
            lit[d].append((int(t["entry_t"]), int(t["exit_t"])))
    out, cur, busy, nday, n_skip, n_cut = [], None, 0, 0, 0, 0
    for t in A.account_units(A.BASE):
        L = lit.get(t["day"], ())
        if any(a <= t["entry_t"] < z for a, z in L):
            n_skip += 1
            continue
        nxt = min((a for a, _ in L if t["entry_t"] < a < t["exit_t"]), default=None)
        if nxt is not None:
            if not len(t["pt"]):
                continue
            pts, w1 = M.cut_at(t, nxt)
            t = {**t, "pts": pts, "w1": w1, "exit_t": nxt}
            n_cut += 1
        if t["day"] != cur:
            cur, busy, nday = t["day"], 0, 0
        if t["entry_t"] < busy or nday >= 2:
            continue
        busy, nday = t["exit_t"], nday + 1
        out.append({"day": t["day"], "risk": float(t["risk"]), "tgt": float(t["tgt"] or 0) or None, "pts": float(t["pts"]),
                    "w1": float(min(0.0, t["w1"])), "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]),
                    "strat": "ATLAS", "src": t["src"]})
    return out, n_skip, n_cut


def by_shared():
    D = SA.data()
    at, n_skip, n_cut = atlas_shared()
    by = collections.defaultdict(list)
    for t in at:
        by[t["day"]].append(t)
    pr = {"LIT": 0, "ATLAS": 1}
    BY = [sorted(list(D["LIT"][i]) + by.get(d, []), key=lambda t: (t["entry_t"], pr[t["strat"]])) for i, d in enumerate(D["S"])]
    return BY, {"atlas_skipped_lit_open": n_skip, "atlas_closed_for_lit": n_cut}


MIXES = {
    "ATLAS alone (today)": ({"ATLAS": ("fq", None)}, False),
    "LIT + ATLAS $250": ({"LIT": ("fq", None), "ATLAS": ("stack", 250.0, 0.3)}, True),
    "LIT + ATLAS (both preset)": ({"LIT": ("fq", None), "ATLAS": ("fq", None)}, True),
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    t0 = time.time()
    S = SA.data()["S"]
    PF = {sp: U.mc_paths(S, sp, a.n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    BYa = BL.by_mix(("ATLAS",))
    BYs, ov = by_shared()
    out = {"date": "2026-11-17", "why": "25K eval passed ($26,946.10 on 2026-11-17)", "n": a.n, "spans": U.SPAN,
           "overlap": ov, "rows": {}}
    print("one-account rule:", ov)
    for sp in BL.SPANS:
        row = {}
        for nm, (z, shared) in MIXES.items():
            BY = BYs if shared else BYa
            r = BL.funded_run(BY, PF[sp], lambda z=z: BL.GF("builder25k", U.UP25, z))
            r["plain_250"] = BL.plain(BY, sp, {"LIT": 250.0, "ATLAS": 250.0} if shared else {"ATLAS": 250.0})
            row[nm] = r
            p = r["plain_250"]
            print(f"{sp:3s} {nm:27s} 1st payout {r['first_med']} (p75 {r['first_p75']}) nopay {r['no_pay_6m']}% lost {r['lost_6m']}% "
                  f"payouts {r['payouts']} to you ${r['per_month']}/mo (${r['paid_6m']} in 6m) | $250 a trade: {p['tpw']}/wk "
                  f"PF {p['pf']} ${p['per_month']}/mo maxDD {p['max_dd']}")
        out["rows"][sp] = row
    if not a.no_save:
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=float)
        print("wrote", os.path.relpath(OUT, BL.ROOT))
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
