"""(A) ATLAS fill realism (research/batch5/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/batch5/fills.py -> research/batch5/fills.json
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
OUT = os.path.join(HERE, "fills.json")
TICK, PV, COMM = 0.25, 2.0, 1.90
SPANS = {"2021-25": ("2021-11-01", "2025-12-31"), "2026 H1": ("2026-01-01", "2026-06-30"), "2026 Jul-Oct": ("2026-07-01", "2026-10-16")}
K_ENTRY = (0, 2, 4, 6, 8, 10, 12)
K_EXIT = (0, 1, 2, 4)
SLIP_EXITS = {"STOP", "stop", "BE", "cut", "T15", "FLAT", "flat", "HEDGE"}      # stop-market / market exits
MEMBER = {"EMA": "EMA", "MD": "MACD", "SR": "S/R"}


def real_fills():
    A = json.load(open(os.path.join(ROOT, "research", "second", "atlas_fills_why.json"), encoding="utf-8"))
    rows = [f for f in A["fills"] if f["bot"] == "ATLAS"]
    extra = 0
    for p in glob.glob(os.path.join(ROOT, "data", "pc_days", "*", "fills.jsonl.gz")):
        for r in (json.loads(x) for x in gzip.open(p, "rt")):
            if r.get("book") in ("atlas", "acctb") and r.get("fill_px") is not None and r.get("leg", "entry") == "entry":   # red team #25: the file has exit rows now
                extra += 1
    return rows, extra


def stats(T, ke, kx):
    """T: list of (pts per micro, risk pts, exit kind). Extra cost in points; R = net pts / risk; $ at $250 risk."""
    if not T:
        return None
    pts = np.array([t[0] for t in T]); risk = np.array([t[1] for t in T])
    slip_x = np.array([kx * TICK if t[2] in SLIP_EXITS else 0.0 for t in T])
    net = pts - ke * TICK - slip_x - COMM / PV
    R = net / risk
    usd = R * 250.0
    g, l = usd[usd > 0].sum(), -usd[usd < 0].sum()
    return {"n": len(T), "mean_r": round(float(R.mean()), 4), "pf": round(float(g / l), 3) if l else None, "net_usd_250": round(float(usd.sum()))}


def breakeven(T, kx):
    lo, hi = 0.0, 40.0
    s0 = stats(T, 0, kx)
    if s0 is None or (s0["pf"] or 0) <= 1.0:
        return 0.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if (stats(T, mid, kx)["pf"] or 0) > 1.0:
            lo = mid
        else:
            hi = mid
    return round(lo, 1)


def main():
    from tools import atlas as A, second_mix as M
    M.units()
    U = A.account_units(A.BASE)
    fills, extra = real_fills()
    meas = [f["ticks_vs_model"] for f in fills]
    res = {"made": "2026-11-26", "design": "research/batch5/DESIGN.md",
           "real_fills": [{k: f[k] for k in ("day", "member", "side", "qty", "model", "open", "fill", "ticks_vs_model")} for f in fills],
           "new_fills_in_pc_days": extra, "measured_entry_ticks_mean": round(float(np.mean(meas)), 1) if meas else None,
           "calibrated": len(meas) + extra >= 10,
           "note": "exit fills are not recorded anywhere in the cloud (the bot books its ledger at the model's prices)", "grid": {}, "breakeven_entry_ticks": {}}
    groups = {"book": U, **{MEMBER[m]: [u for u in U if u["src"] == m] for m in MEMBER}}
    for g, UU in groups.items():
        for sp, (a, z) in SPANS.items():
            T = [(float(u["pts"]), float(u["risk"]), u["exit"]) for u in UU if a <= u["day"] <= z]
            res["grid"].setdefault(g, {})[sp] = {f"{ke}|{kx}": stats(T, ke, kx) for ke in K_ENTRY for kx in K_EXIT}
            res["breakeven_entry_ticks"].setdefault(g, {})[sp] = {f"exit{kx}": breakeven(T, kx) for kx in K_EXIT}
    me = res["measured_entry_ticks_mean"] or 11.7
    ke = int(round(me / 2) * 2)
    res["at_measured"] = {g: {sp: res["grid"][g][sp].get(f"{min(12, ke)}|2") for sp in SPANS} for g in groups}
    lr = res["at_measured"]["book"]["2021-25"]
    res["verdict"] = ("long-run edge SURVIVES realistic fills" if lr and (lr["pf"] or 0) > 1.0 else
                      "long-run edge does NOT survive realistic fills (2021-25 PF <= 1 at the measured entry slippage)")
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("real ATLAS fills:", len(meas), "+", extra, "new; entry ticks", meas, "mean", me)
    for g in groups:
        print(f"{g:6s} break-even entry ticks (exit 2):", {sp: res["breakeven_entry_ticks"][g][sp]["exit2"] for sp in SPANS},
              "| at measured:", {sp: (x["pf"], x["net_usd_250"]) for sp, x in res["at_measured"][g].items()})
        print(f"{'':6s} stored (0|0):", {sp: (res['grid'][g][sp]['0|0']['pf'], res['grid'][g][sp]['0|0']['net_usd_250']) for sp in SPANS})
    print(res["verdict"])


if __name__ == "__main__":
    main()
