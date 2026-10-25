"""Eval weekly loss stop (lit_sizing "wk_loss_usd", default off; research/writeups/lit-risk-money.md, 2026-10-20):
engine/sizing.lit_qty routes 0 in an eval mode once the eval's closed P&L of the current calendar week (state["wk_pnl"],
engine/sizing.eval_state(..., today=)) is <= -wk_loss_usd. Off (key absent) = exactly the old sizing.

    python -X utf8 -m tests.test_lit_wk_loss           # unit checks + the research parity on the 2026 eval path (~25 s)
    python -X utf8 -m tests.test_lit_wk_loss --quick   # unit checks only (~1 s)
Paper only.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import sizing as sz  # noqa: E402

RESULTS = []
LSZ = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
TW = {"mode": "two_week", "two_week": LSZ["two_week"], "two_week_until": 10, "after_mode": "safe_eval", "safe_cap": 0.6}
TR = {"risk_pts": 30.0, "tgt_pts": 150.0, "size_mult": 1.0}


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def unit():
    st = sz.eval_state({"2026-10-12": -990.0}, 0.0, session=3, today="2026-10-14")
    check("eval_state(today=) adds this week's closed eval P&L", st.get("wk_pnl") == -990.0, st)
    old = sz.eval_state({"2026-10-12": -990.0}, 0.0, session=3)
    check("eval_state without today: no wk_pnl key (old output)", "wk_pnl" not in old and {k: v for k, v in st.items() if k != "wk_pnl"} == old)
    st2 = sz.eval_state({"2026-10-09": -990.0, "2026-10-12": 200.0}, -100.0, session=4, today="2026-10-13")
    check("only the same ISO week counts (Friday before is out)", st2["wk_pnl"] == 100.0, st2)
    q0 = sz.lit_qty(26, TR, TW, room=st["room"], state=st, learning=None)
    q1 = sz.lit_qty(26, TR, {**TW, "wk_loss_usd": None}, room=st["room"], state=st, learning=None)
    check("key absent / None: same micros as before", q0["qty"] == q1["qty"] and q0["qty"] > 0, (q0, q1))
    q2 = sz.lit_qty(26, TR, {**TW, "wk_loss_usd": 800.0}, room=st["room"], state=st, learning=None)
    check("week -$990 <= -$800: no trade", q2["qty"] == 0 and "weekly loss stop" in " ".join(q2["reasons"]), q2)
    q3 = sz.lit_qty(26, TR, {**TW, "wk_loss_usd": 1200.0}, room=st["room"], state=st, learning=None)
    # not stopped, but since the A4 ceilings (2026-10-25, engine/sizing.ceilings) the week's $210 left caps the stop-out:
    # 3 x $62 fits, 4 does not (was: "trades as before" = 8 micros, a full stop-out past the -$1,200 week)
    check("week -$990 > -$1,200: trades, capped to the $210 left of the week", 0 < q3["qty"] < q0["qty"]
          and q3["qty"] * 62 <= 210 < (q3["qty"] + 1) * 62 and any("eval weekly loss" in r for r in q3["reasons"]), (q3, q0))
    q4 = sz.lit_qty(26, TR, {**TW, "wk_loss_usd": 800.0}, room=old["room"], state=old, learning=None)
    check("week P&L unknown: no effect, reason logged", q4["qty"] == q0["qty"] and "unknown" in " ".join(q4["reasons"]), q4)
    st11 = sz.eval_state({f"2026-10-{d:02d}": 0.0 for d in (1, 2)}, -1000.0, session=11, today="2026-10-14")
    q5 = sz.lit_qty(26, TR, {**TW, "wk_loss_usd": 800.0}, room=st11["room"], state=st11, learning=None)
    check("applies after session 10 too (after_mode safe_eval)", q5["qty"] == 0, q5)
    q6 = sz.lit_qty(26, TR, {"mode": "normal", "wk_loss_usd": 800.0}, room=st["room"], state=st, learning=None)
    check("non-eval mode (normal): never applied", q6["qty"] == 26, q6)


def parity():
    from tools import lit_risk_money as M
    check("research rule == engine lit_qty on the 2026 eval path (base + all3, -$800 / -$1,200)", M.check_engine_wk())


def main():
    unit()
    if "--quick" not in sys.argv:
        parity()
    print(f"{sum(RESULTS)}/{len(RESULTS)} passed")
    return all(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
