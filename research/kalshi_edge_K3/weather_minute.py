#!/usr/bin/env python3
"""K3 angle 3, minute level: how fast does a Kalshi temperature bucket die after the public METAR shows it is dead?

For each settled daily high/low event since the live-API cutoff (2026-09-13, 1-minute candles exist), find every moment a
METAR (IEM archive, routine + specials) pushes the running max (min) past a bucket so that, with margin m degrees, its outcome
is known: 'between' / tail buckets that can no longer win -> NO; an 'above X' (high) or 'below X' (low) tail already won -> YES.
Then read the 1-minute yes bid/ask at the METAR time + L minutes (L = 2, 5, 10, 15, 30, 60) and price a taker buy of the
known side (NO ask = 100 - yes bid; YES ask). Also sums the volume traded in the first hour after the crossing at a price
that leaves money on the table (known side under 99c).

    python research/kalshi_edge_K3/weather_minute.py
Writes data/weather_minute.json and data/weather_minute_rows.jsonl.gz.
"""
import bisect, calendar, gzip, json, os, random, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk
import weather_late as wl

LAGS = [1, 2, 3, 4, 5, 10, 15, 30, 60]
CUTOFF = calendar.timegm((2026, 9, 14, 0, 0, 0))
N_REF = 100


def candles(tickers, lo, hi):
    d = kk.get("/markets/candlesticks", {"market_tickers": ",".join(tickers), "start_ts": lo, "end_ts": hi, "period_interval": 1})
    out = {}
    for mk in (d or {}).get("markets", []):
        cs = {}
        for k in mk.get("candlesticks", []):
            a = kk.c((k.get("yes_ask") or {}).get("close_dollars")); b = kk.c((k.get("yes_bid") or {}).get("close_dollars"))
            pr = k.get("price") or {}
            cs[k["end_period_ts"]] = (b, a, kk.fl(k.get("volume_fp")) or 0.0, kk.c(pr.get("low_dollars")), kk.c(pr.get("high_dollars")))
        out[mk.get("market_ticker") or mk.get("ticker")] = cs
    return out


def quote_at(cs, t):
    """last 1-minute close at or before t (within 15 min)"""
    keys = sorted(cs)
    i = bisect.bisect_right(keys, t) - 1
    if i < 0 or t - keys[i] > 900:
        return None
    return cs[keys[i]]


def crossings(ms, day, kind, margin):
    """[(t_obs, market, side, M)] first time each market's outcome is known from the METARs"""
    out, done = [], set()
    run = None
    for t, v in day:
        r = round(v)
        run = r if run is None else (max(run, r) if kind == "high" else min(run, r))
        for m in ms:
            if m["t"] in done:
                continue
            st, fs, cs = m["st"], m["fs"], m["cs"]
            side = None
            if kind == "high":
                if (st == "between" and cs < run - margin) or (st in ("less", "less_or_equal") and cs <= run - margin):
                    side = "no"
                elif st in ("greater", "greater_or_equal") and fs < run - margin:
                    side = "yes"
            else:
                if (st == "between" and fs > run + margin) or (st in ("greater", "greater_or_equal") and fs >= run + margin):
                    side = "no"
                elif st in ("less", "less_or_equal") and cs > run + margin:
                    side = "yes"
            if side:
                done.add(m["t"])
                out.append((t, m, side, run))
    return out


