# Pre-registration: a second K8-style clock edge on other Kalshi short markets (written 2026-11-20 ~11:25 UTC, before any data)

Committed before any market of a new series is fetched. Public Kalshi GET only, at most 1 request a second, no key, no order.

## Universe (fixed now)
Every Kalshi series of short up/down or above/below markets that settle every 15 minutes or every hour and have settled markets
on most weekdays between 2026-08-03 and 2026-11-20, other than KXGOLD15M / KXSILVER15M (already K8): e.g. other metals, oil
(WTI / Brent), natural gas, stock indices (S&P / Nasdaq / Dow), FX (EUR/USD, USD/JPY...), crypto (BTC / ETH / SOL ...).
Only markets whose YES is "above the start / target" (a coin-flip at the open, ~50c) are used; range buckets are left out.

## The clock hypothesis (fixed now)
For each series, each window open time of the day (every quarter hour, or every hour for hourly series) and each side
(UP = buy YES, DOWN = buy NO): a $2.50 taker bet at +20 s, held to the result. Price = what public takers of that side really paid
from +20 s (the K8 walk), fee = Kalshi's exact taker fee (ceil to the cent of 0.07 x C x P x (1 - P) per order). Skip a window
when nothing traded on our side by +45 s or the price is over 70c.

## Two stages (fixed now)
1. **Find (results only, cheap):** Aug 3 - Oct 21 (the same find period as K8). For every (series, open time, side) with at least 40
   windows: the win rate. A candidate = win rate >= 62% (the K8 legs won 70-75%; break-even at ~52c + fee is ~54%) and a one-sided
   binomial p under 0.05 / (number of (series, time, side) cells tried) (Bonferroni over every cell of every series).
2. **Price + check (held out):** for at most the 10 best candidates by find-period z-score, fetch the first 45 s of public trades of
   every window Aug 3 - Nov 20 and price them as above. A second edge = net per $1 >= +10% in the find period AND >= +5% per $1
   with >= 12 bets in the held-out Oct 22 - Nov 20, both with fees in.

## Report
The 3 best by held-out net per $1 that passed, with trades a week, win rate, average price, net $ at $2.50 (find and held out),
or **"none"**. Nothing is added to any bot by this research: a pass would only become a PAPER leg proposal for the owner.
