"""Chaos test of the live chain (day-zeroerr 2026-11-24, owner: "no more errors"; docs/FAILURE_MAP.md). Each failure is
simulated in temp folders with a fake clock and the self-test's fake NinjaTrader (engine/ninjatrader._FakeNT); every check
asserts that the detector fires AND that the bot stays safe (no order from a detector, no second entry, the position closed or
protected). Never the owner's phone (every send is captured), never a real account (the adapter trades Sim101; the alarm side
reads a copy of its files under a real-looking account name, as on the PC).

    python -X utf8 -m tests.test_chaos_live

  a. NinjaTrader disconnected       entry refused by the adapter; FEED STALE alarm; 01:55 armed check says NOT READY
  b. stale bars / poll stuck        FEED STALE and ZEUS not polling alarms (fast alarm)
  c. rejected order                 MISSED TRADE (refused) for the main account (fill audit) and for an extra account (guard)
  d. missing stop                   STOP MISSING alarm with the bot running; the adapter re-places an undelivered bracket and
                                    flattens a cancelled stop (existing order path); the alarm then clears
  e. restart mid-trade              TRADE HAS NO STOP (bot stopped); the running-bot alarm stays quiet
  f. clock drift                    entries blocked by the clock guard; a clock hold is a LOUD missed trade
  g. dirty git tree                 the update skips with the file named (real git); 3 h later one 'update stuck' push
  h. account not armed / not in bot MISSED TRADE with the reason within 2 min (extra account, ATLAS account, Rapid not built)
  i. detectors are read-only        a broken bot never raises; no detector calls the adapter
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("LE_SELFTEST_CHILD", "1")       # alert_bus: never a real send

ET = ZoneInfo("America/New_York")
RESULTS = []
REAL = "MFFUEVRPD25K0004321"


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:700]}"), flush=True)


def ts(y, m, d, hh, mm=0, ss=0) -> int:
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


T = ts(2026, 11, 25, 4, 0, 5)                      # a Wednesday, 04:00 ET: inside LIT's window, CME open


def _adapter(tmp, tag):
    from engine.ninjatrader import NinjaTraderAdapter, _FakeNT
    folder = os.path.join(tmp, f"NT_{tag}")
    sd = os.path.join(tmp, f"data_{tag}")
    os.makedirs(sd, exist_ok=True)
    fake = _FakeNT(folder)
    now = [float(T)]
    cfg = {"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_account": "Sim101", "nt_folder": folder,
           "params": {"max_micros": 40, "flat_mod": 955}, "model": "lit", "model_params": {"window": [[120, 930]]},
           "nt_max_entries_day": 999, "nt_state_path": os.path.join(sd, "ninjatrader_state.json"),
           "nt_audit_log": os.path.join(tmp, f"oif_{tag}.log")}
    ad = NinjaTraderAdapter(cfg, clock=lambda: now[0])
    ad._sleep = lambda s: (fake.process(), now.__setitem__(0, now[0] + s))
    ad._alert_fn = lambda *a, **k: None
    return ad, fake, folder, sd, now, cfg


def _order(fake, price, side="sell"):
    d = -1 if side == "sell" else 1
    return {"sym": "NQ", "side": side, "qty": 2, "stop": price - d * 20, "target": price + d * 60, "entry": price, "entry_t": T - 5}


def _as_real(sd, folder, tmp, tag):
    """A copy of the adapter's state under a real account name + its position file (the PC's files, the alarm's view)."""
    sd2 = os.path.join(tmp, f"real_{tag}")
    os.makedirs(sd2, exist_ok=True)
    st = json.load(open(os.path.join(sd, "ninjatrader_state.json")))
    st["account"] = REAL
    json.dump(st, open(os.path.join(sd2, "ninjatrader_state.json"), "w"))
    og = os.path.join(folder, "outgoing")
    for n in os.listdir(og):
        if n.endswith("_Sim101_Position.txt"):
            shutil.copy(os.path.join(og, n), os.path.join(og, n.replace("_Sim101_", f"_{REAL}_")))
    return sd2


