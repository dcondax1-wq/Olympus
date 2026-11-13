#!/usr/bin/env python3
"""K1 study 1: a fair-value MODEL for Kalshi's hourly Nasdaq-100 / S&P 500 above/below markets vs the market's quotes.

Model, all point-in-time:
  level  F = futures price at the decision minute (NQ1! 1m / ES1! 5m, TradingView CME exports) minus the basis
           (futures - index) seen at the most recent Kalshi settlement at or before the decision (same contract only);
  sigma  per-minute vol from a mix of the prior day's VXN/VIX close and the futures' realised vol over the last 60 min,
         scaled by fitted factors (one extra factor when the 09:30 cash open is inside the window);
  shape  Student-t, degrees of freedom fitted.
  p(YES) = P(index at close > strike).
Fitted on TRAIN only (settle before 2026-07-01) by log-loss; TEST = 2026-07-01 .. 2026-10-16 (the futures files end there).
Trading rule: taker buy YES at the ask / NO at 100 - bid when model edge after the fee (0.07 p(1-p), rounded up per contract)
is >= a threshold chosen on TRAIN. Cluster bootstrap by settle time (one event = one cluster).

    python research/kalshi_edge_K1/analyze_index.py [--series KXNASDAQ100U]
"""
import argparse, bisect, datetime as dt, gzip, json, math, os, sys
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk, futures, stats

HERE = os.path.dirname(os.path.abspath(__file__))
ET = ZoneInfo("America/New_York")
SPLIT = int(dt.datetime(2026, 7, 1, tzinfo=ET).timestamp())
HORIZONS = (55, 30, 10)
UNDER = {"KXNASDAQ100U": ("NQ", futures.VXN), "KXINXU": ("ES", futures.VIX)}


def tcdf(x, nu):
    if nu is None or nu > 100:
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    # standardised t (unit variance): scale x by sqrt(nu/(nu-2)), regularized incomplete beta via continued fraction
    x = x * math.sqrt(nu / (nu - 2))
    tt = nu / (nu + x * x)
    ib = betainc(nu / 2, 0.5, tt)
    return 1 - 0.5 * ib if x > 0 else 0.5 * ib


def betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbeta) * cf(a, b, x) / a
    return 1 - math.exp(lbeta) * cf(b, a, 1 - x) / b


def cf(a, b, x, it=200, eps=1e-12):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-30 else 1e-30)
    h = d
    for m in range(1, it):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + aa / c if abs(c) > 1e-30 else 1e-30
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + aa / c if abs(c) > 1e-30 else 1e-30
        de = d * c
        h *= de
        if abs(de - 1) < eps:
            break
    return h


def quote(c, m):
    """state of the book at m minutes before close: the latest 1-min candle ending at or before that minute."""
    for k in range(m, 67):
        q = c.get(str(k))
        if q and q[0] is not None and q[1] is not None:
            return q[0], q[1], k - m
    return None


def build(series):
    sym, volidx = UNDER[series]
    fut = futures.Fut(sym)
    evs = [json.loads(l) for l in gzip.open(os.path.join(kk.DATA, f"idxev_{series}.jsonl.gz"), "rt")]
    bas = []
    for e in sorted(evs, key=lambda e: e["ct"]):
        p = fut.price_at(e["ct"])
        if p and e["ev"]:
            bas.append((e["ct"], p - e["ev"]))
    bt = [b[0] for b in bas]
    rows = []
    for l in gzip.open(os.path.join(kk.DATA, f"idx_{series}.jsonl.gz"), "rt"):
        r = json.loads(l)
        if r["st"] != "greater_or_equal" or r["fs"] is None:
            continue
        ct = r["ct"]
        hour = dt.datetime.fromtimestamp(ct, ET).hour
        vix = futures.prev_close(volidx, dt.datetime.fromtimestamp(ct, ET).date().isoformat())
        for m in HORIZONS:
            t = ct - m * 60
            q = quote(r["c"], m)
            if not q:
                continue
            bid, ask, stale = q
            if not (0 <= bid < ask <= 100):
                continue
            j = bisect.bisect_right(bt, t - 60) - 1
            if j < 0 or fut.rolled_between(bas[j][0], ct) or t - bas[j][0] > 4 * 86400:
                continue
            p0 = fut.price_at(t)
            if not p0:
                continue
            F = p0 - bas[j][1]
            rv = fut.rv(t, 60)
            opn = 1 if hour == 10 else 0
            rows.append({"ct": ct, "m": m, "K": float(r["fs"]) - 0.01, "F": F, "vix": vix or 20.0, "rv": rv, "open": opn,
                         "bid": bid, "ask": ask, "y": 1 if r["res"] == "yes" else 0, "t": r["t"], "vol": r["vol"], "h": hour})
    return rows


def prob(x, P):
    a, b, kopen, nu = P
    v_imp = (x["vix"] / 100) ** 2 / (252 * 390)          # per minute, if all variance were spread over the cash session
    v_rv = x["rv"] if x["rv"] else v_imp
    var = (a * v_imp + b * v_rv) * x["m"] * (kopen if x["open"] else 1.0)
    if var <= 0:
        return None
    z = math.log(x["K"] / x["F"]) / math.sqrt(var)
    return min(max(1 - tcdf(z, nu), 1e-4), 1 - 1e-4)


