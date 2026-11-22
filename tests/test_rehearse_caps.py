"""tools/rehearse_day.py's size check uses the room share the live code really sizes with (day-monday 2026-11-22: after the
owner's room-40% YES the rehearsal still checked ATLAS's funded 25K against 60%, so a 60% size would have passed unnoticed).

    python -X utf8 -m tests.test_rehearse_caps
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    from engine import account_b as AB, second
    from tools import rehearse_day as RD
    blk = {"account": "SimFundedX", "plan": "builder25k", "eval_start": "2026-10-26", "stage": "funded", "funded_start": "2026-11-18",
           "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]}
    live = float(AB.funded_cfg(AB.normalize(blk, second.load_cfg()))["funded"]["pct"])
    chk = RD.PLAN_CAPS["ATLAS funded 25K (B)"][0]
    res = []
    res.append(abs(chk - live) < 1e-9)
    print(f"[{'PASS' if res[-1] else 'FAIL'}] rehearsal checks ATLAS funded 25K at the live share ({chk} vs live {live})")
    old = dict(AB.FUNDED_ON)
    try:
        AB.FUNDED_ON.update(funded_room_pct=None)
        res.append(RD.atlas_funded_share() == 0.6)
        print(f"[{'PASS' if res[-1] else 'FAIL'}] switch off -> the preset's 0.6")
    finally:
        AB.FUNDED_ON.clear()
        AB.FUNDED_ON.update(old)
    print(f"rehearse caps: {sum(res)}/{len(res)} {'ALL PASS' if all(res) else 'FAILED'}")
    return 0 if all(res) else 1


if __name__ == "__main__":
    raise SystemExit(main())
