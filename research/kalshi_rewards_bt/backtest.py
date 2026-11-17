#!/usr/bin/env python3
"""Kalshi rewards backtest, step 3: the SAME rule as tools/kalshi_rewards_paper.py, replayed on the last 30 days of the
public tape (cache/ from harvest.py, depth estimate from depth_profiles.json). Offline, no network, never an order.

Rule (per market, while a liquidity program is active, and until PULL hours before the market's close):
  quote   one bid of Q = Target/5 contracts on BOTH sides at the reward reference price: YES at (yes bid - t ticks), NO at
          (1 - yes ask - t ticks); the yes bid / ask are the last 1-minute candle closes (the book as it was, no look-ahead);
          t = the measured ticks between the best bid and the reference (median per series and price bucket, usually 0).
  queue   a new or moved order joins the BACK of the queue: ahead = QMULT x the measured depth at prices >= the reference.
  fills   taker trades at my price eat the queue first, then fill me; a trade THROUGH my price fills all that is left.
          (a trade below my price means nothing is left ahead of me at my price: its size fills me). A fully filled side is
          refilled at the next quote update (back of the queue again).
  reward  pool $/s x seconds x (my score) / (everyone's score), everyone's = the measured others' score + mine, x the series'
          measured valid-snapshot share. Others' score and queue are drawn jointly from today's snapshots (4 representative
          books per bucket: the 12.5 / 37.5 / 62.5 / 87.5 percentiles by score; the result is their average).
  P&L     each fill: $1 or $0 at settlement (mark at today's mid when not settled yet) - price - maker fee (only where the
          series' fee type has maker fees; --fee-all charges 0.0175 p(1-p) everywhere). Booked on the fill's day.
Days are midnight-ET days 2026-10-18 .. 2026-11-16; halves = the first 15 days and the last 15 days.

    python research/kalshi_rewards_bt/backtest.py            -> results.json + tables"""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harvest import END, SERIES  # noqa: E402

DAYS = 30
T0 = END - DAYS * 86400
HALF = T0 + 15 * 86400
FEE_ALL = "--fee-all" in sys.argv
PULLS = [0, 1, 3, 6, 12, 24, 48]
QMULTS = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
QS = (0.125, 0.375, 0.625, 0.875)


