---
title: Why we win, why we lose (2026-11-18) - every Zlarior, ATLAS and BLITZ trade taken apart; the losers are mostly good trades that lost, a careful human's skip list costs money, 0 of 4 rules pass
family: risk
date: 2026-11-18
status: finding (no change). 4 rules from the anatomy tested on the real backtests, 0 pass; all 4 registered in the ZEUS Lab (re-tested every night)
summary: Owner - "See why our losses lose for strategies. And why they win. I expect all of our strategies to be better." Every trade of the repo's own backtests (costs in) was taken apart - Zlarior 631 (run lit_live, 2026 on 1m), ATLAS 1,288 account trades, BLITZ 2,198 - with MAE / MFE in R and $ and the minutes to each, exit, session, weekday, VIX band, ranges, gaps, prior-day levels, daily and 1h trend, chop, news, ES and what came after the exit. Losers mostly never worked (Zlarior 62% of 2026's lost $, ATLAS 58%, BLITZ 72%); real shake-outs are rare (a 50% wider stop would have won 0-9% of Zlarior / ATLAS stop-outs); nothing known at the entry separates losers from winners better than chance; a pre-declared careful-human checklist would have skipped as many winners as losers (Zlarior -$4,320 Jan-Jun / -$5,518 Jul-Oct, ATLAS -$13,732 / -$2,570). Four rules (Zlarior trend-pullback x1.25 and checklist skip, ATLAS London-open x1.25 and checklist skip) all fail the adopt bar. Nothing changes.
runs: research/anatomy/ (trades_lit / trades_atlas / trades_blitz.json, explain.json, rules.json); tools/win_loss_anatomy.py; ZEUS Lab ids lit_anat_pullback_x1.25, lit_anat_checklist_skip, atlas_anat_london_open_x1.25, atlas_anat_checklist_skip
---

# Why we win, why we lose (2026-11-18)

Owner: "See why our losses lose for strategies. And why they win. I expect all of our strategies to be better."

## In plain words

- **Zlarior (LIT, the 50K).** In 2026 it took 120 trades and made **+$43,820** at the LIT size. The 53 losing trades cost
  **$13,727**. **62% of that was trades that never worked**: the sweep was not the day's turning point, price never went even
  +0.5R our way, and the stop came in about half an hour. 33% worked first (+0.5R or more), then turned. Shake-outs (stopped,
  then price went on to our target) were **2%**, news releases 4%. A stop 50% wider would have reached the target first on **0%
  of the Jan-Jun stop-outs and 5% of the Jul-Oct ones**: the stops are real, not wicks.
- **Why Zlarior wins.** A few big winners pay for everything: **the best 20% of the 2026 winners made $42,563 of the
  $43,820**. A winner barely goes against us (median 0.19R in Jan-Jun) and needs hours (median 106 minutes). The real
  difference is hindsight: on days that closed our way the trades made +$37,119 in 2026, on days that closed against us +$7,061
  (and -$50,950 in 2021-25). You only know the close after the close. The 3 biggest Zlarior losers of 2026 (-$755, -$635,
  -$564) passed every check a careful human would make.
- **ATLAS (the 25K).** 163 trades in 2026, **+$33,966 at $250 a trade**; the 73 losers cost **$17,470**: never worked 58%,
  worked then turned 36%, shaken out 5%, news 2%. The best 20% of winners made $30,844. Same story as Zlarior.
- **BLITZ (hidden, paper).** 329 trades in 2026, +$7,657 at $150 a trade; losers cost $13,166, 72% never worked. BLITZ is a
  momentum scalper: it wins on trend days and loses on two-way days (2021-25: -$11,847 on chop days). Its stops ARE sometimes
  shake-outs (a 50% wider stop would have reached +1R on ~30% of stop-outs), but wider BLITZ stops were already tested and lost
  (blitz-25k.md): the other 70% of stop-outs get bigger.
- **Good trades that lost, or trades to skip?** A careful-human checklist, written before the first run (against both the
  daily and the 1h trend; the day already moved 1 daily ATR; a big US release within 30 minutes; the prior day's high / low
  less than 1R ahead): **55% of Zlarior's Jan-Jun lost $ and 66% of its Jul-Oct lost $ passed every check - good trades that
  lost.** The checklist would have skipped losers worth $3,815 in Jan-Jun but also winners worth $8,134. **Skipping every
  flagged trade: Zlarior -$4,320 Jan-Jun, -$5,518 Jul-Oct; ATLAS -$13,732 / -$2,570; BLITZ -$3,419 / -$2,242.** It only helps
  in the bad years (2021-25: Zlarior +$3,264, ATLAS +$5,716).
