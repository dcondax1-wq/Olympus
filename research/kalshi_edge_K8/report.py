#!/usr/bin/env python3
"""Markdown tables for the write-up, from research/kalshi_edge_K8/results.json (run study.py first)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))


def pct(x, d=0):
    return "n/a" if x is None else ("%+." + str(d) + "f%%") % (100 * x)


def main():
    R = json.load(open(os.path.join(HERE, "results.json")))
    print("| Leg | Train: bets, won, paid, per $1 | **Test: bets, won, paid** | **Test per $1 (95% range)** | Test avg win / loss | Worst streak | Bets/mo | $/mo at $15 |")
    print("|---|---|---|---|---|---|---|---|")
    for k, v in R["legs"].items():
        tr, te = v["tape"]["train"], v["tape"]["test"]
        src = "tape"
        if not te.get("n") and v["m1"]["test"].get("n"):
            tr, te, src = v["m1"]["train"], v["m1"]["test"], "m1"
        if not tr.get("n") and not te.get("n"):
            continue
        trs = ("%d, %.0f%%, %.2f, %s" % (tr["n"], 100 * tr["win_rate"], tr["avg_price"], pct(tr["net_per_$1"]))) if tr.get("n") else "none"
        if te.get("n"):
            ci = te.get("ci95_net_per_$1")
            print("| %s%s | %s | %d, %.0f%%, %.2f | **%s** (%s) | %+.2f / %+.2f | %d | %.0f | %+.0f |" % (
                v["label"], "" if src == "tape" else " (m1)", trs, te["n"], 100 * te["win_rate"], te["avg_price"],
                pct(te["net_per_$1"]), ("%s to %s" % (pct(ci[0]), pct(ci[1]))) if ci else "n/a",
                te["avg_win_$"], te["avg_loss_$"], te["worst_streak"], te["trades_per_month"], te["usd_per_month"]))
        else:
            print("| %s | %s | none | | | | | |" % (v["label"], trs))
    print()
    print("Same legs, entry at the 60-second quote (m1):")
    print("| Leg | Train per $1 (n) | Test per $1 (n) |")
    print("|---|---|---|")
    for k, v in R["legs"].items():
        tr, te = v["m1"]["train"], v["m1"]["test"]
        if tr.get("n") or te.get("n"):
            print("| %s | %s (%s) | %s (%s) |" % (v["label"], pct(tr.get("net_per_$1")), tr.get("n", 0), pct(te.get("net_per_$1")), te.get("n", 0)))
    print()
    print("Month by month (60-s quote): what our side cost vs how often it won")
    for k, v in R["legs"].items():
        if "by_month" in v:
            print("- %s: %s" % (v["label"], "; ".join("%s: %d bets, paid %.2f, won %.0f%%, %s" % (mo, x["n"], x["paid"], 100 * x["won"], pct(x["net_per_$1"]))
                                                    for mo, x in v["by_month"].items())))
    print()
    print("Filters picked on train (tape entry):")
    for k, v in R["legs"].items():
        if "filters" in v:
            f = v["filter_picked_on_train"]
            t = v["filters"][f]["test"]
            n = v["filters"]["none"]["test"]
            print("- %s: picked `%s` -> test %s on %s bets (no filter: %s on %s)" % (v["label"], f, pct(t.get("net_per_$1")), t.get("n"),
                                                                            pct(n.get("net_per_$1")), n.get("n")))
    print()
    c = R.get("candidate")
    if c:
        print("Candidate legs:", c["legs"])
        for p in ("train", "test"):
            s = c[p]
            print("- %s: %d bets, won %.0f%%, per $1 %s (95%% %s), worst streak %d, max drawdown $%.0f, %.0f bets/mo, $%+.0f/mo at $15" % (
                p, s["n"], 100 * s["win_rate"], pct(s["net_per_$1"]), s.get("ci95_net_per_$1"), s["worst_streak"], s["max_dd_$"],
                s["trades_per_month"], s["usd_per_month"]))
        for stake in (10, 20):
            s = c.get("test_at_$%d" % stake)
            if s:
                print("- test at $%d a bet: $%+.0f/mo" % (stake, s["usd_per_month"]))
    m = R.get("mined_control")
    if m:
        print()
        print("Mined control (|z|>=%.1f on train outcomes):" % m["zbar"])
        for p in m["picks"]:
            t = p["test"]
            print("- %s %s %s train z %+.1f: test %s bets, %s" % (p["series"], p["window_close_ET"], p["side"], p["train_z"], t.get("n"), pct(t.get("net_per_$1"))))
        t = m["pooled_test"]
        print("- pooled: %s bets, won %.0f%%, %s" % (t.get("n"), 100 * (t.get("win_rate") or 0), pct(t.get("net_per_$1"))))


if __name__ == "__main__":
    main()
