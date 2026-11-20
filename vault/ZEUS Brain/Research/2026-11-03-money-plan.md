---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - bot/zlarior
  - bot/blitz
type: "research"
date: "2026-11-03"
status: "adopt-candidate (owner decides; needs MFFU's written OK on copying between your own accounts) - a Zlarior copy on the third MFFU slot (the free Builder 25K) pays $334 / $269 / -$7 a month (fleet ..."
source: "research/writeups/2026-11-03-money-plan.md"
aliases:
  - "The money plan on today's settings"
---

# The money plan on today's settings

> [!success] Verdict: adopt-candidate
> adopt-candidate (owner decides; needs MFFU's written OK on copying between your own accounts) - a Zlarior copy on the third MFFU slot (the free Builder 25K) pays $334 / $269 / -$7 a month (fleet preset, today's code) or $375 / $331 / -$15 (the 50K's room 0.8, needs a small fleet option) vs BLITZ on that 25K $286 / $52 / -$39 (H1 / H2 / 2021-25)

**Full title:** The money plan on today's settings (2026-11-03 night) - put Zlarior on the free MFFU 25K instead of BLITZ (+$217-279 a month H2), then add LIT 50K copies at other firms (~$790 a month each); about $3,900 a month with 6 accounts in a Jul-Oct-2026 market

## Summary

Owner 2026-11-02 "overall the amount of money we will make". MFFU lets one person hold 1 funded Builder 50K and 2 funded Builder 25Ks. Today - Zlarior (LIT) on the 50K, ATLAS on one 25K, the other 25K (BLITZ's) off. Every slot was priced the same way - 6 months of eval -> 2 sessions of paperwork -> funded -> MFFU payouts -> the next eval, net of every eval, 1,000 Monte Carlo paths of the real sessions, live eval and funded sizing, $1.90 a micro. Per month (H1 Jan-Jun 2026 / H2 Jul-Oct 2026 / 2021-25 reference) - LIT 50K $823 / $798 / -$7; ATLAS 25K $568 / $382 / -$2; LIT 25K $375 / $331 / -$15 (room 0.8) or $334 / $269 / -$7 (the fleet's 25K preset, 50% room); BLITZ 25K $286 / $52 / -$39. So the free 25K earns most as a Zlarior copy - better than BLITZ in all three spans. The three bots' daily results are uncorrelated (LIT-ATLAS -0.01 / -0.03 / +0.11), while Zlarior copies move together (0.8-0.9). Beyond MFFU every extra LIT 50K-type account adds about $790 a month in a 2026-like market and costs about $25 a month (its evals) in a 2021-25-like one. The plan - MFFU 50K (LIT) + 25K (ATLAS) + 25K (LIT), then LIT 50K copies at LucidPro / FundedNext up to 6 accounts (the $3,000 at-once risk cap of scale-plan.md) - about $3,900 a month on Jul-Oct trades, $4,200 on Jan-Jun, and about -$100 a month of eval fees in a 2021-25 market. Paper only; nothing live changed.

## Money first

| Account slot (6 months, net of every eval) | $ a month H1 / H2 / 2021-25 | 2-week pass / fail H1 / H2 / 2021-25 | evals bought per 6 months (H2) | $ to you per eval bought (H2, 6 months) |
|---|---|---|---|---|
| Zlarior (LIT) MFFU 50K, live | **$823 / $798 / -$7** | 52.9/17.8, 58.6/20.9, 20.7/24.9 | 1.67 | ~$2,870 |
| ATLAS MFFU 25K, live (atx_funded_day.json "today") | $568 / $382 / -$2 | 65.5/0.8 (H1) | 1.44 | ~$1,590 |
| **Zlarior MFFU 25K, room 0.8 (the 50K's rule at half scale)** | **$375 / $331 / -$15** | 55.0/10.6, 57.8/17.3, 20.0/23.2 | 1.57 | ~$1,270 |
| Zlarior MFFU 25K, the fleet's 25K preset (50% room) | $334 / $269 / -$7 | 53.0/0.9, 50.6/0.8, 15.1/1.3 | 1.14 | ~$1,420 |
| BLITZ MFFU 25K (adopted later-break pick) | $286 / $52 / -$39 | 47.9/23.5, 36.2/21.7, 24.7/48.4 | - | - |
| Zlarior copy on a LucidPro / FundedNext 50K (MFFU 50K rules as the proxy, $130 an eval) | $812 / $788 / -$25 | as the 50K | 1.67 | ~$2,830 |

The 25K at $43 (the discount of 2026-10-26) instead of $63 adds $5-9 a month.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-03]]
- Strategies: [[Zlarior (LIT)]], [[BLITZ (paper)]]
- Refers to: [[lit-builder-25k|MFFU Builder 25K next to the 50K]], [[lit-funded-combo|LIT funded accounts on the new live LIT]], [[scale-plan|The scaling plan]], [[scalp-na-mffu|BLITZ]]
- Runs: `rd_lit25k_preset_eval, rd_lit25k_rf80_eval`
- Source: `research/writeups/2026-11-03-money-plan.md`
- Back to [[ZEUS Home]]
