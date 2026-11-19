---
title: Setup grade (2026-11-18) - a calm trader's 7-warning checklist (A / B / C) before every Zlarior and ATLAS signal; grading by the chart does not pick winners, smaller B trades cost money, skipping only the worst pile-ups is a small maybe for Zlarior (could be luck), a loss for ATLAS. Nothing changes.
family: risk
date: 2026-11-18
status: rejected (no change, no proposal). 4 pre-declared versions per strategy + 7 single checks; 1 Zlarior version passes the money gate in all three periods but not the luck test (2021-25 p 0.37) and flips with small definition changes; 0 ATLAS versions pass. ZEUS Lab ids setup_grade_lit / setup_grade_atlas (kind setup_grade, Rejected). live_model*.json, second_model.json, engine/ untouched.
summary: Owner - "More accurate with our trades, don't trade like a bot, trade how a person would, without emotion." Built the checklist a calm discretionary NQ trader asks before each signal, from what is on the chart at that moment only (never the last trade's result): higher-timeframe trend against, a key level within half a stop toward the target, day already extended, inside day (chop), big news in 30 min, ES against, VIX not normal. A = fewer warnings than a typical setup, B = typical, C = more. Checks, weights (1 each) and the cut fixed on Jan-Jun 2026 only; judged untouched on Jul-Oct 2026 and 2021-25, costs in, day / slot left free after a skip. Zlarior, skip C (3+ of 7): +$712 / +$303 / +$11 a month at the Zlarior size, eval path +$124 / +$824 / +$46, 2-week pass 44.5 -> 46.2% / 39.1 -> 47.8%, but random skips of as many setups do as well in 2021-25 (p 0.37; Jul-Oct p 0.16) and it turns into a loss with the first-draft level distance or a stricter C. A full / B half / C skip loses (-$188 / -$1,518 a month). The Jan-Jun-picked grade (trend + level + chop) loses -$592 / -$1,711. ATLAS: every version loses on the funded 25K in Jul-Oct (-$142 a month for skip C). The single check that helped most is the key level in the way, and even it loses money on its own.
runs: none (research/lab/setup_grade.json; tools/setup_grade.py; tests/test_setup_grade.py)
---

# Setup grade: trade like a calm person (2026-11-18)

Owner: "More accurate with our trades, don't trade like a bot, trade how a person would, without emotion." And after the win /
loss anatomy: "Really focus in on the wins and losses. What we are doing good, maybe why we lose."

## For the owner

| What | Result |
|---|---|
| Built | A 7-question checklist a calm trader asks before each trade: trend against me? a key level right in front? day already ran? choppy inside day? big news in 30 min? ES against? VIX not normal? A = fewer warnings than usual, B = usual, C = more. It never looks at the last trade's result (no revenge, no fear). |
| Do the grades pick winners? | **No.** Jul-Oct: Zlarior's clean "A" setups lost **-$1,615**, the ordinary "B" setups made **+$12,333**. ATLAS's "C" setups did as well as its "A" ones in every period. |
| Zlarior: A full, B half, C skip (the human way) | **Loses**: -$188 / -$1,518 a month (Jan-Jun / Jul-Oct). Halving the ordinary setups cuts the big winners. |
| Zlarior: skip only C (3+ warnings stacked up) | **Small maybe, not proven**: +$712 / +$303 / +$11 a month (Jan-Jun / Jul-Oct / 2021-25), eval 2-week pass 39% -> 48% in Jul-Oct. But random skips of as many trades do as well in 2021-25, and a small change to the rule turns it into a loss. Could be luck. |
| ATLAS: any version | **Loses**: skip C = -$142 a month on your funded 25K in Jul-Oct, no-payout chance 15% -> 30%. |
| Which single check helped most | **"A key level right in front of the entry"**: the only one whose trades did worse in every period. But those trades still make money on average, so skipping them alone loses $953 a month (Zlarior, Jul-Oct). |
| What we do well / why we lose | Our winners come from ordinary-looking setups, often against the daily trend and on jumpy-VIX days - exactly the ones a nervous human would pass. The losers do not look different at the entry. Only a pile-up of 3+ warnings lost a little in every period (19 trades in 2026, -$1,282). |

**Verdict: grading setups like a person does not make Zlarior or ATLAS more accurate. Nothing changes, no proposal.** Keep both
bots taking every setup they take today; the bot already trades "without emotion", and a human filter mostly removes winners.

Your steps: none.

## 1. What was already tested (not redone)

`docs/TESTED_AND_REJECTED.md`: grade / confidence sizing and the pre-registered A+ quality score (sweep depth, displacement,
inducements: setup quality, not context), 1h / 15m trend skip / size, an opposing level within 0.97R / 0.61R, day range so far
> 0.80 / 0.92 VIX moves, NQ-vs-ES strength, news-day size, VIX regime size, the learn loop's tilts. Tonight's win / loss anatomy
(`win-loss-anatomy-2026-11-18.md`) skipped every trade flagged by ANY of 4 careful-human checks and lost money in 2026 (its own
numbers: Zlarior -$709 / -$1,486 a month, ATLAS -$2,253 / -$692 on its fixed view). New here: a COUNT of 7 human warnings with
the grade set by the typical setup (skip only when warnings stack up), the A / B / C size use, ES and VWAP / round numbers /
overnight levels in the way, an inside-day chop check, and both strategies on their real account paths with the day / slot
left free after a skip.

## 2. The checklist (tools/setup_grade.py, written before any outcome was looked at)

Every check reads only closed 5m bars at the signal (Zlarior: the 5m CISD trigger bar; ATLAS: the signal bar before the entry
open), the prior days, the prior VIX close and the news calendar. A check that fires = one warning.

| Check | Fires when |
|---|---|
| HTF trend against | the prior session's close is under (long) / over (short) the average of the last 20 closes |
| Key level within 0.5R | the prior-day high / low, the overnight high / low (18:00-09:30, so far), the 18:00 VWAP or a 100-point number sits between the entry and half a stop toward the target |
| Day already extended | the range since 18:00 >= the average daily range of the 14 sessions before |
| Inside day (chop) | the day so far has not left yesterday's high-low range |
| News within 30 min | a high-impact US release (CPI, jobs, PPI, FOMC, ...) in the next 30 minutes |
| ES against | ES moved against the trade over the last 30 minutes (ES bars from 2025-04; before that it cannot fire) |
| VIX not normal | the prior VIX close >= 25, or it jumped >= 20% the day before |

Calibration before any outcome (fire rates only): the key-level check was first written with 1R; it fired on 63-75% of all
setups (the normal state, not a warning), so it became 0.5R. With "0 = A, 1 = B, 2+ = C" about 65% of setups would be C, so the
cut follows the typical setup: m = the median warning count of the strategy's Jan-Jun 2026 trades (2 for both); fewer = A,
m = B, more = C.

Two grades: **all7** (every check counts: the pure checklist) and **h1** (only the checks whose warnings lost R on 8+ Jan-Jun
trades: Zlarior trend + level + chop, ATLAS level + VIX; m = 1). Two uses: **skip C** (A and B as today) and **size** (A as
today, B half, min 1 micro, inside the size-follows-stop rule and every cap; C skipped).

How it was judged (declared before the results): the gate = better than today in Jan-Jun, Jul-Oct AND 2021-25, costs in, 2-4
trades a week, eval 2-week fails not up (Zlarior: the LIT size rule, the live two_week eval path room 0.4 to session 80 incl.
2021-25, the funded 50K Monte Carlo; ATLAS: the funded 25K Monte Carlo at $250 / 30% of the room and the 25K eval path), AND a
luck test: random skips / halves of the same number of trades per period, the day left free (200 draws Zlarior), beaten with
p <= 0.2 in Jul-Oct and 2021-25.

## 3. Wins and losses by grade (today's trades, nothing skipped)

Zlarior, all7 (win %, PF, $ at the Zlarior size, costs in):

| Period | A (fewer warnings) | B (typical) | C (3+ warnings) |
|---|---|---|---|
| Jan-Jun 2026 | 33 trades, 66.7%, PF 7.96, +$25,634 | 35, 60.0%, 3.61, +$8,750 | 12, 33.3%, 0.68, -$483 |
| Jul-Oct 2026 | 17, 23.5%, PF 0.50, **-$1,615** | 16, 81.2%, 18.79, **+$12,333** | 7, 42.9%, 0.39, -$799 |
| 2021-25 | 240, 49.6%, 1.16, +$8,042 | 183, 56.8%, 0.82, -$6,411 | 88, 59.1%, 0.97, -$366 |

Zlarior, h1 grade (trend + level + chop): Jan-Jun A +$16,101 / B +$12,697 / C +$5,104; Jul-Oct A -$272 (2 trades) / B +$5,067 /
C **+$5,124** (18 trades, PF 4.3); 2021-25 A +$10,871 / B +$815 / C -$10,421. The Jan-Jun pattern held in 2021-25 and broke in
Jul-Oct.

ATLAS, all7 (every trade at a fixed $250, costs in):

| Period | A | B | C |
|---|---|---|---|
| Jan-Jun 2026 | 41, 53.7%, PF 2.86, +$7,428 | 42, 52.4%, 3.65, +$9,756 | 21, 52.4%, 1.63, +$1,177 |
| Jul-Oct 2026 | 25, 48.0%, 2.11, +$2,675 | 12, 66.7%, 2.72, +$1,148 | 9, 66.7%, **5.48**, +$1,433 |
| 2025 | 114, 36.0%, 1.19, +$2,858 | 82, 40.2%, 0.86, -$1,282 | 26, 46.2%, 1.97, +$2,890 |
| 2021-24 | 415, 38.6%, 1.03, +$1,326 | 262, 35.1%, 1.05, +$1,588 | 100, 35.0%, 1.23, +$2,984 |

Each check out of sample (R a trade when it fires / when it does not; Zlarior):

| Check | Jan-Jun | Jul-Oct | 2021-25 |
|---|---|---|---|
| HTF trend against | +0.24 / +1.34 | **+1.04 / +0.42** | -0.06 / +0.10 |
| Key level within 0.5R | +0.24 / +1.29 | +0.56 / +0.95 | -0.01 / +0.03 |
| Day already extended | +1.38 / +0.82 (3) | +5.52 / +0.62 (1) | +0.21 / +0.00 |
| Inside day (chop) | +0.36 / +1.38 | **+0.88 / +0.64** | -0.06 / +0.08 |
| News within 30 min | -1.03 / +0.87 (1) | - | -0.33 / +0.02 (3) |
| ES against | +1.41 / +0.79 | +1.05 / +0.66 | +0.12 / +0.01 |
| VIX not normal | **+2.12 / +0.70** | - | **+0.36 / -0.04** |

What this says about our wins and losses:
- **What we do well:** Zlarior's money is in ordinary setups and in the ones a nervous human would pass. Jul-Oct's winners were
  mostly B setups and trades AGAINST the daily trend (+1.04R vs +0.42R); jumpy-VIX days were Zlarior's best trades in Jan-Jun and
  in 2021-25. ATLAS's warned-about trades (C) were its best in Jul-Oct and in 2021-24.
- **Why we lose:** the losers do not look different at the entry (the anatomy found the same: most never reached +0.5R). The
  one consistent thing: when 3+ warnings stack up on a Zlarior setup it lost a little in every period (12 / 7 / 88 trades,
  -$483 / -$799 / -$366).
- **The key level in the way** is the only check that pointed the right way in every Zlarior period (and 3 of 4 for ATLAS:
  +0.19 / +1.45, +0.59 / +0.71, +0.07 / +0.13, +0.07 / +0.02), but those trades still made money on average.

## 4. Zlarior results (the adopt bar)

| Version | trades/wk H1 / H2 / 21-25 | PF | net $ (Zlarior size) | $/month | max DD | eval $/month | 2-week pass/fail | sessions to pass | funded 50K $/mo | gate | luck p (Jul-Oct / 21-25) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| today | 3.12 / 2.56 / 2.38 | 4.98 / 2.91 / 1.01 | +$33,901 / +$9,919 / +$1,265 | +$5,562 / +$2,670 / +$25 | -$2,196 / -$1,396 / -$19,426 | +$5,523 / +$3,159 / -$156 | 44.5/0.0, 39.1/0.0, 10.9/0.8 | 11 / 12 / 21 | +$929 / +$915 / +$58 | - | - |
| h1, skip C | 2.07 / **1.54** / 1.53 | 6.58 / 1.73 / 1.11 | +$30,293 / +$3,562 / +$6,948 | +$4,970 / +$959 / +$136 | -$1,293 / -$3,098 / -$13,044 | +$5,170 / +$1,239 / -$225 | 36.1/0.0, 29.0/0.0, 9.0/0.4 | 13.5 / 6.5 / 19 | +$947 / +$268 / +$47 | no | - |
| h1, size A/B/C | 2.07 / 1.54 / 1.53 | 9.03 / 1.45 / 1.19 | +$24,709 / +$1,270 / +$7,680 | +$4,054 / +$342 / +$150 | -$924 / -$1,800 / -$8,476 | +$3,455 / +$666 / -$56 | 26.1/0.0, 0.0/0.0, 3.0/0.0 | 16 / - / 24 | +$865 / +$157 / +$36 | no | - |
| **all7, skip C** | 2.85 / 2.18 / 2.05 | 6.14 / 3.83 / 1.02 | +$38,244 / +$11,043 / +$1,842 | +$6,274 / +$2,973 / +$36 | -$1,800 / -$1,231 / -$21,604 | +$5,647 / +$3,983 / -$110 | 46.2/0.0, 47.8/0.0, 11.1/0.6 | 10 / 10 / 19 | +$1,033 / +$1,017 / +$61 | PASS | **0.159 / 0.368** |
| all7, size A/B/C | 2.85 / 2.18 / 2.05 | 6.58 / 2.16 / 1.08 | +$32,754 / +$4,278 / +$5,563 | +$5,374 / +$1,152 / +$109 | -$1,252 / -$1,196 / -$14,860 | +$5,006 / +$2,049 / +$42 | 31.1/0.0, 17.4/0.0, 7.9/0.5 | 15 / 31.5 / 24 | +$987 / +$720 / +$51 | no | - |

The one gate passer, all7 skip C (skip a setup with 3+ of 7 warnings, the day stays free for a later setup):
- vs today, a month: Zlarior size **+$712 / +$303 / +$11**, eval path +$124 / +$824 / +$46, funded 50K +$104 / +$102 / +$3;
  2-week passes 44.5 -> 46.2%, 39.1 -> 47.8%, 10.9 -> 11.1%; fails not up; 2.85 / 2.18 trades a week; the 2021-25 max DD is
  worse (-$19,426 -> -$21,604).
- **Luck test:** random skips of as many trades (12 / 7 / 88) with the day left free beat it in 2% of draws in Jan-Jun, 16% in
  Jul-Oct and **37% in 2021-25** (eval path 2.5% / 8.5%): the 2021-25 gain is chance level. The Lab's sign-flip on the per-trade
  $ changes: p 0.15 / 0.12 against a many-tests bar of 0.002 (94 cells). One of 4 versions tried.
- **Robustness (the same rule, small changes, $/month at the Zlarior size):**

| Version | Jan-Jun / Jul-Oct / 2021-25 | eval Jan-Jun / Jul-Oct / 2021-25 | gate |
|---|---|---|---|
| without trend | -$441 / -$468 / -$14 | -$298 / +$454 / +$47 | no |
| without key level | -$148 / **-$2,319** / +$36 | -$843 / -$2,463 / +$272 | no |
| without extended | +$675 / +$303 / +$6 | +$72 / +$824 / +$40 | pass |
| without chop | +$235 / -$1,939 / -$52 | -$776 / -$613 / -$81 | no |
| without news | +$712 / +$216 / +$11 | +$124 / +$814 / +$22 | pass |
| without ES | +$281 / +$130 / -$27 | -$396 / +$767 / +$18 | no |
| without VIX | +$852 / +$303 / +$59 | +$817 / +$824 / +$65 | pass |
| key level at 1R (the first draft) | +$476 / **-$208** / -$20 | -$205 / -$154 / +$64 | no |
| stricter C (4+ warnings) | +$17 / -$39 / -$42 | +$20 / -$87 / -$113 | no |

  Leaving out a check re-sets the typical count, so it also changes how many setups are skipped. The rule only works in this
  exact form: the first-draft level distance or a stricter cut turn Jul-Oct and 2021-25 into losses. **Not adopted.**

Each check alone as a skip ($/month at the Zlarior size, Jan-Jun / Jul-Oct / 2021-25): trend -$208 / -$2,442 / +$58; key level
-$309 / -$953 / +$12; extended -$140 / -$687 / -$36; chop -$1,881 / -$1,265 / +$184; news +$79 / $0 / +$5 (fires on 1 trade in
2026); ES -$1,083 / -$932 / -$24; VIX -$667 / $0 / -$242. None helps in Jul-Oct.

## 5. ATLAS results (funded 25K at $250 / 30% of the room; 25K eval path)

| Version | trades/wk H1 / H2 / 21-25 | PF ($250) | net $ ($250) | funded $/month | 1st payout (sessions) | no payout 6 mo | max DD ($250) | eval 2-week pass/fail H1, H2, 2025, 2021-24 | eval $ (after fees) | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| today | 4.06 / 2.95 / 4.61 | 2.92 / 2.55 / 1.08 | +$18,362 / +$5,256 / +$10,393 | +$541 / +$353 / +$34 | 21 / 32 | 5.8% / 15.0% | -$1,062 / -$876 / -$11,403 | 61.3/0, 43.5/0, 24.9/0, 19.3/0 | +$9,083 / +$2,135 / -$2,111 / -$3,953 | - |
| h1, skip C | 3.83 / 2.95 / 4.39 | 2.99 / 2.55 / 1.05 | +$18,417 / +$5,256 / +$6,455 | +$543 / +$353 / +$33 | 21 / 32 | 5.2% / 15.0% | -$1,062 / -$876 / -$11,346 | 61.3/0, 43.5/0, 24.9/0, 17.5/0 | +$8,979 / +$2,135 / -$2,075 / -$4,274 | no |
| h1, size | 3.83 / 2.95 / 4.39 | 3.47 / 2.33 / 1.06 | +$16,378 / +$3,856 / +$5,280 | +$540 / +$280 / +$34 | 21 / 40 | 4.2% / 19.8% | -$1,339 / -$1,456 / -$8,574 | 60.5/0, 37.7/0, 16.5/0, 12.8/0 | +$8,623 / +$1,671 / -$977 / -$3,971 | no |
| all7, skip C | 3.24 / 2.37 / 4.09 | 3.24 / 2.24 / 1.05 | +$17,185 / +$3,823 / +$5,443 | +$520 / **+$211** / +$27 | 22 / 41 | 5.0% / **30.2%** | -$1,142 / -$1,134 / -$10,796 | 56.3/0, 39.1/0, 18.1/0, 19.0/0 | +$9,456 / +$1,772 / -$1,702 / -$2,837 | no |
| all7, size | 3.24 / 2.37 / 4.09 | 3.03 / 2.14 / 1.05 | +$11,107 / +$3,095 / +$3,985 | +$482 / +$175 / +$24 | 26 / 51 | 4.3% / 33.2% | -$1,448 / -$1,001 / -$9,654 | 42.0/0, 30.4/0, 14.9/0, 14.3/0 | +$7,472 / +$1,378 / -$1,021 / -$3,557 | no |

The h1 grade (key level + VIX both firing) almost never says C (6 / 0 / 3 / 48 trades), so it changes nothing that matters.
Each check alone as a skip (funded $/month, Jan-Jun / Jul-Oct / 2021-25): trend -$301 / -$187 / -$4; key level +$13 / -$203 /
-$11; extended -$50 / -$73 / +$1; chop -$197 / -$84 / -$15; news $0 / $0 / +$1; ES -$171 / -$58 / -$6; VIX -$45 / $0 / +$2. No
check helps ATLAS. No luck test was needed (no version passed the gate).

## 6. Honest notes

- The checklist was written before any result; two things were set from fire rates only (key level 1R -> 0.5R, the typical-count
  cut). The first-draft 1R version is in the robustness table: it loses in Jul-Oct.
- Missing data never fires a check: ES before 2025-04, FOMC-only news in 2021-23. So 2021-24 grades carry fewer warnings.
- 2026 samples are small (Zlarior 80 / 40 trades, ATLAS 104 / 46): a 7-trade skip in Jul-Oct is not proof of anything.
- A human's wish to "trade smaller when unsure" is the costliest idea here: B is the typical setup, and the typical setups hold
  the big winners (Zlarior Jul-Oct: B +$12,333).

## 7. Files

- `tools/setup_grade.py` - the checks (pure functions), the facts at the signal (closed bars only), the Jan-Jun pick, the scoring
  on the real backtests, the luck test, the robustness rows, the report, the ZEUS Lab runner + register.
  `python -X utf8 tools/setup_grade.py run` (~8 min with the luck test) / `report` / `register`.
- `research/lab/setup_grade.json` - every number above (2026 per-trade changes kept for the Lab).
- `tests/test_setup_grade.py` (area nq) - the grade, each check, no look-ahead (a fake market), the Jan-Jun pick, never reads
  P&L, no live file, the stored verdict, the Lab entries.
- ZEUS Lab: kind `setup_grade` (tools/zeus_lab.py), ids `setup_grade_lit`, `setup_grade_atlas` (cells 11 each), status Rejected.
