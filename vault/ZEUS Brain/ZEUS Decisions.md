---
tags:
  - zeus/decisions
type: "decisions"
---

# ZEUS Decisions

> [!question] 2 open
> Answer on the Decide card (Business app). A yes means Claude tests it; nothing live changes without proof.

## Open

> [!question] Fast entry: send Zlarior's and ATLAS's orders on the minute's first trade instead of waiting 2 seconds?
> **Why:** Every real entry so far filled worse than the backtest (ATLAS 10-16 ticks, Zlarior 4) because price runs in the 2.7 s before the order arrives; 2.0 s of that is a built-in wait. Fast entry cuts it to ~0.85 s. Same trades, same sizes, only sooner.
> **Impact:** $0 to ~$160 a month (central ~$100: ATLAS ~5 ticks and Zlarior ~1 tick better per entry); not provable from 1-minute bars, so it is a 2-week test that the fills will settle.
> Added 2026-11-20 · write-up [[nq-speed-fills-2026-11-20|NQ bot speed and fills]] · id `fast-entry`
> Card: [[Decide fast-entry|open the card note]]

> [!question] Rapid EOD 50K ($165): buy it with a hard stop of at most 2 re-buys (3 evals in all, max $495 at risk)?
> **Why:** Best plan in the ranking: daily payouts, 90%, no payout cap. MFFU's own pages (2026-11-22) say the '5 payouts then live' rule is Builder only; a Rapid goes live only at $10,000 in one day or by MFFU's choice.
> **Impact:** About +$2,282 a month in a Jul-Oct-like market (+$5,001 Jan-Jun-like) over 6 months from one account; first payout ~9 weeks after the buy (median). Same purchase as card buy-rapid50-now, plus the re-buy stop.
> Added 2026-11-22 · write-up [[plan-ranking-2026-11-22|Plan ranking]] · id `plan-rapid50k-max2-rebuys`
> Card: [[Decide plan-rapid50k-max2-rebuys|open the card note]]

## Yes

> [!success]- Rapid EOD: ATLAS trades it next to Zlarior from day one?
> **Why:** On the Rapid 25K the 30% best-day rule skips most of Zlarior's trades. Launch check 2026-11-20 at real fills: LIT alone passes the eval in only 25-42% of runs within 60 trading days, ATLAS alone 49-64%, both together 81-86% (median 26-33 days).
> **Impact:** At real fills (ATLAS 10 ticks a side): +$609 a month in a Jul-Oct-like market (+$1,662 Jan-Jun-like, -$28 2021-25-like); first payout about Feb 18 with ATLAS, while without it half the runs see no payout in 6 months. At backtest fills it was +$817 a month (+$2,084 Jan-Jun-like, +$7 2021-25-like).
> Added 2026-11-16 · write-up [[stack-one-account-2026-11-16|More strategies on ONE MFFU account]] · id `atlas-on-rapid`
> Card: [[Decide atlas-on-rapid|open the card note]]

> [!success]- Ask MFFU to say yes in writing: a 2nd Builder 50K and a 2nd 25K eval while the current ones run?
> **Why:** Their rules allow 10 evals, but a written yes protects the payouts if they ever question it.
> **Impact:** Free to ask. A written yes lets you run a fresh Builder 50K ($91.80) next to Zlarior's: +$56 a month Jul-Oct-like (+$53 Jan-Jun-like, -$6 2021-25-like), the 50K's first payout about 8 trading days sooner. It also protects every payout from a rules dispute.
> Added 2026-11-17 · write-up [[mffu-rules-audit-2026-11-17|MFFU rules audit]] · id `ask-mffu-parallel`
> Card: [[Decide ask-mffu-parallel|open the card note]]

> [!success]- Let the cloud watch your PC (a tiny free check every 30 min on the backup GitHub repo) so you get a push if the PC goes silent?
> **Why:** The PC-silent alert is built but needs a cloud runner; the old GitHub account's Actions are off since the suspension. The backup repo's free minutes cover it (~700 of 2,000 a month).
> **Impact:** $0 (free minutes). Catches a dead PC within 30 min instead of days (it was silent Nov 7-17 unnoticed).
> Added None · id `cloud-alerts`
> Card: [[Decide cloud-alerts|open the card note]]

