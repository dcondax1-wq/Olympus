"""POSEIDON (order-flow lane A) out-of-sample check, 2026-11-28.

Lane A exactly as frozen after the Monday fix (research/orderflow/monfix/run.py 'after' rules = engine/of_paper
replay_summary + _prev_summary's new previous-day rule), E5 entry, costs in (the engine's R_e5 / usd_1_e5), on every pulled
real tick day in data/pc_days. Books: 'first' = the first absorbed signal of each day (= the 1-a-day cap the practice lane
trades), 'onepos' = every absorbed signal, one position at a time. In-sample = the 43 trading days the lane was picked on
(2026-09-28..2026-11-25); new = every other trading day. Periods: Dec 2025, 2026 H1 (Jan-Jun), 2026 H2 (Jul-Nov).
Eval sim (simple, labelled): MFFU Builder 25K (target $1,500, EOD trailing $1,000) and 50K ($3,000 / $2,000), started at every
trading day, trades in order, micros = 1 or 2 but never more than $50 risk a trade (of_ladder cap: a trade whose 1-micro
risk is above $50 is skipped). Paper research only: no rule change, nothing armed.
Run: python -X utf8 research/orderflow/oos/run.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "orderflow", "monfix"))
import run as M  # noqa: E402
from engine import of_paper as P  # noqa: E402

IS_FIRST, IS_LAST = "2026-09-28", "2026-11-25"
CAP = 50.0


def period(d):
    if d < "2026-01-01":
        return "dec_2025" if d >= "2025-12-01" else "nov_2025"
    return "h1_2026" if d < "2026-07-01" else "h2_2026"


def tiles(tr, Rk, Uk, days):
    s = M.stats(tr, Rk, Uk, days) if days else None
    if not s or not s["trades"]:
        return {"n": 0, "tpw": round(len(tr) / (len(days) / 5.0), 2) if days else None, "days": len(days)}
    months = max(len(days) / 21.0, 1e-9)
    return {"n": s["trades"], "tpw": s["per_week"], "win_pct": s["win_pct"], "mean_R": s["mean_R"], "pf": s["pf"],
            "usd_1": s["usd_1_micro"], "max_dd": s["max_dd_usd"], "usd_month": round(s["usd_1_micro"] / months, 0),
            "days": len(days), "halves": s["halves"]}


def eval_sim(tr, Rk, Uk, days, target, mll, micros):
    """Start a fresh eval on every trading day; walk later trades in order; pass at +target, blow at -mll (EOD trailing)."""
    by_day = {}
    for r in tr:
        risk1 = abs(float(r[Uk]) / float(r[Rk])) if float(r[Rk]) else None
        if risk1 is None or risk1 > CAP:
            continue
        q = micros if risk1 * micros <= CAP else 1
        by_day.setdefault(r["day"], []).append(float(r[Uk]) * q)
    P_, F_, open_, dpass = 0, 0, 0, []
    for i, d0 in enumerate(days):
        bal, peak, done = 0.0, 0.0, False
        for k, d in enumerate(days[i:]):
            bal += sum(by_day.get(d, []))
            if bal >= target:
                P_ += 1; dpass.append(k + 1); done = True; break
            peak = max(peak, bal)
            if bal <= peak - mll:
                F_ += 1; done = True; break
        if not done:
            open_ += 1
    tot = P_ + F_ + open_
    dpass.sort()
    return {"starts": tot, "pass_pct": round(100 * P_ / tot, 1) if tot else None, "blow_pct": round(100 * F_ / tot, 1) if tot else None,
            "open_pct": round(100 * open_ / tot, 1) if tot else None, "median_days_to_pass": dpass[len(dpass) // 2] if dpass else None}


def main():
    src = os.path.join(ROOT, "data", "pc_days")
    R = M.load(src)
    B, _, _ = P._mods()
    days = [d for d in sorted(R) if dt.date.fromisoformat(d).weekday() < 5 and d not in M.SKIP and B.has_rth(B.Day(d, R[d]))]
    rows, _ = M.rows_for(R, days, "after")
    is_days = [d for d in days if IS_FIRST <= d <= IS_LAST]
    new_days = [d for d in days if d not in is_days]
    out = {"made": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z", "files": len(R), "trading_days": len(days),
           "first": days[0] if days else None, "last": days[-1] if days else None, "in_sample_days": len(is_days),
           "new_days": len(new_days), "books": {}}
    for kind in ("first", "onepos"):
        tr, Rk, Uk = M.book(rows, kind, "e5")
        b = {"in_sample": tiles([r for r in tr if r["day"] in set(is_days)], Rk, Uk, is_days),
             "new": tiles([r for r in tr if r["day"] in set(new_days)], Rk, Uk, new_days),
             "all": tiles(tr, Rk, Uk, days)}
        for p in ("nov_2025", "dec_2025", "h1_2026", "h2_2026"):
            pdays = [d for d in days if period(d) == p]
            b[p] = tiles([r for r in tr if period(r["day"]) == p], Rk, Uk, pdays)
        b["eval"] = {f"{name}_{m}mnq": eval_sim(tr, Rk, Uk, days, t, l, m)
                     for name, t, l in (("b25k", 1500, 1000), ("b50k", 3000, 2000)) for m in (1, 2)}
        out["books"][kind] = b
    json.dump(out, open(os.path.join(HERE, "lane_a.json"), "w"), indent=1)
    print(json.dumps({k: {p: {x: v[p].get(x) for x in ("n", "tpw", "win_pct", "mean_R", "pf", "usd_1", "max_dd", "usd_month", "days")}
                          for p in v if p != "eval"} for k, v in out["books"].items()}, indent=1))
    print(json.dumps({k: v["eval"] for k, v in out["books"].items()}, indent=1))


if __name__ == "__main__":
    main()