def _running(folder, **h):
    return types.SimpleNamespace(running=True, cfg={"adapter": "ninjatrader", "nt_folder": folder, "armed": True,
                                                    "nt_account": REAL}, started_at=T - 3600, thread=None,
                                 health={"last_ok_poll": T - 10, "last_1m_bar_t": T - 65, **h})


def t_disconnect(tmp):
    print("a. NinjaTrader disconnected", flush=True)
    from engine import fast_alarm as FA, live_guard as LG
    ad, fake, folder, sd, now, cfg = _adapter(tmp, "a")
    fake._write("Tradovate.txt", "DISCONNECTED")
    r = ad.place_bracket(_order(fake, fake.price))
    check("adapter refuses the entry while every connection is DISCONNECTED (no order file sent)",
          not r.get("ok") and "DISCONNECTED" in str(r.get("error")) and not fake.files, r)
    bot = _running(folder, feed_block="NinjaTrader bars stale", last_1m_bar_t=T - 400)
    ev = FA.evaluate(bot, T, server_started_at=T - 3600)
    check("fast alarm: FEED STALE fires (bars stop when the connection drops)", "feed_stale" in ev, ev)
    rows = LG.arm_rows(bot, T, live_names=[])
    check("armed check: the real account is NOT READY: NinjaTrader lists no live account",
          rows and not rows[0]["routed"] and "no live account" in rows[0]["why"], rows)
    p = LG.arm_payload(rows, ts(2026, 11, 25, 1, 55))
    check("armed check push is loud (not soft) and masks the account id",
          p and not p.get("soft") and "NOT READY" in p["body"] and "4321" in p["body"] and REAL not in p["body"], p)


def t_stale(tmp):
    print("b. stale bars / poll stuck", flush=True)
    from engine import fast_alarm as FA
    folder = os.path.join(tmp, "NT_b")
    os.makedirs(os.path.join(folder, "outgoing"), exist_ok=True)
    ev = FA.evaluate(_running(folder, last_1m_bar_t=T - 300), T, server_started_at=T - 3600)
    check("1m bar 4 min old -> FEED STALE within 2 min of the 2-bar limit", "feed_stale" in ev and "old" in ev["feed_stale"], ev)
    ev = FA.evaluate(_running(folder, last_ok_poll=T - 200), T, server_started_at=T - 3600)
    check("no good poll for 200 s -> ZEUS not polling", "bot_down" in ev, ev)
    ev = FA.evaluate(_running(folder), T, server_started_at=T - 3600)
    check("fresh bars + polls -> no alarm", not ev, ev)
    sent = []
    fa = FA.FastAlarm(send=lambda p: sent.append(p) or "sent")
    fa.run_seen = T - 3600
    fa._was_running = True
    fa.step(_running(folder, last_1m_bar_t=T - 300), now=T)
    fa.step(_running(folder, last_1m_bar_t=T - 300), now=T + 30)
    check("one push per condition (no storm on the next check)", len(sent) == 1 and sent[0]["code"] == "feed_stale", sent)


