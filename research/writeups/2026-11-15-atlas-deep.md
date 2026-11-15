---
title: ATLAS deep edge (2026-11-15) - the losers are not in the trades but in the account; a "zombie-eval rule" lifts the 25K slot +$59 / +$65 a month (built, OFF), every trade filter is chance
family: risk
date: 2026-11-15
status: adopt-candidate (zombie-eval rule, account_b "eval_min_room" 200 + "last_bullet" 0.8, built and OFF; owner decides). Rejected - 16 trade filters / size tilts from the loser autopsy (LIT won the other side, same-side retry or refusal, LIT on the same side, stop outliers, first-trade half size, weekly brake, daily trend, one trade per side)
summary: Team E-ATLAS. Baseline of ATLAS as it runs on the Builder 25K today (account-B rules, fees at the owner's $43), a loser autopsy of its 2026 and 2021-25 trades (member, side, hour, weekday, VIX, stop in points / ATR / vs the member's own median, target R, daily trend, LIT's day, the members' paper day, nth signal, exit), then 8 pre-declared new ideas (16 variants) and 2 ideas found by the autopsy of the account path (13 variants with neighbours and combinations). Main finding - in 2026 half of ATLAS's signals are never traded (H1 58 of 112, H2 26 of 51, worth +48R / +13R at a fixed risk) because an eval with a low room sizes to 0 micros and idles for weeks ("zombie"); today ATLAS trades 2.11 / 1.60 times a week on the account and only 48% / 38% of weeks have 2+ trades. The zombie-eval rule (give an eval up under $200 of room, and on a low room trade 1 micro when its full stop-out fits 80% of the room) - owner $ a month on the whole 25K slot $639 / $459 / $16 vs $579 / $394 / $11 (H1 / H2 / 2021-25), 2-week pass 67.2 / 43.5 vs 65.5 / 43.5, 3.95 / 2.95 trades a week (weeks 2+ 96% / 81%), paths that lose money 0.2% / 3.3% vs 6.8% / 17.8%. All 13 lifecycle variants lift the slot in both halves (a plateau with a clear mechanism, not a selection). No trade filter survives - the one that passes the slot test (skip ATLAS after LIT won the other side) moves 4 H2 trades worth -0.05R and random skips of the same size pass the 2026 test in 6.7% of draws.
runs: atlas_deep_today, atlas_deep_zombie, atlas_deep_stuck200, atlas_deep_last_bullet08, atlas_deep_lit_won_other, atlas_deep_same_side_lost_skip, atlas_deep_week_brake400, atlas_deep_against_trend_x0
---

## Money first

"Owner $ a month" = what one ATLAS 25K slot pays you a month over 6 months: eval -> funded -> MFFU payouts (80% to you,
5 payouts max) -> a new $43 eval after every fail, give-up or graduation (tools/atx_edge.slot, 300 paths x 3 seeds).
Eval-path trading $ is never paid out; this is the money.

| What | Jan-Jun | Jul-Oct | 2021-25 | 2-week pass (Jan-Jun / Jul-Oct) | Trades a week | Verdict |
|---|---:|---:|---:|---|---|---|
| **ATLAS today** | **$579** | **$394** | $11 | 65.5 / 43.5 | 2.1 / 1.6 | the bar |
| **Zombie-eval rule** (give up under $200 + 1-micro last bullet) | **$639 (+$59)** | **$459 (+$65)** | $16 (+$5) | **67.2 / 43.5** | **4.0 / 3.0** | **adopt-candidate (built, OFF)** |
| Give up under $200 only | $631 (+$51) | $442 (+$48) | $14 | 65.5 / 43.5 | 3.6 / 2.2 | same family |
| Last bullet only (80% of the room) | $629 (+$50) | $454 (+$60) | $13 | 69.7 / 43.5 | 3.8 / 2.8 | same family |
| Skip ATLAS after LIT won the other side today | $598 (+$19) | $423 (+$29) | $14 | 69.7 / 43.5 | 1.7 / 1.7 | chance (see below) |
| Every other trade filter / size tilt (14) | -$167 to +$13 | -$81 to +$0 | -$9 to +$3 | | | rejected |

