---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
  - bot/blitz
type: "research"
date: "2026-11-18"
status: "rejected (no change) - 0 of 8 pre-declared exit ideas pass; BLITZ stays a hidden paper shadow; no Decide proposal"
source: "research/writeups/blitz-review-2026-11-18.md"
aliases:
  - "BLITZ review"
---

# BLITZ review

> [!failure] Verdict: rejected
> rejected (no change) - 0 of 8 pre-declared exit ideas pass; BLITZ stays a hidden paper shadow; no Decide proposal

**Full title:** BLITZ review (2026-11-18 night) - today's rule measured honestly, why its trades win and lose, 8 new exit ideas (0 pass); verdict - keep it on paper, no account of its own; its only paying use is next to Zlarior on a funded account

## Summary

Owner - "I expect all of our strategies to be better", "high win rate / profit". Today's BLITZ (engine/blitz.py v2 as account C, never opposite Zlarior / ATLAS), $150 a trade, $1.90 a micro + 1 tick each way - 2026 Jan-Jun 8.5 trades a week, win 56.7%, PF 1.70, +$963 a month, max DD -$1,152; Jul-Oct 6.8 a week, 56.6%, PF 1.62, +$667, -$815; 2021-25 (5m) 8.6 a week, 50.1%, PF 1.05, +$73, -$5,512 (2024 -$200 a month). One more tick each way - $921 / $635 / $18 a month. Own 25K eval at the live size - 2-week pass / fail 47.9 / 23.5, 36.2 / 21.7, 24.7 / 48.4; the whole 25K slot +$286 / +$52 / -$39 a month. Why - the 30-minute clock exits are the whole profit (70% winners, +0.42R), stop-outs give it back (-0.96R); a trade not at +0.5R by minute 10 ends near 0R in 2026 (-0.06R / -0.02R) and -0.18R in 2021-25, one at +0.5R makes +0.5-0.7R; later band breaks beat first breaks in all 3 spans; no check time, side or VIX band is bad in all 3. Tested (written before the run) - minute-10 / 15 no-follow-through cuts, back-inside-the-band exits, breakeven at +0.5R, cut + 45-minute hold: 0 of 8 pass (the H1 pick, out at minute 10 if never +0.25R, +$22 H1 but -$292 a month Jul-Oct, eval 2-week fails 21.7 -> 40.6%); every idea LOWERS the win rate (35-53% vs 57%). Verdict - stay paper; MFFU's Builder 25K slots are both taken (ATLAS funded + Zlarior 25K #2) and its own 25K pays ~$0 outside Jan-Jun anyway; revisit as an add-on on Zlarior's funded 50K once it is funded.

## Money first

- **Not on its own account.** MFFU's limits (STATE.md) allow Builder 1 x 50K + 2 x 25K funded; the 2 x 25K are ATLAS's funded 25K and Zlarior's
  25K #2. Even with a free slot, its own 25K pays +$286 / +$52 / -$39 a month (Jan-Jun / Jul-Oct / 2021-25) and in Jul-Oct
  random directions on the same signals made about the same slot money (blitz-25k.md): an eval lottery, not an edge.
  BLITZ alone on a Rapid EOD 50K at $300 a trade almost never reaches the $3,000 target (0.1% pass in 60 sessions,
  rule-native-2026-11-17.md).
- **As an add-on next to Zlarior on a funded account: the one paying use, later.** On Zlarior's funded Builder 50K, BLITZ
  only while Zlarior is flat added +$301 / +$290 a month in 2026 and +$16 in 2021-25 (scalp-na-mffu.md); on the Rapid EOD
  (at most 3 a day, $300) +$822 / +$313 but 2021-25 evals fail twice as often (paper lead, rule-native-2026-11-17.md). Both
  need Zlarior's account funded first and engine work (a second strategy on Zlarior's account, up to 6 a day, Zlarior first).
  MFFU's Rapid funded news ban (2 minutes around Tier-1 news) would also block BLITZ's 14:00 check on FOMC days.
- **Not retired either.** Its 2026 edge is real (random directions lose, blitz-25k.md p 0.02-0.05) and it costs nothing on
  paper. It is a 2026-regime bet: one more tick of slippage takes 2021-25 to +$18 a month, and 2024 lost money.
- **So: stay hidden on paper.** No Decide card proposal (nothing passed).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-18]]
- Strategies: [[Zlarior (LIT)]], [[BLITZ (paper)]]
- Refers to: [[blitz-25k|BLITZ on its own MFFU Builder 25K]], [[rule-native-2026-11-17|Rule-native search]], [[scalp-na-mffu|BLITZ]], [[win-loss-anatomy-2026-11-18|Why we win, why we lose]]
- Runs: `none (research/scalp/blitz_review.json, blitz_review_tf1.json, blitz_review_tf5.json); tools/blitz_review.py; ZEUS Lab ids blitz_chk10_loss ... blitz_band_in10_h45 (kind blitz_idea, Rejected)`
- Source: `research/writeups/blitz-review-2026-11-18.md`
- Back to [[ZEUS Home]]
