#!/usr/bin/env python3
"""Coinbase public 1-minute candles (BTC-USD, ETH-USD) as the spot proxy for BRTI. No key. -> data/spot_<SYM>.json.gz"""
import sys, os, json, gzip, time, urllib.request, datetime as dt
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)
sym, days = sys.argv[1], int(sys.argv[2])
end = int(time.time()) // 60 * 60
start = end - days * 86400
rows = {}
t = start
while t < end:
    u = "https://api.exchange.coinbase.com/products/%s-USD/candles?granularity=60&start=%s&end=%s" % (
        sym, dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        dt.datetime.fromtimestamp(min(t + 299 * 60, end), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    for k in range(5):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "research-client"}), timeout=20))
            for c in d:
                rows[c[0]] = c[1:5]  # low, high, open, close
            break
        except Exception:
            time.sleep(1 + k)
    t += 299 * 60
    time.sleep(0.12)
with gzip.open(os.path.join(OUT, "spot_%s.json.gz" % sym), "wt") as fh:
    json.dump(sorted([k] + v for k, v in rows.items()), fh)
print(sym, len(rows))
