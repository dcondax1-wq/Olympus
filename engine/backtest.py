"""High-level backtest entry point used by the CLI, the optimizer and the dashboard API."""
from __future__ import annotations

import os

from . import analytics, learn
from .data import load, resample, DATA_DIR
from .instruments import PARTNER, INSTRUMENTS
from .model import Engine, merge_params  # noqa: F401  (merge_params re-exported for robust.placebo)


def _bars(sym, tf, days_from=None, days_to=None):
    b = load(sym, tf)
    if days_from or days_to:
        idx = [k for k, d in enumerate(b.date_str) if (not days_from or d >= days_from) and (not days_to or d <= days_to)]
        if not idx:
            raise ValueError("no bars in date range")
        b = b.slice(idx[0], idx[-1] + 1)
    return b


def run(sym="NQ", tf="5m", params=None, plan="builder_50k", light=False):
    p = merge_params(params)
    base = _bars(sym, tf, p.get("days_from"), p.get("days_to"))
    if tf in ("1h", "4h"):
        htf = resample(base, "4h") if tf == "1h" else resample(base, "1d")
    else:
        htf = load(sym, "1h") if os.path.exists(os.path.join(DATA_DIR, f"{sym}_1h.csv")) else None
    partner = None
    ps = PARTNER.get(sym)
    if ps and os.path.exists(os.path.join(DATA_DIR, f"{ps}_{tf}.csv")):
        try:
            partner = _bars(ps, tf, p.get("days_from"), p.get("days_to"))
        except ValueError:      # partner history does not reach this window (e.g. ES before 2026-08): SMT features off
            partner = None
    ltf, ltf_src = None, None
    if p["ifvg_tf"] == "lower":
        # hybrid entry: true 1m bars (data/<sym>_1m.csv + verified data/ltf exports, cleaned); missing -> 5m fallback
        from .data import load_ltf
        ltf, ltf_src = load_ltf(sym, base)
    eng = Engine(base, htf=htf, partner=partner, params=p, ltf=ltf).run()
    res = eng.result()
    trades, days = res["trades"], res["days"]
    # intraday worst point per day (realized + open-trade MAE) for drawdown-breach checks
    spec = INSTRUMENTS[sym]
    by_day = {}
    import datetime as dt
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    for t in trades:
        d = (dt.datetime.fromtimestamp(t["entry_t"], et) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")
        t["day"] = d
        by_day.setdefault(d, []).append(t)
    if p.get("memory_write_backtest"):
        # opt-in only: backtest trades go into memory as source 'backtest' (reports / export), never into the learner seed
        try:
            from .memory import MEMORY
            for t in trades:
                MEMORY.record_trade(t, "backtest", sym, tf, p)
        except Exception as e:
            print(f"memory: backtest write failed: {e}")
    for d in days:
        cum, low = 0.0, 0.0
        for t in by_day.get(d["date"], []):
            open_worst = cum - t["mae"] * t["risk_pts"] * t["qty"] * spec["micro_pv"]
            low = min(low, open_worst)
            cum += t["pnl"]
            low = min(low, cum)
        d["low_intraday"] = round(low, 2)
    pl = analytics.PLANS[plan]
    out = {
        "sym": sym, "tf": tf, "params": p,
        "stats": analytics.stats(trades, days),
        "trades": trades,
        "days": days,
        "exit_signals": res["exit_signals"],
        "account_resets": res.get("account_resets", []),
    }
    if "ltf" in res:
        out["ltf"] = {**res["ltf"], "sources": ltf_src}
    if light:
        return out
    out.update({
        "breakdowns": analytics.breakdowns(trades),
        "equity": analytics.equity_curve(trades, p["start_balance"]),
        "eval": analytics.simulate_eval([d["pnl"] for d in days], pl, [d["low_intraday"] for d in days]),
        "rolling": analytics.rolling_evals(days, pl),
        "events": res["events"], "signals": res["signals"], "pools": res["pools"],
        "ifvgs": res["ifvgs"], "profiles": res["profiles"], "structure": res["structure"], "state": res["state"],
        "htf_fvgs": res["htf_fvgs"], "mtf_events": res["mtf_events"], "learner_log": res["learner_log"][-200:],
        "shadows": [{k: v for k, v in s.items() if k != "tags"} for s in res["shadows"]],
        "feature_study": learn.feature_study(res["shadows"]),
        "plan": pl,
        "range": [base.date_str[0], base.date_str[-1]],
    })
    return out

