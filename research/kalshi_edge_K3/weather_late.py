#!/usr/bin/env python3
"""K3 angle 3: late-resolution drift on Kalshi daily HIGH / LOW temperature markets.

The day's high can only go up during the day (the low only down). Once the public observations (ASOS METARs, free from the
Iowa Environmental Mesonet) show the running max above a bucket's top, that bucket is dead (NO) and an 'above X' strike under
the running max is YES, hours before the market closes (11:59 pm local). Does the price lag, i.e. can a taker still buy the
known side under 99c after fees?

Quotes: team C's hourly yes bid/ask closes (research/kalshi_edge_C/data, read only). Obs: IEM ASOS routine + special METARs,
used only if valid at least LAG_MIN minutes before the quote. Settlement: NWS CLI daily max/min in local STANDARD time.
A margin of MARGIN_F degrees is required (METAR C->F rounding can differ from the CLI by 1 F).

    python research/kalshi_edge_K3/weather_late.py [--fetch]
Writes data/asos_<ST>.json.gz (compact obs), data/weather_late.json (results), data/weather_late_trades.jsonl.gz.
"""
import argparse, calendar, gzip, io, json, os, random, sys, time
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk

CDATA = os.path.join(os.path.dirname(kk.HERE), "kalshi_edge_C", "data")
IEM = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
# series -> (IEM station, standard UTC offset hours)
ST = {"KXHIGHNY": ("NYC", -5), "KXHIGHCHI": ("MDW", -6), "KXHIGHMIA": ("MIA", -5), "KXHIGHAUS": ("AUS", -6), "KXHIGHLAX": ("LAX", -8),
      "KXHIGHDEN": ("DEN", -7), "KXHIGHPHIL": ("PHL", -5), "KXHIGHTSFO": ("SFO", -8), "KXHIGHTPHX": ("PHX", -7), "KXHIGHTATL": ("ATL", -5),
      "KXHIGHTSEA": ("SEA", -8), "KXHIGHTBOS": ("BOS", -5), "KXHIGHTDAL": ("DFW", -6), "KXHIGHTDC": ("DCA", -5), "KXHIGHTLV": ("LAS", -8),
      "KXHIGHTHOU": ("HOU", -6), "KXHIGHTMIN": ("MSP", -6), "KXHIGHTOKC": ("OKC", -6), "KXHIGHTNOLA": ("MSY", -6), "KXHIGHTSATX": ("SAT", -6),
      "KXLOWTNYC": ("NYC", -5), "KXLOWTAUS": ("AUS", -6), "KXLOWTDEN": ("DEN", -7), "KXLOWTMIA": ("MIA", -5), "KXLOWTCHI": ("MDW", -6),
      "KXLOWTLAX": ("LAX", -8), "KXLOWTPHIL": ("PHL", -5)}
MAIN = ["KXHIGHNY", "KXHIGHCHI", "KXHIGHMIA", "KXHIGHAUS", "KXHIGHLAX", "KXHIGHDEN", "KXHIGHPHIL"]
LAG_MIN = 10
SPLIT = calendar.timegm((2026, 9, 15, 0, 0, 0))   # train before, test on/after (main cities)
N_REF = 100
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def fetch(station, y1=2026, m1=5, d1=25):
    now = time.gmtime()
    p = {"station": station, "data": "tmpf", "year1": y1, "month1": m1, "day1": d1, "year2": now.tm_year, "month2": now.tm_mon,
         "day2": now.tm_mday, "tz": "Etc/UTC", "format": "onlycomma", "latlon": "no", "missing": "M", "direct": "no"}
    url = IEM + "?" + "&".join(f"{k}={v}" for k, v in p.items()) + "&report_type=3&report_type=4"
    txt = kk.get(url, raw=True)
    obs = []
    for line in (txt or "").splitlines()[1:]:
        a = line.split(",")
        if len(a) < 3 or a[2] in ("M", ""):
            continue
        t = calendar.timegm(time.strptime(a[1], "%Y-%m-%d %H:%M"))
        obs.append([t, round(float(a[2]), 1)])
    obs.sort()
    with gzip.open(os.path.join(kk.DATA, f"asos_{station}.json.gz"), "wt") as fh:
        json.dump(obs, fh, separators=(",", ":"))
    return obs


def load_obs(station):
    return json.load(gzip.open(os.path.join(kk.DATA, f"asos_{station}.json.gz"), "rt"))


def ev_day(e):
    """'KXHIGHNY-26NOV09' -> (2026, 11, 9)"""
    s = e.split("-")[1]
    return 2000 + int(s[:2]), MON[s[2:5]], int(s[5:7])


