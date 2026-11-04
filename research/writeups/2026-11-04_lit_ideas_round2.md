---
title: LIT ideas round 2 - scale-in again (bootstrap by session, best trades removed in steps) and six more new ideas (Asia-slot result, level age, level touches, sweep-then-reclaim time, level reuse, cut time by setup type); plus the Plutus numbers fixed
family: other
date: 2026-11-04
status: nothing to switch on; scale-in is more robust than the "three trades" read suggested (still needs your Sim roundtrip); 27 new versions, none passes the gate; two leads (few-touches size, level-reuse size) are not strong enough; Plutus rebuilt from the live-settings inputs
summary: Job 28. (1) Scale-in at LIT size re-measured with a bootstrap over sessions and over weeks and with only the best 1, 2 or 3 trades removed. (2) Six new LIT ideas, 27 versions on the exact live trades (the re-walk equals all 631 live trades), judged Jan-Jun pick / Jul-Oct check, costs in, size tilts shuffle-tested. (3) Plutus (plans.json) rebuilt from the live-settings research files instead of the 10-19 study.
runs: research/lit/ideas_round2_grid.json, ideas_round2_scale.json; tools/lit_ideas_round2.py
---

## For the owner (one minute)

| What | Result |
|---|---|
| Plutus numbers | **Fixed, rebuilt from the research files** (not hand-edited): Builder 50K funded **$929 / $915** a month, live 2-week eval pass / fail **52.9 / 17.8** and **58.6 / 20.9**, first payout shown **both ways** (26 / 23.5 sessions from the funded start, 49 / 44 from the purchase), ATLAS 25K ($43) and BLITZ 25K ($63) rows, correlation per pair (LIT x ATLAS +0.14, LIT x BLITZ -0.06, ATLAS x BLITZ 0.00, **0.85 only for copies of one strategy**), the MFFU cap **1 funded 50K + 2 funded 25K = 3 accounts**, and the 3-account result **$1,532 / $1,136 with the honest range $1,100-1,800**. Page wording, the Zenith "Path to $3K / $5K / $10K" card and the tests are updated. |
| Scale-in (still OFF), again | The gain is **not just three lucky trades**. Jan-Jun +$10,621 (35 trades), Jul-Oct +$5,344 (18). Bootstrap by session: positive in **93% / 99%** of resamples; by week **97% / 100%**. Remove the single best trade: +$7,692 / +$3,576 (88% / 98% positive). Remove the best three: +$2,275 / +$1,653. Real-cost drag (+4 ticks an add, live $1.90): $362 / $112. Still needs your Sim roundtrip; the one bad day (-$3,301, 2026-01-07) is the risk. |
| 6 new LIT ideas (27 versions) | **None passes.** Asia-slot result: only 11 LIT days in 2026 had an Asia-slot trade the same trading day: too thin to say anything. Level age, level touches, reclaim speed, level reuse, cut time by setup type: size tilts are the same as a random bigger size, or fail one half. |
| Closest to a lead | **Size x1.25 on a level touched few times** (bottom third): LIT +$2,988 / +$1,040 (2021-25 +$1,220), eval path +$5,813 / +$66, funded flat; one more 2-week fail in Jan-Jun (+0.8 points), shuffle p 0.49 / 0.07. And **size x1.25 when LIT's last trade swept the same level within 3 sessions**: +$6,813 / +$511, but Jul-Oct eval path -$1,433 and shuffle p 0.0 / 0.51 (Jan-Jun only). Neither switches on. |

Your steps: none. Not re-run because already tested: second entry after a BE (re-entry after BE: 30 trades, -3.35R), ES divergence at entry (`es_swept` size, round 1: chance).

## 1. Scale-in, honestly again (`tools/lit_ideas_round2.py scale`, `research/lit/ideas_round2_scale.json`)

What it is: the engine's scale-in as built (add after the breakeven on a 1m pullback), compared with today's run trade by trade at the LIT size rule, costs in, 2026 only. A "session" here is a trading day with a LIT trade (80 in Jan-Jun, 40 in Jul-Oct).

| | Jan-Jun | Jul-Oct |
|---|---:|---:|
| Trades with adds / add micros | 35 / 145 | 18 / 45 |
| Extra $ from the adds | **+$10,621** | **+$5,344** |
| Best 3 trade-days | +2,929, +2,913, +2,504 | +1,769, +1,010, +912 |
| Worst 3 | -3,301, -1,768, -802 | -404, -354, -272 |
| Best 1 removed / best 2 / best 3 | +7,692 / +4,779 / +2,275 | +3,576 / +2,566 / +1,653 |
| Bootstrap by session (5,000): 5th / 50th / 95th percentile | -1,335 / +10,247 / +22,661 | +1,529 / +5,174 / +9,724 |
| ... share of resamples above zero | **93%** | **99%** |
| Bootstrap by week: 5th percentile / share above zero | +985 / 97% | +2,083 / 100% |
| Bootstrap by session with the best trade removed: 5th percentile / share above zero | -3,131 / 88% | +639 / 98% |
| Real-cost drag: every add 4 ticks worse + live $1.90 (8 ticks) | -$362 (-$652) | -$112 (-$202) |
| **Net after 4 ticks + live commission** (and with the best trade removed) | **+$10,259 (+$7,330)** | **+$5,232 (+$3,464)** |

