"""CONT track: score every pre-registered continuation variant on NQ and ES (single process).

    python tools/lab_cont_run.py            # all variants x {NQ, ES} x {ytd, aug_oct, y2025, all18m}
Writes research/lab/CONT_<SYM>_<VARIANT>__<period>.json via strategy_lab.score, trade lists to
research/lab/CONT_trades/, and a compact summary to research/lab/CONT_summary.json.
"""
import collections
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import strategy_lab as sl  # noqa: E402
from tools.lab_models import continuation as m  # noqa: E402

PERIODS = ("ytd", "aug_oct", "y2025", "all18m")
OUT = os.path.join(ROOT, "research", "lab")


def extra_stats(tr, a, z):
    tr = [t for t in tr if a <= t["day"] <= z]
    ex = collections.Counter(t["exit_kind"] for t in tr)
    lo = [t for t in tr if t["dir"] == 1]
    sh = [t for t in tr if t["dir"] == -1]
    days = sl.sessions(a, z)
    weeks = collections.Counter()
    for d in days:
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        weeks[(y, w)] += 0
    for t in tr:
        y, w, _ = dt.date.fromisoformat(t["day"]).isocalendar()
        weeks[(y, w)] += 1
    q = collections.defaultdict(float)
    for t in tr:
        y, mth = int(t["day"][:4]), int(t["day"][5:7])
        q[f"{y}Q{(mth - 1) // 3 + 1}"] += t["pnl"]
    rs = sorted(t["risk_pts"] for t in tr)
    return {"exits": dict(ex), "long_n": len(lo), "long_net": round(sum(t["pnl"] for t in lo), 2), "short_n": len(sh),
            "short_net": round(sum(t["pnl"] for t in sh), 2),
            "weeks_ge1": round(100 * sum(v >= 1 for v in weeks.values()) / max(len(weeks), 1), 0),
            "median_risk_pts": rs[len(rs) // 2] if rs else None, "quarters": {k: round(v, 2) for k, v in sorted(q.items())},
            "avg_qty": round(sum(t["qty"] for t in tr) / len(tr), 1) if tr else None}


def main():
    t00 = time.time()
    summary = {}
    os.makedirs(os.path.join(OUT, "CONT_trades"), exist_ok=True)
    for sym in ("NQ", "ES"):
        b = sl.bars(sym, "5m", "2025-04-14", "2026-10-16", warmup_days=30)
        print(f"{sym}: {len(b)} bars {b['day'].iloc[0]} .. {b['day'].iloc[-1]} (last bar {b['et'].iloc[-1]})")
        for v in m.VARIANTS:
            name = f"CONT_{sym}_{v}"
            params = {"variant": v, "sym": sym}
            t0 = time.time()
            tr = m.run(b, params)
            with open(os.path.join(OUT, "CONT_trades", f"{name}.json"), "w", encoding="utf-8") as fh:
                json.dump(tr, fh, indent=0, default=float)
            summary[name] = {}
            for per in PERIODS:
                s = sl.score(tr, name, per, params=m._params(params),
                             notes="ICT continuation, rules fixed in research/lab/CONT_RULES.md before testing")
                a, z = sl.PERIODS[per]
                summary[name][per] = {k: s[k] for k in ("trades", "tpw", "win_rate", "avg_r", "ci95_r", "pf", "net", "max_dd",
                                                        "worst_day", "rolling_pass", "zero_edge_pass", "b2b_pass", "b2b_fail",
                                                        "weeks_in_2_5", "weeks_zero", "losing_months", "months", "completed")}
                summary[name][per].update(extra_stats(tr, a, z))
                summary[name][per]["gate"] = s["gate"]["ok"]
            print(f"  {name}: {len(tr)} trades total, {time.time() - t0:.1f}s")
    with open(os.path.join(OUT, "CONT_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, default=float)
    print(f"done in {time.time() - t00:.0f}s")


if __name__ == "__main__":
    main()
