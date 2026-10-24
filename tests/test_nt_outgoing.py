"""NinjaTrader outgoing\\ files: names, a NinjaTrader restart, a rejected stop, a disconnect (pre-launch audit 2026-10-24).

    python -X utf8 -m tests.test_nt_outgoing          (~5 s, offline: engine/ninjatrader._FakeNT on temp folders, Sim101)

  1. Position file names: 'MNQ 12-26 Globex_<Account>_Position.txt' with an MFFU-style account (letters + digits), an account
     with spaces, the instrument spelled 'MNQ 12-26' / 'MNQ DEC26' / 'MNQ 1226'; another account whose name ends in ours is
     not ours; the reconcile guard (engine/guards._broker_net) reads the same files.
  2. NinjaTrader restart with an open, protected trade (outgoing\\ wiped): never read as flat, nothing is written (no
     re-entry, no flatten), new entries refused + one alert; the position file comes back -> entries allowed again, the
     missing stop / target reports flagged; the broker's stop still closes the trade and the bot sees it.
  3. Restart while flat: a FLAT position file that vanishes blocks nothing. A non-FLAT one (a position the bot does not
     hold) blocks until the file is back or the owner runs --confirm-reset.
  4. Restart while an entry is in flight (its order report gone): once the position file shows the position, the bot places
     the stop and target (never a naked position); a pending entry is never retired as "flat" on missing files.
  5. Python restart: the reset state survives in ninjatrader_state.json (still blocked after a restart of the bot).
  6. Stop REJECTED after the fill -> CLOSEPOSITION at once + alert; stop CANCELLED outside the bot -> flatten.
  7. All connections DISCONNECTED with a trade open -> one alert (rate-limited); new entries refused.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import ninjatrader as nt  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not ok else ""), flush=True)


class Env:
    """One temp NinjaTrader folder + _FakeNT + an adapter on Sim101 at 10:00 ET on a weekday (clock fixed)."""

    def __init__(self, tmp, name, account="Sim101", inst="MNQ 12-26"):
        self.dir = os.path.join(tmp, name)
        self.folder = os.path.join(self.dir, "NinjaTrader 8")
        self.fake = nt._FakeNT(self.folder, price=25020.0)
        self.alerts = []
        self.account, self.inst = account, inst
        self.ad = self.make()

    def make(self):
        import datetime as dt
        t10 = dt.datetime(2026, 10, 21, 10, 0, tzinfo=nt.ET).timestamp()
        ad = nt.NinjaTraderAdapter({"nt_folder": self.folder, "nt_account": self.account, "nt_instrument": self.inst,
                                    "nt_state_path": os.path.join(self.dir, "nt_state.json"),
                                    "nt_audit_log": os.path.join(self.dir, "oif.log"), "nt_ack_wait_s": 0.2,
                                    "nt_fill_wait_s": 0.2, "nt_verify_wait_s": 0.2, "model": "lit"},
                                   clock=lambda: t10 + (time.time() - T0))
        ad._alert_fn = self.alerts.append
        ad._sleep = lambda s_: (self.fake.process(), time.sleep(min(s_, 0.002)))
        return ad

    def lines(self):
        return [ln for _, ls in self.fake.files for ln in ls]

    def wipe(self):
        for fn in os.listdir(self.fake.out):
            os.remove(os.path.join(self.fake.out, fn))

    def back(self):
        time.sleep(0.02)
        self.fake._write("Tradovate.txt", "CONNECTED")
        for acct, inst in list(self.fake.pos):
            self.fake._write_pos(acct, inst)

    def buy(self, qty=2):
        return self.ad.send({"side": "buy", "qty": qty, "stop": 24990.0, "target": 25080.0, "entry": 25020.0, "sym": "NQ",
                             "entry_t": int(self.ad.clock())})


T0 = time.time()


def test_names(tmp):
    print("== 1. outgoing position file names")
    ok = all(nt.inst_key(a) == (r, m, y) for a, (r, m, y) in (
        ("MNQ 12-26", ("MNQ", 12, 26)), ("MNQ 12-26 Globex", ("MNQ", 12, 26)), ("MNQ DEC26 Globex", ("MNQ", 12, 26)),
        ("mnq Dec26", ("MNQ", 12, 26)), ("MNQ 1226 Globex", ("MNQ", 12, 26)), ("NQ 03-27 Globex", ("NQ", 3, 27))))
    check("inst_key: 'MNQ 12-26', 'MNQ 12-26 Globex', 'MNQ DEC26 Globex', 'mnq Dec26', 'MNQ 1226 Globex' = MNQ Dec 2026", ok)
    check("same_instrument: MNQ DEC26 Globex = MNQ 12-26; MNQ 03-27 / NQ 12-26 / MES 12-26 are not",
          nt.same_instrument("MNQ DEC26 Globex", "MNQ 12-26") and not nt.same_instrument("MNQ 03-27 Globex", "MNQ 12-26")
          and not nt.same_instrument("NQ 12-26 Globex", "MNQ 12-26") and not nt.same_instrument("MES 12-26 Globex", "MNQ 12-26"))
    from engine import guards
    for acct, fname in (("MFFUEVBLDR602936016", "MNQ 12-26 Globex_MFFUEVBLDR602936016_Position.txt"),
                        ("My Eval 50K", "MNQ 12-26 Globex_My Eval 50K_Position.txt"),
                        ("MFFUEVBLDR602936016", "MNQ DEC26 Globex_MFFUEVBLDR602936016_Position.txt"),
                        ("MFFUEVBLDR602936016", "MNQ 1226 Globex_MFFUEVBLDR602936016_Position.txt")):
        d = os.path.join(tmp, "names", fname.replace(" ", "_"))
        out = os.path.join(d, "outgoing")
        os.makedirs(out, exist_ok=True)
        os.makedirs(os.path.join(d, "incoming"), exist_ok=True)
        with open(os.path.join(out, fname), "w", encoding="utf-8") as fh:
            fh.write("LONG; 3; 25020.25")
        with open(os.path.join(out, "MNQ 12-26 Globex_X_" + acct + "_Position.txt"), "w", encoding="utf-8") as fh:
            fh.write("SHORT;7;25000")                        # another account whose name ends in ours
        with open(os.path.join(out, "MNQ 12-26 Globex_Sim101_Position.txt"), "w", encoding="utf-8") as fh:
            fh.write("SHORT;5;25000")                        # another account
        ad = nt.NinjaTraderAdapter({"nt_folder": d, "nt_account": acct, "nt_instrument": "MNQ 12-26",
                                    "nt_state_path": os.path.join(d, "s.json")}, readonly=True)
        p = ad.position_for("MNQ 12-26")
        allp = ad.positions()["positions"]
        net, held = guards._broker_net(ad)
        check(f"account {acct!r}, file {fname!r}: LONG 3 @ 25020.25 found, other accounts ignored, reconcile net +3",
              p is not None and p["side"] == "LONG" and p["qty"] == 3 and p["avg"] == 25020.25 and len(allp) == 1 and net == 3,
              f"{p} {allp} {net} {held}")


def test_nt_restart_in_trade(tmp):
    print("== 2. NinjaTrader restart with a protected trade open")
    e = Env(tmp, "restart_trade")
    r = e.buy()
    e.ad.tick()
    lg = e.ad.legs[0] if e.ad.legs else {}
    check("setup: bracket placed and protected, order files seen", r.get("ok") and lg.get("status") == "protected"
          and set(lg.get("seen_ids") or []) >= {lg.get("stop_id"), lg.get("target_id")}, json.dumps(r)[:200])
    n0, a0 = len(e.lines()), len(e.alerts)
    e.wipe()
    for _ in range(3):
        e.ad.tick()
    check("outgoing wiped: reset noticed, ONE alert, the leg stays protected (never read as flat)",
          e.ad.nt_reset is not None and len(e.alerts) == a0 + 1 and "does NOT assume flat" in e.alerts[-1]
          and e.ad.legs and e.ad.legs[0]["status"] == "protected", f"{e.ad.nt_reset} {e.alerts[a0:]}")
    check("outgoing wiped: nothing written by the bot (no re-entry, no flatten, no cancel)", len(e.lines()) == n0,
          str(e.lines()[n0:]))
    check("outgoing wiped: _is_flat on a missing position file is False", not e.ad._is_flat("MNQ 12-26", None)
          and not e.ad._is_flat("MNQ 12-26", lg.get("fill_mtime")))
    # the trade is closed by the broker while the bot is blind? no: the files are back first
    e.back()
    e.ad.tick()
    check("position file back: reset cleared, the missing stop/target reports flagged in an alert",
          e.ad.nt_reset is None and any("did not come back" in x for x in e.alerts[a0 + 1:]), f"{e.alerts[a0 + 1:]}")
    e.ad.tick()
    check("after the reset clears: no new reset from the same files", e.ad.nt_reset is None)
    e.fake.move(24990.0)                                 # the broker's stop fills (NinjaTrader writes its order file again)
    e.ad.tick()
    check("the broker stop fills after the restart: the bot sees it and retires the bracket (no CLOSEPOSITION needed)",
          not e.ad.legs and e.fake.pos.get(("Sim101", "MNQ 12-26"), [0])[0] == 0, json.dumps(e.ad.legs)[:200])


def test_nt_restart_flat(tmp):
    print("== 3. NinjaTrader restart while flat")
    e = Env(tmp, "restart_flat")
    e.fake.pos[("Sim101", "MNQ 12-26")] = [0, 0.0]
    e.fake._write_pos("Sim101", "MNQ 12-26")
    e.ad.tick()
    e.wipe()
    e.ad.tick()
    r = e.buy()
    check("a FLAT position file that vanishes blocks nothing (an NinjaTrader restart cannot open a position)",
          e.ad.nt_reset is None and r.get("ok"), json.dumps(r)[:200])
    e2 = Env(tmp, "restart_manual")
    e2.fake.pos[("Sim101", "MNQ 12-26")] = [-1, 25010.0]       # a position the bot does not hold (manual)
    e2.fake._write_pos("Sim101", "MNQ 12-26")
    e2.ad.tick()
    e2.wipe()
    e2.ad.tick()
    r = e2.buy()
    check("a SHORT position file that vanishes: reset + alert, the entry is REFUSED",
          e2.ad.nt_reset is not None and not r.get("ok") and "reset" in r.get("error", "") and e2.alerts, json.dumps(r)[:200])
    e2.ad.tick()
    check("still blocked while no position file and no confirmation", e2.ad.nt_reset is not None)
    with open(e2.ad.reset_ok_path, "w", encoding="utf-8") as fh:
        json.dump({"t": time.time() + 1}, fh)
    e2.ad.tick()
    check("owner confirmation file (python -m engine.ninjatrader --confirm-reset) clears it", e2.ad.nt_reset is None)


def test_nt_restart_in_flight(tmp):
    print("== 4. NinjaTrader restart while the entry is in flight")
    e = Env(tmp, "restart_flight")
    e.fake.hold_market = True                     # NinjaTrader accepts the market order but reports no fill yet
    r = e.buy(qty=3)
    e.ad.tick()
    lg = e.ad.legs[0] if e.ad.legs else {}
    check("setup: entry pending (no fill report yet), its order file seen", lg.get("status") == "pending"
          and lg.get("entry_id") in (lg.get("seen_ids") or []), json.dumps(r)[:200])
    e.wipe()
    # it fills while NinjaTrader restarts: the broker has the position, no order report is ever written for the entry
    e.fake.pos[("Sim101", "MNQ 12-26")] = [3, 25021.0]
    e.ad.tick()
    lg = e.ad.legs[0] if e.ad.legs else {}
    lg["sent_at"] -= 10 * 3600                     # long past every timeout: still never retired as "flat"
    lg["status"], lg["cancel_sent"] = "cancel_pending", e.ad.clock() - 10 * 3600
    e.ad.tick()
    check("reset while pending: the leg is never retired on missing files", e.ad.legs and e.ad.nt_reset is not None,
          json.dumps(e.ad.legs)[:200])
    n0 = len(e.lines())
    e.fake.hold_market = False
    e.back()
    e.ad.tick()
    new = e.lines()[n0:]
    check("position file back (LONG 3): the in-flight entry is treated as filled and gets its stop + target",
          any(";SELL;3;STOPMARKET;0;24990.00;" in x for x in new) and any(";LIMIT;25080.00;" in x for x in new)
          and e.ad.legs and e.ad.legs[0]["status"] == "protected", str(new))


def test_python_restart(tmp):
    print("== 5. Python restart during an unresolved NinjaTrader reset")
    e = Env(tmp, "py_restart")
    e.buy()
    e.ad.tick()
    e.wipe()
    e.ad.tick()
    ad2 = e.make()                                  # a new process: same ninjatrader_state.json
    check("restored after a Python restart: the open bracket and the reset (still blocked)",
          ad2.legs and ad2.nt_reset is not None and ad2.legs[0]["status"] == "protected")
    ad2.tick()
    check("restored adapter does not write anything on missing files", len(e.lines()) == 3, str(e.lines()))


def test_reject_and_disconnect(tmp):
    print("== 6. stop REJECTED / cancelled outside the bot; 7. disconnect")
    e = Env(tmp, "reject")
    e.fake.reject = {"STOPMARKET"}
    r = e.buy()
    closes = [x for x in e.lines() if x.startswith("CLOSEPOSITION;Sim101;MNQ 12-26")]
    check("stop REJECTED after the fill: CLOSEPOSITION at once, alert, the account flat",
          not r.get("ok") and closes and e.alerts and e.fake.pos.get(("Sim101", "MNQ 12-26"), [0])[0] == 0
          and not e.ad.legs, json.dumps(r)[:200])
    e2 = Env(tmp, "cancel_outside")
    e2.buy()
    sid = e2.ad.legs[0]["stop_id"]
    o = e2.fake.orders[sid]
    o["state"] = "CANCELLED"
    e2.fake._state(sid, o)
    e2.ad.tick()
    check("stop CANCELLED outside the bot: flattened + alert", any(x.startswith("CLOSEPOSITION") for x in e2.lines())
          and e2.fake.pos.get(("Sim101", "MNQ 12-26"), [0])[0] == 0 and any("cancelled/rejected outside" in x for x in e2.alerts))
    e3 = Env(tmp, "disconnect")
    e3.buy()
    e3.fake._write("Tradovate.txt", "DISCONNECTED")
    a0 = len(e3.alerts)
    e3.ad.tick()
    e3.ad.tick()
    check("all connections DISCONNECTED with a trade open: one alert (rate-limited), the trade kept (no flatten written)",
          len(e3.alerts) == a0 + 1 and "DISCONNECTED" in e3.alerts[-1] and e3.ad.legs
          and not any(x.startswith("CLOSEPOSITION") for x in e3.lines()), str(e3.alerts[a0:]))
    e4 = Env(tmp, "disconnect_entry")
    e4.fake._write("Tradovate.txt", "DISCONNECTED")
    r = e4.buy()
    check("all connections DISCONNECTED: a new entry is refused", not r.get("ok") and "DISCONNECTED" in r.get("error", ""))


def main():
    for k in (nt.LIVE_ENV, "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER"):
        os.environ.pop(k, None)
    tmp = tempfile.mkdtemp(prefix="le_nt_outgoing_")
    try:
        for fn in (test_names, test_nt_restart_in_trade, test_nt_restart_flat, test_nt_restart_in_flight, test_python_restart,
                   test_reject_and_disconnect):
            try:
                fn(tmp)
            except Exception as e:
                import traceback
                traceback.print_exc()
                check(f"{fn.__name__}: no exception", False, f"{e.__class__.__name__}: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(ok for _, ok in RESULTS)
    print(f"{n}/{len(RESULTS)} checks passed")
    sys.exit(0 if n == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
