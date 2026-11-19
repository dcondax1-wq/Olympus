#!/usr/bin/env python3
"""Rewards-maker backtest with Kalshi's PUBLISHED scoring (lip.py: per-side shares, $1 minimum per market program) on the
public tape (harvest.py cache) and today's measured depth (profiles.py). Offline, never an order.

Per market, while its liquidity program runs, the rule rests ONE small bid per quoted side:
  price   the side's reward reference (best bid - the measured ticks to the reference) minus `offset` ticks; the book is the last
          closed 1-minute candle (no look-ahead). A side is quoted only if its price is inside `band`.
  size    floor(usd / price) contracts (the owner's budget: dollars, not Target/5).
  pick    only if this order's expected payout for the program period (from the depth draw) is >= `min_expect` $ (the live
          rule reads the same thing from the live book); this is how the $1 minimum is respected.
  queue   a new or moved order joins the BACK of the queue: ahead = qmult x the measured queue at that price.
  fills   taker trades at my price eat the queue first, then fill me; a trade THROUGH my price means my level is gone: the whole
          remaining order is filled. A filled side is re-posted at the next quote change only while the market's inventory is
          under `inv_cap` $.
  reward  pool $/s x seconds x my score / (others' score + my score) / 2 per side (the yes and no sides are shared separately),
          x the series' valid-snapshot share; summed per market program, rounded down to the cent, 0 if under $1.00.
  pauses  `pause_c` cents mid move vs an hour ago -> no quotes for `pause_h` hours; no quotes in the last `pull_h` hours before
          the close; `blackout` = [(weekday 0=Mon, ET hour from, ET hour to)] windows with no quotes.
  P&L     each fill to $1 / $0 at settlement (today's mid if not settled), booked on the fill's day; maker fee only where the
          series has one.
Others' score and the queue come jointly from today's snapshots: 4 representative books per (series, price bucket) at the
12.5 / 37.5 / 62.5 / 87.5 percentiles of others' score; every number is the average over the 4.
    python research/kalshi_best_shot/bt.py [--grid] -> research/kalshi_best_shot/results.json"""
from __future__ import annotations

import bisect
import collections
import heapq
import datetime as dt
import gzip
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lip  # noqa: E402
from profiles import bucket  # noqa: E402

BT = os.environ.get("KREW_BT", "/home/user/kalshi_cache/krew/bt")
QS = (0.125, 0.375, 0.625, 0.875)
ET = -5 * 3600                       # EST (the window is after Nov 1, and the day edges are what matter)
BASE = {"band": (0.01, 0.99), "usd": 10.0, "offset": 0, "pause_c": 0, "pause_h": 1.0, "pull_h": 0.0, "blackout": (),
        "inv_cap": 1e9, "qmult": 1.0, "smult": 1.0, "min_expect": 0.0, "min_payout": True, "sides": ("yes", "no")}


