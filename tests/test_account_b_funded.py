"""ATLAS's funded account (engine/account_b.py stage "funded", 2026-10-26): the switch, the funded sizing and limits, the
payout tracker, the views (heartbeat / ATLAS page / live board / Goals / Start page) and one LiveBot day on a fake Sim
account. Sim / paper / temp files only: nothing is armed, no payout is requested, the real data/ and config are never
written (checked at the end).

    python -X utf8 -m tests.test_account_b_funded            # everything (~5 min: one LiveBot day)
    python -X utf8 -m tests.test_account_b_funded --quick    # without the LiveBot day (~1 min)

 a. the eval is unchanged until the switch: an eval block (no "stage") sizes, views and saves exactly as before (no funded
    keys anywhere), the pass push says "run the funded switch", a pass never switches by itself (no config write in
    AccountB);
 b. the block: stage funded needs a valid funded_start / balance / payouts (else a problem = not traded);
 c. funded sizing = engine/sizing.funded_qty on the 25K funded preset (60% of the room, <= $750 a trade, a winner <= $1,000,
    the $600 soft daily loss, 20 micros, skip when 1 micro could reach the floor); lost -> 0; weights never raise it;
 d. the funded state + tracker on an AccountB: balance / floor / room, the balance before the bot, the floor at start + $100
    after the first payout, buffer, 50% consistency, eligibility, payouts n of 5; lost / stuck / graduated stop new
    entries; the pushes (PAYOUT READY with the account_b record line, consistency, lost, stuck) each once;
 e. the switch: python -m engine.account_b --to-funded (refusals, disarmed, eval history kept, allowlist, re-run, the
    funded stage kept by arm_b / set_account_b), --payout, --funded-status;
 f. the Start page (engine/go.py): ATLAS's "Passed → funded" switches account B (not a Zlarior extra account), the saved
    ATLAS Name follows, the row says funded;
 g. views: info() / heartbeat block, live board (engine/live_board.atlas_now + boardcore.js node render), ATLAS page
    (secondcore.js acctB node render), Goals, scale plan;
 h. one LiveBot day (2026-10-02) with ATLAS funded on a fake Sim103 next to LIT on Sim101: every B entry sized by the
    funded rule on B's funded state, routed to Sim103, LIT unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from engine import account_b as AB  # noqa: E402
# 2026-11-20 lead: the owner said YES to room 40% + 1 micro after 2 losses (engine/account_b FUNDED_ON, ON in the repo). This suite
# pins the BASE 25K funded rule (60%), so it runs with the switches OFF; the ON behaviour has its own suite
# (tests/test_atlas_funded_switches.py) and the last check here (f. owner YES) proves the repo default end to end.
FUNDED_ON_REPO = dict(AB.FUNDED_ON)
AB.FUNDED_ON.update(funded_room_pct=None, streak_shrink=None)
from engine import funded_life as FL  # noqa: E402
from engine import live  # noqa: E402
from engine import multi_account as MA  # noqa: E402
from engine import second  # noqa: E402
from engine import sizing as SZ  # noqa: E402

RESULTS = []
KEYS = ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]
EVAL_NAME, FUND_NAME, LIT_NAME = "MFFUEVBLD25KTEST", "MFFUSFBLD25KTEST", "MFFUEVBLD50KTEST"
P25 = MA.PRESETS["mffu_builder_25k"]["sizing"]["funded"]
A25 = {"mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20}


def check(name, ok, info=""):
    RESULTS.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(info)[:400]})" if info and not ok else ""), flush=True)
    return bool(ok)


class FakeBot:
    def __init__(self, now, state=None):
        self._now = now
        self.state = state or {}
        self.ledger = []
        self._open_routed = None
        self.accts = None
        self.cfg = {"adapter": "paper", "sym": "NQ"}
        self.health = {}
        self.kill = False
        self.state_path = None
        self.logs = []
        self.pushed = []

    def clock(self):
        return self._now

    def _log(self, kind, text, **kw):
        self.logs.append((kind, text))

    def _note_error(self, text):
        self.logs.append(("error", text))

    def _push_send(self, p):
        self.pushed.append(p)


def ts(day, hh=9, mm=0):
    import datetime as dt
    from zoneinfo import ZoneInfo
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hh, mm), ZoneInfo("America/New_York")).timestamp())


def eval_block(name=EVAL_NAME, start="2026-10-26", **kw):
    return {"account": name, "plan": "builder25k", "eval_start": start, "strategies": list(KEYS), "sizing": "need", **kw}


def funded_block(name=FUND_NAME, start="2026-11-09", **kw):
    return {**eval_block(name), "stage": "funded", "funded_start": start, "funded_balance": 25000.0, "payouts": {},
            "eval_account": EVAL_NAME, **kw}


def acct(spec, now, tmp, closes=(), tag="b"):
    fb = FakeBot(now)
    B = AB.AccountB(fb, spec, state_path=os.path.join(tmp, f"{tag}_state.json"))
    B.adapter = live.PaperAdapter({})
    B.closes = [list(c) for c in closes]
    return B, fb


def want_funded(risk, tgt, st):
    """The funded rule recomputed from engine/sizing.funded_qty + the soft daily loss guard (independent of account_b)."""
    q = SZ.funded_qty({"risk_pts": risk, "tgt_pts": tgt, "size_mult": 1.0}, dict(st), P25, acct=A25)
    return int(AB.dll_guard({"qty": min(20, q), "reasons": []}, risk, MA.rules_of({"preset": "mffu_builder_25k"}), st)["qty"])


# ------------------------------------------------------------------------------------------------ a. the eval unchanged
def eval_checks(tmp):
    print("a. the eval until the switch", flush=True)
    sc = second.load_cfg()
    e = AB.normalize(eval_block(), sc)
    e2 = AB.normalize({**eval_block(), "funded_start": "2026-11-09", "payouts": {"2026-11-20": 500}}, sc)   # stray keys, no stage
    check("a. an eval block (no stage) is stage eval, no funded part, plan label unchanged",
          e["problem"] is None and e["stage"] == "eval" and "funded" not in e and e["plan_label"] == "MFFU Builder 25K"
          and not AB.is_funded(e) and not AB.is_funded(e2), e)
    st = lambda room, prof=0.0, cum=0.0, sess=1: {"profit": prof, "cum": cum, "room": room, "session": sess, "n_today": 0, "days_traded": 0}
    grid_same = all(AB.qty(e, {"risk_pts": r, "tgt_pts": 2 * r}, st(room, cum=cum, sess=s_))["qty"]
                    == AB.qty(e2, {"risk_pts": r, "tgt_pts": 2 * r}, st(room, cum=cum, sess=s_))["qty"]
                    for r in (6.0, 15.0, 40.0) for room in (150.0, 900.0, 1600.0) for cum in (-300.0, 0.0) for s_ in (1, 11))
    q = AB.qty(e, {"risk_pts": 10.0, "tgt_pts": 15.0}, st(1000.0))
    # 17 (was 20): live is "eval two_week room_f 0.4" (CLAUDE.md owner-approved sizing; engine/multi_account two_week room_f
    # 0.4, was 0.5): 40% of the $1,000 room / (10 pts x $2 + costs) = 17 micros. Same checks, the expected number only.
    check(f"a. eval sizing as before (25K need, 10-pt stop: 17 micros at room_f 0.4; funded keys without a stage change nothing) "
          f"-> {q['qty']}",
          q["qty"] == 17 and grid_same and not any("funded" in x for x in q["reasons"]), q)
    now = ts("2026-10-28", 9)
    B, fb = acct(e, now, tmp, closes=[["2026-10-26", now - 2 * 86400, 900.0, now - 2 * 86400 - 600],
                                      ["2026-10-27", now - 86400, 650.0, now - 86400 - 600]], tag="ev")
    info, blob, ev = B.info(now), B.blob(), B.eval_view(now)
    check("a. eval info / blob / view carry no funded keys (heartbeat as before)",
          "stage" not in info and "funded" not in info and "stage" not in blob and "funded_start" not in blob
          and "funded" not in ev and ev["status"] == "passed", (list(info), list(blob), ev.get("status")))
    B._lifecycle(now)
    B._lifecycle(now)
    t = [p["title"] for p in fb.pushed]
    body = fb.pushed[0]["body"] if fb.pushed else ""
    check("a. pass: one 'EVAL PASSED' push (title unchanged) that says run the funded switch; the bot never switches itself",
          t == [f"ATLAS {EVAL_NAME} EVAL PASSED \U0001F389"] and "funded switch" in body and "--to-funded" in body
          and "never switches" in body, (t, body))
    src = open(os.path.join(ROOT, "engine", "account_b.py"), encoding="utf-8").read()
    cls = src[src.index("class AccountB"):src.index("def _state_path_for")]
    check("a. AccountB itself never writes the block (no write_local / set_account_b / to_funded inside the class)",
          "write_local(" not in cls and "set_account_b(" not in cls and "to_funded(" not in cls)
    r = AB.qty(e, {"risk_pts": 20.0, "tgt_pts": 40.0}, {**st(1500.0, prof=1500.0), "days_traded": 3})
    check("a. a passed eval sizes 0 (pass lock) until the owner's switch", r["qty"] == 0, r)


# ------------------------------------------------------------------------------------------------ b. the block
def block_checks():
    print("b. the funded block", flush=True)
    sc = second.load_cfg()
    s = AB.normalize(funded_block(), sc)
    check("b. a funded block: no problem, stage funded, the funded part, label 'MFFU Builder 25K funded'",
          s["problem"] is None and AB.is_funded(s) and s["funded"]["start"] == "2026-11-09" and s["funded"]["balance"] == 25000.0
          and s["funded"]["prior"] == 0.0 and s["funded"]["eval_account"] == EVAL_NAME and s["plan_label"] == "MFFU Builder 25K funded", s)
    p = lambda **kw: (AB.normalize(funded_block(**kw), sc) or {}).get("problem")
    check("b. refused: no / bad funded_start, a balance not a 25K's ($0, $50,000, at the floor), a bad payout, a payout before "
          "the start, an unknown stage",
          p(start="") and p(start="11/09/2026") and p(funded_balance=0) and p(funded_balance=50000) and p(funded_balance=24000)
          and p(payouts={"2026-11-20": -5}) and p(payouts={"x": 500}) and p(payouts={"2026-11-01": 500}) and p(stage="live"),
          [p(start=""), p(funded_balance=0), p(payouts={"2026-11-01": 500}), p(stage="live")])
    s3 = AB.normalize(funded_block(funded_balance=25300.0, payouts={"2026-11-20": 900, "2026-11-12": 400.0}), sc)
    check("b. the balance before the bot = prior ($25,300 -> +$300); payouts sorted", s3["problem"] is None and s3["funded"]["prior"] == 300.0
          and list(s3["funded"]["payouts"]) == ["2026-11-12", "2026-11-20"], s3["funded"])


# ------------------------------------------------------------------------------------------------ c. sizing
def owner_yes_checks():
    """f. the repo default after the owner's YES (2026-11-20): room 40% + 1 micro after 2 losses, on the Builder 25K funded account."""
    print("f. owner YES (repo default ON)", flush=True)
    keep = dict(AB.FUNDED_ON)
    try:
        AB.FUNDED_ON.update(FUNDED_ON_REPO)
        check("f. the repo ships room 40% + 1 micro after 2 losses ON", FUNDED_ON_REPO == {"funded_room_pct": 0.4, "streak_shrink": 2}, FUNDED_ON_REPO)
        s = AB.normalize(funded_block(), second.load_cfg())
        f0 = {"room": 1000.0, "cum": 0.0, "locked": False, "loss_streak": 0}
        q = AB.qty(s, {"risk_pts": 40.0, "tgt_pts": 60.0}, f0)
        check(f"f. fresh room $1,000 x 40% = $400, 40-pt stop -> 2 micros (was 3 at 60%) ({q['qty']})", q["qty"] == 2 and q["lock"] is None
              and any("40% of $1,000 room" in x for x in q["reasons"]), q)
        q2 = AB.qty(s, {"risk_pts": 10.0, "tgt_pts": 30.0}, {**f0, "loss_streak": 2})
        check(f"f. after 2 losses in a row: 1 micro until a winner ({q2['qty']})", q2["qty"] == 1 and any("loss streak" in x for x in q2["reasons"]), q2)
        b = AB.normalize(funded_block(funded_room_pct=None, streak_shrink=None), second.load_cfg())
        check("f. a null in the account block still turns both off for that account (3 micros at the 40-pt stop)",
              AB.qty(b, {"risk_pts": 40.0, "tgt_pts": 60.0}, f0)["qty"] == 3)
    finally:
        AB.FUNDED_ON.clear()
        AB.FUNDED_ON.update(keep)


