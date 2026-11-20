"""Skeptic re-test of Decide card atlas-funded-streak-1micro (day-atlasedge E3: after 2 losing ATLAS trades in a row, 1 micro
until the next winner) on the funded Builder 25K from today's account. PAPER RESEARCH ONLY; reuses the card's own simulator
(tools/atlas_edge.py -> tools/atlas_risk PGF3 -> tools/atlas_more PGF2) unchanged and adds only: other path seeds, a 1-day
block bootstrap, 2021-25 year by year, neighbours (1 / 3 losses, cap 2 / 3 micros, streak per leg) and flat smaller sizes.

    python -X utf8 research/skeptic/streak.py [--n 1000]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")):
    sys.path.insert(0, p)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from tools import atlas_edge as AE  # noqa: E402

OUT = os.path.join(HERE, "streak_results.json")
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16"), "REF": ("2021-11-01", "2025-12-31"),
         "Y21-22": ("2021-11-01", "2022-12-31"), "Y2023": ("2023-01-01", "2023-12-31"), "Y2024": ("2024-01-01", "2024-12-31"),
         "Y2025": ("2025-01-01", "2025-12-31")}


def pgs():
    P3 = AE.AR().pgf3()

    class PGS(P3):
        """The card's rule generalised: after `n` losing trades in a row (globally, or per leg with leg=True), at most `cap`
        micros until the next winner. Streak updated at the end of each session from that session's trades (as the card)."""

        def __init__(self, I):
            super().__init__(I)
            self.streak, self.leg_streak, self.qs = 0, {}, []

        def qty(self, t, st):
            q = super().qty(t, st)
            I = self.I
            n = I.get("n")
            if n:
                s = self.leg_streak.get(t["src"], 0) if I.get("leg") else self.streak
                if s >= int(n) and q > int(I.get("cap", 1)):
                    q = int(I.get("cap", 1))
            if q > 0:
                self.qs.append(q)
            return q

        def step(self, ts, keep=None):
            kp = []
            r = super().step(ts, kp)
            if keep is not None:
                keep.extend(kp)
            for t, _, p in kp:
                self.streak = self.streak + 1 if p < 0 else 0
                self.leg_streak[t["src"]] = self.leg_streak.get(t["src"], 0) + 1 if p < 0 else 0
            return r
    return PGS


def paths(S, span, n, seed, block):
    a, z = SPANS[span]
    ix = [i for i, d in enumerate(S) if a <= d <= z]
    lo, hi = ix[0], ix[-1] + 1
    rng = np.random.default_rng(seed)
    from tools import uprisk as U
    P = []
    for _ in range(n):
        s = []
        while len(s) < U.LEN:
            b = int(rng.integers(lo, hi - block + 1))
            s.extend(range(b, b + block))
        P.append(s[:U.LEN])
    return P


def run(I, BY, P):
    from tools import uprisk as U
    PG = pgs()
    rows, qs = [], []
    for seq in P:
        f = AE.AM().at_today(PG(I))
        owner, first, end = 0.0, None, "on"
        for k, si in enumerate(seq):
            ev, x = f.step(BY[si])
            if ev in ("paid", "grad"):
                owner += x
                first = first or k + 1
            if ev in ("lost", "grad"):
                end = ev
                break
            if f.dead:
                end = f.dead
                break
        rows.append((owner / (U.LEN / 21.0), first, end))
        qs.extend(f.qs)
    n = len(rows)
    fr = np.array([r[1] if r[1] else 10 ** 6 for r in rows], float)
    m = float(np.percentile(fr, 50, method="lower"))
    return {"usd_m": round(float(np.mean([r[0] for r in rows]))),
            "lost_6m": round(100.0 * sum(r[2] in ("lost", "stuck", "idle") for r in rows) / n, 1),
            "first_k": None if m >= 10 ** 6 else int(m), "avg_q": round(float(np.mean(qs)), 2) if qs else 0.0}


VARIANTS = {
    "base": {"stuck": 0.0},
    "E3 2 losses -> 1 micro (card)": {"stuck": 0.0, "n": 2, "cap": 1},
    "1 loss -> 1 micro": {"stuck": 0.0, "n": 1, "cap": 1},
    "3 losses -> 1 micro": {"stuck": 0.0, "n": 3, "cap": 1},
    "2 losses -> 2 micros": {"stuck": 0.0, "n": 2, "cap": 2},
    "2 losses -> 3 micros": {"stuck": 0.0, "n": 2, "cap": 3},
    "2 losses of the same leg -> 1 micro (leg reset)": {"stuck": 0.0, "n": 2, "cap": 1, "leg": True},
    "flat 50% of room": {"stuck": 0.0, "pct": 0.5},
    "flat 40% of room": {"stuck": 0.0, "pct": 0.4},
    "flat 30% of room": {"stuck": 0.0, "pct": 0.3},
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    from tools import atlas_revive as RV
    t0 = time.time()
    S = AE.AM().sessions()
    out = {"n": a.n, "rows": {}}
    for ticks in (10, 6):
        T = AE.to_T(AE.opt_units("base", ticks)[0])
        BY = RV.by_session(T, S)
        sets = [("week blocks seed 23 (card)", 23, 5, ("H1", "H2", "REF")),
                ("week blocks seed 101", 101, 5, ("H1", "H2", "REF")),
                ("week blocks seed 7919", 23 + 7919, 5, ("H1", "H2", "REF")),
                ("day blocks seed 23", 23, 1, ("H1", "H2", "REF")),
                ("2021-25 by year, week blocks", 23, 5, ("Y21-22", "Y2023", "Y2024", "Y2025"))]
        for label, seed, block, spans in sets:
            P = {sp: paths(S, sp, a.n, seed, block) for sp in spans}
            only = None if label.startswith("week blocks seed 23") else ("base", "E3 2 losses -> 1 micro (card)")
            for vn, I in VARIANTS.items():
                if only and vn not in only:
                    continue
                r = {sp: run(I, BY, P[sp]) for sp in spans}
                out["rows"][f"{ticks}t | {label} | {vn}"] = r
                print(f"{ticks}t | {label:30s} | {vn:46s} | " + " | ".join(
                    f"{sp} ${r[sp]['usd_m']} lost {r[sp]['lost_6m']}% 1st {r[sp]['first_k']} q {r[sp]['avg_q']}" for sp in spans) +
                    f" [{time.time() - t0:.0f}s]", flush=True)
            with open(OUT, "w", encoding="utf-8") as fh:
                json.dump(out, fh, indent=1)
    return out


if __name__ == "__main__":
    main()
