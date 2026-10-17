# NQ Liquidity Engine: brief for Claude sessions (local or cloud)

The owner trades a **MyFundedFutures (MFFU) Builder 50K** eval and is building this NQ futures bot. They are not a coder and
usually write from a phone. Reply short, plain and result-first: what changed, the numbers, what's next. Do the work instead of
asking; show evidence (backtest numbers, charts) and be honest when something doesn't work.

## Hard rules (never break)
- **Futures data only:** TradingView CME `NQ1!` / `ES1!` exports in `data/` (5m 2021-11 → 2026-10-16; 1m for 2026). Never CFD,
  never Yahoo for testing. The live paper feed polls Yahoo `NQ=F`; say so when it matters.
- **No paid services.** The free PC-off path is the GitHub Actions cloud monitor (`.github/workflows/cloud-monitor.yml`).
- **Paper only.** Never arm live trading or place real orders. MFFU requires the owner to be present for live trading.
- **No secrets in the repo or chat.** `data/alerts.json`, `tv.json`, `tv_device.json`, `autostart.json`, `live_state.json`, `memory.db`
  and `.env*` are gitignored. Telegram/Discord keys live in GitHub Secrets only.
- **Frequency:** **2-4 trades a week** (owner, 2026-10-17; before: at least 2). Never make a filter that pauses trading for weeks the
  default; prefer size changes over skipping.
- **Owner requirements (2026-10-17), keep them in every report and on the dashboard:**
  - Implement what the research proves (better in 2026 AND 2021-25, 2-4 trades a week); store every experiment with its data
    (`tools/runlib.py` → `research/runs/`) and write it up in plain language (`research/writeups/`).
  - **Money, not only R:** every result shows net $ and $ per month next to PF / R.
  - **Eval speed on the MFFU 50K:** an eval should be passed or failed within **2 weeks** and never take more than **3 weeks** to
    pass. Scored as `p10/f10` (pass/fail within 10 sessions), `dec10` (% decided in 10), `p15/f15`, `slow_pass` (% of passes
    slower than 15 sessions) and `pass_med` (median sessions to pass) in every run. The live strategy as of 2026-10-17 decides
    only 19% of evals in 2 weeks (2026) and 6% (2021-25): a fast-eval sizing mode is open work.
  - The strategy is written in plain language in its own area of the dashboard (Strategy page, versioned, with its numbers).
- **Stops** go beyond the sweep extreme, i.e. the high/low made before the IFVG, never at a fixed distance. **Wide stop means less
  risk**: size follows the stop.
- Every result is judged on 2026 **and** on 2021-25 (5 years). A change is adopted only if it holds in both and keeps 2+/week.
  Report trades/week, % weeks with 2+, PF, net, max DD, and MFFU eval pass/fail within 2 weeks and 1 month.

## Live strategy (locked 2026-10-17): `live_model.json` + `STRATEGY.md` (exact rules)
- **Liquidity Engine, eval mode** (`engine/model.py`):
  1. Sweep of a liquidity pool from 08:00 ET.
  2. IFVG/CISD trigger in the killzones (09:30–11:30, 13:30–15:30).
  3. Stop beyond the sweep extreme (10–60 pts).
  4. Target the nearest **major** pool ≥1.5R away, banking 5R on the way when the draw is farther. No major pool means no trade
     (`use_fallback: false`).
  5. BE at 1R, 30-min time stop, giveback exit, max 1 trade/day.
- **Size:** `risk_usd 800` up to a 20-pt stop, then scaled down by `risk_ref_stop 20` (risk = 800×20/stop); `dd_aware false`.
- **Cold-streak filter** (`engine/equity_filter.py`): if the last 15 finished signals sum ≤ 0R, trade at **half size**
  (`cold_mode: half`).
- **Results** (live-loop replay, costs included):
  - 2026 YTD: 89 trades, 2.2/wk, PF 3.48, +$20.1k, max DD −$2.7k; eval within 1 month 31% pass / 0% fail.
  - 5 years: PF 1.32, +$26.6k, max DD −$11.4k; back-to-back evals 11 passed / 19 failed. 2026 was an unusually good year.

