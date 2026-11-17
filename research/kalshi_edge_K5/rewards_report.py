#!/usr/bin/env python3
"""K5: makers-as-a-group P&L per $ filled, with and without the reward pool, per series, train/test split by close date,
95% cluster bootstrap over events. Reads data/maker_<series>.json (maker_fills.py). Writes results_rewards.json."""
import glob, json, os, random, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
TAG = sys.argv[1] if len(sys.argv) > 1 else "_sep"   # "_sep" = markets closing from 2026-09-01 (the big-pool regime)
SPLIT = dt.datetime.fromisoformat((sys.argv[2] if len(sys.argv) > 2 else "2026-10-15") + "T00:00:00+00:00").timestamp()

def boot(rows, key, n=2000, seed=3):
    by = {}
    for r in rows:
        by.setdefault(r["t"].rsplit("-", 1)[0], []).append(r)
    g = [(sum(key(r) for r in v), sum(r["cost"] for r in v)) for v in by.values()]
    if not g or sum(c for _, c in g) <= 0:
        return None
    m = sum(a for a, _ in g) / sum(c for _, c in g)
    rnd = random.Random(seed); k = len(g); ms = []
    for _ in range(n):
        a = c = 0.0
        for _ in range(k):
            x, y = g[rnd.randrange(k)]; a += x; c += y
        ms.append(a / c if c else 0)
    ms.sort()
    return {"edge": m, "lo": ms[int(.025 * n)], "hi": ms[int(.975 * n)], "events": k, "markets": len(rows),
            "filled_usd": sum(r["cost"] for r in rows), "pool_usd": sum(r["pool"] for r in rows)}

out = {}
for fn in sorted(glob.glob(os.path.join(HERE, "data", "maker_*%s.json" % TAG))):
    s = os.path.basename(fn)[6:-5 - len(TAG)]
    rows = [r for r in json.load(open(fn)) if r["cost"] > 0]
    out[s] = {}
    for half, rs in (("train", [r for r in rows if r["close"] < SPLIT]), ("test", [r for r in rows if r["close"] >= SPLIT])):
        out[s][half] = {"fills_only": boot(rs, lambda r: r["pnl"]), "with_pool": boot(rs, lambda r: r["pnl"] + r["pool"])}
json.dump(out, open(os.path.join(HERE, "results_rewards%s.json" % TAG), "w"), indent=1)
f = lambda x: "%+6.1f%% [%+6.1f,%+6.1f]" % (100 * x["edge"], 100 * x["lo"], 100 * x["hi"]) if x else "      n/a"
print("%-18s %-5s %4s %4s %10s %8s  %-26s %-26s" % ("series", "half", "mkts", "evs", "filled$", "pool$", "fills only", "fills + pool"))
for s, v in out.items():
    for half in ("train", "test"):
        a, b = v[half]["fills_only"], v[half]["with_pool"]
        if a:
            print("%-18s %-5s %4d %4d %10.0f %8.0f  %-26s %-26s" % (s, half, a["markets"], a["events"], a["filled_usd"], a["pool_usd"], f(a), f(b)))

# ---- per-order estimate: a new order of Target/5 contracts a side at the reference price (rewards_repeat.py snapshots)
# reward/day = share x pool/day x valid share; fills/day = share x the series' filled $ per market-day (test half);
# fill P&L = that x the test-half maker loss rate. Sensitivity: fills at 2x the share (resting behind the best price is
# filled mostly on the big moves).
from harvest import listing  # noqa: E402
rp = os.path.join(HERE, "data", "rewards_repeat.json")
if os.path.exists(rp):
    rep = json.load(open(rp)); agg = {}
    for t, v in rep.items():
        for o in v:
            agg.setdefault(o["s"], []).append(o)
    est = {}
    print("\nper new order (~$185 capital, Target/5 contracts a side at the reference price), test-half fill rates")
    print("%-20s %8s %9s %10s %9s %9s %10s %8s" % ("series", "share", "reward$/d", "fills$/d", "loss%", "net$/d", "net 2xfill", "per$1/d"))
    for s, v in agg.items():
        if s not in out or not out[s]["test"]["fills_only"]:
            continue
        life = {r["t"]: max((r["close"] - r["open"]) / 86400, 0.5) for r in listing(s)}
        rows = [r for r in json.load(open(os.path.join(HERE, "data", "maker_%s%s.json" % (s, TAG)))) if r["close"] >= SPLIT and r["cost"] > 0]
        fpd = sum(r["cost"] for r in rows) / sum(life.get(r["t"], 7) for r in rows)
        sh = sum(o["share"] for o in v) / len(v); rew = sum(o["pool_day"] * o["share"] * o["valid"] for o in v) / len(v)
        cap = sum(o["cap"] for o in v) / len(v); loss = out[s]["test"]["fills_only"]
        net = rew + sh * fpd * loss["edge"]; net2 = rew + 2 * sh * fpd * loss["edge"]
        lo = rew + sh * fpd * loss["lo"]; hi = rew + sh * fpd * loss["hi"]
        est[s] = {"share": sh, "reward_day": rew, "fills_day": sh * fpd, "loss_rate": loss, "net_day": net, "net_day_lo": lo,
                  "net_day_hi": hi, "net_day_2xfills": net2, "capital": cap, "net_per_dollar_day": net / cap}
        print("%-20s %7.1f%% %9.2f %10.0f %+8.1f%% %+9.2f %+10.2f %+7.2f%%" % (s, 100 * sh, rew, sh * fpd, 100 * loss["edge"], net, net2, 100 * net / cap))
    json.dump(est, open(os.path.join(HERE, "results_rewards_order.json"), "w"), indent=1)
