#!/usr/bin/env python3
"""Team C, part 1: DAILY TEMPERATURE markets vs a REAL public forecast (archived NWS MOS: GFS MOS, NAM MOS, National Blend).

Decision times: E = about 8 pm local the evening before (29 h before the 1 am close), M = about 7 am local on the day (18 h before).
Forecast used at E: the 18Z (else 12Z) run of the day before; at M: the 00Z run of the day (always >= 6 h old, so it was public).
Model: high ~ Normal(forecast + bias, sd), bias and sd = that station's last 60 SETTLED days (walk-forward, nothing fitted on the test block).
Naive model (the fallback the brief asked for): climatology (30-day mean) + 0.7 x persistence (yesterday's high).

Families: main = 7 big cities (discovery), rep = 13 other cities (never used to pick anything), low = daily LOW markets (E only).
    python research/kalshi_edge_C/weather.py [--sims 300]
"""
import argparse, collections, datetime as dt, gzip, json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_c as L
from harvest_c import GROUPS
from mos_fetch import STATIONS

OFF = {"E": 29, "M": 18}
RUNS = {"E": ["18p", "12p"], "M": ["00", "18p", "12p"]}
THETAS = [0.02, 0.05, 0.10, 0.15]


def city(series):
    for pre in ("KXHIGHT", "KXHIGH", "KXLOWT"):
        if series.startswith(pre):
            return series[len(pre):]


def bounds(r):
    if r["st"] == "less":
        return -99.0, r["cs"] - 1.0
    if r["st"] == "greater":
        return r["fs"] + 1.0, 199.0
    return float(r["fs"]), float(r["cs"])


def build_events(series):
    kind = "n" if series.startswith("KXLOWT") else "x"
    st = STATIONS[city(series)]
    ev = collections.defaultdict(list)
    for r in L.load(series):
        if r.get("st") in ("less", "greater", "between") and r.get("e"):
            ev[r["e"]].append(r)
    out = {}
    for e, ms in ev.items():
        try:
            day = dt.datetime.strptime(e.split("-")[1], "%y%b%d").date()
        except Exception:
            continue
        ms.sort(key=lambda r: bounds(r)[0])
        act = next((r["ev"] for r in ms if r["ev"] is not None), None)
        exact = act is not None
        if act is None:
            y = [r for r in ms if r["res"] == "yes"]
            if len(y) == 1:
                a, b = bounds(y[0])
                act = (a + b) / 2 if a > -90 and b < 190 else (b - 0.5 if a < -90 else a + 0.5)
        out[day] = {"e": e, "ms": ms, "act": act, "exact": exact, "station": st, "kind": kind}
    return out


def forecasts(events, mos):
    """adds F[T], mu/sd per model per decision time, walk-forward."""
    days = sorted(events)
    st = events[days[0]]["station"]; kind = events[days[0]]["kind"]
    m = mos.get(st, {})
    for d in days:
        ev = events[d]
        fx = m.get(str(d), {}).get(kind, {})
        ev["F"] = {}
        for T, runs in RUNS.items():
            vals = []
            for model in ("GFS", "NBS", "NAM"):
                v = next((fx.get(model, {}).get(k) for k in runs if fx.get(model, {}).get(k) is not None), None)
                if v is not None:
                    vals.append(v)
            ev["F"][T] = float(np.mean(vals)) if vals else None
        prev = events.get(d - dt.timedelta(days=1), {}).get("act")
        hist = [events[x]["act"] for x in (d - dt.timedelta(days=k) for k in range(1, 31)) if x in events and events[x]["act"] is not None]
        ev["naive"] = (np.mean(hist) + 0.7 * (prev - np.mean(hist))) if prev is not None and len(hist) >= 15 else None
    for d in days:
        ev = events[d]
        ev["mu"], ev["sd"] = {}, {}
        past = [events[x] for x in (d - dt.timedelta(days=k) for k in range(2, 62)) if x in events and events[x]["act"] is not None]
        for T in OFF:
            res = [p["act"] - p["F"][T] for p in past if p["F"].get(T) is not None]
            if ev["F"][T] is not None and len(res) >= 20:
                ev["mu"]["mos" + T] = ev["F"][T] + float(np.mean(res)); ev["sd"]["mos" + T] = max(1.2, float(np.std(res)))
            res = [p["act"] - p["naive"] for p in past if p.get("naive") is not None]
            if ev["naive"] is not None and len(res) >= 20:
                ev["mu"]["naive" + T] = ev["naive"] + float(np.mean(res)); ev["sd"]["naive" + T] = max(1.2, float(np.std(res)))