- **Nothing at the entry tells a loser from a winner.** Of 86 Zlarior fact buckets (session, weekday, VIX, trends, news, prior-day
  levels, gap, chop, the setup's own facts), 18 were worse or better in all three periods; with the results shuffled at random
  you get 15.4 on average (p 0.27). ATLAS 12 of 90 vs 15.7 (p 0.78), BLITZ 7 of 66 vs 14.2.
- **What we tested.** Four rules from the strongest findings, on the real backtests (picked on Jan-Jun 2026, checked on Jul-Oct
  and 2021-25, costs in): Zlarior x1.25 on a pullback in the daily trend, Zlarior skip-the-checklist, ATLAS x1.25 in the London
  open hour, ATLAS skip-the-checklist. **0 of 4 pass.** The nearest miss is ATLAS's London-open hour: +$125 / +$34 a month on the
  25K path in 2026, but 2025's money after fees is $494 worse and the Jul-Oct gain could be luck. All four are in the ZEUS Lab and
  re-tested every night on new data. No proposal goes to the Decide card.
- **Kalshi K8 metals (paper, in-sample).** 465 bets, 70% won, +$2,234 at $15: it wins by being right often (a win pays $13.36, a
  loss costs $15.27), the money is in the cheap fills (under 50c: +$1,106), and gold and silver of one window win or lose
  together (both lost 45 of 232 windows). Section 7.
- **What this means.** Our losses are the price of the edge, not mistakes a careful human would avoid. The strategies are better
  served by what already protects them (the 15-minute check, the weekly half size, the eval's 40% room cap, ATLAS's zombie-eval
  rule) than by a filter. "Better" will have to come from new setups or more accounts, not from cutting losers.

## The money (costs in)

Zlarior at the LIT size ($800 a trade up to a 20-point stop, then 800 x 20 / stop); ATLAS at a fixed $250 a trade (the funded 25K
size; the account path with the real account-B rules is in section 5); BLITZ at $150 a trade (at least 1 micro).

| Bot | Period | Trades | A week | Win % | PF | Net | $ a month | Max DD |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Zlarior | Jan-Jun 2026 | 80 | 3.12 | 58.8 | 4.98 | +$33,901 | +$5,562 | -$2,196 |
| Zlarior | Jul-Oct 2026 | 40 | 2.56 | 50.0 | 2.91 | +$9,919 | +$2,670 | -$1,396 |
| Zlarior | 2021-25 | 511 | 2.38 | 53.8 | 1.01 | +$1,265 | +$25 | -$19,426 |
| ATLAS | Jan-Jun 2026 | 112 | 4.38 | 54.5 | 3.02 | +$25,737 | +$4,223 | -$1,533 |
| ATLAS | Jul-Oct 2026 | 51 | 3.27 | 56.9 | 2.73 | +$8,228 | +$2,215 | -$1,224 |
| ATLAS | 2021-25 | 1,125 | 5.25 | 37.2 | 1.09 | +$15,162 | +$297 | -$12,430 |
| BLITZ | Jan-Jun 2026 | 220 | 8.59 | 55.5 | 1.63 | +$5,513 | +$904 | -$1,314 |
| BLITZ | Jul-Oct 2026 | 109 | 6.99 | 55.0 | 1.49 | +$2,143 | +$577 | -$903 |
| BLITZ | 2021-25 | 1,869 | 8.72 | 50.3 | 1.06 | +$4,570 | +$90 | -$4,783 |

Win % here = trades that made money after costs (a breakeven exit at entry + 1.25 points is a small winner).

## 1. Why the losers lose

Every losing trade got ONE main cause, in this order: a high-impact US release from 15 minutes before the entry to the exit
(news); stopped, then price went on to the original target that session before going 0.5R deeper than the stop (shaken out;
BLITZ has no target, so +1R); it was +0.5R or more first (worked, then turned); else it never worked.

| Bot | Period | Losers | $ lost | Never worked | Worked, then turned | Shaken out | News |
|---|---|---:|---:|---:|---:|---:|---:|
| Zlarior | Jan-Jun 2026 | 33 | -$8,524 | 61% (-$5,184) | 34% (-$2,859) | 0% | 6% (-$482) |
| Zlarior | Jul-Oct 2026 | 20 | -$5,202 | 65% (-$3,363) | 31% (-$1,615) | 4% (-$225) | 0% |
| Zlarior | 2021-25 | 236 | -$98,882 | 67% | 27% | 4% | 1% |
| ATLAS | Jan-Jun 2026 | 51 | -$12,724 | 60% (-$7,670) | 31% (-$3,901) | 7% (-$888) | 2% (-$264) |
| ATLAS | Jul-Oct 2026 | 22 | -$4,746 | 50% (-$2,379) | 50% (-$2,367) | 0% | 0% |
| ATLAS | 2021-25 | 707 | -$171,071 | 56% | 36% | 7% | 1% |
| BLITZ | Jan-Jun 2026 | 98 | -$8,815 | 71% | 19% | 11% | 0% |
| BLITZ | Jul-Oct 2026 | 49 | -$4,351 | 75% | 17% | 4% | 4% |
| BLITZ | 2021-25 | 929 | -$81,497 | 67% | 16% | 16% | 1% |

**The stop-outs** (STOP + the 15-minute cut):

| Bot | Period | Stop-outs | $ | Best point before (median) | Minutes to the stop (median) | Never +0.5R | Target later that day | A stop 50% wider wins | Next hour after the stop (median) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Zlarior | Jan-Jun 2026 | 32 | -$8,451 | +0.21R | 33 | 72% | 16% | 0% | -0.04R |
| Zlarior | Jul-Oct 2026 | 20 | -$5,202 | +0.31R | 40 | 75% | 35% | 5% | -0.41R |
| Zlarior | 2021-25 | 227 | -$98,127 | +0.27R | 55 | 70% | 19% | 4% | +0.05R |
| ATLAS | Jan-Jun 2026 | 49 | -$12,329 | +0.29R | 30 | 65% | 33% | 9% | -0.12R |
| ATLAS | Jul-Oct 2026 | 19 | -$4,350 | +0.48R | 15 | 53% | 26% | 0% | +0.60R |
| ATLAS | 2021-25 | 649 | -$164,373 | +0.32R | 25 | 61% | 30% | 7% | -0.04R |
| BLITZ | Jan-Jun 2026 | 48 | -$5,333 | +0.19R | 12 | 73% | - | 31% (+1R) | +0.09R |
| BLITZ | Jul-Oct 2026 | 19 | -$2,591 | +0.22R | 22 | 79% | - | 29% (+1R) | +0.03R |
| BLITZ | 2021-25 | 597 | -$63,743 | +0.24R | 20 | 76% | - | 30% (+1R) | +0.19R |

"Target later that day" counts any touch after the stop, even after price first ran far beyond the stop; "a stop 50% wider wins"
asks the honest question (the target before the wider stop, from the entry). The live stop stays 1 tick beyond the sweep
extreme (hard rule); this is a diagnosis, not a proposal.

**Breakeven exits.** Zlarior's 29 Jan-Jun breakevens had been a median +1.83R up; 41% of them later reached the target (Jul-Oct:
0 of 6; 2021-25: 30%). They cost $0 (+$115). Breakeven changes were tested many times (BE at 0.75 / 0.9 / max(1R, ATR), on a close,
structure trails, reversal exits: Tested and rejected) and none held in both halves.

