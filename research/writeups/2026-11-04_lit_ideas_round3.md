---
title: LIT ideas round 3 (48 versions of 10 new ideas - quarterly / monthly / weekly levels, inside day, overnight-range percentile, CISD body, time since a win, month-of-year seasonality, limit window, breakeven trigger and cushion, cut time) and one number for every page (funded study rerun with the live presets)
family: other
date: 2026-11-04
status: nothing to switch on; one thin gate pass (the cut-check threshold mfe 0.6R, 2 trades changed) and one lead (a bigger breakeven cushion); every size tilt is chance; the published figures (Plutus, hub, Zenith) now come from one rerun study
summary: Job 29. Part A closes the open items from the Plutus fix - lit_funded_firms.py rerun with today's live trades and the live presets (eval room 0.8, funded 60% / <= $1,500 / winner <= $2,000), the Builder 25K row refreshed, BLITZ given a funded-only study, and every reader (Plutus plans.json, the dashboard hub snapshot, the phone export, Zenith's money card) regenerated so they all show the same figures. Part B is research round 3 on the exact live LIT trades, judged Jan-Jun pick / Jul-Oct check, costs in.
runs: research/lit/funded_firms.json, research/scalp/blitz_funded_study.json, research/lit/ideas_round3_grid.json; tools/lit_funded_firms.py, tools/blitz_funded_study.py, tools/lit_ideas_round3.py
---

## For the owner (one minute)

| What | Result |
|---|---|
| One number everywhere | **Done.** `lit_funded_firms.py` was rerun on today's live trades (the old unit file was the 10-18 rule set, without the 15-minute cut and the breakeven cushion) with the live presets. Plutus, Zenith's money card, the dashboard's `hub.funded` and the phone export now show the same figures: Builder 50K funded **$907 / $914** a month (Jan-Jun / Jul-Oct), live 2-week eval pass / fail **52.9 / 17.8 and 58.6 / 20.9**, first payout **26 / 23 sessions from the funded start and 40 / 41 from the purchase**, 3-firm trio **$2,655 / $2,147** a month, 3-account mix **$1,532 / $1,136** (range **$1,100-1,800**). The Plutus page now reads "Matches the trio on the published site: $2,147"; the old "Differs" note is gone. |
| Builder 25K row | Refreshed (it was the 10-19 figure 49.2 / 9.0): LIT on a 25K at the live presets, 2-week pass / fail **55.5 / 13.3 and 50.0 / 11.5**, funded **$428 / $396** a month, **$368 / $330** from the purchase. Your 25Ks have their own rows: ATLAS 2-week **65.5 / 0.0 and 43.5 / 0.0**, funded $582 / $517; BLITZ **49.6 / 26.9 and 36.2 / 21.7**. |
| BLITZ funded-only estimate | New study (`tools/blitz_funded_study.py`): a funded 25K at BLITZ's $150 size pays **$108 a month in Jan-Jun and $0 in Jul-Oct** on the 3-month-start estimate (22 and 6 starts: too few; the 6-month Monte Carlo that the pages now show is **$322 / $82**, see `2026-11-04_atlas_round3.md`). The page labels it an estimate. The whole slot incl. the eval stays $289 / $52 a month. BLITZ is a small earner. |
| Tests | Plutus 77/77, hub api 130/130, goals 47/47, money goal 86/86, Zenith pages 27/27, Zenith shell 23/23, autorun 100/100, cronos 88/88; Ares 92/92 (twice it timed out waiting for the page on the loaded machine; with the page-ready wait raised from 30 to 180 s it passes, kit restored); the Jarvis hub test (230 checks, unrelated to these files) is slow on this machine and was not re-confirmed. |
| Round 3: 10 new ideas, 48 versions | **No change to the live bot.** Levels (weekly / monthly / quarterly open, quarterly pivots): **0 trades added in 2026**. Inside day, CISD body, overnight-range percentile, time since the last win, month-of-year: all within shuffle chance. Limit window: 30 minutes stays best. Breakeven trigger: 1R stays best. |
| The two things worth a line | **Cut check needs best point 0.6R (not 0.5R) to be waived:** LIT +$86 / +$246, eval path +$172 / +$3,486, fails unchanged, funded +$5 / +$37 - but it changes 1 trade in each half. **A bigger breakeven cushion (3.75 pts instead of 1.25):** LIT +$960 / +$78, funded +$28 / +$3, 2-week pass +0.9 / +1.4, but eval-path $ -$1,187 in Jul-Oct. Both are leads for a forward paper tally, not changes. |