## Tested and rejected (don't redo without a new idea)
- Published models as taught: ICT 2022, Silver Bullet, Mech/IFVG, continuation, ATM 5m/1m with a sharp V (0.2–1.5 trades/wk,
  PF ~1).
- 92 confluences; 6 daily-bias methods; grade/confidence sizing; partials and trails.
- Fixed 10–15 pt stops: wicked out, lose money. Structural stops are rarely ≤15 pts.
- Target variants: no cap / draw mode / "last real pool" all worse (2026 PF 1.6–2.2 vs 3.48).
- Re-sweep, inducement, FBOS, RBOS: recorded as engine features `x_resweep`, `x_inducement`, `x_fbos`, `x_rbos`; no edge that
  held in both periods. "No inducement" looked better, but the sample is thin.
- The skip-mode cold-streak filter: best PF, but it paused for 14 weeks, which the owner rejected.
- All variants with numbers: `research/lab/variant_results.json`.

## Key commands (run from the repo root)
- `python tools/export_backtest.py`: the live-settings 5-year replay → `research/lab/backtest_live.json`. Contains periods, months,
  stop buckets, eval odds, **per-trade reports** (why it entered / plan / result / lessons) and **lessons** (wins vs losses).
  About 1 min on 11 processes.
- `python tools/strategy_lab.py engine --name X --period ytd --params '{...}'`: score a variant. `tools/five_year.py live_jobs`
  is the exact live-loop replay.
- **Research run library** (`tools/runlib.py`, 2026-10-17): every experiment is stored with all its trades and days in
  `research/runs/<id>.json` (+ `index.json`), scored like the live results (2026 / 2021-25 / all, MFFU evals). `rl.replay(params)`
  is the exact live-loop replay (~1.5 min on 4 cores, cached in `research/runs/_cache`), `rl.size(raw, rule=...)` re-sizes
  after the fact (exact), `rl.save(...)` stores a run. `python tools/runlib.py baseline` stores the live strategy. Write-ups go in
  `research/writeups/*.md` (front matter: title, family, date, status, summary, runs). Both dashboards show runs and write-ups
  (Lab). New engine options must default to today's behaviour; bump `ENGINE_EPOCH` in runlib if an existing option changes.
- `python tools/trade_gallery.py --trades <json> --name <n> --all`: annotated trade charts → `research/lab/gallery/` (gitignored).
  Study trades the owner is reviewing are in `research/study/`.
- `python -X utf8 -m tests.test_live_dryrun --quick`: the live-loop harness. Expected 40/44; known fails:
  - replay entries/exits vs plain backtest
  - restart exit routing
  - kill switch later-route
  - "hygiene" (only when the PC bot is running)
- `python tools/cloud_monitor.py --out <tmpdir>`: dry run of the PC-off monitor (README + chart for the `dashboard` branch).

## Infrastructure
- **PC paper bot + dashboard:** `server.py` on http://localhost:8766, supervised by `scripts/run_bot.ps1` (Windows; runs only while
  the PC is on). The UI is the ES-module SPA in `web_next/` layered over `web/`, with the API in `engine/dash_*.py` and
  `engine/next_api.py`.
- **PC-off:** the GitHub Actions cloud monitor runs every 15 min on market days. It is the same engine and settings as
  `live_model.json`, keeps a paper ledger plus an MFFU eval tracker, sends Telegram/Discord alerts, and publishes README.md and
  chart.png to the `dashboard` branch (read in the GitHub app).
- **PC off, free:** `scripts/PC_OFF_OPTIONS.md` (A: TradingView brain + one tap on the phone; B: the PC wakes itself at 07:50 ET,
  trades through NinjaTrader, hibernates at 16:35: `scripts/schedule_pc.ps1`; E: a spare Surface on 24/7: `scripts/setup_dedicated_pc.ps1`;
  paid bridges / VPS only as options C-D). The always-on PC pushes a heartbeat (`engine/heartbeat.py`, branch `heartbeat`,
  on with `LE_HEARTBEAT=1`); the cloud monitor alerts when it goes silent in a session.
