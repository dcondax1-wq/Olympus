---
title: BLITZ review (2026-11-18 night) - today's rule measured honestly, why its trades win and lose, 8 new exit ideas (0 pass); verdict - keep it on paper, no account of its own; its only paying use is next to Zlarior on a funded account
family: other
date: 2026-11-18
status: rejected (no change) - 0 of 8 pre-declared exit ideas pass; BLITZ stays a hidden paper shadow; no Decide proposal
summary: Owner - "I expect all of our strategies to be better", "high win rate / profit". Today's BLITZ (engine/blitz.py v2 as account C, never opposite Zlarior / ATLAS), $150 a trade, $1.90 a micro + 1 tick each way - 2026 Jan-Jun 8.5 trades a week, win 56.7%, PF 1.70, +$963 a month, max DD -$1,152; Jul-Oct 6.8 a week, 56.6%, PF 1.62, +$667, -$815; 2021-25 (5m) 8.6 a week, 50.1%, PF 1.05, +$73, -$5,512 (2024 -$200 a month). One more tick each way - $921 / $635 / $18 a month. Own 25K eval at the live size - 2-week pass / fail 47.9 / 23.5, 36.2 / 21.7, 24.7 / 48.4; the whole 25K slot +$286 / +$52 / -$39 a month. Why - the 30-minute clock exits are the whole profit (70% winners, +0.42R), stop-outs give it back (-0.96R); a trade not at +0.5R by minute 10 ends near 0R in 2026 (-0.06R / -0.02R) and -0.18R in 2021-25, one at +0.5R makes +0.5-0.7R; later band breaks beat first breaks in all 3 spans; no check time, side or VIX band is bad in all 3. Tested (written before the run) - minute-10 / 15 no-follow-through cuts, back-inside-the-band exits, breakeven at +0.5R, cut + 45-minute hold: 0 of 8 pass (the H1 pick, out at minute 10 if never +0.25R, +$22 H1 but -$292 a month Jul-Oct, eval 2-week fails 21.7 -> 40.6%); every idea LOWERS the win rate (35-53% vs 57%). Verdict - stay paper; MFFU's Builder 25K slots are both taken (ATLAS funded + Zlarior 25K #2) and its own 25K pays ~$0 outside Jan-Jun anyway; revisit as an add-on on Zlarior's funded 50K once it is funded.
runs: none (research/scalp/blitz_review.json, blitz_review_tf1.json, blitz_review_tf5.json); tools/blitz_review.py; ZEUS Lab ids blitz_chk10_loss ... blitz_band_in10_h45 (kind blitz_idea, Rejected)
---

## For the owner (one minute)

**BLITZ makes money in 2026 but almost nothing in a normal year, and none of tonight's 8 ideas made it better. Keep it on
paper; do not buy it an account.**

| What | Result |
|---|---|
| BLITZ 2026 Jan-Jun / Jul-Oct, $150 a trade, costs in | **+$963 / +$667 a month**, win 57%, PF 1.70 / 1.62 |
| BLITZ 2021-25 (5 years, same rule) | **+$73 a month** (PF 1.05); 2024 lost $200 a month; one more tick of slippage = +$18 a month |
| Its own Builder 25K (buy, pass, payouts, re-buy) | **+$286 / +$52 / -$39 a month** (Jan-Jun / Jul-Oct / 2021-25) |
| 8 new exit ideas (cut early, leave back inside the band, breakeven) | **0 pass**: each one lowers the win rate (35-53% vs 57%) and loses money in Jan-Jun or Jul-Oct |
| Can it go live? | **No account for it**: both MFFU Builder 25K slots are used (ATLAS funded + Zlarior 25K #2), and alone it pays ~$0 outside Jan-Jun |
| Its one paying use | Next to Zlarior on a funded 50K while Zlarior is flat (+$290-300 a month in 2026, +$16 in 2021-25; scalp-na-mffu.md). Needs Zlarior's 50K funded first (about $3,807 to go) and new code |

Next (nothing changes tonight):
1. Nothing to do. BLITZ keeps running hidden on paper.
2. When Zlarior's 50K passes, ask Claude to re-check "BLITZ next to Zlarior on the funded 50K" on the newest data.
3. Re-check this review on new bars: `python -X utf8 tools/blitz_review.py run --tf 1` (then `--tf 5`, `merge`).

## 1. Today's rule, measured honestly

The rule is engine/blitz.py VERSION 2 (BLITZ_STRATEGY.md): the 14-day noise band, yesterday's range >= 0.8 x its 14-day mean,
10 checks 11:00-15:30, market entry at the next 1m open, stop 1.5 x the 5m ATR (median 60 points in 2026, 39 in 2021-25),
trail 1.5R behind the best price after +1R, out after 30 minutes or at 15:55, at most 6 a day, -3R day stop; as account C
(never opposite Zlarior / ATLAS, closed first at their opposite entry). Costs: $1.90 a micro round trip, entry +1 tick,
every exit -1 tick (1 tick each way). $150 a trade = at least 1 micro. 2026 on CME NQ1! 1m bars (to 2026-10-16), 2021-25
(2021-11 .. 2025-12) on 5m bars (no 1m history exists before 2026).

| Span | Trades | / week | Weeks with 2+ | Win % | Avg R | PF | Net | **$ a month** | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026 Jan-Jun | 217 | 8.5 | 89% | 56.7 | +0.165 | 1.70 | +$5,873 | **+$963** | -$1,152 |
| 2026 Jul-Oct | 106 | 6.8 | 75% | 56.6 | +0.200 | 1.62 | +$2,478 | **+$667** | -$815 |
| 2021-25 (5m) | 1,841 | 8.6 | 80% | 50.1 | +0.013 | 1.05 | +$3,765 | **+$73** | -$5,512 |
| one MORE tick each way (2 per side) | | | | | | 1.66 / 1.58 / 1.01 | | $921 / $635 / **$18** | -$1,193 / -$831 / -$6,733 |
| BLITZ alone (no anti-hedge rule) | 221 / 109 / 1,869 | | | | | 1.63 / 1.49 / 1.06 | | $912 / $577 / $89 | |

- By year (5m, account C): 2022 PF 1.17 (+$244 a month), 2023 1.09 (+$131), **2024 0.88 (-$200)**, 2025 1.08 (+$140).
- The 5m replay reads BLITZ lower than the live 1m rule: 2026 on 5m is PF 1.48 / 1.50 ($830 / $571 a month) against 1.70 /
  1.62 on 1m. So a 1m 2021-25 would probably look a little better than PF 1.05, but not like 2026.
- **Own MFFU Builder 25K at the live size** (40% of the room, the full room from eval session 5, later-break x0.5 / x1.75;
  funded 1 micro <= $150, +$400 day stop; 6-month Monte Carlo, net of every $63 eval):

| 25K | Jan-Jun | Jul-Oct | 2021-25 |
|---|---:|---:|---:|
| 2-week pass / fail | 47.9 / 23.5% | 36.2 / 21.7% | 24.7 / 48.4% |
| Median sessions to pass | 7 | 5 | 5 |
| **Whole slot, $ a month to you** | **+$286** | **+$52** | **-$39** |
| Chance a 6-month slot loses money | 7.6% | 45.9% | 86.0% |

**By check time, side, break and VIX** (at $150 a trade; n / PF / net):

| | Jan-Jun 2026 | Jul-Oct 2026 | 2021-25 |
|---|---|---|---|
| 11:00 | 32 / 2.79 / +$1,989 | 22 / 1.12 / +$142 | 297 / 0.83 / -$2,523 |
| 11:30 | 13 / 0.98 / -$11 | 4 / 0.05 / -$307 | 114 / 1.17 / +$722 |
| 12:00 | 27 / 2.33 / +$1,330 | 16 / 0.49 / -$449 | 232 / 0.87 / -$1,227 |
| 12:30 | 16 / 1.44 / +$235 | 6 / 3.94 / +$360 | 143 / 0.97 / -$200 |
| 13:00 | 24 / 1.53 / +$464 | 12 / 4.76 / +$908 | 205 / 1.00 / -$4 |
| 13:30 | 16 / 0.92 / -$60 | 6 / 0.17 / -$443 | 167 / 1.15 / +$1,149 |
| 14:00 | 22 / 1.29 / +$275 | 12 / 2.32 / +$399 | 186 / 1.57 / +$3,643 |
| 14:30 | 19 / 1.35 / +$261 | 7 / all won / +$675 | 160 / 0.89 / -$831 |
| 15:00 | 23 / 3.96 / +$1,464 | 12 / 3.10 / +$629 | 193 / 1.45 / +$3,531 |
| 15:30 | 25 / 0.95 / -$74 | 9 / 4.85 / +$564 | 144 / 0.93 / -$496 |
| long / short | 144 / 1.47 / +$2,260 · 73 / 2.01 / +$3,612 | 58 / 1.83 / +$1,393 · 48 / 1.46 / +$1,086 | 972 / 1.14 / +$5,496 · 869 / 0.96 / -$1,731 |
| first / later break | 61 / 1.56 / +$1,487 · 156 / 1.76 / +$4,385 | 30 / 1.74 / +$948 · 76 / 1.56 / +$1,530 | 509 / 0.98 / -$510 · 1,332 / 1.07 / +$4,275 |
| VIX low / mid / high | 69 / 2.61 / +$3,209 · 76 / 1.30 / +$1,133 · 72 / 1.58 / +$1,531 | 86 / 1.89 / +$2,326 · 15 / 0.93 / -$84 · 5 / 2.80 / +$237 | 610 / 0.94 / -$1,484 · 614 / 1.09 / +$2,119 · 617 / 1.11 / +$3,130 |

(VIX terciles = the prior close, cut on Jan-Jun 2026 at 17.8 / 19.3 and on 2021-25 at 16.5 / 20.8.)

- **No check time is bad in all three spans**, and no side or VIX band is either (shorts lose in 2021-25 but were the best
  side in Jan-Jun; low VIX is the best band in 2026 and the worst in 2021-25). With 10 times x 3 spans, patterns like 13:30
  (red in both 2026 halves, green in 2021-25) are what chance gives; the anatomy night's chance check on BLITZ's hour found
  the same (7 consistent buckets of 66 vs 14.2 by chance).
- **Later breaks beat first breaks in all three spans** (avg R +0.203 vs +0.066, +0.209 vs +0.178, +0.018 vs -0.001): this is
  the reason for the later-break eval size already on (owner 2026-10-31). Nothing new to add.

## 2. Why BLITZ's trades lose and win (BLITZ-only facts; the general anatomy is win-loss-anatomy-2026-11-18.md)

| | Jan-Jun 2026 | Jul-Oct 2026 | 2021-25 |
|---|---|---|---|
| 30-minute clock exits (n / win % / avg R / net) | 157 / 70% / +0.42R / **+$9,856** | 80 / 70% / +0.41R / **+$4,224** | 1,152 / 71% / +0.43R / **+$60,993** |
| Stop-outs (first stop) | 43 / 0% / -0.96R / **-$5,683** | 17 / 0% / -0.83R / **-$2,318** | 550 / 0% / -0.96R / **-$64,967** |
| 15:55 / trail / hedge exits | 17 trades, +$1,700 | 9 trades, +$572 | 139 trades, +$7,739 |
| Not at +0.5R by minute 10 | 118 / 44% / **-0.06R** / -$1,475 | 58 / 47% / **-0.02R** / -$506 | 1,033 / 41% / **-0.18R** / -$23,660 |
| At +0.5R or more by minute 10 | 84 / 85% / **+0.68R** / +$9,125 | 45 / 73% / **+0.57R** / +$3,410 | 665 / 74% / **+0.52R** / +$43,741 |
| Lost $ from trades whose best point stayed under +0.5R | 77% of $8,417 | 81% of $4,016 | 81% of $80,023 |
| Winners: best point / kept / given back (median) | +1.02R / +0.58R / 0.33R | +1.00R / +0.70R / 0.28R | +0.96R / +0.61R / 0.28R |

In plain words:
- **BLITZ wins by riding a band break for 30 minutes.** The clock exit is the profit (7 of 10 clock exits win); the full stop
  (about 60 points) is the cost. In 2021-25 the two are almost equal (+$61.0k vs -$65.0k), which is the whole "breaks even"
  story: about 30% of trades hit the full stop there (550 of 1,841) against 19% in 2026 (60 of 323).
- **The first 10 minutes tell you a lot, but cutting there does not pay.** Trades that reach +0.5R by minute 10 make
  +0.5-0.7R; the rest end near zero in 2026 (-0.06R / -0.02R) because many of them still come back by the 30-minute clock.
  Cutting them at minute 10 locks in their minute-10 loss and gives up those comebacks (section 3).
- **The winners give back about 0.3R** from their best point (the 1.5R trail after +1R rarely acts: 2 trail exits in Jan-Jun).
  Tighter trails were tested before (4,800 exits, scalp-na-mffu.md) and lose.
- **Trend days vs chop:** the anatomy night found BLITZ loses on two-way days (2021-25 -$11,847 on chop days) and nothing at
  the entry separates them (no bucket beats chance). The yesterday's-range filter is the one day filter that ever held.

## 3. Tested tonight: 8 exit ideas, written down before the first run

Motivation: the anatomy's "72% of BLITZ's lost $ never reached +0.5R". Each idea keeps BLITZ's entries, stop, size and the
30-minute clock (unless it says 45) and only changes the exit. Pick on Jan-Jun 2026 (most $ a month at $150, must beat
today), check on Jul-Oct and 2021-25 (both must beat today), costs in, still a scalper (>= 5 a week), the 25K eval's 2-week
fails not up, daily sign-flip placebo under the ZEUS Lab's many-tests bar (274 cells: p <= 0.00073).

| Idea | Jan-Jun $/mo (today $963) | Jul-Oct (today $667) | 2021-25 (today $73) | Win % H1 / H2 / 21-25 (today 57 / 57 / 50) | 25K 2-week fails H1 / H2 (today 23.5 / 21.7) | Verdict |
|---|---:|---:|---:|---|---|---|
| out at minute 10 if in a loss and never +0.5R | $855 | $775 | $102 | 48 / 48 / 39 | 25.2 / 37.7 | fails H1 |
| out at minute 15 if in a loss and never +0.5R | $747 | $739 | $12 | 49 / 50 / 41 | 33.6 / 21.7 | fails H1, 2021-25 |
| **out at minute 10 if never +0.25R (H1 pick)** | **$985** | **$375** | $99 | 51 / 52 / 44 | 25.2 / 40.6 | **fails Jul-Oct (-$292 a month)** |
| out on a 1m close back inside the noise band | $746 | $361 | $41 | 49 / 49 / 46 | 37.0 / 37.7 | fails all three |
| back inside the band, from minute 10 | $772 | $671 | $47 | 52 / 53 / 47 | 37.0 / 36.2 | fails H1, 2021-25 |
| stop to breakeven at +0.5R | $545 | $207 | $66 | 39 / 40 / 35 | 40.3 / 20.3 | fails all three |
| minute-15 cut, survivors held 45 minutes | $723 | $829 | $105 | 45 / 47 / 39 | 28.6 / 23.2 | fails H1 |
| back inside the band from minute 10, held 45 minutes | $719 | $811 | $101 | 51 / 50 / 45 | 44.5 / 31.9 | fails H1 |

- **0 of 8 pass.** The only one better in Jan-Jun (+$22 a month) loses $292 a month in Jul-Oct and nearly doubles the
  Jul-Oct 2-week eval fails. Its Jan-Jun gain is luck-sized (sign-flip p 0.44).
- **None raises the win rate.** Early cuts and breakeven turn would-be small winners and comebacks into small losers: win
  rate 35-53% against today's 57%. For BLITZ, "high win rate" comes from the 30-minute clock, not from cutting.
- The cut + 45-minute versions make more in Jul-Oct (+$144-162) and 2021-25 (+$28-32) but less in Jan-Jun (-$240) and more
  eval fails in Jan-Jun: the same "helps a weak half, hurts the strong half" seen in every BLITZ exit search since October.
- All 8 are in the ZEUS Lab as kind `blitz_idea` (bot BLITZ, Rejected; the Lab page leaves them out while BLITZ is hidden).

## 4. Verdict: can BLITZ go live?

- **Not on its own account.** MFFU's limits (STATE.md) allow Builder 1 x 50K + 2 x 25K funded; the 2 x 25K are ATLAS's funded 25K and Zlarior's
  25K #2. Even with a free slot, its own 25K pays +$286 / +$52 / -$39 a month (Jan-Jun / Jul-Oct / 2021-25) and in Jul-Oct
  random directions on the same signals made about the same slot money (blitz-25k.md): an eval lottery, not an edge.
  BLITZ alone on a Rapid EOD 50K at $300 a trade almost never reaches the $3,000 target (0.1% pass in 60 sessions,
  rule-native-2026-11-17.md).
- **As an add-on next to Zlarior on a funded account: the one paying use, later.** On Zlarior's funded Builder 50K, BLITZ
  only while Zlarior is flat added +$301 / +$290 a month in 2026 and +$16 in 2021-25 (scalp-na-mffu.md); on the Rapid EOD
  (at most 3 a day, $300) +$822 / +$313 but 2021-25 evals fail twice as often (paper lead, rule-native-2026-11-17.md). Both
  need Zlarior's account funded first and engine work (a second strategy on Zlarior's account, up to 6 a day, Zlarior first).
  MFFU's Rapid funded news ban (2 minutes around Tier-1 news) would also block BLITZ's 14:00 check on FOMC days.
- **Not retired either.** Its 2026 edge is real (random directions lose, blitz-25k.md p 0.02-0.05) and it costs nothing on
  paper. It is a 2026-regime bet: one more tick of slippage takes 2021-25 to +$18 a month, and 2024 lost money.
- **So: stay hidden on paper.** No Decide card proposal (nothing passed).

## 5. Honesty notes

- The executor in tools/blitz_review.py replays the research executor (tools/blitz25k_lib._sim, the one engine/blitz.py was
  checked against, 330/330) trade for trade: 2026 1m 323 of 323 identical, 5m 2,199 of 2,202 identical; the headline table and
  the 25K eval / slot rows equal BLITZ_STRATEGY.md's (its by-year line is BLITZ alone; the by-year line here is account C).
- The ideas were written into the tool before the first run; nothing was tuned after seeing results.
- 2021-25 is the same rule on 5m bars (minute 10 = the 2nd 5m bar, the band check on 5m closes): coarser, and it reads
  BLITZ lower than 1m (2026 on 5m PF 1.48 / 1.50 vs 1.70 / 1.62).
- Jul-Oct is 78 sessions (106 trades): a 2-week pass / fail rate there moves about +/-10 points on noise alone.
- BLITZ's live paper ledger (since 2026-10-28) lives on the PC, which has not reported since 2026-11-07: there are no paper
  trades to read here.
- Data ends 2026-10-16 (TradingView CME NQ1!, futures only).

## Files

- `tools/blitz_review.py` (`run --tf 1`, `run --tf 5`, `merge`, `register`; `lab_result` = the ZEUS Lab runner).
- `research/scalp/blitz_review.json` (verdict + all three spans), `blitz_review_tf1.json`, `blitz_review_tf5.json`.
- `tools/zeus_lab.py`: kind `blitz_idea` (bot `blitz`), and the page never shows a hidden bot's rows.