> [!success]- ATLAS's funded 25K: risk 40% of the room a trade instead of 60% (safer, but the first payout comes later)?
> **Why:** The bot stops ATLAS for good once the funded room is under $100. Smaller trades make that rarer, but each win is smaller, so payouts come later.
> **Impact:** At real fills (10 ticks a side): +$24 a month in a Jan-Jun-like market ($503 -> $527), -$9 Jul-Oct-like ($402 -> $393), -$3 2021-25-like; first payout 3-8 trading days later (Dec 29 instead of Dec 23 Jan-Jun-like; Jan 19 instead of Jan 7 Jul-Oct-like). At backtest fills it was -$26 a month, 5 trading days later.
> Added 2026-11-19 · write-up [[atlas-health-2026-11-18|ATLAS health]] · id `atlas-funded-room-40`
> Card: [[Decide atlas-funded-room-40|open the card note]]

> [!success]- Business page: drop 'Account #4 = LucidPro 50K' and show your MFFU next buys instead (Rapid EOD 25K now, then a fresh Builder 50K and a Rapid EOD 50K from payouts)?
> **Why:** You said MFFU only, and your next buy is the Rapid EOD 25K, but the Business page still plans a LucidPro 50K as account #4 (an older plan from Nov 14).
> **Impact:** $0 by itself (a page fix). For comparison, Jul-Oct-like: the Rapid EOD 25K you buy now is about $1,005 a month, the Rapid EOD 50K from payouts about $1,969 a month; the page's LucidPro line said about $810 a month (an older, non-MFFU estimate).
> Added 2026-11-19 · id `drop-lucid-account4`
> Card: [[Decide drop-lucid-account4|open the card note]]

> [!success]- ATLAS's funded 25K: keep trading 1 micro when the room drops under $100, instead of stopping for good?
> **Why:** Today the bot gives the funded account up at $100 of room. Small 1-micro trades that still fit can climb back: about 1 in 5 such accounts recover in a 2026-like market.
> **Impact:** +$3 a month in a Jul-Oct-like market (+$10 Jan-Jun-like, +$4 2021-25-like); chance of losing the account in 6 months 10.5% -> 9.5% (9.8% -> 7.7% Jan-Jun-like); first payout unchanged. At real fills (10 ticks a side): +$6 a month Jul-Oct-like (+$14 Jan-Jun-like, +$1 2021-25-like); chance of losing the account 23.5% -> 21.7% (20.3% -> 17.6% Jan-Jun-like); first payout unchanged.
> Added 2026-11-19 · write-up [[atlas-more-money-2026-11-19|ATLAS more money]] · id `atlas-funded-keep-trading`
> Card: [[Decide atlas-funded-keep-trading|open the card note]]

> [!success]- ATLAS's funded 25K: after 2 losing trades in a row, trade 1 micro until the next win?
> **Why:** A losing streak is what drains the $887 room and closes the account. Shrinking to 1 micro during a streak keeps most of the money and loses the account far less often.
> **Impact:** At real fills (10 ticks a side), from today's account: -$22 a month in a Jan-Jun-like market ($503 -> $481), +$6 Jul-Oct-like ($402 -> $408), -$1 2021-25-like; first payout about a week later (Dec 30 instead of Dec 23 Jan-Jun-like; Jan 12 instead of Jan 7 Jul-Oct-like). With room 40% also on: $478 / $394 a month.
> Added 2026-11-20 · write-up [[atlas-edge-2026-11-20|ATLAS edge at real fills]] · id `atlas-funded-streak-1micro`
> Card: [[Decide atlas-funded-streak-1micro|open the card note]]

> [!success]- Rapid 25K: size ATLAS for its real fills (assume a 10-tick worse stop)?
> **Why:** ATLAS's real fills are ~10 ticks worse than its backtest, so a full stop costs up to a third more than planned and can push the day past MFFU's $500 pause.
> **Impact:** -$31 a month in a Jul-Oct-like market (-$141 Jan-Jun-like, +$4 2021-25-like); fewer Rapids lost; same first payout date.
> Added 2026-11-20 · write-up [[rapid-launch-2026-11-20|Rapid EOD 25K launch check]] · id `rapid-atlas-size-10t`
> Card: [[Decide rapid-atlas-size-10t|open the card note]]

