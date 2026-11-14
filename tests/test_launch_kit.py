"""MONDAY LAUNCH KIT (2026-11-14; Zlarior on the MFFU 50K eval and ATLAS on its 25K eval go live Monday 2026-11-16 02:00 ET):
the GitHub-free reporting the owner reads on his phone that day. Read-only everywhere: fakes for every file, every HTTP call and
the bot; never the network, never an order, never live_model*.json.

  1. alerts     tools/pc_report.py: a push for every entry (side, micros, entry / stop / target, $ risk and its share of the
                drawdown left, the account) and every exit (how, +/- $ and R, drawdown left, today's $) per account (Zlarior
                50K, ATLAS 25K, BLITZ 25K); a trade that opened and closed between two runs = one push with both; never a late
                "opened"; ATLAS's paper member rows are not the account's trades; a failed push is retried with both keys
  2. fills      tools/fill_check.py: real fills vs the live loop's plan from the bots' own state files (wrong size, missing
                stop, slippage > 2 ticks, bracket prices, costs, an entry that never filled), high-priority pushes once per flag
  3. launch     tools/launch_card.py + engine/live_site.py GET /api/site/launch.json: per bot armed? feed fresh? trades, $,
                drawdown left, flags; the 01:45 ET "ready for 02:00" push (tools/pc_guard.py)
  4. checklist  tools/launch_day.py: docs/LAUNCH_DAY.md and tools/web_public/gate/launch_day.json are the same checklist
  5. page       (node / Chromium, skipped without them) tools/web_public/gate/launch.js draws the card only when served by the PC

  python -X utf8 -m tests.test_launch_kit            (--fast: no browser)
  Browser part under the shared lock: flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_launch_kit
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ["LE_PR_NO_NET"] = "1"                   # the real HTTP helper refuses: only the fakes answer

from zoneinfo import ZoneInfo  # noqa: E402

from tools import pc_report as R  # noqa: E402

ET = ZoneInfo("America/New_York")
RES: list = []
FAST = "--fast" in sys.argv


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:700]})" if info and not cond else ""), flush=True)
    return bool(cond)


def at(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def ascii_ok(s) -> bool:
    return all(ord(ch) < 128 for ch in str(s))


# ============================================================================================== fakes
def lit_card(**kw):
    c = {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "status": "open", "balance": 49145.0, "floor": 48000.0,
         "room": 1145.0, "mll": 2000.0, "today_pnl": 0.0, "dll": 1000.0, "trades_today": 0, "max_day": 1, "eval_start": "2026-11-02", "position": None,
         "configured": True}
    c.update(kw)
    return c


def atlas_card(**kw):
    c = {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "badge": "LIVE", "configured": True, "status": "open", "balance": 24822.0,
         "floor": 24000.0, "room": 822.0, "mll": 1000.0, "today_pnl": 0.0, "dll": 600.0, "trades_today": 0, "max_day": 2, "position": None}
    c.update(kw)
    return c


def blitz_card(**kw):
    c = {"id": "blitz", "name": "BLITZ", "plan": "MFFU Builder 25K", "badge": "SIM", "real": False, "configured": True, "status": "open",
         "room": 1000.0, "mll": 1000.0, "today_pnl": 0.0, "position": None}
    c.update(kw)
    return c


def snap_of(now, board, mode="LIVE", **kw):
    s = {"t": now, "hb": {"running": True, "t": now - 60}, "hb_t": now - 60, "hb_age": 60, "server": True, "nt": True, "market_open": True,
         "entry_hours": True, "mode": mode, "live": {"board": board}}
    s.update(kw)
    return s


def run_events(state, snap):
    return R.events(state, snap)


def titles(msgs):
    return [m["title"] for m in msgs if not m["key"].startswith("guard:")]


def trade_msgs(msgs):
    return [m for m in msgs if m["key"].startswith(("open:", "close:"))]


# ============================================================================================== 1 alerts
def alerts():
    now = at(2026, 11, 16, 10, 15)                # Monday, launch day, entry hours
    pos = {"entry_t": now - 180, "side": "SHORT", "qty": 6, "entry": 25100.25, "stop": 25130.0, "target": 24980.0}
    board = {"lit": lit_card(), "atlas": atlas_card(), "trades": []}
    st, m = run_events({}, snap_of(now - 900, board))
    check("1. first run: only records (no trade push)", not trade_msgs(m), m)
    # ---- an entry on Zlarior: pushed on the next run (one report cycle), every number the owner asked for
    b2 = copy.deepcopy(board)
    b2["lit"]["position"] = dict(pos)
    st, m = run_events(st, snap_of(now, b2))
    tm = trade_msgs(m)
    check("1. Zlarior entry: one push on the next report run, high priority, title 'Zlarior 50K trade opened: SHORT 6 micros'",
          len(tm) == 1 and tm[0]["title"] == "Zlarior 50K trade opened: SHORT 6 micros" and tm[0]["priority"] == "high", tm)
    body = tm[0]["body"] if tm else ""
    check("1. entry body: side, micros, entry, stop (pts), target (pts), $ risk at the stop with costs, its share of the drawdown left, the account",
          "SHORT 6 micros at 25,100.25" in body and "stop 25,130.00 (29.75 pts)" in body and "target 24,980.00 (120.25 pts)" in body
          and "Risk $368 if stopped (costs in), 32% of the $1,145 drawdown left" in body and "Real account (you armed it)" in body, body)
    check("1. the $ risk is micros x stop distance x $2 + $1.90 a micro (6 x 29.75 x 2 + 6 x 1.90 = $368.40)", R.risk_usd(pos) == 368.4, R.risk_usd(pos))
    st, m = run_events(st, snap_of(now + 900, b2))
    check("1. the same open position is not pushed again", not trade_msgs(m), m)
    # ---- the exit: +/- $ and R, how, drawdown left, today
    b3 = copy.deepcopy(board)
    b3["lit"].update(room=1750.0, today_pnl=605.0, trades_today=1)
    b3["trades"] = [{"acct": "lit", "src": "live", "entry_t": pos["entry_t"], "exit_t": now + 1500, "side": "SHORT", "qty": 6, "entry": 25100.25,
                     "stop": 25130.0, "target": 24980.0, "exit_px": 24980.0, "exit": "TARGET", "usd": 605.0, "r": 1.64}]
    st, m = run_events(st, snap_of(now + 1800, b3))
    tm = trade_msgs(m)
    check("1. Zlarior exit: one push 'Zlarior 50K trade closed +$605 (+1.6R)', default priority",
          len(tm) == 1 and tm[0]["title"] == "Zlarior 50K trade closed +$605 (+1.6R)" and tm[0]["priority"] == "default", tm)
    body = tm[0]["body"] if tm else ""
    check("1. exit body: how it ended at which price, +/- $ and R, drawdown left of the max loss, today's $, the account",
          "SHORT 6 micros: TARGET at 24,980.00, +$605 (+1.6R)" in body and "Drawdown left $1,750 of $2,000" in body and "Today +$605" in body
          and "Real account" in body, body)
    # ---- a trade that opened and closed between two runs: ONE push with the entry and the exit
    et2 = now + 2000
    b4 = copy.deepcopy(b3)
    b4["lit"].update(room=1445.0, today_pnl=300.0, trades_today=2)
    b4["trades"] = [{"acct": "lit", "src": "live", "entry_t": et2, "exit_t": et2 + 420, "side": "LONG", "qty": 5, "entry": 25010.0, "stop": 24980.0,
                     "target": 25110.0, "exit_px": 24980.0, "exit": "STOP", "usd": -309.5}] + b3["trades"]
    st, m = run_events(st, snap_of(now + 2700, b4))
    tm = trade_msgs(m)
    body = tm[0]["body"] if tm else ""
    check("1. opened and closed between two runs: one push, its keys both recorded, with the entry (side, micros, stop, target, risk) and the exit (-$, R from the stop, drawdown left)",
          len(tm) == 1 and tm[0]["title"] == "Zlarior 50K trade closed -$310 (-1.0R)" and tm[0]["keys"] == [f"close:lit:{et2}", f"open:lit:{et2}"]
          and body.startswith("Opened Mon ") and "LONG 5 micros at 25,010.00, stop 24,980.00 (30.00 pts), target 25,110.00 (100.00 pts)" in body
          and "Risk $310 if stopped" in body and "Closed: STOP at 24,980.00, -$310 (-1.0R)" in body and "Drawdown left $1,445 of $2,000" in body, tm)
    check("1. R is worked out from the stop when the row has none (-$309.50 / $309.50 = -1.0R)", R._r_of(b4["trades"][0]) == -1.0, R._r_of(b4["trades"][0]))
    st, m = run_events(st, snap_of(now + 3600, b4))
    check("1. nothing repeated on the next run", not trade_msgs(m), m)
    # ---- the update itself: a state from before (a close pushed, no open key) never gets a late "opened"
    old_state = {"seen": {f"close:lit:{et2}": now + 2700}, "cond": {}, "seeded": True}
    _s, m = run_events(old_state, snap_of(now + 3600, b4))
    check("1. a trade closed and pushed before this update: no late 'opened' push", not [x for x in trade_msgs(m) if x["key"].startswith("open:")]
          and f"open:lit:{et2}" in _s["seen"], m)
    # ---- ATLAS on its own 25K (account B): its entry and exit say ATLAS 25K and the real account; its paper member rows are not its trades
    ab_pos = {"entry_t": now + 4000, "side": "LONG", "qty": 3, "entry": 25050.0, "stop": 25020.0, "target": 25120.0, "strategy": "MACD"}
    b5 = copy.deepcopy(b4)
    b5["atlas"]["position"] = dict(ab_pos)
    b5["trades"] = [{"acct": "atlas", "src": "paper", "key": "ema_lon_vix", "member": "EMA", "entry_t": now + 3900, "exit_t": now + 4200, "side": "SHORT",
                     "qty": 2, "entry": 25060.0, "exit": "TARGET", "usd": 140.0}] + b4["trades"]
    st, m = run_events(st, snap_of(now + 4500, b5))
    tm = trade_msgs(m)
    check("1. ATLAS entry on its real 25K: 'ATLAS 25K trade opened: LONG 3 micros', risk $186 of the $822 left, 'Real account'",
          [x["title"] for x in tm] == ["ATLAS 25K trade opened: LONG 3 micros"] and "Risk $186 if stopped (costs in), 23% of the $822 drawdown left" in tm[0]["body"]
          and "Real account." in tm[0]["body"], tm)
    check("1. ATLAS's paper member trade (EMA, src paper) is not pushed while account B trades", not [x for x in tm if "EMA" in x["body"] or "SHORT 2" in x["body"]], tm)
    # ---- ATLAS without an account: its paper rows are its only trades (as before), said as paper
    b6 = {"lit": lit_card(), "atlas": atlas_card(configured=False, badge=None, status="not set up", room=None), "trades": [
        {"acct": "atlas", "src": "paper", "key": "macd_sweep", "entry_t": now + 5000, "exit_t": now + 5400, "side": "LONG", "qty": 2, "entry": 25000.0,
         "stop": 24990.0, "exit": "TARGET", "usd": 80.0}]}
    st2, m = run_events({"seen": {}, "cond": {}, "seeded": True}, snap_of(now + 5500, b6))
    tm = trade_msgs(m)
    check("1. ATLAS with no account set up: its paper trade still pushes, said as paper", len(tm) == 1 and "Paper (no account set up)." in tm[0]["body"], tm)
    # ---- BLITZ on Sim (account C)
    b7 = {"lit": lit_card(), "atlas": atlas_card(), "blitz": blitz_card(position={"entry_t": now + 6000, "side": "SHORT", "qty": 4, "entry": 25080.0,
                                                                                    "stop": 25092.0, "target": 25056.0}), "trades": []}
    _s, m = run_events({"seen": {}, "cond": {}, "seeded": True}, snap_of(now + 6100, b7))
    tm = trade_msgs(m)
    check("1. BLITZ on Sim: 'BLITZ 25K trade opened: SHORT 4 micros', 'Sim account.'", [x["title"] for x in tm] == ["BLITZ 25K trade opened: SHORT 4 micros"]
          and "Sim account." in tm[0]["body"], tm)
    allm = [x for x in trade_msgs(m)]
    check("1. every trade push title is ASCII (an HTTP header) and under 120 characters", all(ascii_ok(x["title"]) and len(x["title"]) <= 120 for x in allm), allm)
    # ---- Zlarior on Sim / paper says so
    _s, m = run_events({"seen": {}, "cond": {}, "seeded": True}, snap_of(now, b2, mode="Sim"))
    check("1. Zlarior on Sim: the entry says 'Sim account.'", trade_msgs(m) and "Sim account." in trade_msgs(m)[0]["body"], m)
    # ---- an open position without a stop in the report says so (the fill check pushes the details)
    b8 = copy.deepcopy(board)
    b8["lit"]["position"] = {**pos, "stop": None}
    _s, m = run_events({"seen": {}, "cond": {}, "seeded": True}, snap_of(now, b8))
    check("1. an open position with no stop in the report: the entry push says 'NO STOP in the report'", trade_msgs(m) and "NO STOP in the report" in trade_msgs(m)[0]["body"], m)


def alerts_retry():
    """Through run_once: a failed combined push is retried with both keys (fake ntfy 429, then OK)."""
    from tests.test_bots_back import Box, FakeHTTP
    from tests.test_live_publish import hb_payload
    b = Box()
    try:
        cfg = b.topic()
        now = at(2026, 11, 16, 10, 0)
        hb = hb_payload(now - 60, position=False)
        b.hb(hb)
        b.run(FakeHTTP(), now)                                  # first run: records
        hb2 = copy.deepcopy(hb)
        hb2["acct"]["trades"].append({"day": "2026-11-16", "entry_t": now + 120, "exit_t": now + 600, "side": "LONG", "qty": 3, "entry": 25010.0,
                                      "stop": 24990.0, "target": 25070.0, "exit_px": 25070.0, "pnl": 354.3, "r": 3.0, "exit": "TARGET"})
        hb2["t"] = now + 840
        b.hb(hb2)
        h = FakeHTTP(ntfy_status=429)
        rec = b.run(h, now + 900)
        state = json.load(open(os.path.join(b.work, "state.json"), encoding="utf-8"))
        check("1. a combined push refused by ntfy (429): both its keys forgotten for the next run", rec["ok"] is False
              and f"close:lit:{now + 120}" not in state["seen"] and f"open:lit:{now + 120}" not in state["seen"], (rec.get("errors"), list(state["seen"])[-4:]))
        hb2["t"] = now + 1740
        b.hb(hb2)
        h = FakeHTTP()
        b.run(h, now + 1800)
        ps = [c for c in h.posts(cfg["topic"]) if "trade" in c["h"].get("Title", "")]
        check("1. ... and sent once on the next run, through the real board (Zlarior 50K, +$354, +3.0R, entry and exit in one push)",
              len(ps) == 1 and ps[0]["h"]["Title"] == "Zlarior 50K trade closed +$354 (+3.0R)" and "Opened " in ps[0]["body"]
              and "LONG 3 micros at 25,010.00, stop 24,990.00 (20.00 pts)" in ps[0]["body"] and "Closed: TARGET at 25,070.00" in ps[0]["body"], ps)
    finally:
        b.cleanup()


# ============================================================================================== 2 fills
class Root:
    """A temp bot folder with the bots' own state files (the shapes engine/live.py, engine/account_b.py and the NinjaTrader
    adapter write), filled by the test."""

    def __init__(self):
        import tempfile
        self.dir = tempfile.mkdtemp(prefix="lk_", dir=os.environ.get("LE_TEST_TMP") or None)
        for d in ("data", os.path.join("logs", "exec_audit"), os.path.join("logs", "learning"), os.path.join("logs", "pc_hb")):
            os.makedirs(os.path.join(self.dir, d), exist_ok=True)

    def write(self, rel, obj):
        p = os.path.join(self.dir, *rel.split("/"))
        with open(p, "w", encoding="utf-8") as fh:
            if rel.endswith(".jsonl"):
                for r in obj:
                    fh.write(json.dumps(r) + "\n")
            else:
                json.dump(obj, fh)

    def cleanup(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)


def entry_row(t, et_, side="sell", qty=6, entry=25100.0, stop=25130.0, target=24980.0, legs=None, ok=True, error=None, env="live",
              account="MFFUEVAL50K1", adapter="ninjatrader", **kw):
    res = {"ok": ok, "adapter": adapter, "account": account, "env": env, "side": "SELL" if side == "sell" else "BUY",
           "legs": legs if legs is not None else [{"instrument": "MNQ 12-26", "qty": qty, "filled": qty, "fill_px": entry, "ok": True,
                                                   "stop": stop, "target": target, "stop_state": "WORKING", "target_state": "WORKING"}]}
    if error:
        res["error"] = error
    if adapter == "paper":
        res = {"ok": True, "adapter": "paper", "note": "simulated"}
    return {"t": t, "sym": "NQ", "side": side, "qty": qty, "entry": entry, "stop": stop, "target": target, "entry_t": et_, "result": res, **kw}


def leg(et_, qty, filled, fill_px, status="protected", bracket=None, stop=25130.0, target=24980.0, nonce="ABCD", d=-1):
    base = f"LE{et_}{nonce}M"
    return {"instrument": "MNQ 12-26", "qty": qty, "side": "SELL" if d == -1 else "BUY", "dir": d, "entry_t": et_, "stop": stop, "stop0": stop,
            "target": target, "entry_id": base + "E", "stop_id": base + "S", "target_id": base + "T", "status": status, "filled": filled,
            "fill_px": fill_px, "bracket_qty": filled if bracket is None else bracket}


LEG_LETTER = {"entry": "E", "stop": "S", "target": "T"}


def order(et_, legname, state, filled, avg, nonce="ABCD", mtime=None):
    """One archived NinjaTrader order state (logs/exec_audit/orders.jsonl): id LE<entry_t><nonce>M<E|S|T>."""
    return {"id": f"LE{et_}{nonce}M{LEG_LETTER[legname]}", "state": state, "filled": filled, "avg": avg, "mtime": mtime or et_ + 60, "seen": et_ + 61}


def fills():
    from tools import fill_check as F
    now = at(2026, 11, 16, 11, 0)
    rt = Root()
    try:
        # ---- a clean Zlarior trade on the real 50K: SHORT 6, filled 1 tick worse, bracket in place, out at the target
        e1 = now - 3600
        rt.write("data/live_state.json", {"adapter": "ninjatrader", "day": "2026-11-16", "ledger": [
            entry_row(e1 + 2, e1, legs=[{"instrument": "MNQ 12-26", "qty": 6, "filled": 6, "fill_px": 25099.75, "ok": True, "stop": 25130.0,
                                         "target": 24980.0, "stop_state": "WORKING", "target_state": "WORKING"}]),
            {"t": e1 + 1800, "side": "exit", "qty": 6, "reason": "TARGET", "entry_t": e1, "exit_t": e1 + 1790, "pnl": 1427.4}]})
        rt.write("logs/exec_audit/orders.jsonl", [order(e1, "entry", "FILLED", 6, 25099.75), order(e1, "stop", "CANCELLED", 0, 0),
                                                  order(e1, "target", "FILLED", 6, 24980.0, mtime=e1 + 1790)])
        revs = F.reviews(rt.dir, now)
        r = revs[0] if revs else {}
        check("2. a clean real trade: reviewed (Zlarior 50K, LIVE), no flag, 'Fill check OK', exit price from NinjaTrader's target fill",
              len(revs) == 1 and r["label"] == "Zlarior 50K" and r["kind"] == "LIVE" and r["ok"] and r["real"]["filled"] == 6
              and r["slip"]["entry_ticks"] == 1.0 and r["real"]["exit"] == 24980.0 and r["real"]["exit_kind"] == "TARGET"
              and r["line"].endswith("Fill check OK."), r)
        check("2. the line says it plainly: filled 6 of 6 at the price, the plan's price, 1 tick worse, the stop, out at the target",
              "filled 6 of 6 at 25,099.75 (plan 25,100.00, 1 tick worse), stop 25,130.00, out target at 24,980.00" in r.get("line", ""), r.get("line"))
        check("2. costs: plan $2.40 a micro (1 tick + $1.90), real $2.40 (1 tick entry + $1.90); execution $ = real fills - booked",
              r["costs"]["plan_micro"] == 2.4 and r["costs"]["real_micro"] == 2.4 and r["costs"]["exec_usd"] == round(6 * ((24980.0 - 25099.75) * -1 * 2 - 1.9) - 1427.4, 2),
              r.get("costs"))
        check("2. push note for the (closed) trade: 'Fill check OK: 6 of 6 filled, 1 tick worse than the plan, the stop was in place.'",
              F.short(r) == "Fill check OK: 6 of 6 filled, 1 tick worse than the plan, the stop was in place.", F.short(r))
        # ---- wrong size, the stop covering fewer micros, a 3-tick entry, an UNPROTECTED leg
        e2 = now - 1200
        led = json.load(open(os.path.join(rt.dir, "data", "live_state.json"), encoding="utf-8"))
        led["ledger"].append(entry_row(e2 + 3, e2, side="buy", qty=5, entry=25010.0, stop=24980.0, target=25110.0,
                                       legs=[{"instrument": "MNQ 12-26", "qty": 5, "filled": 3, "fill_px": 25010.75, "ok": True, "stop": 24980.0,
                                              "target": 25110.0, "stop_state": "WORKING"}]))
        rt.write("data/live_state.json", led)
        rt.write("data/ninjatrader_state.json", {"account": "MFFUEVAL50K1", "legs": [leg(e2, 5, 3, 25010.75, bracket=2, stop=24980.0, target=25110.0, nonce="WXYZ", d=1)]})
        r = next(x for x in F.reviews(rt.dir, now) if x["entry_t"] == e2)
        codes = [f["code"] for f in r["flags"]]
        check("2. wrong size: NinjaTrader filled 3 of the 5 micros sent, and the stop covers 2 of the 3 (two 'size' flags, bad)",
              codes.count("size") == 2 and "NinjaTrader filled 3 micros, the bot sent 5." in [f["text"] for f in r["flags"]]
              and "The stop covers 2 of the 3 filled micros." in [f["text"] for f in r["flags"]] and r["level"] == "bad", r["flags"])
        check("2. entry 3 ticks worse than the plan (25,010.75 vs 25,010.00): 'slip_entry' with the $", "slip_entry" in codes
              and any("3 ticks worse than the plan (25,010.75 vs 25,010.00): $4.50 on 3 micros" in f["text"] for f in r["flags"]), r["flags"])
        led2 = copy.deepcopy(led)
        led2["ledger"][-1]["result"]["legs"][0]["fill_px"] = 25010.5
        rt.write("data/live_state.json", led2)
        r = next(x for x in F.reviews(rt.dir, now) if x["entry_t"] == e2)
        check("2. exactly 2 ticks worse is not flagged (the owner's line is MORE than 2 ticks)", "slip_entry" not in [f["code"] for f in r["flags"]], r["flags"])
        rt.write("data/ninjatrader_state.json", {"account": "MFFUEVAL50K1", "legs": [leg(e2, 5, 5, 25010.5, status="unprotected", bracket=0, stop=24980.0,
                                                                                         target=25110.0, nonce="WXYZ", d=1)]})
        r = next(x for x in F.reviews(rt.dir, now) if x["entry_t"] == e2)
        st = [f for f in r["flags"] if f["code"] == "stop"]
        check("2. missing stop: the NinjaTrader leg is UNPROTECTED -> 'stop' (bad) with the one action (flatten in NinjaTrader if no stop order)",
              st and st[0]["level"] == "bad" and "no stop at NinjaTrader" in st[0]["text"] and "Flatten" in st[0]["fix"], r["flags"])
        # ---- the bracket not delivered at the route, protected later = fine; never protected = flagged
        e3 = now - 900
        legs_nd = [{"instrument": "MNQ 12-26", "qty": 2, "filled": 2, "fill_px": 25050.0, "ok": False, "error": "bracket not delivered: incoming folder locked"}]
        rt.write("data/live_state.json", {"adapter": "ninjatrader", "ledger": [entry_row(e3 + 2, e3, qty=2, entry=25050.0, legs=legs_nd, ok=False,
                                                                                        error="MNQ 12-26: bracket not delivered: incoming folder locked")]})
        rt.write("data/ninjatrader_state.json", {"legs": [leg(e3, 2, 2, 25050.0, status="protected", nonce="P1P1")]})
        r = F.reviews(rt.dir, now)[0]
        check("2. bracket not delivered at the route but the leg is protected on the next poll: no 'stop' flag", "stop" not in [f["code"] for f in r["flags"]], r["flags"])
        rt.write("data/ninjatrader_state.json", {"legs": []})
        r = F.reviews(rt.dir, now)[0]
        check("2. bracket not delivered and never protected: 'stop' flag", "stop" in [f["code"] for f in r["flags"]], r["flags"])
        rt.write("logs/exec_audit/orders.jsonl", [order(e3, "entry", "FILLED", 2, 25050.0, nonce="P1P1"), order(e3, "stop", "REJECTED", 0, 0, nonce="P1P1")])
        rt.write("data/live_state.json", {"adapter": "ninjatrader", "ledger": [entry_row(e3 + 2, e3, qty=2, entry=25050.0)]})
        r = F.reviews(rt.dir, now)[0]
        check("2. NinjaTrader rejected the stop order (archived state REJECTED): 'stop' flag says so",
              any(f["code"] == "stop" and "rejected the stop order" in f["text"] for f in r["flags"]), r["flags"])
        # ---- exit slippage at a breakeven stop, the bracket's price off, costs above plan
        e4 = now - 2400
        rt.write("data/live_state.json", {"adapter": "ninjatrader", "ledger": [
            entry_row(e4 + 2, e4, side="buy", qty=4, entry=25000.0, stop=24970.0, target=25100.0,
                      legs=[{"instrument": "MNQ 12-26", "qty": 4, "filled": 4, "fill_px": 25000.25, "ok": True, "stop": 24970.0, "target": 25100.0,
                             "stop_state": "WORKING"}]),
            {"t": e4 + 600, "side": "modify", "qty": 4, "stop": 25001.25, "reason": "BE", "entry_t": e4, "result": {"ok": True}},
            {"t": e4 + 900, "side": "exit", "qty": 4, "reason": "BE", "entry_t": e4, "exit_t": e4 + 890, "pnl": -2.6}]})
        rt.write("logs/exec_audit/orders.jsonl", [order(e4, "entry", "FILLED", 4, 25000.25, nonce="Q2Q2"), order(e4, "stop", "FILLED", 4, 25000.0, nonce="Q2Q2", mtime=e4 + 890)])
        r = F.reviews(rt.dir, now)[0]
        check("2. a breakeven stop filled 5 ticks past its moved price (25,000.00 vs 25,001.25): 'slip_exit', exit kind BE",
              r["real"]["exit_kind"] == "BE" and r["slip"]["exit_ticks"] == 5.0 and any(f["code"] == "slip_exit" and "5 ticks past its price" in f["text"] for f in r["flags"]), r)
        rt.write("logs/exec_audit/orders.jsonl", [order(e4, "entry", "FILLED", 4, 25000.5, nonce="Q2Q2"), order(e4, "stop", "FILLED", 4, 25000.75, nonce="Q2Q2", mtime=e4 + 890)])
        led4 = json.load(open(os.path.join(rt.dir, "data", "live_state.json"), encoding="utf-8"))
        led4["ledger"][0]["result"]["legs"][0]["fill_px"] = 25000.5
        rt.write("data/live_state.json", led4)
        r = F.reviews(rt.dir, now)[0]
        check("2. 2 ticks in + 2 ticks out (none over 2): 'costs' $3.90 a micro vs the plan's $2.40",
              [f["code"] for f in r["flags"]] == ["costs"] and "Costs $3.90 a micro" in r["flags"][0]["text"] and "$2.40" in r["flags"][0]["text"], r["flags"])
        led4["ledger"][0]["result"]["legs"][0]["stop"] = 24968.0
        rt.write("data/live_state.json", led4)
        r = F.reviews(rt.dir, now)[0]
        check("2. the bracket's stop 8 ticks from the plan's (24,968.00 vs 24,970.00): 'stop_off' (bad)",
              any(f["code"] == "stop_off" and f["level"] == "bad" and "8 ticks apart" in f["text"] for f in r["flags"]), r["flags"])
        # ---- an entry that never filled, a hedge refusal, a pending fill, paper
        e5 = now - 700
        rt.write("logs/exec_audit/orders.jsonl", [])
        rt.write("data/ninjatrader_state.json", {"legs": []})
        rt.write("data/live_state.json", {"adapter": "ninjatrader", "ledger": [
            entry_row(e5 + 2, e5, legs=[], ok=False, error="REFUSED: NinjaTrader reports every connection DISCONNECTED (Rithmic)"),
            entry_row(e5 + 62, e5 + 60, legs=[], ok=False, error="REFUSED: hedging guard: account B holds LONG"),
            entry_row(now - 30, now - 40, legs=[{"instrument": "MNQ 12-26", "qty": 6, "ok": False, "state": "WORKING",
                                                 "note": "fill not reported yet: the stop and target go in the moment NinjaTrader reports it (next poll)"}],
                      ok=False, error="MNQ 12-26: fill not reported yet"),
            entry_row(e5 + 120, e5 + 120, adapter="paper")]})
        rv = {x["entry_t"]: x for x in F.reviews(rt.dir, now)}
        check("2. an entry NinjaTrader refused (connections DISCONNECTED), settled: 'refused' with NinjaTrader's reason",
              e5 in rv and [f["code"] for f in rv[e5]["flags"]] == ["refused"] and "DISCONNECTED" in rv[e5]["flags"][0]["text"], rv.get(e5))
        check("2. the bot's own hedging refusal is by design: not reviewed", e5 + 60 not in rv, list(rv))
        check("2. a fill not reported yet, 40 s after the send: waiting, no flag yet", (now - 40) in rv and not rv[now - 40]["flags"]
              and "waiting for the fill" in rv[now - 40]["line"], rv.get(now - 40))
        check("2. a paper route (fills at the model price): nothing to compare, not reviewed", e5 + 120 not in rv, list(rv))
        later = {x["entry_t"]: x for x in F.reviews(rt.dir, now + 400)}
        check("2. the same fill still not reported 7 minutes later: 'refused' (never filled), in plain words",
              [f["code"] for f in later[now - 40]["flags"]] == ["refused"] and "NinjaTrader never reported a fill" in later[now - 40]["flags"][0]["text"], later.get(now - 40))
        # ---- ATLAS (account B) on its 25K, Sim kind, the learned commission, two accounts on the same minute
        e6 = now - 1500
        rt.write("data/live_state.json", {"adapter": "ninjatrader", "ledger": [entry_row(e6 + 2, e6, qty=6, entry=25100.0, legs=[])]})
        rt.write("data/live_state_acctb.json", {"account": "Sim102", "ledger": [
            entry_row(e6 + 20, e6, side="buy", qty=3, entry=25050.0, stop=25020.0, target=25120.0, env="demo", account="Sim102", src="macd_sweep",
                      strategy="MACD", legs=[{"instrument": "MNQ 12-26", "qty": 3, "filled": 3, "fill_px": 25050.25, "ok": True, "stop": 25020.0,
                                              "target": 25120.0, "stop_state": "WORKING"}])]})
        rt.write("data/ninjatrader_state_acctb.json", {"account": "Sim102", "legs": [leg(e6, 3, 3, 25050.25, stop=25020.0, target=25120.0, nonce="BBBB", d=1)]})
        rt.write("logs/exec_audit/orders.jsonl", [order(e6, "entry", "FILLED", 6, 25100.5, nonce="AAAA"), order(e6, "entry", "FILLED", 3, 25050.25, nonce="BBBB"),
                                                  order(e6, "stop", "WORKING", 0, 0, nonce="BBBB"), order(e6, "stop", "WORKING", 0, 0, nonce="AAAA")])
        rt.write("logs/learning/costs.json", {"bots": {"lit": {"comm": 2.6, "comm_obs": 9}, "atlas": {"comm": 1.9, "comm_obs": 0}}})
        rv = {(x["acct"], x["entry_t"]): x for x in F.reviews(rt.dir, now)}
        a, z = rv.get(("atlas", e6)), rv.get(("lit", e6))
        check("2. ATLAS on account B: reviewed as 'ATLAS 25K', Sim (env demo), its member MACD, its own legs; no flag",
              a and a["label"] == "ATLAS 25K" and a["kind"] == "SIM" and a["strategy"] == "MACD" and a["ok"] and a["real"]["covered"] == 3, a)
        check("2. two accounts entered on the same minute: each gets its own NinjaTrader fill (Zlarior 6 at 25,100.50 by its size, ATLAS 3 by its leg ids)",
              z and z["real"]["filled"] == 6 and z["real"]["fill"] == 25100.5 and a["real"]["fill"] == 25050.25, (z, a))
        check("2. Zlarior's learned commission ($2.60, 9 observations) is used in its costs; ATLAS has learned none ($1.90)",
              z["costs"]["comm"] == 2.6 and a["costs"]["comm"] == 1.9, (z.get("costs"), a.get("costs")))
        check("2. trades older than 36 hours are left out", F.reviews(rt.dir, now + 40 * 3600) == [], F.reviews(rt.dir, now + 40 * 3600))
        sm = F.summary(F.reviews(rt.dir, now), now)
        check("2. summary for the dashboard: today's trades and flags per account, the last rows with their line",
              sm["n"] == 2 and sm["by"]["atlas"]["trades"] == 1 and sm["rows"] and all(set(x) >= {"acct", "line", "level"} for x in sm["rows"]), sm)
        # ---- push text
        r = F.reviews(rt.dir, now)[0]
        flag = {"code": "size", "level": "bad", "text": "NinjaTrader filled 3 micros, the bot sent 5.", "fix": F.FIX["size"]}
        tt, bb = F.push_text({**r, "label": "Zlarior 50K", "kind": "LIVE"}, flag)
        check("2. a flag's push: ASCII title 'Zlarior 50K fill check: wrong size', the plan's numbers and the one action in the body",
              tt == "Zlarior 50K fill check: wrong size" and ascii_ok(tt) and "Plan: entry" in bb and "Do: Open NinjaTrader > Positions" in bb
              and "(real account)" in bb, (tt, bb))
        # ---- junk files never raise
        for rel in ("data/live_state.json", "data/live_state_acctb.json", "data/ninjatrader_state.json"):
            with open(os.path.join(rt.dir, *rel.split("/")), "w", encoding="utf-8") as fh:
                fh.write("{not json")
        with open(os.path.join(rt.dir, "logs", "exec_audit", "orders.jsonl"), "w", encoding="utf-8") as fh:
            fh.write("junk\n{\"id\": 5}\n")
        check("2. broken files: no exception, nothing reviewed", F.reviews(rt.dir, now) == [])
        check("2. junk ledger rows: no exception", isinstance(F.reviews(rt.dir, now, src={"accounts": {"lit": {"ledger": [{"side": "buy", "entry_t": "x"}, 5, None],
                                                                                                                   "legs": "x"}}, "orders": 3}), list))
    finally:
        rt.cleanup()
    src = open(os.path.join(ROOT, "tools", "fill_check.py"), encoding="utf-8").read()
    body = src.split('"""', 2)[-1]
    check("2. fill_check.py is read-only: no file write, no order line, no HTTP, no live_model, no arming",
          not re.search(r"open\([^)]*['\"][wa]b?['\"]|PLACE;|place_line|CLOSEPOSITION|urllib|requests|live_model|LIVE_PHRASE|/api/live", body)
          and "json.dump(" not in body)


