"""PERSON track: score discretionary-layer variants (engine/liquidity_map.py, research/lab/DOL_PLAYBOOK.md) with the
Strategy Lab's own live-loop replay and scorecard (tools/strategy_lab.py is used read-only).

Each session is an independent 20-day live-loop replay (strategy_lab.engine_trades), so ONE replay over ytd yields
exactly the trades of separate dev / confirm / aug_oct runs; they are scored from it with strategy_lab.score().
y2025 is a second replay.

  python tools/lab_person_run.py <variant> [--procs 2]        # writes research/lab/P_<variant>__<period>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("LE_NO_AUTOSTART", "1")

BASE = {"grade_sizing": False, "conviction_step": 0, "max_trades_day": 1}      # live pick (live_model.json)
_T = {"target_mode": "draw"}                                                    # 1. final target (DOL-4)
_PB = {**_T, "manage_mode": "person", "person_trail": False}                     # 2. + TP1 partial + BE (DOL-5, MGMT-1/2)
_TR = {**_PB, "person_trail": True}                                             # 3. + structure trail (MGMT-3)
_CI = {**_TR, "exit_rules": "giveback,cisd_disp"}                               # 4. + opposing CISD exit (MGMT-5)
_TI = {**_CI, "time_stop_min": 60, "noon_exit": True}                           # 5. + time exits (MGMT-7)
_SK = {**_TI, "draw_hrlr": "tp1", "draw_block_r": 1.0}                          # 6. + skip rules (DOL-6)
_ST = {"stop_model": "struct_atr"}                                              # stop alone (STOP-1..3)
VARIANTS = {
    "base": {},
    "1_target": _T,
    "2_partial_be": _PB,
    "3_trail": _TR,
    "4_cisd": _CI,
    "5_time": _TI,
    "6_skip": _SK,
    "7_stop": _ST,
    "7b_stop_cap60": {**_ST, "stop_cap": "spec"},
    "8_full": {**_SK, **_ST},
    "8b_noskip": {**_TI, **_ST},
    "9_sig": {**_SK, **_ST, "draw_pick": "significance"},
    # IN-SAMPLE: data/draw_learner.json is trained on 2021-11..2026-10-13; compare with 1_target only, never adopt on it
    "10_learned": {**_T, "draw_rank": "learned"},
    # added after DRAW_LEARNER.md (coordinator, 18:47 ET): farthest within-reach ERL, + IRL partial, + PM nearest cap
    "12_far": {**_T, "draw_pick": "farthest_reach", "draw_fallback": "skip"},
    "13_far_partial": {**_T, "draw_pick": "farthest_reach", "draw_fallback": "skip", "manage_mode": "person",
                       "person_trail": False},
    "14_far_pm": {**_T, "draw_pick": "farthest_reach", "draw_fallback": "skip", "manage_mode": "person",
                  "person_trail": False, "draw_pm": "nearest"},
    # person management (TP1 at the first internal draw + BE at TP1 / +1R) on TODAY's target (nearest major, 5R cap)
    "15_mgmt_on_base": {"manage_mode": "person", "person_trail": False},
    # added after TRADER_HEURISTICS.md (coordinator, 19:19 ET): 14 + B1 strong prior-day extreme + B3 one side +
    # never fade an opening drive + balance-day nearest draw
    "16_heuristics": {**_T, "draw_pick": "farthest_reach", "draw_fallback": "skip", "manage_mode": "person",
                      "person_trail": False, "draw_pm": "nearest", "draw_pdx": True, "draw_one_side": True,
                      "no_fade_drive": True, "balance_first": True},
    # added after the chart gallery (coordinator, 19:45 ET): most full-stop losers died inside the entry bar
    "17_retest6": {"entry_mode": "retest", "retest_bars": 6},
    "17b_retest12": {"entry_mode": "retest", "retest_bars": 12},
    "18_protected": {"stop_model": "protected_swing", "stop_cap": "spec"},
    "19_combo6": {"entry_mode": "retest", "retest_bars": 6, "stop_model": "protected_swing", "stop_cap": "spec",
                  "manage_mode": "person", "person_trail": False},
    "19b_combo12": {"entry_mode": "retest", "retest_bars": 12, "stop_model": "protected_swing", "stop_cap": "spec",
                    "manage_mode": "person", "person_trail": False},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--periods", default="ytd,y2025")
    a = ap.parse_args()
    from tools import strategy_lab as sl
    params = {**BASE, **VARIANTS[a.variant]}
    name = f"P_{a.variant}"
    out = {}
    for big in a.periods.split(","):
        t0 = time.time()
        s0, s1 = sl.PERIODS[big]
        tr, ds = sl.engine_trades(params, s0, s1, a.procs, name)
        subs = ["dev", "confirm", "aug_oct", "ytd"] if big == "ytd" else [big]
        for per in subs:
            out[per] = sl.score(tr, name, per, given_days=ds, params=params)
        # NB: no "__" in this file name - strategy_lab.board() reads every research/lab/*__*.json as a scorecard
        with open(os.path.join(sl.OUT, f"{name}_trades_{big}.json"), "w", encoding="utf-8") as fh:
            json.dump(tr, fh, default=float)
        print(f"[{name}] {big} replay done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
