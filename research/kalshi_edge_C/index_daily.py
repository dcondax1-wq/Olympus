#!/usr/bin/env python3
"""Team C, part 3: DAILY S&P 500 / Nasdaq-100 close-range markets (KXINX, KXNASDAQ100; 4 pm ET close) vs a simple realised-vol model
built on the repo's own futures bars (data/ES_5m.csv, data/NQ_5m.csv; futures only, TradingView CME exports).

At 1, 2, 4 and 6 hours before the close:
  centre  = the MARKET's own implied median close (we have no cash-index feed; the futures basis is not known to the point), so this
            study tests the WIDTH / SHAPE of the market's distribution (is its implied volatility too wide or too narrow?), not its level;
  sd      = sqrt(bars left) x 5-minute realised vol (half today's since 09:30, half the last 10 sessions' same time-to-close window),
            times one scale factor fitted on futures data BEFORE the test block only (no market prices involved);
  close   ~ lognormal(centre, sd) -> probability of every 25-pt (100-pt) bucket -> compare with the ask.
Discovery = S&P 500 (KXINX). Replication, frozen = Nasdaq-100 (KXNASDAQ100) with NQ bars.
    python research/kalshi_edge_C/index_daily.py [--sims 300]
"""
import argparse, collections, csv, json, math, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_c as L

ROOT = os.path.dirname(os.path.dirname(L.HERE))
OFFS = [1, 2, 4, 6]
THETAS = [0.03, 0.06, 0.10]
FUT = {"KXINX": "ES_5m.csv", "KXNASDAQ100": "NQ_5m.csv"}


def load_bars(fn):
    px = {}
    with open(os.path.join(ROOT, "data", fn)) as fh:
        for r in csv.DictReader(fh):
            px[int(r["time"]) + 300] = float(r["close"])   # key = bar END time
    return px


def rets(px, t0, t1):
    """5-minute log returns of bars ending in (t0, t1]; None if more than 10% of the bars are missing."""
    out, miss = [], 0
    for t in range(t0 + 300, t1 + 1, 300):
        a, b = px.get(t - 300), px.get(t)
        if a is None or b is None:
            miss += 1
        else:
            out.append(math.log(b / a))
    n = (t1 - t0) // 300
    return out if n and miss <= 0.1 * n and len(out) >= 4 else None


def bounds(r):
    if r["st"] == "less":
        return 0.0, float(r["cs"])
    if r["st"] == "greater":
        return float(r["fs"]), 1e9
    return float(r["fs"]), float(r["cs"]) + 0.0001


def build(series, px, kappa=None, cutoff=None):
    ev = collections.defaultdict(list)
    for r in L.load(series):
        if r.get("st") in ("less", "greater", "between") and r.get("e") and "H1600" in r["e"]:
            ev[r["e"]].append(r)
    evs = sorted(ev.items(), key=lambda kv: kv[1][0]["ct"])
    cts = [ms[0]["ct"] for _, ms in evs]
    U = L.Units(); brier = []; zs = []
    for ei, (e, ms) in enumerate(evs):
        ct = ms[0]["ct"]
        day = time.strftime("%Y-%m-%d", time.gmtime(ct))
        ms.sort(key=lambda r: bounds(r)[0])
        for off in OFFS:
            t = ct - off * 3600
            # --- realised-vol forecast of the log return from t to the close (futures only)
            sd = None
            today = rets(px, ct - 6 * 3600 - 1800, t)
            hist = []
            for pc in cts[max(0, ei - 10):ei]:
                h = rets(px, pc - off * 3600, pc)
                if h:
                    hist += h
            v = [np.mean(np.square(x)) for x in (today, hist) if x and len(x) >= 6]
            if v:
                sd = math.sqrt(off * 12 * float(np.mean(v)))
                a, b = px.get(t), px.get(ct)
                if a and b:
                    zs.append((day, off, math.log(b / a) / sd))
            qs = [L.quote(r, off) for r in ms]
            ok = [q for q in qs if q]
            if len(ok) < 5:
                continue
            mids = np.array([max(0.002, (q[0] + q[1]) / 2) if q else 0.002 for q in qs])
            if not 0.6 <= mids.sum() <= 1.6:
                continue
            cum = np.concatenate([[0], np.cumsum(mids / mids.sum())])
            i50 = int(np.searchsorted(cum, 0.5, side="right")) - 1
            lo, hi = bounds(ms[i50])
            if lo <= 0 or hi > 1e8:
                continue   # the median sits in an open tail: cannot centre
            M = lo + (hi - lo) * (0.5 - cum[i50]) / max(1e-9, cum[i50 + 1] - cum[i50])
            s = sd * kappa[off] if (sd and kappa) else None
            for i, (r, q) in enumerate(zip(ms, qs)):
                if not q:
                    continue
                a, b = bounds(r)
                yes = 1.0 if r["res"] == "yes" else 0.0
                pm = np.nan
                if s:
                    pm = (L.ncdf(math.log(b / M) / s) if b < 1e8 else 1.0) - (L.ncdf(math.log(a / M) / s) if a > 0 else 0.0)
                if q[1] - q[0] <= L.MAX_SPREAD and not np.isnan(pm):
                    brier.append((day, off, (q[0] + q[1]) / 2, pm, yes))
                for side, p in L.sides(*q):
                    w = yes if side == "yes" else 1 - yes
                    U.add(series=series, event=e, day=day, T=str(off), side=side, p=p, win=w, nlo=cum[i], nhi=cum[i + 1],
                          e_vol=(pm if side == "yes" else 1 - pm) - p - L.fee(p), band=L.band_of(p))
    return U.finish(), brier, zs


