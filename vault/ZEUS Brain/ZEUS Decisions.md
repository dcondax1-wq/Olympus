---
tags:
  - zeus/decisions
type: "decisions"
---

# ZEUS Decisions

> [!question] 10 open
> Answer on the Decide card (Business app). A yes means Claude tests it; nothing live changes without proof.

## Open

> [!question] Funded 25K: ask for the full $1,000 payout (at balance $27,100) instead of pinging you at $750?
> **Why:** The bot pings you when $750 sits above the $1,100 buffer; waiting for the full $1,000 (balance $27,100) means fewer, bigger requests.
> **Impact:** -$9 a month in a Jul-Oct-like market (-$11 Jan-Jun-like, -$6 2021-25-like); first payout about 2 trading days later. At real fills on ATLAS's 25K (10 ticks a side): about the same money (+$8 a month Jan-Jun-like, -$1 Jul-Oct-like), lost in 6 months 21.7% -> 20.7% (17.6% -> 16.0%), first payout 2-3 trading days later; with room 40% it adds almost nothing (14.0% -> 13.1%).
> Added 2026-11-17 · write-up [[payout-policy-funded25-2026-11-17|Funded Builder 25K payout policy]] · id `payout-ping-1000`
> Card: [[Decide payout-ping-1000|open the card note]]

