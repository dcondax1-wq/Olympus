# Popular ICT/SMC NQ strategies - pre-registered rules (written 2026-11-23 11:55 ET, BEFORE any run)

One fixed version each. No parameter is changed after the first run. Data: TradingView CME NQ1! 5m (`data/NQ_5m.csv`,
back-adjusted), ET clock, session date = the 17:00 ET close. Spans: 2021-25 = 2021-11-08..2025-12-31, 2026H1 = Jan 1 - Jun 30,
2026H2 = Jul 1 - Oct 16 (data end).

Common rules
- FVG: bullish when low[i] > high[i-2] (gap high[i-2]..low[i]), bearish when high[i] < low[i-2]. Retrace entry = limit at the
  proximal edge (bull: low[i]; bear: high[i]). Swings = 5m fractal, 2 bars each side (known only 2 bars after the pivot).
- Stop 1 tick (0.25) beyond the named swing / sweep extreme. Target fixed 2R. One trade a day per strategy. Flat 15:55 ET.
- Fills on 5m bars: limit fills on touch; if stop and target are both inside one bar, the stop is taken; on the entry bar only
  the stop is checked. Pending orders expire at the stated time.
- Costs: $1.90 a micro round trip; 1 tick slippage on market / stop-order entries and on stop and 15:55 exits; limits and targets
  fill at their price.
- Size like LIT: risk $800 up to a 20-pt stop, then 800 x 20 / stop; micros = floor(risk / (stop x $2)), max 40; under 1 micro =
  no trade (this is LIT's rule; it skips stops above ~89 pts).

The ten
1. silver_bullet - first FVG whose 3rd candle closes 10:00-11:00 ET; limit at proximal edge until 11:00; stop beyond the
   3-candle extreme (bull: min low of the 3; bear: max high).
2. judas_swing - midnight open M (00:00 ET), Asian range 20:00-00:00. 02:00-05:00 ET: price takes the Asian high while above M,
   then a 5m close below M -> short at next open; stop beyond the high made since 00:00. Mirror long.
3. asia_sweep - Asian range 20:00-00:00. 00:00-11:00 ET: first bar to trade beyond either side, then a 5m close back inside
   the range (within 12 bars) -> market at next open; stop beyond the sweep extreme.
4. london_breakout - box 19:00-02:00 ET. 02:00-05:00 OCO stop orders 1 tick beyond box high / low; stop 1 tick beyond the
   opposite side of the box.
5. pdhl_sweep - previous session (18:00-17:00) high / low. 09:30-15:00 ET: first bar beyond either, then a 5m close back
   inside (within 12 bars) -> market at next open; stop beyond the sweep extreme.
6. ny_open_fvg - first FVG whose 3rd candle closes 09:30-10:00 ET; limit at proximal edge until 11:00; stop as 1.
7. po3_amd - accumulation = Asian range 20:00-00:00; manipulation = 00:00-09:30 takes exactly one side; distribution = at the
   09:30 open go the other way if price is on the far side of M (long: low swept and open > M; short mirror); stop beyond
   the manipulation extreme (00:00-09:30 low / high).
8. ict2022 - windows 02:00-05:00 and 08:30-11:00 ET: a bar trades beyond the latest confirmed swing high (sweep); within 12
   bars a close below the latest swing low before the sweep (MSS) with a bearish FVG formed from the sweep bar to the MSS bar;
   limit at the FVG proximal edge, valid 12 bars after MSS; stop beyond the sweep extreme. Mirror long.
9. turtle_soup - Raschke/Connors: prior 20-session low made >= 4 sessions ago; today (09:30-15:00) trades below it; buy stop
   at that prior 20-day low; stop 1 tick under today's low at entry. Mirror for highs. Daily 20 bars, intraday exit.
10. unicorn - swings: low A, high B, lower low C (takes A), then a close above B (MSS). Breaker = the last up-close candle
   between B and C. A bullish FVG in the C->MSS leg that overlaps the breaker range -> limit at the top of the overlap,
   valid 12 bars after MSS; stop beyond C. Mirror. Entries 02:00-15:00 ET.

Scoring per span: trades/week, win %, PF, $/month (21 sessions), max DD (daily equity), t of R. Multiple testing: 10
strategies, one-sided p of mean R > 0 over 2021-10 data (all spans pooled) and on 2026 alone, Holm and BH across 10.
Verdict keep only if PF > 1 in all 3 spans AND Holm p < 0.05. LIT: research/lab/backtest_live.json (days, trades).
Add-on: Rapid EOD 50K ($3,000 target, $2,000 EOD trailing, best day <= 30%, max 30 micros) and 25K ($1,500, $1,000, 30%,
max 20 micros, LIT and add-on at half risk); eval started on every session; LIT alone vs LIT + add-on.