In plain words: ATLAS's trades are fine; its eval wastes weeks. When an eval is down to $100-$400 of room, today's size rule
says "0 micros" (one stop-out would not fit half the room) and the account just sits there, often for the rest of the
month. The fix is to either give that eval up and buy a fresh $43 one (under $200 of room) or take its last shot with one
micro. Both bring the trading back to 3-4 a week and pass more funded accounts per half year (1.68 vs 1.49 in Jan-Jun,
1.27 vs 1.11 in Jul-Oct).

**Cost:** about 0.4 more evals per 6 months ($17) in 2026, 2.8 more ($120) in a 2021-25-like market; 1 in 10 Jan-Jun evals is
given up inside 2 weeks (that is the point: decided, not stuck). Funded accounts are unchanged.

## 1. Baseline: ATLAS as it runs today (Builder 25K, account-B rules, costs in)

The account path = back-to-back 25K evals with the real account-B rules (need size, one position, max 2 a day, never
against LIT incl. LIT's armed setups, $600 soft daily loss, stuck under $100), tools/atlas_v2.score (reproduces
atlas-v2.md exactly: 65.5 / 0.0 and 43.5 / 0.0, path +$6,485 / +$4,434).

| | 2026 H1 (Jan-Jun) | 2026 H2 (Jul-Oct) | 2025 | 2021-24 |
|---|---:|---:|---:|---:|
| Signals a week (after the no-hedge rules) | 4.38 | 3.27 | 4.84 | 5.37 |
| **Trades a week on the account** | **2.11** | **1.60** | 2.58 | 3.05 |
| Weeks with 2+ trades | 48% | 38% | 62% | 72% |
| PF (account path) | 2.30 | 3.18 | 0.82 | 1.05 |
| Net $ (one-start path) / $ a month | +$6,485 / +$1,064 | +$4,434 / +$1,194 | -$2,152 / -$175 | +$2,457 / +$63 |
| Max DD (path) | -$926 | -$816 | -$5,816 | -$7,805 |
| 2-week pass / fail / stuck | 65.5 / 0.0 / 0.8 | 43.5 / 0.0 / 0.0 | 30.1 / 0.0 / 23.3 | 22.9 / 0.0 / 27.1 |
| p15 / f15, median sessions to pass, slow_pass | 73.7 / 0, 5, 4.3% | 54.7 / 0, 6, 13.3% | 32.4 / 0, 4, 2.4% | 25.5 / 0, 4, 3.3% |
| **Owner $ a month (whole slot, $43 evals)** | **$579** | **$394** | $11 (2021-25) | |

At a fixed $500 a trade (every signal, no account): H1 112 trades PF 3.02 +$51.5k ($8.4k a month), H2 51 trades PF 2.73
+$16.5k ($4.4k a month), 2021-25 1,125 trades PF 1.09 +$30.3k ($595 a month). It is still a 2026 strategy: in 2021-25
74% of 6-month slot paths lose money.

## 2. Loser autopsy (research/second/atlas_deep_autopsy.json)

R per signal at a fixed risk, costs in; H1 / H2 / 2021-25.

- **Members:** EMA +0.69 / +0.93 / +0.02 R, MACD +1.36 / +0.47 / +0.10, S/R +0.91 / +0.42 / +0.07. No member or side
  loses in 2026; EMA short and S/R short lose a little in 2021-25 (-0.03 / -0.05).
- **Hours:** 06:00 and 11:00 lose in all three spans (-0.52 / -1.06 / -0.49 and -0.27 / -0.02 / -0.29, 2-9 trades a half);
  already tested and rejected as known spikes (atlas-windows-entries-2026-10-30.md). 03:00 makes most of the money.
