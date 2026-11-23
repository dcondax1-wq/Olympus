# Liquidity Engine: NQ futures bot (MFFU Builder 50K)

A mechanical **liquidity sweep → IFVG → draw-on-liquidity** model (Blake-style mech model) with
multi-timeframe context, AMT-derived location and evidence-based confluence scoring. It ships with a dashboard:
command center, chart, replay, backtest lab, prop lab, robustness + exit lab, confluence lab, live/paper bot,
journal and playbook.

## Owner: daily use (Windows PC bot)

Double-click in the bot folder (or the desktop icons `tools/bat/SETUP_SHORTCUTS.bat` makes once): **START_DASHBOARD**,
**HEALTH_CHECK** (green / red checks with the fix), **UPDATE** (stop, pull, pip, restart, self-test), **STOP_BOT**.
Every day: [docs/DAILY_CHECKLIST.md](docs/DAILY_CHECKLIST.md). Something red: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
First-time go-live steps: [docs/GO_LIVE_TONIGHT.md](docs/GO_LIVE_TONIGHT.md).
Last visit to the Surface (no sleep, no update restarts, starts at logon, offline alert): [docs/ONE_TIME_SETUP.md](docs/ONE_TIME_SETUP.md) (`tools/bat/ONE_TIME_SETUP.bat`).

## Quick start

```bash
pip install fastapi uvicorn pandas numpy
python tools/import_tv.py <folder>   # TradingView NQ1!/ES1! exports -> data/ (NinjaTrader bars come in live)
python server.py              # dashboard -> http://127.0.0.1:8765
python bt.py NQ 5m '{}' -v    # CLI backtest with the trade list
```

## The strategy (defaults in engine/model.py)

| Layer | Rule |
|---|---|
| Liquidity map | PDH/PDL, prior-week H/L, Asia / London / overnight H/L, 1H swings, 15m ITH/ITL, equal highs/lows |
| Timeframes | 1D / 4H / 1H / 15m FVG respect-disrespect order flow, 1H + 15m structure, 1H dealing range, HTF FVG key levels |
| Sweep | price trades ≥1 tick through a pool from 08:00 ET → arm the opposite direction |
| Trigger | body close through an FVG inside the manipulation leg (IFVG) on 5m; CISD fallback |
| Score (min 1) | +1 1H trend aligned (−1 against) · +1 sweep in discount/premium of 1H range · ±1 low/high-resistance path · −1 15m already turned (late) |
| Target | nearest **major** untaken pool ≥1.5R (capped at 5R) |
| Stop | 1× buffer beyond the sweep extreme (10–60 NQ pts) |
| Management | no partials, no trailing · breakeven at +1R · exit if not +0.5R within 30 min · flat 15:55 ET |
| Size | $350 base risk in micros × conviction (×1.33 VWAP-side entry, ×0.67 volume-climax raid / first hour) |
| Risk guard | drawdown-aware cap, max 2 trades/day, stop after a winner, $600 daily stop, 40 micros max |
| Windows | NY AM 09:30–11:30 and PM 13:30–15:30 ET (London tested and cut) |

## Results: NQ 5m, 2026-08-06 → 2026-10-15 (real CME futures bars)

- **33 trades (3.3/week) · 48.5% win · +1.06R/trade · PF 5.27 · +$12,716 · max DD −$1,068 · worst day −$468**
- MFFU Builder 50K: 36/36 rolling-start evals passed (avg 11 days); Monte Carlo 99% pass, median 12 days
- Eval Sprint preset ($450): avg 9.3 days, 97% Monte Carlo pass, 0 rolling failures
- All 384 grid configs profitable out-of-sample; every walk-forward fold profitable; robust to 3-tick slippage;
  PF 1.9 even without the 5 best trades

