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
         "room": 1145.0, "mll": 2000.0, "today_pnl": 0.0, "dll": 1000.0, "trades_today": 0, "eval_start": "2026-11-02", "position": None,
         "configured": True}
    c.update(kw)
    return c


def atlas_card(**kw):
    c = {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "badge": "LIVE", "configured": True, "status": "open", "balance": 24822.0,
         "floor": 24000.0, "room": 822.0, "mll": 1000.0, "today_pnl": 0.0, "dll": 600.0, "trades_today": 0, "position": None}
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


def main() -> int:
    alerts()
    alerts_retry()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


def test_launch_kit():                     # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
