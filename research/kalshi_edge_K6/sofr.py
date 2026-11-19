#!/usr/bin/env python3
"""K6 study 3: Kalshi daily SOFR markets (KXSOFRD, 'SOFR for date D is X') against the official NY Fed SOFR history.

Timing (checked on the rule text): market KXSOFRD-<P> settles on the SOFR for the business day D before P, published
by the NY Fed at 8:00 ET on P; it trades from about 8:45 ET on D and closes 7:59 ET on P. While it trades, the newest
official print is SOFR for the day before D (published on D at 8:00 ET). Decision quote = the last hourly quote ending
14:00-17:00 UTC on D (late morning ET). info_ts = D 08:15 ET.

Model: SOFR(D) = SOFR(D-1) + a change drawn from the empirical distribution of past 1-business-day changes for the same
kind of day (month-end, first day of a month, mid-month settlement 15th-16th, other), using only prints before the
decision (all SOFR history from 2019 on FRED). Days with an FOMC change in between are skipped.
Margin fixed on the older half of the markets, the newer half is read once.

    python research/kalshi_edge_K6/sofr.py   # -> results_sofr.json
"""
import bisect, calendar, datetime as dt, gzip, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("K6_OFFLINE", "1")
import kk6
import yields as Yl

HERE = os.path.dirname(os.path.abspath(__file__))
MON = Yl.MON


