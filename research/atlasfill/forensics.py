"""Part 1: every real fill in the cloud vs its signal (research/atlasfill/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/atlasfill/forensics.py -> research/atlasfill/forensics.json
"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "forensics.json")
TICK = 0.25


def pc_bars(day, root="MNQ"):
    p = os.path.join(ROOT, "data", "pc_days", day, "bars", f"{root}_1m.csv.gz")
    if not os.path.exists(p):
        return {}
    R = list(csv.reader(gzip.open(p, "rt")))[1:]
    return {int(float(r[0])): tuple(map(float, r[1:6])) for r in R}


def fills():
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "pc_days", "*", "trades.jsonl.gz"))):
        day = os.path.basename(os.path.dirname(p))
        rows = [json.loads(x) for x in gzip.open(p, "rt")]
        exits = {(r["bot"], r["entry_t"]): r for r in rows if r.get("side") == "exit" and r.get("mode") == "live"}
        for r in rows:
            if r.get("side") not in ("buy", "sell") or r.get("mode") != "live":
                continue
            legs = (r.get("result") or {}).get("legs") or []
            fp = [lg.get("fill_px") for lg in legs if lg.get("fill_px")]
            if not fp:
                continue
            d = 1 if r["side"] == "buy" else -1
            fill = float(np.mean(fp))
            et_ = int(r["entry_t"])
            B = pc_bars(day)
            b = B.get(et_)
            row = {"day": day, "bot": "ATLAS" if r["bot"] == "atlas" else "LIT", "member": r.get("strategy", ""),
                   "side": r["side"], "qty": r.get("qty"), "intended": r["entry"], "filled": fill,
                   "ticks_vs_model": round((fill - float(r["entry"])) * d / TICK, 2), "latency_s": int(r["t"]) - et_,
                   "risk_pts": round(abs(float(r["entry"]) - float(r["stop"])), 2)}
            if b:
                o, h, l, c, v = b
                fav1 = (h - o) if d == 1 else (o - l)
                row.update({"mnq_open": o, "ticks_vs_open": round((fill - o) * d / TICK, 2), "fav1_pts": fav1,
                            "share_of_fav1": round((fill - o) * d / fav1, 3) if fav1 > 0 else None,
                            "first_min_close_vs_open_pts": round((c - o) * d, 2), "first_min_vol": v,
                            "prev_close_vs_open_ticks": round((o - B[et_ - 60][3]) * d / TICK, 2) if (et_ - 60) in B else None})
            x = exits.get((r["bot"], r["entry_t"]))
            if x:
                row["exit"] = {"reason": x.get("reason"), "pnl": x.get("pnl")}
                row["usd_lost_to_slip"] = round(row["ticks_vs_model"] * 0.5 * int(r.get("qty") or 1), 2)
            out.append(row)
    return out


def main():
    F = fills()
    at = [f for f in F if f["bot"] == "ATLAS"]
    lit = [f for f in F if f["bot"] == "LIT"]
    def summ(X):
        if not X:
            return None
        t = np.array([f["ticks_vs_model"] for f in X]); s = [f["share_of_fav1"] for f in X if f.get("share_of_fav1") is not None]
        return {"n": len(X), "ticks_vs_model": t.tolist(), "mean_ticks": round(float(t.mean()), 2), "median_ticks": float(np.median(t)),
                "latency_s": [f["latency_s"] for f in X], "share_of_fav1_mean": round(float(np.mean(s)), 3) if s else None,
                "share_of_fav1": s, "all_worse_in_trade_direction": bool((t > 0).all())}
    sa = summ(at)
    res = {"made": "2026-11-26", "design": "research/atlasfill/DESIGN.md", "fills": F, "atlas": sa, "lit": summ(lit),
           "split_atlas_mean_ticks": {
               "model_tick_already_in_backtest": 1.0,
               "spread_half_crossed": "inside the model's 1 tick (MNQ trades 1 tick wide)",
               "size_impact": "~0 (1-2 micros against NQ's book; the fills sit inside the first minute's range)",
               "move_during_latency": round(sa["mean_ticks"], 2) if sa else None},
           "rests_on": f"{len(at)} real ATLAS fills + {len(lit)} LIT fill(s); no tick data in the cloud (LE_TickRec not pulled), "
                       "no exit fills recorded (the ledger books exits at the model's prices)",
           "reading": ("every ATLAS fill was worse in the trade's own direction (sells filled lower); the give-away is ~a third of the "
                       "first minute's run, and bigger on faster minutes (Nov 20: 20-pt minute, 21 ticks). That is the price running "
                       "away in the 3-5 s between the 5m close and the fill (other bar-close traders + our poll at +2 s + compute), "
                       "not the order's size. LIT, entering on a 1m open after its own pattern, gave away 3 ticks (8% of its minute).")}
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    for f in F:
        print(f"{f['day']} {f['bot']:5s} {f['member']:4s} {f['side']:4s} x{f['qty']} intended {f['intended']} filled {f['filled']} "
              f"-> {f['ticks_vs_model']} ticks worse | latency {f['latency_s']} s | 1st-minute run {f.get('fav1_pts')} pts, "
              f"gave away {f.get('share_of_fav1')} of it | {f.get('exit')}")
    print("ATLAS:", {k: v for k, v in sa.items() if k != 'share_of_fav1'})
    print("LIT:", res["lit"])


if __name__ == "__main__":
    main()