def sizing_checks():
    print("c. funded sizing", flush=True)
    s = AB.normalize(funded_block(), second.load_cfg())
    f0 = {"room": 1000.0, "cum": 0.0, "locked": False}
    q = AB.qty(s, {"risk_pts": 40.0, "tgt_pts": 60.0}, f0)
    check(f"c. fresh room $1,000 x 60% = $600, 40-pt stop -> $300 -> 3 micros ({q['qty']})", q["qty"] == 3 and q["lock"] is None
          and any("60% of $1,000 room" in x for x in q["reasons"]), q)
    q = AB.qty(s, {"risk_pts": 10.0, "tgt_pts": 30.0}, f0)
    check(f"c. a winner <= $1,000: 10-pt stop, 30-pt target -> 17 micros (1000 / 58.1), not 30 ({q['qty']})", q["qty"] == 17, q)
    q = AB.qty(s, {"risk_pts": 6.0, "tgt_pts": 12.0}, {"room": 5000.0, "cum": 0.0, "locked": True})
    check(f"c. never above 20 micros (6-pt stop, room $5,000) -> {q['qty']}", q["qty"] == 20, q)
    q = AB.qty(s, {"risk_pts": 60.0, "tgt_pts": 120.0}, {"room": 100.0, "cum": 0.0, "locked": True})
    check("c. room $100, 60-pt stop: 1 micro could reach the floor -> no trade", q["qty"] == 0, q)
    q = AB.qty(s, {"risk_pts": 20.0, "tgt_pts": 40.0}, {"room": -5.0, "cum": 0.0, "locked": True})
    check("c. room <= 0 (lost) -> 0, lock 'lost'", q["qty"] == 0 and q["lock"] == "lost", q)
    check("c. no state / no stop -> 0 (fails closed)", AB.qty(s, {"risk_pts": 20.0, "tgt_pts": 40.0}, None)["qty"] == 0
          and AB.qty(s, {"risk_pts": 0.0, "tgt_pts": 40.0}, f0)["qty"] == 0)
    bad, n = [], 0
    for risk in (4.0, 8.0, 15.0, 20.0, 25.0, 40.0, 70.0, 120.0, 250.0):
        for tgt in (12.0, 30.0, 80.0, 200.0, 500.0):
            for room in (50.0, 150.0, 400.0, 900.0, 1000.0, 1800.0, 3500.0):
                for cum in (0.0, -300.0, -520.0, 400.0):
                    st = {"room": room, "cum": cum, "locked": room > 1100}
                    got = AB.qty(s, {"risk_pts": risk, "tgt_pts": tgt}, st)["qty"]
                    n += 1
                    loss = got * ((risk + 0.5) * 2.0 + 1.90)
                    win = got * (tgt * 2.0 - 1.90)
                    if got != want_funded(risk, tgt, st) or (got and not (got * risk * 2.0 <= 750 + 1e-6 and loss < room and loss <= 600 + cum + 1e-6
                                                                          and got <= 20 and (got == 1 or win <= 1000 + 1e-6))):
                        bad.append((risk, tgt, room, cum, got, want_funded(risk, tgt, st)))
    check(f"c. {n} states: = engine/sizing.funded_qty on the 25K preset; the risk at the stop <= $750; a full stop-out (stop + "
          "2 ticks, $1.90) < the room and <= the $600 soft daily loss left; a 2+ micro winner <= $1,000; <= 20 micros", not bad, bad[:4])
    sw = AB.normalize(funded_block(weights={"ema_lon_vix": 2.0, "sr_nyreclaim": 0.5}), second.load_cfg())
    a = AB.qty(sw, {"risk_pts": 40.0, "tgt_pts": 60.0}, f0, key="ema_lon_vix")["qty"]
    b = AB.qty(sw, {"risk_pts": 40.0, "tgt_pts": 60.0}, f0, key="sr_nyreclaim")["qty"]
    check(f"c. member weights (ATLAS v2 knob, off by default) never raise the funded size: x2 -> {a} (cap 3), x0.5 -> {b}", a == 3 and b == 1, (a, b))
    cfg = AB.funded_cfg(s)
    check("c. funded cfg = the 25K preset's funded rule + the 25K's $ limits (no scale)",
          all(cfg["funded"][k] == v for k, v in P25.items()) and cfg["acct"]["dll"] == 600.0 and cfg["acct"]["mll"] == 1000.0
          and cfg["acct"]["max_micros"] == 20 and cfg["funded"]["pct_max_usd"] == 750 and cfg["funded"]["max_win"] == 1000, cfg)


