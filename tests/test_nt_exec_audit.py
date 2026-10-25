"""Order lifecycle / recovery / startup audit (pre-launch audit 2026-10-25, research/handoff/2026-10-25/A5_execution.md).

    python -X utf8 -m tests.test_nt_exec_audit        (~10 s, offline: engine/ninjatrader._FakeNT on temp folders)

Sim101 / Sim102 / Sim103 and made-up names on simulated NinjaTrader folders only; nothing reaches a real NinjaTrader and no
real account is armed (the one "live" adapter below writes into a temp folder that no NinjaTrader reads).

  A. kill scope: account B's / an extra account's kill = CLOSEPOSITION + CANCEL by id on ITS account only; never
     FLATTENEVERYTHING / CANCELALLORDERS; the other account's position and bracket are untouched. Only the owner's global
     kill (LiveBot.kill_switch -> scope "global") writes FLATTENEVERYTHING. The writer refuses an account-wide command, a
     line for another account, and a CANCEL of an id that is not the bot's.
  B. LiveBot: a remote flatten (flatten_now) and the kill switch with extra NinjaTrader accounts open: no FLATTENEVERYTHING.
  C. duplicate process: a second process on the same account is DISABLED (sends nothing); another account is not affected;
     the lock goes with the process (a crash never leaves it stale).
  D. account allowlist: a non-Sim account is refused unless its exact Name is allowlisted (file or NINJATRADER_ALLOW).
  E. startup DISARMED until reconciled: an unexplained position, a stale feed, a chart on another contract, a clock check
     not done, an eval anchor that does not reconcile -> entries blocked; once it passes it latches.
  F. file publish: a name already in incoming\\ is never overwritten; an interrupted publish (left in le_outbox\\) is
     deleted, never moved in late.
  G. corrupted state file: never read as flat, moved aside, entries blocked (also after a restart) until NinjaTrader shows
     the account flat; orphan working orders of the bot (from the audit log) are cancelled by id on the flat account.
  H. fill before ack: an entry withdrawn by the bot that NinjaTrader executed anyway is protected; an entry NinjaTrader
     takes at the last moment is protected at once.
  I. target REJECTED after the fill -> flattened at once.
  J. DST: session gates and the trading day across the 2026-11-01 / 2026-03-08 clock changes.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import guards, ninjatrader as nt  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not ok else ""), flush=True)
    return bool(ok)


T10 = dt.datetime(2026, 10, 21, 10, 0, tzinfo=nt.ET).timestamp()        # Wednesday 10:00 ET
T0 = time.time()


def clock():
    return T10 + (time.time() - T0)


class Env:
    """One temp NinjaTrader folder + _FakeNT; adapters on any account in it."""

    def __init__(self, tmp, name):
        self.dir = os.path.join(tmp, name)
        self.folder = os.path.join(self.dir, "NinjaTrader 8")
        self.fake = nt._FakeNT(self.folder, price=25020.0)
        self.alerts = []

    def make(self, account="Sim101", tag="", extra=None, clk=clock):
        cfg = {"nt_folder": self.folder, "nt_account": account, "nt_instrument": "MNQ 12-26", "nt_file_tag": tag,
               "nt_state_path": os.path.join(self.dir, f"nt_state_{account}.json"),
               "nt_audit_log": os.path.join(self.dir, f"oif_{account}.log"), "nt_ack_wait_s": 0.2,
               "nt_fill_wait_s": 0.2, "nt_verify_wait_s": 0.2, "model": "lit", **(extra or {})}
        ad = nt.NinjaTraderAdapter(cfg, clock=clk)
        ad._alert_fn = self.alerts.append
        ad._sleep = lambda s_: (self.fake.process(), time.sleep(min(s_, 0.002)))
        return ad

    def lines(self, k=0):
        return [ln for _, ls in self.fake.files[k:] for ln in ls]

    def buy(self, ad, qty=2, t=None):
        return ad.send({"side": "buy", "qty": qty, "stop": 24990.0, "target": 25080.0, "entry": 25020.0, "sym": "NQ",
                        "entry_t": int(t or ad.clock())})


ACCOUNT_WIDE = ("FLATTENEVERYTHING", "CANCELALLORDERS")


# ------------------------------------------------------------------------------------------------ A. kill scope
def test_kill_scope(tmp):
    print("== A. kill scope: account-scoped unless the owner's global kill")
    e = Env(tmp, "a")
    lit, b = e.make("Sim101"), e.make("Sim102", tag="acctb_")
    r1, r2 = e.buy(lit, 3), e.buy(b, 2)
    check("setup: LIT (Sim101) LONG 3 and account B (Sim102) LONG 2, both protected",
          r1.get("ok") and r2.get("ok") and lit.legs[0]["status"] == "protected" and b.legs[0]["status"] == "protected", (r1, r2))
    ls, lt = lit.legs[0]["stop_id"], lit.legs[0]["target_id"]
    k = len(e.fake.files)
    rk = b.send({"sym": "NQ", "side": "exit", "reason": "KILL SWITCH", "entry_t": b.legs[0]["entry_t"]})   # AccountB.kill's route
    ln = e.lines(k)
    check("account B's kill: no FLATTENEVERYTHING / CANCELALLORDERS written", not any(x.startswith(ACCOUNT_WIDE) for x in ln), ln)
    check("account B's kill: CLOSEPOSITION on Sim102 only; B flat, its legs retired, scope 'account'",
          rk.get("ok") and rk.get("scope") == "account" and any(x == "CLOSEPOSITION;Sim102;MNQ 12-26;;;;;;;;;;" for x in ln)
          and not any(";Sim101;" in x for x in ln) and e.fake.pos[("Sim102", "MNQ 12-26")][0] == 0 and not b.legs, (rk, ln))
    check("account B's kill: LIT's Sim101 position (LONG 3) and its stop / target are untouched",
          e.fake.pos[("Sim101", "MNQ 12-26")][0] == 3 and e.fake.orders[ls]["state"] == "WORKING"
          and e.fake.orders[lt]["state"] == "WORKING" and lit.legs and lit.legs[0]["status"] == "protected")
    rb = e.buy(b, 1)
    check("account B after its kill: new entries refused", not rb.get("ok") and "kill" in rb.get("error", ""), rb)
    # a pending entry (no fill report yet) on an account kill: cancelled by id
    e.fake.hold_market = True
    c = e.make("Sim103", tag="acctc_")
    rp = e.buy(c, 1)
    pid = c.legs[0]["entry_id"] if c.legs else None
    k = len(e.fake.files)
    rk3 = c.kill()
    ln = e.lines(k)
    e.fake.hold_market = False
    check("account kill with an entry still working: CLOSEPOSITION;Sim103 + CANCEL of that entry by id, nothing account-wide",
          not rp.get("ok") and pid and f"CANCEL;;;;;;;;;;{pid};;" in ln and "CLOSEPOSITION;Sim103;MNQ 12-26;;;;;;;;;;" in ln
          and not any(x.startswith(ACCOUNT_WIDE) for x in ln) and e.fake.orders[pid]["state"] == "CANCELLED", (rk3, ln))
    # the writer refuses account-wide commands, another account's line, a foreign id
    w1 = lit._write_oif([nt.FLATTEN_EVERYTHING], "test")
    w2 = lit._write_oif(["CANCELALLORDERS;;;;;;;;;;;;"], "test")
    w3 = lit._write_oif([nt.close_line("Sim102", "MNQ 12-26")], "test")
    w4 = lit._write_oif([nt.place_line("Sim102", "MNQ 12-26", "BUY", 1, "MARKET", order_id="LEX1")], "test")
    w5 = lit._write_oif([nt.cancel_line("NT12345")], "test")
    check("writer: FLATTENEVERYTHING / CANCELALLORDERS outside the global kill, a Sim102 line from the Sim101 adapter and a "
          "CANCEL of a non-bot id are all refused (nothing written)",
          not any(w.get("ok") for w in (w1, w2, w3, w4, w5)) and all("refused" in w.get("error", "") for w in (w1, w2, w3, w4, w5)),
          [w.get("error") for w in (w1, w2, w3, w4, w5)])
    # the owner's global kill on the primary
    k = len(e.fake.files)
    rg = lit.send({"sym": "NQ", "side": "exit", "reason": "KILL SWITCH", "scope": "global"})
    check("owner's global kill (scope 'global', LiveBot.kill_switch only): exactly FLATTENEVERYTHING;;;;;;;;;;;;",
          rg.get("ok") and e.lines(k) == ["FLATTENEVERYTHING;;;;;;;;;;;;"] and e.fake.pos[("Sim101", "MNQ 12-26")][0] == 0
          and not lit._global_kill, (rg, e.lines(k)))
    src = {n: open(os.path.join(ROOT, "engine", n), encoding="utf-8").read() for n in ("account_b.py", "multi_account.py", "live.py")}
    glob_live = src["live.py"].count('"scope": "global"')
    ks = src["live.py"].split("def kill_switch", 1)[1].split("\n    def ", 1)[0]
    check("source: only LiveBot.kill_switch asks for the global scope (account_b.py / multi_account.py never do)",
          '"scope"' not in src["account_b.py"] and '"scope"' not in src["multi_account.py"] and glob_live >= 2
          and ks.count('"scope": "global"') == glob_live, (glob_live, ks.count('"scope": "global"')))


# ------------------------------------------------------------------------------------------------ B. LiveBot with extra accounts
def test_livebot_accounts(tmp):
    print("== B. LiveBot: remote flatten / kill with extra NinjaTrader accounts")
    from tests import test_multi_account as TM
    from engine import multi_account as MA
    for k_ in (nt.LIVE_ENV, "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER"):
        os.environ.pop(k_, None)
    os.environ["LE_LIT_LEARNING"] = os.path.join(tmp, "no_learning.json")
    accts = [a for a in TM.ACCTS if a["adapter"] == "ninjatrader"]
    try:
        for label, act in (("remote flatten (flatten_now)", "flatten"), ("kill switch", "kill")):
            fake = nt._FakeNT(os.path.join(tmp, f"b_{act}", "NinjaTrader 8"))
            clk = TM.Clock(TM.T0 + 290)
            b = TM.make_bot(os.path.join(tmp, f"b_{act}", "bot"), fake, clk, accts)
            clk.t = TM.T0 + 305
            TM.signal(b, TM.pos_at(TM.T0))
            held = {a: fake.pos.get((a, "MNQ 12-26"), [0])[0] for a in ("Sim102", "Sim103")}
            k = len(fake.files)
            if act == "flatten":
                b.flatten_now()
            else:
                b.kill_switch()
            ln = [x for _, ls in fake.files[k:] for x in ls]
            check(f"LiveBot {label}: extra accounts open ({held}) -> each CLOSEPOSITION on its own account, no FLATTENEVERYTHING",
                  all(v > 0 for v in held.values()) and not any(x.startswith(ACCOUNT_WIDE) for x in ln)
                  and any(x.startswith("CLOSEPOSITION;Sim102;") for x in ln) and any(x.startswith("CLOSEPOSITION;Sim103;") for x in ln)
                  and all(fake.pos.get((a, "MNQ 12-26"), [0])[0] == 0 for a in ("Sim102", "Sim103")), (held, ln))
    finally:
        MA.ADAPTER_FACTORY = None


# ------------------------------------------------------------------------------------------------ C. duplicate process
HOLDER = r"""
import sys, time
sys.path.insert(0, sys.argv[1])
from engine import ninjatrader as nt
ad = nt.NinjaTraderAdapter({"nt_folder": sys.argv[2], "nt_account": "Sim101", "nt_instrument": "MNQ 12-26",
                            "nt_state_path": sys.argv[3], "nt_audit_log": sys.argv[3] + ".log"})
