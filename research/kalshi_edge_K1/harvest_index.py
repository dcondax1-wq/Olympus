#!/usr/bin/env python3
"""K1 harvest: Kalshi Nasdaq-100 / S&P 500 HOURLY above/below markets (KXNASDAQ100U / KXINXU), 10:00-16:00 ET, with
1-minute yes bid/ask + trade candles for the last 66 minutes before close. Public read-only API, no key, no orders.

Strike choice is point-in-time (never uses the outcome): at 60 min before close, the futures-implied index level F
(futures minus the basis seen at the last Kalshi settlement) and sigma from the prior day's VXN/VIX; keep strikes with
|ln(K/F)| <= 2.5 sigma(1h), at most N per event spread evenly over that range.

Three phases: list every event (parallel), choose strikes (local, in time order), fetch candles (parallel, random order,
so a stopped run still holds an even sample of days). Everything is cached (cache/, gitignored): a rerun is free.
Writes data/idx_<series>.jsonl.gz, one row per market:
  {t, e, ct, fs, cs, st, res, ev, vol, c: {"<min before close>": [bid, ask, ask_low, bid_high, px_low, px_high, vol]}}
and data/idxev_<series>.jsonl.gz, one row per event: {e, ct, ot, ev, n}.

    python research/kalshi_edge_K1/harvest_index.py --series KXNASDAQ100U,KXINXU [--since 2026-01-02] [--until 2026-10-16] [--n 6]
"""
import argparse, concurrent.futures as cf, datetime as dt, gzip, json, math, os, random, sys, time
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk, futures

ET = ZoneInfo("America/New_York")
CUTOFF = kk.ts("2026-09-13T00:00:00")   # /historical/cutoff market_settled_ts
MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
UNDER = {"KXNASDAQ100U": ("NQ", futures.VXN), "KXINXU": ("ES", futures.VIX)}
WIN = 66
THREADS = 4


def event_ticker(series, d, h):
    return f"{series}-{d.year % 100:02d}{MON[d.month - 1]}{d.day:02d}H{h:02d}00"


def markets(et, ct):
    if ct < CUTOFF:
        d = kk.get("/historical/markets", {"event_ticker": et, "limit": 1000})
    else:
        d = kk.get("/markets", {"event_ticker": et, "limit": 1000})
    keep = ("ticker", "result", "expiration_value", "open_time", "floor_strike", "cap_strike", "strike_type", "volume_fp")
    return [{k: m.get(k) for k in keep} for m in (d or {}).get("markets", []) if m.get("result") in ("yes", "no")]


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
        out[str(m)] = [kk.cents(g(yb, "close_dollars", "close")), kk.cents(g(ya, "close_dollars", "close")),
                       kk.cents(g(ya, "low_dollars", "low")), kk.cents(g(yb, "high_dollars", "high")),
                       kk.cents(g(px, "low_dollars", "low")), kk.cents(g(px, "high_dollars", "high")),
                       int(round(kk.fl(g(k, "volume_fp", "volume")) or 0))]
    return out


def candles_one(m, ct):
    lo, hi = ct - WIN * 60 - 60, ct
    if ct >= CUTOFF:
        d = kk.get(f"/series/{m['ticker'].split('-')[0]}/markets/{m['ticker']}/candlesticks", {"start_ts": lo, "end_ts": hi, "period_interval": 1})
    else:
        d = kk.get(f"/historical/markets/{m['ticker']}/candlesticks", {"start_ts": lo, "end_ts": hi, "period_interval": 1})
    return compact((d or {}).get("candlesticks", []), ct)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="KXNASDAQ100U,KXINXU")
    ap.add_argument("--since", default="2026-01-02")
    ap.add_argument("--until", default="2026-10-16")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--zmax", type=float, default=2.5)
    a = ap.parse_args()
    d0, d1 = dt.date.fromisoformat(a.since), dt.date.fromisoformat(a.until)
    os.makedirs(kk.DATA, exist_ok=True)
    t0 = time.time()
    jobs, plan = [], {}
    for series in a.series.split(","):
        sym, volidx = UNDER[series]
        fut = futures.Fut(sym)
        evs = []
        d = d0
        while d <= d1:
            if d.weekday() < 5:
                for h in range(10, 17):
                    ct = int(dt.datetime(d.year, d.month, d.day, h, tzinfo=ET).timestamp())
                    if ct <= fut.last:
                        evs.append((event_ticker(series, d, h), ct, h))
            d += dt.timedelta(days=1)
        with cf.ThreadPoolExecutor(THREADS) as ex:
            lists = list(ex.map(lambda e: markets(e[0], e[1]), evs))
        print(series, "listed", len(evs), "events", f"{time.time() - t0:.0f}s", kk.STATS, flush=True)
        last_basis, rows_ev, sel_all = None, [], []
        for (et, ct, h), ms in zip(evs, lists):
            if not ms:
                continue
            ev = kk.fl(ms[0].get("expiration_value"))
            rows_ev.append({"e": et, "ct": ct, "ot": kk.ts(ms[0]["open_time"]), "ev": ev, "n": len(ms)})
            t60 = ct - 3600
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
                for _, m in cand:
                    sel_all.append((m, ct, et, ev))
            p = fut.price_at(ct)
            if ev and p:
                last_basis = (ct, p - ev)
        with gzip.open(os.path.join(kk.DATA, f"idxev_{series}.jsonl.gz"), "wt") as fe:
            for r in rows_ev:
                fe.write(json.dumps(r) + "\n")
        plan[series] = sel_all
        jobs += [(series, i) for i in range(len(sel_all))]
        print(series, "events", len(rows_ev), "selected markets", len(sel_all), flush=True)
    random.Random(1).shuffle(jobs)
    got = {}
    done = [0]

    def work(job):
        series, i = job
        m, ct, et, ev = plan[series][i]
        got[job] = candles_one(m, ct)
        done[0] += 1
        if done[0] % 500 == 0:
            print("candles", done[0], "/", len(jobs), f"{time.time() - t0:.0f}s", kk.STATS, flush=True)
    with cf.ThreadPoolExecutor(THREADS) as ex:
        list(ex.map(work, jobs))
    for series, sel in plan.items():
        with gzip.open(os.path.join(kk.DATA, f"idx_{series}.jsonl.gz"), "wt") as fo:
            for i, (m, ct, et, ev) in enumerate(sel):
                fo.write(json.dumps({"t": m["ticker"], "e": et, "ct": ct, "fs": m.get("floor_strike"), "cs": m.get("cap_strike"),
                                     "st": m.get("strike_type"), "res": m["result"], "ev": ev, "vol": kk.fl(m.get("volume_fp")),
                                     "c": got.get((series, i), {})}, separators=(",", ":")) + "\n")
    print("done", {s: len(v) for s, v in plan.items()}, f"{time.time() - t0:.0f}s", kk.STATS, flush=True)


if __name__ == "__main__":
    main()
