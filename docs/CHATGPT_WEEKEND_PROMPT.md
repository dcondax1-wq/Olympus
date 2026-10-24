# Weekend work for ChatGPT (Sat-Sun, before the Sunday-night launch)

How to use: open ONE ChatGPT chat. Paste **Prompt 0** first. Then paste Prompt 1, wait for the full answer, paste Prompt 2, and so on.
When it says "continue?", type `continue`. When everything is done, ask it: `Put all answers in one message, sections 1-12, nothing left out.`
Copy that final message into a file (or several messages) and paste it to Claude on Sunday night.

---

## Prompt 0 (context, paste first)

You are my research assistant this weekend. Another AI (Claude) builds and backtests my futures bot on my real data and will read everything you write on Sunday night, so write for a machine: **exact facts, exact rules, CSV where asked, a source URL + date checked for every fact, UNKNOWN where you are not sure.** No profit promises, no motivation, no filler. Long, complete answers are wanted. If an answer is cut off, continue it when I say "continue".

My setup:
- I trade **NQ / MNQ futures** (CME) through **NinjaTrader 8** on prop-firm evals at **MyFundedFutures (MFFU)**: a **Builder 50K** (strategy "LIT") and a **Builder 25K** (strategy "ATLAS"). Official launch: Sunday night. I pay $91.80 (50K) and $63 (25K) with discount codes.
- The bot runs on a Windows PC (Surface) with Python. It sends orders to NinjaTrader with **Order Instruction Files (OIF)** written to NinjaTrader's `incoming` folder (ATI), reads fills from `outgoing`, and gets bars from a NinjaScript indicator that writes MNQ 1m/5m bars to CSV.
- **LIT** (main strategy, on the 50K): sweep of a liquidity level (Asia/London/NY session highs/lows, previous day/week/month high/low, new-week / new-day opening gaps, build-ups), at least 0.5 ATR deep; an inducement swing taken first (<= 1 ATR, <= 36 bars before); a displacement candle (body >= 0.8 ATR); a 5-minute CISD close (close beyond the open of the candles that made the sweep); a limit order at the CISD level for 30 minutes, then a 1-minute CISD within 20 bars -> enter at the next 1m open. Stop 1 tick beyond the sweep extreme (8-80 pts). Target = the 18:00 ET open +/- one VIX daily expected move (at least 1.5R, banked at 8R). Breakeven at 1R (+1.25 pts for costs); 15-minute check (cut at -0.3R if it never reached +0.5R); flat at 15:55 ET; 1 trade a day; entries 02:00-15:30 ET. Size: micros so one winner passes the eval, capped at 60% of the drawdown room and a $1,000 soft daily loss. Weekly rule: after 2 stop-outs in a week, half size. Monday rule: once Monday took Friday's high, only shorts (low: only longs).
  2026 backtest: ~2.9 trades/week, 55% wins, profit factor ~4, Jul-Oct 2026 about $2,500/month; most trades enter 02:00-08:00 ET. Only ~1 trade in 4 reaches +0.5R, but winners average +4-5R.
