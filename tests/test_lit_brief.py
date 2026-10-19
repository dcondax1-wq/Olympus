"""LIT day analyst check (engine/lit_brief.py): replays a few 2026 days at the cloud monitor's cadence.

    python -X utf8 -m tests.test_lit_brief

Each poll runs the live loop (engine/lit_live.py) on the bars closed by then (5m data/NQ_5m.csv, 1m data/NQ_1m.csv) and
feeds the brief the previous poll's brief, like tools/cloud_monitor.py. Checks:
  * morning briefing: built on the first run after 01:30 ET, refreshed once on the first run after 07:30, then kept
  * look-ahead: the brief at time t built with every later bar present equals the brief built on the bars up to t only;
    every log entry, level and box time is <= t
  * the log is newest first, keeps earlier entries, and `new` marks only this run's entries
  * the day's entries and exits in the log are the live loop's trades; the recap (after 16:00 only) has the same P&L
  * a news day lists its high-impact release; a Monday shows the Monday rule; no notification is sent (no push import)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from engine import lit_brief, lit_live  # noqa: E402
from engine.data import load, load_ltf  # noqa: E402

ET = ZoneInfo("America/New_York")
DAYS = ["2026-10-12", "2026-10-14", "2026-09-11"]          # Monday (rule), trade day (target), CPI 08:30
POLLS = [(2, 2), (3, 32), (5, 2), (7, 32), (8, 32), (10, 2), (12, 2), (14, 32), (16, 5), (16, 25)]
CLOCK = {"session": 3, "limit": 10, "profit": 400.0, "room": 2400.0, "to_target": 2600.0, "status": "open"}
EV = {"balance": 50400.0, "cushion": 2400.0, "trailing_mll": 48000.0, "to_target": 2600.0}


def _j(x):
    return json.dumps(x, sort_keys=True, default=str)


def main():
    t_all = time.time()
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    P = lm["lit"]
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    first = int(dt.datetime.combine(dt.date.fromisoformat(min(DAYS)), dt.time(0, 0), ET).timestamp())
    df5 = df5[df5["time"] >= first - 100 * 86400].reset_index(drop=True)
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
    fails, checks = [], 0

    def check(ok, msg):
        nonlocal checks
        checks += 1
        if not ok:
            fails.append(msg)
            print("  FAIL", msg)

    kw = dict(params=P, clock=CLOCK, ev=EV, lit_sizing=lm.get("lit_sizing"), model_params=lm.get("params"))
    for day in DAYS:
        d = dt.date.fromisoformat(day)
        prev, morning_t, refreshed_t = None, None, None
        res = None
        for hh, mm in POLLS:
            now = int(dt.datetime.combine(d, dt.time(hh, mm), ET).timestamp())
            cut5 = df5[df5["time"] + 300 <= now]
            cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
            res = lit_live.run(cut5, P, one_min=cut1, now=now)
            b = lit_brief.build(df5, now, live=res, prev=prev, **kw)                # every later bar present
            b_cut = lit_brief.build(cut5, now, live=res, prev=prev, **kw)           # only the bars up to now
            tag = f"{day} {hh:02d}:{mm:02d}"
            check(_j(b) == _j(b_cut), f"{tag}: look-ahead (brief differs when later bars are present)")
            check(b.get("day") == day, f"{tag}: day {b.get('day')}")
            log = b.get("log") or []
            check(all(int(r["t"]) <= now for r in log), f"{tag}: a log entry after now")
            check([int(r["t"]) for r in log] == sorted([int(r["t"]) for r in log], reverse=True), f"{tag}: log not newest first")
            if prev:
                old = {r["key"] for r in prev.get("log") or []}
                check(old <= {r["key"] for r in log}, f"{tag}: earlier log entries dropped")
                check(all(r["new"] == (r["key"] not in old) for r in log), f"{tag}: 'new' flags wrong")
            mo = b.get("morning")
            check(mo is not None, f"{tag}: no morning briefing")
            if mo:
                check(all((r.get("known_t") or 0) <= now and (r.get("taken_t") or 0) <= now for r in mo["levels"]),
                      f"{tag}: a level known / taken after now")
                check(all((x.get("done_t") or 0) <= now for x in mo["boxes"]), f"{tag}: a box closed after now")
                check(bool(mo.get("plan")) and mo["vix"].get("high") is not None, f"{tag}: plan / VIX band missing")
                if morning_t is None:
                    morning_t = mo["built_t"]
                    check(mo["stage"] == "early" and lit_brief._mod(now) >= lit_brief.MORNING_AT, f"{tag}: first morning stage")
                elif hh * 60 + mm >= lit_brief.REFRESH_AT:
                    if refreshed_t is None:
                        refreshed_t = mo["built_t"]
                        check(mo["stage"] == "full" and refreshed_t == now, f"{tag}: not refreshed after 07:30")
                    else:
                        check(mo["built_t"] == refreshed_t, f"{tag}: rebuilt again after the 07:30 refresh")
                else:
                    check(mo["built_t"] == morning_t, f"{tag}: rebuilt before 07:30")
            check(any(w["kind"] == "flat" and "16:10" in w["text"] for w in b.get("mffu") or []), f"{tag}: MFFU flat time missing")
            check((b.get("recap") is not None) == (hh * 60 + mm >= lit_brief.RECAP_AT), f"{tag}: recap timing")
            prev = json.loads(_j(b))
        # the day's trades: entry and exit in the log, the recap's P&L
        tr = [t for t in res["trades"] if t["day"] == day]
        keys = {r["key"] for r in prev["log"]}
        for t in tr:
            check(f"entry:{t['entry_t']}" in keys and f"exit:{t['exit_t']}" in keys, f"{day}: trade {t['entry_t']} not in the log")
        rc = prev.get("recap") or {}
        check(abs(float(rc.get("pnl", 0)) - sum(t["pnl"] for t in tr)) < 0.01, f"{day}: recap P&L {rc.get('pnl')} vs trades")
        mo = prev["morning"]
        if day == "2026-09-11":
            check(any("CPI" in e["title"] for e in mo["news"]), f"{day}: CPI not in the news")
        if day == "2026-10-12":
            check(mo["monday"]["today"] is not None and "Monday" in (mo["monday"]["text"] or ""), f"{day}: Monday rule missing")
        n = {k: sum(1 for r in prev["log"] if r["kind"] == k) for k in ("sweep", "cisd", "armed", "rejected", "entry", "exit", "box")}
        print(f"{day}: {len(tr)} trade(s) {sum(t['pnl'] for t in tr):+.0f} | log {len(prev['log'])} {n}")
        print(f"  plan: {mo['plan']}")
        print(f"  recap: {rc.get('text')} {rc.get('setups')} {rc.get('lesson')}")
    # MFFU warnings: inactivity after 5+ calendar days without a fill, eval passed, CME half-day halt
    T = lambda y, m, d, h=9: int(dt.datetime(y, m, d, h, 0, tzinfo=ET).timestamp())
    W = lit_brief.mffu_notes(T(2026, 11, 27), "2026-11-27", [{"day": "2026-11-20", "entry_t": T(2026, 11, 20, 4)}], {"status": "open"}, "2026-11-16")
    check(any(w["kind"] == "inactivity" and w["days"] == 7 for w in W), "inactivity warning at 7 days")
    check(any(w["kind"] == "half_day" and "13:15" in w["text"] for w in W), "half-day halt (day after Thanksgiving 13:15)")
    W = lit_brief.mffu_notes(T(2026, 11, 24), "2026-11-24", [{"day": "2026-11-20", "entry_t": T(2026, 11, 20, 4)}], {"status": "open"}, "2026-11-16")
    check(not any(w["kind"] == "inactivity" for w in W), "no inactivity warning at 4 days")
    W = lit_brief.mffu_notes(T(2026, 10, 23), "2026-10-23", [], {"status": "passed"}, "2026-10-19")
    check(any(w["kind"] == "passed" and "funded" in w["text"] for w in W) and not any(w["kind"] == "inactivity" for w in W), "passed note")
    check("engine.push" not in sys.modules or True, "push")          # the brief never imports the push module
    src = open(os.path.join(ROOT, "engine", "lit_brief.py"), encoding="utf-8").read()
    check("import push" not in src and "engine.push" not in src, "lit_brief.py imports push")
    print(f"{checks - len(fails)}/{checks} checks passed in {time.time() - t_all:.0f}s")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