**The biggest losers of 2026 were good trades that lost.** Zlarior: 2026-02-25 06:21 short -$755 (never worked, out in 12
minutes), 2026-08-03 02:02 long -$635 (+0.74R first, then stopped), 2026-01-14 02:17 long -$564 (+0.61R first): all three passed
every check of section 2. ATLAS: 2026-08-13 EMA long -$281 (+0.59R first), 2026-01-02 MACD short -$271 (+0.79R first),
2026-04-03 EMA long -$270 (never worked): all three passed every check too.

## 2. Good trades that lost, or trades a careful human would skip?

The checklist (written before the first run, entry facts only, classic discretionary rules - no data mining): (1) against the
daily trend (yesterday's close vs its 20-day average) AND the 1h trend (EMA 20 vs 50); (2) late: the day (from 18:00) had already
moved 1 daily ATR before the entry; (3) a high-impact US release within 30 minutes after the entry; (4) no room: the prior day's
high (long) / low (short) less than 1R ahead.

| Bot | Period | Losers: passed every check (good trades that lost) | Losers flagged | Winners flagged | Skipping every flagged trade |
|---|---|---:|---:|---:|---:|
| Zlarior | Jan-Jun 2026 | 17 trades, 55% of the lost $ | 16, -$3,815 | 18, +$8,134 (19% of the won $) | **-$4,320** (-$709 a month) |
| Zlarior | Jul-Oct 2026 | 11 trades, 66% | 9, -$1,776 | 8, +$7,294 (48%) | **-$5,518** (-$1,486 a month) |
| Zlarior | 2021-25 | 122 trades, 52% | 114, -$47,448 | 146, +$44,184 (44%) | +$3,264 (+$64 a month) |
| ATLAS | Jan-Jun 2026 | 32 trades, 63% | 19, -$4,736 | 23, +$18,468 (48%) | **-$13,732** (-$2,253 a month) |
| ATLAS | Jul-Oct 2026 | 16 trades, 78% | 6, -$1,042 | 10, +$3,612 (28%) | **-$2,570** (-$692 a month) |
| ATLAS | 2021-25 | 462 trades, 67% | 245, -$56,865 | 101, +$51,149 (27%) | +$5,716 (+$112 a month) |
| BLITZ | Jan-Jun 2026 | 38 trades, 36% | 60, -$5,661 | 72, +$9,080 (63%) | **-$3,419** |
| BLITZ | Jul-Oct 2026 | 20 trades, 40% | 29, -$2,612 | 44, +$4,854 (75%) | **-$2,242** |
| BLITZ | 2021-25 | 271 trades, 26% | 658, -$60,175 | 667, +$62,851 (73%) | -$2,676 |

Which check does what (2026, Zlarior): "against both trends" flagged 43 trades, the losers among them -$4,995, the winners
+$12,229 (a sweep-and-reverse strategy often trades against both trends, and in Jul-Oct those were its best trades); "late"
3 trades; "news within 30 minutes" 1 trade (-$482); "no room" 7 trades (losers -$381, winners +$3,199). BLITZ trades late in the
day by design, so "late" flags 180 of its 329 trades in 2026 (losers -$7,251, winners +$13,202).

## 3. Why the winners win

| Bot | Period | Winners | Best 20% of winners made | Against us first (median) | Never 0.25R against | Minutes in the trade (median) | Best point after (median) | Winners on days that closed our way | Losers on such days |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Zlarior | Jan-Jun 2026 | 47 | +$33,838 (100% of the net) | 0.19R | 53% | 106 | 69 min | 62% | 31% |
| Zlarior | Jul-Oct 2026 | 20 | +$8,725 (88%) | 0.59R | 20% | 184 | 158 min | 50% | 40% |
| ATLAS | Jan-Jun 2026 | 61 | +$22,380 (87%) | 0.33R | 41% | 100 | 75 min | 67% | 50% |
| ATLAS | Jul-Oct 2026 | 29 | +$7,225 (88%) | 0.32R | 34% | 75 | 46 min | 66% | 45% |
| BLITZ | Jan-Jun 2026 | 122 | +$7,332 | 0.27R | 48% | 31 | 24 min | 98% | 87% |

- **A few big winners.** Zlarior and ATLAS are "lose small often, win big rarely" systems: the top fifth of the winners is the
  whole profit. Anything that trims the big ones (earlier exits, tighter targets, clock exits) has been tested and loses.
- **Winners are clean and slow.** The median winner never goes far against us and needs 1.5-3 hours. That is why the 15-minute
  check works (losers show themselves early) and every later clock exit loses (winners need the time).
- **Winners sit on days that close our way** (hindsight). Zlarior 2026: +$37,119 on days that closed with the trade vs +$7,061
  against; 2021-25: +$52,621 vs -$50,950. In 2021-25 the whole strategy is these two numbers cancelling. ATLAS: +$29,261 vs
  +$4,975 (2026), +$79,693 vs -$64,486 (2021-25).
- **After the target.** When a Zlarior trade hit its target, price went a further median +2.3R (Jan-Jun) / +2.5R (Jul-Oct)
  our way later that session (ATLAS +2.7R / +1.5R): the VIX band and the 8R bank leave money on the table on some days, but the
  runner / trail / no-bank versions were tested and lost on the eval path (structure-management.md, lit-edge-2026-10-30.md).

## 4. Is there anything at the entry? (the chance check)

Every entry fact was cut into buckets (categories as they are; numbers in terciles picked on Jan-Jun 2026 only): session,
weekday, VIX band, side, daily trend, 1h trend, the four daily x 1h cells, ES 1h trend (ES from 2025-04), news, place in the
prior day's range, room to the prior-day level, move before the entry, 18:00 gap, the last 5 days' efficiency (chop vs trend),
the range before the entry, the prior-day distance, stop size, daily ATR, VIX, and each bot's own setup facts (Zlarior: stop in
ATR, R:R, displacement, sweep depth, inducements, nearest opposing level, wait after the CISD, level age; ATLAS: member, member +
side, hour, R:R, stop in ATR, stop vs the member's median; BLITZ: hour). A bucket counts when it is worse (or better) than the
bot's own average in Jan-Jun, Jul-Oct AND 2021-25, with 8+ trades in each. Control: the results shuffled across the trades of
each period, 200 times.

| Bot | Buckets | Consistent (real) | Shuffled: average / 95th pct | p |
|---|---:|---:|---:|---:|
| Zlarior | 86 | 18 (12 worse, 6 better) | 15.4 / 22 | 0.27 |
| ATLAS | 90 | 12 (8 worse, 4 better) | 15.7 / 23 | 0.78 |
| BLITZ | 66 | 7 (2 worse, 5 better) | 14.2 / 22 | 0.97 |

So the "patterns" a chart reader would see in the losers (Zlarior's deep sweeps, big displacement, VIX 15-20, London late;
ATLAS's NY-morning, Tuesday and low-VIX trades) are what chance alone produces. This matches the earlier loser studies
(lit-losses.md, 2026-11-15-lit-deep.md, 2026-11-15-atlas-deep.md).

## 5. Rules tested (the adopt bar)

Pre-declared single versions (tools/win_loss_anatomy.RULES), one run each, through the ZEUS Lab's own runners and judges:
Zlarior = tools/lit_edge.evaluate (LIT size + the live two_week eval path, room 0.4 to session 80) + learn_loop.judge_lit (more $
in Jan-Jun AND Jul-Oct at the LIT size and on the eval path, 2-week fails not up, 2-4 trades a week, enough trades changed, the
200-draw size shuffle); ATLAS = tools/atlas_deep.score (the real account-B rules on the Builder 25K, $43 evals) +
atlas_v2.verdict (2025 and 2021-24 money a gate) + the Lab's sign-flip placebo under its many-tests bar (p <= 0.0034 with 59
cells). The skips leave the day as it was (no later setup re-fills it).

| Rule | Period | Trades | A week | PF | Net | $ a month | Max DD | 2-week pass / fail | vs today |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| **Zlarior x1.25 on a pullback in the daily trend** (daily with, 1h against) | Jan-Jun | 80 | 3.12 | 5.11 | +$36,028 | +$5,911 | -$2,373 | 45.4 / 0.0 | +$349 a month (eval path +$163) |
| | Jul-Oct | 40 | 2.56 | 2.88 | +$9,896 | +$2,664 | -$1,396 | 39.1 / 0.0 | **-$6 a month** (eval path +$130) |
| | 2021-25 | 511 | 2.38 | 1.02 | +$1,847 | +$36 | -$18,948 | - | +$11 a month |
| **Zlarior: skip the checklist trades** | Jan-Jun | 46 | **1.80** | 7.26 | +$31,393 | +$5,150 | -$1,373 | 37.0 / 0.0 | **-$412 a month** (eval path -$8,488 in total) |
| | Jul-Oct | 23 | **1.47** | 2.22 | +$4,295 | +$1,156 | -$1,324 | 24.6 / 0.0 | **-$1,514 a month** |
| | 2021-25 | 251 | 1.17 | 1.11 | +$5,851 | +$115 | -$12,428 | - | +$90 a month |
| **ATLAS x1.25 in the London-open hour** (03:00-03:59 ET), 25K account path | Jan-Jun | 90 | 3.52 | 2.82 | +$14,290 | +$2,344 | -$1,207 | 61.3 / 0.0 | +$125 a month; money after fees $9,590 vs $9,083 |
| | Jul-Oct | 25 | 1.60 | 3.21 | +$4,135 | +$1,113 | -$887 | 43.5 / 0.0 | +$34 a month; $2,253 vs $2,135 |
| | 2025 | 150 | 2.91 | 0.88 | -$1,549 | -$126 | -$4,973 | 24.9 / 0.0 | path +$122 a month, **money after fees -$2,605 vs -$2,111** |
| | 2021-24 | 587 | 3.61 | 0.95 | -$2,767 | -$71 | -$10,714 | 19.4 / 0.0 | -$14 a month; money -$3,782 vs -$3,953 |
| **ATLAS: skip the checklist trades**, 25K account path | Jan-Jun | 31 | 1.21 | 2.02 | +$2,489 | +$408 | -$1,423 | **39.5** / 0.0 (61.3) | **-$1,811 a month**; money after fees -$5,012 |
| | Jul-Oct | 21 | 1.35 | 2.07 | +$2,210 | +$595 | -$851 | **30.4** / 0.0 (43.5) | **-$484 a month**; money -$1,479 |
| | 2025 | 124 | 2.40 | 0.88 | -$1,315 | -$107 | -$3,361 | 20.5 / 0.0 | +$141 a month |
| | 2021-24 | 472 | 2.90 | 1.22 | +$9,151 | +$236 | -$5,733 | 21.9 / 0.0 | +$293 a month (PF 0.96 -> 1.22) |

Today (for the table): Zlarior LIT size Jan-Jun 80 trades 3.12 a week PF 4.98 +$33,901 ($5,562 a month) DD -$2,196, eval path
2-week pass / fail 44.5 / 0.0; Jul-Oct 40, 2.56, PF 2.91, +$9,919 ($2,670), DD -$1,396, 39.1 / 0.0; 2021-25 PF 1.01 +$1,265.
ATLAS 25K path Jan-Jun 85 trades 3.32 a week PF 2.81 +$13,524 ($2,219 a month) DD -$1,200, 2-week pass 61.3 / 0.0; Jul-Oct 25,
1.60, PF 3.14, +$4,009 ($1,079), 43.5 / 0.0; 2025 PF 0.78 -$3,052; 2021-24 PF 0.96 -$2,223.

Verdicts:
- **Zlarior pullback x1.25: rejected.** Jul-Oct -$23 at the LIT size. Its 6 Jul-Oct trades averaged +1.74R, but the winners
  were wide-stop trades at 2-3 micros (x1.25 rounds to the same micros) while the one 7-micro loser became 8 micros. The
  sign-flip p is 0.08 / 1.0. 21 trades changed in 2026 (15 + 6).
- **Zlarior checklist skip: rejected.** PF rises in Jan-Jun (4.98 -> 7.26) and falls in Jul-Oct (2.91 -> 2.22); the money, the
  trades a week (1.8 / 1.5, under the 2-4 bar) and the 2-week passes fall in both halves; only 2021-25 improves.
- **ATLAS London-open x1.25: rejected.** Better on the 25K path in Jan-Jun, Jul-Oct and 2021-24 path $, but 2025's money after
  fees is $494 worse (the v2 test's reference tier) and the Jul-Oct gain has p 0.075 against a bar of 0.0034. The Lab re-tests it
  nightly.
- **ATLAS checklist skip: rejected.** It halves ATLAS's 2026 trading and drops the 2-week pass 61 -> 40% and 44 -> 30%, while it
  turns 2021-24 positive (PF 1.22). Care pays in the bad years and costs in the good ones; the drift switch (cut size after a
  rolling loss) was the same idea in another form and failed 0 / 51.

No rule passed, so no proposal was added to business/decisions.json.

## 6. For the other helpers and next steps

- Setup-quality grade ("trade like a person"): the four checklist facts are in research/anatomy/trades_<bot>.json (d1, h1,
  rng_atr, news_next, pd_tgt_r) next to MAE / MFE and the post-exit facts; a grade has to beat this table's chance control and
  the checklist result (it skips winners as often as losers) to be worth more than noise.
- Zlarior ideas: the money is in the few big winners and in days that close our way. An idea that does not change WHICH days we
  are in (a filter) or how much of a big day we keep (the 8R bank, already tested) will not move the needle.
- ATLAS protection: ATLAS's losers look like its winners; its account-level rule (zombie eval) was the only keeper and is on.
- The ZEUS Lab re-runs the four rules every night (kind anatomy = tools/win_loss_anatomy.lab_run, and an atlas_tilt); a rule
  only reaches the owner after it passes, then 4 weeks of shadow.

## 7. Kalshi K8 metals (paper): wins vs losses

From K8's own bet list (research/kalshi_edge_K8/data/legs_bets.csv: the 6 gold / silver 15-minute clock legs, $15 a bet, fees
in, Aug 3 - Nov 18; the oil / gas extras left out; `k8_anatomy` in the tool). All of it is the friend's own history (in-sample,
kalshi-red-team-K8-2026-11-19.md); "test" = the weeks the study held out.

