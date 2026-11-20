---
tags:
  - zeus/research
  - family/product
  - verdict/finding
type: "research"
date: "2026-11-04"
status: "finding - 12-month money roadmap for the three accounts (display only, nothing live changed)"
source: "research/writeups/2026-11-04_money_roadmap.md"
aliases:
  - "Money roadmap"
---

# Money roadmap

> [!info] Verdict: finding
> finding - 12-month money roadmap for the three accounts (display only, nothing live changed)

**Full title:** Money roadmap: the next 12 months (2026-11-04)

## Summary

Research and display only. Nothing live was touched. Numbers: `tools/money_roadmap.py` -> `research/props/roadmap.json` (3,000 sampled 12-month paths per half). Two versions of every number: **Jan-Jun 2026 (H1)** and **Jul-Oct 2026 (H2)**. **H2 is the conservative one: quote H2.**

## Money first

- **Do first:** ATLAS on the 25K first: it is the first cash (typical first payout 2026-12-21 conservative) and pays its price back in month 2. Run all three accounts at once (LIT 50K, ATLAS 25K, BLITZ 25K): buying all three on day 1 beats every staggered order, and the fees are only $198.
- **Then:** LIT on the 50K second: the biggest total ($6,549 in 12 months) but its first payout is later. BLITZ is the weakest of the three ($2,318): a second ATLAS or a LIT copy would earn more in that slot. When an account has been paid its 5th payout (it then moves to a live account), buy the next ATLAS 25K eval ($43) first: a re-buy adds $3,087 (conservative) in the year, against $544 for LIT and $194 for BLITZ.
- **Expected first payout:** First payout from any account: typical 2026-12-16 (conservative, Jul-Oct) to 2026-12-03 (Jan-Jun); 1 in 10 paths already by 2026-11-18 / 2026-11-23, 9 in 10 by 2026-12-31 / 2027-01-27. It comes from ATLAS (typical 2026-12-21 conservative, 2026-12-04 Jan-Jun); LIT on the 50K comes later (typical 2027-02-09 / 2027-01-22).
- **Best case / worst case by month 12:** Cash to the owner by month 12 (2027-11-05), after every fee including the $198 already paid for the three evals: conservative (Jul-Oct) middle path $13,105, worst case (1 path in 10) $9,759, best case (1 in 10) $14,892; Jan-Jun version middle $14,345, worst $11,820, best $15,370. The worst of all 3,000 sampled paths still ends at $3,512 (H2); no path ends below $0.
- **With re-buying:** If the owner buys a new eval each time an account has been paid 5 times: $16,546 middle path conservative ($12,060 worst / $21,063 best), $22,414 Jan-Jun.
- **Why it fades:** The money is front-loaded: each account stops paying after 5 payouts (5 x $1,000 x 80% = $4,000 on a 25K, 5 x $2,000 x 80% = $8,000 on the 50K, then it moves to a live account that this table does not count), so months 8-12 fall off unless a new eval is bought.

## Links

- Family: [[Family product]]
- Day: [[Day 2026-11-04]]
- Source: `research/writeups/2026-11-04_money_roadmap.md`
- Back to [[ZEUS Home]]
