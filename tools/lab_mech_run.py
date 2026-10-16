"""MECH track runner: score every documented variant of mech_ifvg on NQ and ES over ytd / aug_oct / y2025 / all18m.

Every variant that is run is listed here and scored; nothing else is searched. Single process.
  python tools/lab_mech_run.py            -> scores all variants, writes research/lab/MECH_results.json
"""
import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.strategy_lab import OUT, PERIODS, bars, score  # noqa: E402
from tools.lab_models import mech_ifvg as M  # noqa: E402

# the documented variants (max 3) - see research/lab/MECH_RULES.md
VARIANTS = {
    "base": {},                                   # rules 1-10 as written
    "smt": {"smt": True},                         # + SMT divergence with the partner index required
    "rr2": {"target": "rr", "rr": 2.0},           # fixed 2R target instead of the next draw on liquidity
}
PERIOD_LIST = ["ytd", "aug_oct", "y2025", "all18m"]


def main(only=None):
    t0 = time.time()
    data = {s: bars(s, "5m", "2025-04-14", "2026-10-16", warmup_days=7) for s in ("NQ", "ES")}
    out = {}
    for sym in ("NQ", "ES"):
        partner = data["ES" if sym == "NQ" else "NQ"]
        for vname, vp in VARIANTS.items():
            if only and vname not in only:
                continue
            params = {**vp, "sym": sym}
            trades = [t for t in M.run(data[sym], params, partner) if t["day"] >= PERIODS["all18m"][0]]
            name = f"MECH_{sym}_{vname}"
            with open(os.path.join(OUT, f"MECH_trades_{sym}_{vname}.json"), "w", encoding="utf-8") as fh:
                json.dump(trades, fh)
            res = {}
            for per in PERIOD_LIST:
                s = score(trades, name, per, notes="mech_ifvg public rules", params=params)
                res[per] = {k: s[k] for k in ("trades", "tpw", "win_rate", "avg_r", "ci95_r", "pf", "net", "max_dd", "worst_day",
                                              "rolling_pass", "zero_edge_pass", "b2b_pass", "b2b_fail", "weeks_in_2_5",
                                              "weeks_zero", "losing_months", "months")}
                res[per]["gate"] = s["gate"]["ok"]
            # extra descriptive stats (all18m)
            res["exit_kinds"] = dict(collections.Counter(t["exit_kind"] for t in trades))
            res["levels"] = dict(collections.Counter(lv for t in trades for lv in t["levels"]))
            res["long_short"] = {"long": sum(t["dir"] == 1 for t in trades), "short": sum(t["dir"] == -1 for t in trades)}
            rp = sorted(t["risk_pts"] for t in trades)
            res["median_stop_pts"] = rp[len(rp) // 2] if rp else None
            out[name] = res
    path = os.path.join(OUT, "MECH_results.json")
    old = {}
    if only and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = json.load(fh)
    old.update(out)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(old, fh, indent=1, default=float)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
