"""Unit test of the two-week eval sizing (tools/lit_2wk_sizing.py two_week_qty, the lit_sizing mode "two_week").

    python -X utf8 -m tests.test_lit_2wk_sizing
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.lit_2wk_sizing import MFFU_25K, two_week_qty, eval_state  # noqa: E402

A0 = {"mode": "two_week", "base": "need", "room_f": 1.0, "wk": True}           # the recommended config
C = {"mode": "two_week", "base": "need", "room_f": 0.6, "wk": False}            # the safer option
FRESH = {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0}


def check(name, got, want):
    ok = got == want
    print(f"{'ok  ' if ok else 'FAIL'} {name}: {got} (want {want})")
    return ok


def main():
    r = []
    # one winner passes: 40-pt stop, 200-pt target (5R): ceil(3000 / (200 x 2 - 1.40)) = ceil(7.53) = 8 micros
    r.append(check("fresh eval, 5R target", two_week_qty({"risk_pts": 40, "tgt_pts": 200}, FRESH, A0), 8))
    why = []
    two_week_qty({"risk_pts": 40, "tgt_pts": 200}, FRESH, A0, why=why)
    r.append(check("reason logged", "one winner passes" in why[0], True))
    # target from entry/target prices (a live trade dict)
    r.append(check("target from prices", two_week_qty({"entry": 20000.0, "stop": 19960.0, "target": 20200.0}, FRESH, A0), 8))
    # small target (1.5R): 26 micros wanted, a full stop-out must stay inside the $1,000 soft daily loss:
    # 1000 / ((40 + 0.25) x 2 + 1.40) = 12.2 -> 12
    r.append(check("soft daily loss cap", two_week_qty({"risk_pts": 40, "tgt_pts": 60}, FRESH, A0), 12))
    # after a -$1,000 day: room $1,000 -> room 100%: 1000 / 80 = 12; room 60%: 600 / 80 = 7
    after = {"profit": -1000.0, "cum": 0.0, "room": 1000.0, "session": 2}
    r.append(check("room 100% after a loss", two_week_qty({"risk_pts": 40, "tgt_pts": 60}, after, A0), 12))
    r.append(check("room 60% after a loss", two_week_qty({"risk_pts": 40, "tgt_pts": 60}, after, C), 7))
    # the weekly stop halves the need size (A0 has it on, C off)
    r.append(check("weekly stop x0.5", two_week_qty({"risk_pts": 40, "tgt_pts": 200, "size_mult": 0.5}, FRESH, A0), 4))
    r.append(check("weekly stop off", two_week_qty({"risk_pts": 40, "tgt_pts": 200, "size_mult": 0.5}, FRESH, C), 8))
    # need shrinks as the eval gets closer: +$2,500 -> $500 left -> ceil(500 / 398.6) = 2
    r.append(check("close to target", two_week_qty({"risk_pts": 40, "tgt_pts": 200}, {"profit": 2500.0, "room": 2000.0}, A0), 2))
    # never risk the pass: the day already reached the target
    r.append(check("target reached today", two_week_qty({"risk_pts": 40, "tgt_pts": 200}, {"profit": 2900.0, "cum": 200.0, "room": 2000.0}, A0), 0))
    # minimum 1 micro even when the room is tiny
    r.append(check("min 1 micro", two_week_qty({"risk_pts": 80, "tgt_pts": 160}, {"profit": -1950.0, "room": 50.0}, A0), 1))
    # maximum 40 micros
    r.append(check("max 40 micros", two_week_qty({"risk_pts": 8, "tgt_pts": 12}, FRESH, {**A0, "dll_cap": False}), 40))
    # a losing day so far shrinks the daily-loss budget: -$600 today -> 400 / 81.9 = 4
    r.append(check("daily budget after -$600", two_week_qty({"risk_pts": 40, "tgt_pts": 60}, {"profit": 0.0, "cum": -600.0, "room": 1400.0}, A0), 4))
    # clock press: x2 from session 6 (before the caps)
    P = {**A0, "press_at": 6, "press_mult": 2.0}
    r.append(check("press off before session 6", two_week_qty({"risk_pts": 40, "tgt_pts": 400}, {**FRESH, "session": 5}, P), 4))
    r.append(check("press x2 from session 6", two_week_qty({"risk_pts": 40, "tgt_pts": 400}, {**FRESH, "session": 6}, P), 8))
    # base "lit" = today's eval mode: $800 up to a 25-pt stop: 800 x 25 / 44 / 88 = 5.2 -> 5 (engine/sizing.lit_qty eval == 5)
    r.append(check("lit base 800/25", two_week_qty({"risk_pts": 44}, FRESH, {"base": "lit", "usd": 800, "ref": 25, "room_f": 0.6, "dll_cap": False}), 5))
    # 25K Builder: $1,500 target, $600 soft daily loss, 20 micros: need ceil(1500 / 398.6) = 4; dll 600 / 81.9 = 7
    r.append(check("25K need", two_week_qty({"risk_pts": 40, "tgt_pts": 200}, {"profit": 0.0, "room": 1000.0}, A0, acct=MFFU_25K), 4))
    r.append(check("25K small target", two_week_qty({"risk_pts": 40, "tgt_pts": 60}, {"profit": 0.0, "room": 1000.0}, A0, acct=MFFU_25K), 7))
    # eval state from the day P&L: +1,000 then -500 -> profit 500, floor -1,000 -> room 1,500; session 3
    st = eval_state({"2026-01-05": 1000.0, "2026-01-06": -500.0})
    r.append(check("eval_state", (st["profit"], st["room"], st["session"]), (500.0, 1500.0, 3)))
    st = eval_state({"a": 2200.0, "b": -200.0})                                  # floor locks at +$100
    r.append(check("eval_state lock", st["room"], 1900.0))
    # regression against the study (needs the unit-trade cache from python tools/lit_2wk.py build)
    from tools import lit_2wk as W
    if os.path.exists(W._unit_path("live")):
        o = W.exact(W.FINAL["max_plain"][1], "H1")
        r.append(check("study: A0 H1 2-week pass/fail", (o["p10"], o["f10"]), (58.0, 17.6)))
        o = W.exact(W.FINAL["eval_today"][1], "H1")
        r.append(check("study: today's eval mode H1 (all starts) == 37.5 / 3.1", (o["p10_all"], o["f10_all"]), (37.5, 3.1)))
    else:
        print("skip study regression (no unit-trade cache)")
    print(f"{sum(r)}/{len(r)} passed")
    return all(r)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
