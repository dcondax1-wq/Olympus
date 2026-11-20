"""Red team 2 (2026-11-20, day-redteam2): what could cost money in the next 10 trading days (Thanksgiving week, Christmas,
New Year; restarts mid-trade; a 4th account added live; MFFU rules). Temp dirs only, a fake clock, never the owner's phone.

    python -X utf8 -m tests.test_redteam2_live

h. half-day halt with a broker position open (engine/fast_alarm.halt_open): MFFU does not auto-close at a CME half-day
   halt; a stopped / crashed bot leaves the trade open into it = the account fails. The phone must ring before the halt.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import tempfile
import types
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:700]}"), flush=True)


def ts(y, m, d, hh, mm=0, ss=0) -> int:
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


def _pos(folder, inst, acct, text):
    og = os.path.join(folder, "outgoing")
    os.makedirs(og, exist_ok=True)
    with open(os.path.join(og, f"{inst}_{acct}_Position.txt"), "w", encoding="utf-8") as fh:
        fh.write(text)


def t_halt(tmp):
    print("h. a broker position open into a CME half-day halt", flush=True)
    from engine import fast_alarm as FA
    folder = os.path.join(tmp, "NT")
    stopped = types.SimpleNamespace(running=False, cfg={"adapter": "ninjatrader", "nt_folder": folder})
    running = types.SimpleNamespace(running=True, cfg={"adapter": "ninjatrader", "nt_folder": folder}, started_at=0,
                                    health={"last_ok_poll": 0}, thread=None)
    _pos(folder, "MNQ 12-26 Globex", "MFFUEVLB25K9991234", "SHORT;2;20950.25")
    _pos(folder, "MNQ 12-26 Globex", "Sim101", "LONG;1;20950.25")
    halt = getattr(FA, "halt_open", None)
    ev = lambda b, t: FA.evaluate(b, t, server_started_at=t - 3600, autostart=None)
    thx_1252 = ev(stopped, ts(2026, 11, 26, 12, 52))
    check("Thanksgiving 12:52 ET, bot STOPPED, ATLAS short open on the real account -> 'halt_open' alarm (MFFU does not "
          "close it at the 13:00 half-day halt)", "halt_open" in thx_1252, thx_1252)
    check("the alarm text names the halt, the position (account id cut to 4) and says close it by hand",
          "13:00" in str(thx_1252.get("halt_open")) and "..1234" in str(thx_1252.get("halt_open"))
          and "9991234" not in str(thx_1252.get("halt_open")).replace("..1234", ""), thx_1252)
    check("Thanksgiving 12:52, bot RUNNING (it flattens at 12:55 itself) -> no alarm yet",
          "halt_open" not in ev(running, ts(2026, 11, 26, 12, 52)))
    check("Thanksgiving 12:56, bot running, still open after its own 12:55 flat -> alarm",
          "halt_open" in ev(running, ts(2026, 11, 26, 12, 56)))
    check("Fri 11-27 13:06 and Christmas Eve 12-24 13:06 (halt 13:15), bot stopped -> alarm",
          "halt_open" in ev(stopped, ts(2026, 11, 27, 13, 6)) and "halt_open" in ev(stopped, ts(2026, 12, 24, 13, 6)))
    check("a normal Friday 12:52 / Thanksgiving 12:30 (too early) / 13:01 (halt passed) -> no alarm",
          not any("halt_open" in ev(stopped, t) for t in (ts(2026, 11, 20, 12, 52), ts(2026, 11, 26, 12, 30),
                                                          ts(2026, 11, 26, 13, 1))))
    _pos(folder, "MNQ 12-26 Globex", "MFFUEVLB25K9991234", "FLAT;0;0")
    check("flat on the real account (only the Sim101 position open) -> no alarm",
          "halt_open" not in ev(stopped, ts(2026, 11, 26, 12, 52)))
    # the push goes out even when the day's 6-alarm cap is used up, and no 'back to normal' after the halt itself
    _pos(folder, "MNQ 12-26 Globex", "MFFUEVLB25K9991234", "SHORT;2;20950.25")
    sent = []
    fa = FA.FastAlarm(send=lambda p: (sent.append(p), "sent")[1], clock=lambda: 0)
    day = dt.date(2026, 11, 26).isoformat()
    fa.day_n = {day: FA.DAY_MAX}
    fa.step(stopped, now=ts(2026, 11, 26, 12, 51))
    fa.step(stopped, now=ts(2026, 11, 26, 13, 0, 30))
    check("FastAlarm pushes 'CLOSE THE TRADE NOW' although 6 alarms went out today; no 'Back to normal' when the halt passes",
          [p.get("code") for p in sent] == ["halt_open"] and sent[0].get("title") == "CLOSE THE TRADE NOW", sent)
    sent.clear()
    fa2 = FA.FastAlarm(send=lambda p: (sent.append(p), "sent")[1], clock=lambda: 0)
    fa2.step(stopped, now=ts(2026, 11, 26, 12, 51))
    _pos(folder, "MNQ 12-26 Globex", "MFFUEVLB25K9991234", "FLAT;0;0")
    fa2.step(stopped, now=ts(2026, 11, 26, 12, 53))
    check("closed by hand at 12:53 -> one 'Back to normal: flat before the halt'",
          len(sent) == 2 and sent[1].get("back") and "flat" in sent[1].get("body", ""), sent)
    _pos(folder, "MNQ 12-26 Globex", "MFFUEVLB25K9991234", "SHORT;2;20950.25")
    import time as _t
    t0 = _t.perf_counter()
    for _ in range(200):
        ev(running, ts(2026, 11, 20, 10, 0))
    check("outside the 10 halt minutes the check reads no file (200 evaluations of a normal 10:00 < 50 ms)",
          _t.perf_counter() - t0 < 0.05, _t.perf_counter() - t0)


def t_restart(tmp):
    print("r. a restart between the entry fill and its bracket, the bot NOT resumed (an eval without auto-resume)", flush=True)
    import json
    from engine import fast_alarm as FA
    from engine.ninjatrader import NinjaTraderAdapter, _FakeNT
    folder = os.path.join(tmp, "NTr")
    sd = os.path.join(tmp, "data_r")
    os.makedirs(sd, exist_ok=True)
    fake = _FakeNT(folder)
    T = ts(2026, 11, 23, 4, 0, 5)
    now = [float(T)]
    cfg = {"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_account": "Sim101", "nt_folder": folder,
           "params": {"max_micros": 40, "flat_mod": 955}, "model": "lit", "model_params": {"window": [[120, 930]]},
           "nt_max_entries_day": 999, "nt_state_path": os.path.join(sd, "ninjatrader_state_acctb.json"),
           "nt_audit_log": os.path.join(tmp, "oif_r.log")}

    def make():
        ad = NinjaTraderAdapter(cfg, clock=lambda: now[0])
        ad._sleep = lambda s: (fake.process(), now.__setitem__(0, now[0] + s))
        ad._alert_fn = lambda *a, **k: None
        return ad

    class _Crash(Exception):
        pass
    ad = make()
    real_send = ad._send_lines

    def crash_after_entry(lines, label):
        r = real_send(lines, label)
        if label == "ENTRY":
            fake.process()                              # NinjaTrader fills the market entry
            raise _Crash()                              # the PC / server dies before the stop + target go out
        return r
    ad._send_lines = crash_after_entry
    try:
        ad.place_bracket({"sym": "NQ", "side": "sell", "qty": 2, "stop": fake.price + 20, "target": fake.price - 60,
                          "entry": fake.price, "entry_t": T - 5})
    except _Crash:
        pass
    inst = ad._instruments()["micro"]
    pos = ad.position_for(inst) or {}
    st = json.load(open(cfg["nt_state_path"]))
    working = [o for o in fake.orders.values() if o.get("state") in ("WORKING", "ACCEPTED")]
    check("after the crash: NinjaTrader holds SHORT 2 with NO working stop / target; the state file kept the leg "
          "('entry_sent', write-ahead)", pos.get("side") == "SHORT" and not working
          and [lg["status"] for lg in st["legs"]] == ["entry_sent"], (pos, working, st.get("legs")))
    # the same files as they would sit on the owner's PC for a real account (the adapter's live gate keeps tests on Sim)
    real = "MFFUFUNDB25K0000678"
    st["account"] = real
    json.dump(st, open(cfg["nt_state_path"], "w"))
    _pos(folder, inst, real, f"SHORT;2;{fake.price}")
    stopped = types.SimpleNamespace(running=False, cfg={"adapter": "ninjatrader", "nt_folder": folder})
    ns = getattr(FA, "no_stop", None)
    e30 = ns(stopped, T + 30, state_dir=sd) if ns else None
    e90 = ns(stopped, T + 90, state_dir=sd) if ns else None
    check("bot stopped 90 s after that entry, real account short with no bracket -> 'TRADE HAS NO STOP' alarm "
          "(not in the first 60 s: a running adapter is still placing it)", e30 is None and e90 and "NO stop" in e90
          and "..0678" in e90, (e30, e90))
    run = types.SimpleNamespace(running=True, cfg={"adapter": "ninjatrader", "nt_folder": folder})
    check("bot running again -> no 'no stop' alarm (its first tick places the bracket)", ns is not None and ns(run, T + 90, state_dir=sd) is None)
    st["day"] = "2026-11-20"
    json.dump(st, open(cfg["nt_state_path"], "w"))
    check("another day's state file (the adapter ignores it) -> no alarm", ns is not None and ns(stopped, T + 90, state_dir=sd) is None)
    # the restarted adapter (bot back on) protects the trade once, with no second entry
    st["day"], st["account"] = "2026-11-23", "Sim101"
    json.dump(st, open(cfg["nt_state_path"], "w"))
    ad2 = make()
    ad2.tick()
    fake.process()
    lg = ad2.legs[0] if ad2.legs else {}
    entries = sum(1 for _, ls in fake.files for ln in ls if ln.startswith("PLACE") and ln.rstrip(";").split(";")[5:6] == ["MARKET"])
    r2 = ad2.send({"sym": "NQ", "side": "sell", "qty": 2, "stop": fake.price + 20, "target": fake.price - 60,
                   "entry": fake.price, "entry_t": T + 60})
    check("bot back on: the restarted adapter places the stop + target at its first tick, sends no second entry and "
          "refuses a new one while the bracket is open", lg.get("status") == "protected" and entries == 1 and not r2.get("ok"),
          (lg.get("status"), entries, r2.get("error")))


def main():
    tmp = tempfile.mkdtemp(prefix="rt2_")
    try:
        for t in (t_halt, t_restart):
            try:
                t(tmp)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{t.__name__} ran", False, e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(ok for _, ok in RESULTS)
    print(f"\nredteam2 live: {n}/{len(RESULTS)} checks passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
