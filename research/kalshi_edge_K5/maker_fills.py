#!/usr/bin/env python3
"""K5 rewards vs adverse selection, measured on settled history (public trade tape, GET only).
For every settled market of a series that had a paid liquidity-incentive program: all public trades. Each trade has a
maker on the other side: taker bought YES at p -> maker bought NO at 1-p. Maker P&L per contract = payout - price - maker
fee (0.0175 x p x (1-p), Kalshi's maker rate where charged; charged here everywhere = conservative).
Makers as a group earn: fill P&L + the reward pool. If that is negative per $ of fills, resting for rewards loses.
    python research/kalshi_edge_K5/maker_fills.py SERIES[,SERIES] [max_markets_per_series] [first close YYYY-MM-DD] [file tag]
Writes data/maker_<series>.json (per-market totals, no raw tape)."""
import datetime as dt, gzip, json, os, sys, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import net  # noqa: E402
from harvest import listing  # noqa: E402
HERE = os.path.dirname(os.path.abspath(__file__))
CUT = dt.datetime.fromisoformat(net.get(net.KAL + "/historical/cutoff", cache=False)["trades_created_ts"].replace("Z", "+00:00")).timestamp()
progs = json.load(open(os.path.join(HERE, "data", "raw", "incentive_programs.json")))
pool = collections.defaultdict(float)
for x in progs:
    if x["incentive_type"] == "liquidity" and x["paid_out"]:
        pool[x["market_ticker"]] += x["period_reward"] / 1e4

def trades(t, hist):
    out, cur = [], None
    for _ in range(300):
        p = {"ticker": t, "limit": 1000}
        if cur: p["cursor"] = cur
        d = net.get(net.KAL + ("/historical" if hist else "/markets") + "/trades", p, gap=0.25)
        if not d: break
        out += d.get("trades", [])
        cur = d.get("cursor")
        if not cur or not d.get("trades"): break
    return out

def main():
    mx = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    since = dt.datetime.fromisoformat((sys.argv[3] if len(sys.argv) > 3 else "2020-01-01") + "T00:00:00+00:00").timestamp()
    tag = sys.argv[4] if len(sys.argv) > 4 else ""
    for s in sys.argv[1].split(","):
        fn = os.path.join(HERE, "data", "raw", s + "_list.json.gz")
        rows = json.load(gzip.open(fn, "rt")) if os.path.exists(fn) else listing(s)
        rows = [r for r in rows if r["t"] in pool and (r["vol"] or 0) > 0 and r["close"] >= since]
        random.Random(11).shuffle(rows)
        rows = rows[:mx]
        res = []
        for r in rows:
            tr = trades(r["t"], r["close"] < CUT)
            pnl = cost = cnt = 0.0
            late = collections.Counter()
            for x in tr:
                c = float(x["count_fp"]); py = float(x["yes_price_dollars"])
                # maker holds the opposite side of the taker
                mp = (1 - py) if x["taker_side"] == "yes" else py
                win = (r["res"] == "no") if x["taker_side"] == "yes" else (r["res"] == "yes")
                fee = 0.0175 * mp * (1 - mp)
                pnl += c * ((1.0 if win else 0.0) - mp - fee); cost += c * (mp + fee); cnt += c
            res.append({"t": r["t"], "close": r["close"], "pool": pool[r["t"]], "fills": cnt, "cost": cost, "pnl": pnl, "ntr": len(tr)})
        json.dump(res, open(os.path.join(HERE, "data", "maker_%s%s.json" % (s, tag)), "w"))
        P = sum(x["pool"] for x in res); F = sum(x["pnl"] for x in res); C = sum(x["cost"] for x in res)
        print("%-20s markets %4d  pool $%9.0f  maker fill P&L $%10.0f on $%11.0f filled (%.1f%%)  net incl. pool %.2f%%" %
              (s, len(res), P, F, C, 100 * F / max(C, 1), 100 * (F + P) / max(C, 1)), flush=True)

if __name__ == "__main__":
    main()
