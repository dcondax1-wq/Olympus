"""Lane A forward scoreboard: the pre-registered gate (research/orderflow/DESIGN_lanea_proof.md "forward gate") as one pure
function, for tools/forward_paper.py to print nightly (LEAD_WIRES.md). PAPER RESEARCH ONLY.

    python -X utf8 research/orderflow/lanea_proof/scoreboard.py            # the gate on the pulled days (forward days only)
    python -X utf8 research/orderflow/lanea_proof/scoreboard.py --history  # the same board on the 51 history days (a check)
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

FORWARD_FROM = "2026-11-27"
GATE = {"n": 30, "mean_R": 0.20, "PF": 1.30, "maxdd_R": 6.0}
COMM, PV = 1.90, 2.0


def usd1(r):
    """$ at 1 micro with the $1.90 round trip (the paper row's usd_1 uses $1.40)."""
    return (r["exit"] - r["fill"]) * r["d"] * PV - COMM


def score(rows, since=FORWARD_FROM):
    """rows = lane A decision rows (engine/of_paper state / NQ_paper.json.gz 'rows', or replay_summary rows) of any days.
    Returns the board dict; 'line' is the plain-words line for the Brain room / the nightly print."""
    A = [r for r in rows if r.get("lane") == "A" and r.get("day", "") >= since and r.get("R") is not None and r.get("exit") is not None]
    A.sort(key=lambda r: (r["day"], r.get("t_sig") or 0))
    tk = [r for r in A if r.get("taken")]
    sk = [r for r in A if not r.get("taken")]
    R = np.array([r["R"] for r in tk], float)
    U = np.array([usd1(r) for r in tk], float)
    b = {"since": since, "taken": len(tk), "skipped": len(sk), "need": GATE["n"]}
    if len(tk):
        eq = np.cumsum(R)
        pos, neg = U[U > 0].sum(), -U[U < 0].sum()
        days = sorted({r["day"] for r in tk})
        half = days[len(days) // 2] if len(days) > 1 else days[0]
        h1 = [r["R"] for r in tk if r["day"] < half]
        h2 = [r["R"] for r in tk if r["day"] >= half]
        b.update(mean_R=round(float(R.mean()), 3), PF=round(float(pos / neg), 2) if neg > 0 else None, net_1=round(float(U.sum()), 2),
                 maxdd_R=round(float(np.max(np.maximum.accumulate(np.r_[0.0, eq])[1:] - eq)), 2),
                 skipped_mean_R=round(float(np.mean([r["R"] for r in sk])), 3) if sk else None,
                 half1_mean_R=round(float(np.mean(h1)), 3) if h1 else None, half2_mean_R=round(float(np.mean(h2)), 3) if h2 else None)
        checks = {"n >= 30": len(tk) >= GATE["n"], "mean R >= +0.20": b["mean_R"] >= GATE["mean_R"],
                  "PF >= 1.30": (b["PF"] is None and pos > 0) or (b["PF"] or 0) >= GATE["PF"],
                  "taken > skipped": b["skipped_mean_R"] is None or b["mean_R"] > b["skipped_mean_R"],
                  "both halves >= 0R": (b["half1_mean_R"] or 0) >= 0 and (b["half2_mean_R"] or 0) >= 0,
                  "max DD <= 6R": b["maxdd_R"] <= GATE["maxdd_R"]}
        b["checks"] = checks
    else:
        checks = {}
    if len(tk) < GATE["n"]:
        b["status"] = "TOO FEW"
        fail_early = len(tk) >= 10 and b.get("maxdd_R", 0) > GATE["maxdd_R"]
        if fail_early:
            b["status"] = "REJECTED (max DD over 6R before 30 trades)"
    else:
        b["status"] = "PASS: owner card (eval size re-test first)" if all(checks.values()) else "REJECTED"
    if len(tk):
        b["line"] = (f"Lane A forward (paper, from {since}): {len(tk)} of {GATE['n']} taken trades, {b['mean_R']:+.2f}R avg, PF {b['PF']}, "
                     f"${b['net_1']:+,.0f} at 1 micro, max DD {b['maxdd_R']}R; skipped {len(sk)} at {b['skipped_mean_R']}R -> {b['status']}")
    else:
        b["line"] = f"Lane A forward (paper, from {since}): 0 of {GATE['n']} taken trades yet -> TOO FEW"
    return b


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", action="store_true")
    a = ap.parse_args(argv)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import proof as PR
    R, B = PR.load_days()
    if not R:
        print("no order-flow day here")
        return 2
    _days, rows, _D = PR.signals(R, B)
    print(score(rows, since="2000-01-01" if a.history else FORWARD_FROM)["line"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
