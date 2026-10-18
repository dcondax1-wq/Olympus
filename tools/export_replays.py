"""Session replays for the public dashboard: 5m bars of every trade day of the live-settings replay.

Reads research/lab/backtest_live.json (the trades) and data/NQ_5m.csv (TradingView CME NQ1! futures) and writes
research/lab/replays.json, which tools/build_web_dashboard.py puts into data.json so the PC-off dashboard can step
through each session bar by bar with the trade's sweep, entry, stop, target and exit drawn on it.

  python tools/export_replays.py                 # 2026 trade days (default)
  python tools/export_replays.py --since 2025-01-01
Bars run 07:00-16:00 ET (01:00-16:00 when a trade enters before 07:00, as LIT's London trades do). Prices are stored as integer quarter-points to keep the file small.

LIT model (live_model.json "model": "lit"): replays.json also carries "charts", one chart record per LIT replay trade
(tools/lit_chart_data.py: 5m bars from 2 h before the sweep to 1 h after the exit, 1m bars around the entry, the swept levels,
inducement, sweep extreme, CISD levels, limit, 1m confirmation, breakeven and exit), keyed by <date>_<HHMM ET>_<long|short>.
tools/build_web_dashboard.py writes each one to site/replays/<id>.json (the phone loads them lazily; data.json keeps only the
ids); the PC serves them at /api/next/tradechart/<id> (engine/next_api.py). --no-charts skips them.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BT = os.path.join(ROOT, "research", "lab", "backtest_live.json")
BARS = os.path.join(ROOT, "data", "NQ_5m.csv")
OUT = os.path.join(ROOT, "research", "lab", "replays.json")
ET = ZoneInfo("America/New_York")


def main(since: str, charts: bool = True) -> None:
    with open(BT, encoding="utf-8") as fh:
        trades = [t for t in json.load(fh)["trades"] if t["day"] >= since]
    days = {t["day"] for t in trades}
    by_day: dict = {d: [] for d in days}
    # the old engine trades New York only (bars from 07:00); LIT enters from 02:00 ET, so its replays start at 01:00
    early = any(dt.datetime.fromtimestamp(int(t["entry_t"]), ET).hour < 7 for t in trades)
    a0 = 60 if early else 420
    with open(BARS, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            t = int(float(row["time"]))
            e = dt.datetime.fromtimestamp(t, ET)
            d = e.strftime("%Y-%m-%d")
            if d not in by_day:
                continue
            mod = e.hour * 60 + e.minute
            if a0 <= mod < 960:
                by_day[d].append([t] + [round(float(row[k]) * 4) for k in ("open", "high", "low", "close")])
    out = []
    for t in sorted(trades, key=lambda x: x["entry_t"]):
        bars = sorted(by_day.get(t["day"], []))
        if not bars:
            continue
        out.append({"day": t["day"], "entry_t": t["entry_t"], "t0": bars[0][0],
                    "dt": [round((b[0] - bars[0][0]) / 300) for b in bars],    # bar index (5m steps) from t0
                    "o": [b[1] for b in bars], "h": [b[2] for b in bars], "l": [b[3] for b in bars], "c": [b[4] for b in bars]})
    bundle = {"built": dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M"), "source": "TradingView CME NQ1! 5m (data/NQ_5m.csv)",
              "scale": 4, "sessions": out}
    with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
        lit_model = json.load(fh).get("model") == "lit"
    if charts and lit_model:
        import sys
        sys.path.insert(0, ROOT)
        from tools.lit_chart_data import build
        recs = build(since)
        bundle["charts"] = recs
        bundle["charts_source"] = ("TradingView CME NQ1! 5m (data/NQ_5m.csv) + 1m (data/NQ_1m.csv, on the 5m price basis); "
                                   "tools/lit_chart_data.py")
        # each session row names its trade's chart (same day + entry time)
        ids = {(r["day"], r["entry"]["t"]): k for k, r in recs.items()}
        for s_ in out:
            k = ids.get((s_["day"], int(s_["entry_t"])))
            if k:
                s_["chart"] = k
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, separators=(",", ":"))
    print(f"replays -> {OUT}: {len(out)} sessions, {len(bundle.get('charts') or {})} trade charts, {os.path.getsize(OUT) // 1024} KB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-01-01")
    ap.add_argument("--no-charts", action="store_true", help="skip the LIT trade chart records")
    a = ap.parse_args()
    main(a.since, not a.no_charts)
