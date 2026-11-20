---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
type: "research"
date: "2026-10-26"
status: "adopt-candidate (pre-buy the replacement eval at an account's 4th payout; owner decides, check MFFU first) - ask line, stack reserve and cons_aware rejected"
source: "research/writeups/payout-policy.md"
aliases:
  - "Funded-phase money from the payout rules"
---

# Funded-phase money from the payout rules

> [!success] Verdict: adopt-candidate
> adopt-candidate (pre-buy the replacement eval at an account's 4th payout; owner decides, check MFFU first) - ask line, stack reserve and cons_aware rejected

**Full title:** Funded-phase money from the payout rules - ask line, consistency-aware size, a stack payout reserve and pre-buying the next eval

## Summary

Owner order 2026-10-26, item 2 - more funded money from the MFFU / LucidPro / FundedNext payout mechanics without changing a trade. Played on the owner's copied stack (MFFU Builder 50K + 2 x 25K + 4 x 50K-type accounts, all LIT, live eval + funded sizing, a week apart, 12 months on the same market path, net of every eval; MC 1,000 paths, 5- and 21-session blocks). One mechanic pays - buy the replacement eval when an account takes its 4th payout instead of after its 5th (MFFU / LucidPro / FundedNext all end an account after 5), so the next funded account is ready when the old one leaves - +$232 a month on the stack in both 2026 halves (5-session blocks; +$188 to +$270 with 21-session blocks), +$40 a month for a single 50K, the same in 2021-25 (accounts rarely reach 4 payouts there), for about 2 more evals a year. Rejected - the ask line ($1,000 or $2,000 above the buffer instead of $1,500: -$36 to +$9 a month), cons_aware on the live funded sizing (-$566 / -$223 a month H1 / H2, more dry months), and a stack payout reserve (at most 2-4 payouts a month across the accounts so a ready account waits for an empty month - dry spells fall from 20% to 7-11% but $440-2,800 a month less is paid out within 12 months). Paper only; nothing live changed.

## Money first

The owner's stack, 12 months, $ a month **to you** net of every eval bought (failed / lost / finished accounts bought again at
once). "3 dry months" = the whole stack pays $0 three calendar months in a row somewhere in months 4-12; "$0 months" = the share
of months 4-12 with no payout from any account. 5-session blocks (as tools/uprisk.py); 21-session blocks in brackets.

| Payout rule (stack of 7, all LIT) | H1 | **H2** | 2021-25 | H2: 3 dry months | H2: $0 months | Evals bought in 12 mo (H2) |
|---|---:|---:|---:|---:|---:|---:|
| **Today** (ask at $1,500 above the buffer, the max request, as soon as MFFU allows) | $5,016 ($5,210) | **$4,772** ($4,171) | $60 ($119) | 20.3% (13.0%) | 29.8% (25.7%) | 18.4 |
| **Pre-buy the next eval at the 4th payout** | **$5,248** ($5,480) | **$5,004** ($4,359) | $60 ($119) | 19.7% (13.0%) | 29.1% (25.0%) | 20.2 |
| Pre-buy at the 3rd payout | $5,280 ($5,529) | $5,024 ($4,377) | $58 ($116) | 19.4% (13.1%) | 29.0% (25.0%) | 21.8 |
| Ask only full $2,000 requests | $4,980 ($5,176) | $4,741 ($4,145) | $52 ($107) | 19.8% (12.8%) | 29.6% (25.8%) | 18.2 |
| Ask at $1,000 above the buffer | $5,025 ($5,217) | $4,760 ($4,155) | $63 ($119) | 20.3% (13.7%) | 30.0% (25.9%) | 18.5 |
| Stack reserve: at most 4 payouts a month | $3,836 ($4,068) | $3,803 ($3,734) | $54 ($110) | 10.9% (7.5%) | 15.5% (13.2%) | 16.4 |
| Stack reserve: at most 3 a month | $3,222 ($3,384) | $3,209 ($3,246) | $49 ($103) | 8.7% (5.8%) | 11.3% (9.3%) | 14.5 |
| Stack reserve: at most 2 a month | $2,340 ($2,410) | $2,340 ($2,387) | $35 ($83) | 6.8% (4.1%) | 8.1% (6.4%) | 12.0 |
| cons_aware funded size (true or "after_payout": identical) | $4,450 ($4,631) | $4,549 ($3,838) | $64 ($110) | 23.3% (15.8%) | 32.2% (27.5%) | 17.9 |

One MFFU Builder 50K slot alone, 12 months: today $859 / $812 / $13 a month (H1 / H2 / 2021-25); **pre-buy at the 4th
payout $899 / $853 / $13 (+$40 / +$41 / $0)**; full $2,000 requests $852 / $808 / $12; $1,000 line $862 / $811 / $14.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-26]]
- Refers to: [[diversifier-search|A strategy uncorrelated with LIT]], [[eval-cost|Cheaper evals]], [[funded-path|The funded path]], [[lit-funded-combo|LIT funded accounts on the new live LIT]], [[lit-funded-firms|LIT on 3 funded accounts]], [[uprisk|Uprisk]]
- Source: `research/writeups/payout-policy.md`
- Back to [[ZEUS Home]]
