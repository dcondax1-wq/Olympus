---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-11-13"
status: "adopt-candidate (one rule, owner decides; paper only, nothing live changed) - the \"stop\" reset rule for every account (an account stops buying evals once its own running net is 5 eval prices below ..."
source: "research/writeups/millionaire-plan-2026-11-13.md"
aliases:
  - "The millionaire plan"
---

# The millionaire plan

> [!success] Verdict: adopt-candidate
> adopt-candidate (one rule, owner decides; paper only, nothing live changed) - the "stop" reset rule for every account (an account stops buying evals once its own running net is 5 eval prices below its best): it cuts the eval cash a 2021-25-like market eats by 90-96% and costs 1-3% in a 2026-like market.

**Full title:** The millionaire plan (M1, 2026-11-13) - from prop-firm evals to $1M. In a market like Jul-Oct 2026, 10 LIT accounts pay about $6,900 a month in year 1 and $100K in about 14-18 months; $1M from prop payouts alone takes about 10 years, and about 4-5 years only if a personal account compounds the same edge. In a 2021-25 market it pays nothing, and the only protection is a stop rule on eval buying

## Summary

Owner 2026-11-12 - "You're gonna make me a million of trading prop firms and eventually live accounts, so think like a millionaire." The whole business was run as a Monte Carlo (tools/millionaire_mc.py, 400 paths of 10 years, whole weeks of real LIT trades drawn from Jan-Jun 2026 = H1 pick, Jul-Oct 2026 = H2 check, 2021-25 = REF). Each account = the uprisk engine (MFFU Builder eval on the live two_week sizing, 2 sessions of paperwork, Sim Funded on the live funded preset, 80% payouts, lost or 5 payouts then the next eval), all accounts on the same market path (copies are one bet), $1.90 a micro. H2, year 1, $ a month after every eval fee - 1 account $874, 3 (the MFFU cap) $1,629, 5 $3,221, 10 $6,886; the ladder (3, then 5 at the first payout, then 10 at $10K net) $4,903, then $8,457 a month in years 2-3, $100K after a median 18 months. $1M from prop payouts alone - 36% of H2 paths in 10 years, 0% in 5. With a personal futures account (seeded with $25K once $30K is kept after tax, LIT at 1% of the account a trade) - $1M after a median 52 months (85% within 5 years); in a 2021-25 market 0%. REF - every fleet loses a little (1 account +$5, 10 accounts -$148 a month) and keeps buying evals - $4.6K to $57K of eval cash at the 95th percentile; the stop rule caps that at $459 (1 account) to $4,603 (10). Firm prices and codes checked on the web 2026-11-13 (sources below; the firms' own pages cannot be opened from this machine, so every price is unconfirmed until checkout).

## Money first

H2 = trades of Jul-Oct 2026 (the check half, the one to quote). REF = 2021-25 (LIT shows no edge there). $ a month after
every eval fee, before tax. "Cash to keep" = the most the eval fees ran ahead of payouts (95th percentile): the money you need
on hand so the plan never stops for lack of cash.

| Fleet | Year 1 $ a month (H2) | Worst 1 in 10, year 1 | Years 2-3 $ a month | Cash to keep for evals | $100K (median months) | $1M within 5 years: prop only / with a personal account | 2021-25 market: $ a month, cash to keep (no stop rule / stop rule) |
|---|---:|---:|---:|---:|---:|---|---|
| 1 account (Zlarior 50K) | **$874** | $518 | $956 | $275 | 106 | 0% / 0% (median 103 months) | +$5, $4,553 / **$459** |
| 3 accounts (MFFU's cap: 50K + 25K + 25K) | **$1,629** | $1,006 | $1,822 | $682 | 57 | 0% / 1% (median 80) | -$12, $9,835 / **$963** |
| 5 accounts (+ 2 other-firm 50Ks from day 1) | **$3,221** | $2,000 | $3,718 | $1,347 | 29 | 0% / 39% (median 64) | -$53, $22,125 / **$2,003** |
| 10 accounts (from day 1) | **$6,886** | $4,227 | $8,462 | $2,676 | 14 | 0% / 93% (median 49) | -$148, $57,276 / **$4,603** |
| **The ladder** (3 now, 5 at the first payout, 10 at $10K net) | **$4,903** | $1,732 | **$8,457** | **$682** | **18** | 0% / **85%** (median **52**) | -$24, $24,057 / **$963** |

H1 (Jan-Jun 2026) gives the same picture, a little better: ladder $5,253 / $8,623 a month, $100K in 17 months, $1M with a
personal account in a median 43 months. Prop payouts alone reach $1M within 10 years on 36% (H2) / 44% (H1) of paths: the
ladder's 10-year median is $958K.

**What the numbers say, plainly:**
- **The edge pays, the evals are cheap.** One LIT 50K account makes about $10,500 in its first year (H2) on about $214 of
  evals: about $49 for every $1 of eval fees. A 25K copy makes $33 per $1, an other-firm 50K (at $130 an eval) $35 per $1.
- **More accounts = more money, almost in a straight line, but they are one bet.** All copies trade the same LIT signal, so a
  bad month hits all of them together. Each account can only cost you its eval price.
- **The ladder is the best shape.** It earns about 70% of the 10-account fleet's year 1, needs only $682 of cash (a quarter),
  and in a 2021-25 market it never grows: only 32% of those paths ever buy account 4 (with the stop rule).
- **$1M is a 4-5 year goal only if the edge holds AND a personal account compounds it.** Prop payouts alone are capped by the
  firms (payout caps, 5 payouts an account, account caps per firm): about $100K a year at 10 accounts.
- **In a 2021-25 market none of this works.** Every fleet is about break-even to slightly negative and keeps buying evals.
  The stop rule is what keeps that cheap.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-13]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[2026-11-03-money-plan|The money plan on today's settings]], [[atlas-funded|ATLAS's funded account]], [[eval-guard-2026-11-13|Eval guard]], [[lit-funded-firms|LIT on 3 funded accounts]], [[prop-firms-hub|Prop firm hub]], [[scale-plan|The scaling plan]]
- Runs: `none (business Monte Carlo, not a strategy test; stored in research/lab/millionaire_mc.json)`
- Source: `research/writeups/millionaire-plan-2026-11-13.md`
- Back to [[ZEUS Home]]
