# Lane A execution: how would it REALLY fill, and what is the cheapest way in and out? (pre-registered 2026-11-27, night-of-exec)

PAPER RESEARCH ONLY. Changes no bot, size, arming or route. Written BEFORE any lane A decision was looked at minute by minute.
Code: `research/orderflow/exec_study.py` -> `research/orderflow/exec_results.json` + `research/writeups/ofexec-2026-11-27.md`.
Frozen with this commit: no rule or constant below changes after the first run; a change is a new dated file.

## What the data can and cannot show (honest limits, written first)
- The PC's tick summaries (engine/ofsum.py) are **5m bars + 5m footprints** (volume at each price by aggressor side). No trade
  tape and no seconds leave the PC. NinjaTrader 1m OHLCV bars (`data/NQ_1m.csv`) give the path minute by minute.
- So "the first seconds" are **modelled**, not seen: a market order's give-away = a share of the first minute's run in our
  direction, calibrated on ATLAS's 4 real fills (research/writeups/atlasfill-2026-11-26.md: s = 0.363 of the first minute's run at
  ~3-5 s from close to fill). Latency L seconds -> s(L) = 0.363 x sqrt(L / 4) (the atlasfill convention). L = 1, 2.75 (today, per
  latency-2026-11-26) and 4 s. Floor 1 tick (spread).
- Limit fills: a resting limit fills only when a later trade goes **>= 1 tick through it** (engine/costs.TARGET_THR_TICKS; we are
  last in the queue). "Touch" fills are reported as the optimistic side only. Order within a minute is unknown: when the same 1m
  bar could fill the entry and hit the stop, the stop comes first (conservative). The footprint is used for the queue check at the
  limit price (volume traded at / beyond it in that 5m bar) and to measure stop / target slippage room.

## The signals (unchanged)
Lane A decisions exactly as `engine/of_paper.replay_summary` makes them on each real summary day (DESIGN_paper.md): the TAKEN set
(absorbed, not busy) and the SKIPPED set are frozen from that replay; an entry style never changes which signals are taken (the
"busy" chain is kept as the lane's replay made it). Decision = signal bar close (t_sig + 300). Stop = 1 tick beyond the signal
bar's extreme (CLAUDE.md). Target = 2R from the style's own fill (the lane's rule). Flat at the close of the 15:55 bar.
Exits are checked on 1m bars from the fill minute on (finer than the lane's 5m walk; stop first when one 1m bar touches both).

## Entry styles (all at 1 micro; R = per the style's own risk)
| id | entry | fill rule |
|---|---|---|
| E0 | the lane's paper model | next 5m open + 1 tick (as scored in real_verdict.md) |
| E1a / E1b / E1c | market at decision, latency 1 / 2.75 / 4 s | next 1m open + max(1, round(s(L) x first-minute run in our direction)) ticks |
| E2-5 / E2-15 | limit AT THE SWEPT LEVEL (short at a high: sell limit at the level; long: buy limit at the level), timeout 5 / 15 min | first 1m bar from the decision whose high (short) / low (long) trades >= 1 tick through the level; else no trade |
| E3-k | limit at the decision close +k ticks better (k = 2, 4), timeout 15 min | as E2 |
| E4 | stop-limit "go with the fade": short: sell stop at the signal bar's close - 2 ticks (long mirror), limit 2 ticks past the trigger, timeout 15 min | first 1m bar trading through the trigger; fill = trigger + 1 tick; a 1m bar that opens beyond the limit = no fill |
| E5 | limit at the level for 5 min, then market if not filled (E2-5 + E1b fallback) | |

If a limit's fill price leaves < 4 ticks of risk to the stop it is still taken (risk is real); R is reported, but the money test is $.

## Exits
| id | stop | target |
|---|---|---|
| X0 | stop-market 1 tick beyond the extreme, fill +1 tick (the lane's model) | limit at 2R, filled on a touch |
| X1 | stop fill +2 ticks (engine/costs LIT) | limit, needs 1 tick through |
| X2 | stop fill = max(2, round(0.363 x sqrt(1/4) x the stop minute's run beyond the stop)) ticks (stop sits at the exchange: L = 1 s) | limit, needs 1 tick through |
| X3 | X2 | target 1 tick short of 2R (limit 1 tick earlier, filled on a touch of that price) |
Measured on the real days, reported plainly: per stop hit, how far the stop minute ran beyond the stop (ticks) and the footprint
volume at the stop price; per target hit, the share that only touched (no trade beyond).

## Costs
Commission $1.90 per micro round turn (engine/costs.COMM_RT). The lane's own book uses $1.40: both shown, the decision on $1.90.

## Numbers per style (TAKEN and SKIPPED separately, pooled days and the older / newer half of the days)
signals, fill %, mean ticks given away vs the decision close, mean R per filled trade, **$ per signal at 1 micro** (an unfilled
signal = $0), net $, missed-winner cost (sum of E1b $ of the signals a style did not fill, that E1b won), trades/week, max DD $.

## Decision rules (frozen)
1. **Realistic baseline** = E1b + X2 (market, today's latency, measured-room stops, 1-tick-through targets). It replaces E0 as the
   lane's honest score.
2. A non-market entry is recommended only if, on the TAKEN set, its $ per signal beats E1b's in BOTH halves of the days, its
   fill % >= 70 %, and the TAKEN-vs-SKIPPED separation (mean R TAKEN > SKIPPED, one-sided shuffle p < 0.10) still holds under it.
   Otherwise the recommendation is market (E1b; E1a once fast_entry is on, which is the latency study's ask).
3. Exit: the cheapest honest pair that is NOT optimistic: X2 unless the measured stop room says 2 ticks is too few (median
   run beyond the stop > 4 ticks -> use the measured median). X3 is chosen over X1/X2 targets only if it beats in both halves.
4. Lane A's verdict is re-scored with the recommended pair (same bars as DESIGN_paper.md "Scoring": >= 40, taken > skipped,
   p < 0.10, both halves same sign, taken $ > 0 after costs). It is said plainly if it flips.
5. Small sample (~40 taken): any $ gap under $5 per signal is called "a tie" and the simpler style wins.

## Output for the lead (LEAD_WIRES)
The recommended cost constants for an "OFA" lane in engine/costs.py (entry slip ticks, stop slip ticks, target rule) in
`research/handoff/2026-11-27/night-of-exec/LEAD_WIRES.md`; the helper does not edit engine/costs.py.
