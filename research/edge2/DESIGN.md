# edge2 (2026-11-21): pre-registered design, written and committed BEFORE any run

Lead task: more money from the NQ bots. 10 new ideas, fixed here; nothing below changes after a result is seen.
Code: research/edge2/edge2.py. Output: research/edge2/results.json. Write-up: research/writeups/edge2-2026-11-21.md.
Paper only: no engine file, no live_model*.json, no arming.

## Checked first (docs/TESTED_AND_REJECTED.md, lit-edge-2026-11-20.md, atlas-edge-2026-11-20.md) - NOT redone
ORB 2nd side after a failed break; opening drive; VWAP pullback / reversion; value-area re-entry; Keltner squeeze; POC touch;
Crabel NR4/NR7; Gao intraday momentum (first 30 min -> last 30 min); late-day break / last-half-hour reversal; ICT models,
SMT, Judas (2026-11-20); ATLAS limits at / 1-2 ticks better than the 5m open with 1-2 min timeouts, limit-then-market, next 5m
open, per-leg minutes; LIT limit 2 ticks better; LIT buy-stop entry. Exits: trails (swing / structure / ATR), partials,
change-of-character exits, clock / session-end exits, BE variants are all rejected for LIT and ATLAS -> **no exit idea is
run** (target (3) of the brief: nothing untested is left that one target can express; said, not skipped silently).

## A. ATLAS entry variants (the live ATLAS units, tools/atlas_fills; judged with tools/atlas_edge's own gate G at N = 6 and 10
ticks of arrival cost, B60 and B40, funded 25K from today's account, 1,000 paths, fixed $250 view H1 / H2 / 2025 / 2021-24)
Fill model (as atlas_fills F1): the order arrives when the market is N ticks past the 5m open.
- **A1 deep limit:** limit 8 ticks BETTER than the 5m open, cancelled after 15 minutes (3 5m bars).
- **A2 deeper limit:** 16 ticks better, 15 minutes.
  (1m bars: minute 1 must close 1 tick through, later minutes trade 1 tick through; a target reached first = missed runner;
  5m-only spans: the entry 5m bar must close 1 tick through, i.e. the 15-min window is not modelled: A1/A2 2021-25 is
  pessimistic-by-design and stated.)
- **A3 stop entry (continuation):** a buy-stop / sell-stop 12 ticks past the 5m open, live 5 minutes; filled at the trigger +
  2 ticks; if the stop level is traded first (or in the same minute) = no fill (minute first) / filled-then-stopped (same
  minute, worst case). 5m-only spans: the entry 5m bar decides (high-side first only if the low did not reach the stop).
- **A4 stop entry:** 20 ticks, 10 minutes, same rules.
  Note: under the repo's arrival model (market N ticks past the open) a stop closer than N is just a market order; that is
  why the triggers are 12 / 20 ticks (beyond N = 10). Fill-rate (share of signals filled) reported for every A version.

## N. New stand-alone NQ setups (5m NQ1!, RTH, ET clock; one trade a day each; market entries at the next bar open + 1 tick,
stop 1 tick beyond the setup's extreme (fills 1 tick worse), one target 2R (fills only 1 tick through), stop first if both in a bar,
flat 15:55; $1.90 a micro RT, $250 risk a trade, 20 micros max, too wide = skip; 10-tick stress)
IB = the 09:30-10:25 bars (first hour). ADR14 = mean of the last 14 RTH ranges (closed days only).
- **N1 IB failed-break fade:** 10:30-14:30, price trades >= 1 tick beyond IB high (low), then a 5m close back inside IB within 3
  bars of the first break bar -> fade at the next open; stop 1 tick beyond the highest high (lowest low) since the break.
- **N2 IB break-retest:** 10:30-14:30, first 5m CLOSE beyond IB high (low); then a limit at the IB edge for 6 bars (30 min),
  fills only on a trade 1 tick through; stop 1 tick beyond IB mid (the 50% of IB); skip if the stop is > 0.5 x ADR14.
- **N3 prior-day level break-retest:** 09:45-15:00, first 5m close beyond the prior RTH high (low); limit at the level for 6
  bars; stop 1 tick beyond the breakout bar's opposite end... no: beyond the lowest low (highest high) of the 3 bars before
  the breakout close; skip if the stop is > 0.5 x ADR14.
- **N4 opening gap fade:** gap = 09:30 open vs the prior 15:55 bar close, |gap| between 0.15% and 0.8% of price; at the 09:35
  open enter toward the prior close only if the 09:30 bar closed in the fill direction (close < open for a gap up); stop 1
  tick beyond the 09:30 bar's extreme on the gap side; target = the prior close (1 tick before), skip if < 1R, cap 3R.
- **N5 first-hour trend continuation:** at 10:30, if |10:25 close - 09:30 open| >= 0.35 x ADR14 and the 10:25 close is in the
  top (bottom) 20% of IB -> enter with the move at the 10:30 open; stop 1 tick beyond IB mid; target 2R.
- **N6 overnight-inside breakout:** only on days whose overnight range (18:00-09:25) is inside the prior RTH range; 09:30-11:00,
  first 5m close beyond the prior RTH high (low) -> continuation at the next open; stop 1 tick beyond that close bar's low
  (high); skip if the stop is < 8 pts or > 0.5 x ADR14.

Periods: 2026 Jan-Jun (pick), 2026 Jul-Oct (check), 2021-11..2025-12. All three must pass.

## Pass bars (fixed now)
- **A (ATLAS entries):** tools/atlas_edge.gate_g exactly (funded $ >= base + $10 H1 and H2, REF >= base - $5, lost <= base + 0.5
  pt everywhere, PF >= base H1/H2, fixed $ a month >= base - $10 in H1, H2, 2025, 2021-24, 2.0-4.1 trades/wk) at N = 6 AND 10.
  1m-only effects (2021-25 pessimistic fill window for A1/A2) are stated.
- **N (new setups), each of the three periods:** net > 0 with costs, PF >= 1.2, 10-tick stress net > 0, 0.8-2.5 trades a week;
  AND as an addition to LIT + ATLAS on one 25K (fixed $250 each, real day order): days under -$500 per 100 sessions not higher
  than LIT + ATLAS alone, and the rolling 60-session MFFU Rapid EOD 25K eval pass % higher, in each period. Daily $ correlation
  with LIT and ATLAS reported.
- A survivor -> OFF-by-default code (research module or a switch) + ONE Decide card. 10 ideas: a single marginal pass is
  treated as likely noise and said so.