def fills_report():
    """Through pc_report.run_once with a temp bot folder: the flags are pushed once each, high priority; the trade push ends
    with the fill check; a flag on a trade older than 6 hours is recorded only."""
    from tests.test_bots_back import Box, FakeHTTP
    from tests.test_live_publish import hb_payload
    b = Box()
    try:
        cfg = b.topic()
        now = at(2026, 11, 16, 10, 0)
        os.makedirs(os.path.join(b.root, "data"), exist_ok=True)
        hb = hb_payload(now - 60, position=False)
        b.hb(hb)
        b.run(FakeHTTP(), now)                                   # the first run records what is there
        hb2 = hb_payload(now + 840, position=True)               # the position: SHORT 6 at 25,100.25, entry_t = now + 240
        b.hb(hb2)
        et_ = now + 240
        with open(os.path.join(b.root, "data", "live_state.json"), "w", encoding="utf-8") as fh:
            json.dump({"adapter": "ninjatrader", "ledger": [entry_row(et_ + 2, et_, qty=6, entry=25100.25, stop=25130.0, target=24980.0,
                                                                      legs=[{"instrument": "MNQ 12-26", "qty": 6, "filled": 4, "fill_px": 25099.25, "ok": True,
                                                                             "stop": 25130.0, "target": 24980.0, "stop_state": "WORKING"}])]}, fh)
        h = FakeHTTP()
        rec = b.run(h, now + 900)
        ps = h.posts(cfg["topic"])
        by = {c["h"].get("Title"): c for c in ps}
        fl = [c for c in ps if "fill check" in c["h"].get("Title", "")]
        check("2. reporter: the flags of the new trade are pushed, high priority: wrong size and entry slippage (4 ticks)",
              sorted(c["h"]["Title"] for c in fl) == ["Zlarior 50K fill check: entry slippage", "Zlarior 50K fill check: wrong size"]
              and all(c["h"].get("Priority") == "high" for c in fl), [c["h"] for c in ps])
        op = by.get("Zlarior 50K trade opened: SHORT 6 micros")
        check("2. reporter: the entry push ends with the fill check's flags ('see the separate alert')", op is not None
              and "Fill check: wrong size; entry slippage (separate alert)." in op["body"], [c["body"] for c in ps])
        check("2. reporter: every push header is ASCII", all(ascii_ok(v) for c in ps for v in c["h"].values()), [c["h"] for c in ps])
        h = FakeHTTP()
        b.run(h, now + 1800)
        check("2. reporter: the same flags are not pushed again", not [c for c in h.posts(cfg["topic"]) if "fill check" in c["h"].get("Title", "")],
              [c["h"] for c in h.posts(cfg["topic"])])
        # a flag push refused by ntfy is retried
        with open(os.path.join(b.root, "data", "live_state.json"), "w", encoding="utf-8") as fh:
            json.dump({"adapter": "ninjatrader", "ledger": [entry_row(et_ + 2, et_, qty=6, entry=25100.25, legs=[{"instrument": "MNQ 12-26", "qty": 6, "filled": 4,
                                                                                                                   "fill_px": 25099.25, "ok": True, "stop": 25130.0, "target": 24980.0}]),
                                                            entry_row(now + 1900, now + 1880, side="buy", qty=2, entry=25000.0, stop=24990.0, target=25040.0,
                                                                      legs=[{"instrument": "MNQ 12-26", "qty": 2, "filled": 2, "fill_px": 25000.0, "ok": False,
                                                                             "error": "bracket not delivered: x"}], ok=False, error="bracket not delivered: x")]}, fh)
        h = FakeHTTP(ntfy_status=429)
        b.run(h, now + 2700)
        h = FakeHTTP()
        b.run(h, now + 3600)
        fl = [c for c in h.posts(cfg["topic"]) if "fill check" in c["h"].get("Title", "")]
        check("2. reporter: a missing-stop push refused by ntfy is sent on the next run", [c["h"]["Title"] for c in fl] == ["Zlarior 50K fill check: NO STOP at NinjaTrader"]
              and "Flatten" in fl[0]["body"], [c["h"] for c in h.posts(cfg["topic"])])
        # an old trade's flag (> 6 h) is recorded, not pushed
        old = now - 8 * 3600
        with open(os.path.join(b.root, "data", "live_state.json"), "w", encoding="utf-8") as fh:
            json.dump({"adapter": "ninjatrader", "ledger": [entry_row(old + 2, old, qty=3, legs=[{"instrument": "MNQ 12-26", "qty": 3, "filled": 1, "fill_px": 25100.0,
                                                                                                    "ok": True, "stop": 25130.0, "target": 24980.0}])]}, fh)
        h = FakeHTTP()
        b.run(h, now + 4500)
        check("2. reporter: a flag on a trade older than 6 hours is recorded, never pushed late", not [c for c in h.posts(cfg["topic"]) if "fill check" in c["h"].get("Title", "")],
              [c["h"] for c in h.posts(cfg["topic"])])
    finally:
        b.cleanup()
    now = at(2026, 11, 16, 11, 0)
    rv = {"acct": "blitz", "label": "BLITZ 25K", "entry_t": now - 300, "side": "LONG", "kind": "SIM", "plan": {"qty": 4}, "real": {},
          "flags": [{"code": "size", "level": "bad", "text": "NinjaTrader filled 2 micros, the bot sent 4.", "fix": "x"}]}
    _s, m = R.events({"seen": {}, "cond": {}, "seeded": True}, snap_of(now, {"lit": lit_card(), "trades": []}, fills=[rv]))
    fm = [x for x in m if x["key"].startswith("fill:")]
    check("2. a Sim account's flag (BLITZ on Sim) is pushed at default priority; a real account's is high", [x["priority"] for x in fm] == ["default"]
          and [x["priority"] for x in R.events({"seen": {}, "cond": {}, "seeded": True}, snap_of(now, {"lit": lit_card(), "trades": []}, fills=[{**rv, "kind": "LIVE"}]))[1]
               if x["key"].startswith("fill:")] == ["high"], fm)