- **Stops:** no stop bucket loses in 2026 (points, ATR, vs the member's own median). Stops under 25 points are the weak
  bucket in 2021-25 (-0.02 R, 483 trades). Stops wider than 1.6x the member's usual are the BEST in H2 and 2021-25.
- **Same side lost earlier today** (a member's paper trade or LIT): the retry is the best bucket in every span (+2.27 /
  +1.68 / +0.28 R): a stop hunt before the real move. So "refuted side" is wrong.
- **LIT won the OTHER side earlier today:** the one bucket negative in every span (-0.58 / -0.01 / -0.16 R) - but 9 / 4 / 42
  trades, and LIT's "win" is mostly a breakeven exit after +1R.
- **Daily trend, VIX tercile, weekday, target R, nth signal of the day:** no bucket that holds in all three spans.
- **The account, not the trades:** in 2026 H1 58 of 112 signals are never traded (46 on days with no ATLAS trade at all),
  in H2 26 of 51; they are worth +48R / +13R at a fixed risk. Of the 625 zero-size decisions in the H1 eval runs, 446
  come after session 10 on a room of $125-375: one micro's stop-out no longer fits half the room, so the eval idles
  ("zombie", first seen in atlas-v2.md, never measured on the owner's slot money).

## 3. The ideas (written in tools/atlas_deep.IDEAS before the first run) and results

Gate: better in BOTH 2026 halves on the owner's slot $ and the 2-week pass not lower, 2021-25 not worse, 2+ trades a week,
costs in. The old v2 rule (dead evals not up) is reported too: by design a give-up rule raises "dead", which here means
"decided".

| # | Idea | Variants | Jan-Jun slot | Jul-Oct slot | 2021-25 | Verdict |
|---|---|---:|---:|---:|---:|---|
| 1 | Skip / halve ATLAS when LIT already won the other side today | 2 | +$19 / +$10 | +$29 / +$15 | +$3 / +$2 | chance: random skips of the same 9 / 4 / 42 trades pass the 2026 test in 6.7% of 60 draws; its 4 H2 trades sum to -0.05R (the H2 gain is path luck) |
| 2 | Same-side trade already lost today: skip (refuted) / size x1.25 / x1.5 (retry) | 3 | -$82 / +$2 / -$2 | -$10 / -$2 / -$5 | -$3 / -$0 / -$1 | rejected (the retries are winners; up-size is noise) |
| 3 | Two accounts on one bet: skip while LIT holds the same side / after LIT won the same side | 2 | -$33 / -$20 | $0 / $0 | -$1 / $0 | rejected |
| 4 | Skip a stop wider than 1.6x / 2x the member's own median of its last 20 | 2 | -$13 / +$13 | -$68 / -$10 | $0 / +$3 | rejected (wide stops are good trades) |
| 5 | Eval trades at x0.5 / x0.75 until the eval is green | 2 | -$15 / -$7 | -$10 / -$6 | -$9 / -$6 | rejected (slower passes) |
| 6 | Eval weekly brake at -$400 / -$600 | 2 | $0 / $0 | $0 / $0 | $0 | rejected (never binds in a way that matters) |
| 7 | Daily trend (close vs its 20-day SMA): skip / halve against it | 2 | -$167 / -$28 | -$81 / -$25 | -$3 | rejected |
| 8 | One ATLAS signal per side a day | 1 | -$48 | -$34 | -$2 | rejected |
| 9 | **Last bullet** (from the autopsy): 1 micro when need size is 0 and its stop-out fits 60-100% of the room | 5 | +$43 to +$52 | +$54 to +$60 | +$2 to +$5 | passes, all 5 |
| 10 | **Give a zombie eval up** at the owner's $43 (was judged at $63 per eval in atlas-v2.md): under $150 / 200 / 250 / 300 / 400 | 5 | +$33 to +$73 | +$32 to +$81 | -$1 to +$4 | passes slot; 250-400 lower the 2-week pass (64.7-61.3), 400 loses 2021-25 |
| - | Combinations: bullet 0.8 + give up under $200 / bullet + idea 1 / give up 300 + idea 1 | 3 | +$59 / +$49 / +$65 | +$65 / +$69 / +$78 | +$5 / +$6 / +$3 | the first is the pick |

**Count:** 29 variants. Of the 16 trade-filter / size variants, 2 pass the slot test; at the 6.7% random-skip rate, 1.1 would
pass by chance, so ideas 1-8 found nothing. The lifecycle family (9, 10, combinations: 13 variants) passes 13 of 13 on the
slot in both halves: it changes no trade choice, only when an idle eval is ended or allowed one more micro, so it is not a
selection effect.

**Pick (H1 first, among the variants that keep both 2-week pass rates):** bullet 0.8 + give up under $200, H1 $639 (the best
of the 9). Check Jul-Oct: $459 (+$65), 2-week pass 43.5 (same), 0.0 fail. Years (slot $ a month, today in brackets): 2022
-$11 (-$6), 2023 +$42 (+$37), 2024 +$13 (-$1), 2025 +$41 (+$30); paths that lose money fall in every year.

| Zombie-eval rule vs today | Jan-Jun | Jul-Oct | 2025 | 2021-24 |
|---|---|---|---|---|
| Trades a week / weeks with 2+ | 3.95 / 96% (2.11 / 48%) | 2.95 / 81% (1.60 / 38%) | 4.28 / 94% | 4.69 / 99% |
| 2-week pass / fail / given up | 67.2 / 0.0 / 10.1 (65.5 / 0.0 / 0.8) | 43.5 / 0.0 / 0.0 (same) | 29.7 / 0.0 / 43.4 | 22.6 / 0.0 / 54.2 |
| Decided in 2 weeks (dec10) | 77.3% (66.3%) | 43.5% (43.5%) | 73.1% (53.4%) | 76.8% (50.0%) |
| p15 / f15, median to pass, slow_pass | 76.3 / 0, 5, 5.2% | 54.7 / 0, 6, 13.3% | 32.0 / 0, 4 | 25.0 / 0, 4 |
| PF / net / $ a month / max DD (path) | 3.08 / +$21,583 / $3,541 / -$898 | 2.37 / +$5,299 / $1,427 / -$1,592 | 1.26 / +$6,450 | 1.03 / +$3,039 |
| Owner $ a month (slot) | **$639** ($579) | **$459** ($394) | $16 for 2021-25 ($11) | |
| Funded accounts / evals bought / payouts per 6 months | 1.68 / 2.21 / 4.97 (1.49 / 1.82 / 4.50) | 1.27 / 1.56 / 3.57 (1.11 / 1.44 / 3.07) | 2.29 / 7.95 / 0.56 (1.48 / 5.15 / 0.37) | |
| Slot paths that lose money | 0.2% (6.8%) | 3.3% (17.8%) | 62% (75%) | |

## 4. What was built (OFF) and how to turn it on

`engine/account_b.py`, both keys absent = exactly today (tests/test_atlas_deep.py 16/16: parity of engine qty with the
research sizer on the 2026 path, 141 trades identical; test_second_account_b 45/45, test_account_b_funded 67/67,
test_atlas_v2_shadow 41/41):
- `"eval_min_room": 200` - the EVAL stage's stuck line (push "buy a new one"); the funded stage keeps `min_room` / $100.
- `"last_bullet": 0.8` - when the need size says 0 micros, 1 micro if its full stop-out (stop + 2 ticks, $1.90) fits 80% of
  the room; the soft daily loss guard still applies; never more than 1 micro.

Turn-on (owner decides; never automatic): add both keys to ATLAS's block in `data/account_b.json` on the PC.

## 5. Honest limits

- The slot money is a Monte Carlo of 2026 sessions (5-session blocks); +$59 / +$65 a month is about 10-16%, above the
  seed noise (+-$10) but not huge. 2021-25 stays near zero either way: no edge there, the rule only loses less time.
- The rule buys more evals: 2.21 vs 1.82 per 6 months in 2026, 7.95 vs 5.15 in a 2021-25-like market ($43 each, in the $).
- In Jul-Oct the last bullet never fires inside the first 10 sessions; its H2 gain comes later in an eval's life.
- MFFU: giving up an eval just means stopping it and buying a new $43 one; the 2-funded-25K cap does not bind for one slot.
- Ideas 1-8 rest on 2-20 trades a half per bucket; the autopsy is a description, not a model.

Files: `tools/atlas_deep.py` (autopsy, grid, placebo, slot, years, save), `research/second/atlas_deep_autopsy.json`,
`atlas_deep_grid.json` (29 variants, every number), `atlas_deep_slot.json` (slot per variant x seed, years),
`tests/test_atlas_deep.py`. Nothing in `second_model.json` or `live_model*.json` changed; nothing armed.