# ------------------------------------------------------------------------------------------------ d. state + tracker
def tracker_checks(tmp):
    print("d. funded state, tracker, stops, pushes", flush=True)
    sc = second.load_cfg()
    s = AB.normalize(funded_block(), sc)
    now = ts("2026-11-09", 9)
    B, fb = acct(s, now, tmp, tag="f0")
    ev = B.eval_view(now)
    # owner's plan (CLAUDE.md, engine/funded_life ask_above): the first request is the MAX $1,000 once $2,100 profit is on the
    # account (buffer $1,100 + $1,000), so the payout line of a $25,000 funded account is $27,100 (was $26,850 = buffer + $750)
    check("d. fresh funded 25K: balance $25,000, floor $24,000, room $1,000, payout line $27,100, status funded, session 1",
          ev["stage"] == "funded" and ev["balance"] == 25000 and ev["floor"] == 24000 and ev["room"] == 1000 and ev["target"] == 27100
          and ev["status"] == "funded" and ev["session"] == 1 and ev["funded"]["payouts_max"] == 5, ev)
    st = B.eval_state(now)
    q = AB.qty(B.spec, {"risk_pts": 40.0, "tgt_pts": 60.0}, st)
    check("d. the bot's state sizes with the funded rule (3 micros at a 40-pt stop)", q["qty"] == 3 and st["room"] == 1000.0, (st, q))
    days = [("2026-11-09", 600.0), ("2026-11-10", 500.0), ("2026-11-11", 500.0), ("2026-11-12", 500.0)]
    cl = [[d, ts(d, 10), v, ts(d, 9, 30)] for d, v in days]
    now = ts("2026-11-12", 16, 30)
    B, fb = acct(s, now, tmp, closes=cl, tag="f1")
    ev = B.eval_view(now)
    t = ev["funded"]
    check("d. +$2,100 over 4 days: balance $27,100, floor locked at $25,100, buffer reached, best day 29%, PAYOUT READY $1,000 "
          "($800 to you)", ev["balance"] == 27100 and ev["floor"] == 25100 and t["buffer_reached"] and t["status"] == "ready"
          and t["max_request"] == 1000 and t["to_you"] == 800 and abs(t["best_day_pct"] - 600 / 21) < 0.1 and t["eligible"], (ev, t))
    old_pa = os.environ.get("LE_PAYOUT_AUTOPILOT")
    os.environ["LE_PAYOUT_AUTOPILOT"] = "0"      # the bot's own push (with the autopilot on, engine/payout_autopilot sends the one alert)
    try:
        B._lifecycle(now)
        B._lifecycle(now)
    finally:
        if old_pa is None:
            os.environ.pop("LE_PAYOUT_AUTOPILOT", None)
        else:
            os.environ["LE_PAYOUT_AUTOPILOT"] = old_pa
    P = [p for p in fb.pushed]
    check("d. ONE 'PAYOUT READY: request $1,000' push with the account_b record line; the bot never requests it",
          len(P) == 1 and P[0]["title"] == "PAYOUT READY: request $1,000"
          and "python -X utf8 -m engine.account_b --payout 2026-11-12=1000" in P[0]["body"] and "never requests" in P[0]["body"], P)
    s2 = AB.normalize(funded_block(payouts={"2026-11-12": 1000.0}), sc)
    B2, fb2 = acct(s2, ts("2026-11-13", 9), tmp, closes=cl, tag="f2")
    ev2 = B2.eval_view(ts("2026-11-13", 9))
    check("d. after the $1,000 payout: balance $26,100, floor $25,100 (start + $100), room $1,000, payouts 1/5, a new cycle",
          ev2["balance"] == 26100 and ev2["floor"] == 25100 and ev2["room"] == 1000 and ev2["funded"]["payouts_n"] == 1
          and ev2["funded"]["cycle_profit"] == 0 and ev2["funded"]["paid_to_you"] == 800, ev2)
    big = [[d, ts(d, 10), v, ts(d, 9, 30)] for d, v in (("2026-11-09", 1500.0), ("2026-11-10", 200.0), ("2026-11-11", 150.0))]
    B3, fb3 = acct(s, ts("2026-11-11", 16, 30), tmp, closes=big, tag="f3")
    t3 = B3.funded_view(ts("2026-11-11", 16, 30))
    B3._lifecycle(ts("2026-11-11", 16, 30))
    check("d. one big day (81% of the cycle): consistency, not eligible (limits payouts, not trading), one consistency push; "
          "the next trade still sizes", t3["status"] == "consistency" and not t3["eligible"] and len(fb3.pushed) == 1
          and fb3.pushed[0]["title"].startswith("consistency: best day is 81%")
          and AB.qty(B3.spec, {"risk_pts": 20.0, "tgt_pts": 40.0}, B3.eval_state(ts("2026-11-11", 16, 30)))["qty"] > 0, (t3["status"], fb3.pushed))
    s4 = AB.normalize(funded_block(funded_balance=25300.0), sc)
    B4, _ = acct(s4, ts("2026-11-09", 9), tmp, tag="f4")
    ev4 = B4.eval_view(ts("2026-11-09", 9))
    check("d. funded_balance $25,300 (+$300 before the bot): balance $25,300, floor $24,300, room $1,000",
          ev4["balance"] == 25300 and ev4["floor"] == 24300 and ev4["room"] == 1000 and ev4["funded"]["balance"] == 25300, ev4)
    lost = [["2026-11-09", ts("2026-11-09", 10), -1000.0, ts("2026-11-09", 9, 30)]]
    B5, fb5 = acct(s, ts("2026-11-10", 9), tmp, closes=lost, tag="f5")
    ev5 = B5.eval_view(ts("2026-11-10", 9))
    B5._lifecycle(ts("2026-11-10", 9))
    check("d. -$1,000: lost (room 0), one 'FUNDED ACCOUNT LOST' push", ev5["status"] == "lost" and
          [p["title"] for p in fb5.pushed] == ["FUNDED ACCOUNT LOST"], (ev5.get("status"), [p["title"] for p in fb5.pushed]))
    stk = [["2026-11-09", ts("2026-11-09", 10), -950.0, ts("2026-11-09", 9, 30)]]
    B6, fb6 = acct(s, ts("2026-11-10", 9), tmp, closes=stk, tag="f6")
    ev6 = B6.eval_view(ts("2026-11-10", 9))
    B6._lifecycle(ts("2026-11-10", 9))
    B6._lifecycle(ts("2026-11-10", 9))
    check("d. -$950: stuck (room $50 < $100, as a funded extra account), one 'funded account stuck' push",
          ev6["status"] == "stuck" and len(fb6.pushed) == 1 and "funded account stuck" in fb6.pushed[0]["title"], (ev6.get("status"), fb6.pushed))
    pays = {f"2026-12-0{i}": 1000.0 for i in range(1, 6)}
    s7 = AB.normalize(funded_block(payouts=pays), sc)
    cl7 = [[f"2026-12-0{i}", ts(f"2026-12-0{i}", 10), 1100.0, ts(f"2026-12-0{i}", 9)] for i in range(1, 6)]
    B7, _ = acct(s7, ts("2026-12-07", 9), tmp, closes=cl7, tag="f7")
    ev7 = B7.eval_view(ts("2026-12-07", 9))
    check("d. 5 payouts: graduated ($4,000 to you), MFFU moves it to live", ev7["status"] == "graduated"
          and ev7["funded"]["paid_to_you"] == 4000, ev7)
    # entry blocked on lost / stuck / graduated (the account-level why_bar), at the eval's own code path
    for Bx, lab in ((B5, "lost"), (B6, "stuck"), (B7, "graduated")):
        ev_ = Bx.eval_view(Bx.clock())
        check(f"d. {lab}: no new entry on B (status in the stop list)", ev_["status"] in AB.STOP_STATUSES, ev_.get("status"))
    check("d. the funded stage books from its own closes (no NinjaTrader real-balance anchor / cap)", B._broker() is None)


