"""Shared helpers for the overnight study scripts (study_night_*.py).

Every study runs the REAL engine (engine.backtest.run) once per symbol per variant with flat sizing
({"dd_aware": False, "daily_max_loss": 1e9}, as study_be / study_exitsig do) and then slices the trade list into the
four test periods by trading day. Nothing in engine/ is touched.
"""
from __future__ import annotations

import numpy as np

from engine import backtest

# (label, symbol, first day, last day)  -- None = open ended
SEGS = [("NQ 2026", "NQ", None, None),
        ("CFD Q4 2023", "NQX", None, "2023-12-31"),
        ("CFD 2024", "NQX", "2024-01-01", "2024-12-31"),
        ("CFD 2025", "NQX", "2025-01-01", "2025-12-31")]
FLAT = {"dd_aware": False, "daily_max_loss": 1e9}
MIN_TPW = 2.5          # owner's frequency floor (trades per week, every period)


def in_seg(day, a, z):
    return (not a or day >= a) and (not z or day <= z)


def run_both(params):
    """Run NQ and NQX once with the given overrides on top of flat sizing. Returns {sym: result}."""
    p = {**FLAT, **(params or {})}
    return {sym: backtest.run(sym, "5m", p, light=True) for sym in ("NQ", "NQX")}


def seg_trades(res, label=None):
    """Split a run_both() result into {segment label: (trades, days)}."""
    out = {}
    for lab, sym, a, z in SEGS:
        if label and lab != label:
            continue
        r = res[sym]
        tr = [t for t in r["trades"] if in_seg(t["day"], a, z)]
        dy = [d for d in r["days"] if in_seg(d["date"], a, z)]
        out[lab] = (tr, dy)
    return out


def metrics(tr, dy):
    """Per-period numbers the owner asked for: trades, trades/week, avg R, net $, PF, max DD."""
    nd = len(dy)
    wk = max(nd / 5.0, 1e-9)
    if not tr:
        return {"n": 0, "tpw": 0.0, "avg_r": 0.0, "net": 0.0, "pf": 0.0, "dd": 0.0, "wr": 0.0, "days": nd}
    pnl = np.array([t["pnl"] for t in tr])
    g, l = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    eq = np.cumsum(pnl)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())
    return {"n": len(tr), "tpw": len(tr) / wk, "avg_r": float(np.mean([t["pnl_r"] for t in tr])), "net": float(pnl.sum()),
            "pf": float(g / l) if l > 0 else 99.0, "dd": dd, "wr": float((pnl > 0).mean()), "days": nd}


def fmt(m):
    flag = "" if m["tpw"] >= MIN_TPW else " LOW"
    return f"{m['n']:3d}t {m['tpw']:.1f}/wk{flag} {m['avg_r']:+.2f}R ${m['net']:+6.0f} PF {min(m['pf'], 99):4.1f} DD {m['dd']:5.0f}"


def cell(m):
    """Compact markdown cell."""
    flag = "" if m["tpw"] >= MIN_TPW else " (LOW)"
    return f"{m['n']} / {m['tpw']:.1f}wk{flag} / {m['avg_r']:+.2f}R / ${m['net']:+,.0f} / PF {min(m['pf'], 99):.1f} / DD {m['dd']:,.0f}"


def evaluate(params):
    """Run a variant and return (per-segment metrics dict, four-period total $, min trades/week)."""
    res = run_both(params)
    segs = seg_trades(res)
    ms = {lab: metrics(*segs[lab]) for lab in segs}
    total = sum(m["net"] for m in ms.values())
    min_tpw = min(m["tpw"] for m in ms.values())
    return ms, total, min_tpw


def md_table(rows, header):
    """rows: list of lists of str. Returns a markdown table string."""
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def verdict(ms, total, base_ms, base_total):
    """Owner's adoption rule: better four-period total, no money lost on NQ 2026, >= 2.5 trades/wk everywhere."""
    nq = ms["NQ 2026"]["net"]
    freq_ok = all(m["tpw"] >= MIN_TPW for m in ms.values())
    better = total > base_total
    nq_ok = nq >= base_ms["NQ 2026"]["net"] - 1e-6 if base_ms else nq > 0
    if better and nq_ok and freq_ok:
        return "PASS"
    why = []
    if not better:
        why.append("total not better")
    if not nq_ok:
        why.append("NQ 2026 worse")
    if not freq_ok:
        why.append("freq < 2.5/wk")
    return "fail: " + ", ".join(why)