def t_rejected(tmp):
    print("c. rejected order", flush=True)
    from engine import fill_audit as FAu, live_guard as LG
    ad, fake, folder, sd, now, cfg = _adapter(tmp, "c")
    fake.reject = {"MARKET"}
    r = ad.place_bracket(_order(fake, fake.price))
    pos = ad.position_for(ad._instruments()["micro"]) or {}
    check("NinjaTrader rejects the entry: adapter reports not ok, no position, no bracket left working",
          not r.get("ok") and pos.get("side", "FLAT") == "FLAT"
          and not [o for o in fake.orders.values() if o.get("state") in ("WORKING", "ACCEPTED")], (r, pos))
    et_ = T - 5
    bot = types.SimpleNamespace(running=True, cfg={"adapter": "ninjatrader"}, _blocked_entries=set(), log=[], seen={("entry", et_)},
                                state={}, started_at=T - 3600,
                                ledger=[{"t": T, "side": "sell", "entry_t": et_, "result": {"ok": False, "error": r.get("error") or "REJECTED"}}])
    got = []
    FAu.session_alerts(bot, store=os.path.join(tmp, "fa_c"), now=T + 60, notify=got.append)
    check("main account: MISSED TRADE 'refused' at once (fill audit)", got and "refused" in got[0]["body"], got)
    check("...and it is a LOUD one (not a rule hold)", got and FAu._missed_problem(got[0]) and not FAu._missed_problem(got[0]).get("soft"), got)
    acc = types.SimpleNamespace(spec={"adapter": "ninjatrader", "armed": True, "nt_account": REAL, "name": "Zlarior 25K #2"},
                                name="Zlarior 25K #2", problem=None, adapter=object(), seen={("entry", et_)}, blocked=set(),
                                hedge_wait=set(), added_t=0, open_t=None, closes=[],
                                ledger=[{"t": T, "side": "sell", "entry_t": et_, "result": {"ok": False, "error": "REJECTED: rule #3"}}],
                                disabled_reason=lambda: None)
    bot.accts = types.SimpleNamespace(accounts=[acc])
    ms = LG.missed(bot, et_ + 150)
    check("extra account: guard says MISSED with 'NinjaTrader refused it'", ms and "refused" in ms[0]["why"], ms)


def t_stop(tmp):
    print("d. missing stop at the broker (bot running)", flush=True)
    from engine import fast_alarm as FA
    ad, fake, folder, sd, now, cfg = _adapter(tmp, "d")
    real_send = ad._send_lines
    ad._send_lines = lambda lines, label: ({"ok": False, "error": "outbox locked"} if label == "BRACKET" else real_send(lines, label))
    r = ad.place_bracket(_order(fake, fake.price))
    lg = ad.legs[0] if ad.legs else {}
    check("bracket not delivered: leg 'unprotected', the adapter never pretends it is protected",
          lg.get("status") == "unprotected" and not r.get("ok"), (lg.get("status"), r))
    sd2 = _as_real(sd, folder, tmp, "d1")
    bot = _running(folder)
    e30 = FA.stop_missing(bot, T + 30, folder=folder, state_dir=sd2)
    e90 = FA.stop_missing(bot, T + 90, folder=folder, state_dir=sd2)
    check("STOP MISSING alarm after 60 s (not before: the adapter is still placing it)", e30 is None and e90 and "NO working stop" in e90
          and "..4321" in e90, (e30, e90))
    import engine.ninjatrader as NTm
    keep = NTm.STATE_PATH
    NTm.STATE_PATH = os.path.join(sd2, "ninjatrader_state.json")
    try:
        ev = FA.evaluate(_running(folder, last_ok_poll=T + 85, last_1m_bar_t=T + 20), T + 90, server_started_at=T - 3600)
    finally:
        NTm.STATE_PATH = keep
    check("...through the fast alarm's evaluate (code stop_missing, never capped)", "stop_missing" in ev, ev)
    ad._send_lines = real_send
    now[0] = T + 95
    ad.tick()
    fake.process()
    lg = ad.legs[0] if ad.legs else {}
    s = ad.read_order(lg.get("stop_id", "x")) or {}
    check("re-place: the adapter's next tick sends the bracket through the existing order path; the stop is WORKING",
          lg.get("status") == "protected" and s.get("state") in ("WORKING", "ACCEPTED"), (lg.get("status"), s))
    sd3 = _as_real(sd, folder, tmp, "d2")
    check("alarm clears once the stop works", FA.stop_missing(bot, T + 200, folder=folder, state_dir=sd3) is None)
    sid = lg["stop_id"]
    fake.orders[sid]["state"] = "CANCELLED"
    fake._state(sid, fake.orders[sid])
    sd4 = _as_real(sd, folder, tmp, "d3")
    e = FA.stop_missing(bot, T + 300, folder=folder, state_dir=sd4)
    check("stop cancelled at the broker (by hand / NinjaTrader) -> STOP MISSING alarm names CANCELLED", e and "CANCELLED" in e, e)
    now[0] = T + 300
    ad.tick()
    fake.process()
    pos = ad.position_for(ad._instruments()["micro"]) or {}
    check("bot stays safe: the adapter flattens a position whose stop was lost (never holds without a stop)",
          pos.get("side") == "FLAT", pos)


