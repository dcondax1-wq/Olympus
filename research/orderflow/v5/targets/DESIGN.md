# v5 / targets: lane A with the same entries, different exits (pre-registered 2026-11-27, BEFORE any exit variant was run)

PAPER RESEARCH ONLY. Nothing here changes a bot, a size, an arming or engine/. Code: `research/orderflow/v5/targets/study.py`
(in-sample, the 51 days), `oos.py` (frozen rules on days NOT in the 51). Frozen rules: `frozen.json`. Verdict: `RESULT.md`.
Question: does lane A's edge live in the EXIT? Same signals, same E5 entry, only the exit changes.

## Signals (unchanged, not tuned)
Lane A exactly as `engine/of_paper.replay_summary` makes it on each real summary day (DESIGN_paper.md): level fade at PD H/L,
Globex H/L, ORB H/L (from 10:00), 09:45-15:00 ET signal bars, absorbed = zone dz x d < 0 and |dz| >= 0.20 x vz. The TAKEN set
(absorbed, not busy) and SKIPPED set are frozen from that replay (the busy chain stays as the lane's replay made it, so every
variant trades the SAME entries). Days = the 51 usable days 2026-09-27..2026-11-26 (meta rows >= 50,000).

## Entry (all variants): E5
Decision = signal bar close. A limit AT THE SWEPT LEVEL rests 5 minutes (1m bars from the decision minute): marketable at the
first open if that open is already at/through the level our way (fills at that open); else fills at the level when a 1m bar
trades >= 1 tick through it. A 1m bar reaching the stop before the fill = no trade. Not filled in 5 min = market at the open of
minute 6 **+18 ticks against us**. A fill with risk <= 0 = no trade.
Stop = 1 tick beyond the signal bar's extreme (CLAUDE.md), size follows the stop (R = points / (fill - stop)).

## Costs and fill rules for exits (all variants)
$1.90 round trip per micro. Stop-market fills **2 ticks** worse than the stop (or the bar open if it gapped through).
Limit targets fill only when a 1m bar trades **>= 1 tick through** the target. Market exits (time stop, 15:55 flat) = that
1m bar's close - 2 ticks. A 1m bar that touches stop and target = stop first. The fill minute of a limit fill checks only the stop.
Hard flat at the close of the 15:59 1m bar (= the 15:55 5m bar's close). Path = NinjaTrader 1m bars (`data/NQ_1m.csv`) shifted
by the day's median 5m-open offset (as exec_study.py). If a day has no 1m coverage (OOS days before 2025-12-28), the same rules
run on the day's own 5m summary bars (5-minute window = 1 bar, minute 6 = next bar open, time stops in whole 5m bars); each
day's mode is printed. In-sample is also shown in 5m mode once, as the like-for-like reference for such OOS days.

## Variants (6 tested, fixed; plus the 2R baseline as the reference row, not tested)
| id | target | other exit |
|---|---|---|
| B2R (reference) | 2R limit | - (the lane's rule) |
| T1R | 1R limit | - |
| T15R | 1.5R limit | - |
| T3R | 3R limit | - |
| TOPP | nearest OPPOSITE-type level (a short at a high-type level -> pdl / onl / orl; a long -> pdh / onh / orh), known at the signal bar, whose price is >= 1R in profit from the fill; limit 2 ticks in front of it. None -> 2R | - |
| TRAIL | none | trailing stop: after each CLOSED 5m bar from the fill bar on whose extreme on the stop side is ABSORBED by the lane's own OF1 test (short: high zone, dz > 0 and dz >= 0.20 vz; long: low zone, dz < 0, |dz| >= 0.20 vz), the stop moves to 1 tick beyond that bar's extreme if that is tighter than the current stop. Effective from the next 1m bar. Flat 15:55 |
| TS60 | 2R limit | time stop: market out at the close of the 60th 1m bar counted from the fill minute |
Descriptive only (NOT tested, NOT freezable, not in Holm): TS30 = 2R + 30-minute time stop.

## Reported per variant (TAKEN trades)
trades, trades/week (days / 5 = weeks), win %, mean R, PF ($), net $ at 1 micro, $/month (21 trading days), max DD $ (closed-trade
equity in exit order), both halves by day (first 26 / last 25 days: n, mean R, $), mean R of the SKIPPED signals under the same
exit, the paired difference vs B2R on the same trades (mean dR, d$), and:
- **label-shuffle placebo p**: pool every lane A signal that fills under E5 (taken + skipped); draw the taken count at random
  10,000 times (seed crc32("v5targets")); p = share of draws whose mean R >= the real taken mean R (one-sided).
- **Holm-adjusted p** across the 6 tested variants (on the placebo p).
- day-block bootstrap P(taken mean R <= 0) (10,000, seed 11), descriptive.

## Pass bar (decided now)
YES-candidate = placebo p < 0.05 AND Holm p < 0.10 AND taken mean R > 0 and $ > 0 in BOTH halves AND n >= 30.
"Exit holds the edge" additionally needs the variant's net $ at 1 micro to beat B2R in BOTH halves (else it is the same lane A
edge with a different exit, not an exit edge). Weak = positive both halves but fails placebo/Holm. NO = otherwise.

## Freeze rule (decided now)
frozen.json gets: (1) the best tested variant = YES-candidates first, then the most net $ at 1 micro among those with both
halves > 0, then the lowest placebo p; (2) the second = the next by the same order, if it differs in kind. B2R is always scored
next to them in oos.py. No constant changes after the first run; a change is a new dated file.
