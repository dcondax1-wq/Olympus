"""ATLAS's FIRST PAYOUT AT MFFU'S MINIMUM (night-payfirst 2026-11-23, owner: "take it sooner, one payout small so we can immediately
buy more accounts").

    python -X utf8 -m tests.test_payfirst

a. engine/funded_life.track with first_at_min (ATLAS's plan, engine/account_b.atlas_plan): the FIRST payout is ready on the first day MFFU
   allows one ($1,350 profit = $250 above the $1,100 buffer, 2 traded days, 48 h after the first trade, best day <= 50%) for what MFFU
   allows that day; a best day over 50% still blocks it; from the 2nd payout on the normal plan ($1,000 at $2,100); other 25Ks unchanged
b. engine/payout_autopilot: ONE push "REQUEST PAYOUT TODAY: ATLAS 25K $250" ($200 reaches you) after the close
c. the morning brief line, the phone card (business/payoutcoach.js, node) and engine/payout_coach say the same; the PC post's tracker
   carries fm=1 (engine/mffu_view) and the board card first_at_min (engine/live_board), so the phone knows
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import account_b as AB  # noqa: E402
from engine import funded_life as FL  # noqa: E402
from engine import payout_autopilot as PA  # noqa: E402
from engine import payout_coach as PC  # noqa: E402

ET = ZoneInfo("America/New_York")
RES: list = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:500]}]" if not ok else ""))


AFTER = dt.datetime(2026, 11, 24, 16, 20, tzinfo=ET).timestamp()          # Tuesday after the close
# ATLAS's real start (MFFU's $0 view): Nov 17 first funded trade, -$113 Nov 18, +$514 ... then two more days to $1,350
FIRST = {"2026-11-17": -113.0, "2026-11-18": 514.0, "2026-11-23": 500.0, "2026-11-24": 449.0}      # $1,350, best 38%
HOGGY = {"2026-11-17": -113.0, "2026-11-18": 900.0, "2026-11-24": 563.0}                            # $1,350, best 67%


def atlas(days, pays=None, today="2026-11-24"):
    return FL.track(days, pays or {}, AB.atlas_plan("builder25k"), today=today, start="2026-11-17", name="ATLAS 25K")


def part_a():
    P = AB.atlas_plan("builder25k")
    check("a. ATLAS's plan: the 25K plan + first_at_min (owner 2026-11-23); the module flag is on", P.get("first_at_min") is True
          and AB.ATLAS_FIRST_AT_MIN is True and P["pay_min"] == 250 and P["buffer"] == 1100 and P["ask_above"] == 1000)
    t = atlas(FIRST)
    check("a. $1,350 profit, 4 traded days, best $514 = 38%, 48 h done: READY for $250 ($200 to you), first_at_min",
          t["ready"] and t["eligible"] and t["max_request"] == 250 and t["to_you"] == 200 and t["first_at_min"] is True
          and t["status"] == "ready", t)
    t0 = atlas({k: v for k, v in FIRST.items() if k != "2026-11-24"}, today="2026-11-23")
    check("a. the day before ($901): not ready; 'to payout' = $449 to the $1,350 line ($250 at $1,350), not $1,199 to $2,100",
          not t0["ready"] and t0["to_ask"] == 449 and t0["ask_goal"] == 1350 and t0["ask_amount"] == 250, t0)
    t1 = atlas({**FIRST, "2026-11-24": 649.0})
    check("a. a bigger first eligible day ($1,550): asks what MFFU allows that day ($450 = $360 to you), never above $1,000",
          t1["ready"] and t1["max_request"] == 450 and t1["to_you"] == 360, t1)
    h = atlas(HOGGY)
    check("a. the 50% rule still blocks it: $1,350 with a $900 best day (67%) = not eligible, not ready, the why says it",
          not h["ready"] and not h["eligible"] and not h["cons_ok"] and any("best day" in w for w in h["why"]), h)
    w = atlas({"2026-11-23": 900.0, "2026-11-24": 800.0}, today="2026-11-24")
    check("a. the 48 h wait still holds: first funded trade Nov 23 -> not before Nov 25", not w["ready"] and w["eligible_from"] == "2026-11-25", w)
    after = atlas({**FIRST, "2026-11-25": 300.0, "2026-11-30": 250.0}, {"2026-11-24": 250.0}, today="2026-11-30")
    check("a. after the first payout: back to the normal plan (MFFU would pay, the plan waits for $1,000 at $2,100), first_at_min off",
          after["payouts_n"] == 1 and not after["ready"] and after["first_at_min"] is False and after["ask_amount"] == 1000
          and after["ask_goal"] == 2100, after)
    n = FL.track(FIRST, {}, "builder25k", today="2026-11-24", start="2026-11-17")
    check("a. any other Builder 25K (Zlarior's 25K #2 once funded) keeps the normal plan: $1,350 is eligible, not ready",
          n["eligible"] and not n["ready"] and n["first_at_min"] is False and n["ask_goal"] == 2100, n)
    c = AB.compact_tracker(t)
    check("a. the heartbeat's compact tracker keeps first_at_min (the cards and the phone read it)", c.get("first_at_min") is True, c)


def part_b():
    v = PA.builder(atlas(FIRST), "atlas", "ATLAS 25K")
    a = PA.alerts([v], AFTER)
    check("b. ONE push after the close: 'REQUEST PAYOUT TODAY: ATLAS 25K $250', '$200 reaches you', payout 1 of 4, the MFFU clicks",
          len(a) == 1 and a[0]["title"] == "REQUEST PAYOUT TODAY: ATLAS 25K $250" and "$200 reaches you" in a[0]["body"]
          and "Payout 1 of 4" in a[0]["body"] and "left menu Payouts" in a[0]["body"], a)
    check("b. de-duplicated: the same cycle never twice", not PA.alerts([v], AFTER + 900, {a[0]["key"]: 1}))
    check("b. the 50% case: no push", not PA.alerts([PA.builder(atlas(HOGGY), "atlas", "ATLAS 25K")], AFTER))
    check("b. before the close: no push yet", not PA.alerts([v], dt.datetime(2026, 11, 24, 15, 0, tzinfo=ET).timestamp()))


def part_c():
    from tools import morning_brief as MB
    t = atlas(FIRST)
    line = MB.payday_line([{"key": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "_src": {"funded": t}}])
    check("c. the morning brief: 'REQUEST PAYOUT TODAY: ATLAS 25K $250 ($200 to you) - MFFU dashboard > Payouts, then TRADE_HOME -> P'",
          line == "REQUEST PAYOUT TODAY: ATLAS 25K $250 ($200 to you) - MFFU dashboard > Payouts, then TRADE_HOME -> P", line)
    st = PC.from_tracker(t)
    c = PC.coach(st, "builder25k", "2026-11-24")
    c0 = PC.coach({**st, "first_at_min": False}, "builder25k", "2026-11-24")
    check("c. engine/payout_coach: with ATLAS's flag READY $250 ('REQUEST PAYOUT TODAY: $250'); without it 'MFFU would pay $250 ... waits'",
          c["status"] == "ready" and c["request_today"] == 250 and c["text"].startswith("REQUEST PAYOUT TODAY: $250")
          and c0["status"] == "allowed" and "waits for the full $1,000" in c0["text"], (c.get("text"), c0.get("text")))
    hc = PC.coach(PC.from_tracker(atlas(HOGGY)), "builder25k", "2026-11-24")
    check("c. engine/payout_coach: the 67% best day is not ready (the 50% rule)", hc["status"] == "not_yet" and not hc["eligible"], hc.get("text"))
    js = os.path.join(ROOT, "tools", "web_public", "business", "payoutcoach.js")
    script = (f"const C = require({json.dumps(js)}); const st = C.fromTracker({json.dumps(t)}); const h = C.fromTracker({json.dumps(atlas(HOGGY))});"
              "const a = C.coach(st, 'builder25k', '2026-11-24'), b = C.coach(Object.assign({}, st, {first_at_min: false}), 'builder25k', '2026-11-24');"
              "const c = C.coach(h, 'builder25k', '2026-11-24');"
              "console.log(JSON.stringify({a: [a.status, a.request_today, a.text], b: [b.status, b.text], c: c.status}));")
    p = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    try:
        r = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        check("c. node ran payoutcoach.js", False, p.stderr[-300:])
        return
    check("c. the phone card (payoutcoach.js): the same READY $250 'REQUEST PAYOUT TODAY: $250', 'allowed' without the flag, 67% not ready",
          r["a"][0] == "ready" and r["a"][1] == 250 and r["a"][2] == c["text"] and r["b"][0] == "allowed" and r["c"] == "not_yet", r)
    from engine import mffu_view as MV
    f = MV._funded(t)
    check("c. the PC post's tracker row carries fm=1 (the phone's mffumodel / pc_feed coach state); 0 payouts", f.get("fm") == 1 and f.get("pn") == 0, f)
    lb = open(os.path.join(ROOT, "engine", "live_board.py"), encoding="utf-8").read()
    mm = open(os.path.join(ROOT, "tools", "web_public", "business", "mffumodel.js"), encoding="utf-8").read()
    pf = open(os.path.join(ROOT, "tools", "web_public", "pc_feed.js"), encoding="utf-8").read()
    check("c. the board card's funded block and both phone coach states pass the flag on", '"graduated", "first_at_min", "ask_goal")' in lb
          and "first_at_min: !!(f && f.fm)" in mm and "first_at_min: !!(f && f.fm)" in pf)


def part_d():
    """the Home Money tile (gate/arenas.js + gate.js coachPlan): progress to the PLAN's line, $1,350 for ATLAS's first payout"""
    W = os.path.join(ROOT, "tools", "web_public")
    script = r"""
