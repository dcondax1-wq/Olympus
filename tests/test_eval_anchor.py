"""Eval ANCHOR (2026-10-24): the bot books the MFFU eval from the broker's own balance + floor on a day instead of rebuilding
the trailing floor from its ledger (engine/sizing.anchor_days, LiveBot.eval_anchor / eval_book, engine/eval_life --anchor,
multi_account / account_b sizing_state, the heartbeat eval card, Bot Brain sizing, the 17:05 ET "Check MFFU" push).

    python -X utf8 -m tests.test_eval_anchor

The owner's MFFU dashboard 2026-10-24: balance $49,710.80, floor $48,168.20 -> room $1,542.60, $3,289.20 to $53,000.
Paper only: temp state / anchor files, a simulated NinjaTrader folder; nothing is armed or routed.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import eval_life as EL, multi_account as MA, sizing as sz  # noqa: E402
from engine.ninjatrader import _FakeNT  # noqa: E402
from tests.test_multi_account import Clock, make_bot, ts  # noqa: E402

RESULTS = []
LSZ = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
A = {"as_of": "2026-10-23", "balance": 49710.80, "floor": 48168.20}
T_MON = ts(2026, 10, 26, 10, 0)            # Monday 2026-10-26 10:00 ET (first session after the anchor)
T_TUE = ts(2026, 10, 27, 10, 0)


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def near(a, b, tol=0.005):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


# ------------------------------------------------------------------------------------------------ the math (engine/sizing)
def math_checks():
    raw = {"0000-00-00": -100.0, "2026-10-19": -250.0, "2026-10-22": 61.0}      # the bot's own ledger before the anchor
    days, ex = sz.anchor_days(raw, A)
    check("anchor_days: days up to as_of and the old prior replaced by one prior = balance - start",
          days == {"0000-00-00": -289.20} and ex == {"floor0": -1831.80}, (days, ex))
    st = sz.eval_state(days, 0.0, plan=ex, session=6, today="2026-10-26")
    check("dashboard numbers -> room $1,542.60", near(st["room"], 1542.60), st)
    check("dashboard numbers -> need $3,289.20 (target - profit)", near(sz.TW_50K["target"] - st["profit"] - st["cum"], 3289.20), st)
    me = sz.mffu_eval(days, ex)
    check("mffu_eval: balance $49,710.80, floor $48,168.20, cushion $1,542.60, $3,289.20 to target",
          near(me["balance"], 49710.80) and near(me["trailing_mll"], 48168.20) and near(me["cushion"], 1542.60)
          and near(me["to_target"], 3289.20), me)
    # without the anchor the bot rebuilt floor $48,000 from its ledger (start - $2,000): room overstated
    old = sz.mffu_eval({"0000-00-00": -289.20})
    check("without the anchor the same balance gives the overstated room ($1,710.80)", near(old["cushion"], 1710.80), old)

    # a later +$500 EOD: balance $50,210.80 > the anchored EOD high $50,168.20 -> floor $48,210.80
    d2, ex2 = sz.anchor_days({**raw, "2026-10-26": 500.0}, A)
    s2 = sz.eval_state(d2, 0.0, plan=ex2, session=7, today="2026-10-27")
    m2 = sz.mffu_eval(d2, ex2)
    check("later +$500 EOD raises the floor to $48,210.80 (EOD high $50,210.80 - $2,000), room $2,000",
          near(m2["trailing_mll"], 48210.80) and near(s2["room"], 2000.0) and near(m2["balance"], 50210.80), (m2, s2))
    d3, ex3 = sz.anchor_days({"2026-10-26": 500.0, "2026-10-27": -300.0}, A)
    m3 = sz.mffu_eval(d3, ex3)
    check("then -$300: the floor stays at $48,210.80 (only moves up), room $1,700", near(m3["trailing_mll"], 48210.80)
          and near(m3["cushion"], 1700.0), m3)
    d4, ex4 = sz.anchor_days({"2026-10-26": 300.0}, A)
    m4 = sz.mffu_eval(d4, ex4)
    check("+$300 (EOD $50,010.80 < the anchored high $50,168.20): floor unchanged $48,168.20", near(m4["trailing_mll"], 48168.20), m4)
    d5, ex5 = sz.anchor_days({"2026-10-26": 2500.0}, A)
    m5 = sz.mffu_eval(d5, ex5)
    s5 = sz.eval_state(d5, 0.0, plan=ex5)
    check("big day: the floor locks at start + $100 ($50,100)", near(m5["trailing_mll"], 50100.0) and near(s5["room"], 52210.80 - 50100.0),
          (m5, s5))
    # today's P&L (intraday) counts in the room, not in the floor
    s6 = sz.eval_state(days, -400.0, plan=ex, session=6, today="2026-10-26")
    check("today's closed P&L lowers the room, not the floor ($1,142.60)", near(s6["room"], 1142.60), s6)

    # null / invalid anchor = exactly the behaviour before
    same, e0 = sz.anchor_days(raw, None)
    check("anchor None: the same days object back, no plan extra", same is raw and e0 == {})
    bad = [{"as_of": "2026-13-01", "balance": 1, "floor": 1}, {"as_of": "2026-10-23", "balance": 100.0, "floor": 200.0},
           {"as_of": "2026-10-23", "balance": "x", "floor": 1}, {"balance": 49710.8, "floor": 48168.2}, "junk", {}]
    check("invalid anchors are ignored (bad date, floor > balance, not numbers, no date)",
          all(sz.eval_anchor(b) is None and sz.anchor_days(raw, b)[0] is raw for b in bad))
    check("no anchor: eval_state / mffu_eval / eval_clock identical to the plain call",
          sz.eval_state(raw, -50.0, session=4, today="2026-10-22") == sz.eval_state(raw, -50.0, plan=None, session=4, today="2026-10-22")
          and sz.mffu_eval(raw) == sz.mffu_eval(raw, None)
          and sz.eval_clock(raw, "2026-10-19", "2026-10-22") == sz.eval_clock(raw, "2026-10-19", "2026-10-22", plan=None))
    check("newest_anchor: the latest as_of wins, first on a tie",
          sz.newest_anchor({**A, "as_of": "2026-10-20"}, A)["as_of"] == "2026-10-23"
          and sz.newest_anchor(A, {**A, "balance": 1e5})["balance"] == A["balance"] and sz.newest_anchor(None, "x") is None)

    # the two_week sizer sizes from the anchored room (60% cap) and need
    tr = {"risk_pts": 60.0, "tgt_pts": 100.0, "size_mult": 1.0}       # wide stop: the 60% room cap binds
    r_a = sz.lit_qty(13, tr, LSZ, room=st["room"], state=st, learning=None)
    st_old = sz.eval_state({"0000-00-00": -289.20}, 0.0, session=6, today="2026-10-26")
    r_o = sz.lit_qty(13, tr, LSZ, room=st_old["room"], state=st_old, learning=None)
    cap = int(0.6 * 1542.60 / (60.0 * 2.0))
    check(f"two_week: anchored 60% room cap = {cap} micros (unanchored {r_o['qty']})", r_a["qty"] <= cap and r_a["qty"] < r_o["qty"],
          (r_a, r_o))
    # eval_life.view with the anchor
    v = EL.view({"2026-10-19": -250.0}, "2026-10-19", "2026-10-26", LSZ, anchor=A)
    check("eval_life.view anchored: balance, floor, room, to_target, status open",
          near(v["balance"], 49710.80) and near(v["floor"], 48168.20) and near(v["room"], 1542.60) and near(v["to_target"], 3289.20)
          and v["status"] == "open" and v["anchor"]["as_of"] == "2026-10-23", v)
    v0 = EL.view({"2026-10-19": -250.0}, "2026-10-19", "2026-10-26", LSZ)
    check("eval_life.view without the anchor: no floor / anchor keys (as before)", "anchor" not in v0 and "floor" not in v0, v0)
    vf = EL.view({"2026-10-26": -1600.0}, "2026-10-19", "2026-10-27", LSZ, anchor=A)
    check("anchored fail: -$1,600 after the anchor -> room <= 0 -> failed (the unanchored book would say open)",
          vf["status"] == "failed" and EL.view({"0000-00-00": -289.20, "2026-10-26": -1600.0}, "2026-10-19", "2026-10-27", LSZ)["status"] == "open",
          vf)


# ------------------------------------------------------------------------------------------------ accounts / multi / account B
def account_checks():
    from engine import accounts
    v = accounts.eval_view({"0000-00-00": -100.0, "2026-10-19": -250.0}, "2026-10-19", "2026-10-26", now=T_MON, anchor=A)
    check("heartbeat eval card (accounts.eval_view) anchored: balance / floor / room / to_target",
          near(v["balance"], 49710.80) and near(v["floor"], 48168.20) and near(v["room"], 1542.60) and near(v["to_target"], 3289.20)
          and v["anchor"]["floor"] == 48168.20, v)
    v0 = accounts.eval_view({"0000-00-00": -100.0, "2026-10-19": -250.0}, "2026-10-19", "2026-10-26", now=T_MON)
    check("eval card without the anchor: unchanged (floor $48,000)", near(v0["floor"], 48000.0) and "anchor" not in v0, v0)
    R50 = MA.rules_of({"preset": "mffu_builder_50k"})
    closes = [("2026-10-21", 1, -250.0), ("2026-10-26", 2, 500.0)]
    s = MA.sizing_state("two_week", closes, "2026-10-27", "2026-10-19", R50, prior=-100.0, anchor=A)
    check("multi_account.sizing_state anchored (+$500 after): room $2,000, profit +$210.80",
          near(s["room"], 2000.0) and near(s["profit"], 210.80) and s["anchor"]["as_of"] == "2026-10-23", s)
    s0 = MA.sizing_state("two_week", closes, "2026-10-27", "2026-10-19", R50, prior=-100.0)
    s0b = MA.sizing_state("two_week", closes, "2026-10-27", "2026-10-19", R50, prior=-100.0, anchor=None)
    check("multi_account.sizing_state anchor None: identical to before", s0 == s0b and "anchor" not in s0)
    R25 = MA.rules_of({"preset": "mffu_builder_25k"})
    s25 = MA.sizing_state("two_week", [], "2026-10-26", "2026-10-19", R25, anchor={"as_of": "2026-10-23", "balance": 24800.0,
                                                                                   "floor": 24100.0})
    check("Builder 25K (account B / extra) anchored: room $700, need $1,700", near(s25["room"], 700.0)
          and near(R25["target"] - s25["profit"], 1700.0), s25)
    sf = MA.sizing_state("funded", closes, "2026-10-27", "2026-10-19", R50, anchor=A)
    sf0 = MA.sizing_state("funded", closes, "2026-10-27", "2026-10-19", R50)
    check("funded mode ignores the eval anchor", sf == sf0)


# ------------------------------------------------------------------------------------------------ the PC bot + the CLI
def bot_checks(tmp):
    fake = _FakeNT(os.path.join(tmp, "NinjaTrader 8"))
    clock = Clock(T_MON + 290)

    def bot(prev, name, extra=None):
        b = make_bot(os.path.join(tmp, name), fake, clock, None, extra_cfg={"eval_start": "2026-10-19", **(extra or {})})
        b._lit_sizing = copy.deepcopy(LSZ)
        b._eval_prev = dict(prev)
        b.state = {"model": "lit"}
        return b

    prev = {"2026-10-19": -250.0, "2026-10-22": 61.0}
    b0 = bot(prev, "b0")
    st0 = b0.eval_state()
    exp = sz.eval_state({"0000-00-00": -100.0, **prev}, 0.0, session=sz.eval_session("2026-10-19", "2026-10-26"), today="2026-10-26")
    exp["n_today"] = 0
    check("LiveBot without an anchor: eval_state / eval_room exactly as before", b0.eval_anchor() is None and st0 == exp
          and b0.eval_room() == sz.mffu_eval(b0.eval_days())["cushion"], (st0, exp))
    from engine import accounts
    check("heartbeat acct block without an anchor: no anchor key", "anchor" not in accounts.pc_activity(b0, now=T_MON)["eval"])
    check("a test bot reads the anchor file next to its own state file, never data/eval_anchor.json",
          EL.anchor_path(b0.state_path) == os.path.join(tmp, "b0", "eval_anchor.json"))

    b = bot(prev, "b1")
    p = EL.anchor_path(b.state_path)
    rc = EL.main(["--anchor", "--balance", "49710.80", "--floor", "48168.20", "--as-of", "2026-10-23", "--anchor-file", p])
    d = json.load(open(p, encoding="utf-8"))
    check("owner CLI --anchor: rc 0, main entry written (temp + rename)", rc == 0 and d["main"]["balance"] == 49710.80
          and d["main"]["floor"] == 48168.20 and d["main"]["as_of"] == "2026-10-23" and not os.path.exists(p + ".tmp"), d)
    st = b.eval_state()
    check("LiveBot anchored: eval_state room $1,542.60, need $3,289.20, session count unchanged",
          near(st["room"], 1542.60) and near(3000.0 - st["profit"] - st["cum"], 3289.20) and st["session"] == st0["session"]
          and st["anchor"]["as_of"] == "2026-10-23", st)
    check("LiveBot anchored: eval_room $1,542.60", near(b.eval_room(), 1542.60), b.eval_room())
    b._eval_life_tick() if hasattr(b, "_push_send") else None
    el = b.eval_life()
    check("LiveBot anchored: eval_life balance / floor / room", near(el["balance"], 49710.80) and near(el["floor"], 48168.20)
          and near(el["room"], 1542.60), el)
    ck = b.eval_clock()
    check("LiveBot anchored: eval clock room + to_target", near(ck["room"], 1542.60) and near(ck["to_target"], 3289.20), ck)
    hb = accounts.pc_activity(b, now=T_MON)
    check("heartbeat acct block carries the anchor; raw days unchanged", hb["eval"].get("anchor", {}).get("floor") == 48168.20
          and hb["eval"]["days"] == {"0000-00-00": -100.0, **prev}, hb["eval"])
    sec = accounts._pc_section({"id": "x", "kind": "eval"}, {"present": True, "t": T_MON, "acct": hb}, {"lit_sizing": LSZ},
                               "2026-10-26", T_MON)
    check("cloud / phone eval card from the heartbeat: room $1,542.60, floor $48,168.20, $3,289.20 to go",
          near(sec["eval"]["room"], 1542.60) and near(sec["eval"]["floor"], 48168.20) and near(sec["eval"]["to_target"], 3289.20),
          sec["eval"])
    from engine import brain
    sz_out = brain._sizing({"risk": 30.0, "tgt": 200.0, "what": "test"}, {"lit_sizing": LSZ, "eval_state": st}, None, {}, None)
    steps = {s_["label"]: s_ for s_ in sz_out["steps"]}
    check("Bot Brain sizing: MFFU anchor step + 'Left to +$3,000' = $3,289 + 60% cap on the $1,543 room",
          "MFFU anchor" in steps and "48,168.20" in steps["MFFU anchor"]["text"] and "3,289" in steps["Left to +$3,000"]["value"]
          and "1,543" in steps["60% room cap"]["text"], sz_out["steps"])

    # the session after: a routed +$500 day raises the floor
    clock.t = T_TUE + 290
    b2 = bot({**prev, "2026-10-26": 500.0}, "b2")
    EL.save_anchor(A, path=EL.anchor_path(b2.state_path))
    st2 = b2.eval_state()
    check("LiveBot: +$500 routed after the anchor -> room $2,000 (floor $48,210.80)", near(st2["room"], 2000.0), st2)
    # an older start-cfg anchor loses to the newer file
    b3 = bot(prev, "b3", extra={"eval_anchor": {"as_of": "2026-10-20", "balance": 49900.0, "floor": 48000.0}})
    check("start cfg anchor alone is used", b3.eval_anchor()["as_of"] == "2026-10-20")
    EL.save_anchor(A, path=EL.anchor_path(b3.state_path))
    check("the newer CLI anchor wins over an older start cfg anchor", b3.eval_anchor()["as_of"] == "2026-10-23")
    # per-account entries (extra accounts / account B by NinjaTrader Name) do not leak into the main account
    p4 = os.path.join(tmp, "acc_only.json")
    rc4 = EL.main(["--anchor", "--balance", "24800", "--floor", "24100", "--as-of", "2026-10-23", "--account", "SIMB25K", "--anchor-file", p4])
    check("--account writes the account entry only", rc4 == 0 and EL.load_anchor("SIMB25K", path=p4)["floor"] == 24100.0
          and EL.load_anchor(None, path=p4) is None and EL.load_anchor("OTHER", path=p4, main=False) is None)
    rc5 = EL.main(["--anchor", "--balance", "100", "--floor", "200", "--as-of", "2026-10-23", "--anchor-file", p4])
    check("--anchor refuses floor > balance (rc 1, nothing written)", rc5 == 1 and EL.load_anchor(None, path=p4) is None)

    # the 17:05 ET push
    from engine import ops_checks as oc
    hbx = {"t": T_MON, "acct": hb}
    view = oc.account_view(hbx, T_MON)
    n = oc.mffu_check_notice(hbx, view, ts(2026, 10, 26, 17, 5))
    check("17:05 push: 'Check MFFU: bot thinks balance $49,710.80, floor $48,168.20' + the re-anchor command",
          n is not None and n["title"].startswith("Check MFFU: bot thinks balance $49,710.80, floor $48,168.20")
          and "--anchor" in n["body"] and "anchored 2026-10-23" in n["body"] and n["key"] == "ops:mffu:2026-10-26", n)
    check("17:05 push window: weekdays 17:05-17:55 ET only", oc.due(ts(2026, 10, 26, 17, 5))["mffu_check"]
          and not oc.due(ts(2026, 10, 26, 16, 30))["mffu_check"] and not oc.due(ts(2026, 10, 25, 17, 10))["mffu_check"])
    sent = []
    st_ops = {"sent": {}}
    oc.tick(now=ts(2026, 10, 26, 17, 10), ctx={"hb": hbx, "net": {"up": True}, "folder": os.path.join(tmp, "nofolder"), "now": T_MON},
            state=st_ops, sender=lambda p_: (sent.append(p_), {"sent": 1})[1], state_path=os.path.join(tmp, "ops.json"), do_backup=False)
    oc.tick(now=ts(2026, 10, 26, 17, 30), ctx={"hb": hbx, "net": {"up": True}, "folder": os.path.join(tmp, "nofolder"), "now": T_MON},
            state=st_ops, sender=lambda p_: (sent.append(p_), {"sent": 1})[1], state_path=os.path.join(tmp, "ops.json"), do_backup=False)
    mf = [p_ for p_ in sent if str(p_.get("key", "")).startswith("ops:mffu:")]
    check("ops tick sends the MFFU check once a day", len(mf) == 1, [p_.get("key") for p_ in sent])


def main():
    tmp = tempfile.mkdtemp(prefix="le_anchor_")
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    try:
        math_checks()
        account_checks()
        bot_checks(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RESULTS), sum(RESULTS)
    print(f"eval anchor: {ok}/{n} {'ALL PASS' if ok == n else 'FAILURES'}")
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    main()
