# Order flow v5, family "combo": lane A x LIT / ATLAS / regime / day-type context (pre-registered 2026-11-27, BEFORE any result)

PAPER RESEARCH ONLY. Nothing here changes a bot, a size, an arming or an order; no engine/ file is edited. Code (written after
this file): `research/orderflow/v5/combo/core.py` + `run.py`; out-of-sample scorer `oos.py` (frozen variants only).

## What I had seen before writing this (honest)
- Lane A (absorbed level fade at prior-day RTH H/L, Globex H/L, opening-range H/L): 40 taken +0.49R vs 53 skipped -0.31R,
  p 0.0065, newer half weaker (real_verdict.md, lanea-proof). With E5 entry it stays YES (ofexec). Splits (descriptive):
  Globex/ORB good, prior-day weak; shorts better than longs; 32 of 40 taken trades 09:45-10:30.
- v5 "levels" control V0 = lane A through the shared E5 simulator (`v5/levels/core.py`): 63 booked, +0.30R, PF 1.65,
  +$2,648 at 1 micro, halves +0.21 / +0.41R, absorbed-minus-not gap +0.96 / +0.68R. I reuse that exact simulator.
- I have computed NO number for any context filter below (ATLAS trend, LIT armed, S1, VIX, open type) on these days.
- From research/writeups/regime2026: S1 (realized range) is a real ATLAS-only effect in 2021-26; VIX is not the 2026 signature.

## Data
The 51 usable real NQ tick-summary days 2026-09-27..2026-11-26 (`data/pc_days/<day>/of/`, >= 50,000 trades, quote-rule sides).
Context bars: `data/NQ_5m.csv` (TradingView CME NQ1!, futures), extended with the pc_days 5m bars for any time after its last
bar (same prices on these days); `data/NQ_1d.csv` for the daily range (days after it: daily H/L/C built from the 5m frame,
trading day 18:00-17:00 ET); `data/VIX_1d.csv` (CBOE cash close). Futures only.

## The base signal (unchanged lane A, = v5/levels V0)
`levels/core.v0_candidates`: prior-day RTH H/L + Globex H/L (`of_battery.levels`) + opening range 09:30-10:00 H/L from 10:00;
bars opening 09:45-15:00 ET; a closed 5m bar trades >= 1 tick through the level and closes back -> fade; one signal per level per
day. ABSORBED (OF1): zone = footprint within 8 ticks of the bar's pushed extreme, dz x d < 0 and |dz| >= 0.20 x vz.
Every candidate is simulated as if taken by `levels/core.simulate` (the trade rules below).

## Trade (identical for every variant)
- Stop = 1 tick beyond the signal bar's extreme. Size follows the stop (R units; $ shown at 1 micro MNQ, $0.50 a tick).
- Entry E5 (coarse, 5m): decision at the signal bar close; next bar opens at/beyond the level our way -> fill at its open;
  else it trades >= 1 tick through the level -> fill at the level (that bar: stop check only); else stop traded -> no fill;
  else market at the following bar's open + 18 ticks against us. Fill at/beyond the stop -> no trade.