def day_kind(d, bdays):
    """calendar type of business day d (ISO): 'me' last business day of a month, 'ms' first, 'mid' the 15th-16th
    settlement day, 'pre' the business day before a month end, else 'n'."""
    i = bisect.bisect_left(bdays, d)
    nxt = bdays[i + 1] if i + 1 < len(bdays) else (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()
    prv = bdays[i - 1] if i > 0 else d
    if nxt[:7] != d[:7]:
        return "me"
    if prv[:7] != d[:7]:
        return "ms"
    nn = bdays[i + 2] if i + 2 < len(bdays) else nxt
    if nn[:7] != d[:7]:
        return "pre"
    if 15 <= int(d[8:]) <= 16 or (int(d[8:]) == 17 and dt.date.fromisoformat(d).weekday() == 0):
        return "mid"
    return "n"


def main():
    Y = Yl.Yields()
    S = Y.f["SOFR"]
    sd = Y.days["SOFR"]
    U = Y.f["DFEDTARU"]
    fn = os.path.join(kk6.DATA, "q_KXSOFRD.jsonl.gz")
    rows = [json.loads(l) for l in gzip.open(fn, "rt")]
    lst = {m["ticker"]: m for m in kk6.markets("KXSOFRD") + kk6.markets("KXSOFRD", historical=True)}
    obs = []
    for r in rows:
        if not r["c"]:
            continue
        tk = r["e"].split("-")[1]                       # 26SEP30 = the PUBLICATION date; the rate is for the business day before
        P = dt.date(2000 + int(tk[:2]), MON[tk[2:5].title()], int(tk[5:7])).isoformat()
        i = bisect.bisect_left(sd, P) - 1                # D = last business day before P
        if i < 2:
            continue
        D = sd[i]
        base_day = sd[i - 1]                             # newest print known while the market trades (published on D, 8:00 ET)
        if U.get(base_day) != U.get(D):                  # a policy change in between: skip
            continue
        dd = dt.date.fromisoformat(D)
        lo = calendar.timegm((dd.year, dd.month, dd.day, 14, 0, 0))
        hi = calendar.timegm((dd.year, dd.month, dd.day, 17, 0, 0))
        q = [c for c in r["c"] if lo <= c[0] <= hi]
        if not q:
            continue
        q = q[-1]
        info = calendar.timegm((dd.year, dd.month, dd.day, 8, 15, 0)) + Yl.et_offset(dd) * 3600
        dm1 = base_day
        kind = day_kind(D, sd)
        # empirical 2-business-day changes (bp) for the same kind of day, prints known before the decision
        hist = []
        for j in range(1, i):                            # 1-business-day changes whose second print is known (<= base_day)
            if day_kind(sd[j], sd) != kind or U.get(sd[j]) != U.get(sd[j - 1]):
                continue
            hist.append(int(round((S[sd[j]] - S[sd[j - 1]]) * 100)))
        hist = hist[-(250 if kind == "n" else 40):]
        if len(hist) < 15:
            continue
        vals, cnt = np.unique(hist, return_counts=True)
        pmf = {int(v): c for v, c in zip(vals, cnt)}
        # light smoothing: 1 pseudo-count spread over -3..+3 bp around every observed change
        sm = {}
        for v, c in pmf.items():
            for dlt in range(-3, 4):
                sm[v + dlt] = sm.get(v + dlt, 0) + (c if dlt == 0 else 0.05)
        tot = sum(sm.values())
        s0 = int(round(S[base_day] * 100))
        m = lst.get(r["t"], {})
        st = r["st"]
        fs = None if r["fs"] is None else int(round(r["fs"] * 100))
        cs = None if r["cs"] is None else int(round(r["cs"] * 100))
        if st == "between":
            win = lambda x: x == fs
        elif st == "greater_or_equal":
            win = lambda x: x >= fs
        elif st == "less_or_equal":
            win = lambda x: x <= cs
        else:
            continue
        p = sum(c for v, c in sm.items() if win(s0 + v)) / tot
        actual = int(round(S[D] * 100))
        y = 1 if r["res"] == "yes" else 0
        obs.append({"t": r["t"], "e": r["e"], "d": dm1, "ts": q[0], "info": info, "bid": q[1], "ask": q[2], "qv": q[3],
                    "p": min(max(p, 0.002), 0.998), "y": y, "settle": D, "ct": r["ct"], "kind": kind,
                    "check": int(win(actual)) == y})
    obs.sort(key=lambda o: o["settle"])
    days = sorted({o["settle"] for o in obs})
    split = days[len(days) // 2]
    tr = [o for o in obs if o["settle"] < split]
    te = [o for o in obs if o["settle"] >= split]
    res = {"n_obs": len(obs), "events": len(days), "split": split, "outcome_check_ok": sum(o["check"] for o in obs),
           "brier": {}}
    for nm, ob in (("train", tr), ("test", te)):
        ok = [o for o in ob if o["ask"] - o["bid"] <= 10]
        res["brier"][nm] = {"n": len(ok), "market_mid": Yl.brier([(o["bid"] + o["ask"]) / 200 for o in ok], [o["y"] for o in ok]),
                            "model": Yl.brier([o["p"] for o in ok], [o["y"] for o in ok])}
    grid = []
    for mg in (0.0, 0.03, 0.05, 0.08, 0.12, 0.2):
        for sp in (4, 8, 15):
            s = Yl.summarize(Yl.trades(tr, mg, sp))
            if s["n"] >= 20:
                grid.append((s["net_per_dollar"], mg, sp, s["n"]))
    grid.sort(reverse=True)
    res["train_grid"] = grid
    mg, sp = (grid[0][1], grid[0][2]) if grid else (0.1, 8)
    res["rule"] = {"margin": mg, "max_spread_c": sp}
    res["train"] = Yl.summarize(Yl.trades(tr, mg, sp))
    tt = Yl.trades(te, mg, sp)
    res["test"] = Yl.summarize(tt)
    res["test_by_kind"] = {k: Yl.summarize([x for x in tt if x["kind"] == k]) for k in ("n", "me", "ms", "mid", "pre")}
    json.dump(res, open(os.path.join(HERE, "results_sofr.json"), "w"), indent=1)
    vt = [{"ts": x["ts"], "info_ts": x["info"], "price": x["price"], "contracts": kk6.fee_order(x["price"])[0],
           "outcome": x["won"], "event": x["e"], "ticker": x["t"], "settle_ts": x["ct"]} for x in tt]
    json.dump({"rule": res["rule"], "trades": vt}, open(os.path.join(HERE, "trades_sofr_test.json"), "w"))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
