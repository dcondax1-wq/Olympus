"""Probe: trade fields, and whether regime_mode='none' (full size) gives the same trade list as the default half-size rule."""
from engine import backtest

F = {"dd_aware": False, "daily_max_loss": 1e9}
if __name__ == "__main__":
    for sym in ("NQ", "NQX"):
        a = backtest.run(sym, "5m", F, light=True)
        b = backtest.run(sym, "5m", {**F, "regime_mode": "none"}, light=True)
        t = a["trades"][0]
        if sym == "NQ":
            print(sorted(t.keys()))
            print({k: v for k, v in t["features"].items() if k.startswith("rg_")})
            print(a["days"][0].keys())
        print(sym, len(a["trades"]), len(b["trades"]), [x["entry_t"] for x in a["trades"]] == [x["entry_t"] for x in b["trades"]])
        ra, rb = a["trades"], b["trades"]
        if len(ra) == len(rb):
            diff = [(x["day"], x["pnl"], y["pnl"], x.get("regime"), x["features"].get("rg_er10"), x["qty"], y["qty"])
                    for x, y in zip(ra, rb) if abs(x["pnl"] - y["pnl"]) > 1]
            print(len(diff), sum(1 for x in ra if x.get("regime") == "trending"), diff[:6])
            bad = [(x["day"], x["pnl"], y["pnl"] * 0.5, x["qty"], y["qty"]) for x, y in zip(ra, rb)
                   if x.get("regime") == "trending" and abs(x["pnl"] - 0.5 * y["pnl"]) > 0.15 * abs(y["pnl"]) + 5]
            print("approx errs", len(bad), bad[:5])
        print(a["days"][0]["date"], a["days"][-1]["date"], len(a["days"]))
        print(sorted(set(d["date"][:7] for d in a["days"])))
