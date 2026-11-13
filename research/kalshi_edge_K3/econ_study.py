#!/usr/bin/env python3
"""K3 angle 2: Kalshi on the big US releases, 2021-2026.

A. Calibration / taker P&L of every quoted strike (CPI m/m, core CPI, CPI y/y, payrolls, unemployment, jobless claims, Fed rate),
   by family x time before close x side x price band. Train = events closing before 2025-01-01, test = 2025-01-01 onward.
   Null for multiple testing: outcomes re-drawn from the market's own mid prices, one latent draw per event (a ladder of
   'above X' strikes moves together), max t over all cells, 300 runs.
B. Outside model, CPI m/m and core m/m: the Cleveland Fed nowcast of the day before (public), error spread fitted on the nowcast's
   own 2013-2020 record (before any Kalshi event in the test), P(print > X) with the 0.1 rounding. Trade when the model beats
   the ask by >= THR (picked on train events only); compare Brier of market mid, model and a blend.
C. Outside model, jobless claims: last week's first print (Kalshi's own settlement value of the previous event) plus the
   empirical week-on-week change distribution from FRED ICSA 2015-2019 + 2022-2024.

Fees: 0.07 p (1-p), rounded up per order, priced for 100-lot orders. Spread over 6c skipped. 95% ranges: cluster bootstrap by event.
    python research/kalshi_edge_K3/econ_study.py
Writes data/econ_results.json.
"""
import bisect, calendar, glob, gzip, json, math, os, random, statistics, sys, time
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk

SPLIT = calendar.timegm((2025, 1, 1, 0, 0, 0))
MAXSPREAD = 6
FAM = {"KXCPI": "cpi_mm", "KXCPICORE": "core_mm", "KXCPIYOY": "cpi_yoy", "KXPAYROLLS": "payrolls", "KXU3": "u3",
       "KXJOBLESSCLAIMS": "claims", "KXJOBLESS": "claims_old", "KXFED": "fed_rate", "KXFEDDECISION": "fed_decision"}
OFFB = {"1-4h": (1, 2, 3, 4), "6-24h": (6, 12, 24), "2-7d": (48, 72, 120, 168)}
BANDS = [("longshot<=15", 1, 15), ("mid16-84", 16, 84), ("fav>=85", 85, 99)]


def fpc(p):
    return kk.fee_c(p, 100) / 100


def load():
    rows = []
    for fn in glob.glob(os.path.join(kk.DATA, "econ_*.jsonl.gz")):
        ser = os.path.basename(fn)[5:-9]
        for l in gzip.open(fn, "rt"):
            r = json.loads(l)
            r["fam"] = FAM.get(ser, ser)
            rows.append(r)
    return rows


def units(rows):
    """one taker trade per (market, offset bucket, side): the first offset in the bucket that has a quote"""
    out = []
    for r in rows:
        for ob, offs in OFFB.items():
            q = next((r["q"][str(o)] for o in offs if str(o) in r["q"]), None)
            if not q:
                continue
            b, a = q[0], q[1]
            if a <= 0 or a >= 100 or b <= 0 or a - b > MAXSPREAD:
                continue
            mid = (a + b) / 2
            for side, p, won in (("yes", a, r["res"] == "yes"), ("no", 100 - b, r["res"] == "no")):
                out.append({"fam": r["fam"], "e": r["e"], "ct": r["ct"], "ob": ob, "side": side, "p": p, "won": won,
                            "pnl": (100 if won else 0) - p - fpc(p), "mid": mid if side == "yes" else 100 - mid, "t": r["t"]})
    return out


def band(p):
    for n, lo, hi in BANDS:
        if lo <= p <= hi:
            return n
    return None


def cell_stats(us, nb=1000, seed=1):
    if not us:
        return None
    cl = defaultdict(list)
    for u in us:
        cl[u["e"]].append(u)
    ks = list(cl)
    rnd = random.Random(seed)

    def f(xs):
        s = sum(u["p"] for u in xs)
        return sum(u["pnl"] for u in xs) / s if s else 0.0
    est = f(us)
    bs = sorted(f([u for k in (rnd.choice(ks) for _ in ks) for u in cl[k]]) for _ in range(nb))
    se = statistics.pstdev(bs) or 1e-9
    return {"n": len(us), "events": len(ks), "edge_per_$": round(est, 4), "lo": round(bs[int(0.025 * nb)], 4),
            "hi": round(bs[int(0.975 * nb)], 4), "t": round(est / se, 2), "win": round(sum(u["won"] for u in us) / len(us), 3),
            "avg_p": round(sum(u["p"] for u in us) / len(us), 1)}