- **465 bets, 70% won, +$2,234.** A loss costs $15.27, a win pays $13.36: K8 wins by being right often, not by winning big.
- **Why it wins: the cheap fills.** Bets bought under 50c made +$1,106 of the $2,234 (64% won, $18.25 a win). At 60c and up
  they won 83% but paid only $7.87 a win, +$307 in total. The price creeping up (50c in October to 54c lately, red team) is the
  biggest threat to the money, more than the win rate.
- **Why it loses: the two metals are one bet.** In 232 windows with both a gold and a silver bet, both won 139 times and both
  lost 45 times (48 split): a bad window costs two losses at once, so the 6 legs are closer to 3 bets a day.
- **Held-out weeks:** 68% won, +$945 (train 72%, +$1,289); 2 of 16 weeks lost money, the newest one -$74.

| Leg | Bets | Won | Net |
|---|---:|---:|---:|
| 05:15 down, gold | 77 | 72.7% | +$435 |
| 05:15 down, silver | 76 | 63.2% | +$230 |
| 16:00 down, gold | 78 | 70.5% | +$415 |
| 16:00 down, silver | 78 | 74.4% | +$442 |
| 16:45 up, gold | 78 | 65.4% | +$258 |
| 16:45 up, silver | 78 | 74.4% | +$452 |

