#!/usr/bin/env python3
"""K6 study 2: Kalshi Fed-decision markets (KXFED 'upper bound above X after the meeting', KXFEDDECISION 'hike / hold /
cut') against a probability implied by OFFICIAL public rates: the 1-month Treasury bill (constant maturity, FRED DGS1MO
= Treasury's curve), the effective fed funds rate (NY Fed EFFR, known with a one-day lag) and the target range.

CME fed funds / SOFR futures history is not free (no official free archive; FedWatch history is paid), so the bill is the
closest free market-implied rate. Implied change at the meeting (day D, k calendar days after the evening d):
    avg 1-month rate = r_now + delta x (30 - k) / 30   ->   delta = (bill_1m - spread - r_now) x 30 / (30 - k)
spread = median(bill_1m - EFFR) over the previous 120 business days that had no meeting in the next 31 days.
P(change >= c) = Phi((delta - c + 0.125) / SIGMA), SIGMA fitted on meetings before 2025 (older half), evenings with
k <= 20 days only. Trading margin fixed on the older half; meetings from 2025 on are the held-out half.
Also a model-free pre-registered rule: buy NO on any Fed outcome whose YES is priced 10c or less, last 10 days.

    python research/kalshi_edge_K6/fed.py      # -> results_fed.json
"""
import bisect, datetime as dt, gzip, json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("K6_OFFLINE", "1")
import kk6
import yields as Yl

HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = "2025-01-01"


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def load():
    rows = []
    for s in ("KXFED", "KXFEDDECISION"):
        fn = os.path.join(kk6.DATA, f"q_{s}.jsonl.gz")
        if not os.path.exists(fn):
            continue
        for line in gzip.open(fn, "rt"):
            r = json.loads(line)
            r["series"] = s
            if r["c"]:
                rows.append(r)
    return rows


def change_needed(r, U0):
    """(lo, hi) of the policy change (in %, multiples of 0.25) that makes this market YES."""
    if r["series"] == "KXFED":           # upper bound after the meeting > fs  <=>  change >= fs - U0 + 0.25
        if r["st"] == "greater":
            return (round(r["fs"] - U0 + 0.25, 2), 9)
        if r["st"] == "less":
            return (-9, round(r["cs"] - U0 - 0.25, 2))
        return None
    code = r["t"].split("-")[-1]
    return {"H26": (0.5, 9), "H25": (0.25, 0.25), "H0": (0, 0), "C25": (-0.25, -0.25), "C26": (-9, -0.5)}.get(code)


def model_p(rng_, delta, sigma):
    lo, hi = rng_

    def ge(c):
        return 1.0 if c <= -8 else ncdf((delta - c + 0.125) / sigma)
    p_lo = ge(lo)
    p_hi = 0.0 if hi >= 8 else ge(hi + 0.25)
    return min(max(p_lo - p_hi, 0.001), 0.999)


