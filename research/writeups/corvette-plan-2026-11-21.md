---
title: The Corvette plan - prop income scale-up (MFFU + other firms) and car timeline
family: money
date: 2026-11-21
status: research (owner yes/no on any new firm)
summary: 8 prop firms checked against their own rule pages for automated NinjaTrader bots + copying; income model + car timeline.
---

CORVETTE MONEY PLAN (2026-11-21). Research only. No repo file edited, nothing pushed or bought, no orders placed. These are projections from backtests, not results.

## The answer in one table (money to the owner after each firm's 80/90% split, every eval fee and re-buy, and the 30% tax pot)
| Plan | Dec-Feb total (middle) | A typical month Mar-Jun 2027: bad 1-in-10 / middle / good 1-in-10 | Total by Sep 30 2027 (middle); in brackets if MFFU freezes at its live move | Edge halves, by Sep (middle) | 2021-25-like, by Sep (middle / bad) |
|---|---|---|---|---|---|
| MFFU only, today | $3,195 | $1,417 / $4,514 / $7,611 | $35,894 ($14,362) | $4,080 | -$1,707 / -$2,399 |
| MFFU + the 3 MFFU buys | $6,303 | $1,835 / $5,312 / $9,012 | $46,466 ($17,098) | $6,567 | -$4,012 / -$5,443 |
| **+ Lucid x5 (3 on Dec 7, 2 paid from payouts)** | $10,981 | **$4,632 / $10,345 / $15,218** | **$75,965 ($47,846)** | $8,434 | -$4,516 / -$5,947 |
| or + FundedNext x5 (2 on Dec 7, 3 from payouts) | $12,413 | $2,427 / $6,150 / $10,391 | $55,879 ($26,517) | $9,178 | -$4,514 / -$5,948 |

**Car verdict: pay cash. Do not take a loan on this income in 2027.**
- **Most realistic car:** a C7 Stingray (~$40k). The cash target is $49.1k kept.
- **With MFFU + Lucid in a normal market:** the middle month is **June 2027**. The chance by Sep 30 2027 is 89%, or 44% if MFFU freezes its other accounts at the live move.
- **Bad 1-in-10 run:** not by Sep 2027.
- **If the edge halves:** about a 5% chance by Sep 2027.
- **In a 2021-25-like market:** never; you end about $4.5k down.
- **The loan test** (payment under 25% of bad-case monthly income) passes only for the C7 Stingray, only May-Jul 2027, and only if nothing freezes. It fails again by August, when the sim accounts move to live.

## How this was run
- I used the repo's own model (tools/money/fleet_90day.py on fleet_months.py) and stretched it to Sep 30 2027, with 1,000 paths per market.
- Fills are the repo's real fills: ATLAS at 10 ticks a side, LIT as stored.
- I added Lucid and FundedNext accounts on the SAME paths. Each runs LIT + ATLAS $500 at the MFFU Rapid 50K sizing, under each firm's payout rules.
- Freeze bound: MFFU payouts after the first Builder 5th payout are set to $0. MFFU says the other sim accounts then go dormant.
- Lucid's own live move is always modelled as closing every Lucid sim account. FundedNext's 15th payout is modelled as stopping every FundedNext account.
- Live-account income is counted as $0, because nobody knows it yet.
- The base and 3-buy rows match the write-up's model. For example, all3 by June: median $28,294 here vs $27,881 there. The small gaps come from longer, re-drawn paths.
- Scratch files:
  - (cloud scratch) car_fleet.py
  - (cloud scratch) car_analyze.py
  - (cloud scratch) car_analysis.json
  - (cloud scratch) car_fleet_v3dec7.json
  - (cloud scratch) car_fleet_v2.json

