"""Risk monitors (night-risk 2026-11-18, docs/ZEUS_FEATURES.md #14 + #25): the ZEUS circuit breaker (live vs backtest twin ADVICE,
engine/circuit_breaker.py) and the runaway-order throttle (engine/msg_throttle.py, alarm ON, entry block OFF by default).
Temp folders and a simulated NinjaTrader only; nothing is routed to a broker, nothing is armed, the real Board is never written.

  python -X utf8 -m tests.test_risk_monitors        # ~2 s
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import circuit_breaker as CB  # noqa: E402
from engine import msg_throttle as MT  # noqa: E402
from engine import notify  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"))


def ts(y, m, d, hh, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def write(root, rel, obj):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def matched(t, live_pnl, bt_pnl, q=4, entry=25000.0, stop=24990.0):
    # risk = 10 pts x $2 x 4 = $80 a trade
    return {"status": "matched", "entry_t": t, "exit_t": t + 1800, "live_qty": q, "bt_entry": entry, "bt_stop": stop,
            "live_pnl": live_pnl, "bt_pnl_live_qty": bt_pnl}


def breaker_tests(tmp):
    root = os.path.join(tmp, "cb")
    t0 = ts(2026, 11, 10, 9, 40)
    ev = []
    emit = lambda kind, acct, text, data=None: ev.append((kind, acct, text, data))
    # 1. live = twin, even while losing: OK, no push (a losing streak the twin also had is normal)
    write(root, "logs/exec_audit/report.json", {"rows": [matched(t0 + i * 86400, -80.0, -80.0) for i in range(5)]})
    p = CB.flags(root, now=t0 + 6 * 86400, emit=emit)
    v = CB.status(root)["zlarior"]["v"]
    check("breaker: 5 losers that the twin also lost = OK, gap 0R, no push, no Board line", v["level"] == "ok" and v["gap_r"] == 0 and not p and not ev, (v, p, ev))
    # 2. live 1R worse than the twin on 4 trades: gap -4R -> SIZE DOWN (push once + Board)
    rows = [matched(t0 + i * 86400, -80.0, -80.0) for i in range(5)] + [matched(t0 + (5 + i) * 86400, -80.0, 0.0) for i in range(4)]
    write(root, "logs/exec_audit/report.json", {"rows": rows})
    p = CB.flags(root, now=t0 + 10 * 86400, emit=emit)
    v = CB.status(root)["zlarior"]["v"]
    check("breaker: live -1R vs twin on 4 trades = gap -4R = SIZE DOWN", v["level"] == "size_down" and abs(v["gap_r"] + 4) < 1e-6, v)
    check("breaker: SIZE DOWN = one push (key breaker:zlarior:size_down:<newest>, $ first, says advice only)",
          len(p) == 1 and p[0]["key"].startswith("breaker:zlarior:size_down:") and "-$320" in p[0]["body"] and "Advice only" in p[0]["body"]
          and "HALF size" in p[0]["body"], p)
    check("breaker: + one Board event risk_alert on account zlarior", len(ev) == 1 and ev[0][0] == "risk_alert" and ev[0][1] == "zlarior", ev)
    p2 = CB.flags(root, now=t0 + 10 * 86400 + 900, emit=emit)
    check("breaker: the next run with the same trades sends nothing again", not p2 and len(ev) == 1, (p2, ev))
    # 3. one freak trade (-8R vs twin) is clipped to -2R: never PAUSE on one trade
    write(root, "logs/exec_audit/report.json", {"rows": [matched(t0 + i * 86400, 0.0, 0.0) for i in range(4)] + [matched(t0 + 4 * 86400, -80.0, 560.0)]})
    v1 = CB.verdict(CB.lit_pairs(root)[0])
    check("breaker: a single -8R divergence counts -2R (clip): WATCH at most, never PAUSE alone", v1["gap_r"] == -2.0 and v1["level"] == "watch", v1)
    # 4. 6 trades each 1R worse -> PAUSE
    v2 = CB.verdict([{"t": i, "entry_t": i, "live_r": -1.0, "twin_r": 0.0, "gap_usd": -80.0} for i in range(6)])
    check("breaker: gap -6R = PAUSE (recommend the phone PAUSE)", v2["level"] == "pause" and "PAUSE" in CB.text("zlarior", v2)[1], v2)
    check("breaker: fewer than 3 trades = no verdict", CB.verdict([{"t": 1, "entry_t": 1, "live_r": -5, "twin_r": 0, "gap_usd": -400}])["level"] == "ok")
    # 5. recovery: back to normal = Board line, no push
    root2 = os.path.join(tmp, "cb2")
    ev2 = []
    em2 = lambda kind, acct, text, data=None: ev2.append((kind, acct, text, data))
    write(root2, "logs/exec_audit/report.json", {"rows": [matched(t0 + i * 86400, -80.0, 0.0) for i in range(4)]})
    CB.flags(root2, now=t0 + 5 * 86400, emit=em2)
    good = [matched(t0 + i * 86400, -80.0, 0.0) for i in range(4)] + [matched(t0 + (4 + i) * 86400, 80.0, 0.0) for i in range(3)]
    write(root2, "logs/exec_audit/report.json", {"rows": good})
    p3 = CB.flags(root2, now=t0 + 9 * 86400, emit=em2)
    check("breaker: the gap recovers (-4R -> -1R) = 'back to normal' Board line, no push",
          not p3 and len(ev2) == 2 and "back to normal" in ev2[-1][2] and ev2[-1][3]["level"] == "ok", (p3, ev2))
    # 6. ATLAS: account B's ledger vs the trade_watch twin (twin carries r)
    root3 = os.path.join(tmp, "cb3")
    from engine.account_b import trading_day
    led, twin = [], {}
    for i in range(4):
        t = ts(2026, 11, 9 + i, 10, 0)
        led.append({"t": t + 5, "side": "buy", "qty": 2, "stop": 24990.0, "entry": 25000.0, "entry_t": t, "src": "macd",
                    "result": {"ok": True, "legs": [{"fill_px": 25000.0, "filled": 2}]}})
        led.append({"t": t + 900, "side": "exit", "qty": 2, "reason": "STOP", "pnl": -40.0, "entry_t": t, "exit_t": t + 900})
        twin.setdefault(trading_day(t), {"sig": "x", "trades": []})["trades"].append(
            {"key": "macd", "entry_t": t, "dir": 1, "entry": 25000.0, "stop": 24990.0, "exit_kind": "TARGET", "usd": 40.0, "r": 1.0})
    write(root3, "data/live_state_acctb.json", {"ledger": led})
    write(root3, "logs/exec_audit/atlas_twin.json", twin)
    pa, _ = CB.atlas_pairs(root3)
    va = CB.verdict(pa)
    check("breaker: ATLAS 4 live stops (-1R) where the twin made +1R = gap -8R -> PAUSE ($ gap -$320)",
          len(pa) == 4 and va["level"] == "pause" and va["gap_r"] == -8.0 and round(va["gap_usd"]) == -320, (pa, va))
    os.environ["LE_BREAKER"] = "0"
    try:
        check("breaker: LE_BREAKER=0 = off (no push, no Board)", CB.flags(root3, emit=em2) == [])
    finally:
        os.environ.pop("LE_BREAKER", None)
    check("notify: breaker pushes are type account_status, throttle pushes type problems (both ON by default)",
          notify.kind_of("breaker:atlas:pause:1") == "account_status" and notify.kind_of("risk:throttle:1234:2026-11-18:burst") == "problems"
          and notify.on("account_status", notify.merge({})) and notify.on("problems", notify.merge({})))


def throttle_unit(tmp):
    p = os.path.join(tmp, "th", "ninjatrader_state_msgs.json")
    now = ts(2026, 11, 18, 10, 0)
    th = MT.Throttle(p, "MFFUEVBLDR001234", {"nt_msg_per_min": 3})
    trips = [th.note(["CANCEL;;;;;;;;;;LE1S;;"], now + i) for i in range(5)]
    got = [x for x in trips if x]
    check("throttle: the 4th order file inside 60 s trips 'burst' once (not again the same day)", len(got) == 1 and got[0]["code"] == "burst"
          and trips[3] is got[0], trips)
    check("throttle: the file keeps the last 4 of the account only", "1234" == json.load(open(p))["acct4"] and "MFFU" not in open(p).read())
    check("throttle: block OFF by default -> entries never refused", th.entry_block(now + 10) is None)
    thb = MT.Throttle(p, "MFFUEVBLDR001234", {"nt_msg_per_min": 3, "nt_msg_throttle_block": True})
    check("throttle: block ON + tripped today -> entries refused (state survives a restart)", "throttle tripped" in (thb.entry_block(now + 20) or ""))
    check("throttle: block ON, next CME day -> entries allowed again", thb.entry_block(ts(2026, 11, 19, 10, 0)) is None)
    check("throttle: 18:00 ET counts as the next trading day", MT.trading_day(ts(2026, 11, 18, 18, 5)) == "2026-11-19"
          and MT.trading_day(ts(2026, 11, 20, 18, 5)) == "2026-11-23")
    th2 = MT.Throttle(os.path.join(tmp, "th2", "x_msgs.json"), "Sim101", {"nt_change_per_order": 12})
    tr = [th2.note(["CHANGE;;;;0;;0;25020.25;;;LE9S;;"], now + 120 * i) for i in range(14)]
    check("throttle: 13 stop changes on ONE order id in a day trips 'change' (a stop-modify loop)",
          [x["code"] for x in tr if x] == ["change"] and tr[12] is not None, tr)
    th3 = MT.Throttle(os.path.join(tmp, "th3", "y_msgs.json"), "Sim101", {"nt_msg_per_day": 5, "nt_msg_per_min": 99})
    tr3 = [th3.note(["CANCEL;;;;;;;;;;LE2S;;"], now + 600 * i) for i in range(7)]
    check("throttle: the 6th file of a trading day over a limit of 5 trips 'day'", [x["code"] for x in tr3 if x] == ["day"] and tr3[5] is not None, tr3)
    # flags + reset read data/ninjatrader_state*_msgs.json under a root
    root = os.path.join(tmp, "throot")
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    shutil.copy(p, os.path.join(root, "data", "ninjatrader_state_acctb_msgs.json"))
    fl = MT.flags(root, now=now + 60)
    check("throttle: pc_report hook = one push per trip, key risk:throttle:<last4>:<day>:<code>, body says the block is OFF",
          len(fl) == 1 and fl[0]["key"] == "risk:throttle:1234:2026-11-18:burst" and "Nothing was blocked" in fl[0]["body"], fl)
    check("throttle: --reset clears today's trip (block ON no longer refuses)", MT.reset(root, now=now + 70) == 1 and
          MT.Throttle(os.path.join(root, "data", "ninjatrader_state_acctb_msgs.json"), "x", {"nt_msg_throttle_block": True}).entry_block(now + 80) is None)
    sw = os.path.join(tmp, "sw.json")
    check("throttle: switch file / env: default OFF, file ON, LE_MSG_THROTTLE_BLOCK=0 wins",
          not MT.block_on({}, env={}, switch_path=sw) and (write(tmp, "sw.json", {"block": True}) or MT.block_on({}, env={}, switch_path=sw))
          and not MT.block_on({}, env={"LE_MSG_THROTTLE_BLOCK": "0"}, switch_path=sw))


def throttle_adapter(tmp):
    from engine import ninjatrader as NT
    folder = os.path.join(tmp, "nt", "NinjaTrader 8")
    fake = NT._FakeNT(folder)
    now = [ts(2026, 10, 21, 10, 5)]                 # a Wednesday, in the session
    alerts = []

    def make(extra=None):
        cfg = {"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_folder": folder, "params": {"max_micros": 40, "flat_mod": 955},
               "nt_state_path": os.path.join(tmp, "nt", "nt_state.json"), "nt_audit_log": os.path.join(tmp, "nt", "oif.log"),
               "nt_msg_per_min": 2, **(extra or {})}
        ad = NT.NinjaTraderAdapter(cfg, clock=lambda: now[0])
        ad._sleep = lambda s: (fake.process(), now.__setitem__(0, now[0] + s))
        ad._alert_fn = alerts.append
        return ad

    ad = make()
    for i in range(3):
        ad._write_oif([NT.cancel_line(f"LE{i}S")], "test cancel")
    check("adapter: 3 order files in a minute over a limit of 2 = one critical alert naming the runaway", len(alerts) == 1 and "runaway" in alerts[0], alerts)
    check("adapter: block OFF -> the entry gate stays open after a trip", ad._gate("entry") is None, ad._gate("entry"))
    adb = make({"nt_msg_throttle_block": True})
    g = adb._gate("entry")
    check("adapter: block ON -> new entries / adds refused (REFUSED: message throttle ...)", bool(g) and "message throttle" in g["error"], g)
    check("adapter: block ON never stops a stop change / cancel / close (the modify gate is untouched)", adb._gate("modify") is None)
    w = adb._write_oif([NT.cancel_line("LE7S")], "test cancel")
    check("adapter: block ON -> a protective file (CANCEL) is still written", w["ok"], w)
    ro = NT.NinjaTraderAdapter({"adapter": "ninjatrader", "nt_folder": folder, "account": "Sim101",
                                "nt_state_path": os.path.join(tmp, "nt", "ro.json")}, readonly=True)
    check("adapter: a read-only adapter has no throttle (never writes a file)", ro.throttle is None)
    fake.release()


def main():
    tmp = tempfile.mkdtemp(prefix="risk_mon_")
    os.environ["LE_BOARD_DIR"] = os.path.join(tmp, "board")
    try:
        breaker_tests(tmp)
        throttle_unit(tmp)
        throttle_adapter(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nrisk monitors: {n}/{len(RES)} passed")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