# ------------------------------------------------------------------------------------------------ e. the switch
def tmp_copy(tmp, tag):
    d = os.path.join(tmp, tag)
    os.makedirs(os.path.join(d, "data"), exist_ok=True)
    p = os.path.join(d, "second_model.json")
    shutil.copy(second.CFG_PATH, p)
    return p, os.path.join(d, "data", "allow.json")


def switch_checks(tmp):
    print("e. the switch", flush=True)
    ok_st = lambda: (True, "PASS (fake)")
    p, allow = tmp_copy(tmp, "sw")
    raw0 = open(p, "rb").read()
    r0 = AB.to_funded(FUND_NAME, "2026-11-09", path=p, selftest=ok_st, allow_path=allow, lit_account=LIT_NAME)
    check("e. no account B yet: refused", not r0["ok"] and "no account" in r0["error"], r0)
    AB.write_local({**eval_block(), "armed": True, "prior_pnl": -20.0, "eval_anchor": {"as_of": "2026-10-27", "balance": 24990.0,
                                                                                         "floor": 23990.0}}, p)
    sp = AB.state_file(p)
    json.dump({"account": EVAL_NAME, "closes": [["2026-10-26", 1, 900.0, 0], ["2026-10-27", 2, 650.0, 0]], "ledger": []}, open(sp, "w"))
    refusals = {
        "the eval's own Name": AB.to_funded(EVAL_NAME, "2026-11-09", path=p, selftest=ok_st, allow_path=allow, lit_account=LIT_NAME),
        "LIT's account": AB.to_funded(LIT_NAME, "2026-11-09", path=p, selftest=ok_st, allow_path=allow, lit_account=LIT_NAME),
        "a bad day": AB.to_funded(FUND_NAME, "9 Nov", path=p, selftest=ok_st, allow_path=allow, lit_account=LIT_NAME),
        "a $0 balance": AB.to_funded(FUND_NAME, "2026-11-09", 0, path=p, selftest=ok_st, allow_path=allow, lit_account=LIT_NAME),
        "a bad name": AB.to_funded("A;B", "2026-11-09", path=p, selftest=ok_st, allow_path=allow, lit_account=LIT_NAME),
        "the self-test failing": AB.to_funded(FUND_NAME, "2026-11-09", path=p, selftest=lambda: (False, "FAIL (1/69)"), allow_path=allow,
                                              lit_account=LIT_NAME)}
    blk0 = AB.raw_cfg(p)
    check("e. refused (nothing written): " + ", ".join(refusals), all(not r["ok"] for r in refusals.values())
          and blk0.get("account") == EVAL_NAME and "stage" not in blk0 and not os.path.exists(allow), {k: v.get("error") for k, v in refusals.items()})
    r = AB.to_funded(FUND_NAME, "2026-11-09", path=p, selftest=ok_st, allow_path=allow, lit_account=LIT_NAME, today="2026-11-06")
    b = AB.raw_cfg(p) or {}
    check("e. --to-funded: the local block = funded on the NEW Name from its day, DISARMED (armed, the eval's anchor and prior "
          "dropped), strategies / plan / sizing kept, the passed eval's Name kept",
          r["ok"] and b.get("account") == FUND_NAME and b.get("stage") == "funded" and b.get("funded_start") == "2026-11-09"
          and b.get("funded_balance") == 25000.0 and b.get("payouts") == {} and b.get("eval_account") == EVAL_NAME
          and "armed" not in b and "eval_anchor" not in b and "prior_pnl" not in b and b.get("strategies") == KEYS
          and b.get("plan") == "builder25k" and b.get("funded_set") == "2026-11-06" and r["sim"] is False, (r, b))
    from engine.ninjatrader import allowed_accounts
    arch = os.path.join(os.path.dirname(sp), f"live_state_acctb.eval_{EVAL_NAME}.json")
    check("e. the funded Name is on the (temp) allowlist; the eval's state file kept as live_state_acctb.eval_<Name>.json; "
          "second_model.json untouched", FUND_NAME in allowed_accounts(allow) and r["archived"] == arch and os.path.exists(arch)
          and json.load(open(arch))["account"] == EVAL_NAME and open(p, "rb").read() == raw0, (r.get("archived"), allowed_accounts(allow)))
    check("e. the switch says the funded rule and NOT armed", "60%" in r["rule"] and "$750" in r["rule"] and "$1,000" in r["rule"]
          and "NOT armed" in r["say"], r)
    r2 = AB.to_funded("MFFUSFOTHER", "2026-11-09", path=p, selftest=ok_st, allow_path=allow, lit_account=LIT_NAME)
    check("e. already funded on a Name: another funded Name refused", not r2["ok"] and "already funded" in r2["error"], r2)
    rp = AB.record_payout("2026-11-20=900", path=p)
    r3 = AB.to_funded(FUND_NAME, "2026-11-10", 25050, path=p, selftest=ok_st, allow_path=allow, lit_account=LIT_NAME)
    b3 = AB.raw_cfg(p) or {}
    check("e. --payout recorded; re-running the switch on the same funded Name updates start / balance and keeps the payouts "
          "and the eval Name", rp["ok"] and r3["ok"] and b3.get("funded_start") == "2026-11-10" and b3.get("funded_balance") == 25050.0
          and b3.get("payouts") == {"2026-11-20": 900.0} and b3.get("eval_account") == EVAL_NAME, (rp, r3, b3))
    bad = [AB.record_payout(x, path=p) for x in ("2026-11-20", "x=5", "2026-11-21=-4", "2026-11-01=500")]
    check("e. --payout refused: no amount, a bad day, a negative $, a day before the funded start", all(not x["ok"] for x in bad),
          [x.get("error") for x in bad])
    note = AB.record_payout("2026-11-25=1500", path=p)
    check("e. a payout above MFFU's $1,000 request max is recorded with a note", note["ok"] and note.get("note"), note)
    AB.write_local({**(AB.raw_cfg(p) or {}), "payouts": {"2026-11-20": 900.0}}, p)
    from engine import go as G
    keep = G.SECOND_PATH
    try:
        G.SECOND_PATH = p
        ra = G.arm_b(FUND_NAME, path=p, selftest=ok_st)
    finally:
        G.SECOND_PATH = keep
    ba = AB.raw_cfg(p) or {}
    check("e. arming the funded account (the Start page's typed phrase -> engine/go.arm_b) keeps the funded stage",
          ra.get("ok") and ba.get("armed") is True and ba.get("stage") == "funded" and ba.get("funded_start") == "2026-11-10"
          and ba.get("payouts") == {"2026-11-20": 900.0}, (ra, ba))
    rl = AB.set_account_b(FUND_NAME, plan="builder25k", start="2026-10-26", path=p, selftest=ok_st)     # what launch prep does
    bl = AB.raw_cfg(p) or {}
    check("e. set_account_b on the same funded Name (launch prep) keeps the funded stage (never back to an eval)",
          rl["ok"] and bl.get("stage") == "funded" and bl.get("eval_account") == EVAL_NAME, bl)
    json.dump({"account": FUND_NAME, "closes": [["2026-11-10", 1, 400.0, 0], ["2026-11-11", 2, 300.0, 0]]}, open(sp, "w"))
    fs = AB.funded_status(path=p, today="2026-11-12")
    check("e. --funded-status: the tracker from the block and B's state file (+$50 before the bot, +$700, $900 paid)",
          fs["ok"] and fs["account"] == FUND_NAME and fs["tracker"]["payouts_n"] == 1 and fs["tracker"]["balance"] == 25000 + 50 + 700 - 900, fs)
    off = AB.set_account_b("off", path=p)
    check("e. --account-b off still turns ATLAS off", off["ok"] and AB.raw_cfg(p) is None)
    # the CLI on temp paths (second.CFG_PATH / the allowlist / the self-test pointed at temp copies)
    p2, allow2 = tmp_copy(tmp, "cli")
    AB.write_local(eval_block(), p2)
    from engine import ninjatrader as NT
    keep = (second.CFG_PATH, NT.ALLOW_PATH, second._selftest_ok, AB._lit_name)
    try:
        second.CFG_PATH, NT.ALLOW_PATH = p2, allow2
        second._selftest_ok = lambda timeout=600: (True, "PASS (fake)")
        AB._lit_name = lambda: LIT_NAME
        rc = AB.main(["--to-funded", "--account", FUND_NAME, "--start", "2026-11-09", "--balance", "25000"])
        rc2 = AB.main(["--payout", "2026-11-20=800"])
        rc3 = AB.main(["--funded-status"])
        rc4 = AB.main(["--to-funded", "--account", FUND_NAME])
    finally:
        second.CFG_PATH, NT.ALLOW_PATH, second._selftest_ok, AB._lit_name = keep
    bc = AB.raw_cfg(p2) or {}
    check("e. CLI: python -m engine.account_b --to-funded / --payout / --funded-status (temp files); --start missing refused",
          rc == 0 and rc2 == 0 and rc3 == 0 and rc4 == 1 and bc.get("stage") == "funded" and bc.get("payouts") == {"2026-11-20": 800.0}
          and FUND_NAME in allowed_accounts(allow2), (rc, rc2, rc3, rc4, bc))


