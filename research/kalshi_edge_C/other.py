#!/usr/bin/env python3
"""Team C, parts 2 and 4: other recurring series (gas prices, treasury yield, FX daily range, Spotify / Netflix / Rotten Tomatoes,
TSA, NYC rain) and ECONOMIC RELEASES (descriptive only: a handful of events).

Recurring series: price-band calibration cells (class x hours before close x side x price band) + one outside-signal model for the
daily US gas price (AAA): tomorrow's change = phi x today's change (momentum, phi and sd fitted walk-forward on the last 60 settled days).
Only series with >= 300 settled, quoted markets are used. Same protocol as lib_c.py.
    python research/kalshi_edge_C/other.py [--sims 300]
"""
import argparse, collections, json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_c as L
from harvest_c import GROUPS

CLASS = {"KXAAAGASD": "gas daily", "KXDIESELD": "gas daily", "KXAAAGASW": "gas weekly/monthly", "KXAAAGASM": "gas weekly/monthly",
         "KXTNOTED": "rates+fx", "KXTNOTEW": "rates+fx", "KXUSDJPY": "rates+fx", "KXEURUSD": "rates+fx",
         "KXSPOTIFYD": "media charts", "KXNETFLIXRANKSHOW": "media charts", "KXRT": "media charts", "KXTSAW": "tsa+rain", "KXRAINNYC": "tsa+rain"}
OFFS = [3, 12, 24]
THETAS = [0.03, 0.06, 0.10]


def groups(series):
    ev = collections.defaultdict(list)
    for r in L.load(series):
        if r.get("e"):
            ev[r["e"]].append(r)
    return sorted(ev.items(), key=lambda kv: kv[1][0]["ct"])


def null_bounds(ms, qs):
    """interval of the null uniform in which each market resolves yes (see lib_c.null_wins)."""
    mids = np.array([max(0.003, (q[0] + q[1]) / 2) if q else 0.003 for q in qs])
    types = [r.get("st") for r in ms]
    if all(t in ("greater", "less") for t in types):
        return [((0.0, m) if t == "greater" else (1.0 - m, 1.0)) for t, m in zip(types, mids)]
    cum = np.concatenate([[0], np.cumsum(mids / mids.sum())])
    return [(cum[i], cum[i + 1]) for i in range(len(ms))]


def gas_model(evs):
    """-> {event: (mu, sd)} for the daily AAA price: momentum on the last published prices, walk-forward."""
    price = [(e, next((r["ev"] for r in ms if r["ev"] is not None), None)) for e, ms in evs]
    out = {}
    for i in range(len(price)):
        hist = [p for _, p in price[max(0, i - 62):i]]
        if len(hist) < 25 or any(h is None for h in hist[-3:]):
            continue
        h = [x for x in hist if x is not None]
        d = np.diff(h)
        x, y = d[:-1], d[1:]
        phi = float((x * y).sum() / max(1e-12, (x * x).sum()))
        phi = min(1.0, max(0.0, phi))
        sd = max(0.002, float(np.std(y - phi * x)))
        out[price[i][0]] = (h[-1] + phi * (h[-1] - h[-2]), sd)
    return out


def build():
    U = L.Units(); counts = {}
    for s, k in CLASS.items():
        evs = groups(s)
        nq = sum(1 for _, ms in evs for r in ms if r["q"])
        counts[s] = {"class": k, "settled_markets": sum(len(ms) for _, ms in evs), "with_quotes": nq, "events": len(evs), "used": nq >= 300}
        if nq < 300:
            continue
        gm = gas_model(evs) if s == "KXAAAGASD" else {}
        for e, ms in evs:
            ms.sort(key=lambda r: (r.get("fs") or 0, r["t"]))
            day = time.strftime("%Y-%m-%d", time.gmtime(ms[0]["ct"]))
            for off in OFFS:
                qs = [L.quote(r, off) for r in ms]
                if not any(qs):
                    continue
                nb = null_bounds(ms, qs)
                for r, q, (lo, hi) in zip(ms, qs, nb):
                    if not q:
                        continue
                    yes = 1.0 if r["res"] == "yes" else 0.0
                    pm = np.nan
                    if e in gm and r.get("st") == "greater" and r.get("fs") is not None:
                        mu, sd = gm[e]
                        pm = 1 - L.ncdf((float(r["fs"]) - mu) / sd)
                    for side, p in L.sides(*q):
                        U.add(series=s, klass=k, event=e, day=day, T=str(off), side=side, p=p, win=yes if side == "yes" else 1 - yes,
                              nlo=lo, nhi=hi, band=L.band_of(p), e_gas=(pm if side == "yes" else 1 - pm) - p - L.fee(p))
    return U.finish(), counts


