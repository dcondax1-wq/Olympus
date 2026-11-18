---
title: Rapid EOD 25K - which LIT lane rule under the 30% best-day rule
family: risk
date: 2026-11-18
status: done - paper only. Rule (b) "1 micro, bank at the day's room" is a small win on speed and payout in both 2026 halves; built OFF in engine/rapid.py + engine/multi_account.py; owner yes/no. Nothing live changed.
summary: On the Rapid EOD 25K eval, today's guard skips 65% (Jan-Jun) / 60% (Jul-Oct) of LIT trades because 1 micro's winner pays more than the day's $427 room. (b) taking those at 1 micro with the exit limit at the room passes in 28 / 20 sessions vs 31 / 25, first payout 45 / 44 vs 48 / 50 sessions from buying, $2,317 / $1,038 vs $2,312 / $972 a month; costs 60-session fails 1.3 / 1.4% vs 0.3 / 0.7% (2-week fails 0% either way). (c) letting the day break 30% and (d) LIT off are both clearly worse.
runs: none (research/lab/rapid25_lit_lane.json)
---

## For the owner

**ZEUS on the Rapid 25K: let Zlarior take the trades it skips today, at 1 micro, and close them at the day's room
($427 minus what is already made today).** Small win, your call; it is built and OFF.

| Rule for LIT on the Rapid 25K eval (a month to you, after the $97.20 fee) | Jan-Jun 2026 | **Jul-Oct 2026** | 2021-25 |
|---|---:|---:|---:|
| (a) today: skip when 1 micro's winner is too big | $2,312 | $972 | -$6 |
| **(b) 1 micro, close at the day's room** | **$2,317** | **$1,038** | $3 |
| (c) 1 micro, normal target, let the day break 30% | $1,557 | $916 | -$9 |
| (d) LIT off in the eval (ATLAS only) | $1,719 | $754 | -$3 |
| Eval pass, median sessions: a / **b** / c / d | 31 / **28** / 33 / 41 | 25 / **20** / 27 / 33 | 33 / 31 / 32 / 36 |
| First payout from buying, median sessions: a / **b** | 48 / **45** | 50 / **44** | 68 / 68.5 |
| Eval fails in 2 weeks: a / **b** | 0% / 0% | 0% / 0% | 0.3% / 0.5% |
| Eval fails in 60 sessions: a / **b** | 0.3% / **1.3%** | 0.7% / **1.4%** | 57% / 60% |

(21 sessions = about a month. 2021-25 = a market where the bots have no edge: about $0 either way.)

- The catch: (b) trades more, so about **1 more eval in 100 fails** within 60 sessions (still 0 in the first 2 weeks), and in
  Jan-Jun the worst 10% of 6-month runs make less ($235 vs $482 a month). Faster in the middle, a bit worse in the tail.
- To turn it on (after your yes), at the PC: `python -X utf8 -m engine.rapid --lit-bank on` then START BOT + your phrase.

## 1. The problem (tonight's rehearsal, confirmed here)

The Rapid EOD 25K eval needs the best day <= 30% of the profit; the bot keeps a winning day under 30% x $1,500 x 0.95 =
**$427** (including ATLAS's closed $ today). LIT's targets are about 6x the stop (banked at 8R), so on the 25K **64% of
Jan-Jun and 58% of Jul-Oct LIT trades have a 1-micro winner above $427** (28% in 2021-25). In the eval Monte Carlo the guard
skips **65% / 60% / 28%** of the LIT trades the sizing wanted to take: ATLAS does most of the trading.

## 2. MFFU's rule (research/lit/mffu_rules.json, rapid_eod_50k.eval; the 25K uses the same)

"best day <= 30% of the profit; **not a breach, trade more days**" (status confirmed, MFFU help center + plan page). It is
checked at the PASS, not intraday: a too-big day does not fail the eval, it raises the profit needed (best day / 0.3).
So (c) is legal; "pause until the other days catch up" is not a thing - you have to keep making money to dilute it, and
pausing only delays the pass. (c) was modelled as "keep trading normally".

## 3. How it was tested

`tools/money/rapid25_lit_lane.py` on `tools/money/rapid25.py` "25K, keep $500" (same stored LIT + ATLAS trades, costs $1.90
a micro + 1 tick, ATLAS $250 / 30% of the room with today's guard, Tier-1 news flat on the funded account, eval 2,000 paths x
60 sessions seed 7, 6-month slot 1,000 x 126 seed 23, eval -> funded -> re-buy at $97.20). Row (a) reproduces rapid25
exactly ($2,312 / $972 / -$6, eval 31 / 25 / 33). Only the eval's LIT lane changes (funded has no best-day rule).

- (b) when the guard says 0 micros: 1 micro with a limit exit at entry +/- (room $ + $1.90) / $2, rounded down to a tick.
  It fills only if the trade's own best excursion (ledger mfe_r, which excludes a limit fill bar and checks the stop first
  in each bar) went **1 tick through** that price; otherwise the trade's own outcome. Taken only if the bank is >= 1R and
  nearer than the target. 1R was fixed before the run; 0.5R / 2R give the same result, 3R a little less (H2 $1,021).