Reading: the earlier "three trades make 78% / 69%" is true but not the whole story. With the best trade gone it still makes $7.3k and $3.5k after costs, and a resample of the trading days is above zero in 88-99% of draws. The risk is the left tail in Jan-Jun (5th percentile -$1.3k by session, -$3.1k without the best trade): an add moved the stop on 2026-01-07 and turned a target winner into a BE (-$3,301). The eval path and funded side (round 1 / 10-30 numbers) are unchanged: adds on the eval only from session 5, none on funded. Still gated by your Sim roundtrip (`--sim-roundtrip-add`).

## 2. Six new ideas, written down before testing

| # | Idea | Why it could add money | Versions |
|---|---|---|---|
| 1 | **Asia-slot interaction**: the Asia slot (18:00-02:00, one trade, `lit_asia`) of the same trading day, finished before LIT's entry, sizes LIT: after a loss / a win x0.75 / x1.25, same or opposite direction | the overnight tape tells the day's character | 6 |
| 2 | **Level age**: hours since the swept level formed (old resting liquidity vs fresh) | older levels hold more stops | 3 |
| 3 | **Level touches**: how often the level was touched before the sweep | many touches = more resting stops, or an exhausted level | 3 |
| 4 | **Sweep-then-reclaim time**: 5m bars from the sweep to the CISD close | a fast reclaim is a trap, a slow one a trend | 3 |
| 5 | **One entry per level** (as size): the same level swept by LIT's trade in the last 3 sessions x0.75 / x1.25 | a level that already worked or failed | 2 |
| 6 | **Cut time by setup type**: the 15-minute check moved to 10 or 25 minutes for London vs NY, session boxes vs build-up levels, wide stops | one clock may not fit every setup | 10 |

Rules as always: Jan-Jun pick, Jul-Oct check, 2021-25 a reference line only, the LIT size rule and the live two_week eval path and the funded 50K as money, all from the same code as the 11-04 night (`tools/lit_ideas_night.py`, `tools/lit_edge.py`); size tilts keep every trade (cut points fixed on Jan-Jun terciles) and get the shuffle test (150 draws). Bar to beat: Jan-Jun +$33,901 (PF 4.98), Jul-Oct +$9,919 (PF 2.91); eval 2-week pass / fail 57.1 / 1.7 and 52.2 / 5.8.

## 3. Results

| Idea | Best version | Result vs today (Jan-Jun / Jul-Oct) | Verdict |
|---|---|---|---|
| Asia-slot result / direction | any | 2026 has 17 Asia-slot trading days; **11** LIT days with an Asia trade the same day. Changes 0-3 trades, +-$0.8k | not testable: far too few days (needs the Asia slot routed first) |
| Level age | fresh level x1.25 | LIT +$3,655 / +$173, eval +$4,177 / -$298, shuffle p 0.11 / 0.61 | Jul-Oct fades; chance |
| Level touches | few touches x1.25 | LIT +$2,988 / +$1,040, 2021-25 +$1,220, eval +$5,813 / +$66, funded -$1 / +$10, **fails +0.8 (Jan-Jun)**, shuffle p 0.49 / 0.07 | **closest lead**, not a pass: Jan-Jun gain is size, Jul-Oct p 0.07 on 8 changed trades |
| Level touches | many x1.25; many x1.25 + few x0.75 | +$1,616 / +$187 (eval -$1,907 / -$1,281); -$1,821 / -$2,491 | no |
| Sweep-then-reclaim time | fast x1.25 | LIT +$673 / +$506, eval -$1,138 / +$709, p 0.89 / 0.31 | chance |
| Sweep-then-reclaim time | fast up + slow down; slow down | -$3,095 / -$481; -$3,768 / -$987 | no: slow reclaims are not worse |
| One entry per level | same level again x0.75 | -$8,500 / -$1,578 | no: repeat sweeps are better, not worse |
| One entry per level | same level again x1.25 | LIT +$6,813 / +$511, 2021-25 +$1,204, eval +$3,475 / **-$1,433**, p 0.00 / 0.51 | **lead in Jan-Jun only**: 25 trades changed in Jan-Jun, 10 in Jul-Oct; Jul-Oct eval path down |
| Cut time by setup type | London 10 min | LIT +$2,077 / +$212, eval -$2,483 / -$1,585 | no |
| Cut time by setup type | session box 25 min | LIT -$360 / -$454, eval +$1,425 / +$3,541, 2-week fails 0 / -5.8 | LIT size down, eval up: mixed, no |
| Cut time by setup type | London 25 / build-up 25 / wide stop 25 / NY 10 / NY 25 / box 10 / build-up 10 / wide stop 10 | all between -$1,240 and +$2,068 in one half, the other half <= 0 or the eval path down | no: 15 minutes stays the best single clock |

