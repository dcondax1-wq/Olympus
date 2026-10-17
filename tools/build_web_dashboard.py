"""Build the PC-off web dashboard (static site) published to the public repo demetrades2000-coder/nq-dashboard (GitHub Pages).

The site is one page (tools/web_public/index.html) that reads everything from data.json; nothing runs on a server.
data.json holds:
  live      the cloud monitor's state (model state, eval tracker, cold-streak filter, paper ledger, recent bars, pools)
  results   the live-settings 5-year replay (periods, months, daily P&L, stop buckets, eval odds, lessons)
  trades    every replay trade with its report (why it entered / plan / result / lessons); 2026 with full detail
  replays   5m session bars for each replay trade day (tools/export_replays.py)
  variants  every tested variant (research/lab/variant_results.json)
  study     trades under review (research/study), charts copied to study/
  cold      the cold-streak filter config, state and its last-15 window
Only results go public: no code, no secrets, no STRATEGY.md text.

  python tools/build_web_dashboard.py --state dash/state.json --chart dash/chart.png --out site
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
LAB = os.path.join(ROOT, "research", "lab")
STUDY = os.path.join(ROOT, "research", "study")
ICONS = os.path.join(ROOT, "web", "icons")

FULL = ("day", "entry_t", "exit_t", "side", "entry", "stop", "target", "exit_price", "exit", "trigger", "grade", "regime",
        "risk_pts", "qty", "risk_usd", "r", "pnl", "half", "pools", "sweep_ext", "zone", "target_label", "conf_tags", "mfe",
        "bars_held", "checklist", "smc", "report")
SLIM_DROP = ("conf_tags", "checklist", "smc", "zone", "pools")


def _load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _trades(bt):
    out = []
    for t in reversed(bt.get("trades") or []):
        row = {k: t.get(k) for k in FULL}
        rep = dict(row.get("report") or {})
        rep.pop("strategy", None)
        row["report"] = rep
        if not str(row["day"]).startswith("2026"):
            for k in SLIM_DROP:
                row.pop(k, None)
        for k in ("mfe", "r", "risk_usd", "pnl"):
            if isinstance(row.get(k), float):
                row[k] = round(row[k], 3)
        out.append(row)
    return out


def _study(out):
    items = []
    if not os.path.isdir(STUDY):
        return items
    os.makedirs(os.path.join(out, "study"), exist_ok=True)
    stems = sorted({os.path.splitext(n)[0] for n in os.listdir(STUDY) if n.endswith((".json", ".png"))}, reverse=True)
    for stem in stems:
        png, js = os.path.join(STUDY, stem + ".png"), os.path.join(STUDY, stem + ".json")
        it = {"id": stem, "date": stem[:10], "title": stem[11:].replace("_", " "), "image": None, "trades": []}
        if os.path.exists(png):
            shutil.copy(png, os.path.join(out, "study", stem + ".png"))
            it["image"] = "study/" + stem + ".png"
        d = _load(js, {}) or {}
        it["trades"] = [{k: t.get(k) for k in ("day", "dir", "r", "pnl", "risk_pts", "qty", "exit", "trigger", "grade", "regime")}
                        for t in d.get("trades") or []]
        it["risk_usd"] = (d.get("params") or {}).get("risk_usd")
        items.append(it)
    return items


def build(state_path, chart_path, out):
    os.makedirs(out, exist_ok=True)
    st = _load(state_path, {}) or {}
    bt = _load(os.path.join(LAB, "backtest_live.json"), {}) or {}
    ledger = sorted((st.get("ledger") or {}).values(), key=lambda v: (v.get("day", ""), v.get("entry", "")), reverse=True)
    live = {k: st.get(k) for k in ("last_run", "first_run", "runs", "health", "eval", "model_state", "position", "strategy",
                                   "equity_filter", "price", "today", "events", "engine_trades", "bars", "pools")}
    live["ledger"] = ledger[:200]
    results = None
    if bt:
        results = {"meta": {k: bt.get("meta", {}).get(k) for k in ("built", "strategy", "data", "costs", "method", "equity_filter")},
                   "periods": bt.get("periods", {}), "months": bt.get("months", {}), "stop_buckets": bt.get("stop_buckets", []),
                   "lessons": bt.get("lessons", {}), "days": [[d["date"], round(d["pnl"], 2), d.get("trades", 0)] for d in bt.get("days", [])]}
    shadow = _load(os.path.join(os.path.dirname(state_path) or ".", "shadow_ledger.json"), None) \
        or _load(os.path.join(ROOT, "data", "shadow_ledger_seed.json"), []) or []
    lm = _load(os.path.join(ROOT, "live_model.json"), {}) or {}
    cfg = lm.get("equity_filter") or {}
    data = {
        "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "live": live,
        "results": results,
        "trades": _trades(bt),
        "replays": (_load(os.path.join(LAB, "replays.json"), {}) or {}),
        "variants": _load(os.path.join(LAB, "variant_results.json"), {}) or {},
        "study": _study(out),
        "cold": {"config": cfg, "now": st.get("equity_filter"),
                 "window": [{"day": x.get("day"), "r": x.get("r")} for x in sorted(shadow, key=lambda x: x.get("exit_t", 0))[-int(cfg.get("lookback", 15)):]]},
        "sizing": {"risk_usd": (lm.get("params") or {}).get("risk_usd"), "risk_ref_stop": (lm.get("params") or {}).get("risk_ref_stop"),
                   "max_trades_day": (lm.get("params") or {}).get("max_trades_day"), "label": lm.get("label"), "chosen": lm.get("chosen")},
    }
    with open(os.path.join(out, "data.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"), default=str)
    # the page, the home-screen app files and its icons
    for name in os.listdir(WEB):
        src = os.path.join(WEB, name)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(out, name))
    os.makedirs(os.path.join(out, "icons"), exist_ok=True)
    for name in ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png", "icon.svg"):
        if os.path.exists(os.path.join(ICONS, name)):
            shutil.copy(os.path.join(ICONS, name), os.path.join(out, "icons", name))
    if chart_path and os.path.exists(chart_path):
        shutil.copy(chart_path, os.path.join(out, "chart.png"))
    open(os.path.join(out, ".nojekyll"), "w").close()
    kb = os.path.getsize(os.path.join(out, "data.json")) // 1024
    print(f"site -> {out}: data.json {kb} KB, {len(ledger)} paper trades, {len(data['trades'])} replay trades, "
          f"{len(data['replays'].get('sessions', []))} replays, {len(data['variants'].get('rows', []))} variants, {len(data['study'])} study")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="dash/state.json")
    ap.add_argument("--chart", default="dash/chart.png")
    ap.add_argument("--out", default="site")
    a = ap.parse_args()
    build(a.state, a.chart, a.out)
