"""MFFU Builder Sim Funded tracker (engine/funded_life.py), the funded switch (engine/eval_life --to-funded, 50K and 25K),
the funded sizing math vs research/writeups/lit-funded-sizing.md, the consistency-aware cap (engine/sizing.funded_qty
"cons_aware", OFF by default), and the bot's funded pushes (LiveBot._funded_life_tick, read-only).

    python -X utf8 -m tests.test_funded_life

Paper only: temp files, made-up account names; nothing is armed, no payout is ever requested by the code.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import eval_life as EL, funded_life as FL, multi_account as MA, sizing as sz  # noqa: E402

from tests.sizing_pins import OLD_FUNDED, OLD_FUNDED_25K  # noqa: E402

RESULTS = []
# the sizing math is checked on the write-up rule it was written for (lit-funded-sizing.md: 40% of the room, <= $800 /
# $400, a winner <= $1,500 / $750); the presets carry the owner's 2026-10-25 rule (uprisk.md: 60%, <= $1,500 / $750, a
# winner <= $2,000 / $1,000), checked in new_rule_checks()
REC50 = OLD_FUNDED
REC25 = OLD_FUNDED_25K
NEW50 = MA.PRESETS["mffu_builder_50k"]["sizing"]["funded"]
NEW25 = MA.PRESETS["mffu_builder_25k"]["sizing"]["funded"]


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


# ------------------------------------------------------------------------------------------------ the tracker
def tracker_checks():
    t = FL.track({}, {}, "builder50k", today="2026-11-03", name="F")
    check("fresh 50K: balance $50,000, floor $48,000, room $2,000, payout line $53,600, payouts 0/5, building",
          t["balance"] == 50000 and t["floor"] == 48000 and t["room"] == 2000 and t["ask_at_balance"] == 53600
          and t["payouts_n"] == 0 and t["payouts_max"] == 5 and t["status"] == "building" and not t["eligible"], t)
    d = {"2026-11-03": 900.0}
    t = FL.track(d, {}, "builder50k", today="2026-11-04")
    check("48 h after the first trade: first request from 2026-11-05 (first trade 11-03)",
          t["first_trade"] == "2026-11-03" and t["eligible_from"] == "2026-11-05" and any("48 h" in w for w in t["why"]), t["why"])
    t = FL.track({"2026-11-06": 900.0}, {}, "builder50k", today="2026-11-06")
    check("first trade on a Friday: eligible from the next Monday", t["eligible_from"] == "2026-11-09", t["eligible_from"])
    # one big day: consistency blocks the payout
    d = {"2026-11-03": 3000.0, "2026-11-04": 400.0, "2026-11-05": 300.0}
    t = FL.track(d, {}, "builder50k", today="2026-11-05")
    check("best day $3,000 of a $3,700 cycle = 81%: consistency block, ~$2,300 more profit on other days, M more days > 0",
          t["status"] == "consistency" and abs(t["best_day_pct"] - 81.1) < 0.1 and t["cons_need_profit"] == 2300.0
          and t["more_days"] >= 1 and not t["eligible"] and "trade" in t["text"], t)
    n = FL.notices({**t, "id": "x"}, 1_800_000_000)
    check("consistency push: 'consistency: best day is 81% of the cycle, trade M more days', stable key",
          len(n) == 1 and n[0]["title"].startswith("consistency: best day is 81% of the cycle, trade ")
          and n[0]["title"].endswith("more days") and n[0]["key"] == FL.notices(t, 1_800_000_999)[0]["key"], n)
    # eligible by MFFU but below the owner's $1,500-above-buffer habit
    d = {"2026-11-03": 700.0, "2026-11-04": 600.0, "2026-11-05": 800.0, "2026-11-06": 700.0}
    t = FL.track(d, {}, "builder50k", today="2026-11-06")
    check("$2,800: $700 above the buffer: MFFU would pay $700 (eligible), the owner's rule waits for $53,600 (not ready, no push)",
          t["eligible"] and not t["ready"] and t["max_request"] == 700 and t["status"] == "eligible" and not FL.notices(t, 1), t)
    d = {"2026-11-03": 900.0, "2026-11-04": -300.0, "2026-11-05": 1500.0, "2026-11-06": 700.0, "2026-11-09": 1600.0}
    t = FL.track(d, {}, "builder50k", today="2026-11-09", name="F50")
    n = FL.notices({**t, "id": "mffu50k_funded"}, 1_800_000_000)
    check("$4,400 over 5 days, best 36%: PAYOUT READY, max request $2,000 ($1,600 to you)",
          t["status"] == "ready" and t["max_request"] == 2000 and t["to_you"] == 1600 and t["cons_ok"], t)
    check("ready push: 'PAYOUT READY: request $2,000' + the record command; the code never requests it",
          len(n) == 1 and n[0]["title"] == "PAYOUT READY: request $2,000" and "--payout 2026-11-09=2000" in n[0]["body"]
          and "never requests" in n[0]["body"], n)
    # after the payout: the MLL sits at start + $100, the cycle resets
    t2 = FL.track(d, {"2026-11-09": 2000.0}, "builder50k", today="2026-11-10")
    check("after the 1st payout: balance $52,400, floor $50,100 (MLL at start + $100), cycle reset, payouts 1/5",
          t2["balance"] == 52400 and t2["floor"] == 50100 and t2["room"] == 2300 and t2["cycle_profit"] == 0
          and t2["payouts_n"] == 1 and t2["cycle_start"] == "2026-11-10" and t2["paid_to_you"] == 1600, t2)
    # 25K numbers
    t = FL.track({}, {}, "builder25k", today="2026-11-03")
    check("fresh 25K: floor $24,000, buffer $26,100, payout line $26,850, request $250-$1,000",
          t["floor"] == 24000 and t["buffer_balance"] == 26100 and t["ask_at_balance"] == 26850 and t["request_min"] == 250
          and t["request_max"] == 1000, t)
    d = {"2026-11-03": 600.0, "2026-11-04": 500.0, "2026-11-05": 400.0, "2026-11-06": 500.0}
    t = FL.track(d, {}, "builder25k", today="2026-11-06")
    check("25K +$2,000 over 4 days: ready, request $900 (balance - $1,100 buffer, < $1,000 max)",
          t["status"] == "ready" and t["max_request"] == 900, t)
    # lost / graduated
    t = FL.track({"2026-11-03": -2000.0}, {}, "builder50k", today="2026-11-03")
    check("room 0: lost + 'FUNDED ACCOUNT LOST' push", t["status"] == "lost" and FL.notices(t, 1)[0]["title"] == "FUNDED ACCOUNT LOST", t)
    pays = {f"2026-12-0{i}": 2000.0 for i in range(1, 6)}
    days = {f"2026-12-0{i}": 2500.0 for i in range(1, 6)}
    t = FL.track(days, pays, "builder50k", today="2026-12-07")
    check("5 sim payouts: graduated (MFFU moves to live), $8,000 to you", t["status"] == "graduated" and t["paid_to_you"] == 8000, t)
    # agrees with the older eval_life.payout_check on a real-shaped path
    d = {"2026-11-03": 900.0, "2026-11-04": -300.0, "2026-11-05": 1500.0, "2026-11-06": 700.0, "2026-11-09": 1600.0}
    pc = EL.payout_check(d, {})
    t = FL.track(d, {}, "builder50k", today="2026-11-09")
    check("tracker == eval_life.payout_check (ok, amount, cycle profit, best day)",
          pc["ok"] == t["ready"] and pc["amount"] == t["max_request"] and pc["cycle_profit"] == t["cycle_profit"]
          and pc["best_day"] == t["best_day"], (pc, t["max_request"]))


# ------------------------------------------------------------------------------------------------ the sizing math
def sizing_checks():
    f0 = sz.funded_state({})
    tr = {"risk_pts": 40.0, "tgt_pts": 60.0}
    check("write-up rule: fresh room $2,000 x 40% = $800, 40-pt stop -> $400 -> 5 micros",
          sz.funded_qty(tr, f0, REC50) == 5)
    check("write-up rule: a winner <= $1,500: 200-pt target -> 3 micros (1500 / 398.1)",
          sz.funded_qty({"risk_pts": 40.0, "tgt_pts": 200.0}, f0, REC50) == 3)
    s1 = sz.funded_state({"d1": -1500.0})
    check("write-up rule: room $500 -> $200 -> 1 micro (size shrinks with the room)", sz.funded_qty(tr, s1, REC50) == 1)
    check("write-up rule: room $100, 60-pt stop: 1 micro could reach the floor -> skip (0)",
          sz.funded_qty({"risk_pts": 60.0, "tgt_pts": 120.0}, {"room": 100.0, "cum": 0.0, "locked": True}, REC50) == 0)
    check("write-up rule: the soft daily loss: day -$900, 40-pt stop -> 1 micro", sz.funded_qty(tr, {**f0, "cum": -900.0, "room": 2000.0}, REC50) == 1)
    check("25K rule: fresh room $1,000 x 40% = $400, 40-pt stop -> 2 micros",
          sz.funded_qty(tr, sz.funded_state({}, plan={"mll": 1000.0, "lock": 100.0}), REC25,
                        acct={"mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20}) == 2)
    # cons_aware absent / False = the research rule, bit for bit, over a grid
    same = True
    cyc = {"cycle_target": 2000.0, "cycle_prev": 300.0, "best_prev": 300.0, "payouts_n": 1}
    for risk in (8.0, 15.0, 25.0, 40.0, 70.0):
        for tgt in (40.0, 120.0, 250.0, 400.0):
            for room in (150.0, 600.0, 2000.0, 3500.0):
                st = {"room": room, "cum": 0.0, "locked": room > 2000, **cyc}
                a = sz.funded_qty({"risk_pts": risk, "tgt_pts": tgt}, st, REC50)
                b = sz.funded_qty({"risk_pts": risk, "tgt_pts": tgt}, st, {**REC50, "cons_aware": False})
                c = sz.funded_qty({"risk_pts": risk, "tgt_pts": tgt}, {"room": room, "cum": 0.0, "locked": room > 2000}, {**REC50, "cons_aware": True})
                same = same and a == b == c
    check("cons_aware off (absent / False, or no cycle state) = the research rule on 80 trades x rooms", same)
    # cons_aware on: the 2nd cycle (target $2,000): today's day <= max($1,000, earlier cycle profit)
    st = {"room": 3000.0, "cum": 0.0, "locked": True, "cycle_target": 2000.0, "cycle_prev": 0.0, "payouts_n": 1}
    why = []
    q = sz.funded_qty({"risk_pts": 10.0, "tgt_pts": 100.0}, st, {**REC50, "cons_aware": True}, why=why)
    q0 = sz.funded_qty({"risk_pts": 10.0, "tgt_pts": 100.0}, st, REC50)
    check("cons_aware: 2nd cycle, 100-pt target: a winner <= $1,000 -> 5 micros (research rule 7)", q == 5 and q0 == 7
          and any("consistency" in w for w in why), (q, q0, why))
    q = sz.funded_qty({"risk_pts": 10.0, "tgt_pts": 100.0}, {**st, "cycle_prev": 1800.0}, {**REC50, "cons_aware": True})
    check("cons_aware: $1,800 already in the cycle -> today may pay $1,800: back to the research size 7", q == 7, q)
    q = sz.funded_qty({"risk_pts": 10.0, "tgt_pts": 600.0}, {**st, "cum": 990.0}, {**REC50, "cons_aware": True})
    check("cons_aware is soft: at the cap it sizes down to 1 micro, never skips", q == 1, q)
    q = sz.funded_qty({"risk_pts": 10.0, "tgt_pts": 100.0}, {**st, "payouts_n": 0, "cycle_target": 2000.0},
                      {**REC50, "cons_aware": "after_payout"})
    check("cons_aware 'after_payout': the 1st cycle keeps the research size", q == 7, q)
    c = sz.funded_cycle({"a": 2500.0, "b": 2000.0, "c": 500.0, "d": -200.0}, 0.0, {"b": 2000.0})
    check("funded_cycle: after a $2,000 payout on b: cycle start $2,500, cycle $300 over 2 days, best $500, target $1,600",
          c == {"cycle_start_bal": 2500.0, "cycle_prev": 300.0, "best_prev": 500.0, "cycle_days_prev": 2, "payouts_n": 1,
                "cycle_target": 1600.0}, c)
    st = MA.sizing_state("funded", [("2026-11-03", 1, 900.0), ("2026-11-04", 2, 400.0)], "2026-11-05", "2026-11-03",
                         MA.rules_of({"preset": "mffu_builder_25k"}))
    base = sz.funded_state({"2026-11-03": 900.0, "2026-11-04": 400.0}, 0.0, {}, plan=MA._plan(MA.rules_of({"preset": "mffu_builder_25k"}), True))
    check("multi_account funded state: funded_state keys unchanged + the 25K cycle (target $1,100 + $1,000)",
          all(st[k] == v for k, v in base.items()) and st["cycle_target"] == 2100.0 and st["cycle_prev"] == 1300.0, st)
    # the defaults stay the research rule
    check("presets: funded cfg has no cons_aware (OFF: research/writeups/funded-path.md)",
          "cons_aware" not in NEW50 and "cons_aware" not in NEW25 and sz.FD_DEFAULT["cons_aware"] is False)


def new_rule_checks():
    """The owner's funded rule (2026-10-25, research/writeups/uprisk.md) on the presets: 60% of the room, <= $1,500 (50K) /
    $750 (25K), a winner <= $2,000 / $1,000; every full stop-out (stop + 2 ticks, $1.90) inside the room (strict), the soft
    daily loss and the $ cap; skip when 1 micro could reach the floor."""
    f0 = sz.funded_state({})
    tr = {"risk_pts": 40.0, "tgt_pts": 60.0}
    check("uprisk 50K: fresh room $2,000 x 60% = $1,200, 40-pt stop -> $600 -> 7 micros", sz.funded_qty(tr, f0, NEW50) == 7)
    check("uprisk 50K: a winner <= $2,000: 200-pt target -> 5 micros (2000 / 398.1)",
          sz.funded_qty({"risk_pts": 40.0, "tgt_pts": 200.0}, f0, NEW50) == 5)
    check("uprisk 50K: room $100, 60-pt stop: 1 micro could reach the floor -> skip (0)",
          sz.funded_qty({"risk_pts": 60.0, "tgt_pts": 120.0}, {"room": 100.0, "cum": 0.0, "locked": True}, NEW50) == 0)
    A25 = {"mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20}
    check("uprisk 25K: fresh room $1,000 x 60% = $600, 40-pt stop -> 3 micros",
          sz.funded_qty(tr, sz.funded_state({}, plan={"mll": 1000.0, "lock": 100.0}), NEW25, acct=A25) == 3)
    bad = []
    for cfg, acct, cap_usd, dll, mx in ((NEW50, None, 1500.0, 1000.0, 40), (NEW25, A25, 750.0, 600.0, 20)):
        for risk in (4.0, 8.0, 15.0, 20.0, 25.0, 40.0, 70.0, 120.0, 250.0):
            for tgt in (30.0, 80.0, 200.0, 500.0):
                for room in (50.0, 150.0, 400.0, 900.0, 2000.0, 3500.0, 6000.0):
                    for cum in (0.0, -300.0, -dll + 80.0, 500.0):
                        q = sz.funded_qty({"risk_pts": risk, "tgt_pts": tgt}, {"room": room, "cum": cum, "locked": room > 2000},
                                          cfg, acct=acct)
                        if not q:
                            continue
                        l = q * ((risk + 0.5) * 2.0 + 1.90)
                        win = q * (tgt * 2.0 - 1.90)
                        if not (l <= cap_usd and l < room and l <= dll + cum + 1e-6 and q <= mx
                                and (q == 1 or win <= cfg["max_win"] + 1e-6)):
                            bad.append((cap_usd, risk, tgt, room, cum, q, round(l), round(win)))
    check("uprisk sweep (50K + 25K presets, 2,016 states): a full stop-out never past the $1,500 / $750 cap, the room "
          "(never reaches the floor), the soft daily loss; a 2+ micro winner <= $2,000 / $1,000", not bad, bad[:4])


# ------------------------------------------------------------------------------------------------ the switch + the bot
def switch_checks(tmp):
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    check("default: live_model.json lit_sizing is an eval mode (passed eval -> stop + push), no funded account configured",
          (lm.get("lit_sizing") or {}).get("mode") in EL.EVAL_MODES and not any((a or {}).get("mode") == "funded"
                                                                              for a in lm.get("accounts") or []))
    p = os.path.join(tmp, "acc.json")
    rc = EL.main(["--to-funded", "--account", "FUNDFAKE50", "--start", "2026-11-03", "--file", p])
    rc2 = EL.main(["--to-funded", "--account", "FUNDFAKE25", "--start", "2026-11-04", "--plan", "builder25k", "--file", p])
    rows = {r["id"]: MA.normalize(r) for r in MA.load_file(p)}
    a, b = rows.get("mffu50k_funded"), rows.get("mffu25k_funded")
    check("--to-funded (50K) and --to-funded --plan builder25k: two disarmed mode-funded entries with their presets",
          rc == 0 and rc2 == 0 and a and b and a["mode"] == b["mode"] == "funded" and a["preset"] == "mffu_builder_50k"
          and b["preset"] == "mffu_builder_25k" and not a["armed"] and not b["armed"] and b["funded"]["start"] == "2026-11-04", rows)
    check("unknown plan refused", EL.to_funded("X", "2026-11-03", path=p, plan="builder100k") == 1)
    rc3 = EL.main(["--payout", "2026-11-20=900", "--id", "mffu25k_funded", "--file", p])
    check("--payout on the 25K by id", rc3 == 0 and MA.load_file(p)[1]["funded"]["payouts"] == {"2026-11-20": 900.0})
    # the bot: a paper funded account, closes injected, the tick pushes PAYOUT READY once
    from engine.ninjatrader import _FakeNT
    from tests.test_multi_account import Clock, make_bot, ts
    fake = _FakeNT(os.path.join(tmp, "nt"))
    clock = Clock(ts(2026, 11, 9, 16, 30))
    pp = os.path.join(tmp, "acc_paper.json")
    EL.to_funded("", "2026-11-03", path=pp, adapter="paper")
    b = make_bot(os.path.join(tmp, "bot"), fake, clock, MA.load_file(pp), extra_cfg={"eval_start": "2026-10-19"})
    acc = b.accts.accounts[0]
    for i, (d, v) in enumerate({"2026-11-03": 900.0, "2026-11-04": -300.0, "2026-11-05": 1500.0, "2026-11-06": 700.0,
                                "2026-11-09": 1600.0}.items()):
        acc.closes.append((d, 1_790_000_000 + i, v))
    sent = []
    b._push_send = sent.append
    seen = set()
    b._funded_life_tick(seen)
    b._funded_life_tick(seen)
    fl = getattr(b, "funded_life", None) or []
    check("bot: funded tracker in the state, ONE 'PAYOUT READY: request $2,000' push over two polls",
          len(fl) == 1 and fl[0]["status"] == "ready" and len(sent) == 1 and sent[0]["title"] == "PAYOUT READY: request $2,000", (fl, sent))
    check("bot: the tracker changes nothing it trades (sizing state = funded_state, payouts untouched)",
          not (acc.spec.get("funded") or {}).get("payouts"))
    # data.json block
    blk = FL.block([{"id": "f", "name": "F", "kind": "funded", "funded": {"start": "2026-11-03", "preset": "mffu_builder_25k"},
                     "plan_rules": {"start": 25000.0}, "days": [["2026-11-03", 600.0], ["2026-11-04", 500.0]]},
                    {"id": "e", "kind": "eval"}], today="2026-11-05")
    check("data.json funded block: only funded accounts, 25K plan from the preset, default line says stop + tell",
          blk["n"] == 1 and blk["accounts"][0]["plan"] == "builder25k" and "stops trading" in blk["default"], blk)
    from engine import goals as G
    g = G.payout_goal({"accounts": [{"id": "f", "name": "F", "kind": "funded", "eval": {"balance": 51100.0},
                                     "funded": {"start": "2026-11-03"}, "days": [["2026-11-03", 1100.0]]}]}, {})
    check("goals.payout_goal: tracker fields (buffer progress, cycle, best day %, payouts n/5, status)",
          g["stage"] == "funded" and g.get("tracker", {}).get("payouts_max") == 5 and "frac" in g and g.get("status"), g)


def main():
    tmp = tempfile.mkdtemp(prefix="le_funded_")
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    try:
        tracker_checks()
        sizing_checks()
        new_rule_checks()
        switch_checks(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RESULTS), sum(RESULTS)
    print(f"funded life: {ok}/{n} {'ALL PASS' if ok == n else 'FAILURES'}")
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    main()
