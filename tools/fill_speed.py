"""Signal -> fill per account, in seconds, ticks and $ (day-speed 2026-11-20). Read-only report on the PC's day files.

    python -X utf8 tools/fill_speed.py [--days-dir data/pc_days] [--json out.json]

Reads data/pc_days/<day>/fills.jsonl.gz (engine/datapipe.day_fills: every MARKET entry order, every account: sent time, fill
time, fill price) and the same day's bars/<ROOT>_1m.csv.gz for the fill bar's open (the price the backtests fill at). Days
packed before fills.jsonl.gz existed (before 2026-11-21) have no send / fill seconds: their entries come from trades.jsonl.gz
(the ledger stamp, taken AFTER the fill and the bracket) and are marked "stamp only".
Per account (book): n, seconds open -> sent and sent -> filled (median / worst), ticks past the open (median / worst), and $
past the backtest (which counts 1 tick): (ticks - 1) x $0.50 per micro (MNQ) / $5.00 per mini (NQ) x the filled quantity.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK = 0.25


def _jl(path):
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return [json.loads(x) for x in fh if x.strip()]
    except (OSError, ValueError):
        return []


def _opens(day_dir) -> dict:
    import pandas as pd
    out = {}
    for f in sorted(glob.glob(os.path.join(day_dir, "bars", "*_1m.csv.gz"))):
        try:
            b = pd.read_csv(f)
            out.update(dict(zip(b["time"].astype("int64"), b["open"].astype(float))))
        except Exception:
            continue
    return out


def tick_usd(instrument: str) -> float:
    return 5.0 if str(instrument or "").upper().startswith("NQ") else 0.5


def collect(days_dir: str) -> list:
    rows = []
    for d in sorted(glob.glob(os.path.join(days_dir, "????-??-??"))):
        day = os.path.basename(d)
        opens = _opens(d)
        fills = [r for r in _jl(os.path.join(d, "fills.jsonl.gz")) if r.get("fill_px") and r.get("filled")]
        if fills:
            for r in fills:
                side = 1 if str(r.get("action", "")).upper() == "BUY" else -1
                op = opens.get(int(r["entry_t"]))
                ticks = None if op is None else round((float(r["fill_px"]) - op) * side / TICK, 2)
                rows.append({"day": day, "book": r.get("book") or "?", "entry_t": int(r["entry_t"]), "qty": int(r["filled"]),
                             "instrument": r.get("instrument"), "open": op, "fill": float(r["fill_px"]), "ticks": ticks,
                             "sent_s": r.get("sent_s_after_open"), "fill_s": r.get("fill_s_after_sent"), "src": "fills"})
            continue
        for r in _jl(os.path.join(d, "trades.jsonl.gz")):        # older days: the ledger stamp only
            legs = [lg for lg in ((r.get("result") or {}).get("legs") or []) if lg.get("fill_px") and lg.get("filled")]
            if r.get("side") not in ("buy", "sell") or r.get("mode") != "live" or not legs:
                continue
            q = sum(int(lg["filled"]) for lg in legs)
            px = sum(float(lg["fill_px"]) * int(lg["filled"]) for lg in legs) / q
            side = 1 if r["side"] == "buy" else -1
            op = opens.get(int(r["entry_t"]))
            rows.append({"day": day, "book": str(r.get("bot") or "?"), "entry_t": int(r["entry_t"]), "qty": q,
                         "instrument": (legs[0].get("instrument") or "MNQ"), "open": op, "fill": px,
                         "ticks": None if op is None else round((px - op) * side / TICK, 2),
                         "sent_s": None, "fill_s": None, "stamp_s": int(r["t"]) - int(r["entry_t"]), "src": "stamp only"})
    for r in rows:
        r["usd_vs_backtest"] = None if r["ticks"] is None else round((r["ticks"] - 1.0) * tick_usd(r["instrument"]) * r["qty"], 2)
    return rows


def summary(rows) -> dict:
    out = {}
    for book in sorted({r["book"] for r in rows}):
        R = [r for r in rows if r["book"] == book]
        def med_worst(k):
            v = [float(r[k]) for r in R if r.get(k) is not None]
            return (round(statistics.median(v), 2), round(max(v), 2)) if v else (None, None)
        out[book] = {"n": len(R), "with_seconds": sum(1 for r in R if r.get("sent_s") is not None),
                     "sent_s": med_worst("sent_s"), "fill_s": med_worst("fill_s"), "ticks": med_worst("ticks"),
                     "usd_vs_backtest": med_worst("usd_vs_backtest"),
                     "usd_total": round(sum(r["usd_vs_backtest"] or 0 for r in R), 2)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -X utf8 tools/fill_speed.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--days-dir", default=os.path.join(ROOT, "data", "pc_days"))
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    rows = collect(a.days_dir)
    s = summary(rows)
    print("  account | entries | open->sent s (med / worst) | sent->filled s | ticks past open (med / worst) | $ past backtest (med / worst / total)")
    for b, x in s.items():
        print(f"  {b:<8}| {x['n']:>3} ({x['with_seconds']} timed) | {x['sent_s'][0]} / {x['sent_s'][1]} | {x['fill_s'][0]} / {x['fill_s'][1]} "
              f"| {x['ticks'][0]} / {x['ticks'][1]} | ${x['usd_vs_backtest'][0]} / ${x['usd_vs_backtest'][1]} / ${x['usd_total']}")
    if not rows:
        print("  no live fills in", a.days_dir, "(python tools/data_pull.py --latest pulls the PC's days)")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"rows": rows, "by_account": s}, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
