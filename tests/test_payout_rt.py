"""Payout autopilot red team (2026-11-23). Offline: fakes + temp files; never a payout request.

  a. a SECOND funded ATLAS (new eval -> new funded account, same slot "atlas") gets its own "do not take payout #5" alert
  b. record(): the #4 / #5 words count THIS funded account's payouts (its own record), not every row the slot ever had
  c. payout #4's alert asks the owner to check MFFU shows exactly 3 paid (an unrecorded payout would make it the 5th)
    python -X utf8 -m tests.test_payout_rt
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import payout_autopilot as PA  # noqa: E402
from tests import test_payout_autopilot as T  # noqa: E402  (its fixtures: b25, GOOD)

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{str(info)[:300]}]"))


AFTER = dt.datetime(2026, 11, 24, 16, 20, tzinfo=ET).timestamp()


def main() -> int:
    p3 = {"2026-10-01": 1000, "2026-10-10": 1000, "2026-10-20": 1000}
    pays4 = dict(p3, **{"2026-10-28": 1000})
    t1 = T.b25(T.GOOD, pays4, prior=4000)
    t2 = dict(t1, start="2027-01-04")                 # the next funded ATLAS, also at 4 payouts later on
    sent = {}
    a1 = [a["key"] for a in PA.alerts([PA.builder(t1, "atlas")], AFTER, sent)]
    for k in a1:
        sent[k] = 1
    a2 = [a["key"] for a in PA.alerts([PA.builder(t2, "atlas")], AFTER, sent)]
    check("a. the 2nd funded ATLAS gets its own 'do not take payout #5' alert (key per funded account)",
          any(k.startswith("payout5:stop:atlas:2026-11-02") for k in a1) and any(k.startswith("payout5:stop:atlas:2027-01-04") for k in a2),
          (a1, a2))
    with tempfile.TemporaryDirectory() as d:
        lp = os.path.join(d, "ledger.json")
        json.dump({"rows": [{"key": "atlas", "day": f"2026-11-{10 + i}", "gross": 1000.0, "to_you": 800.0, "kind": "builder"}
                            for i in range(4)]}, open(lp, "w"))           # the FIRST funded ATLAS's 4 payouts
        rec = {"atlas": lambda spec: {"ok": True}, "count": lambda key: 1}   # the new funded ATLAS: this is its 1st
        r = PA.record("atlas", 1000, "2027-01-20", ledger_path=lp, recorders=rec)
        check("b1. the new account's 1st payout: no '#5 / live' warning (old account's rows do not count)", r["ok"] and not r.get("warn"), r)
        rec["count"] = lambda key: 4
        r = PA.record("atlas", 1000, "2027-02-20", ledger_path=lp, recorders=rec)
        check("b2. its 4th: 'the last, close it'", r["ok"] and "payout #4" in (r.get("warn") or ""), r)
        rec["count"] = lambda key: 5
        r = PA.record("atlas", 1000, "2027-02-27", ledger_path=lp, recorders=rec)
        check("b3. its 5th: the 'tell Claude now' warning", "payout #5" in (r.get("warn") or ""), r)
    v3 = PA.builder(T.b25(T.GOOD, p3, prior=3000), "atlas")
    al = PA.alerts([v3], AFTER, {})
    body = " ".join(a["body"] for a in al if a["key"].startswith("payout:"))
    check("c. payout #4's alert: check MFFU shows exactly 3 paid, else do NOT request", v3["ready"] and "exactly 3 paid" in body, (v3, al))
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
