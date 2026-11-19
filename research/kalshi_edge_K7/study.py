#!/usr/bin/env python3
"""K7 step 3: the near-certain "carry" study (buy the 90-99c side some hours / days before the SCHEDULED close, hold to settlement).

No look-ahead:
  * the clock is the scheduled close, known when the market opens: the close time for markets that cannot close early; for markets
    that can close early, Kalshi's expected_expiration_time (identical for every market of an event and not moved by an early close:
    checked, YES and NO markets show the same exp-vs-close pattern) minus the series' usual offset, else latest_expiration_time minus
    its usual offset (offsets = medians over NO-result markets, old half first). The real close is never used to place a trade; a
    market already closed at the decision time is simply not traded.
  * the quote is the last candle that ENDED at or before the decision time (hourly: at most 3 h old; daily: at most 36 h old).
  * buy at the ask (YES at yes ask, NO at 100 - yes bid), spread at most MAX_SPREAD, fee 0.07 x fee_multiplier x C x P x (1-P) rounded
    UP to the cent on a $10 order (C = floor(10 / P) contracts). The series' fee multiplier comes from Kalshi's own series list.
Split: old half (train, markets closed before 2026-09-19) picks; new half (test, 2026-09-19 .. 2026-11-18) judges, read once.
Cells: family x price band x horizon. A cell is carried only if its train cluster t beats a one-sided Bonferroni bar over every
eligible train cell. Pre-registered pooled rules are reported whatever train says.
    python research/kalshi_edge_K7/study.py          -> research/kalshi_edge_K7/results.json (+ trades_test_best.json)
"""
import gzip
import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import universe  # noqa: E402

CACHE = os.environ.get("KK7_CACHE", "/home/user/kalshi_cache/knew2")
HERE = os.path.dirname(os.path.abspath(__file__))
H = 3600
HORIZONS = [("2h", 2 * H), ("8h", 8 * H), ("1d", 24 * H), ("3d", 72 * H), ("7d", 168 * H), ("21d", 21 * 24 * H), ("60d", 60 * 24 * H)]
BANDS = [("90-94c", 90, 93), ("94-97c", 94, 96), ("97-99c", 97, 99)]       # ask in cents, inclusive
MAX_SPREAD = 5
STAKE = 10.0
APY = 0.035                                   # Kalshi's published rate on cash AND open positions (help center, read 2026-11-18)


def fee_order(p, contracts, mult):
    """Kalshi taker fee for one order, rounded up to the cent."""
    x = 0.07 * mult * contracts * p * (1 - p)
    return math.ceil(round(x * 100, 6)) / 100.0


def series_meta():
    fam = {}
    for f, L in universe.pick().items():
        for s in L:
            fam[s["t"]] = (f, s["fm"] if s["fm"] is not None else 1)
    return fam


