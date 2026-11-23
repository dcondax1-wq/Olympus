---
tags:
  - zeus/strategy
  - lane/rapid
  - market/nq
type: "strategy"
key: "rapid"
---

# Rapid lanes

> [!abstract] MFFU Rapid EOD accounts: Zlarior (LIT) and ATLAS together, one trade at a time.
> Zlarior (LIT) and ATLAS trade the Rapid together, one trade at a time. Nothing trades until step 2. One Rapid at a time (a 25K or a 50K). Checked end to end on a test PC 2026-11-20 (night-rapidready).

## Rules in plain words

- **1. Add it (1 minute)**
- **2. START BOT**
- **3. Check it**
- **MFFU's rules vs the bot (25K; MFFU help center + plan page, read 2026-11-19)**
- **If something looks wrong**
- **Later**

## Performance by period

_No period table published for this one yet; see the write-ups._

## Tested and rejected

> [!failure]- Rule-native layer
> 2nd target / 1R / scalp / profit lock: no sooner payout. Lead only: BLITZ max 3/day on the Rapid (chance-level by count; 2021-25 2-week eval fails 2.9% -> 6.0%). Watch on paper.
> Write-ups: [[rule-native-2026-11-17|Rule-native search]]

> [!failure]- ICT ATM range + ES/NQ SMT as the trigger, MES, Judas swing
> 5 pre-registered sets, $250, costs in: every SMT set loses all 3 periods (PF 0.57-0.99, gross 0.59-1.05), MES not cleaner (10-tick stress -$3.7k..-$10.1k), Judas control +$1,672 Jan-Jun then -$2,244 Jul-Oct / -$11,472 2021-25. Rapid 25K eval pass 0-5%. 0 pass.
> Write-ups: [[newstrat-ict-smt-2026-11-20|New strategy for the extra accounts]]

> [!failure]- Rapid EOD levers
> on LIT + ATLAS $500 Rapid EOD 50K: eval give-up / re-buy (room < $500-1,000, session > 30/45, 30%-rule need > $3-4k: +$12-104/mo = noise, 2021-25 worse), eval day caps (none, stop at +$500/+$700, balance-aware guard: today's 30% size guard is best), Asia slot at LIT size (funded lost 9.4% / 2.0% / 27.3%), fixed $1,000 payout requests, different mixes per account for more $ (identical copies pay more in both halves; different mixes only cut the no-pay risk): rejected. Lead: keep a $1,000 funded cushion.
> Write-ups: [[rapid-levers-2026-11-16|Rapid EOD 50K levers]]

> [!failure]- Rapid 25K slot
> one engine at real fills (rank.py): ATLAS only $707 / $141 a month vs today's LIT + ATLAS $1,883 / $800 (rejected again); bank lane = card rapid25-lit-bank NO (eval fail 0.5 -> 3.1%); a Rapid EOD 50K in the slot $5,001 / $2,281 a month but 2021-25 -$560 vs -$300 and eval fail 2.5 / 4.6% vs 0.3 / 2.4%: fails the pre-set safety bar (already on cards buy-rapid50-now / plan-rapid50k-max2-rebuys). Today's lanes stay.
> Write-ups: [[rapid25-slot-2026-11-22|Rapid 25K slot]]

> [!failure]- 2026-11-22 Lucid accounts on a $300 a month fleet
> REJECTED as a way to speed up at $300: adding 1/2/3/5 LucidPro 50K (LIT only, assumed $126) to the Rapid EOD 50K + FundedNext 50K plan out of the SAME $300 budget leaves Jan-Jun-like unchanged (+$264 +- $324 with 2, -$53 +- $370 with 3) and only helps Jul-Oct-like (+$4.7k to +$5.6k over 6 months); buying Lucid FIRST (5 accounts) loses $16.3k Jan-Jun-like and halves the worst 10% ($27.2k -> $16.3k), because the Lucid copies displace the bigger accounts. It works only with a larger budget ($500: 3 Lucid = Decide card lucid-3-at-500-budget). 75 fleets tried.
> Write-ups: [[fleet-v2-2026-11-22|Fleet v2]]


## Write-ups

| Date | Write-up | Verdict |
|---|---|---|
| 2026-11-22 | [[rapid25-slot-2026-11-22\|Rapid 25K slot]] | rejected |
| 2026-11-22 | [[plan-ranking-2026-11-22\|Plan ranking]] | research |
| 2026-11-22 | [[one-account-book-2026-11-22\|One account, combined book]] | research |
| 2026-11-22 | [[fleet-plan-2026-11-22\|Fleet plan]] | research |
| 2026-11-21 | [[rapid25-pass-2026-11-21\|Rapid EOD 25K]] | finding |
| 2026-11-21 | [[rapid-funded-refit-2026-11-21\|Rapid EOD funded refit]] | finding |
| 2026-11-21 | [[fleet-90day-2026-11-21\|The 90-day money machine]] | research |
| 2026-11-20 | [[skeptic-live-patches-2026-11-20\|Skeptic check of the two live sizing patches]] | research |
| 2026-11-20 | [[skeptic-atlas-streak-2026-11-20\|Skeptic check of Decide card atlas-funded-streak-1micro]] | research |
| 2026-11-20 | [[rapid50-ready-2026-11-20\|Rapid EOD 50K readiness]] | finding |
| 2026-11-20 | [[rapid-launch-2026-11-20\|Rapid EOD 25K launch check]] | finding |
| 2026-11-20 | [[newstrat-ict-smt-2026-11-20\|New strategy for the extra accounts]] | rejected |
| 2026-11-20 | [[atlas-risk-real-fills-2026-11-20\|ATLAS funded 25K at real fills]] | finding |
| 2026-11-19 | [[one-account-combo-2026-11-19\|ONE account, several bots]] | research |
| 2026-11-18 | [[rapid25-lit-lane-2026-11-18\|Rapid EOD 25K]] | research |
| 2026-11-17 | [[rule-native-2026-11-17\|Rule-native search]] | adopt-candidate |
| 2026-11-17 | [[rapid-25k-vs-50k-2026-11-17\|MFFU Rapid EOD 25K vs Rapid EOD 50K for LIT + ATLAS]] | research |
| 2026-11-16 | [[stack-one-account-2026-11-16\|More strategies on ONE MFFU account]] | promising |
| 2026-11-16 | [[rapid-levers-2026-11-16\|Rapid EOD 50K levers]] | research |
| 2026-10-19 | [[lit-mffu-rapid-stack\|LIT on stacked MFFU Rapid / Rapid EOD 50K accounts next to the Builder 50K]] | info |
| 2026-10-18 | [[lit-prop-firms\|LIT on every prop firm]] | info |

## Links

- Uses [[Zlarior (LIT)]] and [[ATLAS]]
- [[ZEUS Lessons]] · [[ZEUS Decisions]] · [[ZEUS Home]]
