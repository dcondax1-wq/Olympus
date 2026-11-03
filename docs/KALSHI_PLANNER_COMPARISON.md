# Kalshi page and Planner: what the best apps have, what we have, what was added (2026-11-03)

Screens (iPhone 13 profile, 390 x 844, WebKit): `research/handoff/2026-11-03/kalshi_planner/`.

## Kalshi page (`tools/web_public/kalshi/`, contract `kalshi.json` v3)

Compared with Kalshi's own app, Polymarket's portfolio, and prediction-market trackers and bot dashboards (PolyTrack-style
P&L trackers, Polymarket analytics sites, open-source Kalshi bot dashboards).

| Feature | Kalshi app | Polymarket | Trackers / bot dashboards | Ours before | Added now |
|---|---|---|---|---|---|
| Balance, today / week / all-time P&L | yes | yes | yes | yes | all-time win rate and ROI tiles (`stats`) |
| Open positions with price and value | yes | yes | yes | yes | **live edge** (bot's chance − price) and **EV** per bet, total live edge in the header |
| Settlement countdowns | close time | end date | some | per bet | "Next settles" in the header; bets settling within 15 min become alerts |
| Equity / bankroll curve | balance chart | P&L chart | yes | yes (scrub, ranges) | unchanged |
| Daily P&L calendar | no | no | some | yes | unchanged |
| P&L by market category | no | no | yes | no | **By market**: P&L bars, win rate, ROI per category (coin, weather, indices …) |
| Win rate and ROI by contract price | no | no | yes (key for favourite strategies) | no | **By price**: win rate vs break-even, ROI and P&L per price range (90-95¢, 95-97¢, 97-99¢ …) |
| Calibration (predicted vs actual) | no | no | yes (Brier / reliability charts) | no | **Calibration** chart: dots per group vs the honest-odds line, the weighted gap in points |
| Kelly sizing | no | no | bot dashboards | no | **Edge & sizing**: Kelly per open bet (¼ / ½ / full, the bot's max bet), a size tag (on size / over / under), a Kelly calculator |
| Alerts list | price alerts | no | yes | stale / offline notes only | **Alerts**: the bot's own (paused, blocked, service down, losing run, red day) + settles-soon |
| Strategies table | no | no | bot dashboards | yes | unchanged |
| Its own look | brand green | brand blue | — | Jarvis violet | **Kalshi theme**: mint + cyan on green-black, K mark, ticker tape, aurora, `theme-color` #010a07 |
| Not connected yet | — | — | — | the one step + preview | plus what lights up once connected |

Without the v3 fields (a v1 / v2 feed) the page works the breakdowns out from the last 40 trades and says so.

### kalshi.json v3 fields (additive, all optional; `docs/KALSHI_PUBLISH.md`, `tools/kalshi_kit/public/SETUP.md`)
`categories`, `buckets`, `calibration` + `calib_basis`, `alerts`, `kelly`, `stats`, and `category` / `prob` on positions
and trades. The server script fills all of them from the bot's files except **`prob`** (the bot's own chance; not in
`trades.db`) and **`kelly`** (only if the settings files hold `KELLY_FRACTION` / `MAX_BET` / `MIN_EDGE`).

## Planner add-ons (`tools/planner_patches/30-flow.patch`)

Compared with Sunsama, Motion, Akiflow, Todoist, Notion Calendar and Structured.

| Feature | Who has it | Planner before | Added now |
|---|---|---|---|
| Time-blocking tasks | all six | yes (Block time, Plan my day, drag) | Block time straight from Deadline risk |
| Focus timer | Structured, Akiflow, Sunsama | yes (a bar at the bottom) | 40-olympus **Focus mode**: full-screen ring, task + length pick, 5-min break, minutes today |
| Habits and streaks | Structured, Todoist (habits via recurring) | yes (Habits) | — |
| Daily planning / shutdown review | Sunsama | yes (Plan day, Close out the day, Weekly review + reminder) | — |
| Quick add with natural language | Todoist, Akiflow, Motion | yes (20-power: "gym tue thu 7am", bills …) | — |
| Command palette / universal capture | Akiflow, Notion Calendar | yes (Ctrl/Cmd+K, Capture) | — |
| Auto-reschedule overdue work | Motion | yes (20-power Catch up) | — |
| **Workload vs capacity** ("you planned more than you can do") | Sunsama, Motion | no | **Workload**: today's estimates vs free time left, red when over, **Trim to fit** (lowest priority to tomorrow, Undo) |
| **Deadline risk** (tasks that will miss their date) | Motion | no | **Deadline risk**: 14-day earliest-date-first check against 60% of free time; Fix → Block the best gap |
| **Daily task goal + streak** (Karma) | Todoist | no (Daily score is broader) | **Daily goal**: ring, 7-day bars, days in a row; goal 1-10 |
| Scheduling links / time zones | Notion Calendar | Find a time + copy availability | not added (needs a server; the Planner is static) |
| Day timeline | Structured | Now and next strip | 40-olympus **Day timeline**: today's events on one track, a NOW beam, now / next, an empty state |

All three go through the Planner's own `snapshot()` + `commit()` (sync, tombstones, Undo); the only new key is the
device-only `planner.flow.goal`. Tests: the patch's own `planner/tests/flow.test.js` (41 behaviour checks) and
`tests.test_planner_addons` (the real patches apply to the live planner-backup and every `ext-*.js` is loaded once).
