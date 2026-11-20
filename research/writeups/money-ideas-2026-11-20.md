# Money ideas (2026-11-20, night-moneyideas)

Paper research only. Nothing live changed. MFFU only, owner's real prices (CLUB 40%: Builder 50K $91.80, 25K $63,
Rapid EOD 25K $97.20, Rapid EOD 50K $165). "$ a month" = to you after fees and MFFU's cut, before the 30% tax pot,
in a Jul-Oct 2026-like market unless it says otherwise. In a 2021-25-like market the NQ bots earn about $0, so every NQ
number below can be $0.

## Plain words first
1. **Answer 4 Decide cards (5 minutes): about +$1,650 a month.** The open cards Claude recommends YES: ATLAS on the Rapid
   (+$817), ATLAS + Zlarior on the funded 50K (+$696), the Rapid 25K LIT bank rule (+$83), ask MFFU about a parallel eval
   (+$56). 2021-25-like: about +$34. Nothing else on this list pays this much per minute.
2. **The 5th funded slot must be the Rapid EOD 50K, never a 2nd Rapid 25K.** MFFU allows 5 funded accounts in all. Zlarior
   50K + ATLAS 25K + 25K #2 + the Rapid 25K hold 4 (an eval holds its slot because it will try to fund). A 2nd Rapid 25K
   ($97.20) fits the $150 round, but it would take the last slot: about $972 a month instead of $2,812 = **-$1,840 a month
   for good**. Pay the $165 from kept payouts (the goals plan: ~Dec 24). Built: `money_book.next_buy` refuses that mistake.
3. **Kalshi: start K8 at $8 a bet, not $15.** $15 on $55 = 3 losses in a row and the pot is too small to bet. Ladder with
   the K8 page's own picks: $8 from $53, $10 from $67, $15 from $100. On the stored bets: chance the $55 is wiped out in 4
   weeks **7.9% -> 0.2%** as tested, **24.8% -> 3.3%** if the edge is half as good; median after 4 weeks $467 -> $430. New
   Decide card `kalshi-stake-ladder` (recommend yes; no code change: you pick $8 on the page).
4. **An eval dies -> buy the same plan again that night, not a reset, not "after the weekend".** A funded slot is worth about
   $17 (25K) to $134 (Rapid 50K) a trading day; MFFU publishes no reset price for one-time plans and a reset doesn't extend
   the account. Built: `money_book.dead_eval` (3 steps, checks money and slot).
5. **Holiday sale codes are usually WORSE than CLUB.** The only past MFFU holiday code found (CYBER25, Nov 2025, aggregator,
   not confirmed) was 30% off; CLUB is 40%. A 30% code costs $10 (Builder 25K) to $28 (Rapid 50K) more. Use a code only if it beats
   40%; don't delay a buy waiting for Black Friday. Built: `money_book.best_price` flags codes worse than CLUB.
6. **Eval fees lower the tax.** The 30% pot is 30% of payouts, but tax is on profit after costs, so the pot over-holds about
   30% of every fee: ~$95 on tonight's four accounts ($315 of fees). Keep every MFFU receipt; after the Jan 15, 2027 estimate
   is paid, the over-held part can fund the next eval. Education, not tax advice. Built: `money_book.tax_true_up`.

## All ideas, ranked by $ a month per hour of your time
| # | Idea | $ impact (range) | Risk | Your effort | State |
|---|---|---|---|---|---|
| 1 | Answer the 4 recommended-YES Decide cards | +$1,650/mo (+$34 2021-25-like; +$3,800 Jan-Jun-like) | cards list their own risks | 5 min | cards open |
| 2 | 5th slot = Rapid 50K, not a 2nd Rapid 25K | +$1,840/mo vs the mistake | none | 0 | BUILT (rule) |
| 3 | Kalshi $8 start + ladder | avoids an 8-25% chance of losing the $55 and K8's $390-590/mo; -$37 median in 4 wks if all goes well | slower start | 1 tap | BUILT + card |
| 4 | Dead eval: re-buy same night | +$17 to +$134 per trading day sooner | none | 10 min per event | BUILT |
| 5 | Never buy an eval with no funded slot to land in | saves $63-165 each | none | 0 | BUILT (slots) |
| 6 | Code vs CLUB check before every buy | +$10-28 per buy | none | 1 min | BUILT |
| 7 | Tax pot true-up for fees | ~30% of fees back (~$95 now) once a year | under-holding if a fee isn't a real cost | 10 min a quarter | BUILT |
| 8 | Kalshi sweep: the bot never bets over $15, so cash above ~$150 doesn't grow; move the extra out monthly, 30% to the pot | protects winnings; $0 growth cost | none | 5 min a month | rule only |
| 9 | Kalshi winnings are taxable too: 30% of every Kalshi withdrawal to the pot | avoids a surprise bill | none | 1 min | rule only |
| 10 | Christmas week inactivity: 7 calendar days with no trade on a funded account = profits lost. Dec 25 and Jan 1 are closed, Dec 24 is a half day. The bot warns from day 5; on that push, decide the same day | protects $887-2,000 of funded profit | rare | 2 min if it fires | warning exists |
| 11 | 2nd Builder 50K eval: only after MFFU answers (can't fund while Zlarior's 50K is funded) | +$56/mo (card) | wasted $91.80 if MFFU says no | 5 min email | card open |
| 12 | Same LIT signals on more evals (copy trading is allowed) | $0: every funded slot is already planned; extra evals die together (16% both, lit_two_evals) | fee drain | - | rejected |
| 13 | Re-test "promising, not proven" research | nearest miss (London build-up x1.25) +$14/mo and failed eval H1; 1,000+ cells already rejected | - | - | not worth a test tonight |

## Proof notes
- Kalshi: `tools/money/kalshi_bankroll.py` -> `research/lab/kalshi_bankroll.json`. The 3 LIVE legs (gold 05:30 down, gold
  17:00 up, silver 17:00 up), 105 held-out bets (Oct 1-Nov 18, 76.2% won, break-even 52.6%) and 128 earlier bets (Aug-Sep);
  fee and real entry price in each bet. Whole days resampled (a day's 3 bets move together), 20 trading days, 20,000 paths,
  $55 start, bust = under $5. "Half edge" / "no edge" flip wins to losses until the win rate is halfway to / at break-even.

| Rule (bust % / median after 4 weeks) | As tested | Aug-Sep bets | Half edge | No edge |
|---|---|---|---|---|
| Flat $15 (Monday's plan) | 7.9% / $467 | 12.3% / $319 | 24.8% / $244 | 65.9% / $2 |
| Flat $8 | 1.4% / $277 | 2.5% / $199 | 8.4% / $165 | 43.1% / $40 |
| **Ladder $8 -> $10 -> $15** | **0.2% / $430** | **0.5% / $276** | **3.3% / $207** | **29.0% / $40** |

  Book depth is not the limit at these sizes (median ~3,000 contracts on our side in the first 45 s); the bot's own $15 hard
  cap is, so growth turns linear once the cash passes $100. The live legs were picked with the held-out months in view, so
  read "half edge" as the honest case.
- MFFU caps: research/lit/mffu_rules.json (5 sim funded; Builder 50K 1, 25K 2, Rapid EOD 50K 3; 10 evals) + MFFU help
  article 16727601 (Rapid EOD 25K: 3). Slot $: rapid-25k-vs-50k-2026-11-17.md (Rapid 50K $2,812 / 25K $972 Jul-Oct),
  eval-cost.md (Builder 50K $818 / 25K $352 H2).
- Tests: `python -X utf8 -m tests.test_money_ideas` (17 checks; area `money`).