# ============================================================================================== 3 launch card + the 01:45 push
def live_of(now, lit=None, atlas=None, blitz=None, running=True, feed=None, account=None, facts=None, blocks=None, nt=True):
    """A live.json (engine/live_publish.build shape) with the parts the Launch card reads."""
    pc = {"running": running, "adapter": "ninjatrader", "present": True, "t": now - 10,
          "health": {"account": {"name": "MFFUEVAL50K1", "adapter": "ninjatrader", "is_live": True, "label": "LIVE", "armed": True, "enabled": True,
                                 "disabled": None, **(account or {})},
                     "feed": {"age_1m_s": 20, "age_5m_s": 80, "stale": False, "market_open": True, "entries_blocked": False, "block": None, **(feed or {})},
                     "nt": {"connected": nt}},
          "launch": {"facts": facts if facts is not None else {"lit_armed": True, "b": {"configured": True, "account": "MFFUEVAL25K1", "armed": True}}}}
    board = {"t": now - 10, "lit": lit or lit_card(), "atlas": atlas or atlas_card(), "blocks": blocks or [], "trades": []}
    if blitz:
        board["blitz"] = blitz
    return {"v": 1, "kind": "le-live", "t": now - 10, "pc": pc, "board": board,
            "pc_verdict": {"code": "TRADING", "label": "TRADING YOUR EVAL", "level": "ok", "reason": "LIT watching"}}


