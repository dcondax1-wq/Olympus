"""A deterministic demo data.json for HERMES: three weeks of Zlarior on the MFFU 50K eval, ATLAS on its 25K, the cloud's
paper twin, the Mind, live learning and the backtest's eval odds. Made-up numbers (the page shows a DEMO badge), the same
shapes engine/accounts.build_accounts and tools/build_web_dashboard.py write. Used by the page's demo and the tests.

NOW is Friday 2026-10-30 17:00 ET. The week's numbers (the tests check them by hand):
  Zlarior  Tue -$240.00 (stop, wick then target) · Thu +$1,912.50 (8R target) · Fri +$310.00 (flat at the close)
  ATLAS    Wed +$240.00 · Fri -$150.00
  -> net +$2,072.50 on 5 trades, 3 wins, 2 losses; the twin's paper trades are not counted (the PC has trades).
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
NOW = int(dt.datetime(2026, 10, 30, 17, 0, tzinfo=NY).timestamp())
WEEK_NET = 2072.50
WEEK_TRADES = 5

# day, entry HH:MM, minutes held, side, entry, risk pts, exit kind, R, $, qty, mfe (R), cause
LIT = [
    ("2026-10-06", "09:42", 48, "LONG", 24812.25, 22.0, "TARGET", 8.0, 1520.00, 4, 8.0, None),
    ("2026-10-08", "10:05", 21, "SHORT", 24960.50, 18.5, "STOP", -1.0, -190.00, 5, 0.4, "late_london"),
    ("2026-10-09", "03:15", 64, "LONG", 24890.00, 15.25, "BE", -0.02, -4.10, 6, 1.1, "be_scratch"),
    ("2026-10-14", "09:51", 12, "SHORT", 25102.75, 20.0, "STOP", -1.0, -205.00, 5, 0.2, "not_turning_point"),
    ("2026-10-16", "10:22", 15, "LONG", 25040.00, 26.0, "TIME", -0.4, -82.00, 4, 0.3, None),
    ("2026-10-20", "09:38", 95, "SHORT", 25210.50, 19.0, "TARGET", 6.4, 1216.00, 5, 6.4, None),
    ("2026-10-22", "02:48", 33, "LONG", 25005.25, 24.0, "STOP", -1.0, -260.00, 5, 0.6, "wick_then_target"),
    ("2026-10-23", "11:05", 280, "LONG", 25118.00, 17.5, "FLAT", 1.6, 448.00, 8, 2.3, None),
    ("2026-10-27", "09:44", 18, "LONG", 25301.25, 21.0, "STOP", -1.0, -240.00, 6, 0.5, "wick_then_target"),
    ("2026-10-29", "09:47", 74, "SHORT", 25412.00, 23.75, "TARGET", 8.0, 1912.50, 5, 8.0, None),
    ("2026-10-30", "03:20", 690, "LONG", 25288.50, 16.0, "FLAT", 1.2, 310.00, 8, 2.9, None),
]
ATLAS = [
    ("2026-10-28", "10:31", 36, "LONG", 25350.25, 12.0, "TARGET", 2.0, 240.00, 5, 2.1, None),
    ("2026-10-30", "13:02", 22, "SHORT", 25270.75, 15.0, "STOP", -1.0, -150.00, 5, 0.3, None),
]


def ts(day: str, hhmm: str) -> int:
    h, m = (int(x) for x in hhmm.split(":"))
    return int(dt.datetime.fromisoformat(day).replace(hour=h, minute=m, tzinfo=NY).timestamp())


def trades(rows) -> list:
    out = []
    for day, hhmm, held, side, entry, risk, ex, r, pnl, qty, mfe, cause in rows:
        d = 1 if side == "LONG" else -1
        e0 = ts(day, hhmm)
        stop = round(entry - d * risk, 2)
        exit_px = round(entry + d * r * risk, 2)
        t = {"day": day, "entry_t": e0, "exit_t": e0 + held * 60, "side": side, "qty": qty, "entry": entry, "stop": stop,
             "target": round(entry + d * 8 * risk, 2), "exit_px": exit_px, "exit": ex, "r": r, "pnl": pnl, "risk_pts": risk,
             "mfe": mfe, "sweep_ext": round(stop + d * 0.25, 2)}
        if cause:
            t["cause"] = cause
        out.append(t)
    return out


def eval_block(rows, start_day: str, start=50000.0, target=3000.0, mll=2000.0, lock=50100.0) -> dict:
    """The eval view engine/accounts.eval_view would give for these trades (trailing floor on the closing balance)."""
    days = {}
    for t in rows:
        if t["day"] >= start_day:
            days[t["day"]] = round(days.get(t["day"], 0.0) + t["pnl"], 2)
    bal, peak = start, start
    for d in sorted(days):
        bal = round(bal + days[d], 2)
        peak = max(peak, bal)
    floor = min(lock, peak - mll)
    profit = round(bal - start, 2)
    return {"start_balance": start, "balance": bal, "profit": profit, "to_target": round(max(0.0, target - profit), 2),
            "target_balance": start + target, "floor": floor, "room": round(bal - floor, 2), "locked": floor >= lock - 0.01,
            "mll": mll, "dll": 1000.0, "progress": round(max(0.0, min(1.0, profit / target)), 4), "session": len(days),
            "sessions": 10, "start": start_day, "status": "on_track", "clock_text": f"Session {len(days)} of 10"}


def bars_around(t: dict) -> list:
    """5m bars across a trade (a smooth walk from the entry to the exit with one pullback) for the 'bars' spark."""
    out, n = [], 24
    e0 = t["entry_t"] - 30 * 60
    d = 1 if t["side"] == "LONG" else -1
    for i in range(n):
        f = i / (n - 1)
        wob = (6 if 6 <= i <= 9 else 0) * d
        c = round(t["entry"] + (t["exit_px"] - t["entry"]) * max(0.0, f * 1.15 - 0.15) - wob + (i % 3 - 1) * 1.5, 2)
        out.append([e0 + i * 300, c, c + 3, c - 3, c])
    return out


def data() -> dict:
    lit, atl = trades(LIT), trades(ATLAS)
    twin = trades(LIT)
    lit_ev, atl_ev = eval_block(lit, "2026-10-22"), eval_block(atl, "2026-10-27", 25000.0, 1500.0, 1000.0, 25100.0)
    best = next(t for t in lit if t["day"] == "2026-10-29")
    acc = [
        {"id": "mffu50k_eval", "name": "MFFU 50K Eval", "firm": "MFFU", "plan": "Builder 50K", "kind": "eval", "source": "pc",
         "badge": "SIM", "eval": lit_ev, "trades": lit, "orders": [], "days": []},
        {"id": "atlas25k", "name": "ATLAS 25K", "firm": "MFFU", "plan": "Builder 25K", "kind": "eval", "source": "pc",
         "badge": "SIM", "eval": atl_ev, "trades": atl, "orders": []},
        {"id": "cloud_paper", "name": "Paper (cloud)", "kind": "paper", "source": "cloud", "badge": "PAPER",
         "eval": eval_block(twin, "2026-10-22"), "trades": twin, "orders": []},
    ]
    mind = {"reviews": [
        {"t": ts("2026-10-29", "16:10"), "bot": "Zlarior", "trade": {"entry_t": best["entry_t"]}, "grade": "A",
         "lesson": "The cleanest setup of the month: ES swept with NQ, displacement inside 10 minutes, 8R banked."},
        {"t": ts("2026-10-27", "16:05"), "bot": "Zlarior", "trade": {"entry_t": ts("2026-10-27", "09:44")}, "grade": "B",
         "lesson": "A wick took the stop by 2 ticks, then price ran to the target. The stop was right; the size kept it at 1R."}],
        "proposals": [{"id": "p17", "bot": "Zlarior", "idea": "Skip setups 05:00-08:00 ET when London already ran 1.5 ATR",
                       "status": "testing"}]}
    return {"built": "2026-10-30 17:00 ET", "accounts": acc,
            "live": {"bars": bars_around(best), "pc": {"mind": mind}},
            "learning": {"causes_month": {"month": "2026-10", "by_cause": [
                {"cause": "wick_then_target", "label": "stopped by a wick, then price went on to the target the same day",
                 "n": 2, "usd": -500.0}]}},
            "learning_live": {"weekly": [{"label": "Oct 26 - Oct 30", "bots": {"lit": {"live_usd": 1982.5, "twin_usd": 2040.0}}}],
                              "suggest": [{"kind": "cost_reserve", "title": "Price fills at 2 ticks and $0.74 a micro"}]},
            "extras": {"two_week": {"eval": {"H2": {"p10": 58.6, "f10": 20.9, "pass_med": 7}}}}}


def home() -> dict:
    d = data()
    return {"built": d["built"], "home_only": True, "extras": d["extras"],
            "accounts": [{k: v for k, v in a.items() if k not in ("trades", "days", "orders")} for a in d["accounts"]]}
