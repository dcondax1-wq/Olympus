"""day-blitzready 2026-11-27: the BLITZ PAPER lane (engine/blitz_paper.py) - paper only, one runner, kill respected, paper = backtest.
  a. no broker / adapter / live-loop import, no order or live-switch word, and no way to name an account
  b. tick: outside the session / off / kill do nothing new; a good run writes state, the trade log (each trade ONCE) and the report
  c. paper = backtest: sessions of data/NQ_1m.csv through the live path (1 poll a minute, cold start) equal blitz.backtest trade for trade
  d. engine/ops_checks.blitz_paper_kick: weekdays 09:25-16:05 ET, detached BELOW_NORMAL, never twice, off, kill, restart flag
  e. the PC feed: p4 BLITZ = paper from a fresh report (stale / error / absent = the old words)
  f. tools/blitz_ladder: the gate counts (shelve, collect, pass) and the card carries 2026 H1 / H2 / 2021-25
    python -X utf8 -m tests.test_blitz_paper
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def et(day, hm):
    h, m = hm.split(":")
    return int(dt.datetime.fromisoformat(f"{day}T{int(h):02d}:{int(m):02d}:00").replace(tzinfo=ET).timestamp())


def main() -> int:
    import pandas as pd
    from engine import blitz as BZ, blitz_paper as BP, ops_checks as OC, pc_checklist as PCC
    src = open(os.path.join(ROOT, "engine", "blitz_paper.py"), encoding="utf-8").read()
    # a ------------------------------------------------------------------------------------------------
    imps = set(re.findall(r"^\s*(?:from\s+(\.?[\w.]*)\s+import|import\s+([\w.]+))", src, re.M))
    mods = {a or b for a, b in imps}
    bad = {m for m in mods if any(w in m for w in ("ninjatrader", "adapter", "live", "account", "second", "tradovate", "firms", "multi_account"))} - {"oflive"}
    check("a1 no broker / adapter / live-loop import", not bad, bad)
    check("a2 no order / live-switch / phrase word in the code", not re.search(r"I ACCEPT|--blitz|place_order|submit|OIF|\.route\(|arm_c", src), "")
    # c (first: one cold replay) -------------------------------------------------------------------------
    r = BP.replay(3, active=True)
    check("c1 last 3 sessions with a BLITZ trade: live path == backtest, trade for trade", r["match"] and r["n_backtest"] > 0, (r["n_backtest"], r["n_live"], r["only_backtest"][:2], r["only_live"][:2]))
    check("c2 the trade log holds every live trade once (exit rows)", len(r["logged"]) == r["n_live"], (len(r["logged"]), r["n_live"]))
    r0 = BP.replay(3)
    check("c3 the very last 3 sessions: same (even when none traded)", r0["match"], r0["only_backtest"][:2])
    # b ------------------------------------------------------------------------------------------------
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))[["time", "open", "high", "low", "close"]]
    day = r["sessions"][-1]
    td = tempfile.mkdtemp(prefix="bzp_")
    os.makedirs(os.path.join(td, "data"))
    now = et(day, "16:05")
    sub = df[df["time"] <= now - 60]
    out = BP.tick(et(day, "08:00"), td, df1=sub)
    check("b1 outside 09:25-16:10 ET: nothing", not out["ok"] and not os.path.exists(os.path.join(td, "data", "blitz_paper.json")), out)
    out = BP.tick(now, td, df1=sub)
    check("b2 a run in session: ok, state + report written", out["ok"] and os.path.exists(os.path.join(td, "data", "blitz_paper", "state.json"))
          and BP.fresh(BP.compact(td), now), out)
    rep = BP.compact(td)
    check("b3 the report says paper + never_routed", rep["paper"] is True and rep["never_routed"] is True and rep["state"] == "paper", rep)
    n1 = len(BP.read_trades(td))
    BP.tick(now + 30, td, df1=sub)
    check("b4 a second run never repeats a logged trade", len(BP.read_trades(td)) == n1, (n1, len(BP.read_trades(td))))
    check("b5 the report is today's, stale / other day is not fresh", not BP.fresh(rep, now + 3600) and not BP.fresh({**rep, "error": "x"}, now))
    open(os.path.join(td, "data", "live_state.json"), "w").write(json.dumps({"kill": True}))
    out = BP.tick(now + 60, td, df1=sub)
    check("b6 kill switch: frozen, no new paper entry, report says kill", out["why"] == "kill" and BP.compact(td)["state"] == "kill", out)
    os.remove(os.path.join(td, "data", "live_state.json"))
    open(os.path.join(td, "data", "blitz_paper_off"), "w").write("1")
    check("b7 off file: nothing", BP.tick(now + 90, td, df1=sub)["why"] == "off")
    # d ------------------------------------------------------------------------------------------------
    td2 = tempfile.mkdtemp(prefix="bzk_")
    os.makedirs(os.path.join(td2, "data"))
    calls = []

    class P:
        def __init__(self, *a, **k):
            calls.append((a, k))
    mon = et("2026-11-30", "10:00")
    check("d1 weekday in session: started, detached, never an order", OC.blitz_paper_kick(mon, True, td2, P) == "started" and len(calls) == 1
          and calls[0][0][0][-3:] == ["-m", "engine.blitz_paper", "loop"], calls)
    if os.name == "nt":
        check("d1b BELOW_NORMAL flag on Windows", calls[0][1]["creationflags"] & 0x4000)
    check("d2 never twice: a start < 3 min ago", OC.blitz_paper_kick(mon + 60, True, td2, P) == "starting" and len(calls) == 1)
    json.dump({"t": mon + 70}, open(os.path.join(td2, "data", "blitz_paper_run.json"), "w"))
    check("d3 never twice: a live heartbeat", OC.blitz_paper_kick(mon + 100, True, td2, P) == "running" and len(calls) == 1)
    check("d4 weekend / before 09:25 / after 16:05: not due", OC.blitz_paper_kick(et("2026-11-28", "11:00"), True, td2, P) is None
          and OC.blitz_paper_kick(et("2026-11-30", "09:00"), True, td2, P) is None and OC.blitz_paper_kick(et("2026-11-30", "16:06"), True, td2, P) is None)
    os.remove(os.path.join(td2, "data", "blitz_paper_run.json"))
    os.remove(os.path.join(td2, "data", "blitz_paper_start.json"))
    json.dump({"kill": True}, open(os.path.join(td2, "data", "live_state.json"), "w"))
    check("d5 kill: not started", OC.blitz_paper_kick(mon + 400, True, td2, P) == "kill" and len(calls) == 1)
    os.remove(os.path.join(td2, "data", "live_state.json"))
    open(os.path.join(td2, "data", "blitz_paper_off"), "w").write("1")
    check("d6 off file: not started", OC.blitz_paper_kick(mon + 500, True, td2, P) == "off" and len(calls) == 1)
    os.remove(os.path.join(td2, "data", "blitz_paper_off"))
    json.dump({"t": mon, "stopped": True}, open(os.path.join(td2, "data", "blitz_paper_run.json"), "w"))
    check("d7 a stopped heartbeat does not block a new run", OC.blitz_paper_kick(mon + 500, True, td2, P) == "started")
    # loop: exits at 16:10 / stop flag, heartbeat
    td3 = tempfile.mkdtemp(prefix="bzl_")
    os.makedirs(os.path.join(td3, "data"))
    BP.loop(td3, clock=lambda: et("2026-11-30", "16:11"), sleep=lambda s: None)
    check("d8 the loop exits itself after 16:10 ET", (json.load(open(os.path.join(td3, "data", "blitz_paper_run.json"))) or {}).get("stopped") is True)
    # e ------------------------------------------------------------------------------------------------
    pl = lambda bp: next(p for p in PCC.pillars({}, {}, {}, True, bp) if p[0] == "BLITZ")
    check("e1 fresh paper report: p4 BLITZ = paper", pl({"paper": True, "fresh": True, "today_n": 2})[1] == "paper", pl({"paper": True, "fresh": True}))
    check("e2 stale / error / absent: the old 'off' words", all(pl(b)[1] == "off" for b in (None, {"paper": True, "fresh": False}, {"paper": True, "fresh": True, "error": "x"})))
    # f ------------------------------------------------------------------------------------------------
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import blitz_ladder as L
    row = lambda i, u, rr: {"entry_t": i, "r_usd150": u, "r": rr, "risk_pts": 40.0, "ev": "exit", "day": "2026-12-01"}
    good = [row(i, 60 if i % 3 else -40, 0.4 if i % 3 else -0.5) for i in range(40)]
    par = {"checked": 40, "match": 40, "pending": 0}
    s = L.score(good, par)
    check("f1 a good forward run passes the gate", s["passed"] and "ask" in s["status"], s)
    check("f2 parity miss or pending = not passed", not L.score(good, {"checked": 40, "match": 39, "pending": 0})["passed"] and not L.score(good, {"checked": 40, "match": 40, "pending": 1})["passed"])
    bad_rows = [row(i, -50 if i % 2 else 20, -0.4 if i % 2 else 0.2) for i in range(16)]
    check("f3 a bad start shelves BLITZ (no ask)", L.score(bad_rows, par)["status"] == "shelved", L.score(bad_rows, par))
    check("f4 too few trades = collecting", L.score(good[:10], par)["status"].startswith("collecting"))
    c = L.card(write=False)
    check("f5 the card has H1 / H2 / 2021-25 with costs", all(c["spans"][k].get("pf") for k in ("H1", "H2", "R")) and c["spans"]["H1"]["per_week"] > 5, c["spans"]["H1"])
    check("f6 card says paper only + the gate", c["paper_only"] and c["gate"]["params"]["n"] == 40)
    print(f"\n{sum(RES)}/{len(RES)}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
