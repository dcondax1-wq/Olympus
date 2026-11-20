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

> [!failure]- Rapid EOD levers
> on LIT + ATLAS $500 Rapid EOD 50K: eval give-up / re-buy (room < $500-1,000, session > 30/45, 30%-rule need > $3-4k: +$12-104/mo = noise, 2021-25 worse), eval day caps (none, stop at +$500/+$700, balance-aware guard: today's 30% size guard is best), Asia slot at LIT size (funded lost 9.4% / 2.0% / 27.3%), fixed $1,000 payout requests, different mixes per account for more $ (identical copies pay more in both halves; different mixes only cut the no-pay risk): rejected. Lead: keep a $1,000 funded cushion.
> Write-ups: [[rapid-levers-2026-11-16|Rapid EOD 50K levers]]


## Write-ups

| Date | Write-up | Verdict |
|---|---|---|
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
