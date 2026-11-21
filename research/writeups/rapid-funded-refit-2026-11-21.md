---
title: Rapid EOD funded refit - the Builder's winner cap does not belong on a Rapid; a bigger cap + keep more in the account
family: risk
date: 2026-11-21
status: finding - recommend YES on new card rapid-funded-refit (25K cap $2,000 + keep $1,000; a 50K cap $4,000 + keep $2,000) and on keep-1000-rapid (reopened). Owner's yes before any preset change; nothing live changed.
summary: The Rapid funded presets copied the Builder's per-trade winner cap ($1,000 25K / $2,000 50K), which only exists for the Builder's 50% consistency and $2,000 payout cap; MFFU's Rapid EOD funded has neither. Pre-registered grid (cap x amount kept in x room share, 1,000 paths, ATLAS at real fills and sized on a 10-tick stop): on the 25K, cap $2,000 + keep $1,000 makes $2,283 / $1,083 a month vs $1,742 / $769 (Jan-Jun / Jul-Oct-like) and loses fewer funded accounts (24.0 -> 18.3%, 34.5 -> 31.8%); 2021-25 -$47 vs -$46. On a 50K the rule's pick was cap $7,500 + keep $2,000 ($7,551 / $2,888), but its biggest simulated day reaches $9,621 (MFFU moves a Rapid to LIVE at $10,000 in a day and pauses every sim account), so Claude recommends cap $4,000 + keep $2,000 ($6,404 / $2,921, lost 19.4 -> 15.3%, 22.7 -> 21.6%, biggest day $7,229). The cap alone loses more accounts; keeping more in alone is ~$0 for 10 fewer lost Rapids in 100.
runs: tools/money/rapid_funded_refit.py run -> research/lab/rapid_funded_refit.json; design research/second/rapid_funded_refit_design.md (0023b1a3, committed first)
---

# Rapid EOD funded refit (2026-11-21)

## For the owner (one minute)

**Once your Rapid 25K is funded, let a winning trade pay up to $2,000 (today $1,000) and keep $1,000 in the account after
each payout (today $500). More money and fewer lost accounts. Two Decide cards: rapid-funded-refit and keep-1000-rapid.**

