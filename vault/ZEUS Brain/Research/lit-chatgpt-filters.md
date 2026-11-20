---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-24"
status: "rejected"
source: "research/writeups/lit-chatgpt-filters.md"
aliases:
  - "ChatGPT's 20 LIT filters and the VXN / VIX9D target band"
---

# ChatGPT's 20 LIT filters and the VXN / VIX9D target band

> [!failure] Verdict: rejected
> rejected

**Full title:** ChatGPT's 20 LIT filters and the VXN / VIX9D target band - 66 tests, nothing worth switching on

## Summary

The owner's ChatGPT dossier (2026-10-24) proposed 20 skip / cancel filters for LIT (L01-L20, each with a primary and two alternative thresholds) and a target band from VXN (V3) or VIX9D (V4) instead of VIX. All 66 versions were run on the live LIT exactly as specified (2026 H1 pick, H2 check, 2021-25 reference, costs in, eval path = live two_week sizing). Nothing is worth adopting. Two versions pass the paper rule, but they are no-ops. L09 P (at most 1 earlier touch of the level) adds $144 in H1 and $0 in H2 by changing 2 trades. L19 A2 (stop at most 4x the sweep's depth) adds $4 by changing 1 trade. A random-skip placebo matches both 28-38% of the time. The best-looking filter, L08 P (sweep within 30 minutes of the inducement), makes +$956 / +$1,100. It drops 4 of the 23 big runners (tail 82.6%), falls to 2.09 trades a week (67% of weeks with 2+), lowers the H2 2-week eval pass from 52.2 to 47.8%, loses $7.4k on 2021-25 when measured on 5m bars, and its 15-minute version loses $8k in H1. Most filters cut the big winners and lose $5k-$35k. Five of them (L04, L05, L13, L14 and in effect L12) almost cannot be met with LIT's 5m displacement and CISD, so they stop nearly every trade. VXN and VIX9D bands move the money by -$3.2k to +$1.2k a half, the same size as plain VIX x0.9 / x1.1 controls. VIX9D x1.1 is +$1,249 in H1 but -$422 in H2. VXN x1.0 is -$753 / +$621. LIT live stays as it is.

## Money first

- **Nothing to switch on.** The two lines that pass the rule change 1-2 trades for $4-$144. The only filter with real money
  in both halves (L08 P, +$2.1k) cuts the big winners and the eval odds, and it reverses on 5 years of 5m data.
- LIT's edge is the far VIX-band runner. Filters that ask for a prettier sweep, a faster reaction or a cleaner approach
  remove those runners about as often as the losers.
- The VXN / VIX9D band is no better than the VIX band. It is noise around the same target. VIX stays.
- Paper only. No engine file and no `live_model*.json` was changed.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-24]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[hq-lit|HQ LIT]], [[lit-adv-continuation|LIT advanced report ch2-4]], [[lit-entry-precision|LIT entry precision]], [[lit-experiments|LIT experiments]], [[lit-report-tests|LIT report tests]]
- Runs: `lit_live, lit_gpt_l01_p, lit_gpt_l01_a1, lit_gpt_l01_a2, lit_gpt_l02_p, lit_gpt_l02_a1, lit_gpt_l02_a2, lit_gpt_l03_p, lit_gpt_l03_a1, lit_gpt_l03_a2, lit_gpt_l04_p, lit_gpt_l04_a1, lit_gpt_l04_a2, lit_gpt_l05_p, lit_gpt_l05_a1, lit_gpt_l05_a2, lit_gpt_l06_p, lit_gpt_l06_a1, lit_gpt_l06_a2, lit_gpt_`
- Source: `research/writeups/lit-chatgpt-filters.md`
- Back to [[ZEUS Home]]
