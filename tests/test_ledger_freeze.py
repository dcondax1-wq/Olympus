"""The cloud monitor's paper ledger keeps the decision made on the bars available at the time (LIT report ch.27, "a later
data correction changes a historical pivot: retain the decision made on the original available data").

  python -X utf8 -m tests.test_ledger_freeze
"""
from __future__ import annotations

import sys

from tools import cloud_monitor as cm


def _trade(exit_reason="STOP", pnl_r=-1.0, pnl=-800.0, exit_t=1_792_000_600):
    return {"entry_t": 1_792_000_000, "exit_t": exit_t, "dir": 1, "pnl_r": pnl_r, "pnl": pnl, "qty": 20, "exit_reason": exit_reason,
            "trigger": "LIT", "risk_pts": 20.0}


def main() -> int:
    ok = True
    led = {}
    cm.update_ledger(led, {"model": "lit", "trades": [_trade()]}, 1_791_000_000, None, None, None, None)
    row = dict(led[1_792_000_000])
    # the same trade re-simulated on revised bars: a target instead of the stop
    cm.update_ledger(led, {"model": "lit", "trades": [_trade("TARGET", 3.2, 2560.0, 1_792_003_000)]}, 1_791_000_000, None, None, None, None)
    after = led[1_792_000_000]
    c1 = all(after[k] == row[k] for k in ("exit", "R", "usd", "exit_ts", "qty"))
    c2 = after.get("revised_replay") == {"exit": "TARGET", "R": 3.2, "exit_ts": 1_792_003_000}
    print(f"[{'PASS' if c1 else 'FAIL'}] a finished paper trade is not rewritten by a re-run on revised bars")
    print(f"[{'PASS' if c2 else 'FAIL'}] the revised replay is noted next to it ({after.get('revised_replay')})")
    cm.update_ledger(led, {"model": "lit", "trades": [_trade()]}, 1_791_000_000, None, None, None, None)
    c3 = "revised_replay" not in led[1_792_000_000]
    print(f"[{'PASS' if c3 else 'FAIL'}] the note goes away when the replay agrees again")
    ok = c1 and c2 and c3
    print("ledger freeze:", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
