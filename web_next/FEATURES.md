# Dashboard features registry (owner 2026-10-28: "50 VERY useful features ... very clean and organized")

Status: **new** = built 2026-10-28 · **surfaced** = it already existed and now has a place on Home / Real results / the
nav · **existed** = already there and easy to reach, left as it is · **skipped** = not built, with the reason.
PC = the dashboard at localhost:8766 (`web_next/`), phone = the phone app (`tools/web_public/`). Shared renderers:
`realcore.js` (new, window.RealUI), `boardcore.js` (live board), `tradepics.js` (trade pictures); each is a byte-identical
copy in both apps. Data for every real-account view: `engine/live_board.py` (its new `"real"` block = real trades only,
ledger check, the H2 backtest cone). Group C (21-30, AI / strategy insight) is built by another agent in
`web_next/js/next/insight*.js`.

## A. Accounts & money

| # | Feature | Status | Where |
|---|---|---|---|
| 1 | Real today P&L per account | new | Home "Today · real accounts" card per account (big number = today's real $, from the PC ledger, never paper) |
| 2 | Balance / room-to-floor / $-to-target gauges | new | Home Today cards: balance tile + "Room to floor" and "To target" gauges with real numbers |
| 3 | Eval day N of 10 + pass ETA | new | Home Today cards: "Eval day 8 of 10" + "pass ≈ day N" at the 2026 H2 backtest pace ($ per session) |
| 4 | Payout tracker (funded later) | existed + surfaced | Goals page "Funded & payouts" (PC cc.js, phone hub.js), live board funded rows (boardcore.js); shows on the ATLAS card once funded |
| 5 | P&L calendar day / week / month | existed + new | PC `pnlcal`, phone P&L calendar; new real-only daily bars on Real results |
| 6 | Real equity curve vs backtest band | new | Real results "Live vs backtest": real line by eval session over the 2026 H2 bootstrap cone (p5-p95, p25-p75, p50), with a verdict |
| 7 | Commissions + slippage paid | existed + surfaced | Zlarior / ATLAS > Results > Learning (live_learning: real-fill costs), phone Execution page |
| 8 | $ by strategy (Zlarior, ATLAS members) | new | Real results "$ by strategy" (Zlarior, ATLAS · EMA / MACD / S/R; real money only) |
| 9 | Goal progress (Road to $10K, Stingray) | existed | Goals page (money.js / moneycore.js), phone Home Goals card |
| 10 | Account health score | new | Home Today cards: one number 0-100 in a ring + the reasons (room, guards, red lights, stale data, refused orders, bot stopped) |

## B. Trades

| # | Feature | Status | Where |
|---|---|---|---|
| 11 | Live position card ($ to stop / $ to target, R now) | new | Home Today cards: open position row with "now", "to stop", "to target" in $ and R |
| 12 | Trade timeline (signal -> order -> fill -> BE -> exit, latencies) | new | Real results trade log: tap a trade for its timeline with the time between steps, hold time, risk in $ |
| 13 | Trade chart with REAL size / $ | new | tradepics.js titles + captions say "PAPER 7 micros +$3,879 · REAL: no order on the account"; live board trade log paper rows carry their REAL twin |
| 14 | Journal note per trade | existed | PC Zlarior > Trades > Journal (`journal`), phone Trades > Journal |
| 15 | Why-entered checklist | existed | Trade sheets: "Why Zlarior took it" / checklist (phone index.html trade sheet, PC trades.js, Bot Brain) |
| 16 | Why no trade today | new | Home Today cards: "No trade yet today" + the blocking guard / what the bot waits for / done for today |
| 17 | Refused / missed orders with NinjaTrader's reason | new | Real results "Incidents" + Home "What happened today" (orders that were refused and never filled, with the reason) |
| 18 | Slippage per trade | existed + surfaced | Learning pages: trade reviews vs the twin (live_learning), phone Execution page |
| 19 | R distribution | new | Real results "R distribution" (closed real trades) |
| 20 | Win / loss streaks | new | Real results KPIs: streak now + longest won / lost in a row |

## C. AI / strategy insight (21-30)

| # | Feature | Status | Where |
|---|---|---|---|
| 21 | (group C) | other agent | `web_next/js/next/insight*.js` + the "AI Insights" menu entry |
| 22 | (group C) | other agent | same |
| 23 | (group C) | other agent | same |
| 24 | (group C) | other agent | same |
| 25 | (group C) | other agent | same |
| 26 | (group C) | other agent | same |
| 27 | (group C) | other agent | same |
| 28 | (group C) | other agent | same |
| 29 | (group C) | other agent | same |
| 30 | (group C) | other agent | same |

## D. Safety

| # | Feature | Status | Where |
|---|---|---|---|
| 31 | Kill switch | existed + surfaced | PC Bot Control HOLD TO KILL; the Home Safety card links to it (phone: Remote page, read-only note) |
| 32 | Daily loss meter | new | Home Today cards "Daily loss" gauge + Safety card rows per account |
| 33 | Floor proximity with real numbers | new | Today cards room gauge + Safety card; the **ledger check** flags a booked day with no real trade (2026-10-27 -$965.20) and shows the room if it is a ledger error ($1,106, not the fake "$140 left"); the floor alert on the live board carries the same doubt |
| 34 | Hedge / opposite-conflict indicator (LIT vs ATLAS) | new | Home "LIT vs ATLAS" line + Safety card row (opposite positions now = red, opposite sides today = amber) |
| 35 | NinjaTrader connection + orders confirmed | new | Safety card: NinjaTrader light + "N of M orders confirmed" per account today, with the refusal reason |
| 36 | Feed freshness | existed + surfaced | Live board health strip + Safety card "Feed (1m bars)" |
| 37 | Clock | existed + surfaced | Health strip + Safety card "PC clock" |
| 38 | Version / update status | existed | Home footer (version + branch), Start page "Update" step |
| 39 | Alert center with dedupe + mute | existed | engine/alerts_plus.py (dedupe, levels), phone Notifications (mute per kind, more.js), PC Alerts page |
| 40 | Incident log (refused orders, restarts, voided P&L) | new + existed | Real results "Incidents" (refused orders, ledger checks); restarts and voided days in the PC Bot log (`botlog`) |

## E. Ops / UX

| # | Feature | Status | Where |
|---|---|---|---|
| 41 | Run / Stop switch | existed | runswitch.js, top of every PC page (kept) |
| 42 | Single System Status checklist | existed + new | Home launch checklist (until all green) + health lights + the new Safety card in one place |
| 43 | Notification settings | existed | phone More > Notifications, PC Alerts page |
| 44 | Search / command palette | existed | PC Ctrl+K palette (palette.js), phone More search |
| 45 | Mobile-first layout | new | realcore.js cards: 1 column under 720 px, no horizontal scroll at 390 px (checked by tests/shots_real.py), 40-44 px tap targets; PC tab bar now Home · Zlarior · ATLAS · Real results · All tools |
| 46 | Dark / light correct | new | realcore.js uses only the theme tokens (--ink, --surface, --good ...); screenshot dash_pc_home_1440_light.png |
| 47 | Plain-language tooltips / glossary | new + existed | dotted terms on the Today / Results cards (Room to floor, To target, Daily loss, Eval day, R, Real, Paper, Health score, Pass ETA, Backtest band); full glossary on the Learn hub page |
| 48 | CSV export of real trades | new | Real results "Export real trades (CSV)" with a running P&L column |
| 49 | Weekly report card | new + existed | Real results "This week" grade (A-D) with trades vs the goal; Sunday weekly review (`review` / phone Weekly) |
| 50 | What changed today | new | Home "What happened today": every order, fill, exit, refusal and ledger check of both accounts today, newest first (software changes: phone More > What's new) |

## F. Deep space + Mission Control (2026-10-29, owner: "make it look cooler ... features I should have had")

Shared renderer `missioncore.js` (window.MissionUI, byte-identical in both apps), styles `mission.css` + `space.css` (byte-identical),
the 3D scene `tools/web_public/fx/src/space.js` (in fx.js). Phone: `mission.js` (Home strip + `#/mission`, More > Today); PC:
`js/next/mission.js` (page `mission`, Main group right after Home). Data: the live board only (+ the Live View data for BLITZ's line,
the news calendar); read-only. Tests: `python -X utf8 -m tests.test_space_ui`.

| # | Feature | Status | Where |
|---|---|---|---|
| 51 | Deep space 3D background | new | Both apps by default: Earth (oceans, continents, clouds, night-side city lights), the Moon crossing the Sun with its round shadow sliding over the Earth (city lights come on inside it), the Sun's corona + glare + lens ghosts, three-layer parallax stars, Milky Way, nebulae; slow camera drift, pointer / scroll / tilt parallax; warp streaks on a page change. Settings Max / Lite / Off (+ Deep space / Galaxy) |
| 52 | Bot satellites | new | Three satellites orbit the Earth: Zlarior blue, ATLAS orange, BLITZ purple; dim when off, breathing when waiting, a ring ping when armed, bright with a beam to the ground while in a trade (from the live board) |
| 53 | Shooting star per closed trade | new | Green for a win, red for a loss, once per newly closed trade (the board's trade log, remembered per device) |
| 54 | Aurora follows today's P&L | new | The atmosphere rim and the night-side aurora turn green on a green day, red on a red day, cyan when flat (sum of today's real P&L of the accounts) |
| 55 | Mission Control | new | The three accounts as orbits / planets (Zlarior 50K, ATLAS 25K, BLITZ 25K "paper / not live yet" until its account exists): balance, $ to target, room to the floor, today's P&L, the open position with $ at stop / target, eval day N of 10, next window countdown, the bot's thinking line, a health light. Phone: Home strip + #/mission; PC: Main > Mission Control |
| 56 | Today's mission | new | One line per bot: what it is waiting for or doing right now (Home strip + Mission Control) |
| 57 | Next-session countdown | new | Market open / closed and the time to the next 18:00 ET session (Home strip + Mission Control) |
| 58 | If it stops out now | new | Per account: $ lost at the stop and the room to the floor after it (flat: one full stop at today's size), the day-loss used |
| 59 | Why no trade yet? | new | Per bot: market closed, outside its hours (next window), daily limit, every guard with its fix, the setup stage, rules (Monday), news close by |
| 60 | Session timeline | new | 18:00 → 17:00 ET with Asia / London / New York, each bot's entry hours (ATLAS per member), the news, now, the 15:55 flat |
| 61 | Alerts center | new | Every red / amber item (board lines, guards, health strip, a stop-out that would leave little room, the bot's feed) with All / Red / Amber filters |
| 62 | Health constellation | new | PC bot · NinjaTrader · feed · heartbeat · phone feed · cloud as linked stars, red links where the chain breaks |
| 63 | Eval runway | new | $ to go per session left vs the backtest's $ per session, and how many winners at today's size it takes |
| 64 | Streaks & consistency | new | Green / red booked days, the current streak, the best day as a share of the profit vs the MFFU 50% payout rule |
| 65 | Daily loss & week pace | new | The daily loss limit used today (gauge) and this week's trades vs the 2-4 goal |
| 66 | Next news | new | The next high-impact events with a countdown |
| 67 | Live View market structure | new | When the data has `structure` (engine/liveview_api.view): premium / discount shading, liquidity pools (BSL / SSL, swept ticked), HH / HL / LH / LL swings of 5m / 15m / 1h, each frame's last BOS / CHoCH, protected high / low, a Structure switch and a "Market structure" card in the thinking panel; nothing is drawn without the block |
| 68 | Telemetry strip | new | Mission Control's top: NQ price (last bar), ATR, VIX / VXN, the VIX-band objective down / up, a ticking ET clock (from the board's map) |
| 69 | Satellite name tags | new | A small tag rides next to each bot's satellite in the 3D sky ("Zlarior · IN TRADE", "ATLAS · ARMED", "BLITZ · PAPER"), hidden behind the planet; each eval's progress to its target as a ring around its planet on Mission Control |
| 70 | Holodeck | new | The day in 3D on both apps (PC Main > Holodeck after Live View, phone #/holo + Home button): every fill at its exact second and price (real solid, paper hollow, slip vs the model), trades as glass volumes with the stop stepping to break-even, each LIT setup step by step, what every bot is thinking (panels in the scene + the Minds panel), working orders, levels, structure; Flat / 3D / Fly camera, replay 1x-120x, day picker, full screen; 2D fallback without WebGL (tests.test_holo_ui) |

## G. BLITZ tab, the Mind, Trader's deck (2026-10-29 night, owner: "How's the scalp bot coming along? Make a separate tab at the bottom ... keep finding stuff to add")

Shared renderers, each a byte-identical copy in both apps: `blitzcore.js` (window.BlitzUI), `mindcore.js` (window.MindUI),
`deckcore.js` (window.DeckUI); phone `tools/web_public/blitz.js`, PC `web_next/js/next/blitz.js`. Data the apps already have:
the BLITZ paper shadow (`engine/blitz.card`: data.json "blitz" on the phone, `GET /api/next/blitz` on the PC = the card + account
C's block), the Live View BLITZ layer (liveview.json / `/api/next/liveview`), account C (live.json `pc.account_c`), the live
board, goals.calendar, the news; the Mind block (liveview.json / live.json "mind", `/api/next/mind`; nothing drawn while it is
absent). Read-only: no new control, only links. Tests: `python -X utf8 -m tests.test_blitz_tab [--shots <dir>]`.

| # | Feature | Status | Where |
|---|---|---|---|
| 71 | BLITZ tab | new | Phone: a sixth bottom tab (Home · Zlarior · ATLAS · BLITZ · Money · More, 44 px targets at 390 px), `#/blitz/<part>`; PC: Main > BLITZ right after ATLAS. Sections: **Today** (state, next check with a countdown, today's noise band drawn per check with the price and the signals, the day filter verdict "trading today" / "skipped: yesterday's range X x its 14-day mean", signals, the open PAPER / SIM / REAL position with $ at the stop and the trail, account C off / Sim test / armed / paused with its eval and scorecard), **Brain** (what it is thinking, the playbook rule now B1-B8 with the ladder, structure note, the two paper ledgers, the Mind's BLITZ cards), **Trades** (account C's real / Sim trades, the paper 25K eval and 50K + LIT ledgers, a 3D replay link per trade, pictures when they exist), **Results** (the research bands of BLITZ_STRATEGY.md with $ a month, live vs the band per metric, the kill-switch contract with the floors and how close it is, paper evals), **Rules** (BLITZ_STRATEGY.md in plain words), **Go live** (the 3 steps for next week, the console line, preflight from the data) |
| 72 | Mind (Brain v2) | new | Phone `#/mind` (More > Today) + PC Main > Mind: market regime (trend, volatility, day type with its accuracy note), each bot's if-then game plan (scenarios with levels, $ expected, odds, what changes its mind), similar past setups (n, win %, avg R, $, confidence, examples), A-F trade reviews (right / wrong / lesson / luck, Holodeck link), self-research ideas with their H1 / H2 / 2021-25 evidence and status, alerts, IQ (setups stored, calibration). Per bot on the Zlarior Bot Brain, ATLAS > Brain and BLITZ > Brain; a compact card on Home (both apps) |
| 73 | Risk meter (all accounts) | new | Home (both apps) + Trader's deck: open risk $ on Zlarior / ATLAS / BLITZ vs each room to the floor, today's daily loss used + the open risk vs each limit, and "if every open trade stops out now" vs the combined daily loss |
| 74 | Next 24 hours | new | Home (compact) + Trader's deck: a 24 h track per bot (Zlarior 02:00-15:30, each ATLAS member's hours, BLITZ's 10 checks as ticks), the 15:55 flat, the CME halt and the 18:00 open, the news, early closes (flat 5 min before the halt), the US clock change within 7 days (Sun Nov 1: clocks back; every time stays ET) |
| 75 | Eval odds from today's balance | new | Trader's deck: pass / undecided / fail within the sessions left, from today's $ to go and room (a random walk at the 2026 H2 pace: Zlarior from the backtest cone, the others from their $ per session), next to the research odds from the start; labelled an estimate |
| 76 | Real P&L calendar per bot | new | Trader's deck: the last 6 weeks as day squares per bot (green / red, brighter = bigger), green / red days and the total; real fills only (the board's real trades, account C when it is live), never paper |
| 77 | Trade journal | new | Trader's deck: every trade on the board (REAL / PAPER) with its Mind review grade and lesson, and a "Replay in 3D" link (Holodeck on that day) |
| 78 | Notification center | new | Trader's deck: every red / amber board line, health item, guard, Mind alert, the paused contract and the bot's feed in one list, All / Red / Amber, a mute per bot (Zlarior / ATLAS / BLITZ / System) kept on this device only (pushes keep their own settings) |
| 79 | Since you last looked | new | Home (both apps) + Trader's deck: closed / opened trades (real $), alerts, reviews and ideas since this device last opened Home (localStorage) |
| 81 | Live board: BLITZ's own card | new | `boardcore.js` (both apps): once account C is on (the board's `blitz` block), "Right now" shows a third card (balance, room, today, session, the open position, what it waits for, the blocks), the Home cut a third mini card, the trade log a BLITZ filter, "Week and eval" its progress; two accounts exactly as before otherwise |
| 80 | Holodeck replay links | new | Mission Control (both apps) + Trader's deck + BLITZ trades + Mind reviews: "Replay a day in the Holodeck" per traded day; the phone opens `#/holo/<day>`, the PC opens the Holodeck on that day |
| 82 | Status bar | new | Night 3 (2026-10-30), `statuscore.js` (both apps, byte-identical): one bar on top of Home answers "is everything OK right now?" (PC bot, NinjaTrader, feed, Zlarior / ATLAS / BLITZ, the next window with a countdown, alerts) in one sentence + chips; a tap opens every line with its fix. A quiet PC is amber until 30 min before a window, then red |
| 83 | Sunday open readiness | new | Home (both apps), Fri 00:00 -> Sun 20:00 ET (from Thu 18:00 on a clock-change weekend): CME reopens Sun 18:00 ET, "clocks go back 1 hour" on Sun Nov 1 2026, what each bot does first (Zlarior Mon 02:00 ET, ATLAS's first member window, BLITZ off until its 25K), a readiness list (PC + bot, NinjaTrader, bars, Windows clock) |
| 84 | Account cards with eval rings | new | Phone Home + the top of each bot tab: one card per bot (Zlarior 50K, ATLAS 25K, BLITZ 25K) with an animated ring (progress to the target, or the share of the max loss used in red), $ to the target (count-up), room + eval day, today's real $, a sparkline of the real days, a REAL / SIM / PAPER tag, a state chip |
| 85 | Each bot's day in one line | new | `StatusUI.oneLine`: in a trade / armed / window open until hh:mm / next window with a countdown / done for today / blocked, on the account cards and in the status bar |
| 86 | What matters now | new | Phone Home: the open trades ($ at the stop and target), the next window (countdown), the next high-impact news in 24 h, the last REAL trade (NinjaTrader fills only) |
| 87 | Search palette | new | Phone: a search button in the header (and "/" or Ctrl/Cmd+K): every page, each bot's five sections and live numbers ("Zlarior: $4,600 to the target"), letters-in-order matching, recent picks first, arrow keys + Enter (the PC keeps its Ctrl K palette) |
| 88 | Smart empty states | new | `StatusUI.empty(kind)`: what will appear and when (trades, real results, BLITZ paper, Mind, the PC feed); every older empty box gets the same calm style |
| 89 | Once-a-day intro | new | Phone: the first open of the day only (ET date in `le.intro.day`), skippable (tap, any key, Skip): a light-speed star field settles, the three bots' orbs swing into orbit, the day's status line; never under reduced motion / Motion off / an automated browser (unless `?intro=1`) |
| 90 | Motion system | new | Page transitions, card entrances (40 ms apart, first visit only), count-ups, press states, rings / sparklines drawn in once per visit (not on every live redraw), glowing live dots, the sky's parallax with scroll / tilt / mouse; reduced motion = none (both apps) |
| 91 | Sharper deep space | new | fx.js: the Earth bake at 1536 px on a Retina phone at Max (was 1024; Lite / small screens unchanged), crisper pin-point stars |
| 92 | This week vs the goal | new | `StatusUI.week` (phone Home, PC Home under the status bar): per bot this week's real trades against its goal (Zlarior 2-4, ATLAS 3-4), Mon-Fri as dots (green / red day, today ringed, future dashed) and the week's real $ (the board's `progress`) |
| 93 | Since you last looked, in one line | new | Phone Home > What matters now: the deck's digest (closed / opened trades with real $, alerts, reviews, ideas since this device last looked) as one row with a count, one tap to the deck |
| 94 | Greeting + ET clock | new | Phone Home: "Good evening" and the date + time in ET (the bots' clock) above the status bar, ticking |
| 95 | Sliding tab pill | new | Phone bottom bar: one glass pill slides to the open tab in that tab's colour (Zlarior blue, ATLAS orange, BLITZ purple); reduced motion = it jumps |
| 96 | Status dot on every page | new | Phone header: one dot with the status bar's verdict (green / amber / red, a soft pulse when all good) on every page; a tap opens the full status on Home |
| 97 | Recent pages | new | More: the pages you opened last as chips under the search box (`le.pl.visits`, this device only) |
| 98 | Cinematic sky | new | Both apps: a soft vignette and a faint top light over the deep-space sky (the CSS sky and the 3D scene), dark theme only; the CSS sky drifts a little with scroll / tilt / the mouse |
| 99 | Ctrl K knows the bots | new | PC palette: each bot's five sections ("ATLAS · Rules", "BLITZ · Trades" ...) and "Status: <verdict>" (opens Home with the status bar open) next to every page |

## Organization (2026-10-30, night 3: "organized, clean")
- One information architecture on both apps. **Home** = the status bar, the three accounts, what matters now (+ the Sunday
  open card on weekends, quick tiles to Live View · Holodeck · Mission Control · Mind); every older Home card (Mission
  strip, the real accounts in full, Safety, Right now, the deck + Mind, launch checklist, plan, one tap away) is under
  **Everything else on Home** (one tap, remembered). **Each bot tab** = Today · Brain · Trades · Results · Rules in the same
  order and words (Zlarior: Plan / Levels are chips under Today, Strategy is Rules; ATLAS: Setups is Rules, Setup stats under
  Results; BLITZ: Go live is a chip under Rules). **Money** = real money only (Real results · Accounts today · Eval timeline);
  the research $ pages (Money plan, prop firms, what-if, scale, accounts) moved to More > Money planning with their links.
  **More** = Today · Insight · Bot and health · Trades · Money planning · This app, Advanced folded, searchable.
- PC sidebar Main in plain sections: Home · Start, **Bots** (Zlarior · ATLAS · BLITZ, in their colours), **Live** (Mission
  Control · Live View · Holodeck), **Money** (Real results), **Insight** (Mind · Trader's deck · AI Insights), All tools.
- Duplicates out: one freshness pill in the phone header (the PC's live chip wins over the cloud one; offline / stale
  banners still show), the per-page refresh line folded into it, the Zlarior Today plan line (same as "Right now"), the
  Safety card no longer piles up on every live redraw (real.js), the critical alert one line on every page but Home.
- Colour roles: Zlarior blue #4f9bff, ATLAS orange #ff9a3d, BLITZ purple #b388ff on the tab bar, section bar, cards and
  sidebar; good / warn / bad for state only. Nothing was deleted; every old link (#/plan, #/strategy, #/money, #/second ...)
  still opens its page.

## Organization (2026-10-28)
- PC sidebar Main (6 items): Home · Start · Zlarior · ATLAS · **Real results** · All tools; the backtest page is renamed
  **Backtest & research** (was "Results") and sits under Advanced > Results; everything else stays under Advanced. Strategy 3 has a placeholder card on Home ("Strategy 3 (research)", paper only).
- Home order: verdict · Today · real accounts · launch checklist (until green) · what to do now · Right now · Safety ·
  health · eval cards (folded) · today's setups / news / log (folded).
- Phone: Home starts with the real accounts + Safety (the paper/verdict hero cards and the "last trade" card step aside);
  Money tab gets Real results (#/real).
