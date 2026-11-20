---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
type: "research"
date: "2026-10-26"
status: "adopt-candidate (small; owner decides) - keep the two_week eval sizing after session 10 instead of switching to safe_eval"
source: "research/writeups/eval-cost.md"
aliases:
  - "Cheaper evals"
---

# Cheaper evals

> [!success] Verdict: adopt-candidate
> adopt-candidate (small; owner decides) - keep the two_week eval sizing after session 10 instead of switching to safe_eval

**Full title:** Cheaper evals - which eval sizing buys a funded account cheapest and fastest at the owner's real prices

## Summary

Owner order 2026-10-26, item 3 - the eval-sizing trade-off between pass speed and fail rate when many evals are bought, priced at the owner's prices (MFFU Builder 25K $63 / $43, Builder 50K $91.80, LucidPro 50K $115-134, FundedNext 50K $159-170). 13 LIT eval sizings, each eval bought again at once after a fail (MC 1,000 paths, 2026 H1 / H2 and 2021-25). The fee is small next to time - a funded 50K is worth about $40 a session - so the cheapest sizing per funded account (room 40-55%) is the slowest and pays least. One change holds in H1, H2 and 2021-25, on the 50K and the 25K and at every price - keep the two_week sizing after session 10 instead of dropping to safe_eval (two_week_until 999, no reset). Exact MFFU slot money, 6 months, net of every eval - 50K $837 / $818 / +$7 a month vs $823 / $798 / -$7 today (H1 / H2 / 2021-25); 25K at $63 $383 / $352 / -$9 vs $375 / $331 / -$15. Funded within 20 sessions H2 85% vs 78%, 2021-25 40% vs 34%; evals per funded 50K in 2021-25 2.77 vs 3.25 ($254 vs $298). The 2-week pass/fail is unchanged (52.9 / 17.8, 58.6 / 20.9), slow passes fall (H2 13.8% -> 8.8%), fails within 20 sessions rise 3-4 points. Resets (a new eval at session 10 / 15 / 20) are no better and lose in 2021-25 - keep "no reset". Paper only; nothing live changed.

## Money first

One account slot for 6 months (eval -> 2 sessions of MFFU paperwork -> funded -> payouts -> lost or 5 payouts -> buy again),
$ a month **to you** net of every eval bought. Exact replay (`tools/uprisk.py` life on the live funded sizing: 60% of the room,
<= $1,500 a trade, a winner <= $2,000; 25K at half scale). LIT trades: the 120 live 2026 trades of run `lit_live`, 2021-25 =
its 511 5m-only reference rows.

| Eval sizing (LIT) | 50K at $91.80: H1 | **H2** | 2021-25 | 25K at $63: H1 | **H2** | 2021-25 | 25K at $43: H2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Today** (two_week, room 80%, no weekly stop, safe_eval after session 10, no reset) | $823 | **$798** | -$7 | $375 | **$331** | -$15 | $336 |
| **Keep two_week after session 10** (`two_week_until` 999) | **$837** | **$818** | **+$7** | **$383** | **$352** | **-$9** | **$357** |
| ... with room 90% | $840 | $822 | +$7 | $389 | $355 | -$8 | $361 |
| ... with room 70% | $831 | $807 | +$4 | $377 | $344 | -$11 | $349 |
| Room 70% (safe_eval after 10) | $818 | $789 | -$7 | $369 | $322 | -$15 | $327 |
| Buy a new eval at session 10 (room 80%) | $828 | $813 | -$27 | $382 | $351 | -$29 | $358 |
| Buy a new eval at session 15 | $825 | $806 | -$23 | $380 | $344 | -$24 | $350 |
| Room 40% (cheapest per funded account in 2026) | $792 | $747 | -$15 | $365 | $308 | -$18 | $312 |

- **Keep the two_week sizing after session 10: +$14 / +$20 / +$14 a month per 50K slot, +$8 / +$21 / +$6 per 25K slot.** It is
  better in all three spans on both plans, so it passes the "2026 AND 2021-25" rule. Across the owner's 7 accounts (1 x 50K +
  2 x 25K + 4 x 50K-type) that is about **+$110-130 a month** in 2026 and keeps the 2021-25 fee drain smaller.
- The money is small because an eval is cheap next to a funded account. **Speed is what pays:** a funded 50K pays about
  $915 a month (H2), about $40 for every session it is funded earlier. A whole extra eval costs $43-$170.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-26]]
- Refers to: [[lit-funded-combo|LIT funded accounts on the new live LIT]], [[prop-codes-2026-10|Prop-firm discount codes, October 2026]], [[uprisk|Uprisk]]
- Source: `research/writeups/eval-cost.md`
- Back to [[ZEUS Home]]
