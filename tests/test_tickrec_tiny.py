"""engine.tickrec.tiny(): the order-flow pillar's line for the PC's status post (day-pillars 2026-11-24).
    python -X utf8 -m tests.test_tickrec_tiny
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import tickrec as T  # noqa: E402

RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


def main():
    keep = (T.nq_days, T.is_enabled, T.recorder_status)
    try:
        T.nq_days, T.is_enabled, T.recorder_status = (lambda: []), (lambda: False), (lambda nd=None: {})
        check("never set up (off, no days) = None: nothing is sent", T.tiny(1.0) is None)
        T.nq_days = lambda: ["2026-10-01", "2026-10-02", "2026-11-23"]
        T.is_enabled = lambda: True
        T.recorder_status = lambda nd=None: {"backfill": "running", "oldest": "2026-09-14"}
        t = T.tiny(1795000000)
        check("days, the 60-day target, backfill, oldest, newest, time", t == {"on": True, "d": 3, "of": 60, "bf": "running", "o": "2026-09-14", "l": "2026-11-23", "t": 1795000000}, t)
        check("small (< 120 bytes as JSON)", len(json.dumps(t, separators=(",", ":"))) < 120, len(json.dumps(t)))
        T.recorder_status = lambda nd=None: {}
        t = T.tiny(5)
        check("no recorder status file: oldest = the first day on disk, no backfill key", t.get("o") == "2026-10-01" and "bf" not in t, t)
        T.recorder_status = lambda nd=None: {"backfill": "done", "oldest": "2026-01-05"}
        with tempfile.TemporaryDirectory() as td:
            f = os.path.join(td, "data", "tickrec_tiny.json")
            ok = T.write_tiny(f, 7)
            got = json.load(open(f)) if os.path.exists(f) else None
            check("write_tiny: plain JSON file for pc_report (no import needed), replaced whole", ok and got and got["d"] == 3 and got["bf"] == "done" and not os.path.exists(f + ".tmp"), got)
        keepn = T.NOTE_PATH
        with tempfile.TemporaryDirectory() as td:
            T.NOTE_PATH = os.path.join(td, "data", "orderflow_note.json")
            T.write_tiny(None, 9)
            check("the default file sits next to the order-flow note (tests that move the note never write into the repo)", os.path.exists(os.path.join(td, "data", "tickrec_tiny.json")))
        T.NOTE_PATH = keepn
        check("the autopilot writes it after each ingest", "write_tiny()" in open(os.path.join(ROOT, "engine", "tickrec.py"), encoding="utf-8").read().split("def autopilot", 1)[1].split("def ", 1)[0])
        def boom():
            raise OSError("disk")
        T.nq_days = boom
        check("never raises (a broken disk = None)", T.tiny(5) is None)
    finally:
        T.nq_days, T.is_enabled, T.recorder_status = keep
    print(f"\n{sum(RES)}/{len(RES)} passed")
    sys.exit(0 if all(RES) else 1)


if __name__ == "__main__":
    main()
