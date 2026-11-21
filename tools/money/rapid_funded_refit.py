"""Rapid EOD funded refit (2026-11-21, day-rapid): the funded presets' winner cap, cushion and room share, on the Rapid EOD
25K and 50K. PAPER RESEARCH ONLY: reads stored trades, writes research/lab/rapid_funded_refit.json, changes nothing live.
Design (committed first): research/second/rapid_funded_refit_design.md. Write-up: research/writeups/rapid-funded-refit-2026-11-21.md.

    python -X utf8 tools/money/rapid_funded_refit.py run [--n 1000]
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)

OUT = os.path.join(ROOT, "research", "lab", "rapid_funded_refit.json")
SPANS = ("H1", "H2", "REF")
GRID = {"25k": {"cap": (1000.0, 2000.0), "cushion": (500.0, 1000.0), "room": (0.6, 0.4)},
        "50k": {"cap": (2000.0, 4000.0, 7500.0), "cushion": (1000.0, 2000.0), "room": (0.6, 0.4)}}
CAP_50K_MAX = 7500.0          # never above: a $10,000 day moves an MFFU Rapid to live and suspends every sim account


def key(cap, cush, room):
    return f"cap{int(cap)}_keep{int(cush)}_room{int(room * 100)}"


def spec(size, cap, cush, room):
    import rapid25 as R25
    import rapid_levers as RL
    import uprisk as U
    if size == "50k" and cap > CAP_50K_MAX:
        raise ValueError("the 50K is never uncapped past $7,500 (MFFU's $10,000 day moves it to live)")
    pol = ("cushion", float(cush))
    sp = dict(R25.acct(size, pol))
    _E, F = R25.rules(size)
    z = sp["z"]
    up = {**(U.UP25 if size == "25k" else U.UP50), "pct": float(room), "max_win": float(cap)}
    sp["fund"] = lambda: RL.Rapid(up, F, z, pol)
    return sp


def cmd_run(n=1000, log=print):
    import rapid25_launch as RLA
    AR = RLA._AR()
    t0 = time.time()
    AR.rapid_patch(AR.T_at(10))
    res = {"date": "2026-11-21", "design": "research/second/rapid_funded_refit_design.md", "n_paths": n,
           "cost": "ATLAS 10 ticks a side, ATLAS sized on a 10-tick stop", "rows": {"25k": {}, "50k": {}}}
    with RLA.slip10():
        for size, g in GRID.items():
            dll = 500.0 if size == "25k" else 1000.0
            for cap, cush, room in itertools.product(g["cap"], g["cushion"], g["room"]):
                k = key(cap, cush, room)
                r = RLA.life_row(spec(size, cap, cush, room), n, dll)
                res["rows"][size][k] = r
                log(f"{size} {k:26s} " + " | ".join(f"{s} ${r[s]['usd_m']}/mo lost {r[s]['lost_6m']}% 1st {r[s]['first_date']} "
                                                    f"none {r[s]['no_pay_6m']}%" for s in SPANS) + f"  [{time.time() - t0:.0f}s]")
    res["judge"] = {s: judge(s, res["rows"][s]) for s in GRID}
    res["took_s"] = round(time.time() - t0)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    log(json.dumps(res["judge"], indent=1))
    return res


def judge(size, rows):
    g = GRID[size]
    base = key(g["cap"][0], g["cushion"][0], g["room"][0])
    b = rows[base]
    cands = [k for k, r in rows.items() if k != base and all(r[s]["usd_m"] > b[s]["usd_m"] for s in ("H1", "H2"))
             and all(r[s]["lost_6m"] <= b[s]["lost_6m"] + 2.0 for s in ("H1", "H2"))]
    win = max(cands, key=lambda k: rows[k]["H1"]["usd_m"]) if cands else None
    cap_only = {key(c, g["cushion"][0], g["room"][0]) for c in g["cap"][1:]}
    keep_only = key(g["cap"][0], g["cushion"][1], g["room"][0])
    return {"base": base, "candidates": cands, "winner": win, "cap_only": sorted(cap_only), "keep_only": keep_only}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run",))
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    cmd_run(a.n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