def T(s):
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def F(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def bucket(p):
    return "cheap" if p < 0.15 else "rich" if p > 0.85 else "mid"


def profiles():
    d = json.load(open(os.path.join(HERE, "depth_profiles.json")))
    out = {}
    for s, pr in d["profiles"].items():
        obs = [o for o in d["obs"] if o["s"] == s]
        bk = collections.defaultdict(list)
        allx = []
        for o in obs:
            for sd in ("yes", "no"):
                x = o[sd]
                if x and x.get("ref") is not None:
                    bk[bucket(x["ref"])].append(x)
                    allx.append(x)
        rep = {}
        for b in ("cheap", "mid", "rich"):
            xs = sorted(bk.get(b) or allx, key=lambda x: x["score_t"])
            if not xs:
                continue
            rep[b] = [{"ahead_t": xs[min(len(xs) - 1, int(q * len(xs)))]["ahead_t"], "score_t": xs[min(len(xs) - 1, int(q * len(xs)))]["score_t"],
                       "ticks": sorted(x["ticks"] for x in xs)[len(xs) // 2]} for q in QS]
        out[s] = {"valid": pr["valid_pct"] / 100.0, "rep": rep}
    return out


def maker_fee(p, n, fee_type):
    if not FEE_ALL and "maker" not in str(fee_type or ""):
        return 0.0
    return 0.0175 * n * p * (1 - p)


def sim(m, v, prof, fee_type, r, qmult, pull_h, acc, jump_c=0):
    """one market, one representative book r: adds day buckets to acc[day] = [reward, fill_pnl, capital_seconds, fills, fill_cost]."""
    info = v["info"]
    res = info.get("result") or ""
    close = T(info["close_time"]) if info.get("close_time") else END + 86400 * 365
    yb, ya = F(info.get("yes_bid_dollars")), F(info.get("yes_ask_dollars"))
    mid_now = (yb + ya) / 2 if yb is not None and ya is not None else F(info.get("last_price_dollars")) or 0.5
    val_yes = 1.0 if res == "yes" else 0.0 if res == "no" else mid_now
    progs = sorted(v["programs"], key=lambda p: p["start"])
    stop = min(END, close - pull_h * 3600)
    windows = [(max(p["start"], T0), min(p["end"], stop), p) for p in progs if min(p["end"], stop) > max(p["start"], T0)]
    if not windows or not prof["rep"]:
        return
    cand = [c for c in v["candles"] if c[0] <= END]
    cts = [c[0] for c in cand]
    trades = [x for x in v["trades"] if T0 - 3600 <= x[0] <= END]
    # event times: quote changes + trades + window edges
    ev = set()
    last = None
    for c in cand:
        q = (c[1], c[2])
        if q != last:
            ev.add(c[0])
            last = q
    for a, b, _ in windows:
        ev.add(a)
        ev.add(b)
    ev = sorted(e for e in ev if windows[0][0] <= e <= windows[-1][1])
    if not ev:
        return
    sides = {sd: {"p": None, "q": 0.0, "queue": 0.0} for sd in ("yes", "no")}
    Q = None
    ti = bisect.bisect_left([x[0] for x in trades], ev[0])
    held = [0.0]                       # $ in filled contracts (parked until settlement)

    def prog_at(t):
        for a, b, p in windows:
            if a <= t < b:
                return p
        return None

    for k, t in enumerate(ev):
        nxt = ev[k + 1] if k + 1 < len(ev) else None
        p = prog_at(t)
        # the book as of t (last candle closed at or before t)
        ci = bisect.bisect_right(cts, t) - 1
        bid = F(cand[ci][1]) if ci >= 0 else None
        ask = F(cand[ci][2]) if ci >= 0 else None
        jumped = False
        if jump_c and p is not None and bid is not None and ask is not None:
            cj = bisect.bisect_right(cts, t - 3600) - 1
            b0, a0 = (F(cand[cj][1]), F(cand[cj][2])) if cj >= 0 else (None, None)
            jumped = b0 is not None and a0 is not None and abs((bid + ask) / 2 - (b0 + a0) / 2) >= jump_c / 100 - 1e-9
        if p is None or jumped:
            for sd in sides.values():
                sd.update(p=None, q=0.0, queue=0.0)
        else:
            tgt = p["target"]
            Q = tgt / 5
            for sd, px in (("yes", bid), ("no", (1 - ask) if ask is not None else None)):
                o = sides[sd]
                if px is None or px <= 0 or px >= 1:
                    o.update(p=None, q=0.0, queue=0.0)
                    continue
                rp = prof["rep"].get(bucket(px)) or next(iter(prof["rep"].values()))
                rp = rp[r]
                ref = round(px - rp["ticks"] * 0.01, 2)
                if ref < 0.01:
                    o.update(p=None, q=0.0, queue=0.0)
                    continue
                if o["p"] is None or abs(o["p"] - ref) > 1e-9 or o["q"] <= 1e-9:
                    o.update(p=ref, q=Q, queue=qmult * rp["ahead_t"] * tgt, rp=rp)
        if nxt is None:
            break
        dur = nxt - t
        day = int((t - T0) // 86400)
        a = acc[day]
        # reward over [t, nxt) with the orders as they are now (fills inside the gap shrink q only from the next event)
        if p is not None and sides["yes"]["p"] is not None and sides["no"]["p"] is not None:
            tgt = p["target"]
            my = sides["yes"]["q"] + sides["no"]["q"]
            tot = my + sides["yes"]["rp"]["score_t"] * tgt + sides["no"]["rp"]["score_t"] * tgt
            usd_s = p["usd"] / max(p["end"] - p["start"], 1)
            if tot > 0:
                a[0] += usd_s * dur * my / tot * prof["valid"]
        cap = sum((o["p"] or 0) * o["q"] for o in sides.values()) + held[0]
        a[2] += cap * dur
        # trades in [t, nxt)
        while ti < len(trades) and trades[ti][0] < nxt:
            tt, side, py, n = trades[ti]
            ti += 1
            if tt < t:
                continue
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
                if px < o["p"] - 1e-9:          # through my price: the queue at my price is gone, this size would have hit me
                    o["queue"] = 0.0
                    got = min(n, o["q"])
                else:
                    eat = min(n, o["queue"])
                    o["queue"] -= eat
                    got = min(n - eat, o["q"])
                if got <= 1e-9:
                    continue
                o["q"] -= got
                held[0] += got * o["p"]
                win = val_yes if sd == "yes" else 1 - val_yes
                fee = maker_fee(o["p"], got, fee_type)
                dd = acc[int((tt - T0) // 86400)]
                dd[1] += got * (win - o["p"]) - fee
                dd[3] += 1
                dd[4] += got * o["p"]


_DATA = {}


def run_series(s, prof, qmult, pull_h, jump_c=0):
    d = _DATA.get(s) or _DATA.setdefault(s, json.load(gzip.open(os.path.join(HERE, "cache", s + ".json.gz"), "rt")))
    acc = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0, 0.0])
    nrep = len(QS)
    for m, v in d["markets"].items():
        for r in range(nrep):
            sim(m, v, prof, d["fee_type"], r, qmult, pull_h, acc, jump_c)
    for a in acc.values():          # average over the representative books
        for i in range(5):
            a[i] /= nrep
    return d, acc


def halves(acc):
    out = {}
    for name, lo, hi in (("first15", 0, 15), ("last15", 15, 30), ("all30", 0, 30)):
        rows = [acc[k] for k in range(lo, hi) if k in acc]
        rew = sum(a[0] for a in rows)
        fil = sum(a[1] for a in rows)
        capd = sum(a[2] for a in rows) / 86400
        out[name] = {"reward": rew, "fill_pnl": fil, "net": rew + fil, "capital_days": capd, "fills": sum(a[3] for a in rows),
                     "filled_usd": sum(a[4] for a in rows),
                     "net_per100_day": 100 * (rew + fil) / capd if capd > 0 else None,
                     "reward_per100_day": 100 * rew / capd if capd > 0 else None,
                     "fill_per100_day": 100 * fil / capd if capd > 0 else None,
                     "avg_capital": capd / (hi - lo)}
    return out


JUMPS = [0, 3, 5, 10]


def variants():
    out = [("queue", str(q), (q, 0, 0)) for q in QMULTS]
    out += [("pull", str(h), (1.0, h, 0)) for h in PULLS]
    out += [("jump", str(j), (1.0, 0, j)) for j in JUMPS]
    return out


def pooled(accs):
    acc = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0, 0.0])
    for a in accs:
        for k, row in a.items():
            for i in range(5):
                acc[k][i] += row[i]
    return halves(acc)


def fmt(h):
    f = lambda x: "%+6.2f" % x if x is not None else "   n/a"     # noqa: E731
    return "%s / %s" % (f(h["first15"]["net_per100_day"]), f(h["last15"]["net_per100_day"]))


def main():
    prof = profiles()
    series = [s for s in SERIES if os.path.exists(os.path.join(HERE, "cache", s + ".json.gz")) and s in prof]
    res = {"rule": "tools/kalshi_rewards_paper.py rule on the public tape", "window": [T0, END], "fee_all": FEE_ALL,
           "units": "net $ per $100 parked per day (parked = resting bids + filled contracts)", "series": {}, "pooled": {}}
    keep = collections.defaultdict(list)
    for s in series:
        R = {"queue": {}, "pull": {}, "jump": {}}
        for grp, key, (qm, ph, jc) in variants():
            d, acc = run_series(s, prof[s], qm, ph, jc)
            R[grp][key] = halves(acc)
            keep[(grp, key)].append(acc)
        R.update(fee_type=d["fee_type"], markets=len(d["markets"]), markets_in_series=d["n_markets"], valid=prof[s]["valid"],
                 pool_window=d["pool_usd_window"])
        res["series"][s] = R
        b = R["queue"]["1.0"]
        print("%-20s mkts %2d/%4d  base %s   reward %s  fills %s  n fills %d/%d" % (
            s, len(d["markets"]), d["n_markets"], fmt(b),
            "%+.2f/%+.2f" % (b["first15"]["reward_per100_day"] or 0, b["last15"]["reward_per100_day"] or 0),
            "%+.2f/%+.2f" % (b["first15"]["fill_per100_day"] or 0, b["last15"]["fill_per100_day"] or 0), b["first15"]["fills"], b["last15"]["fills"]), flush=True)
        for grp in ("queue", "pull", "jump"):
            print("   %-5s" % grp, "  ".join("%s:%s" % (k, fmt(v)) for k, v in R[grp].items()))
    for (grp, key), accs in keep.items():
        res["pooled"].setdefault(grp, {})[key] = pooled(accs)
    print("POOLED")
    for grp in ("queue", "pull", "jump"):
        print("   %-5s" % grp, "  ".join("%s:%s" % (k, fmt(v)) for k, v in res["pooled"][grp].items()))
    # the owner table: base rule (queue x1, no pull) and the guarded rule (no quotes for an hour after a 5c move), per series,
    # with the half-share sensitivity (others' depth twice what today's books show = about half the reward)
    print("\nper $100 parked per day: base | half share | 5c guard   (first 15 days / last 15 days)")
    for s in list(res["series"]) + ["POOLED"]:
        R = res["pooled"] if s == "POOLED" else res["series"][s]
        b, g = R["queue"]["1.0"], R["jump"]["5"]
        hs = {h: ((b[h]["reward_per100_day"] or 0) / 2 + (b[h]["fill_per100_day"] or 0)) if b[h]["capital_days"] else None for h in ("first15", "last15")}
        R["half_share"] = hs
        print("%-20s %s | %s | %s   reward %+.2f/%+.2f  fills %+.2f/%+.2f" % (s, fmt(b), "%s / %s" % tuple("%+6.2f" % x if x is not None else "   n/a" for x in (hs["first15"], hs["last15"])),
              fmt(g), b["first15"]["reward_per100_day"] or 0, b["last15"]["reward_per100_day"] or 0, b["first15"]["fill_per100_day"] or 0, b["last15"]["fill_per100_day"] or 0))
    json.dump(res, open(os.path.join(HERE, "results%s.json" % ("_feeall" if FEE_ALL else "")), "w"), indent=1)
    if not FEE_ALL:                    # the Kalshi page's backtest line (tools/kalshi_rewards_paper.py --site-copy reads it)
        P = res["pooled"]
        b, g = P["queue"]["1.0"], P["jump"]["5"]
        f1, l1 = b["first15"]["net_per100_day"], b["last15"]["net_per100_day"]
        g1, gl = g["first15"]["net_per100_day"], g["last15"]["net_per100_day"]
        u = lambda x: ("+" if x >= 0 else "-") + "$%.2f" % abs(x)      # noqa: E731
        verdict = "positive in both halves" if min(f1, l1) > 0 else "not positive in both halves"
        json.dump({"date": "2026-11-17", "per100_first15": round(f1, 2), "per100_last15": round(l1, 2),
                   "guard_first15": round(g1, 2), "guard_last15": round(gl, 2), "verdict": verdict, "series": len(res["series"]),
                   "text": "%s / %s a day per $100 parked (first / last 15 days, %d series); with the 5c pause %s / %s. %s."
                           % (u(f1), u(l1), len(res["series"]), u(g1), u(gl), verdict[0].upper() + verdict[1:])},
                  open(os.path.join(HERE, "headline.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
