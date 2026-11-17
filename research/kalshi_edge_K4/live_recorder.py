#!/usr/bin/env python3
"""K4 live check (GET only, no key, no order): record, every ~3 s with OUR clock, the Polymarket midpoint and the Kalshi
yes bid/ask of the current 15-minute BTC / ETH up/down windows. Used to (1) learn what a Polymarket prices-history stamp
means (compare the history fetched afterwards with what we saw live) and (2) measure the REAL-TIME lead / lag between the
venues (does a Polymarket move predict Kalshi's next move?).
    python research/kalshi_edge_K4/live_recorder.py MINUTES   -> data/live_<start>.json
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import CLOB, GAMMA, KAL, get  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
COINS = {"BTC": "btc", "ETH": "eth"}


def current(coin):
    now = int(time.time())
    op = now - now % 900
    e = get(GAMMA + "/events", {"slug": "%s-updown-15m-%d" % (COINS[coin], op)}, cache=False)
    tok = json.loads(e[0]["markets"][0]["clobTokenIds"])[0] if e else None
    d = get(KAL + "/markets", {"series_ticker": "KX%s15M" % coin, "status": "open", "limit": 20}, cache=False)
    ms = sorted((d or {}).get("markets", []), key=lambda m: m["close_time"])
    tk = ms[0]["ticker"] if ms else None
    return op, tok, tk


def main():
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 20
    end = time.time() + minutes * 60
    rec = []
    cur = {}
    while time.time() < end:
        for coin in COINS:
            now = time.time()
            if coin not in cur or now >= cur[coin][0] + 900:
                cur[coin] = current(coin)
            op, tok, tk = cur[coin]
            t0 = time.time()
            mid = get(CLOB + "/midpoint", {"token_id": tok}, gap=0.05, cache=False) if tok else None
            km = get(KAL + "/markets/" + tk, gap=0.05, cache=False) if tk else None
            t1 = time.time()
            m = (km or {}).get("market", {})
            rec.append({"coin": coin, "t": (t0 + t1) / 2, "op": op, "tok": tok, "tk": tk,
                        "pm": float(mid["mid"]) if mid and mid.get("mid") else None,
                        "kb": float(m["yes_bid_dollars"]) if m.get("yes_bid_dollars") else None,
                        "ka": float(m["yes_ask_dollars"]) if m.get("yes_ask_dollars") else None})
        if len(rec) % 40 == 0:  # save as we go (a restart must not lose the run)
            save(rec)
        time.sleep(max(0, 3 - (time.time() - t0)))
    print("saved", save(rec), len(rec))


def save(rec):
    fn = os.path.join(HERE, "data", "live_%d.json" % int(rec[0]["t"]))
    with open(fn + ".part", "w") as f:
        json.dump(rec, f)
    os.replace(fn + ".part", fn)
    return fn


if __name__ == "__main__":
    main()
