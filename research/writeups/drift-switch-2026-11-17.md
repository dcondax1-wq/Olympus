---
title: "Edge stopped working" switch - cut size when LIT's / ATLAS's own record drifts below expectation, restore on recovery
family: risk
date: 2026-11-17
status: rejected - 0 of 51 variants pass; the timing is no better than random cuts of the same size (chance). Paper only, nothing live changed.
summary: Owner idea 2026-11-17. Each strategy watches its own record of finished trades (net R, 2021-11 on, paper trades included) and cuts its size to x0.5 / x0.25 / paper while the record drifts (last N trades sum <= 0 or -5R, last-N profit factor < 1 / 1.2, 4 / 6 / 8 losers in a row, cumulative R 5-15R under its 50 / 100-trade high), restoring as soon as the rule clears. 17 rules x 3 levels = 51 variants, scored on the stored lit_live 2026 trades + the 2021-25 REF trades and on the MFFU Builder 50K (LIT alone) and Rapid EOD 50K (LIT + ATLAS $500) with the same Monte Carlo paths as tools/money/stack_one_account.py, costs in. The long-window rules never fire in 2026, so 2026 money is untouched. In 2021-25 they halve the failed Builder evals (55% -> 28% within 60 sessions) and cut fees ($212 -> $166 per 6 months), but the payouts fall by the same amount: the Builder still makes -$7 instead of -$9 a month (noise), and the Rapid EOD falls from +$63 to +$12 a month. Cutting the same number of trades at random places in 2021-25 does as well (the best of the 51 beats 90% of random shifts, the headline rule 80.5%; 95% was needed). No variant passes the pre-registered gate; 2.0% of the random-shift controls pass it by luck.
runs: none (research/lab/drift_switch.json)
---

## For the owner (one minute)

Best version: **"after 50 trades that add up to a loss, go to paper until they add up to a profit again."**

| What (6 months of one account, after the eval fees, your share) | Jan-Jun 2026 | **Jul-Oct 2026 (check)** | 2021-25 (no edge) |
|---|---:|---:|---:|
| Builder 50K, LIT, today: $ a month | $779 | **$753** | -$9 |
| ... with the switch | $779 | **$753** | -$7 |
| ... evals bought in 6 months (today -> switch) | 1.38 -> 1.38 | 1.38 -> 1.38 | **2.31 -> 1.81** |
| Rapid EOD 50K, LIT + ATLAS $500, today: $ a month | $5,022 | **$2,301** | $63 |
| ... with the switch | $5,022 | **$2,301** | **$12** (worse) |
| LIT alone at $500 a trade, 2021-25: net / worst drawdown | | | $1,961 / -$19,725 -> $8,907 / -$11,083 |

In plain words:
- **In 2026 it costs nothing, because it never switches on.** LIT's last 50 trades were never in the red in 2026.
- **In a 2021-25 market it buys fewer evals, but it also gets fewer payouts.** On the Builder that comes out even. On
  the Rapid it is worse. You do not keep more money.
- **It is luck, not a real signal.** Cutting the same number of 2021-25 trades at random times does about as well. The
  record does not tell you when the edge is gone.
- **Verdict: no.** 0 of 51 versions pass. Nothing changed.

Next:
1. Nothing to switch. The honest protection stays the same: watch the live record by eye, and stop buying evals by hand if
   LIT's 2026 edge fades.
2. To re-run: `python -X utf8 tools/money/drift_switch.py --n 300`

## 1. What was tested

- **Already tested (lit-risk-money.md, 2026-10-20):** short cold / drawdown / streak rules on LIT at x0.5. Those were the
  last 5-20 trades summing to <= 0R, a 5R drawdown, and 2 stop-outs in a row. All of them cost money in 2026. This test is
  different in four ways:
  - It uses long windows that need no prediction, plus profit-factor rules.
  - It has a paper mode (skip the trade, keep recording it) with an automatic restore.
  - It applies the same rule to ATLAS on its own record.
  - It is scored on the MFFU accounts, against 2021-25 losses, failed evals and fees.
- **The record.** Net R = points / stop points, with slippage already in the stored prices. It counts every trade of that
  strategy that closed before this entry, from 2021-11 on, paper trades included, so the switch can turn back on.
  - LIT: the 511 REF trades of 2021-25 + the 120 live (lit_live) trades of 2026.
  - ATLAS: tools/atlas.account_units, never opposite LIT.