global.window = { setTimeout: () => 0, location: { hash: '', pathname: '/', search: '' } };
global.document = { readyState: 'complete', getElementById: () => null, addEventListener() {}, documentElement: { classList: { toggle() {}, contains: () => false } } };
global.fetch = () => Promise.reject(new Error('offline'));
const A = require(%s), C = require(%s);
const a = C.coach({ balance: 401.38, first_at_min: true }, 'builder25k', '2026-11-24'), b = C.coach({ balance: 401.38 }, 'builder25k', '2026-11-24');
const mk = (goal, toGoal) => A.lines({ N: { cards: [{ key: 'atlas', kind: 'funded', today: 0, room: 1000, toAsk: 949, goal, toGoal }], running: true } }, null, null, '2026-11-24', null);
console.log(JSON.stringify({ a: [a.plan_line, a.profit], b: [b.plan_line], first: mk(a.plan_line, a.plan_line - a.profit).money.text,
  later: mk(b.plan_line, b.plan_line - b.profit).money.text, old: mk(undefined, undefined).money.text }));
""" % (json.dumps(os.path.join(W, "gate", "arenas.js")), json.dumps(os.path.join(W, "business", "payoutcoach.js")))
    p = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    try:
        r = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        check("d. node ran arenas.js + payoutcoach.js", False, p.stderr[-300:])
        return
    check("d. the coach's plan line in MFFU's $0 terms: $1,350 with ATLAS's flag (first payout), $2,100 without", r["a"] == [1350, 401.38] and r["b"] == [2100], r)
    check("d. Home's Money tile: 'Payout: $401 of $1,350' for ATLAS's first payout ($2,100 after it); no plan line = the old $2,100 words",
          r["first"] == "Payout: $401 of $1,350" and r["later"] == "Payout: $401 of $2,100" and r["old"] == "Payout: $1,151 of $2,100", r)
    g = open(os.path.join(W, "gate", "gate.js"), encoding="utf-8").read()
    check("d. gate.js passes the board's first_at_min to the coach (coachPlan) and the card's goal / toGoal to the tile",
          "coachPlan(a, board[k], !!fd.first_at_min)" in g and "goal: pl ? pl.goal : null, toGoal: pl ? pl.toGoal : null" in g)


def main() -> int:
    part_a()
    part_b()
    part_c()
    part_d()
    ok = sum(RES)
    print(f"\npayfirst: {ok}/{len(RES)} {'ALL PASS' if ok == len(RES) else 'FAILED'}")
    return 0 if ok == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
