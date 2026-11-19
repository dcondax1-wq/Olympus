---
title: One account, Zlarior + ATLAS on the Builder 50K - the FINAL rules (12 pre-registered rule sets, MFFU live move in)
family: risk
date: 2026-11-19
status: done - paper only. Winner by the rule fixed in advance - first in keeps the account, ATLAS at HALF its own size while the account is in the eval, full size once funded (research/lab/combo_50k.json). Likely better than Zlarior alone, not sure - 1 Jul-Oct-like stretch in 7 still gives $0 or less, and no ATLAS size or eval guard changes that. Nothing live changed.
summary: Owner 2026-11-19 "More research, we are gonna perfect this and build it. I don't want bullshit results". Design committed before any variant result (f80bacac) - 12 rule sets (conflict first-in / Zlarior-the-other-way closes ATLAS / any Zlarior entry closes ATLAS; ATLAS at 100 / 60 / 40% of its size; ATLAS out of / at 50% in the eval; eval guards - ATLAS only with >= $1,500 room, no entry after a -$500 day; 2 combinations), MFFU's move to a live account after the 5th payout modelled in every row, day- AND week-block bootstraps 2,000 x 126, Jan-Jun / Jul-Oct / 2021-25 / 2022, +1 tick, ATLAS's 5 best days removed, live account worth $0, 200 resampled Jul-Oct histories. Pick - 5 constraints (beats Zlarior alone > 2 SE in both 2026 halves; 2021-25 >= -$50; 2-week eval fails <= 5%; still ahead at +1 tick; $0 or worse in <= 7% of histories). No row passes all 5 (best 8.5%); 8 pass the first 4; the best Jul-Oct $ of those = ATLAS at 50% in the eval - $2,554 / $1,501 / $16 / $25 a month (Jan-Jun / Jul-Oct / 2021-25 / 2022, week blocks) vs Zlarior alone $905 / $805 / -$10 / $166; 2-week eval fails 0.0 / 4.4 / 7.0% (base combo 2.8 / 8.8 / 33.6%, Zlarior 0.5%). If the live account after payout 5 is worth $0 - gain +$466 / +$392 / +$14. Tied with it (within noise) - the $1,500 eval room guard (2-week fails 0.8%). Most robust - "any Zlarior entry closes ATLAS" ($0 or worse 8.5%) but 10% early eval fails alone; two post-hoc combinations with it are listed, not adopted.
runs: none (research/lab/combo_final.json, research/lab/combo_50k.json)
---

## For the owner (one minute)

**Build this:** Zlarior + ATLAS on the Builder 50K, one position at a time (the first bot in keeps the account), and
**ATLAS trades at half its own size until the eval passes**, full size once funded. Everything else stays as today.

