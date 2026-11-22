"""Fleet plan (lane E follow-up, 2026-11-22): which mix of prop accounts for an eval budget of $150 / $300 / $500 a month.
PAPER RESEARCH ONLY. Design (committed before the scored run): research/fleet/DESIGN.md.
Engine: research/plans/rank.py through research/onebook/book.py (real fills); every account of a fleet on the SAME path.

    python -X utf8 research/fleet/fleet.py [--n 1000] [--jobs 4]   -> research/fleet/results.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "onebook"))
import book as B  # noqa: E402

R, SOA, U = B.R, B.SOA, B.U
OUT = os.path.join(HERE, "results.json")
LEN, MO, CORVETTE = 504, 21, 70000.0
B03, B11 = "B03 LIT + ATLAS first-come", "B11 size split: LIT x0.5 in the eval"
TYPES = {   # key -> (plan, book, firm, funded cap of this type)
    "B50": ("mffu_builder_50k", B03, "mffu", 1), "B25": ("mffu_builder_25k", B03, "mffu", 2),
    "R25": ("mffu_rapid_eod_25k", B03, "mffu", 3), "R50": ("mffu_rapid_eod_50k", B11, "mffu", 3),
    "FN": ("fn_rapid_daily_50k", B03, "fn", 2)}
LISTS = {"L0 today's types (B50, B25, R25)": ("B50", "B25", "R25"), "L1 Rapid EOD 50K, then Rapid 25K": ("R50", "R25"),
         "L2 FundedNext 50K, then Rapid EOD 50K": ("FN", "R50"), "L3 Rapid EOD 50K + FundedNext 50K alternating": ("R50", "FN"),
         "L4 Builder 50K, then Builder 25K": ("B50", "B25"), "L5 Rapid EOD 25K only": ("R25",)}
BUDGETS = (150, 300, 500)
STOPS = ("S0", "S3")
POLS = ("P4", "P5")
_SP = {}


def spec(key, book=None, pol="P5"):
    k = (key, book, pol)
    if k not in _SP:
        plan, bk, _, _ = TYPES[key]
        sp = B.build(plan, book or bk)
        if plan.startswith("mffu_builder") and pol == "P4":
            F4 = {**sp["F"], "max_payouts": 4}
            big = "50k" in plan
            ask = "cap" if F4["cap1"] < 1e8 else F4["pay_min"]
            sp["fund"] = lambda F4=F4, z=sp["z"], big=big, ask=ask: R.Funded(U.UP50 if big else U.UP25, F4, z, ask)
        _SP[k] = sp
    return _SP[k]


class Acct:
    def __init__(self, key, sp, e=None, f=None):
        self.key, self.sp, self.e, self.f, self.wait = key, sp, e, f, 0
        self.firm, self.builder, self.rapid = TYPES[key][2], key in ("B50", "B25"), key in ("R25", "R50")


def start_fleet(pol):
    """The owner's 4 MFFU accounts as they stand (sunk cost)."""
    out = []
    sp = spec("B50", "B09 LIT eval, LIT + ATLAS once funded", pol)
    e = sp["ev"]()
    e.bal, e.peak, e.floor, e.s, e.dtr = -807.0, 168.0, -1832.0, 10, 8
    out.append(Acct("B50", sp, e=e))
    sp = spec("B25", "B02 ATLAS only", pol)
    f = sp["fund"]()
    f.bal, f.peak, f.floor = -113.0, 0.0, -1000.0
    out.append(Acct("B25", sp, f=f))
    sp = spec("R25", B03, pol)
    out.append(Acct("R25", sp, e=sp["ev"]()))
    sp = spec("B25", "B01 LIT only", pol)
    out.append(Acct("B25", sp, e=sp["ev"]()))
    return out


def run_path(seq, blist, budget, stop, pol):
    accts = start_fleet(pol)
    avail, fees, owner, streak, stopped, live, fn_pays = 0.0, 0.0, 0.0, 0, False, None, 0
    cum6 = cum12 = None
    hit = None
    buys = []
    pays = 0
    turn = 0
    for k, si in enumerate(seq[:LEN]):
        if k % MO == 0:
            avail += budget
        # ---- buy
        if not stopped:
            alt = blist == ("R50", "FN")
            while True:
                order = list(blist[turn % 2:] + blist[:turn % 2]) if alt else list(blist)
                bought = False
                for t in order:
                    plan, _, firm, cap = TYPES[t]
                    price = R.PLANS[plan]
                    if price > avail + 1e-9 or (firm == "mffu" and live) or (firm == "fn" and fn_pays >= 15):
                        continue
                    same = sum(1 for x in accts if x.key == t)
                    mffu = sum(1 for x in accts if x.firm == "mffu")
                    if same >= cap or (firm == "mffu" and mffu >= 5):
                        continue
                    sp = spec(t, None, pol)
                    accts.append(Acct(t, sp, e=sp["ev"]()))
                    avail -= price
                    fees += price
                    buys.append((k, t))
                    bought = True
                    turn += 1
                    break
                if not bought:
                    break
        # ---- trade the day
        keep = []
        for a in accts:
            if a.firm == "mffu" and live:
                continue                                    # dormant after the live move
            B.CFG.clear()
            B.CFG.update(a.sp["knobs"])
            if a.e is not None:
                r, _ = a.e.step(a.sp["BYe"][si])
                if r == "pass":
                    a.e, a.wait = None, R.GAP
                elif r in ("fail", "stuck"):
                    streak += 1
                    continue
                keep.append(a)
                continue
            if a.f is None:
                a.wait -= 1
                if a.wait <= 0:
                    a.f = a.sp["fund"]()
                keep.append(a)
                continue
            ev, x, cum = a.f.step(a.sp["BYf"][si])
            if ev in ("paid", "grad"):
                owner += x
                pays += 1
                streak = 0
                if a.firm == "fn":
                    fn_pays += 1
            if a.rapid and cum is not None and cum >= 10000.0:
                live = live or ("rapid10k", k)
            if ev == "lost":
                streak += 1
                continue
            if ev == "grad":
                if a.builder and pol == "P5":
                    live = live or ("builder5", k)
                continue
            keep.append(a)
        accts = keep
        if stop == "S3" and streak >= 3:
            stopped = True
        if k == 125:
            cum6 = (owner, fees, pays, bool(live))
        if k == 251:
            cum12 = (owner, fees, bool(live))
        if hit is None and owner - fees >= CORVETTE:
            hit = k + 1
    B.CFG.clear()
    return {"o6": cum6[0], "f6": cum6[1], "p6": cum6[2], "live6": cum6[3], "o12": cum12[0], "f12": cum12[1], "hit": hit,
            "live12": cum12[2], "net24": owner - fees, "buy0": [t for kk, t in buys if kk == 0], "buys6": [t for kk, t in buys if kk < 126]}