### What the research kept, cut and learned
- **Kept:** 1H trend, premium/discount, LRL/HRL path, late-entry penalty, major-pool DOL targets, BE at 1R, 30-min time stop.
- **Cut (no edge):** AMT-location points, protected H/L, SMT, pool quality, AMT targets, partials (all variants),
  trailing stops, London session, hard MTF alignment gates, the walk-forward learner (needs more data).
- **Learned → conviction sizing:** VWAP-side entries help; volume-climax raids and first-hour entries hurt (sign-stable on NQ and ES).
- **ES does not work with this model** (0/384 configs profitable out-of-sample). Trade NQ.

### News, volatility, gamma, Quarterly Theory and trade grades
- **News & Risk page**: Forex Factory weekly calendar (all currencies), BLS/Fed historical calendar (`data/build_news.py`),
  headlines (ForexLive, CNBC, MarketWatch, Investing.com, Fed), VIX/VXN regime, NQ day-range vs 20-day average,
  mega-cap earnings, and a live trade guard (also shown in the top bar and enforced by the live bot).
- Defaults: no entries 15 min before → 30 min after high-impact USD releases, no FOMC-day afternoons, flatten 5 min
  before a release, no new entries once the day has run 1.6× its normal range. News/VIX never explained the losing regimes;
  the guard is a safety net. The day-range guard removed losing trend-day trades.
- **Gamma** (`engine/gamma.py`): SqueezeMetrics daily S&P GEX history + live QQQ call wall / put wall / gamma flip mapped to NQ
  (chart layer "Gamma"). Gamma regime did NOT separate winning from losing periods: context only.
- **Quarterly Theory / AMD**: 90-min and 22.5-min quarters, true opens (session 07:30/13:30, 90-min, weekly, daily 18:00).
  "Q2 manipulation → Q3 entry" and "raid beyond the 90-min true open" helped in 2 of 3 periods: graded at partial weight.
- **Trade grade A+…D**: every signal gets a checklist of learned confluences weighted by evidence; size A+ ×1.5 … D ×0.5.
  Graded sizing beat conviction sizing in all three periods. "Defensive" preset skips D grades.
- Current default (NQ 5m, Aug–Oct 2026): 31 trades (3.1/week), PF 7.26, +$14,190, max DD −$654.

### Placebo test and out-of-period check (deeper research)
- **Placebo (NQ futures 2026):** 1,000 random-time/random-direction strategies with identical stops, targets and
  management average −0.06R; the real strategy (+1.06R) beats 999 of them (p ≈ 0.001). Flipping real entries loses
  (−0.27R). 90% CI of avg R: +0.45R to +1.68R. Within this sample the entries carry real information.
- **Out-of-period on Dukascopy Nasdaq-100 CFD (Q4 2023, Q4 2025): the strategy LOSES** (−0.35 to −0.41R/trade,
  ~15% win rate, worse than random). Either the edge is regime-specific, or the CFD (cash-index pricing, broker tick
  volume) behaves differently from CME futures. An overlap test on CFD data for Aug–Oct 2026 (`--range`) decides
  which. **Until the strategy is confirmed on more real futures history, do not trade it live with real money.**

### Testing on real futures (TradingView / NinjaTrader / Databento)
- `tradingview/liquidity_engine.pine`: Pine v5 port of the default strategy. Paste into the Pine Editor, add to an
  **MNQ1! 5m** chart, open the Strategy Tester (Deep Backtesting for multi-year history). Export the trade list to compare.
- `data/import_futures.py csv NQ export.csv`: TradingView *Export chart data* (NQ1!/MNQ1! 5m or 1m) into the full engine.
- `data/import_futures.py ninjatrader NQ export.txt` or `... databento NQ 2024-01-01 2026-08-01` (needs DATABENTO_API_KEY).

### Honest caveats
Only ~50 sessions of free intraday futures data exist, and several study rounds have looked at the after-split
window, so it is no longer pristine. Treat the numbers as promising, not proven: **paper trade 2–4 weeks first.**
Long-horizon validation: `python data/dukascopy.py 1 NQX` (slow, throttled), then Robustness → "Run NQX test".

