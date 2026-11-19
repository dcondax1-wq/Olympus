#!/usr/bin/env python3
"""Pull the full market list (settled + archived) of Kalshi commodity series: open/close times, the reference price
("floor_strike" = the Pyth price at the window start), the settlement value (Pyth price at the close) and the result.
Writes /home/user/kalshi_cache/kmetal/mk_<SERIES>.jsonl (one compact row per market).  Public GET only, <=1 req/s.

    python research/kalshi_edge_K8/harvest_markets.py KXGOLD15M KXSILVER15M ...
"""
import json, os, sys
import kk8

OUT = "/home/user/kalshi_cache/kmetal"
KEEP = ("ticker", "event_ticker", "open_time", "close_time", "floor_strike", "cap_strike", "strike_type", "expiration_value",
        "result", "volume_fp", "open_interest_fp", "settlement_ts", "status", "yes_sub_title")


def compact(m):
    r = {k: m.get(k) for k in KEEP}
    return r


def harvest(series):
    rows = {}
    for hist in (False, True):
        for status in (["settled"] if not hist else [None]):
            for m in kk8.markets(series, status=status, historical=hist):
                rows[m["ticker"]] = compact(m)
    # also markets that are closed but not yet settled / finalized
    for m in kk8.markets(series, status="closed"):
        rows.setdefault(m["ticker"], compact(m))
    fn = os.path.join(OUT, "mk_%s.jsonl" % series)
    with open(fn, "w") as fh:
        for t in sorted(rows, key=lambda t: rows[t]["close_time"] or ""):
            fh.write(json.dumps(rows[t]) + "\n")
    ct = sorted(r["close_time"] for r in rows.values() if r["close_time"])
    print(series, len(rows), ct[0] if ct else None, ct[-1] if ct else None, kk8.STATS, flush=True)


if __name__ == "__main__":
    for s in sys.argv[1:]:
        harvest(s)
