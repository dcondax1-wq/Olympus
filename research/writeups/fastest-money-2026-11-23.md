---
title: Fastest money - days to the first real dollar and $ in the first 30 days for LIT + ATLAS, every bot-legal path (props, a small live account, crypto, our current MFFU accounts)
family: money
date: 2026-11-23
status: done - research only, nothing armed, nothing bought, no live file touched
summary: Firm rules were re-checked on 2026-11-23 from the firms' own help pages where they opened (URLs below). The money numbers come from the LIT + ATLAS backtest trades (research/money30/*.py on rank.py's real-fills engine, 1,000 paths, whole weeks drawn from Jan-Jun 2026 = H1, Jul-Oct 2026 = H2 and 2021-25 = REF, costs in). Blunt answer - no new prop account pays most of the time inside 30 days. The quickest real dollars are (1) the ATLAS 25K funded account we already have ($0, first payout in about 13-15 sessions when it comes, 24-56% chance inside 30 days), (2) a $500 live NinjaTrader account trading 1 MNQ (cash any day, about +$1.3k median in a 2026-like month, but a 16% chance of losing ~$400 and -$378 median in a 2021-25-like month), (3) FundedNext Rapid Daily ($149.99 50K / $64.99 25K, the only fresh prop that pays inside 30 days about a third of the time). For $150 this week, buy one FundedNext Rapid Daily 50K, but only after FundedNext confirms in writing that NinjaTrader connects. If it doesn't, buy nothing.
runs: research/money30/fresh30.py -> fresh30_all.json, fresh30_top.json; research/money30/current30.py -> current30.json, live30_rt2.json
---

## For the owner (one minute)

- **No fresh prop account pays inside 30 days in the typical case.** For every new eval, the median 30-day result is minus the fee. The eval takes about 6-8 sessions, then the funded account has to build its buffer.
- **Fastest real cash we already own: the ATLAS 25K funded account.** It needs +$949 more (MFFU profit $1,350) before MFFU pays anything. There is no cost and no risk to the eval budget.
- **The fastest new money is a small live account**, but it is real-money risk. On 1 MNQ with $500 the bot makes cash from about day 2. In a 2021-25-like market it loses about $380 in a month.
- **$150 this week:** one FundedNext Rapid Daily 50K ($149.99, code RAPID, official price). Before you pay, ask FundedNext support in writing: "Can I trade my Rapid account from NinjaTrader 8 with my own automated strategy?" Their page names only Tradovate. If the answer is no, keep the $150.
- Nothing here is armed or bought. Every number is marked **[BT]** = from backtest or **[RULE]** = firm rule (with its source).

## Top 5 (ranked by days to the first real dollar, then $ in 30 days)

