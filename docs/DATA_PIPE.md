# Data pipe + ZEUS daily review (2026-11-18)

Owner: "the bot and you should constantly be learning, improving, adapting... more data, better communication."

| What | How |
|---|---|
| What the PC sends | Every CME day: NinjaTrader 1m + 5m bars (MNQ / NQ / MES / ES charts), every trade row of Zlarior, the extra accounts, ATLAS, ATLAS v2 (live and paper), the "why no trade" log, live vs the backtest twin, the ZEUS review. |
| Where | **Over ntfy.sh, on request** (night-data 2026-11-18, `engine/datafeed.py`): Claude posts one small request to the topic `olympus-nq-data-...`, the PC answers with ONE zip attachment (the same day folders as below). Nothing on GitHub. |
| When | The PC checks for a request every 5 minutes (its ops task), never during 01:50-16:00 ET on weekdays (the session). It answers within ~5 minutes, at most 8 times a day. The nightly run after 17:05 ET still packs every day on the PC (`logs/datapipe/days/`) and writes the ZEUS review. |
| Why not GitHub | The backup repo `dcondax1-wq/olympus` is **public** (GitHub API, 2026-11-18): a `data` branch there would publish every trade forever. The PC also has no push sign-in (it reads the public repo without one), so every nightly push failed. Automated pushes are what the first account was suspended for. The git push is OFF (`LE_DATAPIPE_GIT=1` turns it back on, e.g. after the repo is private again and the PC signed in). |
| Sign-in | None. Nothing for the owner to do. |
| Privacy | Account names cut to the last 4 (`...1234`), no balances or cash, no file paths, never the live phrase. |
| Phone | ONE push a day, only when something needs you (orders refused again, no trades for 6 sessions while the backtest traded, missed trades twice, no bars, edge light turned RED, the data push failing). Every day one "ZEUS review" line on the Board. |
| Strategy ideas | Go to a research queue for Claude (`research/zeus_queue.jsonl` after a pull), never to live settings. Claude tests them under CLAUDE.md "Strategy changes". |

## On the PC (by hand, any time)
- Nothing is needed. `python -X utf8 -m engine.datafeed status` shows the last answers sent to Claude; `... datafeed pack --since 2026-11-10` builds the zip locally only (`logs/datafeed/pack.zip`).
- `python -X utf8 -m engine.datapipe run` packs + reviews now (`--day 2026-11-18` for one day); `--git` would push to the backup (off by default, see above).
- Off: `LE_DATAFEED=0` (requests only) or `LE_DATAPIPE=0` (everything). Local copies: `logs/datapipe/days/`, review: `logs/zeus/latest.json`, feed log: `logs/datafeed/`.

## For Claude (cloud)
1. `python tools/data_pull.py --latest` (use a 10-minute Bash timeout): asks the PC from the newest day already in `data/`, waits up to 9
   minutes, downloads (size + sha256 must match the PC's message), unzips into `data/pc_days/` (gitignored), then appends the PC's bars
   newer than `data/NQ_1m.csv` / `NQ_5m.csv` / `ES_5m.csv` (+ 15m / 1h; TradingView rows are never rewritten, 5m first so no bar is
   rebuilt from part of its minutes; an unfinished session stays out of `data/` until it is complete; a new contract month is refused
   until the roll is in `data/NQ_rolls.json`) and queues the proposals. `--edge` then runs `tools/edge_health.py`.
   `--wait 0` only asks (or uses an answer already on the topic: it is kept 3 h); `--feed-status` shows the topic.
2. During 01:50-16:00 ET the PC does not answer: the request waits (6 h), run the command again after 16:05 ET.
3. Commit the refreshed `data/*.csv` only when the research needs it (they are tracked).
4. ntfy.sh free limits (measured): attachment <= 2 MB (the PC sends <= 1.85 MB, oldest day first; a longer gap says "more" and
   `--latest` asks again from the next day), kept 3 h; 250 messages a day per IP (the PC's status posts use ~210, so answers are
   capped at 8 a day). The topic name is in this public repo like the status topic: only trades with account names cut to the last 4
   (no balances, no paths) and market bars travel; the cloud accepts only an answer to its own request id, from ntfy.sh, with the
   announced checksum, and only the known day-file names.

Code: `engine/datafeed.py` (ntfy request / answer, the zip, `extract` for the cloud), `engine/datapipe.py` (PC side packing; its git push
is off by default: scratch git dir `data/datapipe_pub.git`, plumbing only, never forced), `engine/zeus_review.py`
(the review, same function on the PC and in the cloud), `tools/data_pull.py`. Hook:
`engine/ops_checks.tick` (5 min) -> `datapipe.maybe_run` -> `datafeed.maybe_answer`. Tests: `python -X utf8 -m tests.test_datapipe` (offline: a local bare repo stands in for GitHub), `python -X utf8 -m tests.test_datafeed`
(offline: a local fake ntfy server, fake clock: the PC tick, the size cap, privacy, refused bundles, the git switch).
