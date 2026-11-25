# Order-flow idea mill - pre-registered design 2 (written 2026-11-25, BEFORE any tick data reached the cloud)

Research only, paper. Nothing here trades or changes a live setting. Code: `research/orderflow/of_mill.py` (features, entries,
gates; `--selftest` on synthetic days). It runs on the same per-day summaries as DESIGN.md (`engine/ofsum.py`: 5m bars with
buy / sell / block volume, the footprint, and, from the day the depth recorder starts, the 5m depth summary).
DESIGN.md (OF1-OF6, the battery) stays exactly as it is; this is the WIDE search, so it has to pass much harder gates.

Hook for the research helper's idea mill (`research/ideamill`, not on any branch yet): `of_mill.candidates(days)` returns
one row per variant, `{"id", "family", "entry", "feature", "side", "trades": [{"day", "t", "pnl", "alt"}]}`. `alt` = the P&L if
the rule did nothing (a filter: the trade is taken; a stand-alone: 0) and `flip` = the coin-flip twin for the placebo.
The mill can apply its own 4 gates to these rows; `of_mill.gates()` applies the same 4 below so nothing waits for it.

## Frozen before data
- **Decision time:** every feature uses only bars CLOSED before the entry bar's open (5m grid). A trade's direction is d
  (+1 long, -1 short); every feature is SIGNED by d, so "high" always means "order flow agrees with the trade".
- **Entries (3 families):**
  - `LIT` - the live LIT replay's trades (`tools/lit_losses.run2`, sessions=None, costs in), as a FILTER.
  - `ATLAS` - ATLAS member MD (MACD at a sweep) trades (`tools/second_mix.units()["MD"]`, $ = R x $250), as a FILTER.
  - `LVL` - stand-alone fade at the first touch of each level of the day: prior-day RTH high / low, Globex high / low
    (18:00-09:30), RTH opening-range (09:30-10:00) high / low. 09:45-15:00 ET, a 5m bar trades >= 1 tick through the level and
    closes back on the other side -> enter against the push at the next open; stop 1 tick beyond that bar, target 2R, flat
    15:55, $500 risk, $1.40 a micro + 1 tick slippage each way (of_study._sim_df). One trade per level per day.
