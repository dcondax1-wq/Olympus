#!/usr/bin/env python3
"""Red team on K8 (the friend's 15-minute gold / silver clock bets, research/kalshi_edge_K8/). Offline: reads the K8 raw cache
/home/user/kalshi_cache/kmetal (read only) and research/kalshi_edge_K8/data/legs_bets.csv. Never touches the network.

  1 outcome rule  Kalshi's result vs the filed rule (UP iff settle >= target, tie = UP), and target = the previous window's settle
  2 entry timing  the study's entry (VWAP of takers of our side 15-30 s after the open, fallback 5-45 s) vs entries a bot really
                  has at +20 s: the first trade of our side at or after 20 s, the VWAP of the first 28 contracts after 20 s (a
                  $15 order walking the same liquidity), the open sweep (0-1 s) for comparison
  3 fees / fills  verify.py on every bet at $15 = floor(15 / price) contracts, fee ceil(0.07 C P (1-P)) per order
  4 decay         month by month and the last 4 weeks (Oct 22 - Nov 18) alone
  5 clocks        the Oct 26-30 week (UK on GMT, US still on EDT): 05:15-05:30 ET vs 06:15-06:30 ET; the coming mismatch weeks
  6 luck          how good the best 6 of all gold + silver quarter hours look on these 78 days if every window were a coin flip
Writes results_k8.json next to this file.
    python research/kalshi_red_team/k8_check.py"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import json
import math
import os
import random
import sys
import zoneinfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import verify as V  # noqa: E402

CACHE = "/home/user/kalshi_cache/kmetal"
BETS = os.path.join(ROOT, "research", "kalshi_edge_K8", "data", "legs_bets.csv")
OUT = os.path.join(HERE, "results_k8.json")
ET, LON, UTC = zoneinfo.ZoneInfo("America/New_York"), zoneinfo.ZoneInfo("Europe/London"), dt.timezone.utc
SER = {"gold": "KXGOLD15M", "silver": "KXSILVER15M"}
LEGS = {"A_gold": ("gold", "0530", "no"), "A_silver": ("silver", "0530", "no"), "B_gold": ("gold", "1700", "yes"),
        "B_silver": ("silver", "1700", "yes"), "C_silver": ("silver", "1615", "no"), "C_gold": ("gold", "1615", "no")}
STAKE = 15.0


def T(s):
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def load_markets(series):
    out = []
    for line in open(os.path.join(CACHE, "mk_%s.jsonl" % series)):
        r = json.loads(line)
        out.append(r)
    return out


def open_tape(series):
    d = {}
    fn = os.path.join(CACHE, "ot_%s.jsonl" % series)
    for line in open(fn):
        r = json.loads(line)
        d[r["t"]] = r
    return d


def our(tr, side):
    """our side's taker trades: (seconds after open, our price, contracts)."""
    return [(x[0], (x[2] if x[1] == "yes" else round(1 - x[2], 4)), x[3]) for x in tr if x[1] == side]


def walk(tr, side, t0, n_contracts):
    """VWAP of the first n contracts of our side's taker trades at or after t0 seconds (None if the tape has fewer)."""
    got, cost = 0.0, 0.0
    for t, p, c in sorted(our(tr, side)):
        if t < t0:
            continue
        take = min(c, n_contracts - got)
        got += take
        cost += take * p
        if got >= n_contracts - 1e-9:
            return cost / got, t
    return (cost / got, None) if got > 0 else (None, None)


