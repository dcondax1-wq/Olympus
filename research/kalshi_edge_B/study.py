#!/usr/bin/env python3
"""Team B Kalshi edge study: structure / behaviour tests on settled BTC markets (public data, fees in, walk-forward).

    python research/kalshi_edge_B/study.py            # runs everything, writes results.json

Per-contract profit of a taker buy at price p (dollars): win - p - 0.07*p*(1-p).  'edge' below = mean of that, per $1 contract
(so 0.01 = one cent per contract; ROI = edge / mean cost).  Splits are by time, never random:
train = first 55% of close times, val = next 20%, test = last 25% (touched once, after the rule was frozen).
"""
import json, math, os, sys, datetime as dt
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *

HERE = os.path.dirname(os.path.abspath(__file__))
R = {"notes": [], "tests_run": 0}


def prep(name):
    rows = load(name)
    for r in rows:
        r["q"] = {int(c[0]): (c[1], c[2], c[3]) for c in (r.get("c") or [])}
        r["win"] = 1 if r["res"] == "yes" else 0
    rows.sort(key=lambda r: r["close"])
    return rows


def quote(r, tau):
    """(yes_bid, yes_ask) at tau minutes before close, or None when empty / crossed / degenerate."""
    q = r["q"].get(int(r["close"] - tau * 60))
    if not q or q[0] is None or q[1] is None:
        return None
    b, a = q[0], q[1]
    if not (0 < a <= 1 and 0 <= b < 1 and a >= b):
        return None
    return b, a


def split(rows):
    n = len(rows)
    a, b = int(n * 0.55), int(n * 0.75)
    return {"train": rows[:a], "val": rows[a:b], "test": rows[b:]}


def day(r):
    if "15M" not in r["t"]:
        return r["e"]  # hourly ladders: strikes of one hour share one outcome path -> cluster by event
    return dt.datetime.fromtimestamp(r["close"], dt.timezone.utc).strftime("%m-%d")


def summarise(profits, cost, wins, groups):
    n = len(profits)
    if n == 0:
        return {"n": 0}
    m, lo, hi = cluster_ci(profits, groups)
    wl, wh = wilson(sum(wins), n)
    mc = sum(cost) / n
    mf = float(np.mean([fee(c) for c in cost]))
    # win-rate based interval on the same edge (honest when almost every bet wins and the day-bootstrap has no variance)
    wlo, whi = wl - mc - mf, wh - mc - mf
    return {"n": n, "clusters": len(set(groups)), "edge": round(m, 4), "ci": [round(min(lo, wlo), 4), round(max(hi, whi), 4)], "ci_days": [round(lo, 4), round(hi, 4)],
            "ci_wilson": [round(wlo, 4), round(whi, 4)], "roi": round(m / mc, 4),
            "win": round(sum(wins) / n, 4), "win_wilson": [round(wl, 4), round(wh, 4)], "avg_price": round(mc, 4)}


def buy(r, side, p):
    w = r["win"] if side == "yes" else 1 - r["win"]
    return w - p - fee(p), w


# ----------------------------------------------------------------------------- 4) late-expiry favourites (what the bot does)
def favourites(rows, label, taus, bands):
    out = []
    for tau in taus:
        for lo, hi in bands:
            prof, cost, wins, grp, tm = [], [], [], [], []
            for r in rows:
                qq = quote(r, tau)
                if not qq:
                    continue
                b, a = qq
                # favourite side only: yes if bid>=.5 else no
                if b >= 0.5:
                    side, p = "yes", a
                else:
                    side, p = "no", 1 - b
                if not (lo <= p < hi):
                    continue
                pr, w = buy(r, side, p)
                prof.append(pr); cost.append(p); wins.append(w); grp.append(day(r)); tm.append(r["close"])
            R["tests_run"] += 1
            sp = split_arrays(prof, cost, wins, grp, tm, rows)
            out.append({"series": label, "tau_min": tau, "band": "%.2f-%.2f" % (lo, hi), "all": summarise(prof, cost, wins, grp), **sp})
    return out


def split_arrays(prof, cost, wins, grp, tm, rows):
    n = len(rows)
    t1, t2 = rows[int(n * 0.55)]["close"], rows[int(n * 0.75)]["close"]
    res = {}
    for nm, sel in (("train", lambda t: t < t1), ("val", lambda t: t1 <= t < t2), ("test", lambda t: t >= t2)):
        idx = [i for i, t in enumerate(tm) if sel(t)]
        res[nm] = summarise([prof[i] for i in idx], [cost[i] for i in idx], [wins[i] for i in idx], [grp[i] for i in idx])
    return res


# ----------------------------------------------------------------------------- 2) lognormal vol model vs quoted price
def model_prob(S, K, sig_min, tau, sig_b, kv):
    sd = math.sqrt((kv * sig_min) ** 2 * max(tau - 0.5, 0.25) + sig_b ** 2)
    return ncdf(math.log(S / K) / sd)


def basis_sigma(rows, spot):
    d = []
    for r in rows:
        S = spot.at(r["close"])
        if S and r["ev"]:
            d.append(math.log(r["ev"] / S))
    return float(np.std(d)) if len(d) > 20 else 0.0004, len(d)


