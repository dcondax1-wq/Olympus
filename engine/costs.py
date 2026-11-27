"""One place for trading costs in research, eval and money estimates (big-exitreal 2026-11-26).

Source: research/writeups/exitreal-2026-11-26.md (pre-registered study) + research/writeups/execpol-2026-11-26.md (fills).
Read by the money / plan pipeline (tools/account4_sim, tools/money/stack_one_account, research/plans/rank, tools/forecast).

NOT read by the live loop: engine/lit.py, lit_live.py, live.py, second.py, account_*.py, sizing.py and every module the
running bot imports keep their own constants on purpose (a change there is a strategy / sizing change: live-vs-backtest
identity tests and the update gate). Changing a number here changes research and money pages only; re-run the pages listed in
research/writeups/exitreal-2026-11-26.md after a change.
"""
from __future__ import annotations

TICK = 0.25                 # NQ / MNQ tick (points)
PV_MNQ = 2.0                # $ per point per micro
COMM_RT = 1.90              # $ per micro round turn (MFFU list price; one broker fill so far implies $1.82: keep 1.90 until 10)
ENTRY_SLIP_TICKS = {"LIT": 1, "ATLAS": 12, "OFA": 18}   # market entries vs the model's price: LIT 3 / 0 (n=2), ATLAS 9 / 11 / 15 (n=3);
#   OFA = order-flow lane A (absorbed level fade) market at today's 2.75 s delay: MODELLED (ATLAS share x first-minute run),
#   research/writeups/ofexec-2026-11-27.md; its recommended entry is OFA_ENTRY below, where only the fallback pays this
OFA_ENTRY = "limit_at_level_5m_then_market"   # E5: resting limit at the swept level 300 s (fills 1 tick through), else market
OFA_LIMIT_WAIT_S = 300
STOP_SLIP_TICKS = 2         # stop-market and market exits (breakeven, time, end of day, flatten); the backtests store 1
# per bot (lead 2026-11-26: no number may go UP on an unmeasured assumption): ATLAS keeps the old pessimistic 10 ticks until
# ~10 of its real stop fills are logged (fills.jsonl.gz exit_slip_ticks); LIT uses the study's 2
STOP_SLIP_TICKS_BY = {"LIT": 2, "ATLAS": 10, "OFA": 2}   # OFA: base 2 as LIT; stress 10 (ofexec X2); no real stop fill yet
TARGET_THR_TICKS = 1        # a limit target needs a trade this many ticks through it (no stored trade was touch-only)
GAP_FILLS_AT_OPEN = True    # a bar that opens through the stop fills near that open, not at the stop

STOP_SLIP = STOP_SLIP_TICKS * TICK          # points
BACKTEST_STOP_SLIP_TICKS = 1                # what the stored LIT / ATLAS trades already carry on a stop / market exit
BACKTEST_LIT_COMM = 1.40                    # what engine/lit.py's research backtest books ($ per micro round turn)


def stop_slip_ticks(bot: str) -> int:
    """Ticks on a stop / market exit for a bot ("LIT" / "ATLAS"); unknown bots get STOP_SLIP_TICKS."""
    return STOP_SLIP_TICKS_BY.get(str(bot).upper(), STOP_SLIP_TICKS)


def entry_slip(bot: str) -> float:
    """Points of entry slippage for a bot ("LIT" / "ATLAS"); unknown bots get LIT's."""
    return ENTRY_SLIP_TICKS.get(str(bot).upper(), ENTRY_SLIP_TICKS["LIT"]) * TICK


def extra_exit_pts(exit_kind: str) -> float:
    """Points to take off a STORED trade's exit so it carries STOP_SLIP_TICKS instead of the backtest's 1 tick: 0 for a target
    (a limit), the extra ticks for every stop / market exit."""
    if str(exit_kind or "").upper().startswith("TARGET"):
        return 0.0
    return max(0, STOP_SLIP_TICKS_BY["LIT"] - BACKTEST_STOP_SLIP_TICKS) * TICK
