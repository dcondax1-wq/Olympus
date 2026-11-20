---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "adopt-candidate"
source: "research/writeups/lit-losses.md"
aliases:
  - "LIT losses"
---

# LIT losses

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** LIT losses - where and why LIT loses in 2026, and the rules worth adding

## Summary

Every 2026 trade of LIT final was taken apart (time, level, sweep, inducement, stop, MFE, news, VIX, ES, opens, 1H/4H). 59 stop-outs carry 97% of the lost dollars. They are trades that never worked (median best point +0.3R, 45 minutes to the stop), not shake-outs. About 110 rules were tested, each picked on Jan-Jun and checked on Jul-Oct, plus timeframes and the masters-study filters. Two rules help both halves and the eval: a weekly stop (after 2 stop-outs in a week, half size for the rest of it) and a Monday rule (once Monday has taken Friday's high, only shorts; once it has taken Friday's low, only longs). Together (lit_loss_pack): 2026 +$41.7k, PF 3.66, max DD -$2.3k, eval pass rate 95.5% (was 80%), H1 +$2.1k and H2 +$0.75k better than LIT final. Every exit-management idea (scale-outs, trails, stop to the inducement) and every other timeframe lost money in both halves.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `lit_live, lit_loss_pack, lit_loss_weekly_stop, lit_loss_monday, lit_loss_after_win, lit_loss_pack_win, lit_loss_idm12, lit_final`
- Source: `research/writeups/lit-losses.md`
- Back to [[ZEUS Home]]