def launch():
    from tools import launch_card as LC
    now = at(2026, 11, 16, 1, 45)
    good = LC.build(live_of(now), [], {"level": "ok", "text": "Phone alerts on: last check 4 min ago."}, now)
    rows = {r["id"]: r for r in good["bots"]}
    check("3. all well: level ok, 'Zlarior and ATLAS armed; feed fresh (1-minute bar 20 s old); no flags.'",
          good["level"] == "ok" and good["headline"] == "Zlarior and ATLAS armed; feed fresh (1-minute bar 20 s old); no flags." and not good["global"], good)
    z = rows.get("lit", {})
    check("3. Zlarior's row: LIVE, armed, running, feed fresh, 0 of 1 trades, $0 today, $1,145 of $2,000 left (43% used), no flag",
          z.get("state") == "LIVE, armed" and z.get("running") is True and z["feed"]["ok"] and z["trades"] == 0 and z["today"] == 0.0
          and z["room"] == 1145.0 and z["mll"] == 2000.0 and round(z["used"], 3) == 0.427 and z["flags"] == [] and z["label"] == "Zlarior 50K", z)
    check("3. ATLAS's row: 'ATLAS 25K' LIVE, armed, $822 of $1,000", rows["atlas"]["state"] == "LIVE, armed" and rows["atlas"]["room"] == 822.0
          and rows["atlas"]["label"] == "ATLAS 25K", rows["atlas"])
    check("3. the card says where the checklist is and the report line; the whole card is small (< 8 KB)",
          good["checklist"] == "gate/launch_day.json" and good["report"]["level"] == "ok" and len(json.dumps(good)) < 8000, len(json.dumps(good)))
    # ---- what stops every account: said once, on top, with the one action
    c = LC.build(live_of(now, running=False), [], {}, now)
    check("3. the bot stopped: one global flag (not one per bot), level bad, the headline, the GO_LIVE_EVAL.bat action",
          [g["code"] for g in c["global"]] == ["stopped"] and c["level"] == "bad" and c["headline"].startswith("The bot is stopped on the PC")
          and "GO_LIVE_EVAL.bat" in c["global"][0]["fix"] and all(not [f for f in r["flags"] if f["code"] == "stopped"] for r in c["bots"]), c)
    c = LC.build(live_of(now, feed={"stale": True, "entries_blocked": True, "block": "FEED STALE: 1m bar 7 min old", "age_1m_s": 420}), [], {}, now)
    check("3. FEED STALE: a global flag with the LE_BarFeed action; each bot's Feed fact says STALE",
          c["global"] and c["global"][0]["code"] == "feed" and "LE_BarFeed" in c["global"][0]["fix"] and all(r["feed"]["ok"] is False for r in c["bots"]), c["global"])
    c = LC.build(live_of(now, nt=False), [], {}, now)
    check("3. NinjaTrader not connected: a global flag", [g["code"] for g in c["global"]] == ["nt"], c["global"])
    c = LC.build(live_of(now, blocks=[{"text": "Kill switch used today: no orders until the next session", "kind": "kill", "fix": "Kill switch used today"}]), [], {}, now)
    check("3. the board's own global blocks (kill switch ...) come through with their fix", [g["code"] for g in c["global"]] == ["kill"]
          and c["global"][0]["fix"], c["global"])
    c = LC.build(live_of(now, running=False, blocks=[{"text": "The bot is stopped: no new entries", "kind": "stopped", "fix": "x"}]), [], {}, now)
    check("3. ... never twice (the board's 'stopped' block and ours)", [g["code"] for g in c["global"]] == ["stopped"], c["global"])
    # ---- per bot
    c = LC.build(live_of(now, account={"armed": False}, facts={"lit_armed": False, "b": {"armed": True}}), [], {}, now)
    z = c["bots"][0]
    check("3. Zlarior on its real account but not armed: 'real account, NOT armed', a bad flag with the arm-it-yourself action",
          z["state"] == "real account, NOT armed" and [f["code"] for f in z["flags"]] == ["armed"] and "GO_LIVE_EVAL.bat" in z["flags"][0]["fix"]
          and c["level"] == "bad", z)
    c = LC.build(live_of(now, atlas=atlas_card(badge="SIM")), [], {}, now)
    check("3. ATLAS on Sim: 'Sim', no flag; the headline says it", c["bots"][1]["state"] == "Sim" and not c["bots"][1]["flags"]
          and "ATLAS Sim" in c["headline"], (c["bots"][1], c["headline"]))
    c = LC.build(live_of(now, facts={"lit_armed": True, "b": {"armed": False}}), [], {}, now)
    check("3. ATLAS's 25K real but account B not armed: NOT armed (bad)", c["bots"][1]["state"] == "real account, NOT armed" and c["level"] == "bad", c["bots"][1])
    c = LC.build(live_of(now, atlas=atlas_card(configured=False, badge=None, status="not set up", room=None,
                                                blocks=[{"text": "ATLAS account (account B) is not set up on the PC", "kind": "account", "fix": "Start & Accounts page"}])), [], {}, now)
    a = c["bots"][1]
    check("3. ATLAS not set up: 'not set up', its block a note (warn, not an alarm); the headline names it",
          a["state"] == "not set up" and a["level"] == "warn" and a["flags"][0]["level"] == "warn" and c["level"] == "warn"
          and "ATLAS not set up" in c["headline"], (a, c["headline"]))
    c = LC.build(live_of(now, lit=lit_card(room=900.0)), [], {}, now)
    check("3. 55% of the drawdown used: a warn flag; 80%: bad", [f["level"] for f in c["bots"][0]["flags"]] == ["warn"]
          and [f["level"] for f in LC.build(live_of(now, lit=lit_card(room=400.0)), [], {}, now)["bots"][0]["flags"]] == ["bad"], c["bots"][0]["flags"])
    c = LC.build(live_of(now, lit=lit_card(today_pnl=-760.0)), [], {}, now)
    check("3. down $760 of the $1,000 daily loss limit: a bad 'dll' flag", [f["code"] for f in c["bots"][0]["flags"]] == ["dll"], c["bots"][0]["flags"])
    pos = {"entry_t": now - 60, "side": "LONG", "qty": 20, "entry": 25000.0, "stop": 24970.0, "target": 25100.0}
    c = LC.build(live_of(now, lit=lit_card(room=1100.0, position=pos)), [], {}, now)
    z = c["bots"][0]
    check("3. an open trade whose stop would cost more than the drawdown left (20 x 30 pts x $2 + costs = $1,238 > $1,100): bad 'risk'",
          z["position"]["risk_usd"] == 1238.0 and "risk" in [f["code"] for f in z["flags"]], z)
    c = LC.build(live_of(now, lit=lit_card(position={**pos, "qty": 2, "stop": None})), [], {}, now)
    check("3. an open trade with no stop in the report: bad 'nostop'", "nostop" in [f["code"] for f in c["bots"][0]["flags"]], c["bots"][0]["flags"])
    revs = [{"acct": "lit", "entry_t": now - 1200, "line": "Zlarior 50K LONG Mon 01:25 ET: filled 3 of 5 ...", "flags": [
        {"code": "size", "level": "bad", "text": "NinjaTrader filled 3 micros, the bot sent 5.", "fix": "Open NinjaTrader > Positions"}]},
            {"acct": "lit", "entry_t": now - 30 * 3600, "line": "old", "flags": [{"code": "slip_entry", "level": "warn", "text": "old one", "fix": ""}]}]
    c = LC.build(live_of(now), revs, {}, now)
    z = c["bots"][0]
    check("3. today's fill-check flag on Zlarior's row ('Fill check: ...', its action); yesterday's not; its line kept",
          [f["text"] for f in z["flags"]] == ["Fill check: NinjaTrader filled 3 micros, the bot sent 5."] and z["flags"][0]["fix"] == "Open NinjaTrader > Positions"
          and z["fills"][0].startswith("Zlarior 50K LONG") and c["level"] == "bad", z)
    c = LC.build(live_of(now, blitz=blitz_card()), [], {}, now)
    check("3. BLITZ on its own account (Sim): a third row; an 'off' BLITZ card: no row", [r["id"] for r in c["bots"]] == ["lit", "atlas", "blitz"]
          and [r["id"] for r in LC.build(live_of(now, blitz={"id": "blitz", "off": True}), [], {}, now)["bots"]] == ["lit", "atlas"], [r["id"] for r in c["bots"]])
    c = LC.build(None, [], {}, now)
    check("3. no live numbers from the bot: live false, level bad, says so", c["live"] is False and c["level"] == "bad" and "not available" in c["headline"], c)
    check("3. junk never raises", all(isinstance(LC.build(x, "y", 5, now), dict) for x in ({"kind": "le-live", "pc": 3, "board": {"lit": "x", "atlas": [1]}}, "x", 7)))
    check("3. a phone-report warning shows on top (warn), never as an alarm",
          LC.build(live_of(now), [], {"level": "warn", "text": "The phone report last ran 50 min ago.", "fix": "BOTS_BACK"}, now)["level"] == "warn")