def t_restart(tmp):
    print("e. restart mid-trade (entry filled, server died before the bracket, not resumed)", flush=True)
    from engine import fast_alarm as FA
    ad, fake, folder, sd, now, cfg = _adapter(tmp, "e")

    class _Crash(Exception):
        pass
    real_send = ad._send_lines

    def crash(lines, label):
        r = real_send(lines, label)
        if label == "ENTRY":
            fake.process()
            raise _Crash()
        return r
    ad._send_lines = crash
    try:
        ad.place_bracket(_order(fake, fake.price))
    except _Crash:
        pass
    sd2 = _as_real(sd, folder, tmp, "e")
    stopped = types.SimpleNamespace(running=False, cfg={"adapter": "ninjatrader", "nt_folder": folder})
    e = FA.no_stop(stopped, T + 90, folder=folder, state_dir=sd2)
    check("bot stopped with a filled entry and no bracket -> TRADE HAS NO STOP", e and "NO stop" in e, e)
    check("the running-bot check stays quiet for a stopped bot (one alarm, not two)",
          FA.stop_missing(stopped, T + 90, folder=folder, state_dir=sd2) is None)


def t_clock(tmp):
    print("f. clock drift", flush=True)
    import time
    from engine import guards, fill_audit as FAu
    saved = dict(guards._CLOCK)
    try:
        guards._CLOCK.update(drift=8.0, bad=2, ok_t=time.time())
        bot = types.SimpleNamespace(clock=time.time)
        p = guards.clock_problem(bot, {"clock": True, "clock_max_s": 5.0})
        check("PC clock 8 s off (2 probes) -> new entries blocked", p and "PC clock" in p, p)
        check("a clock hold is a LOUD missed trade, not a quiet rule hold",
              not FAu.rule_hold("The backtest took it, the PC bot did not: GUARD " + str(p)))
    finally:
        guards._CLOCK.clear()
        guards._CLOCK.update(saved)


def _git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                               "GIT_COMMITTER_EMAIL": "t@t"})


def t_git(tmp):
    print("g. dirty git tree blocks the update", flush=True)
    from engine import autoupdate as AU, live_guard as LG
    bare, pc, dev = (os.path.join(tmp, x) for x in ("o.git", "pc", "dev"))
    _git(tmp, "init", "-q", "--bare", "-b", "pc", bare)
    _git(tmp, "clone", "-q", bare, dev)
    _git(dev, "checkout", "-q", "-b", "pc")
    os.makedirs(os.path.join(dev, "engine"), exist_ok=True)
    open(os.path.join(dev, "engine", "x.py"), "w").write("A = 1\n")
    _git(dev, "add", "-A")
    _git(dev, "commit", "-q", "-m", "one")
    _git(dev, "push", "-q", "origin", "pc")
    _git(tmp, "clone", "-q", "-b", "pc", bare, pc)
    open(os.path.join(dev, "engine", "x.py"), "w").write("A = 2\n")
    _git(dev, "commit", "-q", "-am", "two")
    _git(dev, "push", "-q", "origin", "pc")
    open(os.path.join(pc, "engine", "x.py"), "w").write("A = 99  # hand edit\n")
    ff = AU.fast_forward(AU.Shell(pc), "pc", src={"remote": "origin", "branch": "pc", "label": "test"})
    check("a hand edit of a file the update rewrites: skipped, file named, alert on, the edit untouched",
          ff["status"] == "skipped" and "engine/x.py" in ff["reason"] and ff.get("alert")
          and "99" in open(os.path.join(pc, "engine", "x.py")).read(), ff)
    au = {"last": {"t": T, "status": "skipped", "reason": ff["reason"]}}
    st, p = LG.update_stuck(None, au, T + 60)
    check("guard: no push in the first 3 h (the hourly park may fix it)", p is None and st.get("since") == T, (st, p))
    st, p = LG.update_stuck(st, au, T + 3 * 3600 + 60)
    check("guard: 3 h stuck -> ONE 'Bot update stuck' push with the file and the fix", p and "engine/x.py" in p["body"]
          and "stuck" in p["title"], p)
    st2, p2 = LG.update_stuck(st, au, T + 4 * 3600)
    check("...not again the same day", p2 is None, p2)
    st3, p3 = LG.update_stuck(st2, {"last": {"t": T + 5 * 3600, "status": "skipped", "reason": "not flat: LIT trade open"}}, T + 5 * 3600)
    check("a 'not flat' wait is not 'stuck' (no push, the stuck clock kept)", p3 is None and st3.get("since") == T, st3)
    st4, _ = LG.update_stuck(st3, {"last": {"t": T + 6 * 3600, "status": "updated", "reason": "a -> b"}}, T + 6 * 3600)
    check("an installed update clears it", st4 == {}, st4)


