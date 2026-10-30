"""LIT scale-in owner switches (research/writeups/lit-edge-2026-10-30.md adopt-candidate; OFF until the owner sets them in
live_model.json "lit_sizing" and the Sim add roundtrip passed): "scale_in_from_session": N (no add before eval session N) and
"scale_in_funded": false (no add on a funded account), the same in the PC bot (engine/live.LiveBot._add_qty) and the cloud
paper ledger (tools/cloud_monitor.lit_add_usd). Absent = today's sizing, unchanged.

  python -X utf8 -m tests.test_scale_in_switches          # < 2 s
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from engine import live as LV, sizing  # noqa: E402
import cloud_monitor as CM  # noqa: E402

RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {info}"), flush=True)


def bot(lsz, session, mode="two_week"):
    errs = []
    b = SimpleNamespace(_lit_sizing={"mode": mode, **lsz}, state={"strategy": {"params": {"scale_in": {"f": 1.0}}}}, _open_qty=6,
                        cfg={"params": {"max_micros": 40}}, _note_error=errs.append)
    b.eval_state = lambda: {"session": session, "profit": 0.0, "cum": 0.0}
    b.eval_room = lambda: 1800.0
    b.day_pnl_routed = lambda: 0.0
    b._adds_qty = lambda et: 0
    b.errs = errs
    return b


POS = {"qty": 6, "risk_pts": 40.0, "entry_t": 1790000000, "adds": []}
ADD = {"n": 1, "rk": 2.5, "qty": 6, "prev_rk": [], "f": 1.0}


def q(b):
    return LV.LiveBot._add_qty(b, dict(POS), dict(ADD))


def main():
    base = q(bot({}, 2))
    check("no switch: today's add size (an add > 0 at session 2)", base > 0, base)
    check("from_session 5: no add at session 2 and 4", q(bot({"scale_in_from_session": 5}, 2)) == 0 and q(bot({"scale_in_from_session": 5}, 4)) == 0)
    check("from_session 5: the same add as today from session 5", q(bot({"scale_in_from_session": 5}, 5)) == q(bot({}, 5)) > 0)
    fb = bot({"scale_in_funded": False}, 3, mode="funded")
    check("scale_in_funded false: no add on a funded account", q(fb) == 0 and not fb.errs, fb.errs)
    fa = bot({}, 3, mode="funded")
    check("funded without the switch: unchanged (today's funded add path)", q(fa) == LV.LiveBot._add_qty(fa, dict(POS), dict(ADD)))
    # the cloud paper ledger books the same
    t = {"entry_t": 1790000000, "qty": 6, "pts": 30.0, "risk_pts": 40.0, "adds": [{"rk": 2.5, "prev_rk": [], "qty": 6, "pts": 20.0}]}
    day = CM.tday(t["entry_t"])
    s_of = sizing.eval_session
    start_s2 = next(d for d in (f"2026-09-{x:02d}" for x in range(1, 29)) if s_of(d, day) == 2)
    lsz = {"mode": "two_week", "eval_start": start_s2}
    usd0, q0 = CM.lit_add_usd({}, t, 6, lsz)
    usd5, q5 = CM.lit_add_usd({}, t, 6, {**lsz, "scale_in_from_session": 5})
    check("cloud: no switch books the add; from_session 5 at session 2 books none",
          sum(q0) > 0 and q5 == [0] and usd5 == round(6 * (30.0 * 2.0 - float(t.get("comm_rt", sizing.LIVE_COMM))), 2), (q0, q5, usd5))
    usdf, qf = CM.lit_add_usd({}, t, 6, {"mode": "funded", "scale_in_funded": False})
    check("cloud: funded switch books no add", qf == [0], qf)
    src = open(os.path.join(ROOT, "live_model.json"), encoding="utf-8").read()
    check("the switches are OFF in live_model.json (owner decides)", "scale_in_from_session" not in src and "scale_in_funded" not in src)
    print(f"\nscale-in switches: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
