---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "rejected"
source: "research/writeups/lit-entry-precision.md"
aliases:
  - "LIT entry precision"
---

# LIT entry precision

> [!failure] Verdict: rejected
> rejected

**Full title:** LIT entry precision - can the entry be "on the dot"? Direct limit vs confirmation vs refined limit, per original setup

## Summary

The owner asked for entries that are on the dot. 43 entry variants were run on the exact live LIT setups of 2026 (true 1m bars, costs in), picked on Jan-Jun and checked on Jul-Oct, scored in $ on the LIT rule and on the MFFU 50K 2-week pass rate under the live two_week sizing. Following the owner's advanced report (ch.5 / ch.13 experiment 1), every entry rule was also compared per original setup, with a missed fill counted as $0, at one common $1,000 budget. Today's entry (tap of the 5m CISD level, then the first 1m CISD, buy the next 1m open) is still the best. No variant is better in both halves. A plain resting limit at the zone fills 3 setups in 4 instead of 1 in 2 and gets a better price on the trades both take, but the extra fills are the setups that never confirm, and they lose (H1 -$28.9k at $1,000 a setup). Every refined limit misses the runaways; every later or slower confirmation (1m BOS, 2m/3m CISD, close back above the zone) gives up more than it saves. The closest miss, a limit at the CISD candle close for 1 minute then market, is +$1.3k in H1 and -$0.2k in H2 (2-week pass 52.9 / 49.3 vs 52.9 / 50.7). Nothing to implement. Paper only.

## Money first

- **Keep today's entry.** It is the best of 43 in the pick half, and no variant beats it in both halves.
- Under the report's paired, per-setup comparison:
  - the confirmation step earns its missed fills: the setups it skips lose money;
  - refinement does not pay for its misses.
- No engine option was added: the task's rule is to implement only what passes H1 and H2. `engine/lit.py`,
  `live_model.json` and the live loop are unchanged.
- **Where "on the dot" can still be gained: execution, not rules.** `lit-live-fills.md` found that the PC bot buys about
  95 s late, ±7.5 pts. That costs more eval odds (pass rate 85% → 71%) than any rule here could add. The fix is to decide
  on the CISD bar's close and poll 2 s after each minute. That is the real "on the dot" work.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-1m-management|LIT on the 1-minute chart]], [[lit-experiments|LIT experiments]], [[lit-live-fills|LIT live fills]], [[lit-report-tests|LIT report tests]], [[lit-tight-stops-size|LIT tight stops and bigger size]], [[lit-trade-selection|LIT trade selection]], [[lit-untested-entries|LIT untested entry ideas]]
- Runs: `lit_ep_live, lit_ep_direct, lit_ep_bos1m, lit_ep_reclaim, lit_ep_close, lit_ep_lm_close1, lit_ep_lm_fvg3, lit_ep_zone_mid, lit_ep_tol16, lit_ep_two_step, lit_ep_runaway05, lit_ep_cisd3m`
- Source: `research/writeups/lit-entry-precision.md`
- Back to [[ZEUS Home]]
