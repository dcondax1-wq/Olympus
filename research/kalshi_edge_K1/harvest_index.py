#!/usr/bin/env python3
"""K1 harvest: Kalshi Nasdaq-100 / S&P 500 HOURLY above/below markets (KXNASDAQ100U / KXINXU), 10:00-16:00 ET, with
1-minute yes bid/ask + trade candles for the last 66 minutes before close. Public read-only API, no key, no orders.

Strike choice is point-in-time (never uses the outcome): at 60 min before close, the futures-implied index level F
(futures minus the basis seen at the last Kalshi settlement) and sigma from the prior day's VXN/VIX; keep strikes with
|ln(K/F)| <= 2.5 sigma(1h), at most N per event spread evenly over that range.

Writes data/idx_<series>.jsonl.gz, one row per market:
  {t, e, ct, fs, cs, st, res, ev, vol, c: {"<min before close>": [bid, ask, ask_low, bid_high, px_low, px_high, vol]}}
and data/idxev_<series>.jsonl.gz, one row per event: {e, ct, ot, ev, n}.

    python research/kalshi_edge_K1/harvest_index.py --series KXNASDAQ100U [--since 2026-01-02] [--until 2026-10-16] [--n 10]
"""
import argparse, datetime as dt, gzip, json, math, os, sys, time
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk, futures

ET = ZoneInfo("America/New_York")
CUTOFF = kk.ts("2026-09-13T00:00:00")   # /historical/cutoff market_settled_ts
MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
UNDER = {"KXNASDAQ100U": ("NQ", futures.VXN), "KXINXU": ("ES", futures.VIX)}
WIN = 66


def event_ticker(series, d, h):
    return f"{series}-{d.year % 100:02d}{MON[d.month - 1]}{d.day:02d}H{h:02d}00"


def markets(et, ct):
    if ct < CUTOFF:
        d = kk.get("/historical/markets", {"event_ticker": et, "limit": 1000})
    else:
        d = kk.get("/markets", {"event_ticker": et, "limit": 1000})
    return [m for m in (d or {}).get("markets", []) if m.get("result") in ("yes", "no")]


def g(x, *names):
    for n in names:
        if isinstance(x, dict) and x.get(n) is not None:
            return x[n]
    return None


def compact(cands, ct):
    out = {}
    for k in cands:
        m = (ct - k["end_period_ts"]) // 60
        if m < 0 or m > WIN:
            continue
        ya, yb, px = k.get("yes_ask") or {}, k.get("yes_bid") or {}, k.get("price") or {}
        row = [kk.cents(g(yb, "close_dollars", "close")), kk.cents(g(ya, "close_dollars", "close")),
               kk.cents(g(ya, "low_dollars", "low")), kk.cents(g(yb, "high_dollars", "high")),
               kk.cents(g(px, "low_dollars", "low")), kk.cents(g(px, "high_dollars", "high")),
               int(round(kk.fl(g(k, "volume_fp", "volume")) or 0))]
        out[str(m)] = row
    return out


def candles(series, ms, ct):
    lo, hi = ct - WIN * 60 - 60, ct
    if ct >= CUTOFF:
        d = kk.get("/markets/candlesticks", {"market_tickers": ",".join(m["ticker"] for m in ms), "start_ts": lo, "end_ts": hi, "period_interval": 1})
        res = {}
        for mk in (d or {}).get("markets", []):
            res[g(mk, "market_ticker", "ticker")] = compact(mk.get("candlesticks", []), ct)
        return res
    import concurrent.futures as cf

    def one(m):
        d = kk.get(f"/historical/markets/{m['ticker']}/candlesticks", {"start_ts": lo, "end_ts": hi, "period_interval": 1})
        return m["ticker"], compact((d or {}).get("candlesticks", []), ct)
    with cf.ThreadPoolExecutor(3) as ex:
        return dict(ex.map(one, ms))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="KXNASDAQ100U")
    ap.add_argument("--since", default="2026-01-02")
    ap.add_argument("--until", default="2026-10-16")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--zmax", type=float, default=2.5)
    a = ap.parse_args()
    sym, volidx = UNDER[a.series]
    fut = futures.Fut(sym)
    d0, d1 = dt.date.fromisoformat(a.since), dt.date.fromisoformat(a.until)
    os.makedirs(kk.DATA, exist_ok=True)
    fo = gzip.open(os.path.join(kk.DATA, f"idx_{a.series}.jsonl.gz"), "wt")
    fe = gzip.open(os.path.join(kk.DATA, f"idxev_{a.series}.jsonl.gz"), "wt")
    last_basis = None   # (ct, basis)
    t0, nev, nmk = time.time(), 0, 0
    d = d0
    while d <= d1:
        if d.weekday() < 5:
            for h in range(10, 17):
                ct = int(dt.datetime(d.year, d.month, d.day, h, tzinfo=ET).timestamp())
                if ct > fut.last:
                    break
                et = event_ticker(a.series, d, h)
                ms = markets(et, ct)
                if not ms:
                    continue
                ev = kk.fl(ms[0].get("expiration_value"))
                fe.write(json.dumps({"e": et, "ct": ct, "ot": kk.ts(ms[0]["open_time"]), "ev": ev, "n": len(ms)}) + "\n")
                nev += 1
                # point-in-time strike selection at 60 min before close
                t60 = ct - 3600
                sel = []
                if last_basis and not fut.rolled_between(last_basis[0], ct) and fut.price_at(t60):
                    F = fut.price_at(t60) - last_basis[1]
                    v = futures.prev_close(volidx, dt.datetime.fromtimestamp(ct, ET).date().isoformat())
                    sig = (v or 20) / 100 * math.sqrt(1 / (252 * 6.5)) * (1.5 if h == 10 else 1.0)
                    cand = []
                    for m in ms:
                        k = m.get("floor_strike") if m.get("floor_strike") is not None else m.get("cap_strike")
                        if k is None:
                            continue
                        z = math.log(float(k) / F) / sig
                        if abs(z) <= a.zmax:
                            cand.append((z, m))
                    cand.sort(key=lambda x: x[0])
                    if len(cand) > a.n:
                        step = (len(cand) - 1) / (a.n - 1)
                        cand = [cand[int(round(i * step))] for i in range(a.n)]
                    sel = [m for _, m in cand]
                if sel:
                    cs = candles(a.series, sel, ct)
                    for m in sel:
                        fo.write(json.dumps({"t": m["ticker"], "e": et, "ct": ct, "fs": m.get("floor_strike"), "cs": m.get("cap_strike"),
                                             "st": m.get("strike_type"), "res": m["result"], "ev": ev, "vol": kk.fl(m.get("volume_fp")),
                                             "c": cs.get(m["ticker"], {})}, separators=(",", ":")) + "\n")
                        nmk += 1
                p = fut.price_at(ct)
                if ev and p:
                    last_basis = (ct, p - ev)
            fo.flush(); fe.flush()
            if d.weekday() == 4:
                print(d, "events", nev, "markets", nmk, f"{time.time() - t0:.0f}s", kk.STATS, flush=True)
        d += dt.timedelta(days=1)
    fo.close(); fe.close()
    print("done", a.series, "events", nev, "markets", nmk, f"{time.time() - t0:.0f}s", kk.STATS, flush=True)


if __name__ == "__main__":
    main()
