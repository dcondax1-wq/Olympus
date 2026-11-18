# Data pipe + ZEUS daily review (2026-11-18)

Owner: "the bot and you should constantly be learning, improving, adapting... more data, better communication."

| What | How |
|---|---|
| What the PC sends | Every CME day: NinjaTrader 1m + 5m bars (MNQ / NQ / MES / ES charts), every trade row of Zlarior, the extra accounts, ATLAS, ATLAS v2 (live and paper), the "why no trade" log, live vs the backtest twin, the ZEUS review. |
| Where | The private backup repo `dcondax1-wq/olympus`, branch `data`, folder `days/YYYY-MM-DD/`. Append-only, small gzip files. Never `pc` or `main`. |
| When | After 17:05 ET on weekdays (a missed day is sent later, outside 01:50-16:00 ET). The first run backfills ~45 days from the PC's bar archive. |
| Sign-in | The same saved GitHub sign-in the auto-update uses. Nothing new to set up once `python -m engine.autoupdate --connect` worked. |
| Privacy | Account names cut to the last 4 (`...1234`), no balances or cash, no file paths, never the live phrase. |
| Phone | ONE push a day, only when something needs you (orders refused again, no trades for 6 sessions while the backtest traded, missed trades twice, no bars, edge light turned RED, the data push failing). Every day one "ZEUS review" line on the Board. |
| Strategy ideas | Go to a research queue for Claude (`research/zeus_queue.jsonl` after a pull), never to live settings. Claude tests them under CLAUDE.md "Strategy changes". |

## On the PC (by hand, any time)
- `python -X utf8 -m engine.datapipe run` sends now (`--day 2026-11-18` for one day, `--no-push` = local only).
- `python -X utf8 -m engine.datapipe run --signin` once if the push says the sign-in failed (a GitHub window may open: sign in as dcondax1-wq).
- `python -X utf8 -m engine.datapipe status` shows the last push.
- Off: set `LE_DATAPIPE=0`. Local copies: `logs/datapipe/days/`, review: `logs/zeus/latest.json`.

## For Claude (cloud)
1. Attach the backup (add_repo `dcondax1-wq/olympus`, read is enough) if `git ls-remote olympus` fails.
2. `python tools/data_pull.py --review` = `git fetch olympus data`, copy the days to `data/pc_days/` (gitignored), append the PC's bars
   newer than `data/NQ_1m.csv` / `NQ_5m.csv` / `ES_*` (TradingView rows are never overwritten; a new contract month is refused until
   the roll is in `data/NQ_rolls.json`), queue the proposals, rebuild the ZEUS review. `--edge` then runs `tools/edge_health.py`.
3. Commit the refreshed `data/*.csv` only when the research needs it (they are tracked).

Code: `engine/datapipe.py` (PC side, scratch git dir `data/datapipe_pub.git`, plumbing only, never forced), `engine/zeus_review.py`
(the review, same function on the PC and in the cloud), `tools/data_pull.py`. Hooks: `tools/pc_report.py` (15 min) and
`engine/ops_checks.tick` (5 min). Tests: `python -X utf8 -m tests.test_datapipe` (offline: a local bare repo stands in for GitHub).