def main():
    Y = Yl.Yields()
    f = Y.f
    rows = load()
    meet_days = sorted({Yl.time_day(r["ct"]) for r in rows})

    def latest(s, day, strict=False):
        ds = Y.days[s]
        i = (bisect.bisect_left(ds, day) if strict else bisect.bisect_right(ds, day)) - 1
        return (ds[i], f[s][ds[i]]) if i >= 0 else (None, None)

    def spread(day):
        ds = [x for x in Y.known("DGS1MO", day)[-120:]]
        vals = []
        for x in ds:
            nxt = [m for m in meet_days if x < m <= (dt.date.fromisoformat(x) + dt.timedelta(days=31)).isoformat()]
            if nxt:
                continue
            e = latest("EFFR", x)[1]
            if e is not None:
                vals.append(f["DGS1MO"][x] - e)
        return float(np.median(vals)) if len(vals) >= 5 else None

    obs = []
    sp_cache = {}
    for r in rows:
        D = Yl.time_day(r["ct"])
        for d, q in Yl.decision_points(dict(r, barrier=False), Y):
            k = (dt.date.fromisoformat(D) - dt.date.fromisoformat(d)).days
            if not (1 <= k <= 20) or d not in f["DGS1MO"]:
                continue
            U0 = latest("DFEDTARU", d)[1]
            e_day, effr = latest("EFFR", d, strict=True)     # EFFR for day d is published the next morning
            if U0 is None or effr is None:
                continue
            if d not in sp_cache:
                sp_cache[d] = spread(d)
            sp = sp_cache[d]
            if sp is None:
                continue
            delta = (f["DGS1MO"][d] - sp - effr) * 30.0 / (30 - k)
            cr = change_needed(r, U0)
            if cr is None:
                continue
            obs.append({"t": r["t"], "e": r["e"].split("-")[1], "s": r["series"], "d": d, "k": k, "ts": q[0],
                        "info": Yl.info_ts(dt.date.fromisoformat(d)), "bid": q[1], "ask": q[2], "delta": delta, "cr": cr,
                        "y": 1 if r["res"] == "yes" else 0, "settle": D, "ct": r["ct"]})
    tr_obs = [o for o in obs if o["settle"] < SPLIT]
    te_obs = [o for o in obs if o["settle"] >= SPLIT]
    best = None
    for sg in (0.04, 0.06, 0.08, 0.10, 0.13, 0.16, 0.20, 0.25, 0.30):
        ll = 0
        for o in tr_obs:
            p = model_p(o["cr"], o["delta"], sg)
            ll -= o["y"] * math.log(p) + (1 - o["y"]) * math.log(1 - p)
        ll /= max(len(tr_obs), 1)
        if best is None or ll < best[0]:
            best = (ll, sg)
    SIG = best[1]
    for o in obs:
        o["p"] = model_p(o["cr"], o["delta"], SIG)

    def br(ob):
        ok = [o for o in ob if o["ask"] - o["bid"] <= 10]
        return {"n": len(ok), "meetings": len({o["e"] for o in ok}),
                "market_mid": Yl.brier([(o["bid"] + o["ask"]) / 200 for o in ok], [o["y"] for o in ok]),
                "model": Yl.brier([o["p"] for o in ok], [o["y"] for o in ok])}
    res = {"sigma": SIG, "logloss_train": best[0], "split": SPLIT, "n_obs": {"train": len(tr_obs), "test": len(te_obs)},
           "brier": {"train": br(tr_obs), "test": br(te_obs)}}
    grid = []
    for mg in (0.0, 0.03, 0.05, 0.08, 0.12, 0.2):
        for sp in (3, 6, 10):
            s = Yl.summarize(Yl.trades(tr_obs, mg, sp))
            if s["n"] >= 15:
                grid.append((s["net_per_dollar"], mg, sp, s["n"]))
    grid.sort(reverse=True)
    res["train_grid"] = grid
    mg, sp = (grid[0][1], grid[0][2]) if grid else (0.1, 6)
    res["rule"] = {"margin": mg, "max_spread_c": sp}
    res["train"] = Yl.summarize(Yl.trades(tr_obs, mg, sp))
    te = Yl.trades(te_obs, mg, sp)
    res["test"] = Yl.summarize(te)
    res["test_trades"] = [{k: x[k] for k in ("t", "d", "side", "price", "p", "won", "r")} for x in te]

    # model-free pre-registered: NO on any outcome with YES ask <= 10c (NO = 1 - bid), last 10 days, first evening
    def longshot(ob):
        out, seen = [], set()
        for o in sorted(ob, key=lambda o: o["ts"]):
            if o["t"] in seen or o["k"] > 10 or o["ask"] > 10 or o["ask"] - o["bid"] > 6 or o["bid"] < 1:
                continue
            na = 1 - o["bid"] / 100
            won = o["y"] == 0
            seen.add(o["t"])
            out.append(dict(o, side="no", price=na, won=int(won), r=kk6.pnl_per_dollar(na, won)))
        return out
    res["longshot_no_train"] = Yl.summarize(longshot(tr_obs))
    res["longshot_no_test"] = Yl.summarize(longshot(te_obs))
    json.dump(res, open(os.path.join(HERE, "results_fed.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "test_trades"}, indent=1))


if __name__ == "__main__":
    main()
