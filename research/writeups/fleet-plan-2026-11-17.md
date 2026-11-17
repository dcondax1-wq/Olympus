---
title: Fleet plan - all 5 MFFU accounts on one Monte Carlo, month by month for 6 months
family: risk
date: 2026-11-17
status: plan (paper research, nothing live changed) - in 2026-like markets the fleet pays from mid-December and keeps $20-35k (4 accounts) or $29-54k (5 accounts) after fees, splits and the 30% tax pot in 6 months; in a 2021-25-like market it makes about $0 and most evals never pass.
summary: One Monte Carlo of the owner's whole fleet on the SAME 5-session-block paths (tools/uprisk.mc_paths seed 23, 1,000 paths x 126 sessions = 2026-11-17 to 2027-05-13 per market), so the accounts are correlated the way they really are (same signals). Accounts - Zlarior Builder 50K eval from its real hole ($49,192.78, $3,807 to go, $1,025 room), funded LIT + ATLAS $500; ATLAS funded Builder 25K from $25,000 this week, ATLAS alone; a NEW Builder 25K eval ($63) LIT, funded LIT + ATLAS $250 (one-account rule); a NEW Rapid EOD 50K ($165) LIT + ATLAS $500, 30% guard, $1,000 cushion; the 5th slot = Rapid EOD 50K #2 bought once payouts in hand after the tax pot reach $165. Re-buy = the research slot logic (a failed eval is bought again at once, a lost funded starts a fresh eval). 6-month cash after fees, splits and 30% tax pot (mean, 5 accounts) $28,568 Jul-Oct-like / $54,349 Jan-Jun-like / $12 2021-25-like; 4 accounts $20,406 / $35,239 / $57. P(no payout by Jan 31) 6.2% / 3.1% / 76.4%. Cash to keep for buys + re-buys (p95) $320 / $320 / $1,363.
runs: none (research/lab/fleet_plan.json, tools/money/fleet_plan.py; page tools/web_public/business/plan.html + plan.json)
---

## For the owner