def pnl(price, win, stake=STAKE):
    n = max(1, int(stake // price))
    fee = float(V.fee(round(price, 4), n))
    cost = n * price + fee
    return (n - cost) if win else -cost, cost, n, fee


def summarize(rows, key):
    """rows: dicts with date, win, and entry prices under `key`; net per $1 at $15 a bet with a day-cluster bootstrap."""
    xs = [r for r in rows if r.get(key) is not None]
    if not xs:
        return {"n": 0}
    items = []
    for r in xs:
        net, cost, n, fee = pnl(r[key], r["win"])
        items.append({"cluster": str(r["date"]), "pnl": net, "cost": cost, "reward": 0.0, "won": r["win"], "ts": 0, "fee": fee})
    net = sum(i["pnl"] for i in items)
    cost = sum(i["cost"] for i in items)
    lo, hi = V.boot_ci(items, 2000, 7)
    days = len({r["date"] for r in xs})
    return {"n": len(xs), "days": days, "win_rate": round(sum(r["win"] for r in xs) / len(xs), 3),
            "avg_price": round(sum(r[key] for r in xs) / len(xs), 3), "net_usd_at_15": round(net, 2),
            "net_per_1": round(net / cost, 4), "ci95": [round(lo, 4), round(hi, 4)], "t": round(V.cluster_t(items), 2),
            "usd_per_week_at_15": round(net / max(days / 5.0, 1e-9), 2)}


def main():
    res = {}
    # ---------------------------------------------------------- 1. the outcome rule
    rule = {}
    for name, s in SER.items():
        mk = load_markets(s)
        bad = tie = n = chain_ok = chain_n = 0
        by_close = {}
        for r in mk:
            by_close[r["close_time"]] = r
        for r in mk:
            if r.get("result") not in ("yes", "no"):
                continue
            fs, ev = r.get("floor_strike"), r.get("expiration_value")
            if fs is None or ev in (None, ""):
                continue
            try:
                fs, ev = float(fs), float(ev)
            except (TypeError, ValueError):
                continue                                   # a few markets carry 'Yes' instead of a number
            n += 1
            want = "yes" if ev >= fs - 1e-12 else "no"
            bad += want != r["result"]
            tie += abs(ev - fs) < 1e-12
            prev = by_close.get(r["open_time"])            # the window that closed when this one opened
            if prev and prev.get("expiration_value") not in (None, ""):
                try:
                    pv = float(prev["expiration_value"])
                except (TypeError, ValueError):
                    pv = None
                if pv is not None:
                    chain_n += 1
                    chain_ok += abs(pv - fs) < 1e-9
        rule[name] = {"markets": n, "result_disagrees_with_rule": bad, "ties": tie, "target_equals_previous_settle": [chain_ok, chain_n]}
    res["outcome_rule"] = rule
    # ---------------------------------------------------------- 2. entry timing
    tape = {name: open_tape(s) for name, s in SER.items()}
    bets = [r for r in csv.DictReader(open(BETS)) if r["leg"] in LEGS]
    rows = []
    for b in bets:
        name, hh, side = LEGS[b["leg"]]
        rec = tape[name].get(b["ticker"])
        if rec is None:
            continue
        tr = rec["tr"]
        o = our(tr, side)
        w1530 = [(p, c) for t, p, c in o if 15 <= t <= 30]
        used_fallback = not w1530
        first20 = next(((p, t) for t, p, c in sorted(o) if t >= 20.0), (None, None))
        walk28, t_done = walk(tr, side, 20.0, int(STAKE // float(b["entry_15_30s"])))
        open_sweep = [(p, c) for t, p, c in o if t <= 1.0]
        before20 = [(t, p) for t, p, c in o if t < 20.0]
        rows.append({"date": b["date"], "leg": b["leg"], "period": b["period"], "win": b["won"] == "1",
                     "study": float(b["entry_15_30s"]), "ask60": float(b["entry_60s"]) if b["entry_60s"] else None,
                     "first_at_20s": first20[0], "first_at_20s_t": first20[1], "walk_28_after_20s": walk28, "walk_done_t": t_done,
                     "open_sweep_vwap": (sum(p * c for p, c in open_sweep) / sum(c for p, c in open_sweep)) if open_sweep else None,
                     "last_before_20s": before20[-1][1] if before20 else None,
                     "fallback_5_45s": used_fallback, "our_contracts_15_30s": sum(c for p, c in w1530),
                     "ticker": b["ticker"], "net_reported": float(b["net_usd_at_15"])})
    res["entry"] = {"bets": len(rows), "fallback_5_45s_used": sum(r["fallback_5_45s"] for r in rows),
                    "no_trade_of_our_side_after_20s": sum(1 for r in rows if r["first_at_20s"] is None),
                    "walk_not_filled_by_45s": sum(1 for r in rows if r["walk_done_t"] is None)}
    # price gaps: what a +20 s bot pays vs the study's entry
    def gap(k):
        g = [r[k] - r["study"] for r in rows if r.get(k) is not None]
        g.sort()
        return {"n": len(g), "mean_c": round(100 * sum(g) / len(g), 2), "median_c": round(100 * g[len(g) // 2], 2),
                "p90_c": round(100 * g[int(0.9 * len(g))], 2)} if g else None
    res["entry"]["gap_vs_study"] = {k: gap(k) for k in ("first_at_20s", "walk_28_after_20s", "ask60", "open_sweep_vwap")}
    # P&L per entry, all / train / test / last 4 weeks
    keys = ("study", "first_at_20s", "walk_28_after_20s", "ask60")
    periods = {"train Aug3-Sep30": lambda r: r["period"] == "train", "test Oct1-Nov18": lambda r: r["period"] == "test",
               "last 4 weeks Oct22-Nov18": lambda r: r["date"] >= "2026-10-22", "last 2 weeks Nov5-Nov18": lambda r: r["date"] >= "2026-11-05",
               "all Aug3-Nov18": lambda r: True}
    res["pnl"] = {p: {k: summarize([r for r in rows if f(r)], k) for k in keys} for p, f in periods.items()}
    # winners vs losers: does the study's entry favour us? (later prices are more informed)
    for k in ("first_at_20s", "walk_28_after_20s"):
        wg = [r[k] - r["study"] for r in rows if r.get(k) is not None and r["win"]]
        lg = [r[k] - r["study"] for r in rows if r.get(k) is not None and not r["win"]]
        res["entry"]["gap_%s_winners_losers_c" % k] = [round(100 * sum(wg) / len(wg), 2), round(100 * sum(lg) / len(lg), 2)]
    # ---------------------------------------------------------- 3. fees: the verifier on every bet as the study booked it
    vrows = []
    for r in rows:
        name, hh, side = LEGS[r["leg"]]
        close_et = dt.datetime.strptime(r["ticker"].split("-")[1], "%y%b%d%H%M").replace(tzinfo=ET)
        open_utc = (close_et - dt.timedelta(minutes=15)).astimezone(UTC)
        vrows.append({"ts": (open_utc + dt.timedelta(seconds=20)).timestamp(), "info_ts": open_utc.timestamp(), "price": r["study"],
                      "contracts": int(STAKE // r["study"]), "outcome": 1 if r["win"] else 0, "event": r["date"], "ticker": r["ticker"],
                      "pnl_reported": r["net_reported"]})
    vv = V.verify(vrows, {"name": "K8 6 metals legs as booked (study entry, $15)"}, rules_tried=384, split="2026-10-01T00:00:00Z", boot=2000)
    res["verify_as_booked"] = {k: vv[k] for k in ("verdict", "reasons", "problem_counts", "all", "first_half", "second_half")}
    print(V.report(vv))
    # the same at the causal +20 s walk price (whole contracts floor(15 / price))
    vrows2 = []
    for r, x in zip(rows, vrows):
        if r["walk_28_after_20s"] is None:
            continue
        y = dict(x)
        y.pop("pnl_reported")
        y["price"] = round(r["walk_28_after_20s"], 4)
        y["contracts"] = int(STAKE // y["price"])
        vrows2.append(y)
    vv2 = V.verify(vrows2, {"name": "K8 at the +20 s walk price"}, rules_tried=384, split="2026-10-01T00:00:00Z", boot=2000)
    res["verify_walk_20s"] = {k: vv2[k] for k in ("verdict", "reasons", "problem_counts", "all", "first_half", "second_half")}
    print(V.report(vv2))
    # ---------------------------------------------------------- 4. month by month (study entry and +20 s walk)
    bym = collections.defaultdict(list)
    for r in rows:
        bym[r["date"][:7]].append(r)
    res["by_month"] = {m: {k: summarize(v, k) for k in ("study", "walk_28_after_20s")} for m, v in sorted(bym.items())}
    byw = collections.defaultdict(list)
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        byw[str(d - dt.timedelta(days=d.weekday()))].append(r)
    res["by_week_study"] = {w: (len(v), round(sum(x["win"] for x in v) / len(v), 2), summarize(v, "study")["net_usd_at_15"]) for w, v in sorted(byw.items())}
    res["by_leg_last4w"] = {leg: {k: summarize([r for r in rows if r["leg"] == leg and r["date"] >= "2026-10-22"], k) for k in ("study", "walk_28_after_20s")} for leg in LEGS}
    res["by_leg_all"] = {leg: summarize([r for r in rows if r["leg"] == leg], "study") for leg in LEGS}
    # ---------------------------------------------------------- 5. clocks: the one week the UK and US clocks differed
    clocks = {}
    for name, s in SER.items():
        mk = load_markets(s)
        idx = {(r["event_ticker"].split("-")[1][:7], r["event_ticker"].split("-")[1][7:11]): r for r in mk if r.get("result") in ("yes", "no")}
        rowsc = []
        for d in ("26OCT26", "26OCT27", "26OCT28", "26OCT29", "26OCT30"):
            a, b = idx.get((d, "0530")), idx.get((d, "0630"))
            rowsc.append({"day": d, "0515-0530ET_down": None if not a else a["result"] == "no", "0615-0630ET_down": None if not b else b["result"] == "no"})
        # all other weekdays Aug 3 - Nov 18: the same two windows
        other = {"0530": [0, 0], "0630": [0, 0]}
        for (d, hh), r in idx.items():
            if hh not in other:
                continue
            day = dt.datetime.strptime(d, "%y%b%d").date()
            if day.weekday() >= 5 or not (dt.date(2026, 8, 3) <= day <= dt.date(2026, 11, 18)) or dt.date(2026, 10, 26) <= day <= dt.date(2026, 10, 30):
                continue
            other[hh][0] += r["result"] == "no"
            other[hh][1] += 1
        clocks[name] = {"oct26_30": rowsc, "other_days_down": {k: "%d/%d" % tuple(v) for k, v in other.items()}}
    # the coming weeks: when is 10:30 London not 05:30 ET?
    mism = []
    d = dt.date(2026, 11, 19)
    while d <= dt.date(2027, 4, 30):
        if d.weekday() < 5:
            lon = dt.datetime(d.year, d.month, d.day, 10, 30, tzinfo=LON).astimezone(ET)
            if lon.strftime("%H:%M") != "05:30":
                mism.append(str(d))
        d += dt.timedelta(days=1)
    clocks["weekdays_until_2027_04_30_where_1030_London_is_not_0530_ET"] = [mism[0], mism[-1], len(mism)] if mism else []
    res["clocks"] = clocks
    # ---------------------------------------------------------- 6. luck: the best 6 of all quarter hours if every one were a coin flip
    ups = collections.defaultdict(list)
    for name, s in SER.items():
        for r in load_markets(s):
            if r.get("result") not in ("yes", "no"):
                continue
            code = r["event_ticker"].split("-")[1]
            day = dt.datetime.strptime(code[:7], "%y%b%d").date()
            if day.weekday() >= 5 or not (dt.date(2026, 8, 3) <= day <= dt.date(2026, 11, 18)):
                continue
            ups[(name, code[7:11])].append(r["result"] == "yes")
    wins = {k: v for k, v in ups.items() if len(v) >= 60}
    obs = []
    for (name, hh), v in wins.items():
        p = sum(v) / len(v)
        obs.append((max(p, 1 - p), name, hh, "up" if p >= 0.5 else "down", len(v), round((p - 0.5) / math.sqrt(0.25 / len(v)), 2)))
    obs.sort(reverse=True)
    rnd = random.Random(11)
    top6 = []
    for _ in range(2000):
        sim = []
        for k, v in wins.items():
            n = len(v)
            h = sum(rnd.random() < 0.5 for _ in range(n)) / n
            sim.append(max(h, 1 - h))
        sim.sort(reverse=True)
        top6.append(sum(sim[:6]) / 6)
    top6.sort()
    friend = [x for x in obs if (x[1], x[2]) in {(v[0], v[1]) for v in LEGS.values()}]
    res["luck"] = {"windows_scanned": len(wins), "sides": 2 * len(wins),
                   "observed_top10": [(round(a, 3), b, c, d, e, f) for a, b, c, d, e, f in obs[:10]],
                   "friend_legs_full_sample": [(round(a, 3), b, c, d, e, f) for a, b, c, d, e, f in friend],
                   "friend_legs_avg_win": round(sum(x[0] for x in friend) / len(friend), 3),
                   "coin_flip_top6_avg_win": {"median": round(top6[len(top6) // 2], 3), "p95": round(top6[int(0.95 * len(top6))], 3),
                                              "p99": round(top6[int(0.99 * len(top6))], 3)},
                   "bonferroni_z_bar_5pct_two_sided": round(V.bar_t(2 * len(wins)), 2)}
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    # ---- print
    print("OUTCOME RULE", json.dumps(res["outcome_rule"]))
    print("ENTRY", json.dumps(res["entry"]))
    for p, v in res["pnl"].items():
        print("%-26s" % p, {k: (x.get("n"), x.get("win_rate"), x.get("avg_price"), x.get("net_per_1"), x.get("ci95")) for k, x in v.items()})
    for m, v in res["by_month"].items():
        print("month", m, {k: (x["n"], x["win_rate"], x["avg_price"], x["net_per_1"], x["ci95"]) for k, x in v.items()})
    print("weeks", res["by_week_study"])
    for leg, v in res["by_leg_last4w"].items():
        print("last4w", leg, {k: (x.get("n"), x.get("win_rate"), x.get("net_per_1"), x.get("ci95")) for k, x in v.items()})
    print("CLOCKS", json.dumps(res["clocks"]))
    print("LUCK", json.dumps(res["luck"]))


if __name__ == "__main__":
    main()