def econ_table():
    """descriptive only. Favourite = the highest-priced market of an event 24 h before the close (the release)."""
    out = []
    for s in GROUPS["econ"]:
        evs = groups(s)
        row = {"series": s, "events": len(evs), "markets": sum(len(ms) for _, ms in evs)}
        for off in (24, 3):
            favs = []; sq = []
            for e, ms in evs:
                qs = [(r, L.quote(r, off)) for r in ms]
                qs = [(r, q) for r, q in qs if q and q[1] - q[0] <= 0.06 and q[1] < 1]
                for r, q in qs:
                    sq.append((((q[0] + q[1]) / 2) - (r["res"] == "yes")) ** 2)
                if qs:
                    r, q = max(qs, key=lambda x: x[1][1])
                    p = q[1]
                    favs.append((p, 1.0 if r["res"] == "yes" else 0.0))
            if favs:
                p = np.array([f[0] for f in favs]); w = np.array([f[1] for f in favs])
                row[f"{off}h"] = {"events_quoted": len(favs), "favourite_avg_ask": round(float(p.mean()), 3), "favourite_won": round(float(w.mean()), 3),
                                  "edge_per_$_buying_favourite": round(float((w - p - 0.07 * p * (1 - p)).sum() / p.sum()), 4),
                                  "brier_mid_all_markets": round(float(np.mean(sq)), 4), "markets_quoted": len(sq)}
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=300)
    a = ap.parse_args()
    U, counts = build()
    res = {"generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "series": counts, "econ_descriptive": econ_table()}
    if U.n:
        c = U.col
        days = sorted(set(c["day"]))
        cutoff = days[int(len(days) * 0.75)]
        cells = {}
        for k in sorted(set(c["klass"])):
            for off in OFFS:
                for side in ("yes", "no"):
                    m = (c["klass"] == k) & (c["T"] == str(off)) & (c["side"] == side)
                    for bi, (lo, hi) in enumerate(L.BANDS):
                        cells[f"{k} | price band {int(lo*100)}-{int(hi*100)}c | {off}h before close | buy {side}"] = m & (c["band"] == bi)
        for off in OFFS:
            for side in ("yes", "no"):
                for th in THETAS:
                    cells[f"gas momentum model says underpriced by >= {int(th*100)}c | {off}h before close | buy {side}"] = \
                        (c["series"] == "KXAAAGASD") & (c["T"] == str(off)) & (c["side"] == side) & (np.nan_to_num(c["e_gas"], nan=-9) >= th)
        R = L.run_family(U, cells, c["day"] < cutoff, n_sims=a.sims, label="other recurring series")
        R.update(units=U.n, days=len(days), first_day=days[0], last_day=days[-1], test_from=cutoff)
        res["family"] = R
        print(f"other: units {U.n}, days {len(days)}, test from {cutoff}, eligible {R['cells_eligible']}/{R['cells_defined']}, null p95 t {R['null_max_t_p95']}, carried {len(R['carried'])}, survive {len(R['survive'])}")
    json.dump(res, open(os.path.join(L.HERE, "results_other.json"), "w"), indent=1)
    print("wrote results_other.json")


if __name__ == "__main__":
    main()