- **Rules** (17):
  - The last N trades sum to <= thr R: N 20 / 30 / 50, thr 0 / -5.
  - The last N trades' profit factor < p: N 30 / 50, p 1.0 / 1.2.
  - K losers in a row: K 4 / 6 / 8. The next winner restores the size.
  - Cumulative R is D R or more under its best of the last X trades: X 50 with D 5 / 10 / 15, and X 100 with D 10.
- **Levels** (3): x0.5, x0.25, or paper (x0). A cut size is rounded down but never goes below 1 micro.
- **Sizes and accounts.** The account's normal size comes first, then the multiplier:
  - Eval: the live two_week size.
  - Funded: UP50 (60% of the room, at most $1,500, a winner capped at $2,000).
  - ATLAS: stack_q at $500.
  - Accounts and costs are identical to stack-one-account-2026-11-16.md: Builder 50K at $91.80, and Rapid EOD 50K at $94
    with the 30% best-day guard and the Tier-1 news rule. $1.90 a micro, plus 1 tick on market fills and stops.
- **Monte Carlo.** The same paths as stack_one_account (seeds 7 / 23): eval 2,000 x 60 sessions; funded and the 6-month slot
  1,000 x 126. The multiplier is fixed per trade from the real history, so the resampled days keep the switch's real state.
- **Gate (set before the run).**
  - In both 2026 halves, the slot $ a month on both accounts must stay >= 95% of today. Jan-Jun picks, Jul-Oct checks.
  - In 2021-25, all of these must improve: the slot $ on both accounts, the fees on both accounts (= no more evals
    bought), the plain net $ and the plain max drawdown.
- **Chance.** Each variant is run 6 more times with its 2021-25 cut pattern circularly shifted to a random place inside
  2021-25. That keeps the share of trades cut and the streak lengths, and leaves 2026 as the rule has it.
  - Account level: 306 shifted runs at 333 paths.
  - Trades-only level: 200 shifts per variant.

## 2. Results (Builder slot $/mo H1 / H2 / REF, fees per 6 months REF; Rapid same; LIT-at-$500 2021-25 net / max DD)

| Variant (selected; all 51 in research/lab/drift_switch.json) | Builder slot | B fees REF | Rapid slot | R fees REF | plain REF net / DD |
|---|---|---:|---|---:|---|
| **today (off)** | 779 / 753 / -9 | 212 | 5,022 / 2,301 / 63 | 273 | 1,961 / -19,725 |
| sum50 <= 0R -> paper (= pf50 < 1) | 779 / 753 / **-7** | **166** | 5,022 / 2,301 / **12** | 209 | **8,907 / -11,083** |
| sum50 <= 0R -> x0.5 | 779 / 753 / -11 | 188 | 5,022 / 2,301 / 35 | 252 | 5,691 / -14,507 |
| sum20 <= 0R -> x0.5 | **739 / 684** / -16 | 188 | 4,905 / **2,045** / 45 | 245 | 875 / -13,489 |
| sum30 <= -5R -> paper | 779 / 753 / -21 | 205 | 5,022 / 2,301 / 38 | 240 | -5,633 / -22,936 |
| pf50 < 1.2 -> paper | 709 / 753 / -9 | 153 | **4,478** / 2,301 / -5 | 187 | 6,793 / **-7,651** |
| 4 losers in a row -> paper | 829 / 752 / -13 | 207 | 4,920 / **1,767** / 33 | 260 | 520 / -17,196 |
| 6 losers in a row -> x0.5 | 756 / 753 / -11 | 212 | 5,000 / 2,301 / 59 | 271 | 2,083 / -19,461 |
| dd5R under the 50-trade high -> paper | **560** / 753 / -12 | 147 | **3,715** / 2,301 / 15 | 169 | 6,845 / -8,798 |
| dd10R under the 100-trade high -> paper | 779 / 753 / -13 | 167 | 5,022 / 2,301 / 27 | 190 | 4,247 / -12,950 |
| dd15R under the 50-trade high -> x0.5 | 779 / 753 / **-8** | 207 | 5,022 / 2,301 / 63 | 263 | 3,068 / -18,018 |

The best variant (sum50 <= 0R -> paper) in more detail:

