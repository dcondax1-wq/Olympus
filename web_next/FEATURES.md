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

## Organization (2026-10-28)
- PC sidebar Main (6 items): Home · Start · Zlarior · ATLAS · **Real results** · All tools; the backtest page is renamed
  **Backtest & research** (was "Results") and sits under Advanced > Results; everything else stays under Advanced. Strategy 3 has a placeholder card on Home ("Strategy 3 (research)", paper only).
- Home order: verdict · Today · real accounts · launch checklist (until green) · what to do now · Right now · Safety ·
  health · eval cards (folded) · today's setups / news / log (folded).
- Phone: Home starts with the real accounts + Safety (the paper/verdict hero cards and the "last trade" card step aside);
  Money tab gets Real results (#/real).
