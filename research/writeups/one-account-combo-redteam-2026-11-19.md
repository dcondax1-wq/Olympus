---
title: Red team - Zlarior + ATLAS on ONE Builder 50K (one-account-combo-2026-11-19.md)
family: risk
date: 2026-11-19
status: done - paper only. The study's numbers are computed right (an independent re-build gets the same $ within noise), but the Jul-Oct gain (+$572 a month) rests on 5 ATLAS days; without them it is about $0. Jan-Jun gain is solid; 2021-25 is ~$0 and 2022 is worse. Verdict - "only if" (see the last line). Nothing live changed.
summary: Owner 2026-11-19 "don't give me bullshit results". Skeptic check of the one-account combo study (design 4e682267, results 2fbb392e). Own simulator written from research/lit/mffu_rules.json + the live engine sizing functions (engine/sizing.lit_qty / funded_qty, engine/account_b.qty / funded_qty), not the study's helpers. Same headline within Monte Carlo noise (Jul-Oct Zlarior alone $736 vs study $714, Zlarior + ATLAS $1,305 vs $1,286, gap +$569 vs +$572). Breaks - remove ATLAS's 5 best Jul-Oct days (25.5 of its 27.9 R) and the gain is -$23 a month; resampling the 16 Jul-Oct weeks themselves, the gain is <= $0 in 14% of histories; week-block bootstrap puts the Jul-Oct 2-week eval fails at 8.8% (study 2.1%); MFFU's move to live after the 5th payout (a funded combo reaches it in 81% of Jul-Oct runs vs 33%) cuts the Jul-Oct gain to +$428; 2022 alone -$108. Holds - trade inputs = the repo's stored trades (Zlarior 631/631 = research/anatomy, ATLAS 100% = the second_mix member cache), no exits after 16:00, no overlaps, first-in, shared EOD floor, 40 micros, costs; +2 ticks each way +$533; Zlarior priority instead of first-in +$484; LIT-armed block no change.
runs: none (scratch only; numbers below)
---

## For the owner (one minute)

**The math is right. The Jul-Oct promise is thinner than it looks.** I rebuilt the whole test my own way and got the same
dollars. But in Jul-Oct the extra money comes from ATLAS catching 5 big days out of 78. Take those 5 days away and
Zlarior + ATLAS makes the same as Zlarior alone (not less, not more). Jan-Jun holds up even without ATLAS's best days.