(27 versions, `research/lit/ideas_round2_grid.json`; the full table is in the appendix.)

## 4. What to change on the live bot (owner decides)

**Nothing.**
1. Scale-in: unchanged advice (eval only, from session 5, none on funded, after your Sim roundtrip). The robustness check removes the "three lucky trades" worry but not the single-trade tail risk.
2. Leads for a forward paper tally only: size x1.25 on a few-touches level; size x1.25 when LIT's last trade swept the same level inside 3 sessions. Neither beats chance in both halves with no more fails, and each is one of 17 size tilts tried tonight (a Bonferroni bar of p < 0.003, which 150 shuffles cannot resolve).

## 5. Rejected tonight and why

Asia-slot sizing (too few days); level age old/fresh (Jul-Oct fades, chance); many-touches size (loses on the eval path); reclaim-speed size (fast up is chance, slow down loses); one-entry-per-level as a size-down (repeat sweeps are better); every cut-time version (15 minutes stays best; none is up in both halves with the eval path up). Not re-run because already in "Tested and rejected": second entry after a BE stop, ES divergence at entry.

## 6. Plutus fix (what changed and what is still open)

- `tools/ares_plutus_build.py` now reads `research/lit/uprisk_*.json` (live settings 2026-10-25), `research/second/atlas_funded.json`, `research/scalp/ab_blitz_final.json`, `research/second/sn_plan.json`, `sn_corr.json`, `research/lit/mffu_rules.json`; `plans.json` carries a new `strategy` block (accounts, per-pair correlation, MFFU cap, 3-account result and range, by-count table) and its MFFU rows are the live-settings study (Builder 50K net $764 / $774 a month from purchase, funded $929 / $915; Builder 25K LIT $277 / $327, funded $445 / $405).
- The page (Notes tab) shows the strategy table, both first-payout counts, the cap and the range; the Risk tab says 0.85 only for copies and gives the pair correlations; the Zenith path card names the 3-account cap and your 3-strategy range.
- Tests: `test_plutus_page` 76/76 (Playwright included), `test_ares_page` 92/92 (the first full run timed out on the loaded machine at a page reload; rules.json is unchanged, the rerun passed), `test_goals` 47/47, `test_money_goal` 86/86, `test_zenith_shell` 23/23, `test_zenith_pages` 27/27.
- **Still open (flagged, not fixed here):** (1) the Lucid and FundedNext rows and the 3-firm "trio" are still the 2026-10-19 study (older LIT sizing; the trio is now the sum of the rebuilt MFFU row and the old Lucid / FundedNext rows: $1,966 / $2,460 a month, not a new Monte Carlo); (2) the site's `data.json` (`hub.funded` in `tools/hub_data.py`) still publishes the old trio ($1,754 / $2,315) from `funded_firms.json`, so the Plutus page now says "Differs from the trio on the published site: $1,754" until `funded_firms.json` is rerun with the live presets (`tools/lit_funded_firms.py`); (3) the Builder 25K row's 2-week pass / fail is still the 10-19 figure (49.2 / 9.0); (4) BLITZ has no funded-only study, so its row shows the research slot ($289 / $52) and the model ($191 / $140).

## Appendix - every version (change vs today)