def part_a(rows):
    us = units(rows)
    cells = defaultdict(list)
    for u in us:
        b = band(u["p"])
        if b:
            cells[(u["fam"], u["ob"], u["side"], b)].append(u)
    res = {}
    for k, v in sorted(cells.items()):
        tr = [u for u in v if u["ct"] < SPLIT]
        te = [u for u in v if u["ct"] >= SPLIT]
        if len({u["e"] for u in tr}) < 10:
            continue
        res["|".join(k)] = {"train": cell_stats(tr), "test": cell_stats(te) if te else None}
    # null: max train t over cells when outcomes are drawn from the mid prices (one latent per event)
    tmax_null = null_maxt([u for u in us if u["ct"] < SPLIT], list(res))
    pooled = {}
    for name, filt in (("all_yes", lambda u: u["side"] == "yes"), ("all_no", lambda u: u["side"] == "no"),
                       ("fav>=85_any", lambda u: u["p"] >= 85), ("longshot_no(yes<=15)", lambda u: u["side"] == "no" and u["p"] >= 85),
                       ("mid_any", lambda u: 16 <= u["p"] <= 84)):
        pooled[name] = {"train": cell_stats([u for u in us if filt(u) and u["ct"] < SPLIT]),
                        "test": cell_stats([u for u in us if filt(u) and u["ct"] >= SPLIT])}
    # calibration at the mid, by family (before costs)
    calib = {}
    for fam in sorted({u["fam"] for u in us}):
        for lo, hi in ((1, 10), (10, 30), (30, 70), (70, 90), (90, 99)):
            xs = [u for u in us if u["fam"] == fam and u["side"] == "yes" and lo <= u["mid"] < hi and u["ob"] == "6-24h"]
            if len(xs) >= 20:
                calib[f"{fam}|{lo}-{hi}"] = {"n": len(xs), "events": len({u['e'] for u in xs}), "priced": round(sum(u["mid"] for u in xs) / len(xs), 1),
                                             "won": round(100 * sum(u["won"] for u in xs) / len(xs), 1)}
    return {"cells": res, "null_maxt_95": tmax_null, "pooled": pooled, "calibration_mid_6_24h": calib, "n_units": len(us)}