## No

> [!failure]- Funded 25K: ask for the full $1,000 payout (at balance $27,100) instead of pinging you at $750?
> **Why:** The bot pings you when $750 sits above the $1,100 buffer; waiting for the full $1,000 (balance $27,100) means fewer, bigger requests.
> **Impact:** -$9 a month in a Jul-Oct-like market (-$11 Jan-Jun-like, -$6 2021-25-like); first payout about 2 trading days later. At real fills on ATLAS's 25K (10 ticks a side): about the same money (+$8 a month Jan-Jun-like, -$1 Jul-Oct-like), lost in 6 months 21.7% -> 20.7% (17.6% -> 16.0%), first payout 2-3 trading days later; with room 40% it adds almost nothing (14.0% -> 13.1%).
> Added 2026-11-17 · write-up [[payout-policy-funded25-2026-11-17|Funded Builder 25K payout policy]] · id `payout-ping-1000`
> Card: [[Decide payout-ping-1000|open the card note]]

> [!failure]- Funded 25K: Zlarior (LIT) trades it too, next to ATLAS?
> **Why:** Two strategies on ATLAS's funded 25K: more trades and a sooner first payout, but bigger swings on a $1,000 floor.
> **Impact:** +$125 a month in a Jul-Oct-like market (+$141 Jan-Jun-like, -$26 2021-25-like); first payout about 7 trading days sooner.
> Added 2026-11-17 · write-up [[funded25-lit-atlas-2026-11-17|ATLAS's funded Builder 25K]] · id `zlarior-funded25`
> Card: [[Decide zlarior-funded25|open the card note]]

## Later

> [!note]- Zlarior's Builder 50K: ATLAS trades it too (one position at a time, first bot in keeps it; ATLAS at half its size until the eval passes, full size once funded)?
> **Why:** Best of 12 rule sets fixed before testing: it keeps most of the extra money and halves the evals that die in 2 weeks (9% -> 4% Jul-Oct); it beat Zlarior alone in Jan-Jun, Jul-Oct and 2021-25, with MFFU's move to live after payout 5 counted.
> **Impact:** +$696 a month in a Jul-Oct-like market (+$392 if the live account after payout 5 is worth nothing), +$1,649 Jan-Jun-like (+$466), +$26 2021-25-like; 2022-like -$141; after the extra eval fees.
> Added 2026-11-19 · write-up [[one-account-combo-final-2026-11-19|One account, Zlarior + ATLAS on the Builder 50K]] · id `zlarior-atlas-50k`
> Card: [[Decide zlarior-atlas-50k|open the card note]]

> [!note]- Big idea: run a free 30-day test of a 'Prop Slot Planner' page for other prop traders (faceless brand, no name), plus 1 short video a day?
> **Why:** Bot income depends on the market (about $0 in a 2021-25-like market). The one thing no prop tool sells yet is our planner: which account to buy next, when, and what you keep after tax.
> **Impact:** Bear $0, base ~$600/mo by month 6, bull ~$3,900/mo by month 12; 3-6 of your hours a week (the videos). Kill it if there are under 300 visits, 30 emails or 3 pre-orders in 30 days; go at 10+ pre-orders.
> Added 2026-11-20 · write-up [[huge-idea-2026-11-20|The "huge idea" check]] · id `copilot-test`
> Card: [[Decide copilot-test|open the card note]]

> [!note]- Kalshi K8 live from Monday: bet only the 2 gold windows (drop silver 4:45 PM) to make the bot switching itself off rarer?
> **Why:** The newest week (Nov 16-20) was the worst of 16 (6 of 15 won). Gold-only trips the stops about 4x less often, but silver also made money in the history (74% won, +$0.92 a bet).
> **Impact:** About -$4 a week: +$12.23 -> +$8.02 a week as in the history (+$6.17 -> +$3.97 if the edge is 10 points weaker); after 4 weeks $103 -> $88 on average.
> Added 2026-11-21 · write-up [[kalshi-k8-live-2026-11-21|K8 goes live Monday]] · id `kalshi-k8-gold-only`
> Card: [[Decide kalshi-k8-gold-only|open the card note]]

## Done

> [!note]- Zlarior's 50K: ATLAS trades it too once it is funded (the eval stays Zlarior alone)?
> **Why:** Two strategies give about 2 winning days a week instead of 1, which the payout rules need. ATLAS in the eval fails more, so funded only.
> **Impact:** +$451 a month in a Jul-Oct-like market (+$422 Jan-Jun-like, +$2 2021-25-like); first payout about 9 trading days sooner.
> Added 2026-11-16 · write-up [[stack-one-account-2026-11-16|More strategies on ONE MFFU account]] · id `atlas-on-50k-funded`
> Card: [[Decide atlas-on-50k-funded|open the card note]]

> [!note]- Kalshi K8: start at $8 a bet (not $15) and step up with the cash: $10 from $67, $15 from $100?
> **Why:** $15 a bet on $55 means 3 losses in a row (the test had a streak of 8) leave too little to bet. Betting about 15% of the cash keeps the pot alive while it grows.
> **Impact:** Chance the $55 is wiped out in the first 4 weeks: 7.9% -> 0.2% as tested, 24.8% -> 3.3% if the edge is half as good; median after 4 weeks $467 -> $430 (-$37) if the edge holds.
> Added 2026-11-20 · write-up [[money-ideas-2026-11-20|Money ideas]] · id `kalshi-stake-ladder`
> Card: [[Decide kalshi-stake-ladder|open the card note]]

## Superseded

> [!note]- Rapid 25K: Zlarior trades 1 micro and takes profit at the day's room (instead of skipping most trades)?
> **Why:** MFFU closes a Rapid that goes 7 days without a trade, and the 30% best-day guard makes the Rapid 25K skip most trades: the red team's replay of Nov 6-19 traded it on 1 day in 10. With this lane on, the same days traded on 4. In the simulation 56% / 44% of evals (Jan-Jun / Jul-Oct-like) hit 5 trading days without a trade as built; 22% / 9% with it.
> **Impact:** With MFFU's 7-day inactivity close counted: +$164 a month in a Jul-Oct-like market (+$363 Jan-Jun-like, +$4 2021-25-like); the eval passes in 71% / 90% of runs instead of 41% / 54%; first payout about 3 weeks sooner (Feb 5-9 vs Feb 24-26).
> Added 2026-11-18 · write-up [[rapid25-pass-2026-11-21|Rapid EOD 25K]] · id `rapid25-lit-bank`
> Card: [[Decide rapid25-lit-bank|open the card note]]

> [!note]- Rapid funded payouts: always leave $1,000 above the buffer in each Rapid?
> **Why:** Leaving more in the Rapid after each payout gives the bot more room, so fewer funded accounts get stuck; each payout is smaller and comes later.
> **Impact:** About $0 on its own: -$18 a month in a Jul-Oct-like market (+$49 Jan-Jun-like, -$2 2021-25-like); first payout about 1-2 weeks later.
> Added 2026-11-16 · write-up [[rapid-funded-refit-2026-11-21|Rapid EOD funded refit]] · id `keep-1000-rapid`
> Card: [[Decide keep-1000-rapid|open the card note]]

> [!note]- Buy the 5th funded slot (Rapid EOD 50K, $165 with CLUB) now from your pocket, instead of waiting for ATLAS's first payout (about Jan 13)?
> **Why:** MFFU allows 5 funded accounts; you hold 4. The Rapid EOD 50K is the biggest earner in the plan, and every week it waits is a week it is not passing its eval.
> **Impact:** After MFFU's cut, fees and the 30% tax pot: +$554 a month to Jun 30 in a Jul-Oct-like market (+$164 if the edge halves, -$80 2021-25-like); Dec-Feb in total +$2,673 / +$514 / -$225.
> Added 2026-11-21 · write-up [[fleet-90day-2026-11-21|The 90-day money machine]] · id `buy-rapid50-now`
> Card: [[Decide buy-rapid50-now|open the card note]]

> [!note]- When a Builder 25K dies (ATLAS's funded 25K lost, or the 25K #2 eval fails), put a Rapid EOD 50K ($165) in that slot instead of a new $63 Builder 25K?
> **Why:** A Builder 25K slot earns a few hundred a month; a Rapid EOD 50K slot earns several times that. MFFU allows 3 Rapid EOD 50Ks, so the swap fits the caps.
> **Impact:** After MFFU's cut, fees and the 30% tax pot: +$249 a month to Jun 30 in a Jul-Oct-like market (+$126 if the edge halves, -$72 2021-25-like); Dec-Feb in total +$43 / +$12 / -$173.
> Added 2026-11-21 · write-up [[fleet-90day-2026-11-21|The 90-day money machine]] · id `refill-25k-with-rapid50`
> Card: [[Decide refill-25k-with-rapid50|open the card note]]

> [!note]- Buy a 2nd Builder 50K eval now ($91.80) next to Zlarior's, running the same LIT signal (only the first to pass becomes the funded 50K)?
> **Why:** MFFU's public pages allow parallel evals (10 at once; the funded caps apply on the pass), so you don't need the written yes. Two tries at the 50K = it is funded sooner.
> **Impact:** After MFFU's cut, fees and the 30% tax pot: +$63 a month to Jun 30 in a Jul-Oct-like market (+$8 if the edge halves, -$5 2021-25-like); Dec-Feb in total +$479 / +$115 / +$32.
> Added 2026-11-21 · write-up [[fleet-90day-2026-11-21|The 90-day money machine]] · id `second-50k-eval-now`
> Card: [[Decide second-50k-eval-now|open the card note]]

## Waiting

> [!note]- Rapid funded: let a winner pay up to $2,000 on the 25K ($4,000 on a 50K) and keep $1,000 ($2,000) in the account?
> **Why:** The Rapid funded presets copied the Builder's winner cap ($1,000 / $2,000), made for the Builder's 50% consistency and $2,000 payout cap. MFFU's Rapid EOD funded has neither. A bigger cap pays more; keeping more in the account stops it losing more.
> **Impact:** Rapid 25K: +$314 a month in a Jul-Oct-like market (+$541 Jan-Jun-like, -$1 2021-25-like). A Rapid 50K (once bought): +$647 / +$1,460 / +$4.
> Added 2026-11-21 · write-up [[rapid-funded-refit-2026-11-21|Rapid EOD funded refit]] · id `rapid-funded-refit`
> Card: [[Decide rapid-funded-refit|open the card note]]

> [!note]- FundedNext Rapid Daily 50K (~$150 with code RAPID): add one, with at most 2 re-buys (max $450 at risk)?
> **Why:** Second best in the ranking and a different firm (MFFU limits: 5 sim funded, and a live move pauses every MFFU sim account). FundedNext allows copying the same strategy across firms under your name.
> **Impact:** About +$1,546 a month in a Jul-Oct-like market (+$1,679 Jan-Jun-like) over 6 months; first payout ~5 weeks after the buy (median); payouts max $1,200 each, 5 per account.
> Added 2026-11-22 · write-up [[plan-ranking-2026-11-22|Plan ranking]] · id `plan-fundednext50k-max2-rebuys`
> Card: [[Decide plan-fundednext50k-max2-rebuys|open the card note]]

> [!note]- LucidPro 50K: add up to 3 on top of the Rapid EOD 50K + FundedNext 50K plan, and raise the monthly eval budget from $300 to $500?
> **Why:** Same bots (LIT) on more accounts at a third firm, outside MFFU's caps and live-move risk. Paper test (fleet v2, 75 fleets x 3 spans x 1,000 paths): beats the $300 plan in both 2026 halves, also if the Lucid price is $50 higher.
> **Impact:** vs the $300 plan, 6 months: about +$1,786 a month (Jan-Jun-like) / +$2,215 a month (Jul-Oct-like); $70k about 1.5 months sooner in Jul-Oct-like (6.9 vs 8.4 months). About half is just the extra $200 a month of budget; the 3 Lucid accounts add +$5.9k / +$9.4k over 6 months on top of a $500 plan with none.
> Added 2026-11-22 · write-up [[fleet-v2-2026-11-22|Fleet v2]] · id `lucid-3-at-500-budget`
> Card: [[Decide lucid-3-at-500-budget|open the card note]]

Back to [[ZEUS Home]]
