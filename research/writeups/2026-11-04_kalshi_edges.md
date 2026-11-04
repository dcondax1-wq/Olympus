# Kalshi Edge v2: why it loses, and what (if anything) works

2026-11-04. Research only. No Kalshi API call, no order, no secret, the bot untouched. Data: the public feed
`kalshi.json` (1,836 settled buys with price/asset/strategy totals, 41 days of daily P&L, the last 40 trades).
Numbers regenerate with `python tools/kalshi_research.py` (tables in `research/kalshi/edge_tables.json`, schema in the
script's docstring). Everything below is **after Kalshi's fees**: the bot's own P&L already has the fee taken out
(checked on the last 40 trades: fee = 0.07 x contracts x price x (1 - price), to the cent).

## The answer in one table

| Question | Answer |
|---|---|
| Why is it negative? | Kalshi's fee. Before fees the bot is at about +$10 on $21,602 bet (0.05%); the fees are about $73 (0.34% of the money bet). It buys fairly priced favourites and pays the toll. |
| Is there a positive pocket? | Maybe one: entries at **95c and above**. 1,075 trades, 98.0% won (97.0% to 98.7%) against 96.9% needed. +$206 on $15,275 (+1.4% per $, range +0.5% to +2.1%). Thin, and it is the pay for tail risk (see below). Not proven (see "how sure"). |
| What loses? | **90-95c entries: -$248** (581 trades, ROI -4.7%, range -7.9% to -1.6%). **XRP: -$107** (192 trades, ROI -6.1%). **15-min favourites: -$89** (95.0% won, needs 96.6%; already OFF). Under 90c: -$20, unproven. |
| Why a 94% win rate still loses | A win pays about **$0.71**, a loss costs about **$12.89**: one loss erases 18 wins on average (50+ wins at 98c). Break-even loss rate is 5.2%, the bot's is 5.5%. |
| Biggest hidden cause | **Losing bets were bigger than winning bets** below 97c. At equal size the 90-95c bucket would have lost about $57, it lost $248: $192 came from size. Bets grew with the bankroll ($233 peak on Oct 23) and the worst days came right after (Oct 24: -$102 = -47% in a day). |
| Risk of ruin now ($55.81) | High at today's size. Late favourite only, 6 contracts (10.5% of bankroll per bet), 90 days: 29% chance to fall under $6 at the observed win rate; 3 contracts 10%; 1 contract 0.2%. If it trades like Sep 23 to Nov 2: 55% to 67% in 90 days. |
| What to do (suggestions) | Keep 15-min favourites off; floor 95c; stop XRP and the alts; shrink to 1-3 contracts (2-5% of bankroll) and size down after losses, not up after wins. Details below. |

## 1. Win rate against price, by entry bucket

"Needs" = the win rate that breaks even at that price after fees. Grey = fewer than 30 trades, ignore. "ROI" is dollars won per dollar
bet; the range is a bootstrap (95%). "Size effect" = actual P&L minus what equal-size bets would have made (negative = losing bets were bigger).

| Entry price | n | Won | Won, 95% range | Priced at | Needs | Edge (pts) | Bet $ | P&L $ | ROI per $ | ROI range | Size effect $ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| under 60c (grey) | 10 | 10% | 2-40% | 19-43% | | | 16 | -7.2 | | | |
| 60-80c | 35 | 77.1% | 61.0-87.9 | 73.5% | 74.9 | +2.3 | 124 | -29.4 | -23.8% | -47.0 to +8.3 | -33 |
| 80-90c | 135 | 86.7% | 79.9-91.4 | 86.2% | 87.0 | -0.3 | 843 | +16.2 | +1.9% | -4.1 to +7.1 | +19 |
| **90-95c** | 581 | 92.2% | 89.8-94.2 | 92.8% | 93.2 | -1.0 | 5,343 | **-248.3** | **-4.7%** | **-7.9 to -1.6** | -192 |
| **95-97c** | 715 | 97.8% | 96.4-98.6 | 96.1% | 96.4 | +1.4 | 9,182 | **+137.0** | **+1.5%** | **+0.3 to +2.5** | +3 |
| **97-99c** | 360 | 98.6% | 96.8-99.4 | 97.7% | 97.9 | +0.7 | 6,093 | **+69.0** | **+1.1%** | **+0.1 to +2.0** | +23 |
| 95-99c together | 1,075 | 98.0% | 97.0-98.7 | 96.6% | 96.9 | +1.2 | 15,275 | +205.9 | +1.4% | +0.5 to +2.1 | +19 |
| everything under 95c | 761 | 89.5% | 87.1-91.5 | 90.0% | 90.6 | -1.1 | 6,327 | -268.8 | -4.2% | -7.3 to -1.2 | -190 |
| all settled buys | 1,836 | 94.5% | 93.4-95.5 | 93.9% | 94.3 | | 21,602 | -62.8 | -0.3% | -1.5 to +0.9 | -114 |

Limit of the feed: the top bucket is 97-99c, so **98c and above cannot be split out**. The 60-80c row has the single worst bet-size distortion:
losing bets about $6.60 against winning bets about $2.60 (inferred from the totals, an estimate).

Plain reading: the market is priced almost exactly right (within +/-1.5 points everywhere). There is **no favourite-longshot gift** here; the
only visible premium is that 95c+ favourites won about 1.2 points more often than their price says, which is worth more than the 0.2 to 0.3 point
fee. The 90-95c bucket is the opposite: it wins half a point less than its price, pays 0.5 point in fees, and its losing bets were large.

**How sure.** The 95-99c result has a one-sided p-value of 0.012 before allowing for the fact that I looked at about 14 slices (allowing for that
it is roughly 0.15). Wins are not independent either (coins move together), so the effective sample is smaller than 1,075. Read it as "plausible,
small, worth a forward paper test", not as "proven". The 90-95c loss is stronger evidence (the whole range is below zero) but part of it is bet size, which is a different cause.

## 2. By strategy (the feed gives only totals, not price per strategy)

Recent entry price comes from the last 40 trades only (n small), so "needs" is approximate.

| Strategy | Mode | n | Won / lost | Won, 95% range | P&L | Reading |
|---|---|---|---|---|---|---|
| 15-min favourites | off | 1,131 | 1,074 / 57 | 95.0% (93.5-96.1) | -$88.77 | Needs 96.6% at its ~96.3c entries. **Negative, p = 0.002.** Keep off. |
| Late favourite (BTC hourly) | live | 182 | 179 / 3 | 98.4% (95.3-99.4) | +$16.26 | Entries ~97.8c, needs 98.0%. **Cannot be told apart from zero** (p = 0.49). One loss erases ~50 wins. |
| Hourly BTC | paper now | 291 | 277 / 14 | 95.2% (92.1-97.1) | +$30.32 | Positive, price unknown; its entries must have averaged under 94.8c. Worth a paper rerun. |
| combo | - | 159 | 156 / 3 | 98.1% (94.6-99.4) | +$5.29 | Price unknown, tiny edge at best. |
| Value | - | 40 | 30 / 10 | 75.0% (59.8-85.8) | -$13.04 | Negative. Turn off. |
| Gold 5 PM (grey) | live | 3 | 3 / 0 | | +$7.13 | n=3, no information. |
| Flip exit sell-backs (grey) | off | 16 | 5 / 11 | | -$7.66 | Selling back before expiry lost money. |
| Sniper test, arb, arbx (grey) | - | 14, 4, 5 | | | -$5.25, -$2.82, -$0.65 | Too few to judge; all negative. |

Note: the "1,735 W / 110 L" is the sum of the strategy rows (it includes sell-backs). The 1,836 settled buys have 101 losses. The strategy rows add to
-$59.19, not -$81.77: about **-$22.6 sits in books the feed does not list** (it shows only 10 strategies).

## 3. By coin

Entry price per coin is not in the feed (proxy used). "Entry must be below" = the average price at which this win rate would just break even.

| Coin | n | Won (95% range) | Bet $ | P&L | ROI (95% range) | Entry must be below | Reading |
|---|---|---|---|---|---|---|---|
| Bitcoin | 623 | 95.0% (93.0-96.5) | 7,547 | +$51.82 | +0.7% (+0.1 to +1.2) | 94.7c | Positive, mostly the two hourly books. |
| Other (NEAR, ZEC...) | 347 | 96.8% (94.4-98.2) | 4,879 | +$23.96 | +0.5% (-1.6 to +2.3) | 96.6c | Unproven. |
| **XRP** | 192 | 92.7% (88.1-95.6) | 1,739 | **-$106.63** | **-6.1% (-10.9 to -1.9)** | 92.2c | **Clearly negative**, bigger than the whole bot's loss. |
| Dogecoin | 165 | 95.8% (91.5-97.9) | 2,092 | -$0.65 | 0.0% | 95.5c | Flat. |
| Ethereum | 165 | 92.1% (87.0-95.3) | 1,779 | -$5.35 | -0.3% | 91.6c | Unproven. |
| Solana | 142 | 90.8% (85.0-94.6) | 989 | -$13.29 | -1.3% | 90.2c | Unproven, leaning negative. |
| HYPE | 122 | 93.4% (87.6-96.6) | 1,640 | -$12.14 | -0.7% | 93.0c | Unproven. |
| BNB | 77 | 94.8% (87.4-98.0) | 874 | -$7.66 | -0.9% | 94.4c | Unproven. |
| Gold (grey) | 3 | | 62 | +$7.13 | | | n=3. |

Coins and price buckets overlap (a loss is counted in both), so do not add them together.

## 4. Fees

Formula (third-party descriptions of Kalshi's schedule, [chudi.dev](https://chudi.dev/blog/kalshi-fees), [oddpool](https://www.oddpool.com/research/prediction-market-fees-explained)):
taker fee = 0.07 x contracts x price x (1 - price), rounded to the cent. The bot's P&L matches it. Maker (resting) orders pay a lower rate where they apply (about 0.0175).
I could not reach kalshi.com's own page, so check the live schedule.

| Price | Fee per contract | Fee as share of the win | Break-even win rate | One loss erases |
|---|---|---|---|---|
| 90c | 0.63c | 6.3% | 90.6% | 10 wins |
| 95c | 0.33c | 6.7% | 95.3% | 20 wins |
| 96c | 0.27c | 6.7% | 96.3% | 26 wins |
| 97c | 0.20c | 6.8% | 97.2% | 35 wins |
| 98c | 0.14c | 6.9% | 98.1% | 53 wins |
| 99c | 0.07c | 6.9% | 99.1% | 106 wins |

At every price the fee is about 7% of what a win pays, so the cheaper the contract's profit, the more the fee matters. The cent rounding also bites small orders: 6 contracts at 98c owe $0.0082, charged $0.01.
Estimated total: **$73 of fees on $21,602 bet**. The same bets as resting (maker) orders would have paid about $18 (not tested: fills, and who fills you, change).

## 5. Streaks, clustering, ruin

- Daily P&L, 41 days: 18 negative days, longest run 5, best +$81, worst -$102. **The 5 worst days (-$279) are 77% of all money lost on losing days.**
- Balance path (rebuilt from the totals, assumes no deposits): $137.6 start, peak **$233** (Oct 23), now **$55.81**: down 76% from the peak.
- Day-to-day swings are 1.3x what independent trades would give, and one day does not predict the next (autocorrelation -0.03). So clustering is mild; the damage is **big losing bets**, not a bad streak.
- Same-window overlap (last 40 trades): 7 of 18 fifteen-minute windows had two coins bought at once; the largest window held $31.76 = 57% of the balance. Only 1 loss in the 40, so same-hour correlation between BTC/ETH/DOGE/XRP **cannot be measured from the feed**. What-if for 3 bets in one window, each 5% to lose: independent, all three lose 0.013%; if their losses are correlated 0.5, 1.8% (143 times as often); at 0.8, 3.6%.
- Bets are placed 6 to 9 minutes before close (both books).

**Forward simulation, Late favourite only, 12 bets a day, 90 days, start $55.81, "ruin" = under $6** (real fee rounding, price 97.8c):

| Win rate assumed | 6 contracts (today) | 3 contracts | 1 contract | 5% of bankroll | 2% of bankroll |
|---|---|---|---|---|---|
| observed (179 W / 3 L, with uncertainty) | 28.9% ruin | 10.4% | 0.2% | 0.7% | 0.2% |
| fair price, no gross edge | 15.0% | 0.1% | 0% | 0% | 0% |
| pessimistic (lower end of the range, 95.3%) | 100% | 95% | 0.1% | 3.5% | 0.1% |

Median end balance is about $55 to $61 at the small sizes in the first two rows: **at a safe size the edge makes about $2 in 90 days; at a size that could make real money the bot is more likely to bust.** The edge is too thin for the bankroll.

Replaying the real daily returns (Sep 23 to Nov 2, mostly the 15-min era): chance of falling under $10 within 30 days 18% to 23%, within 90 days 55% to 67%.

**Kelly (best share of bankroll per bet, if you trust the numbers):** Late favourite 19.5% at the raw win rate, but **5% once you allow for not knowing the true win rate** (about $2.90, 3 contracts), and **0% if you start from a neutral guess**. The 95c+ buckets give 20% to 38% in theory; do not use it: it assumes independent bets and a stable edge. Never more than a quarter of Kelly; at this evidence that is 1 to 2% of the bankroll. The feed shows the bot's `min_edge` setting at **0.0**, i.e. no required edge over price and fee.

## 6. Suggestions for the bot's owner (not tested forward, not orders; the bot is untouched)

1. **Keep 15-min favourites off.** -$89 over 1,131 trades, significantly below break-even. Do not restart the alt coins (XRP -$107).
2. **Price floor at 95c** (suggestion). 90-95c lost $248; 95c+ made $206. The floor is chosen after seeing this data, so run it on paper first.
3. **Price cap**: at 99c one loss erases 106 wins and the fee needs 99.1%; at 98c it is 53 and 98.1%. A cap near 98c is a maths suggestion; the feed cannot confirm it (no 98c+ split).
4. **Size**: 1 to 3 contracts (2% to 5% of the bankroll) per bet, one bet per 15-minute window, total open under 10%. Stop sizing up after a good week: the big losses came after the bankroll peaked.
5. **Daily stop** (for survival, not for edge): a day-loss limit of about 10% of the day's opening balance. Days do not cluster, so it will not raise profit; it caps the worst day, which is what ruin is made of.
6. **No stop-loss selling.** The sell-back rows lost $7.66 on 16 trades (5 won, 11 lost). No evidence a stop helps on a 95c+ favourite.
7. **Turn off or leave off:** 15-min favourites, Value, Sniper test, arb/arbx, flip exit. **Keep as paper:** Hourly BTC (+$30.32 on 291), Late favourite.
8. **Raise `min_edge`** above 0 so a bet needs a win chance above price plus fee (about 0.3 to 1 point).
9. **Hours to avoid:** the feed cannot say (40 trades, 19:00 ET has the one big loss, n=3). Ask the bot's own chat for a one-off export of the order table (time, ticker, side, book, contracts, price, pnl) and this answer, plus asset x strategy and loss correlation, is a 2-second rerun.

## 7. Five new ideas to paper-test (small samples, be honest)

| # | Idea | Why | How to test from the data | n needed |
|---|---|---|---|---|
| 1 | Only buy 95c and above | 95-99c +$206, 90-95c -$248 | Log every candidate with the rule fixed in advance; judge win rate minus (price + fee) with a Wilson range | ~600 |
| 2 | Resting (maker) entries one cent better | Fees are the whole loss; maker fee is about a quarter | Virtual limit at bid+1c, fill only if trades print through it; compare fill rate and win rate of FILLED vs all signals | ~300 |
| 3 | Distance-to-strike filter, hourly BTC | The 3 late-favourite losses are "BTC crossed the strike late"; strike and time are in the ticker | Join trades with free public 1-minute BTC candles (not Kalshi); bucket by distance in volatility units; check the losses sit in the closest bucket | ~400 |
| 4 | One bet per 15-minute window, BTC/ETH only | Coins move together; alts lose | Group by expiry; measure same-window loss correlation; replay "best-priced coin only" | ~500 |
| 5 | Hour and settlement-average filter | Hourly BTC settles on a short average; thin overnight books | Tag candidates with expiry hour (ET) and minutes-to-expiry (3 / 6 / 10 min); compare win rate minus price by hour block | ~800 |

Control (not a trade): fade the extremes, i.e. buy the 1-3c side. The feed says 97-99c favourites win 98.6% against 97.7% priced, so fading should lose; log it at 1 contract to confirm.

## What this cannot tell you
- The feed has totals by price, coin and strategy, never combinations (strategy x price, coin x hour). Per-hour and per-side results come from 40 trades only: all grey.
- Bet size per strategy and per loss is inferred from totals, not observed.
- Fee schedule is from secondary sources; the bot's own P&L supports the 0.07 rate.
- Everything was looked at in-sample; the positive 95c+ pocket especially needs forward proof.

## In the app: the guard (2026-11-04)
The top card of the Kalshi page is now "Do not take this bet" (`tools/web_public/kalshi/kalshi.js`, `guardHtml`). For every open bet it checks the
rules above against the numbers the bot publishes: the price band that loses (a band is only called a leak on 100+ bets; with no published bands the
90-95c leak of -$248.30 stands in), the fee against the win rate that band / strategy has had (needs p + 0.07 p (1-p)), the size (10% of the balance =
careful, 25% = do not take), a coin that has lost (3%+ of what was bet, 30+ bets) and bets that settle together. Green / amber / red, each with its dollar
reason. With nothing open it still shows, and four price chips (91 / 94 / 96 / 98c) check a bet of the bot's usual size before it exists. Suggestions only:
the page has no form, no link to Kalshi and sends nothing. Test: `python -X utf8 -m tests.test_kalshi_page` (checks g1 to g7; `--only=guard` for just those).

## In the app: "Why am I losing" and "If you change the bot" (2026-11-04)
- **Why am I losing** is the first card of the Kalshi page: one sentence with the top two dollar leaks of different kinds (a price band, a coin, a strategy,
  the fees), from the feed's own totals. On the 2026-11-04 feed: "You are down $81.77 mostly because 90–95¢ bets lost $248.30 on 581 bets and XRP bets lost
  $106.63 on 192 bets. These overlap, so do not add them up." Under 100 settled bets it says "not enough settled bets yet".
- **If you change the bot** (first card of Edge) replays the past bets under three simple rule sets and shows net $ after fees, the typical worst dip and the
  chance of ruin next to the bot as it is. A: skip the 90–95¢ band (+$185.48 on the past bets, ruin about 0%, against -$62.82 and 13% as it is). B: only 95¢ and up,
  every bet capped at 2% of today's balance ($1.12): +$16.46, ruin 0%. C: skip 90–95¢ and cap the rest at 2%: +$5.67, ruin 0%. Net is the past bets replayed (exact);
  dip and ruin come from 400 seeded runs of the next 200 bets drawn from the same price bands at the bot's usual bet. One line says what the data supports (a set
  whose net beats the bot's with ruin under 5%), or "keep the bot as it is", or "not enough bets" under 100. It is a backtest of past bets, picked after looking:
  suggestions only, try it on paper first. The same maths is `tools/kalshi_whatif.py` (writes `kalshicity/whatif.json`); a test holds the two equal.

## The forward test (2026-11-04)
The what-if card replays PAST bets with a band picked after looking at them. `tools/kalshi_forward.py` is the honest version: it freezes a start date (the feed's own
time at its first run, in `forward_state.json`) and from then on applies rule sets A, B and C to every NEW settled bet, once each, in the order they were placed
(A skips 90-95c; B keeps 95c+ at 2% of the balance; C skips 90-95c and caps the rest at 2%). Nothing placed before the start is counted, so there is no look-ahead; the
band is still flagged as picked after the fact. It keeps a running net $, wins / losses and max drawdown per set next to the bot as it is, says "collecting" until 30 new bets
and names a leader only after that. The feed carries only its last 40 bets, so if more than that settle between two runs the tally is flagged "may be incomplete".
Files (new, in kalshicity/): `forward.json` (the Kalshi page's "Forward test" strip reads it; absent = "collecting: 0 bets so far"), `forward_state.json`, `forward_card.json`.
Feed unreachable, or no new bets: nothing is rewritten. Test: `python -X utf8 -m tests.test_kalshi_forward` (23 checks) and `tests.test_kalshi_page --only=whatif`.

## Where the money is: the scan (2026-11-04)
`tools/kalshi_scan.py` works out, for every slice of the bot's bets with 30+ bets, the fee-adjusted expected value per $1 risked, (win rate - price - fee) / price with the
research's own fee function (`tools/kalshi_research.fee_pc`), with a 95% Wilson range, and writes `kalshicity/scan.json` (under 30 KB): the top 5 slices worth a paper test and the
top 5 to avoid, in plain words with the dollars. Slices from the feed's totals over every settled bet: price band, coin, strategy. Slices from bets seen one by one (the city's ledger
plus the feed's last 40): the time of day (ET: Asia, London, NY morning, NY afternoon) and its crossings with band and coin. A coin's or a strategy's price is not in the totals, so
its recent mean price is assumed and a positive result on an assumed price is always flagged fragile (so are cells under 100 bets and ranges that include zero). On the 2026-11-04
feed: avoid the 90-95c band (-1.1c per $1, lost $248 on $5,343) and XRP (-3.7c, lost $107); paper-test 95-97c (+1.5c, made $137). Looking back, not proven: 18 overlapping
slices were looked at, so the best are partly luck. The Kalshi page's "Where the money is" card (Edge, under the what-if card) reads scan.json when the site has it, else the same
maths on the feed's price bands, else a dated sample. Tests: `python -X utf8 -m tests.test_kalshi_scan` (27) and `tests.test_kalshi_page --only=scan` (s1-s7).
