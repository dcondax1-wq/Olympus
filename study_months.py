"""Month-by-month critique: where did the money come from and go, and what did the market look like in losing months?"""
from collections import defaultdict

import numpy as np

from engine import backtest

FLAT = {"dd_aware": False, "daily_max_loss": 1e9}

if __name__ == "__main__":
    rows = []
    for sym in ("NQ", "NQX"):
        r = backtest.run(sym, "5m", FLAT, light=True)
        bym = defaultdict(lambda: {"tr": [], "days": []})
        for t in r["trades"]:
            bym[t["day"][:7]]["tr"].append(t)
        for d in r["days"]:
            bym[d["date"][:7]]["days"].append(d)
        for m in sorted(bym):
            tr, days = bym[m]["tr"], bym[m]["days"]
            if len(days) < 5:
                continue
            er = [d["er10"] for d in days if d.get("er10") is not None]
            closes = [d.get("balance") for d in days]
            pnl = sum(t["pnl"] for t in tr)
            wins = sum(1 for t in tr if t["pnl"] > 0)
            tgt = sum(1 for t in tr if t["exit_reason"] == "TARGET")
            stops = sum(1 for t in tr if t["exit_reason"] == "STOP")
            big = sum(1 for t in tr if t["pnl_r"] >= 2)
            rows.append((sym, m, len(days), len(tr), pnl, wins, tgt, stops, big, float(np.mean(er)) if er else float("nan"),
                         sum(1 for d in days if d.get("regime") == "trending")))
    print(f"{'data':4s} {'month':7s} {'days':>4s} {'trades':>6s} {'net $':>8s} {'win':>4s} {'tgt':>4s} {'stop':>4s} {'2R+':>4s} {'er10':>5s} {'trend-days':>10s}")
    for sym, m, nd, nt, pnl, w, tg, st, big, er, td in rows:
        print(f"{sym:4s} {m:7s} {nd:4d} {nt:6d} {pnl:+8.0f} {w:4d} {tg:4d} {st:4d} {big:4d} {er:5.2f} {td:10d}")
