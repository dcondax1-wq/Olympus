---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
type: "research"
date: "2026-10-25"
status: "adopt-candidate"
source: "research/writeups/funded-path.md"
aliases:
  - "The funded path"
---

# The funded path

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** The funded path - from a passed eval to money in the bank

## Summary

Once an MFFU Builder eval passes, the funded account is where the money is. Replayed on the 2026 trades (costs in, $1.90 a micro) through the new sim funded tracker (engine/funded_life.py) and the research funded sizing, a funded Builder 50K trading Zlarior (LIT) pays you about $835 a month on the Jul-Oct check half ($889 Jan-Jun), loses 0% of accounts in 6 months, and its first payout comes after a median 33 funded sessions (about 7 weeks), $1,600 to you. ATLAS on a funded 25K pays $318 / $622 a month but loses 13.6% of accounts in 6 months on Jul-Oct. Zlarior on a second 25K pays $389 / $329. All three together: about $1,540 a month (Jul-Oct) to $1,840 (Jan-Jun) for $217.80 of evals. A consistency-aware size (shrink a day's winner to stay under the 50% rule) was built and tested: it cuts the days the money waits on the 50% rule from 37 to 13 but pays $76 a month less on Jan-Jun, so it stays OFF. Nothing live changed: a passed eval still stops and tells the owner; funded trading starts only with the owner's command.

## Money first

| Funded account (MFFU Builder Sim Funded) | $ a month to you, Jul-Oct (check) | Jan-Jun (picked) | Paid in 6 months, Jul-Oct · Jan-Jun | Account lost in 6 months | First payout (median funded sessions) | Got a payout within 3 months |
|---|---|---|---|---|---|---|
| **Zlarior (LIT) on the Builder 50K** | **$835** | $889 | $5,009 · $5,336 | 0.0% · 0.0% | 33 · 33 | 79% · 83% |
| ATLAS on a Builder 25K | $318 | $622 | $1,911 · $3,735 | 13.6% · 1.8% | 40 · 22 | 65% · 97% |
| Zlarior on a 2nd Builder 25K | $389 | $329 | $2,334 · $1,976 | 0.0% · 0.0% | 34 · 47 | 75% · 66% |
| **All three** | **~$1,540** | ~$1,840 | ~$9,250 · ~$11,050 | | | |

- "To you" = MFFU's 80% share. Monte Carlo: 1,000 funded accounts of 6 months each (126 sessions), drawn in 5-session blocks
  from the half; real CME NQ1! / MNQ trades of 2026 (Zlarior: the 120 trades of run `lit_live`; ATLAS: the 175 trades of the
  $500 book), $1.90 a micro round trip, 1 tick of slippage on market entries and stop exits.
- The worst 10% of Zlarior 50K accounts still paid $1,551 (Jul-Oct) / $2,829 (Jan-Jun) in 6 months. Max risk on one trade:
  $422-440 (50K), $323-335 (ATLAS 25K), $189-211 (Zlarior 25K).
- **Real 2026 path (one account from the half's first session):** Zlarior 50K Jan-Jun: 5 payouts, $8,000 to you, first at
  session 22 (graduated to live). Jul-Oct (78 sessions only): 1 payout, $1,600, at session 67: the slow case. ATLAS 25K
  Jan-Jun 5 payouts / $3,930; Jul-Oct 1 / $800.
- **Days to the first payout:** a median 33 funded sessions (Zlarior 50K), i.e. about 7 weeks after the funded start; with
  the eval's own median of 5-7 sessions to pass and a few days of MFFU paperwork, the first money lands about **2 months
  after the eval starts**.
- **Consistency blocks:** on a typical 6-month Zlarior 50K account, the money is above the payout line but the 50% best-day
  rule holds it for 37 (Jan-Jun) / 38 (Jul-Oct) sessions in total (94% / 89% of accounts hit it at least once). It is not a
  breach: the account just trades more days. The tracker says how many ("consistency: best day is 81% of the cycle, trade 3
  more days").
- **2021-25 (reference only):** Zlarior's 2021-25 line is PF ~1.0 on 5m entries; lit-funded-sizing.md showed no sizing makes it
  pay there (the recommended funded rule shrinks with the room instead of dying: 2 of 3 back-to-back accounts lost in 5 years).
  These numbers are 2026 numbers.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-25]]
- Refers to: [[lit-funded-firms|LIT on 3 funded accounts]], [[lit-funded-sizing|LIT funded sizing]], [[lit-money-batch2|LIT money batch 2]]
- Runs: `funded_path_lit50_rec, funded_path_lit50_cons, funded_path_lit50_cons2, funded_path_atlas25_rec, funded_path_atlas25_cons, funded_path_atlas25_cons2, funded_path_lit25_rec, funded_path_lit25_cons`
- Source: `research/writeups/funded-path.md`
- Back to [[ZEUS Home]]
