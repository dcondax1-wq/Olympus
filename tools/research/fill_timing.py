"""Fill timing + slippage per bot from every real NinjaTrader fill in the repo (day-speed 2026-11-20). Read-only research.

    python -X utf8 tools/research/fill_timing.py [--pc-days data/pc_days] [--json out.json]

Sources (whatever is present):
  1. data/pc_days/**: any JSON / JSON.GZ / JSONL dict with "sent_at" + "fill_px" (engine/ninjatrader legs as kept by
     engine/fill_audit._leg_view: sent_at = the bot's clock when the entry order file went out, fill_mtime = NinjaTrader's
     own order-state file time of the fill). Gives the exact split: bar open -> order sent -> fill.
  2. research/second/atlas_fills_why.json (night-nqlive / day atlas-fills, 2026-11-20): the 4 fills known so far, with the
     ledger stamp only (taken AFTER the fill + bracket were confirmed, so an upper bound on the send time).
Bar open = the 1m bar the order filled in (data/NQ_1m.csv: same index points as MNQ).
Timing vs price: backtest twin fills at open + 1 tick. 'price' part = 1 tick (crossing the spread on a 1-2 micro market
order); 'timing' part = the rest (the market moved between the open and the order's arrival).
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TICK = 0.25


def _walk(o, out):
    if isinstance(o, dict):
        if "sent_at" in o and o.get("fill_px") and o.get("entry_t"):
            out.append(o)
        for v in o.values():
            _walk(v, out)
    elif isinstance(o, list):
        for v in o:
            _walk(v, out)


def pc_legs(folder):
    out = []
    if not folder or not os.path.isdir(folder):
        return out
    for dp, _, fs in os.walk(folder):
        for f in fs:
            p = os.path.join(dp, f)
            try:
                if f.endswith(".json.gz"):
                    with gzip.open(p, "rt", encoding="utf-8") as fh:
                        _walk(json.load(fh), out)
                elif f.endswith(".json"):
                    with open(p, encoding="utf-8") as fh:
                        _walk(json.load(fh), out)
                elif f.endswith(".jsonl"):
                    with open(p, encoding="utf-8") as fh:
                        for ln in fh:
                            if ln.strip():
                                _walk(json.loads(ln), out)
            except Exception:
                continue
    seen, uniq = set(), []
    for lg in out:
        k = (lg.get("entry_id") or "", int(lg["entry_t"]), lg.get("instrument"))
        if k not in seen:
            seen.add(k)
            uniq.append(lg)
    return uniq


def bar_open(t1m):
    import pandas as pd
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    return dict(zip(df["time"].astype("int64"), df["open"].astype(float)))


def analyse(pc_days=None):
    rows = []
    legs = pc_legs(pc_days or os.path.join(ROOT, "data", "pc_days"))
    if legs:
        o1 = bar_open(None)
        for lg in legs:
            sent = float(lg["sent_at"])
            b = int(sent // 60 * 60)
            op = o1.get(b)
            d = int(lg.get("dir") or (1 if str(lg.get("side", "")).upper() == "BUY" else -1))
            fm = float(lg["fill_mtime"]) if lg.get("fill_mtime") else None
            slip = None if op is None else (float(lg["fill_px"]) - op) * d / TICK
            rows.append({"src": "pc_days leg", "instrument": lg.get("instrument"), "entry_t": int(lg["entry_t"]), "dir": d,
                         "qty": lg.get("filled") or lg.get("qty"), "bar_open_t": b, "sent_s_after_open": round(sent - b, 3),
                         "fill_s_after_sent": None if fm is None else round(fm - sent, 3), "open": op,
                         "fill": float(lg["fill_px"]), "ticks_vs_open": slip})
    known = os.path.join(ROOT, "research", "second", "atlas_fills_why.json")
    have = {r["entry_t"] for r in rows}
    if os.path.exists(known):
        for f in json.load(open(known, encoding="utf-8"))["fills"]:
            if int(f["entry_t"]) in have:
                continue
            rows.append({"src": "ledger stamp (after fill + bracket)", "bot": f["bot"], "member": f.get("member"),
                         "entry_t": int(f["entry_t"]), "et": f["et"], "day": f["day"], "dir": 1 if f["side"] == "BUY" else -1,
                         "qty": f["qty"], "ledger_s_after_open": f["ledger_s_after_open"], "open": f["open"], "model": f["model"],
                         "fill": f["fill"], "ticks_vs_open": f["ticks_vs_open"], "ticks_vs_model": f["ticks_vs_model"],
                         "entry_bar": f["entry_bar"]})
    for r in rows:
        tv = r.get("ticks_vs_open")
        if tv is not None:
            r["price_part_ticks"] = min(1.0, max(tv, 0.0))
            r["timing_part_ticks"] = round(tv - r["price_part_ticks"], 2)
            r["usd_vs_backtest"] = round((tv - 1.0) * TICK * 2.0 * float(r.get("qty") or 1), 2)
    by = {}
    for r in rows:
        by.setdefault(r.get("bot") or r.get("instrument") or "?", []).append(r)
    summ = {k: {"n": len(v), "median_ticks_vs_open": statistics.median([x["ticks_vs_open"] for x in v if x.get("ticks_vs_open") is not None] or [0]),
                "order_type": "MARKET (entry), bracket STOPMARKET + LIMIT (exits: no fill prices recorded)"} for k, v in by.items()}
    return {"rows": rows, "by_bot": summ, "pc_legs": len(legs)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc-days")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    res = analyse(a.pc_days)
    for r in res["rows"]:
        print(json.dumps({k: r.get(k) for k in ("src", "bot", "et", "day", "qty", "sent_s_after_open", "fill_s_after_sent",
                                                 "ledger_s_after_open", "ticks_vs_open", "timing_part_ticks", "usd_vs_backtest")}))
    print(json.dumps(res["by_bot"]))
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
