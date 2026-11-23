---
title: Re-test of every rejected idea under the owner's alternative standards (frequency dropped, per-account, on top of LIT + ATLAS, rolling walk-forward)
family: research
date: 2026-11-23
status: done - paper only. 0 of 131 idea families pass the multiple-testing bar. One family (stop hunt) clears every account test but its menu was hand-picked with hindsight, and the first fresh month is -$642. Proposal below = paper lane only. Nothing live changed.
runs: none (research/retest/wf.json, wf_fit3.json, wf_fit12.json, summary.json, fresh_stophunt.json; code tools/retest/)
---

## For the owner (one minute)

**Blunt verdict: the old standards didn't throw out a winner.** Under the looser but still honest rules you asked for,
the most lenient way to score 131 rejected idea families finds **none that beats chance once you allow for how many we
tested.** Ten look good on their own (p < 0.05). With 131 tries, about 6-7 would look that good by luck.
Most of the gains people remember come from runs that were **picked after looking at the same data**, and they melt
when the pick is made on past months only.

One idea family deserves a paper lane: the **stop-hunt book** (Asia resweep hunt + trend-inducement hunt, 2026-10-23).
Added on top of Zlarior + ATLAS it raises $ a month on **every plan in every period** in the account simulator (Builder 50K
+$30 / +$368 / +$299 a month in 2022-25 / Jan-Jun / Jul-Oct). It does **not** pass the multiple-testing bar
(p 0.0011 vs the 0.00038 needed), over half of its picks were chosen with hindsight, and on the **fresh month nobody has
looked at (Oct 17 - Nov 19)** its two frozen rules made **-$642** (8 trades). Proposal: paper only, judge after 3 fresh months.

| what | result |
|---|---|
| Idea families re-tested | 131 (2,345 stored runs + 896 regenerated cells of the newest hunts), Kalshi excluded |
| Pass Bonferroni (p < 0.05 / 131 = 0.00038) | **0** |
| Pass p < 0.05 alone | 10 (about 6-7 expected by luck) |
| Beat Zlarior + ATLAS on an account in all 3 periods (> 2 paired SE) | stop hunt (all 4 account rows); NA picks, retail picks, gap/ORB, continuation on ONE plan each |
| Of those, clean (no hindsight in the menu) AND all 3 periods | **0** on the Rapid 25K / Builder 25K; Builder 50K Zlarior-only: ORB 2nd side (+$9 / +$16 / +$20, too small to matter), PM continuation (+$26 / +$93 / +$151, WF p 0.095) |
| Fresh month (Oct 17 - Nov 19, never seen by any pick) | stop hunt -$642 (8 trades); others not re-run |

Next (paper only):
1. Read the stop-hunt proposal (section 5). Yes / no is yours; nothing is armed either way.
2. If yes, the lead adds it as a **paper** lane (no money). Re-score it on new bars every month:
   `python -X utf8 tools/retest/fresh_stophunt.py`
3. Re-run the whole re-test after each new month of data: `python -X utf8 tools/retest/retest.py wf && python -X utf8 tools/retest/report.py`

## 1. The standards (as asked) and what stayed fixed

