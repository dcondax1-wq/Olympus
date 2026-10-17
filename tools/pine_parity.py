"""Pine vs Python parity: TradingView Strategy Tester "List of trades" CSV  <->  engine.backtest trades.

    python -X utf8 tools/pine_parity.py <tv_trades.csv> [--tz America/New_York] [--params '{"risk_usd": 600}']
                                        [--from 2026-08-24 --to 2026-10-16] [--tol-min 10] [--r-tol 0.3]
    python -X utf8 tools/pine_parity.py <tv_trades.csv> --defaults --no-cold     # the old comparison (engine DEFAULTS, no sizing)
    python -X utf8 tools/pine_parity.py --selftest      # builds a synthetic TV export from the Python trades

Python side: the live strategy (live_model.json params; --params overrides single keys, --defaults uses the engine
DEFAULTS instead) run from the first day of the TradingView list, so both start cold, then the cold-streak filter applied
exactly as tools/export_backtest.py does (engine/equity_filter.py + engine/sizing.py: cold streak x cold_size, late entry
x late_mult, rounded down once, at least 1). --py-bars <csv> runs the engine on a TradingView bar export instead of
data/NQ_5m.csv.

Export on TradingView: Strategy Tester > List of trades > Export (CSV). Set the chart timezone to New York (or pass
--tz with the chart's timezone: the export's Date/Time column is in the chart timezone).

Matching: same side and entry time within --tol-min minutes (nearest wins). For every match the exit-reason class
(TARGET / STOP / BE / TIME / TIMESTOP / GIVEBACK / SIGNAL) and the gross R (points moved / planned risk points) are
compared. Parity score = full matches / (python + tradingview - entry matches), i.e. the Jaccard overlap of the two
trade lists counting a trade only when entry, side and exit class agree and R is within --r-tol. Sizes (contracts after
the cold-streak cut) and $ (Python re-priced with TradingView's MNQ commission, $1.50 per contract round trip) are
compared on every matched trade.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
DATE_FMTS = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%b %d, %Y, %H:%M",
             "%b %d, %Y %H:%M", "%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M", "%Y/%m/%d %H:%M")


# ------------------------------------------------------------------------------------------------ classification
def py_class(reason: str) -> str:
    r = (reason or "").upper()
    if r == "TARGET":
        return "TARGET"
    if r == "STOP":
        return "STOP"
    if r.startswith("BE") or "TRAIL" in r:
        return "BE"
    if r == "TIME STOP":
        return "TIMESTOP"
    if r in ("TIME", "EOD", "NEWS FLAT", "TIME SAFETY", "FLAT"):
        return "TIME"
    if "GIVEBACK" in r:
        return "GIVEBACK"
    return "SIGNAL"


def tv_class(signal: str, r_gross: float | None) -> str:
    s = (signal or "").upper().strip()
    if "TARGET" in s:
        return "TARGET"
    if "TIME STOP" in s:
        return "TIMESTOP"
    if "GIVEBACK" in s:
        return "GIVEBACK"
    if "FLAT" in s or "CLOSE" in s:          # "FLAT", "NEWS FLAT", TradingView's default close-all comment
        return "TIME"
    if "STOP" in s or s in ("XL", "XS", ""):
        if s in ("XL", "XS", "") and r_gross is not None and r_gross > 0.5:
            return "TARGET"                   # bracket exit without comment_profit/loss: infer from the result
        return "BE" if (r_gross is not None and r_gross > -0.15) else "STOP"
    return "SIGNAL"


# ------------------------------------------------------------------------------------------------ TradingView CSV
def _parse_time(s: str, tz: ZoneInfo) -> int:
    s = s.strip()
    for f in DATE_FMTS:
        try:
            return int(dt.datetime.strptime(s, f).replace(tzinfo=tz).timestamp())
        except ValueError:
            continue
    raise ValueError(f"unrecognised Date/Time {s!r}")


def _num(s) -> float | None:
    if s is None:
        return None
    s = str(s).replace(",", "").replace("$", "").replace("USD", "").replace("−", "-").strip()
    try:
        return float(s)
    except ValueError:
        return None


def read_tv(path: str, tz: str = "America/New_York") -> list[dict]:
    """One dict per round trip: entry_t, dir, entry, exit, qty, profit, entry_signal, exit_signal, risk_pts (fill to 'sl=',
    else the planned 'r=')."""
    zone = ZoneInfo(tz)
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    cols = {k.lower().strip(): k for k in rows[0].keys()}

    def col(*cands, contains=None):
        for c in cands:
            if c in cols:
                return cols[c]
        if contains:
            for k, v in cols.items():
                if all(x in k for x in contains):
                    return v
        return None
    c_no = col("trade #", "trade", "trade number", contains=("trade",))
    c_type = col("type")
    c_sig = col("signal")
    c_time = col("date/time", "date and time", "date", contains=("date",))
    c_px = col("price usd", "price", contains=("price",))
    c_qty = col("contracts", "quantity", "qty", "size (qty)", "position size (qty)", contains=("qty",)) or col(contains=("contract",))
    c_pnl = col("profit usd", "profit", "net p&l usd", "net p&l", contains=("p&l",)) or col(contains=("profit",))
    if not (c_no and c_type and c_time and c_px):
        raise ValueError(f"not a TradingView 'List of trades' export (columns: {list(rows[0].keys())})")
    trades: dict[str, dict] = {}
    for r in rows:
        no = str(r[c_no]).strip()
        typ = str(r[c_type]).lower()
        t = trades.setdefault(no, {"no": no})
        side = 1 if "long" in typ else (-1 if "short" in typ else 0)
        if side:
            t["dir"] = side
        if "entry" in typ:
            t["entry_t"] = _parse_time(r[c_time], zone)
            t["entry"] = _num(r[c_px])
            t["entry_signal"] = (r.get(c_sig) or "").strip() if c_sig else ""
            t["qty"] = _num(r.get(c_qty)) if c_qty else None
        elif "exit" in typ:
            t["exit_t"] = _parse_time(r[c_time], zone) if str(r[c_time]).strip() else None
            t["exit"] = _num(r[c_px])
            t["exit_signal"] = (r.get(c_sig) or "").strip() if c_sig else ""
            t["profit"] = _num(r.get(c_pnl)) if c_pnl else None
    out = []
    for t in trades.values():
        if "entry_t" not in t or "dir" not in t:
            continue
        m = re.search(r"r=([0-9.]+)", t.get("entry_signal", ""))
        t["risk_pts"] = float(m.group(1)) if m else None
        m = re.search(r"sl=([0-9.]+)", t.get("entry_signal", ""))
        if m and t.get("entry") is not None:
            t["risk_pts"] = abs(t["entry"] - float(m.group(1)))     # risk from the actual fill, like the engine's risk_pts
        t["cold"] = bool(re.search(r"\bcold\b", t.get("entry_signal", "")))   # cold-streak size (entry comment tag)
        t["late"] = bool(re.search(r"\blate\b", t.get("entry_signal", "")))   # late-entry size (entry comment tag)
        out.append(t)
    return sorted(out, key=lambda x: x["entry_t"])


# ------------------------------------------------------------------------------------------------ Python side
def live_model() -> dict:
    with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as f:
        return json.load(f)


def _patch_bars(bars_csv: str):
    """Make engine.backtest read NQ 5m (and its 1H) from a TradingView bar export instead of data/NQ_*.csv. The export is
    the unadjusted continuous contract, so it is back-adjusted with data/NQ_rolls.json first, like data/NQ_5m.csv; the
    1H bars are built from the same 5m bars (no earlier history: a cold start like the TradingView chart)."""
    import numpy as np
    import pandas as pd
    import engine.backtest as bt
    from engine.data import from_frame, load as real_load, resample
    df = pd.read_csv(bars_csv)
    df.columns = [c.lower() for c in df.columns]
    df = df[["time", "open", "high", "low", "close", "volume"]].copy()
    df["volume"] = df["volume"].fillna(0)
    rolls = json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json"), encoding="utf-8"))["rolls"]
    adj = np.zeros(len(df))
    for r in rolls:
        if r.get("gap") is not None:
            adj[df["time"].values < int(r["switch_t"])] += float(r["gap"])
    for k in ("open", "high", "low", "close"):
        df[k] = df[k] + adj
    b5 = from_frame("NQ", "5m", df)
    b1h = resample(b5, "1h")

    def load(sym, tf):
        if sym == "NQ" and tf == "5m":
            return b5
        if sym == "NQ" and tf == "1h":
            return b1h
        return real_load(sym, tf)
    bt.load = load


def py_trades(params: dict | None = None, day_from: str | None = None, day_to: str | None = None,
              bars_csv: str | None = None, cache: str | None = None, defaults: bool = False) -> list[dict]:
    """Engine trades for the live strategy (live_model.json params, `params` on top; defaults=True: engine DEFAULTS + params)
    from day_from to day_to (trading days). cache: JSON file to reuse / store the result (keyed by the arguments)."""
    p = ({} if defaults else dict(live_model()["params"]))
    p.update(params or {})
    if day_from:
        p["days_from"] = day_from
    if day_to:
        p["days_to"] = day_to
    key = json.dumps({"p": p, "bars": bars_csv and os.path.abspath(bars_csv)}, sort_keys=True)
    if cache and os.path.exists(cache):
        c = json.load(open(cache, encoding="utf-8"))
        if c.get("key") == key:
            return c["trades"]
    if bars_csv:
        _patch_bars(bars_csv)
    from engine.backtest import run
    res = run("NQ", "5m", p, light=True)
    learned = [x["key"] for x in res.get("exit_signals") or [] if x.get("learned")]
    if learned:
        print(f"note: the engine's exit learner acted on {learned} - Pine has only the fixed giveback rule")
    out = []
    for t in res["trades"]:
        out.append({"entry_t": int(t["entry_t"]), "dir": int(t["dir"]), "entry": float(t["entry"]), "exit": float(t["exit_price"]),
                    "exit_t": int(t["exit_t"]), "risk_pts": float(t["risk_pts"]), "qty": int(t["qty"]),
                    "minis": int(t.get("minis") or 0), "micros": int(t.get("micros") or 0), "stop": float(t.get("stop0") or t["stop"]),
                    "target": float(t["target"]), "reason": t["exit_reason"], "grade": t.get("grade"), "pnl_r": float(t["pnl_r"]),
                    "pnl": float(t["pnl"]), "regime": t.get("regime"), "m15_trend": int(t.get("m15_trend") or 0)})
    if cache:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump({"key": key, "trades": out}, f)
    return out


def apply_cold(py: list[dict], cfg="live", ledger_from: int | None = None, sizing="live") -> list[dict]:
    """The live-loop sizing exactly as tools/export_backtest.py applies it. Cold streak (engine/equity_filter.status): the
    ledger is the engine's own trades (R = pnl_r at the engine's size); an entry is cold when the last `lookback` trades
    that finished before it sum to <= min_sum_r R (rounded to 2 decimals, at least `lookback` of them) -> x cold_size.
    Late entry (engine/sizing.py, live_model.json "sizing"): the 15m structure already pointed the trade's way at the
    signal -> x late_mult. One rounding: qty = max(1, floor(qty x cold x late)); cold_mode skip -> no trade.
    ledger_from (s): only trades entered from then on count, like TradingView, whose record starts with the chart's history.
    Adds qty_full, qty (sized), cold, late, cold_sum, pnl_mnq ($ with TradingView's MNQ commission) and pnl_sized."""
    from engine import sizing as szm
    lm = live_model()
    cfg = lm.get("equity_filter") if cfg == "live" else cfg
    sizing = lm.get("sizing") if sizing == "live" else sizing
    sizing = {**(sizing or {}), "press": None}
    rows = sorted(py, key=lambda t: t["entry_t"])
    for t in rows:
        q0 = int(t.get("qty_full", t["qty"]))
        t["qty_full"] = q0
        m, s = 1.0, None
        if cfg:
            lb, thr = int(cfg.get("lookback", 15)), float(cfg.get("min_sum_r", 0.0))
            fin = [x for x in rows if x["exit_t"] < t["entry_t"] and (ledger_from is None or x["entry_t"] >= ledger_from)]
            last = fin[-lb:]
            s = round(sum(float(x["pnl_r"]) for x in last), 2)
            on = len(last) < lb or s > thr
            half = cfg.get("cold_mode", "skip") == "half"
            m = 1.0 if on else (min(1.0, max(0.0, float(cfg.get("cold_size", 0.5)))) if half else 0.0)
        tr = {"dir": t["dir"], "m15_trend": t.get("m15_trend", 0), "risk_pts": t["risk_pts"]}
        q = szm.route_qty(q0, tr, m, sizing, lm.get("params"))["qty"] if m > 0 else 0
        late = sizing.get("late_mult") is not None and float(sizing["late_mult"]) < 1 and szm.is_late(tr)
        t.update(qty=q, cold=m < 1, late=bool(late), cold_sum=s,
                 pnl_mnq=round(((t["exit"] - t["entry"]) * t["dir"] * 2.0 - 1.5) * q, 2),
                 pnl_sized=round(t["pnl"] * q / q0, 2) if q0 else 0.0)
    return rows


def _day(ts: int) -> str:
    return (dt.datetime.fromtimestamp(ts, ET) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


# ------------------------------------------------------------------------------------------------ compare
def compare(py: list[dict], tv: list[dict], tol_min: float = 10, r_tol: float = 0.3, day_from=None, day_to=None,
            verbose=True, t_to: int | None = None) -> dict:
    """t_to: ignore Python trades entered after this time (s) - the end of the TradingView bars."""
    if tv and day_from is None:
        day_from = _day(min(t["entry_t"] for t in tv))
    if tv and day_to is None:
        day_to = _day(max(t["entry_t"] for t in tv))
    py = [t for t in py if (day_from is None or _day(t["entry_t"]) >= day_from) and (day_to is None or _day(t["entry_t"]) <= day_to)
          and (t_to is None or t["entry_t"] <= t_to) and t.get("qty", 1) > 0]
    used = set()
    rows = []
    for p in py:
        best, bd = None, None
        for j, t in enumerate(tv):
            if j in used or t["dir"] != p["dir"]:
                continue
            d = abs(t["entry_t"] - p["entry_t"])
            if d <= tol_min * 60 and (bd is None or d < bd):
                best, bd = j, d
        pr = (p["exit"] - p["entry"]) * p["dir"] / p["risk_pts"]
        pc = py_class(p["reason"])
        base = {"t": p["entry_t"], "dir": p["dir"], "py": pc, "py_r": pr, "py_q": p.get("qty"), "py_cold": p.get("cold"),
                "py_late": p.get("late"), "py_usd": p.get("pnl_mnq"), "py_usd_engine": p.get("pnl_sized", p.get("pnl"))}
        if best is None:
            rows.append({**base, "tv": None, "tv_r": None, "tv_q": None, "tv_cold": None, "tv_late": None, "tv_usd": None,
                         "dt": None, "size_ok": None, "status": "PY ONLY"})
            continue
        used.add(best)
        t = tv[best]
        risk = t.get("risk_pts") or p["risk_pts"]
        tr = (t["exit"] - t["entry"]) * t["dir"] / risk if t.get("exit") is not None and risk else None
        tc = tv_class(t.get("exit_signal", ""), tr)
        status = "MATCH"
        if tc != pc:
            status = "EXIT DIFF"
        elif tr is None or abs(tr - pr) > r_tol:
            status = "R DIFF"
        tq = int(t["qty"]) if t.get("qty") is not None else None
        rows.append({**base, "tv": tc, "tv_r": tr, "tv_q": tq, "tv_cold": t.get("cold"), "tv_late": t.get("late"), "tv_usd": t.get("profit"),
                     "dt": (t["entry_t"] - p["entry_t"]) // 60,
                     "size_ok": None if tq is None or p.get("qty") is None else tq == int(p["qty"]), "status": status})
    for j, t in enumerate(tv):
        if j in used:
            continue
        risk = t.get("risk_pts")
        tr = (t["exit"] - t["entry"]) * t["dir"] / risk if t.get("exit") is not None and risk else None
        rows.append({"t": t["entry_t"], "dir": t["dir"], "py": None, "py_r": None, "py_q": None, "py_cold": None, "py_late": None,
                     "py_usd": None, "py_usd_engine": None, "tv": tv_class(t.get("exit_signal", ""), tr), "tv_r": tr,
                     "tv_q": int(t["qty"]) if t.get("qty") is not None else None, "tv_cold": t.get("cold"), "tv_late": t.get("late"),
                     "tv_usd": t.get("profit"), "dt": None, "size_ok": None, "status": "TV ONLY"})
    rows.sort(key=lambda r: r["t"])
    n_py, n_tv = len(py), len(tv)
    entry_m = sum(1 for r in rows if r["status"] in ("MATCH", "EXIT DIFF", "R DIFF"))
    full_m = sum(1 for r in rows if r["status"] == "MATCH")
    size_m = sum(1 for r in rows if r["size_ok"])
    cold_m = sum(1 for r in rows if r["status"] != "PY ONLY" and r["status"] != "TV ONLY" and r["py_cold"] is not None
                 and r["tv_cold"] is not None and bool(r["py_cold"]) == bool(r["tv_cold"]))
    late_m = sum(1 for r in rows if r["status"] not in ("PY ONLY", "TV ONLY") and r["py_late"] is not None
                 and r["tv_late"] is not None and bool(r["py_late"]) == bool(r["tv_late"]))
    denom = n_py + n_tv - entry_m
    net = lambda key, src: round(sum(r[key] for r in rows if r.get(key) is not None and r["status"] in src), 2)
    both = ("MATCH", "EXIT DIFF", "R DIFF")
    out = {"n_py": n_py, "n_tv": n_tv, "entry_matches": entry_m, "full_matches": full_m, "size_matches": size_m,
           "cold_flag_matches": cold_m, "py_cold_trades": sum(1 for t in py if t.get("cold")),
           "tv_cold_trades": sum(1 for t in tv if t.get("cold")), "late_flag_matches": late_m,
           "py_late_trades": sum(1 for t in py if t.get("late")), "tv_late_trades": sum(1 for t in tv if t.get("late")),
           "entry_parity": round(entry_m / denom, 3) if denom else 1.0, "parity": round(full_m / denom, 3) if denom else 1.0,
           "net_tv": round(sum(t.get("profit") or 0.0 for t in tv), 2),
           "net_py_mnq": round(sum(t.get("pnl_mnq") or 0.0 for t in py), 2) if py and "pnl_mnq" in py[0] else None,
           "net_py_engine": round(sum(t.get("pnl_sized", t.get("pnl")) or 0.0 for t in py), 2) if py and "pnl" in py[0] else None,
           "net_matched_tv": net("tv_usd", both), "net_matched_py_mnq": net("py_usd", both),
           "window": [day_from, day_to], "rows": rows}
    if verbose:
        f = lambda x: "" if x is None else f"{x:+.2f}"
        g = lambda x: "" if x is None else f"{x:+.0f}"
        q = lambda x, c, l=False: "" if x is None else f"{x}{'c' if c else ''}{'l' if l else ''}"
        print(f"Window {day_from} .. {day_to} | python {n_py} trades | tradingview {n_tv} trades")
        print(f"{'entry (ET)':17} {'side':4} {'python':9} {'R':>6} {'qty':>4} {'$':>7}   {'tradingview':11} {'R':>6} {'qty':>4} {'$':>7} {'dt':>3}  status")
        for r in rows:
            print(f"{dt.datetime.fromtimestamp(r['t'], ET):%Y-%m-%d %H:%M} {'L' if r['dir'] == 1 else 'S':4} {r['py'] or '-':9} {f(r['py_r']):>6} "
                  f"{q(r['py_q'], r['py_cold'], r['py_late']):>4} {g(r['py_usd']):>7}   {r['tv'] or '-':11} {f(r['tv_r']):>6} {q(r['tv_q'], r['tv_cold'], r['tv_late']):>4} "
                  f"{g(r['tv_usd']):>7} {'' if r['dt'] is None else r['dt']:>3}  {r['status']}"
                  + ("" if r["size_ok"] in (None, True) else "  SIZE DIFF"))
        print(f"Entry parity {out['entry_parity']:.0%} ({entry_m} matched) | full parity {out['parity']:.0%} "
              f"({full_m} with the same exit class and R within {r_tol}) | same size {size_m} | qty column: c = cold-streak size, l = late-entry size")
        if out["net_py_mnq"] is not None:
            print(f"Net: tradingview {out['net_tv']:+,.2f} | python {out['net_py_mnq']:+,.2f} with MNQ commission "
                  f"({out['net_py_engine']:+,.2f} engine commission) | cold-streak trades: python {out['py_cold_trades']}, "
                  f"tradingview {out['tv_cold_trades']} | late-entry trades: python {out['py_late_trades']}, tradingview {out['tv_late_trades']}")
    return out


# ------------------------------------------------------------------------------------------------ synthetic self-test
def write_tv_csv(path: str, trades: list[dict], tz: str = "America/New_York"):
    """Write trades in TradingView's 'List of trades' layout (newest first, Exit row above Entry row)."""
    zone = ZoneInfo(tz)
    hdr = ["Trade #", "Type", "Signal", "Date/Time", "Price USD", "Contracts", "Profit USD", "Profit %", "Cum. Profit USD",
           "Cum. Profit %", "Run-up USD", "Run-up %", "Drawdown USD", "Drawdown %"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(hdr)
        cum = 0.0
        rows = []
        for n, t in enumerate(trades, 1):
            side = "long" if t["dir"] == 1 else "short"
            pnl = (t["exit"] - t["entry"]) * t["dir"] * 2.0 * t["qty"] - 1.5 * t["qty"]
            cum += pnl
            ts = lambda x: dt.datetime.fromtimestamp(x, zone).strftime("%Y-%m-%d %H:%M")
            rows.append([[n, f"Exit {side}", t["exit_signal"], ts(t["exit_t"]), f"{t['exit']:.2f}", t["qty"], f"{pnl:.2f}", "", f"{cum:.2f}", "", "", "", "", ""],
                         [n, f"Entry {side}", t["entry_signal"], ts(t["entry_t"]), f"{t['entry']:.2f}", t["qty"], f"{pnl:.2f}", "", f"{cum:.2f}", "", "", "", "", ""]])
        for pair in reversed(rows):
            w.writerows(pair)


def _tv_signal_for(reason: str) -> str:
    c = py_class(reason)
    return {"TARGET": "TARGET", "STOP": "STOP", "BE": "STOP", "TIMESTOP": "TIME STOP", "GIVEBACK": "GIVEBACK",
            "TIME": "FLAT"}.get(c, "SIGNAL")


def selftest() -> bool:
    py = py_trades(day_from="2026-08-24", day_to="2026-10-16")
    assert len(py) >= 6, f"need >= 6 python trades for the self-test, got {len(py)}"
    syn = []
    for k, p in enumerate(py):
        t = {"dir": p["dir"], "entry_t": p["entry_t"], "entry": p["entry"], "exit": p["exit"], "exit_t": p["exit_t"], "qty": p["qty"],
             "entry_signal": f"{'L' if p['dir'] == 1 else 'S'} r={p['risk_pts']:.2f} g={p['grade']}", "exit_signal": _tv_signal_for(p["reason"])}
        if k == 1:
            t["entry_t"] += 300                                        # TV filled one bar later: still an entry match
        if k == 2:
            continue                                                   # TV missed this trade -> PY ONLY
        if k == 3:
            t["exit_signal"] = "GIVEBACK" if py_class(p["reason"]) != "GIVEBACK" else "TARGET"   # different exit -> EXIT DIFF
        if k == 4:
            t["exit"] = p["exit"] + p["dir"] * 0.5 * p["risk_pts"]   # same exit class, +0.5R better fill -> R DIFF
        syn.append(t)
    extra = dict(syn[-1])
    extra["entry_t"] = py[-1]["entry_t"] - 3 * 3600                    # TV-only trade 3 h earlier the same day
    extra["exit_t"] = extra["entry_t"] + 1800
    extra["dir"] = -py[-1]["dir"]
    extra["exit"] = extra["entry"] - extra["dir"] * 10
    extra["exit_signal"] = "STOP"
    syn.append(extra)
    syn.sort(key=lambda x: x["entry_t"])
    path = os.path.join(tempfile.mkdtemp(prefix="pine_parity_"), "tv_trades.csv")
    write_tv_csv(path, syn)
    tv = read_tv(path)
    assert len(tv) == len(syn), (len(tv), len(syn))
    assert tv[0]["risk_pts"] is not None and tv[0]["entry_signal"].startswith(("L", "S"))
    res = compare(py, tv)
    st = {}
    for r in res["rows"]:
        st[r["status"]] = st.get(r["status"], 0) + 1
    ok = (st.get("PY ONLY") == 1 and st.get("TV ONLY") == 1 and st.get("EXIT DIFF") == 1 and st.get("R DIFF") == 1
          and res["entry_matches"] == len(py) - 1 and res["full_matches"] == len(py) - 3)          # k=2 missing, k=3 exit diff, k=4 R diff
    # the shifted entry (k=1) must still be a full match
    shifted = next(r for r in res["rows"] if r["t"] == py[1]["entry_t"])
    ok = ok and shifted["status"] == "MATCH" and shifted["dt"] == 5
    print(f"\nself-test statuses {st} -> {'PASS' if ok else 'FAIL'}  (csv: {path})")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--tz", default="America/New_York")
    ap.add_argument("--params", default="{}", help="JSON engine params on top of live_model.json (or of DEFAULTS with --defaults)")
    ap.add_argument("--defaults", action="store_true", help="engine DEFAULTS instead of live_model.json (the 2026-10-16 comparison)")
    ap.add_argument("--no-cold", action="store_true", help="Python side without the cold-streak filter")
    ap.add_argument("--py-bars", help="run the Python engine on this TradingView bar export instead of data/NQ_5m.csv")
    ap.add_argument("--from", dest="day_from")
    ap.add_argument("--to", dest="day_to")
    ap.add_argument("--tol-min", type=float, default=10)
    ap.add_argument("--r-tol", type=float, default=0.3)
    ap.add_argument("--json", help="also write the result rows to this JSON file")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if not a.csv:
        ap.error("csv path required (or --selftest)")
    tv = read_tv(a.csv, a.tz)
    # --from = the first day of the TradingView chart: Python then starts cold on that day too. Without it Python runs
    # over the whole history (warm pools / structure) and its cold-streak record starts at the first TradingView trade.
    py = py_trades(json.loads(a.params), day_from=a.day_from, day_to=a.day_to, bars_csv=a.py_bars, defaults=a.defaults)
    if not a.no_cold:
        t0 = None if a.day_from or not tv else min(t["entry_t"] for t in tv) - 600
        py = apply_cold(py, None if a.defaults else "live", ledger_from=t0, sizing=None if a.defaults else "live")
    res = compare(py, tv, a.tol_min, a.r_tol, a.day_from, a.day_to)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, default=str)


if __name__ == "__main__":
    main()
