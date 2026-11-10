#!/usr/bin/env python3
"""Kalshi edge, team A: calibration / base-rate walk-forward on REAL market quotes (public API snapshots from harvest.py).

Unit of analysis: (settled market, minutes-before-close bucket, side). We BUY at the quoted ask (yes: ask, no: 1 - yes bid), so spread and
Kalshi's fee are paid. Fee per contract = 0.07 * p * (1 - p) (the formula the bot's own P&L was checked against; Kalshi rounds up to the cent,
which only makes costs slightly higher). Net result per $1 staked = (win - p - fee) / p.

Protocol (fixed before looking at the held-out block):
  * TRAIN = everything closing before the cutoff, TEST = the last block (default last 14 days). Cells are chosen on TRAIN only.
  * Cells: asset class x time-to-close bucket x side x entry-price band. Eligible: n >= MIN_N and >= MIN_CLUSTERS independent clusters.
  * Multiple testing: ~300 cells are tested, so a cell must beat the 95th percentile of the MAX t-statistic over all cells in a
    market-calibrated null simulation (outcomes drawn at the market mid price, one uniform per close-time cluster so strikes of the same
    ladder move together). This is the permutation / shuffle baseline. Only cells that pass are carried to TEST.
  * TEST verdict per carried cell: point edge > 0 AND cluster-bootstrap one-sided 95% lower bound > 0 (Bonferroni over carried cells).
Everything is cluster-robust: trades that close at the same time in the same asset class are ONE cluster (a BTC move settles a whole ladder at once).

    python research/kalshi_edge_A/analyze.py [--test-days 14] [--sims 400]
"""
import argparse, glob, json, math, os, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "results.json")
MIN_N, MIN_CL = 150, 40
MAX_SPREAD = 0.04
BANDS = [(0.01, 0.10), (0.10, 0.30), (0.30, 0.50), (0.50, 0.70), (0.70, 0.90), (0.90, 0.95), (0.95, 0.98), (0.98, 0.995)]
TBUCK = {"T2-5m": (2, 5), "T10-30m": (10, 30), "T60-240m": (60, 240)}
OFF_USE = {"T2-5m": ["2", "5"], "T10-30m": ["10", "20", "30"], "T60-240m": ["60", "120", "240"]}


def klass(s):
    if s.endswith("15M"):
        return "15min " + ("crypto" if s[:5] in ("KXBTC", "KXETH", "KXSOL", "KXXRP", "KXDOG") else "other")
    if s.startswith(("KXBTC", "KXETH", "KXSOL", "KXXRP", "KXDOGE")):
        return "hourly crypto above/below" if s.endswith("D") else "hourly crypto range"
    if s.startswith(("KXINX", "KXNASDAQ")):
        return "index"
    if s.startswith(("KXGOLD", "KXWTI")):
        return "gold/oil"
    if s.startswith("KXHIGH"):
        return "weather high"
    return "other"


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 1)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / 2 / n) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / d
    return (c - h, c + h)


def load():
    rows = []
    for fn in sorted(glob.glob(os.path.join(DATA, "snap_*.jsonl"))):
        for ln in open(fn):
            r = json.loads(ln)
            rows.append(r)
    return rows