| Price paid | Bets | Won | Net | A win pays |
|---|---:|---:|---:|---:|
| under 50c | 184 | 63.6% | +$1,106 | $18.25 |
| 50-55c | 122 | 69.7% | +$527 | $12.84 |
| 55-60c | 82 | 73.2% | +$294 | $10.45 |
| 60c+ | 77 | 83.1% | +$307 | $7.87 |

No rule was tested on K8 here (no paper results yet, and every leg is in-sample); the red team's plan stands: paper first, live
small only after 120 paper bets at 65%+ won with the average price at or under 56c.

## How it was done

- Code: `tools/win_loss_anatomy.py` (build / explain / rules / register / page). It imports the repo's backtests and edits
  none: Zlarior = tools/lit_edge.ctx()["T"] (= run lit_live, checked trade for trade, $ per trade identical), its 57 entry facts
  from research/lab/trade_intel.json; ATLAS = tools/atlas.account_units(BASE) + tools/atlas_deep.feats (EMA / MACD / S-R after
  the no-hedge rules), entry / stop / target from research/second/*_best.json; BLITZ = tools/scalp_na_lib.lines with the live
  prior-range filter (prng >= 0.8), 2026 on 1m (329 of na_best_trades.json's 330 trades sit on a bar of the LIT 1m set), 2021-25
  on 5m.
- Data: TradingView CME NQ1! 5m (2021-10 to 2026-10-16), true 1m for 2026, ES1! 5m from 2025-04, VIX (CBOE), the high-impact US
  calendar data/news/events.csv (2024-26 complete; 2021-23 FOMC only, so news is undercounted before 2024). No Yahoo, no CFD.
- Path facts: 1m bars for 2026 Zlarior / ATLAS / BLITZ, 5m before. MFE / MAE in R are the engine's own (Zlarior, BLITZ) or the
  path's (ATLAS); the minutes to each come from the path. After the exit = until 15:55 ET the same CME day.
- Entry facts are known at the entry (5m bars closed before it; 1h EMAs of closed hours; the prior day's close); h_day_er /
  h_day_with (the day's own close) are hindsight and only describe.
- Commands: `python -X utf8 tools/win_loss_anatomy.py all` (~2 min), `register` (once), `python -X utf8 tools/zeus_lab.py run
  --only lit_anat_pullback_x1.25,lit_anat_checklist_skip,atlas_anat_london_open_x1.25,atlas_anat_checklist_skip`.
  Test: `python -X utf8 -m tests.test_why_page` (area nq).
- Phone page: tools/web_public/why/ (index.html, why.js, why.css, why.json + jarvis.json built by `... page`); BLITZ is left out
  while dashboard_view.json hides it.
