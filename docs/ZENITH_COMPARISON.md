# Zenith vs the best trading dashboards (2026-11-03)

What the leading journals and prop-firm dashboards give a trader, what Zenith (the phone dashboard, `tools/web_public/`)
already had, what was added on 2026-11-03, and why each one matters for money. Sources: the products' public feature
pages and help docs as known on 2026-11-03 (TradeZella, Tradervue, Edgewonk, TraderSync, the MFFU / Tradovate account
dashboard, NinjaTrader 8 Trade Performance, TradingView's paper / portfolio view, prop-firm trackers such as
PropFirmApp-style multi-account trackers). Zenith is read-only and paper-first: it never places or changes a trade.

**Where the new things live:** Zlarior > Results > **Scorecard** (`#/pro/<part>`, also More > Insight, a Home card under
the quick tiles, and the PC dashboard's sidebar Insight). Renderer `tools/web_public/procore.js` (= `web_next/js/next/procore.js`),
phone glue `pro.js`, PC glue `web_next/js/next/pro.js`, journal tags in `hub.js`. Test: `python -X utf8 -m tests.test_zenith_pro`.

## The table

| Feature | Who has it | Zenith before | Added 2026-11-03 | Why it matters for money |
|---|---|---|---|---|
| One-number performance score (radar of 6 metrics) | TradeZella (Zella score), TraderSync | No | **Zenith score** 0-100: win rate (breakevens out), profit factor, payoff, recovery factor, green weeks, drawdown vs the $2,000 max loss; radar + grade A-F; H2 check score beside it | One glance says whether the edge is holding; a falling score is the first sign to cut size before the eval pays for it |
| Expectancy in $ and R | Edgewonk, TraderSync, Tradervue | Only inside run pages (R) | Expectancy $ / trade and R, $ a month, $ per session, on every span | $ per trade x trades per week = the paycheck; the owner rule "money, not only R" |
| SQN / recovery factor | Edgewonk, NinjaTrader (recovery, Sharpe) | No | SQN (Van Tharp, capped at 100 trades) and recovery factor | Separates a real edge from a lucky streak before more evals are bought |
| Streaks + last 20 | TradeZella, TraderSync | Week calendar had streak counts | Longest win / loss run, worst losing run **in $**, current run, the last 20 as dots | The worst losing run in $ is what the eval's room has to survive |
| R-multiple distribution | Edgewonk, Tradervue, NinjaTrader | Edge page (R only) | R buckets with the **$ each bucket made** | Shows the money comes from a few 3R+ winners: never cut the target early |
| Win rate / $ by weekday, hour, side, exit | Tradervue reports, TradeZella, NinjaTrader | Intraday heat, Edge (R) | One card with $ and win % per weekday, entry time, side, exit type | Where the dollars come from, read-only (the rule: size changes over skipping days) |
| Drawdown curve vs the prop-firm floor | MFFU / Tradovate (trailing drawdown line), prop trackers | Eval curve (real balance only) | **Underwater chart**: $ below the last high vs the $1,000 daily limit and the $2,000 max loss, longest drawdown, worst week | The eval dies at the trailing floor, not at a loss count: this is the number that ends an account |
| Risk of ruin | TraderSync (calculator), Edgewonk | Lab > Evals (research Monte Carlo) | Quick eval odds from any span: pass / fail in 2 and 3 weeks, median sessions, risk of ruin | Whether a $91.80 eval is a good bet at today's size |
| Eval progress ring, days left, pace to target | MFFU / Tradovate, prop trackers | Rings on the account cards | **Eval pace**: ring, $ needed per session vs the bot's own H2 $ per session, sessions it should take, losses in a row the room can take, research odds | Says early if an eval will miss the 2-week goal (the owner's rule: decided in 2 weeks, never over 3) |
| Payout tracker | MFFU dashboard, prop trackers | Money > Funded & payouts | The payout path on Eval pace (buffer, first payout, 50% best-day rule, split) + the H2 best-day share | The 50% consistency rule decides when the first payout can be asked |
| "What if" sizing simulator | Edgewonk (simulator), TraderSync | What if (the next trade only) | **What if: sizing** 0.25x-2x slider: net $, $ a month, max drawdown, worst day vs the daily limit, eval pass / fail odds; 0.5x / 1x / 1.5x / 2x table | Shows bigger size passes faster AND fails faster: the right size is a money decision, made with numbers |
| Playbook (setups with their stats) | TradeZella Playbooks, TraderSync | Strategy page (rules in words) | **Playbook**: the LIT rules as a numbered checklist + one graded card per level family swept (net $, $ a month, expectancy, win rate, PF, the levels) | Shows which swept levels pay the bills |
| Trade journal with tags and notes | Tradervue, TradeZella, Edgewonk, TraderSync | Journal with notes, filters, CSV | **Tags** (A+ setup, Textbook, News day, Bad fill, Late entry, Early exit, Would skip, Lesson), a tag filter, tags in the CSV; Scorecard > Tags = $ by tag | Turns "I think news days are bad" into a number in $ |
| Mobile share card | TradeZella, TraderSync | Month share card (More > Share card) | "Share my scorecard": a 1080x1350 PNG to the iPhone share sheet | Quick proof for a prop-firm or a friend without screenshots of private balances |
| Calendar P&L heatmap | TradeZella, TraderSync, Tradervue | Yes (Calendar, week calendar, real P&L calendar) | — | — |
| MAE / MFE scatter | Tradervue, NinjaTrader, TraderSync | Yes (Edge, Trade intel) | — | — |
| Trade replay | TradeZella, TraderSync | Yes (Holodeck 3D replay, Replays) | — | — |
| AI insights | TraderSync (Cypher), TradeZella | Yes (Mind, AI watch, Live learning) | — | — |
| Multi-account view | Prop trackers, TradingView | Yes (status bar, three account cards, Mission Control) | — | — |
| Execution quality (slippage) | NinjaTrader, Tradervue | Yes (Execution page, Live learning) | — | — |
| Broker auto-sync | All (Tradovate, NinjaTrader imports) | Yes (the PC pushes NinjaTrader fills) | — | — |
| Tiltmeter / emotions | Edgewonk | No | Not added: the bot trades, not the owner; the tags cover "Would skip" | — |
| Sharpe / Sortino | NinjaTrader, TradingView | No | Not added: with 2-4 trades a week a daily Sharpe is noise; SQN and recovery factor say more | — |

## Navigation (2026-11-03)
- One clear home: Home keeps the status bar, the three account cards, what matters now, the quick tiles, then **one**
  Scorecard card; everything older stays folded under "Everything else on Home".
- Each bot tab: Today · Brain · Trades · Results · Rules. Zlarior > Results now opens on the Scorecard (the old
  Performance, Replay, Calendar, Edge, Execution, Learning are the next chips).
- More: Today (+ **Data City** `datacity/` and the **Strategy Tree** `tree/`, sibling pages on the same site) · Insight
  (Scorecard first) · Bot and health · Trades · Money planning · This app · Advanced (folded).

## Honest limits
- Backtest spans are the live-settings replay with costs in; the 2021-25 line is a reference, 2026 H2 is the check
  period. The "Real" span counts only closed NinjaTrader fills (few so far).
- The quick eval odds resample days of the chosen span; the research odds (walk-forward, every start date, Lab > Evals)
  win when they differ. Sizing what-ifs scale each trade's $ (real micros round).
