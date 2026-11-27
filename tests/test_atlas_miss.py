"""ATLAS's funded 25K skipped S/R at 10:10 ET with no reason (day-atlasmiss, 2026-11-27): S/R LONG traded on Zlarior 50K (combo)
and the Rapid EOD 25K (+$304 each, 1 micro), nothing on ATLAS's own funded account, and no "why" anywhere.

    python -X utf8 -m tests.test_atlas_miss          # ~20 s, temp folders only, nothing routed to a broker

  1. the replay of today's 10:10 S/R LONG (entry 26,289.50, stop 26,210.75, target 26,440.25) on the funded spec: B routes
     1 MNQ LONG (the funded 40% sizing), also while the combo holds the same LONG on Zlarior's 50K (one direction is allowed)
  2. a stuck position record (an entry of Nov 20 still marked open, NinjaTrader FLAT, no order working): B does not route, but
     says why (held code "open", since = that entry), the 15-minute status shows it (account_b.status_tiny -> pc_report core
     "ab"), trade_watch pushes "missed" naming the stuck record
  3. the self-heal (heal_stale): cleared only on two FLAT reads >= 2 min apart, then one log line + one Board event "ATLAS funded:
     cleared a stuck position record", and the same 10:10 open routes 1 MNQ; NEVER cleared when NinjaTrader shows a position, a
     leg is working, the position file is missing, the entry is under 30 min old, or the adapter is paper
  4. every other silent skip leaves its reason: late (> 45 s), kill switch; a soft reason never overwrites a real one
  5. trade_watch: B never checked the open while running (no probe, no reason, state saved after it) -> "missed"; PC off -> nothing
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_b as AB  # noqa: E402
from engine import board_events  # noqa: E402
from engine import second  # noqa: E402
from tools import pc_report as PR  # noqa: E402
from tools import trade_watch as TW  # noqa: E402

RES = []
TB = 1795792200                    # Fri 2026-11-27 10:10 ET (the real S/R LONG)
OLD = 1795164300                   # Thu 2026-11-20 EMA SHORT (B's last real trade)
KEY = "sr_nyreclaim"
SIG = {"entry_t": TB, "exit_kind": "OPEN", "dir": 1, "entry": 26289.5, "stop": 26210.75, "target": 26440.25, "qty": 3}


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


class FakeBot:
    def __init__(self, now):
        self._now = now
        self.state = {"price": 26289.5}
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


class NTStub:
    """A NinjaTrader-like adapter: legs, position files per contract (None = no file), every order taken."""
    name = "stub"

    def __init__(self, pos="FLAT", legs=None, files=True):
        self.legs, self.history, self.pos, self.files, self.sent = list(legs or []), [], pos, files, []

    def send(self, action):
        self.sent.append(dict(action))
        if action.get("side") in ("buy", "sell"):
            return {"ok": True, "legs": [{"instrument": "MNQ 12-26", "qty": action["qty"], "filled": action["qty"], "ok": True}]}
        return {"ok": True}

    def _instruments(self):
        return {"mini": "NQ 12-26", "micro": "MNQ 12-26"}

    def position_for(self, inst):
        if not self.files:
            return None
        if inst == "MNQ 12-26" and self.pos != "FLAT":
            return {"side": self.pos, "qty": 1}
        return {"side": "FLAT", "qty": 0}


class Paper:
    name = "paper"

    def __init__(self):
        self.sent = []

    def send(self, action):
        self.sent.append(dict(action))
        return {"ok": True}


def spec():
    blk = {"account": "Sim6018", "plan": "builder25k", "stage": "funded", "funded_start": "2026-11-17", "funded_balance": 25000,
           "strategies": ["ema_lon_vix", "macd_sweep", KEY], "sizing": "need", "armed": True}
    return AB.normalize(blk, second.load_cfg())


def keys_file(root):
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    json.dump({"account_b": {"account": "SIM-B", "plan": "builder25k", "strategies": ["ema_lon_vix", "macd_sweep", KEY]}},
              open(os.path.join(root, "data", "account_b.json"), "w"))


def frames():
    t5 = [TB - 300 * i for i in range(60, 0, -1)]
    t1 = [TB - 60 * i for i in range(120, 0, -1)]
    row = lambda t: {"time": t, "open": 26280.0, "high": 26290.0, "low": 26270.0, "close": 26285.0, "volume": 100.0}
    return pd.DataFrame([row(t) for t in t5]), pd.DataFrame([row(t) for t in t1])


def make(tmp, adapter, now=TB + 12):
    bot = FakeBot(now)
    B = AB.AccountB(bot, spec(), state_path=os.path.join(tmp, f"b_{len(os.listdir(tmp))}.json"))
    B.adapter = adapter
    return bot, B


def enter(B, now=None, trade=SIG):
    real = second.run
    second.run = lambda *a, **k: {"strategies": {KEY: {"short": "S/R", "trades": [dict(trade)]}}}
    try:
        df5, df1 = frames()
        sub = {"strategies": {KEY: {"short": "S/R", "route": True}}}
        B.entry(df5, df1, sub, [KEY], "NQ", now if now is not None else B.clock())
    finally:
        second.run = real


def stick(B):
    """A Nov 20 entry still marked open (the suspected state on the PC)."""
    B.open_t = OLD
    B.prov[OLD] = {"key": "ema_lon_vix", "short": "EMA", "qty": 1, "dir": -1, "entry": 26380.75, "stop": 26419.5,
                   "target": 26122.75, "day": "2026-11-20"}


def buys(ad):
    return [a for a in ad.sent if a.get("side") in ("buy", "sell")]


def part1(tmp):
    bot, B = make(tmp, NTStub())
    enter(B)
    b = buys(B.adapter)
    check("1. today's 10:10 S/R LONG on the funded spec: B routes 1 MNQ LONG (funded 40% of the $1,000 room)",
          len(b) == 1 and b[0]["side"] == "buy" and b[0]["qty"] == 1 and b[0]["src"] == KEY and B.open_t == TB, (b, bot.logs[-3:]))
    bot2, B2 = make(tmp, NTStub())
    bot2._open_routed = TB                                   # the combo's ATLAS LONG on Zlarior's 50K, same open
    bot2.ledger = [{"side": "buy", "entry_t": TB, "qty": 1}]
    bot2.state["position"] = {"dir": 1}
    enter(B2)
    check("1. ... also while the combo holds the same LONG on Zlarior's 50K (one direction across accounts is allowed)",
          len(buys(B2.adapter)) == 1 and B2.open_t == TB, bot2.logs[-3:])


def part2(tmp):
    bot, B = make(tmp, NTStub())
    stick(B)
    enter(B)
    h = B.held.get(str(TB)) or {}
    check("2. stuck record: nothing routed, but B says why (held code 'open', since the Nov 20 entry)",
          not buys(B.adapter) and h.get("code") == "open" and h.get("since") == OLD and "still open" in h.get("why", ""), h)
    B.save()
    st = AB.status_tiny(B.state_path, now=TB + 60)
    check("2. ... the 15-minute status block shows the open record and today's reason", st and st["o"] == OLD and st["hn"] == 1
          and st["h"][0][0] == TB and "still open" in st["h"][0][2], st)
    core = PR.split({"t": TB + 60, "v": 1, "kind": "le-live", "ab": st})[0]
    check("2. ... it rides the CORE post (every 15 minutes), small", core.get("ab", {}).get("o") == OLD
          and len(json.dumps(core["ab"])) <= 360, core.get("ab"))
    root = os.path.join(tmp, "tw")
    keys_file(root)
    shutil.copy(B.state_path, os.path.join(root, "data", "live_state_acctb.json"))
    tw = {"2026-11-27": [{"key": KEY, "short": "S/R", "entry_t": TB, "dir": 1, "entry": 26289.5, "stop": 26210.75, "usd": 304.1}]}
    fl = TW.atlas_flags(root, now=TB + 3600, twin=lambda days, keys: tw)
    check("2. ... trade_watch pushes 'missed' naming the stuck record", len(fl) == 1 and fl[0]["code"] == "missed"
          and "stuck" in fl[0]["body"] and "+$304" in fl[0]["body"], fl)


def part3(tmp):
    ev = []
    real = board_events.emit
    board_events.emit = lambda *a, **k: ev.append(a)
    try:
        bot, B = make(tmp, NTStub())
        stick(B)
        r1 = B.heal_stale(TB - 300)
        r2 = B.heal_stale(TB - 250)
        check("3. one FLAT read is not enough, nor a second one under 2 min later", not r1 and not r2 and B.open_t == OLD)
        r3 = B.heal_stale(TB - 120)
        pv = B.prov.get(OLD) or {}
        check("3. two FLAT reads >= 2 min apart: the stuck record is cleared (final, reason kept)", r3 and B.open_t is None
              and pv.get("final") and "FLAT" in (pv.get("stale_cleared") or {}).get("why", ""), pv)
        check("3. ... one log line + one Board event 'ATLAS funded: cleared a stuck position record'",
              len(ev) == 1 and ev[0][0] == "risk_alert" and ev[0][1] == "atlas" and ev[0][2] == "ATLAS funded: cleared a stuck position record"
              and any("cleared a stuck position record" in t for _, t in bot.logs), (ev, bot.logs[-2:]))
        enter(B)
        check("3. ... and the 10:10 S/R LONG routes 1 MNQ", len(buys(B.adapter)) == 1 and B.open_t == TB, bot.logs[-3:])
        st = AB.status_tiny(B.state_path, now=TB + 60)
        check("3. ... the status shows the clear [t, entry_t]", st and st.get("sc") == [TB - 120, OLD], st)

        def never(name, adapter, now0=TB - 300, setup=None):
            n0 = len(ev)
            _, Bx = make(tmp, adapter)
            stick(Bx)
            if setup:
                setup(Bx)
            for dt_ in (0, 130, 260, 400):
                Bx.heal_stale(now0 + dt_)
            check(f"3. never cleared: {name}", Bx.open_t is not None and len(ev) == n0, Bx.open_t)
        never("NinjaTrader shows a LONG on MNQ", NTStub(pos="LONG"))
        never("a leg of the account is working", NTStub(legs=[{"instrument": "MNQ 12-26", "entry_t": OLD, "status": "protected"}]))
        never("no position file (a NinjaTrader restart proves nothing)", NTStub(files=False))
        never("the paper adapter (it keeps its own book)", Paper())
        never("an entry under 30 min old", NTStub(), now0=TB + 60, setup=lambda Bx: (setattr(Bx, "open_t", TB),
              Bx.prov.__setitem__(TB, {"key": KEY, "short": "S/R", "qty": 1, "dir": 1, "day": "2026-11-27"})))
        _, Bc = make(tmp, NTStub())
        stick(Bc)
        Bc.prov[OLD]["closing"] = {"reason": "NO TRADE", "done": False, "t": OLD + 600}
        Bc.heal_stale(TB - 300)
        Bc.heal_stale(TB - 120)
        check("3. a close never confirmed (no leg, NinjaTrader FLAT twice) is freed too, its close marked done",
              Bc.open_t is None and Bc.prov[OLD]["closing"]["done"] and not Bc.closing_open())
    finally:
        board_events.emit = real


def part4(tmp):
    bot, B = make(tmp, NTStub())
    enter(B, now=TB + 60)
    h = B.held.get(str(TB)) or {}
    check("4. a 5m open first checked 60 s late: not probed, reason 'late' kept", not buys(B.adapter) and h.get("code") == "late"
          and "60 s" in h.get("why", ""), h)
    enter(B, now=TB + 70)
    check("4. ... written once (not a new reason every poll)", (B.held.get(str(TB)) or {}).get("why") == h.get("why"))
    bot2, B2 = make(tmp, NTStub())
    bot2.kill = True
    enter(B2)
    check("4. kill switch: nothing routed, reason 'kill'", not buys(B2.adapter) and (B2.held.get(str(TB)) or {}).get("code") == "kill")
    B2._hold(TB + 300, None, "late x", code="late")
    B2._hold(TB + 300, KEY, "no hedging: LIT is in a SHORT trade")
    B2._hold(TB + 600, KEY, "size 0 (x)")
    B2._hold(TB + 600, None, "late y", code="late")
    check("4. a real reason overwrites a soft one, never the other way", B2.held[str(TB + 300)]["why"].startswith("no hedging")
          and "code" not in B2.held[str(TB + 300)] and B2.held[str(TB + 600)]["why"] == "size 0 (x)", B2.held)


def part5(tmp):
    tw = {"2026-11-27": [{"key": KEY, "short": "S/R", "entry_t": TB, "dir": 1, "entry": 26289.5, "stop": 26210.75, "usd": 304.1}]}

    def flags(saved_at, probes):
        root = tempfile.mkdtemp(dir=tmp)
        keys_file(root)
        st = {"v": 1, "account": "SIM-B", "ledger": [], "seen": [["probe", t] for t in probes], "held": {}, "saved_at": saved_at}
        json.dump(st, open(os.path.join(root, "data", "live_state_acctb.json"), "w"))
        return TW.atlas_flags(root, now=TB + 3600, twin=lambda days, keys: tw)
    f = flags(TB + 900, [TB - 300])
    check("5. B never checked the 10:10 open while running (no probe, no reason, saved after it): 'missed'",
          len(f) == 1 and "never checked that open" in f[0]["body"], f)
    check("5. PC off at 10:10 (state last saved before it): nothing", flags(TB - 600, [TB - 300]) == [])


def main():
    tmp = tempfile.mkdtemp(prefix="atlasmiss_")
    try:
        for fn in (part1, part2, part3, part4, part5):
            try:
                fn(tmp)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{fn.__name__} raised {e.__class__.__name__}: {e}", False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if RES and all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