def build(rows):
    """-> dict of numpy arrays, one entry per (market, bucket, side). One offset per market/bucket (the latest valid one in the bucket)."""
    rec = []
    for r in rows:
        k = klass(r["s"])
        yes = 1 if r["res"] == "yes" else 0
        for bn, offs in OFF_USE.items():
            q = None
            for o in offs:
                if o in r["q"]:
                    q = r["q"][o]
                    break
            if not q:
                continue
            ask, bid = q[0], q[1]
            if ask - bid > MAX_SPREAD or ask <= 0 or bid >= 1 or ask < bid:
                continue
            mid = (ask + bid) / 2
            # buy yes at ask ; buy no at 1-bid
            for side, p, win in (("yes", ask, yes), ("no", 1 - bid, 1 - yes)):
                if p < 0.01 or p > 0.995:
                    continue
                fee = 0.07 * p * (1 - p)
                rec.append((k, bn, side, p, win, fee, mid if side == "yes" else 1 - mid, r["ct"], k + "|" + str(r["ct"] // 60), q[2], r["s"]))
    cols = list(zip(*rec))
    names = ["klass", "buck", "side", "p", "win", "fee", "pm", "ct", "cl", "qvol", "series"]
    return {n: (np.array(c) if n not in ("klass", "buck", "side", "cl", "series") else np.array(c, dtype=object)) for n, c in zip(names, cols)}


def band_of(p):
    for i, (a, b) in enumerate(BANDS):
        if a <= p < b or (i == len(BANDS) - 1 and p == b):
            return i
    return -1


def cell_stats(pnl, cost, cl):
    """pnl/cost arrays, cl cluster labels -> (n, n_cl, edge, t_cluster)."""
    n = len(pnl)
    S, C = pnl.sum(), cost.sum()
    edge = S / C
    # cluster-robust SE of the ratio estimator S/C
    u, inv = np.unique(cl, return_inverse=True)
    resid = np.bincount(inv, weights=pnl - edge * cost, minlength=len(u))
    se = math.sqrt((resid ** 2).sum()) / C if C > 0 else float("nan")
    return n, len(u), edge, (edge / se if se > 0 else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-days", type=int, default=14)
    ap.add_argument("--sims", type=int, default=400)
    a = ap.parse_args()
    t0 = time.time()
    rows = load()
    D = build(rows)
    N = len(D["p"])
    ct = D["ct"].astype(np.int64)
    cutoff = int(ct.max()) - a.test_days * 86400
    tr = ct < cutoff
    band = np.array([band_of(p) for p in D["p"]])
    pnl = (D["win"] - D["p"] - D["fee"])  # per 1 contract
    cost = D["p"]
    keys = [(k, b, s, bi) for k in sorted(set(D["klass"])) for b in TBUCK for s in ("yes", "no") for bi in range(len(BANDS))]
    idx = {}
    for key in keys:
        m = (D["klass"] == key[0]) & (D["buck"] == key[1]) & (D["side"] == key[2]) & (band == key[3])
        idx[key] = np.where(m)[0]

    def evaluate(mask):
        out = {}
        for key, ii in idx.items():
            j = ii[mask[ii]]
            if len(j) < MIN_N:
                continue
            n, ncl, e, t = cell_stats(pnl[j], cost[j], D["cl"][j])
            if ncl < MIN_CL:
                continue
            out[key] = (n, ncl, e, t)
        return out

    train = evaluate(tr)
    print(f"rows {len(rows)} markets, {N} trade-units, cutoff {time.strftime('%Y-%m-%d', time.gmtime(cutoff))}, eligible train cells {len(train)} of {len(keys)}")

    # ---- permutation / market-calibrated null: max t over eligible cells (train block)
    rng = np.random.default_rng(11)
    ctr = D["cl"][tr]
    ucl, cinv = np.unique(np.array([c for c in D["cl"]]), return_inverse=True)
    maxt = []
    elig = list(train.keys())
    pm = D["pm"]
    for _ in range(a.sims):
        U = rng.random(len(ucl))[cinv]
        yes_sim = np.where(D["side"] == "yes", U < pm, U >= (1 - pm))  # side-aware: for 'no' side, p_no = pm, win iff yes false  ->  U >= pm_yes
        # for no side pm = 1 - mid_yes ; the no-contract wins iff U >= mid_yes = 1 - pm
        pn = yes_sim.astype(float) - D["p"] - D["fee"]
        best = -9
        for key in elig:
            ii = idx[key]
            j = ii[tr[ii]]
            n, ncl, e, t = cell_stats(pn[j], cost[j], D["cl"][j])
            best = max(best, t)
        maxt.append(best)
    thr = float(np.percentile(maxt, 95))
    print(f"null max-t 95th pct = {thr:.2f} (median {np.median(maxt):.2f}), {time.time() - t0:.0f}s")

    # ---- test block
    test = evaluate(~tr)
    cells = []
    for key in keys:
        if key not in train and key not in test:
            continue
        rec = {"cell": " | ".join([key[0], key[1], "buy " + key[2], f"{int(BANDS[key[3]][0]*100)}-{int(BANDS[key[3]][1]*100)}c"])}
        if key in train:
            n, ncl, e, t = train[key]
            rec.update(train_n=n, train_clusters=ncl, train_edge=round(e, 4), train_t=round(t, 2), carried=bool(t > thr and e > 0))
        if key in test:
            n, ncl, e, t = test[key]
            rec.update(test_n=n, test_clusters=ncl, test_edge=round(e, 4), test_t=round(t, 2))
        ii = idx[key]
        j = ii[tr[ii]]
        if len(j):
            rec["train_win"] = round(float(D["win"][j].mean()), 4)
            rec["train_price"] = round(float(D["p"][j].mean()), 4)
            rec["train_mid_gap_pts"] = round(float((D["win"][j] - D["pm"][j]).mean() * 100), 2)
        cells.append(rec)

    # ---- bootstrap CIs for carried cells in test
    carried = [c for c in cells if c.get("carried")]
    nc = max(1, len(carried))
    bs = np.random.default_rng(5)
    for c in carried:
        key = next(k for k in keys if " | ".join([k[0], k[1], "buy " + k[2], f"{int(BANDS[k[3]][0]*100)}-{int(BANDS[k[3]][1]*100)}c"]) == c["cell"])
        ii = idx[key]
        j = ii[~tr[ii]]
        if len(j) == 0:
            continue
        u, inv = np.unique(D["cl"][j], return_inverse=True)
        sp = np.bincount(inv, weights=pnl[j]); sc = np.bincount(inv, weights=cost[j])
        eds = []
        for _ in range(2000):
            s = bs.integers(0, len(u), len(u))
            eds.append(sp[s].sum() / sc[s].sum())
        alpha = 0.05 / nc
        c["test_ci_lo_bonf"] = round(float(np.percentile(eds, alpha * 100)), 4)
        c["test_ci95"] = [round(float(np.percentile(eds, 2.5)), 4), round(float(np.percentile(eds, 97.5)), 4)]
        wk = int(D["win"][j].sum()); c["test_win_ci"] = [round(x, 4) for x in wilson(wk, len(j))]
        c["survives"] = bool(c["test_edge"] > 0 and c["test_ci_lo_bonf"] > 0)

    # ---- pure calibration by band (mid price, no fees, no spread): where is the market wrong at all? train and test side by side.
    # Also the "maker at mid" counterfactual: buy the YES at mid with NO fee and NO spread (an upper bound for a resting order that always
    # fills, which real maker orders do not: adverse selection). If even that is not positive out of sample, makers cannot help either.
    calib = []
    for k in sorted(set(D["klass"])):
        for bi, (lo, hi) in enumerate(BANDS):
            row = {"class": k, "band": f"{int(lo*100)}-{int(hi*100)}c"}
            ok = False
            for blk, mask in (("train", tr), ("test", ~tr)):
                m = (D["klass"] == k) & (D["side"] == "yes") & (D["pm"] >= lo) & (D["pm"] < hi) & (D["buck"] == "T10-30m") & mask
                n = int(m.sum())
                if n < 60:
                    continue
                w = D["win"][m]
                lo_, hi_ = wilson(int(w.sum()), n)
                cl = D["cl"][m]
                mm = float(D["pm"][m].mean())
                _, ncl, e_mid, t_mid = cell_stats(w - D["pm"][m], D["pm"][m], cl)
                row[blk] = {"n": n, "mid": round(mm, 4), "won": round(float(w.mean()), 4), "gap_pts": round(float((w.mean() - mm) * 100), 2),
                            "won_ci": [round(lo_, 4), round(hi_, 4)], "maker_mid_edge_per_$": round(e_mid, 4), "t_cluster": round(t_mid, 2)}
                ok = True
            if ok:
                calib.append(row)

    # ---- overall, per class, taker cost of simply buying everything
    overall = []
    for k in sorted(set(D["klass"])):
        for b in TBUCK:
            for blk, mask in (("train", tr), ("test", ~tr)):
                m = (D["klass"] == k) & (D["buck"] == b) & mask
                if m.sum() < 50:
                    continue
                n, ncl, e, t = cell_stats(pnl[m], cost[m], D["cl"][m])
                overall.append({"class": k, "bucket": b, "block": blk, "n": n, "edge_all_buys": round(e, 4)})

    # ---- pre-specified pooled candidates (longshot / favourite bias, the textbook hypothesis; NOT picked from the cells above).
    # Written down before the held-out block was read: buy the side priced >= 90c ("favourite") or equivalently sell the <= 10c longshot.
    # Bonferroni over these 7 tests.
    def boot(j, rs):
        u, inv = np.unique(D["cl"][j], return_inverse=True)
        sp = np.bincount(inv, weights=pnl[j]); sc = np.bincount(inv, weights=cost[j])
        e = []
        for _ in range(2000):
            q = rs.integers(0, len(u), len(u))
            e.append(sp[q].sum() / sc[q].sum())
        return float(np.percentile(e, 0.05 / 7 * 100)), [float(np.percentile(e, 2.5)), float(np.percentile(e, 97.5))]

    cands = [("Buy any side priced 90c+ (all classes, all times)", lambda: D["p"] >= 0.90),
             ("Buy any side priced 95c+ (all classes, all times)", lambda: D["p"] >= 0.95),
             ("Sell the longshot: buy NO when YES is <= 10c, T-2..5m", lambda: (D["side"] == "no") & (D["p"] >= 0.90) & (D["buck"] == "T2-5m")),
             ("Sell the longshot: buy NO when YES is <= 10c, T-10..30m", lambda: (D["side"] == "no") & (D["p"] >= 0.90) & (D["buck"] == "T10-30m")),
             ("15-min crypto only, side priced 90c+", lambda: (D["klass"] == "15min crypto") & (D["p"] >= 0.90)),
             ("Hourly crypto above/below only, side priced 90c+", lambda: (D["klass"] == "hourly crypto above/below") & (D["p"] >= 0.90)),
             ("Index hourly only, side priced 90c+", lambda: (D["klass"] == "index") & (D["p"] >= 0.90))]
    rs = np.random.default_rng(3)
    prereg = []
    for name, fn in cands:
        m = fn()
        rec = {"candidate": name}
        for blk, mask in (("train", tr), ("test", ~tr)):
            j = np.where(m & mask)[0]
            if len(j) < 30:
                rec[blk] = {"n": int(len(j))}; continue
            n, ncl, e, t = cell_stats(pnl[j], cost[j], D["cl"][j])
            lo_b, ci = boot(j, rs)
            rec[blk] = {"n": n, "clusters": ncl, "win": round(float(D["win"][j].mean()), 4), "price": round(float(D["p"][j].mean()), 4),
                        "edge_per_$": round(e, 4), "ci95": [round(x, 4) for x in ci], "lo_bonf": round(lo_b, 4), "t_cluster": round(t, 2),
                        "avg_pnl_per_contract_$": round(float(pnl[j].mean()), 4)}
        te = rec.get("test", {})
        rec["survives"] = bool(te.get("edge_per_$", -1) > 0 and te.get("lo_bonf", -1) > 0 and rec.get("train", {}).get("edge_per_$", -1) > 0)
        prereg.append(rec)

    res = {"generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "markets": len(rows), "units": int(N),
           "train_end": time.strftime("%Y-%m-%d", time.gmtime(cutoff)), "data_from": time.strftime("%Y-%m-%d", time.gmtime(int(ct.min()))),
           "data_to": time.strftime("%Y-%m-%d", time.gmtime(int(ct.max()))), "null_max_t_p95": round(thr, 3), "null_max_t_median": round(float(np.median(maxt)), 3),
           "cells_tested": len(train), "cells_carried": len(carried), "cells_survive": sum(1 for c in carried if c.get("survives")),
           "carried": carried, "prereg": prereg, "calibration_mid": calib, "overall": overall,
           "top_train_cells": sorted([c for c in cells if "train_t" in c], key=lambda c: -c["train_t"])[:15], "all_cells": cells,
           "protocol": {"min_n": MIN_N, "min_clusters": MIN_CL, "max_spread": MAX_SPREAD, "fee": "0.07*p*(1-p) per contract", "sims": a.sims}}
    json.dump(res, open(OUT, "w"), indent=1)
    print(f"carried {len(carried)}, survive {res['cells_survive']}; wrote {OUT}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
