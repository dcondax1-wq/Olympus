"""PAYOUT POLICY over 12 months (research/payout/DESIGN.md, pre-registered 700b7705e + erratum 073e031ed). PAPER RESEARCH ONLY:
reads stored trades, writes research/payout/results.json; never requests a payout, changes nothing live.

3 accounts (25K ATLAS, 25K LIT + ATLAS $250, 50K LIT) x 3 markets (2026-like, 25% mix, 2021-25) x 5 request policies (asap,
half, today = max, max + cushion, cycle-timed), 252 sessions, payouts 1-4 only (the 5th moves the owner to live), the same
paths for every policy (tools/money/payout25.PolicyFunded on tools/uprisk.Funded = MFFU's Builder sim-funded rules).

    python -X utf8 tools/money/payout_year.py [--n 600]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import builder_levers as BL  # noqa: E402
import funded25 as F25  # noqa: E402
import payout25 as P25  # noqa: E402

SA, U, np = BL.SA, BL.U, BL.np
OUT = os.path.join(BL.ROOT, "research", "payout", "results.json")
YEAR, BLOCK, LAST = 252, 5, 4
MARKETS = {"2026-like": 1.0, "25% mix": 0.25, "2021-25": 0.0}


def policies(M, m):
    return {"asap": {"ask": m}, "half": {"ask": M / 2.0}, "today = max": {"ask": M},
            "max + cushion": {"ask": m, "cushion": 0.3 * M, "need": 1.3 * M}, "cycle-timed": {"ask": None, "cycle": "cycle25" if M <= 1000 else "cycle"}}


ACCOUNTS = {  # name -> (plan, cfg, z, shared trades)
    "25K ATLAS": ("builder25k", "UP25", {"ATLAS": ("fq", None)}, False),
    "25K LIT + ATLAS": ("builder25k", "UP25", {"LIT": ("fq", None), "ATLAS": ("stack", 250.0, 0.3)}, True),
    "50K LIT": ("builder50k", "UP50", {"LIT": ("fq", None)}, "lit"),
}


class Cushion(P25.PolicyFunded):
    """max + cushion: ask the full M only when M + 30 % of M sits above the buffer."""

    def _fast_track(self, day):
        tr = super()._fast_track(day)
        need = self.pol.get("need")
        if need is not None and tr["status"] == "ready" and tr["above_buffer"] < need:
            tr = dict(tr)
            tr["status"] = "eligible"
        return tr


def mix_paths(S, n, p26, seed=BL.A4.SEED_LIFE):
    a26, z26 = U.span_ix(S, "H1")[0], U.span_ix(S, "H2")[1]
    ar, zr = U.span_ix(S, "REF")
    rng = np.random.default_rng(seed)
    P = []
    for _ in range(n):
        s = []
        while len(s) < YEAR:
            lo, hi = (a26, z26) if rng.random() < p26 else (ar, zr)
            b = int(rng.integers(lo, hi - BLOCK + 1))
            s.extend(range(b, b + BLOCK))
        P.append(s[:YEAR])
    return P


def run(BY, paths, mk):
    out = []
    for seq in paths:
        f = mk()
        cash, first, npay, dead = 0.0, None, 0, False
        for k, si in enumerate(seq):
            ev, x = f.step(BY[si])
            if ev in ("paid", "grad"):
                cash += x
                npay += 1
                first = first or k + 1
                if npay >= LAST:
                    break                                   # payout 4 taken: close the account (never the 5th)
            if ev == "lost":
                dead = True
                break
        if not dead and npay < LAST and f.state == "on":
            floor = max(f.floor, f.A["lock"]) if f.pays else f.floor
            dead = f.bal - floor < P25.STUCK
        out.append((cash, first, npay, dead))
    c = np.array([x[0] for x in out])
    fr = [x[1] for x in out if x[1]]
    n = len(out)
    return {"cash_12m": round(float(c.mean())), "cash_p25": round(float(np.percentile(c, 25))), "cash_p75": round(float(np.percentile(c, 75))),
            "lost_pct": round(100.0 * sum(1 for x in out if x[3]) / n, 1), "no_pay_pct": round(100.0 * (n - len(fr)) / n, 1),
            "payouts": round(float(np.mean([x[2] for x in out])), 2), "first_med": float(np.median(fr)) if fr else None,
            "four_pct": round(100.0 * sum(1 for x in out if x[2] >= LAST) / n, 1)}


def pick(rows):
    base = "today = max"
    ok = lambda nm: all(rows[mk][nm]["lost_pct"] <= rows[mk][base]["lost_pct"] + 0.5 and
                        rows[mk][nm]["no_pay_pct"] <= rows[mk][base]["no_pay_pct"] + 2.0 for mk in MARKETS)
    cand = [nm for nm in rows["25% mix"] if ok(nm)]
    best = max(cand, key=lambda nm: (rows["25% mix"][nm]["cash_12m"], -(rows["25% mix"][nm]["first_med"] or 999)))
    gain = rows["25% mix"][best]["cash_12m"] - rows["25% mix"][base]["cash_12m"]
    return {"best": best, "gain_vs_today_25mix": gain, "adopt": best if (best != base and gain > 25) else base}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    t0 = time.time()
    S = SA.data()["S"]
    PM = {mk: mix_paths(S, a.n, p) for mk, p in MARKETS.items()}
    BYa, BYl = BL.by_mix(("ATLAS",)), BL.by_mix(("LIT",))
    BYs, ov = F25.by_shared()
    out = {"design": "research/payout/DESIGN.md", "n": a.n, "sessions": YEAR, "rows": {}, "pick": {}}
    for acct, (plan, cfg, z, shared) in ACCOUNTS.items():
        P = U.fplan(plan)[0]
        pols = policies(float(P["pay_max"]), float(P["pay_min"]))
        BY = BYl if shared == "lit" else (BYs if shared else BYa)
        rows = {}
        for mk in MARKETS:
            rows[mk] = {}
            for pn, pol in pols.items():
                cls = Cushion if "need" in pol else P25.PolicyFunded
                r = run(BY, PM[mk], lambda pol=pol, cls=cls: cls(plan, getattr(U, cfg), z, pol))
                rows[mk][pn] = r
                print(f"{acct:16s} {mk:9s} {pn:14s} ${r['cash_12m']:>5} (P25 {r['cash_p25']}, P75 {r['cash_p75']}) lost {r['lost_pct']}% "
                      f"nopay {r['no_pay_pct']}% pays {r['payouts']} 1st {r['first_med']} ({time.time() - t0:.0f}s)", flush=True)
        out["rows"][acct] = rows
        out["pick"][acct] = pick(rows)
        print(acct, json.dumps(out["pick"][acct]), flush=True)
    if not a.no_save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump(out, open(OUT, "w"), indent=1, default=float)
        print("wrote", os.path.relpath(OUT, BL.ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
