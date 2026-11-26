"""STRATEGY HEALTH BANDS (research/batch5/DESIGN.md part C). PAPER RESEARCH ONLY: reads trades, changes nothing.

    python -X utf8 tools/health_bands.py     # -> research/health/bands.json (+ a table); nightly-safe (seconds)

bands.json shape (the dashboard plots live against it daily):
  {"made", "window": 20, "bots": {"LIT"|"ATLAS"|"BLITZ": {
      "bands": {"2026": {"p5", "p50", "p95", "n_windows", "trades"}, "2021-25": {...}},     # rolling 20-trade mean R
      "live": {"n", "mean_r", "trades": [{"day", "r", "usd"}], "pct_in_2026", "pct_in_2021_25", "zone"}}}}
  zone = "too few" (< 5 live trades) | "below the 5% band" | "inside" | "above the 95% band" (judged on the 2026 band).
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "health", "bands.json")
W = 20
POOLS = {"2026": ("2026-01-01", "2026-12-31"), "2021-25": ("2021-11-01", "2025-12-31")}


def backtest_r():
    from tools import stops_targets_time as STT
    from tools import atlas as A, second_mix as M
    L = STT.size_matched(STT.units())
    lit = [(l["day"], l["entry_t"], l["pnl"] / (l["risk0"] * 2.0 * max(1, l["qty"]))) for l in L]
    M.units()
    at = [(u["day"], u["entry_t"], (float(u["pts"]) - 0.95) / float(u["risk"])) for u in A.account_units(A.BASE)]
    rows = [json.loads(x) for x in gzip.open(os.path.join(ROOT, "research", "learn", "lessons.jsonl.gz"), "rt", encoding="utf-8")]
    bl = [(r["day"], r["entry_t"], float(r["r"])) for r in rows if r.get("pillar") == "blitz" and r.get("r") is not None]
    return {"LIT": sorted(lit, key=lambda x: x[1]), "ATLAS": sorted(at, key=lambda x: x[1]), "BLITZ": sorted(bl, key=lambda x: x[1])}


def band(rs):
    if len(rs) < W + 1:
        return None
    x = np.convolve(np.asarray(rs, float), np.ones(W) / W, mode="valid")
    return {"p5": round(float(np.percentile(x, 5)), 3), "p50": round(float(np.percentile(x, 50)), 3),
            "p95": round(float(np.percentile(x, 95)), 3), "n_windows": int(len(x)), "trades": len(rs), "_x": x}


def live_trades():
    """Closed live trades per bot from the PC's day folders (entry rows give the planned risk) + the cloud's trades.json."""
    out = {"LIT": {}, "ATLAS": {}, "BLITZ": {}}
    name = {"zlarior": "LIT", "atlas": "ATLAS", "blitz": "BLITZ"}
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "pc_days", "*", "trades.jsonl.gz"))):
        rows = [json.loads(x) for x in gzip.open(p, "rt")]
        ent = {(r["bot"], r["entry_t"]): r for r in rows if r.get("side") in ("buy", "sell") and r.get("mode") == "live"}
        for r in rows:
            if r.get("side") != "exit" or r.get("mode") != "live" or r.get("src", "").startswith("accounts/"):
                continue
            e = ent.get((r["bot"], r["entry_t"]))
            if not e or not e.get("stop") or not e.get("qty"):
                continue
            risk = abs(float(e["entry"]) - float(e["stop"])) * 2.0 * int(e["qty"])
            b = name.get(r["bot"])
            if b and risk > 0:
                out[b][int(r["entry_t"])] = {"day": os.path.basename(os.path.dirname(p)), "r": round(float(r["pnl"]) / risk, 3), "usd": r["pnl"]}
    try:
        T = json.load(open(os.path.join(ROOT, "tools", "web_public", "trading", "trades.json"), encoding="utf-8"))["trades"]
        for t in T:
            if t.get("src") == "live" and t.get("r") is not None:
                b = {"LIT": "LIT", "ATLAS": "ATLAS"}.get(t.get("bot"))
                if b and int(t["t"]) not in out[b]:
                    out[b][int(t["t"])] = {"day": t["day"], "r": float(t["r"]), "usd": t["usd"]}
    except (OSError, ValueError, KeyError):
        pass
    return {b: [v for _, v in sorted(d.items())] for b, d in out.items()}


def pct_of(x, val):
    return round(100.0 * float(np.mean(x <= val)), 1)


def run(say=print):
    BT = backtest_r()
    LV = live_trades()
    res = {"made": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "window": W, "bots": {}}
    for b, T in BT.items():
        bands = {p: band([r for d, _, r in T if a <= d <= z]) for p, (a, z) in POOLS.items()}
        live = LV.get(b, [])[-W:]
        lv = {"n": len(live), "trades": live}
        if live:
            m = float(np.mean([t["r"] for t in live]))
            lv["mean_r"] = round(m, 3)
            for p in POOLS:
                if bands[p]:
                    lv[f"pct_in_{p.replace('-', '_')}"] = pct_of(bands[p]["_x"], m)
            b26 = bands["2026"]
            lv["zone"] = ("too few to judge (< 5 live trades)" if len(live) < 5 else
                          "below the 5% band" if m < b26["p5"] else "above the 95% band" if m > b26["p95"] else "inside the 2026 band")
        else:
            lv["zone"] = "no live trades in the cloud"
        res["bots"][b] = {"bands": {p: {k: v for k, v in (bd or {}).items() if k != "_x"} for p, bd in bands.items()}, "live": lv}
        bd = bands["2026"]
        say(f"{b:6s} 2026 band 5/50/95 {bd['p5']} / {bd['p50']} / {bd['p95']} | 2021-25 {bands['2021-25']['p5']} / "
            f"{bands['2021-25']['p50']} / {bands['2021-25']['p95']} | live n {lv['n']} mean {lv.get('mean_r')} -> {lv['zone']}")
    # LIT's backtest twin over the live window (tools/livegap.lit_twin, the PC's own bars): its mean R vs rolling windows of
    # the SAME length (a 7-trade mean swings more than a 20-trade one)
    try:
        from tools import livegap as LG
        tw, _ = LG.lit_twin(since="2026-10-12")
        tw = [t for t in tw if t["day"] >= "2026-10-19"]
        if tw:
            k = len(tw)
            m = float(np.mean([t["r"] for t in tw]))
            pc = {}
            for p, (a, z) in POOLS.items():
                rs = [r for d, _, r in BT["LIT"] if a <= d <= z]
                x = np.convolve(np.asarray(rs, float), np.ones(k) / k, mode="valid")
                pc[p] = pct_of(x, m)
            res["bots"]["LIT"]["twin_live_window"] = {"from": "2026-10-19", "to": tw[-1]["day"], "n": k, "mean_r": round(m, 3),
                                                     "pct_of_same_length_windows": pc}
            say(f"LIT twin over the live window: {k} trades, mean {m:.3f}R = percentile {pc} of same-length backtest windows")
    except Exception as ex:  # noqa: BLE001
        say(f"LIT twin skipped ({ex.__class__.__name__})")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    return res


if __name__ == "__main__":
    run()