def null_maxt(us_train, keys, runs=300, seed=11):
    cells = defaultdict(list)
    for u in us_train:
        b = band(u["p"])
        if b and "|".join((u["fam"], u["ob"], u["side"], b)) in keys:
            cells["|".join((u["fam"], u["ob"], u["side"], b))].append(u)
    rnd = random.Random(seed)
    evs = sorted({u["e"] for u in us_train})
    mx = []
    for _ in range(runs):
        lat = {e: rnd.random() for e in evs}   # one uniform per event: YES iff latent < P(yes) at mid -> monotone ladders
        best = 0.0
        for k, v in cells.items():
            byev = defaultdict(float); st = defaultdict(float)
            for u in v:
                pyes = u["mid"] / 100 if u["side"] == "yes" else 1 - u["mid"] / 100
                yes = lat[u["e"]] < pyes
                won = yes if u["side"] == "yes" else not yes
                byev[u["e"]] += (100 if won else 0) - u["p"] - fpc(u["p"]); st[u["e"]] += u["p"]
            ks = list(byev)
            if len(ks) < 10:
                continue
            tot = sum(byev.values()) / sum(st.values())
            # quick cluster se
            vals = [byev[k] / st[k] for k in ks]
            w = [st[k] for k in ks]
            m = sum(a * b for a, b in zip(vals, w)) / sum(w)
            var = sum((b * (a - m)) ** 2 for a, b in zip(vals, w)) / (sum(w) ** 2)
            t = tot / math.sqrt(var) if var > 0 else 0
            best = max(best, t)
        mx.append(best)
    mx.sort()
    return round(mx[int(0.95 * len(mx))], 2)


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def part_b(rows):
    nc = json.load(open(os.path.join(kk.DATA, "nowcast_cpi.json")))
    # nowcast error spread from 2013-07..2020-12 (day-before-release nowcast vs actual), headline and core
    def last_now(month, k, before):
        d = nc.get(month)
        if not d:
            return None
        xs = [x for x in d["days"] if x[k] is not None and x[0] < before]
        return xs[-1][k] if xs else None
    errs = {1: [], 2: []}
    for mo, d in nc.items():
        if mo > "2020-12":
            continue
        for k in (1, 2):
            a = d["actual"][k - 1]
            xs = [x for x in d["days"] if x[k] is not None]
            if a is not None and xs:
                errs[k].append(a - xs[-1][k])
    sig = {k: statistics.pstdev(v) for k, v in errs.items()}
    bias = {k: statistics.mean(v) for k, v in errs.items()}
    out = {"sigma_2013_2020": {"cpi": round(sig[1], 4), "core": round(sig[2], 4)}, "bias": {"cpi": round(bias[1], 4), "core": round(bias[2], 4)},
           "n_err": {"cpi": len(errs[1]), "core": len(errs[2])}}
    trades = []
    for r in rows:
        if r["fam"] not in ("cpi_mm", "core_mm") or r["st"] != "greater" or r["fs"] is None:
            continue
        k = 1 if r["fam"] == "cpi_mm" else 2
        # event 'KXCPI-26OCT' = October data, released in November
        tag = r["e"].split("-")[1]
        yy, mon = 2000 + int(tag[:2]), {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}[tag[2:5]]
        month = f"{yy:04d}-{mon:02d}"
        for ob, offs in OFFB.items():
            if ob == "1-4h":
                continue
            o = next((o for o in offs if str(o) in r["q"]), None)
            if o is None:
                continue
            b, a = r["q"][str(o)][:2]
            if a <= 0 or a >= 100 or b <= 0 or a - b > MAXSPREAD:
                continue
            tq = r["ct"] - o * 3600
            day = time.strftime("%Y-%m-%d", time.gmtime(tq))
            now = last_now(month, k, day)   # the nowcast published before the quote day
            if now is None:
                continue
            pm = 1 - ncdf((r["fs"] + 0.05 - (now + bias[k])) / sig[k])
            yes = r["res"] == "yes"
            trades.append({"fam": r["fam"], "e": r["e"], "ct": r["ct"], "ob": ob, "strike": r["fs"], "now": round(now, 3),
                           "pm": round(100 * pm, 2), "a": a, "b": b, "yes": yes})
    res = {}
    for ob in ("6-24h", "2-7d"):
        xs = [t for t in trades if t["ob"] == ob]
        tr = [t for t in xs if t["ct"] < SPLIT]; te = [t for t in xs if t["ct"] >= SPLIT]

        def brier(ts, f):
            return round(sum((f(t) / 100 - t["yes"]) ** 2 for t in ts) / len(ts), 4) if ts else None
        cell = {"n_train": len(tr), "n_test": len(te), "events_train": len({t['e'] for t in tr}), "events_test": len({t['e'] for t in te}),
                "brier_market_train": brier(tr, lambda t: (t["a"] + t["b"]) / 2), "brier_model_train": brier(tr, lambda t: t["pm"]),
                "brier_market_test": brier(te, lambda t: (t["a"] + t["b"]) / 2), "brier_model_test": brier(te, lambda t: t["pm"])}
        # trade rule: buy YES if pm - ask >= thr; buy NO if (100-pm) - (100-bid) >= thr. thr picked on train.
        def trade(ts, thr):
            us = []
            for t in ts:
                if t["pm"] - t["a"] >= thr:
                    p = t["a"]; won = t["yes"]
                elif (100 - t["pm"]) - (100 - t["b"]) >= thr:
                    p = 100 - t["b"]; won = not t["yes"]
                else:
                    continue
                us.append({"e": t["e"], "p": p, "won": won, "pnl": (100 if won else 0) - p - fpc(p)})
            return us
        grid = {}
        for thr in (3, 5, 8, 12, 20):
            grid[thr] = cell_stats(trade(tr, thr))
        best = max((k for k in grid if grid[k] and grid[k]["n"] >= 30), key=lambda k: grid[k]["t"], default=None)
        cell["train_grid"] = grid
        cell["thr_picked_on_train"] = best
        cell["test_at_thr"] = cell_stats(trade(te, best)) if best is not None else None
        res[ob] = cell
    out["cells"] = res
    return out


