# day-obsidian2: ZEUS Brain, the huge vault that learns (pushed on day-obsidian2)

| What | Result |
|---|---|
| Vault | `vault/ZEUS Brain`: **1,202 linked notes** (was 449), 8,820 links, about 2 MB of text (5 MB on disk), far under 30 MB |
| New notes | 628 trades · 9 lessons · 13 news types · 47 weekly reviews · 13 Decide cards · 7 hard rules · hubs ZEUS Trades / Weeks / News / Rules / Dataview |
| Trades | every published trade (1 live, 3 paper, 295 backtest at account size: trades.json) + the 2026 backtests of the loss anatomy (BLITZ 329 at its $150 research size). Each: prices, R, $, MFE/MAE, context, news that day, links to day, week, strategy, member, account |
| Learning | every loser gets ONE main cause (never worked / worked then turned / shaken out / news hit) + the 4 careful-human checklist flags, using the loss anatomy's own rules (`tools/win_loss_anatomy.cause_of / checks_of`). Live + paper losers are classified from the NQ 1m bars (the live loser on Oct 28 = "worked then turned"). Lesson notes recount on every build: by bot x period (2026 halves + 2021-25), month by month, examples, and "would skipping pay?" with a plain verdict (today: no checklist filter loses money in every period, so keep taking them) |
| Daily + weekly | each Day note: what each bot did ($ by bot and source), every trade, the day's lessons, the news, the week. Each Week note: $ by bot, PF, best / worst trade, the losses' reasons, news, research written, Decide cards added |
| Dataview | numbers are real numbers in the front matter (pnl, r, trades), so Dataview can sum them; the queries live only in `ZEUS Dataview`; Home and every other note read fine without plugins |
| Refresh | already wired: the cloud night (`tools/learn_night.py`) rebuilds `vault/`, the PC sync (`tools/obsidian_sync.py`) rebuilds `<your vault>/OLYMPUS/ZEUS Brain` once an hour. 1 s a build, same input = same bytes, only changed notes are rewritten |
| iPhone | `docs/OBSIDIAN.md`: 3 steps, free (Obsidian app + the Git plugin you already use for Jarvis) |
| Tests | `tests.test_obsidian_brain` **39/39** (14 new checks: every new note kind, reason codes, recounting, size < 30 MB, real build idempotent, no clock/network); smoke 7/8 (the red one is `test_zenith_mode`: no Python Playwright in this container, same as last night); area pc: see below |
| Bot safety | nothing under engine/, server.py, live_model*, accounts, scripts touched. Only `tools/obsidian_brain.py`, new `tools/obsidian_more.py`, its test, `vault/`, `docs/OBSIDIAN.md` |

Honest numbers on Home today: real trades (live + paper) = 4, all losers, -$1,975 (3 "worked then turned", 1 "never worked").
2026 backtest losers: "never worked" 182 (-$38,216), "worked then turned" 82 (-$20,656), shaken out 15, news 3.

Screenshots (Markdown rendered to HTML here, phone width, Obsidian-like dark theme; Graph view drawn from the real links):
`graph_view.png`, `ZEUS_Home.png` (+ `ZEUS_Home_full.png`), `Week_2026_W44.png`, `Day_2026_10_28.png`,
`Lesson_against_both_trends.png`, `Trade_2026_10_28_0343_LIT_short_live.png`.

Owner's steps (docs/OBSIDIAN.md):
1. PC once: `python tools/obsidian_sync.py --setup "C:\Users\YOU\Documents\Obsidian\YourVault"` (skip if done).
2. PC Obsidian: Git plugin on, auto commit-and-sync every 30 minutes (same repo as Jarvis).
3. iPhone: Obsidian app → Git plugin → clone that repo → open OLYMPUS/ZEUS Brain/ZEUS Home.
