# ATM model: the owner's rules, and the exact mechanical version we tested

Model: `tools/lab_models/atm.py` (`run`, `run_raw`, `build_all`, `state`). Runner: `tools/lab_atm_run.py`.
Data: TradingView CME futures NQ1! 5m (ES1! 5m for SMT), as in `data/NQ_5m.csv` / `data/ES_5m.csv`. Official CME data only (TradingView / NinjaTrader), no CFD.

Everything below was fixed before the scored batch was run. Where the owner's words leave room, the choice is marked
**(ours)**. None of these choices was changed after a scored result was seen.

## A. The owner's rules (as given)

1. Mark the range from 07:00 to 09:25 ET: its highest high (ATM high) and lowest low (ATM low).
2. After the NY open (09:30), wait for a sweep of one side: price trades at least 1 tick beyond the ATM high or low.
3. Wait for a strong V-shape inversion and an IFVG. Use the highest timeframe that shows an IFVG ("1–3 minute,
   maybe 5 minute").
4. Add confluences if seen: 1H trend, SMT with ES, NQ relative strength vs ES, open location, FVG/IFVG size, V strength,
   LRLR path, target is EQH/EQL or a session level.
5. Stop beyond the most recent low/high. Target the opposite side of the ATM range; also consider clear liquidity before
   it (EQH/EQL, Asia/London/prior-day highs and lows, stacked highs/lows). Skip if the opposite side is under 1.5R.
6. Take profit; flat by 15:55. One trade a day. Entries 09:30–11:30 ET.
7. Sizing: better setup = 1 full NQ, less confident = micros.

## B. Plain rules a trader can follow by hand (5m chart; shorts mirror)

1. **Range.** At 09:30 mark the high and low of the 5m candles from 07:00 through the 09:25 candle.
2. **Sweep.** From the 09:30 candle until 11:30, wait for a candle to trade 1 tick or more below the ATM low (or above
   the ATM high). That side is now the "swept" side and the other side is the target. If the target side is traded
   through before you are in, the setup is off for the day.
3. **Extreme and leg.** The extreme is the lowest low since the sweep. The sweep leg runs from the last swing high
   before the extreme (a 5m high with 2 lower highs on each side) down to the extreme. A new lower low restarts
   steps 3–5 from the new extreme.
4. **Strong V.** Within 6 candles of the extreme, a candle must close back above the ATM low, at or above the 50% level
   of the sweep leg, and by then at least one bullish displacement candle must have printed (body at least 1×ATR14, or
   body at least 60% of the candle's range).
5. **IFVG.** A bearish fair value gap that formed inside the sweep leg must have been closed above by a candle body (a
   close above the gap's top) after the extreme.
6. **Entry.** Buy at the close of the first candle, within 6 candles of the extreme, at which steps 4 and 5 are both done
   and the close is inside the range.
7. **Stop.** Below the extreme by max(2 ticks, 0.1×ATR14).
8. **Target and skip.** The target is the ATM high (limit 1 tick under it). If the ATM high is less than 1.5R away,
   skip the trade.
9. **Management.** Leave the stop and target alone. Flat at 15:55. One trade a day.
10. **Size.** Count the confluences (section D). 5 or more: 1 NQ (10 MNQ) if the stop costs ≤ $700, otherwise $700 of
    risk in MNQ. 3–4: $350 in MNQ. 0–2: $175 in MNQ (minimum 1). Never risk past the $1,000 daily loss limit.

## C. Exact mechanical definitions (what the code does)

**Bars and time.**
- Bars are labeled by open time in ET. A bar is known at its open + 5 min.
- `tf` is a parameter, so 1m/3m frames run the same code.
- The trading day is the CME session from 18:00 to 17:00, labeled by the date it ends (`strategy_lab.bars`).

**R1. ATM range.**
- The bars opening at ET minute ≥ 420 and < 570, that is 07:00 through the 09:25 bar. **(ours)**: "to 09:25" is read as
  *including* the candle labeled 09:25, so the range is final exactly at the 09:30 open.
- At least half of the range bars must exist (holiday guard).
- `ATM_H` = max high, `ATM_L` = min low.

**R2. Sweep.**
- From the bar opening 09:30 through the last entry bar, a long arms when `low ≤ ATM_L − 1 tick`. A short arms when
  `high ≥ ATM_H + 1 tick`.
- **(ours) one draw per day:** when the ATM high is traded through by 1 tick, the long side dies for the day, because its
  target liquidity is gone. The mirror kills the short. So only the first-swept side can set up. With 2 trades a day the
  second trade must re-sweep the same side after the first trade has closed.

**R3. Extreme and sweep leg.**
- `e` = the bar with the lowest low since the sweep bar. Every lower low moves `e` and restarts the V clock.
- Leg origin: the last 5m fractal swing high (D1, k=2: high > the 2 previous highs and ≥ the 2 next highs) whose pivot
  bar is before `e` and which is confirmed (pivot + 2 bars) by the current bar. The search covers 48 bars (4 h) before
  `e`.
- If there is none, the origin is the highest high of those 48 bars.
- Leg = origin high − extreme low.

**R4. Strong V** (all checked on closes, within `N` bars of `e`; base N = 6, so 30 min).
- *Reclaim:* some close in bars `e..e+N` is above `ATM_L`.
- *Retrace:* that close is ≥ extreme + X × leg (base X = 50%).
- *Displacement:* a bullish candle (close > open) in bars `e..` that close, with body ≥ 1.0×ATR14 **or** body ≥ 60% of
  its range. This is the owner's "or". ATR14 is Wilder's ATR on the same frame, including the candle itself.
- The extreme candle itself may be the reclaim candle (a one-candle V).

**R5. IFVG** (an FVG created by the sweep leg, inverted by a body close).
- Candidate gaps:
  - every bearish 3-candle FVG `high[c3] < low[c1]` with c1 ≥ the leg origin and c3 ≤ `e`
  - size ≥ 1 tick
  - and no close above its top between c3 and `e` (otherwise it was already broken inside the leg)
- Inversion: a close above the gap's top on any bar from `max(e, c3+1)` on. "Through" = a body close beyond the far edge
  (DOL D6).
- **Highest timeframe:** the code runs one timeframe at a time (`tf`). On our data 5m is the only one, so it is also the
  highest. A multi-frame "take the highest frame that shows an IFVG" needs 1m/3m history that we do not have (see
  ATM_REPORT.md).

**R6. Entry.**
- Market at the close of the first bar `i` with `e ≤ i ≤ e+N` where R4 and R5 are both satisfied by bar `i` and
  `close[i] > ATM_L`.
- The entry bar must open before 11:30 (base), or before 11:00 in the `win1100` variant.
- A signal that is skipped (R8) uses up that extreme. Only a new lower low re-arms it.

**R7. Stop.** `stop = low[e] − max(2 ticks, 0.1×ATR14[i])`. `R = entry − stop`.

**R8. Target and skip.**
- (a) Base: the target is `ATM_H`. The limit sits at `ATM_H − 1 tick` and is filled only on a bar whose high reaches
  `ATM_H`, so the limit is traded through by a tick.
- Skip if `ATM_H − entry < min_rr × R` (base 1.5; variants 1.0 and 2.0).
- Also skip if flat $350 sizing gives 0 MNQ (the stop is wider than about 175 pts). That is the house rule.
- (b) `tgt_first`: the nearest **clear pool** strictly below `ATM_H − tol` and at least 1.0R from entry, whose path is
  clean (LRLR, below). If there is none, use `ATM_H`.
  - Pools: PDH/PDL; prior RTH (09:30–16:00) H/L; Asia (20:00–24:00) H/L; London (02:00–05:00) H/L; relative equal
    highs/lows on 5m.
  - EQH/EQL follows DOL D8: 2 swings within max(2 ticks, 0.1×ATR), at least 3 bars apart, with a pullback of at least
    1×ATR between them; the level is the higher one. "Stacked highs" are covered by EQH.
  - A pool must be formed before the signal close, and not yet traded through by 1 tick.
- (c) `tgt_half`: half the contracts (ceil(n/2), keeping at least 1 runner) exit at the (b) pool. The runner goes to
  `ATM_H`. After the partial fills, the stop moves to entry, effective from the next bar.
  - With 1 contract, or with no pool, it is the base trade.
- Same-bar rule: stop first, then partial, then target.
- A gap through the stop fills at the bar open.

**R9. Management.**
- No break-even, trail or early exit (the owner gave none), except BE after the partial in (c).
- Flat at the close of the bar opening 15:50 (15:55 ET).
- One position at a time, `max_trades_day` = 1 (variant 2).

**Costs.** As in `strategy_lab.make_trade`:
- MNQ $2/pt; 1 NQ = 10 MNQ in P&L
- $1.40 round trip per micro-equivalent
- 1 tick of slippage on the market entry and on stop, BE and time exits; limit targets fill at their price

## D. Confluences (logged on every trade; they only feed the sizing score)

Each is True/False at the signal close, causal. **All thresholds are ours** and were fixed before any result.

| key | True when (long; shorts mirror) |
|---|---|
| `trend_1h_with` | The last *closed* 1H bar's BOS trend is up. Clock-aligned 1H bars; a 3-candle swing; the trend flips on a 1H close through the last confirmed swing (same as `lab_confluences`). |
| `smt` | ES has **not** traded 1 tick below its own 07:00–09:25 low between 09:30 and the signal bar, while NQ swept its low. |
| `nq_rs_with` | NQ's % change since the 09:30 open is above ES's: long the stronger index. |
| `open_loc_with` | The 09:30 open is in the lower half of the ATM range (on the swept side), so the sweep is a short Judas run from the open and the whole range lies ahead. |
| `ifvg_big` | The largest inverted leg FVG is ≥ 0.25×ATR14. |
| `v_fast` | The first close back inside the range comes within 2 bars of the extreme. |
| `lrlr` | At most 1 resistance zone between entry and the target (DOL-6). Zones are fresh 5m swing highs of today, plus live (untapped) bearish 15m FVGs from the last 2 days whose bottom is in the corridor; zones within tol are merged; the target zone itself is excluded. |
| `tgt_pool` | `ATM_H` is within tol = max(2 ticks, 0.1×ATR14) of PDH, prior RTH high, Asia high, London high or the overnight (18:00–09:30) high, **or** it forms a relative EQH (D8) with another 5m swing high today. |

Logged but not scored: CPI/NFP/FOMC day (`info.news`), big RTH gap ≥ 0.25 ADR10 (`info.gap_big`), bars to reclaim,
leg and IFVG size in points, and the path resistance count `n_res`.

## E. Sizing tiers (fixed before results)

- `score` = the number of the 8 confluences that are True (None counts as 0).
- Tiers:
  - **A** if score ≥ 5: `min(10, floor($700 / (stop_pts × $2)))` MNQ. That is 1 NQ when the stop costs ≤ $700, otherwise
    $700 of risk in micros.
  - **B** if score is 3–4: $350 in micros (`strategy_lab.size`, max 40).
  - **C** if score ≤ 2: $175 in micros, minimum 1. The minimum keeps the same entries as the flat scheme.
- The stop distance for sizing includes the 1-tick entry slippage, as `strategy_lab.size` does.
- **Flat comparison:** $350 fixed risk on exactly the same entries.
- **DLL guard (both schemes):** a trade's size is cut so that the realized day loss plus its risk stays within $1,000.
  This only matters with 2 trades a day.

## F. Variants (the complete list; each changes one thing from the base)

| name | change |
|---|---|
| `base` | rules above: N=6, X=50%, target (a), skip < 1.5R, 1 trade a day, entries 09:30–11:30 |
| `n4` | V within 4 bars |
| `n8` | V within 8 bars |
| `x618` | V retrace ≥ 61.8% |
| `tgt_first` | target (b): the first clear pool with a clean path, else the opposite side |
| `tgt_half` | target (c): half at the first clear pool, runner to the opposite side, BE after the partial |
| `rr1` | skip only if the opposite side is < 1R |
| `rr2` | skip if the opposite side is < 2R |
| `two_a_day` | up to 2 trades a day |
| `win1100` | entries 09:30–11:00 |

- Each variant is scored with both sizing schemes (flat $350 and tiered) on dev, confirm, ytd, aug_oct and y2025. That
  is one batch, run once.
- The "best variant" is picked by **dev net (flat sizing)** only.

## G. 1m/3m version (pre-registered 2026-10-16 19:10 ET, before any 1m result was seen)

This is the owner's execution style: read the setup on 1–3m and take the highest timeframe that shows an IFVG. Code:
`atm.run_raw_mtf` (and `atm.run` with `tf=1`). Everything not listed here is as in sections B–E.

**Data.**
- TradingView NQ1! **1m** bars: the stitched, back-adjusted `data/clean/NQ_1m_tv.csv` (copied to `data/NQ_1m.csv`, see
  `research/lab/DATA_1M.md`). Development only uses raw chunks for sessions after the 2026-09-14 roll, where raw =
  adjusted.
- ES1! **5m** (TradingView) for SMT and relative strength. There is no TradingView ES 1m, so ES is read only from 5m
  bars that have closed.
- The old Yahoo `NQ_1m.csv` is never used.
- Scoring uses whatever 2026 sessions the 1m file covers. The covered session count is reported for every period.

**G1. Frames.**
- 2m, 3m and 5m bars are resampled from 1m in clock-aligned buckets (`time // (tf·60)`): first open, max high, min low,
  last close.
- A higher-frame bar is used only at a 1m close at or after its bucket end, so a forming bar is never read.
- 1H (for the trend) and 15m (for the LRLR gaps) also come from 1m, under the same rule.

**G2. Range and sweep.**
- ATM range = the 1m bars opening 07:00–09:29. This is the same span as the 5m version (07:00 through the end of the
  09:25 5m candle).
- Sweep = the first 1m bar, from 09:30 on, that trades ≥ 1 tick beyond. The one-draw-per-day rule is unchanged.
- Extreme = the lowest 1m low since the sweep (the highest high for shorts). A new extreme restarts the setup.

**G3. The ladder ("highest timeframe IFVG we find").**
- At every 1m close after the sweep, evaluate the frames in order **5m → 3m → 1m** (variant: 5 → 3 → 2 → 1).
- On each frame, evaluate the latest *closed* bar, once.
- The first frame whose V + IFVG signal is complete triggers the entry. That frame is recorded as `trigger_tf`.

**G4. The signal on the trigger frame.** The R3–R5 definitions, computed entirely on that frame:
- extreme bar = the frame bar containing the extreme
- leg origin = the last k=2 fractal swing high on that frame before the extreme bar, confirmed by the evaluated bar,
  searched over 240 minutes
- V within **30 minutes** of the extreme, i.e. N = 30/tf bars: 6 on 5m, 10 on 3m, 15 on 2m, 30 on 1m
- reclaim + 50% of that frame's leg + a displacement candle on that frame (body ≥ 1×ATR14 of that frame, or ≥ 60% of
  its range)
- IFVG = an FVG of that frame created by its leg and closed through by a body on that frame

**G5. Entry, stop, target.**
- Entry: market at the 1m close where the signal completes; the close must be inside the range.
- Stop: the sweep extreme ∓ max(2 ticks, 0.1×ATR14 of the trigger frame). This is still the owner's rule, but the entry
  comes earlier.
- Target: the opposite ATM side (limit 1 tick inside, filled when price reaches the level).
- Skip if the opposite side is < **1.5R** away.
- Positions are managed on 1m bars from the next 1m bar: stop first, flat at 15:55, one trade a day, entries 09:30–11:30
  (1m close ≤ 11:30).

**G6. Confluences** (same 8 keys and thresholds, adapted to the frames):
- `ifvg_big` uses the trigger frame's ATR14.
- `v_fast` = the first 1m close back inside the range within 10 minutes of the extreme. That is the 5m version's
  "2 bars".
- `lrlr`, `tgt_pool` and the first-clear-pool search use the 5m frame and 15m gaps built from 1m, exactly as in the 5m
  version, at the last closed 5m bar.
- SMT and RS use ES 5m bars closed by the entry.

**G7. Sizing.**
- Flat $350 is the default.
- The A/B/C tiers (section E) are reported next to it. They are **recommended only if they rank trades on dev**: avg R
  ordered A > B > C, and Spearman ρ(score, R) > 0 with a one-sided p < 0.10, both on dev, and not reversed on confirm.

**G8. Variants** (complete list, 6 lines; each scored flat and tiered on every covered period, once):

| name | change from `m1_base` |
|---|---|
| `m1_base` | G1–G7: ladder 5→3→1, V within 30 min, X 50%, opposite-side target, skip < 1.5R, 1 trade a day, 09:30–11:30 |
| `m1_rr1` | skip only if the opposite side is < 1.0R |
| `m1_nbars6` | V within 6 bars of the trigger frame (6 min on 1m, 18 on 3m, 30 on 5m): the owner's "6 bars", taken literally |
| `m1_tf5321` | ladder 5→3→2→1 (2m added) |
| `m1_tgt_half` | half at the first clear pool (section C, R8 (c)), runner to the opposite side, BE after the partial |
| `m1_two_a_day` | up to 2 trades a day |

**Selection.**
- The "best" 1m variant is the one with the highest **dev net (flat)**, provided the 1m file covers at least 40 dev
  sessions.
- Otherwise it is the highest net (flat) on the covered 2026 sessions before 2026-08-03, and aug_oct is the check.
- Gallery files:
  - `research/lab/ATM_trades_1m_base.json`
  - `research/lab/ATM_trades_1m_best.json`

  Both hold the 2026 trades, flat sizing, with the tier, `trigger_tf`, and the sweep, leg and IFVG coordinates in `info`.

**Scored once, 2026-10-16 19:25 ET**, on `data/clean/NQ_1m_tv.csv` (209 sessions, every 2026 period fully covered):
- Selection by dev net picked `m1_nbars6`.
- The tier rank test (G7) failed, so the module's default sizing is now flat.
- Results: ATM_REPORT.md section 9.
