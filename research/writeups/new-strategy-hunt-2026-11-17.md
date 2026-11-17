---
title: New-strategy hunt - a third NQ strategy for more winning days (lunch squeeze, PM continuation, value-area failed auction, 80% rule, London extension fade) - nothing passes
family: other
date: 2026-11-17
status: rejected - 0 of 354 cells hold in 2026 H1, H2, 2025 and 2021-24 (coin-flip directions give 3.7); no H1 pick exists at 2-4 trades a week; nothing built, nothing live changed
summary: Lead order 2026-11-17 - MFFU payouts need many winning days (Rapid 30% best-day rule, Builder funded 50% consistency) and LIT trades ~2.5 times a week, so find a third strategy that wins on days LIT and ATLAS don't. Four new families on CME NQ1! 5m RTH (costs in, stops 1 tick beyond structure, $500 a trade, one trade a day), 354 cells counted, hypotheses fixed before the run - LSQ lunch-range squeeze -> PM break (with / against / any AM trend; covers the 14:00-15:30 continuation idea), FAV failed auction at the prior session's value-area edge (volume profile from 5m bars), D80 Dalton's 80% rule, LXF London 02:00 -> 09:30 extension fade at the NY open. The first pullback after a 2-sigma opening drive was discarded as already covered (hq-continuation, BLITZ opening drive). Result - 0 cells hold in all four spans vs 3.7 with coin-flip directions; only 24 cells trade 2-4 a week in H1 and none of them has PF >= 1.2 there, so there is no H1 pick. Correlation with LIT is ~0 everywhere (-0.11..+0.12 daily), but none makes money that holds; an own Builder 50K at $400 a trade passes 0% within 40 sessions. The PM continuation WITH the AM trend is positive in 71 of 72 cells in 2021-24 and 0 of 72 in 2026 H1 (the E2 "late break" pattern again). Nothing adopted.
runs: (no rl runs) research/second/new_hunt.json, tools/new_hunt.py
---

## For the owner (one minute)

| What | Result |
|---|---|
| Ideas tested | 4 new families, 354 versions (lunch squeeze, afternoon trend, value-area fakeout, London fade) |
| Hold in 2026 H1 + H2 + 2025 + 2021-24 | **0** (luck alone gives about 4) |
| 2-4 trades a week and good in Jan-Jun | **none**, so nothing to check on Jul-Oct |
| Overlap with LIT's days | about 0 (they'd win on different days) but they don't make money |
| Own 50K eval at $400 a trade | 0% pass in 2 months (they make $0-450 a month at best, and lose some years) |
| Verdict | **Nothing passes.** Keep LIT + ATLAS. No new account. |

## What was asked

MFFU's payout rules reward many winning days. LIT makes most of its money on a few big days (~2.5 trades a week), ATLAS adds
some. A third strategy that wins on OTHER days would make every eval and payout faster. Hard rules: 2-4 trades a week,
costs in, stops beyond structure, pick on 2026 Jan-Jun, check on Jul-Oct, show 2021-25, count every cell, report the
correlation with LIT's daily P&L (`research/lab/backtest_live.json`).

## What was NOT redone (already on the "Tested and rejected" list)

- First pullback after a 2-sigma opening drive: `hq-continuation.md` (first pullback in a London / NY leg of k ATR into its
  FVG / OB / 50%, 186,624 versions), BLITZ opening drive (`blitz-25k.md`), the 2-sigma excursion tilt (`atlas-blitz-edge`).
- Plain ORB, gap fade (incl. failed opening drive), VWAP fades, NR7 / NR4, the "late break" at a new day high after 14:00,
  the last-half-hour reversal (`nq-new-strategies-2026-11-13.md`, `public-strategies-2026-11-17.md`).
- Volume profile as a LIT size filter (`vwap-volume-profile.md`). Its edges as their OWN setup were not tested before: done here.

## The four families (hypotheses fixed before the run, `tools/new_hunt.py` docstring)