| | Builder today | Builder + switch | Rapid today | Rapid + switch |
|---|---|---|---|---|
| 2026 (both halves) | identical | identical (never on) | identical | identical |
| LIT 2021-25 at $500: trades/wk, PF, $/mo, max DD | 2.4, 1.02, $38, -$19,725 | 1.4, 1.14, $174, -$11,083 | 7.0, 1.07, $486, -$37,025 (LIT+ATLAS) | 4.2, 1.12, $525, -$21,094 |
| 2021-25 eval: fail within 60 sessions | 55.1% | **28.1%** | 68.0% | 47.2% |
| 2021-25 eval: pass within 60 sessions / median sessions | 29.8% / 14 | 30.1% / 16 | 19.2% / 29 | 13.2% / 37 |
| 2021-25 6 months: evals bought, fees | 2.31, $212 | 1.81, $166 | 2.90, $273 | 2.22, $209 |
| 2021-25 6 months: payouts to you a month | $27 | $21 | $108 | $46 |
| 2021-25 6 months: net a month / no payout at all | -$9 / 90.6% | -$7 / 92.7% | $63 / 82.2% | $12 / 91.5% |
| funded accounts lost | 0% | 0% | 0% | 0% |

Counts over the 51 variants:
- Builder Jan-Jun >= 95% of today: 41. Builder Jul-Oct: 48. Rapid Jan-Jun: 46. Rapid Jul-Oct: 45.
- 2021-25 fees not up: 47 Builder, 51 Rapid. The plain max DD is smaller in 45, and the plain net is up in 31.
- **2021-25 slot $ up: only 3 on the Builder and 2 on the Rapid, and never both.**
- The Builder-only checks pass for 3 variants (sum50 <= 0 paper, pf50 < 1 paper, dd15R x0.5). All three lose $ on the
  Rapid in 2021-25.
- **Full gate: 0 / 51.**

## 3. Is the timing real? (no)

- **Accounts.** 0 of 51 real variants pass the gate. On the same smaller paths, 6 of the 306 randomly shifted ones pass
  (2.0%). Real is no better than chance.
- **Trades only (LIT at $500, 2021-25 in order).**
  - For each variant, 200 random shifts of its own cut pattern were compared with the real rule.
  - The best real rule beats 90% of its shifts on net $ (p 0.10) and 89.5% on max DD (p 0.105).
  - No variant reaches p < 0.05. With 51 tries, about 2-3 would by luck alone.
  - The headline rule (sum50 <= 0R -> paper) beats 80.5% of its shifts on net $ and 67% on drawdown. A random shift of the
    same cuts makes +$1,648 and has a -$13,234 drawdown (median). The real rule makes +$8,907 with -$11,083.
- **Why.** LIT's 2021-25 trades have no memory. A 50-trade losing stretch does not predict the next trades. So the drawdown
  falls in proportion to the trades skipped (fewer trades = less swing), not because the bad ones were skipped. The same
  thing was found for the short windows in October (lit-risk-money.md: "a cold filter is small exactly when the next target
  comes").
- **Why the accounts do not gain.** In a no-edge market, an eval that trades less fails less often, but it also passes
  less often. Every eval it no longer buys is also a payout it no longer gets. On the Rapid, ATLAS's 2021-25 record has a
  small edge (PF 1.07 with LIT), so switching it to paper costs money there.

## 4. Honest limits

- The long-window rules are free in 2026 only because the 2026 record never had a losing 50-trade stretch. If 2026's edge
  faded slowly, the switch would turn on after about 20 weeks of LIT trades (50 trades at 2.5 a week). That is too slow
  to save an eval, and the 2021-25 test says it would not save money anyway.
- One Monte Carlo seed pair, as stack_one_account. Gaps under ~$10 a month on the Builder 2021-25 slot are noise.
- The multiplier is read from the real history and attached to each trade. A resampled path keeps the switch's real state
  on that day, not a state rebuilt from the path.
- The restore uses no hysteresis: the rule clears as soon as the window sums above the line. A slower restore would only
  skip more of the recovery trades.
- Nothing live was changed: no live_model*.json, engine file, sw.js or dashboard file.

Files: `tools/money/drift_switch.py` (the study; patches stack_one_account's Ev / BuilderFunded / Rapid in-process to apply
the multiplier), `research/lab/drift_switch.json` (all 51 variants x 2 accounts x 3 spans, the cut share per span, the
chance runs).
