# ICT lab round 2 (2026-11-25): design + pre-registration (written BEFORE the run)

Lead 2026-11-25 (owner: "just do more"): more concepts from online, every test view, the real engine for any card.
Same data, harness, views and luck count as round 1 (`research/ictlab/DESIGN.md` sections 2 and 5). Paper research only.
Code `research/ictlab/ict_lab2.py` (re-uses `ict_lab.py` + `tools/popular_ict.py`). 5m bars, ET clock, MNQ, costs in,
one trade a day max, LIT sizing for standalones, stop 1 tick beyond the structural extreme, 2R unless a target is named.
Prior tests (TESTED_AND_REJECTED): Turtle Soup + Unicorn (2026-11-23, rejected), Mech/IFVG (published models, PF ~1),
order blocks as LIT confluences (2026-10-18, chance), VWAP 2SD reversion + ORB 30 textbook versions (rejected), RSI /
BVC divergence (refuted). Re-run here only for the new views and the new pairings.

## 1. Concepts (definition as taught + source) and the standalone rule

| id | concept / source | standalone rule |
|---|---|---|
| S_MMBM | ICT Market Maker Buy / Sell Model (2016-17 mentorship, "MMxM"): price leaves an original consolidation, runs sell-side liquidity, smart-money reversal (MSS), returns to the consolidation | 08:30-12:00: price trades below the PDL (MMBM; above the PDH = MMSM); after the run, the first 5m close above the highest high of the 6 bars before the run's low = MSS -> enter next bar; stop 1 tick beyond the run's extreme; **target = the 00:00-08:25 high (low)** = the consolidation; skip if < 1R or stop > 80 pts |
| S_TURTLE | Turtle Soup (Connors & Raschke, *Street Smarts* 1995; ICT) | `popular_ict.s_turtle` (20-day low/high false break, stop order back through it), 2R |
| S_BREAKER | ICT breaker block (2016-17 mentorship) | 09:30-12:00, confirmed 5m pivots only (known 2 bars after): pivot high A, then pivot low C below every low of the 12 bars before A (the sweep), then a close above A's high = MSS. Breaker = the last up-close candle in the 3 bars up to A. Limit at its high, live 12 bars, stop 1 tick under C. Mirror for shorts. 2R |
| S_MITIG | ICT mitigation block (same source; the no-sweep twin of the breaker) | same as S_BREAKER but C is a HIGHER low (no sweep, a failure swing) |
| S_OB | ICT order block, strict (2016-17 mentorship) | 09:30-12:00: displacement candle (body >= 2x the median body of the prior 20) that leaves an FVG and closes above the last confirmed pivot high; OB = the last down-close candle in the 5 before it. Limit at the OB high from the FVG's close, live 12 bars, stop 1 tick under the OB low. Mirror. 2R |
| S_UNICORN | ICT Unicorn (breaker + FVG, 2022-23 YouTube) | `popular_ict.s_unicorn`, 2R |
| S_IFVG | Inversion FVG (ICT 2023) | 09:30-12:00: an FVG forms; a later 5m close (within 24 bars) through its far side inverts it; limit at the gap edge in the new direction, live 12 bars, stop 1 tick beyond the extreme since the gap. 2R |
| S_BPR | Balanced Price Range (ICT 2022-23: overlapping opposite FVGs) | a bullish and a bearish FVG within 12 bars whose ranges overlap; direction = the later one; limit at the overlap's near edge, live 12 bars, stop 1 tick beyond the formation's extreme. 2R |
| S_VOID | Liquidity void (ICT: one-sided delivery gets rebalanced) | 09:30-12:00: 3 consecutive same-colour candles, each low above the prior low (up) / high below (down), total move >= 2x ATR(14, 5m) -> fade at the next open, **target = the void's 50%**, stop 1 tick beyond the void extreme; skip < 1R |
| S_W_TUE | ICT weekly profile: classic expansion / low (high) of the week on Tuesday (ICT 2016-17 "weekly profiles") | weekly bias = prior week closed in its upper half -> long (lower -> short). Tuesday 02:00-12:00: sweep of Monday's low (bias long) and a 5m close back above within 12 bars -> long, stop 1 tick under the sweep. 2R |
| S_W_WED | Weekly profile: Wednesday reversal | Wednesday 02:00-12:00, only when Mon-Tue went against the bias (Tue close below Mon open for a long bias): sweep of the Mon-Tue low and a close back -> long (bias side only). 2R |
| S_W_THU | Weekly profile: consolidation reversal | Thursday 02:00-12:00, only when the Mon-Wed range <= 60% of the prior week's range: sweep of the Mon-Wed high or low and a close back inside -> reverse. 2R |
| S_DOR | ICT daily open (midnight open) retracement in the NY session (2022 mentorship) | daily bias = PDH/PDL draw (round 1); at 08:30 price on the bias side of the 00:00 open -> limit at the 00:00 open, live 08:30-11:00, stop 1 tick beyond the 00:00-08:25 extreme (skip if it is not beyond the open, or > 60 pts). 2R |
| S_WPO3 | Power of 3 on the weekly (ICT: weekly open, manipulation Mon-Tue, distribution) | Tue-Thu 09:30-12:00: the week traded below the weekly open (Sunday 18:00) and the weekly bias is long -> first 5m close back above the weekly open -> long, stop 1 tick under the week's low (skip > 150 pts). Mirror. 2R |
| S_WYCKOFF | Wyckoff spring / upthrust (Wyckoff; Pruden, *The Three Skills of Top Trading*) | box = the prior 3 sessions' high / low. 09:30-15:00: a 5m low under the box low on volume <= its 20-bar average, a close back inside within 3 bars -> long, stop 1 tick under the spring. Upthrust mirror. 2R |
| S_MP80 | Market Profile 80% rule (Dalton, *Mind over Markets*) | prior RTH value area (70% of volume around the POC, 5-pt bins, 09:30-16:00): the 09:30 open outside it; two consecutive 30-min brackets close inside -> enter toward the far edge, **target = the far VA edge**, stop 1 tick beyond today's extreme on the open's side; until 13:00; skip < 1R |
| S_VAFADE | VAH / VAL fades (Market Profile) | open inside the prior VA: the first touch of VAH -> limit short at VAH, stop VAH + 25% of the VA width, **target POC**; VAL mirror; 09:35-15:00 |
| S_VWAPSD | VWAP 2-SD band mean reversion (textbook) | RTH VWAP from 09:30 with volume-weighted SD: 10:00-15:00 a 5m close beyond +-2 SD, the next close back inside -> fade at the next open, stop 1 tick beyond the extreme, **target VWAP**, skip < 1R |
| S_ORBV | Opening range breakout with a volume filter (Crabel / textbook) | OR = 09:30-09:55; 10:00-12:00 the first close beyond the OR on volume >= 1.5x the OR bars' mean -> enter next open, stop 1 tick beyond the OR midpoint. 2R |
| S_DIVRSI / S_DIVMACD | RSI(14) / MACD(12,26,9) histogram divergence at a level (textbook) | levels = PDH / PDL and the 00:00-09:25 high / low; 09:30-12:00: a bar takes a level with a higher high than the highest high of 6-36 bars earlier while RSI (MACD hist) is lower than there; a close back through the level within 6 bars -> reverse, stop 1 tick beyond the extreme. 2R |
| S_ROUND | Round-number magnet (100-pt levels) | 09:30: the nearest 100-pt level 15-60 pts away and untouched since 00:00 -> trade toward it at the open, **target = the level**, stop 1 tick beyond the 00:00-09:25 extreme; skip < 1R |
| S_PWFADE / S_PWBRK | Prior-week high / low tests | fade: a sweep of PWH / PWL and a close back inside within 12 bars, 09:30-15:00. break: 2 consecutive 5m closes beyond PWH / PWL (09:30-14:00) -> with the break, stop 1 tick beyond those 2 bars. 2R |