All on CME NQ1! 5m RTH (back-adjusted TradingView export, 2021-11 -> 2026-10-16), the `tools/div_search.py` executor: signal
on a 5m close, entry at the next open + 1 tick, stop fills at the stop (or the open through it) - 1 tick, a target needs a
trade-through, stop + target in one bar = stop, flat 15:55. $1.90 a micro. $500 risk a trade, micros = floor(500 / (stop x $2
+ $1.90)), 1-40 (size follows the stop). Stops under 8 pts widened to 8. One trade a day per cell.

1. **LSQ lunch squeeze -> PM break (216 cells; covers ideas 1 and 2).** Lunch box 11:00-13:00 / 11:30-13:30 / 12:00-14:00.
   Squeeze gate: any / box <= 50% of the AM range / box <= 80% of its own 20-day mean. First 5m close beyond the box from
   the box end to 15:00. Direction: any / only WITH the AM move (>= 0.5 sigma, = the 14:00-15:30 continuation) / only
   AGAINST it. Stop 1 tick beyond the box's far side or its middle. Target 1.5R / 2R / 3R / the 15:55 close.
2. **FAV failed auction at the prior value-area edge (72 cells).** Prior RTH session's volume profile from its 5m bars (each
   bar's volume spread over its 1-pt bins), POC, VAH / VAL = 70% contiguous around the POC. A probe beyond VAH (VAL) by 0 or
   0.1 x the 14-day range that closes back inside within 1 / 3 / 6 bars = excess -> fade. Stop 1 tick beyond the probe
   extreme. Window to 11:30 / 15:00; any open / open inside value. Target POC / the far edge (needs >= 1R) / 2R.
3. **D80 Dalton's 80% rule (12 cells).** Open outside the prior value area, then 1 / 2 half-hour closes back inside ->
   toward the far edge / POC / 2R. Stop 1 tick beyond the day's extreme on the outside side. Entries to 12:00 / 15:00.
4. **LXF London extension fade (54 cells).** 02:00 -> 09:30 move >= 1.0 / 1.5 / 2.0 x its 20-day mean size. Trigger: a 5m
   close beyond the 09:30-09:45 or 09:30-10:00 range, or back across the 09:30 open, against the extension. Stop 1 tick
   beyond the RTH extreme so far. Target 50% / 100% of the extension (needs >= 1R) / 2R. Entries to 11:30 / 13:00.
   Near-overlap with the E2 gap fade (measured from the prior close); here from London's 02:00.

Judging: "holds" = n >= 5, net > 0 and PF >= 1.1 in each of H1 (Jan-Jun 2026), H2 (Jul-Oct 16), 2025, 2021-24. Chance
level = the same 354 cells with coin-flip directions (stop and target mirrored at the same distance), 10 seeds. H1 pick =
n >= 20, PF >= 1.2, 2-4 trades a week, best H1 $; then H2 and 2021-25 read untouched.

## Results (every cell counted)

| Family | Cells | Hold all 4 spans | Coin-flip mean (max) | H1 + H2 both > 0 | 2-4/wk in H1 | ...of those PF >= 1.2 in H1 | H1 pick |
|---|---|---|---|---|---|---|---|
| LSQ lunch squeeze / PM trend | 216 | 0 | 2.4 (4) | 23 | 24 | 0 | none |
| FAV value-area failed auction | 72 | 0 | 0.8 (2) | 0 | 0 | 0 | none |
| D80 80% rule | 12 | 0 | 0.3 (1) | 3 | 0 | 0 | none |
| LXF London extension fade | 54 | 0 | 0.2 (1) | 0 | 0 | 0 | none |
| **All** | **354** | **0** | **3.7** | 26 | 24 | 0 | **none** |

Zero real cells hold where luck alone gives about 4: the families are at or below chance. With no 2-4/week cell good enough
on Jan-Jun, the H1 -> H2 check has nothing to check. Of the 26 "H1 + H2 both > 0" cells, 24 lose 2025 and the other two
(`d80_c2_u12_r2`, `d80_c2_u15_far`: 5-12 trades a half, 0.2-0.3 a week) are flat in 2025 (PF 1.02-1.07) and lose 2021-24;
all but one trade 0.2-1.2 a week. These are 2026-only wins: **not proven**.