- One target 2R from the fill (lane A's), needs 1 tick through. Stop fill 2 ticks worse (gap open beyond: open - 2 ticks).
  Flat at the close of the 15:55 bar - 2 ticks. Costs $1.90 a micro round trip. R = net $ / (risk x $2), costs in.
- BOOK of a variant = candidates that are ABSORBED **and** pass the variant's context, resolved, one position at a time
  (busy rule of levels/core.book). A candidate the context rejects never blocks.

## The context flags (all known at the signal bar's close; d = fade direction)
- **AT (ATLAS EMA trend, engine/second `ema_pullback` trend "t15_60" = tools/second_ema)**: t15 = sign(EMA21 - EMA50) of the
  15m closes, t60 = same on 1h (clock-aligned HTF bars from the 5m frame, `tools/retail_standalone.htf/to5`: an HTF value
  is used only from the 5m bar on which that HTF bar closed). AT = (t15 == d and t60 == d).
- **LA (LIT armed the same side)**: LIT's own liquidity levels of that trading day (`engine.lit.Market().levels(k)`: session
  boxes, PDH/PDL, PWH/PWL, PMH/PML, gaps, build-ups; live sweep_names = all). For a LONG: some LOW-side level known before
  the signal bar had its FIRST breach (5m low < level, `lit._first_breach` from max(known, day start - 600)) at a bar j with
  i - 23 <= j <= i (LIT's sweep_win 24 bars), and (highest such swept level - lowest low of bars j..i) >= 0.5 x ATR14(5m) at i
  (LIT's live depth 0.5). Mirror for SHORT (high-side levels, highs). LA = that is true.
- **S1 (wide-range regime, regime2026 S1_RV)**: rng = (high - low) / close per daily session; rv20 = 20-session mean; ON when
  the previous session's rv20 > the previous session's trailing 252-session median of rv20 (min 120 sessions).
- **VX (high VIX, regime2026 S2_VIX)**: the last VIX cash close before the session day > the trailing 252-session median of
  that same series (min 120).
- **IO (day type: inside-open / balance open)**: the 09:30 ET bar's open is strictly inside the prior usable day's RTH
  (09:30-16:00) high-low (lane A's pdh / pdl). Fades are a balance-day trade (Dalton): the hypothesis is IO helps.

## Variants (6, fixed; the hypothesis for each = the context HELPS lane A)
| id | book = absorbed AND |
|---|---|
| C1 | AT: only in the direction of the ATLAS 15m + 1h EMA trend |
| C2 | LA: only when LIT is armed (swept, depth >= 0.5 ATR, within 24 bars) on the same side |
| C3 | S1: only on wide-range regime days |
| C4 | VX: only on high-VIX days |
| C5 | IO: only on inside-open (balance) days |
| C6 | vote: at least 3 of AT, LA, S1, VX, IO |
Control C0 = lane A alone (absorbed, no context) through the same code: printed, NOT a variant, not in Holm, not frozen.

## Scores (per variant)
trades (booked), trades/week (= n / (51 days / 5)), win %, mean R, PF ($), net $ at 1 micro, $/month (net / (51 / 21)),
max DD $ (booked, by exit time), halves by day (older 26 days / newer 25 days): booked mean R and the context gap.
**Context gap** = mean R (as if taken) of resolved ABSORBED candidates with the flag true minus those with it false.
**Placebo p** (one-sided, 5,000 shuffles, p = (hits + 1) / 5,001): shuffle the flag over the resolved absorbed candidates.
Day-level flags (S1, VX, IO) are shuffled at the DAY level (the day -> flag map permuted over the days that hold absorbed
candidates); candidate-level flags (AT, LA, vote) at the candidate level. **Holm-Bonferroni over the 6 placebo p.**

## Pass bar (fixed now)
- **YES-candidate**: booked >= 20, net $ > 0, PF >= 1.20, booked mean R > 0 in BOTH halves, context gap > 0 in BOTH halves,
  placebo p < 0.10 AND Holm-adjusted p < 0.10.
- **weak**: booked >= 20, net $ > 0, gap > 0 overall, raw p < 0.20, but fails another YES test.
- **TOO FEW**: booked < 20 (or a flag that is the same for every absorbed candidate: no test). **NO**: everything else.
- A YES is only a reason to log the flag forward next to lane A (paper). The strategy protocol (2021-25 too) cannot be met
  with tick days; no engine change follows.

## Freeze rule (fixed now)
`frozen.json` = the best 2 variants by (verdict YES > weak > NO > TOO FEW, then Holm p, then net $), even if weak / NO.
`oos.py` scores them on every usable pc_days day NOT in the 51 (same code, same table, Holm over the 2).