- (b+) the same bank but at LIT's full size; (c) 1 micro at the normal target; (c+) no guard on LIT; (d) LIT skipped.
- Picked on Jan-Jun with "60-session fails <= 2%, 0 in 2 weeks": (b+) is fastest but fails 3.8%; (b) is the pick. Checked on
  Jul-Oct: (b) is better on $ (+$66), pass (20 vs 25) and first payout (44 vs 50); fails 1.4% vs 0.7%.

## 4. Results (H1 = Jan-Jun 2026, H2 = Jul-Oct 2026, REF = 2021-25; H1 / H2 / REF in each cell)

| Rule | eval median | 2-wk fail % | 60-s fail % | 60-s pass % | 1st payout from buying | **$/mo** | worst 10% $/mo | no pay 6m % |
|---|---|---|---|---|---|---|---|---|
| a skip (today) | 31 / 25 / 33 | 0 / 0 / 0.3 | 0.3 / 0.7 / 57.2 | 88.0 / 89.2 / 15.0 | 48 / 50 / 68 | **2,312 / 972 / -6** | 482 / -16 / -65 | 6.6 / 18.4 / 92.2 |
| **b 1 micro, bank at the room** | **28 / 20 / 31** | 0 / 0 / 0.5 | 1.3 / 1.4 / 59.5 | 85.9 / 94.0 / 17.4 | **45 / 44 / 68.5** | **2,317 / 1,038 / 3** | 235 / -16 / -65 | 7.4 / 17.5 / 89.8 |
| b+ full size, bank at the room | 21 / 19 / 22 | 0.2 / 0 / 1.9 | 3.8 / 4.0 / 69.3 | 83.5 / 84.8 / 21.1 | 38 / 45 / 71 | 2,422 / 987 / 6 | 204 / -16 / -81 | 8.4 / 19.8 / 87.6 |
| c 1 micro, let the day break 30% | 33 / 27 / 32 | 0 / 0 / 0.5 | 1.1 / 1.9 / 60.8 | 54.1 / 85.0 / 14.3 | 63 / 53 / 71 | 1,557 / 916 / -9 | -16 / -16 / -65 | 22.9 / 19.8 / 92.1 |
| c+ no guard on LIT | 49 / 41 / 38 | 0.1 / 0 / 2.1 | 3.8 / 4.3 / 68.0 | 8.4 / 31.6 / 2.3 | 98 / 82 / 75 | 393 / 435 / -41 | -16 / -16 / -81 | 64.3 / 44.3 / 98.1 |
| d LIT off in the eval | 41 / 33 / 36 | 0 / 0 / 0 | 0.1 / 0 / 34.2 | 62.2 / 71.0 / 13.3 | 63 / 60 / 72.5 | 1,719 / 754 / -3 | -16 / -16 / -49 | 14.9 / 26.7 / 93.8 |

- **Why (b) helps:** the skipped trades still have an edge at 1 micro. Most never reach the bank (only ~1 in 7 of the extra
  trades fills it: in H1, per trade +$26 with the bank vs +$50 at the full target), but they add small wins and traded days
  (MFFU wants 4) without ever breaking 30%.
- **Why (c) loses:** one big LIT day sets the best day high; then the eval needs best / 0.3 in profit, and the guard keeps
  every later day small, so passes slow down (H1 60-session pass 54% vs 88%).
- **Why (d) loses:** ATLAS alone is slow (41 / 33 sessions); it fails less in 2021-25 (34% vs 57%) but earns no more there.
- Trades / week, PF, net $, max DD of the LIT + ATLAS mix are unchanged (same stored trades; rapid-levers section 2:
  7.2 / 5.5 / 7.0 a week, PF 3.12 / 2.74 / 1.07); only which LIT trades the eval takes and how they exit changes.
- Not a strategy change: the same LIT signals; only this account's size (1 micro) and exit (the best-day room) change in
  the eval when the guard would skip. "Eval-only 3-6R bank" in docs/TESTED_AND_REJECTED.md was a different idea (every
  LIT trade on the Builder eval); this one touches only the trades the 25K skips today.

## 5. What was built (OFF)

- `engine/rapid.py`: `lit_bank()` (1 micro, exit = entry +/- the room in points, >= 1R, nearer than the target),
  `bank_pnl()` (booked at the bank when the model went 1 tick through it, else the model's own $, never above the bank),
  `lit_bank_on()`, lane_spec passes `lit_bank` only for a 25K block with `"lit_bank": true`, CLI `--lit-bank on|off`.
- `engine/multi_account.py` (Rapid lane only, when the spec has `lit_bank`): qty_for takes 1 micro instead of the skip,
  the bracket's target = the bank price, the exit books the bank $ (reason "BANK (best-day room)"), the bank survives a
  restart. Eval only; funded, the 50K and every other account are unchanged.
- Tests: `tests/test_rapid25.py` section g (14 new checks, 69/69); `tests/test_rapid.py` unchanged 60/60.

## 6. Honest limits

- Fills: the bank assumes a 1-tick trade-through fills the limit; the booked $ is decided at the model's exit (the bot does
  not see the broker's fill earlier), so ATLAS stays blocked until LIT's model trade ends - as in the backtest.
- The gain is modest (+$5 / +$66 a month, 3-6 sessions sooner) and costs ~1 point of 60-session fails; in H1 the worst 10%
  of runs are worse. This is a speed vs tail choice, not a free lunch.
- 2026 is an unusually good year; 2021-25 has no edge for either rule.
