# Final report: the strategy the bot now runs (Sat 2026-10-17)

All tests use **real CME futures data from your TradingView**: NQ1! 5m (Oct 2021 → Oct 16 2026), NQ1! 1m for 2026, ES1! 5m. No CFD, no Yahoo. Commissions and 1-tick slippage are included. Sizing is a fixed $350 risk per trade.

## Bottom line
- The bot runs **your Liquidity Engine, upgraded to trade like a person**. It targets liquidity it can actually reach, scales out at the first internal draw, moves to breakeven after that, and sits out FOMC days.
- It made money in **every period tested**: Jan–Jun 2026, Jul–Oct 2026, and 2025.
- It trades **about 2.2 times a week**.
- It is **paper only**.
- It is steadier than the old version, but makes about half the old version's 2026 profit, because the old one made almost everything in Aug–Oct.

## The rules
1. **Liquidity map:** prior day/week highs and lows, Asia/London/overnight highs and lows, 1H swings, equal highs/lows, and unmitigated FVGs.
2. **Setup:** price sweeps one of those pools from 8:00 AM. That arms a trade the other way.
3. **Entry:** in the NY killzones (9:30–11:30, 1:30–3:30), the first candle that closes through an FVG from the sweep leg (IFVG), or a CISD.
4. **Stop:** beyond the sweep extreme. Size = $350 ÷ stop, in micros.
5. **Target:** the farthest real liquidity that's still within today's remaining range, at least 1.5R away. In the afternoon, the nearest draw. If there's no draw, no trade.
6. **Management:** take a partial at the first internal draw, then move the stop to breakeven. Flat by 3:55 PM.
7. **Risk:** 1 trade a day, done after a winner, no trades on FOMC days, and the daily loss stop.

## Results

| Period | Trades/week | Win % | Profit factor | Net | Max drawdown | 50K eval pass (zero-edge luck) |
|---|---:|---:|---:|---:|---:|---|
| Jan–Jun 2026 | 2.1 | 28% | 1.42 | **+$2,140** | −$2,206 | 54% (21%) |
| Jul–Oct 2026 | 2.5 | 36% | 2.27 | **+$4,127** | −$752 | 100% (17%) |
| **All of 2026** | **2.2** | 32% | **1.75** | **+$6,266** | −$2,959 | **64% (9%)** |
| Apr–Dec 2025 | 2.8 | 28% | 1.16 | **+$1,290** | −$2,460 | — |
| *Old version, 2026 (for comparison)* | *2.3* | *26%* | *2.41* | *+$11,630* | *−$3,147* | *48% (27%)* |

**2026 by month:**

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct |
|---|---|---|---|---|---|---|---|---|---|
| +$846 | −$356 | +$3,054 | +$290 | −$820 | −$876 | −$336 | +$1,794 | +$2,355 | +$314 |

- Losing months are small; the worst day was −$354.
- 69% of weeks had 2–5 trades.

**Risk per trade:**
- A typical stop is about 43 NQ points, traded with about 3 MNQ micros, so about $300 at risk.
- The average winner is +$506. The average loser is −$138, because the partial plus breakeven turns many losers into scratches.

## What was tested and dropped (same data, same costs)
- **Published models, built exactly as taught:** ICT 2022, Mech/IFVG (PB Blake style), Silver Bullet, Continuation. None had an edge.
- **Your ATM model:** on 5m it almost never qualified. On 1–3m it trades about 1.4 times a week, but it's flat for the year: profitable Jan–Jun, losing Jul–Oct.
- **92 confluences:** none survived a fair luck check. Kept: skip FOMC days.
- **Daily bias, 6 methods:** TTrades candle closure, ICT HTF draw, structure, AMD, a combination, and your session AMD (Asia → London → NY). None predicts the NY session (all about 50%). Trading only with the TTrades bias would have cut 2026 from +$11.6k to +$0.2k.
- **Trader brain:**
  - Its grades don't pick winners, so it doesn't change trades.
  - It writes the pre-market story and the reasoning for every trade (journal).
- **Confidence sizing (1 NQ on A+):** the grades don't rank trades, and it broke the drawdown limit. Sizing stays flat at $350.
- **Retest entries, protected-swing stops, trailing, the full playbook stack:** each lost money in at least one half.

## Honest caveats
- **Max drawdown is $2,959 in 2026, above the eval's $2,000 trailing limit.** Every version tested was over that limit, including the old one. Before risking an eval, lower risk to about $250 a trade, or paper-trade first.
- **Results aren't statistically proven.** The confidence range on average R still includes zero. Profitable in every period is encouraging, not proof.
- **The TradingView strategy has not been updated with the new person-style targets yet.** Going live through TradingView needs that Pine update and a parity check first. The paper bot and the free cloud monitor already run the new version.

## What's running
- **PC paper bot:** final strategy, paper only.
- **Free cloud monitor (GitHub Actions):** final strategy. Its dashboard is at `github.com/demetrades2000-coder/nq-liquidity-engine`, `dashboard` branch.
- **Chart gallery:** `research/lab/gallery/index.html`, 251 trades with the bot's reasoning.
- **Detail reports:** `research/lab/` (PERSON_REPORT, BIAS_REPORT, CONFLUENCE_RESULTS, ATM_REPORT, RISK_REPORT, TRADER_LAYER_REPORT, NARRATIVE_*).
