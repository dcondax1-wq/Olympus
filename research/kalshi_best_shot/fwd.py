#!/usr/bin/env python3
"""Forward PAPER test of the plan's rule with Kalshi's published scoring (lip.py): GET-only public data, <= 1 request a second,
never an order. Every cycle it reads the public book of every rewarded market of the series, keeps ONE virtual bid per chosen
side (price = reference - offset ticks, size = floor(usd / price) contracts, only sides priced inside the band whose order would
earn >= min_expect $ over the program period), joins the BACK of the queue, fills from the public trade tape (at my price after the
queue ahead, through my price = whole order), and credits the per-side share of the pool for the time since the last cycle
(at most --gap x 2 s). At each program's end: rounded down to the cent, nothing under $1.00 (the published rule).
Also books every snapshot to the books file (books.py format) for the depth profiles.
    python research/kalshi_best_shot/fwd.py SERIES,.. [--band 0.01,0.10] [--usd 10] [--offset 0] [--min-expect 1.5]
                                            [--pause-c 5] [--loops 24] [--gap 600] [--ledger PATH]"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import math
import os
import random
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kget  # noqa: E402
import lip  # noqa: E402
from books import OUT as BOOKS, levels, markets, programs  # noqa: E402

LEDGER = "/home/user/kalshi_cache/krew/fwd/ledger.json"


def save(path, d):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(d, f)
    os.replace(tmp, path)


def load(path):
    try:
        d = json.load(open(path))
        if d.get("kind") == "kalshi_best_shot_fwd":
            return d
    except (OSError, ValueError):
        pass
    return {"v": 2, "kind": "kalshi_best_shot_fwd", "paper_only": True, "rules": {}, "cycles": 0, "started": None, "updated": None}


def choose(yes, no, prog, rule):
    """the sides to quote now: [(side, price, size, expected $ for the program period, queue ahead)]."""
    out = []
    for sd, L in (("yes", yes), ("no", no)):
        ref = lip.ref_price(L, prog["target"])
        if ref is None:
            continue
        price = round(ref - rule["offset"] * lip.TICK, 2)
        if price < 0.01 or not (rule["band"][0] - 1e-9 <= price <= rule["band"][1] + 1e-9):
            continue
        n = math.floor(rule["usd"] / price + 1e-9)
        if n < 1:
            continue
        rate = lip.reward_rate(yes, no, sd, price, n, prog["target"], prog["df"], prog["usd_day"])
        per = min(prog["end"] - prog["start"], 31 * 86400) / 86400
        if rate * per < rule["min_expect"]:
            continue
        out.append((sd, price, n, rate * per, lip.ahead(L, price)))
    return out


def apply_trades(o, tr):
    """fills of one virtual bid from public trades newer than its last look (back-of-queue, through = whole order)."""
    got_all = 0.0
    for x in tr:
        ts = dt.datetime.fromisoformat(x["created_time"].replace("Z", "+00:00")).timestamp()
        if ts <= o["seen_t"] or x["trade_id"] in o.get("ids", []):
            continue
        o.setdefault("ids", []).append(x["trade_id"])
        py, n, side = float(x["yes_price_dollars"]), float(x["count_fp"]), x["taker_side"]
        px = py if (o["side"] == "yes" and side == "no") else (round(1 - py, 4) if (o["side"] == "no" and side == "yes") else None)
        if px is None or px > o["p"] + 1e-9 or o["q"] <= 1e-9:
            continue
        if px < o["p"] - 1e-9:
            got, o["queue"] = o["q"], 0.0
        else:
            eat = min(n, o["queue"])
            o["queue"] -= eat
            got = min(n - eat, o["q"])
        if got > 1e-9:
            o["q"] -= got
            got_all += got
    o["ids"] = o.get("ids", [])[-200:]
    return got_all


def cycle(led, series, rules, now, gap, books_f=None, max_per=0):
    led["started"] = led.get("started") or now
    for name, rule in rules.items():
        led["rules"].setdefault(name, {"rule": rule, "orders": {}, "programs": {}, "fills": [], "cap_s": 0.0})
    for s in series:
        pr = programs(s)
        mk = markets(s)
        ts = sorted(x for x in pr if x in mk)
        if max_per and len(ts) > max_per:          # a fixed seeded sample, plus every market where an order already rests
            keep = set(random.Random(11).sample(ts, max_per))
            keep |= {o["m"] for R in led["rules"].values() for o in R["orders"].values() if o["q"] > 0}
            ts = [t for t in ts if t in keep]
        for t in ts:
            p = pr[t]
            ob = kget.get("/markets/%s/orderbook" % t, cache=False)
            if ob is None:
                continue
            yes, no = levels(ob, "yes_dollars"), levels(ob, "no_dollars")
            if books_f is not None:
                books_f.write(json.dumps({"t": round(now, 1), "m": t, "s": s, "yes": yes, "no": no, "prog": p, "mk": mk[t]}) + "\n")
            live = [o for R in led["rules"].values() for o in R["orders"].values() if o["m"] == t and o["q"] > 0]
            tr = []
            if live:
                since = min(o["seen_t"] for o in live)
                tr = (kget.get("/markets/trades", {"ticker": t, "limit": 1000, "min_ts": int(since)}, cache=False) or {}).get("trades") or []
            mid = (yes[0][0] + 1 - no[0][0]) / 2 if yes and no else None
            for name, R in led["rules"].items():
                rule = R["rule"]
                pid = "%s|%d" % (t, int(p["end"]))
                P = R["programs"].setdefault(pid, {"m": t, "s": s, "end": p["end"], "usd_day": p["usd_day"], "reward": 0.0, "secs": 0.0})
                for o in [o for o in R["orders"].values() if o["m"] == t and o["q"] > 0]:
                    got = apply_trades(o, tr)
                    if got > 0:
                        R["fills"].append({"m": t, "side": o["side"], "p": o["p"], "n": got, "t": now})
                    o["seen_t"] = now
                    dtm = min(max(now - o["last_t"], 0.0), 2 * gap)
                    if o["q"] > 0:
                        P["reward"] += lip.reward_rate(yes, no, o["side"], o["p"], o["q"], p["target"], p["df"], p["usd_day"]) * dtm / 86400
                        P["secs"] += dtm
                        R["cap_s"] += o["p"] * o["q"] * dtm
                    o["last_t"] = now
                for f in R["fills"]:
                    if f["m"] == t and mid is not None:
                        f["mark"] = mid if f["side"] == "yes" else 1 - mid
                want = {(sd, price): (n, e, q) for sd, price, n, e, q in choose(yes, no, p, rule)}
                for o in R["orders"].values():
                    if o["m"] == t and o["q"] > 0 and (o["side"], o["p"]) not in want:
                        o["q"] = 0.0
                for (sd, price), (n, e, q) in want.items():
                    k = "%s|%s|%.2f" % (t, sd, price)
                    o = R["orders"].get(k)
                    if o and o["q"] > 0:
                        continue
                    R["orders"][k] = {"m": t, "side": sd, "p": price, "q": float(n), "n0": float(n), "queue": q, "expect": round(e, 2),
                                      "placed": now, "seen_t": now, "last_t": now}
    for R in led["rules"].values():
        R["orders"] = {k: o for k, o in R["orders"].items() if o["q"] > 0 or now - o["placed"] < 86400}
    led["cycles"] += 1
    led["updated"] = now
    return led


def report(led, now=None):
    now = now or time.time()
    out = {"hours": round((led["updated"] - led["started"]) / 3600, 2) if led.get("started") else 0, "cycles": led["cycles"], "rules": {}}
    for name, R in led["rules"].items():
        raw = sum(P["reward"] for P in R["programs"].values())
        done = [P for P in R["programs"].values() if P["end"] <= now and P["reward"] > 0]
        fills = R["fills"]
        fill_pnl = sum(f["n"] * (f.get("mark", f["p"]) - f["p"]) for f in fills)
        capd = R["cap_s"] / 86400
        out["rules"][name] = {"reward_raw": round(raw, 2), "paid_closed": round(sum(lip.payout(P["reward"]) for P in done), 2),
                              "closed_programs": len(done), "closed_paid": sum(1 for P in done if lip.payout(P["reward"]) > 0),
                              "fills": len(fills), "filled_usd": round(sum(f["p"] * f["n"] for f in fills), 2), "fill_pnl_mark": round(fill_pnl, 2),
                              "orders_now": sum(1 for o in R["orders"].values() if o["q"] > 0),
                              "parked_now": round(sum(o["p"] * o["q"] for o in R["orders"].values() if o["q"] > 0), 2),
                              "reward_per100_day": round(100 * raw / capd, 2) if capd > 0 else None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("series")
    ap.add_argument("--rules", default="floor:0.01:0.01:10:0:1.5,cheap:0.01:0.10:10:0:1.5,all:0.01:0.99:10:0:1.5",
                    help="name:lo:hi:usd:offset:min_expect,...")
    ap.add_argument("--loops", type=int, default=1)
    ap.add_argument("--gap", type=float, default=600.0)
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--max", type=int, default=0, help="markets per series per cycle (0 = all)")
    a = ap.parse_args()
    rules = {}
    for x in a.rules.split(","):
        nm, lo, hi, usd, off, me = x.split(":")
        rules[nm] = {"band": [float(lo), float(hi)], "usd": float(usd), "offset": int(off), "min_expect": float(me)}
    led = load(a.ledger)
    for k in range(a.loops):
        t0 = time.time()
        os.makedirs(BOOKS, exist_ok=True)
        with gzip.open(os.path.join(BOOKS, dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d") + "_fwd%s.jsonl.gz" % ("" if a.ledger == LEDGER else "_" + os.path.basename(a.ledger).split(".")[0])), "at") as bf:
            try:
                cycle(led, a.series.split(","), rules, t0, a.gap, bf, a.max)
            except Exception as e:  # noqa: BLE001
                print("cycle error", repr(e), flush=True)
        save(a.ledger, led)
        print(dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S"), json.dumps(report(led)), kget.STATS, flush=True)
        if k < a.loops - 1:
            time.sleep(max(1.0, a.gap - (time.time() - t0)))


if __name__ == "__main__":
    main()