def report():
    import shutil
    import tempfile
    from tools import launch_card as LC
    now = at(2026, 11, 16, 1, 45)
    d = tempfile.mkdtemp(prefix="lkr_", dir=os.environ.get("LE_TEST_TMP") or None)
    try:
        work = os.path.join(d, "work")
        os.makedirs(work)
        r = LC.report_state(work, None, now)
        check("3. report: the 15-minute report never ran on this PC -> warn 'has not run on this PC yet' + BOTS_BACK.bat", r["level"] == "warn"
              and "has not run on this PC yet" in r["text"] and "BOTS_BACK.bat" in r["fix"], r)

        def last(**kw):
            with open(os.path.join(work, "last.json"), "w", encoding="utf-8") as fh:
                json.dump({"t": now - 240, "ok": True, "errors": [], "sent": 1, "alerts_last": {"t": now - 7200, "title": "x"}, "alerts_on": True, **kw}, fh)
        last(t=now - 3000)
        r = LC.report_state(work, None, now)
        check("3. report: last run 50 min ago -> warn 'last ran 50 min ago'", r["level"] == "warn" and "last ran 50 min ago" in r["text"], r)
        last(alerts_on=False)
        r = LC.report_state(work, None, now)
        check("3. report: it runs but no alert topic is set -> 'Phone alerts are not set up on this PC.'", r["level"] == "warn"
              and r["text"] == "Phone alerts are not set up on this PC.", r)
        last(errors=["alert: ntfy.sh rate limit (too many messages today): next run tries again"], ok=False)
        r = LC.report_state(work, None, now)
        check("3. report: the last run could not send -> warn with ntfy's reason", r["level"] == "warn" and "rate limit" in r["text"], r)
        last()
        r = LC.report_state(work, None, now)
        check("3. report: fresh -> 'Phone alerts on: last check 4 min ago, last push 2 h ago.'", r["level"] == "ok"
              and r["text"] == "Phone alerts on: last check 4 min ago, last push 2 h ago.", r)
        with open(os.path.join(work, "last.json"), "w", encoding="utf-8") as fh:
            json.dump({"t": now - 240, "ok": True, "errors": []}, fh)
        r = LC.report_state(work, None, now)
        check("3. report: a last.json from before this update (no alerts_on): fine, 'Phone report: last check 4 min ago.'", r["level"] == "ok"
              and r["text"] == "Phone report: last check 4 min ago.", r)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    # through the real report: last.json says whether alerts go out, never which topic
    from tests.test_bots_back import Box, FakeHTTP
    from tests.test_live_publish import hb_payload
    b = Box()
    try:
        b.hb(hb_payload(now - 60, position=False))
        b.run(FakeHTTP(), now)
        l0 = json.load(open(os.path.join(b.work, "last.json"), encoding="utf-8"))
        cfg = b.topic()
        b.run(FakeHTTP(), now + 900)
        l1 = json.load(open(os.path.join(b.work, "last.json"), encoding="utf-8"))
        r = LC.report_state(b.work, None, now + 960)
        check("3. pc_report writes alerts_on (false without a topic, true with one) and never the topic; the card's report says 'Phone alerts on'",
              l0.get("alerts_on") is False and l1.get("alerts_on") is True and cfg["topic"] not in json.dumps(l1) and cfg["topic"] not in json.dumps(r)
              and r["text"].startswith("Phone alerts on: last check"), (l0.get("alerts_on"), l1.get("alerts_on"), r))
    finally:
        b.cleanup()
    body = open(os.path.join(ROOT, "tools", "launch_card.py"), encoding="utf-8").read().split('"""', 2)[-1]
    check("3. launch_card.py never reads the private ntfy settings (no ntfy.json, no load_cfg): the server only sees the report's last.json",
          "ntfy.json" not in body and "load_cfg" not in body)


