"""Round 2, DESIGN2 section 3: LIT x0.5 against the 00:00 True Day Open on FUNDED accounts only (real engine, rank.py funded
classes via research/onebook/book.py; the sizer hook of research/ictlab/proof.py). Paths start funded (no eval leg).

    python -X utf8 research/ictlab/tdo_funded.py [--n 1000]   -> research/ictlab/tdo_funded.json
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proof as PR  # noqa: E402  (book.py + the per-trade multiplier hook)

R, U, SOA, BK = PR.R, PR.U, PR.SOA, PR.BK
PLANS = ("mffu_builder_50k", "mffu_builder_25k", "mffu_rapid_eod_25k")


def funded_run(sp, paths, n_sess=126):
    rows = []
    for seq in paths:
        f = sp["fund"]()
        owner, pays, first, lost = 0.0, 0, None, None
        for k, si in enumerate(seq[:n_sess]):
            ev, x, _ = f.step(sp["BYf"][si])
            if ev in ("paid", "grad"):
                owner += x
                pays += 1
                first = first or k + 1
            if ev in ("lost", "grad"):
                lost = k + 1 if ev == "lost" else None
                break
        rows.append((owner, pays, first, lost))
    n = len(rows)
    fp = [r[2] for r in rows if r[2]]
    return {"owner_6m": round(float(np.mean([r[0] for r in rows]))), "owner_p10": round(float(np.percentile([r[0] for r in rows], 10))),
            "payouts": round(float(np.mean([r[1] for r in rows])), 2), "no_pay": round(100.0 * sum(1 for r in rows if not r[1]) / n, 1),
            "lost": round(100.0 * sum(1 for r in rows if r[3]) / n, 1), "first_med": float(np.median(fp)) if fp else None}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    S = SOA.data()["S"]
    PF = {s: U.mc_paths(S, s, a.n, length=R.LEN, seed=23) for s in PR.SPANS}
    out = {"n": a.n, "rule": "LIT x0.5 when the entry (at/after 00:00 ET) is long above / short below the 00:00 open; funded stage only",
           "plans": {}}
    for plan in PLANS:
        P = {}
        for lab, f in (("as_is", None), ("tdo_half", PR.m_A)):
            sp = PR.wrap(BK.build(plan, "B01 LIT only"))
            BK.CFG.clear()
            PR.MF["f"] = f
            P[lab] = {s: funded_run(sp, PF[s]) for s in PR.SPANS}
            PR.MF["f"] = None
        out["plans"][plan] = P
        for s in PR.SPANS:
            x, y = P["as_is"][s], P["tdo_half"][s]
            print(f"{plan:20s} {s:5s} owner ${x['owner_6m']} -> ${y['owner_6m']} (p10 {x['owner_p10']} -> {y['owner_p10']}) payouts "
                  f"{x['payouts']} -> {y['payouts']} lost {x['lost']}% -> {y['lost']}% no-pay {x['no_pay']} -> {y['no_pay']} "
                  f"first {x['first_med']} -> {y['first_med']}", flush=True)
    json.dump(out, open(os.path.join(HERE, "tdo_funded.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
