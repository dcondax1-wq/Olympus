#!/usr/bin/env python3
"""The public trade tape of the first 45 seconds of chosen 15-minute windows (where the friend's bot buys: its fills are
at 20-25 s after the window opens).  Gives a realistic entry price at ~20 s instead of the 60 s candle quote.
Output: /home/user/kalshi_cache/kmetal/ot_<SERIES>.jsonl, one row per market:
  {"t": ticker, "o": open_ts, "tr": [[seconds_after_open, taker_side, yes_price, count], ...]}
Public GET only, <=1 request/second (shared pacing file with the other K8 harvesters).

    python research/kalshi_edge_K8/harvest_open_trades.py KXGOLD15M 0530,1700,1615
"""
import json, os, sys
import kk8

OUT = "/home/user/kalshi_cache/kmetal"


def main():
    series, wins = sys.argv[1], set(sys.argv[2].split(","))
    roll_only = len(sys.argv) > 3 and sys.argv[3] == "--roll"
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import k8lib
    roll = set()
    for y, m in [(2026, 8), (2026, 9), (2026, 10), (2026, 11)]:
        roll |= set(k8lib.gsci_roll_days(y, m))
    rows = [m for m in k8lib.load_markets(series) if m["hhmm"] in wins and m["vol"] > 0 and m["date"].weekday() < 5]
    if roll_only:
        rows = [m for m in rows if m["date"] in roll]
    fn = os.path.join(OUT, "ot_%s.jsonl" % series)
    done = set()
    if os.path.exists(fn):
        done = {json.loads(l)["t"] for l in open(fn)}
    cut = kk8.ts((kk8.get("/historical/cutoff", cache=False) or {}).get("trades_created_ts", "2026-09-19T00:00:00Z"))
    todo = [m for m in rows if m["t"] not in done]
    print(series, "todo", len(todo), flush=True)
    with open(fn, "a") as out:
        for i, m in enumerate(todo):
            o = kk8.ts(m["open"])
            hist = o < cut
            tr = kk8.trades(m["t"], min_ts=o - 1, max_ts=o + 45, max_pages=3, historical=hist)
            if not tr and hist:
                tr = kk8.trades(m["t"], min_ts=o - 1, max_ts=o + 45, max_pages=3, historical=False)
            rec = []
            for x in tr:
                t = kk8.ts(x["created_time"]) + float("0." + x["created_time"][20:26].rstrip("Z") or "0") - o
                yp = x.get("yes_price_dollars")
                if yp is None and x.get("yes_price") is not None:
                    yp = float(x["yes_price"]) / (100.0 if float(x["yes_price"]) > 1 else 1.0)
                cnt = x.get("count_fp", x.get("count"))
                rec.append([round(t, 2), x.get("taker_side"), float(yp), float(cnt)])
            out.write(json.dumps({"t": m["t"], "o": o, "tr": sorted(rec)}) + "\n")
            if i % 25 == 0:
                out.flush()
                print(series, i, "/", len(todo), kk8.STATS, flush=True)
    print(series, "done", kk8.STATS, flush=True)


if __name__ == "__main__":
    main()