| version | LIT $ vs today Jan-Jun / Jul-Oct | 2021-25 ref | eval-path $ Jan-Jun / Jul-Oct | 2-week pass change | 2-week fail change | funded $/mo change | trades changed (Jan-Jun / Jul-Oct) | shuffle p (Jan-Jun / Jul-Oct) |
|---|---|---|---|---|---|---|---|---|
| lvl_age_old_up125 | +839 / +463 | +506 | -606 / -917 | +0.0 / +0.0 | +0.0 / -1.5 | 11 / 13 | 12 / 7 | 0.833 / 0.427 |
| lvl_age_old_up125_fresh_dn075 | -2,785 / +92 | +1,249 | -12,045 / -3,823 | -15.9 / -1.5 | -1.7 / -1.5 | -3 / -14 | 29 / 13 | worse in a half |
| lvl_age_fresh_up125 | +3,655 / +173 | +562 | +4,177 / -298 | +0.0 / +0.0 | +0.8 / +0.0 | -1 / 1 | 13 / 5 | 0.113 / 0.607 |
| lvl_touch_many_up125 | +1,616 / +187 | +42 | -1,907 / -1,281 | +0.0 / +0.0 | +0.0 / -1.5 | 13 / 12 | 15 / 5 | 0.753 / 0.607 |
| lvl_touch_many_up125_few_dn075 | -1,821 / -2,491 | +547 | -10,314 / -6,986 | -17.6 / -4.4 | -1.7 / -1.5 | -7 / -43 | 38 / 16 | worse in a half |
| lvl_touch_few_up125 | +2,988 / +1,040 | +1,220 | +5,813 / +66 | +0.0 / +0.0 | +0.8 / +0.0 | -1 / 10 | 17 / 8 | 0.487 / 0.067 |
| reclaim_fast_up125 | +673 / +506 | +1,678 | -1,138 / +709 | +0.0 / +0.0 | +0.8 / +0.0 | 9 / 14 | 12 / 7 | 0.893 / 0.307 |
| reclaim_fast_up125_slow_dn075 | -3,095 / -481 | +4,224 | -3,844 / +2,715 | -15.1 / -5.8 | +5.0 / -5.8 | -15 / -4 | 34 / 16 | worse in a half |
| reclaim_slow_dn075 | -3,768 / -987 | +2,545 | -5,334 / +1,848 | -15.1 / -5.8 | -1.7 / -5.8 | -22 / -15 | 22 / 9 | worse in a half |
| reuse_dn075 | -8,500 / -1,578 | -2,250 | -14,586 / +1,556 | -30.2 / -8.7 | -1.7 / -5.8 | 7 / -24 | 36 / 13 | worse in a half |
| reuse_up125 | +6,813 / +511 | +1,204 | +3,475 / -1,433 | +2.6 / +0.0 | +0.0 / +0.0 | -2 / 4 | 25 / 10 | 0.0 / 0.507 |
| asia_lost_dn075 | -4 / +0 | +703 | +73 / +165 | +0.9 / +0.0 | +0.0 / +0.0 | 0 / 8 | 1 / 0 | worse in a half |
| asia_lost_up125 | +3 / +0 | -511 | +404 / -166 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 1 / 0 | worse in a half |
| asia_won_up125 | +842 / +0 | +1 | +616 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3 / 0 | worse in a half |
| asia_won_dn075 | -776 / +0 | -296 | -3,099 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | -1 / 0 | 3 / 0 | worse in a half |
| asia_same_dir_up125 | +891 / +0 | -225 | +1,582 / -166 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 2 / 0 | worse in a half |
| asia_opp_dir_dn075 | +44 / +0 | +285 | -180 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 1 / 0 | 2 / 0 | worse in a half |
| london_at10_rest15 | +2,077 / +212 | +0 | -2,483 / -1,585 | +0.0 / -1.5 | +0.0 / +0.0 | -4 / 27 | 15 / 4 | n/a |
| london_at25_rest15 | -587 / -1,240 | -24 | -38 / -4,112 | +0.0 / -8.7 | -1.7 / +0.0 | -13 / -146 | 14 / 5 | n/a |
| ny_at10 | -71 / -254 | +0 | -284 / -288 | +0.0 / +0.0 | +0.0 / +0.0 | -6 / -36 | 1 / 1 | n/a |
| ny_at25 | +60 / +0 | +0 | +1,209 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 5 / 0 | 4 / 0 | n/a |
| box_at10 | +1,961 / -420 | +0 | -611 / -1,435 | +0.0 / -1.5 | +0.0 / +0.0 | -8 / -49 | 7 / 6 | n/a |
| box_at25 | -360 / -454 | +0 | +1,425 / +3,541 | +0.0 / -1.5 | +0.0 / -5.8 | -13 / 5 | 15 / 8 | n/a |
| buildup_at10 | +75 / -2 | +0 | -2,133 / -694 | +0.0 / +0.0 | +1.7 / +0.0 | -1 / 0 | 13 / 1 | n/a |
| buildup_at25 | -376 / -1,243 | -24 | -1,839 / -3,728 | +0.0 / -7.3 | +0.0 / +0.0 | -21 / -165 | 8 / 3 | n/a |
| wide_stop_at25 | +13 / -1,203 | +0 | +1,607 / -3,580 | +0.0 / -7.3 | +0.0 / +0.0 | -7 / -167 | 12 / 5 | n/a |
| wide_stop_at10 | +2,068 / -343 | +0 | -862 / -1,069 | +0.0 / +0.0 | +0.0 / +0.0 | -15 / -64 | 10 / 3 | n/a |