def model_scan(rows, spot, label, taus, margins, kvs, sig_b):
    """every (tau, margin, kv): buy whichever side has model prob - ask - fee > margin."""
    grid = []
    t_all = [r["close"] for r in rows]
    n = len(rows)
    t1, t2 = rows[int(n * 0.55)]["close"], rows[int(n * 0.75)]["close"]
    for tau in taus:
        pre = []
        for r in rows:
            qq = quote(r, tau)
            if not qq or r["k"] is None:
                continue
            ts = r["close"] - tau * 60
            S, sg = spot.at(ts), spot.vol(ts)
            if not S or not sg:
                continue
            pre.append((r, qq, S, sg))
        for kv in kvs:
            pm = [(r, qq, model_prob(S, r["k"], sg, tau, sig_b, kv)) for r, qq, S, sg in pre]
            for mg in margins:
                prof, cost, wins, grp, tm = [], [], [], [], []
                for r, (b, a), p in pm:
                    ey, en = p - a - fee(a), (1 - p) - (1 - b) - fee(1 - b)
                    if ey >= en and ey > mg:
                        side, pr_ = "yes", a
                    elif en > mg:
                        side, pr_ = "no", 1 - b
                    else:
                        continue
                    pr, w = buy(r, side, pr_)
                    prof.append(pr); cost.append(pr_); wins.append(w); grp.append(day(r)); tm.append(r["close"])
                R["tests_run"] += 1
                sp = split_arrays(prof, cost, wins, grp, tm, rows)
                grid.append({"series": label, "tau_min": tau, "kv": kv, "margin": mg, "all": summarise(prof, cost, wins, grp), **sp})
    return grid


def calib_model(rows, spot, label, tau, sig_b):
    """Brier score of the lognormal model vs the market mid at tau min before close (test block only)."""
    sp = split(rows)["test"]
    bm, bk, n = 0.0, 0.0, 0
    for r in sp:
        qq = quote(r, tau)
        ts = r["close"] - tau * 60
        S, sg = spot.at(ts), spot.vol(ts)
        if not qq or not S or not sg or r["k"] is None:
            continue
        p = model_prob(S, r["k"], sg, tau, sig_b, 1.0)
        mid = (qq[0] + qq[1]) / 2
        bm += (p - r["win"]) ** 2; bk += (mid - r["win"]) ** 2; n += 1
    return {"series": label, "tau_min": tau, "n_test": n, "brier_model": round(bm / max(n, 1), 4), "brier_market_mid": round(bk / max(n, 1), 4)}


# ----------------------------------------------------------------------------- 1) strike ladder consistency (hourly)
def ladder(rows, taus):
    ev = {}
    for r in rows:
        ev.setdefault(r["e"], []).append(r)
    out = []
    for tau in taus:
        n_ev = n_pairs = n_viol = n_viol_fee = 0
        gaps, profits, grp = [], [], []
        for e, ms in ev.items():
            qs = []
            for r in ms:
                qq = quote(r, tau)
                if qq:
                    qs.append((r["k"], qq[0], qq[1], r))
            if len(qs) < 3:
                continue
            n_ev += 1
            qs.sort(key=lambda x: x[0])
            for i in range(len(qs)):
                for j in range(i + 1, len(qs)):
                    k1, b1, a1, r1 = qs[i]
                    k2, b2, a2, r2 = qs[j]
                    n_pairs += 1
                    # P(>k1) must be >= P(>k2): buy yes@k1 (ask a1), buy no@k2 (cost 1-b2). Payoff >= 1 always.
                    cost = a1 + (1 - b2)
                    if cost < 1:
                        n_viol += 1
                        net = 1 - cost - fee(a1) - fee(1 - b2)
                        # realised payoff of the pair (>=1 by construction; 2 when k1<S<=k2)
                        pay = r1["win"] + (1 - r2["win"])
                        gaps.append(1 - cost)
                        if net > 0:
                            n_viol_fee += 1
                            profits.append(pay - cost - fee(a1) - fee(1 - b2)); grp.append(e)
        out.append({"tau_min": tau, "events": n_ev, "pairs": n_pairs, "violations_gross": n_viol, "violations_after_fees": n_viol_fee,
                    "avg_gross_gap": round(float(np.mean(gaps)), 4) if gaps else None,
                    "after_fee_mean_profit_per_pair": round(float(np.mean(profits)), 4) if profits else None,
                    "after_fee_ci": [round(x, 4) for x in cluster_ci(profits, grp)[1:]] if profits else None,
                    "after_fee_events": len(set(grp))})
    return out