def gap_for(rows):
    """series-level clock for markets that CAN close early: expected_expiration_time ("exp") minus its usual offset from the close of
    NO-result markets (they run to the schedule). Used only if that offset is tight (median |exp - close| <= 3 h and 75th
    percentile <= 6 h; OLD half, else all NO markets): otherwise the series has no reliable clock and gets first-touch trades only."""
    def ok(r):
        return r.get("cce") and r["res"] == "no" and r.get("exp") and r.get("late") and r["exp"] < r["late"] - 60 and r.get("close")
    g = [r["exp"] - r["close"] for r in rows.values() if r["hist"] and ok(r)]
    if len(g) < 5:
        g = [r["exp"] - r["close"] for r in rows.values() if ok(r)]
    if len(g) < 5:
        return None
    a = sorted(abs(x) for x in g)
    if a[len(a) // 2] > 3 * H or a[(3 * len(a)) // 4] > 6 * H:
        return None
    return statistics.median(g)


def quote_at(cs, T, iv):
    stale = 3 * H if iv == 60 else 36 * H
    best = None
    for c in cs:              # sorted by end ts
        if c[0] <= T:
            best = c
        else:
            break
    if not best or best[0] < T - stale:
        return None
    return best


def make_trade(row, rec, fam, mult, hname, band, side, price, T, info_ts):
    p = price / 100.0
    C = int(STAKE // p)
    fee = fee_order(p, C, mult)
    cost = C * p + fee
    won = 1 if row["res"] == side else 0
    end = row.get("sett") or row["close"]
    return {"t": row["t"], "e": row["e"], "series": row["t"].split("-")[0], "fam": fam, "half": rec["half"], "h": hname,
            "band": band, "side": side, "price": price, "C": C, "fee": fee, "cost": cost, "won": won, "pnl": C * won - cost,
            "ts": T, "info_ts": info_ts, "settle_ts": end, "days": max(0.0, (end - info_ts) / 86400.0), "mult": mult}


def sides(c):
    """(side, price, band) for a candle quote with both sides and a spread of at most MAX_SPREAD."""
    if c[1] is None or c[2] is None or c[2] - c[1] > MAX_SPREAD or c[2] <= c[1]:
        return []
    out = []
    for side, price in (("yes", c[2]), ("no", 100 - c[1])):
        band = next((b for b, lo, hi in BANDS if lo <= price <= hi), None)
        if band:
            out.append((side, price, band))
    return out


def trades_for_market(rec, row, fam, mult, gap):
    """clock design: at fixed times before the scheduled close."""
    cs = sorted(rec["c"], key=lambda c: c[0])
    if not cs:
        return []
    if not row.get("cce"):
        anchor = row["close"]                                  # cannot close early: the close is the schedule
    elif gap is not None and row.get("exp") and row.get("late") and row["exp"] < row["late"] - 60:
        anchor = row["exp"] - gap                              # Kalshi's expected expiration (same for every market of an event,
                                                               # not moved by an early close) minus the series' usual offset
    else:
        return []                                              # no reliable clock: first-touch trades only
    out = []
    for hname, hs in HORIZONS:
        T = anchor - hs
        if T < row["open"] or T >= row["close"]:          # not open yet, or already closed (finished) at the decision time
            continue
        if (rec["iv"] == 1440 and hs < 24 * H) or (rec["iv"] == 60 and hs > 7 * 24 * H):
            continue
        c = quote_at(cs, T, rec["iv"])
        if not c:
            continue
        for side, price, band in sides(c):
            out.append(make_trade(row, rec, fam, mult, hname, band, side, price, T, c[0]))
    return out


def first_touch(rec, row, fam, mult):
    """touch design: the first candle (after the open, before the close) whose ask for a side is in a band: buy it, once per band."""
    out, done = [], set()
    for c in sorted(rec["c"], key=lambda c: c[0]):
        if c[0] < row["open"] or c[0] >= row["close"]:
            continue
        for side, price, band in sides(c):
            if band not in done:
                done.add(band)
                out.append(make_trade(row, rec, fam, mult, "touch", band, side, price, c[0], c[0]))
    return out


SCALE = {}       # series -> (live-window events / sampled events, live-window span in days)


def full_month(ts):
    """trades a month if EVERY live-window event of these series were traded (test half only): sample count x scale / span."""
    by = defaultdict(int)
    for x in ts:
        by[x["series"]] += 1
    return sum(n * SCALE.get(s, (1, 60))[0] / SCALE.get(s, (1, 60))[1] * 30.4 for s, n in by.items())


def load_list(series):
    fn = os.path.join(CACHE, "lists", series + ".json.gz")
    if not os.path.exists(fn):
        return None
    with gzip.open(fn, "rt") as fh:
        return {r["t"]: r for r in json.load(fh)}


def collect():
    meta = series_meta()
    trades = []
    for s, (fam, mult) in meta.items():
        fn = os.path.join(CACHE, "candles", s + ".jsonl.gz")
        if not os.path.exists(fn):
            continue
        rows = load_list(s)              # one series at a time (memory)
        if not rows:
            continue
        gap = gap_for(rows)
        live = [r for r in rows.values() if not r["hist"]]
        if live:                         # full-coverage scale for $/month: all live-window events vs the 15 sampled
            ne = len({r["e"] for r in live})
            span = max(1.0, (max(r["close"] for r in live) - min(r["close"] for r in live)) / 86400.0)
            SCALE[s] = (ne / max(1, min(15, ne)), span)
        seen = set()
        try:
            with gzip.open(fn, "rt") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if rec["t"] in seen or rec["t"] not in rows:
                        continue
                    seen.add(rec["t"])
                    trades += trades_for_market(rec, rows[rec["t"]], fam, mult, gap)
                    trades += first_touch(rec, rows[rec["t"]], fam, mult)
        except (EOFError, OSError):      # file still being written
            pass
        del rows
    return trades


# ------------------------------------------------------------------ statistics
def cluster_boot(ts, n=2000, seed=7):
    by = defaultdict(lambda: [0.0, 0.0])
    for x in ts:
        by[x["e"]][0] += x["pnl"]
        by[x["e"]][1] += x["cost"]
    g = list(by.values())
    k = len(g)
    if k < 2:
        return None, None
    rnd = random.Random(seed)
    v = []
    for _ in range(n):
        s = c = 0.0
        for _ in range(k):
            a, b = g[rnd.randrange(k)]
            s += a
            c += b
        v.append(s / c)
    v.sort()
    return v[int(0.025 * n)], v[int(0.975 * n)]


def cluster_t(ts):
    by = defaultdict(lambda: [0.0, 0.0])
    for x in ts:
        by[x["e"]][0] += x["pnl"]
        by[x["e"]][1] += x["cost"]
    k = len(by)
    S = sum(a for a, _ in by.values())
    C = sum(b for _, b in by.values())
    if k < 3 or C <= 0:
        return 0.0
    r = S / C
    var = sum((a - r * b) ** 2 for a, b in by.values()) * k / (k - 1) / C ** 2
    return r / math.sqrt(var) if var > 0 else (9.99 if r > 0 else -9.99 if r < 0 else 0.0)


def worst_streak(ts):
    best = cur = 0
    for x in sorted(ts, key=lambda x: x["ts"]):
        cur = 0 if x["won"] else cur + 1
        best = max(best, cur)
    return best


def exact_loss_upper(losses, n):
    """one-sided 95% upper bound on the loss rate (Clopper-Pearson)."""
    if n == 0:
        return None
    lo, hi = losses / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        # P(X <= losses | p = mid)
        cdf = sum(math.comb(n, j) * mid ** j * (1 - mid) ** (n - j) for j in range(losses + 1))
        if cdf > 0.05:
            lo = mid
        else:
            hi = mid
    return hi


def summ(ts, days_span=None):
    if not ts:
        return {"n": 0}
    cost = sum(x["cost"] for x in ts)
    pnl = sum(x["pnl"] for x in ts)
    wins = [x for x in ts if x["won"]]
    losses = [x for x in ts if not x["won"]]
    lo, hi = cluster_boot(ts)
    interest = sum(x["cost"] * APY * x["days"] / 365.0 for x in ts)
    span = days_span or max(1.0, (max(x["ts"] for x in ts) - min(x["ts"] for x in ts)) / 86400.0)
    n_loss = len(losses)
    be_loss = 1 - sum(x["cost"] for x in ts) / sum(x["C"] for x in ts)       # break-even loss rate per contract
    return {"n": len(ts), "events": len({x["e"] for x in ts}), "series": len({x["series"] for x in ts}),
            "win_rate": round(len(wins) / len(ts), 4), "losses": n_loss,
            "loss_rate_upper95": round(exact_loss_upper(n_loss, len(ts)), 4) if len(ts) <= 3000 else None,
            "breakeven_loss_rate": round(be_loss, 4),
            "avg_win_usd": round(statistics.mean(x["pnl"] for x in wins), 3) if wins else None,
            "avg_loss_usd": round(statistics.mean(x["pnl"] for x in losses), 3) if losses else None,
            "net_per_1": round(pnl / cost, 4), "ci95": [round(lo, 4) if lo is not None else None, round(hi, 4) if hi is not None else None],
            "t": round(cluster_t(ts), 2), "net_usd_at_10": round(pnl, 2), "fees_usd": round(sum(x["fee"] for x in ts), 2),
            "avg_price_c": round(statistics.mean(x["price"] for x in ts), 1), "avg_days_held": round(statistics.mean(x["days"] for x in ts), 2),
            "interest_usd": round(interest, 2), "net_per_1_with_interest": round((pnl + interest) / cost, 4),
            "annualized_net_no_interest": round((pnl / cost) * 365.0 / max(0.04, statistics.mean(x["days"] for x in ts)), 3),
            "worst_losing_streak": worst_streak(ts), "trades_per_month_sample": round(len(ts) / span * 30.4, 1),
            "trades_per_month_full": round(full_month(ts), 1) if ts[0]["half"] == "new" else None,
            "usd_month_at_10_full": round(pnl / cost * STAKE * full_month(ts), 2) if ts[0]["half"] == "new" else None}


def bar(n_cells):
    return statistics.NormalDist().inv_cdf(1 - 0.05 / max(1, n_cells))


def main():
    trades = collect()
    old = [x for x in trades if x["half"] == "old"]
    new = [x for x in trades if x["half"] == "new"]
    cells = defaultdict(list)
    for x in old:
        cells[(x["fam"], x["band"], x["h"])].append(x)
    elig = {k: v for k, v in cells.items() if len(v) >= 30 and len({x["e"] for x in v}) >= 8}
    b = bar(len(elig))
    train_rows = []
    for k, v in sorted(elig.items()):
        train_rows.append({"fam": k[0], "band": k[1], "h": k[2], "train": summ(v)})
    carried = [r for r in train_rows if r["train"]["t"] > b and r["train"]["net_per_1"] > 0]
    loose = [r for r in train_rows if r["train"]["t"] > 1.96 and r["train"]["net_per_1"] > 0]
    newc = defaultdict(list)
    for x in new:
        newc[(x["fam"], x["band"], x["h"])].append(x)
    for r in carried + loose:
        r["test"] = summ(newc.get((r["fam"], r["band"], r["h"]), []))
    # pre-registered pooled rules (reported whatever train says)
    prereg = {}
    for bn, _, _ in BANDS:
        for hn in [h for h, _ in HORIZONS] + ["touch"]:
            tr = [x for x in old if x["band"] == bn and x["h"] == hn]
            te = [x for x in new if x["band"] == bn and x["h"] == hn]
            prereg["all families, %s, %s before" % (bn, hn)] = {"train": summ(tr), "test": summ(te)}
    by_fam = {}
    for f in sorted({x["fam"] for x in trades}):
        d = {}
        for design, keep in (("touch", lambda x: x["h"] == "touch"), ("clock", lambda x: x["h"] != "touch")):
            d[design] = {"train": summ([x for x in old if x["fam"] == f and keep(x)]), "test": summ([x for x in new if x["fam"] == f and keep(x)]),
                         "by_band_train": {bn: summ([x for x in old if x["fam"] == f and keep(x) and x["band"] == bn]) for bn, _, _ in BANDS},
                         "by_band_test": {bn: summ([x for x in new if x["fam"] == f and keep(x) and x["band"] == bn]) for bn, _, _ in BANDS}}
        by_fam[f] = d
    by_h = {}
    for hn, _ in HORIZONS:
        by_h[hn] = {"train": summ([x for x in old if x["h"] == hn]), "test": summ([x for x in new if x["h"] == hn])}
    losers = sorted([x for x in new if not x["won"]], key=lambda x: -x["price"])[:40]
    res = {"n_trades": {"train": len(old), "test": len(new)}, "markets": {"train": len({x["t"] for x in old}), "test": len({x["t"] for x in new})},
           "eligible_train_cells": len(elig), "bonferroni_bar_t": round(b, 2), "carried": carried,
           "loose_t196_cells": loose, "train_cells": train_rows, "prereg_pooled": prereg, "by_family": by_fam, "by_horizon": by_h,
           "all_touch": {"train": summ([x for x in old if x["h"] == "touch"]), "test": summ([x for x in new if x["h"] == "touch"])},
           "all_clock": {"train": summ([x for x in old if x["h"] != "touch"]), "test": summ([x for x in new if x["h"] != "touch"])},
           "test_losers_most_expensive": [{k: x[k] for k in ("t", "h", "band", "side", "price", "fam")} for x in losers]}
    print("trades train %d test %d, eligible cells %d, bar t %.2f, carried %d, loose %d" % (len(old), len(new), len(elig), b, len(carried), len(loose)))
    if "--final" not in sys.argv:          # interim runs never write the test half to disk either
        res = {k: v for k, v in res.items() if k in ("n_trades", "markets", "eligible_train_cells", "bonferroni_bar_t", "train_cells")}
        with open(os.path.join(HERE, "results_train_only.json"), "w") as fo:
            json.dump(res, fo, indent=1)
    else:
        with open(os.path.join(HERE, "results.json"), "w") as fo:
            json.dump(res, fo, indent=1)
        with gzip.open(os.path.join(CACHE, "trades_all.json.gz"), "wt") as fo:
            json.dump(trades, fo)
    final = "--final" in sys.argv          # the test half is printed only on the one final run (design frozen before)
    for f, d in by_fam.items():
        for design in ("touch", "clock"):
            a, t = d[design]["train"], d[design]["test"]
            print("%-20s %-5s train n %5d win %s net %s" % (f, design, a.get("n", 0), a.get("win_rate"), a.get("net_per_1")) +
                  (" | test n %5d win %s net %s" % (t.get("n", 0), t.get("win_rate"), t.get("net_per_1")) if final else ""))
    for r in carried:
        print("CARRIED", r["fam"], r["band"], r["h"], "train", r["train"]["n"], r["train"]["net_per_1"], r["train"]["t"],
              ("test %s %s" % (r["test"].get("n"), r["test"].get("net_per_1"))) if final else "")
    return res


if __name__ == "__main__":
    main()
