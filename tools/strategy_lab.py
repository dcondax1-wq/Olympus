"""Strategy Lab: one scorecard and one protocol for every 2026 strategy candidate (real CME NQ1! only, never CFD).

PROTOCOL (fixed before any tuning - do not change it to make a candidate look better)
  dev      2026-01-02 .. 2026-06-30   build and tune rules here, as often as you like
  confirm  2026-07-01 .. 2026-10-16   final check; every run is logged in research/lab/confirm_log.csv
  ytd      2026-01-02 .. 2026-10-16   the owner's headline number ("profitable through this year")
  GATE (both dev and confirm): net > 0, PF >= 1.3, 2.0-5.0 trades/week on average, max drawdown < $2,000 (the eval's
  trailing max loss), and rolling MFFU 50K pass rate at least 10 points above the zero-edge baseline.

COSTS / SIZING for rule modules (the Liquidity Engine applies its own, equivalent costs)
  MNQ $2/pt, $1.40 round-trip commission per micro, 1 tick (0.25 pt) slippage on market and stop fills, none on limit
  targets. Fixed risk: size = floor(RISK_USD / (stop_pts * $2)), max 40 micros. No grade sizing (straight rules).

TRADE FORMAT (list of dicts, one per trade): entry_t (unix s), exit_t, dir (+1/-1), entry, stop, exit, qty,
  exit_kind ('stop'|'target'|'market'|'time'|'be'), setup (str), optional mae_pts. Use make_trade() to fill pnl and r.

USAGE
  python tools/strategy_lab.py engine --name A_base --period dev [--params '{"grade_sizing": false}']
  python tools/strategy_lab.py score  --name B_x --period dev --trades research/lab/trades_B_x.json
  python tools/strategy_lab.py board                       # rebuild research/lab/LEADERBOARD.md
  from tools.strategy_lab import bars, make_trade, score    # in your own module
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "lab")
ET = ZoneInfo("America/New_York")
PERIODS = {"dev": ("2026-01-02", "2026-06-30"), "confirm": ("2026-07-01", "2026-10-16"), "ytd": ("2026-01-02", "2026-10-16"),
           "aug_oct": ("2026-08-03", "2026-10-16"), "y2025": ("2025-04-14", "2025-12-31"), "all18m": ("2025-04-14", "2026-10-16")}
RISK_USD, POINT_VALUE, COMMISSION_RT, SLIP_PTS, MAX_QTY = 350.0, 2.0, 1.40, 0.25, 40
PV = {"NQ": 2.0, "ES": 5.0}           # micro contracts: MNQ $2/pt, MES $5/pt (ES data starts 2025-04-13)
GATE = {"pf": 1.3, "tpw": (2.0, 5.0), "max_dd": -2000.0, "pass_edge_pts": 10.0}


# ------------------------------------------------------------------------------------------------ data
_BARS = {}


def bars(sym="NQ", tf="5m", start=None, end=None, warmup_days=0):
    """Bars as a DataFrame: time (unix open), open/high/low/close/volume, et (datetime ET), day (trading day: the session
    that opens 18:00 ET belongs to the next date), mod (ET minutes after midnight). start/end are trading days."""
    key = (sym, tf)
    if key not in _BARS:
        df = pd.read_csv(os.path.join(ROOT, "data", f"{sym}_{tf}.csv"))
        df = df[~((df["high"] == df["low"]) & (df["volume"] <= 0))].sort_values("time").reset_index(drop=True)
        et = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(ET)
        df["et"] = et
        df["day"] = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")
        df["mod"] = et.dt.hour * 60 + et.dt.minute
        _BARS[key] = df
    df = _BARS[key]
    if start:
        a = (dt.date.fromisoformat(start) - dt.timedelta(days=warmup_days)).isoformat() if warmup_days else start
        df = df[df["day"] >= a]
    if end:
        df = df[df["day"] <= end]
    return df.reset_index(drop=True)


def sessions(start, end):
    return sorted(set(bars("NQ", "5m", start, end)["day"]))


# ------------------------------------------------------------------------------------------------ trades
def size(stop_pts, risk_usd=RISK_USD, sym="NQ"):
    if stop_pts <= 0:
        return 0
    return int(min(MAX_QTY, risk_usd // (stop_pts * PV.get(sym, POINT_VALUE))))


def make_trade(entry_t, exit_t, d, entry, stop, exit_px, exit_kind, setup="", qty=None, mae_pts=None, sym="NQ",
               risk_usd=RISK_USD, entry_kind="market", **extra):
    """Fill pnl ($, after costs) and r for a rule-module trade. entry_kind 'market' (signal close, pays 1 tick) or
    'limit' (resting order filled at its price, no slippage). sym 'NQ' -> MNQ $2/pt, 'ES' -> MES $5/pt."""
    pv = PV.get(sym, POINT_VALUE)
    risk_pts = abs(entry - stop)
    slip_in = SLIP_PTS if entry_kind == "market" else 0.0
    q = size(risk_pts + slip_in, risk_usd, sym) if qty is None else int(qty)
    fill_in = entry + d * slip_in
    fill_out = exit_px - d * SLIP_PTS if exit_kind in ("stop", "market", "time", "be") else exit_px
    pts = (fill_out - fill_in) * d
    pnl = pts * pv * q - COMMISSION_RT * q
    r = pnl / (risk_pts * pv * q) if q and risk_pts else 0.0
    day = (dt.datetime.fromtimestamp(int(entry_t), ET) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")
    t = {"day": day, "entry_t": int(entry_t), "exit_t": int(exit_t), "dir": int(d), "entry": float(entry), "stop": float(stop),
         "exit": float(exit_px), "exit_kind": exit_kind, "setup": setup, "qty": q, "risk_pts": round(risk_pts, 2),
         "pnl": round(pnl, 2), "r": round(r, 3), "sym": sym}
    if mae_pts is not None:
        t["mae_usd"] = round(mae_pts * pv * q, 2)
    t.update(extra)
    return t


# ------------------------------------------------------------------------------------------------ stats
def _boot(x, n=4000, seed=7):
    x = np.asarray(x, float)
    if len(x) < 5:
        return [None, None]
    m = x[np.random.default_rng(seed).integers(0, len(x), (n, len(x)))].mean(1)
    return [round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3)]


def day_series(trades, start, end, given_days=None):
    """Daily P&L + intraday low (worst realized/open point) for every session in the period (no-trade days = 0)."""
    if given_days is not None:
        return [d for d in given_days if start <= d["date"] <= end]
    by = collections.defaultdict(list)
    for t in sorted(trades, key=lambda t: t["entry_t"]):
        by[t["day"]].append(t)
    out = []
    for d in sessions(start, end):
        cum, low = 0.0, 0.0
        for t in by.get(d, []):
            low = min(low, cum - abs(t.get("mae_usd", 0.0)))
            cum += t["pnl"]
            low = min(low, cum)
        out.append({"date": d, "pnl": round(cum, 2), "low": round(low, 2), "trades": len(by.get(d, []))})
    return out


def evals(days):
    from engine.analytics import PLANS, rolling_evals, simulate_eval
    plan = PLANS["builder_50k"]
    ds = [{"date": d["date"], "pnl": d["pnl"], "low_intraday": d["low"]} for d in days]
    roll = rolling_evals(ds, plan)
    k, b2b = 0, collections.Counter()
    while k < len(ds):
        r = simulate_eval([d["pnl"] for d in ds[k:]], plan, [d["low_intraday"] for d in ds[k:]])
        b2b[r["result"]] += 1
        if r["result"] == "OPEN":
            break
        k += max(1, r["days"])
    tdays = [d for d in ds if d["pnl"] != 0]
    mu = float(np.mean([d["pnl"] for d in tdays])) if tdays else 0.0
    zero = [{**d, "pnl": d["pnl"] - mu, "low_intraday": min(0.0, d["low_intraday"] - mu)} if d["pnl"] != 0 else d for d in ds]
    base = rolling_evals(zero, plan)
    return {"rolling_pass": roll["pass_rate"], "avg_days_to_pass": roll["avg_days_to_pass"], "completed": roll["completed"],
            "b2b_pass": b2b["PASS"], "b2b_fail": b2b["FAIL"], "zero_edge_pass": base["pass_rate"]}


def stats(trades, start, end, given_days=None):
    tr = [t for t in trades if start <= t["day"] <= end]
    days = day_series(tr, start, end, given_days)
    n = len(tr)
    pnl = np.array([t["pnl"] for t in tr]) if n else np.zeros(0)
    rr = np.array([t["r"] for t in tr]) if n else np.zeros(0)
    gp, gl = float(pnl[pnl > 0].sum()), float(-pnl[pnl < 0].sum())
    dpnl = np.array([d["pnl"] for d in days]) if days else np.zeros(1)
    eq = np.cumsum(dpnl)
    max_dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()) if len(eq) else 0.0
    weeks = collections.Counter()
    for d in days:
        y, w, _ = dt.date.fromisoformat(d["date"]).isocalendar()
        weeks[(y, w)] += d.get("trades", 0) if given_days is None else 0
    if given_days is not None:
        for t in tr:
            y, w, _ = dt.date.fromisoformat(t["day"]).isocalendar()
            weeks[(y, w)] += 1
    wk = list(weeks.values())
    months = collections.Counter(t["day"][:7] for t in tr)
    mnet = collections.defaultdict(float)
    for t in tr:
        mnet[t["day"][:7]] += t["pnl"]
    s = {"period": [start, end], "sessions": len(days), "trades": n, "tpw": round(n / max(len(days) / 5, 1e-9), 2),
         "weeks_in_2_5": round(100 * sum(2 <= v <= 5 for v in wk) / max(len(wk), 1), 0),
         "weeks_zero": round(100 * sum(v == 0 for v in wk) / max(len(wk), 1), 0),
         "win_rate": round(float((pnl > 0).mean() * 100), 1) if n else 0.0,
         "avg_r": round(float(rr.mean()), 3) if n else 0.0, "ci95_r": _boot(rr),
         "pf": round(gp / gl, 2) if gl > 0 else (None if gp == 0 else 99.0), "net": round(float(pnl.sum()), 2),
         "max_dd": round(max_dd, 2), "worst_day": round(float(dpnl.min()), 2) if len(dpnl) else 0.0,
         "months": {m: {"trades": months[m], "net": round(mnet[m], 2)} for m in sorted(months)},
         "losing_months": sum(1 for m in mnet if mnet[m] < 0)}
    s.update(evals(days))
    return s


def gate(s):
    lo, hi = GATE["tpw"]
    checks = {"net>0": s["net"] > 0, f"PF>={GATE['pf']}": (s["pf"] or 0) >= GATE["pf"], f"{lo}-{hi}/wk": lo <= s["tpw"] <= hi,
              "maxDD<$2k": s["max_dd"] > GATE["max_dd"],
              f"pass>=zero+{GATE['pass_edge_pts']:.0f}": (s["rolling_pass"] or 0) >= (s["zero_edge_pass"] or 0) + GATE["pass_edge_pts"]}
    return {"ok": all(checks.values()), "checks": checks}


# ------------------------------------------------------------------------------------------------ outputs
def score(trades, name, period="dev", given_days=None, notes="", params=None):
    a, z = PERIODS[period]
    s = stats(trades, a, z, given_days)
    s["gate"] = gate(s)
    s.update({"name": name, "period_name": period, "notes": notes, "params": params, "scored_at": int(time.time())})
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f"{name}__{period}.json"), "w", encoding="utf-8") as fh:
        json.dump(s, fh, indent=1, default=float)
    if period in ("confirm", "ytd"):
        new = not os.path.exists(os.path.join(OUT, "confirm_log.csv"))
        with open(os.path.join(OUT, "confirm_log.csv"), "a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["utc", "name", "period", "trades", "tpw", "pf", "net", "max_dd", "rolling_pass", "zero_edge", "gate"])
            w.writerow([dt.datetime.utcnow().isoformat(timespec="seconds"), name, period, s["trades"], s["tpw"], s["pf"],
                        s["net"], s["max_dd"], s["rolling_pass"], s["zero_edge_pass"], s["gate"]["ok"]])
    board()
    line = (f"{name} [{period}] trades={s['trades']} tpw={s['tpw']} wr={s['win_rate']}% avgR={s['avg_r']:+.3f} {s['ci95_r']} "
            f"PF={s['pf']} net={s['net']:+,.0f} maxDD={s['max_dd']:,.0f} pass={s['rolling_pass']}% (zero-edge "
            f"{s['zero_edge_pass']}%) b2b={s['b2b_pass']}/{s['b2b_fail']} gate={'PASS' if s['gate']['ok'] else 'fail'} "
            f"{[k for k, v in s['gate']['checks'].items() if not v]}")
    print(line)
    return s


def board():
    rows = []
    for f in sorted(os.listdir(OUT)) if os.path.isdir(OUT) else []:
        if f.endswith(".json") and "__" in f:
            try:
                with open(os.path.join(OUT, f), encoding="utf-8") as fh:
                    rows.append(json.load(fh))
            except Exception:
                pass
    by = collections.defaultdict(dict)
    for s in rows:
        by[s["name"]][s["period_name"]] = s
    L = ["# Strategy Lab leaderboard (2026, real NQ1!)", "",
         f"Protocol: dev {PERIODS['dev'][0]}..{PERIODS['dev'][1]} | confirm {PERIODS['confirm'][0]}..{PERIODS['confirm'][1]} | "
         f"gate PF>={GATE['pf']}, {GATE['tpw'][0]}-{GATE['tpw'][1]}/wk, maxDD<$2k, net>0, eval pass >= zero-edge+{GATE['pass_edge_pts']:.0f}pts",
         "", "| name | period | trades | /wk | win % | avg R [95% CI] | PF | net $ | max DD $ | 50K pass % (zero-edge) | b2b | gate |",
         "|---|---|---:|---:|---:|---|---:|---:|---:|---|---|---|"]
    def key(n):
        d = by[n].get("dev", {})
        return -(d.get("net") or -1e9)
    for n in sorted(by, key=key):
        for p in ("dev", "confirm", "ytd"):
            s = by[n].get(p)
            if not s:
                continue
            L.append(f"| {n} | {p} | {s['trades']} | {s['tpw']} | {s['win_rate']} | {s['avg_r']:+.3f} {s['ci95_r']} | {s['pf']} | "
                     f"{s['net']:+,.0f} | {s['max_dd']:,.0f} | {s['rolling_pass']} ({s['zero_edge_pass']}) | {s['b2b_pass']}/{s['b2b_fail']} | "
                     f"{'PASS' if s['gate']['ok'] else 'fail'} |")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "LEADERBOARD.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


# ------------------------------------------------------------------------------------------------ Liquidity Engine adapter
def engine_trades(params, start, end, procs=10, label="eng"):
    """Exact live-loop replay of the Liquidity Engine (20-day window per session, as engine/live.py) for sessions in
    [start, end]. Returns (trades, days) in lab format."""
    from multiprocessing import Pool

    from tools import five_year as fy
    jobs = [j for j in fy.live_jobs(params or {}, label) if start <= j[2] <= end]
    with Pool(min(procs, len(jobs))) as p:
        outs = p.map(fy.bt, jobs, chunksize=4)
    res = fy.merge(outs, label)
    trades = [{**t, "setup": t.get("trigger") or "engine"} for t in res["trades"]]
    days = [{"date": d["date"], "pnl": d["pnl"], "low": d["low"], "trades": d.get("trades", 0)} for d in res["days"]]
    return trades, days


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["engine", "score", "board"])
    ap.add_argument("--name")
    ap.add_argument("--period", default="dev", choices=list(PERIODS))
    ap.add_argument("--params", default="{}")
    ap.add_argument("--trades")
    ap.add_argument("--procs", type=int, default=10)
    a = ap.parse_args()
    if a.cmd == "board":
        board()
    elif a.cmd == "engine":
        p = json.loads(a.params)
        s0, s1 = PERIODS[a.period]
        tr, ds = engine_trades(p, s0, s1, a.procs, a.name)
        score(tr, a.name, a.period, given_days=ds, params=p)
    else:
        with open(a.trades, encoding="utf-8") as fh:
            score(json.load(fh), a.name, a.period)
