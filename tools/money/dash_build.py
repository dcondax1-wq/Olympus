"""Money dashboards data (night-revamp-dash 2026-11-20): one small file for the Money pages' charts.

    python tools/money/dash_build.py            -> tools/web_public/business/dash.json (< 60 KB)
    python tools/money/dash_build.py --check    -> build to memory, print sizes, write nothing

Reads only files already in the repo (no engine run, no network):
  research/lab/edge_health.json   edge health over time (LIT's 40-session R a week + light per day; ATLAS card)       BACKTEST replay
  research/lab/backtest_live.json the live-rules LIT backtest: months, days (equity), trades (best / worst, win / loss)  BACKTEST
  research/lab/money_plan.json    the 1,000-run money plan: first payout dates, pass dates, $ a month per account     ESTIMATE
Every block carries "label" (BACKTEST / ESTIMATE) and "built" (its source's own date) so the pages can say what and how old.
No account id, no name beyond the bots' and accounts' public labels the site already shows.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAB = os.path.join(ROOT, "research", "lab")
OUT = os.path.join(ROOT, "tools", "web_public", "business", "dash.json")
MAX_BYTES = 60_000


def _load(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _r(x, n=0):
    try:
        v = round(float(x), n)
        return int(v) if n == 0 else v
    except (TypeError, ValueError):
        return None


def edge(eh) -> dict | None:
    if not isinstance(eh, dict):
        return None
    light = eh.get("light") or {}
    ser = [[s.get("day"), _r(s.get("r_week"), 2), (s.get("light") or "?")[:1]] for s in light.get("series") or [] if s.get("day")]
    card = eh.get("card") or {}
    lit40 = ((eh.get("lit") or {}).get("windows") or {}).get("40") or {}
    return {"label": "BACKTEST", "what": "LIT replayed on each day's real bars: R a week over its last 40 sessions",
            "built": eh.get("built"), "data_to": card.get("data_to"), "light": card.get("light"), "line": card.get("line"),
            "cuts": (light.get("cuts") or {}), "series": ser[-260:], "now": lit40.get("now"),
            "rates": light.get("rates"), "atlas": card.get("atlas"), "note": card.get("note")}


def backtest(bt) -> dict | None:
    if not isinstance(bt, dict):
        return None
    meta = bt.get("meta") or {}
    months = [[k, _r(v.get("net")), v.get("trades"), v.get("wins")] for k, v in sorted((bt.get("months") or {}).items())]
    per = {}
    for k, v in (bt.get("periods") or {}).items():
        per[k] = {x: v.get(x) for x in ("from", "to", "trades", "per_week", "win_pct", "pf", "net", "per_month", "max_dd", "worst_day", "best_day")}
    # 2026 equity: cumulative $ per trading day (the backtest's own day rows), max 1 point a day
    eq, cum, peak, dd = [], 0.0, 0.0, 0.0
    for d in bt.get("days") or []:
        day = d.get("date") or ""
        if not day.startswith("2026"):
            continue
        cum += float(d.get("pnl") or 0)
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
        eq.append([day, _r(cum)])
    tr = [t for t in bt.get("trades") or [] if str(t.get("day", "")).startswith("2026") and isinstance(t.get("pnl"), (int, float))]

    def brief(t):
        rep = t.get("report") or {}
        return {"day": t.get("day"), "time": rep.get("time"), "side": t.get("side"), "exit": t.get("exit"), "r": _r(t.get("r"), 2),
                "pnl": _r(t.get("pnl")), "risk_usd": _r(t.get("risk_usd")), "pools": (t.get("pools") or [])[:3]}
    wins = [t for t in tr if t["pnl"] > 0]
    losses = [t for t in tr if t["pnl"] < 0]
    streak_w = streak_l = cw = cl = 0
    for t in tr:
        if t["pnl"] > 0:
            cw, cl = cw + 1, 0
        elif t["pnl"] < 0:
            cl, cw = cl + 1, 0
        streak_w, streak_l = max(streak_w, cw), max(streak_l, cl)
    stats = {"n": len(tr), "wins": len(wins), "losses": len(losses), "flat": len(tr) - len(wins) - len(losses),
             "avg_win": _r(sum(t["pnl"] for t in wins) / len(wins)) if wins else None,
             "avg_loss": _r(sum(t["pnl"] for t in losses) / len(losses)) if losses else None,
             "streak_w": streak_w, "streak_l": streak_l,
             "exits": {e: sum(1 for t in tr if t.get("exit") == e) for e in sorted({t.get("exit") for t in tr if t.get("exit")})}}
    best = max(tr, key=lambda t: t["pnl"]) if tr else None
    worst = min(tr, key=lambda t: t["pnl"]) if tr else None
    return {"label": "BACKTEST", "what": "LIT with the live rules on TradingView NQ1! futures bars, costs in", "built": meta.get("built"),
            "strategy": meta.get("strategy"), "months": months, "periods": per, "equity_2026": eq, "max_dd_2026": _r(dd),
            "stats_2026": stats, "best": brief(best) if best else None, "worst": brief(worst) if worst else None}


def plan(mp) -> dict | None:
    if not isinstance(mp, dict):
        return None
    rows = mp.get("rows") or {}
    names = mp.get("names") or {}
    out = {"label": "ESTIMATE", "what": "The middle of 1,000 runs of a market like each period (money_plan.json)", "built": mp.get("date"),
           "months": mp.get("months"), "markets": mp.get("markets"), "now": mp.get("now"), "by_market": {}}
    for mk in ("H2", "H1", "REF"):
        r = rows.get(mk) or {}
        accts = []
        for key, a in (r.get("accounts") or {}).items():
            ev = a.get("eval") or {}
            accts.append({"key": key, "name": names.get(key, key), "first_pay": a.get("first_pay"), "first_pay_p25": a.get("first_pay_p25"),
                          "first_pay_p75": a.get("first_pay_p75"), "first_pay_usd": a.get("first_pay_usd"), "p_no_pay_6m": a.get("p_no_pay_6m"),
                          "pass_date": ev.get("pass_date"), "funded_med": a.get("funded_med"), "buy_med": a.get("buy_med"),
                          "cash_m": a.get("cash_m"), "net_m": a.get("net_m"), "month_cash": a.get("month_cash"), "lost_6m": a.get("lost_6m")})
        fleet = ((r.get("fleet") or {}).get("four") or {}).get("months") or []
        out["by_market"][mk] = {"accounts": accts,
                                "fleet": [{k: m.get(k) for k in ("month", "net_mean", "cum_net_p10", "cum_net_p50", "cum_net_p90")} for m in fleet]}
    return out


def build() -> dict:
    out = {"v": 1, "kind": "money-dash", "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "built_by": "tools/money/dash_build.py",
           "edge": edge(_load(os.path.join(LAB, "edge_health.json"))),
           "backtest": backtest(_load(os.path.join(LAB, "backtest_live.json"))),
           "plan": plan(_load(os.path.join(LAB, "money_plan.json")))}
    out["sources"] = ["research/lab/edge_health.json", "research/lab/backtest_live.json", "research/lab/money_plan.json"]
    return out


def main(argv) -> int:
    d = build()
    raw = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
    print(f"dash.json {len(raw):,} bytes (edge {len(json.dumps(d['edge'])):,}, backtest {len(json.dumps(d['backtest'])):,}, plan {len(json.dumps(d['plan'])):,})")
    if len(raw) > MAX_BYTES:
        print(f"too big: over {MAX_BYTES:,} bytes")
        return 1
    if "--check" in argv:
        return 0
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(raw)
    print("wrote", os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
