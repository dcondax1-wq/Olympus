# Exit + backtest realism: pre-registration (big-exitreal, 2026-11-26)

Written and committed BEFORE any result. PAPER RESEARCH ONLY: no strategy, size or live setting changes. A cost constant is
proposed, never applied, unless the fix is pure modelling (then it goes through the lead).

## Question
Every $ / PF / pass % we quote rests on the backtests' exit fills. Plain assumptions today:
- LIT (engine/lit.py simulate_x): stop = stop level - 1 tick (SLIP), a bar that opens through the stop still fills at the
  stop - 1 tick; target = filled on a TOUCH at the level; commission $1.40 (research) while MFFU charges $1.90.
- ATLAS (research/second/*_best.json, via tools/atlas.account_units): exit slippage 1 tick in the stored exit; target on a
  touch.
- The eval engines (research/plans/rank.py, tools/money/stack_one_account.py) take these points per micro and apply $1.90.
A target LIMIT can sit unfilled in the queue when price only touches it; a stop-market can fill worse than 1 tick, and much
worse on a gap. How much do the numbers move?

## Real exits (calibration, honest)
The cloud has NO exit fill prices from the broker except ATLAS's Nov 20 target (SELL 1 MNQ at 26,380.75, +$514.18,
data/pc_days via livegap). The bot books its ledger at the model's exit prices (research/batch5), so the other "live" exits
(LIT Oct 28 / Nov 16 stops, ATLAS Nov 6 / 17 / 18) cannot calibrate slippage. They are listed, with what the 1m bars say
about each (touch vs trade-through at the target, gap at the stop), and nothing is fitted to them.

## Models (applied to the stored trades, per trade, on bars: NQ 1m for 2026, 5m for 2021-25)
| id | Target | Stop / market exits |
|---|---|---|
| E0 | as stored (touch fills) | as stored |
| Et | needs a trade-THROUGH of 1 tick; a touch-only target is re-walked (below) | as stored |
| Es | as stored | +1 tick (2 in all), and a bar that OPENS through the stop fills at that open (- 2 ticks) |
| **E1** | Et | Es (the realistic model) |
| E2 | trade-through 2 ticks | +3 ticks (4 in all) + the gap rule (stress) |
Re-walk of a touch-only target: from the next bar on, the same day: filled at the target when a bar trades through it (same
$), stopped at the ORIGINAL stop if price comes back to it first (- the model's stop slippage), else closed at the 15:55 ET
bar's close (- the stop slippage). A breakeven stop would make that loss smaller: reported as the bound "E1-BE" (stop at
the entry price instead) for the touch-only trades.

## Metrics
Plain, per bot and span (2026 H1, 2026 Jul-Oct, 2021-25), $250 risk a trade, $1.90/micro: trades/week, PF, net $, $/month,
max drawdown. Eval: research/plans/rank.py's eval_run + slot_run (the real eval / funded engines, ATLAS at its measured entry
fills as rank.py does) for MFFU Builder 50K, Builder 25K and Rapid EOD 25K, 1,000 paths a span (H1 / H2 / REF): pass %,
median days, net $ over 6 months.

## Judgement (decided now)
The backtests are called OPTIMISTIC if E1 moves, in ANY span, a bot's net $ by more than 5% or a plan's pass % by more than
2 points (absolute). Then: corrected cost constants are proposed for ONE place (engine/costs.py), with the list of every page
and number that would change. Otherwise: "exits are modelled fairly", no change. E2 is shown as the stress band only.
