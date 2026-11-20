"""Live vs backtest gap PROPOSAL (tools/live_gap_proposal.py, night-litmore 2026-11-19). No engine file is changed.

Pins (1) today's engine/fill_audit verdict on a day before the PC's own records start: the Oct 28 2026 short WAS traded
live (5 MNQ, -$437, tools/web_public/trading/trades.json) but the audit, which has no uptime sample or ledger row for that
day, calls it "missed: PC bot off (no record of the bot that day)"; (2) the proposed classify(): such a day is "unknown"
and is not counted as a missed trade; a day the PC was on, or off on its own record, keeps today's verdict.

    python -X utf8 -m tests.test_live_gap_proposal
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import fill_audit as fa  # noqa: E402
from tools import live_gap_proposal as G  # noqa: E402

RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""))


def main() -> bool:
    oct28 = 1793173380                                    # 2026-10-28 03:43 ET, the live short
    notes = {"uptime": [{"t": 1794002400, "running": True}]}   # the PC's first uptime sample: Nov 6 (after the trade)
    live_days = {"2026-11-16"}
    bt = {"entry_t": oct28, "dir": -1, "entry": 29945.0, "stop": 29987.5, "target": 29665.75, "exit_price": 29987.75,
          "exit_reason": "STOP", "qty": 4, "pnl": -347.6}
    row = fa.compare(bt, None, notes, live_days)
    check("today: the audit calls the traded Oct 28 short missed", row["status"] == "missed", row)
    check("today: ... with 'no record of the bot that day'", "no record" in row["reason"], row["reason"])
    check("today: pc_on is None (no record), not False", row["pc_on"] is None, row["pc_on"])

    first = "2026-11-03"                                  # the PC's own records start Nov 3-6
    v = G.classify("2026-10-28", row["pc_on"], first)
    check("proposal: a day before the first record is 'unknown'", v["status"] == "unknown", v)
    check("proposal: not counted as missed", v["count_as_missed"] is False, v)
    check("proposal: says to check the broker statement", "broker statement" in v["reason"], v)
    v2 = G.classify("2026-11-10", None, first)
    check("proposal: a day AFTER the first record with no record stays missed", v2["status"] == "missed" and v2["count_as_missed"], v2)
    v3 = G.classify("2026-11-10", False, first)
    check("proposal: PC off on its own record stays 'PC bot off'", v3["reason"] == "PC bot off", v3)
    v4 = G.classify("2026-11-10", True, first)
    check("proposal: PC on keeps 'did not route it'", "did not route" in v4["reason"], v4)

    # the gap table: 7 backtest trades since the eval start, 2 traded live, net of the missed ones negative (saved $)
    s = G.summary()
    check("gap table: 7 twin trades, 2 traded live", s["twin_trades"] == 7 and s["traded_live"] == 2, s)
    check("gap table: the trades not on the account were net losers", s["missed_twin_lit_usd"] < 0, s)
    tr = json.load(open(os.path.join(ROOT, "tools", "web_public", "trading", "trades.json"), encoding="utf-8"))
    live28 = [t for t in tr["trades"] if t.get("src") == "live" and t.get("t") == oct28]
    check("published trades: the Oct 28 short is a LIVE trade (-$437)", live28 and abs(live28[0]["usd"] + 437.0) < 0.01, live28)
    ok = all(RES)
    print(f"{sum(RES)}/{len(RES)} passed")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
