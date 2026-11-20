# nqdash2 report (round 2, deeper NQ pages) - branch night-nqdash2, 4 commits, pushed
| what | result |
|---|---|
| Trading `9. Deep dive` (follows the bot / data / account filters) | equity + drawdown-from-peak, LIVE vs backtest twin in R, R and $ spread, win % by hour x weekday, streaks, best/worst 5, trade timeline (entry/stop/target/exit) |
| MFFU center | each account: first-payout date range (most likely + p10-p90 band, $ and odds) from the payday plan, labelled ESTIMATE |
| NQ page | "News this week" (bot's high-impact US calendar), each bot's "waiting for" always shown (LIVE / PAPER / last said + age), real fill cost from learned.json |
| Shared kit | `nqdeep.js` + `nqdeep.css`: one chart style, tokens only (light/dark), opacity-only motion, every box tagged LIVE/PAPER/BACKTEST + age |
| Data | `tools/nqdash_export.py` -> `business/payday.json`, `nq/news_week.json` (no ids, no balances); lead adds it to the build |
| Tests | new test_nqdeep 26/26; test_mffu_center 33/33; test_nq_page 50/50; privacy 59/59; trading 49/51 (2 Odeon fails pre-existing on pc) |
| Speed / fit | full trading render 73 ms at 4x CPU; no sideways scroll at 390 px; no page errors |
Screenshots: trading_deep_dark/light.png, mffu_payday_dark.png, nq_news_light.png, nq_bots_dark.png. Lead steps: LEAD_WIRES.md.
