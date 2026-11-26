"""day-alloc 2026-11-26 cards (research/writeups/alloc-2026-11-26.md): both OFF by default.

    python -X utf8 -m tests.test_alloc_cards      (~3 s; the LiveBot Sim replay of card 2 is tests/test_lit25_replay.py)

 card 3  research/lab/combo_50k.json guards.atlas_from_et ("09:30"): no ATLAS entry before that ET time on the combo lanes
         (Zlarior 50K + the 25K #2, eval and funded); absent / null = today exactly; a bad value = the rules are not usable
 card 2  engine/lit25 --on (LIT also on ATLAS's funded 25K): refused without the typed live phrase or with a failing NT self-test;
         the file never holds the phrase; --off needs no phrase
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.disable(logging.WARNING)
from engine import combo50k as CB  # noqa: E402
from engine import lit25  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=None):
    RES.append((name, bool(ok)))
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + ("" if ok or info is None else f"  {str(info)[:300]}"))


def ts(h, m, day=(2026, 9, 2)):
    return int(dt.datetime(*day, h, m, tzinfo=ET).timestamp())


def main() -> int:
    # ---- card 3
    live_rules = CB.load_rules()
    check("card 3: the research rules file has no atlas_from_et -> None (today)", live_rules["guards"].get("atlas_from_et") is None
          and not live_rules.get("problem"), live_rules["guards"])
    g = CB.normalize({"guards": {"atlas_from_et": "9:30 ET"}})
    check("card 3: '9:30 ET' -> '09:30', rules usable", g["guards"]["atlas_from_et"] == "09:30" and g["problem"] is None, g)
    check("card 3: null = off; a bad time / after 15:50 = rules not usable",
          CB.normalize({"guards": {"atlas_from_et": None}})["guards"]["atlas_from_et"] is None
          and CB.normalize({"guards": {"atlas_from_et": "x"}})["problem"] and CB.normalize({"guards": {"atlas_from_et": "16:00"}})["problem"])
    base = {"on": True, "account": "Sim101", "atlas_size_factor": {"eval": 1.0, "funded": 1.0}, "guards": dict(CB.GUARD_DEFAULTS),
            "max_micros": 40}
    on = {**base, "guards": {**base["guards"], "atlas_from_et": "09:30"}}
    sp25 = {**base, "plan": "builder25k"}
    on25 = {**on, "plan": "builder25k"}
    st = {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 3, "n_today": 0, "wk_pnl": 0.0, "days_traded": 1}
    bad, n = [], 0
    for b_, o_ in ((base, on), (sp25, on25)):
        for stage in ("eval", "funded"):
            for h, m in ((2, 30), (3, 55), (9, 25), (9, 30), (10, 15), (14, 45)):
                for rp in (6.0, 14.0, 33.0):
                    tr = {"risk_pts": rp, "tgt_pts": 6 * rp, "entry_t": ts(h, m)}
                    q0 = CB.atlas_qty(b_, tr, dict(st), "2026-08-03", stage=stage)
                    q1 = CB.atlas_qty(o_, tr, dict(st), "2026-08-03", stage=stage)
                    n += 1
                    before = h * 60 + m < 9 * 60 + 30
                    if before and (q1["qty"] != 0 or "atlas_from_et" not in " ".join(q1["reasons"])):
                        bad.append(("before", stage, h, m, q1))
                    if not before and q1 != q0:
                        bad.append(("after", stage, h, m, q0, q1))
    check(f"card 3: before 09:30 ET -> 0 micros with the reason; from 09:30 = today's size exactly (50K + 25K, eval + funded, {n} cases)",
          not bad, bad[:3])
    q = CB.atlas_qty(on, {"risk_pts": 10.0, "tgt_pts": 60.0}, dict(st), "2026-08-03")
    check("card 3: guard on + entry time unknown -> fails closed (0)", q["qty"] == 0, q)
    q0 = CB.atlas_qty(base, {"risk_pts": 10.0, "tgt_pts": 60.0}, dict(st), "2026-08-03")
    check("card 3: guard off + no entry time = today (unchanged)", q0["qty"] > 0, q0)
    # ---- card 2
    with tempfile.TemporaryDirectory() as d:
        fp = os.path.join(d, "lit25.json")
        r0 = lit25.set_on("yes", fp, selftest=lambda: (True, "ok"))
        check("card 2: --on without the phrase: refused, nothing written", not r0["ok"] and not os.path.exists(fp), r0)
        r1 = lit25.set_on("I ACCEPT LIVE RISK", fp, selftest=lambda: (False, "no NinjaTrader"))
        check("card 2: a failing NT self-test: refused, nothing written", not r1["ok"] and not os.path.exists(fp), r1)
        r2 = lit25.set_on("I ACCEPT LIVE RISK", fp, selftest=lambda: (True, "ok"))
        txt = open(fp, encoding="utf-8").read()
        check("card 2: phrase + self-test OK: ON, the file holds only {on: true} (never the phrase)",
              r2["ok"] and lit25.is_on(fp) and "ACCEPT" not in txt and json.loads(txt).get("on") is True, (r2, txt))
        lit25.save(False, fp)
        check("card 2: --off needs no phrase", lit25.is_on(fp) is False)
        old = lit25.PATH
        lit25.PATH = fp
        try:
            import builtins
            real = builtins.input
            builtins.input = lambda *_: (_ for _ in ()).throw(EOFError())
            try:
                rc = lit25.main(["--on"])
            finally:
                builtins.input = real
        finally:
            lit25.PATH = old
        check("card 2: CLI --on with no answer (EOF): exit 1, still OFF", rc == 1 and lit25.is_on(fp) is False)
    fails = [n_ for n_, ok in RES if not ok]
    print(f"\n{len(RES) - len(fails)}/{len(RES)} OK" + (f"  FAIL: {fails}" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