def prob(mu, sd, a, b):
    return L.ncdf((b + 0.5 - mu) / sd) - L.ncdf((a - 0.5 - mu) / sd)


def units_for(series_list, mos, times):
    U = L.Units()
    brier = []   # (family rows) day, T, mid, p_mos, p_naive, yes
    ferr = []
    for s in series_list:
        events = build_events(s)
        if not events:
            continue
        forecasts(events, mos)
        for d, ev in sorted(events.items()):
            if ev["act"] is not None and ev["exact"]:
                ferr.append((s, str(d), ev["act"], ev["F"].get("E"), ev["F"].get("M"), ev.get("naive")))
            for T in times:
                qs = [L.quote(r, OFF[T]) for r in ev["ms"]]
                if sum(q is not None for q in qs) < 3:
                    continue
                mids = np.array([max(0.005, (q[0] + q[1]) / 2) if q else 0.005 for q in qs])
                cum = np.concatenate([[0], np.cumsum(mids / mids.sum())])
                for i, (r, q) in enumerate(zip(ev["ms"], qs)):
                    if not q:
                        continue
                    a, b = bounds(r)
                    yes = 1.0 if r["res"] == "yes" else 0.0
                    pm = {k: (prob(ev["mu"][k + T], ev["sd"][k + T], a, b) if (k + T) in ev["mu"] else np.nan) for k in ("mos", "naive")}
                    if q[1] - q[0] <= L.MAX_SPREAD:
                        brier.append((str(d), T, (q[0] + q[1]) / 2, pm["mos"], pm["naive"], yes))
                    for side, p in L.sides(*q):
                        w = yes if side == "yes" else 1 - yes
                        U.add(series=s, event=ev["e"], day=str(d), T=T, side=side, p=p, win=w, nlo=cum[i], nhi=cum[i + 1],
                              e_mos=(pm["mos"] if side == "yes" else 1 - pm["mos"]) - p - L.fee(p),
                              e_naive=(pm["naive"] if side == "yes" else 1 - pm["naive"]) - p - L.fee(p),
                              band=L.band_of(p), vol=r["vol"] or 0.0)
    return U.finish(), brier, ferr


def make_cells(U, times):
    c = U.col
    cells = {}
    for T in times:
        mT = c["T"] == T
        for side in ("yes", "no"):
            mS = mT & (c["side"] == side)
            for mdl in ("mos", "naive"):
                for th in THETAS:
                    cells[f"{mdl} model says underpriced by >= {int(th*100)}c | {T} | buy {side}"] = mS & (np.nan_to_num(c["e_" + mdl], nan=-9) >= th)
            for bi, (lo, hi) in enumerate(L.BANDS):
                cells[f"price band {int(lo*100)}-{int(hi*100)}c | {T} | buy {side}"] = mS & (c["band"] == bi)
    return cells