> [!question] Funded 25K: Zlarior (LIT) trades it too, next to ATLAS?
> **Why:** Two strategies on ATLAS's funded 25K: more trades and a sooner first payout, but bigger swings on a $1,000 floor.
> **Impact:** +$125 a month in a Jul-Oct-like market (+$141 Jan-Jun-like, -$26 2021-25-like); first payout about 7 trading days sooner.
> Added 2026-11-17 · write-up [[funded25-lit-atlas-2026-11-17|ATLAS's funded Builder 25K]] · id `zlarior-funded25`
> Card: [[Decide zlarior-funded25|open the card note]]

> [!question] Rapid 25K: Zlarior trades 1 micro and takes profit at the day's room (instead of skipping most trades)?
> **Why:** Today the 30% best-day guard skips 60-65% of Zlarior's trades there. Banking at the room passes and pays sooner, but fails a little more.
> **Impact:** +$83 a month in a Jul-Oct-like market (+$10 Jan-Jun-like, +$7 2021-25-like); first payout about 5 trading days sooner.
> Added 2026-11-18 · write-up [[rapid25-lit-lane-2026-11-18|Rapid EOD 25K]] · id `rapid25-lit-bank`
> Card: [[Decide rapid25-lit-bank|open the card note]]

> [!question] Rapid EOD: ATLAS trades it next to Zlarior from day one?
> **Why:** On the Rapid 25K the 30% best-day rule skips most of Zlarior's trades: alone it passes in about 42 trading days, with ATLAS about 25.
> **Impact:** At real fills (ATLAS 10 ticks a side): +$609 a month in a Jul-Oct-like market (+$1,662 Jan-Jun-like, -$28 2021-25-like); first payout about Feb 18 with ATLAS, while without it half the runs see no payout in 6 months. At backtest fills it was +$817 a month (+$2,084 Jan-Jun-like, +$7 2021-25-like).
> Added 2026-11-16 · write-up [[stack-one-account-2026-11-16|More strategies on ONE MFFU account]] · id `atlas-on-rapid`
> Card: [[Decide atlas-on-rapid|open the card note]]

> [!question] Rapid funded payouts: always leave $1,000 above the buffer in each Rapid?
> **Why:** Leaving more in the Rapid after each payout gives the bot more room, so fewer funded accounts get stuck; each payout is smaller and comes later.
> **Impact:** -$20 a month in a Jul-Oct-like market (+$56 Jan-Jun-like, -$3 2021-25-like); first payout about 4 trading days later.
> Added 2026-11-16 · write-up [[rapid-levers-2026-11-16|Rapid EOD 50K levers]] · id `keep-1000-rapid`
> Card: [[Decide keep-1000-rapid|open the card note]]

> [!question] Ask MFFU to say yes in writing: a 2nd Builder 50K and a 2nd 25K eval while the current ones run?
> **Why:** Their rules allow 10 evals, but a written yes protects the payouts if they ever question it.
> **Impact:** Free to ask. A written yes lets you run a fresh Builder 50K ($91.80) next to Zlarior's: +$56 a month Jul-Oct-like (+$53 Jan-Jun-like, -$6 2021-25-like), the 50K's first payout about 8 trading days sooner. It also protects every payout from a rules dispute.
> Added 2026-11-17 · write-up [[mffu-rules-audit-2026-11-17|MFFU rules audit]] · id `ask-mffu-parallel`
> Card: [[Decide ask-mffu-parallel|open the card note]]

> [!question] Let the cloud watch your PC (a tiny free check every 30 min on the backup GitHub repo) so you get a push if the PC goes silent?
> **Why:** The PC-silent alert is built but needs a cloud runner; the old GitHub account's Actions are off since the suspension. The backup repo's free minutes cover it (~700 of 2,000 a month).
> **Impact:** $0 (free minutes). Catches a dead PC within 30 min instead of days (it was silent Nov 7-17 unnoticed).
> Added None · id `cloud-alerts`
> Card: [[Decide cloud-alerts|open the card note]]

> [!question] ATLAS's funded 25K: risk 40% of the room a trade instead of 60% (safer, but the first payout comes later)?
> **Why:** The bot stops ATLAS for good once the funded room is under $100. Smaller trades make that rarer, but each win is smaller, so payouts come later.
> **Impact:** At real fills (10 ticks a side): +$24 a month in a Jan-Jun-like market ($503 -> $527), -$9 Jul-Oct-like ($402 -> $393), -$3 2021-25-like; first payout 3-8 trading days later (Dec 29 instead of Dec 23 Jan-Jun-like; Jan 19 instead of Jan 7 Jul-Oct-like). At backtest fills it was -$26 a month, 5 trading days later.
> Added 2026-11-19 · write-up [[atlas-health-2026-11-18|ATLAS health]] · id `atlas-funded-room-40`
> Card: [[Decide atlas-funded-room-40|open the card note]]

> [!question] Business page: drop 'Account #4 = LucidPro 50K' and show your MFFU next buys instead (Rapid EOD 25K now, then a fresh Builder 50K and a Rapid EOD 50K from payouts)?
> **Why:** You said MFFU only, and your next buy is the Rapid EOD 25K, but the Business page still plans a LucidPro 50K as account #4 (an older plan from Nov 14).
> **Impact:** $0 by itself (a page fix). For comparison, Jul-Oct-like: the Rapid EOD 25K you buy now is about $1,005 a month, the Rapid EOD 50K from payouts about $1,969 a month; the page's LucidPro line said about $810 a month (an older, non-MFFU estimate).
> Added 2026-11-19 · id `drop-lucid-account4`
> Card: [[Decide drop-lucid-account4|open the card note]]

> [!question] Zlarior's Builder 50K: ATLAS trades it too (one position at a time, first bot in keeps it; ATLAS at half its size until the eval passes, full size once funded)?
> **Why:** Best of 12 rule sets fixed before testing: it keeps most of the extra money and halves the evals that die in 2 weeks (9% -> 4% Jul-Oct); it beat Zlarior alone in Jan-Jun, Jul-Oct and 2021-25, with MFFU's move to live after payout 5 counted.
> **Impact:** +$696 a month in a Jul-Oct-like market (+$392 if the live account after payout 5 is worth nothing), +$1,649 Jan-Jun-like (+$466), +$26 2021-25-like; 2022-like -$141; after the extra eval fees.
> Added 2026-11-19 · write-up [[one-account-combo-final-2026-11-19|One account, Zlarior + ATLAS on the Builder 50K]] · id `zlarior-atlas-50k`
> Card: [[Decide zlarior-atlas-50k|open the card note]]

## Yes

> [!success]- ATLAS's funded 25K: keep trading 1 micro when the room drops under $100, instead of stopping for good?
> **Why:** Today the bot gives the funded account up at $100 of room. Small 1-micro trades that still fit can climb back: about 1 in 5 such accounts recover in a 2026-like market.
> **Impact:** +$3 a month in a Jul-Oct-like market (+$10 Jan-Jun-like, +$4 2021-25-like); chance of losing the account in 6 months 10.5% -> 9.5% (9.8% -> 7.7% Jan-Jun-like); first payout unchanged. At real fills (10 ticks a side): +$6 a month Jul-Oct-like (+$14 Jan-Jun-like, +$1 2021-25-like); chance of losing the account 23.5% -> 21.7% (20.3% -> 17.6% Jan-Jun-like); first payout unchanged.
> Added 2026-11-19 · write-up [[atlas-more-money-2026-11-19|ATLAS more money]] · id `atlas-funded-keep-trading`
> Card: [[Decide atlas-funded-keep-trading|open the card note]]

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

Back to [[ZEUS Home]]