| Rapid 25K funded (6 months, after fees + MFFU's 90%, before tax) | Jan-Jun-like | Jul-Oct-like | 2021-25-like |
|---|---:|---:|---:|
| Today ($1,000 cap, keep $500) | $1,742 / lost 24.0% | $769 / lost 34.5% | -$46 |
| **Refit ($2,000 cap, keep $1,000)** | **$2,283 / lost 18.3%** | **$1,083 / lost 31.8%** | -$47 |
| Only keep $1,000 (keep-1000-rapid) | $1,791 / lost 14.2% | $751 / lost 24.8% | -$48 |
| Only the $2,000 cap | $2,143 / lost 32.7% | $1,015 / lost 42.0% | -$45 |

A Rapid 50K (when bought): today $4,944 / $2,274 a month; **$4,000 cap + keep $2,000: $6,404 / $2,921**, lost 19.4 -> 15.3% /
22.7 -> 21.6%.

## Why the cap is wrong for a Rapid

engine/multi_account mffu_rapid_eod_25k / _50k sizing.funded = tools/uprisk UP25 / UP50: 60% of the room, <= $750 / $1,500 risk,
a winner <= $1,000 / $2,000. The winner cap came from the Builder funded rules (best day <= 50% of the cycle, $2,000 payout
max). Rapid EOD funded (research/lit/mffu_rules.json): no consistency, no payout cap, daily payouts above the $1,100 / $2,100
buffer. One rule that matters: a Rapid with **$10,000 net in one day goes LIVE**, and MFFU then pauses every sim account
and new purchases (mffu_rules live_move_other_accounts).

## The grid (pre-registered; ATLAS 10 ticks a side and sized on a 10-tick stop; eval as built)

Rapid 25K ($ a month / funded lost in 6 months):

| Winner cap | Kept in | Room share | Jan-Jun-like $/mo / lost | Jul-Oct-like | 2021-25-like |
|---:|---:|---:|---|---|---|
| $1,000 | $500 | 60% | $1,742 / 24.0% | $769 / 34.5% | $-46 / 17.1% |
| $1,000 | $500 | 40% | $1,716 / 23.4% | $705 / 32.8% | $-46 / 16.8% |
| $1,000 | $1,000 | 60% | $1,791 / 14.2% | $751 / 24.8% | $-48 / 17.0% |
| $1,000 | $1,000 | 40% | $1,768 / 14.4% | $707 / 24.8% | $-48 / 16.6% |
| $2,000 | $500 | 60% | $2,143 / 32.7% | $1,015 / 42.0% | $-45 / 17.7% |
| $2,000 | $500 | 40% | $2,101 / 28.9% | $810 / 35.5% | $-45 / 16.7% |
| $2,000 | $1,000 | 60% | $2,283 / 18.3% | $1,083 / 31.8% | $-47 / 17.5% |
| $2,000 | $1,000 | 40% | $2,246 / 16.6% | $949 / 28.3% | $-47 / 16.7% |

Rapid 50K:

| Winner cap | Kept in | Room share | Jan-Jun-like $/mo / lost | Jul-Oct-like | 2021-25-like |
|---:|---:|---:|---|---|---|
| $2,000 | $1,000 | 60% | $4,944 / 19.4% | $2,274 / 22.7% | $-87 / 26.9% |
| $2,000 | $1,000 | 40% | $4,953 / 15.3% | $2,106 / 18.2% | $-85 / 25.9% |
| $2,000 | $2,000 | 60% | $5,206 / 10.0% | $2,353 / 15.2% | $-92 / 26.9% |
| $2,000 | $2,000 | 40% | $5,156 / 8.2% | $2,210 / 13.1% | $-90 / 25.7% |
| $4,000 | $1,000 | 60% | $5,964 / 25.3% | $2,630 / 31.0% | $-79 / 26.9% |
| $4,000 | $1,000 | 40% | $5,938 / 17.5% | $2,247 / 20.0% | $-80 / 26.0% |
| $4,000 | $2,000 | 60% | $6,404 / 15.3% | $2,921 / 21.6% | $-83 / 26.9% |
| $4,000 | $2,000 | 40% | $6,376 / 10.1% | $2,591 / 15.3% | $-84 / 25.6% |
| $7,500 | $1,000 | 60% | $6,888 / 27.0% | $2,529 / 31.8% | $-76 / 27.0% |
| $7,500 | $1,000 | 40% | $6,591 / 17.6% | $2,207 / 20.2% | $-79 / 26.0% |
| $7,500 | $2,000 | 60% | $7,551 / 16.5% | $2,888 / 23.1% | $-80 / 26.9% |
| $7,500 | $2,000 | 40% | $7,397 / 10.3% | $2,573 / 15.5% | $-82 / 25.7% |

Decision rule (more $ than today in both 2026 halves, funded lost <= today + 2 pts; best Jan-Jun $ wins):
- 25K: candidates cap $2,000 + keep $1,000 at 60% or 40% room; **winner $2,000 / $1,000 / 60%**.
- 50K: 5 candidates; the rule's winner is $7,500 / $2,000 / 60%. **Not recommended** (safety, outside the money rule):

| 50K setup | Biggest day, Jan-Jun-like (median path / worst path) | Jul-Oct-like worst | 2021-25-like worst | Paths with a day >= $7,500 (H1) |
|---|---|---|---|---|
| today $2,000 / $1,000 | $5,075 / $5,282 | $2,963 | $5,154 | 0 |
| **$4,000 / $2,000 (recommended)** | $7,146 / $7,229 | $3,667 | $7,220 | 0 |
| $7,500 / $2,000 (rule's pick) | $8,244 / $8,798 | $4,697 | **$9,621** | 720 of 1,000 |

$9,621 is $379 from MFFU's live move. With real fills, two lanes the same day and a bigger NQ, $7,500 is too close. $4,000
keeps a ~$2,800 margin and makes MORE in the Jul-Oct-like market ($2,921 vs $2,888).

## How to apply (after the owner's yes; the lead, Sim check first)

engine/multi_account PRESETS mffu_rapid_eod_25k sizing.funded max_win 1000 -> 2000; mffu_rapid_eod_50k 2000 -> 4000;
engine/rapid.PLANS cushion 500 -> 1000 (25K), 1000 -> 2000 (50K); tests.test_rapid25 / test_money_plan expected numbers.
Funded stage only: the eval is unchanged.

## Limits

Reshuffled weeks of the past; 3 real ATLAS fills set the cost; the biggest-day check counts booked $ per day (an open trade's
peak is not modelled); the 50K is not owned yet (5th slot, ~late Dec).
