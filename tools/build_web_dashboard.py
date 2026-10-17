"""Build the PC-off web dashboard (static site) published to the public repo demetrades2000-coder/nq-dashboard (GitHub Pages).

Only results go public: no code, no params beyond the strategy label, no secrets. Inputs are what the cloud monitor already
produces plus the backtest bundle:

  python tools/build_web_dashboard.py --state dash/state.json --chart dash/chart.png --out site
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "tools", "web_public", "index.html")
BACKTEST = os.path.join(ROOT, "research", "lab", "backtest_live.json")


def _load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def build(state_path, chart_path, out):
    os.makedirs(out, exist_ok=True)
    st = _load(state_path, {}) or {}
    bt = _load(BACKTEST, {}) or {}
    ledger = sorted((st.get("ledger") or {}).values(), key=lambda v: v.get("entry", ""), reverse=True)
    live = {k: st.get(k) for k in ("last_run", "first_run", "runs", "health", "eval", "model_state", "position", "strategy",
                                   "equity_filter", "price", "today", "events", "engine_trades")}
    live["ledger"] = ledger[:30]
    results = None
    if bt:
        cum, eq = 0.0, []
        for d in bt.get("days", []):
            cum += d["pnl"]
            eq.append([d["date"], round(cum, 2)])
        trades = bt.get("trades", [])
        results = {"meta": {k: bt["meta"].get(k) for k in ("built", "strategy", "data", "costs", "method")},
                   "periods": bt.get("periods", {}), "months": bt.get("months", {}), "stop_buckets": bt.get("stop_buckets", []),
                   "lessons": bt.get("lessons", {}), "equity": eq,
                   "trades": [{k: t.get(k) for k in ("day", "side", "entry", "stop", "target", "exit_price", "exit", "risk_pts", "qty",
                                                     "risk_usd", "r", "pnl", "half", "report")} for t in trades[-80:]][::-1]}
        for p in results["periods"].values():
            ev = p.get("eval", {}).get("back_to_back", {})
            ev.pop("runs", None)
    data = {"built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "live": live, "results": results}
    with open(os.path.join(out, "data.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"), default=str)
    shutil.copy(TEMPLATE, os.path.join(out, "index.html"))
    if chart_path and os.path.exists(chart_path):
        shutil.copy(chart_path, os.path.join(out, "chart.png"))
    open(os.path.join(out, ".nojekyll"), "w").close()
    print(f"site -> {out}: {len(ledger)} paper trades, results {'yes' if results else 'no'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="dash/state.json")
    ap.add_argument("--chart", default="dash/chart.png")
    ap.add_argument("--out", default="site")
    a = ap.parse_args()
    build(a.state, a.chart, a.out)
