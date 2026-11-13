# Kalshi: going live with real money (risk rules)

2026-11-13, team K1. For the owner's real-money Kalshi account and the bot on the Oracle VM. Paper research only from
here: nothing in this repo can reach the VM, place an order or read a key. **You apply these rules yourself**, through the
"kalshi-server" chat on the VM.

## The honest answer first

| Question | Answer |
|---|---|
| Is there a proven Kalshi edge to trade this weekend? | **No.** Four research teams (A, B, C, K1) plus the bot's own 1,836 bets tested several hundred rule settings on crypto, index, weather, economics and other markets. After Kalshi's fee and the spread, none made money on data it had not seen. K1's last three (index fair value from NQ/ES futures, weather locks, resting limit orders) all lost on held-out data: `research/writeups/kalshi-edge-2026-11-13.md`. |
| Then what does "ready" mean? | The bot can be **safe** by this weekend (the limits below cap what a bad day can cost). It cannot be **profitable on evidence** by this weekend. |
| What may trade with real money? | Only a rule that has passed the paper test below. Today **none** has. Until one does, real money stays at the tiny "tuition" size below, or off. |
| Where is the paper test? | `tools/kalshi_paper.py` (read-only, public data, no key), run every 15 minutes on the VM (the message below sets it up). It logs every signal and its result to `k1_paper.json`. |

## The rules (plain words)

1. **Per trade: at most $3, and never more than 5% of the balance.** At a $55 balance that is $2.75: 2 or 3 contracts at
   90c+, never "all in". Size never goes up after a win streak (the two biggest past losses came right after the balance peaked).
2. **Per day: stop after losing $6 or 10% of the morning balance, whichever is smaller.** No new orders until the next day.
3. **Open at once: at most $10 in total**, and at most one bet per settle time (coins and strikes that settle together
   lose together).
4. **Per week: stop after losing $15.** The bot pauses until you look at it and restart it yourself.
5. **Total "tuition" budget: $25.** If the balance falls $25 below where real trading started, the bot switches itself off
   (kill switch) and stays off until you restart it.
6. **Kill switch you control.** A file named `STOP` in the bot's folder (or the setting `enabled: false`) stops every new
   order within one minute. The bot checks it before every order. It also stops by itself on: 3 losses in a row, an API
   error it does not understand, or price data older than 2 minutes.
7. **Only cheap-to-trade markets.** Spread 2c or less, and the bot's own expected edge must beat price + fee + 1c
   (`MIN_EDGE` at least 0.01, never 0.0 as it was). Never buy at 90-95c, no XRP, 15-minute favourites stay off
   (`docs/KALSHI_STOP_LIST.md`).
8. **No selling back, no averaging down, no doubling after a loss.**
9. **Which edge:** none is proven. The only book with a positive history is the BTC hourly late favourite (+$16 on 182
   bets, 3 losses: positive, not proven). If you want real money on something, it is that one, at 1 contract, under
   rules 1-8. Everything else stays paper.

## When a paper rule may get real money (the bar, fixed before the data)

A rule from `k1_paper.json` (or the bot's own paper books) may trade real money only when **all** of these hold:
- at least **100 settled paper signals** over at least **4 weeks** and **20 different days**;
- **net positive after fees** at the price it would really pay (taker ask, or a maker fill only if the market traded
  through the price);
- the **95% range of profit per $1 is above zero** (the ledger and `research/kalshi_edge_K1/stats.py` compute it);
- the research result it came from was positive on held-out data (today: none).
Then it starts at the rule-1 size for 2 more weeks before any size change, and the rules above still apply.

## Your 3 steps

1. Open the **kalshi-server** chat in the Claude app and paste the message below.
2. Check its reply lists the new limits and says the bot is still paused (or at 1 contract, if you chose that).
3. Look at the paper ledger once a week (Kalshi page, once wired); move real money only when a rule passes the bar above.

```
Please add these risk limits to the bot, show me the config diff, run its dry-run/self-test, and change nothing else: (1) max $3 per trade and never more than 5% of the balance; (2) stop for the day after losing $6 or 10% of the morning balance, whichever is smaller; (3) at most $10 open in total and at most one bet per settle time; (4) pause after losing $15 in a week until I restart it; (5) switch the bot off if the balance falls $25 below today's starting balance; (6) a kill switch: a file named STOP in the bot folder (or enabled=false) blocks every new order, checked before each order, plus auto-stop on 3 losses in a row, an unknown API error, or price data older than 2 minutes; (7) only markets with a spread of 2c or less, MIN_EDGE at least 0.01, no buys at 90-95c, no XRP, 15-minute favourites off; (8) no selling back, no averaging down, no size increase after wins. Only the BTC hourly late-favourite book may trade real money, at 1 contract; everything else paper. Leave the bot paused until I say "go". Tell me the exact command to create and remove the STOP file. Then copy tools/kalshi_paper.py and research/kalshi_edge_K1/paper_rules.json from my nq-liquidity-engine repo to ~/k1/ (same sub-folders), run `python3 ~/k1/tools/kalshi_paper.py --selftest`, and add a cron line that runs `python3 ~/k1/tools/kalshi_paper.py --out ~/k1/k1_paper.json` every 15 minutes (paper only: it reads public data, uses no key and never places an order).
```