| standard | how it was run here |
|---|---|
| (1) Frequency rule dropped | No 2-4 trades/week gate. Judged by **$ per month after costs** (walk-forward stream; then $ a month to the owner net of eval fees on each account). |
| (2) Per-account fit | Every candidate scored separately on **Rapid EOD 25K** (daily payouts, EOD drawdown; Zlarior + ATLAS in lanes, the preset built for it), **Builder 25K** and **Builder 50K** (Zlarior + ATLAS, own sizing), plus Builder 50K with Zlarior alone (today's live 50K). An idea may pass one plan only. |
| (3) Portfolio | The idea rides **on top of** Zlarior + ATLAS in `tools/money/combo_account.py`, unchanged: one net position (first in keeps the account), the engine's own sizing, the new bot sized as a lane (min($125 x plan, 30% of room, day loss left)), MFFU rules incl. the move to live after payout 5, $1.90 a micro + 1 tick per fill, 2,000 six-month paths, same paths for base and candidate (paired). Reported: net $ a month, gain vs base, chance the 6 months lose, 10th percentile, median days to pass the eval, median sessions to the first payout, daily correlation, same-day overlap. "Smooths" = no worse on $ (>= -$25), lower loss chance and a higher 10th percentile in all 3 periods. |
| (4) Walk-forward | Every month from **2022-05 to 2026-10**: fit on the 6 months before, pick the variant (or "no change") with the most $, record that variant's $ in the test month only. 54 months stitched = the out-of-sample (OOS) result. Checked with 3- and 12-month fits. |
| Futures data only | CME NQ1! / ES1! bars in `data/` (TradingView exports + NinjaTrader bars). Nothing else. |
| Costs in | Every stored run already had costs; regenerated cells at $1.90 a micro + each tool's own fills; account sims $1.90 + 1 tick. |
| Real out-of-sample | Parameters picked only on months before the test month. Families whose stored runs were themselves "picks"/"best"/"plateau" chosen on the full data are **flagged** (hindsight share) - their OOS is not clean. |
| Multiple testing | Bonferroni across all 131 families: one-sided p on the 54 OOS months must be < 0.05 / 131 = **0.00038**. Within a family the walk-forward itself absorbs the choice among variants. |

How a modification (a LIT / ATLAS / BLITZ tweak) is scored: its **daily $ minus its own study's base run**
(base = the most correlated base-like run, corr >= 0.3), after **removing any size-up** (variant scaled to the base's
average $ on trading days: more contracts is leverage, not an idea). A new stand-alone strategy is scored vs cash. Only
runs marked rejected or promising (never adopted) count as "thrown out"; info / baseline / adopt-candidate runs are not
re-litigated.

## 2. Ranked table (the ideas that matter)

$ a month = 6-month slot to the owner after eval fees, gain vs today's Zlarior + ATLAS on the same account and the same
paths, in **2022-05..25 / Jan-Jun 2026 / Jul-Oct 2026**. Base: Builder 50K Z+A $56 / $2,726 / $1,556; Builder 25K Z+A
-$7 / $1,325 / $637; Rapid 25K Z+A lanes -$15 / $2,146 / $617; Builder 50K Zlarior alone -$5 / $872 / $734.

| # | idea (study) | standard it passes | WF OOS $/mo of the stream alone ($500/trade) | gain on Rapid 25K | gain on Builder 25K | gain on Builder 50K (Z+A) | max DD of the stream ($250/trade) 2022-25 / H1 / H2 | days to pass / first payout, Builder 50K (base 5/5/7 and 66/24/33) | out-of-sample verdict |
|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | **Stop-hunt book** (stophunt, 2026-10-23) | (1), (2) all 3 plans, (3) beats + smooths on B50, (4) p 0.0011 | **$850** (2022-25 $602, H1 $2,314, H2 $1,376) | **+$19 / +$200 / +$177** | **+$9 / +$105 / +$103** | **+$30 / +$368 / +$299** | -$7,497 / -$483 / -$750 | 5/5/7 and 65/23/30 | Fails Bonferroni (0.0011 > 0.00038). 56% of the WF picks are hindsight runs (picked on H1 + 2025 + 2021-24 out of 28.7 M variants; the 2026-10-23 audit called trend "not real", Asia "weak"). Fresh Oct 17 - Nov 19: **-$642** on 8 trades. Corr with Z+A 0.06; 2-3 trades/week; trades on the same day as Z/A on ~80% of its days. |
| 2 | Noise-area momentum, stored picks (diversifier-search) | (1), (4) raw p 0.02; (2) only B50 Zlarior-alone | $1,024 | -$16 / +$270 / +$258 | -$8 / +$384 / +$194 | -$20 / +$673 / +$391 | -$8,384 / -$2,182 / -$2,266 | 5/5/6 and 65/22/30 | **Hindsight** (the picks were chosen on 2021-24 + H1). Clean versions lose a period: full 144-cell grid WF B50 -$20 / +$405 / **-$93**; the paper's own rule fixed B50 -$3 / **-$295** / +$406. Not real enough. |
| 3 | Retail stand-alone picks (retail-standalone) | (1), (4) raw p 0.049; (2) only B50 Zlarior-alone (+$56 / +$91 / +$49) | $1,094 (H1 **-$277**) | +$9 / **-$285** / -$48 | +$15 / -$119 / -$45 | +$41 / **-$362** / -$33 | -$4,952 / -$2,801 / -$615 | - | **Hindsight** (every pick is a "best" / "plateau" run). Hurts every Z+A account in 2026. |
| 4 | PM continuation (hq-continuation) | (1); (2) B50 Zlarior-alone only (+$26 / +$93 / +$151) | $327 (p 0.095) | +$5 / **-$307** / +$37 | +$9 / -$69 / +$50 | +$13 / -$93 / +$124 | -$5,635 / -$1,617 / -$1,059 | - | Clean menu but WF p 0.095 (not even raw). Only helps a Zlarior-alone 50K; costs Zlarior + ATLAS accounts in Jan-Jun. |
| 5 | ORB 2nd side after a failed break (E2, regenerated) | (4) raw p 0.031; (2) B50 Zlarior-alone (+$9 / +$16 / +$20) | $284 | +$2 / $0 / $0 | +$2 / $0 / $0 | +$1 / +$64 / +$36 | -$2,678 / -$920 / -$1,046 | 5/5/7 | Clean but tiny: on the 25Ks it is almost always blocked by Z/A already in a trade. Not worth a lane. |
| 6 | Post-close follow at the reopen (third-strategy lead, fixed cell) | (3) on 2026 only | - (fixed rule) | -$2 / +$269 / +$21 | +$1 / +$138 / +$36 | -$5 / +$207 / +$96 | -$4,548 / -$705 / -$1,915 | 5/5/7 and 65/23/32 | The cell was the study's paper lead (chosen with all periods in view); the clean 80-cell WF loses: B50 -$30 / -$7 / **-$219**. 2022-25 slightly negative. |
| 7 | G1 gap fade (E2 paper lead, fixed) | (3) 2022-25 + H1 only | - | +$9 / +$90 / $0 | +$4 / +$63 / $0 | +$28 / +$46 / **-$174** | -$2,058 / -$2,230 / -$1,364 | - | Loses Jul-Oct on the 50K. Clean grid WF p 0.07. |
| 8 | DAPHNE strategy tree (2026-11-03) | (4) raw p 0.004 | $418 (H1 -$108, H2 -$165) | +$9 / **-$343** / +$36 | +$7 / -$130 / +$11 | +$25 / -$297 / -$82 | -$2,159 / -$2,230 / -$624 | - | Real in 2022-25, dead in 2026. Fails. |
| 9 | London-to-NY extension fade (new-hunt lxf, regenerated) | (4) raw p 0.0055 | $334 (H2 -$187) | $0 / $0 / $0 | +$2 / $0 / $0 | +$15 / -$61 / $0 | -$1,787 / -$977 / -$749 | - | Trades ~1/wk and is blocked by Z/A on the accounts. 2026 negative. |
| 10 | Dalton 80% rule (new-hunt d80, regenerated) | (1), (4) raw p 0.0086 | $189 (all 3 periods +) | +$1 / $0 / +$40 | +$2 / $0 / $0 | +$7 / +$17 / **-$90** | -$1,338 / -$725 / -$697 | - | Positive alone in every period but too thin; loses Jul-Oct on the 50K. |
| 11 | Best LIT / ATLAS modification families (hq-habits, funded-path, lit-report-coverage, lit-gap-audit, ATLAS v2 ...) | none | +$132 to +$279 a month of extra $ at the same risk | not run (no family passes stage 1) | | | | | Best p 0.11 (funded-path). lit-gap-audit is the only one positive in all 3 periods (+$120 / +$736 / +$487) but p 0.17. Most "promising" LIT tweaks flip sign between periods. |

Everything else (the other 120 families): appendix. Stand-alone families that make money alone but are cut to ~$0 on
the accounts (lxf, d80, ORB, pva, ksq) are cut because the account holds one position and Zlarior / ATLAS are already in
the trade on most of their days (same-day overlap 70-90%).

Walk-forward length check (3 / 6 / 12-month fits, $ a month and p): stop hunt $549 p 0.023 / $850 p 0.0011 / $528 p 0.031;
NA picks $714 / $1,024 / $866 (p 0.02-0.09); strategy tree $444 / $418 / $456 (p 0.002-0.004, all 2022-25); none crosses
0.00038 at any length.

## 3. What the alternative standards change, honestly

- **Dropping the 2-4 trades/week rule changes nothing that matters.** The thin ideas (0.3-1 a week: lxf, d80, ORB, Camarilla,
  NR7, pre-FOMC) are allowed now, but their $ is small and on a real account they mostly sit behind Zlarior / ATLAS.
- **Per-account scoring helps only on a Zlarior-alone Builder 50K.** With ATLAS on the account the spare slots are few; a
  third bot is mostly blocked or adds a losing stretch. On the Rapid 25K nothing clean helps all three periods.
- **The portfolio view is where the stop hunt shows up.** Weak in its own eval (its own 25K: -$10 to -$16 a month - it can't
  pass alone), but on top of Zlarior + ATLAS it lowers the chance a 6-month 50K slot loses (59.0 -> 56.9% in 2022-25;
  1.1 -> 0.3% in Jul-Oct) and lifts the 10th percentile ($751 -> $1,015 a month Jul-Oct). That is the "smooths LIT" case
  you asked about - it is the one real one.
- **Rolling walk-forward removes the luck of a fixed split** but cannot clean a menu that was built with hindsight. That is
  why the stop-hunt, NA and retail numbers are flagged: the runs saved in the library were already winners of searches that
  saw 2021-2026.

## 4. Limits (read before trusting any number)

- Stored runs end 2026-10-16. Only the stop hunt was re-run on the fresh bars (to 2026-11-19).
- Modifications were judged on daily $ at equal risk, not on the account simulator (no family passed stage 1, so none was
  pushed through). Pure sizing / payout-mechanics studies are neutralised by the equal-risk rule by design.
- Stored trades without a worst-open price were given a full stop as their worst open loss (harsher for the candidate).
- The account bootstrap resamples the same real days, so its z-scores are far bigger than the real evidence; the
  multiple-testing decision is made on the 54 walk-forward months, not on the bootstrap.
- The ATLAS member studies (EMA, MACD, S/R) are ATLAS itself and the meta-labeling family re-sizes ATLAS; both were
  excluded from "new money" (their $ is ATLAS's).
- Kalshi studies excluded as asked. Overnight-hold public strategies (pub_strats) were not scored: MFFU flat by 16:10.

## 5. Proposal for the owner (not a live change)

**Stop-hunt book as a paper lane on top of Zlarior + ATLAS (Builder 50K first).**
- What: the two frozen 2026-10-23 rules (`tools/stophunt.FINAL`: Asia resweep hunt, fixed 2R; trend inducement hunt on
  5m swings, fixed 2R), one position on the account, first in keeps it, lane size min($250, 30% of room, day loss left) on
  the 50K ($125 on a 25K).
- Expected if the past holds: +$30 / +$368 / +$299 a month on the Builder 50K (2022-25 / Jan-Jun / Jul-Oct), +$103-200 on
  the 25Ks in 2026, eval days unchanged, first payout 1-3 sessions sooner.
- Why only paper: fails the multiple-testing bar, half the evidence was picked with hindsight, the fresh month is -$642,
  and 2022-25 alone adds only +$9 to +$30 a month.
- Go-live test fixed now (before any new data): after 3 fresh months (to 2027-02-19) the book must be positive in $ after
  costs on at least 25 trades, AND re-running this file on the new months must give the 50K Z+A+P row a gain > 0 in the
  fresh months. Either fails -> drop it for good.

## 6. Reproduce

    python -X utf8 tools/retest/regen.py third|hunt|plus|e2|div|pub     # per-trade cells of the newest hunts (needs numba)
    python -X utf8 tools/retest/retest.py wf                             # stage 1 walk-forward (RETEST_FIT=3 / 12 for checks)
    python -X utf8 tools/retest/accounts.py <family> 2000                # stage 2 on top of Z+A ('none' = bases, 'fixed=<id>')
    python -X utf8 tools/retest/report.py                                # summary.json + the table numbers
    python -X utf8 tools/retest/fresh_stophunt.py                        # frozen stop-hunt rules on fresh bars

## Appendix: all 131 families, walk-forward (6-month fit, 1-month test, 2022-05..2026-10)

$ a month of the stream (stand-alone at $500 a trade) or of the extra $ at equal risk (modifications). p = one-sided t on
the 54 OOS months. Bonferroni needs p < 0.00038.

| # | family (study / regenerated hunt) | kind | variants | WF OOS $/mo (all) | 2022-05..25 | 2026 H1 | 2026 Jul-Oct | p (one-sided) | raw p<0.05 | Bonferroni |
|---:|---|---|---:|---:|---:|---:|---:|---:|:-:|:-:|
| 1 | retail-standalone | stream | 26 | 1,094 | 1,304 | -276 | 835 | 0.0490 | yes | no |
| 2 | diversifier-search | stream | 6 | 1,024 | 532 | 3,229 | 3,124 | 0.0204 | yes | no |
| 3 | stophunt | stream | 7 | 850 | 602 | 2,314 | 1,376 | 0.0011 | yes | no |
| 4 | div:NA | stream | 144 | 577 | 445 | 1,752 | 268 | 0.0704 |  | no |
| 5 | meta-labeling | stream | 4 | 572 | 438 | 1,096 | 1,255 | 0.0072 | yes | no |
| 6 | 2026-11-03-strategy-tree.md | stream | 2 | 418 | 543 | -108 | -165 | 0.0039 | yes | no |
| 7 | lit-funded-sizing | mod | 1 | 402 | 494 | 0 | 0 | 0.0387 | yes | no |
| 8 | hq-bias | stream | 4 | 345 | 154 | 1,904 | 108 | 0.0910 |  | no |
| 9 | hunt:lxf | stream | 54 | 334 | 412 | 108 | -187 | 0.0055 | yes | no |
| 10 | hq-continuation | stream | 8 | 327 | 241 | 509 | 998 | 0.0954 |  | no |
| 11 | nq-new-strategies-2026-11-13 | stream | 8 | 286 | 58 | 1,797 | 517 | 0.1258 |  | no |
| 12 | e2:orb2 | stream | 18 | 284 | 230 | 906 | -47 | 0.0309 | yes | no |
| 13 | hq-habits | mod | 42 | 279 | -39 | 1,875 | 1,381 | 0.1366 |  | no |
| 14 | funded-path | mod | 5 | 248 | 84 | 1,114 | 746 | 0.1141 |  | no |
| 15 | e2:gapf | stream | 24 | 244 | 308 | -230 | 262 | 0.0735 |  | no |
| 16 | lit-report-coverage | mod | 33 | 242 | 430 | -380 | -897 | 0.1043 |  | no |
| 17 | lit-gap-audit | mod | 20 | 215 | 120 | 736 | 487 | 0.1661 |  | no |
| 18 | hq-lit | mod | 20 | 205 | 238 | 592 | -745 | 0.1984 |  | no |
| 19 | third:cam | stream | 44 | 196 | 200 | 488 | -295 | 0.2658 |  | no |
| 20 | hunt:d80 | stream | 12 | 189 | 194 | 218 | 98 | 0.0086 | yes | no |
| 21 | e2:eod | stream | 18 | 179 | 323 | -368 | -584 | 0.3307 |  | no |
| 22 | 2026-11-04_second_strategies_night | mod | 4 | 177 | 145 | 415 | 174 | 0.1149 |  | no |
| 23 | lit-batch3b | mod | 22 | 164 | 0 | 826 | 980 | 0.2001 |  | no |
| 24 | nq-edge-2026-11-13 | mod | 18 | 161 | 206 | -111 | 77 | 0.1580 |  | no |
| 25 | scalp-na-mffu | mod | 3 | 157 | -63 | 1,215 | 990 | 0.1258 |  | no |
| 26 | hq-reversion | stream | 8 | 156 | 128 | 684 | -325 | 0.2026 |  | no |
| 27 | second-mix | mod | 4 | 141 | 290 | -303 | -825 | 0.3313 |  | no |
| 28 | atlas-v2 | mod | 10 | 132 | 77 | 1,099 | -725 | 0.2591 |  | no |
| 29 | third:pcm | stream | 80 | 125 | 193 | 149 | -659 | 0.2901 |  | no |
| 30 | quant-anomalies | mod | 28 | 122 | 148 | 1,012 | -1,502 | 0.3373 |  | no |
| 31 | atlas-edge-2026-10-30b | mod | 11 | 120 | 171 | -671 | 754 | 0.2991 |  | no |
| 32 | lit-batch3a | mod | 27 | 101 | 39 | 517 | 153 | 0.2820 |  | no |
| 33 | other | mod | 10 | 95 | 10 | 969 | -276 | 0.3798 |  | no |
| 34 | 2026-11-03-eval-dp | mod | 2 | 87 | 189 | -538 | -102 | 0.3516 |  | no |
| 35 | atlas-windows-entries-2026-10-30 | mod | 10 | 82 | 0 | 644 | 148 | 0.3360 |  | no |
| 36 | lit-experiments | mod | 9 | 69 | 82 | 8 | 23 | 0.3591 |  | no |
| 37 | lit-loss-learning | mod | 10 | 69 | 84 | 0 | 0 | 0.3604 |  | no |
| 38 | lit-market-context | mod | 12 | 69 | 84 | 0 | 0 | 0.3604 |  | no |
| 39 | lit-htf-confluences | mod | 11 | 66 | 73 | -444 | 755 | 0.3930 |  | no |
| 40 | es-and-sessions-2026-11-13 | stream | 5 | 62 | -212 | 1,925 | 281 | 0.3463 |  | no |
| 41 | lit-trade-selection | mod | 5 | 61 | -114 | 976 | 619 | 0.3629 |  | no |
| 42 | 2026-11-15-s2-edge | mod | 7 | 61 | -2 | 472 | 136 | 0.0540 |  | no |
| 43 | 2026-11-04_atlas_round3 | mod | 10 | 60 | 0 | 379 | 249 | 0.0301 | yes | no |
| 44 | blitz-edge-2026-10-30b | mod | 7 | 60 | 57 | 138 | -18 | 0.1618 |  | no |
| 45 | plus:pva | stream | 1 | 49 | 60 | 0 | 0 | 0.2157 |  | no |
| 46 | lit-risk-money | mod | 7 | 46 | 0 | 461 | -73 | 0.2196 |  | no |
| 47 | unexpected-factors.md | mod | 16 | 40 | 58 | -258 | 292 | 0.3461 |  | no |
| 48 | eval-sizing.md | mod | 11 | 38 | -20 | 96 | 591 | 0.3050 |  | no |
| 49 | lit-untested-bias | mod | 30 | 38 | 90 | 92 | -616 | 0.4080 |  | no |
| 50 | plus:ksq | stream | 8 | 34 | 45 | -7 | -20 | 0.3050 |  | no |
| 51 | lit-edge-2026-10-30 | mod | 20 | 34 | 134 | -818 | 201 | 0.3862 |  | no |
| 52 | risk-sizing.md | mod | 47 | 29 | -45 | -16 | 912 | 0.3794 |  | no |
| 53 | lit-1m-management | mod | 14 | 25 | 0 | 1,806 | -2,376 | 0.4527 |  | no |
| 54 | e2:rs | stream | 16 | 18 | 50 | -24 | -269 | 0.4238 |  | no |
| 55 | loss-cut-eval-pass | mod | 46 | 16 | 27 | 10 | -93 | 0.4130 |  | no |
| 56 | atlas-blitz-edge-2026-10-30 | mod | 8 | 12 | -127 | 1,169 | -190 | 0.4774 |  | no |
| 57 | lit-all-hours | mod | 10 | 9 | -86 | -50 | 1,147 | 0.4847 |  | no |
| 58 | intraday-anatomy.md | mod | 7 | 6 | -50 | 278 | 217 | 0.4674 |  | no |
| 59 | vwap-volume-profile.md | mod | 60 | 6 | -16 | -131 | 452 | 0.4741 |  | no |
| 60 | lit-ablation | mod | 10 | -1 | 0 | -87 | 110 | 0.5436 |  | no |
| 61 | cross-market-context.md | mod | 25 | -8 | -8 | -37 | 40 | 0.5522 |  | no |
| 62 | structure-management | mod | 21 | -10 | 95 | -866 | 128 | 0.5204 |  | no |
| 63 | bias-filters.md | mod | 46 | -10 | -50 | -123 | 609 | 0.5224 |  | no |
| 64 | second-ema | mod | 2 | -17 | 208 | -1,680 | 0 | 0.5221 |  | no |
| 65 | e2:news | stream | 8 | -17 | -8 | 29 | -191 | 0.6279 |  | no |
| 66 | second-account-b | mod | 1 | -19 | -73 | 588 | -329 | 0.6257 |  | no |
| 67 | lit-final | mod | 1 | -20 | 4 | -213 | 0 | 0.6306 |  | no |
| 68 | trade-construction-summary.md | mod | 3 | -21 | 32 | -190 | -354 | 0.6698 |  | no |
| 69 | scalp-mean-reversion.md | stream | 3 | -22 | -176 | 1,995 | -1,358 | 0.5361 |  | no |
| 70 | atlas-funded-one-a-day-2026-10-31 | mod | 5 | -25 | -13 | -125 | 0 | 0.5924 |  | no |
| 71 | blitz-streak-size-2026-10-31.md | mod | 2 | -26 | -43 | 0 | 123 | 0.8408 |  | no |
| 72 | risk-summary.md | mod | 8 | -37 | -7 | 84 | -549 | 0.6941 |  | no |
| 73 | b-holds-vs-lit-priority | mod | 2 | -39 | -40 | -54 | -4 | 0.6649 |  | no |
| 74 | blitz-25k | mod | 2 | -39 | 3 | -372 | 0 | 0.7563 |  | no |
| 75 | uprisk | mod | 3 | -42 | 0 | 402 | -1,175 | 0.7112 |  | no |
| 76 | calendar-effects.md | mod | 6 | -43 | -48 | -46 | 23 | 0.8058 |  | no |
| 77 | lit-adv-audit-smt | mod | 7 | -48 | 8 | -440 | -73 | 0.8322 |  | no |
| 78 | parameter-robustness.md | mod | 12 | -50 | -68 | 15 | 49 | 0.8885 |  | no |
| 79 | lit-money-batch2 | mod | 7 | -52 | 0 | 1,706 | -3,257 | 0.6157 |  | no |
| 80 | management.md | mod | 29 | -59 | -82 | -140 | 316 | 0.6892 |  | no |
| 81 | 2026-11-03-money-plan | mod | 1 | -61 | -74 | 0 | 0 | 0.6523 |  | no |
| 82 | what-to-expect.md | mod | 6 | -73 | -68 | -23 | -196 | 0.8906 |  | no |
| 83 | lit-order-blocks | mod | 17 | -83 | -89 | -27 | -95 | 0.7489 |  | no |
| 84 | lit-untested-stops | mod | 41 | -90 | -81 | -1,094 | 1,324 | 0.6395 |  | no |
| 85 | 2026-11-04_lit_ideas_night | mod | 9 | -98 | 34 | -696 | -658 | 0.7280 |  | no |
| 86 | stress-tests.md | mod | 1 | -98 | -61 | -433 | 0 | 0.8814 |  | no |
| 87 | discretion-score-2026-10-30 | mod | 9 | -109 | -109 | -242 | 92 | 0.7647 |  | no |
| 88 | lit-adv-continuation | mod | 24 | -110 | 17 | -1,111 | 0 | 0.6953 |  | no |
| 89 | lit-entry-precision | mod | 10 | -111 | 0 | -604 | -590 | 0.9184 |  | no |
| 90 | lit-adv-management | mod | 18 | -118 | 0 | -825 | -353 | 0.9394 |  | no |
| 91 | win-rate-and-sessions | mod | 45 | -122 | -186 | 377 | -174 | 0.7365 |  | no |
| 92 | moving-averages.md | mod | 16 | -124 | -90 | -28 | -640 | 0.9194 |  | no |
| 93 | 2026-11-15-atlas-deep | mod | 6 | -127 | -117 | -356 | 115 | 0.8088 |  | no |
| 94 | lit-big-ideas | mod | 7 | -133 | 0 | -2,123 | 1,384 | 0.8014 |  | no |
| 95 | div:IB | stream | 24 | -136 | -50 | -170 | -1,025 | 0.7501 |  | no |
| 96 | targets.md | mod | 15 | -145 | -130 | -381 | 41 | 0.9455 |  | no |
| 97 | lit-losses | mod | 3 | -146 | -69 | -276 | -798 | 0.8709 |  | no |
| 98 | pub:day | stream | 12 | -154 | -122 | -280 | -316 | 0.8017 |  | no |
| 99 | lit-retail-entries | mod | 59 | -156 | -126 | 221 | -1,057 | 0.8038 |  | no |
| 100 | plus:poc | stream | 4 | -156 | -128 | -394 | -111 | 0.8864 |  | no |
| 101 | atlas | mod | 4 | -157 | -120 | -107 | -650 | 0.8749 |  | no |
| 102 | lit-bias-discretion | mod | 39 | -159 | 0 | -218 | -1,822 | 0.7958 |  | no |
| 103 | lit-supplement | mod | 20 | -164 | -152 | -354 | -17 | 0.8029 |  | no |
| 104 | lit-untested-entries | mod | 30 | -165 | 81 | -845 | -1,846 | 0.8265 |  | no |
| 105 | e2:pdx | stream | 18 | -170 | -131 | -252 | -476 | 0.8794 |  | no |
| 106 | plus:vwp | stream | 8 | -178 | -98 | -476 | -609 | 0.7320 |  | no |
| 107 | 2026-11-03-prometheus | mod | 5 | -180 | -223 | 1,141 | -1,693 | 0.7953 |  | no |
| 108 | atlas-confluences | mod | 7 | -184 | -209 | -393 | 407 | 0.9024 |  | no |
| 109 | plus:odc | stream | 8 | -201 | -73 | -917 | -530 | 0.9535 |  | no |
| 110 | timing | mod | 2 | -208 | -199 | -414 | 0 | 0.9552 |  | no |
| 111 | lit-new-entries | mod | 20 | -214 | -184 | -229 | -515 | 0.9397 |  | no |
| 112 | lit-two-week-eval | mod | 6 | -215 | -61 | -1,284 | -311 | 0.8279 |  | no |
| 113 | lit-reversal-exit | mod | 12 | -250 | 135 | -1,187 | -3,085 | 0.8613 |  | no |
| 114 | lit-more-entries | mod | 17 | -270 | -152 | -872 | -656 | 0.8599 |  | no |
| 115 | hunt:lsq | stream | 216 | -272 | -281 | -451 | 92 | 0.9272 |  | no |
| 116 | lit-chatgpt-filters | mod | 66 | -280 | 17 | -3,093 | 669 | 0.8141 |  | no |
| 117 | 2026-11-15-lit-deep | mod | 8 | -283 | -78 | -1,948 | -33 | 0.8748 |  | no |
| 118 | lit-strategy | mod | 2 | -289 | -247 | 253 | -1,562 | 0.9555 |  | no |
| 119 | stops.md | mod | 20 | -290 | -311 | -841 | 758 | 0.9814 |  | no |
| 120 | lit-retail-confluence | mod | 281 | -295 | -206 | -683 | -694 | 0.8932 |  | no |
| 121 | second-sr | mod | 6 | -308 | -502 | 1,483 | -870 | 0.8871 |  | no |
| 122 | lit-more-setups | mod | 18 | -344 | -272 | -1,056 | -67 | 0.9714 |  | no |
| 123 | lit-untested-targets | mod | 56 | -362 | 156 | -3,642 | -1,135 | 0.8591 |  | no |
| 124 | lit-report-tests | mod | 43 | -381 | -310 | -771 | -581 | 0.9498 |  | no |
| 125 | third:tds | stream | 48 | -421 | -354 | -1,000 | -289 | 0.8466 |  | no |
| 126 | atlas-chatgpt-breakouts | stream | 30 | -486 | -400 | -665 | -1,171 | 0.8593 |  | no |
| 127 | lit-tight-stops-size | mod | 10 | -506 | -517 | 1,729 | -3,733 | 0.7649 |  | no |
| 128 | e2:vwr | stream | 18 | -531 | -666 | -286 | 585 | 0.9828 |  | no |
| 129 | hunt:fav | stream | 72 | -639 | -520 | -1,219 | -1,074 | 0.9991 |  | no |
| 130 | allday | stream | 22 | -742 | -692 | 432 | -3,050 | 0.9670 |  | no |
| 131 | second-md | mod | 9 | -820 | -786 | 130 | -2,624 | 0.9703 |  | no |