# ------------------------------------------------------------------------------------------------ f. the Start page
def start_page_checks(tmp):
    print("f. the Start page (engine/go.py)", flush=True)
    from engine import go as G
    d = os.path.join(tmp, "go")
    os.makedirs(os.path.join(d, "data"), exist_ok=True)
    keep = {k: getattr(G, k) for k in ("CFG", "SECOND_PATH", "ALLOW_PATH", "ACCOUNTS_PATH", "ANCHOR_PATH", "bot_running", "nt_balances",
                                        "nt_names")}
    keep_st = second._selftest_ok
    try:
        G.CFG = os.path.join(d, "data", "start_bot.json")
        G.SECOND_PATH = os.path.join(d, "second_model.json")
        shutil.copy(second.CFG_PATH, G.SECOND_PATH)
        G.ALLOW_PATH = os.path.join(d, "data", "allow.json")
        G.ACCOUNTS_PATH = os.path.join(d, "data", "accounts.json")
        G.ANCHOR_PATH = os.path.join(d, "data", "eval_anchor.json")
        G.bot_running = lambda: False
        G.nt_balances = lambda: {}
        G.nt_names = lambda folder=None: []
        second._selftest_ok = lambda timeout=600: (True, "PASS (fake)")
        G._save({"lit": LIT_NAME, "atlas": EVAL_NAME, "prepped": "2026-10-26"}, G.CFG)
        AB.write_local({**eval_block(), "armed": True}, G.SECOND_PATH)
        G._allow(LIT_NAME)
        G._allow(EVAL_NAME)
        rows = {r["name"]: r for r in G.accounts()["rows"]}
        check("f. accounts: ATLAS's 25K is an eval row (the 'Passed → funded' button shows for it)",
              rows.get(EVAL_NAME, {}).get("state") == "eval" and rows[EVAL_NAME]["role"] == "b", rows)
        bad1 = G.to_funded(EVAL_NAME, LIT_NAME, "2026-11-09")
        bad2 = G.to_funded(EVAL_NAME, EVAL_NAME, "2026-11-09")
        bad3 = G.to_funded(EVAL_NAME, "Sim101", "2026-11-09")
        check("f. refused: the 50K's Name, the eval's own Name, a Sim account", not bad1["ok"] and not bad2["ok"] and not bad3["ok"],
              (bad1, bad2, bad3))
        r = G.to_funded(EVAL_NAME, FUND_NAME, "2026-11-09")
        b = AB.raw_cfg(G.SECOND_PATH) or {}
        cfg = G._read(G.CFG)
        ex = MA.load_file(G.ACCOUNTS_PATH)
        check("f. 'Passed → funded' on ATLAS's row switches ACCOUNT B (data/account_b.json funded, disarmed), not a Zlarior "
              "extra account; the saved ATLAS Name follows; setup stays done; allowlisted",
              r["ok"] and b.get("stage") == "funded" and b.get("account") == FUND_NAME and "armed" not in b and not ex
              and cfg.get("atlas") == FUND_NAME and cfg.get("prepped") == "2026-10-26" and FUND_NAME in G._allowed()
              and "Not armed" in r["say"], (r, b, cfg, ex))
        rows = {r_["name"]: r_ for r_ in G.accounts()["rows"]}
        fr = rows.get(FUND_NAME, {})
        check("f. accounts: the row says funded (MFFU Builder 25K funded, from its first funded day, passed eval noted, not armed)",
              fr.get("state") == "funded" and fr.get("plan_label") == "MFFU Builder 25K funded" and fr.get("start") == "2026-11-09"
              and EVAL_NAME in (fr.get("note") or "") and fr.get("armed") is False and fr.get("bot") == "ATLAS", fr)
        again = G.to_funded(FUND_NAME, "MFFUSFX", "2026-11-09")
        check("f. a funded row has no 'Passed → funded' (refused)", not again["ok"], again)
        miss = G.setup_missing()
        st = G.status(state={}, connected=lambda: True, feed=lambda: None)
        arm = {s_["key"]: s_ for s_ in st["steps"]}["armed"]
        check("f. Start page: setup still done for the funded Name; 'Armed' is red until the owner types the phrase (25K not armed)",
              not miss and not arm["done"] and "25K not armed" in arm["detail"], (miss, arm))
    finally:
        for k, v in keep.items():
            setattr(G, k, v)
        second._selftest_ok = keep_st


