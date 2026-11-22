---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "adopt-candidate"
source: "research/writeups/lit-funded-sizing.md"
aliases:
  - "LIT funded sizing"
---

# LIT funded sizing

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** LIT funded sizing - how big to trade once the MFFU eval is passed

## Summary

After the MFFU Builder 50K eval passes, the goal changes from speed to payouts without losing the account. The exact live LIT trades of 2026 were replayed on a modelled MFFU funded account (EOD trailing $2,000 locking at +$100, $1,000 soft daily loss, payouts above a $2,100 buffer, $500-$2,000 a request, best day at most 50% of the cycle, 5 sim payouts, 80% split). Keeping today's normal or eval size on a funded account loses 20-22% (Jan-Jun) / 28-29% (Jul-Oct) of accounts within 6 months. The new mode "funded" risks 40% of the room to the floor (at most $800, so a fresh account trades the normal LIT size), sizes so a winner pays at most $1,500 (the 50% best-day payout rule), keeps the weekly stop, and skips a trade when even 1 micro could reach the floor. It loses 1.0% / 1.5% of accounts in 6 months and pays $4,613 / $4,433 in 6 months ($769 / $739 a month) vs $3,423 / $3,020 for normal size ($1.90 commission). The best-day cap is the lever that matters; fixed $ tiers, fractional Kelly and % of the room all sit on the same plateau once it is on. Paper only; live_model.json is unchanged.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-prop-firms|LIT on every prop firm]]
- Runs: `lit_funded_rec, lit_funded_normal, lit_funded_tiers`
- Source: `research/writeups/lit-funded-sizing.md`
- Back to [[ZEUS Home]]
