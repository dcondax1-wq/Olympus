---
title: ATLAS's funded Builder 25K - ATLAS alone vs LIT + ATLAS $250 on the same account
family: risk
date: 2026-11-17
status: candidate (owner decides; built OFF in engine/lit25.py) - faster first payout and a little more $ in both 2026 halves, but more 6-month no-payout paths in both halves and slightly worse in 2021-25.
summary: ATLAS's 25K eval passed (balance $26,946.10 on 2026-11-17, target $26,500). Funded 25K (MFFU Builder 25K funded rules = engine/funded_life builder25k - $1,000 EOD trailing, payouts above the $1,100 buffer, $250 min / $1,000 max, 80%, 50% consistency, 2 days a cycle, 5 payouts), a fresh funded start, 600 Monte Carlo paths of 126 sessions per half (builder_levers seeds), costs in, the live one-account rule (ATLAS skipped while LIT holds either side; LIT entering closes ATLAS at market, 1 tick: 38 skips + 84 cuts over 2021-26). First payout ask (median sessions) ATLAS alone 18 / 26 (H1 / H2) vs LIT + ATLAS $250 14 / 18; to the owner $592 / $497 vs $599 / $529 a month; no payout in 6 months 5.0 / 5.5% vs 7.5 / 12.2%; lost 0% everywhere. 2021-25 - $48 vs $35 a month, 78 vs 82% no payout. Reference - both at the 25K funded preset 13 / 14 sessions, $628 / $568, no payout 4.2 / 10.5%.
runs: none (research/lab/builder_funded25.json, tools/money/funded25.py)
---

## For the owner

| Funded 25K, 6 months | 1st payout ask (sessions) | No payout in 6 m | $ a month to you | Trades/week, PF at $250, max DD |
|---|---|---|---|---|
| ATLAS alone (today) | 18 / **26** | 5.0% / **5.5%** | $592 / **$497** | 4.1 / 3.0 a week, PF 2.92 / 2.55, -$1,062 / -$876 |
| LIT + ATLAS $250 | 14 / **18** | 7.5% / **12.2%** | $599 / **$529** | 6.9 / 5.5 a week, PF 3.07 / 2.64, -$1,108 / -$1,202 |
| (ref) LIT + ATLAS, both at the preset | 13 / **14** | 4.2% / **10.5%** | $628 / **$568** | same trades |
| 2021-25, alone vs $250 | 17 vs 20 | 78% vs 82% | $48 vs $35 | PF 1.08 vs 1.02 |

Jan-Jun 2026 / **Jul-Oct 2026**. The $ hardly moves because ATLAS alone already reaches 4-5 of the 5 payouts in 6 months;
LIT mostly buys speed. More no-payout paths: one big LIT winner can make one day more than 50% of a cycle's profit (the
consistency rule holds the payout). Eval speed: not applicable (the eval passed). Rule check: better in both 2026 halves on
speed and $, worse on no-payout and in 2021-25: not a clear yes. Built OFF (docs/LIT25_FUNDED.md).

    python -X utf8 tools/money/funded25.py --n 600