# ------------------------------------------------------------------------------------------------ g. views
def view_checks(tmp):
    print("g. views: heartbeat, live board, ATLAS page, Goals, scale plan", flush=True)
    s = AB.normalize(funded_block(), second.load_cfg())
    cl = [[d, ts(d, 10), v, ts(d, 9, 30)] for d, v in (("2026-11-09", 600.0), ("2026-11-10", 500.0), ("2026-11-11", 400.0))]
    now = ts("2026-11-11", 16, 30)
    B, _ = acct(s, now, tmp, closes=cl, tag="v")
    info = B.info(now)
    check("g. info() (heartbeat second.route.account_b): stage funded, sizing funded, the compact tracker, the passed eval",
          info.get("stage") == "funded" and info.get("sizing") == "funded" and isinstance(info.get("funded"), dict)
          and info["funded"].get("ask_at_balance") == 27100 and "funded" not in info["eval"] and info["eval"]["status"] == "funded"
          and info.get("eval_account") == EVAL_NAME and len(json.dumps(info)) < 6000, {k: info.get(k) for k in ("stage", "sizing")})
    cp = second.compact({"t": 1, "day": "2026-11-11", "strategies": {k: {"label": k, "short": k, "on": True, "trades": []} for k in KEYS}},
                        route={"keys": [], "account": None, "open": None, "routed": [], "account_b": info})
    check("g. second.compact keeps account_b's funded block (the heartbeat's second.route)",
          ((cp.get("route") or {}).get("account_b") or {}).get("stage") == "funded")
    from engine import live_board as LB
    a = LB.atlas_now({"second": {"route": {"account_b": info}, "strategies": {}}}, now)
    check("g. live board: ATLAS card stage funded, $ to the payout line, the tracker (buffer, best day, payouts), the funded size text",
          a.get("stage") == "funded" and a["target_balance"] == 27100 and a["to_target"] == 600 and a["funded"]["payouts_max"] == 5
          and a["funded"]["buffer_reached"] is True and "60% of the room" in a["micros"]["what"] and not a.get("blocks"), a)
    lost = B.info(now)
    lost["eval"] = {**lost["eval"], "status": "lost"}
    al = LB.atlas_now({"second": {"route": {"account_b": lost}, "strategies": {}}}, now)
    check("g. live board: a lost funded account shows a block with the plain fix", any("Funded account lost" in b_["text"] for b_ in al["blocks"]), al["blocks"])
    from engine import goals as GO
    g = GO._atlas_account({"second": {"route": {"account_b": info}}})
    pg = GO.payout_goal({"accounts": [], "second": {"route": {"account_b": info}}}, {})
    check("g. Goals: ATLAS's card is funded (the tracker's sentence), the payout goal reads ATLAS's tracker",
          g["stage"] == "funded" and g["sentence"] == info["funded"]["text"] and pg["stage"] == "funded" and pg["funded"] == 1
          and pg["ask_at"] == 27100, (g, pg))
    from engine import scale_plan as SP
    rows = SP.overlay([], acct_b=info)
    check("g. scale plan: ATLAS's row is funded", any(r_.get("strategy") == "ATLAS" and r_.get("stage") == "funded" for r_ in rows), rows)
    node = shutil.which("node")
    if not node:
        check("g. node render skipped (no node)", True)
        return
    B2 = {"lit": None, "atlas": a, "blocks": [], "trades": []}
    bp = os.path.join(tmp, "board.json")
    json.dump(B2, open(bp, "w"))
    js = r"""
global.window = global; global.setInterval = () => 0;
global.document = { getElementById: () => ({}), querySelectorAll: () => [], head: { appendChild() {} }, createElement: () => ({}) };
require(process.argv[1]);
const B = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const h = window.BoardUI.page(B, {});
console.log(JSON.stringify({ line: h.includes('payout line'), pays: h.includes('Payouts') && h.includes('0 of 5'), row: h.includes('bd-k">Payout<'),
  buf: h.includes('buffer reached'), sess: h.includes('goal: pass in 10') }));
"""
    r = subprocess.run([node, "-e", js, os.path.join(ROOT, "tools", "web_public", "boardcore.js"), bp], capture_output=True, text=True)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {"stderr": r.stderr[-400:]}
    check("g. boardcore.js node render (ATLAS funded): $ to the payout line, payouts 0 of 5, the Payout row, no eval session KPI",
          o.get("line") and o.get("pays") and o.get("row") and o.get("buf") and not o.get("sess"), o)
    sc = os.path.join(ROOT, "tools", "web_public", "secondcore.js")
    js2 = ("const fs=require('fs');const window={};const document={head:{appendChild(){}},getElementById(){return null},"
           "createElement(){return {}}};global.window=window;global.document=document;"
           f"eval(fs.readFileSync({json.dumps(sc)},'utf8'));const U=window.SecondUI;const ab={json.dumps(info)};"
           "const h=U.acctB(ab);const S={strategies:[{key:'ema_lon_vix',short:'EMA'}],account_b:ab};const c=U.atlasCard(S,null,null);"
           "console.log(JSON.stringify({f:h.includes('Funded'),line:h.includes('Payout line'),buf:h.includes('Buffer'),cons:h.includes('50% rule'),"
           "pay:h.includes('0 of 5'),rec:h.includes('engine.account_b --payout'),never:h.includes('never requests'),prog:c.progText}));")
    r = subprocess.run([node, "-e", js2], capture_output=True, text=True)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {"stderr": r.stderr[-400:]}
    check("g. secondcore.js node render (ATLAS page): funded card with payout line, buffer, 50% rule, payouts 0 of 5, the record "
          "line, 'never requests'; Home card says FUNDED", all(o.get(k) for k in ("f", "line", "buf", "cons", "pay", "rec", "never"))
          and str(o.get("prog") or "").startswith("FUNDED"), o)
    a1 = open(os.path.join(ROOT, "tools", "web_public", "secondcore.js"), "rb").read() == open(os.path.join(ROOT, "web_next", "js", "next", "secondcore.js"), "rb").read()
    a2 = open(os.path.join(ROOT, "tools", "web_public", "boardcore.js"), "rb").read() == open(os.path.join(ROOT, "web_next", "js", "next", "boardcore.js"), "rb").read()
    sw = open(os.path.join(ROOT, "tools", "web_public", "sw.js"), encoding="utf-8").read()
    import re
    check("g. secondcore.js / boardcore.js byte-identical on both apps; phone cache bumped (le-public-v38+)",
          a1 and a2 and int(re.search(r"le-public-v(\d+)", sw).group(1)) >= 38)