# ----------------------------------------------------------------------------- 3) maker vs taker
def maker(rows, label, taus):
    """Rest a buy on the favourite at its bid.  Unconditional (assumes fill) vs conditional on a fill proxy
    (the next minute's ask close fell to our bid or lower).  Maker fee 0.0175*p*(1-p).  The gap = adverse selection."""
    out = []
    for tau in taus:
        rec = {"unfilled": 0}
        U, F = [], []
        spread = []
        for r in rows:
            qq = quote(r, tau)
            nxt = quote(r, tau - 1) if tau > 1 else None
            if not qq:
                continue
            b, a = qq
            if b >= 0.5:
                side, price = "yes", b
                nxt_ask = nxt[1] if nxt else None
            else:
                side, price = "no", 1 - a
                nxt_ask = (1 - nxt[0]) if nxt else None  # no-ask
            if not (0.6 <= price < 0.99):
                continue
            spread.append(a - b)
            w = r["win"] if side == "yes" else 1 - r["win"]
            pr = w - price - fee(price, 0.0175)
            U.append(pr)
            if nxt_ask is not None and nxt_ask <= price + 1e-9:
                F.append(pr)
        # taker comparison on the same markets: cross the spread
        T = []
        for r in rows:
            qq = quote(r, tau)
            if not qq:
                continue
            b, a = qq
            side, price = ("yes", a) if b >= 0.5 else ("no", 1 - b)
            if not (0.6 <= price < 0.995):
                continue
            T.append(buy(r, side, price)[0])
        R["tests_run"] += 1
        out.append({"series": label, "tau_min": tau, "n": len(U), "mean_spread": round(float(np.mean(spread)), 4) if spread else None,
                    "maker_if_always_filled": round(float(np.mean(U)), 4) if U else None,
                    "maker_filled_proxy_n": len(F), "maker_when_filled_proxy": round(float(np.mean(F)), 4) if F else None,
                    "taker_same_markets_n": len(T), "taker": round(float(np.mean(T)), 4) if T else None})
    return out


# ----------------------------------------------------------------------------- time of day / events (descriptive, flagged exploratory)
def by_hour(rows, spot, sig_b, tau=3, kv=1.0, mg=0.04):
    H = {}
    for r in rows:
        qq = quote(r, tau)
        ts = r["close"] - tau * 60
        S, sg = spot.at(ts), spot.vol(ts)
        if not qq or not S or not sg or r["k"] is None:
            continue
        p = model_prob(S, r["k"], sg, tau, sig_b, kv)
        b, a = qq
        ey, en = p - a - fee(a), (1 - p) - (1 - b) - fee(1 - b)
        if ey >= en and ey > mg:
            side, pr_ = "yes", a
        elif en > mg:
            side, pr_ = "no", 1 - b
        else:
            continue
        pr, w = buy(r, side, pr_)
        h = dt.datetime.fromtimestamp(r["close"], dt.timezone.utc).hour
        H.setdefault(h, []).append(pr)
    return {str(h): {"n": len(v), "edge": round(float(np.mean(v)), 4)} for h, v in sorted(H.items())}


def main():
    spot = Spot("BTC")
    m15 = prep("KXBTC15M.json.gz")
    R["data"] = {"btc15m_markets": len(m15), "first": m15[0]["close"], "last": m15[-1]["close"]}
    sig_b, nb = basis_sigma(m15, spot)
    R["basis_sigma"] = {"value": round(sig_b, 6), "n": nb, "meaning": "std of ln(BRTI settlement / Coinbase close) at expiry"}
    R["favourites_15m"] = favourites(m15, "KXBTC15M", [1, 2, 3, 5, 8], [(0.90, 0.95), (0.95, 0.97), (0.97, 0.99), (0.99, 1.01)])
    R["model_15m_grid"] = model_scan(m15, spot, "KXBTC15M", [2, 3, 5, 8], [0.0, 0.02, 0.04, 0.06, 0.10], [0.9, 1.0, 1.2], sig_b)
    R["model_calib_15m"] = [calib_model(m15, spot, "KXBTC15M", t, sig_b) for t in (2, 3, 5, 8)]
    R["maker_15m"] = maker(m15, "KXBTC15M", [2, 3, 5])
    R["hour_15m"] = by_hour(m15, spot, sig_b)
    hp = os.path.join(HERE, "data", "KXBTCD.json.gz")
    if os.path.exists(hp):
        hr = prep("KXBTCD.json.gz")
        R["data"]["btcd_markets"] = len(hr)
        R["data"]["btcd_events"] = len({r["e"] for r in hr})
        R["ladder_hourly"] = ladder(hr, [1, 2, 3, 5, 10, 20])
        R["favourites_hourly"] = favourites(hr, "KXBTCD", [2, 5, 10], [(0.90, 0.95), (0.95, 0.97), (0.97, 0.99), (0.99, 1.01)])
        R["model_hourly_grid"] = model_scan(hr, spot, "KXBTCD", [3, 5, 10, 20], [0.0, 0.02, 0.04, 0.06, 0.10], [0.9, 1.0, 1.2], sig_b)
        R["model_calib_hourly"] = [calib_model(hr, spot, "KXBTCD", t, sig_b) for t in (3, 5, 10, 20)]
        R["maker_hourly"] = maker(hr, "KXBTCD", [3, 5, 10])
    json.dump(R, open(os.path.join(HERE, "results.json"), "w"), indent=1)
    print("tests_run", R["tests_run"])


if __name__ == "__main__":
    main()
