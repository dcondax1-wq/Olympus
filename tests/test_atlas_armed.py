"""night 2026-11-27: ATLAS's heartbeat block carries its armed flag, so readiness stops saying "ATLAS 25K is not armed" (NOT READY)
while ATLAS is armed and trading live (the owner's Trading Home at 00:15 ET).

    python -X utf8 -m tests.test_atlas_armed
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_b as AB, second  # noqa: E402
from engine import preflight  # noqa: E402
from tests.test_account_b_funded import acct, funded_block, ts  # noqa: E402

R = []


def check(name, ok, info=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{(': ' + str(info)[:300]) if info and not ok else ''}")
    R.append(bool(ok))


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_atlas_armed_")
    sc = second.load_cfg()
    now = ts("2026-11-27", 0)
    armed = AB.normalize(funded_block(armed=True), sc)
    B, _ = acct(armed, now, tmp, tag="a1")
    info = B.info(now)
    check("1. account_b.info() carries 'armed' (the owner-typed flag the adapter's live gate uses)", info.get("armed") is True, info.get("armed"))
    hb = {"second": {"route": {"account_b": {**info, "kind": "LIVE", "enabled": True}}}}
    rows = [r for r in preflight.arms(hb) if r[0] == "ATLAS 25K"]
    check("2. preflight.arms: an armed LIVE ATLAS is ok -> readiness has no 'ATLAS 25K is not armed' blocker",
          rows and rows[0][1] is True and rows[0][2] == "LIVE, armed", rows)
    off = AB.normalize(funded_block(), sc)
    B2, _ = acct(off, now, tmp, tag="a2")
    i2 = B2.info(now)
    rows = [r for r in preflight.arms({"second": {"route": {"account_b": {**i2, "kind": "LIVE", "enabled": True}}}}) if r[0] == "ATLAS 25K"]
    check("3. a really unarmed ATLAS still reads 'LIVE, NOT armed' (the real NOT READY stays)", i2.get("armed") is False
          and rows and rows[0][1] is False and rows[0][2] == "LIVE, NOT armed", rows)
    from engine import brain_glance as BG
    check("4. the phone glance (brain_glance._ab_armed) still says armed with the new key", BG._ab_armed({**info, "kind": "LIVE",
                                                                                                         "enabled": True}) is True)
    print(f"\n{sum(R)}/{len(R)} passed")
    return 0 if all(R) else 1


if __name__ == "__main__":
    sys.exit(main())
