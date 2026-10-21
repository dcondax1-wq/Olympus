"""Monthly out-of-sample scoreboard + anchored walk-forward of the live LIT (competitor-features #13, 2026-10-21).

Per month of 2026: the backtest of the live config (run lit_live, LIT size rule: $, PF, trades, win %), the eval-path $ (run
lit_adopt_t15_be_off_eval, two_week sizing), and an anchored walk-forward: on months Jan..k pick the best point of a small
grid around the live knobs (15-minute check time / cut, breakeven offset, displacement, sweep depth, VIX-band width,
minimum R:R: 3 values each = 729 points), trade month k+1 with it. The H1 / H2 check becomes 9 small checks. The paper and
PC months are added at build time (engine/perf.py months()) from the cloud ledger and the PC's trades.
The walk-forward of tools/lit_batch3b.py (3-month rolling pick, on the combo grid) is quoted next to it as a reference.

  python -X utf8 tools/lit_walkforward.py      # ~2 min: one 2026 window (tools/lit_robust.Win) + 729 replays of run_x
-> research/lab/walkforward.json. Read-only research: nothing in live_model.json changes.
"""
from __future__ import annotations

import collections
import datetime as dt
import itertools
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "lab", "walkforward.json")
VERSION = 1
GRID = {"t_at": [10, 15, 20], "be_off": [0.75, 1.25, 1.75], "disp": [0.7, 0.8, 0.9], "depth": [0.4, 0.5, 0.6],
        "vix_k": [0.8, 1.0, 1.2], "min_rr": [1.25, 1.5, 2.0]}
MONTHS = [f"2026-{m:02d}" for m in range(1, 11)]


def opts(p, P):
    o = {k: v for k, v in p.items() if k != "t_at"}
    o["t_check"] = {**(P.get("t_check") or {"x": 0.3, "mfe": 0.5}), "at": p["t_at"]}
    return o


def month_stats(T):
    M = collections.defaultdict(list)
    for t in T:
        M[t["day"][:7]].append(float(t["pnl"]))
    out = {}
    for m in MONTHS:
        p = np.array(M.get(m) or [])
        gl = -p[p < 0].sum()
        out[m] = {"n": int(len(p)), "net": round(float(p.sum())), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
                  "win": round(100.0 * float((p > 0).mean()), 1) if len(p) else None}
    return out


def run_months(rid):
    try:
        r = json.load(open(os.path.join(ROOT, "research", "runs", rid + ".json"), encoding="utf-8"))
    except OSError:
        return None
    c = r["trade_cols"]
    return month_stats([dict(zip(c, x)) for x in r["trades"] if x[0] >= "2026-01-01"])


def main():
    from tools.lit_robust import Win, live_params
    t0 = time.time()
    P = live_params()
    W = Win(P)
    keys = list(GRID)
    live_p = {"t_at": P["t_check"]["at"], "be_off": P["be_off"], "disp": P["disp"], "depth": P["depth"], "vix_k": P["vix_k"],
              "min_rr": P["min_rr"]}
    pts = [dict(zip(keys, v)) for v in itertools.product(*[GRID[k] for k in keys])]
    rows = []
    for n, p in enumerate(pts):
        T = W.run(opts(p, P))
        rows.append({"p": p, "m": {m: v["net"] for m, v in month_stats(T).items()}})
        if n % 200 == 0:
            print(f"  {n}/{len(pts)} {time.time() - t0:.0f}s", flush=True)
    live = next(r for r in rows if r["p"] == live_p)
    seq = []
    for k in range(1, len(MONTHS)):
        tr, nx = MONTHS[:k], MONTHS[k]
        best = max(rows, key=lambda r: (sum(r["m"][m] for m in tr), r["p"] == live_p))
        seq.append({"month": nx, "train": f"{tr[0]}..{tr[-1]}", "pick": best["p"], "pick_is_live": best["p"] == live_p,
                    "train_net": sum(best["m"][m] for m in tr), "wf": best["m"][nx], "live": live["m"][nx]})
    wf_sum, live_sum = sum(x["wf"] for x in seq), sum(x["live"] for x in seq)
    # each month's rank of the live point in the grid (1 = best of 729): how often is the fixed pick near the top?
    ranks = {m: 1 + sum(1 for r in rows if r["m"][m] > live["m"][m]) for m in MONTHS}
    b3 = None
    try:
        S = json.load(open(os.path.join(ROOT, "research", "lit", "batch3b.json"), encoding="utf-8"))["stable"]["walk_forward"]
        b3 = {v: {"wf": S[v]["wf"], "fixed": S[v]["fixed"], "live": S[v]["live"], "from": S[v]["months"][0]["month"],
                  "to": S[v]["months"][-1]["month"]} for v in ("lit", "eval")}
    except Exception:
        pass
    out = {"v": VERSION, "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "seconds": round(time.time() - t0),
           "grid": GRID, "n_points": len(rows), "live_point": live_p,
           "months": MONTHS, "backtest": run_months("lit_live"), "eval_path": run_months("lit_adopt_t15_be_off_eval"),
           "walk_forward": {"months": seq, "wf": wf_sum, "live": live_sum,
                            "beats_live": sum(1 for x in seq if x["wf"] > x["live"]),
                            "picked_live": sum(1 for x in seq if x["pick_is_live"])},
           "live_rank": ranks, "batch3b": b3,
           "expect": {"h1_per_month": 5560, "h2_per_month": 2556, "note": "run lit_live LIT size rule: H1 (picked) $5,560/mo, H2 (check) $2,556/mo"},
           "method": ("Anchored walk-forward on 2026: for month k+1 the grid point with the best $ over Jan..k (LIT size rule) "
                      "trades month k+1. Grid: 15-minute check at 10 / 15 / 20 min, breakeven offset 0.75 / 1.25 / 1.75 pts, "
                      "displacement 0.7 / 0.8 / 0.9 ATR, sweep depth 0.4 / 0.5 / 0.6 ATR, VIX band 0.8 / 1.0 / 1.2 x, minimum "
                      "R:R 1.25 / 1.5 / 2.0. Ties go to the live point.")}
    out["text"] = (f"Walk-forward Feb-Oct 2026 (re-pick every month on all months before): {wf_sum:+,} vs the fixed live config "
                   f"{live_sum:+,}; re-picking beat the fixed config in {out['walk_forward']['beats_live']} of {len(seq)} months "
                   f"and picked the live point itself {out['walk_forward']['picked_live']} times.")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    print(out["text"])
    print(f"-> {OUT} ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
