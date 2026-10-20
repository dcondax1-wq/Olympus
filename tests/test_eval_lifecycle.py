"""MFFU Builder 50K eval lifecycle (engine/eval_life.py, engine/sizing.eval_lock, LiveBot._eval_life_tick): the pass day,
the fail day, the minimum-days trade, the eval weekly loss stop on / off, the funded switch, and the funded MFFU Builder
50K on the 2026 LIT trades through the live funded code path (best-day cap, buffer, payouts recorded).

    python -X utf8 -m tests.test_eval_lifecycle           # everything (~30 s: builds the 2026 unit cache once if missing)
    python -X utf8 -m tests.test_eval_lifecycle --quick   # without the 2026 funded replay (~5 s)

Paper only: temp state / accounts files, made-up account names, a simulated NinjaTrader folder; nothing is armed.
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
from tests.test_multi_account import Clock, make_bot, pos_at, ts  # noqa: E402

RESULTS = []
LSZ = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
T_WED = ts(2026, 10, 21, 10, 0)            # Wednesday 2026-10-21, 10:00 ET
TR = {"risk_pts": 30.0, "tgt_pts": 200.0, "size_mult": 1.0}


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def q_of(lsz, st, qty=13, trade=TR):
    return sz.lit_qty(qty, trade, lsz, room=st.get("room"), state=st, learning=None)


# ------------------------------------------------------------------------------------------------ sizing (engine/sizing)
def sizing_checks():
    L = copy.deepcopy(LSZ)
    # pass on session 1 (no prior P&L): session 2 = one 1-micro minimum-days trade, session 3 = nothing
    s2 = sz.eval_state({"2026-10-19": 3050.0}, 0.0, session=2, today="2026-10-20")
    r = q_of(L, s2)
    check("pass day +1: MFFU minimum days -> one 1-micro trade", r["qty"] == 1, r)
    s2b = {**s2, "n_today": 1}
    check("pass day +1, an entry already routed today: 0", q_of(L, s2b)["qty"] == 0)
    s3 = sz.eval_state({"2026-10-19": 3050.0, "2026-10-20": -2.0}, 0.0, session=3, today="2026-10-21")
    r = q_of(L, s3)
    check("pass day +2 (2 traded days): no trade", r["qty"] == 0 and "target already reached" in " ".join(r["reasons"]), r)
    # the same day the target is hit: no 2nd trade (1 a day anyway; the target today -> 0)
    s1 = sz.eval_state({}, 3100.0, session=1, today="2026-10-19")
    check("target reached today: no new trade", q_of(L, s1)["qty"] == 0)
    # the owner's -$100 prior counts as an earlier traded day: +$3,100 on session 1 already has 2 traded days
    sp = sz.eval_state({"0000-00-00": -100.0, "2026-10-19": 3100.0}, 0.0, session=2, today="2026-10-20")
    check("with the -$100 prior (balance $53,000): passed, 2 traded days -> no trade", sp["profit"] == 3000.0 and q_of(L, sp)["qty"] == 0, sp)
    # after session 10 (after_mode safe_eval): before 2026-10-20 a passed eval kept trading at the safe_eval size
    days = {f"2026-10-{d:02d}": 0.0 for d in (5, 6, 7, 8, 9, 12, 13, 14, 15, 16)}
    days["2026-10-15"] = -50.0
    days["2026-10-16"] = 3250.0
    s11 = sz.eval_state(days, 0.0, session=11, today="2026-10-19")
    on, off = q_of(L, s11), q_of({**L, "pass_lock": False}, s11)
    check("passed eval after session 10 (safe_eval): no trade (pass_lock)", on["qty"] == 0 and on.get("lock") == "passed", on)
    check("pass_lock false = the old sizing (safe_eval kept trading a passed eval)", off["qty"] > 0, off)
    # fail day: room <= 0 -> 0; the room caps' min-1-micro rule traded 1 micro before
    sf = sz.eval_state({"0000-00-00": -100.0, "2026-10-19": -1950.0}, 0.0, session=2, today="2026-10-20")
    fon, foff = q_of(L, sf), q_of({**L, "pass_lock": False}, sf)
    check("failed eval (room -$50): no trade", sf["room"] < 0 and fon["qty"] == 0 and fon.get("lock") == "failed", (sf, fon))
    check("pass_lock false: the old 1-micro trade on a failed eval", foff["qty"] == 1, foff)
    # open eval: unchanged
    so = sz.eval_state({"2026-10-19": 400.0}, 0.0, session=2, today="2026-10-20")
    check("open eval: pass_lock changes nothing", q_of(L, so)["qty"] == q_of({**L, "pass_lock": False}, so)["qty"] > 0)
    check("mode normal / funded: no eval lock", sz.lit_qty(13, TR, {"mode": "normal"}, state=sf, learning=None)["qty"] == 13)
    # weekly loss stop
    sw = sz.eval_state({"2026-10-19": -700.0, "2026-10-20": -600.0}, 0.0, session=3, today="2026-10-21")
    check("weekly loss stop OFF (key absent, live_model.json today): trades", "wk_loss_usd" not in LSZ and q_of(L, sw)["qty"] > 0)
    w_on = q_of({**L, "wk_loss_usd": 1200}, sw)
    check("weekly loss stop ON at -$1,200, week -$1,300: no trade", w_on["qty"] == 0 and "weekly loss stop" in " ".join(w_on["reasons"]), w_on)
    sw2 = sz.eval_state({"2026-10-16": -1300.0}, 0.0, session=6, today="2026-10-19")
    check("weekly loss stop: a new week (Monday) trades again", q_of({**L, "wk_loss_usd": 1200}, sw2)["qty"] > 0)


# ------------------------------------------------------------------------------------------------ views + pushes
def view_checks():
    L = copy.deepcopy(LSZ)
    v = EL.view({"0000-00-00": -100.0, "2026-10-19": 3100.0}, "2026-10-19", "2026-10-20", L)
    check("view: passed at balance $53,000", v["status"] == "passed" and v["balance"] == 53000.0 and v["min_days_left"] == 0, v)
    n = EL.notices(v, "MFFU 50K", T_WED)
    b = n[0]["body"] if n else ""
    check("pass push: 'EVAL PASSED \U0001F389 next steps' + agreement, account name, funded command, payout habit",
          len(n) == 1 and n[0]["title"] == "EVAL PASSED \U0001F389 next steps" and "agreement" in b and "--to-funded" in b and len(b) <= 600 and "Name" in b
          and "$53,600" in b and "$2,100 buffer" in b and "$2,000" in b and n[0]["key"] == "eval:passed:2026-10-19", n)
    v1 = EL.view({"2026-10-19": 3050.0}, "2026-10-19", "2026-10-20", L)
    check("view: passed on session 1 -> 1 minimum day left", v1["min_days_left"] == 1 and "minimum-days" in v1["trading"], v1)
    vf = EL.view({"0000-00-00": -100.0, "2026-10-19": -1950.0}, "2026-10-19", "2026-10-20", L)
    nf = EL.notices(vf, "MFFU 50K", T_WED)
    bf = nf[0]["body"] if nf else ""
    check("fail push: owner price, verify the code at checkout, stagger 5 sessions",
          vf["status"] == "failed" and len(nf) == 1 and "FAILED" in nf[0]["title"] and EL.OWNER_PRICE in bf
          and "verify the code at checkout" in bf and "5 sessions" in bf, nf)
    vo = EL.view({"2026-10-19": -700.0, "2026-10-20": -600.0}, "2026-10-19", "2026-10-21", L)
    check("weekly loss stop off: state 'off', no push", vo["wk_stop"]["state"] == "off" and not EL.notices(vo, "x", T_WED), vo["wk_stop"])
    vw = EL.view({"2026-10-19": -700.0, "2026-10-20": -600.0}, "2026-10-19", "2026-10-21", {**L, "wk_loss_usd": 1200})
    nw = EL.notices(vw, "MFFU 50K", T_WED)
    check("weekly loss stop tripped: state + one push keyed by the week",
          vw["wk_stop"]["state"] == "tripped" and len(nw) == 1 and nw[0]["key"] == "eval:wkstop:2026-10-19:2026-10-19", (vw["wk_stop"], nw))
    va = EL.view({"2026-10-19": -300.0}, "2026-10-19", "2026-10-21", {**L, "wk_loss_usd": 1200})
    check("weekly loss stop armed: state 'armed', no push", va["wk_stop"]["state"] == "armed" and not EL.notices(va, "x", T_WED), va["wk_stop"])


# ------------------------------------------------------------------------------------------------ the PC bot (LiveBot)
def bot_checks(tmp):
    fake = _FakeNT(os.path.join(tmp, "NinjaTrader 8"))
    clock = Clock(T_WED + 290)

    def bot(prev, lsz, start="2026-10-19"):
        b = make_bot(os.path.join(tmp, f"b{len(os.listdir(tmp))}"), fake, clock, None, extra_cfg={"eval_start": start})
        b._lit_sizing = copy.deepcopy(lsz)
        b._eval_prev = dict(prev)
        b.state = {"model": "lit"}
        sent = []
        b._push_send = lambda p: sent.append(p)
        return b, sent

    L = copy.deepcopy(LSZ)
    p = pos_at(T_WED, qty=13)
    b, sent = bot({"2026-10-19": 400.0}, L)
    q_open = b._equity_qty(T_WED, 13, p)
    b._eval_life_tick()
    check("LiveBot open eval: trades, eval_life open, weekly stop off, no push",
          q_open > 0 and b.state["eval_life"]["status"] == "open" and b.state["eval_life"]["wk_stop"]["state"] == "off" and not sent,
          (q_open, b.state.get("eval_life")))
    b, sent = bot({"2026-10-19": 3100.0}, L)                       # -$100 prior from live_model.json: balance $53,000
    q = b._equity_qty(T_WED, 13, p)
    b._eval_life_tick()
    b._eval_life_tick()
    check("LiveBot pass day: no new trade, eval_life passed, ONE pass push (once per poll loop)",
          q == 0 and b.state["eval_life"]["status"] == "passed" and len(sent) == 1 and "EVAL PASSED" in sent[0]["title"], (q, sent))
    check("LiveBot pass day: logged on the bot's risk log", any("EVAL PASSED" in l["text"] for l in b.log))
    b, sent = bot({"2026-10-20": 3050.0}, {**L, "eval_prior_pnl": 0.0}, start="2026-10-20")
    b.cfg["eval_prior_pnl"] = 0.0
    q = b._equity_qty(T_WED, 13, p)
    check("LiveBot pass day +1 with 1 traded day: the 1-micro minimum-days trade", q == 1, q)
    b, sent = bot({"2026-10-05": -50.0, "2026-10-16": 3250.0}, L, start="2026-10-05")
    q = b._equity_qty(T_WED, 13, p)
    check("LiveBot passed eval after session 10 (safe_eval): no trade", q == 0, q)
    b, sent = bot({"2026-10-19": -1950.0}, L)
    q = b._equity_qty(T_WED, 13, p)
    b._eval_life_tick()
    check("LiveBot fail day: no trade, eval_life failed, one fail push",
          q == 0 and b.state["eval_life"]["status"] == "failed" and len(sent) == 1 and "FAILED" in sent[0]["title"], (q, sent))
    b, sent = bot({"2026-10-19": -700.0, "2026-10-20": -600.0}, {**L, "wk_loss_usd": 1200})
    q = b._equity_qty(T_WED, 13, p)
    b._eval_life_tick()
    check("LiveBot weekly loss stop ON: no trade, tripped, one push", q == 0 and b.state["eval_life"]["wk_stop"]["state"] == "tripped"
          and len(sent) == 1 and "Weekly loss stop" in sent[0]["title"], (q, sent))
    b, sent = bot({"2026-10-19": -700.0, "2026-10-20": -600.0}, L)
    q = b._equity_qty(T_WED, 13, p)
    check("LiveBot weekly loss stop OFF (live_model.json): trades", q > 0, q)
    from engine import accounts, pcdash_api
    b._eval_life_tick()
    h = accounts.pc_health(b, T_WED)
    sv = pcdash_api.status_view(b, T_WED)
    check("heartbeat health + PC status carry eval_life (weekly loss stop off/armed/tripped)",
          (h.get("eval_life") or {}).get("wk_stop") == "off" and (h["eval_life"].get("pushes") is True)
          and (sv.get("eval_life") or {}).get("status") == "open", (h.get("eval_life"), sv.get("eval_life")))
    from engine import ops_checks as oc
    hb = {"t": T_WED, "health": h, "acct": {}}
    check("ops_checks: no 2nd pass / fail push while the bot (fresh heartbeat with eval_life) sends its own; old bot -> ops sends",
          oc.bot_pushes_eval(hb, {"fresh": True}) and not oc.bot_pushes_eval(hb, {"fresh": False})
          and not oc.bot_pushes_eval({"t": T_WED, "health": {k: v for k, v in h.items() if k != "eval_life"}}, {"fresh": True}))

    # ---- the funded switch: one command -> data/accounts.json, then the bot sizes the funded account with funded_state
    path = os.path.join(tmp, "accounts.json")
    rc = EL.to_funded("FUNDEDFAKE01", "2026-10-22", path=path)
    rows = MA.load_file(path)
    n = MA.normalize(rows[0]) if rows else {}
    check("--to-funded: a disarmed mode-funded MFFU Builder 50K entry with its funded start",
          rc == 0 and len(rows) == 1 and n["mode"] == "funded" and n["preset"] == "mffu_builder_50k" and not n["armed"]
          and n["funded"].get("start") == "2026-10-22" and n["nt_account"] == "FUNDEDFAKE01" and not n["problem"], rows)
    rc2 = EL.record_payout("2026-11-20=2000", path=path)
    check("--payout records the payout on the funded account", rc2 == 0
          and MA.load_file(path)[0]["funded"]["payouts"] == {"2026-11-20": 2000.0}, MA.load_file(path))
    rc3 = EL.to_funded("FUNDEDFAKE01", "2026-10-22", path=path)
    check("--to-funded again: same entry updated, not duplicated", rc3 == 0 and len(MA.load_file(path)) == 1)
    pp = os.path.join(tmp, "accounts_paper.json")
    EL.to_funded("", "2026-10-21", path=pp, adapter="paper")
    spec = MA.load_file(pp)
    clock.t = T_WED + 290
    bf = make_bot(os.path.join(tmp, "bf"), fake, clock, spec, extra_cfg={"eval_start": "2026-10-19"})
    bf._lit_sizing = copy.deepcopy(LSZ)
    a = bf.accts.accounts[0] if bf.accts else None
    st = a.state("2026-10-21") if a else None
    q = a.qty_for({**p, "tgt_pts": 200.0}, T_WED + 305) if a else None
    exp = sz.funded_qty({"risk_pts": 30.0, "tgt_pts": 200.0}, st, MA.PRESETS["mffu_builder_50k"]["sizing"]["funded"])
    check("funded account in the bot: mode funded, funded_state room $2,000, micros = funded_qty (40% room, <= $1,500 winner)",
          a is not None and a.mode == "funded" and st and st["room"] == 2000.0 and q == exp and q >= 1, (st, q, exp))


# ------------------------------------------------------------------------------------------------ funded on 2026
def funded_2026():
    """The 2026 LIT trades (run lit_live units) on one funded MFFU Builder 50K through the live code path:
    multi_account.sizing_state("funded") + sizing.lit_qty(mode funded, the preset's funded cfg) + the account's dll cap;
    a payout at a session's end whenever eval_life.payout_check says ok (the owner's habit: $1,500+ above the buffer)."""
    from tools import lit_risk_money as M
    U = [u for u in M.load()["base"]["U"] if str(u["day"]) >= "2026-01-01"]
    spec = MA.normalize({"id": "f", "adapter": "paper", "preset": "mffu_builder_50k", "mode": "funded", "funded": {"start": "2026-01-02"}})
    R = spec["rules"]
    cfg = MA.sizing_cfg(LSZ, spec)
    closes, payouts, days, rows, pay_rows = [], {}, {}, [], []
    lost = None
    for u in U:
        d = str(u["day"])
        st = MA.sizing_state("funded", closes, d, "2026-01-02", R, payouts=payouts)
        if st["room"] <= 0:
            lost = d
            break
        r = sz.lit_qty(10, {"risk_pts": float(u["risk"]), "tgt_pts": float(u["tgt"]), "size_mult": float(u.get("wk_m") or 1.0)},
                       cfg, room=st["room"], state=st, learning=None)
        q = int(r["qty"])
        if q:
            loss1 = (float(u["risk"]) + sz.TW_DLL_SLIP) * sz.TW_PV + sz.TW_COMM
            q = min(q, max(1, int((float(R["dll"]) + min(0.0, days.get(d, 0.0))) / loss1)))   # Account.qty_for's daily cap
        pnl = round(q * (float(u["pts"]) * sz.TW_PV - sz.TW_COMM), 2)
        rows.append({"day": d, "q": q, "win_usd": q * (float(u["tgt"]) * sz.TW_PV - sz.TW_COMM), "pnl": pnl, "room": st["room"],
                     "risk_usd": q * ((float(u["risk"]) + 0.5) * sz.TW_PV + sz.TW_COMM)})
        if q:
            closes.append((d, int(u["exit_t"]), pnl))
            days[d] = round(days.get(d, 0.0) + pnl, 2)
        pc = EL.payout_check(days, payouts)
        if pc["ok"]:
            before = sz.funded_state(days, 0.0, payouts)
            payouts[d] = pc["amount"]
            after = sz.funded_state(days, 0.0, payouts)
            pay_rows.append({"day": d, **pc, "floor_before": before["floor"], "floor_after": after["floor"],
                             "bal_drop": round(before["balance"] - after["balance"], 2)})
    traded = [x for x in rows if x["q"]]
    big = [x for x in traded if x["q"] > 1 and x["win_usd"] > 1500.0 + 1e-6]
    check("funded 2026: every trade with 2+ micros pays at most $1,500 at its target (best-day cap)", not big, big[:3])
    check("funded 2026: the account is never lost (room > 0 at every entry)", lost is None and all(x["room"] > 0 for x in rows), lost)
    check("funded 2026: each payout asked only at $1,500+ above the $2,100 buffer, $500-$2,000",
          pay_rows and all(p["above_buffer"] >= 1500.0 and 500.0 <= p["amount"] <= 2000.0 for p in pay_rows), pay_rows[:2])
    check("funded 2026: payouts lower the balance, never the floor",
          all(abs(p["bal_drop"] - p["amount"]) < 1e-6 and p["floor_after"] == p["floor_before"] for p in pay_rows), pay_rows[:2])
    check("funded 2026: every payout meets best day <= 50% of the cycle and 2+ traded days",
          all(p["best_day"] <= 0.5 * p["cycle_profit"] + 1e-6 and p["cycle_days"] >= 2 for p in pay_rows), pay_rows[:2])
    check("funded 2026: at most 5 sim payouts", len(pay_rows) <= 5, len(pay_rows))
    paid = sum(p["amount"] for p in pay_rows)
    n_months = 9.5
    end = sz.funded_state(days, 0.0, payouts)
    print(f"  funded MFFU Builder 50K on 2026 (Jan 2 - Oct 16): {len(traded)} trades, net ${sum(days.values()):,.0f}, "
          f"{len(pay_rows)} payouts ${paid:,.0f} (80% to you: ${paid * 0.8:,.0f}, ~${paid * 0.8 / n_months:,.0f}/mo), "
          f"first {pay_rows[0]['day'] if pay_rows else '-'}, max risk ${max(x['risk_usd'] for x in traded):,.0f}, "
          f"median micros {sorted(x['q'] for x in traded)[len(traded) // 2]}, end balance ${50000 + end['balance']:,.0f} "
          f"room ${end['room']:,.0f}", flush=True)
    for p in pay_rows:
        print(f"    payout {p['day']}: ${p['amount']:,.0f} (cycle ${p['cycle_profit']:,.0f} over {p['cycle_days']} days, best day "
              f"${p['best_day']:,.0f})", flush=True)


def main():
    tmp = tempfile.mkdtemp(prefix="le_evallife_")
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    try:
        sizing_checks()
        view_checks()
        bot_checks(tmp)
        if "--quick" not in sys.argv:
            funded_2026()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RESULTS), sum(RESULTS)
    print(f"eval lifecycle: {ok}/{n} {'ALL PASS' if ok == n else 'FAILURES'}")
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    main()
