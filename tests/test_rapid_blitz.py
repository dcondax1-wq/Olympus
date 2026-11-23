"""BLITZ on the Rapid EOD 25K EVAL (engine/rapid_blitz.py, owner YES 2026-11-23): a 3rd lane on the Rapid's one account.

    python -X utf8 -m tests.test_rapid_blitz          # paper LiveBots, temp files, Sim / made-up names only (~10 s)

  a. who gets it: the Rapid EOD 25K in eval only (not the 50K, not funded, not with "blitz": false); the CLI switch
  b. the paper LiveBot builds it on the Rapid's account (own tag acctrb_ / state file), the 50K and no-Rapid bots do not
  c. size = the validated research lane: min($300, 30% of the room, the $500 day left) / one stop-out, then the 30% best day
  d. ONE book: LIT's lane, ATLAS and BLITZ read each other's closes (room, day $, the soft day lock)
  e. one position on the account (LIT > ATLAS > BLITZ): BLITZ waits while a higher lane holds / enters; LIT's lane and
     ATLAS entering close BLITZ first (any side) and route only when it is flat
  f. no hedge across accounts: account C / another account's lane opposite blocks BLITZ; account B, the extra accounts and
     LIT's own 50K entry close the Rapid's BLITZ first when it holds the other side
  g. eval only while running: the Rapid switched to funded / off stops new BLITZ entries (the open one is still managed)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import multi_account as MA, rapid, rapid_blitz as RB  # noqa: E402
from tests.test_rapid import Clock, T0, DAY, check, make_bot, lane, RESULTS, ts  # noqa: E402

BLK25 = {"v": 1, "account": "Sim-RapidBlitz25", "plan": "mffu_rapid_eod_25k", "stage": "eval", "eval_start": DAY, "armed": False,
         "payouts": {}}


def open_blitz(rb, tb, d=1, q=2, entry=25020.0, stop=25000.0):
    """A BLITZ position routed on the paper adapter, as AccountC._enter books it."""
    rb.open_t = tb
    rb.prov[tb] = {"key": "blitz", "short": "BLITZ", "qty": q, "dir": d, "est": False, "entry": entry, "stop": stop, "stop_now": stop,
                   "target": entry + d * 400, "t": tb, "risk_pts": abs(entry - stop), "day": DAY, "sig_t": tb - 60}
    rb.route({"sym": "NQ", "side": "buy" if d == 1 else "sell", "qty": q, "stop": stop, "target": entry + d * 400, "entry": entry,
              "entry_t": tb, "src": "blitz", "strategy": "BLITZ"})


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="rapidblitz_")
    try:
        # ---- a. who gets it
        ok, _ = RB.wanted(BLK25)
        check("a. Rapid EOD 25K eval: BLITZ lane ON by default", ok)
        check("a. Rapid EOD 50K: no BLITZ lane", not RB.wanted({**BLK25, "plan": "mffu_rapid_eod_50k"})[0])
        check("a. funded Rapid 25K: no BLITZ lane (eval only)", not RB.wanted({**BLK25, "stage": "funded"})[0])
        check("a. \"blitz\": false: no BLITZ lane", not RB.wanted({**BLK25, "blitz": False})[0])
        p = os.path.join(tmp, "rapid.json")
        rapid.PATH = p
        rapid.save(dict(BLK25), p)
        rc = rapid.main(["--blitz", "off"])
        off_ok = rc == 0 and rapid.load(p).get("blitz") is False
        rapid.main(["--blitz", "on"])
        check("a. CLI: engine.rapid --blitz off / on writes the switch", off_ok and rapid.load(p).get("blitz") is True)
        rapid.save({**BLK25, "plan": "mffu_rapid_eod_50k"}, p)
        check("a. CLI: --blitz refused on a 50K", rapid.main(["--blitz", "on"]) == 1)
        check("a. rules line names the BLITZ lane on the 25K eval only",
              "BLITZ <= $300" in rapid.rules_line(BLK25) and "BLITZ" not in rapid.rules_line({**BLK25, "stage": "funded"}))
        rapid.PATH = None

        # ---- b. the bot builds it
        clk = Clock(T0)
        b = make_bot(os.path.join(tmp, "b25"), clk, dict(BLK25))
        rb = b.acct_rb
        check("b. 25K eval bot: BLITZ lane built on the Rapid's account", rb is not None and rb.name == BLK25["account"]
              and b.acct_r is not None and b.acct_rb2 is None, getattr(rb, "name", None))
        cfg = rb.adapter_cfg() if rb else {}
        check("b. own order tag acctrb_ + own NinjaTrader state + own bot state file",
              cfg.get("nt_file_tag") == "acctrb_" and cfg.get("nt_state_path", "").endswith("ninjatrader_state_acctrb.json")
              and rb.state_path.endswith("live_state_acctrb.json"), (cfg.get("nt_file_tag"), cfg.get("nt_state_path")))
        check("b. the Rapid 25K's rules (target $1,500, $1,000 floor, $500 soft day, 20 micros)",
              rb.rules["target"] == 1500.0 and rb.rules["mll"] == 1000.0 and rb.rules["dll"] == 500.0 and rb.rules["max_micros"] == 20)
        check("b. not armed (the owner's phrase arms the Rapid; never this module)", cfg.get("armed") is False)
        b50 = make_bot(os.path.join(tmp, "b50"), Clock(T0), {**BLK25, "account": "Sim-Rapid50", "plan": "mffu_rapid_eod_50k"})
        check("b. 50K bot: no BLITZ lane", b50.acct_rb is None and b50.acct_r is not None)
        b0 = make_bot(os.path.join(tmp, "b0"), Clock(T0), False)
        check("b. no Rapid: no BLITZ lane", b0.acct_rb is None and b0._rapid_blitzes() == [])

        # ---- c. size
        st = rb.eval_state(T0)
        s1 = rb.size_entry(40.0, st)
        # $300 = min($300, 30% x $1,000, $500); one stop-out (40 + 0.25) x 2 + 1.90 = $82.40 -> 3; 2R winner $158.10 a micro,
        # best day 0.3 x 1,500 x 0.95 = $427.50 -> 2
        check("c. room $1,000, 40-pt stop: $300 / $82.40 = 3 micros, the 30% best day -> 2", s1["qty"] == 2, s1)
        s2 = rb.size_entry(10.0, st)
        check("c. 10-pt stop: $300 / $22.40 = 13 -> best day $427.50 / $38.10 = 11", s2["qty"] == 11, s2)
        s3 = rb.size_entry(200.0, st)
        check("c. 200-pt stop: one stop-out $402.40 > $300: 0 (never 1 micro over the lane's $)", s3["qty"] == 0, s3)
        ln = lane(b)
        with ln.mx:
            ln.closes.append([DAY, T0 - 600, 300.0, T0 - 1800, None])
        s4 = rb.size_entry(10.0, rb.eval_state(T0))
        check("c. LIT's lane +$300 today: BLITZ's best-day cap = ($427.50 - $300) / $38.10 = 3", s4["qty"] == 3, s4)

        # ---- d. one book
        check("d. BLITZ reads LIT's lane's close (day $ and the book)", rb.day_pnl(DAY) == 300.0
              and abs(float(rb.eval_state(T0)["cum"]) - 300.0) < 1e-6, (rb.day_pnl(DAY), rb.eval_state(T0).get("cum")))
        with rb.mx:
            rb.closes.append([DAY, T0 - 300, -120.0, T0 - 900, -1.0])
        check("d. LIT's lane reads BLITZ's close", ln.day_pnl(DAY) == 180.0, ln.day_pnl(DAY))
        check("d. ATLAS reads BLITZ's close", b.acct_r.day_pnl(DAY) == 180.0, b.acct_r.day_pnl(DAY))
        with rb.mx:
            rb.closes.append([DAY, T0 - 200, -700.0, T0 - 400, -3.0])
        rb.check_lock(T0)
        check("d. the $500 soft day on the account's SUM locks BLITZ out today", bool(rb.lock) and rb.lock.get("day") == DAY, rb.lock)
        with rb.mx:
            rb.closes = []
            ln.closes = []
        rb.lock = None

        # ---- e. one position on the account
        b.state = {**(b.state or {}), "enter_now": {"entry_t": T0, "dir": -1}}
        check("e. LIT entering (any side): BLITZ waits", "LIT is entering" in str(rb.opposite(1)), rb.opposite(1))
        b.state.pop("enter_now", None)
        ln.open_t = T0 - 300
        check("e. LIT's lane holds a trade here: BLITZ waits", "LIT's lane holds" in str(rb.opposite(1)), rb.opposite(1))
        ln.open_t = None
        b.acct_r.open_t = T0 - 300
        b.acct_r.prov[T0 - 300] = {"dir": 1, "qty": 1}
        check("e. ATLAS holds the SAME side here: BLITZ still waits (one position per account)", "ATLAS holds" in str(rb.opposite(1)),
              rb.opposite(1))
        b.acct_r.open_t = None
        b.acct_r.prov.pop(T0 - 300, None)
        check("e. account flat: BLITZ may enter", rb.opposite(1) is None, rb.opposite(1))
        tb = T0 + 60
        open_blitz(rb, tb, d=-1)
        held = ln._shared_holds()
        check("e. LIT's lane sees BLITZ holding the account (no blind CLOSEPOSITION)", held and "BLITZ" in held, held)
        okL = rb.yield_to_lit(1, "NQ", T0 + 120, px=25020.0, any_side=True)
        check("e. LIT's lane entering: BLITZ's SHORT closed first (paper confirms), then True", okL is True and rb.open_t is None,
              (okL, rb.open_t))
        open_blitz(rb, tb + 60, d=1)
        why = b.acct_r._c_yield(1, T0 + 300, "NQ", T0 + 300, 25020.0)
        check("e. ATLAS entering the SAME side: BLITZ closed first (ATLAS > BLITZ), ATLAS may route", why is None and rb.open_t is None,
              (why, rb.open_t))
        check("e. sharers of LIT's lane = ATLAS + BLITZ", ln.sharers() == [b.acct_r, rb], ln.sharers())

        # ---- f. no hedge across accounts
        class Other:                                      # another account's BLITZ / ATLAS holding a position
            def __init__(self, name, d):
                self.name, self.open_t, self.prov, self.label = name, T0, {T0: {"dir": d}}, f"x {name}"

            def closing_open(self):
                return []

            def yield_to(self, *a, **k):
                return True
        b.acct_c = Other("Sim-C", -1)
        check("f. account C holds SHORT on another account: BLITZ LONG here refused", "BLITZ (account C)" in str(rb.opposite(1)),
              rb.opposite(1))
        check("f. ... a LONG on the other account is not a hedge: allowed", rb.opposite(-1) is None, rb.opposite(-1))
        b.acct_c = None
        open_blitz(rb, tb + 120, d=-1)
        oo = b.accts.others_opposite(1, None)
        check("f. the extra accounts see the Rapid's BLITZ SHORT (others_opposite)", oo and "BLITZ on the Rapid EOD" in oo, oo)
        oo2 = b.accts.others_opposite(1, ln)
        check("f. ... but not from its own account (that is the one-position yield)", oo2 is None, oo2)
        okx = rb.yield_to(1, "ATLAS", "NQ", T0 + 400, px=25020.0)
        check("f. another account entering LONG: the Rapid's BLITZ SHORT is closed first", okx is True and rb.open_t is None, (okx, rb.open_t))
        open_blitz(rb, tb + 180, d=-1)
        ent = {"entry_t": T0 + 600, "dir": 1, "entry": 25020.0}
        okH = b._hedge_clear_c(ent, "NQ", T0 + 600)
        check("f. LIT's own 50K entry LONG: the Rapid's BLITZ SHORT closed first (LiveBot._hedge_clear_c)", okH is True and rb.open_t is None,
              (okH, rb.open_t))

        # ---- g. eval only while running
        rb.blk = {**BLK25, "stage": "funded"}
        sg = rb.size_entry(10.0, rb.eval_state(T0))
        check("g. the Rapid switched to funded: no new BLITZ entry", sg["qty"] == 0 and "eval-only" in sg["reasons"][0], sg)
        rb.blk = {**BLK25, "blitz": False}
        check("g. switched off: no new BLITZ entry", rb.size_entry(10.0, rb.eval_state(T0))["qty"] == 0)
        rb.blk = {**BLK25, "account": "another"}
        check("g. the Rapid's account changed: no new BLITZ entry", rb.size_entry(10.0, rb.eval_state(T0))["qty"] == 0)
        rb.blk = dict(BLK25)
        with rb.mx:
            rb.closes = [[DAY, T0 - 100, 1500.0, T0 - 200, 5.0]]
        check("g. target reached on the book: no new trade", rb.size_entry(10.0, rb.eval_state(T0))["qty"] == 0)
        ev = rb.eval_view(T0)
        check("g. pass needs 4 days + best day <= 30% (one $1,500 day = still open)", ev.get("status") == "open" and ev.get("pass_wait"), ev)
        for x in (b, b50, b0):
            x.stop()
    finally:
        rapid.PATH = None
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RESULTS), sum(RESULTS)
    print(f"\n{ok}/{n} passed" + ("" if ok == n else " -> FAILURES"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