## Live / paper trading (engine/live.py)
The live bot re-runs the same engine on every closed bar. Adapters: **paper** (default), **TradersPost** webhook,
**Tradovate** REST (demo unless `TRADOVATE_ENV=live`; credentials only via env vars; untested against a real account).
Non-paper adapters must be explicitly armed; a kill switch flattens and stops.
**MFFU:** automation is reported as allowed with **active oversight**; no unattended bots, HFT or sim-fill exploits. Confirm with MFFU.

## Going live (Tradovate / MFFU)
Execution: `engine/tradovate.py` (REST adapter, bracket entries via `placeOSO`, stop modify, cancel, liquidate, kill)
and real-time bars via the Tradovate market-data websocket (`TradovateData`). Checklist: `engine/golive.py`.
Offline proof of the order lifecycle without credentials: `python -m engine.tradovate` (mocked HTTP, prints every payload).

**Morning procedure (do it in this order):**
1. **API key.** Tradovate web/desktop > Settings > **API Access** > generate a key: note the **CID** and **secret**.
   Market data for the bot comes from the Tradovate entitlement that ships with the MFFU account (no extra feed needed).
2. **Credentials in your environment only** (never in the dashboard, never in chat, never committed). Create
   `.env.local.ps1` next to `server.py` with placeholders replaced, then dot-source it in the PowerShell window that starts the server:
   ```powershell
   $env:TRADOVATE_USER   = "your_tradovate_login"
   $env:TRADOVATE_PASS   = "your_tradovate_password"
   $env:TRADOVATE_CID    = "12345"            # API Access > CID (integer)
   $env:TRADOVATE_SECRET = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
   $env:TRADOVATE_APP_ID = "LiquidityEngine"  # optional, default
   $env:TRADOVATE_ACCOUNT = ""                # optional: account name or id when you have more than one
   $env:TRADOVATE_ENV    = "demo"             # demo first; "live" only after the checklist is green
   ```
   `. .\.env.local.ps1; python server.py` (add `.env.local.ps1` to any backup/ignore list).
3. **Checklist on DEMO.** Open the Live page: the "Go-live checklist" runs automatically (credentials, auth, account
   + balance, front-month contracts and expiry, bar-feed freshness, clock drift, risk settings vs MFFU 50K, news
   blackout, live gate, presence acknowledgement). Every red row says what to fix. Press **Round-trip test (demo)**:
   it places a 1-lot MNQ limit far below the market and cancels it; the Tradovate order log must show both.
4. **Shadow run on demo.** Execution = *Tradovate DEMO*, Bar source = *Tradovate market data*, tick "present and
   monitoring", Start bot. Let it take at least one full signal (entry + bracket + exit) on the demo account.
5. **Switch to live.** Stop the server, `$env:TRADOVATE_ENV = "live"`, restart, re-run the checklist (expect
   "LIVE env but NOT armed"). Type **`I ACCEPT LIVE RISK`** in the Arm panel, press **ARM LIVE** (pill turns red
   "LIVE ARMED"; arm state is memory-only and resets on restart).
6. **Paper-shadow first signal, then live.** Start once more in *Paper* for one signal while the live account is armed
   but idle, compare the paper entry with what you see on the Tradovate DOM; then Stop, select *Tradovate LIVE*, Start.
7. **Kill switch**: hold the red button 1.5 s (or `POST /api/live/kill`): cancels every working order, liquidates,
   stops the bot. The adapter also refuses entries after `flat_mod` (15:55 ET) and flattens anything open at that time.

**Hard gates in code:** live URL only when `TRADOVATE_ENV=live` **and** the start config is armed **and** carries the
phrase; orders above `max_micros` (40) or 4 minis are refused, not clamped; every order is sent with `isAutomated: true`;
logins are rate-limited (Tradovate allows 5/hour: tokens are cached ~90 min and renewed, never retried in a loop);
Live trading requires a real-time CME bar source (NinjaTrader, or **Tradovate**).

