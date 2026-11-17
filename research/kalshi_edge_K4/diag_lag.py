"""K4 diagnostic: is Polymarket's price-history print aligned with Kalshi's minute quote? Mean |poly - kalshi mid| when
the Kalshi quote is taken k minutes later (k > 0) or earlier (k < 0) than the poly print; and which venue forecasts
better 5 minutes before the close (Brier score against each venue's own result)."""
import statistics

from crypto_xvenue import load, pm_at, quotes

for coin in ("BTC", "ETH", "SOL", "XRP"):
    gaps = {k: [] for k in range(-3, 4)}
    brier = {"kalshi": [], "poly": []}
    for r in load(coin):
        q = quotes(r)
        pm = sorted(r.get("pm") or [])
        if not pm or r.get("pm_res") is None:
            continue
        y = 1.0 if r["res"] == "yes" else 0.0
        yp = 1.0 if r["pm_res"] == "yes" else 0.0
        for m in range(4, 12):
            pu = pm_at(pm, r["close"] - m * 60)
            if pu is None:
                continue
            for k in gaps:
                if (m - k) in q:
                    b, a = q[m - k]
                    gaps[k].append(abs(pu - (a + b) / 2))
            if m == 5 and m in q:
                brier["kalshi"].append(((q[m][0] + q[m][1]) / 2 - y) ** 2)
                brier["poly"].append((pu - yp) ** 2)
    print(coin, "mean |poly - kalshi mid| by Kalshi offset (min):", {k: round(statistics.mean(v), 4) for k, v in gaps.items()},
          "| Brier 5 min out:", {k: round(statistics.mean(v), 4) for k, v in brier.items()}, "n", len(brier["poly"]))
