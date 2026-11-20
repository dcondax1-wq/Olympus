---
tags:
  - zeus/research
  - family/other
  - verdict/info
type: "research"
date: "2026-10-18"
status: "info"
source: "research/writeups/mffu-rules.md"
aliases:
  - "MFFU rulebook"
---

# MFFU rulebook

> [!note] Verdict: info
> info

**Full title:** MFFU rulebook (Builder 50K / 25K) and does the bot follow it

## Summary

Every MyFundedFutures Builder rule that matters for the bot, from MFFU's own help center (searched 2026-10-18), and a check of the bot against each one (tests/test_mffu_rules.py, 43 ok, 0 fail, 5 warnings). The bot breaks no rule. Five gaps to fix. (1) MFFU charges $1.90 per micro round trip, not the $1.40 the backtests use: about -$310 to -$350 a year. (2) The 7-day inactivity rule: LIT went 7+ days without a trade 3 times in 2026, and nothing warns you. (3) If MFFU wants 2 trading days to pass, the bot stops trading once the target is hit, so you must place one small trade the next day yourself. (4) After a pass, switch the sizing to funded by hand. (5) A full stop-out can reach $1,008 against the $1,000 soft daily loss. That is a pause, not a fail.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Runs: `lit_live, lit_2wk_rec`
- Source: `research/writeups/mffu-rules.md`
- Back to [[ZEUS Home]]
