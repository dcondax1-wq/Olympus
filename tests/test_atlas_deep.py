"""ATLAS zombie-eval rule (2026-11-15, research/writeups/2026-11-15-atlas-deep.md): account_b "eval_min_room" and
"last_bullet", BUILT BUT OFF.

 a. without the keys: normalize() adds no key, min_room() = $100 (or "min_room"), qty() is today's
 b. "eval_min_room" 200: the eval's stuck line is $200, a FUNDED spec keeps min_room / $100; bad values are refused
 c. "last_bullet" 0.8: need size 0 on a low room -> 1 micro when the full stop-out fits 80% of the room, never more than
    1, the soft daily loss still applies; a bad value is refused
 d. parity: the 2026 H1 + H2 ATLAS eval path sized through engine/account_b.qty with the keys = tools/atlas_deep.py's
    research sizer (identical trades and micros); without the keys = today's path
 e. second_model.json "account_b" still null (nothing switched on)

    python -X utf8 -m tests.test_atlas_deep
Paper research only.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import account_b as AB  # noqa: E402

RESULTS = []
BLK = {"account": "Sim102", "plan": "builder25k", "eval_start": "2026-10-26",
       "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"], "sizing": "need"}
KEY_OF = {"EMA": "ema_lon_vix", "MD": "macd_sweep", "SR": "sr_nyreclaim"}


def check(name, ok, detail=None):
    RESULTS.append((name, bool(ok)))
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok or detail is None else f"   {detail!r}"[:400]), flush=True)


def part_a():
    s0 = AB.normalize(BLK)
    check("a. normalize() without the keys: no eval_min_room / last_bullet key, no problem, min_room $100",
          s0["problem"] is None and "eval_min_room" not in s0 and "last_bullet" not in s0 and AB.min_room(s0) == 100.0)
    s1 = AB.normalize({**BLK, "min_room": 150})
    check("a. min_room alone keeps its meaning (eval and funded): $150", AB.min_room(s1) == 150.0)
    st = {"profit": -400.0, "cum": 0.0, "room": 180.0, "session": 12, "n_today": 0}
    q = AB.qty(s0, {"risk_pts": 40.0, "tgt_pts": 120.0}, st)
    check(f"a. today on a $180 room: 1 micro of a 40-pt stop does not fit 50% of the room -> 0 ({q['qty']})", q["qty"] == 0, q)


def part_b():
    s = AB.normalize({**BLK, "eval_min_room": 200})
    check("b. eval_min_room 200 -> the eval's stuck line is $200", s["problem"] is None and AB.min_room(s) == 200.0)
    f = {**s, "stage": "funded", "funded": {"start": "2026-11-20"}}
    check("b. the same spec FUNDED -> stuck line back to $100 (the funded stage never uses eval_min_room)", AB.min_room(f) == 100.0)
    f2 = {**f, "min_room": 150.0}
    check("b. funded + min_room 150 -> $150", AB.min_room(f2) == 150.0)
    bad = [AB.normalize({**BLK, "eval_min_room": "x"})["problem"], AB.normalize({**BLK, "eval_min_room": 5000})["problem"]]
    check("b. a bad eval_min_room is refused (a problem = not traded)", all(bad), bad)


def part_c():
    s = AB.normalize({**BLK, "last_bullet": 0.8})
    check("c. last_bullet 0.8 accepted", s["problem"] is None and s["last_bullet"] == 0.8)
    st = {"profit": -400.0, "cum": 0.0, "room": 180.0, "session": 12, "n_today": 0}
    q = AB.qty(s, {"risk_pts": 40.0, "tgt_pts": 120.0}, st)
    # 1 micro: (40 + 0.5) x $2 + $1.90 = $82.90 <= 0.8 x $180 = $144
    check(f"c. $180 room, 40-pt stop: 1 micro (its $82.90 stop-out fits 80% of the room) ({q['qty']})", q["qty"] == 1, q)
    q2 = AB.qty(s, {"risk_pts": 75.0, "tgt_pts": 150.0}, st)
    check(f"c. $180 room, 75-pt stop: $152.90 > $144 -> still 0 ({q2['qty']})", q2["qty"] == 0, q2)
    st3 = {**st, "cum": -560.0}
    q3 = AB.qty(s, {"risk_pts": 40.0, "tgt_pts": 120.0}, st3)
    check(f"c. $40 left of the $600 soft daily loss -> the day guard still says 0 ({q3['qty']})", q3["qty"] == 0, q3)
    stf = {"profit": 0.0, "cum": 0.0, "room": 1000.0, "session": 1, "n_today": 0}
    a, b = AB.qty(AB.normalize(BLK), {"risk_pts": 30.0, "tgt_pts": 90.0}, stf), AB.qty(s, {"risk_pts": 30.0, "tgt_pts": 90.0}, stf)
    check(f"c. a normal room: last_bullet changes nothing ({a['qty']} = {b['qty']})", a == b, (a, b))
    bad = [AB.normalize({**BLK, "last_bullet": 0})["problem"], AB.normalize({**BLK, "last_bullet": 1.5})["problem"],
           AB.normalize({**BLK, "last_bullet": "x"})["problem"]]
    check("c. a bad last_bullet is refused", all(bad), bad)


def part_d():
    from tools import atlas as A
    from tools import atlas_deep as D
    from tools import second_account_b as SAB
    from tools import atlas_v2 as V2
    V2.install()
    D._patch()
    U = A.account_units(A.BASE)
    key = lambda x: (x["src"], x["entry_t"], x["qty"], round(x["pnl"], 2))

    def path(fn, V):
        keep = A.q_variant
        A.q_variant = fn
        try:
            with A.Plan(V) as pl:
                return {s: SAB.score(U, "atlas", s, pl.safe_rule)[1] for s in ("H1", "H2")}
        finally:
            A.q_variant = keep
    for blk, deep in (({}, {}), ({"last_bullet": 0.8}, {"last_bullet": 0.8})):
        sp = AB.normalize({**BLK, **blk})
        sp = {**sp, "rules": A.spec()["rules"]}
        V = D.V_of(deep)
        ref = path(A.q_variant, V)
        eng = path(lambda t, st, V_: AB.qty(sp, {"risk_pts": t["risk"], "tgt_pts": t["tgt"]}, dict(st), key=KEY_OF.get(t["src"]))["qty"], V)
        n = sum(len(v) for v in ref.values())
        same = all([key(x) for x in ref[s]] == [key(x) for x in eng[s]] for s in ref)
        check(f"d. 2026 H1 + H2 ATLAS eval path, engine qty {blk or '(no keys)'} = research sizer ({n} trades identical)",
              same and n > 50, n)


def part_e():
    c = json.load(open(os.path.join(ROOT, "second_model.json"), encoding="utf-8"))
    check("e. second_model.json account_b still null (nothing switched on)", c.get("account_b") is None)


def main():
    for p in (part_a, part_b, part_c, part_d, part_e):
        p()
    n = sum(1 for _, ok in RESULTS if ok)
    print(f"atlas deep (zombie-eval rule): {n}/{len(RESULTS)} checks passed")
    sys.exit(0 if n == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