- **Variants:** each feature x each entry family x 2 sides (`hi` = keep / take only when the signed feature >= the Discovery
  median of that feature on that family's trades; `lo` = <= the median). Depth features (G) only enter the gates once >= 40
  days of depth exist (forward only; until then listed "waiting for depth").
- **Days:** tick days with >= 50,000 trades. **Discovery** = the older half, **Holdout** = the newer half (as DESIGN.md).
  Medians come from Discovery only. Looks: the battery's (40 / 60 / 120 / 250 days).

## The four gates (all must pass; a pass is a CANDIDATE only)
1. **Discovery + FDR:** in Discovery, gain > 0 (filter: kept net $ minus all-trades net $; stand-alone: net $) with >= 8
   trades kept, placebo p from 1,000 draws (filter: skip the same number of random trades; stand-alone: coin-flip direction),
   then **Benjamini-Hochberg at q = 0.10 across EVERY variant of the look** (not only the good ones).
2. **Holdout:** the same variant on the newer half: gain > 0, >= 8 trades kept, placebo p < 0.10, and for stand-alones PF >= 1.15
   and >= 0.5 trades a week.
3. **Deflated Sharpe** (Bailey & Lopez de Prado 2014) of the variant's daily P&L over ALL tick days, with N = the number of
   variants tried at that look, skew / kurtosis from the same series: **DSR >= 0.95**.
4. **Forward paper:** the variant runs on paper on the days after the look; it must stay positive (gain > 0) over the first 20
   forward tick days before an owner yes / no card is even written. Until then: "pending forward".
Every variant is logged with its gate results (`research/orderflow/mill_results.json` in the cloud, `logs/orderflow/` on the PC).
A failed variant goes to `docs/TESTED_AND_REJECTED.md` in one summary line per look (count + best near miss), not re-tuned.

## The 48 features (bars k-1, k-2 ... = closed 5m bars before entry; vol = bar volume; ATR5 = mean range of the 20 bars before)
| # | Group | Feature (signed by d) |
|---|---|---|
| A1 | delta | delta(k-1) / vol(k-1) |
| A2 | delta | sum delta(k-3..k-1) / sum vol |
| A3 | delta | sum delta(k-6..k-1) / sum vol |
| A4 | delta | RTH CVD change over the last 12 bars / their volume (0 before 10:30) |
| A5 | delta | delta-price divergence: +1 when delta(6 bars) agrees with d while price(6 bars) moved against d, -1 the reverse, else 0 |
| A6 | delta | CVD divergence at the extreme (OF6 rule, G = 6): +1 bullish for a long / bearish for a short, -1 the opposite, else 0 |
| B1 | footprint | stacked imbalances (>= 3 prices in a row, diagonal ask >= 3 x bid one tick lower = buy; mirror = sell) in k-1: buy - sell |
| B2 | footprint | the same over k-3..k-1 |
| B3 | footprint | diagonal imbalance sum: sum over prices of log((ask(p)+1) / (bid(p-1)+1)) in k-1 / prices |
| B4 | footprint | POC place in k-1: (POC - low) / range, mapped to [-1, 1] |
| B5 | footprint | POC migration: (POC(k-1) - POC(k-6)) / ATR5 |
| B6 | footprint | unfinished auction at the extreme AGAINST the trade in k-1 (both bid and ask volume at its last tick): -1, finished: +1 |
| B7 | footprint | exhaustion: volume at the extreme against the trade <= 2% of vol(k-1): +1 else 0 |
| B8 | footprint | single prints: share of prices of k-3..k-1 with volume <= 1% of their volume |
| B9 | footprint | delta in the top 2 ticks minus delta in the bottom 2 ticks of k-1, / vol |
| B10 | footprint | OF1 absorption at k-1's extreme against the trade: +1 absorbed, -1 not, 0 no zone |
| B11 | footprint | absorption share abs(dz) / vz at that extreme, x the absorbed sign |
| C1 | large lots | signed block volume >= 10 lots, k-3..k-1, / vol |
| C2 | large lots | the same >= 20 lots |
| C3 | large lots | the same >= 50 lots |
| C4 | large lots | the same at OF2's threshold (bth), k-6..k-1 |
| C5 | large lots | cluster: bars in k-6..k-1 with abs(b20) >= 30% of their volume, signed by the sum |
| C6 | large lots | large-lot share abs(b20) / vol over k-3..k-1 (unsigned: "who is here") |
| D1 | trapped | trapped traders: k-2 broke the 6-bar high (low) with delta in the break direction and k-1 closed back inside -> +1 for the fade side |
| D2 | trapped | failed-break delta: delta(k-2) x -1 when D1 fired, else 0, / vol |
| E1 | effort | effort vs result: (vol / range) of k-1 / its 20-bar median, x sign(delta agrees) |
| E2 | effort | relative volume k-1 vs the 20-bar median |
| E3 | effort | low-volume pullback: vol(k-3..k-1) < 0.7 x vol(k-6..k-4) while the move is against d: +1 |
| E4 | effort | delta per tick moved over k-3..k-1 |
| F1 | level | volume within 2 ticks of the entry family's level (LIT: the swept level = the sweep extreme) / day's mean bar volume |
| F2 | level | delta at the sweep extreme zone (8 ticks) / zone volume |
| F3 | level | bars since the extreme of the last 12 |
| F4 | level | buy-VWAP minus sell-VWAP of the RTH session, in ticks |
| G1 | depth | imbalance (bid5 - ask5) / (bid5 + ask5), k-1 |
| G2 | depth | the same, mean of k-3..k-1 |
| G3 | depth | change of bid5 - ask5 from k-4 to k-1, / their mean |
| G4 | depth | pulls on the side AGAINST the trade minus pulls on the trade's side, k-3..k-1 |
| G5 | depth | stacks on the trade's side minus stacks against, k-3..k-1 |
| G6 | depth | wall ratio: log(bmax / amax) of k-1 |
| G7 | depth | iceberg refill proxy: volume traded at k-1's extreme / the biggest displayed level there > 2: +1 |
| G8 | depth | mean spread of k-1 (unsigned) |
| H1 | CVD | CVD z-score: (CVD(k-1) - mean of the last 20) / their std |
| H2 | CVD | sign of the RTH CVD so far |
| H3 | CVD | Globex CVD (18:00-09:30) / its volume |
| H4 | CVD | opening 30-min delta / volume (0 before 10:00) |
| H5 | CVD | day CVD at a new high (low) while price is not: -1 for a long, +1 for a short (and the mirror) |
| H6 | CVD | day's cumulative b20 / day volume so far |
| H7 | CVD | absorption bars today: bars with abs(delta) > 0.3 x vol and abs(c - o) < 0.25 x range, signed by their delta sum |
| H8 | CVD | delta of the bar just before the entry family's trigger bar minus the day's mean bar delta, / vol |

Variant count: 48 features x 3 entries x 2 sides = 288 (204 without depth). FDR is over all of them at each look.