- **ATLAS** (on the 25K): three strategies pooled, $500 risk a trade, max 2 a day, never opposite to LIT: (1) London EMA pullback (with a VIX filter), (2) MACD divergence at a liquidity sweep, (3) NY sweep-and-reclaim of support/resistance.
- My rules: official data only (CME via TradingView/NinjaTrader, CBOE VIX; never Yahoo), structural stops (never fixed distance), 2-4 trades a week, pass an eval within 2 weeks, never a filter that stops trading for weeks.
- Already tested and rejected (don't suggest again unless it is a truly new angle): HTF bias filters and top-down draw targets, order blocks, FVG entries, partials at 1R/1.5R/2R, trailing stops, earlier/later breakeven, A+ setup grading, killzone-only filters, a second trade after a loss, mean reversion at extremes, NY/London continuation pullbacks, SMT divergence NQ/ES, 15m/1h entries, EMA/MACD/VWAP/volume-profile confluences, trend-day mode, volatility sizing, stop-hunt resweep setups, Asia-session LIT on the eval, self-adjusting ("learning") size.

Reply only "ready" to this message.

---

## Prompt 1: MFFU rules that can break the bot (most important)

For MFFU **Builder 25K and Builder 50K** (eval and funded), current rules as of today, from MFFU's own help center / terms:
1. Max contracts and micros, any scaling plan, MNQ vs NQ equivalence.
2. Daily loss limit (if any), end-of-day trailing drawdown: how the floor moves, when it locks, intraday vs end of day.
3. **News trading**: any restriction around CPI, NFP, FOMC or other releases (which events, minutes before/after, eval vs funded).
4. Consistency / best-day rules for the eval and for payouts (exact %).
5. Minimum trading days to pass and to get paid.
6. **Two accounts at once** (a 50K and a 25K): allowed? Same instrument at the same time? Opposite directions (hedging between accounts)? Copy trading between my own accounts? Max funded accounts per person per plan and across plans.
7. Automated trading / bots / NinjaTrader ATI / third-party software: allowed in eval and in funded? Any "must be present" or "no fully automated" rule? Any VPS rule?
8. Payout rules (minimum balance/buffer, split, frequency, first-payout timing, max payout).
9. Holiday and early-close handling: does MFFU force-flatten earlier than CME? Weekend holding?
10. What gets an account closed for "prohibited strategies" (e.g. HFT, latency arbitrage, hedging, copy trading from other people)?
11. Activation fee, reset price, monthly fee for Builder plans.

Answer as a table: rule | 25K eval | 25K funded | 50K eval | 50K funded | exact quote | source URL | date checked. Then a 5-line summary: which rules could stop my bot from trading or fail an eval.

---

## Prompt 2: News calendar 2021-2026 (CSV)

Exact dates and release times (Eastern Time) from **2021-11-01 to 2026-12-31** for: CPI, PPI, Core PCE (Personal Income and Outlays), NFP (Employment Situation), JOLTS, FOMC statement (14:00) and press conference (14:30), FOMC minutes, GDP advance estimate, ISM Manufacturing PMI, ISM Services PMI, Retail Sales, weekly Jobless Claims (only list the date pattern, not every Thursday). Sources: BLS, BEA, Federal Reserve, ISM, Census.

One row per event:
```
date,time_et,event,impact,source
2026-01-09,08:30,NFP,high,bls.gov
```
impact = high (CPI, NFP, FOMC statement/presser, PCE) or medium (the rest). Mark releases that were delayed or moved (e.g. the 2025 government shutdown) with a note column. If the list is long, split it by year and I will say continue.

---

## Prompt 3: CME calendar for NQ (CSV)

For 2021-2027:
1. CME equity-index futures holidays and early closes (date, close time ET, reopen time).
2. NQ quarterly contracts: last trading day, and the roll date (when volume moves to the next contract; CME's "roll date" is usually 8 days before expiry).
3. The **December 2026 roll**: NQZ2026 -> NQH2027 exact roll date and last trading day.
4. Daylight-saving switch dates for the US and the UK/Europe 2021-2027 (my sessions are in ET; London session times shift when the clocks change).

CSV blocks:
```
date,type,detail,source
```

---

## Prompt 4: NinjaTrader 8 ATI / OIF exact formats

From NinjaTrader's official help guide (ninjatrader.com/support/helpGuides/nt8):
1. The exact OIF line format for PLACE, CANCEL, CHANGE, CLOSEPOSITION, CANCELALLORDERS, FLATTENEVERYTHING, with each field position, and an example for each.
2. **CHANGE**: can I change only the quantity of a working stop and target order (keep the price)? What goes in the price fields to keep them (0? blank?). Exact example line for "change order id X to quantity 2".
3. OCO: how to place a stop + target as an OCO pair with OIF, and what happens to the OCO partner when I change one order's quantity.
4. The `outgoing` folder: file names and line formats for order state and position files; when they are written.
5. ATI must-have settings (Tools > Options > Automated trading interface), "AT interface" enable, and known issues (files not processed, account name with spaces, Sim101 vs live accounts, multiple accounts).
6. Known gotchas with ATI on prop-firm accounts (Rithmic / Tradovate connections that MFFU uses).

Quote the help guide wording and give each URL.

---

## Prompt 5: NinjaScript bar export indicator review

I have a NinjaScript indicator that writes MNQ 1m and 5m bars to CSV and the forming bar's open from OnMarketData. List:
1. The exact NinjaScript events and properties to use (OnBarUpdate with Calculate.OnBarClose vs OnEachTick, AddDataSeries for 1m and 5m, BarsInProgress, IsFirstTickOfBar, Time[0] meaning bar END time in NinjaTrader).
2. Common mistakes that make bar files late, duplicated or shifted by one bar (bar time = close time, session template, time zone setting, tick replay).
3. How to make the file write atomic and safe for another program to read at the same time (write temp + File.Replace / File.Move).
4. The trading-hours template that matches CME globex for MNQ (18:00-17:00 ET) and how to set it.
Give C# snippets.

---

## Prompt 6: 20 new LIT ideas as exact, testable rules

From ICT / LIT / smart-money teaching (Romz, Candleman, Waqar Asim, ReimFX, TradingHub, Inner Circle Trader) and from market-microstructure research, list **20 ideas that could raise win rate or profit** and are NOT in the rejected list in Prompt 0.

For each idea:
- name
- the exact rule using only 5m/1m OHLC bars, session times, prior-day/week/month levels and the daily VIX close (no order book, no volume profile, no future bars)
- every threshold as a number, with a default and 2 alternatives to test
- the moment it is known (which bar close)
- what it changes: skip / size up / size down / entry / stop / target
- why it should work (one line) and which teacher or paper it comes from

Bad: "wait for strong confirmation". Good: "skip if the 5m candle before the sweep has a body > 1.5 x ATR(14) of 5m".

Then rank the 20 by how likely they are to help a strategy whose profit comes from rare far targets (+4-5R winners, ~25% of trades).

---

## Prompt 7: 10 ATLAS ideas

Same format as Prompt 6, for a second strategy family that should trade **2+ times a week on a 25K with $500 risk** and not be correlated with LIT (different hours or different logic). Include where each idea was published or taught, and any published backtest numbers on NQ/ES (with the source).

---

## Prompt 8: Launch-day risk checklist (things that go wrong with trading bots)

List the 40 most common ways an automated futures bot loses money or fails a prop eval for reasons that are NOT the strategy, e.g. duplicate orders after a restart, stop not placed after a fill, wrong account, contract roll, DST change, holiday hours, data feed frozen, Windows update reboot, sleep mode, clock drift, partial fills, rejected orders, margin, price limit, connection loss to the broker, news spikes and slippage, time zone bugs.
For each: how it happens, how to detect it automatically, how to prevent it, how to test it on Sim. Table form.

---

## Prompt 9: Windows PC as a 24/5 trading box

For a Windows 11 Surface running NinjaTrader 8 + Python 24/5:
1. Exact settings to stop sleep, hibernate, Windows Update reboots during market hours, USB/Wi-Fi power saving, and the lid/power-button behaviour (with the PowerShell / powercfg commands).
2. Auto-login and auto-start of NinjaTrader and a Python script after a reboot (Task Scheduler XML or commands).
3. Clock sync (w32tm commands) and how to check drift.
4. How to keep NinjaTrader connected (auto-reconnect settings) and how to detect a disconnect from outside.
5. Free remote access options to check on it from an iPhone.

---

## Prompt 10: Scaling plan with prop firms (table)

I want to pass the 50K and 25K, take payouts, then add more accounts copying LIT.
1. Which tools copy trades between NinjaTrader accounts (Replikanto, NinjaTrader's own trade copier, others): price, whether MFFU and other firms allow them.
2. Prop firms that allow **bots/automation + news trading + NinjaTrader + no best-day/consistency rule in the eval**, with plan sizes, current prices (and common discount codes), drawdown type, payout rules, max accounts per person. At least 10 firms. Source URL + date for each.
3. A month-by-month plan for the first 6 months for someone starting with one funded 50K and one 25K, assuming the strategy makes about $2,500/month on a 50K-size account (show the math, pessimistic and expected case, include eval costs and resets).

---

## Prompt 11: VIX expected-move target check

My target uses the 18:00 ET open +/- one "VIX one-day move". Give:
1. The exact formula for the one-day expected move from VIX (VIX / sqrt(252) as a % of price) and the version using VXN (Nasdaq-100 volatility) instead.
2. Where CBOE publishes the official daily VIX and VXN history files (exact URLs, file format, time of the daily close).
3. Published studies on how often NQ/ES reach the 1-day implied move (hit rates), with sources.
4. Ideas to make the target smarter using only daily VIX/VXN (e.g. VIX term structure from VIX9D/VIX3M CSVs from CBOE) written as exact rules.

---

## Prompt 12: Questions Claude should answer before launch

Read all your answers above and write a list of the 25 most important questions or checks for Claude to run on the bot before the Sunday-night launch, ordered by how much money each could save. One line each, as a checklist.

Then put everything (sections 1-12) together in one final message with clear headers so I can copy it in one go.