def logloss(rows, P):
    s = 0.0
    for x in rows:
        p = prob(x, P)
        s -= math.log(p if x["y"] else 1 - p)
    return s / len(rows)


def fit(rows):
    rows = [x for x in rows if 2 <= (x["ask"] + x["bid"]) / 2 <= 98] or rows   # the informative strikes
    if len(rows) > 8000:
        rows = rows[:: len(rows) // 8000 + 1]
    best = None
    for nu in (3, 4, 6, 10, None):
        for a in (0.0, 0.5, 1.0, 1.5, 2.0):
            for b in (0.0, 0.5, 1.0, 1.5):
                if a == 0 and b == 0:
                    continue
                for ko in (1.0, 1.5, 2.0, 3.0):
                    P = (a, b, ko, nu)
                    ll = logloss(rows, P)
                    if best is None or ll < best[0]:
                        best = (ll, P)
    return best


def trades(rows, P, thr, horizon=None):
    out = []
    for x in rows:
        if horizon and x["m"] != horizon:
            continue
        p = prob(x, P)
        a, b = x["ask"], x["bid"]
        ey = 100 * p - a - kk.fee_c(a) if 1 <= a <= 99 else -999
        en = 100 * (1 - p) - (100 - b) - kk.fee_c(100 - b) if 1 <= b <= 99 else -999
        if ey >= thr and ey >= en:
            out.append((x["ct"], (100 if x["y"] else 0) - a - kk.fee_c(a), a))
        elif en >= thr:
            out.append((x["ct"], (0 if x["y"] else 100) - (100 - b) - kk.fee_c(100 - b), 100 - b))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="KXNASDAQ100U")
    a = ap.parse_args()
    rows = build(a.series)
    tr = [x for x in rows if x["ct"] < SPLIT]
    te = [x for x in rows if x["ct"] >= SPLIT]
    print(a.series, "rows", len(rows), "train", len(tr), "test", len(te))
    ll, P = fit(tr)
    print("fit", P, "train logloss", round(ll, 4))
    out = {"series": a.series, "split": "2026-07-01", "n_train_rows": len(tr), "n_test_rows": len(te), "params": P, "horizons": {}}

    def brier(rs):
        bm = bq = 0.0; lm = lq = 0.0
        for x in rs:
            p = prob(x, P); mid = min(max((x["bid"] + x["ask"]) / 200, 0.005), 0.995)
            bm += (mid - x["y"]) ** 2; bq += (p - x["y"]) ** 2
            lm -= math.log(mid if x["y"] else 1 - mid); lq -= math.log(p if x["y"] else 1 - p)
        n = max(len(rs), 1)
        return {"n": len(rs), "brier_market_mid": round(bm / n, 5), "brier_model": round(bq / n, 5),
                "logloss_market_mid": round(lm / n, 4), "logloss_model": round(lq / n, 4)}

    for m in HORIZONS:
        trm = [x for x in tr if x["m"] == m]; tem = [x for x in te if x["m"] == m]
        # only rows with a real market (spread <= 10c, mid between 3 and 97): the far strikes are 0/100 and uninformative
        live = lambda rs: [x for x in rs if x["ask"] - x["bid"] <= 10 and 3 <= (x["ask"] + x["bid"]) / 2 <= 97]
        h = {"skill_train": brier(live(trm)), "skill_test": brier(live(tem)), "spread_med_c": None}
        sp = sorted(x["ask"] - x["bid"] for x in live(tem))
        h["spread_med_c"] = sp[len(sp) // 2] if sp else None
        best = None
        for thr in (2, 4, 6, 8, 10, 15):
            b = stats.block(trades(trm, P, thr))
            if b.get("n", 0) >= 50 and (best is None or b["edge_per_usd"] > best[1]["edge_per_usd"]):
                best = (thr, b)
        if best:
            thr = best[0]
            h["thr_c"] = thr
            h["train"] = best[1]
            h["test"] = stats.block(trades(tem, P, thr))
        h["all_thr_test"] = {str(t): stats.block(trades(tem, P, t)) for t in (2, 4, 6, 8, 10, 15)}
        h["all_thr_train"] = {str(t): stats.block(trades(trm, P, t)) for t in (2, 4, 6, 8, 10, 15)}
        out["horizons"][str(m)] = h
        print(m, "min:", json.dumps({k: h.get(k) for k in ("skill_train", "skill_test", "spread_med_c", "thr_c", "train", "test")}))
    # control: buy YES at the ask on every live row (spread <= 10c, mid 3-97) at 30 min, test block: the taker cost alone
    ctl = [(x["ct"], (100 if x["y"] else 0) - x["ask"] - kk.fee_c(x["ask"]), x["ask"]) for x in te
           if x["m"] == 30 and x["ask"] - x["bid"] <= 10 and 3 <= (x["ask"] + x["bid"]) / 2 <= 97 and 1 <= x["ask"] <= 99]
    out["control_buy_all_yes_30m_test"] = stats.block(ctl)
    print("control buy-all YES 30 min, test:", json.dumps(out["control_buy_all_yes_30m_test"]))
    json.dump(out, open(os.path.join(HERE, f"results_index_{a.series}.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
