"""tools/cost_alarm.py (2026-11-20): the nightly real-cost alarm. Pure checks + one real run with --print (no file written).
    python -X utf8 -m tests.test_cost_alarm
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import cost_alarm as CA  # noqa: E402

R = []


def check(name, ok, info=""):
    R.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({info})" if info and not ok else ""), flush=True)


t_stop = {"r": -1.0, "risk_pts": 20.0, "exit": "STOP"}
t_tgt = {"r": 3.0, "risk_pts": 20.0, "exit": "TARGET"}
check("a target pays only the entry's extra ticks", abs(CA.r_at(t_tgt, 10) - (3.0 - 10 * 0.25 / 20)) < 1e-9)
check("a stop pays the entry's extra + 1 more tick (2 in all)", abs(CA.r_at(t_stop, 10) - (-1.0 - 11 * 0.25 / 20)) < 1e-9)
check("no stop distance -> skipped", CA.r_at({"r": 1, "risk_pts": 0, "exit": "STOP"}, 3) is None)
check("PF = R won / R lost", CA.pf([2.0, -1.0, 1.0, -1.0]) == 1.5 and CA.pf([1.0]) is None)
check("last-40 window = 40 weekdays ending on the day", len(CA.sessions_to("2026-11-19")) == 40 and CA.sessions_to("2026-11-19")[-1] == "2026-11-19")
M = {"atlas": {"n": 2, "med": 11.0, "src": "t"}, "zlarior": {"n": 9, "med": 400.0, "src": "t"}}
a, z = CA.check("atlas", M), CA.check("zlarior", M)
check("under 5 fills -> NOT ENOUGH FILLS (no alarm on noise)", a["flag"] == "NOT ENOUGH FILLS", a["flag"])
check("an absurd cost (400 ticks) on 9 fills -> RED", z["flag"] == "RED" and z["pf40"] is not None and z["pf40"] < 1.0, z)
M2 = {"atlas": {"n": 9, "med": 0.0, "src": "t"}}
g = CA.check("atlas", M2)
check("at the backtest's own cost ATLAS's last 40 is GREEN", g["flag"] == "GREEN", g["line"])
before = os.path.getmtime(CA.OUT) if os.path.exists(CA.OUT) else None
CA.main(["--print"])
check("--print writes no file", (os.path.getmtime(CA.OUT) if os.path.exists(CA.OUT) else None) == before)
print(f"cost alarm: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAILED'}")
sys.exit(0 if all(R) else 1)
