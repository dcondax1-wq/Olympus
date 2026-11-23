"""A damaged state file never means a clean day (night-statesafe 2026-11-23, engine/state_safe.py, engine/live.py _restore /
_save_state, engine/account_b.py _load / save).

  a. every save keeps the previous good copy (.bak); a damaged file never replaces a good .bak
  b. LIT: unreadable live_state.json + today's .bak -> the kill flag, today's ledger (daily loss), trades today come back
  c. LIT: no usable copy -> rebuild from logs/exec_audit only when PROVED complete (rebuild_lit: the copy ran after the last order,
     no entry left open); else NO NEW ENTRIES today (the LIT entry is not routed, the reason is logged) + ONE phone message;
     the pause outlives a restart the same day and ends on the next trading day
  d. ATLAS (account_b): the same: today's .bak; else the older .bak's history + a lock-out for today (its own lock path)
  e. a healthy start is unchanged (no pause, no message, the state restored exactly as before)
    python -X utf8 -m tests.test_state_safe        (~3 s, temp files only, paper adapter)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import threading
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import state_safe as SS  # noqa: E402
from engine.live import LiveBot, trading_day  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []
PUSHED = []
SS.PUSH = PUSHED.append


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:300]})" if info and not cond else ""), flush=True)


def ts(y, mo, d, h, mi=0):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


T = ts(2026, 10, 21, 11, 0)            # Wednesday 11:00 ET
DAY = trading_day(T)


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


CFG = {"sym": "NQ", "tf": "5m", "adapter": "paper", "model": "lit", "params": {"max_micros": 40, "flat_mod": 955}}


def bot(tmp, t=T):
    b = LiveBot()
    b.clock = Clock(t)
    b.state_path = os.path.join(tmp, "live_state.json")
    r = b.start(dict(CFG), spawn=False)
    assert r.get("ok"), r
    return b


def blob(day=DAY, kill=False, pnl=-500.0, t=T - 3600, **kw):
    led = [{"t": t - 600, "sym": "NQ", "side": "buy", "qty": 2, "entry_t": t - 900, "result": {"ok": True}},
           {"t": t, "sym": "NQ", "side": "exit", "qty": 2, "entry_t": t - 900, "reason": "STOP", "pnl": pnl, "result": {"ok": True}}]
    return {"version": 1, "saved_at": t, "day": day, "sym": "NQ", "tf": "5m", "adapter": "paper", "kill": kill, "ledger": led,
            "seen": [], "week_exits": [], "eval_days": {}, **kw}


def write(p, d):
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(d, fh)


def damage(p):
    with open(p, "w", encoding="utf-8") as fh:
        fh.write('{"version": 1, "day": "' + DAY + '", "ledger": [{"t": 17')        # a torn write


def entry_routed(b, now):
    """Feed LIT one fresh entry signal; True when it was routed (a buy / sell row in the ledger)."""
    n0 = sum(1 for r in b.ledger if r.get("side") in ("buy", "sell"))
    et_ = (now // 300) * 300 - 300
    pos = {"entry_t": et_, "dir": 1, "qty": 1, "entry": 25020.0, "stop": 24990.0, "stop0": 24990.0, "target": 25220.0,
           "risk_pts": 30.0, "be": False}
    b.state = {"model": "lit", "position": pos, "lit": {}}
    b._lit_sizing = {"mode": "normal"}
    try:
        b._route_signals({"trades": [], "events": []}, "NQ", int(now), 300)
    except Exception as e:  # noqa: BLE001
        return f"raised {e.__class__.__name__}: {e}"
    return sum(1 for r in b.ledger if r.get("side") in ("buy", "sell")) > n0


def logs(b):
    return " | ".join(str(x.get("text")) for x in list(b.log)[:30])


# ------------------------------------------------------------------------------------------------ a + e
def part_a():
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "live_state.json")
        write(p, blob(kill=True))
        b = bot(tmp)
        check("e. healthy start: kill + today's ledger restored exactly as before, no pause, no message",
              b.kill and b.day_pnl_routed() == -500.0 and b._state_block_day is None and not PUSHED, (b.kill, b.day_pnl_routed()))
        first = open(p, encoding="utf-8").read()
        b._save_state()
        check("a. a save after a clean read keeps the previous good copy as live_state.json.bak",
              os.path.exists(p + ".bak") and json.load(open(p + ".bak"))["kill"] is True, os.listdir(tmp))
        b._save_state()
        check("a. ... and the main file is the new save (valid JSON, same day)", json.load(open(p))["day"] == DAY)
        damage(p)
        good_bak = open(p + ".bak", encoding="utf-8").read()
        b2 = LiveBot()                          # a new process that finds the damaged file: it must not rotate it over the .bak
        b2.clock, b2.state_path = Clock(T), p
        b2.start(dict(CFG), spawn=False)
        check("a. a damaged main file never replaces the good .bak (rotation only after a clean read / write)",
              json.loads(good_bak)["day"] == DAY and json.load(open(p + ".bak"))["day"] == DAY and b2.kill, first[:40])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ b
def part_b():
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "live_state.json")
        write(p + ".bak", blob(kill=True, pnl=-700.0))
        damage(p)
        PUSHED.clear()
        b = bot(tmp)
        check("b. unreadable live_state.json + today's .bak: kill ON, today's -$700 and the trade come back (no clean day)",
              b.kill and b.day_pnl_routed() == -700.0 and b.trades_today() == 1, (b.kill, b.day_pnl_routed(), logs(b)))
        check("b. ... said in the log, no pause, no phone message (nothing was lost)",
              "restored from today's backup" in logs(b) and b._state_block_day is None and not PUSHED, logs(b))
        os.remove(p)
        write(p + ".bak", blob(kill=False, pnl=-300.0))
        b = bot(tmp)
        check("b. a save cut off between the two renames (main gone, today's .bak there) = the .bak, not a clean day",
              b.day_pnl_routed() == -300.0 and b._state_block_day is None, (b.day_pnl_routed(), logs(b)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ c
def part_c():
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "live_state.json")
        write(p + ".bak", blob(day="2026-10-20", t=ts(2026, 10, 20, 11), eval_days={"2026-10-20": 250.0}))
        damage(p)
        PUSHED.clear()
        b = bot(tmp)
        check("c. no usable copy (only yesterday's .bak, paper: no proof for a rebuild): NO NEW ENTRIES today",
              b._state_block_day == DAY and "NO NEW ENTRIES" in logs(b), logs(b))
        check("c. ... ONE plain phone message: entries paused, exits untouched, nothing needs doing",
              len(PUSHED) == 1 and "Entries paused today" in PUSHED[0]["title"] and "Nothing needs doing" in PUSHED[0]["body"]
              and "untouched" in PUSHED[0]["body"], PUSHED)
        check("c. ... the older backup still gives the earlier days (the eval's 2026-10-20)", b._eval_prev.get("2026-10-20") == 250.0,
              b._eval_prev)
        r = entry_routed(b, T + 600)
        check("c. a fresh LIT entry is NOT routed, the reason says the state file was damaged", r is False
              and "state file was damaged" in logs(b), (r, logs(b)))
        b._save_state()
        b2 = bot(tmp, T + 1200)
        check("c. the pause outlives a restart the same day (saved in the good file it writes); no second message",
              b2._state_block_day == DAY and len(PUSHED) == 1 and entry_routed(b2, T + 1800) is False, (b2._state_block_day, PUSHED))
        nxt = ts(2026, 10, 22, 10, 0)
        b3 = bot(tmp, nxt)
        check("c. the next trading day: entries again (the pause is for one ET day only)", b3._state_block_day in (None, DAY)
              and entry_routed(b3, nxt + 600) is True, (b3._state_block_day, logs(b3)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_c_rebuild():
    tmp = tempfile.mkdtemp()
    try:
        st = os.path.join(tmp, "exec")
        os.makedirs(st)
        led = blob(kill=False, pnl=-400.0)["ledger"]
        with open(os.path.join(st, "ledger.jsonl"), "w", encoding="utf-8") as fh:
            for r in led + led[:1]:                          # a duplicate row too
                fh.write(json.dumps({**r, "adapter": "ninjatrader"}) + "\n")
        write(os.path.join(st, "notes.json"), {"uptime": [{"t": T - 120, "running": True, "kill": False}]})
        audit = os.path.join(tmp, "oif.log")

        def aline(t, acct="Sim101"):
            return f"{dt.datetime.fromtimestamp(t, ET):%Y-%m-%d %H:%M:%S} ET  {acct}  oif_le_1.txt  PLACE;Sim101;MNQ 12-26;BUY;1\n"
        with open(audit, "w", encoding="utf-8") as fh:
            fh.write(aline(T - 900) + aline(T - 60, "OTHER"))
        rb = SS.rebuild_lit(DAY, trading_day, audit, "Sim101", st)
        check("c. rebuild: the copy ran after this account's last order, every entry has its exit -> today's ledger (deduped), kill off",
              rb and len(rb["ledger"]) == 2 and rb["kill"] is False and sum(float(r.get("pnl") or 0) for r in rb["ledger"]) == -400.0, rb)
        with open(audit, "a", encoding="utf-8") as fh:
            fh.write(aline(T - 30))
        check("c. rebuild refused when an order went out AFTER the last copy (its row may be missing)",
              SS.rebuild_lit(DAY, trading_day, audit, "Sim101", st) is None)
        with open(audit, "w", encoding="utf-8") as fh:
            fh.write(aline(T - 900))
        with open(os.path.join(st, "ledger.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": T - 200, "side": "buy", "qty": 1, "entry_t": T - 300, "result": {"ok": True}}) + "\n")
        check("c. rebuild refused when an entry has no exit (a position may be open)", SS.rebuild_lit(DAY, trading_day, audit, "Sim101", st) is None)
        write(os.path.join(st, "notes.json"), {"uptime": [{"t": T - 120, "running": True, "kill": True}]})
        with open(os.path.join(st, "ledger.jsonl"), "w", encoding="utf-8") as fh:
            for r in led:
                fh.write(json.dumps(r) + "\n")
        rb = SS.rebuild_lit(DAY, trading_day, audit, "Sim101", st)
        check("c. rebuild: the kill flag comes from the copy's last uptime sample", rb and rb["kill"] is True, rb)
        write(os.path.join(st, "notes.json"), {"uptime": [{"t": T - 86400, "running": True, "kill": False}]})
        check("c. rebuild refused when the copy did not run today", SS.rebuild_lit(DAY, trading_day, audit, "Sim101", st) is None)
        write(os.path.join(st, "notes.json"), {"uptime": [{"t": T - 120, "running": True, "kill": False}]})
        check("c. rebuild refused on paper / without the order log (no proof)", SS.rebuild_lit(DAY, trading_day, None, None, st) is None
              and SS.rebuild_lit(DAY, trading_day, os.path.join(tmp, "none.log"), "Sim101", st) is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ d
def part_d():
    from engine import account_b as AB

    class B:
        state_path = "/tmp/not-the-real-bot.json"

        def clock(self):
            return T
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "live_state_acctb.json")

        def acct():
            a = AB.AccountB.__new__(AB.AccountB)
            a.bot, a.state_path, a.name, a.label = B(), p, "SimB25", "ATLAS 25K"
            a.mx = threading.RLock()
            a.spec = {"plan": "builder25k"}
            a.closes, a.ledger, a.prov, a.open_t, a.seen, a.lock, a.notified, a.held = [], [], {}, None, set(), None, [], {}
            a.logs = []
            a.log = lambda k, m: a.logs.append(m)
            return a

        def ab_blob(t, lock=None, closes=None):
            return {"v": 1, "account": "SimB25", "plan": "builder25k", "saved_at": t, "ledger": [], "closes": closes or [[DAY, 1, -300.0]],
                    "prov": {}, "open_t": None, "seen": [], "lock": lock, "notified": [], "held": {}}
        write(p + ".bak", ab_blob(T - 600, lock={"day": DAY, "reason": "soft daily loss: today $-620"}))
        damage(p)
        PUSHED.clear()
        a = acct()
        a._load()
        check("d. ATLAS: unreadable state + today's .bak -> today's lock-out and closes come back (no clean day)",
              a.lock and "soft daily loss" in a.lock["reason"] and a.closes == [[DAY, 1, -300.0]] and not PUSHED, (a.lock, a.closes))
        write(p + ".bak", ab_blob(ts(2026, 10, 20, 11), closes=[["2026-10-20", 1, 200.0]]))
        damage(p)
        a = acct()
        a._load()
        check("d. ATLAS: only yesterday's .bak -> its history (closes) + a lock-out for TODAY (no new entry) + one message",
              a.lock and a.lock["day"] == DAY and "damaged" in a.lock["reason"] and a.closes == [["2026-10-20", 1, 200.0]]
              and len(PUSHED) == 1 and "live_state_acctb.json" in PUSHED[0]["body"], (a.lock, a.closes, PUSHED))
        os.remove(p + ".bak")
        damage(p)
        a = acct()
        a._load()
        check("d. ATLAS: nothing usable -> locked out today all the same", a.lock and a.lock["day"] == DAY, a.lock)
        os.remove(p)
        n0 = len(PUSHED)
        a = acct()
        a._load()
        check("e. ATLAS: no file at all (a first start) = clean as before, no lock, no message", a.lock is None and len(PUSHED) == n0)
        write(p, ab_blob(T - 60))
        a = acct()
        a._load()
        a.funded = lambda: False
        a.save()
        a.save()
        check("a. ATLAS: a save after a clean read keeps the previous good copy (.bak)", os.path.exists(p + ".bak")
              and json.load(open(p + ".bak"))["account"] == "SimB25" and json.load(open(p))["account"] == "SimB25")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ f + g (job J)
EXTRA = {"id": "fund", "name": "Paper funded", "adapter": "paper", "preset": "mffu_builder_50k", "mode": "funded",
         "funded": {"start": "2026-10-01", "payouts": {}}}


def part_f():
    """the extra accounts (engine/multi_account: data/live_state_accounts.json): the same fallback."""
    import copy
    from engine import multi_account as MA
    MA.ADAPTER_FACTORY = None
    tmp = tempfile.mkdtemp()
    try:
        ap = os.path.join(tmp, "live_state_accounts.json")

        def start(t=T):
            b = LiveBot()
            b.clock = Clock(t)
            b.state_path = os.path.join(tmp, "live_state.json")
            r = b.start({**CFG, "accounts": [copy.deepcopy(EXTRA)], "accounts_parallel": False}, spawn=False)
            assert r.get("ok"), r
            return b, next(a for a in b.accts.accounts if a.id == "fund")

        def ab(day, lock=None, closes=None):
            return {"v": 1, "saved_at": T - 600, "day": day, "accounts": {"fund": {"id": "fund", "nt_account": "", "day": day,
                    "ledger": [], "closes": closes or [[day, 1, -450.0]], "seen": [], "open_t": None, "open_qty": None,
                    "blocked": [], "flattened": [], "provisional": {}, "lock": lock}}}
        b, a = start()
        b.accts.save()
        b.accts.save()
        check("f. extras: a save after a clean start keeps the previous good copy (live_state_accounts.json.bak)",
              os.path.exists(ap + ".bak") and json.load(open(ap + ".bak"))["day"] == DAY)
        write(ap + ".bak", ab(DAY, lock={"day": DAY, "reason": "soft daily loss", "t": T - 600}))
        damage(ap)
        PUSHED.clear()
        b, a = start()
        check("f. extras: unreadable file + today's .bak -> today's lock-out and closes come back, no pause, no message",
              a.lock and a.lock["reason"] == "soft daily loss" and a.closes == [[DAY, 1, -450.0]] and not PUSHED, (a.lock, a.closes))
        write(ap + ".bak", ab("2026-10-20", closes=[["2026-10-20", 1, 300.0]]))
        damage(ap)
        b, a = start()
        why = a.entry_block(T + 600) if callable(getattr(a, "entry_block", None)) else None
        check("f. extras: only yesterday's .bak -> its closes + every extra account locked out TODAY (no new entry) + one message",
              a.lock and a.lock["day"] == DAY and a.lock.get("state_damaged") and "damaged" in a.lock["reason"]
              and a.closes == [["2026-10-20", 1, 300.0]] and len(PUSHED) == 1 and "live_state_accounts.json" in PUSHED[0]["body"],
              (a.lock, a.closes, PUSHED))
        b.accts.save()
        b2, a2 = start(T + 1200)
        check("f. extras: the lock-out outlives a restart the same day (no second message)", a2.lock and a2.lock.get("state_damaged")
              and len(PUSHED) == 1, a2.lock)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_g():
    """on purpose: a damaged-state pause never blocks the keep-alive (its 1 MNQ keeps the account from MFFU's inactivity close)."""
    from engine import keepalive as KA

    class O:
        def __init__(self, lock):
            self.lock = lock
    g = lambda lk: {"key": "x:fund", "lanes": [{"kind": "extra", "obj": O(lk)}]}   # noqa: E731
    b = LiveBot()
    b.clock = Clock(T)
    dmg = KA._stood_down(b, g({"day": DAY, "reason": "the state file was damaged today", "state_damaged": True}), T)
    normal = KA._stood_down(b, g({"day": DAY, "reason": "soft daily loss"}), T)
    check("g. keep-alive: an extra account's damaged-state pause does NOT stand it down; a real lock-out still does",
          dmg is None and normal and "soft daily loss" in normal, (dmg, normal))
    src = open(os.path.join(ROOT, "engine", "keepalive.py"), encoding="utf-8").read()
    check("g. keep-alive: the ATLAS lane skips a state_damaged lock and LIT's _state_block_day is not read (on purpose, commented)",
          src.count('not lk.get("state_damaged")') == 2 and "_state_block_day" not in src.replace(
              "LiveBot._state_block_day, engine/state_safe) is NOT checked here", ""))


def main() -> int:
    for f in (part_a, part_b, part_c, part_c_rebuild, part_d, part_f, part_g):
        try:
            f()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
    n, ok = len(RES), sum(RES)
    print(f"\nstate safe: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