**MFFU Builder 50K notes (confirm the current rules on the MFFU site before trading):** automation is allowed only with
the trader **present and actively monitoring** (no unattended runs, no HFT); the $1,000 daily loss limit is a *soft*
pause (the bot's own stop is $600), the $2,000 max loss trails at end of day, payout buffer $2,100, no consistency rule
during the evaluation (funded-stage consistency rules may apply later: check). The strategy **lost in 2 of 4 historical
periods**: start at the minimum size (`risk_usd` $350, 1 micro per ~$35-60 of stop distance, i.e. 1-2 MNQ per
trade) and scale only after live results confirm the backtest.

## Running unattended
The server (dashboard + paper bot + trade memory) must never live inside an editor / terminal / AI-tool session: when
that session closes, the server dies with it. `scripts\run_bot.ps1` is a supervisor that starts `python server.py`,
restarts it on any exit (back-off 5 s, 15 s, then 60 s), loads `.env.local.ps1` if present (values never printed) and
serves on **port 8766** (phone over Tailscale: `http://<PC Tailscale IP>:8766`, shown in the Tailscale app). A Task Scheduler task starts the
supervisor at logon and on unlock. Real-money execution does **not** depend on this PC (that path is the TradingView
strategy + webhook bridge); this keeps the paper mirror, the dashboard and the memory running.

**Sunday afternoon, once (PowerShell in the project folder):**
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_autostart.ps1 -DryRun   # preview, changes nothing
powershell -ExecutionPolicy Bypass -File .\scripts\install_autostart.ps1          # creates task "LiquidityEngine"
```
If it reports *Access is denied*, run the same line once from PowerShell opened with *Run as administrator* (the task
still runs as you, unelevated). Then stop any server you started by hand, **reboot**, log in, and check:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\status.ps1     # SERVER UP, SUPER alive, TASK Ready/Running
```
Open the dashboard on the phone, **Start** the paper bot, then test a crash: `.\scripts\stop_bot.ps1 -RestartServer`
(kills only server.py): within ~10 s the supervisor restarts it, the bot resumes by itself and you get a phone alert
"auto-resumed". Remove the task with `scripts\uninstall_autostart.ps1`.

**Daily commands:** `scripts\status.ps1` (up/down, bot running, adapter, `data_age_s`, last error, watchdog issues,
log tail) · `scripts\stop_bot.ps1` (intentional stop: stops the bot via the API, which also turns auto-resume off,
then ends server + supervisor) · `stop_bot.ps1 -KeepAutostart` (end everything but resume the bot at the next start)
· `stop_bot.ps1 -RestartServer` (pick up code changes; the bot resumes) · `Start-ScheduledTask LiquidityEngine`
(start the supervisor without logging off).

**Auto-resume.** Every successful Start writes `data/autostart.json` (the start config with passwords / tokens /
webhook URLs / confirm phrases stripped, `saved_at`, `mode`). When the server starts and that file is less than 7
days old, a **paper** or **Tradovate DEMO** bot is started again automatically (the bot's own `live_state.json`
restore then brings back today's ledger, open position and kill flag), an alert is sent and a log line written.
**Live never auto-resumes** (tradovate-live, or `tradovate` while `TRADOVATE_ENV=live`, or TradersPost): you get an
alert "bot NOT resumed" instead. Stop and the kill switch delete the file, so an intentional stop stays stopped.
Set `LE_NO_AUTOSTART=1` to disable resume for one run.

**Watchdog + keep-awake** (inside the server): every 30 s it checks for a poll older than 3 x `poll_sec`, a dead poll
thread, and a stale feed for more than 10 min between 09:00 and 16:00 ET on weekdays; each condition sends one
alert (at most every 30 min) and a "recovered" message. `GET /api/health/watchdog` shows `{ok, issues, uptime_s,
server_started_at, autostart, keepawake}`; `GET /api/health/ping` is the endpoint for an external uptime monitor.
While the bot runs, the server asks Windows not to sleep (`SetThreadExecutionState`, this process only; no power
plan or setting is changed; the screen may still turn off). Configure Telegram/Discord in Settings so these alerts
reach the phone.

**Windows settings to set by hand for the week:**
- Settings > Windows Update: **Pause updates** for 1 week, and set **Active hours** to cover 08:00-17:00 ET (an
  update reboot logs you off; the task restarts the server only after you log back in).
- Settings > System > Power: **Sleep = Never when plugged in** (keep-awake covers the bot, not the dashboard alone),
  and keep the PC on AC power.
- Tailscale: **Run at login / start automatically** and stay signed in; otherwise the phone URL dies after a reboot.
- Consider automatic sign-in after reboot only if the PC is physically secure (the task runs only while you are
  logged on).

**Logs:** `logs\server-YYYYMMDD.log` (one per day, 30 days kept): `[supervisor]` lines are starts, exits with exit
code and run time, and restarts; `[autostart]` lines say whether the bot resumed and why; `[watchdog]` lines are the
alerts; Python tracebacks from failed polls appear in between. A server that keeps exiting within seconds shows as
"restarting in 60 s" repeatedly: read the traceback above it.

**Honest limits.** If the PC loses power, crashes hard, is logged off (Windows Update reboot) or loses internet, the
paper bot, dashboard, alerts and watchdog all stop with it, and nobody is told (the watchdog lives in the same
process; point an external monitor at `/api/health/ping` over Tailscale if you need that). Any real position is
protected only by the brackets (stop + target) already resting at the broker: while the PC is down there are no new
trades and no management (no stop moves, no time flatten from this machine). After a restart the bot does not chase
entries it missed and logs any position it cannot account for.

## Live via TradingView (computer off)
Tradovate does not issue API keys for prop-firm / evaluation accounts (MFFU included), so the REST adapter above
cannot reach the MFFU account. The live path is instead:

`tradingview/liquidity_engine.pine` (Pine v5 strategy on TradingView's servers, MNQ1! 5m) -> one alert with message
`{{strategy.order.alert_message}}` -> webhook -> **TradersPost** (default) or **PickMyTrade** -> Tradovate OAuth -> MFFU.

- The script is the Python model's DEFAULTS in Pine: grade sizing A+..D, trending-regime half size, MLL-aware risk
  cap, 1.6x day-range filter, pasted news blackout list, breakeven at 1R, 30-min time stop, giveback exit, 15:55 flat,
  2 trades/day, stop after a win, $600 daily stop. Every entry sends a market order with its stop and target attached.
  Bot exits send `exit`, and breakeven sends a stop modification.
- Owner steps (TradingView 2FA, bridge choice and costs, OAuth to MFFU/Tradovate, the single alert, paper first,
  pause / kill switch, MFFU oversight) and the full Pine-vs-Python difference list are in **`tradingview/BRIDGE_SETUP.md`**.
- Parity check: export the Strategy Tester "List of trades" CSV, then
  `python -X utf8 tools/pine_parity.py <export.csv>` (matched table + parity score; `--selftest` runs it on a
  synthetic export).
- Re-create the alert after changing any input (the weekly news list included): an alert freezes the inputs it was
  created with. Computer-off does not mean unattended: MFFU requires you to be present and monitoring.

## Research scripts
`research.py` (384-config OOS grid) · `study_mtf*.py` (timeframes) · `study_exits.py` / `study_combo.py` (TP/SL/partials) ·
`study_dol.py` (draw on liquidity) · `study_pass*.py` (eval speed) · `study_conf2.py` / `study_conv.py` (confluence discovery) · `study_final.py`

Not financial advice. Backtests are hypothetical; futures trading carries substantial risk of loss.
