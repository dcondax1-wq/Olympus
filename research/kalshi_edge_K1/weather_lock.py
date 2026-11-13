#!/usr/bin/env python3
"""K1 weather study: does the market under-use what the thermometer has ALREADY shown on the settle day?

The high can only go up during the day. Once the station has read M degrees, every bracket wholly below M is dead (NO
certain) and every 'above X' with X < M is won (YES certain). A second, model-based rule prices the brackets ABOVE M
from the historical distribution of how much more the temperature still rises after hour h (IEM ASOS + NWS CLI
2024-2025, never the test days).

Quotes: team C's hourly yes bid/ask snapshots (research/kalshi_edge_C/data/snap_KXHIGH*.jsonl.gz, public Kalshi API).
Observations: cache/wobs.json.gz (weather_obs.py). Costs: taker buy at the ask (NO side: 100 - yes bid), fee
0.07*p*(1-p) rounded up per contract. Split by time: train = settle dates before 2026-09-15, test = from 2026-09-15.
Cluster bootstrap by settle date (all cities on one date move together).

    python research/kalshi_edge_K1/weather_lock.py
"""
import bisect, collections, datetime as dt, glob, gzip, json, math, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk
import stats

HERE = os.path.dirname(os.path.abspath(__file__))
CDATA = os.path.join(HERE, "..", "kalshi_edge_C", "data")
SPLIT = "2026-09-15"
LAG = 10 * 60          # an observation is usable 10 min after its time (IEM / NWS publish within minutes)
MON = {m: i + 1 for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def city_of(series):
    return series.replace("KXHIGH", "")


def ev_date(e):
    s = e.split("-")[1]
    return dt.date(2000 + int(s[:2]), MON[s[2:5]], int(s[5:7]))


def quote_time(ct, off):
    return (ct // 3600) * 3600 - off * 3600 if ct % 3600 == 0 else (ct // 3600) * 3600 - (off - 1) * 3600


class Obs:
    def __init__(self, rec):
        self.tz = rec["tz_std"]
        o = sorted((x for x in rec["obs"] if x[1] is not None or x[2] is not None), key=lambda x: x[0])
        self.t = [x[0] for x in o]
        self.v = o
        self.cli = rec["cli"]

    def day_start(self, d):
        return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp()) - self.tz * 3600

    def state(self, d, t):
        """(max so far as the whole-degree reading, latest temperature) for local-standard day d using reports up to t - LAG."""
        s = self.day_start(d)
        i0 = bisect.bisect_left(self.t, s)
        i1 = bisect.bisect_right(self.t, t - LAG)
        mx, last = None, None
        for k in range(i0, i1):
            ts, temp, m6 = self.v[k]
            if temp is not None:
                mx = temp if mx is None else max(mx, temp)
                last = temp
            if m6 is not None and ts - 6 * 3600 >= s - 60:
                mx = m6 if mx is None else max(mx, m6)
        if mx is None or last is None or i1 - i0 < 6:
            return None
        return int(math.floor(mx + 0.5)), last


def rise_table(obs_by_city, years=("2024", "2025")):
    """empirical P(final CLI high - max so far = r) by (local hour, bucket of max-so-far minus current temp), from history only."""
    tab = collections.defaultdict(collections.Counter)
    for city, ob in obs_by_city.items():
        for day, hi in ob.cli.items():
            if day[:4] not in years:
                continue
            d = dt.date.fromisoformat(day)
            for h in range(10, 24):
                st = ob.state(d, ob.day_start(d) + h * 3600)
                if not st:
                    continue
                m, last = st
                r = hi - m
                if r < -3:      # bad CLI or bad obs: skip
                    continue
                tab[(h, gap_bucket(m - last))][max(r, 0)] += 1
    return tab


def gap_bucket(g):
    return 0 if g < 1 else 1 if g < 3 else 2 if g < 6 else 3


def p_bracket(dist, m, st, fs, cs):
    n = sum(dist.values())
    if n < 200:
        return None
    p = 0.0
    for r, c in dist.items():
        h = m + r
        y = (h > fs) if st == "greater" else (h < cs) if st == "less" else (fs <= h <= cs)
        if y:
            p += c
    return (p + 0.5) / (n + 1)


def main():
    w = json.load(gzip.open(os.path.join(kk.CACHE, "wobs.json.gz"), "rt"))
    obs = {c: Obs(r) for c, r in w.items()}
    # 1. data check: the CLI high vs the obs max of the whole day (H >= M should hold)
    chk = collections.Counter()
    for c, ob in obs.items():
        for day, hi in ob.cli.items():
            d = dt.date.fromisoformat(day)
            st = ob.state(d, ob.day_start(d) + 24 * 3600 + LAG)
            if st:
                chk[max(-3, min(3, hi - st[0]))] += 1
    print("CLI high minus whole-day obs max (count):", sorted(chk.items()))
    rt = rise_table(obs)
    rows = []
    for fn in sorted(glob.glob(os.path.join(CDATA, "snap_KXHIGH*.jsonl.gz"))):
        series = os.path.basename(fn)[5:-9]
        city = city_of(series)
        ob = obs.get(city)
        if not ob:
            continue
        for l in gzip.open(fn, "rt"):
            r = json.loads(l)
            d = ev_date(r["e"])
            if d.isoformat() < "2026-05-01":
                continue
            yes = r["res"] == "yes"
            for off, q in r["q"].items():
                bid, ask = q[0], q[1]
                tq = quote_time(r["ct"], int(off))
                hloc = (tq - ob.day_start(d)) / 3600
                if hloc < 10 or hloc > 23.5:
                    continue
                st = ob.state(d, tq)
                if not st:
                    continue
                m, last = st
                rows.append({"d": d.isoformat(), "city": city, "h": int(round(hloc)), "st": r["st"], "fs": r["fs"], "cs": r["cs"],
                             "m": m, "gap": m - last, "bid": bid, "ask": ask, "yes": yes, "t": r["t"]})
    print("quote rows on settle day", len(rows))
    out = {"split": SPLIT, "rows": len(rows), "cli_check": dict((str(k), v) for k, v in chk.items()), "rules": {}}

    def trades_lock(margin):
        ts = []
        for x in rows:
            fs, cs, m = x["fs"], x["cs"], x["m"]
            if x["st"] == "between" and cs is not None and cs <= m - 1 - margin or x["st"] == "less" and cs is not None and m >= cs + margin:
                cost = 100 - x["bid"]        # buy NO
                win = not x["yes"]
            elif x["st"] == "greater" and fs is not None and m >= fs + 1 + margin:
                cost = x["ask"]              # buy YES
                win = x["yes"]
            else:
                continue
            if cost > 98 or cost < 1:
                continue
            ts.append((x["d"], cost, win, x))
        return ts

    for margin in (0, 1, 2):
        ts = trades_lock(margin)
        res = stats.summarize([(d, (100 if wn else 0) - c - kk.fee_c(c), c) for d, c, wn, _ in ts], SPLIT)
        res["losses"] = [{"t": x["t"], "h": x["h"], "m": x["m"], "cost": c} for d, c, wn, x in ts if not wn][:20]
        out["rules"][f"lock_margin{margin}"] = res
        print(f"LOCK margin {margin}:", json.dumps({k: v for k, v in res.items() if k != 'losses'}), "losses", len([1 for t in ts if not t[2]]))

    # model rule: brackets at or above the max so far, priced from the rise table (history 2024-2025 only)
    for hmin, thr in [(13, 3), (13, 5), (13, 8), (18, 3), (18, 5), (18, 8)]:
        ts = []
        for x in rows:
            if x["h"] < hmin:
                continue
            dist = rt.get((x["h"], gap_bucket(x["gap"])))
            if not dist:
                continue
            p = p_bracket(dist, x["m"], x["st"], x["fs"], x["cs"])
            if p is None:
                continue
            a, b = x["ask"], x["bid"]
            ey = 100 * p - a - kk.fee_c(a) if 1 <= a <= 99 else -99
            en = 100 * (1 - p) - (100 - b) - kk.fee_c(100 - b) if 1 <= b <= 99 else -99
            if ey >= thr and ey >= en:
                ts.append((x["d"], a, x["yes"]))
            elif en >= thr:
                ts.append((x["d"], 100 - b, not x["yes"]))
        res = stats.summarize([(d, (100 if wn else 0) - c - kk.fee_c(c), c) for d, c, wn in ts], SPLIT)
        out["rules"][f"rise_model_from{hmin}h_thr{thr}"] = res
        print(f"RISE MODEL from {hmin}h thr {thr}c:", json.dumps(res))
    # market vs model Brier on test rows (h >= 13), same rows
    for hmin in (13, 18):
      bm, bq, n = 0.0, 0.0, 0
      for x in rows:
        if x["d"] < SPLIT or x["h"] < hmin or not (0 < x["bid"] <= x["ask"] < 100):
            continue
        dist = rt.get((x["h"], gap_bucket(x["gap"])))
        p = p_bracket(dist, x["m"], x["st"], x["fs"], x["cs"]) if dist else None
        if p is None:
            continue
        y = 1.0 if x["yes"] else 0.0
        bm += ((x["bid"] + x["ask"]) / 200 - y) ** 2
        bq += (p - y) ** 2
        n += 1
      out[f"brier_test_h{hmin}plus"] = {"n": n, "market_mid": round(bm / max(n, 1), 4), "rise_model": round(bq / max(n, 1), 4)}
      print(f"Brier test (h>={hmin}):", out[f"brier_test_h{hmin}plus"])
    json.dump(out, open(os.path.join(HERE, "results_weather.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