| 6 months (Nov 17 - May 13), after fees + MFFU splits + 30% tax pot | 2026 Jul-Oct-like | 2026 Jan-Jun-like | 2021-25-like |
|---|---|---|---|
| **5 accounts** (+ Rapid #2 from payouts): average | **$28,568** | $54,349 | $12 |
| bad 10 in 100 / middle / good 10 in 100 | $8,180 / $28,676 / $47,864 | $24,442 / $54,351 / $82,832 | -$1,198 / -$713 / $1,729 |
| **4 accounts** (one Rapid, today's plan): average | **$20,406** | $35,239 | $57 |
| First payout of any account (likely) | Dec 18 | Dec 11 | Dec 29 (only 18.6% by Dec 31) |
| Chance of NO payout at all by Jan 31 | 6.2% | 3.1% | **76.4%** |
| Cash to keep for buys + re-buys (9 in 10 / 19 in 20) | $320 / $320 | $320 / $320 | $1,198 / $1,363 |
| All 5 funded at the same time | Feb 2 (92%) | Jan 27 (98%) | 5% |

Before the tax pot (cash after fees and splits): 5 accounts $41,048 / $77,892 / $400.

- **The honest read:** the 2026 numbers are the good case. In the 2021-25-like market most evals never pass, 2 in 3 runs see no
  payout in 6 months and the fleet ends about -$700 (the fees). H1 2026 is where LIT was picked, so Jul-Oct is the fair 2026 row.
- **What it costs today:** $228 (new 25K $63 + Rapid EOD $165). Keep **$320** in total (today's $228 + one Builder 50K re-buy);
  keep **$1,400** if you want cover for a 2021-25-like stretch.
- **Every number assumes the PC bot trades every day.** It has not reported since Nov 7: fix that first.

### Month by month, 5 accounts, Jul-Oct-like (the fair row)

| Month | Cash to you (after fees, splits) | After 30% tax pot | Running total after tax: bad / middle / good |
|---|---|---|---|
| Nov 17-30 | -$174 | -$193 | -$228 / -$228 / -$228 |
| Dec | $2,245 | $1,533 | -$228 / $226 / $4,446 |
| Jan | $5,480 | $3,821 | $75 / $3,512 / $12,650 |
| Feb | $8,286 | $5,793 | $1,131 / $9,426 / $23,131 |
| Mar | $10,782 | $7,534 | $3,417 / $17,757 / $33,658 |
| Apr | $10,259 | $7,166 | $6,901 / $25,296 / $43,680 |
| May 1-13 | $4,170 | $2,914 | $8,180 / $28,676 / $47,864 |

Jan-Jun-like: after tax -$174 / $2,908 / $7,639 / $10,800 / $14,160 / $13,866 / $5,151 (running middle $54,351).
2021-25-like: after tax -$221 / $6 / $42 / $40 / $65 / $57 / $24 (running middle -$713).
4 accounts (no Rapid #2), after tax, Jul-Oct-like: -$187 / $1,621 / $3,419 / $4,317 / $4,960 / $4,491 / $1,786.

### When each account pays first (median payout day; chance by Jan 31; 6 months to you after tax)

| Account | Jul-Oct-like | Jan-Jun-like | 2021-25-like |
|---|---|---|---|
| ATLAS funded 25K (ATLAS alone) | Dec 24; 81%; $2,109 | Dec 14; 91%; $2,804 | Dec 14; 21%; $199 |
| New Builder 25K (LIT, funded + ATLAS $250) | Jan 7; 58%; $1,830 | Dec 30; 71%; $2,543 | Jan 25; 4%; -$65 |
| Rapid EOD 50K (LIT + ATLAS $500) | Jan 15; 64%; $11,758 | Jan 6; 80%; $25,156 | Feb 18; 5%; -$25 |
| Zlarior 50K (funded LIT + ATLAS $500) | Jan 15; 61%; $4,709 | Jan 18; 62%; $4,736 | Mar 8; 2%; -$52 |
| Rapid EOD 50K #2 (5th slot) | Feb 19; 21%; $8,162 | Feb 8; 37%; $19,110 | Mar 1; 1%; -$44 |

Funded (median): Zlarior Dec 18 / Dec 17 / Feb 9 (58% in 6 months); new 25K Dec 3 / Dec 4 / Jan 11 (50%); Rapid Dec 18 /
Dec 18 / Feb 8 (52%). The Rapid makes the most money once funded (daily payouts, 90%), the ATLAS 25K pays first.

### What to buy, and when (the "fill all 5 funded slots" schedule)

MFFU limits: 5 funded at once (1 Builder 50K, 2 Builder 25K, up to 3 Rapid EOD 50K), 10 evals.

1. **Now:** the new Builder 25K ($63) + the Rapid EOD 50K ($165) = $228 from your pocket. Slots then: Zlarior 50K eval,
   ATLAS 25K funded, new 25K eval, Rapid eval = 4 of 5.
2. **An eval fails:** buy the same one again at once (slot logic; early give-up was tested and is noise). Expected buys in 6 months
   (Jul-Oct-like): Zlarior 0.96 (fails or finishes its 5 payouts), new 25K 1.56, Rapid 1.03 (= the first buy only).
3. **Payouts in hand after the tax pot reach $165** (median Dec 21 Jul-Oct-like, Dec 14 Jan-Jun-like; 35% of 2021-25 runs):
   buy **Rapid EOD 50K #2** = the 5th funded slot, paid from payouts. You said one Rapid for now: it adds about $8,200 / $19,100
   after tax in 6 months (2026-like), about $0 in 2021-25. Your call.
4. **All 5 funded at once:** median Feb 2 (Jul-Oct-like): 8.5% by Dec 31, 43% by Jan 31, 68% by Feb 28, 92% by May.
5. A Builder 50K re-buy is the "possibly a fresh Builder 50K later": it happens automatically in the plan if Zlarior fails.
   A fresh 50K in parallel NOW (before Zlarior fails) is the builder-levers question and waits on MFFU saying yes in writing.

## How it was run

- `python -X utf8 tools/money/fleet_plan.py` (1,000 paths a market, ~2.5 min). Reuses, unchanged: builder_levers (GEv eval from
  any hole, GF funded with the request policy, Seat = eval -> 2 sessions -> funded -> fresh eval, by_mix), funded25.by_shared
  (LIT + ATLAS on one 25K, the engine/lit25 rule), rapid_levers (Ev with the 30% guard, Rapid funded with the $1,000 cushion,
  Slot). Prices are the owner's CLUB prices: 50K $91.80, 25K $63, Rapid EOD 50K $165 (rapid_levers.PRICE set to $165).
- **Same paths:** every account steps the same session index on each path (5-session blocks from H1 = 2026 Jan-Jun,
  H2 = 2026 Jul-Oct, REF = 2021-11..2025), so bad weeks are shared. Rapid #2 starts on the session after its buy.
- **Cash:** payouts x split (80% Builder, 90% Rapid) minus every fee on the day it is paid. "After tax" = 30% of each payout to
  the tax pot (STATE.md rule), fees not tax-adjusted. "Cash to keep" = the most the fleet is ever down on a path (fees paid
  minus payouts in hand after tax), today's $228 included.
- **Checks:** single accounts match their own studies - Rapid alone ~$6,000 / ~$2,800 a month before tax (rapid-levers
  cushion row $6,014 / $2,824), ATLAS funded 25K ~$500 a month Jul-Oct (funded25 $497).
- **Not in it:** the PC not trading (silent since Nov 7), payout processing days (2-4 business days to the bank), MFFU's 2%
  price-limit rule, the Rapid EOD 25K question (another helper), BLITZ, any strategy change. Zlarior's session count (~26) is
  an estimate. Zlarior funded with ATLAS $500 and ATLAS on the Rapid are the accounts.json plan; both are still owner yes/nos.
- No strategy change: live_model*.json, engine files untouched. Paper research only.
