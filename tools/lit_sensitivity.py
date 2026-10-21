"""Parameter sensitivity of the live LIT config: heat-map grids around its key knobs.

Each cell is the live settings (live_model.json "lit") with one or two knobs moved, replayed by the engine
(tools/lit_final.run = engine/lit.py run_x, LIT size rule, costs in) and scored the LIT way: 2026 H1 (where the settings
were picked), H2 (the check) and 2026, with 2021-25 as a reference line (5m bars only there: t_check never acts).
  depth x disp          sweep depth (ATR) x displacement body (ATR)
  min_stop x max_stop   the planned stop range (pts)
  t_check at x x        the 15-minute check: minutes after the fill x how far below the entry (R) the close must be
  be_off                breakeven offset (pts above the entry)
A cell is a plateau when its neighbours make about the same money; a sharp knob is one whose neighbours fall off. The live
cell is marked. Output research/lab/sensitivity.json (PC: Data -> Sensitivity; the old engine's study is in
research/archive/engine-2026-10-17/sensitivity.json).

    python -X utf8 tools/lit_sensitivity.py            # ~70 replays, ~5-8 min with the LIT candidate cache
    python -X utf8 tools/lit_sensitivity.py --quick    # coarser grids (~25 replays)
Read-only research: nothing in live_model.json changes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "lab", "sensitivity.json")
SP = ("H1", "H2", "2026", "2021-25")
MONTHS = {"H1": 6.0, "H2": 3.5, "2026": 9.5, "2021-25": 50.0}


def grids(quick=False):
    """(id, title, x knob, x values, y knob, y values, how to set a cell)."""
    if quick:
        return [
            ("depth_disp", "Sweep depth x displacement (ATR)", "depth", [0.4, 0.5, 0.6], "disp", [0.7, 0.8, 0.9], None),
            ("stop_range", "Stop range (pts)", "min_stop", [6.0, 8.0, 10.0], "max_stop", [70.0, 80.0, 90.0], None),
            ("t_check", "15-minute check: minutes x R below entry", "at", [10, 15, 20], "x", [0.2, 0.3, 0.4], "t_check"),
            ("be_off", "Breakeven offset (pts)", "be_off", [0.0, 1.25, 2.0], None, None, None),
        ]
    return [
        ("depth_disp", "Sweep depth x displacement (ATR)", "depth", [0.3, 0.4, 0.5, 0.6, 0.7], "disp", [0.6, 0.7, 0.8, 0.9, 1.0], None),
        ("stop_range", "Stop range (pts)", "min_stop", [6.0, 8.0, 10.0, 12.0], "max_stop", [60.0, 70.0, 80.0, 90.0, 100.0], None),
        ("t_check", "15-minute check: minutes x R below entry", "at", [10, 15, 20, 25], "x", [0.2, 0.3, 0.4, 0.5], "t_check"),
        ("be_off", "Breakeven offset (pts)", "be_off", [0.0, 0.5, 1.0, 1.25, 1.5, 2.0, 3.0], None, None, None),
    ]


def cell_params(base, xk, xv, yk, yv, nest):
    P = json.loads(json.dumps(base))
    if nest:
        P[nest] = {**(P.get(nest) or {}), xk: xv, **({yk: yv} if yk else {})}
    else:
        P[xk] = xv
        if yk:
            P[yk] = yv
    return P


def score(T):
    from tools import lit_final as F
    o = F.score(T, spans=SP, fast=True)
    out = {}
    for s in SP:
        x = o[s]
        out[s] = {"n": x["n"], "tpw": x["tpw"], "pf": x["pf"], "net": x["net"], "dd": x["dd"], "per_month": round(x["net"] / MONTHS[s])}
    return out


def build(quick=False):
    from engine import lit
    from tools import lit_final as F
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    base = {**lit.DEFAULTS, **lm["lit"]}
    t0 = time.time()
    live = score(F.run(base))
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "strategy": "LIT (live_model.json lit)",
           "method": "tools/lit_sensitivity.py: engine/lit.py run_x via tools/lit_final.run, LIT size rule, costs in; 2026 H1 = pick, "
                     "H2 = check, 2021-25 reference (5m only)", "spans": list(SP), "live": live, "grids": []}
    for gid, title, xk, xs, yk, ys, nest in grids(quick):
        cur = (base.get(nest) or {}) if nest else base
        g = {"id": gid, "title": title, "x": {"key": xk, "values": xs, "live": cur.get(xk)},
             "y": {"key": yk, "values": ys, "live": cur.get(yk)} if yk else None, "nest": nest, "cells": []}
        for yv in (ys or [None]):
            for xv in xs:
                P = cell_params(base, xk, xv, yk, yv, nest)
                S = score(F.run(P))
                g["cells"].append({"x": xv, "y": yv, "live": xv == cur.get(xk) and (yk is None or yv == cur.get(yk)), **S})
                print(f"{gid:11s} {xk}={xv}" + (f" {yk}={yv}" if yk else "") + "  " +
                      "  ".join(f"{s} {S[s]['net']:+,} PF {S[s]['pf']}" for s in ("H1", "H2")), flush=True)
        # plateau check: the live cell's one-step neighbours, and how many beat live in both halves
        xi = xs.index(g["x"]["live"]) if g["x"]["live"] in xs else None
        yi = ys.index(g["y"]["live"]) if yk and g["y"]["live"] in ys else None
        nb = []
        for c in g["cells"]:
            dx = xs.index(c["x"]) - xi if xi is not None else 99
            dy = (ys.index(c["y"]) - yi) if (yk and yi is not None) else 0
            if max(abs(dx), abs(dy)) == 1:
                nb.append(c)
        g["neighbours"] = {"n": len(nb), "profitable_both": sum(1 for c in nb if c["H1"]["net"] > 0 and c["H2"]["net"] > 0),
                           "beat_live_both": sum(1 for c in nb if c["H1"]["net"] > live["H1"]["net"] and c["H2"]["net"] > live["H2"]["net"]),
                           "h2_min": min((c["H2"]["net"] for c in nb), default=None), "h2_max": max((c["H2"]["net"] for c in nb), default=None)}
        out["grids"].append(g)
    out["seconds"] = round(time.time() - t0)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    out = build(a.quick)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    for g in out["grids"]:
        nb = g["neighbours"]
        print(f"{g['id']}: {nb['n']} neighbours of the live cell, {nb['profitable_both']} profitable in both halves, "
              f"{nb['beat_live_both']} beat live in both; H2 {nb['h2_min']:+,} .. {nb['h2_max']:+,}" if nb["n"] else g["id"])
    print("->", os.path.relpath(OUT, ROOT), f"({out['seconds']} s)")


if __name__ == "__main__":
    main()