def brier_table(brier, cutoff):
    """Brier score (lower = better forecaster) of the market mid, the models, and the best market+MOS mix (weight picked on TRAIN only)."""
    out = {}
    for T in ("E", "M"):
        blk = {}
        for name, f in (("train", lambda d: d < cutoff), ("test", lambda d: d >= cutoff)):
            rows = [b for b in brier if f(b[0]) and b[1] == T and not np.isnan(b[3]) and not np.isnan(b[4])]
            if len(rows) >= 50:
                blk[name] = np.array([b[2:] for b in rows], dtype=float)
        w_best = None
        if "train" in blk:
            a = blk["train"]
            w_best = min((float((((1 - w) * a[:, 0] + w * a[:, 1] - a[:, 3]) ** 2).mean()), w) for w in np.arange(0, 1.01, 0.05))[1]
        for name, a in blk.items():
            out[f"{name} {T}"] = {"n": len(a), "brier_market_mid": round(float(((a[:, 0] - a[:, 3]) ** 2).mean()), 5),
                                  "brier_mos_model": round(float(((a[:, 1] - a[:, 3]) ** 2).mean()), 5),
                                  "brier_naive_model": round(float(((a[:, 2] - a[:, 3]) ** 2).mean()), 5),
                                  "best_mix_weight_on_forecast_(train)": round(float(w_best), 2),
                                  "brier_best_mix": round(float((((1 - w_best) * a[:, 0] + w_best * a[:, 1] - a[:, 3]) ** 2).mean()), 5)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=300)
    a = ap.parse_args()
    t0 = time.time()
    mos = json.load(gzip.open(os.path.join(L.DATA, "mos.json.gz"), "rt"))
    res = {"generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "families": {}}
    fam = {"main": (GROUPS["weather_main"], ["E", "M"]), "rep": (GROUPS["weather_rep"], ["E", "M"]), "low": (GROUPS["weather_low"], ["E"])}
    built = {k: units_for(s, mos, t) for k, (s, t) in fam.items()}
    U, brier, ferr = built["main"]
    days = sorted(set(U.col["day"]))
    cutoff = days[int(len(days) * 0.75)]
    res.update(quoted_days=len(days), first_day=days[0], last_day=days[-1], test_from=cutoff)
    # forecast quality (no market involved): mean abs error of each forecast on days with an exact settlement value
    fq = {}
    for k in built:
        fe = built[k][2]
        fq[k] = {"days": len(fe)}
        for nm, i in (("mos_evening", 3), ("mos_morning", 4), ("naive", 5)):
            v = [abs(x[2] - x[i]) for x in fe if x[i] is not None]
            if v:
                fq[k][nm + "_mae_F"] = round(float(np.mean(v)), 2); fq[k][nm + "_n"] = len(v)
    res["forecast_quality"] = fq
    cells = make_cells(U, ["E", "M"])
    tr = U.col["day"] < cutoff
    R = L.run_family(U, cells, tr, n_sims=a.sims, label="weather main (7 cities)")
    R["units"] = U.n; R["brier"] = brier_table(brier, cutoff)
    res["families"]["main"] = R
    print(f"main: units {U.n}, days {len(days)}, test from {cutoff}, eligible {R['cells_eligible']}/{R['cells_defined']}, null p95 t {R['null_max_t_p95']}, "
          f"carried {len(R['carried'])}, survive {len(R['survive'])}  ({time.time()-t0:.0f}s)", flush=True)
    # replication families: NOTHING is picked here. Every main cell is evaluated frozen (all days, and test days only).
    for k in ("rep", "low"):
        U2, br2, _ = built[k]
        if U2.n == 0:
            continue
        c2 = make_cells(U2, fam[k][1])
        te2 = U2.col["day"] >= cutoff
        rows = []
        for name, m in c2.items():
            rows.append({"cell": name, "all_days": L.frozen(U2, m), "test_days_only": L.frozen(U2, m & te2)})
        res["families"][k] = {"units": U2.n, "days": len(set(U2.col["day"])), "brier": brier_table(br2, cutoff), "frozen_cells": rows}
        print(k, "units", U2.n, "days", len(set(U2.col["day"])), flush=True)
    # pre-registered headline rule (written before any result was read): trade when the MOS model says the price is >= 5c too cheap
    head = {}
    for k in built:
        Uk = built[k][0]
        if Uk.n == 0:
            continue
        ck = Uk.col
        m = np.nan_to_num(ck["e_mos"], nan=-9) >= 0.05
        head[k] = {"train": L.frozen(Uk, m & (ck["day"] < cutoff)), "test": L.frozen(Uk, m & (ck["day"] >= cutoff)),
                   "all_buys_control_test": L.frozen(Uk, ck["day"] >= cutoff)}
    res["headline_rule_mos_5c"] = head
    json.dump(res, open(os.path.join(L.HERE, "results_weather.json"), "w"), indent=1)
    print("wrote results_weather.json", f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
