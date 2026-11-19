#!/usr/bin/env python3
"""K7 step 2: yes bid / ask candles for a seeded sample of settled markets, PUBLIC GET only (1 request a second).

Sample per series, fixed before any outcome is looked at (seed 7):
  old half = markets Kalshi already moved to /historical (closed before 2026-09-19): up to OLD_EVENTS events, about OLD_TARGET
             markets in all (at least 2, at most 12 per event; one request per market);
  new half = the live window (closed 2026-09-19 .. 2026-11-18): up to NEW_EVENTS events, every market of the event (one batch request
             per event).
Candles: markets open 7 days or less -> hourly over their last 7 days; longer -> daily over their whole life.
Stored compactly (resumable) in /home/user/kalshi_cache/knew2/candles/<SERIES>.jsonl.gz: one line per market
  {"t", "e", "half", "iv", "c": [[end_ts, yes_bid_c, yes_ask_c, volume], ...]}  (bid 0 / ask 100 = no quote -> null)
    python research/kalshi_edge_K7/harvest.py [SERIES ...]
"""
import gzip
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kapi  # noqa: E402
import universe  # noqa: E402

LISTS = os.path.join(kapi.CACHE, "lists")
OUTD = os.path.join(kapi.CACHE, "candles")
os.makedirs(OUTD, exist_ok=True)
OLD_EVENTS, OLD_PER_EVENT, OLD_TARGET, NEW_EVENTS = 15, 2, 30, 15
NEW_MAX = int(os.environ.get("K7_NEW_MAX", "40"))      # 12 was used for the last 22 series (time: the machine restarted three times)
SHORT = 7 * 86400


def q(c, side):
    v = kapi.fnum(((c.get(side) or {}).get("close_dollars")) if isinstance(c.get(side), dict) else None)
    if v is None:
        v = kapi.fnum((c.get(side) or {}).get("close")) if isinstance(c.get(side), dict) else None
    if v is None:
        return None
    x = int(round(v * 100))
    if (side == "yes_bid" and x <= 0) or (side == "yes_ask" and x >= 100):
        return None
    return x


def compact(cs):
    return [[c["end_period_ts"], q(c, "yes_bid"), q(c, "yes_ask"), kapi.fnum(c.get("volume_fp") or c.get("volume")) or 0] for c in cs]


def window(rows):
    op = min(r["open"] for r in rows)
    cl = max(r["close"] for r in rows)
    if cl - op <= SHORT:
        return 60, int(op) - 3600, int(cl) + 60
    return 1440, int(op) - 86400, int(cl) + 60


def sample(rows, seed):
    rnd = random.Random(seed)
    old = {}
    new = {}
    for r in rows:
        if not r.get("open") or not r.get("close") or r["close"] <= r["open"]:
            continue
        (old if r["hist"] else new).setdefault(r["e"], []).append(r)
    oe = sorted(old)
    ne = sorted(new)
    rnd.shuffle(oe)
    rnd.shuffle(ne)
    pick_old = []
    chosen = oe[:OLD_EVENTS]
    per = min(12, max(OLD_PER_EVENT, -(-OLD_TARGET // max(1, len(chosen)))))   # few events -> more markets from each
    for e in chosen:
        ms = sorted(old[e], key=lambda r: r["t"])
        rnd.shuffle(ms)
        pick_old.append((e, ms[:per]))
    pick_new = []
    for e in ne[:NEW_EVENTS]:
        ms = sorted(new[e], key=lambda r: r["t"])
        rnd.shuffle(ms)
        pick_new.append((e, ms[:NEW_MAX]))
    return pick_old, pick_new


def run(series):
    fn = os.path.join(LISTS, series + ".json.gz")
    if not os.path.exists(fn):
        return 0
    with gzip.open(fn, "rt") as fh:
        rows = json.load(fh)
    out = os.path.join(OUTD, series + ".jsonl.gz")
    done = set()
    if os.path.exists(out):
        good, broken = [], False
        try:
            with gzip.open(out, "rt") as fh:
                for line in fh:
                    try:
                        done.add(json.loads(line)["t"])
                        good.append(line)
                    except Exception:
                        broken = True
        except Exception:         # a crash mid-write: keep what was read, rewrite the file clean
            broken = True
        if broken:
            with gzip.open(out + ".tmp", "wt") as fo:
                fo.writelines(good)
            os.replace(out + ".tmp", out)
    pick_old, pick_new = sample(rows, 7)
    n = 0
    with gzip.open(out, "at") as fo:
        for e, ms in pick_old:
            for r in ms:
                if r["t"] in done:
                    continue
                iv, a, b = window([r])
                d = kapi.get("/historical/markets/%s/candlesticks" % r["t"], {"start_ts": a, "end_ts": b, "period_interval": iv}, cache=False)
                cs = compact((d or {}).get("candlesticks") or [])
                fo.write(json.dumps({"t": r["t"], "e": e, "half": "old", "iv": iv, "c": cs}) + "\n")
                n += 1
            fo.flush()
        for e, ms in pick_new:
            ms = [r for r in ms if r["t"] not in done]
            if not ms:
                continue
            iv, a, b = window(ms)
            by = {}
            step = 20 if iv == 60 else 6          # keep each batch response small (candle-count limits)
            for k in range(0, len(ms), step):
                d = kapi.get("/markets/candlesticks", {"market_tickers": ",".join(r["t"] for r in ms[k:k + step]), "start_ts": a,
                                                       "end_ts": b, "period_interval": iv}, cache=False)
                by.update({m["market_ticker"]: m.get("candlesticks") or [] for m in (d or {}).get("markets", [])})
            for r in ms:
                fo.write(json.dumps({"t": r["t"], "e": e, "half": "new", "iv": iv, "c": compact(by.get(r["t"], []))}) + "\n")
                n += 1
            fo.flush()
    return n


def main(argv):
    order = ["mentions", "entertainment", "politics", "sci_tech_companies", "econ_fin_other", "sports_futures", "climate_other", "sports_props"]
    P = universe.pick()
    names = argv or [s["t"] for fam in order for s in P.get(fam, [])]
    for i, s in enumerate(names):
        n = run(s)
        print("%3d/%d %-26s new rows %4d  requests so far %d" % (i + 1, len(names), s, n, kapi.STATS["net"]), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
