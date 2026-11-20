# Zlarior (LIT) more money - pre-registered design, batch 2 (2026-11-19, night-litmore)

The owner's added scope (verbatim): "It doesn't have to be straight strategy: fills, thinking process before and through
trades, news, bias, entries, more than just the strategy and rules. Maybe some trades for ES / NQ if it looks cleaner."
Written and committed BEFORE any idea below (and before any batch 1 idea) was run. Same base, same scoring, same gate
G1-G6 as `more_money_design_batch1.md`. Ideas tried in total = batch 1 (2) + batch 2 (7) = 9. Research only.

## Already tested (read first; NOT redone)
- Bias: 12 daily-bias methods as size / target / filter, 31 filters, 0 pass (`lit-bias-discretion.md`: HTF draw PDH/PDL/
  PWH/PWL, nearer PDH/PDL, previous close, premium/discount, Power of 3, weekly profile, midnight / 08:30 / 09:30 / 18:00
  opens, Asia direction, prior displacement, daily FVG, 1H/4H/D structure, NQ-ES SMT on PD levels, a vote); Asia range
  gate, 18:00 gap against x0.75, weekly profile skip (`lit-untested-bias.md`, `zeus-lab-lit-ideas`).
- News: out / BE before CPI-jobs-PPI-FOMC, news setups, news size tilts, "big release within 30 min" warning.
- Through the trade: 1m "trade is wrong" cuts (1m CISD against, new 1m low, back inside the swept level, higher low
  taken, volume surge), reversal-candle exits, structure CHoCH exits, the 15-minute check variants.
- ES/NQ: SMT at the sweep as a SIZE tilt (`lit-adv-audit-smt.md` experiment 5), ES LIT alone, NQ + ES first fill.
- Fills: the fill model study (`lit-live-fills.md`), late entries (`lit-robust.md`), conditional pullback limits (smart
  entries).

## Ideas (each ONE version, numbers fixed here)
1. **fill_limit_close** (fills / entries): today the bot buys at MARKET at the open of the bar after the 1m CISD close
   (backtest: that open + 1 tick). New: a LIMIT at the 1m CISD candle's close price for that one bar; it counts as filled
   only if the bar trades 1 tick through the limit (queue). Filled -> entry = the limit, no slippage; management starts
   at the next bar (the fill bar's favourable move is not counted; a stop touch inside the fill bar = a full stop-out).
   Not filled -> market at the next bar's open + 1 tick (no trade is skipped). 1m days only; the stop stays 1 tick beyond
   the sweep extreme and the size follows the real stop. Also reported, not an idea: the real fills found (live Oct 28
   short, Nov 16 long) vs the model, and how much the backtest's touch-fill on targets is worth (target needs 1 tick through).
2. **bias_london** (bias before the trade): a New York setup (entry bar 08:00 or later) is taken only on London's
   "discount" side: a long only when the sweep extreme is at or below the midpoint of today's London box (02:00-05:00),
   a short only at or above it. London setups (before 08:00) unchanged. A skipped setup leaves the day free.
3. **news_after** (news): on a Tier-1 day (a "high" impact US release in data/news/events.csv: CPI, jobs, FOMC decision /
   minutes, ...), setups whose 5m trigger bar closes before the day's first high-impact release are skipped; the day stays
   free for a setup after the release. 2021-23 has FOMC days only.
4. **cisd_fail** (through the trade): the shift failed. Before the trade has reached +0.5R and before breakeven, a 5m close
   below the lower of the 5m CISD level and the entry (long; mirror for shorts) -> out at the next 1m open (- 1 tick).
5. **es_fail** (through the trade, ES does not confirm): before +0.5R and before breakeven, an ES 5m close beyond ES's own
   extreme of the window from 60 minutes before NQ's sweep extreme to the fill (long: an ES close below that ES low) -> NQ
   out at the next 1m open after that ES bar closes (- 1 tick). ES data 2025-04-14 .. 2026-10-16 only.
6. **smt_filter** (ES vs NQ confirmation): SMT = at NQ's sweep extreme (that 5m bar and one on each side), ES did NOT make a
   new 2-hour extreme (long: ES's low of those 3 bars stays above ES's lowest low of the 24 bars before them). Keep an NQ
   setup only when SMT is present; a skipped setup leaves the day free. Days without ES data: unchanged.
7. **smt_pick** (trade the cleaner one): when SMT is present (ES held while NQ swept), trade MES instead of MNQ on that
   setup: ES entry at the open of the first ES 5m bar at / after NQ's fill (+ 1 tick), stop 1 tick beyond ES's extreme from
   NQ's sweep bar to the ES entry, target = ES's own VIX band (ES 18:00 open +/- one VIX move), at least 1.5R (else the NQ
   trade is kept), banked at 8R; ES stop must be 2.25-22.5 ES pts (E3 scaling) else NQ is kept; breakeven at +1R to
   entry + 0.75 ES pts, flat 15:55, 5m execution (no ES 1m, so no 15-minute check), stop before target in a shared bar.
   Same size rules on MNQ-equivalent points (MES $5 / ES pt = 2.5 MNQ pts). No SMT -> the NQ trade as today.