def route():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from engine import live_site as LS
    from tools import launch_card as LC
    now = int(dt.datetime.now().timestamp())
    real = (LC.cached_reviews, LC.report_state)
    LC.cached_reviews = lambda now=None, root=None, ttl=None: []
    LC.report_state = lambda work=None, env=None, now=None: {"level": "ok", "text": "Phone alerts on: last check 4 min ago."}
    try:
        app = FastAPI()
        box = {"live": live_of(now)}
        LS.install(app, live=lambda: box["live"], kalshi_cfg={})
        LS._S["live"].ttl = 0
        cl = TestClient(app)
        r = cl.get("/api/site/launch.json")
        j = r.json()
        check("3. GET /api/site/launch.json: 200, kind le-launch, the two bots, no-store", r.status_code == 200 and j.get("kind") == "le-launch"
              and [b["id"] for b in j["bots"]] == ["lit", "atlas"] and r.headers.get("cache-control") == "no-store", (r.status_code, j))
        link = {"X-Forwarded-For": "100.101.102.103", "Tailscale-User-Login": "owner@example.com"}
        check("3. over the phone link: GET allowed, POST refused (403) before any route", cl.get("/api/site/launch.json", headers=link).status_code == 200
              and cl.post("/api/site/launch.json", headers=link).status_code == 403)
        box["live"] = None
        j = cl.get("/api/site/launch.json").json()
        check("3. the bot's live numbers not available: still 200 with live false and the plain sentence", j.get("live") is False and "not available" in j.get("headline", ""), j)
        LC.payload, real_payload = (lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))), LC.payload
        try:
            r = cl.get("/api/site/launch.json")
            check("3. a failure inside: 503 with a plain error, never a crash", r.status_code == 503 and r.json().get("ok") is False, r.text)
        finally:
            LC.payload = real_payload
    finally:
        LC.cached_reviews, LC.report_state = real
    src = open(os.path.join(ROOT, "engine", "live_site.py"), encoding="utf-8").read().split('"""', 2)[-1]
    check("3. live_site.py stays read only (no POST route, no file write, no live_model)", "router.post" not in src and "live_model" not in src
          and not re.search(r"open\([^)]*['\"][wa]b?['\"]", src))
    for rel in ("tools/launch_card.py",):
        body = open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8").read().split('"""', 2)[-1]
        check(f"3. {rel}: read only (no file write, no order line, no HTTP, no live_model, no arming)",
              not re.search(r"open\([^)]*['\"][wa]b?['\"]|PLACE;|place_line|CLOSEPOSITION|urllib|requests\.|live_model|LIVE_PHRASE|/api/live/", body)
              and "json.dump(" not in body, rel)