print("READY" if not ad.disabled else "DISABLED " + str(ad.disabled), flush=True)
sys.stdin.read()
"""


def test_duplicate_process(tmp):
    print("== C. duplicate process: one bot process per account")
    e = Env(tmp, "c")
    p = subprocess.Popen([sys.executable, "-c", HOLDER, ROOT, e.folder, os.path.join(e.dir, "other_state.json")],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        first = p.stdout.readline().strip()
        ad = e.make("Sim101")
        k = len(e.fake.files)
        r = e.buy(ad, 1)
        check("a first bot process holds Sim101; a second one starts DISABLED ('another bot process') and writes nothing",
              first == "READY" and ad.disabled and "another bot process" in ad.disabled and not r.get("ok")
              and len(e.fake.files) == k and not os.listdir(e.fake.inc), (first, ad.disabled, r))
        other = e.make("Sim102")
        check("the same second process may still trade another account (Sim102): not disabled", not other.disabled, other.disabled)
        check("the lock names the holder (pid) for the owner", str(p.pid) in (ad.disabled or ""), ad.disabled)
        ad_b = e.make("Sim101")
        check("same process, second adapter on Sim101 while the other process holds it: still disabled", bool(ad_b.disabled))
    finally:
        p.stdin.close()
        p.wait(timeout=20)
    ad2 = e.make("Sim101")
    check("the holder exits (or crashes): the lock goes with it, a new bot on Sim101 is enabled (no stale lock)",
          not ad2.disabled, ad2.disabled)
    ad3 = e.make("Sim101")
    check("several adapters in one process on the same account share the lock (a restarted LiveBot)", not ad3.disabled, ad3.disabled)
    p2 = subprocess.Popen([sys.executable, "-c", HOLDER, ROOT, e.folder, os.path.join(e.dir, "other_state.json")],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    held = p2.stdout.readline().strip()
    p2.stdin.close()
    p2.wait(timeout=20)
    from engine.live import LiveBot
    lb = LiveBot()
    lb.adapter = ad3
    lb.state_path = os.path.join(e.dir, "lb_state.json")
    lb.stop()                                      # LiveBot.stop gives the account lock back
    p3 = subprocess.Popen([sys.executable, "-c", HOLDER, ROOT, e.folder, os.path.join(e.dir, "other_state.json")],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    free = p3.stdout.readline().strip()
    p3.stdin.close()
    p3.wait(timeout=20)
    check("while this process's bot runs, another process is refused; after LiveBot.stop() the account is free again "
          "(a Sim check / the next start can take it)", held.startswith("DISABLED") and free == "READY", (held, free))


# ------------------------------------------------------------------------------------------------ D. allowlist
def test_allowlist(tmp):
    print("== D. account allowlist")
    e = Env(tmp, "d")
    allow = os.path.join(e.dir, "allow.json")
    os.environ[nt.LIVE_ENV] = "1"
    os.environ.pop(nt.ALLOW_ENV, None)
    try:
        base = {"armed": True, "confirm": LIVE_PHRASE, "nt_allow_path": allow}
        a0 = e.make("MFFUTEST001", extra=base)
        nt.allow_account("MFFUTEST001", path=allow)
        a1 = e.make("MFFUTEST001", extra=base)
        a2 = e.make("MFFUTEST002", extra=base)                  # a typo / another real account
        a3 = e.make("mffutest001", extra=base)                  # case differs
        os.environ[nt.ALLOW_ENV] = "MFFUTEST002, XYZ"
        a4 = e.make("MFFUTEST002", extra=base)
        os.environ.pop(nt.ALLOW_ENV, None)
        nt.allow_account("MFFUTEST001", path=allow, remove=True)
        a5 = e.make("MFFUTEST001", extra=base)
        s1 = e.make("Sim101", extra={"nt_allow_path": allow})
    finally:
        os.environ.pop(nt.LIVE_ENV, None)
        os.environ.pop(nt.ALLOW_ENV, None)
    check("armed + phrase + NINJATRADER_LIVE=1 but not allowlisted -> DISABLED with the --allow-account command",
          a0.disabled and "allowlist" in a0.disabled and "--allow-account" in a0.disabled, a0.disabled)
    check("allowlisted by file (--allow-account) -> enabled; another Name or other capitals -> refused",
          a1.disabled is None and a2.disabled and "allowlist" in a2.disabled and a3.disabled and "allowlist" in a3.disabled,
          (a1.disabled, a2.disabled, a3.disabled))
    check("NINJATRADER_ALLOW (comma list in .env.local.ps1) also allows; removing the Name refuses again",
          a4.disabled is None and a5.disabled and "allowlist" in a5.disabled, (a4.disabled, a5.disabled))
    check("Sim accounts need no allowlist entry", s1.disabled is None, s1.disabled)
    try:
        nt.allow_account("A;B", path=allow)
        bad = False
    except ValueError:
        bad = True
    check("an account Name with ';' (would break the OIF line) is refused by --allow-account", bad)


# ------------------------------------------------------------------------------------------------ E. startup disarmed
class StubBot:
    def __init__(self, ad, clk=clock):
        self.adapter, self.cfg = ad, {"adapter": "ninjatrader"}
        self.ledger, self._open_routed, self._open_qty, self._open_adds = [], None, None, []
        self.health = {"stale": False, "entries_blocked": False}
        self.clock = clk
        self._lit_sizing = {"mode": "normal"}
        self.state_path = os.path.join(tempfile.gettempdir(), "le_stub_live_state.json")
        self.log_rows, self._startup_ok, self._startup_last = [], None, None

    def _log(self, kind, text, **kw):
        self.log_rows.append((kind, text))


def test_startup(tmp):
    print("== E. startup DISARMED until reconciled")
    c = {**guards.DEFAULTS}
    e = Env(tmp, "e")
    first = e.make("Sim101")
    e.buy(first, 2)                            # a position the next bot will not know (its state file is another one)
    ad = e.make("Sim101", extra={"nt_state_path": os.path.join(e.dir, "fresh_state.json")})
    bot = StubBot(ad)
    p1 = guards.startup_problems(bot, c)
    check("unexplained NinjaTrader position (LONG 2, no bracket / ledger of this bot): DISARMED",
          any("no bracket of the bot explains" in x for x in p1) and any("ledger flat" in x for x in p1), p1)
    e.fake._do("CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;")
    bot.health = {"stale": True, "entries_blocked": True, "feed_block": "NinjaTrader MNQ 1m stale"}
    p2 = guards.startup_problems(bot, c)
    check("account flat now, but the bar feed is stale: still DISARMED (feed)", p2 and all("feed" in x for x in p2), p2)
    bot.health = {"stale": False, "entries_blocked": False}
    feed = os.path.join(e.folder, nt.FEED_DIR)
    os.makedirs(feed, exist_ok=True)
    with open(os.path.join(feed, "MNQ_instrument.txt"), "w") as fh:
        fh.write("MNQ 09-26\n")
    p3 = guards.startup_problems(bot, c)
    check("chart on MNQ 09-26 while the orders go to MNQ 12-26: DISARMED (contract)", any("old contract" in x for x in p3), p3)
    with open(os.path.join(feed, "MNQ_instrument.txt"), "w") as fh:
        fh.write("MNQ 12-26\n")
    pr = guards.entry_problems(bot, {"entry_t": int(clock())}, {"side": "buy", "qty": 1, "stop": 24990.0, "target": 25080.0,
                                                                  "entry": 25020.0}, 1, int(clock()),
                               c={**c, "calendar": False, "order_sanity": False, "dup_entry": False, "daily_loss": False}, s={})
    check("everything reconciles: the entry check passes and the startup gate LATCHES (logged STARTUP RECONCILED)",
          not pr and bot._startup_ok and any("STARTUP RECONCILED" in t for _, t in bot.log_rows), (pr, bot.log_rows[-2:]))
    e.fake._do("PLACE;Sim101;MNQ 12-26;BUY;1;MARKET;0;0;DAY;;LEMANUAL1;;")
    check("latched: later problems are the regular guards' job (reconcile / adapter), not the startup gate",
          guards.startup_problems(bot, c) == [])
    e.fake._do("CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;")
    # clock: the real bot waits for one finished probe
    saved = dict(guards._CLOCK)
    try:
        guards._CLOCK.update({"drift": None, "bad": 0, "t": 0.0, "ok_t": 0.0, "running": False, "done": 0,
                              "probe": lambda: (time.sleep(0.05), 0.2)[1]})
        rb = StubBot(ad, clk=time.time)
        rb.adapter = None
        pc = guards.startup_problems(rb, c)
        for _ in range(200):
            if guards._CLOCK.get("done"):
                break
            time.sleep(0.01)
        pc2 = guards.startup_problems(rb, c)
        check("real clock: DISARMED until one clock probe has finished (the probe is started by the check), then clear",
              any("clock check" in x for x in pc) and not any("clock" in x for x in pc2), (pc, pc2))
    finally:
        guards._CLOCK.clear()
        guards._CLOCK.update(saved)
    # eval anchor (a real-account adapter stub in an eval mode)

    class Ad:
        sim, account = False, "MFFUTEST001"
    ab = StubBot(None)
    ab.adapter = Ad()
    ab._lit_sizing = {"mode": "two_week"}
    ab.state_path = os.path.join(e.dir, "live_state.json")
    ab.eval_start = lambda: ""
    ab.eval_anchor = lambda: None
    ab.eval_room = lambda: 1800.0
    pa = guards._anchor_problems(ab, c)
    ab.eval_start = lambda: "2026-10-19"
    ab.eval_anchor = lambda: {"as_of": "2026-12-31", "balance": 50500.0, "floor": 48500.0}
    pb = guards._anchor_problems(ab, c)
    ab.eval_anchor = lambda: {"as_of": "2026-10-20", "balance": 50500.0, "floor": 48500.0}
    ab.eval_room = lambda: -5.0
    pcr = guards._anchor_problems(ab, c)
    with open(os.path.join(e.dir, "eval_anchor.json"), "w") as fh:
        json.dump({"main": {"as_of": "bad"}}, fh)
    ab.eval_anchor = lambda: None
    ab.eval_room = lambda: 1800.0
    pd_ = guards._anchor_problems(ab, c)
    ab.eval_anchor = lambda: {"as_of": "2026-10-20", "balance": 50500.0, "floor": 48500.0}
    pe = guards._anchor_problems(ab, c)
    check("eval anchor (real account, two_week): eval start unknown / anchor in the future / room <= 0 / an anchor file with "
          "no valid anchor -> DISARMED; a valid anchor and room -> clear",
          any("eval start unknown" in x for x in pa) and any("future" in x for x in pb) and any("<= 0" in x for x in pcr)
          and any("no valid anchor" in x for x in pd_) and pe == [], (pa, pb, pcr, pd_, pe))
    ab.adapter.sim = True
    check("Sim accounts: the eval anchor never blocks (paper / Sim101 rehearsals)", guards._anchor_problems(ab, c) == [])


# ------------------------------------------------------------------------------------------------ F. file publish
def test_publish(tmp):
    print("== F. file publish: no overwrite, interrupted publish")
    e = Env(tmp, "f")
    ad = e.make("Sim101")
    e.fake.running = False                        # NinjaTrader not reading, so the files stay where they are
    fixed = 1792867523922

    class TimeShim:
        def __getattr__(self, n):
            return getattr(time, n)

        @staticmethod
        def time_ns():
            return fixed * 1_000_000
    taken = os.path.join(ad.incoming, f"oif_le_{fixed}_{ad._seq + 1}.txt")
    with open(taken, "w") as fh:
        fh.write("PLACE;Sim101;MNQ 12-26;BUY;1;MARKET;0;0;DAY;;LEOTHER1E;;\r\n")
    real = nt.time
    nt.time = TimeShim()
    try:
        w = ad._write_oif([nt.cancel_line("LETEST1S")], "test")
    finally:
        nt.time = real
    with open(taken) as fh:
        kept = fh.read()
    check("a file name already in incoming\\ is NEVER overwritten: our order goes under the next name",
          w.get("ok") and w["file"] != os.path.basename(taken) and "LEOTHER1E" in kept and os.path.exists(w["path"])
          and not os.listdir(os.path.join(e.folder, "le_outbox")), (w, kept))
    src, dst = os.path.join(e.dir, "a.txt"), os.path.join(e.dir, "b.txt")
    for p_, t_ in ((src, "new"), (dst, "old")):
        with open(p_, "w") as fh:
            fh.write(t_)
    try:
        nt._publish(src, dst)
        refused = False
    except FileExistsError:
        refused = True
    check("_publish refuses an existing target (Windows rename / POSIX link), the old file stays",
          refused and open(dst).read() == "old")
    for n in os.listdir(ad.incoming):
        os.remove(os.path.join(ad.incoming, n))
    # interrupted publish: the bot died between writing le_outbox\<name> and moving it in
    box = os.path.join(e.folder, "le_outbox")
    stale = os.path.join(box, "oif_le_1792867000000_7.txt")
    with open(stale, "w") as fh:
        fh.write("PLACE;Sim101;MNQ 12-26;BUY;1;MARKET;0;0;DAY;;LESTALE1E;;\r\n")
    old = time.time() - 60
    os.utime(stale, (old, old))
    e.fake.running = True
    e.make("Sim101")
    e.fake.process()
    check("interrupted publish: the unpublished file left in le_outbox\\ is deleted at start, never moved into incoming\\",
          not os.path.exists(stale) and "LESTALE1E" not in json.dumps(e.lines()) and not os.listdir(ad.incoming))


# ------------------------------------------------------------------------------------------------ G. corrupted state file
def test_corrupt_state(tmp):
    print("== G. corrupted state file")
    e = Env(tmp, "g")
    st = os.path.join(e.dir, "nt_state_Sim101.json")
    ad = e.make("Sim101")
    r = e.buy(ad, 2)
    sid, tid = ad.legs[0]["stop_id"], ad.legs[0]["target_id"]
    with open(st, "w") as fh:
        fh.write('{"version": 1, "legs": [{"entry_id": "LE17')          # torn write
    e.alerts.clear()
    ad2 = e.make("Sim101")
    corrupt = [n for n in os.listdir(e.dir) if ".corrupt-" in n]
    ad2.tick()                                   # the phone alert goes out at the first tick (the bot wires alerts after start)
    rr = e.buy(ad2, 1)
    check("torn state file with a trade open: not read as flat, moved aside (.corrupt-*), alert, new entry REFUSED",
          r.get("ok") and ad2.state_problem and corrupt and e.alerts and not rr.get("ok") and "unreadable" in rr.get("error", ""),
          (corrupt, rr, e.alerts[:1]))
    ad3 = e.make("Sim101")
    check("a restart after that still blocks (the problem is saved, the torn file is gone)", bool(ad3.state_problem))
    with open(os.path.join(e.dir, "list_state.json"), "w") as fh:
        fh.write("[]")
    ad_l = e.make("Sim101", extra={"nt_state_path": os.path.join(e.dir, "list_state.json")})
    check("a state file holding valid JSON of the wrong shape ([]) does not crash the adapter: treated as unreadable",
          bool(ad_l.state_problem))
    # the model exit still closes the position (CLOSEPOSITION of our instrument), the stop / target stay working (fake)
    e.fake.close_cancels = False
    xr = ad3.send({"sym": "NQ", "side": "exit", "reason": "TIME", "entry_t": int(clock())})
    check("the model's exit is still routed: CLOSEPOSITION closes the position although the bracket was lost",
          e.fake.pos[("Sim101", "MNQ 12-26")][0] == 0 and xr.get("instruments") == ["MNQ 12-26"], xr)
    orphan_live = e.fake.orders[sid]["state"] == "WORKING" and e.fake.orders[tid]["state"] == "WORKING"
    k = len(e.fake.files)
    ad3.tick()
    ln = e.lines(k)
    check("flat account + the lost bracket's stop / target still working (orphans, ids from the audit log): CANCEL by id",
          orphan_live and f"CANCEL;;;;;;;;;;{sid};;" in ln and f"CANCEL;;;;;;;;;;{tid};;" in ln
          and e.fake.orders[sid]["state"] == "CANCELLED" and not any(x.startswith(ACCOUNT_WIDE) for x in ln), ln)
    ad3.tick()
    e.fake.close_cancels = True
    r4 = e.buy(ad3, 1)
    check("account flat and no order of the bot working: the block clears, entries allowed again", ad3.state_problem is None
          and r4.get("ok"), (ad3.state_problem, r4))
    ad3.send({"sym": "NQ", "side": "exit", "reason": "TIME", "entry_t": ad3.legs[0]["entry_t"] if ad3.legs else None})


# ------------------------------------------------------------------------------------------------ H. fill before ack
def test_fill_before_ack(tmp):
    print("== H. fill before the ack / after the withdraw")
    e = Env(tmp, "h")
    ad = e.make("Sim101")
    e.fake.running = False
    r = e.buy(ad, 2)
    check("NinjaTrader did not pick the entry up in time: withdrawn, ok False, watched",
          not r.get("ok") and ad.withdrawn and not os.listdir(ad.incoming), r)
    eid = ad.withdrawn[0]["entry_id"]
    # NinjaTrader had read the file before the delete (a Windows race): it executes the order anyway
    e.fake.running = True
    e.fake._do(nt.place_line("Sim101", "MNQ 12-26", "BUY", 2, "MARKET", order_id=eid))
    k = len(e.fake.files)
    ad.tick()
    ad.tick()
    ln = e.lines(k)
    check("the withdrawn entry filled anyway: the next ticks place its stop + target (OCO), never a naked position",
          any(";STOPMARKET;" in x and x.startswith("PLACE;Sim101") for x in ln) and any(";LIMIT;" in x for x in ln)
          and ad.legs and ad.legs[0]["status"] == "protected" and ad.legs[0]["filled"] == 2, (ln, ad.legs[:1]))
    ad.send({"sym": "NQ", "side": "exit", "reason": "TIME", "entry_t": ad.legs[0]["entry_t"]})
    # NinjaTrader takes the file at the very last moment (the withdraw finds it gone)
    e2 = Env(tmp, "h2")
    ad2 = e2.make("Sim101")
    e2.fake.running = False
    real_w = ad2._withdraw

    def late(path):
        e2.fake.running = True
        e2.fake.process()
        return real_w(path)
    ad2._withdraw = late
    r2 = e2.buy(ad2, 1)
    check("picked up at the last moment (fill reported before the bot saw the ack): treated as sent, stop + target placed",
          r2.get("ok") and ad2.legs and ad2.legs[0]["status"] == "protected" and not ad2.withdrawn, r2)


# ------------------------------------------------------------------------------------------------ I. target rejected
def test_target_rejected(tmp):
    print("== I. target REJECTED after the fill")
    e = Env(tmp, "i")
    ad = e.make("Sim101")
    e.fake.reject = {"LIMIT"}
    k = len(e.fake.files)
    r = e.buy(ad, 2)
    ln = e.lines(k)
    check("target REJECTED: flattened at once (CLOSEPOSITION), the stop cancelled, alert, ok False",
          not r.get("ok") and "target REJECTED" in r.get("error", "") and "CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;" in ln
          and e.fake.pos[("Sim101", "MNQ 12-26")][0] == 0 and not ad.legs and e.alerts, (r, ln))


# ------------------------------------------------------------------------------------------------ J. DST
def test_dst(tmp):
    print("== J. DST")
    e = Env(tmp, "j")

    def at(y, mo, d, h, mi):
        return dt.datetime(y, mo, d, h, mi, tzinfo=nt.ET).timestamp()
    rows = []
    for (y, mo, d) in ((2026, 11, 2), (2026, 3, 9)):          # the Mondays after the fall-back / spring-forward Sundays
        for (h, mi, want) in ((1, 59, False), (2, 1, True), (15, 39, True), (15, 56, False)):
            t = at(y, mo, d, h, mi)
            ad = e.make("Sim101", clk=lambda t=t: t)
            g = ad._gate("entry")
            rows.append(((y, mo, d, h, mi), want, g is None))
    check("entry gate in ET wall time on both DST Mondays: 01:59 refused, 02:01 allowed, 15:39 allowed, 15:56 refused",
          all(w == got for _, w, got in rows), [r_ for r_ in rows if r_[1] != r_[2]])
    td = [nt._trading_day(at(2026, 11, 1, 18, 30)), nt._trading_day(at(2026, 11, 1, 1, 30)),
          nt._trading_day(at(2026, 3, 8, 18, 30)), nt._trading_day(at(2026, 3, 9, 16, 59))]
    check("trading day across the clock change: Sun 18:30 -> Monday; 01:30 on the fall-back night -> Sunday's date",
          td == ["2026-11-02", "2026-11-01", "2026-03-09", "2026-03-09"], td)


def main():
    tmp = tempfile.mkdtemp(prefix="le_nt_exec_audit_")
    saved = {k: os.environ.get(k) for k in (nt.LIVE_ENV, nt.ALLOW_ENV, "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER", "LE_LIT_LEARNING")}
    t0 = time.time()
    try:
        for k in (nt.LIVE_ENV, nt.ALLOW_ENV, "NINJATRADER_ACCOUNT", "NINJATRADER_FOLDER"):
            os.environ.pop(k, None)
        for fn in (test_kill_scope, test_livebot_accounts, test_duplicate_process, test_allowlist, test_startup, test_publish,
                   test_corrupt_state, test_fill_before_ack, test_target_rejected, test_dst):
            try:
                fn(tmp)
            except Exception as ex:
                import traceback
                traceback.print_exc()
                check(f"{fn.__name__} raised {ex.__class__.__name__}: {ex}", False)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed in {time.time() - t0:.0f} s")
    for n in bad:
        print("  FAIL", n)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