# ------------------------------------------------------------------------------------------------ h. one LiveBot day
def bot_day():
    print("h. one LiveBot day: ATLAS funded on a fake Sim103 next to LIT on Sim101", flush=True)
    from tests import test_second_account_b as TB
    from tests.test_second_route import Harness, Ref, at
    ref = Ref()
    H = Harness(ref)
    H._fake = None
    TB.install_factory(H)
    calls = []
    real_qty = AB.qty

    def spy(spec, trade, state, base=None, key=None):
        r = real_qty(spec, trade, state, base=base, key=key)
        calls.append({"funded": AB.is_funded(spec), "trade": dict(trade), "state": dict(state or {}), "qty": int(r["qty"]), "key": key})
        return r
    AB.qty = spy
    day = "2026-10-02"
    try:
        ab = {"account": "Sim103", "plan": "builder25k", "eval_start": "2026-09-01", "strategies": list(KEYS), "sizing": "need",
              "stage": "funded", "funded_start": day, "funded_balance": 25000.0, "eval_account": "Sim102"}
        b, fake = TB.bot_b(H, "funded_" + day, at(day, 1, 45), ab)
        B = b.acct_b
        check("h. account B started funded on Sim103, no problem", B is not None and not B.disabled_reason() and B.funded(),
              B and B.disabled_reason())
        errors = []
        pos = TB.run(H, b, fake, TB.poll_times(H, day), errors)
        ents = [r for r in B.ledger if r.get("side") in ("buy", "sell")]
        sized = {c["state"].get("room"): c for c in calls}
        okq, rows = True, []
        for e in ents:
            c = next((c for c in reversed(calls) if c["key"] == e.get("src") and c["qty"] == int(e["qty"])), None)
            w = want_funded(float(c["trade"]["risk_pts"]), float(c["trade"]["tgt_pts"]), c["state"]) if c else None
            rows.append((e.get("src"), e.get("qty"), w, (c or {}).get("state", {}).get("room")))
            okq = okq and c is not None and c["funded"] and w == int(e["qty"])
        check(f"h. {day}: every B entry ({len(ents)}) sized by the funded rule on B's funded state (= engine/sizing.funded_qty "
              "on the 25K preset)", ents and okq and all(c["funded"] for c in calls), (rows, len(calls), sized and list(sized)[:3]))
        first = next((c for c in calls if c["funded"]), {})
        check("h. the first entry's state is the fresh funded account (room $1,000, today $0)",
              abs(float(first.get("state", {}).get("room", 0)) - 1000.0) < 1e-6 and float(first["state"].get("cum", 1)) == 0.0, first)
        acc = {a_ for (a_, _), (q, _x) in fake.pos.items()} | {a_ for a_, *_ in [f.split("_")[:1] for f, _ in fake.files]}
        lit = [r for r in b.ledger if r.get("side") in ("buy", "sell")]
        check(f"h. B's orders go to Sim103 (tag acctb_), LIT's {len(lit)} to Sim101 as run lit_live, never opposite at a poll, no error",
              any("acctb" in f.lower() for f, _ in fake.files) and len(lit) == len(ref.lit.get(day, []))
              and not [(w, p1, p2) for w, p1, p2 in pos if p1 * p2 < 0] and not errors
              and not [x["text"] for x in b.log if "account B failed" in x["text"]], (errors[:2], acc))
        info = (b.second_route_info() or {}).get("account_b") or {}
        ev = B.eval_view()
        check("h. after the day: the heartbeat block is funded, the day's closed P&L is in the funded balance / tracker",
              info.get("stage") == "funded" and info["eval"]["status"] in ("funded", "stuck", "lost")
              and abs(ev["balance"] - (25000.0 + sum(float(c[2]) for c in B.closes))) < 0.01
              and (info.get("funded") or {}).get("cycle_days", 0) == (1 if B.closes else 0), (info.get("eval"), B.closes))
    finally:
        AB.qty = real_qty
        AB.ADAPTER_FACTORY = None
        H.close()