def t_missed(tmp):
    print("h. accounts not armed / not in the bot: MISSED TRADE with the reason", flush=True)
    from engine import live_guard as LG
    et_ = T - 5
    acc = types.SimpleNamespace(spec={"adapter": "ninjatrader", "armed": False, "nt_account": REAL, "name": "Rapid EOD 25K"},
                                name="Rapid EOD 25K", problem=None, adapter=None, seen=set(), blocked=set(), hedge_wait=set(),
                                added_t=0, open_t=None, closes=[], ledger=[], disabled_reason=lambda: "adapter not created")
    ok_acc = types.SimpleNamespace(spec={"adapter": "ninjatrader", "armed": True, "nt_account": "MFFUEVX0001111", "name": "Z2"},
                                   name="Z2", problem=None, adapter=object(), seen={("entry", et_)}, blocked=set(), hedge_wait=set(),
                                   added_t=0, open_t=None, closes=[], disabled_reason=lambda: None,
                                   ledger=[{"t": T, "side": "sell", "entry_t": et_, "result": {"ok": True}}])
    rule = types.SimpleNamespace(**{**vars(ok_acc), "name": "Z3", "ledger": [], "blocked": {et_}})
    tb = ts(2026, 11, 25, 3, 45)
    atl = types.SimpleNamespace(spec={"adapter": "ninjatrader", "armed": True, "keys": ["ema_lon_vix"]}, label="ATLAS 25K",
                                name=REAL, problem="the saved name is not in NinjaTrader", adapter=None, seen=set(), held={},
                                open_t=None, closes=[], ledger=[], disabled_reason=lambda: "the saved name is not in NinjaTrader")
    bot = types.SimpleNamespace(running=True, cfg={"adapter": "ninjatrader"}, seen={("entry", et_)}, state={},
                                accts=types.SimpleNamespace(accounts=[acc, ok_acc, rule]), acct_b=atl, acct_r=None, acct_r2=None,
                                second={"strategies": {"ema_lon_vix": {"trades": [{"entry_t": tb, "dir": -1}]}}})
    check("not yet 2 min after the entry -> nothing (the account may still route it)",
          not [m for m in LG.missed(bot, et_ + 60) if m["model"] == "lit"])
    ms = LG.missed(bot, et_ + 125)
    names = sorted(m["account"] for m in ms)
    check("2 min later: MISSED on the not-armed account and ATLAS's account; none on the one that took it or its rule hold",
          names == ["ATLAS 25K", "Rapid EOD 25K"], ms)
    w = {m["account"]: m["why"] for m in ms}
    check("each with its reason (start problem / name not in NinjaTrader)",
          "adapter not created" in w.get("Rapid EOD 25K", "") and "not in NinjaTrader" in w.get("ATLAS 25K", ""), w)
    got = []
    g = LG.LiveGuard(send=lambda p: got.append(p) or "sent", state_path=os.path.join(tmp, "lg.json"), au_path=os.path.join(tmp, "none.json"))
    g.step(bot, et_ + 125)
    g._miss_t = 0
    g.step(bot, et_ + 190)
    miss = [p for p in got if p["code"] == "missed"]
    check("LiveGuard pushes each miss ONCE, loud, ids masked", len(miss) == 2 and all(not p.get("soft") for p in miss)
          and all(REAL not in p["title"] + p["body"] for p in miss), got)
    bot.accts = types.SimpleNamespace(accounts=[])
    bot.acct_b = None
    import engine.launch_check as LC
    orig = LC.rapid_fact
    LC.rapid_fact = lambda b, path=None, slot="rapid": ({"label": "Rapid EOD 25K", "armed": False, "lit": False, "atlas": False,
                                                         "problem": None} if slot == "rapid" else None)
    try:
        ms = LG.missed(bot, et_ + 125)
    finally:
        LC.rapid_fact = orig
    check("Rapid configured but not built in the running bot (not armed at START): LIT and ATLAS signals reported missed",
          sorted(m["model"] for m in ms) == ["atlas", "lit"] and all("not armed" in m["why"] for m in ms), ms)
    due = [LG.arm_due(ts(2026, 11, 25, h, m), set()) for h, m in ((1, 54), (1, 55), (9, 5), (9, 20), (12, 0))]
    check("armed check due at 01:55 and 09:00 ET only", [bool(x) for x in due] == [False, True, True, False, False], due)
    check("no armed check on a Saturday", LG.arm_due(ts(2026, 11, 28, 9, 0), set()) is None)


