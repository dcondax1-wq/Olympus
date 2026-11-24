# 24-hour coverage + a walk-forward portfolio of everything built (2026-11-24)

Owner: "24/7 trading, more strategies, smarter, time and price, confluence". PAPER RESEARCH ONLY. Rules first:
`research/portfolio/DESIGN.md` (committed before any hold-out). Code `research/portfolio/coverage.py`, `portfolio.py`.

## Verdict
**No portfolio beats today (LIT + ATLAS) on both hold-outs. Nothing to switch on.** Adding the best 6 of 508 uncorrelated
tested ideas makes a little more $, but with a lower PF, deeper drawdowns, 15+ extra trades a week and much worse eval odds
in Jul-Oct. The one real hole in the week is Asia (18:00-02:00 ET): no live strategy trades it, and every Asia idea tested so
far failed (TESTED_AND_REJECTED: LIT Asia slot, Asia resweep hunt, E3 sessions).

## (1) Coverage of the week (`coverage.json`)
- 220 open 30-min slots a week (Sun 18:00 - Fri 17:00, minus the 16:00-18:00 close). **140 covered (64%), 80 empty.**
- **Covered: 02:00-15:30 ET every weekday.** LIT 02:00-15:30; ATLAS EMA 03:00-09:00, MACD 02:00-04:30 + 09:30-10:30, S/R
  09:30-11:30; BLITZ 11:00-15:30.
- **Empty: 18:00-02:00 ET (Asia) every night**, by choice (tested and rejected) and partly MFFU-free: the Builder accounts
  allow it; the Rapid funded account bans trading 2 minutes either side of the main US news.
- **Closed / not allowed:** 15:55 bot flat, 16:10 MFFU auto-close, 17:00-18:00 CME halt.
- Backtest $ by time (all three pillars, 2021-26, costs in): best 03:00-04:00 (+$54,853 over 439 trades), 09:30-10:30 +$14k,
  15:00 +$7k; worst 06:30 (-$6,769), 11:00 (-$5,083), 05:00-06:00 (-$7k).

## (2) Portfolio search (`results.json`)
Pool: 1,983 stored runs covering 2021-11 .. 2026-10-16. Picked on 2021-11..2024 + Jan-Jun 2026 only: 508 pass the candidate
rule (>= 100 trades, PF >= 1.10, daily corr with LIT and ATLAS < 0.30). Greedy by Sharpe added 6, each scaled to 25% of LIT's
daily swing: datacity_holdout_portfolio x0.33, strategytree_top5 x0.61, sh_book x0.32, retail_sa_sr_sr_limit_best x0.27,
div_na_paper x0.16, sh_trend_idm x0.53 (the add-ons' daily corr with today ~0).

| Span | Book | Trades/wk | PF | Net $ | $/mo | Max DD | 50K pass/fail (40 sessions), days | 25K | Rapid 25K |
|---|---|---|---|---|---|---|---|---|---|
| PICK | today | 7.1 | 1.17 | +$27,653 | $616 | -$34,012 | 31/65, 11 | 32/64, 11 | 1/72, 32 |
| PICK | portfolio | 24.0 | 1.24 | +$58,446 | $1,303 | -$28,976 | 33/67, 8 | 37/63, 9 | 12/74, 21 |
| **2025 (hold-out)** | today | 6.5 | 1.13 | +$4,480 | $365 | -$7,550 | 32/60, 10 | 38/54, 12 | 0/65 |
| **2025 (hold-out)** | portfolio | 21.9 | 1.09 | +$5,453 | $444 | -$10,568 | 35/61, 8 | 39/57, 9 | 4/78, 28 |
| **Jul-Oct 2026 (hold-out)** | today | 5.5 | 3.36 | +$16,311 | $4,391 | -$1,493 | 100/0, 17 | 100/0, 17 | 69/0, 33 |
| **Jul-Oct 2026 (hold-out)** | portfolio | 20.1 | 2.49 | +$19,324 | $5,203 | -$2,329 | **64/36**, 8 | 67/33, 7 | 51/39, 21 |

Why it fails the pre-set bar: lower PF in both hold-outs; drawdown 1.4x / 1.6x; Jul-Oct 50K fails 0% -> 36% (more trades =
more ways to hit the trailing floor); 15 add-on trades a week (bar 2-6).
Honest caveats: (a) daily-level book (the one-position rule cannot be enforced from daily rows; it would only cut trades);
(b) 3 of the 6 members are "best of" picks from earlier projects whose own selection may have seen 2025-26 data, which
flatters the portfolio, and it STILL fails; (c) "today" here = run lit_live (LIT size) + atlas_funded_live, not the eval-path
sizing, so its eval odds differ from the live dashboards; (d) the stored runs end Oct 16 (no Nov in the hold-out).
"Time x price" members: only those already in the pool; none newly designed.