Your steps: none.

## Part A - one number for every page

What was wrong: `research/lit/funded_firms.json` (10-19) still carried the old presets (room 0.6; funded 40% / $800 / winner $1,500) and the 10-18 trade file, so Plutus, the dashboard hub and Zenith each showed a different slice of the old study; my 11-04 Plutus fix had patched the Builder rows from other files, which made the page disagree with the published trio ("Differs from the trio on the published site: $1,754").

What was done (research / display only; no trading code):
1. `tools/lit_funded_firms.py`: new `units` command rebuilds the two unit files from today's live LIT trades (`tools/lit_edge.trades`, 631 trades, 120 in 2026, the weekly-stop multiplier and the best open profit per trade); the Builder 50K and 25K plans now use the live presets (`LIVE_EVAL` room_f 0.8 then safe_eval; `FUNDED_MODE` 60% of the room, <= $1,500, winner <= $2,000, skip_breach; the 25K runs the same caps through the plan scale 0.5 = <= $750 and a winner <= $1,000); `overlay_engine_eval` puts the engine-faithful 2-week pass / fail (`research/lit/uprisk_eval.json`, the engine's own two_week sizing) over the study's approximation for the Builder 50K (the study's own 53.1 / 10.9 and 53.8 / 5.1 are kept as `eval_study`); `trio2125` adds the trio's 2021-25 reference line; `all` reran every plan and combo (12 minutes).
2. `tools/ares_plutus_build.py` reads the file again (the Builder rows are no longer patched from other files); the strategy block reads ATLAS from `second/atlas_funded.json`, BLITZ from `scalp/ab_blitz_final.json` + the new `scalp/blitz_funded_study.json`, the 3-account model from `second/sn_plan.json`. First payout is carried both ways per plan (`first_pay_funded`, `first_pay_sessions`).
3. The dashboard hub snapshot `tools/web_hub_snapshot.json` (data.json `hub.funded`: the trio) and the phone export `research/props/hub.json` (`firms`: the LIT fit per plan and the combos) were rebuilt from the same file; the test fixture carries the same trio.
4. Zenith's "Path to $3K / $5K / $10K" card reads `plans.json` (the steady rate $987 / $962 is now the months 4-6 rate of the rerun study; the 3-account row names your three strategies' range).

