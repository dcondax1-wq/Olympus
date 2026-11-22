---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - bot/atlas
type: "research"
date: "2026-10-26"
status: "adopt-candidate"
source: "research/writeups/atlas-funded.md"
aliases:
  - "ATLAS's funded account"
---

# ATLAS's funded account

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** ATLAS's funded account - what the 25K pays once its eval passes

## Summary

Once ATLAS's MFFU Builder 25K eval (MFFUEVBLD…6017, $43) passes, the bot can now keep trading ATLAS on the new funded account under the funded rules (one owner-run switch, never automatic). Replayed on ATLAS's real trades under the account-B rules (no hedging against LIT, LIT's armed setups block it), with the live funded sizing (60% of the room, at most $750 a trade, a winner at most $1,000) and MFFU's payout rules, a funded ATLAS 25K pays you about $517 a month on the Jul-Oct check half ($582 Jan-Jun), 0.65 payouts a month, the first payout after a median 24 funded sessions, 0% of accounts lost and 8.5% stuck (under $100 of room) in 6 months. In a 2025 or 2021-24 market it pays only $64 / $39 a month and 89-96% of funded accounts get stuck within 6 months, because ATLAS has almost no edge there. Paper only; nothing is armed.

## Money first

ATLAS on a funded MFFU Builder 25K, 6 months, the live funded rule. "To you" = MFFU's 80% share.

| Funded ATLAS 25K | 2026 H1 Jan-Jun (pick) | **2026 H2 Jul-Oct (check, quote this)** | 2025 (reference) | 2021-24 (reference) |
|---|---:|---:|---:|---:|
| **$ a month to you** | $582 | **$517** | $64 | $39 |
| ... the worst 1 in 10 accounts | $400 | $242 | $0 | $0 |
| Paid to you in 6 months | $3,494 | $3,100 | $382 | $235 |
| Payouts a month | 0.73 | **0.65** | 0.08 | 0.05 |
| Payouts in 6 months | 4.4 | 3.9 | 0.5 | 0.3 |
| First payout (median funded sessions) | 18 | **24** (about 5 weeks) | 21 | 17 |
| Got a payout within 3 months | 92% | 90% | 27% | 19% |
| All 5 sim payouts in 6 months ($4,000 to you, then MFFU moves it to live) | 77% | 51% | 1% | 1% |
| **Accounts lost** (the floor hit) | 0.0% | **0.0%** | 0.0% | 0.0% |
| Accounts stuck (under $100 of room: the bot stops) | 8.2% | **8.5%** | 89% | 96% |
| Trading profit made in the account, a month | $1,575 | $1,416 | $82 | $5 |
| Trades a week | 4.0 | 3.1 | 4.4 | 4.9 |
| Biggest single trade (full stop-out) | $485 | $527 | $558 | $563 |

- **Per eval bought** (the chance it ever passes x 6 months of funded pay, less the eval): $3,178 (Jan-Jun) / **$3,057
  (Jul-Oct)** at this account's $43 price ($3,158 / $3,037 at your usual $63). In 2025 $82, in 2021-24 $27.
- **The real 2026 path** (one funded account from the half's first session, a new one when it ends): Jan-Jun 2 accounts,
  6 payouts, **$4,800 to you ($788 a month)**, the first account got all 5 payouts; Jul-Oct (78 sessions only) 1 account,
  3 payouts, **$2,400 ($646 a month)**. Net of the evals they need: $764 / $632 a month.
- **In a weak year it barely pays.** 2025: 7 funded accounts one after the other, 6 stuck, 2 payouts, $1,600 to you, but
  the 21 evals needed to get those 7 accounts cost about $1,350: **+$20 a month net**. 2021-24: 24 accounts, 23 stuck,
  $5,936 paid, about $5,060 of evals: **+$23 a month net**. Nothing is lost beyond eval fees; there is just almost no
  money in it, because ATLAS's own edge is about zero there (eval path PF 0.82 in 2025, 1.05 in 2021-24).
- **Why "stuck" and not "lost":** the funded size is a share of the room to the floor, so a losing streak makes the trades
  smaller and the account almost never hits the floor. It shrinks until 1 micro no longer fits a stop (room under $100);
  then the bot stops trading it (as a funded Zlarior account already does) and pushes "buy a new eval".
- **The money piles up:** a 2026 account makes about $1,400-1,600 a month of trading profit, but only about $650 a month
  comes out (MFFU's $1,000 request cap, the 50% best-day rule, 2 traded days a cycle); after 6 months about $4,600-5,100 is
  still in the account. The 50% rule holds a payout back on 43-48 of the 126 sessions. That is MFFU's limit, not risk.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-26]]
- Strategies: [[ATLAS]]
- Refers to: [[funded-path|The funded path]], [[lit-funded-sizing|LIT funded sizing]], [[uprisk|Uprisk]]
- Runs: `atlas_funded_live, atlas_funded_old`
- Source: `research/writeups/atlas-funded.md`
- Back to [[ZEUS Home]]