## 2. Confluences on LIT and ATLAS (eval-safe first)

Modes: **HALF** = x0.5 when the trade does NOT have it (eval-safe, the main mode), **ONLY** = skip without it. No x1.5.
At the entry bar, trade side aligned:
F_OB (inside an active strict OB zone, last 36 bars), F_BRK (inside a breaker zone, last 36 bars), F_FVG (inside an unfilled
same-side FVG, last 24 bars), F_IFVG (inside an inverted FVG, last 36 bars), F_WEEK (side = weekly bias), F_WPO3 (long below /
short above the weekly open), F_DOR (side = daily bias and within 10 pts of / beyond the 00:00 open on the buy side),
F_VA (long below prior VAL / short above VAH), F_POC (long below / short above the prior POC), F_VWAP (RTH: long below
VWAP-1SD / short above +1SD; outside RTH = no filter), F_DIV (RSI divergence of the trade's side in the last 12 bars),
F_ROUND (a 100-pt level within 40 pts ahead), F_PW (the trade's extreme is beyond PWL / PWH), F_WYK (the extreme bar of the last
12 had volume <= its 20-bar average), F_ORB (after 10:00: long above / short below the 09:30-09:55 range; else no filter),
F_TURTLE (the extreme is beyond the 20-day low / high).
**Pairs:** every pair of these 16 in HALF mode (x0.5 unless the trade has BOTH) on LIT and ATLAS = 240 pre-listed tries.
**Standalone gates:** every standalone x {weekly bias, daily bias (PDH/PDL draw), True Day Open side} (round-1 features).
All counted in the luck tally (placebos: random x0.5 / random keep sets of the same size; sign-flip for standalones).

## 3. True Day Open re-test (funded preset only)

LIT x0.5 against the 00:00 open (round-1 form A) on FUNDED accounts only, real engine (`research/plans/rank.py` funded
classes, 1,000 x 126-session funded paths per span, H1 / H2 / 2021-25 / 2025): Builder 50K, Builder 25K, Rapid EOD 25K;
payouts $ to the owner, payouts count, lost %, first payout.

## 4. Card rule (unchanged) and the real engine
Card = better in >= 4 of 5 years (and vs random) AND walk-forward positive AND placebo p < 0.05 AND the house split rule
(LIT: 2026 H1 and H2 better; ATLAS / standalone: both 2026 halves and 2021-25), 2-4 trades/week for standalones.
Every card then gets the round-1 proof (`research/ictlab/proof.py` style) before it is called one.