def make_cells(U):
    c = U.col
    cells = {}
    for off in OFFS:
        mT = c["T"] == str(off)
        for side in ("yes", "no"):
            mS = mT & (c["side"] == side)
            for th in THETAS:
                cells[f"vol model says underpriced by >= {int(th*100)}c | {off}h before close | buy {side}"] = mS & (np.nan_to_num(c["e_vol"], nan=-9) >= th)
            if off in (2, 6):
                for bi, (lo, hi) in enumerate(L.BANDS):
                    cells[f"price band {int(lo*100)}-{int(hi*100)}c | {off}h before close | buy {side}"] = mS & (c["band"] == bi)
    return cells


def brier_table(brier, cutoff):
    out = {}
    for blk, f in (("train", lambda d: d < cutoff), ("test", lambda d: d >= cutoff)):
        for off in OFFS:
            a = np.array([b[2:] for b in brier if f(b[0]) and b[1] == off], dtype=float)
            if len(a) >= 50:
                out[f"{blk} {off}h"] = {"n": len(a), "brier_market_mid": round(float(((a[:, 0] - a[:, 2]) ** 2).mean()), 5),
                                        "brier_vol_model": round(float(((a[:, 1] - a[:, 2]) ** 2).mean()), 5)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=300)
    a = ap.parse_args()
    res = {"generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "families": {}}
    cutoff = None
    for series in ("KXINX", "KXNASDAQ100"):
        px = load_bars(FUT[series])
        U0, _, zs = build(series, px)
        if U0.n == 0:
            print(series, "no data"); continue
        days = sorted(set(U0.col["day"]))
        if cutoff is None:
            cutoff = days[int(len(days) * 0.75)]
        # scale factor: realised sd of (true return / forecast sd) on futures data strictly before the test block
        kappa = {}
        for off in OFFS:
            z = [x[2] for x in zs if x[1] == off and x[0] < cutoff]
            kappa[off] = float(np.std(z)) if len(z) >= 15 else 1.0
        U, brier, _ = build(series, px, kappa)
        cells = make_cells(U)
        tr = U.col["day"] < cutoff
        info = {"units": U.n, "days": len(days), "first_day": days[0], "last_day": days[-1], "test_from": cutoff,
                "days_with_futures_model": len(set(b[0] for b in brier)), "vol_scale": {str(k): round(v, 3) for k, v in kappa.items()},
                "brier": brier_table(brier, cutoff)}
        if series == "KXINX":
            R = L.run_family(U, cells, tr, n_sims=a.sims, label="S&P 500 daily range (discovery)")
            R.update(info)
            res["families"]["spx"] = R
            print(f"spx: units {U.n}, days {len(days)}, test from {cutoff}, eligible {R['cells_eligible']}/{R['cells_defined']}, null p95 t {R['null_max_t_p95']}, carried {len(R['carried'])}, survive {len(R['survive'])}", flush=True)
        else:
            rows = [{"cell": n, "train_days": L.frozen(U, m & tr), "test_days_only": L.frozen(U, m & ~tr)} for n, m in cells.items()]
            info["frozen_cells"] = rows
            res["families"]["ndx"] = info
            print("ndx: units", U.n, "days", len(days), flush=True)
    json.dump(res, open(os.path.join(L.HERE, "results_index.json"), "w"), indent=1)
    print("wrote results_index.json")


if __name__ == "__main__":
    main()
