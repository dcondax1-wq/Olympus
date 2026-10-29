"""Autopilot score (2026-10-29, engine/autopilot.py, docs/AUTOPILOT.md): manual steps this week, published with the
heartbeat's "remote" block next to the hands-off score.

    python -X utf8 -m tests.test_autopilot      (temp files only)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import autopilot as AP  # noqa: E402
from engine import handsoff as HO  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def ts(*a):
    return int(dt.datetime(*a, tzinfo=ET).timestamp())


def main():
    tmp = tempfile.mkdtemp(prefix="le_autopilot_")
    try:
        tp, hp = os.path.join(tmp, "autopilot.jsonl"), os.path.join(tmp, "handsoff.jsonl")
        now = ts(2026, 11, 4, 12, 0)                                   # Wednesday
        w0 = AP.week(now, tp, hp)
        check("an empty week: 0 manual steps, score 100, 'hands-free'", w0["manual"] == 0 and w0["score"] == 100
              and w0["verdict"] == "hands-free" and w0["week"] == "2026-11-02", w0)
        AP.note_tap("/api/next/start/go", now=ts(2026, 11, 2, 7, 0), path=tp)
        AP.note_tap("/api/next/start/arm", now=ts(2026, 11, 2, 7, 1), path=tp)
        AP.note_tap("/api/next/start/go", now=ts(2026, 11, 2, 7, 10), path=tp)          # the page's own retry: same step
        AP.note_tap("/api/next/start/status", now=ts(2026, 11, 2, 7, 2), path=tp)       # a read: not a step
        AP.note_tap("/api/next/start/go", now=ts(2026, 10, 30, 7, 0), path=tp)          # last week
        HO.record("stop", "pc", "dashboard Stop", now=ts(2026, 11, 3, 10, 0), path=hp)
        HO.record("restart", "pc", "server start", now=ts(2026, 11, 1, 20, 0), path=hp)  # Sunday evening: 0 points, not a step
        w = AP.week(now, tp, hp)
        check("this week (Mon 11-02 .. Sun 11-08 ET): Start trading (+ its retry 10 min later, one step) + the live phrase + a "
              "dashboard Stop = 3 manual steps, score 70; last week's tap, a read and an out-of-hours restart are not counted",
              w["manual"] == 3 and w["score"] == 70 and [x["what"] for x in w["items"]]
              == ["Start trading tapped", "Live phrase typed (arm)", "Bot stopped by hand"], w)
        c = AP.compact(tmp, now)
        check("compact (the heartbeat block): score, manual steps, the last ones, the catalogue size",
              c["score"] == 70 and c["manual"] == 3 and len(c["last"]) == 3 and c["steps"] == len(AP.STEPS) and c["auto_steps"] >= 7, c)
        from engine import remote_ctl
        done = os.path.join(tmp, "remote_done.json")
        hb = remote_ctl.hb_field(done, now=now)
        check("the heartbeat's remote block carries autopilot next to handsoff", "autopilot" in hb and "handsoff" in hb
              and hb["autopilot"].get("manual") == 3, hb.get("autopilot"))
        # the Start page: a write from the PC is a manual step; the job's own /resume and a phone request are not
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from engine import go as G, start_api as S
        keep = (G.CFG, G.set_names, G.resume_now)
        G.CFG = os.path.join(tmp, "start_bot.json")
        try:
            G.set_names = lambda lit, atlas: {"ok": True, "say": "saved"}
            G.resume_now = lambda *a, **k: {"ok": True}
            S._bot = lambda: SimpleNamespace(running=False, cfg={})
            app = FastAPI()
            app.include_router(S.router)
            local = TestClient(app, base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50001))
            phone = TestClient(app, base_url="http://192.168.1.20:8766", client=("192.168.1.50", 50003))
            local.post("/api/next/start/names", json={"lit": "A", "atlas": "B"})
            local.post("/api/next/start/resume")
            phone.post("/api/next/start/names", json={"lit": "A", "atlas": "B"})
            rows = [json.loads(x) for x in open(os.path.join(tmp, "autopilot.jsonl"))]
            check("Start page: the PC's 'names' write is one tap in the temp log (next to the temp start_bot.json); the job's "
                  "/resume and the phone's refused request add nothing", [r["what"] for r in rows if r["t"] > now - 86400 * 400][-1:]
                  == ["Account Names set"] and sum(1 for r in rows if r["what"] == "Account Names set") == 1, rows[-3:])
        finally:
            G.CFG, G.set_names, G.resume_now = keep
        check("the catalogue: every step has an id, a plain line, a state (auto / manual / planned) and how",
              all(len(s) == 4 and s[2] in ("auto", "manual", "planned") for s in AP.STEPS))
        check("no real data/autopilot.jsonl written by the tests", not os.path.exists(os.path.join(ROOT, "data", "autopilot.jsonl"))
              or os.path.getmtime(os.path.join(ROOT, "data", "autopilot.jsonl")) < now - 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"autopilot: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
