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
- **Frequency:** at least **2 setups a week**. Never make a filter that pauses trading for weeks the default.
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
  the PC is on). The UI is the ES-module SPA in `web/`, with the API in `engine/dash_*.py`.
- **PC-off:** the GitHub Actions cloud monitor runs every 15 min on market days. It is the same engine and settings as
  `live_model.json`, keeps a paper ledger plus an MFFU eval tracker, sends Telegram/Discord alerts, and publishes README.md and
  chart.png to the `dashboard` branch (read in the GitHub app).
- **TradingView:** Pine port in `tradingview/liquidity_engine.pine` (parity notes in `research/PINE_PARITY.md`). It does **not**
  have the cold-streak filter or the new sizing/target rules yet.
- Refreshing `data/*.csv` needs the owner's TradingView export (tools/grab_tv_export.py on the PC). Cloud sessions can't do it.

## Open work
1. **Dashboard revamp** (owner priority): a premium dark "command center" look, no default browser controls, custom SVG icons,
   glass cards, animated numbers, phone-first.
   - Top level: Today · Chart · Trades · **Data** (Results, Backtests, Replays, Tested Variants, What the Bot Learned, Study Trades,
     Deep Stats, Data Sources) · **Modules** (tile grid: Strategy Rules, Liquidity Engine, Cold-Streak Filter, Risk & Sizing,
     Markets & News, Regimes, Confluence Lab, Robustness, Prop Firms, Memory, Briefing, Reports, Journal, TradingView, Alerts) ·
     Settings. Ctrl+K command palette.
   - Build in `web_next/` and swap when verified. `engine/ui_api.py` is an unfinished start; it is not committed.
2. Phone dashboard on the `dashboard` branch: per-trade stop pts, micros, $ risk, R, half-size flag, eval progress bar.
3. Port the cold-streak filter plus the new sizing and target rules to the Pine script.
4. Optional: test "smaller size when inducement was taken first" when more data exists.