def ready():
    from tools import launch_card as LC
    from tools import pc_guard as G
    mon = at(2026, 11, 16, 1, 45)

    def snap(now, live, **kw):
        s = {"t": now, "hb": {"running": True}, "hb_age": 60, "server": True, "nt": True, "mode": "LIVE", "live": live, "cond": {}, "fills": []}
        s.update(kw)
        return s

    def rdy(msgs):
        return [x for x in msgs if x["key"].startswith(("guard:ready:", "guard:notready:"))]
    st, m = G.guard({}, snap(mon, live_of(mon)), roll_state={})
    rd = rdy(m)
    check("3. 01:45 ET Monday, all well: one silent push 'Ready for 02:00 ET: Zlarior LIVE armed, ATLAS LIVE armed', through the quiet hours",
          len(rd) == 1 and rd[0]["key"] == "guard:ready:2026-11-16" and rd[0]["title"] == "Ready for 02:00 ET: Zlarior LIVE armed, ATLAS LIVE armed"
          and rd[0]["priority"] == "low" and G.quiet(mon), rd)
    body = rd[0]["body"] if rd else ""
    check("3. its body: each account's state and drawdown left, the bot, NinjaTrader, the feed, 'Entries from 02:00 ET.'",
          "Zlarior 50K: LIVE, armed, drawdown left $1,145 of $2,000" in body and "ATLAS 25K: LIVE, armed, drawdown left $822 of $1,000" in body
          and "Bot running, NinjaTrader on, feed fresh" in body and body.endswith("Entries from 02:00 ET."), body)
    _s, m = G.guard(st, snap(mon + 600, live_of(mon + 600)), roll_state={})
    check("3. once a day", not rdy(m), m)
    for label, t in (("01:20 ET", at(2026, 11, 16, 1, 20)), ("02:05 ET", at(2026, 11, 16, 2, 5)), ("Saturday", at(2026, 11, 21, 1, 45)),
                     ("Christmas Day", at(2026, 12, 25, 1, 45))):
        _s, m = G.guard({}, snap(t, live_of(t)), roll_state={})
        check(f"3. no ready push at {label}", not rdy(m), (label, m))
    down = {"bot_down": "The bot server on the PC is not answering. Double-click GO_LIVE_EVAL.bat on the PC."}
    st, m = G.guard({}, snap(at(2026, 11, 16, 1, 36), live_of(mon), cond=down), roll_state={})
    rd = rdy(m)
    check("3. the bot server down at 01:36: 'NOT ready for 02:00 ET: The bot server on the PC is not answering', high, with the fix",
          rd and rd[0]["key"] == "guard:notready:2026-11-16" and rd[0]["title"].startswith("NOT ready for 02:00 ET: The bot server on the PC is not answering")
          and rd[0]["priority"] == "high" and "Fix: The bot server on the PC is not answering. Double-click GO_LIVE_EVAL.bat" in rd[0]["body"], rd)
    st, m = G.guard(st, snap(at(2026, 11, 16, 1, 51), live_of(mon)), roll_state={})
    check("3. ... fixed by 01:51: then the 'Ready for 02:00 ET' push", [x["title"] for x in rdy(m)] == ["Ready for 02:00 ET: Zlarior LIVE armed, ATLAS LIVE armed"], rdy(m))
    _s, m = G.guard(st, snap(at(2026, 11, 16, 1, 58), live_of(mon), cond=down), roll_state={})
    check("3. ... and no second 'NOT ready' that day (the bot-down alert itself still comes from the report)", not rdy(m), rdy(m))
    _s, m = G.guard({}, snap(mon, live_of(mon, running=False), hb={"running": False}), roll_state={})
    rd = rdy(m)
    check("3. the bot stopped at 01:45 (before the report's own 01:50 'stopped' alert): NOT ready, GO_LIVE_EVAL.bat",
          rd and rd[0]["priority"] == "high" and "The bot is stopped on the PC" in rd[0]["title"] and "GO_LIVE_EVAL.bat" in rd[0]["body"], rd)
    _s, m = G.guard({}, snap(mon, live_of(mon, account={"armed": False}, facts={"lit_armed": False, "b": {"armed": True}})), roll_state={})
    rd = rdy(m)
    check("3. Zlarior not armed: NOT ready, with the arm-it-yourself action",
          rd and rd[0]["title"].startswith("NOT ready") and "Arm it yourself at the PC" in rd[0]["body"], rd)
    _s, m = G.guard({}, snap(mon, live_of(mon), hb_age=3600), roll_state={})
    rd = rdy(m)
    check("3. the last report an hour old: NOT ready, 'The bot has not reported for 60 min'", rd and "The bot has not reported for 60 min" in rd[0]["title"], rd)
    _s, m = G.guard({}, snap(mon, live_of(mon, lit=lit_card(room=300.0))), roll_state={})
    rd = rdy(m)
    check("3. 85% of the drawdown used is not 'NOT ready' (it has its own push): still Ready", rd and rd[0]["title"].startswith("Ready"), rd)
    check("3. ready titles are ASCII and short", all(ascii_ok(x["title"]) and len(x["title"]) <= 118 for x in LC.ready_push(snap(mon, live_of(mon)), mon)))
    _s, m = G.guard({}, {"t": mon}, roll_state={})
    check("3. a guard call without the report's look at the PC (no hb_age) never says ready or not (tests/test_roll_now's bare calls)", not rdy(m), m)


def ready_report():
    """Through pc_report.run_once at 01:45 ET Monday (Box, the real board of the test heartbeat): the ready push goes out silent."""
    from tests.test_bots_back import Box, FakeHTTP
    from tests.test_live_publish import hb_payload
    from engine import roll_watch
    real_fact = roll_watch.fact
    roll_watch.fact = lambda *a, **k: {}
    b = Box()
    try:
        cfg = b.topic()
        t0 = at(2026, 11, 16, 1, 15)
        b.hb(hb_payload(t0 - 60, position=False))
        b.run(FakeHTTP(), t0)
        now = at(2026, 11, 16, 1, 45)
        b.hb(hb_payload(now - 60, position=False))
        h = FakeHTTP()
        b.run(h, now)
        rd = [c for c in h.posts(cfg["topic"]) if c["h"].get("Title", "").startswith(("Ready for", "NOT ready"))]
        check("3. reporter at 01:45 ET: 'Ready for 02:00 ET: Zlarior LIVE armed, ATLAS not set up', sent with ntfy priority low",
              len(rd) == 1 and rd[0]["h"]["Title"] == "Ready for 02:00 ET: Zlarior LIVE armed, ATLAS not set up" and rd[0]["h"].get("Priority") == "low",
              [c["h"] for c in h.posts(cfg["topic"])])
    finally:
        roll_watch.fact = real_fact
        b.cleanup()


# ============================================================================================== 4 the first-day checklist
def checklist():
    from tools import launch_day as LD
    check("4. docs/LAUNCH_DAY.md and gate/launch_day.json are in sync with tools/launch_day.py (--check)", LD.main(["--check"]) == 0)
    doc = open(LD.MD, encoding="utf-8").read()
    js = json.load(open(LD.JS, encoding="utf-8"))
    steps = re.search(r"## Your 3 steps\n(.*?)\n## ", doc, re.S)
    n = len(re.findall(r"^\d\. ", steps.group(1), re.M)) if steps else 0
    cmds = re.findall(r"`(python [^`]*|powershell [^`]*|pwsh [^`]*)`", steps.group(1)) if steps else []
    check("4. the page: the owner's steps on top (01:45 first), at most 3, no copy-paste command, no code block",
          steps is not None and doc.index("## Your 3 steps") < doc.index("## 01:45 ET") and 1 <= n <= 3 and not cmds and "```" not in doc and "01:45" in steps.group(1), (n, cmds))
    check("4. the page: what to look for at 01:45, what each push means, the fill check flags, each as a table (what / means / do)",
          all(h in doc for h in ("## 01:45 ET: what to look for", "## What each push means", "## Fill check flags")) and doc.count("|---|---|---|") == 3)
    for word, why in (("FEED STALE", "feed"), ("Bot down", "bot down"), ("NO STOP at NinjaTrader", "missing stop"), ("wrong size", "size"),
                      ("LE_BarFeed", "the feed fix"), ("GO_LIVE_EVAL.bat", "bring back / arm"), ("STOP_BOT.bat", "stop everything"), ("Flatten", "flatten by hand")):
        check(f"4. the page names {why} ({word})", word in doc)
    rows = [r for s in js["sections"] for r in s["rows"]]
    check("4. every row has a one-line action (no line break, never empty) and the card has the same 3 sections, 3 steps and the stop line as the page",
          all(len(r) == 3 and r[2] and "\n" not in r[2] for r in rows) and len(js["sections"]) == 3 and js["steps"] == LD.STEPS and js["stop"] in doc
          and all(s["title"] in doc for s in js["sections"]) and all(r[0] in doc for r in rows), js["sections"][0]["rows"][:2])
    check("4. the checklist never says Claude arms or trades: you arm at the PC, the phone only reads",
          "You arm them yourself" in doc and "nothing on the phone can trade" in doc and not re.search(r"Claude (arms|types the phrase|places)", doc))
    check("4. the card file is small (< 12 KB) and has no secret-looking field", len(json.dumps(js)) < 12000 and not re.search(r"token|secret|password|nq-[a-z]+-[a-z]+-[a-z]+-\d{4}", json.dumps(js)))


# ============================================================================================== 5 the page
def page_static():
    js = open(os.path.join(ROOT, "tools", "web_public", "gate", "launch.js"), encoding="utf-8").read()
    css = open(os.path.join(ROOT, "tools", "web_public", "gate", "launch.css"), encoding="utf-8").read()
    html = open(os.path.join(ROOT, "tools", "web_public", "gate", "index.html"), encoding="utf-8").read()
    code = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    code = "\n".join(ln.split("//")[0] if "://" not in ln else ln for ln in code.splitlines())
    es6 = [p for p in (r"=>", r"\blet\s", r"\bconst\s", r"`", r"\bclass\s+\w+\s*[{e]", r"\.\.\.\w") if re.search(p, code)]
    check("5. launch.js: ES5 classic script (no arrow, let, const, template string, class, spread)", not es6, es6)
    check("5. launch.js: no markup from data (textContent only), no POST / XHR / storage / cookies / web address",
          not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new Function|XMLHttpRequest|sendBeacon|method:\s*['\"]POST|"
                        r"localStorage|sessionStorage|indexedDB|document\.cookie|https?://", js) and "textContent" in js)
    check("5. launch.js: reads only /api/site/launch.json and gate/launch_day.json; draws only when the page path starts with /site/",
          "API = '/api/site/launch.json'" in js and "base + 'gate/launch_day.json'" in js and "ON_PC = /^\\/site\\//.test(" in js and "if (!ON_PC) return;" in js)
    check("5. gate/index.html loads launch.js only under /site/ (any other copy never downloads it), after gate.js",
          "if (!/^\\/site\\//.test(location.pathname || '')) return;" in html and html.index("'gate/gate.js?v=g4'") < html.index("gate/launch.js?v=l1"))
    check("5. launch.css: colours only through the AGORA tokens (no literal colour), tabular numbers, 44 px summaries",
          not re.search(r"#[0-9a-fA-F]{3,6}\b|rgb\(\s*\d", css) and "tabular-nums" in css and "min-height: 44px" in css)


