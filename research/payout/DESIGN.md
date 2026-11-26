# Payout policy over 12 months - pre-registered design (2026-11-26, written BEFORE the run)

Paper research only: reads stored trades, never requests a payout, changes nothing live. Code: `tools/money/payout_year.py`
(extends `tools/money/payout25.py`, the 6-month 25K study of 2026-11-17, on the same engine: `tools/uprisk.Funded` = MFFU Builder
sim-funded rules from `research/lit/mffu_rules.json` via `engine/funded_life`, per-strategy sizing from `builder_levers.GF`,
costs in, the live one-account rule for LIT + ATLAS).

## Question
Which request habit gets the most cash to the owner per 12 months of a funded account WITHOUT breaking it: request early, at a
middle line, at today's line, at the max, or at the max with a cushion?

## Accounts (3)
- **25K ATLAS** - MFFU Builder 25K funded, ATLAS alone at its funded preset (the live ATLAS 25K today).
- **25K LIT + ATLAS** - the same account with LIT at its preset + ATLAS $250 a trade (the combo option).
- **50K LIT** - MFFU Builder 50K funded, LIT at its preset (Zlarior's eval once it passes).

## Markets (3), 600 Monte Carlo paths each, 5-session blocks, seed fixed
- **2026-like**: blocks from 2026-01-01 .. 2026-10-16 only.
- **25% mix**: each block from 2026 with probability 0.25, else from 2021-11 .. 2025-12 (the realistic-pessimistic case).
- **2021-25**: blocks from 2021-11 .. 2025-12 only.

## Horizon and rules
252 sessions (12 months). Payouts 1-4 only (the 5th moves the owner to live and puts every sim account to sleep:
fleet-plan 2026-11-22, engine/payout_autopilot BUILDER_LAST): after payout 4 the account is closed and its cash counted.
Lost = the max-loss floor hit, or stuck under $100 of room. MFFU's own rules always apply (buffer, $ min / max per request,
2 traded days a cycle, best day <= 50 % of the cycle, 48 h before the first, 80 % to the owner).

## Policies (6; M = the plan's max request, m = its min: 25K $1,000 / $250, 50K $2,000 / $500)
1. **asap** - ask the first day MFFU allows, for what sits above the buffer (>= m).
2. **half** - wait until M / 2 sits above the buffer.
3. **today** - today's line (engine/funded_life ask_above: 25K $750, 50K $1,500).
4. **max** - wait until the full M sits above the buffer (the owner's current plan on the Builders).
5. **max + cushion** - ask M only when M + 30 % of M sits above the buffer (the 30 % stays as extra room).
6. **cycle-timed** - the existing builder_levers cycle25 schedule (M on the cycle's 2nd traded day, then less each day).

## Measured (per account x market x policy)
Cash to the owner in 12 months (mean, and P25 / P75), P(account lost in 12 months), P(no payout in 12 months), payouts taken,
first payout (median sessions).

## Pick rule (fixed now)
For each account: the policy with the most mean cash per 12 months in the **25% mix**, among the policies whose P(lost) is
<= today's + 0.5 points and whose P(no payout) is <= today's + 2 points in EVERY market. Ties: the sooner first payout. If no policy
beats today's cash in the 25% mix by more than $25 a year, keep today's. The result is a request HABIT (an owner yes/no), never
an automatic request.