30 days = 21 trading sessions. "Bad case" = the worst 10% of paths in a 2026-like market. "REF" = the median in a 2021-25-like market (the bots' edge mostly gone).
Days to first $ = the median session of the first payout among paths that pay, plus the firm's processing time [RULE].

| # | Option | Cost | Days to first $ | $ in 30 days: median / bad case (H2 Jul-Oct; H1 Jan-Jun) [BT] | Chance of cash in 30 days [BT] | Risk | Bots allowed (source) |
|---|---|---|---|---|---|---|---|
| 1 | **ATLAS 25K funded (MFFU Builder) we already have**, ask the $250 minimum | $0 | ~13 sessions (~18 days) when it pays [BT] + instant-12 h approval [RULE] | $0 / $0 (H2); $800 / $0 (H1). Mean +$236 (H2) | 36% H2, 56% H1, 7% REF | 0.2% account loss in 30 days (31% in REF) [BT] | Yes [RULE] [MFFU fair play](https://help.myfundedfutures.com/en/articles/8444599-fair-play-and-prohibited-trading-practices) |
| 2 | **Live NinjaTrader account, $500, 1 MNQ** (LIT + ATLAS) | $500 deposit, $12/mo data (free when funded), ~$2.00 round trip | **~2 sessions** to +$100 withdrawable [BT]; no payout rule, your own money [RULE] | **+$1,309 / -$393** (H2); +$1,564 / -$398 (H1); REF median **-$378** | 82% H2, 57% REF | **16% lose ~$400 in a month (H2), 57% in REF** [BT] | Yes, your own account [RULE] [NinjaTrader pricing](https://ninjatrader.com/pricing/) |
| 3 | **FundedNext Rapid Daily 50K** (fresh) | $149.99 (code RAPID; list $299.99) [RULE] | ~22 sessions (~31 days) [BT] + "99.99% within 24h" [RULE] | -$150 / -$150 (H2); mean **+$666**, best 10% +$3,090. H1 mean +$1,115 | 34% H2, 44% H1, 3% REF | fee only. NinjaTrader **not confirmed** | Yes [RULE] [FN bots article](https://helpfutures.fundednext.com/en/articles/14298560-is-the-usage-of-automated-trading-systems-eas-and-bots-allowed-in-fundednext-futures) |
| 4 | **FundedNext Rapid Daily 25K** (fresh) | $64.99 [RULE] | ~22 sessions [BT] + 24 h [RULE] | -$65 / -$65 (H2); mean ~+$360 (sim used a $100 price: +$325) | 31% H2, 45% H1, 4% REF | fee only; same NinjaTrader question | Yes, same source |
| 5 | **Live account, $300, 1 MNQ** | $300 + data | ~2 sessions [BT] | +$691 / -$205 (H2); REF median **-$191** | 62% H2 | **38% lose ~$160-200 (H2), 79% in REF**: one 84-point LIT stop is $168 [BT] | Yes [RULE] |

Next after the top 5: MFFU Builder 50K / 25K fresh (paid inside 30 days 15-24% [BT], first pay ~27-29 sessions), Lucid (13-15%, ~31 sessions), the Zlarior 50K eval we already have (57% pass inside 30 days, only 11-13% paid), and Rapid EOD 25K fresh (~1% paid inside 30 days, first pay ~43 sessions = 2 months; the 30% best-day eval rule makes it slow).

### Why ATLAS is #1 even though its median is $0
- It is the only option with zero cost and zero eval risk. It has to make +$949 in about 3 weeks. ATLAS made that in about half of H1-like months and a third of H2-like months.
- **Asking $250 instead of waiting for $1,000 helps very little.** Chance of a payout in 30 days rises from 24% to 36% (H2), the mean from $207 to $236 [BT]. But a $250 payout uses one of the four payouts we take before closing (fleet plan: never take the 5th). Over the account's life that costs up to $600 of cash. **Keep the $1,000 ask unless you need cash this month.**
- Running LIT on the ATLAS 25K as well gives 70% paid inside 30 days, median +$596 (H2) [BT]. But the chance of losing the funded account goes from 0.2% to 12% (65% in REF). That is a strategy change that needs your yes, and it is not recommended.

## (a) Bot-legal futures props with daily / fast payouts: today's rules

[O] = the firm's own page; [3P] = third-party / affiliate page. These pages returned 403 from here: Lucid's main FAQ, Bulenox, Apex, Take Profit Trader, and Topstep's automation article.

| Firm / plan | Bots for our unattended NinjaTrader bot | Payouts [RULE] | First $ for us [BT] | Verdict |
|---|---|---|---|---|
| **MFFU Rapid EOD 50K** | Yes [O] | daily, $500 min above the $2,100 buffer, then **$500 net since the last payout**, no cap, 90%; first eligible 24 h after the first funded trade; most approved instantly, otherwise 6-12 business hours [O] [Rapid EOD 50K](https://help.myfundedfutures.com/en/articles/16158363-rapid-eod-50k-a-comprehensive-look), [payout overview](https://help.myfundedfutures.com/en/articles/13745661-payout-policy-overview-best-and-fastest-prop-firm-payouts) | ~39 sessions (eval 30% best-day, 4 days) | the best monthly money (fleet plan), slow first $ |
| **FundedNext Rapid Daily** | Yes [O] | daily, from $500 cycle profit, cap $1,000 -> $1,250 (50K), no consistency, 90%, paid within 24 h [O] [Rapid page](https://fundednext.com/futures/rapid) | ~17-22 sessions | **fastest fresh prop**, if NinjaTrader works (the page names only Tradovate) |
| FundedNext Rapid Pro | Yes [O] | every 3 days, 40% funded best-day rule [O] | ~29-31 sessions | slower than Daily |
| **Lucid (Pro / Flex / Direct)** | Yes, bots and copiers [O] [permitted activities](https://intercom.help/lucid-trading/en/articles/11404728-permitted-activities); **NinjaTrader supported via CQG** [O] [platforms](https://intercom.help/lucid-trading/en/articles/11404614-lucid-trading-supported-platforms) | Flex: $500 min, 50% of profit up to $2,000 (50K), 5 days of $150+ a cycle, paid within 2 business days, live after 5 [O] [Flex payouts](https://support.lucidtrading.com/en/articles/12945796); Direct (instant): 20% consistency [O] | ~30-35 sessions | backup; the 5-winning-day cycle slows the first $ |
| Tradeify (Lightning instant / Select / Growth) | **Conditional, effectively no for us**: "sole owner of the bot", "We scan to ensure there are no similar orders on other accounts", the same bot at other firms "breaks policy" [O] [guidelines](https://intercom.help/tradeify/en/articles/10468318-guidelines-for-traders) | Lightning: $1,000 min, $3,000 goal first, 20-30% consistency [O] | - | **ruled out**: our bot runs at MFFU, so payouts would be at risk |
| Bulenox | Conditional: prior written approval [3P] | weekly (Wednesday), 10 trading days before the first payout, 40% rule [3P] | - | slow; needs approval |
| Topstep | Only through the TopstepX API; **no NinjaTrader for new Combines** [O] [platform change](https://help.topstep.com/en/articles/11667498-important-changes-to-topstep-supported-platforms) | 5 winning days of $150 per payout, $125 min, 1-3 business days [O] [payout policy](https://help.topstep.com/en/articles/8284233-topstep-payout-policy) | ~28-30 sessions (if ported) | ruled out until the bot is ported |
| Alpha Futures | **No**: "full automation is strictly forbidden" [O] [prohibited](https://help.alpha-futures.com/en/articles/9508585-prohibited-trading-practices) | - | - | banned |
| Apex | **No** (reported "no automation or algorithm usage", 2026-07-31) [3P] [source](https://blog.pickmytrade.trade/apex-funded-automation-rules-2026/) | - | sim looks good, but a ban means the payout gets denied | banned |
| Take Profit Trader | **No** [3P] [source](https://blog.traderspost.io/article/take-profit-trader-review) | PRO+ daily [3P] | - | banned |
| Elite Trader Funding / Earn2Trade | written authorisation only / sources conflict [3P] | - | - | not worth it |

## (b) A $200-$500 live account trading 1 MNQ

| Item | Value | Source |
|---|---|---|
| Minimum deposit | any amount > $0 ($5 ACH minimum) | [RULE] [NinjaTrader pricing](https://ninjatrader.com/pricing/) |
| MNQ intraday margin | **$100** (overnight $4,647: never hold) | [RULE] [NinjaTrader margins](https://ninjatrader.com/pricing/margins/); AMP is also $100 [AMP](https://www.ampfutures.com/trading-info/margins) |
| Commission | $0.39 a side on the Free plan, plus $0.19 clearing and exchange / NFA fees. **We used $2.00 a round trip** (not verified to the cent) | [RULE] [account fees](https://ninjatrader.com/pricing/account-fees/) |
| Data / platform | CME Level I $12 a month, "free when your account is funded"; $35 a month inactivity fee on the Free plan | [RULE] same page |
| Bots | allowed (your own money) | [RULE] |
| $ in 30 days, $500 / $300 | median +$1,309 / +$691 (H2), +$1,564 / +$537 (H1), **REF -$378 / -$191** | [BT] live30_rt2.json |
| Risk of ruin in 30 days (balance under $140, can't trade) | $500: 16% H2, 20% H1, **57% REF**. $300: 38% / 45% / **79%** | [BT] |
| $ a month, 1 MNQ, no ruin (all trades) | H2 about $1,600 a month (LIT $2,838 + ATLAS $3,096 over 78 sessions); REF about $120 a month | [BT] trade lists |

Blunt notes:
- At $200-300 a single LIT stop (median 52 points = $104, max 84 = $168) takes half the account. **$500 is the smallest size that survives a normal losing streak.**
- The sim skips a trade when margin + its stop doesn't fit. It doesn't model LIT and ATLAS being in a trade at the same time (that would need 2 micros, $200 margin). Real results would be a bit lower.
- This is the only option that pays in days. It is also the only one where a bad month takes real money, not just a fee. MFFU's rules say nothing about running a personal account beside its accounts, but **hedging across accounts is banned** (ACCOUNT_RULES), so the live account must never be opposite a prop account.

## (c) Crypto props and CME micro BTC / ETH

- **Our bots don't trade crypto.** LIT and ATLAS are NQ strategies with no BTC/ETH backtest. Any crypto number would be made up, so there is none here. That rules crypto out for "fastest cash with OUR bots".
- HyroTrader: bots allowed if the strategy is your own, 12-48 h payouts in USDT/USDC, 80-90% split; some 2026 complaints of denied payouts and IP bans [O blog / 3P] ([HyroTrader](https://www.hyrotrader.com/blog/prop-firms-that-allow-bots/), [review](https://fundedtrading.com/propfirm/hyrotrader/)). **The most legitimate of the crypto props, still not proven.**
- Breakout (Kraken): its own terminal only, unclear on bots [3P]. Bitfunded: mixed, delayed payouts [3P]. **Crypto Fund Trader: avoid** (FINMA warning 2024, payout denials) [3P] ([source](https://coincodecap.com/crypto-fund-trader-review)).
- CME Micro Bitcoin / Ether (MBT / MET) on futures props: Topstep lists them [O] ([Topstep](https://www.topstep.com/blog/new-permitted-products-offered-at-topstep/)), but no NinjaTrader there. MFFU, FundedNext and Lucid are not confirmed. **Verdict: no.**

## (d) Faster cash from our current MFFU accounts (within the rules)

Today's balances (board 2026-11-23 10:12 ET): ATLAS 25K funded +$401; Zlarior 50K eval $49,214 ($3,786 to pass, $1,046 room); 25K #2 eval $25,024; Rapid EOD 25K eval $25,000 (fresh).

| Account | Rule that gates the first $ [RULE] | 30-day result [BT] (H2 / H1 / REF) | Faster, inside the rules? |
|---|---|---|---|
| ATLAS 25K funded | $250 min above the $1,100 buffer (MFFU profit >= $1,350), 2 traded days, best day <= 50%, 80% split, $1,000 max; 48 h after the first funded trade ([Builder 25K / payout overview](https://help.myfundedfutures.com/en/articles/13745661-payout-policy-overview-best-and-fastest-prop-firm-payouts)) | paid 24% / 54% / 7% with the $1,000 ask; 36% / 56% / 7% with the $250 ask | the $250 ask is slightly faster but costs payout slots (above): keep $1,000 |
| Zlarior 50K eval -> Builder 50K funded | pass $53,000; funded $500 min above the $2,100 buffer, $2,000 max, 50% best day, 80% ([Builder 50K guide](https://help.myfundedfutures.com/en/articles/14290805-builder-plan-50k-a-comprehensive-guide)) | pass 57% / 64% / 11%; paid inside 30 days 11-13% / 13% / 0.4%; ask $500 vs $2,000 = +1-2 points | no: the eval is the bottleneck |
| 25K #2 eval -> Builder 25K | pass $26,500, then as ATLAS | pass 72% / 73% / 21%; paid inside 30 days 20% / 21% / 1% | no |
| Rapid EOD 25K eval -> funded | eval best day <= 30%, 4 days; funded daily, $500 min above the $1,100 buffer, $250 net since the last, 90%, news window banned ([Rapid EOD 25K](https://help.myfundedfutures.com/en/articles/16727601-rapid-eod-25k-a-comprehensive-look)) | pass 30% / 14% / 2%; paid inside 30 days ~1% | no: the 30% eval rule takes ~27 sessions to pass |

Bottom line for (d): the only lever that changes 30-day cash is the payout ask on ATLAS, and it isn't worth it. **The real speed-up is keeping the bot running every session** (the 7-day inactivity rule plus the STALE PC on today's board: a silent PC is $0).

## Recommended plan: $150 budget, this week

1. **$0 - keep ATLAS 25K and the three evals running every session.** Fix the PC that went silent at 10:12 ET today first: that is the cheapest dollar.
2. **$149.99 - one FundedNext Rapid Daily 50K, only after a written yes on NinjaTrader.** Ask support: "Can I trade a Futures Rapid account from NinjaTrader 8 with my own automated strategy?" If yes, buy with code RAPID (or a Black Friday code if it is cheaper at checkout). This matches the fleet plan's $150 pick (FundedNext 50K first). Expected [BT]: pass in about 7 sessions; first payout after a median 22 sessions; 34% chance of cash inside 30 days; mean +$666 net by day 30; worst case -$150.
3. **If FundedNext says no: buy nothing new this week.** Keep the $150 toward a $500 live account later, or toward the Rapid EOD 50K on the fleet plan. Don't open a $150 live account: one LIT stop is $104-168.

What would change this: if 2026's edge fades (the REF rows), every option loses about its fee in a month and the live account loses real money. That is the risk you are signing up for.

## Method and caveats

- Engine: research/plans/rank.py (the fleet plan's real-fills engine). It runs LIT + ATLAS at their live sizing, ATLAS at 10-tick fills, commissions $1.90 a micro, the MFFU news window on Rapid funded. The MC draws whole weeks of each span, 1,000 paths, seed 31 / 41. Fresh accounts: no re-buy inside the 30 days.
- Prices used [RULE unless marked]: FN 50K $149.99, FN 25K $64.99 (the sim used $100), MFFU at the owner's prices, Lucid $126 (assumed), Topstep $49 (activation fee not counted), Apex $35 (Apex and Topstep are shown only for comparison: banned or no NinjaTrader).
- Payout processing days (FN 24 h, MFFU instant-12 h, Lucid 2 business days, Topstep 1-3 business days) are added in words, not in the sim.
- Not modelled: payout denial, the 48 h first-trade wait on Builder funded, LIT and ATLAS concurrency on 1 MNQ.
