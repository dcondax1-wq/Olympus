#!/usr/bin/env python3
"""K3 angle 1 (live): summarise the passes in data/live_scan.jsonl.gz.
For every opportunity seen with net > 0 after fees: how many passes it was there (passes are ~10 min apart), executable size at the
top of book, dollars available (net x size), days until the money comes back, and annualised return.
Groups: me_yes_exhaustive (true arbitrage), me_no (true arbitrage, at most one YES), ladder (true arbitrage),
me_yes_not_exhaustive (NOT an arbitrage: a missing 'other' outcome; shown only as a count).
Writes data/scan_report.json.
"""
import gzip, json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk


def main():
    recs = [json.loads(l) for l in gzip.open(os.path.join(kk.DATA, "live_scan.jsonl.gz"), "rt")]
    seen = defaultdict(list)
    for i, r in enumerate(recs):
        for o in r["opps"]:
            if o["net_c"] <= 0:
                continue
            g = o["k"]
            if g == "me_yes":
                g = "me_yes_exhaustive" if o.get("exh") else "me_yes_not_exhaustive"
            key = (g, o["e"], tuple(o.get("pair") or ()))
            seen[key].append((i, o))
    groups = defaultdict(list)
    for (g, e, pair), xs in seen.items():
        o = max(xs, key=lambda x: x[1]["net_c"] * x[1]["size"])[1]
        days = o.get("days")
        cost = o["cost_c"]
        groups[g].append({"e": e, "pair": list(pair), "passes": len(xs), "of": len(recs), "first": xs[0][0], "last": xs[-1][0],
                          "net_c": o["net_c"], "cost_c": cost, "size": o["size"], "usd_avail": round(o["net_c"] * o["size"] / 100, 2),
                          "capital_usd": round(cost * o["size"] / 100, 2), "days": days,
                          "ann_ret": round(o["net_c"] / cost * 365 / days, 4) if days and cost else None, "cat": o.get("cat"), "s": o.get("s")})
    out = {"passes": len(recs), "first_ts": recs[0]["ts"], "last_ts": recs[-1]["ts"], "events_per_pass": [r["events"] for r in recs],
           "markets_per_pass": [r["markets"] for r in recs], "groups": {}}
    for g, xs in groups.items():
        xs.sort(key=lambda x: -x["usd_avail"])
        near = [x for x in xs if x["days"] is not None and x["days"] <= 31]
        out["groups"][g] = {"n_distinct": len(xs), "usd_avail_sum": round(sum(x["usd_avail"] for x in xs), 2),
                            "usd_avail_sum_close_within_31d": round(sum(x["usd_avail"] for x in near), 2),
                            "n_close_within_31d": len(near), "median_passes": sorted(x["passes"] for x in xs)[len(xs) // 2] if xs else 0,
                            "top": xs[:25]}
        print(g, {k: v for k, v in out["groups"][g].items() if k != "top"})
        for x in xs[:8]:
            print("   ", x)
    # sum-of-prices distribution for active mutually-exclusive events (last pass)
    last = recs[-1]
    over = [s[2] - 100 for s in last["me_sums"]]
    if over:
        over.sort()
        out["last_pass_me_sum_ask_minus_100"] = {"n": len(over), "p05": over[len(over) // 20], "median": over[len(over) // 2], "p95": over[len(over) * 19 // 20]}
        print("sum(ask)-100 over active ME events:", out["last_pass_me_sum_ask_minus_100"])
    json.dump(out, open(os.path.join(kk.DATA, "scan_report.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