def T(s):
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def F(x):
    if x is None or isinstance(x, float):
        return x
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def day_of(ts):
    """the ET day number of a timestamp (the backtest's day buckets)."""
    return int((ts + ET) // 86400)


def et_day(ts):
    return dt.datetime.fromtimestamp(ts + ET, dt.timezone.utc).strftime("%Y-%m-%d")


def et_wd_hour(ts):
    d = dt.datetime.fromtimestamp(ts + ET, dt.timezone.utc)
    return d.weekday(), d.hour + d.minute / 60.0


def reps(prof_series, prof_all, b):
    """4 representative books for a price bucket: (S, ahead0..3, ticks) at the score quantiles; falls back to the series' other
    buckets, then to every series' same bucket."""
    xs = (prof_series or {}).get(b) or []
    if len(xs) < 4:
        xs = xs + [x for bb, L in (prof_series or {}).items() if bb != b for x in L] if len(xs) < 2 else xs
    if len(xs) < 2:
        xs = prof_all.get(b) or []
    if not xs:
        return None
    xs = sorted(xs, key=lambda x: x["S"])
    return [xs[min(len(xs) - 1, int(q * len(xs)))] for q in QS]


def valid_share(prof_series):
    v = [x["valid"] for L in (prof_series or {}).values() for x in L]
    return sum(1 for x in v if x) / len(v) if v else 1.0


def sim(v, rep_fn, vshare, fee_type, rule, r, T0, T1, days, stats):
    info = v["info"]
    res = info.get("result") or ""
    close = T(info["close_time"]) if info.get("close_time") else T1 + 365 * 86400
    yb, ya = F(info.get("yes_bid_dollars")), F(info.get("yes_ask_dollars"))
    mid_now = (yb + ya) / 2 if yb is not None and ya is not None and ya > 0 else (F(info.get("last_price_dollars")) or 0.5)
    val_yes = 1.0 if res == "yes" else 0.0 if res == "no" else mid_now
    stop = min(T1, close - rule["pull_h"] * 3600)
    wins = sorted([(max(p["start"], T0), min(p["end"], stop), i, p) for i, p in enumerate(v["programs"])
                   if min(p["end"], stop) > max(p["start"], T0)])
    if not wins:
        return
    cand = [c for c in v["candles"] if c[0] <= T1]
    if not cand:
        return
    cts = [c[0] for c in cand]
    trades = [x for x in v["trades"] if wins[0][0] <= x[0] <= wins[-1][1]]
    ev = {a for a, _, _, _ in wins} | {b for _, b, _, _ in wins}
    last = None
    for c in cand:
        q = (c[1], c[2])
        if q != last:
            ev.add(c[0])
            last = q
    if rule["blackout"]:
        d0 = int((wins[0][0] + ET) // 86400)
        for d in range(d0, int((wins[-1][1] + ET) // 86400) + 2):
            for _, h0, h1 in rule["blackout"]:
                ev.add(d * 86400 - ET + h0 * 3600)
                ev.add(d * 86400 - ET + h1 * 3600)
    lo, hi = wins[0][0], wins[-1][1]
    ev = sorted(e for e in ev if lo <= e <= hi)
    sides = {sd: {"p": None, "q": 0.0, "queue": 0.0, "S": 0.0, "m": 1.0} for sd in ("yes", "no")}
    df = wins[0][3]["df"]
    rew = collections.defaultdict(float)
    held = [0.0]
    inv = [0.0]
    pause_until = -1.0
    tts = [x[0] for x in trades]
    ti = 0

    def prog_at(t):
        for a, b, i, p in wins:
            if a <= t < b:
                return i, p
        return None, None

    extra = []                                   # pause ends (a pause can end between two quote changes)
    k = 0
    t = None
    while True:
        if t is None:
            t = ev[0]
        nxt_ev = ev[k + 1] if k + 1 < len(ev) else None
        pid, p = prog_at(t)
        ci = bisect.bisect_right(cts, t) - 1
        bid = F(cand[ci][1]) if ci >= 0 else None
        ask = F(cand[ci][2]) if ci >= 0 else None
        if bid is not None and ask is not None and 0 < bid < ask < 1 and rule["pause_c"]:
            cj = bisect.bisect_right(cts, t - 3600) - 1
            b0, a0 = (F(cand[cj][1]), F(cand[cj][2])) if cj >= 0 else (None, None)
            if b0 is not None and a0 is not None and 0 < b0 < a0 < 1 and abs((bid + ask) / 2 - (b0 + a0) / 2) >= rule["pause_c"] / 100.0 - 1e-9:
                pu = cand[ci][0] + rule["pause_h"] * 3600
                if pu > pause_until + 1e-9:
                    pause_until = pu
                    heapq.heappush(extra, pu)
        quoting = p is not None and t >= pause_until
        if quoting and rule["blackout"]:
            wd, hr = et_wd_hour(t)
            quoting = not any(wd == w and h0 <= hr < h1 for w, h0, h1 in rule["blackout"])
        for sd in ("yes", "no"):
            o = sides[sd]
            best = (bid if sd == "yes" else (1 - ask) if ask is not None else None) if (bid is not None and ask is not None and 0 < bid < ask < 1) else None
            if not quoting or best is None or sd not in rule["sides"] or inv[0] >= rule["inv_cap"] - 1e-9:
                o.update(p=None, q=0.0)
                continue
            rp = rep_fn(bucket(best))
            if not rp:
                o.update(p=None, q=0.0)
                continue
            x = rp[r]
            price = round(best - (x["ticks"] + rule["offset"]) * lip.TICK, 2)
            if price < 0.01 or not (rule["band"][0] - 1e-9 <= price <= rule["band"][1] + 1e-9):
                o.update(p=None, q=0.0)
                continue
            if o["p"] is None or abs(o["p"] - price) > 1e-9 or o["q"] <= 1e-9:
                n = math.floor(rule["usd"] / price + 1e-9)
                S = rule["smult"] * x["S"]
                ft = x.get("floor_ticks", 99)
                m = df ** rule["offset"] if (ft is None or ft < 0 or rule["offset"] <= ft) else 0.0   # past the Target walk: no score
                usd_s = p["usd"] / max(p["end"] - p["start"], 1)
                exp_day = usd_s * 86400 * (n * m / (S + n * m) if S + n * m > 0 else 0) / 2 * vshare
                per_len = min(p["end"] - p["start"], 86400 * 31) / 86400
                if n < 1 or exp_day * per_len < rule["min_expect"]:
                    o.update(p=None, q=0.0)
                    continue
                o.update(p=price, q=float(n), queue=rule["qmult"] * x.get("ahead%d" % rule["offset"], x["ahead0"]), S=S, m=m)
        while extra and extra[0] <= t + 1e-9:
            heapq.heappop(extra)
        nxt = min(x for x in (nxt_ev, extra[0] if extra else None) if x is not None) if (nxt_ev is not None or extra) else None
        if nxt is not None and nxt > hi:
            nxt = hi if hi > t else None
        if nxt is None or nxt <= t:
            break
        usd_s = p["usd"] / max(p["end"] - p["start"], 1) if p is not None else 0.0

        def accrue(a, b):
            # reward and parked $ over [a, b) with the orders as they are now (split at ET midnights for the day buckets)
            while b > a + 1e-9:
                e = min(b, (math.floor((a + ET) / 86400) + 1) * 86400 - ET)
                dur = e - a
                if p is not None:
                    for o in sides.values():
                        if o["p"] is not None and o["q"] > 1e-9:
                            my = o["q"] * o["m"]
                            rew[pid] += usd_s * dur * my / (o["S"] + my) / 2 * vshare
                cap = sum(o["p"] * o["q"] for o in sides.values() if o["p"] is not None) + held[0]
                days[int((a + ET) // 86400)][2] += cap * dur
                a = e

        cur = t
        while ti < len(trades) and trades[ti][0] < nxt:
            tt, side, py, n = trades[ti]
            ti += 1
            if tt < t:
                continue
            if tt > cur:
                accrue(cur, tt)
                cur = tt
            for sd in ("yes", "no"):
                o = sides[sd]
                if o["p"] is None or o["q"] <= 1e-9:
                    continue
                if sd == "yes" and side == "no":
                    px = py
                elif sd == "no" and side == "yes":
                    px = round(1 - py, 4)
                else:
                    continue
                if px > o["p"] + 1e-9:
                    continue
                if px < o["p"] - 1e-9:
                    got = o["q"]
                    o["queue"] = 0.0
                    stats["through"] += 1
                else:
                    eat = min(n, o["queue"])
                    o["queue"] -= eat
                    got = min(n - eat, o["q"])
                if got <= 1e-9:
                    continue
                o["q"] -= got
                held[0] += got * o["p"]
                inv[0] += got * o["p"]
                win = val_yes if sd == "yes" else 1 - val_yes
                fee = lip.maker_fee(o["p"], got, fee_type)
                d = days[int((tt + ET) // 86400)]
                d[1] += got * (win - o["p"]) - fee
                d[3] += 1
                d[4] += got * o["p"]
                stats["fills"] += 1
                if o["q"] <= 1e-9:
                    o["p"] = None
        accrue(cur, nxt)
        if nxt_ev is not None and nxt >= nxt_ev - 1e-9:
            k += 1
        t = nxt
    if held[0] > 0 and t is not None:                  # filled contracts stay parked until the close (or the window end)
        a, b = t, min(close, T1)
        while b > a + 1e-9:
            e = min(b, (math.floor((a + ET) / 86400) + 1) * 86400 - ET)
            days[int((a + ET) // 86400)][2] += held[0] * (e - a)
            a = e
    for pid, x in rew.items():
        a, b, i, p = next(w for w in wins if w[2] == pid)
        paid = lip.payout(x) if rule["min_payout"] else x
        days[int((p["end"] - 1 + ET) // 86400)][0] += paid
        stats["programs"] += 1
        stats["paid_programs"] += 1 if paid > 0 else 0
        stats["unpaid_usd"] += x - paid if rule["min_payout"] else 0.0


_DATA = {}


def load(s):
    if s not in _DATA:
        d = json.load(gzip.open(os.path.join(BT, s + ".json.gz"), "rt"))
        for v in d["markets"].values():
            v["candles"] = [[c[0], F(c[1]), F(c[2]), c[3]] for c in v["candles"]]
        _DATA[s] = d
    return _DATA[s]


def run(s, prof, rule, T0, T1):
    d = load(s)
    ps = prof.get(s) or {}
    allb = collections.defaultdict(list)
    for L in prof.values():
        for b, xs in L.items():
            allb[b] += xs
    cache = {}

    def rep_fn(b):
        if b not in cache:
            cache[b] = reps(ps, allb, b)
        return cache[b]

    vs = valid_share(ps) if ps else 1.0
    days = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0, 0.0])
    stats = collections.Counter()
    for m, v in d["markets"].items():
        for r in range(len(QS)):
            sim(v, rep_fn, vs, d.get("fee_type"), rule, r, T0, T1, days, stats)
    out = {}
    for k, row in days.items():
        out[dt.datetime.fromtimestamp(k * 86400, dt.timezone.utc).strftime("%Y-%m-%d")] = [x / len(QS) for x in row]
    for k in list(stats):
        stats[k] /= len(QS)
    return out, stats


def summarize(days, d0, d1):
    """days: {ET day: [reward, fill_pnl, capital_seconds, fills, filled_usd]}; d0..d1 inclusive ET day strings."""
    ks = sorted(k for k in days if d0 <= k <= d1)
    rew = sum(days[k][0] for k in ks)
    fil = sum(days[k][1] for k in ks)
    capd = sum(days[k][2] for k in ks) / 86400
    nets = [days[k][0] + days[k][1] for k in ks]
    n = max(len(ks), 1)
    return {"days": len(ks), "reward": round(rew, 2), "fill_pnl": round(fil, 2), "net": round(rew + fil, 2),
            "avg_capital": round(capd / n, 2), "fills": round(sum(days[k][3] for k in ks), 1),
            "net_per100_day": round(100 * (rew + fil) / capd, 3) if capd > 0 else None,
            "reward_per100_day": round(100 * rew / capd, 3) if capd > 0 else None,
            "fill_per100_day": round(100 * fil / capd, 3) if capd > 0 else None,
            "days_up": sum(1 for x in nets if x > 1e-9), "days_down": sum(1 for x in nets if x < -1e-9),
            "worst_day": round(min(nets), 2) if nets else None, "best_day": round(max(nets), 2) if nets else None}


# ------------------------------------------------------------------------------------------------ the grid (fixed before the run)
D0, DMID, D1 = "2026-10-18", "2026-11-02", "2026-11-18"          # halves: Oct 18 - Nov 2 / Nov 3 - Nov 18 (16 + 16 ET days)
BANDS = {"f1": (0.01, 0.01), "c1": (0.01, 0.03), "c2": (0.04, 0.10), "lo": (0.11, 0.35), "mid": (0.36, 0.64), "hi": (0.65, 0.89), "top": (0.90, 0.99),
         "all": (0.01, 0.99)}
# the planned default, fixed before the run: $10 bids, only where the order would earn >= $1.50 for its program (the $1 rule),
# stop a market after a $10 fill, pause an hour after a 5c move, and no quotes in the last 33 h (the counted week is over, the
# answer is known to ship trackers, only the published number is missing)
GRID_BASE = dict(BASE, usd=10.0, min_expect=1.5, inv_cap=10.0, pause_c=5, pause_h=1.0, pull_h=33.0)


def grid():
    out = []
    for b, band in BANDS.items():
        out.append(("%s" % b, dict(GRID_BASE, band=band)))
        out.append(("%s_off1" % b, dict(GRID_BASE, band=band, offset=1)))
        out.append(("%s_nopause" % b, dict(GRID_BASE, band=band, pause_c=0)))
        out.append(("%s_nopull" % b, dict(GRID_BASE, band=band, pull_h=0.0)))
    return out


def sensitivities(rule):
    return [("as_picked", rule), ("depth_x2", dict(rule, smult=2.0)), ("queue_x0.25", dict(rule, qmult=0.25)),
            ("no_pick", dict(rule, min_expect=0.0)), ("usd25", dict(rule, usd=25.0)), ("pull24h", dict(rule, pull_h=24.0)),
            ("no_1usd_rule", dict(rule, min_payout=False))]


def halves(days):
    nxt = (dt.date.fromisoformat(DMID) + dt.timedelta(days=1)).isoformat()
    return {"first": summarize(days, D0, DMID), "last": summarize(days, nxt, D1), "all": summarize(days, D0, D1)}


def pooled_days(day_maps):
    acc = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0, 0.0])
    for dm in day_maps:
        for k, row in dm.items():
            for i in range(5):
                acc[k][i] += row[i]
    return acc


def positive_both(h):
    a, b = h["first"]["net_per100_day"], h["last"]["net_per100_day"]
    return a is not None and b is not None and a > 0 and b > 0


def main():
    prof = json.load(open(os.path.join(HERE, "depth_profiles.json")))["profiles"]
    t0 = dt.datetime.fromisoformat(D0).replace(tzinfo=dt.timezone.utc).timestamp() - ET
    t1 = dt.datetime.fromisoformat(D1).replace(tzinfo=dt.timezone.utc).timestamp() - ET + 86400
    series = sorted(f[:-8] for f in os.listdir(BT) if f.endswith(".json.gz"))
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    if only:
        series = [s for s in series if s in only[0].split(",")]
    res = {"rule": "bt.py: published LIP scoring, $10 bids, back of the queue, hourly book", "window": [D0, D1], "half_split_after": DMID,
           "base": {k: v for k, v in GRID_BASE.items()}, "series": {}, "carried": [], "pooled": {}, "cells": 0}
    keep = {}
    for s in series:
        R = {}
        for name, rule in grid():
            days, st = run(s, prof, rule, t0, t1)
            R[name] = dict(halves(days), stats={k: round(v, 2) for k, v in st.items()})
            res["cells"] += 2
            keep[(s, name)] = days
            h = R[name]
            print("%-20s %-12s first %7s  last %7s  (reward %6s/%6s fills %6s/%6s)  n_fills %5s/%5s paid %s/%s" % (
                s, name, h["first"]["net_per100_day"], h["last"]["net_per100_day"], h["first"]["reward_per100_day"], h["last"]["reward_per100_day"],
                h["first"]["fill_per100_day"], h["last"]["fill_per100_day"], h["first"]["fills"], h["last"]["fills"],
                h["stats"].get("paid_programs"), h["stats"].get("programs")), flush=True)
        res["series"][s] = R
        # carried: the planned default (no suffix) positive in both halves, and still positive with twice the depth and a 4x
        # shorter queue (fixed before the run)
        for b in BANDS:
            if b == "all" or not positive_both(R[b]):
                continue
            sens = {}
            for nm, rule in sensitivities(dict(GRID_BASE, band=BANDS[b])):
                if nm == "as_picked":
                    continue
                days, st = run(s, prof, rule, t0, t1)
                sens[nm] = halves(days)
                res["cells"] += 2
            R[b]["sensitivity"] = sens
            ok = positive_both(sens["depth_x2"]) and positive_both(sens["queue_x0.25"])
            print("   carried?", s, b, ok, {k: (v["first"]["net_per100_day"], v["last"]["net_per100_day"]) for k, v in sens.items()}, flush=True)
            if ok:
                res["carried"].append([s, b])
        _DATA.pop(s, None)
    if res["carried"]:
        pdays = pooled_days(keep[(s, b)] for s, b in res["carried"])
        res["pooled"]["carried"] = halves(pdays)
        res["pooled"]["carried_daily"] = {k: [round(x, 3) for x in v] for k, v in sorted(pdays.items())}
    alld = pooled_days(keep[(s, "all")] for s in series)
    res["pooled"]["all_bands_all_series"] = halves(alld)
    json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1)
    print("cells", res["cells"], "carried", res["carried"])
    for k, v in res["pooled"].items():
        if isinstance(v, dict) and "first" in v:
            print("POOLED", k, {h: {x: v[h][x] for x in ("net_per100_day", "reward_per100_day", "fill_per100_day", "avg_capital", "days_up", "days_down", "worst_day", "fills")} for h in ("first", "last")})


if __name__ == "__main__":
    main()