| What I checked | Result |
|---|---|
| Are the $ computed right? (my own simulator, same rules) | **Yes.** Jul-Oct: alone $736, with ATLAS $1,305 a month (study $714 / $1,286). Jan-Jun $826 / $1,863. 2021-25 -$11 / +$42 |
| Real trades, today's rules, no peeking? | **Yes.** Zlarior = the 631 stored trades exactly; ATLAS = its stored member trades exactly; nobody holds past 16:00; no two trades at once |
| Account rules (50K: $3,000 target, $2,000 EOD trailing, $1,000 day, 40 micros, payouts $500-$2,000, 80%) | **Right**, same as the rulebook. Rapid EOD 25K rows use unverified numbers (30% best day + 4 days are right) |
| Jul-Oct +$570 a month: is it a few lucky days? | **Yes, mostly.** ATLAS made 27.9 R in Jul-Oct; 25.5 R came from 5 days (Jul 24, Jul 15, Aug 7, Aug 4, Oct 2). Without them: **-$23 a month** vs Zlarior alone |
| Same test, a different 16 weeks like Jul-Oct (resampled weeks) | Gain median +$567 a month; **$0 or worse in 14%** of the histories |
| Jan-Jun gain without ATLAS's 5 / 10 best days | **Still +$714 / +$445 a month** (solid) |
| 2022 alone (a year Zlarior was good) | **-$108 a month** vs Zlarior alone (study said -$113: right) |
| Evals dying inside 2 weeks (weeks kept together, not shuffled days) | Jul-Oct **8.8%** (study 2.1%), Jan-Jun 2.8%, 2021-25 34% (Zlarior alone 0.5%) |
| MFFU moves you to a LIVE account after the 5th payout (sim accounts go dormant) | A funded combo 50K gets 5 payouts within 6 months in 81% of Jul-Oct runs (alone 33%). Counting only up to then: gain **+$428** a month, not +$569 |
| Worse fills (+2 ticks every entry and exit) | Still +$533 (Jul-Oct). Costs are not the problem |
| Zlarior closes ATLAS when it goes the other way (today's live rule) instead of "first in keeps it" | +$484 Jul-Oct, +$918 Jan-Jun: also fine |

What it means in $: in a Jul-Oct-like market the middle guess is **about +$570 a month more**, but 1 stretch in 7 gives
$0 or less (1 in 10: -$70 or worse; 1 in 10: +$1,260 or better). It depends on ATLAS catching its few big trend days. It rarely costs you much in 2026-like markets; in a 2022-like market it costs about
$110 a month (more evals bought: ~7 in 6 months instead of ~3 in a 2021-25-like market).

Next (paper only):
1. Decide the card `zlarior-atlas-50k` knowing the gain is "likely, not sure" (Jul-Oct-like: about +$570 a month, $0 or less 1 time in 7).
2. If yes, the lead builds the account lock below (section 6) and Sim-tests it before you arm anything.
3. Re-check after November with the new days: `/home/user/heavy.sh python -X utf8 tools/money/combo_account.py study`

## 1. Claim by claim

| Claim (study) | Verdict | Key number (mine) |
|---|---|---|
| Builder 50K Z+A $1,888 / $1,286 / $44 a month vs Z $827 / $714 / -$7 | **holds** (arithmetic) | $1,863 / $1,305 / $42 vs $826 / $736 / -$11 |
| Eval median 5-7 days vs 9-10 | **holds** | 5 / 7 vs 9 / 10 |
| Funded pays within 30 days 74% vs 53% (Jul-Oct) | **holds** | 76% vs 56% |
| 2-week eval fails 0.1% -> 2-4% (2026), 0.5% -> 34% (2021-25) | **weak** (2026 understated) | week blocks: Jul-Oct 8.8%, Jan-Jun 2.8%; 2021-25 34% |
| +$572 a month Jul-Oct, "> 2 SE" | **weak** | 5 ATLAS days carry it: without them -$23; resampled weeks: <= $0 in 14% |
| +$1,060 a month Jan-Jun | **holds** | +$714 without ATLAS's 5 best days, +$445 without 10; resampled weeks <= $0 in 0.5% |
| 2021-25 +$51, "> 2 SE" | **weak** | +$53 but worse in 65% of runs; +2 ticks +$22; 2022 -$108 |
| Gain is ATLAS's edge, not variance (placebo) | **holds** | agrees with the drop test: no ATLAS big days, no gain |
| 160 rows x 3 periods, 54 judged, 8 passed, 1 proposed | **holds** (counted in the results file) | but "2 SE" is Monte Carlo noise only, see 4 |
| Inputs = real backtests at today's rules, no look-ahead | **holds** | see 2 |
| One-account mechanics, MFFU rules, $ math | **holds**, one rule missing | MFFU live move after payout 5: +$428 instead of +$569 |

## 2. Trade inputs (check 1)

- **Zlarior:** the study's 631 trades (80 Jan-Jun, 40 Jul-Oct, 511 in 2021-25) are the same 631 as
  `research/anatomy/trades_lit.json` (built today from the live loop): same day, entry minute and side for all 631, R
  equal within 0.06 (the anatomy R has the costs in). The only other difference: 14 time-cut exits (CUT_T15) are stamped
  1 minute earlier in the study's file (same result; it frees the account 1 minute sooner, too small to matter).
- **ATLAS:** all 1,218 trades match the stored member trades (`second_mix_units.pkl`, EMA / MACD / S-R) exactly on
  day, entry, side, stop and points. ATLAS's own rules hold: never two ATLAS trades at once, at most 2 a day.
  - This is NOT the live ATLAS of the 25K (`research/anatomy/trades_atlas.json`): that one is cut around Zlarior on
    another account (HEDGE closes, armed-setup blocks). 2021-25: raw ATLAS +130 R vs live +60 R (partly costs in the
    anatomy R, partly the cuts). On one account the account rule replaces those cuts, so raw is the right input; but the
    LIT-armed block still matters live, so I re-ran with it: it removes 2 ATLAS trades in Jul-Oct (-1.0 R): no change.
- **No look-ahead found:** every exit is on its own day, Zlarior's latest exit 16:00, ATLAS 15:55 (MFFU 16:10).
  ATLAS's exit time is the close of its exit bar (conservative for "one at a time"). Targets (VIX band) use the prior
  close. Stops are filled 1 tick worse (all 909 stops). Small soft spot: ATLAS's worst open loss skips its own entry bar,
  so a floor touch inside the first 5 minutes could be missed (rare: sizes keep a full stop-out inside the room).
- **Out of sample?** Zlarior: picked on Jan-Jun, checked on Jul-Oct. ATLAS: its tweaks were picked on Jan-Jun
  (atlas.md), but its members were built with 2021-25 and 2026 in view: none of the three periods is fully unseen for ATLAS.

## 3. One-account mechanics and MFFU rules (checks 2-4)

My simulator (scratch, ~250 lines) reads the rulebook (`research/lit/mffu_rules.json`, Builder 50K) and calls only the live
sizing functions. It does: one position on the account (a signal while anything is open is skipped, either side), sizes
each trade from the room left at that moment (balance + today's closed P&L - trailing floor), the $1,000 soft day across
both bots (a trade crossing it is cut there, +1 tick), the intraday floor touch with open losses, the floor moved only at
the close from BOTH bots' day, locked at +$100, 40 micros, $1.90 a micro, eval stuck under $200, funded stuck under $100,
funded payouts (buffer $2,100, $500-$2,000, 2 days, 50% best day, 48 h, the bot asks at $1,500 above buffer, 80%,
5 payouts), 2 sessions of paperwork, a new $91.80 eval after every fail / loss / 5th payout.

- Same $ as the study within noise in all three periods (table in 1). Overlaps really skipped: on the real days Zlarior
  loses 22 trades to ATLAS in Jan-Jun (13 same side +17.6 R, 9 opposite -1.9 R) and 7 in Jul-Oct (5 same side +10.2 R);
  ATLAS loses 10 / 4.
- Builder 50K and 25K numbers match the rulebook line by line. Rapid EOD 25K: 30% best day + 4 days and $1,000 EOD are
  right but its row comes from `research/props/firm_rules.json` marked unverified (2026-10-18), and it is not in mffu_rules.json.
- **$ math by hand (Jul-Oct, the study's own file):** Z+A owner $1,317 a month - fees $185.3 / 6 = **$1,286**; 2.02 evals x
  $91.80 = $185.4. Z: $735 - $127.1 / 6 = **$714**. The 80% split is applied once, every re-buy is counted, the first eval too.
- **Missing rule:** the rulebook says after the 5th Builder payout MFFU moves you to a LIVE account and the sim accounts go
  dormant. The study buys a new eval and keeps going. A funded combo account gets its 5th payout within 6 months in 81% of Jul-Oct runs (alone 33%;
  per 6-month slot 0.72 vs 0.18 times). Stopping the count at that point: Jul-Oct gain **+$428** (Jan-Jun +$475). Also: your other sim accounts
  (ATLAS funded 25K, Zlarior 25K #2) would go dormant sooner - not in anyone's numbers.

## 4. Robustness (check 5) - where it breaks

Jul-Oct is 78 trading days. ATLAS traded 42 of them for +27.9 R; its 5 best days made 25.5 R. The study's "> 2 standard
errors" measures only the shuffling noise of 2,000 runs drawn from those same 78 days, not the chance that the next
78 days are different.

| Test ($ a month gap, Z+A minus Z, Builder 50K) | Jan-Jun | Jul-Oct | 2021-25 |
|---|---:|---:|---:|
| Study | +$1,060 | +$572 | +$51 |
| Mine, days drawn (same method, own code) | +$1,037 | +$569 | +$53 |
| Weeks drawn (a week's days stay together) | +$1,075 | +$543 | +$64 |
| ATLAS's trades removed on its 5 best days | +$714 | **-$23** | - |
| ... on its 10 best days | +$445 | **-$317** | - |
| Its 5 best days removed for both bots | +$771 | -$17 | - |
| Resampled histories (the weeks themselves redrawn, 200 x): median / 10% worst / share <= $0 | +$1,087 / +$641 / 0.5% | +$567 / -$73 / **14%** | - |
| Count stops at the 5th payout (MFFU live move) | +$475 | +$428 | +$53 |
| +1 / +2 ticks every entry and exit | +$1,034 / +$1,017 | +$558 / +$533 | +$37 / +$22 |
| Zlarior closes ATLAS when it enters the other way | +$918 | +$484 | +$42 |
| ATLAS blocked while Zlarior has an opposite setup armed | +$1,025 | +$561 | +$54 |

By year (days drawn): 2022 **-$108**, 2023 +$92, 2024 +$34, 2025 +$111 (weeks drawn: 2022 -$131). In every year of
2021-25 the combo is worse than Zlarior alone in 56-76% of runs: it buys 2-3x more evals and lives on the rare runs
where ATLAS gets funded and pays.

Leave one week out (Jul-Oct, 16 weeks, 1,000 runs each): the gain stays between +$199 and +$787. The week that matters
most is Aug 3-7 (two of ATLAS's 5 best days): without it +$199. No single week makes the gain; the 5 big days spread
over 4 weeks do, and losing all of them (or a market that does not give them) takes the gain to about $0.

2-week eval fails with weeks kept together: Zlarior alone 0.5% / 0.5% / 0.5%, Zlarior + ATLAS 2.8% / **8.8%** / 34%
(Jan-Jun / Jul-Oct / 2021-25). Bad ATLAS days come in bunches, so drawing single days hides how often two bad weeks open
an eval. Every one is a $91.80 re-buy (already in the $).

## 5. The two-account picture (check 6)

Today: Zlarior on the 50K eval and the 25K #2 eval, ATLAS on its FUNDED 25K. Live rule today: Zlarior has priority (ATLAS's
25K is closed at market when Zlarior enters the other way, "HEDGE"), the 25K #2 already waits for ATLAS's close, and ATLAS
never enters against Zlarior's open trade or armed setup.

"First in keeps the account" on the 50K makes the cross-account picture **better, not worse**, if it is applied to every account:
- ATLAS in first (same signal on the 50K and its 25K, same side = allowed): Zlarior waits on the 50K, exactly like the 25K #2
  already does. No opposite position anywhere, and ATLAS's funded 25K is no longer hedge-closed by Zlarior's 50K (those
  closes cost ATLAS about 8 R in Jan-Jun, 1.8 R in Jul-Oct, 4 R in 2021-25).
- Zlarior in first: ATLAS is skipped on the 50K (one position); on its 25K today's no-hedge rule already skips an opposite
  ATLAS signal and allows a same-side one. No hedge.
- Price: ATLAS now trades the same signal on two accounts. A bad ATLAS day hits the 50K and the funded 25K together (and
  the funded 25K already strands ~9% of accounts at its $100 stuck line, atlas-health-2026-11-18.md). Not in any number here.
- Zlarior loses its same-side trades on the 50K while ATLAS holds (Jan-Jun 13 trades, +17.6 R) - already in the $.

## 6. What the live build must do (for the lead, before any Sim test)

1. One position per account at the NinjaTrader account level: before either bot routes on the 50K, check the account's
   real position AND the other bot's working entry orders; skip if either exists (NinjaTrader nets one account: an ATLAS
   sell against Zlarior's long would close it, not hedge it).
2. When ATLAS fills on the 50K, cancel Zlarior's resting limit entries on the 50K (both sides) - otherwise a fill either
   adds to ATLAS (untested "adds") or flattens it. Keep ATLAS's existing "Zlarior armed opposite = no entry" rule on the 50K
   (it costs nothing: 2 trades in Jul-Oct).
3. One bracket (stop + target) per account: only the open bot's OCO lives on the 50K.
4. One fleet-wide direction lock: no account opens against an open position on any other account (Zlarior 50K and 25K #2
   wait for ATLAS; ATLAS skips against Zlarior). Use the SAME first-in rule everywhere, or re-run the study if the 50K
   keeps "Zlarior priority" (tested above: +$484 Jul-Oct, also fine).
5. Both bots size from the 50K's shared room at the moment of entry (Zlarior: two_week room 40% to session 80; ATLAS:
   account_b need size on the builder50k preset, zombie-eval $200, last bullet; funded: 60% of room <= $1,500, winner <= $2,000);
   the $1,000 soft day counts both bots.
6. Re-run the study after the build if anything differs (adds, priority, sizes).

## 7. Files

Scratch only (not in the repo, may be cleared): /tmp/claude-0/-home-user/1c5df1a3-c52b-5e3b-a05e-7ae8d672b70d/scratchpad/rt/
(`rt_sim.py` the independent simulator; `exp_base.py`, `exp_robust.py` week / years / drop / pool / jack / misc / armed /
zprio, `exp_funded.py`, `cmp_inputs.py`, `overlap.py`; results `robust_*.json`, `pool_*.log`, `jack_H2.log`).
Inputs read: research/lab/combo_account_trades.json, research/anatomy/trades_lit.json / trades_atlas.json, the repo's
research/runs/_cache second_mix_units.pkl and atlas_lit_armed.pkl. Nothing in `live_model*.json` or the engine was touched.

## 8. Verdict

Put Zlarior + ATLAS on the Builder 50K: **only if** the lead first builds the account-level lock of section 6 (one
position, cancel Zlarior's resting order when ATLAS fills, one bracket, one fleet-wide direction) and it passes Sim, and you
take the gain as "likely, not sure": Jan-Jun-like +$700 to +$1,100 a month (solid), Jul-Oct-like about +$570 (it rests on
ATLAS's few big trend days; 1 in 7 resampled histories is $0 or worse), 2021-25-like about $0 with 2-3x the eval re-buys
(2022-like -$110). The study's "8 passed, 1 proposed" is counted right, but its "> 2 standard errors" is Monte Carlo noise,
not proof about the next months.