| $ a month to you after eval fees (6 months, MFFU's move to live after payout 5 counted) | Jan-Jun 2026 | **Jul-Oct 2026** | 2021-25 | 2022 alone |
|---|---:|---:|---:|---:|
| Zlarior alone (today) | $905 | **$805** | -$10 | $166 |
| Zlarior + ATLAS, the study's rule (ATLAS full size from day 1) | $2,770 | $1,591 | $55 | $35 |
| **Zlarior + ATLAS, final rule (ATLAS half size in the eval)** | **$2,554** | **$1,501** | $16 | $25 |
| ... its 10-90% of runs | $1,318 to $3,887 | $503 to $2,578 | -$92 to $221 | -$92 to $236 |
| ... gain over Zlarior alone (same runs) | **+$1,649** | **+$696** | +$26 | **-$141** |
| ... gain if the live account after payout 5 is worth $0 (worst case) | +$466 | +$392 | +$14 | - |
| Evals that die inside 2 weeks: Zlarior alone / study rule / final | 0.5 / 2.8 / **0.0%** | 0.5 / 8.8 / **4.4%** | 0.5 / 33.6 / **7.0%** | 0.8 / 27.4 / 5.8% |
| Eval passed: median days (Zlarior alone / final) | 10 / 12 | 7 / 8 | 14 / 17 | 17 / 17 |
| Funded: first payout within 30 trading days (alone / final) | 55 / 92% | 57 / 68% | 7 / 19% | 21 / 18% |

(Week blocks: whole real weeks kept together, the harsher test. Day blocks give the same picture: Jul-Oct $1,461 vs $734.)

In plain words:
- **Why half size in the eval:** ATLAS at full size from day 1 made 9 evals in 100 die inside 2 weeks in a Jul-Oct-like
  market (bad ATLAS days come in bunches). Half size keeps most of the money (-$90 a month vs the study's rule) and halves
  those early deaths; once funded ATLAS trades full size, where its edge pays (first payout within 30 days 68% vs 57%).
- **Likely, not sure:** if the next 16 weeks look like a reshuffled Jul-Oct, 1 time in 7 the pair makes $0 or less than
  Zlarior alone. Without ATLAS's 5 best Jul-Oct days the gain is about $0 (-$26). Jan-Jun-like markets: solid (+$1,074
  even without ATLAS's 5 best days). 2022-like markets: about $141 a month LESS than Zlarior alone.
- **Nothing fixes the "1 in 7"** with ATLAS's size or an eval guard (question 3). A smaller ATLAS makes it worse (60%: 1 in
  5.4; 40%: 1 in 4.3), because a small ATLAS trade still blocks Zlarior's trades. Only "Zlarior always takes the account"
  helped (1 in 12), but on its own it kills 10% of evals inside 2 weeks.
- **Tied option, same money:** "ATLAS stops in the eval once the eval has lost $500 from its high" makes $15 a month less
  in Jul-Oct (inside the noise) with 5x fewer 2-week eval deaths (0.8%). The rule fixed in advance picks on Jul-Oct $ only,
  so the half-size rule stands; either is fine.

Next (paper only):
1. Decide the card `zlarior-atlas-50k` (updated with these numbers).
2. On yes, the lead builds `research/lab/combo_50k.json` (section 6) and Sim-tests it before you arm anything.
3. After December: re-run on the new days, including the "Zlarior always takes the account" rows:
   `/home/user/heavy.sh python -X utf8 tools/money/combo_account.py final`

## 1. What was tested (fixed and committed BEFORE any variant result: f80bacac)

Design: `research/lab/combo_final_design_2026-11-19.md`. Code: `tools/money/combo_account.py final` (results
`research/lab/combo_final.json`). The study's model is kept (same 631 Zlarior trades, same ATLAS member trades, the
engine's own sizing calls, the shared room, the $1,000 soft day across both bots, 40 micros, $1.90 a micro + 1 tick per
market fill); with `live` set to "rebuy" it reproduces the study exactly ($827 / $714 / -$7 and $1,888 / $1,286 / $44).