## 1. Which other firm (only firms where bots and copying are clearly allowed and NinjaTrader works)
- **Lucid (best by $).**
  - Re-read today: "Automated trading systems and trade copiers are permitted" (https://support.lucidtrading.com/en/articles/11404728-other-trading-activities).
  - NinjaTrader works via Tradovate.
  - Cap: 5 funded per household, 10 accounts in all (https://support.lucidtrading.com/en/articles/11404617-maximum-number-of-accounts).
  - 5 accounts add **+$27,720 by June** (middle). That is about $790 a month per account after everything. Bad 1-in-10: +$8,051.
  - If the edge halves, the middle result is -$504: in 75% of runs Lucid closes after its pocket budget is spent. In a 2021-25-like market: -$504.
  - Open question: its Terms of Use return 403 to our fetcher (https://www.lucidtrading.com/?p=1121). Whether the same bot may also run at MFFU is UNREAD, so get a written OK first.
- **FundedNext (backup, clearest rules).**
  - Copying between FundedNext and other prop firms under the same name is explicitly allowed (https://helpfutures.fundednext.com/en/articles/17230319-what-is-copy-group-trading-policy-at-fundednext-futures).
  - But it caps out: the 15th payout on the profile triggers live review (https://helpfutures.fundednext.com/en/articles/16522296-road-to-live-trading-rapid-flex-direct). Payouts are $1,000 each (https://helpfutures.fundednext.com/en/articles/17229779-fundednext-futures-rapid-daily-fundednext-account-all-rules).
  - So 5 accounts add only about **+$9,480 in total** (bad 1-in-10 +$8,351), and the cap is hit around Mar 8 2027.
- **Excluded:**
  - Topstep: no NinjaTrader, "TopstepX(TM) is the only available trading platform" (https://help.topstep.com/en/articles/8284199-new-to-topstep-start-here). It would need the $14.50/mo ProjectX API, a paid service. No bots on Live.
  - Tradeify: "using it across multiple firms is against Tradeify's policy" (s6.6, https://tradeify.co/funded-trader-agreement).
  - Bulenox: bots need written approval, cross-company copying is banned, and VPNs are banned, which is a risk for Tailscale (https://form.jotform.com/230508683548160).
  - Bots banned outright:
    - Apex: User Agreement (https://dashboard.apextraderfunding.com/legal/user-agreement), seen only through search copies because the site returns 403.
    - Take Profit Trader: UTP #1 (https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/34431153546397-TakeProfitTrader-Universal-Trading-Policies-UTP).
    - Alpha Futures: https://help.alpha-futures.com/en/articles/9508585-prohibited-trading-practices

## 2. When each car is affordable (cash; loan test shown)
"Cash needed" = Maryland out-the-door price + a $3,000 eval reserve + 6 months of age-25 insurance.

| Car | Out the door / cash needed | 20% down if a loan ever passes | Payment, 60 mo at 8.81% / income it needs (4x) | MFFU + 3 buys | + Lucid x5: middle month (chance by Sep if MFFU freezes) | Bad 1-in-10 |
|---|---|---|---|---|---|---|
| C7 Stingray 2015-17, ~$40k | $43,742 / $49,100 | $8,000 | $739 / $2,955 | 45% by Sep (0% if MFFU freezes) | **Jun 2027** (44%) | not by Sep 2027 |
| C8 Stingray 2022-23 1LT, ~$58k | $62,912 / $68,700 | $11,600 | $1,060 / $4,242 | 16% by Sep | Aug 2027 (0.4%) | no |
| C7 Z06 2016-17, ~$63k | $68,237 / $74,200 | $12,600 | $1,150 / $4,599 | 11% | Sep 2027 (0%) | no |
| C8 Z06 2023-24, ~$92k | $99,122 / $105,700 | $18,400 | $1,668 / $6,673 | 1% | 11% by Sep (0%) | no |

**Loan check against bad-case income** (1-in-10 runs, average of the last 3 months):
- With MFFU + Lucid, the bad case peaks at $3,850 in June 2027 and falls to $2,160 by September.
- If MFFU freezes, it peaks at $2,920 in May and falls to about $0 by July.
- Add insurance (about $390-590/mo at age 25, $270-410 more at age 20) and no car passes in any month.
- Lenders usually want 2 years of tax returns for 1099 income. That is general practice, not checked against a source.

**Real-money rule for later:** a loan only once the smallest of your last 3 real months (after the 30% pot) is at least 4x the payment, and that holds after at least one firm's live move.

**If he can afford to lose $630:** all 5 Lucid accounts on Dec 7 still give a C7 Stingray in June 2027 at the middle even if MFFU freezes (68% chance by Sep). But in 17.5% of normal-market runs all 5 fail together before paying, versus 4.5% with 3 now + 2 later.

## 3. Purchases in order (never borrow for evals; pay only from pocket money you can lose, or from banked payouts)
| # | When | Buy | $ | Paid from |
|---|---|---|---|---|
| 1 | Mon Nov 23 | MFFU Rapid EOD 50K, code CLUB (card buy-rapid50-now) | $165.00 | pocket |
| 2 | by Fri Nov 27 | MFFU 2nd Builder 50K eval (card second-50k-eval-now) | $91.80 | pocket |
| 3 | Mon Nov 23 | Email Lucid for a written OK (text in step 1 below) | $0 | - |
| 4 | Mon Dec 7, only after the written OK and a PC Sim check | 3 x LucidPro 50K, **DLL ON** (picked at checkout; it can never be changed: https://support.lucidtrading.com/en/articles/16226068-lucidpro-customization) | ~$378 (~$126 each with a 30% code; list $180; third-party price from https://pipback.com/firms/lucid-trading/accounts/pro; check at checkout, no real price yet) | pocket |
| 5 | ~Jan 13-15 2027 (when banked kept cash is at least $626) | LucidPro 50K #4 and #5 | ~$252 | banked payouts only |
| 6 | the night a Builder 25K dies | MFFU Rapid EOD 50K instead of a $63 25K (card refill-25k-with-rapid50) | $165 | payouts if banked, else pocket |
| 7 | the night a Lucid account dies | re-buy LucidPro 50K | ~$126 | banked payouts; ONE pocket re-buy in total, then stop Lucid |

- **Pocket money:** $634.80, at most $760.80. Plus $165 if a 25K dies before any payout has banked.
- **Backup if Lucid says no:** FundedNext Rapid Daily 50K.
  - Dec 7: 2 accounts for $149.99 + $179.99 (code RAPID; https://helpfutures.fundednext.com/en/articles/16295692-fundednext-futures-rapid-daily-rapid-pro-up-discount-offer).
  - Then 3 more at $179.99, from payouts only.
  - Pocket cap $510.
- **Key dates in the model (normal market):**
  - First Lucid payout: about Jan 28.
  - MFFU live move: middle Apr 27.
  - Lucid live move (first account's payout 5): middle Jun 11 (58% by Jun 30, 92% by Sep 30).

**Risk of losing it** (every account trades the same 2 bots on the same days, so they lose together):
- **Normal market:**
  - The bad 1-in-10 Dec-Feb is about $0 (-$20) even with 10 accounts.
  - The deepest money-out dip is -$856 (bad 1-in-10).
  - The chance of ending below $0 by Sep is 0%.
- **Edge halves:**
  - 27% chance of ending below $0.
  - The deepest dip is -$3,097.
- **2021-25-like:**
  - 94% chance of ending below $0. Middle -$4,516, bad -$5,947.
  - Most of that is MFFU's rule of re-buying every dead eval the same night, about $4,000 by Sep. **Add a stop rule:** no MFFU re-buys after 8 weeks with no payout.
- **Lucid on its own:** chance that every Lucid account dies before any payout is 4.5% (normal), 75% (edge halves), 99% (2021-25-like). The loss is capped at $504.

**Rules that could void accounts:**
- **Lucid hedging (biggest risk).** Banned "across multiple accounts held by the same user" AND "between different firms or funded platforms". That includes minis vs micros in separate accounts and "long ES in one account and short NQ in a separate account". Penalty: accounts reset to the prior day's balance with the drawdown not restored, and no on-demand payouts. Repeats breach every account and can mean a permanent ban (re-read today: https://support.lucidtrading.com/en/articles/11404734-prohibited-hedging).
  - Today ATLAS runs alone on MFFU's 25K while LIT runs alone on the MFFU evals. So LIT long at Lucid while ATLAS is short at MFFU would be a cross-firm hedge.
  - A global direction lock across every firm is mandatory. Its cost (skipped trades) is NOT in the model.
- **Lucid live move.** "All simulated prop accounts are closed when a trader is moved live, or opts out of trading live via cash-out". Live starts at $0 (re-read today: https://support.lucidtrading.com/en/articles/16558826-new-live-structure).
- **Other Lucid rules:**
  - 30-day inactivity deletes the account (https://support.lucidtrading.com/en/articles/11404632-inactivity-policy).
  - Be flat by 4:45 PM ET (https://support.lucidtrading.com/en/articles/11404729-allowed-trading-times).
  - Payouts: 40% best-day rule, $2,000 then $2,500, $52,100 buffer (https://support.lucidtrading.com/en/articles/12890092-lucidpro-payouts).
  - Unverified user reports of "cross-user" resets: nobody else in the household should be on Lucid.
- **MFFU** (per docs/ACCOUNT_RULES.md, checked 2026-11-20):
  - Hedging across your own accounts is banned (rulebook entry, no URL in docs/ACCOUNT_RULES.md); bots allowed but "only you trade it" (https://help.myfundedfutures.com/en/articles/8444599).
  - 7-day inactivity (https://help.myfundedfutures.com/en/articles/16596524).
  - Builder payout #5 moves the account to live and the other sims go dormant (https://help.myfundedfutures.com/en/articles/12109396-comprehensive-faq-live-accounts-at-myfunded-futures).
  - The one-Builder-funded conflict (https://help.myfundedfutures.com/en/articles/14290805-builder-plan-50k-a-comprehensive-guide).
- **FundedNext:**
  - "Using an EA that incorporates third-party applications such as Telegram or WhatsApp is strictly prohibited". Our alert bus sends Telegram (https://helpfutures.fundednext.com/en/articles/17225788-fundednext-futures-most-frequently-asked-questions).
  - From the Terms (https://fundednext.com/futures-challenge-terms):
    - 1.2.21 bans cross-firm hedging.
    - 2.1.7 bans using different IPs for the dashboard and for trading. A phone on cellular counts.
    - 2.2.6 says you must share your system for review on request.
  - Account rolling and flipping are banned (https://helpfutures.fundednext.com/en/articles/14298337-what-are-the-prohibited-trading-strategies-of-fundednext-futures).

## 4. What Claude builds (paper only; the owner arms with his phrase)
1. **Lucid preset `lucid_pro_50k`**:
   - Eval: LIT two_week room_f 0.4 + ATLAS $500, with the bot's soft day stop at $1,000 (under Lucid's $1,200).
   - Funded: UP50 sizing + a 40% best-day guard; payout ping at $4,100 (first $2,000), then at +$2,500 each cycle.
   - Flat 15:55; a 30-day keep-alive.
   - Paperwork: the rules go into research/props/firm_rules.json and docs/ACCOUNT_RULES.md, with a test. The strategy-test protocol is still owed, because Lucid's 40% rule is not tested yet.
2. **NinjaTrader:** a second connection (Lucid's Tradovate login, "NinjaTrader" type, Multi-provider).
   - A Sim selftest that ATI order files reach the Lucid account names while MFFU is also live.
   - Note that FLATTENEVERYTHING flattens both firms.
   - Whether Lucid needs a paid NinjaTrader license is unknown. If it does, that is a paid service and needs his yes.
3. **Global direction lock** in engine/firms.py hedge_conflict: one direction per index family (NQ/MNQ, and ES vs NQ) across all MFFU and Lucid accounts, hand trades included. This builds on the TOP25 #1 branch.
4. **Money tracking:**
   - Lucid seats in tools/money and on the Money page.
   - A payout tracker per firm, with one 30% pot.
   - A "hold payout 5" switch per firm (and MFFU "pause at payout 4"), so the owner chooses when to go live.
   - A Lucid budget guard: re-buy only with banked cash of price + $500, allow 1 pocket re-buy, then stop.
5. **FundedNext backup only:**
   - A `fn_rapid_daily_50k` preset: $1,000 x3 then $1,250 x2 payouts, a 15-payout counter.
   - Telegram/Discord turned off on the alert bus (ntfy + Web Push fallback).
   - A CME early-close flatten, the 2% price-limit guard on, and account names re-mapped after a reset.

**Note:** these numbers use today's live presets. A concurrent finding, research/writeups/rapid-funded-refit-2026-11-21.md (pending the owner's yes), would raise the MFFU Rapid numbers.

## Owner's hands-only steps
1. **Send the email below to Lucid support, then read Lucid's Terms of Use in a real browser.** Our fetcher gets 403, so only he can read them. Copy-paste:
   `Before I buy LucidPro 50K: I wrote my own automated NQ/MNQ strategy (only I use it), it runs from my home Windows PC through NinjaTrader, 2-4 trades a week, no VPS, no copier service, and the same strategy also trades my own accounts at another prop firm under my name, always the same direction, never opposite. Is that allowed under your Terms, including any connected-accounts or trading-in-concert clauses? Please confirm in writing.`
2. **Say yes or no to adding a second firm.** This is a strategy decision. His earlier "MFFU only" stands until he changes it. Buy #1 and #2 now either way: those are the existing cards.
3. **On a written yes from Lucid:**
   - Sign up with one profile, and nobody else in the household on Lucid.
   - Choose DLL ON at checkout.
   - Do ID/KYC before the first payout and set up Plaid or WorkMarket.
   - Enter the Lucid login in NinjaTrader on the PC, then type the live phrase after the Sim check.
   - Every firm sends a 1099: keep the 30% pot and pay quarterly estimates.
   - For the car: get at least 5 insurance quotes, because prices differ by 2x or more.

## Caveats
- The model resamples 5-session blocks of history. The normal market is Jul-Oct 2026, which is only about 4 months of out-of-sample data. In 2021-25 the bots made about $0.
- Lucid and FundedNext prices are third-party or list-with-code prices, not real prices the owner has paid.
- Running past Sep 30 2027 is not modelled.