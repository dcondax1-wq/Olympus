---
tags:
  - zeus/research
  - family/money
  - verdict/research
  - bot/zlarior
  - bot/atlas
  - bot/blitz
  - lane/rapid
type: "research"
date: "2026-11-22"
status: "done - paper only, no Decide card (the picked book fails the \"not worse 2021-25\" bar). Nothing live changed."
source: "research/writeups/one-account-book-2026-11-22.md"
aliases:
  - "One account, combined book"
---

# One account, combined book

> [!abstract] Verdict: research
> done - paper only, no Decide card (the picked book fails the "not worse 2021-25" bar). Nothing live changed.

**Full title:** One account, combined book - every mix of Zlarior (LIT) + ATLAS (+ BLITZ) on ONE MFFU account at real fills; the pre-registered best (Rapid EOD 50K, LIT + ATLAS, LIT half size in the eval) beats today's two accounts in both 2026 halves but is worse in 2021-25, so no new card

## Summary

Lane E. Pre-registered (research/onebook/DESIGN.md, committed 12c9f71cc before the scored run). 13 books x 4 MFFU accounts = 52 books + today's setup = 53 counted, on research/plans/rank.py's real-fills engine (ATLAS 10 ticks a side), 1,000 paths x 126 sessions, same paths for every book. Pick on Jan-Jun among books whose eval fail is at most LIT-alone + 2 points - MFFU Rapid EOD 50K ($165), LIT + ATLAS first-come with LIT at half size in the eval - $4,918 / $2,204 / -$88 a month (Jan-Jun / Jul-Oct / 2021-25-like) vs today's two accounts (LIT on the Builder 50K + ATLAS on the Builder 25K) $981 / $857 / -$62. Paired on the same paths - +$23,623 / +$8,086 / -$156 over 6 months (SE $406 / $229 / $32), 2022 alone -$781. Without ATLAS's 5 best Jul-Oct days the Jul-Oct gain is +$114 (SE $136) = about $0. Fails the 2021-25 bar: no card. The gain is the account type (Rapid EOD 50K, already on the open card plan-rapid50k-max2-rebuys), not a new way to mix the bots.

## Links

- Family: [[Family money]]
- Day: [[Day 2026-11-22]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]], [[BLITZ (paper)]], [[Rapid lanes]]
- Runs: `research/onebook/book.py -> results.json; research/onebook/robust.py -> robust.json (labelled post-hoc)`
- Source: `research/writeups/one-account-book-2026-11-22.md`
- Back to [[ZEUS Home]]
