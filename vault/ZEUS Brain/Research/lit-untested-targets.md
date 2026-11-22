---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "one small adopt-candidate (take the profit at 12:00 ET when the trade is at least +0.5R); everything else rejected"
source: "research/writeups/lit-untested-targets.md"
aliases:
  - "LIT untested target and exit ideas"
---

# LIT untested target and exit ideas

> [!success] Verdict: adopt-candidate
> one small adopt-candidate (take the profit at 12:00 ET when the trade is at least +0.5R); everything else rejected

**Full title:** LIT untested target and exit ideas - HTF FVG / order block targets, news and midday exits, reverse-inducement exits, a daily profit stop, other bank levels

## Summary

58 variants of the live LIT trade were tested on CME NQ1! futures (5m + true 1m bars, 2026), each picked on Jan-Jun and checked on Jul-Oct, with the live eval sizing ($800 up to a 25-pt stop, 60% room cap). Same setups, same entries, same stops; only the target or the exit changes. Higher-timeframe targets (the nearest unfilled 1H/4H fair value gap or order block) lose money in both halves, alone or next to the VIX band. Taking profit before 08:30 news, leaving when the reverse trade's inducement gets taken, a second trade a day with a daily profit stop, banking at 6R/10R/never, a VIX band x 0.8/1.2 and front-running the band are all rejected. One idea helps both halves a little - take the profit at 12:00 ET (the end of the New York morning) when the trade is at least +0.5R, else let it run: H1 +$915 (PF 4.01 to 4.09), H2 +$1,132 (PF 2.51 to 2.68), 2021-25 reference +$13.6k, same 2.6-3.1 trades a week, 2-week eval pass H1 37.5% to 39.8%. It touches only 7 trades of 2026, so it is a small, thin edge. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-experiments|LIT experiments]], [[lit-report-coverage|LIT report coverage]]
- Runs: `lit_u_targets_base, lit_u_targets_tx_1200_0p5R, lit_u_targets_tx_1130_0p5R, lit_u_targets_tx_1145_0p5R, lit_u_targets_htf_fvg4h_nearer, lit_u_targets_htf_ob4h_else_vix, lit_u_targets_tx_news0830_l5_1R, lit_u_targets_oi_idm_1R, lit_u_targets_oi_rev_1R, lit_u_targets_mpd2_pstop800, lit_u_targets_bank_`
- Source: `research/writeups/lit-untested-targets.md`
- Back to [[ZEUS Home]]
