---
tags:
  - zeus/research
  - family/sessions
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "rejected"
source: "research/writeups/lit-all-hours.md"
aliases:
  - "LIT all hours"
---

# LIT all hours

> [!failure] Verdict: rejected
> rejected

**Full title:** LIT all hours - trading the whole CME day (Asia, 15:30-16:00, more trades a day, re-arming, the 18:00 F-BoS, trendline liquidity)

## Summary

The owner asked for LIT to look for trades all the time (CME NQ trades 18:00-17:00 ET). 30 variants on the exact live LIT (1m entries, live stops and targets, two_week eval sizing, costs in), picked on Jan-Jun 2026 and checked on Jul-Oct. Nothing passes both halves. Adding the Asia session (18:00-02:00) to the one daily slot gives more money in Jul-Oct but less in Jan-Jun (-$5.5k) and fewer 2-week eval passes in Jan-Jun; Asia setups on their own lose money in Jan-Jun (PF 0.82). Two trades a day, one per session and re-arming after a target or breakeven all trade more (3.4-5.6 a week) and make more in Jul-Oct, but every one loses money or 2-week passes in Jan-Jun and most raise the eval fail rate. The 15:30-16:00 extension changes nothing (2 trades). The owner's F-BoS idea (a false break of the 16:30-17:00 build-up at the 18:00 open) is the closest: +$107 in Jan-Jun, +$4.8k in Jul-Oct, Jul-Oct 2-week passes 50.7% -> 66.7%, but Jan-Jun passes stay 52.9% with fails 8.4% -> 13.4%, and its 16 trades in 2026 have 3 winners (none in Jan-Jun; one +$3.6k trade carries Jul-Oct). Trendline/channel liquidity as an extra level is worse in both halves. The live LIT (02:00-15:30, 1 trade a day) stays. Paper only.

## Links

- Family: [[Family sessions]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `lit_hours_base, lit_hours_full, lit_hours_asia_only, lit_hours_late, lit_hours_2day_sal, lit_hours_rearm, lit_hours_full_1sess, lit_hours_full_rearm_sal, lit_hours_fbos, lit_hours_fbos_cycle, lit_hours_ts`
- Source: `research/writeups/lit-all-hours.md`
- Back to [[ZEUS Home]]
