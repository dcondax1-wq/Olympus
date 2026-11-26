# Entry execution policy for LIT and ATLAS: pre-registration (big-execution, 2026-11-26)

Written and committed BEFORE any result. PAPER RESEARCH ONLY: nothing live changes; the deliverable is a card or a "no".

## Question
The bots enter at MARKET. Real ATLAS entries filled 9 / 11 / 15 ticks worse than the model (n=3; research/batch5); at ~12
ticks ATLAS's 2021-25 edge is gone (break-even 3.1 ticks). LIT's one measured fill: 3 ticks (Nov 16); Oct 28 identical.
Does another entry order (limit at the signal price, marketable limit, wait for a pullback, hybrid) make more net $ per
SIGNAL, after the trades it misses?

## Data and signals (no change to any strategy)
- Signals = the stored backtests, unchanged: ATLAS `tools/atlas.account_units(BASE)` (EMA / MACD / S/R book), LIT
  `tools/lit_losses.base_trades()`. Per signal: time, side, model entry price, the model's exit price + time + kind, risk pts.
- Bars: NQ 1m (`data/NQ_1m.csv`, 2026 only) for 2026 H1 (Jan-Jun) and 2026 Jul-Oct 16; NQ 5m (`data/NQ_5m.csv`) for
  2021-25 (no 1m before 2026: the coarse test, reported as such). Futures only.
- Model entry price P: ATLAS = open of the signal bar; LIT = open of the 1m bar after the CISD (stored entry_px minus 1 tick).

## Policies (direction-neutral; "worse" = against the trade)
| id | Order | Fill rule |
|---|---|---|
| MKT | market (today) | fills at P + s ticks worse, s = the market slippage (ATLAS 12 = measured mean 11.7; LIT 2 = measured 3 and 0). Grid s = 0, 2, 4, 8, 12, 16 |
| LIM0-N | passive limit AT P, cancel after N min (N = 1, 2, 5, 15) | filled at P when a bar trades THROUGH P by q ticks (q = 1: a touch can sit unfilled in the queue) before the cancel and before the model trade's exit |
| LIMb-N | passive limit b ticks BETTER than P (b = 2, 4), N = 5 | same rule at P - b |
| MLk | marketable limit k ticks worse (k = 2, 4, 8) | fills at P + s if s <= k; else rests at P + k and fills on a trade-through there (N = 5) |
| PB-N | wait for the first 1m bar closing AGAINST the trade within N = 5 min, then market at the next open + 2 ticks | as MKT from that bar |
| HYB-N | limit at P for N = 2 min, then market (P_now + s) only if the price is within 0.25 R of P, else skip | combination |

Conservative intrabar rules (OHLC cannot order events inside a bar):
- The bot's order reaches CME ~4 s after the bar opens (measured ATLAS ledger 3-5 s). On the ENTRY bar a passive fill needs a
  trade-through of q + 2 ticks (the first seconds may be the extreme, before the order rests); variant "next" ignores the entry
  bar completely (most conservative).
- Fill bar = the model's exit bar: a winner counts as MISSED (target first), a loser as FILLED (adverse first).
- A missed signal = $0 (its winner or loser is not taken). Exits are the model's (same price levels: the stop, target, breakeven
  and time rules are levels / times, so a different fill price moves only the entry). Management relative to R (breakeven at
  +1R) is kept at the model's levels: a small approximation, stated.

Costs: MNQ $2/pt, commission $1.90 per micro round turn (MFFU), stop / market / time exits 2 ticks slippage, target limits 0.
Size: ATLAS $250 risk per trade on the model stop (as research/batch5); LIT the backtest's own qty. Both shown also in R.

## Judgement (decided now)
Primary metric: **net $ per signal** (missed = 0) at the measured market slippage, per span: 2026 H1, 2026 Jul-Oct, 2021-25.
A policy is ADOPTED for a strategy only if ALL hold:
1. it beats MKT at the measured slippage in all three spans (2021-25 on 5m bars with the conservative entry-bar rule);
2. it still beats MKT at HALF the measured slippage (ATLAS 6, LIT 1) in both 2026 spans (the measured number may be a
   small-sample fluke) under the "next" variant OR the base rule, and loses no more than 10% of the baseline $ in the
   worst span under "next";
3. it misses no more than 25% of the model's winners in any span;
4. it reproduces the real fills: for the 3 real ATLAS entries, the policy's fill vs the real one is stated.
Ties -> keep the simpler order (MKT). Otherwise the answer is "no": keep market entries.
Pre-registered expectation (the hypothesis, not a result): ATLAS's 5m-close signals coincide with everybody's 5m-close signals,
so the first seconds overshoot and revert; a limit at P for a few minutes should fill most trades about s ticks better. LIT
enters after a CISD with little slippage, so a limit gains little there and misses runners.