def t_safe(tmp):
    print("i. detectors are read-only and never raise", flush=True)
    from engine import live_guard as LG, fast_alarm as FA

    class Boom:
        running = True
        cfg = {"adapter": "ninjatrader"}

        def __getattr__(self, k):
            raise RuntimeError("broken bot")
    g = LG.LiveGuard(send=lambda p: "sent", state_path=os.path.join(tmp, "lg2.json"), au_path=os.path.join(tmp, "none.json"))
    try:
        g.step(Boom(), T)
        ok = True
    except Exception as e:  # noqa: BLE001
        ok = e
    check("a broken bot object never raises out of the guard", ok is True, ok)

    class NoTouch:
        def __getattr__(self, k):
            if k in ("send", "place_bracket", "flatten", "kill", "modify_stop", "cancel_all"):
                raise AssertionError(f"detector called adapter.{k}")
            raise AttributeError(k)
    et_ = T - 5
    acc = types.SimpleNamespace(spec={"adapter": "ninjatrader", "armed": True}, name="A", problem=None, adapter=NoTouch(),
                                seen=set(), blocked=set(), hedge_wait=set(), added_t=0, open_t=None, closes=[], ledger=[],
                                disabled_reason=lambda: None)
    bot = types.SimpleNamespace(running=True, cfg={"adapter": "ninjatrader"}, seen={("entry", et_)}, state={},
                                accts=types.SimpleNamespace(accounts=[acc]), acct_b=None, acct_r=None, acct_r2=None, adapter=NoTouch())
    try:
        ms = LG.missed(bot, et_ + 130)
        LG.arm_rows(bot, et_ + 130, live_names=[])
        FA.evaluate(bot, et_ + 130, server_started_at=T - 3600)
        ok = True
    except AssertionError as e:
        ok, ms = e, None
    check("no detector touches an order method (missed / armed / fast alarm)", ok is True, ok)
    check("kill switch engaged: the guard says nothing (no account trades on purpose)",
          not LG.missed(types.SimpleNamespace(**{**vars(bot), "kill": True}), et_ + 130))
    check("paper bot: the guard says nothing", not LG.missed(types.SimpleNamespace(**{**vars(bot), "cfg": {"adapter": "paper"}}), et_ + 130))


def main():
    tmp = tempfile.mkdtemp(prefix="chaos_")
    try:
        for t in (t_disconnect, t_stale, t_rejected, t_stop, t_restart, t_clock, t_git, t_missed, t_safe):
            try:
                t(tmp)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{t.__name__} ran", False, e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(ok for _, ok in RESULTS)
    print(f"\nchaos live: {n}/{len(RESULTS)} checks passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