**Closest cells (shown so nobody chases them; none passes):**

| Cell | H1 n / wk / PF / $ | H2 n / wk / PF / $ | 2025 PF / $ | 2021-24 PF / $ | Corr LIT (H1 / H2 / 21-25) |
|---|---|---|---|---|---|
| `lsq_1130_any_any_opp_r1.5` (the only 2-4/wk cell positive in H1) | 59 / 2.2 / 1.08 / +$388 ($66/mo, DD -$1,668) | 36 / 2.3 / 1.44 / +$858 ($237/mo) | 0.77 / -$3,047 | 1.10 / +$5,624 ($148/mo, DD -$4,530) | 0.12 / -0.01 / -0.01 |
| `lsq_1130_any_against_opp_r1.5` (fade the AM trend in the PM) | 18 / 0.7 / 2.47 / +$1,371 | 8 / 0.5 / 6.18 / +$902 | 0.63 / -$1,719 | 0.80 / -$3,832 | -0.03 / -0.02 / -0.04 |
| `d80_c1_u12_r2` (best D80; H1 pick at any frequency) | 18 / 0.7 / 1.56 / +$1,127 | 16 / 1.0 / 0.77 / -$704 | 1.80 / +$4,719 | 1.41 / +$11,633 | 0.00 / -0.02 / -0.01 |
| `lxf_k10_or30_r2_l11` (best LXF on H1) | 18 / 0.7 / 1.77 / +$972 | 10 / 0.6 / 0.26 / -$1,555 | 1.60 / +$2,739 | 1.29 / +$6,663 | -0.01 / -0.04 / -0.11 |

- **PM continuation WITH the AM trend (idea 2):** positive in 71 of 72 cells in 2021-24 but 0 of 72 in 2026 H1 and 29 of 72
  in H2, ~0.6 trades a week. Same story as E2's late break: an old-years edge that is gone in 2026.
- **D80 and LXF** are real-looking in 2021-25 (PF 1.3-1.5, +$190-330/mo) but lose Jul-Oct 2026, trade ~1 a week, and their
  stops are 105-180 pts (1-2 micros at $500): placebo p for H2 0.82 / 0.91.
- **FAV (value-area fakeouts):** loses almost everywhere (9 of 72 cells positive in H1, 20 of 72 in 2021-25).

**Winning days (the reason for the hunt).** The closest cell would add LIT-free winning days (LIT 7.9 -> 9.0 winning days a
month in H1, 5.2 -> 7.2 in H2, 5.4 -> 7.7 in 2021-25; 54-76% of its winning days are days LIT did not win; corr with ATLAS
-0.06 / +0.13 / -0.03). But it adds about as many LOSING days: at PF 1.08 / 0.77 in H1 / 2025 more winning days without
positive money only spread the same drawdown thinner and do not move a payout.

**Eval.** On its own Builder 50K (+$3,000, $2,000 EOD trailing), $400 a trade, a start every session: 0% pass within 40
sessions for every cell above in H1, H2 and 2021-25 (fails 0.7-6.7% in 2021-25; the rest still open). At $66-450 a month
none can reach $3,000 in two months.

## Verdict

Nothing passes. No third strategy, no new account, nothing built; LIT and ATLAS unchanged. The ideas in this hunt (lunch
squeeze, 14:00-15:30 continuation, value-area failed auction, 80% rule, London extension fade) go on the "Tested and
rejected" list. Not done: 1m execution (the 1m file starts 2025-12-29, so it could not check 2021-25; with no 5m survivor
there was nothing to confirm), ES context (ES 5m only from 2025-04).

Reproduce: `python -X utf8 tools/new_hunt.py grid` (~5 min) -> `research/second/new_hunt.json` (every cell's spans).
