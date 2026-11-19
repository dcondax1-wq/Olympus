#!/usr/bin/env python3
"""K7 step 5: print the writeup tables (markdown) from research/kalshi_edge_K7/results.json (the final run)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "results.json")))
FAM = {"mentions": "Mentions (what will X say)", "politics": "Politics + elections", "entertainment": "Entertainment (awards, TV, charts, RT)",
       "sci_tech_companies": "Science / tech / companies / world", "econ_fin_other": "Fed, rate cuts, yearly index, other finance",
       "climate_other": "Weather other than daily highs/lows", "sports_futures": "Sports futures (season / tournament winners)",
       "sports_props": "Sports in-game (spreads, totals, props)"}


def pct(x, d=1):
    return "n/a" if x is None else ("%+." + str(d) + "f%%") % (100 * x)


def wr(s):
    return "n/a" if not s.get("n") else "%.1f%%" % (100 * s["win_rate"])


def row(name, s, test=True):
    if not s.get("n"):
        return "| %s | 0 | | | | | | |" % name
    ci = s.get("ci95") or [None, None]
    return "| %s | %d (%d ev) | %s | %s / %s | %s (%s to %s) | %s | %s | %s |" % (
        name, s["n"], s["events"], wr(s), ("$%+.2f" % s["avg_win_usd"]) if s.get("avg_win_usd") is not None else "-",
        ("$%+.2f" % s["avg_loss_usd"]) if s.get("avg_loss_usd") is not None else "-", pct(s["net_per_1"]), pct(ci[0]), pct(ci[1]),
        s["worst_losing_streak"], ("%.0f" % s["trades_per_month_full"]) if test and s.get("trades_per_month_full") is not None else "-",
        ("$%+.0f" % s["usd_month_at_10_full"]) if test and s.get("usd_month_at_10_full") is not None else "-")


HDR = "| Rule | Trades | Win rate | Avg win / avg loss ($10 bet) | Net per $1 (95%) | Worst losing streak | Trades/month (all markets) | $/month at $10 |\n|---|---|---|---|---|---|---|---|"

print("## by family, first-touch, all bands, TEST (train in the next table)\n" + HDR)
for f in FAM:
    d = R["by_family"].get(f)
    if d:
        print(row(FAM[f], d["touch"]["test"]))
print("\n## by family, first-touch, TRAIN\n" + HDR)
for f in FAM:
    d = R["by_family"].get(f)
    if d:
        print(row(FAM[f], d["touch"]["train"], test=False))
print("\n## by band, all families, first-touch\n| Band | Train n / win / net | Test n / win / net (95%) | Test loss rate (exact 95% upper) vs break-even | worst streak |\n|---|---|---|---|---|")
for k, v in R["prereg_pooled"].items():
    if k.endswith("touch before"):
        a, t = v["train"], v["test"]
        print("| %s | %s / %s / %s | %s / %s / %s (%s to %s) | %s (%s) vs %s | %s |" % (k.split(",")[1].strip(), a.get("n"), wr(a), pct(a.get("net_per_1")),
              t.get("n"), wr(t), pct(t.get("net_per_1")), pct((t.get("ci95") or [None])[0]), pct((t.get("ci95") or [None, None])[1]),
              pct(1 - t["win_rate"]) if t.get("n") else "n/a", pct(t.get("loss_rate_upper95")), pct(t.get("breakeven_loss_rate")), t.get("worst_losing_streak")))
print("\n## clock design: by horizon, all families and bands\n| Horizon before scheduled close | Train n / win / net | Test n / win / net (95%) | Test avg days held | Test annualized (no interest) |\n|---|---|---|---|---|")
for h, v in R["by_horizon"].items():
    a, t = v["train"], v["test"]
    print("| %s | %s / %s / %s | %s / %s / %s (%s to %s) | %s | %s |" % (h, a.get("n"), wr(a), pct(a.get("net_per_1")), t.get("n"), wr(t), pct(t.get("net_per_1")),
          pct((t.get("ci95") or [None])[0]), pct((t.get("ci95") or [None, None])[1]), t.get("avg_days_held"), pct(t.get("annualized_net_no_interest"), 0)))
print("\n## pre-registered pooled (band x horizon), test\n| Rule | Train n / net | Test n / win / net (95%) | worst streak | interest adds |\n|---|---|---|---|---|")
for k, v in R["prereg_pooled"].items():
    a, t = v["train"], v["test"]
    if t.get("n"):
        print("| %s | %s / %s | %s / %s / %s (%s to %s) | %s | %s |" % (k, a.get("n"), pct(a.get("net_per_1")), t["n"], wr(t), pct(t["net_per_1"]),
              pct(t["ci95"][0]), pct(t["ci95"][1]), t["worst_losing_streak"], pct(t["net_per_1_with_interest"] - t["net_per_1"], 2)))
print("\n## carried cells (train t above the bar %.2f over %d cells)" % (R["bonferroni_bar_t"], R["eligible_train_cells"]))
for c in R["carried"]:
    print("-", c["fam"], c["band"], c["h"], "train n", c["train"]["n"], pct(c["train"]["net_per_1"]), "t", c["train"]["t"], "| test", c["test"].get("n"),
          wr(c["test"]), pct(c["test"].get("net_per_1")), c["test"].get("ci95"))
print("\n## loose cells (train t > 1.96): %d" % len(R["loose_t196_cells"]))
pos = [c for c in R["loose_t196_cells"] if c["test"].get("n") and c["test"]["net_per_1"] > 0]
print("test positive: %d of %d with test trades" % (len(pos), sum(1 for c in R["loose_t196_cells"] if c["test"].get("n"))))
for c in R["loose_t196_cells"]:
    print("-", c["fam"], c["band"], c["h"], "train n", c["train"]["n"], pct(c["train"]["net_per_1"]), "t", c["train"]["t"], "| test", c["test"].get("n"),
          wr(c["test"]) if c["test"].get("n") else "", pct(c["test"].get("net_per_1")))
print("\n## all\n", json.dumps({k: R[k] for k in ("n_trades", "markets", "all_touch", "all_clock")}, indent=0)[:3000])
