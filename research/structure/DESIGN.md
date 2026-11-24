# Structure variants: pre-registration (written 2026-11-24 BEFORE any variant was run)

PAPER RESEARCH ONLY. Nothing here changes `live_model*.json`, `engine/live.py`, `engine/lit_live.py`, sizing or arming.
Code: `research/structure/variants.py` -> `research/structure/variants.json`. Base rates: `research/structure/study.py` ->
`STRUCTURE_ATLAS.json`, write-up `research/writeups/structure-2026-11-24.md`.

**Honesty note (read first).** The base-rate study (`study.py`) was run on ALL spans (2021-25, Jan-Jun 2026, Jul 2026-now)
before this file was written, and it includes the pillars' trades tagged by structure. So the variants below were chosen
knowing roughly how the tags looked in every span, including the Jul-Oct check half. That makes a pass LESS trustworthy than a
blind one; to pay for it every gate below is strict (every span, not just the average) and a many-tests bar of 0.05 / 8 is
applied to the placebo test. Already-rejected ideas that overlap (NR7 / NR4 / inside-day breakouts, Crabel, IB breakouts,
displacement-quality filters on LIT, structure stops / targets on LIT) are NOT re-run.

Costs everywhere: $1.40 a micro round trip + 1 tick slippage on stop / time exits (research `lit.COMM`, `lit.SLIP`).
Spans: 2021-25 = Oct 2021 - Dec 2025, H1 = Jan-Jun 2026, H2 = Jul 2026 - the last bar.

## Standalone (must pass H1 AND H2 AND 2021-25)
Shared: NQ 5m bars (data/NQ_5m.csv), MNQ micros at $2/pt, risk $500 a trade, micros = floor(500 / (stop pts x 2)), 1..40,
size follows the stop. One trade a day, entries 02:00-15:30 ET, flat 15:55 ET. A bar that touches stop and target = stop.
Zigzag swing = `bars.zigzag`, reversal 0.3 x daily ATR14 (prior 14 sessions); expansion leg >= 0.75 ATR; the leg is only
known at its CONFIRMATION bar (no look-ahead); 5m displacement = body >= 1.5 x 5m ATR14, close in the outer 25%.

- **S1 Expansion pullback 0.5.** A confirmed expansion leg that contains a displacement candle in its direction. At the
  confirmation bar, if price has not yet reached the 0.5 retracement, rest a limit there. Stop 1 tick beyond the leg start
  (the swing). Target = the leg extreme (retest). Cancel when a new pivot confirms or at 15:30.
- **S2 Deep pullback 0.79 -> 1.272.** Same leg rule; limit at the 0.79 retracement, stop 1 tick beyond the leg start, target
  the 1.272 extension of the leg.
- **S3 Expansion follows expansion.** Days after a big day (prior session range >= 1.5 ATR) OR with a big overnight range
  (18:00-09:30 >= 0.6 ATR). The first 5m displacement candle 09:30-11:00 ET -> enter at the next bar open in its direction,
  stop 1 tick beyond the displacement candle's far end (its low for a long), target 2R.

Gate: PF >= 1.10 and net $ > 0 in each of the three spans, 1-5 trades a week on average (2-4 wanted), the Builder 50K eval
2-week pass > fail in H1 and H2.

## LIT filters / boosts (picked on Jan-Jun 2026, checked on Jul-Oct 2026; 2021-25 reported, not a gate)
Base = the live LIT trades (`tools/stops_targets_time.units()` = run `lit_live`, same fills), risk-matched $ via
`size_matched`, 50K eval path via `tools/lit_edge.eval_path`, 3-account evals via `stops_targets_time.evals`.
Structure tags are causal (bars closed before the entry).
- **F1 LIT skip "late chase":** skip the trade when a 5m displacement candle IN the trade's direction closed in the 30 min
  before the entry (the move already went).
- **F2 LIT skip "mid-retrace fade":** skip when the trade is against the last confirmed swing and price sits 0.5-0.79 into its
  retracement (no level, no extreme: the middle).
- **F3 LIT boost x1.5 "at the day's extreme":** 1.5x the micros (cap 40) when the entry is in the 0-20% of the day's range
  so far on the trade's side (long near the day's low so far / short near its high) = the start of a possible expansion.

Gate (LIT rule): H1 AND H2 net $ higher than live (risk-matched), 50K eval path net higher and 2-week fails not higher in H1
and H2, >= 2 trades a week; placebo: the same number of trades skipped / boosted at random (2,000 draws) beats the rule in
< 0.05 / 8 of draws in H2.

## ATLAS / BLITZ filters (must be better in H1 AND H2 AND 2021-25)
Base = the pillars' own backtest trades in `research/learn/lessons.jsonl.gz` (tools/win_loss_anatomy, costs in), $ as stored.
- **F4 ATLAS skip "middle of the day's range":** skip when the entry is 50-80% of the day's range so far on the trade's side.
- **F5 BLITZ skip "half-used day":** skip when the day's range so far at entry is 0.5-0.8 ATR (neither quiet nor expanded).

Gate: net $ higher and PF not lower in each of the three spans, trades a week still >= 2 (ATLAS) / within BLITZ's own band;
placebo random-skip p < 0.05 / 8 pooled over the three spans. Caveat (the same as Market Learn's): a trade-list skip; ATLAS's
account rules could take a different trade after a skip, so a pass needs the full backtest re-run before any yes.

Eval speed for every variant: rolling starts on each session, the Builder 50K rules (target $3,000, MLL $2,000 trailing EOD,
lock $100, DLL $1,000), trades booked at their own $; 2-week (10 sessions) pass / fail %, 40-session pass %, median days.
