"""Safety guards on the PC bot's order route (engine/guards.py, wired into engine/live.py). Offline: fake NinjaTrader
(engine/ninjatrader._FakeNT), stub adapters, no network, no real account.

    python -X utf8 -m tests.test_guards            # everything (~1 min: includes the 2026 LIT backtest, 120 trades)
    python -X utf8 -m tests.test_guards --quick    # without the 2026 proof

A. order sanity (pure): plan / 40 / account max / wrong-side stop / > 100 pts / < 1.5R / $ at risk.
B. calendar (pure): weekend, 17:00 break, CME full closures, before 02:00, at the flat time, CME early-close cutoff.
C. 2026 proof: every 2026 LIT trade (tools/lit_final.run on live_model.json "lit") passes order sanity + calendar at the
   routed tick prices; the two_week eval run's worst $ at risk is under max_risk_usd; default-off guards are off.
D. LiveBot route (stub adapter): an entry that fails sanity is NOT routed ("GUARD ..."), pushed; one entry a day and the
   same signal never twice, even after a restart with live_state.json gone; a NO TRADE flatten does not count; the daily
   loss; the clock drift (only on the real clock); the news minute (off by default, on when configured).
E. Room alarm: once below $800, once below $400.
F. Reconcile (fake NinjaTrader): an unknown position while the ledger is flat -> push + CLOSEPOSITION; a position the
   ledger has that NinjaTrader does not -> push only, after 6 min; matching -> nothing; 17:00 P&L reconcile.
G. Stale data: a stale 1m NinjaTrader file alone blocks entries (FEED STALE); a stale 1m-open file does not block (the
   entry is sized from the CISD close and checked once its fill bar closes); a fresh one is used.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import guards, live  # noqa: E402
from engine.ninjatrader import ET, NinjaTraderAdapter, _FakeNT, place_line  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:600]) if info and not ok else ''}", flush=True)
    RES.append(bool(ok))


def at(y, m, d, hh, mm, ss=0):
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


def act(side="buy", qty=5, entry=25000.0, stop=24970.0, target=25090.0):
    return {"sym": "NQ", "side": side, "qty": qty, "entry": entry, "stop": stop, "target": target, "entry_t": 0}


# ------------------------------------------------------------------------------------------------ A / B pure
def pure():
    check("A. a normal LIT order passes", guards.sanity(act(), 5, 40) == [])
    check("A. more micros than the sizing plan -> refused", any("sizing plan" in x for x in guards.sanity(act(qty=6), 5, 40)))
    check("A. more than 40 micros -> refused", any("40-micro cap" in x for x in guards.sanity(act(qty=41, stop=24995.0, target=25010.0), 41, 60)))
    check("A. more than the account's max -> refused", any("account's max" in x for x in guards.sanity(act(qty=6), 6, 5)))
    check("A. long with the stop above the entry -> refused", any("wrong side" in x for x in guards.sanity(act(stop=25010.0), 5, 40)))
    check("A. short with the stop below the entry -> refused",
          any("wrong side" in x for x in guards.sanity(act(side="sell", stop=24990.0, target=24900.0), 5, 40)))
    check("A. stop 101 pts away -> refused", any("101.0 pts" in x for x in guards.sanity(act(qty=1, stop=24899.0, target=25200.0), 1, 40)))
    check("A. stop exactly 100 pts away -> allowed", guards.sanity(act(qty=1, stop=24900.0, target=25150.0), 1, 40) == [])
    check("A. target 1.4R -> refused", any("1.40R" in x for x in guards.sanity(act(target=25042.0), 5, 40)))
    check("A. target exactly 1.5R -> allowed", guards.sanity(act(target=25045.0), 5, 40) == [])
    check("A. a 1.5R target rounded 1 tick toward the entry (1.49R) -> allowed (tick slack)",
          guards.sanity(act(target=25044.75), 5, 40) == [])
    check("A. the self-test's 1.35R target -> refused", any("1.35R" in x for x in guards.sanity(
        act(qty=3, stop=24970.25, target=25087.25, entry=25020.0), 3, 40)))
    check("A. $1,250 at risk -> refused", any("at risk" in x for x in guards.sanity(act(qty=20, stop=24969.0, target=25100.0), 20, 40)))
    check("A. missing stop -> refused", guards.sanity(act(stop=None), 5, 40) != [])
    # B. calendar (session_from 02:00, flat 15:55)
    cal = guards.calendar
    check("B. Thu 10:00 ET -> allowed", cal(at(2026, 10, 22, 10, 0), at(2026, 10, 22, 10, 0, 3)) == [])
    check("B. Saturday -> refused", cal(at(2026, 10, 24, 10, 0), at(2026, 10, 24, 10, 0)) != [])
    check("B. Sunday 17:30 ET (before the 18:00 open) -> refused", cal(at(2026, 10, 25, 17, 30), at(2026, 10, 25, 17, 30)) != [])
    check("B. 17:30 ET daily break -> refused", cal(at(2026, 10, 22, 17, 30), at(2026, 10, 22, 17, 30)) != [])
    check("B. 01:30 ET (before 02:00) -> refused", any("session start" in x for x in cal(at(2026, 10, 22, 1, 30), at(2026, 10, 22, 1, 30))))
    check("B. 15:55 ET (flat time) -> refused", any("cutoff 15:55" in x for x in cal(at(2026, 10, 22, 15, 55), at(2026, 10, 22, 15, 55))))
    check("B. Christmas 2026 (Fri) -> refused, CME holiday", any("holiday" in x for x in cal(at(2026, 12, 25, 10, 0), at(2026, 12, 25, 10, 0))))
    check("B. New Year 2027 (Fri) -> refused", any("holiday" in x for x in cal(at(2027, 1, 1, 10, 0), at(2027, 1, 1, 10, 0))))
    check("B. New Year 2023 fell on a Sunday: Mon 2023-01-02 refused", guards.full_closure("2023-01-02") and not guards.full_closure("2023-01-03"))
    check("B. Black Friday 2026-11-27 (13:15 halt): 12:55 allowed, 13:00 refused (15 min before)",
          cal(at(2026, 11, 27, 12, 55), at(2026, 11, 27, 12, 55)) == []
          and any("early close" in x for x in cal(at(2026, 11, 27, 13, 0), at(2026, 11, 27, 13, 0))))
    check("B. Thanksgiving 2026-11-26 (13:00 halt): 12:45 refused", any("early close" in x for x in cal(at(2026, 11, 26, 12, 45), at(2026, 11, 26, 12, 45))))
    ev = [{"t": at(2026, 11, 10, 8, 30), "event": "CPI (consumer inflation)", "impact": "high"}]
    check("news: 08:28:30 and 08:32 are inside 2 min of CPI, 08:27 and 08:33 are not",
          guards.news_hit(at(2026, 11, 10, 8, 28, 30), 2, ev) and guards.news_hit(at(2026, 11, 10, 8, 32), 2, ev)
          and not guards.news_hit(at(2026, 11, 10, 8, 27), 2, ev) and not guards.news_hit(at(2026, 11, 10, 8, 33), 2, ev))
    d = guards.DEFAULTS
    check("defaults: news OFF; order sanity, duplicates, room alarm, daily loss, reconcile (+ flatten), P&L reconcile, clock, calendar ON",
          d["news"] is False and all(d[k] for k in ("order_sanity", "dup_entry", "room_alarm", "daily_loss", "reconcile",
                                                    "reconcile_flatten", "pnl_reconcile", "clock", "calendar")))
    ev_csv = guards.news_hit(at(2026, 11, 10, 8, 31), 2)
    check("news: the Tier-1 calendar comes from data/news (CPI 2026-11-10 08:30)", ev_csv and "CPI" in ev_csv, ev_csv)


# ------------------------------------------------------------------------------------------------ C. 2026 proof
def proof_2026():
    from tools import lit_final as F
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    R = [t for t in F.run(P) if t["day"] >= "2026-01-01"]
    bad = []
    for t in R:
        d = int(t["dir"])
        a = {"side": "buy" if d == 1 else "sell", "qty": int(t["qty"]), "entry": t["entry_px"],
             "stop": live.tick_px(t["stop_px"], d), "target": live.tick_px(t["target_px"], d, target=True)}
        p = guards.sanity(a, int(t["qty"]), 40) + guards.calendar(int(t["entry_t"]), int(t["entry_t"]) + 3,
                                                                  session_from=int(P["window"][0][0]), flat_mod=955)
        if p:
            bad.append((t["day"], p))
    check(f"C. 2026: all {len(R)} LIT trades pass order sanity + calendar (0 would be blocked)", len(R) == 120 and not bad, bad[:5])
    worst = []
    for run in ("lit_live", "lit_adopt_t15_be_off_eval"):
        rr = json.load(open(os.path.join(ROOT, "research", "runs", f"{run}.json"), encoding="utf-8"))
        cols = rr["trade_cols"]
        rows = [dict(zip(cols, x)) for x in rr["trades"] if x[0] >= "2026"]
        worst.append(max(r["qty"] * (r["risk_pts"] * guards.PV + guards.COMM) for r in rows))
    check(f"C. worst 2026 $ at risk incl. costs: LIT rule ${worst[0]:,.0f}, two_week eval ${worst[1]:,.0f} < max_risk_usd "
          f"${guards.DEFAULTS['max_risk_usd']:,.0f}", max(worst) < guards.DEFAULTS["max_risk_usd"], worst)


# ------------------------------------------------------------------------------------------------ D. LiveBot route
class Stub:
    name = "stub"

    def __init__(self):
        self.sent = []

    def send(self, a):
        self.sent.append(dict(a))
        return {"ok": True}


def make_bot(tmp, now, cfg=None):
    b = live.LiveBot()
    b.clock = lambda: now[0]
    b.state_path = os.path.join(tmp, "live_state.json")
    b._remember = lambda *a, **kw: None
    b._journal = lambda *a, **kw: None
    b.pushes = []
    b._push_send = lambda p: b.pushes.append(p)
    b.cfg = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "params": {"max_micros": 40}, **(cfg or {})}
    b.adapter = Stub()
    b.started_at = int(now[0]) - 6 * 3600
    return b


def pos(t, qty=3, entry=25000.0, stop=24970.0, target=25090.0, d=1):
    return {"entry_t": t, "dir": d, "qty": qty, "entry": entry, "stop": stop, "stop0": stop, "target": target,
            "risk_pts": abs(entry - stop), "setup": "LIT"}


def route(b, p, now):
    b.state = {"model": "lit", "position": p, "strategy": {"params": {"window": [[120, 930]]}}}
    n = len(b.adapter.sent)
    b._route_signals({"trades": [], "events": []}, "NQ", int(now), 300)
    return [a for a in b.adapter.sent[n:] if a.get("side") in ("buy", "sell")]


def bot_route():
    tmp = tempfile.mkdtemp(prefix="le_guards_")
    try:
        t0 = at(2026, 10, 22, 10, 0)
        now = [t0 + 303]
        b = make_bot(tmp, now)
        sent = route(b, pos(t0, stop=24870.0, target=25300.0), now[0])
        check("D. stop 130 pts away: NOT routed, 'NOT routed: GUARD' logged, pushed",
              not sent and any("NOT routed: GUARD" in x["text"] and "130.0 pts" in x["text"] for x in b.log)
              and b.pushes and b.pushes[-1]["kind"] == "ops" and "Entry blocked" in b.pushes[-1]["title"], [list(b.log)[:3], b.pushes])
        # a good entry goes through and is recorded
        t1 = t0 + 1800
        now[0] = t1 + 303
        sent = route(b, pos(t1), now[0])
        st = guards.load_state(b)
        check("D. a normal entry is routed (side, qty, tick stop / target) and recorded in guards_state.json",
              len(sent) == 1 and sent[0]["qty"] == 3 and sent[0]["stop"] == 24970.0 and t1 in st["routed"]["2026-10-22"], [sent, st])
        # the model's position closes; a second entry the same day: blocked (1 a day)
        b.state["position"] = None
        b._open_routed = None
        t2 = t0 + 3600
        now[0] = t2 + 303
        sent = route(b, pos(t2), now[0])
        check("D. a 2nd entry the same day: NOT routed (1 trade a day)",
              not sent and any("already routed today" in x["text"] for x in b.log), list(b.log)[:2])
        # restart with live_state.json lost: the same signal / the same day stays blocked
        os.remove(b.state_path)
        now[0] = t1 + 303 + 20                   # restarted inside the same bar (the late-entry rule would not stop it)
        b2 = make_bot(tmp, now)
        sent = route(b2, pos(t1), now[0])
        check("D. restart, live_state.json deleted: the same signal is NOT routed again (persisted)",
              not sent and any("already routed" in x["text"] for x in b2.log), list(b2.log)[:2])
        # the next day: allowed
        t3 = at(2026, 10, 23, 4, 0)
        now[0] = t3 + 303
        b3 = make_bot(tmp, now)
        sent = route(b3, pos(t3), now[0])
        check("D. the next trading day: routed", len(sent) == 1)
        # NO TRADE void: an entry flattened as NO TRADE does not count
        t4 = at(2026, 10, 26, 4, 0)
        now[0] = t4 + 303
        b4 = make_bot(tmp, now)
        route(b4, pos(t4), now[0])
        b4.ledger.append({"t": int(now[0]) + 60, "sym": "NQ", "side": "exit", "qty": 3, "reason": "NO TRADE", "entry_t": t4, "pnl": 0.0})
        b4._open_routed = None
        t5 = t4 + 1200
        now[0] = t5 + 303
        sent = route(b4, pos(t5), now[0])
        check("D. after a NO TRADE flatten (the estimate was not the model's trade) the model's later entry is routed", len(sent) == 1,
              list(b4.log)[:3])
        # daily loss: today's routed P&L -$1,000 -> blocked
        t6 = at(2026, 10, 27, 4, 0)
        now[0] = t6 + 303
        b5 = make_bot(tmp, now, cfg={"guards": {"max_per_day": 3}})
        b5.ledger.append({"t": t6 - 3600, "sym": "NQ", "side": "exit", "qty": 3, "reason": "STOP", "entry_t": t6 - 7200, "pnl": -1000.0})
        sent = route(b5, pos(t6), now[0])
        check("D. today's routed P&L -$1,000: NOT routed (soft daily loss) + push",
              not sent and any("soft daily loss" in x["text"] for x in b5.log) and b5.pushes, list(b5.log)[:2])
        b5.ledger[-1]["pnl"] = -999.0
        b5.seen.discard(("entry", t6))
        sent = route(b5, pos(t6), now[0])
        check("D. -$999: routed", len(sent) == 1, list(b5.log)[:2])
        # clock drift: simulated clock -> ignored; real clock -> blocks
        guards._CLOCK.update({"drift": -8.0, "bad": 2, "t": time.time(), "ok_t": time.time(), "running": False})
        t7 = at(2026, 10, 28, 4, 0)
        now[0] = t7 + 303
        b6 = make_bot(tmp, now)
        sent = route(b6, pos(t7), now[0])
        check("D. clock drift 8 s with a simulated clock (test harness): ignored, routed", len(sent) == 1)
        b7 = make_bot(tmp, now)
        c = {**guards.DEFAULTS, "dup_entry": False, "calendar": False}
        b7.clock = time.time
        b7.state = {"model": "lit", "strategy": {"params": {}}}
        pr = guards.entry_problems(b7, pos(t7 + 600), live.LiveBot._entry_action(pos(t7 + 600), 3, "NQ"), 3, int(time.time()), c=c, s={})
        check("D. clock 8 s ahead on the real clock (2 probes): entry blocked", any("PC clock 8.0 s ahead" in x for x in pr), pr)
        guards._CLOCK.update({"bad": 1})
        pr = guards.entry_problems(b7, pos(t7 + 600), live.LiveBot._entry_action(pos(t7 + 600), 3, "NQ"), 3, int(time.time()), c=c, s={})
        check("D. one bad probe only (not confirmed yet): not blocked", not any("PC clock" in x for x in pr), pr)
        guards._CLOCK.update({"drift": None, "bad": 0, "t": 0.0})
        probes = iter([7.0, 7.5])
        guards._CLOCK["probe"] = lambda: next(probes)
        try:
            b7.health = {}
            guards.clock_tick(b7, c, now_real=1e12)
            for _ in range(50):
                if not guards._CLOCK["running"]:
                    break
                time.sleep(0.02)
            guards._CLOCK["t"] = 0.0
            guards.clock_tick(b7, c, now_real=1e12)
            for _ in range(50):
                if not guards._CLOCK["running"]:
                    break
                time.sleep(0.02)
            check("D. clock probe thread: two 7 s answers -> confirmed (bad 2), PC clock behind", guards._CLOCK["bad"] == 2
                  and guards.clock_problem(b7, c) and "behind" in guards.clock_problem(b7, c), dict(guards._CLOCK))
        finally:
            guards._CLOCK.update({"drift": None, "bad": 0, "t": 0.0, "ok_t": 0.0, "probe": None, "running": False})
        # news minute: off by default, on when configured
        cpi = at(2026, 11, 10, 8, 30)
        now[0] = cpi + 60
        b8 = make_bot(tmp, now)
        sent = route(b8, pos(cpi - 240), now[0])
        check("D. news guard OFF (default): an entry 1 min after CPI is routed", len(sent) == 1)
        b9 = make_bot(tmp, now, cfg={"guards": {"news": True, "dup_entry": False}})
        b9.seen = set()
        sent = route(b9, pos(cpi - 240), now[0])
        check("D. news guard ON (start cfg guards.news): the same entry is NOT routed", not sent
              and any("Tier-1 news" in x["text"] for x in b9.log), list(b9.log)[:2])
        # E. room alarm
        b10 = make_bot(tmp, now, cfg={"eval_start": "2026-10-19"})
        b10._lit_sizing = {"mode": "two_week", "eval_start": "2026-10-19"}
        b10.clock = lambda: at(2026, 10, 23, 11, 0)
        b10._eval_prev = {"2026-10-19": -1150.0}
        guards.tick(b10, at(2026, 10, 23, 11, 0))
        r0, n0 = b10.eval_room(), len(b10.pushes)
        b10._eval_prev["2026-10-20"] = -100.0
        guards.tick(b10, at(2026, 10, 23, 11, 1))
        guards.tick(b10, at(2026, 10, 23, 11, 2))
        r1, n1 = b10.eval_room(), len(b10.pushes)
        b10._eval_prev["2026-10-21"] = -400.0
        guards.tick(b10, at(2026, 10, 23, 11, 3))
        guards.tick(b10, at(2026, 10, 23, 11, 4))
        titles = [p["title"] for p in b10.pushes]
        check("E. room $850: no alarm", r0 == 850.0 and n0 == 0, (r0, titles))
        check("E. room $750: 'below $800' pushed once (2 polls)", r1 == 750.0 and n1 == 1, (r1, titles))
        check("E. room $350: 'below $400' pushed once; 5 polls, 2 pushes in all",
              titles == ["Eval room below $800", "Eval room below $400"], titles)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ F. reconcile
def reconcile():
    tmp = tempfile.mkdtemp(prefix="le_guards_nt_")
    try:
        folder = os.path.join(tmp, "NinjaTrader 8")
        fake = _FakeNT(folder)
        fake.move(25020.0)
        now = [float(at(2026, 10, 22, 10, 0, 3))]
        cfg = {"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_folder": folder, "params": {"max_micros": 40, "flat_mod": 955},
               "nt_state_path": os.path.join(tmp, "nt.json"), "nt_audit_log": os.path.join(tmp, "oif.log")}
        ad = NinjaTraderAdapter(cfg, clock=lambda: now[0])
        ad._sleep = lambda s: (fake.process(), now.__setitem__(0, now[0] + s))
        ad._alert_fn = lambda *a: None
        b = make_bot(tmp, now)
        b.adapter = ad
        inst = ad._instruments()["micro"]
        check("F. account flat, ledger flat: nothing", (guards.reconcile_tick(b, guards.DEFAULTS, int(now[0])), b.pushes) == (None, []))
        # a position the bot does not know (a manual order / an orphan)
        fake._do(place_line("Sim101", inst, "BUY", 2, "MARKET", order_id="MANUAL1"))
        k = len(fake.files)
        guards.reconcile_tick(b, guards.DEFAULTS, int(now[0]))
        check("F. unknown LONG 2: first poll only notes it (no push, no close yet)", not b.pushes and len(fake.files) == k)
        now[0] += 30
        guards.reconcile_tick(b, guards.DEFAULTS, int(now[0]))
        fake.process()
        lines = [ln for _, ls in fake.files[k:] for ln in ls]
        check("F. 30 s later: push 'Position mismatch' + CLOSEPOSITION -> the account is flat",
              b.pushes and b.pushes[0]["title"] == "Position mismatch" and any(ln.startswith("CLOSEPOSITION") for ln in lines)
              and fake.pos[("Sim101", inst)][0] == 0 and any(r.get("reason") == "RECONCILE" for r in b.ledger), [b.pushes, lines])
        # the bot's position, NinjaTrader flat: push after 6 min, never a close
        now[0] += 600
        t = int(now[0]) - 3
        b.ledger.append({"t": t - 600, "sym": "NQ", "side": "buy", "qty": 3, "entry_t": t - 900, "result": {"ok": True}})
        b._open_routed, b._open_qty = t - 900, 3
        n, k = len(b.pushes), len(fake.files)
        guards.reconcile_tick(b, guards.DEFAULTS, int(now[0]))
        now[0] += 120
        guards.reconcile_tick(b, guards.DEFAULTS, int(now[0]))
        p_early = len(b.pushes) - n
        now[0] += 300
        guards.reconcile_tick(b, guards.DEFAULTS, int(now[0]))
        check("F. ledger LONG 3, NinjaTrader flat: no push within 6 min (a bracket fill the model has not seen yet), then push, no order",
              p_early == 0 and len(b.pushes) == n + 1 and "LONG 3 micros" in b.pushes[-1]["body"] and len(fake.files) == k, b.pushes[-1:])
        # matching: route a real bracket through the adapter
        b._open_routed = None
        b.ledger = []
        b.pushes = []
        now[0] += 3600
        t = int(now[0]) - 3
        r = b._route({"sym": "NQ", "side": "buy", "qty": 4, "stop": 24990.0, "target": 25060.0, "entry": 25020.0, "entry_t": t})
        b._open_routed, b._open_qty = t, 4
        now[0] += 200
        guards.reconcile_tick(b, guards.DEFAULTS, int(now[0]))
        now[0] += 400
        guards.reconcile_tick(b, guards.DEFAULTS, int(now[0]))
        check("F. the bot's bracket (LONG 4) = NinjaTrader LONG 4: nothing", r["ok"] and not b.pushes, [r, b.pushes])
        # the target fills at NinjaTrader, the model exits: 17:00 P&L reconcile
        fake.move(25060.0)
        ad.tick()
        model_pnl = round(4 * (40.0 * 2.0) - 4 * 1.90, 2)
        b.ledger.append({"t": int(now[0]), "sym": "NQ", "side": "exit", "qty": 4, "reason": "TARGET", "entry_t": t, "pnl": model_pnl})
        b._open_routed = None
        s = {}
        guards.pnl_tick(b, guards.DEFAULTS, at(2026, 10, 22, 16, 59), s)
        none_before = not b.pushes and "pnl_done" not in s
        guards.pnl_tick(b, guards.DEFAULTS, at(2026, 10, 22, 17, 2), s)
        check("F. 17:00 P&L reconcile: NinjaTrader fills +$312.40 = ledger: logged, no push (and nothing before 17:00)",
              none_before and not b.pushes and s.get("pnl_done") == "2026-10-22"
              and any("P&L reconcile" in x["text"] and "+312.40" in x["text"] for x in b.log), [list(b.log)[:2], b.pushes])
        b.ledger[-1]["pnl"] = model_pnl + 50.0
        s = {}
        guards.pnl_tick(b, guards.DEFAULTS, at(2026, 10, 22, 17, 3), s)
        guards.pnl_tick(b, guards.DEFAULTS, at(2026, 10, 22, 17, 8), s)
        check("F. ledger $50 above NinjaTrader's fills: one push 'P&L mismatch'",
              len(b.pushes) == 1 and b.pushes[0]["title"] == "P&L mismatch" and "diff $-50" in b.pushes[0]["body"], b.pushes)
        b.pushes = []
        b.adapter = Stub()
        guards.reconcile_tick(b, guards.DEFAULTS, int(now[0]))
        check("F. paper / stub adapter: reconcile does nothing", not b.pushes)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ G. stale data
def stale_data():
    import pandas as pd
    from engine import alerts, news, pcbars
    tmp = tempfile.mkdtemp(prefix="le_guards_feed_")
    keep = (alerts.send, news.ff_calendar, news.volatility, news.guard)
    undo = pcbars.install_yahoo_guard()
    try:
        alerts.send = lambda *a, **kw: None
        news.ff_calendar = lambda: []
        news.volatility = lambda: {}
        news.guard = lambda now=None, params=None, vol=None, events=None: {"allowed": True, "reasons": [], "regime": None,
                                                                            "next_high": None, "now": now}
        NOW = at(2026, 10, 16, 10, 3, 2)
        NT_FROM = at(2026, 10, 12, 18, 0)
        TV_END = at(2026, 10, 14, 0, 0)
        b1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
        b5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        b1 = b1[b1["time"] >= TV_END - 40 * 86400].reset_index(drop=True)
        b5 = b5[b5["time"] >= TV_END - 70 * 86400].reset_index(drop=True)
        folder = os.path.join(tmp, "NinjaTrader 8")
        feed = os.path.join(folder, "le_feed")
        os.makedirs(feed, exist_ok=True)

        def write(upto1, upto5, open_t=None):
            for name, df, secs, upto in (("MNQ_1m.csv", b1, 60, upto1), ("MNQ_5m.csv", b5, 300, upto5)):
                x = df[(df["time"] >= NT_FROM) & (df["time"] + secs <= upto)]
                x[["time", "open", "high", "low", "close", "volume"]].to_csv(os.path.join(feed, name), index=False, header=False)
            p = os.path.join(feed, "MNQ_1m_open.csv")
            if open_t is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(f"{open_t},25000.25\n")
        clock = [NOW]
        bot = live.LiveBot()
        bot.clock = lambda: clock[0]
        bot.state_path = os.path.join(tmp, "live_state.json")
        bot._remember = lambda *a, **kw: None
        tv = {tf: df[df["time"] < TV_END].reset_index(drop=True) for tf, df in (("1m", b1), ("5m", b5))}
        bot.read_hist = lambda sym, tf: tv.get(tf, pd.DataFrame(columns=pcbars.COLS)) if sym == "NQ" else pd.DataFrame(columns=pcbars.COLS)
        r = bot.start({"sym": "NQ", "tf": "5m", "adapter": "paper", "model": "lit", "nt_folder": folder}, spawn=False)
        m0 = NOW - NOW % 60
        write(m0, m0, open_t=m0)
        bot._nt_feed = None
        bot.poll_once()
        h = bot.health
        check("G. fresh 1m + 5m + 1m-open files: no block, the forming 1m open is read from MNQ_1m_open.csv",
              r.get("ok") and not h.get("entries_blocked") and not h.get("nt_down_1m") and bot._forming.get(("NQ", 60)) == (m0, 25000.25),
              {k: h.get(k) for k in ("entries_blocked", "nt_down", "nt_down_1m", "feed_block")})
        write(m0, m0, open_t=m0 - 600)
        bot._nt_feed = None
        clock[0] = NOW + 1
        bot.poll_once()
        h = bot.health
        check("G. 1m-open file 10 min old: NOT a block (forming open unknown -> the entry is sized from the CISD close and "
              "checked when its fill bar closes)", not h.get("entries_blocked") and bot._forming.get(("NQ", 60)) is None,
              {k: h.get(k) for k in ("entries_blocked", "nt_down_1m")})
        write(m0 - 40 * 60, m0, open_t=m0)
        bot._nt_feed = None
        clock[0] = NOW + 2
        bot.poll_once()
        h = bot.health
        check("G. only the 1m file stale (40 min; 5m fresh): FEED STALE, NEW entries blocked at once",
              h.get("entries_blocked") and "stale" in str(h.get("nt_down_1m")) and not h.get("nt_down")
              and "MNQ_1m.csv" in str(h.get("feed_block")), {k: h.get(k) for k in ("entries_blocked", "nt_down", "nt_down_1m", "feed_block")})
        ent_t = NOW - NOW % 300
        bot.state = {"model": "lit", "position": pos(ent_t), "strategy": {"params": {"window": [[120, 930]]}}}
        bot.started_at = ent_t - 3600
        n = len(bot.ledger)
        bot._route_signals({"trades": [], "events": []}, "NQ", int(clock[0]), 300)
        check("G. an entry while only the 1m feed is stale is NOT routed ('feed stale')",
              not [x for x in bot.ledger[n:] if x.get("side") in ("buy", "sell")] and any("NOT routed: feed stale" in x["text"] for x in bot.log))
        os.remove(os.path.join(feed, "MNQ_1m.csv"))
        bot._nt_feed = None
        clock[0] = NOW + 3
        bot.poll_once()
        check("G. 1m file missing: blocked too", bot.health.get("entries_blocked") and bot.health.get("nt_down_1m"))
        check("G. no Yahoo call in any of it", not undo.calls)
    finally:
        undo()
        alerts.send, news.ff_calendar, news.volatility, news.guard = keep
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    quick = "--quick" in sys.argv
    os.environ.pop("LE_LIVE_MODEL", None)
    pure()
    if not quick:
        proof_2026()
    bot_route()
    reconcile()
    stale_data()
    ok = sum(RES)
    print(f"\nguards test: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