- **TradingView:** Pine port in `tradingview/liquidity_engine.pine` (parity notes in `research/PINE_PARITY.md`). Since 2026-10-17 it
  carries the locked rules ($800/20-pt sizing, 1 trade/day, no fallback target, cold-streak filter with a `cold size` input)
  and an "Alert format" input: bridge JSON (TradersPost / PickMyTrade) or phone text. `tools/pine_sim.py` is its bar-by-bar
  replica: 780/780 trades equal to the engine on the same bars; TradingView trades MNQ1! prices (the engine NQ1!), so a few
  trades a year differ. Expected Strategy Tester numbers and the Sunday checklist: `tradingview/BRIDGE_SETUP.md`.
- Refreshing `data/*.csv` needs the owner's TradingView export (tools/grab_tv_export.py on the PC). Cloud sessions can't do it.

## Open work
1. **Dashboard revamp: shipped 2026-10-17** (`web_next/`, served by default; `LE_UI=classic` serves the old `web/`).
   - `web_next/` overlays `web/`: server.py serves a file from `web_next/` if it exists, else from `web/`, so every page module
     in `web/js` is shared. Overrides: `index.html` (shell), `js/app.js` (router), `js/skins.js` (Obsidian default skin),
     `css/next.css` (design system + every control), `sw.js`, `manifest.webmanifest`.
   - New code in `web_next/js/next/`: `routes.js` (Today · Chart · Trades · Data · Modules · Settings), `shell.js` (sidebar,
     phone tab bar, Data tabs, Modules grid), `controls.js` (custom dropdowns replace every `<select>`, glyphs become SVG icons),
     `icons.js`, `viz.js` (SVG charts), `trades.js`, `datahub.js` (Results, Variants, Lessons, Study), `modpages.js` (Rules,
     Cold-Streak, Risk & Sizing). API: `engine/next_api.py` (`/api/next/*`, read-only, from research/lab + research/study).
   - The Today page hero is the 3D Live Oracle (see the 3D layer below). Next: polish ideas only (per-module live badges).
2. **PC-off web dashboard (done 2026-10-17):** https://demetrades2000-coder.github.io/nq-dashboard/, a Home Screen app (PWA) in the
   same dark design. One static page `tools/web_public/index.html` (+ manifest, sw.js) reads only `data.json`, built by
   `tools/build_web_dashboard.py` on every cloud-monitor run: live state + recent bars + pools, results, every replay trade with
   its report, replays (`tools/export_replays.py` → `research/lab/replays.json`, rerun after a new export), variants, lessons,
   study trades. The scheduled run uses the workflow on the default branch, so merge changes there.
   - **3D layer (2026-10-17):** three.js source in `tools/web_public/fx/src/` (`core.js` loop + quality, `field.js` galaxy background,
     `aura.js` card glow, `taps.js` tap sparks, `orb.js` Live Oracle, `candles.js` 3D chart + replay, `galaxy.js` trade galaxy,
     `city.js` month city). Build with `cd tools/web_public/fx && npm install && npm run build`: it writes the one bundle
     `tools/web_public/fx.js`, copies it to `web_next/js/fx.js` and stamps its hash into both import URLs (commit all of it). Lazy-loaded after first paint; Settings has
     Max / Lite / Off; off or no WebGL2 leaves the 2D page. `fx/dev.html?view=orb|galaxy|city|candles` is a test harness;
     add `?fxfixed` to a page URL to stop the auto resolution drop in screenshots. PC side: `web_next/js/next/fx3d.js`.
3. Pine port done 2026-10-17 (see TradingView above). Open: compile check on TradingView (6 constructs listed in BRIDGE_SETUP.md), optionally read signals from NQ1! so both feeds agree.
4. Optional: test "smaller size when inducement was taken first" when more data exists.
