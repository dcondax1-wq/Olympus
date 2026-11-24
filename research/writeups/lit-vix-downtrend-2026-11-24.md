# LIT in high-VIX falling markets: bad luck or a losing regime? (2026-11-24)

Lead's question after the live audit: LIT had 0 real winners in its 7 twin trades Oct 19 - Nov 20 while NQ fell 31k -> 25k.
PAPER RESEARCH ONLY. Rules written first: `research/litvix/DESIGN.md`. Code `research/litvix/study.py` -> `results.json`.
Trades: the live LIT rules 2021-10 .. 2026-10-16 (run lit_live, 631) + the twin on PC bars to Nov 20 (7), risk-matched $, costs in.

## Verdict: variance, not a regime. No rule to switch on.
- **The premise was off: the losers did NOT come at VIX 25+.** At the 7 live-window entries the prior VIX close was 17.5-21.2
  (6 in 15-20, 1 in 20-25). VIX only went 25+ around Nov 20, after the trades. 6 of 7 had a 20-day DOWN trend.
- **VIX 25+ is LIT's BEST band**: 2021-25 70 trades, win 67%, PF 2.50, +$9,590; Jan-Jun 2026 6 trades, PF 22.7, +$4,065
  (0 in Jul-Oct). VIX 25+ with a 20-day downtrend: 2021-25 PF 2.66 (longs PF 1.74, shorts 4.43).
- **0 real winners in 7 is normal for LIT.** Real winners (+0.5R or more) are about 1 trade in 5-6 (2021-25 14%,
  Jan-Jun 23%, Jul-Oct 33%; the rest are breakeven scratches and stops). Runs of 7+ trades without one: 25 in 2021-25,
  **4 in Jan-Jun 2026 (the best half ever, longest 12)**, 1 in Jul-Oct. At 2026 rates a year of trades (~125) has such a run
  99.6% of the time. On the plain "$ > 0" count the live window was W L L W L L L (longest 3; 2026 had a 7, 2021-25 a 10).

| Rule (pre-registered) | Skipped (2021-25 / H1 / H2) | 2021-25 | Jan-Jun 2026 | Jul 2026-now | Verdict |
|---|---|---|---|---|---|
| V1 longs off when VIX > 25 and the 20-day trend is down | 24 / 1 / 0 trades, those made +$1,911 / +$1,236 / $0 | +$1,265 -> -$646 | $33,901 -> $32,665, 50K eval $33,663 -> $30,575 | unchanged $9,060 | FAIL: skips winners (placebo p 0.65) |
| V2 all LIT off when VIX > 25 and the 20-day trend is down | 49 / 4 / 0, those made +$6,544 / +$3,087 / $0 | +$1,265 -> -$5,698 | $33,901 -> $30,814, eval -$7.5k | unchanged | FAIL (placebo p 0.83) |

## The tables (all spans pooled; per span in results.json)
| Bucket | Trades | Win % | PF | Net $ | Longest run without a $ winner |
|---|---|---|---|---|---|
| VIX < 15 | 143 | 52 | 1.27 | +$8,700 | 7 |
| VIX 15-20 | 303 | 53 | 1.30 | +$16,633 | 6 |
| VIX 20-25 | 116 | 51 | 1.26 | +$5,238 | 6 |
| VIX 25+ | 76 | 67 | 3.07 | +$13,655 | 4 |
| VIX 20-25 + 20-day down | 34 | 41 | 0.52 | -$3,296 | 9 |
| VIX 25+ + 20-day down | 53 | 70 | 3.41 | +$9,631 | 3 |
| down trend, longs | 73 | 52 | 0.73 | -$2,784 | 5 |
| down trend, shorts | 56 | 57 | 1.40 | +$3,353 | 5 |
| up trend, longs | 90 | 59 | 2.19 | +$17,925 | 3 |

One thing to WATCH, not a rule: **VIX 20-25 with a 20-day downtrend** is LIT's weakest corner in 2021-25 (28 trades, PF 0.01,
-$6,208), but in Jan-Jun 2026 it made +$2,884 (5 trades, PF 5.9) and Jul-Oct has 1 trade. It flips sign between spans, so the
CLAUDE.md bar says no. Also: longs in a 20-day downtrend lost in 2021-25 (PF 0.55) and Jul-Oct (PF 1.5, +$494, n6) but won in Jan-Jun.
Already tested nearby: the setup-grade warnings (daily trend vs SMA20 against, VIX >= 25 or +20%) in TESTED_AND_REJECTED.

## ATLAS funded at 1 micro on Nov 20 (livegap cause #2): BY DESIGN
From the code: `engine/account_b.funded_qty` -> `engine/sizing.funded_qty` with the MFFU Builder 25K funded preset
(`engine/multi_account`, mode funded): pct 0.6 of the room ($1,000 -> $600), ref 20 pts, **max_win $1,000** ("a winner <= $1,000",
owner-approved funded sizing 2026-10-25, `research/writeups/uprisk.md`), skip_breach. Nov 20 EMA short: stop 38.75 pts, target
258 pts = $516 a micro, so 2 micros ($1,032) would break the $1,000 best-day cap -> **1 micro**. Replayed today:
`60% of $887 room -> $532`, `best day <= $1,000 -> 1`. It is NOT the payfirst plan (`ATLAS_FIRST_AT_MIN`, night-payfirst
2026-11-23: that only changes WHEN the first payout is asked, never the size). Cost vs 2 micros on this trade: ~$516.
The livegap -$631 estimate used the median live risk; the real "what if" (2 micros) is -$516, and the cap is a consistency /
best-day guard the owner chose.
