"""Live vs backtest gap, Zlarior 50K eval (night-litmore 2026-11-19). RESEARCH + PROPOSAL ONLY: engine/ is not edited.

data_pull 2026-11-19 / the PC's trade review said the backtest twin traded Oct 26, 27, 28 and Nov 3 and the bot did not
("PC bot off (no record of the bot that day)"). What the code and the files we can see say (write-up
research/writeups/lit-more-money-2026-11-19.md, section "Why live missed trades"):

  day    twin (today's bars, LIT size)   what really happened                         evidence
  10-26  08:37 short BE  +$0.6           NOT traded: the model entered during a gap     engine/live.py comment at the un-routed exit
                                         (bot down / feed burst), never routed          ("a missed 08:37 BE trade booked +$0.10 on the 50K at 23:08 ET 2026-10-26")
  10-27  06:12 short STOP -$137          NOT on the account: every MFFU order went to    engine/ninjatrader.py _nt_said_no_account / _no_trace,
                                         an account Name without the "R" (refused);     engine/live.py _void_refused_days ("Zlarior's 06:12 SELL 7 ...
                                         the bot booked -$965 that was voided (fixed)    -$965.30 on the 50K eval, never filled")
  10-28  03:43 short STOP -$348          TRADED live: 5 MNQ, -$437                      tools/web_public/trading/trades.json live.lit.2026-10-28_0343_short
  11-03  15:39 long EOD  +$28            no record (bot re-set up 20:51-21:06 ET)       heartbeat remote.handsoff / autopilot events (Tue Nov 3)
  11-10  03:33 long STOP -$231           NOT traded (balance unchanged)                 balance $49,313.54 (Nov 6) -> $49,192.78 (Nov 17) = only Nov 16's -$129;
  11-11  03:56 short CUT -$42            NOT traded (balance unchanged)                 PC silent Nov 7-17 (report task never installed, no auto-update)
  11-16  06:16 long STOP -$129           TRADED live: 1 MNQ, -$129.40                   data/pc_days/2026-11-16 trades (fill 27,799.50)

So the four "missed" verdicts are three different things: one real miss (Oct 26, $0), one broker refusal that is fixed
(Oct 27, it SAVED ~$965), one real live trade the audit could not see (Oct 28), and one unknown (Nov 3, +$28 at the LIT
size). Two more real misses came later (Nov 10-11, both losers). Net: missing them saved money, by luck.

The audit bug (engine/fill_audit._pc_on / _miss_reason): a day BEFORE the PC's own first record (its exec_audit store and
trade rows start Nov 3-6) has no uptime samples and no ledger rows, so _pc_on returns None and the row is called
"missed: PC bot off (no record of the bot that day)" - even for Oct 28, which was traded. PROPOSED fix (not applied):
classify() below - such a day is status "unknown" ("before the PC's records start <day>: check the broker statement"),
left out of the missed count and missed $. A test (tests/test_live_gap_proposal.py) pins both today's behaviour and the
proposal on the Oct 28 case.

    python -X utf8 tools/live_gap_proposal.py      # prints the table above from the data in the repo
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

GAP = [
    {"day": "2026-10-26", "et": "08:37", "side": "SHORT", "twin_exit": "BE", "twin_lit_usd": 0.6, "live": "missed",
     "why": "the model entered during a gap (bot down / feed burst): never routed", "live_usd": 0.0},
    {"day": "2026-10-27", "et": "06:12", "side": "SHORT", "twin_exit": "STOP", "twin_lit_usd": -137.4, "live": "refused",
     "why": "MFFU account Name without the R: NinjaTrader refused the order (fixed in code; the booked -$965 was voided)",
     "live_usd": 0.0, "eval_size_usd": -965.3},
    {"day": "2026-10-28", "et": "03:43", "side": "SHORT", "twin_exit": "STOP", "twin_lit_usd": -347.6, "live": "traded",
     "why": "traded live, 5 MNQ (the audit could not see it: its records start later)", "live_usd": -437.0},
    {"day": "2026-11-03", "et": "15:39", "side": "LONG", "twin_exit": "EOD", "twin_lit_usd": 27.6, "live": "unknown",
     "why": "no PC record; the bot was re-set up and re-armed by hand 20:51-21:06 ET that evening", "live_usd": None},
    {"day": "2026-11-10", "et": "03:33", "side": "LONG", "twin_exit": "STOP", "twin_lit_usd": -230.8, "live": "missed",
     "why": "not on the account (balance unchanged Nov 6 -> Nov 17 except Nov 16); PC silent Nov 7-17", "live_usd": 0.0},
    {"day": "2026-11-11", "et": "03:56", "side": "SHORT", "twin_exit": "CUT_T15", "twin_lit_usd": -41.9, "live": "missed",
     "why": "same as Nov 10", "live_usd": 0.0},
    {"day": "2026-11-16", "et": "06:16", "side": "LONG", "twin_exit": "STOP", "twin_lit_usd": -128.9, "live": "traded",
     "why": "traded live, 1 MNQ (fill 27,799.50 vs model 27,798.75: 3 ticks worse)", "live_usd": -129.4},
]


def classify(day: str, pc_on, first_record_day: str | None) -> dict:
    """PROPOSED replacement for engine/fill_audit's missed-row verdict when the bot left no record that day.
    pc_on: engine/fill_audit._pc_on's answer (True / False / None). first_record_day: the first trading day the PC left any
    record (ledger row, uptime sample, held-back entry, trade row). Returns {"status", "reason", "count_as_missed"}."""
    if pc_on is None and first_record_day and day < first_record_day:
        return {"status": "unknown", "count_as_missed": False,
                "reason": f"before the PC's own records start ({first_record_day}): not known whether the bot traded - "
                          "check the broker statement"}
    if pc_on is None:
        return {"status": "missed", "count_as_missed": True, "reason": "PC bot off (no record of the bot that day)"}
    if pc_on is False:
        return {"status": "missed", "count_as_missed": True, "reason": "PC bot off"}
    return {"status": "missed", "count_as_missed": True,
            "reason": "bot running but did not route it (feed difference or restart; see the bot log)"}


def summary() -> dict:
    tw = sum(r["twin_lit_usd"] for r in GAP)
    traded = [r for r in GAP if r["live"] == "traded"]
    not_on = [r for r in GAP if r["live"] in ("missed", "refused")]
    return {"twin_trades": len(GAP), "traded_live": len(traded), "not_on_account": len(not_on),
            "unknown": sum(1 for r in GAP if r["live"] == "unknown"),
            "twin_lit_usd": round(tw, 1), "missed_twin_lit_usd": round(sum(r["twin_lit_usd"] for r in not_on), 1),
            "live_usd": round(sum(r["live_usd"] or 0.0 for r in GAP), 1)}


if __name__ == "__main__":
    for r in GAP:
        print(f"{r['day']} {r['et']} {r['side']:5s} twin {r['twin_exit']:7s} {r['twin_lit_usd']:+8.1f}  live {r['live']:8s} {r['why']}")
    print(json.dumps(summary()))