Model fixes in EVERY row:
- **MFFU's move to live after the 5th payout** (research/lit/mffu_rules.json): the sim account ends and no new eval is
  bought while the live account trades (sim accounts go dormant); the live account: $2,000 EOD trailing that stops at
  the start, $1,000 soft day, daily payouts >= $250, 80%, no consistency rule; a live breach = 21 days (15 sessions) with
  no eval, then a new one. Assumed, not in the rulebook: it starts at $0 profit, 40 micros, the bots size it by their
  funded rules, the bot keeps a $2,000 cushion and withdraws the rest. Because that is an assumption, every row also ran
  with **the live account worth $0** (the slot simply ends at payout 5: the red team's model).
- **Week blocks next to day blocks** (2,000 x 126 sessions each, the same paths for every row), four periods.
- **An ATLAS trade closed early** (conflict rules 2 and 3) is priced from ATLAS's own stored path: the last bar close at
  or before Zlarior's entry minute, minus 1 tick, with its worst open loss up to then (no look-ahead). On the real days
  rule 2 closes 9 / 2 / 35 ATLAS trades (Jan-Jun / Jul-Oct / 2021-25), rule 3 closes 22 / 7 / 91.

The 12 rule sets (each with its reason in the design file): 1 base (study); 2 zprio - Zlarior entering the other way
closes ATLAS (today's HEDGE between the accounts); 3 zfull - any Zlarior entry closes ATLAS; 4 / 5 ATLAS at 60% / 40%;
6 ATLAS out of the eval; 7 ATLAS 50% in the eval, 100% funded; 8 in the eval ATLAS only with >= $1,500 room; 9 in the
eval no entry after a -$500 day; 10 = 4 + 8; 11 = 8 + 9; 12 = 6 + ATLAS 60% funded. Not run, with reason: keeping only
ATLAS members positive in every pre-Jul-Oct period - all three are (net of commission, H1 / 2021-25: EMA +30.8 / +18.1 R,
MACD +46.6 / +56.8, S-R +22.9 / +7.8), so that rule = the base. (The per-member Jul-Oct numbers were seen before the
design was written; S-R is weak there, +1.1 R, and stays in because the rule uses pre-Jul-Oct data only.)

The pick (fixed): C1 gap vs Zlarior alone > 2 paired SE in Jan-Jun AND Jul-Oct, day AND week blocks; C2 2021-25 gap >=
-$50 a month; C3 eval fails inside 2 weeks <= 5% in both 2026 halves, day AND week; C4 still ahead at +1 tick; C5 $0 or
worse in <= 7% of 200 resampled Jul-Oct histories. Tier A (C1-C5) -> best Jul-Oct week $; else tier B (C1-C4) -> best
Jul-Oct week $; else keep the base.

## 2. Results (all 12 + Zlarior alone; gap = vs Zlarior alone on the same paths; C1-C5 = Y passed / n failed)

### Money ($ a month after fees, MFFU live move in; week-block / day-block bootstrap; gap vs Zlarior alone)

| Row | Jan-Jun | Jul-Oct | 2021-25 | 2022 | C1-C5 |
|---|---|---|---|---|---|
| Z | $905 / $872 | $805 / $734 | -$10 / -$7 | $166 / $170 | today |
| base | $2,770 / $2,726 (+1,865) | $1,591 / $1,556 (+786) | $55 / $44 (+65) | $35 / $58 (-131) | YYnYn |
| zprio | $2,496 / $2,477 (+1,591) | $1,472 / $1,413 (+667) | $41 / $28 (+51) | $63 / $103 (-103) | YYnYn |
| zfull | $2,524 / $2,517 (+1,619) | $1,745 / $1,699 (+940) | $34 / $30 (+43) | $63 / $106 (-104) | YYnYn |
| a60 | $1,802 / $1,835 (+897) | $1,244 / $1,184 (+439) | $10 / -$6 (+20) | $32 / $48 (-134) | YYYYn |
| a40 | $1,367 / $1,423 (+462) | $1,081 / $1,007 (+277) | -$1 / -$9 (+8) | $53 / $65 (-113) | YYYYn |
| a_eval_off | $2,406 / $2,420 (+1,501) | $1,424 / $1,394 (+619) | $15 / $11 (+25) | $49 / $61 (-117) | YYYYn |
| a50_eval | $2,554 / $2,563 (+1,649) | $1,501 / $1,461 (+696) | $16 / $7 (+26) | $25 / $43 (-141) | YYYYn |
| room1500 | $2,591 / $2,519 (+1,686) | $1,486 / $1,456 (+681) | $24 / $17 (+33) | $40 / $57 (-126) | YYYYn |
| daycap500 | $2,743 / $2,706 (+1,838) | $1,582 / $1,549 (+777) | $57 / $42 (+67) | $43 / $56 (-123) | YYnYn |
| a60_room1500 | $1,745 / $1,764 (+840) | $1,207 / $1,144 (+402) | $1 / -$6 (+11) | $43 / $54 (-123) | YYYYn |
| room1500_daycap500 | $2,577 / $2,515 (+1,672) | $1,489 / $1,453 (+684) | $25 / $16 (+35) | $39 / $57 (-127) | YYYYn |
| a_eval_off_a60 | $1,688 / $1,739 (+783) | $1,182 / $1,137 (+377) | $6 / $1 (+16) | $58 / $62 (-108) | YYYYn |

### Safety and speed (week-block; day-block in brackets)

| Row | eval fail in 2 weeks H1 / H2 / 21-25 | eval fail in 60 H1 / H2 | eval pass median days H1 / H2 | funded 1st payout <= 30 / 60 d H2 | 6 months lose money H2 |
|---|---|---|---|---|---|
| Z | 0.5% (0.1%) / 0.5% (0.1%) / 0.5% (0.5%) | 15.7% / 14.5% | 10.0 / 7.0 | 57.2% / 80.5% | 7.7% |
| base | 2.8% (4.0%) / 8.8% (2.1%) / 33.6% (33.7%) | 8.8% / 19.4% | 6.0 / 6.0 | 68.1% / 85.3% | 1.1% |
| zprio | 3.2% (4.5%) / 9.2% (2.7%) / 31.9% (32.8%) | 10.5% / 22.4% | 6.0 / 5.0 | 66.7% / 83.0% | 1.9% |
| zfull | 3.1% (3.9%) / 10.1% (2.5%) / 30.4% (32.4%) | 9.9% / 22.1% | 6.0 / 5.0 | 72.1% / 85.7% | 0.8% |
| a60 | 0.0% (0.8%) / 4.0% (0.6%) / 9.1% (8.8%) | 2.6% / 15.2% | 12.0 / 8.0 | 66.2% / 86.5% | 1.6% |
| a40 | 0.0% (0.4%) / 3.4% (0.4%) / 5.2% (4.2%) | 1.6% / 15.4% | 14.0 / 8.0 | 62.9% / 85.5% | 2.7% |
| a_eval_off | 0.5% (0.1%) / 0.5% (0.1%) / 0.5% (0.5%) | 15.7% / 14.5% | 10.0 / 7.0 | 68.1% / 85.3% | 5.0% |
| a50_eval | 0.0% (0.6%) / 4.4% (0.5%) / 7.0% (6.2%) | 1.9% / 15.8% | 12.0 / 8.0 | 68.1% / 85.3% | 2.4% |
| room1500 | 0.7% (0.2%) / 0.8% (0.2%) / 1.6% (1.2%) | 12.3% / 14.2% | 6.0 / 8.0 | 68.1% / 85.3% | 3.6% |
| daycap500 | 5.5% (4.5%) / 8.8% (2.1%) / 33.5% (32.4%) | 13.3% / 20.5% | 6.0 / 6.0 | 68.1% / 85.3% | 1.2% |
| a60_room1500 | 0.6% (0.1%) / 0.8% (0.1%) / 0.4% (0.9%) | 10.6% / 13.2% | 11.0 / 8.0 | 66.2% / 86.5% | 3.6% |
| room1500_daycap500 | 0.8% (0.1%) / 0.8% (0.2%) / 1.6% (1.1%) | 12.9% / 14.0% | 6.0 / 8.0 | 68.1% / 85.3% | 3.6% |
| a_eval_off_a60 | 0.5% (0.1%) / 0.5% (0.1%) / 0.5% (0.5%) | 15.7% / 14.5% | 10.0 / 7.0 | 66.2% / 86.5% | 4.4% |

### Robustness (gap vs Zlarior alone, $ a month; H1 / H2 / 21-25)

| Row | +1 tick (week) | ATLAS's 5 best days removed (day) | live worth $0 (stop at payout 5, day) | old model: new eval after payout 5 (day) | H2 histories: gap <= $0 / 10% / median / 90% |
|---|---|---|---|---|---|
| base | +1,862 / +755 / +47 | +1,150 / -14 / +29 | +475 / +435 / +51 | +1,061 / +572 / +51 | 14.5% / -108 / +782 / +2,194 |
| zprio | +1,590 / +637 / +34 | +1,197 / -119 / +16 | +462 / +385 / +36 | - | 19.0% / -212 / +673 / +1,962 |
| zfull | +1,600 / +903 / +29 | +1,267 / +109 / +19 | +466 / +472 / +37 | - | 8.5% / +120 / +945 / +2,295 |
| a60 | +928 / +406 / +12 | +593 / -2 / -11 | +424 / +307 / +2 | - | 18.5% / -134 / +422 / +1,278 |
| a40 | +498 / +251 / +3 | +361 / -16 / -9 | +327 / +209 / -2 | - | 23.0% / -225 / +266 / +884 |
| a_eval_off | +1,511 / +584 / +23 | +984 / -16 / +12 | +420 / +349 / +18 | - | 14.5% / -100 / +576 / +1,679 |
| a50_eval | +1,650 / +662 / +14 | +1,074 / -26 / +2 | +466 / +392 / +14 | - | 14.5% / -129 / +654 / +1,971 |
| room1500 | +1,681 / +651 / +30 | +1,009 / -36 / +18 | +436 / +381 / +25 | - | 14.5% / -115 / +657 / +1,943 |
| daycap500 | +1,829 / +747 / +55 | +1,129 / -23 / +28 | +473 / +430 / +49 | - | 14.5% / -108 / +765 / +2,186 |
| a60_room1500 | +871 / +367 / +7 | +544 / -14 / -5 | +391 / +276 / +2 | - | 18.5% / -147 / +369 / +1,211 |
| room1500_daycap500 | +1,668 / +652 / +30 | +1,006 / -37 / +16 | +434 / +380 / +23 | - | 14.5% / -115 / +651 / +1,942 |
| a_eval_off_a60 | +818 / +343 / +15 | +532 / +0 / +1 | +370 / +268 / +9 | - | 17.5% / -122 / +353 / +1,081 |

Pick: tier B, winner **a50_eval** (tier A = all of C1-C5: none; C1-C4: ['a60', 'a40', 'a_eval_off', 'a50_eval', 'room1500', 'a60_room1500', 'room1500_daycap500', 'a_eval_off_a60']).

## 3. The pick

- **Tier A (all five): none.** C5 ("$0 or worse" in <= 7% of resampled Jul-Oct histories) failed for every row; the
  lowest was zfull at 8.5%.
- **Tier B (C1-C4): 8 rows** - a60, a40, a_eval_off, a50_eval, room1500, a60_room1500, room1500_daycap500, a_eval_off_a60.
  The base, zprio, zfull and daycap500 fail C3 (2-week eval fails 8.8-10.1% in Jul-Oct with week blocks; daycap500
  even 5.5% in Jan-Jun: a -$500 day stop does not stop the first bad day, and it blocks Zlarior's comebacks).
- **Winner: a50_eval** (highest Jul-Oct week $ of tier B: $1,501). Runner-up room1500 $1,486: the $15 gap is inside the
  noise (paired SE about $15 per gap). It has 5x fewer 2-week eval deaths (0.8% vs 4.4% Jul-Oct, 1.6% vs 7.0% 2021-25)
  but more 60-day fails in Jan-Jun (12.3% vs 1.9%); money is the same in every period ($ a month after the re-buys).
  The rule fixed in advance ranks on Jul-Oct $ only, so a50_eval is the config; room1500 is an equal choice.
- "Nothing beats the base" does not apply: the base itself fails C3 (8.8% > the 5% bar).
  The winner makes $90 a month less than the base in Jul-Oct (-$216 Jan-Jun, -$39 2021-25) for half the early fails.

Dropped and why (one line each):
- base (study): most money in Jan-Jun, but 8.8% of evals die inside 2 weeks (Jul-Oct, week blocks) and 34% in 2021-25.
- zprio (Zlarior the other way closes ATLAS): less money than the base everywhere (Jul-Oct +$667 vs +$786), same early
  fails, more fragile ($0 or worse 19%). The closes cut ATLAS's winners more than they save.
- zfull (any Zlarior entry closes ATLAS): the most Jul-Oct money (+$940) and the most robust (8.5%; +$109 even without
  ATLAS's 5 best days) - but 10.1% early eval fails and less in Jan-Jun (+$1,619) and 2021-25 (+$43). Fails C3.
- a60 / a40: evals safe (4.0 / 3.4% Jul-Oct) but the gain halves (+$439 / +$277) and gets MORE fragile (18.5 / 23% $0 or
  worse): a small ATLAS trade still holds the account and blocks Zlarior.
- a_eval_off (ATLAS only once funded): Zlarior's own eval (0.5% early fails) but $77 a month less than the winner in Jul-Oct.
- daycap500: no help (early fails 5.5% / 8.8%).
- the combinations (a60_room1500, room1500_daycap500, a_eval_off_a60): pass C1-C4, less money than their parts.

## 4. Question 3 - which ATLAS share and guard makes "$0 or worse" drop well below 1 in 7?

**None of them.** 200 resampled Jul-Oct histories (the 16 weeks redrawn, 500 runs each, the same histories for every row):

| ATLAS share / guard | $0 or worse | gap 10% / median / 90% |
|---|---:|---|
| 100%, no guard (base) | 14.5% | -$108 / +$782 / +$2,194 |
| 60% / 40% | 18.5% / 23.0% | -$134 / +$422 / +$1,278 ; -$225 / +$266 / +$884 |
| out of the eval / 50% in the eval (winner) | 14.5% / 14.5% | -$100 / +$576 / +$1,679 ; -$129 / +$654 / +$1,971 |
| eval room guard $1,500 / day stop -$500 | 14.5% / 14.5% | -$115 / +$657 / +$1,943 ; -$108 / +$765 / +$2,186 |
| **Zlarior always takes the account (zfull)** | **8.5%** | **+$120** / +$945 / +$2,295 |

Why: the bad histories are the ones where ATLAS's few big trend days are missing. Eval guards act only in the eval, so
they cannot change that; a smaller ATLAS shrinks its gain but still takes the account away from Zlarior's trades. Only
giving Zlarior its trades back (zfull) lifts the bad tail, because then a quiet ATLAS stretch costs Zlarior nothing.

## 5. Post-hoc rows (chosen AFTER seeing the 12; same data; NOT adopted)

zfull is the most robust conflict rule but fails the eval bar; the two eval fixes that passed the bar were bolted on
afterwards to see whether the two effects add up. They do, but this is exactly the kind of after-the-fact pick that
looks better than it is, so neither is the config. Re-test both on Nov-Dec 2026 days under the same 5 constraints.

| Post-hoc row | gap vs Zlarior alone (week) Jan-Jun / Jul-Oct / 2021-25 / 2022 | 2-week fails Jul-Oct (week) | $0 or worse | C1-C5 |
|---|---|---:|---:|---|
| zfull + ATLAS 50% in the eval | +$1,465 / +$859 / +$28 / -$104 | 5.0% | 8.0% | YYYYn |
| zfull + eval room guard $1,500 | +$1,450 / +$806 / +$19 / -$105 | 0.8% | 8.0% | YYYYn |

(Both: without ATLAS's 5 best Jul-Oct days still +$103 / +$70; live account worth $0: +$448 / +$413 Jul-Oct. They make
~$200 a month less than the winner in Jan-Jun and ~$110-160 more in Jul-Oct. Live build cost: Zlarior's resting limit
entries must stay working while ATLAS holds, and a Zlarior fill must flatten ATLAS's part and replace its bracket.)

## 6. What the live build must do (the lead; Sim first)

`research/lab/combo_50k.json` (the file the build reads):

- One position per account at the NinjaTrader account level: before either bot routes on the 50K, check the account's
  real position AND the other bot's working entry orders; skip if either exists (conflict "first").
- When ATLAS fills on the 50K, cancel Zlarior's resting limit entries on the 50K; one bracket (the open bot's OCO) per account.
- **ATLAS's size on this account = max(1, floor(0.5 x its own account_b size)) while the account is an eval**, 1.0 x
  once funded (and on the live account after payout 5). Zlarior's sizes unchanged. Both size from the 50K's shared room;
  the $1,000 soft day counts both bots; 40 micros; flat by 16:10.
- One direction lock across accounts (red team section 6): no account opens against an open position on another.
- After the 5th sim payout MFFU moves you to live and the other sim accounts go dormant: the plan must expect that.

## 7. Honesty notes

- **Variants:** 12 pre-registered + 2 post-hoc (labelled) = 14 rows x up to 4 periods x 7 tests (day, week, +1 tick day /
  week, best-5-days drop, live worth $0, study model for parity) + 200 histories. The pick rule was fixed first and followed.
- **The live-account assumption moves the absolute $ a lot** (the winner's Jan-Jun $2,554 includes about $1,261 a month
  from the live account after payout 5). The gap with the live account worth $0 is the floor: +$466 / +$392 / +$14.
  The order of the rows is about the same under both (zfull and the base on top, a40 at the bottom).
- **Same data as the study:** Jul-Oct is 78 trading days, Jan-Jun 128; ATLAS's members were built with 2021-25 and 2026
  in view (red team section 2); none of the periods is fully unseen for ATLAS. The resampled histories and the
  best-days drop are the honest uncertainty, not the +-2 SE (that is only shuffling noise).
- **2022 is still a loss** for every row (-$103 to -$141 a month vs Zlarior alone): in a year where Zlarior is strong
  alone and ATLAS weak, sharing the room costs money. No guard tested fixes that.
- Model limits (unchanged from the study): trades of a day in entry order on closed P&L; ATLAS's worst open loss skips
  its own entry bar; gaps through stops, outages, MFFU rule changes not modelled; the other sim accounts going dormant at
  the live move are not counted.

## 8. Files

- Design (before results): `research/lab/combo_final_design_2026-11-19.md`
- Code + test: `tools/money/combo_account.py` (`final`, `posthoc`, `final-table`, `build-paths`), `tests/test_combo_account.py` (part h)
- Results: `research/lab/combo_final.json`; config: `research/lab/combo_50k.json`; ATLAS paths: `research/lab/combo_atlas_paths.json`
- Decide card: `zlarior-atlas-50k` in `tools/web_public/business/decisions.json`
