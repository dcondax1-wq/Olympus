# Weekend prompt for ChatGPT (paste everything below the line)

---

You are helping me prepare research for my futures trading bot. Another AI (Claude) builds and backtests the bot on my real data; it will read your answer on Sunday night. Your job is to give it **precise, checkable facts and testable rule definitions**, not opinions or profit claims. Where you are not sure, write UNKNOWN. Cite a source (URL + date checked) for every fact.

## My setup (context)
- I trade **NQ / MNQ futures** (CME) through **NinjaTrader 8** on prop-firm evals at **MyFundedFutures (MFFU)**: a **Builder 50K** (strategy "LIT") and a **Builder 25K** (strategy "ATLAS") starting Monday. I pay $91.80 (50K) and $63 (25K) with discount codes.
- **LIT** (main strategy): sweep of a liquidity level (session highs/lows, previous day/week/month high/low, opening gaps) at least 0.5 ATR deep, an inducement swing taken first, a displacement candle (body >= 0.8 ATR), a 5-minute CISD close, then a 1-minute CISD entry. Stop 1 tick beyond the sweep extreme, target = the 18:00 open +/- one VIX daily move (at least 1.5R, banked at 8R), breakeven at 1R (+1.25 pts for costs), 15-minute check, flat 15:55 ET, 1 trade a day, entries 02:00-15:30 ET. Size follows the stop and the eval room left. 2026 backtest: ~2.9 trades/week, 55% wins, profit factor ~4, Jul-Oct 2026 about $2,500/month.
- **ATLAS** (25K): three paper strategies pooled: a London EMA pullback, a MACD divergence at a liquidity sweep, and a NY sweep-and-reclaim of support/resistance. $500 risk a trade, max 2 a day, never opposite to LIT.
- Rules I keep: official data only (CME via TradingView/NinjaTrader, CBOE VIX), structural stops (never fixed distance), 2-4 trades a week, pass an eval within 2 weeks.

## What I need from you (answer each section, in this order)

### 1. MFFU rules that can break my bot (most important)
For **Builder 25K and Builder 50K**, current rules as of this weekend:
1. Max contracts / micros allowed, and any scaling plan.
2. Daily loss limit, end-of-day trailing drawdown, how the floor moves and when it locks.
3. **News trading**: any restriction around CPI, NFP, FOMC or other releases (minutes before/after, which events)?
4. Consistency or "best day" rules for the eval and for payouts.
5. Running **two accounts at once** (a 50K and a 25K): allowed? Can they trade the same instrument at the same time, the opposite direction (hedging), or copy each other? How many funded accounts per person per plan?
6. Automated trading / bots / NinjaTrader strategies: allowed in eval and funded? Any "must be present" rule?
7. Payout rules after passing (minimum days, split, first payout timing, buffer).
8. Holidays and early closes: does MFFU flatten earlier than CME?

Give a table: rule | 25K | 50K | source URL | date checked.

### 2. High-impact US news calendar (as CSV)
Exact dates and times (Eastern Time) from **2021-11-01 to 2026-12-31** for: CPI, Core PCE, NFP (jobs report), FOMC statement (14:00) and press conference, GDP advance, PPI, ISM Manufacturing PMI. Use the official sources (BLS, BEA, Federal Reserve, ISM).
Format, one row per event:
```
date,time_et,event,source
2026-01-09,08:30,NFP,bls.gov
```
Note the events that moved due to the 2025 government shutdown or schedule changes.

### 3. CME calendar for NQ (as CSV)
2021-2027: market holidays, early closes (time ET) and the **NQ quarterly roll dates** (the day volume moves to the next contract, plus the last trading day). Most important: the **December 2026 roll** (NQZ2026 → NQH2027) date.

### 4. LIT ideas written as testable rules
From the ICT / LIT / smart-money teaching you know (Romz, Candleman, Waqar Asim, ReimFX, TradingHub style), list **10 ideas that could raise win rate or profit** that are NOT in this list of things already tested and rejected:
- HTF bias filters, order blocks, FVG entries, partials, trailing stops, A+ grading, killzone-only filters, second trades after a loss, mean reversion at extremes, NY/London continuation pullbacks, SMT divergence, 15m/1h entries, EMA/MACD/VWAP confluences.

For each idea give **exact rules a computer can follow** using only OHLC bars (5m and 1m) and known levels: what to measure, the threshold, when it is known (no future bars), and how it changes the entry, stop, target or size. Bad: "wait for strong confirmation". Good: "skip if the 5m candle before the sweep has a body > 1.5 ATR".

### 5. Two-account scaling plan
With a 50K (LIT) and a 25K (ATLAS) at MFFU, and later more accounts copying LIT: what is the legal way to scale (copy trading tools allowed by MFFU, max accounts per firm, which other prop firms allow bots + news trading + no best-day rule for evals)? Give a table with current prices and rules, sources and dates.

## Output rules
- Plain text and CSV blocks only, so I can paste it back.
- No profit promises. Mark every unverified item UNKNOWN.
- Put a 5-line summary at the top: the rules from section 1 that could stop a bot from trading or fail an eval.