def quote_ts(ct, off, back):
    tgt = (ct // 3600) * 3600 - off * 3600 if ct % 3600 == 0 else (ct // 3600) * 3600 - (off - 1) * 3600
    return tgt - 3600 * back


def fpc(p):
    return kk.fee_c(p, N_REF) / N_REF


def run(series_list, margin, kind):
    """kind 'high' or 'low'. Returns trades list."""
    trades, viol = [], {"n_days": 0, "obs_beyond_cli": 0, "mismatch_res": 0}
    for ser in series_list:
        fn = os.path.join(CDATA, f"snap_{ser}.jsonl.gz")
        if not os.path.exists(fn):
            continue
        stn, off_h = ST[ser]
        obs = load_obs(stn)
        ots = [o[0] for o in obs]
        import bisect
        rows = [json.loads(l) for l in gzip.open(fn, "rt")]
        byev = defaultdict(list)
        for r in rows:
            byev[r["e"]].append(r)
        for e, ms in byev.items():
            y, mo, d = ev_day(e)
            w0 = calendar.timegm((y, mo, d, 0, 0, 0)) - off_h * 3600     # local standard midnight in UTC
            w1 = w0 + 86400
            i0 = bisect.bisect_left(ots, w0)
            i1 = bisect.bisect_left(ots, w1)
            day = obs[i0:i1]
            if len(day) < 18:
                continue
            ev = next((m["ev"] for m in ms if m["ev"] is not None), None)
            if ev is None:
                continue
            viol["n_days"] += 1
            full = max(o[1] for o in day) if kind == "high" else min(o[1] for o in day)
            if (kind == "high" and round(full) > ev) or (kind == "low" and round(full) < ev):
                viol["obs_beyond_cli"] += 1
            for m in ms:
                # semantics check against the settled value
                st, fs, cs = m["st"], m["fs"], m["cs"]
                truth = (fs <= ev <= cs) if st == "between" else (ev > fs) if st in ("greater", "greater_or_equal") else (ev < cs)
                if truth != (m["res"] == "yes"):
                    viol["mismatch_res"] += 1
                for o, q in m["q"].items():
                    bid, ask, vol, back = q
                    t = quote_ts(m["ct"], int(o), back)
                    tk = t - LAG_MIN * 60
                    j = bisect.bisect_right(ots, tk)
                    seen = [x[1] for x in obs[i0:min(j, i1)]]
                    if len(seen) < 3:
                        continue
                    M = round(max(seen)) if kind == "high" else round(min(seen))
                    side = None
                    if kind == "high":
                        if st == "between" and cs < M - margin:
                            side = "no"
                        elif st in ("less", "less_or_equal") and cs <= M - margin:
                            side = "no"
                        elif st in ("greater", "greater_or_equal") and fs < M - margin:
                            side = "yes"
                    else:
                        if st == "between" and fs > M + margin:
                            side = "no"
                        elif st in ("greater", "greater_or_equal") and fs >= M + margin:
                            side = "no"
                        elif st in ("less", "less_or_equal") and cs > M + margin:
                            side = "yes"
                    if not side:
                        continue
                    price = (100 - bid) if side == "no" else ask
                    viol.setdefault("known", 0); viol["known"] += 1
                    viol.setdefault("known_hrs", defaultdict(int))[int((m["ct"] - t) // 3600)] += 1
                    viol.setdefault("price_hist", defaultdict(int))[price] += 1
                    if price >= 100 or price <= 0:
                        continue
                    won = (m["res"] == side)
                    pnl = (100 if won else 0) - price - fpc(price)
                    trades.append({"s": ser, "e": e, "t": m["t"], "ts": t, "off": int(o), "side": side, "p": price, "won": won,
                                   "pnl": round(pnl, 3), "vol": vol, "hrs_left": round((m["ct"] - t) / 3600, 1),
                                   "local_h": int(((t + off_h * 3600) % 86400) // 3600), "M": M})
    return trades, viol


def boot(trades, nb=2000, seed=7):
    """per-$1 edge with a cluster bootstrap by settlement day"""
    if not trades:
        return None
    cl = defaultdict(list)
    for t in trades:
        cl[t["e"].split("-")[1]].append(t)
    keys = list(cl)
    rnd = random.Random(seed)
    est = sum(t["pnl"] for t in trades) / sum(t["p"] for t in trades)
    bs = []
    for _ in range(nb):
        pn = st = 0.0
        for k in (rnd.choice(keys) for _ in keys):
            for t in cl[k]:
                pn += t["pnl"]; st += t["p"]
        bs.append(pn / st if st else 0)
    bs.sort()
    return {"n": len(trades), "days": len(keys), "wins": sum(t["won"] for t in trades), "edge_per_$": round(est, 4),
            "lo": round(bs[int(0.025 * nb)], 4), "hi": round(bs[int(0.975 * nb)], 4),
            "avg_price": round(sum(t["p"] for t in trades) / len(trades), 1), "avg_pnl_c": round(sum(t["pnl"] for t in trades) / len(trades), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()
    if a.fetch:
        for stn in sorted({v[0] for v in ST.values()}):
            o = fetch(stn)
            print(stn, len(o), flush=True)
    out = {"lag_min": LAG_MIN, "split": "train < 2026-09-15 <= test", "fee": "0.07 p(1-p), 100-lot orders, rounded up", "cells": {}}
    all_tr = []
    for kind, group, label in (("high", MAIN, "high_main"), ("high", [s for s in ST if s.startswith("KXHIGHT")], "high_rep13"),
                               ("low", [s for s in ST if s.startswith("KXLOWT")], "low7")):
        for margin in (0, 1, 2):
            tr, viol = run(group, margin, kind)
            for t in tr:
                t["grp"] = label; t["margin"] = margin
            if margin == 1:
                all_tr += tr
            cell = {"viol": viol, "all": boot(tr)}
            cell["train"] = boot([t for t in tr if t["ts"] < SPLIT])
            cell["test"] = boot([t for t in tr if t["ts"] >= SPLIT])
            for lo, hi, nm in ((1, 99, "price<=98"), (99, 100, "price=99")):
                cell[nm] = boot([t for t in tr if lo <= t["p"] < hi]) if nm == "price<=98" else boot([t for t in tr if t["p"] == 99])
            cell["losses"] = [t for t in tr if not t["won"]][:15]
            out["cells"][f"{label}_m{margin}"] = cell
            print(label, "margin", margin, viol, "\n   all", cell["all"], "\n   train", cell["train"], "\n   test", cell["test"],
                  "\n   <=98c", cell["price<=98"], "\n   99c", cell["price=99"], flush=True)
    json.dump(out, open(os.path.join(kk.DATA, "weather_late.json"), "w"), indent=1)
    with gzip.open(os.path.join(kk.DATA, "weather_late_trades.jsonl.gz"), "wt") as fh:
        for t in all_tr:
            fh.write(json.dumps(t, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