def part_c(rows):
    fred = json.load(open(os.path.join(kk.DATA, "icsa.json")))
    vals = [(d, v) for d, v in fred if ("2015" <= d[:4] <= "2019") or ("2022" <= d[:4] <= "2024")]
    chg = [math.log(vals[i][1] / vals[i - 1][1]) for i in range(1, len(vals)) if vals[i][0][:4] == vals[i - 1][0][:4]]
    chg.sort()
    cl = [r for r in rows if r["fam"] == "claims" and r["st"] == "greater_or_equal" and r["fs"] is not None]
    evv = {}
    for r in cl:
        if r["ev"] is not None:
            evv[r["e"]] = (r["ct"], r["ev"])
    evs = sorted(evv.items(), key=lambda x: x[1][0])
    prev = {evs[i][0]: evs[i - 1][1][1] for i in range(1, len(evs)) if evs[i][1][0] - evs[i - 1][1][0] < 9 * 86400}
    trades = []
    for r in cl:
        if r["e"] not in prev:
            continue
        p0 = prev[r["e"]]
        thr_log = math.log(r["fs"] / p0)
        pm = 100 * (1 - bisect.bisect_left(chg, thr_log) / len(chg))   # P(value >= strike)
        for ob, offs in OFFB.items():
            if ob == "1-4h":
                continue
            o = next((o for o in offs if str(o) in r["q"]), None)
            if o is None:
                continue
            b, a = r["q"][str(o)][:2]
            if a <= 0 or a >= 100 or b <= 0 or a - b > MAXSPREAD:
                continue
            trades.append({"e": r["e"], "ct": r["ct"], "ob": ob, "pm": pm, "a": a, "b": b, "yes": r["res"] == "yes"})
    out = {"n_changes": len(chg), "sd_log_change": round(statistics.pstdev(chg), 4), "events": len(prev), "cells": {}}
    # claims markets exist only from 2025-06: split by time inside (first 60% of events train)
    evo = sorted({t["e"] for t in trades}, key=lambda e: evv[e][0])
    cut = evv[evo[int(0.6 * len(evo))]][0] if evo else 0
    for ob in ("6-24h", "2-7d"):
        xs = [t for t in trades if t["ob"] == ob]
        tr = [t for t in xs if t["ct"] < cut]; te = [t for t in xs if t["ct"] >= cut]

        def brier(ts, f):
            return round(sum((f(t) / 100 - t["yes"]) ** 2 for t in ts) / len(ts), 4) if ts else None

        def trade(ts, thr):
            us = []
            for t in ts:
                if t["pm"] - t["a"] >= thr:
                    us.append({"e": t["e"], "p": t["a"], "won": t["yes"], "pnl": (100 if t["yes"] else 0) - t["a"] - fpc(t["a"])})
                elif t["b"] - t["pm"] >= thr:
                    p = 100 - t["b"]
                    us.append({"e": t["e"], "p": p, "won": not t["yes"], "pnl": (0 if t["yes"] else 100) - p - fpc(p)})
            return us
        grid = {thr: cell_stats(trade(tr, thr)) for thr in (3, 5, 8, 12, 20)}
        best = max((k for k in grid if grid[k] and grid[k]["n"] >= 30), key=lambda k: grid[k]["t"], default=None)
        out["cells"][ob] = {"n_train": len(tr), "n_test": len(te), "brier_market_train": brier(tr, lambda t: (t["a"] + t["b"]) / 2),
                            "brier_model_train": brier(tr, lambda t: t["pm"]), "brier_market_test": brier(te, lambda t: (t["a"] + t["b"]) / 2),
                            "brier_model_test": brier(te, lambda t: t["pm"]), "train_grid": grid, "thr_picked_on_train": best,
                            "test_at_thr": cell_stats(trade(te, best)) if best is not None else None}
    return out


def main():
    rows = load()
    # semantics check: 'greater' YES iff value > strike
    bad = sum(1 for r in rows if r["st"] in ("greater",) and r["ev"] is not None and r["fs"] is not None and ((r["ev"] > r["fs"]) != (r["res"] == "yes")))
    bad_ge = sum(1 for r in rows if r["st"] == "greater_or_equal" and r["ev"] is not None and r["fs"] is not None and ((r["ev"] >= r["fs"]) != (r["res"] == "yes")))
    out = {"n_markets": len(rows), "semantics_mismatch": {"greater": bad, "greater_or_equal": bad_ge}, "split": "train < 2025-01-01 <= test"}
    print("markets", len(rows), out["semantics_mismatch"], flush=True)
    out["A"] = part_a(rows)
    A = out["A"]
    print("null max-t 95%:", A["null_maxt_95"], "cells", len(A["cells"]))
    for k, v in sorted(A["cells"].items(), key=lambda kv: -(kv[1]["train"]["t"] if kv[1]["train"] else 0))[:12]:
        print("  ", k, v)
    for k, v in A["pooled"].items():
        print("  pooled", k, v)
    out["B"] = part_b(rows)
    print("B", json.dumps(out["B"], indent=None)[:3000])
    out["C"] = part_c(rows)
    print("C", json.dumps(out["C"], indent=None)[:3000])
    json.dump(out, open(os.path.join(kk.DATA, "econ_results.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