def main():
    rows = []
    groups = [("high", s) for s in wl.ST if s.startswith("KXHIGH")] + [("low", s) for s in wl.ST if s.startswith("KXLOWT")]
    for kind, ser in groups:
        fn = os.path.join(wl.CDATA, f"snap_{ser}.jsonl.gz")
        if not os.path.exists(fn):
            continue
        stn, off_h = wl.ST[ser]
        obs = wl.load_obs(stn)
        ots = [o[0] for o in obs]
        byev = defaultdict(list)
        for r in (json.loads(l) for l in gzip.open(fn, "rt")):
            if r["ct"] >= CUTOFF:
                byev[r["e"]].append(r)
        n_ev = 0
        for e, ms in sorted(byev.items()):
            y, mo, d = wl.ev_day(e)
            w0 = calendar.timegm((y, mo, d, 0, 0, 0)) - off_h * 3600
            day = obs[bisect.bisect_left(ots, w0):bisect.bisect_left(ots, w0 + 86400)]
            if len(day) < 18:
                continue
            cr = [(t, m, s, M, mg) for mg in (0, 1) for (t, m, s, M) in crossings(ms, day, kind, mg)]
            # only crossings that happen while the market trades (it opens the day before, closes ~1 am local)
            cr = [x for x in cr if x[0] < x[1]["ct"] - 60 * 60 and (x[1]["ot"] is None or x[0] > x[1]["ot"])]
            if not cr:
                continue
            tick = sorted({x[1]["t"] for x in cr})
            lo = min(x[0] for x in cr) - 1800
            hi = min(max(x[0] for x in cr) + 3700, max(m["ct"] for m in ms))
            cs = candles(tick, lo, hi)
            n_ev += 1
            for t, m, side, M, mg in cr:
                c = cs.get(m["t"]) or {}
                if not c:
                    continue
                q0 = quote_at(c, t)
                rec = {"s": ser, "e": e, "t": m["t"], "kind": kind, "margin": mg, "side": side, "t_obs": t, "M": M,
                       "won": m["res"] == side, "hrs_left": round((m["ct"] - t) / 3600, 1),
                       "local_h": int(((t + off_h * 3600) % 86400) // 3600)}
                rec["p0"] = None if not q0 else ((100 - q0[0]) if side == "no" else q0[1])
                for L in LAGS:
                    q = quote_at(c, t + 60 * L)
                    rec[f"p{L}"] = None if not q else ((100 - q[0]) if side == "no" else q[1])
                # volume in the first hour after t+2 min that printed at a price where the known side cost < 99
                vol_bad = 0.0
                for ts_, (b, a, v, plo, phi) in c.items():
                    if t + 120 <= ts_ <= t + 3600 and v:
                        # known NO: a YES print at >= 2c means NO changed hands at <= 98c
                        if side == "no" and phi is not None and phi >= 2:
                            vol_bad += v
                        if side == "yes" and plo is not None and plo <= 98:
                            vol_bad += v
                rec["vol_bad_1h"] = round(vol_bad, 1)
                rows.append(rec)
        print(ser, "events with crossings", n_ev, "rows", len(rows), kk.STATS, flush=True)
    with gzip.open(os.path.join(kk.DATA, "weather_minute_rows.jsonl.gz"), "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    summarize(rows)


def fpc(p):
    return kk.fee_c(p, N_REF) / N_REF


def boot(tr, key, nb=2000, seed=3):
    cl = defaultdict(list)
    for r in tr:
        cl[r["e"].split("-")[1]].append(r)
    ks = list(cl)
    rnd = random.Random(seed)

    def stat(rs):
        st = sum(r[key] for r in rs)
        return sum((100 if r["won"] else 0) - r[key] - fpc(r[key]) for r in rs) / st if st else 0
    bs = sorted(stat([r for k in (rnd.choice(ks) for _ in ks) for r in cl[k]]) for _ in range(nb))
    return round(stat(tr), 4), round(bs[int(0.025 * nb)], 4), round(bs[int(0.975 * nb)], 4), len(ks)


def summarize(rows):
    out = {"n_rows": len(rows), "cells": {}}
    for kind in ("high", "low"):
        for mg in (0, 1):
            rs = [r for r in rows if r["kind"] == kind and r["margin"] == mg]
            if not rs:
                continue
            cell = {"n_cross": len(rs), "won": sum(r["won"] for r in rs), "win_rate": round(sum(r["won"] for r in rs) / len(rs), 4),
                    "vol_bad_1h_total": round(sum(r["vol_bad_1h"] for r in rs)), "lags": {}}
            for L in [0] + LAGS:
                k = f"p{L}"
                q = [r for r in rs if r.get(k) is not None]
                buy = [r for r in q if r[k] < 100]
                d = {"n_quoted": len(q), "n_buyable": len(buy), "share_buyable": round(len(buy) / len(q), 3) if q else None}
                if buy:
                    d["avg_price"] = round(sum(r[k] for r in buy) / len(buy), 2)
                    d["won"] = sum(r["won"] for r in buy)
                    e, lo, hi, nd = boot(buy, k)
                    d.update({"edge_per_$": e, "lo": lo, "hi": hi, "days": nd,
                              "net_c_per_contract": round(sum((100 if r["won"] else 0) - r[k] - fpc(r[k]) for r in buy) / len(buy), 3)})
                    alld = sorted({r["e"].split("-")[1] for r in rs}, key=lambda s: wl.ev_day("x-" + s))
                    cutd = set(alld[int(0.6 * len(alld)):])
                    for nm, sub in (("train_first60pct_days", [r for r in buy if r["e"].split("-")[1] not in cutd]),
                                    ("test_last40pct_days", [r for r in buy if r["e"].split("-")[1] in cutd]),
                                    ("main7", [r for r in buy if r["s"] in wl.MAIN or r["s"].replace("KXLOWT", "") in ("NYC", "AUS", "DEN", "MIA", "CHI", "LAX", "PHIL")]),
                                    ("other13", [r for r in buy if r["s"].startswith("KXHIGHT")])):
                        if sub:
                            e2, lo2, hi2, nd2 = boot(sub, k)
                            d[nm] = {"n": len(sub), "won": sum(r["won"] for r in sub), "edge_per_$": e2, "lo": lo2, "hi": hi2, "days": nd2}
                    d["price_hist"] = dict(sorted(defaultdict(int, {p: sum(1 for r in buy if r[k] == p) for p in {r[k] for r in buy}}).items()))
                cell["lags"][str(L)] = d
            out["cells"][f"{kind}_m{mg}"] = cell
            print(kind, "margin", mg, json.dumps({k: v for k, v in cell.items() if k != "lags"}))
            for L, d in cell["lags"].items():
                print("   lag", L, {k: v for k, v in d.items() if k != "price_hist"}, "prices", list(d.get("price_hist", {}).items())[:12])
    json.dump(out, open(os.path.join(kk.DATA, "weather_minute.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
