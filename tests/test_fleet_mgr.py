"""engine/fleet_mgr.py: advice only, one alert per account change with the next money move. Fakes only (rows, cards, a sender).

  a. the first look records the fleet and sends nothing
  b. eval failed (Builder 25K, no card): re-buy the same plan tonight at $63 ($43), and the Rapid 50K refill card is offered
  c. Rapid EOD 50K died: card plan-rapid50k-max2-rebuys open -> "decide card ... first"; yes -> "re-buy #1 of 2 ... $165";
     after 2 re-buys -> "stop this slot" (the card's hard stop)
  d. 3 dead in a row -> STOP buying (the fleet plan's S3); an added account ends the streak
  e. MFFU caps: Builder 50K is 1 per user (no slot = no re-buy); 5 funded slots in all (next move: no buy)
  f. Builder payout 4 -> "close it, buy the next account" (never #5); payouts 1-3 send nothing here (the payout autopilot does)
  g. a Rapid paid >= $6,500 -> the live-move risk line, once
  h. passed -> one tap on the Start page; an account gone -> its slot is free + the next move
  i. one alert per change (the same state twice = nothing); a failed send is tried again
  j. the phone line: tiny() <= 200 bytes, no ids; Trading Home shows a 'Fleet' line that is info only (never a to-do)
  k. real prices: $91.80 / $63 / $97.20 / $165; cards read from decisions.json (all four buying cards open today)
    python -X utf8 -m tests.test_fleet_mgr
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import fleet_mgr as FM  # noqa: E402

RES: list = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:500]}]" if detail and not ok else ""))


def R(key, label, plan, stage="eval", n=0, paid=0.0):
    return {"key": key, "label": label, "plan": plan, "stage": stage, "payouts_n": n, "paid": paid}


def fleet(**over):
    rows = [R("lit", "Zlarior 50K", "builder50k"), R("atlas", "ATLAS 25K", "builder25k", "funded", 0),
            R("x:b25k_2", "Zlarior 25K #2", "builder25k"), R("rapid", "Rapid EOD 25K", "rapideod25")]
    return [dict(r, **over.get(r["key"], {})) for r in rows]


OPEN = {"plan-rapid50k-max2-rebuys": "open", "refill-25k-with-rapid50": "open", "buy-rapid50-now": "open"}
YES = {**OPEN, "plan-rapid50k-max2-rebuys": "yes"}


def run(st, rows, cd=OPEN):
    return FM.step(st, rows, cd)


def part_a():
    st, al = run({}, fleet())
    check("a. first look: records 4 accounts, no alert", not al and len(st["rows"]) == 4, al)


def part_b():
    st, _ = run({}, fleet())
    st, al = run(st, fleet(**{"x:b25k_2": {"stage": "failed"}}))
    check("b. 25K #2 failed: ONE alert 'Zlarior 25K #2 failed its eval'", len(al) == 1 and al[0]["title"] == "Zlarior 25K #2 failed its eval", al)
    b = al[0]["body"] if al else ""
    check("b. re-buy the same plan tonight: Builder 25K $63 ($43 if your code works), not a reset", "Builder 25K $63" in b and "$43" in b
          and "not a reset" in b, b)
    check("b. the Rapid 50K refill offered only as a card question", "refill-25k-with-rapid50" in b and "$165" in b, b)


def part_c():
    rows = fleet() + [R("rapid2", "Rapid EOD 50K #2", "rapideod50")]
    st, _ = run({}, rows)
    dead = [dict(r, stage="failed") if r["key"] == "rapid2" else r for r in rows]
    st1, al = run(st, dead, OPEN)
    check("c. Rapid 50K died, card open: 'Decide card plan-rapid50k-max2-rebuys first'", al and "Decide card plan-rapid50k-max2-rebuys first" in al[0]["body"], al)
    st2, al = run(st, dead, YES)
    check("c. card yes: 'Re-buy #1 of 2 allowed under the plan: Rapid EOD 50K $165'", al and "Re-buy #1 of 2 allowed" in al[0]["body"]
          and "$165" in al[0]["body"], al)
    st3, _ = run(st2, rows, YES)                       # re-bought: the same key back in its eval
    check("c. the re-buy is counted (1)", st3.get("rebuys", {}).get("rapideod50") == 1 and st3.get("dead_streak") == 0, st3.get("rebuys"))
    st4, al = run(st3, dead, YES)
    check("c. dies again: 'Re-buy #2 of 2'", al and "Re-buy #2 of 2" in al[0]["body"], al)
    st5, _ = run(st4, rows, YES)
    st6, al = run(st5, dead, YES)
    check("c. after 2 re-buys: no more, 'Stop this slot'", al and "No more re-buys" in al[0]["body"] and "Stop this slot" in al[0]["body"], al)


def part_d():
    st, _ = run({}, fleet())
    st, _ = run(st, fleet(lit={"stage": "failed"}))
    st, _ = run(st, fleet(lit={"stage": "failed"}, **{"x:b25k_2": {"stage": "failed"}}))
    st, al = run(st, fleet(lit={"stage": "failed"}, **{"x:b25k_2": {"stage": "failed"}}, atlas={"stage": "lost"}))
    check("d. the 3rd dead in a row: 'STOP buying' (the fleet plan's stop)", al and "STOP buying" in al[0]["body"] and st["dead_streak"] == 3, al)
    check("d. the next move says no buy", FM.next_move(fleet(lit={"stage": "failed"}), OPEN, st).startswith("no buy: 3 accounts died"))
    st, _ = run(st, fleet(**{"x:b25k_2": {"stage": "failed"}}, atlas={"stage": "lost"}))     # Zlarior 50K re-bought (back in eval)
    check("d. an added account ends the streak", st["dead_streak"] == 0, st.get("dead_streak"))


def part_e():
    rows = fleet() + [R("x:b50b", "Builder 50K #2", "builder50k")]
    st, _ = run({}, rows)
    st, al = run(st, [dict(r, stage="failed") if r["key"] == "x:b50b" else r for r in rows])
    check("e. a 2nd Builder 50K died: no re-buy, MFFU's cap (1 per user) is full", al and "No re-buy: MFFU's cap for Builder 50K" in al[0]["body"], al)
    five = fleet() + [R("rapid2", "Rapid EOD 50K #2", "rapideod50")]
    check("e. 5 accounts alive = 5 of 5 funded slots: next move = no buy", FM.next_move(five, YES, {}).startswith("no buy: all 5"), FM.next_move(five, YES, {}))
    check("e. 4 alive + the Rapid card open: 'decide card ... first'", "decide card plan-rapid50k-max2-rebuys first" in FM.next_move(fleet(), OPEN, {}))
    check("e. 4 alive + the Rapid card yes: buy a Rapid EOD 50K ($165)", "buy a Rapid EOD 50K ($165" in FM.next_move(fleet(), YES, {}))


def part_f():
    st, _ = run({}, fleet())
    st, al = run(st, fleet(atlas={"payouts_n": 1}))
    check("f. payout 1: nothing from the fleet manager (the payout autopilot handles it)", not al, al)
    st, _ = run(st, fleet(atlas={"payouts_n": 3}))
    st, al = run(st, fleet(atlas={"payouts_n": 4}))
    check("f. payout 4: 'ATLAS 25K took payout 4: close it, buy the next account'", al and al[0]["title"] ==
          "ATLAS 25K took payout 4: close it, buy the next account" and "Never take payout #5" in al[0]["body"], al)
    check("f. ... with the next move", al and "Next:" in al[0]["body"], al)


def part_g():
    rows = fleet(rapid={"stage": "funded", "payouts_n": 9, "paid": 6200.0})
    st, _ = run({}, rows)
    st, al = run(st, fleet(rapid={"stage": "funded", "payouts_n": 10, "paid": 6700.0}))
    check("g. a Rapid at $6,700 paid: the live-move risk line", al and "Rapid live-move risk" in al[0]["title"] and "$7,000" in al[0]["body"], al)
    st["told"] = {a["key"]: 1 for a in al}
    st, al = run(st, fleet(rapid={"stage": "funded", "payouts_n": 11, "paid": 7200.0}))
    check("g. ... once", not al, al)


def part_h():
    st, _ = run({}, fleet())
    st, al = run(st, fleet(lit={"stage": "passed"}))
    check("h. passed: 'Zlarior 50K PASSED' + one tap on the Start page", al and al[0]["title"] == "Zlarior 50K PASSED" and "Start page" in al[0]["body"], al)
    gone = [r for r in fleet(lit={"stage": "passed"}) if r["key"] != "x:b25k_2"]
    st, al = run(st, gone)
    check("rt2. gone from ONE read only (a flaky inventory): no alert yet", not al, al)
    st, al = run(st, gone)
    check("h. an account gone (2 reads in a row): 'its slot is free' + the next move", al and "slot is free" in al[0]["title"]
          and "Next:" in al[0]["body"], al)
    st2, _ = run({}, fleet())
    st2, al = run(st2, [r for r in fleet() if r["key"] != "atlas"])
    st2, al2 = run(st2, fleet())
    check("rt2. back on the next read: no 'closed', no 'added' noise", not al and not al2, (al, al2))
    st3, _ = run({}, fleet())
    st3, _ = run(st3, fleet(lit={"stage": "passed"}))
    st3, _ = run(st3, fleet(lit={"stage": "failed"}))
    st3, _ = run(st3, fleet(lit={"stage": "eval"}))                   # re-bought on the same key
    st3, al = run(st3, fleet(lit={"stage": "passed"}))
    check("rt2. a re-bought account on the same key that passes gets its own PASSED alert",
          any(a["title"] == "Zlarior 50K PASSED" for a in al), al)


def part_i():
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "fm.json")
        FM.tick(rows=fleet(), cd=OPEN, sender=lambda a: True, path=p)
        r = FM.tick(rows=fleet(lit={"stage": "failed"}), cd=OPEN, sender=lambda a: False, path=p)
        check("i. a failed send is reported, not marked told", r["alerts"] and not r["alerts"][0]["sent"], r)
        r2 = FM.tick(rows=fleet(lit={"stage": "failed"}), cd=OPEN, sender=lambda a: True, path=p)
        check("i. ... and sent on the next tick (it waited as pending)", len(r2["alerts"]) == 1 and r2["alerts"][0]["sent"], r2)
        r3 = FM.tick(rows=fleet(lit={"stage": "failed"}), cd=OPEN, sender=lambda a: True, path=p)
        check("i. the same state again = nothing", not r3["alerts"], r3)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_j():
    t = FM.tiny(fleet(), OPEN, {})
    s = json.dumps(t)
    check("j. tiny <= 200 bytes of text, counts + labels, no ids", len(t["s"]) <= 200 and t["n"] == 4 and t["sl"] == "4/5"
          and "MFFU" in t["s"] and not any(c.isdigit() and len(c) > 4 for c in s.split()), t)
    check("j. the phone line names the card in words", "Rapid EOD 50K card" in t["s"], t)
    js = os.path.join(ROOT, "tools", "web_public", "nq", "trading_home_core.js")
    code = ("const T=require(%s);const now=1795403700;"
            "const r=T.today({t:now-60,accounts:[],fl:{s:'4 MFFU accounts, 4 of 5 funded slots planned. Next: x',n:4,sl:'4/5'}},{now});"
            "const f=r.lines.find(l=>l.id==='fleet');const r0=T.today({t:now-60,accounts:[]},{now});"
            "console.log(JSON.stringify({f,left:r.left,left0:r0.left,has0:!!r0.lines.find(l=>l.id==='fleet')}));") % json.dumps(js)
    try:
        out = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30).stdout.strip())
        check("j. Trading Home: a 'Fleet' line from the post's fl block, info only (not a to-do)", out["f"] and out["f"]["title"] == "Fleet"
              and out["f"]["ok"] is True and out["left"] == out["left0"], out)
        check("j. no fl block = no Fleet line", out["has0"] is False, out)
    except Exception as e:  # noqa: BLE001
        check(f"j. node run ({e.__class__.__name__})", False)
    src = open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read()
    check("j. the status post carries fl (pc_report: snap + ext + EXT_ORDER) and the tick runs", '"fl"' in src and "_fm.tick()" in src)


def part_k():
    check("k. the owner's real prices", FM.PRICE == {"builder50k": 91.80, "builder25k": 63.0, "rapideod25": 97.20, "rapideod50": 165.0})
    cd = FM.cards()
    check("k. decisions.json read: the four buying cards are open today (no buy is suggested as approved)",
          all(cd.get(k) == "open" for k in ("plan-rapid50k-max2-rebuys", "plan-fundednext50k-max2-rebuys", "buy-rapid50-now", "refill-25k-with-rapid50")), cd)
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "d.json")
        json.dump({"items": [{"id": "plan-rapid50k-max2-rebuys", "status": "answered", "answer": "yes"}, {"id": "x", "status": "no"}]}, open(p, "w"))
        c2 = FM.cards(p)
        check("k. an answered yes = yes; status no = no", c2 == {"plan-rapid50k-max2-rebuys": "yes", "x": "no"}, c2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    src = open(os.path.join(ROOT, "engine", "fleet_mgr.py"), encoding="utf-8").read()
    check("k. advice only: no buy / arm / order / payout request code", not any(w in src for w in ("arm(", "place_order", "record_payout", "requests.post")))


def part_rt2():
    """red team 2: gather() reads a Rapid's payouts n / $ paid from its own slot (the autopilot's view carries neither), so the
    $6,500 live-move line can fire at all."""
    from engine import account_cli as AC, rapid as RP, payout_autopilot as PA
    old = (AC.inventory, RP.read, PA.gather)
    try:
        AC.inventory = lambda: [{"name": "R1", "plan": "rapideod25", "stage": "funded", "role": "rapid", "id": "rapid", "sim": False}]
        RP.read = lambda p=None: {"account": "R1", "stage": "funded", "payouts": {"2026-12-01": 3500.0, "2026-12-09": 3200.0}}
        PA.gather = lambda today=None: [{"key": "rapid", "kind": "rapid", "ready": False}]
        rows = FM.gather()
    finally:
        AC.inventory, RP.read, PA.gather = old
    check("rt2. gather: the Rapid's 2 payouts and $6,700 paid come from its slot", rows and rows[0]["payouts_n"] == 2
          and rows[0]["paid"] == 6700.0, rows)
    st, _ = run({}, [dict(rows[0], payouts_n=1, paid=3500.0)])
    st, al = run(st, rows)
    check("rt2. ... so the live-move risk alert fires", any("live-move" in a["title"] for a in al), al)


def main() -> int:
    for f in (part_a, part_b, part_c, part_d, part_e, part_f, part_g, part_h, part_i, part_j, part_k, part_rt2):
        try:
            f()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
    n, ok = len(RES), sum(RES)
    print(f"\nfleet manager: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