def page_browser():
    """Chromium (iPhone size) on the real engine/live_site.py routes in-process (uvicorn), the real Gate from tools/web_public: the Launch
    card under Right now when the PC serves the site, not anywhere else. Fake bot numbers, the report and the fill check stubbed."""
    if FAST:
        print("[SKIP] 5. --fast: no browser")
        return
    try:
        import threading
        import time as _t
        import uvicorn
        from fastapi import FastAPI
        from playwright.sync_api import sync_playwright  # noqa: F401
        from tests import agora_kit as AK
        from engine import live_site as LS
        from tools import launch_card as LC
    except Exception as e:
        print(f"[SKIP] 5. no browser kit ({e.__class__.__name__}): the Chromium run was skipped")
        return
    now = int(_t.time())
    box = {"live": live_of(now), "revs": []}
    real = (LC.cached_reviews, LC.report_state)
    LC.cached_reviews = lambda now=None, root=None, ttl=None: box["revs"]
    LC.report_state = lambda work=None, env=None, now=None: {"level": "ok", "text": "Phone alerts on: last check 4 min ago."}
    old_dir = os.environ.get("LE_SITE_DIR")
    os.environ["LE_SITE_DIR"] = os.path.join(ROOT, "data", "no_such_site_for_tests")      # no built site: the real files of tools/web_public
    app = FastAPI()
    LS.install(app, live=lambda: box["live"], kalshi_cfg={})
    LS._S["live"].ttl = 0
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    for _ in range(100):
        if srv.started:
            break
        _t.sleep(0.1)
    origin = f"http://127.0.0.1:{srv.servers[0].sockets[0].getsockname()[1]}"
    CARD = ("() => { const c = document.querySelector('#launch'); if (!c) return null; const prev = c.previousElementSibling;"
            " return { after: prev && prev.id, level: c.dataset.level, badge: document.querySelector('#launchBadge').textContent, line: document.querySelector('#launchLine').textContent,"
            " bots: [...c.querySelectorAll('.lk-bot')].map((b) => ({ id: b.dataset.bot, name: b.querySelector('.lk-name').textContent, pill: b.querySelector('.lk-pill').textContent,"
            " facts: [...b.querySelectorAll('.lk-f')].map((f) => f.textContent), flags: [...b.querySelectorAll('.lk-flag')].map((f) => f.textContent) })),"
            " global: [...document.querySelectorAll('#launchGlobal .lk-flag')].map((f) => f.textContent), report: document.querySelector('#launchReport').textContent,"
            " foot: document.querySelector('#launchFoot').textContent }; }")
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(origin + "/site/gate/")
            p.wait_for_function("window.GATE && window.GATE.ready() && window.GATE_LAUNCH && window.GATE_LAUNCH.ready()", timeout=60000, polling=200)
            p.wait_for_timeout(300)
            r = p.evaluate(CARD)
            check("5. served by the PC (/site/gate/): the Launch card right under Right now, 'Ready', the headline",
                  r and r["after"] == "now" and r["badge"] == "Ready" and r["level"] == "ok"
                  and r["line"] == "Zlarior and ATLAS armed; feed fresh (1-minute bar 20 s old); no flags.", r)
            z = (r or {}).get("bots", [{}])[0]
            check("5. Zlarior's row: name, 'LIVE, armed', Feed Fresh, Trades today 0 of 1, Today $0, Drawdown left $1,145 of $2,000 (43% used)",
                  z.get("name") == "Zlarior 50K" and z.get("pill") == "LIVE, armed" and z.get("facts", [""])[0].startswith("FeedFresh")
                  and "Trades today0 of 1" in z.get("facts", []) and "Today$0" in z.get("facts", [])
                  and "Drawdown left$1,145of $2,000 (43% used)" in z.get("facts", []), z)
            check("5. ATLAS's row and the phone-report line; 'Live from your PC'", r and r["bots"][1]["name"] == "ATLAS 25K" and r["report"] == "Phone alerts on: last check 4 min ago."
                  and r["foot"].startswith("Live from your PC"), r)
            check("5. phone rules: taps >= 44 px, no sideways scroll, no console error, nothing off the origin", not AK.taps(p) and AK.no_sideways(p) and not errs and not off,
                  (AK.taps(p)[:4], errs[:3], off[:3]))
            ck = p.evaluate("() => { const c = document.querySelector('#launchDay'); if (!c) return null; return { after: c.previousElementSibling && c.previousElementSibling.id,"
                            " title: c.querySelector('h2').textContent, steps: c.querySelectorAll('.lk-steps li').length,"
                            " secs: [...c.querySelectorAll('details')].map((x) => [x.querySelector('summary').textContent, x.open, x.querySelectorAll('.lk-item').length]),"
                            " stop: (c.querySelector('.lk-stop') || {}).textContent }; }")
            check("5. the first-day checklist card right under the Launch card: its 3 steps, 3 sections (01:45 open first), every row, the stop line",
                  ck and ck["after"] == "launch" and ck["title"] == "Launch day: Monday Nov 16" and ck["steps"] == 3
                  and [s[0] for s in ck["secs"]] == ["01:45 ET: what to look for", "What each push means", "Fill check flags (after a real trade)"]
                  and [s[1] for s in ck["secs"]] == [True, False, False] and [s[2] for s in ck["secs"]] == [6, 13, 6] and ck["stop"].startswith("Stop everything"), ck)
            p.click("#launchDay details[data-sec='fills'] summary")
            check("5. a tap opens a section", p.evaluate("() => document.querySelector(\"#launchDay details[data-sec='fills']\").open"))
            AK.shot(p, "launch-ready")
            # ---- not ready: the bot stopped + a fill-check flag on Zlarior
            box["live"] = live_of(now, running=False)
            box["revs"] = [{"acct": "lit", "entry_t": now - 600, "line": "Zlarior 50K SHORT: filled 3 of 5.", "flags": [
                {"code": "size", "level": "bad", "text": "NinjaTrader filled 3 micros, the bot sent 5.", "fix": "Open NinjaTrader > Positions."}]}]
            p.reload()
            p.wait_for_function("window.GATE_LAUNCH && window.GATE_LAUNCH.ready() && document.querySelector('#launch').dataset.level === 'bad'", timeout=60000, polling=200)
            r = p.evaluate(CARD)
            check("5. not ready: 'Fix now', the bot stopped on top with 'Do: ... GO_LIVE_EVAL.bat'", r["badge"] == "Fix now" and r["global"]
                  and r["global"][0].startswith("The bot is stopped on the PC") and "Do: On the PC double-click GO_LIVE_EVAL.bat" in r["global"][0], r)
            check("5. ... and the fill check's flag on Zlarior's row with its action", any("Fill check: NinjaTrader filled 3 micros, the bot sent 5." in f
                                                                                         and "Do: Open NinjaTrader > Positions." in f for f in r["bots"][0]["flags"]), r["bots"][0])
            check("5. no sideways scroll with the long flag texts, no console error", AK.no_sideways(p) and not errs, errs[:3])
            AK.shot(p, "launch-fix")
            ctx.close()
            # ---- a bot server started before this code: the route is missing (404)
            ctx, p, errs, seen, off = AK.page(br, origin)
            ctx.route("**/api/site/launch.json*", lambda rt: rt.fulfill(status=404, content_type="application/json", body='{"detail":"Not Found"}'))
            p.goto(origin + "/site/gate/")
            p.wait_for_function("window.GATE_LAUNCH && window.GATE_LAUNCH.ready()", timeout=60000, polling=200)
            r = p.evaluate(CARD)
            check("5. an older bot server (no launch route): 'Not available' and the one restart sentence, no error", r["badge"] == "Not available"
                  and "runs an older version" in r["line"] and "STOP_BOT.bat, then GO_LIVE_EVAL.bat" in r["line"] and not errs, (r, errs[:3]))
            ctx.close()
        # ---- any other copy of the site (not under /site/): no card, launch.js never loaded
        srv2, origin2 = AK.serve({"/home.json": json.dumps({"live": {"pc": {"t": now - 60, "running": True}}, "board": {"t": now - 60}})})
        try:
            with AK.browser() as br:
                ctx, p, errs, seen, off = AK.page(br, origin2)
                p.goto(origin2 + "/gate/")
                p.wait_for_function("window.GATE && window.GATE.ready()", timeout=60000, polling=200)
                p.wait_for_timeout(500)
                r = p.evaluate("() => ({ card: !!document.querySelector('#launch'), js: typeof window.GATE_LAUNCH, asked: performance.getEntriesByType('resource').some((e) => /launch/.test(e.name)) })")
                check("5. the public copy (not served by the PC): no Launch card, launch.js not even downloaded", r == {"card": False, "js": "undefined", "asked": False}, r)
                ctx.close()
        finally:
            srv2.shutdown()
    finally:
        srv.should_exit = True
        LC.cached_reviews, LC.report_state = real
        if old_dir is None:
            os.environ.pop("LE_SITE_DIR", None)
        else:
            os.environ["LE_SITE_DIR"] = old_dir


def main() -> int:
    alerts()
    alerts_retry()
    fills()
    fills_report()
    launch()
    report()
    route()
    ready()
    ready_report()
    checklist()
    page_static()
    page_browser()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


def test_launch_kit():                     # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