def summarize(rows):
    n6 = np.array([r["o6"] - r["f6"] for r in rows])
    n12 = np.array([r["o12"] - r["f12"] for r in rows])
    hits = [r["hit"] for r in rows]
    hv = sorted(h if h else 10 ** 6 for h in hits)
    med = hv[len(hv) // 2]
    from collections import Counter
    b6 = Counter(t for r in rows for t in r["buys6"])
    return {"net6": round(float(n6.mean())), "per_month": round(float(n6.mean()) / 6), "p10_6": round(float(np.percentile(n6, 10))),
            "owner6": round(float(np.mean([r["o6"] for r in rows]))), "fees6": round(float(np.mean([r["f6"] for r in rows])), 1),
            "pays6": round(float(np.mean([r["p6"] for r in rows])), 1), "live6": round(100.0 * float(np.mean([r["live6"] for r in rows])), 1),
            "net12": round(float(n12.mean())), "p10_12": round(float(np.percentile(n12, 10))),
            "live12": round(100.0 * float(np.mean([r["live12"] for r in rows])), 1),
            "net24": round(float(np.mean([r["net24"] for r in rows]))),
            "corvette_med_months": (round(med / MO, 1) if med < 10 ** 6 else None),
            "corvette_6m": round(100.0 * sum(1 for h in hits if h and h <= 126) / len(rows), 1),
            "corvette_12m": round(100.0 * sum(1 for h in hits if h and h <= 252) / len(rows), 1),
            "corvette_24m": round(100.0 * sum(1 for h in hits if h) / len(rows), 1),
            "buy_week1": rows[0]["buy0"], "buys6_avg": {t: round(c / len(rows), 2) for t, c in b6.items()}}


_PATHS = {}


def job(args):
    lname, budget, stop, pol, span, n = args
    if span not in _PATHS:
        S = SOA.data()["S"]
        _PATHS[span] = U.mc_paths(S, span, n, length=LEN, seed=23)
    rows = [run_path(seq, LISTS[lname], budget, stop, pol) for seq in _PATHS[span]]
    return (lname, budget, stop, pol, span), summarize(rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args(argv)
    t0 = time.time()
    grid = [(l, b, s, p, sp, a.n) for l, b, s, p in itertools.product(LISTS, BUDGETS, STOPS, POLS) for sp in R.SPANS]
    out = {}
    with Pool(a.jobs) as pool:
        for key, res in pool.imap_unordered(job, grid):
            l, b, s, p, sp = key
            out.setdefault(f"{l} | ${b}/mo | {s} | {p}", {})[sp] = res
            print(f"{l:48s} ${b} {s} {p} {sp:3s} net6 ${res['net6']} p10 ${res['p10_6']} fees ${res['fees6']} live6 {res['live6']}% "
                  f"corvette {res['corvette_med_months']} mo (6m {res['corvette_6m']}%, 12m {res['corvette_12m']}%) [{time.time() - t0:.0f}s]", flush=True)
    pick = {}
    for b in BUDGETS:
        base = out[f"L0 today's types (B50, B25, R25) | ${b}/mo | S0 | P4"]["REF"]["net6"]
        c = [(v["H2"]["net6"], k) for k, v in out.items() if f"| ${b}/mo |" in k and v["REF"]["net6"] >= base - b]
        c.sort(reverse=True)
        h1 = max((v["H1"]["net6"], k) for k, v in out.items() if f"| ${b}/mo |" in k)
        pick[str(b)] = {"pick": c[0][1], "ref_bar": base - b, "eligible": len(c), "best_h1": h1[1]}
    json.dump({"n": a.n, "fleets_counted": len(out), "rows": out, "pick": pick}, open(OUT, "w"), indent=1, default=float)
    print("PICK", json.dumps(pick, indent=1))


if __name__ == "__main__":
    main()