| Figure | Before (published) | Now (everywhere) |
|---|---|---|
| Builder 50K funded stage, a month to you | $758 / $736 (Plutus), $929 / $915 (docs) | **$907 / $914** (study; the docs' $929 / $915 are the uprisk Monte Carlo, within 2%) |
| Builder 50K from the purchase, net of fees | $618 / $562 | **$790 / $771** |
| 2-week eval pass / fail | 48.1 / 4.1 and 53.9 / 6.3 | **52.9 / 17.8 and 58.6 / 20.9** |
| First payout (sessions) | 43 / 47 (purchase) | **26 / 23 from the funded start, 40 / 41 from the purchase** |
| 3-firm trio (three copies of LIT), a month | $2,315 / $1,754 | **$2,655 / $2,147** (months 4-6 $3,292 / $2,792; 2021-25 reference -$92) |
| Builder 25K (LIT) 2-week pass / fail; funded; net | 49.2 / 9.0; $277 / $327 net | **55.5 / 13.3 and 50.0 / 11.5; $428 / $396 funded; $368 / $330 net** |
| BLITZ funded-only | none | **$108 / $0 a month (estimate; 45% / 100% of starts stuck)** |

Honest limits: Lucid and FundedNext rules are the 10-19 research (unchanged), their sizing is the study's own pick on Jan-Jun; the eval-fail figure for the Builder 25K is the study's approximation (no engine-faithful 25K run exists); the funded study's `loss_6m` of 1.5-2.4% is the study's, the uprisk run shows 0%.

## 1. Round 3 - the ideas, written down before testing

| # | Idea | Why it could add money | Versions |
|---|---|---|---|
| 1 | **Weekly / monthly / quarterly open and quarterly pivots as sweep levels** (a subclass of the engine's Market with extra level classes; the engine file is untouched) | big-timeframe opens are where stops rest | 7 |
| 2 | **Inside day** (the prior day inside the day before it): size x0.75 / x1.25 | a coil before expansion, or chop | 2 |
| 3 | **Overnight range percentile at the entry** (18:00 to the CISD close vs the same stretch on the last 60 days) | an active tape trends | 3 |
| 4 | **CISD candle body in ATR** (the trigger candle, not the displacement) | a strong close is conviction | 3 |
| 5 | **Sessions since LIT's last winner** (drought x1.25 / x0.75, fresh win x0.75 / x1.25) | regime memory | 4 |
| 6 | **Month-of-year**: top / bottom 3 months picked on 2021-25, checked on 2026, with a month-label permutation | seasonality, if it is real it repeats | 3 + permutation |
| 7 | **Limit window**: valid 15 / 20 / 25 / 35 / 40 / 45 / 60 minutes (live 30) | the fill rule | 7 |
| 8 | **Breakeven trigger** 0.75 / 0.9 / 1.1 / 1.25 / 1.5 R and **cost cushion** 0.5 / 2.5 / 3.75 pts (live 1.0R, 1.25 pts) and 3 pairs | protect sooner / later | 11 |
| 9 | **Cut check at 12 / 18 minutes** and its thresholds (best point 0.4 / 0.6R, close 0.2 / 0.4R below) | one clock | 8 |
| 10 | (quarterly pivots P and R1/S1, monthly and quarterly open counted inside idea 1) | | |

Not repeated because already in "Tested and rejected" or rounds 1 / 2: second entry after a BE, ES divergence, level touches / age, weekday, VIX sizes, partials.

Rules as always: Jan-Jun pick, Jul-Oct check, 2021-25 a reference line only; the LIT size rule, the live two_week eval path and the funded 50K as money; size tilts keep every trade and get the shuffle test (150 draws). Bar to beat: Jan-Jun +$33,901 (PF 4.98), Jul-Oct +$9,919 (PF 2.91); eval 2-week pass / fail 57.1 / 1.7 and 52.2 / 5.8. A first run of the breakeven versions through the entry engine changed nothing because the post-fill executor ignores engine exit params; they were rerun as post-fill options (`be_r`, `be_off` in `tools/lit_ideas_night.manage2`).

## 2. Results (48 versions, full table in the appendix)

| Idea | Best version | Result vs today (Jan-Jun / Jul-Oct) | Verdict |
|---|---|---|---|
| Levels | all five | **0 trades added in 2026** (trade list identical); 2021-25: 1 trade (-$111) | the engine's levels already cover these prices: no setup is left to add |
| Inside day | x1.25 | LIT +$831 / -$89, eval +$642 / -$1,296 | no |
| Overnight-range percentile | high x1.25 | LIT +$834 / +$643, eval +$2,738 / -$378, shuffle p 0.86 / 0.17 | chance; eval H2 down |
| CISD candle body | low x1.25 | LIT +$3,174 / -$222 | Jan-Jun only; "high" is worse in Jul-Oct |
| Time since a win | drought x1.25 | LIT +$2,793 / +$218, 2021-25 +$2,549, eval +$4,660 / -$280, shuffle 0.60 / 0.67 | chance; eval H2 down |
| Time since a win | fresh win x1.25 | LIT +$2,052 / +$294, eval -$1,487 / -$199, shuffle p_both 0.02 | eval path down: no |
| Month-of-year | picked on 2021-25 (Feb, Aug, Oct up; Jan, Mar, Apr down) | LIT **-$6,058 / +$987** | **fails**: the 2021-25 months do not repeat in 2026 (permutation p 0.997 in Jan-Jun) |
| Limit window | 15 / 20 / 25 min | -$5,072 / -$97 ; -$1,806 / -$609 ; -$1,842 / +$353 (fewer fills, fewer trades a week) | shorter loses |
| Limit window | 35 / 40 / 45 / 60 min | +$0 / +$4 ; -$83 / +$4 ; -$83 / +$4 ; -$4 / -$138 | 30 minutes is on a plateau (0-2 trades change) |
| Breakeven trigger | 0.75R / 0.9R | -$6,501 / -$5,049 ; -$931 / -$579 | earlier loses |
| Breakeven trigger | 1.1R / 1.25R / 1.5R | -$133 / $0 ; -$3,112 / $0 ; -$5,574 / $0 (2021-25 +$7,961 / +$14,271 at 1.25 / 1.5R: a reference line) | 1R stays |
| Breakeven cushion | 3.75 pts | LIT **+$960 / +$78**, funded +$28 / +$3, 2-week pass +0.9 / +1.4, fails 0 / -5.8, eval path +$1,498 / **-$1,187**, 2021-25 -$1,283 | **lead**: Jul-Oct is flat and the eval path loses |
| Breakeven cushion | 0.5 / 2.5 pts | -$288 / -$63 ; +$480 / -$47 | no |
| Cut check | threshold mfe 0.6R | LIT +$86 / +$246, eval +$172 / +$3,486, fails 0 / 0, funded +$5 / +$37 | **passes the gate on 2 changed trades** (1 per half): not a finding |
| Cut check | at 12 / 18 min; x 0.2 / 0.4R | 12: -$334 / -$882; 18: -$659 / -$155; x0.2: +$151 / -$1,464; x0.4: -$429 / -$380 | 15 minutes / 0.3R stay |

(Bonferroni over the 12 size tilts: p must be under 0.004; the lowest, "fresh win x1.25" p_both 0.02, is above it and fails the eval path. Month-label permutation: 300 random 3-up / 3-down month sets gain as much in both halves 5% of the time, but the real pick loses in Jan-Jun.)

## 3. What to change on the live bot (owner decides)

**Nothing.**
- Forward paper tally only (no switch): the breakeven cushion (3.75 pts; the live code's `be_off`) and the cut waiver at best point 0.6R. The cushion is the bigger of the two (+$960 in Jan-Jun, flat in Jul-Oct) and costs eval-path money in Jul-Oct; the waiver changes 2 trades in 10 months.
- Plutus / hub / Zenith: nothing to do; they now agree.

## 4. Rejected tonight and why

Level classes (no new trades), inside day, overnight-range percentile, CISD body, time since a win, month-of-year (picked months lose in Jan-Jun), limit windows other than 30 minutes (shorter loses fills, longer is the same), breakeven triggers other than 1R, 12 / 18-minute cuts and the other thresholds.

## Appendix - every version (change vs today)

| version | LIT $ vs today Jan-Jun / Jul-Oct | 2021-25 ref | eval-path $ Jan-Jun / Jul-Oct | 2-week pass change | 2-week fail change | funded $/mo change | trades changed (Jan-Jun / Jul-Oct) | shuffle p (Jan-Jun / Jul-Oct) |
|---|---|---|---|---|---|---|---|---|
| cut:cut_at_12 | -334 / -882 | +36 | -2,118 / -2,776 | +0.0 / -1.5 | +0.0 / -5.8 | -20 / -75 | 11 / 10 | n/a |
| cut:cut_at_18 | -659 / -155 | +48 | -1,451 / +170 | +0.0 / +0.0 | +0.0 / +0.0 | -47 / -7 | 18 / 7 | n/a |
| cut:cut_x0.2R | +151 / -1,464 | +0 | +1,491 / -3,572 | +0.0 / -8.7 | -1.7 / -5.8 | 12 / -179 | 2 / 4 | n/a |
| cut:cut_x0.4R | -429 / -380 | +0 | -2,204 / -54 | +0.0 / +0.0 | +0.0 / +0.0 | -24 / -44 | 4 / 2 | n/a |
| cut:cut_mfe0.4R | +0 / -292 | +0 | +0 / -54 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / -19 | 0 / 1 | n/a |
| cut:cut_mfe0.6R | +86 / +246 | +0 | +172 / +3,486 | +0.0 / +0.0 | +0.0 / +0.0 | 5 / 37 | 1 / 1 | n/a |
| cut:cut_at_12_x0.2 | +119 / -1,551 | +36 | -1,468 / +1,661 | +0.9 / -5.8 | +0.0 / -5.8 | 14 / -137 | 14 / 13 | n/a |
| cut:cut_at_18_x0.4 | -809 / -242 | +48 | -2,359 / -88 | +0.0 / +0.0 | +0.0 / +0.0 | -52 / -17 | 16 / 6 | n/a |
| params:wait_3bars_15min | -5,072 / -97 | -5,351 | -5,609 / -2,599 | -6.7 / +1.4 | +4.2 / +0.0 | -119 / -79 | 11 / 5 | n/a |
| params:wait_4bars_20min | -1,806 / -609 | -3,129 | -2,104 / -2,716 | +0.0 / +0.0 | +4.2 / +0.0 | -40 / -113 | 8 / 3 | n/a |
| params:wait_5bars_25min | -1,842 / +353 | -2,714 | -2,477 / +401 | +0.0 / +0.0 | +4.2 / +0.0 | -53 / 33 | 3 / 1 | n/a |
| params:wait_7bars_35min | +0 / +4 | -1,067 | +0 / +1 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 0 / 1 | n/a |
| params:wait_8bars_40min | -83 / +4 | -2,798 | +196 / +1 | +0.0 / +0.0 | +0.0 / +0.0 | -22 / 0 | 2 / 1 | n/a |
| params:wait_9bars_45min | -83 / +4 | -3,608 | +196 / +1 | +0.0 / +0.0 | +0.0 / +0.0 | -22 / 0 | 2 / 1 | n/a |
| params:wait_12bars_60min | -4 / -138 | -8,787 | +1,524 / -486 | +0.0 / +0.0 | -0.9 / +0.0 | -45 / -4 | 6 / 3 | n/a |
| tilt:inside_dn075 | -1,152 / -66 | -2,279 | -2,754 / +1,468 | -5.0 / +0.0 | +0.0 / +0.0 | -17 / 6 | 3 / 2 | worse in a half |
| tilt:inside_up125 | +831 / -89 | +1,560 | +642 / -1,296 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 3 / 1 | worse in a half |
| tilt:cisdbody_high_up125 | +1,581 / -346 | -1,165 | +1,083 / -848 | +2.6 / +0.0 | +0.0 / -5.8 | -1 / -10 | 11 / 6 | worse in a half |
| tilt:cisdbody_low_up125 | +3,174 / -222 | -850 | +3,475 / -190 | +0.0 / +0.0 | +0.0 / +4.3 | 9 / 16 | 17 / 3 | worse in a half |
| tilt:cisdbody_high_up_low_dn | -3,625 / -1,809 | -295 | -9,581 / -1,596 | -26.0 / -1.5 | +0.0 / -5.8 | -59 / -69 | 33 / 14 | worse in a half |
| tilt:onrange_high_up125 | +834 / +643 | +1,597 | +2,738 / -378 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / -9 | 9 / 6 | 0.86 / 0.167 |
| tilt:onrange_low_up125 | +2,157 / -63 | -1,292 | +475 / -778 | +2.6 / +0.0 | +0.8 / -1.5 | -1 / 22 | 16 / 9 | worse in a half |
| tilt:onrange_high_up_low_dn | -1,820 / -1,561 | +2,979 | +836 / -840 | -8.4 / -24.7 | -1.7 / -5.8 | 7 / -83 | 31 / 23 | worse in a half |
| tilt:drought_up125 | +2,793 / +218 | +2,549 | +4,660 / -280 | +2.6 / +0.0 | +0.0 / -5.8 | 12 / 5 | 19 / 8 | 0.6 / 0.667 |
| tilt:drought_dn075 | -3,342 / -1,516 | -3,239 | -10,056 / -2,244 | -21.0 / -8.7 | +0.0 / -5.8 | -41 / -10 | 30 / 13 | worse in a half |
| tilt:fresh_win_dn075 | -2,975 / -1,130 | +1,364 | -8,537 / -1,196 | -3.3 / -2.9 | +0.0 / +0.0 | -23 / -15 | 6 / 4 | worse in a half |
| tilt:fresh_win_up125 | +2,052 / +294 | -373 | -1,487 / -199 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 1 | 4 / 2 | 0.053 / 0.307 |
| season:season_pick_up125_dn075 | -6,058 / +987 | +6,165 | -3,702 / +496 | -15.9 / +0.0 | +0.0 / -5.8 | -29 / 5 | 41 / 8 | worse in a half |
| season:season_pick_dn_only075 | -6,510 / +0 | +3,130 | -5,813 / +0 | -15.9 / +0.0 | +0.0 / +0.0 | -29 / 0 | 33 / 0 | worse in a half |
| season:season_pick_up_only125 | +452 / +987 | +3,035 | +2,111 / +496 | +0.0 / +0.0 | +0.0 / -5.8 | 2 / 5 | 8 / 8 | 0.66 / 0.107 |
| levels:weekly_open | +0 / +0 | +0 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 0 / 0 | n/a |
| levels:monthly_open | +0 / +0 | -111 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 0 / 0 | n/a |
| levels:quarterly_open | +0 / +0 | -111 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 0 / 0 | n/a |
| levels:quarterly_pivot_R1S1 | +0 / +0 | +5 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 0 / 0 | n/a |
| levels:quarterly_pivot_P | +0 / +0 | +0 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 0 / 0 | n/a |
| levels:weekly_and_monthly_open | +0 / +0 | -111 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 0 / 0 | n/a |
| levels:all_five | +0 / +0 | -106 | +0 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | 0 / 0 | 0 / 0 | n/a |
| be:be_trigger_0.75R | -6,501 / -5,049 | -14,170 | +2,910 / -4,884 | -7.5 / +0.0 | +0.0 / -5.8 | -52 / -355 | 5 / 6 | n/a |
| be:be_trigger_0.9R | -931 / -579 | -4,382 | -532 / -1,158 | +0.0 / -1.5 | +0.0 / +0.0 | -20 / -54 | 1 / 1 | n/a |
| be:be_trigger_1.1R | -133 / +0 | +1,100 | -498 / +0 | +0.0 / +0.0 | +0.0 / +0.0 | -11 / 0 | 1 / 0 | n/a |
| be:be_trigger_1.25R | -3,112 / +0 | +7,961 | -7,011 / +0 | -0.8 / +0.0 | +0.0 / +0.0 | -99 / 0 | 6 / 0 | n/a |
| be:be_trigger_1.5R | -5,574 / +0 | +14,271 | -7,268 / +0 | +3.4 / +0.0 | +0.0 / +0.0 | -127 / 0 | 13 / 0 | n/a |
| be:be_cushion_0.5pts | -288 / -63 | +370 | -868 / +97 | +0.0 / +0.0 | +0.8 / -5.8 | -45 / -4 | 29 / 6 | n/a |
| be:be_cushion_2.5pts | +480 / -47 | -187 | +417 / -1,297 | +0.0 / +0.0 | +0.0 / -5.8 | 16 / -5 | 29 / 7 | n/a |
| be:be_cushion_3.75pts | +960 / +78 | -1,283 | +1,498 / -1,187 | +0.9 / +1.4 | +0.0 / -5.8 | 28 / 3 | 29 / 7 | n/a |
| be:be_trigger_0.75R_cushion_2.5pts | -5,886 / -5,053 | -18,302 | +3,447 / -6,286 | -7.5 / +0.0 | +0.0 / -5.8 | -37 / -357 | 33 / 13 | n/a |
| be:be_trigger_1.25R_cushion_0.5pts | -3,295 / -63 | +8,768 | -7,432 / +97 | -0.8 / +0.0 | +0.8 / -5.8 | -134 / -4 | 30 / 6 | n/a |
| be:be_trigger_0.9R_cushion_3.75pts | +99 / -3,604 | -4,240 | +1,012 / -5,432 | +0.9 / +0.0 | +0.0 / -5.8 | 9 / -177 | 30 / 9 | n/a |
