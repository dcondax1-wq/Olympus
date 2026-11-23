"""ninjatrader/LE_TickRec.cs backfill (day-ofprogram 2026-11-23) + the zero-click chain on the Python side.

1. C# 5 compile against tests/nt_stub/NtStubs.cs (mono mcs); read-only scan (no Account / order / OIF code).
2. Behaviour driver (tests/nt_stub/NtStubsTick.cs fake history server + TickRecDriver.cs): off = no request; trading hours =
   wait; one request at a time, newest ET day first, front contract, Tick 1; whole-day bf_ files via .tmp; skips .done /
   .none / Saturday; stops at the end of the server's history and remembers it; 17:15 ET nightly pass; 10 GB disk guard;
   a hung request is dropped and retried; disable stops it.
3. engine.tickrec: bf_ files replace a partial live day, become .done, unchanged live files are not re-read; autopilot runs
   the study once at 60 NQ days (with a fake study), not during 02:00-16:05 ET, writes one phone line; a second look only
   when the backfill says done; tools/pc_report pushes the line once and starts the autopilot only outside trading hours.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
STUB = os.path.join(ROOT, "tests", "nt_stub")
CS = os.path.join(ROOT, "ninjatrader", "LE_TickRec.cs")
P = F = 0


def ok(c, what):
    global P, F
    print(("PASS " if c else "FAIL ") + what, flush=True)
    if c:
        P += 1
    else:
        F += 1


def cs_part():
    src = open(CS, encoding="utf-8").read()
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("//"))
    ok(not re.search(r"\bAccount\b|\bOrders?\b|Submit|CreateOrder|PlaceOrder|Cancel|Flatten|incoming|ChangeOrder|\bAtm|\bATI\b|\bOIF\b|PLACE;|\$\"|\?\.|=>", code),
       "LE_TickRec.cs: no Account / order / OIF code, C# 5 only")
    if not (shutil.which("mcs") and shutil.which("mono")):
        print("SKIP: mono (mcs) not installed (apt-get install -y mono-mcs mono-runtime)")
        return
    tmp = tempfile.mkdtemp(prefix="le_tickrec_cs_")
    try:
        r = subprocess.run(["mcs", "-langversion:5", "-target:library", "-out:" + os.path.join(tmp, "a.dll"),
                            os.path.join(STUB, "NtStubs.cs"), CS], capture_output=True, text=True, timeout=180)
        ok(r.returncode == 0 and "error" not in (r.stdout + r.stderr).lower(), "compiles as C# 5 against NtStubs.cs " + (r.stdout + r.stderr)[-400:])
        exe = os.path.join(tmp, "d.exe")
        r = subprocess.run(["mcs", "-langversion:5", "-out:" + exe, os.path.join(STUB, "NtStubsTick.cs"),
                            os.path.join(STUB, "TickRecDriver.cs"), CS], capture_output=True, text=True, timeout=180)
        ok(r.returncode == 0, "driver compiles " + (r.stdout + r.stderr)[-400:])
        if r.returncode == 0:
            r = subprocess.run(["mono", exe], capture_output=True, text=True, timeout=180,
                               env={**os.environ, "LE_NTSTUB_DIR": os.path.join(tmp, "nt")})
            fails = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
            ok(r.returncode == 0 and "ALL PASS" in r.stdout, "backfill behaviour driver: %d checks, %s" % (r.stdout.count("PASS "), fails or "all pass"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def py_part():
    from engine import tickrec as T
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    tmp = tempfile.mkdtemp(prefix="le_tickrec_py_")
    keep = (T.TICK_DIR, T.CFG_PATH, T.AUTO_PATH, T.NOTE_PATH)
    try:
        nd = os.path.join(tmp, "NinjaTrader 8"); rd = os.path.join(nd, "le_ticks"); os.makedirs(rd)
        T.TICK_DIR = os.path.join(tmp, "ticks"); T.CFG_PATH = os.path.join(tmp, "data", "tickrec.json")
        T.AUTO_PATH = os.path.join(tmp, "data", "orderflow_auto.json"); T.NOTE_PATH = os.path.join(tmp, "data", "orderflow_note.json")
        os.environ["OLYMPUS_NT_DIR"] = nd
        os.environ.pop(T.ENV, None)
        # live partial day (2 ticks, stamps the server will not repeat) then the server's whole day
        with open(os.path.join(rd, "NQ_2026-11-20.csv"), "w") as f:
            f.write("t_ms,price,size,bid,ask\n1795185000001,21000.25,1,21000,21000.25\n1795185000101,21000,1,21000,21000.25\n")
        r1 = T.ingest()
        ok(r1["live_files"] == 1 and len(T.read_day("2026-11-20")) == 2, "live file ingested")
        r1b = T.ingest()
        ok(r1b["live_files"] == 0, "unchanged live file not re-read")
        with open(os.path.join(rd, "bf_NQ_2026-11-20.csv"), "w") as f:
            f.write("t_ms,price,size,bid,ask\n" + "".join("%d,21000.25,1,21000,21000.25\n" % (1795185000000 + 1000 * i) for i in range(5)))
        r2 = T.ingest()
        ok(r2["backfill_files"] == 1 and len(T.read_day("2026-11-20")) == 5, "backfill day REPLACES the partial live day (5 rows, not 7)")
        ok(os.path.exists(os.path.join(rd, "bf_NQ_2026-11-20.done")) and not os.path.exists(os.path.join(rd, "bf_NQ_2026-11-20.csv")),
           "backfill csv -> .done marker (disk stays small, LE_TickRec skips the day)")
        os.utime(os.path.join(rd, "NQ_2026-11-20.csv"), None)
        open(os.path.join(rd, "NQ_2026-11-20.csv"), "a").write("1795185000201,21000,1,21000,21000.25\n")
        T.ingest()
        ok(len(T.read_day("2026-11-20")) == 5, "past live day ignored once the server's day is in")
        # NinjaTrader's filled-in quotes (Bid = Last, Ask = Bid + 1 tick) must not turn every trade into a sell
        px = [21000 + 0.25 * (i % 7) for i in range(200)]
        fx = T.frame(list(range(200)), "NQ", px, [1] * 200, px, [x + 0.25 for x in px])
        ok(fx.bid.eq(0).all() and (fx.side == -1).mean() < 0.5, "filled-in quotes dropped -> tick rule (not 100% sells)")
        rb = [x - 0.25 if i % 2 else x for i, x in enumerate(px)]
        rx = T.frame(list(range(200)), "NQ", px, [1] * 200, rb, [b + 0.25 for b in rb])
        ok(rx.bid.gt(0).all(), "real quotes (about half at the bid) are kept")
        # autopilot
        calls = []

        def fake_study():
            calls.append(1)
            return {"PRE-REGISTERED (PREREG_ticks.md)": {
                "OF1 sweep absorption (skip not-absorbed)": {"2026 H1": {"gain$": 1200}, "2026 H2": {"gain$": -300}, "verdict": "REJECTED"},
                "OF2 block prints (skip blocks against)": {"2026 H1": {"gain$": -50}, "2026 H2": {"gain$": -10}, "verdict": "REJECTED"},
                "OF3A LVN rejection, tick profile + delta with trade": {"2026 H1": {"net$": 400}, "2026 H2": {"net$": -100}, "verdict": "REJECTED"}}}
        night = dt.datetime(2026, 11, 24, 20, 0, tzinfo=ET)
        ok(T.autopilot(night, fake_study)["why"].startswith("tick recorder is off"), "autopilot: recorder off = nothing")
        T.set_enabled(True, ["NQ"])
        ok("trading hours" in T.autopilot(dt.datetime(2026, 11, 24, 10, 0, tzinfo=ET), fake_study)["why"], "autopilot: never 02:00-16:05 ET weekdays")
        r = T.autopilot(night, fake_study)
        ok(not r["ran"] and "1 of 60" in r["why"] and not calls, "under 60 NQ days: waits (%s)" % r.get("why"))
        import pandas as pd
        base = pd.Timestamp("2026-08-03 14:00", tz="UTC")
        for k in range(61):
            t = base + pd.Timedelta(days=k)
            T.write_days(T.frame([t.value, t.value + 10**9], "NQ", [21000.0, 21000.25], [1, 2], [20999.75, 21000], [21000, 21000.25]))
        r = T.autopilot(night, fake_study)
        ok(r["ran"] and r["look"] == "first look" and len(calls) == 1, "60+ NQ days: study runs once (%s)" % r.get("nq_days"))
        note = json.load(open(T.NOTE_PATH))
        ok(note["key"].startswith("research:orderflow:") and "OF1 absorption REJECTED (+1200/-300$)" in note["body"] and "LIT stays" in note["body"],
           "one phone line: " + note["body"])
        r = T.autopilot(night, fake_study)
        ok(not r["ran"] and len(calls) == 1, "no second run without the backfill done")
        with open(os.path.join(rd, "le_tickrec_status.txt"), "w") as f:
            f.write("2026-11-24T01:00:00Z,on=1,instruments=NQ 12-26,rows=0,backfill=done,backfill_days=90,oldest=2025-11-25,bf_errors=0,low_disk=0\n")
        for k in range(61, 85):
            t = base + pd.Timedelta(days=k)
            T.write_days(T.frame([t.value], "NQ", [21000.0], [1], [20999.75], [21000]))
        r = T.autopilot(night, fake_study)
        ok(r["ran"] and "final" in r["look"] and len(calls) == 2, "backfill done + 20 more days: the final look (2 looks max)")
        for k in range(85, 120):
            t = base + pd.Timedelta(days=k)
            T.write_days(T.frame([t.value], "NQ", [21000.0], [1], [20999.75], [21000]))
        ok(not T.autopilot(night, fake_study)["ran"] and len(calls) == 2, "never a third look")
        # pc_report: pushes the note once; kick only outside trading hours and only when enabled
        from tools import pc_report as R
        snap = {"t": 1795500000, "research": [note]}
        st, msgs = R.events({"seen": {}, "cond": {}, "seeded": True}, {**snap, "fills": [], "watch": [], "risk": []})
        mine = [m for m in msgs if m["key"].startswith("research:")]
        ok(len(mine) == 1 and mine[0]["body"] == note["body"], "pc_report pushes the line")
        st2, msgs2 = R.events(st, {**snap, "fills": [], "watch": [], "risk": []})
        ok(not [m for m in msgs2 if m["key"].startswith("research:")], "... once")
        from engine import notify
        ok(notify.kind_of(note["key"]) == "daily_summary", "push type = daily_summary (on in the owner's settings)")
        root2 = os.path.join(tmp, "olympus"); os.makedirs(os.path.join(root2, "data"))
        seen = []
        tue10 = dt.datetime(2026, 11, 24, 10, 0, tzinfo=ET).timestamp(); tue20 = night.timestamp()
        ok(not R.tick_autopilot_kick(root2, tue20, popen=lambda *a, **k: seen.append(a)), "kick: recorder off -> no start")
        json.dump({"enabled": True}, open(os.path.join(root2, "data", "tickrec.json"), "w"))
        ok(not R.tick_autopilot_kick(root2, tue10, popen=lambda *a, **k: seen.append(a)) and not seen, "kick: never at 10:00 ET Tuesday")
        ok(R.tick_autopilot_kick(root2, tue20, popen=lambda *a, **k: seen.append(a)) and seen and seen[0][0][-1] == "autopilot",
           "kick: 20:00 ET starts `python -m engine.tickrec autopilot` as its own process")
        rp = open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read()
        ok(not re.search(r"^\s*(from engine import tickrec|import engine\.tickrec|from engine\.tickrec)", rp, re.M),
           "pc_report never imports the tick code (subprocess only)")
    finally:
        T.TICK_DIR, T.CFG_PATH, T.AUTO_PATH, T.NOTE_PATH = keep
        os.environ.pop("OLYMPUS_NT_DIR", None)
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    cs_part()
    py_part()
    print("test_tickrec_cs: %d passed, %d failed" % (P, F))
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