def digest(paths):
    out = {}
    for p in paths:
        try:
            out[p] = hashlib.md5(open(p, "rb").read()).hexdigest()
        except FileNotFoundError:
            out[p] = None
    return out


def main():
    quick = "--quick" in sys.argv
    real = [os.path.join(ROOT, x) for x in ("second_model.json", "live_model.json", "live_model_lit.json", os.path.join("data", "account_b.json"),
                                             os.path.join("data", "nt_accounts_allow.json"), os.path.join("data", "accounts.json"),
                                             os.path.join("data", "start_bot.json"), os.path.join("data", "live_state_acctb.json"))]
    before = digest(real)
    tmp = tempfile.mkdtemp(prefix="le_acctb_funded_")
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    try:
        eval_checks(tmp)
        block_checks()
        sizing_checks()
        tracker_checks(tmp)
        switch_checks(tmp)
        start_page_checks(tmp)
        view_checks(tmp)
        owner_yes_checks()
        if not quick:
            bot_day()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    after = digest(real)
    check("the real second_model.json, live_model*.json and data/ files did not change", before == after,
          {p: (before[p], after[p]) for p in real if before[p] != after[p]})
    n, ok = len(RESULTS), sum(RESULTS)
    print(f"account B funded: {ok}/{n} {'ALL PASS' if ok == n else 'FAILURES'}")
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    main()
