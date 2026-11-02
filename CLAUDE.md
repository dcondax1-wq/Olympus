# NQ Liquidity Engine: brief for Claude sessions (local or cloud)

The owner trades a **MyFundedFutures (MFFU) Builder 50K** eval and is building this NQ futures bot. They are not a coder and
usually write from a phone. Reply short, plain and result-first: what changed, the numbers, what's next. Do the work instead of
asking; show evidence (backtest numbers, charts) and be honest when something doesn't work.
**Steps for the owner (2026-10-20): at most 3 numbered steps, one copy-paste line, no options or side notes; do every other
part yourself or fold it into a script.**

**Every report has a table (owner 2026-11-02)**: what was done / the numbers / what's next, in a table.
**One chat (owner 2026-11-01; "our lead chat" 2026-11-02):** he makes every change, for every project, from his one Claude Code chat on this repo, to
save time and usage. Start from the map (CLAUDE_REFERENCE "One chat"), run only the tests for the area touched, no agent
swarms unless he asks.
**This file is the short brief, loaded into every message: keep it short.** The full detail (every switch, run, result,
command and file) is in `docs/CLAUDE_REFERENCE.md`; read the section you need before touching that area, and put new detail
there, not here.

## Hard rules (never break)
- **Futures data only:** TradingView CME `NQ1!` / `ES1!` exports in `data/` (5m 2021-11 → 2026-10-16; 1m for 2026). Never CFD,
  never Yahoo for testing. **No Yahoo live either (owner 2026-10-19, `live_model.json` `"no_yahoo": true`, `engine/pcbars.py`):**
  the PC bot trades on NinjaTrader MNQ bars (LE_BarFeed) + the TradingView exports + its own archive `data/nt_bars/`
  (gitignored); a stale NinjaTrader feed blocks new entries (FEED STALE), never a Yahoo fallback. The cloud monitor and
  watcher trade on the bars the PC pushes with its heartbeat (`heartbeat` branch: `bars_1m.csv.gz`, `bars_5m.csv.gz`); PC
  bars missing/stale -> no new paper entries ("waiting for NinjaTrader bars from the PC"). VIX/VXN from CBOE's own file.
- **No paid services.** The free PC-off path is the GitHub Actions cloud monitor (`.github/workflows/cloud-monitor.yml`); since
  no_yahoo it needs the PC's bars, so with the PC off it only waits (no paper entries).
- **Paper only.** Never arm live trading or place real orders. MFFU requires the owner to be present for live trading.
  Owner goes live on the eval himself (`docs/GO_LIVE_TONIGHT.md`); never arm it for him.
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
    slower than 15 sessions) and `pass_med` (median sessions to pass) in every run.
  - The strategy is written in plain language in its own area of the dashboard (Strategy page, versioned, with its numbers).
- **Stops** go beyond the sweep extreme, i.e. the high/low made before the IFVG, never at a fixed distance. **Wide stop means less
  risk**: size follows the stop.
- **Owner's trading principles (2026-10-18, keep them):** the stop sits at the protected low/high (1 tick beyond the
  sweep extreme), never a random or fixed distance; a bigger stop means fewer micros (de-risk), a small stop allows more;
  one clear target (the VIX-band objective, banked at 8R), no greed; size follows the stop and the target.
- Every result is judged on 2026 **and** on 2021-25 (5 years). A change is adopted only if it holds in both and keeps 2+/week.
  Report trades/week, % weeks with 2+, PF, net, max DD, and MFFU eval pass/fail within 2 weeks and 1 month.
  **Exception for LIT changes (owner 2026-10-18):** LIT is tuned and judged on 2026 only: pick on Jan-Jun, check on Jul-Oct,
  report both halves; 2021-25 is a reference line, never a gate.
- **Prop-firm prices:** use the owner's real prices (Builder 25K $63, the ATLAS 25K of 2026-10-26 $43, Builder 50K $91.80, one-time, $0 activation), not list
  prices; look for current discount codes before quoting any firm's price.

## The system in one screen (details: `docs/CLAUDE_REFERENCE.md`)
- **Live strategy: LIT** (locked 2026-10-18; `engine/lit.py`, params `live_model.json` "lit" = `live_model_lit.json` =
  `research/lit/lit_final.json`, plain language in `STRATEGY.md`). Sweep of a LIT level -> inducement -> displacement ->
  5m CISD -> limit 30 min, then 1m CISD; stop 1 tick beyond the sweep extreme; target 18:00 open +/- 1 VIX day move, banked
  at 8R; BE at 1R (+1.25 pts costs), 15-minute cut, flat 15:55, 1 trade/day, entries 02:00-15:30. Sizing `lit_sizing.mode`
  two_week. **Scale-in is built but OFF** until the owner's Sim roundtrip passes. Change both `live_model.json` and
  `live_model_lit.json`, then rerun `python tools/lit_losses.py live`.
- **Headline (run `lit_live`, costs in):** 2026 PF 4.19, +$43,820; **quote the H2 check rate: PF 2.91, +$9,919 (~$2,670/mo)** (cisd1m 22 since 2026-10-24).
  **Uprisk (owner 2026-10-25, `uprisk.md`):** eval two_week room_f 0.8, no eval weekly stop (2-week pass/fail H2 58.6/20.9,
  was 53.7/2.2); funded 60% of room, <= $1,500, winner <= $2,000 (~$915/mo H2 to the owner, 0% lost).
- **Live loop:** `engine/lit_live.py`; PC bot `engine/live.py` (`server.py`, http://localhost:8766) routes to NinjaTrader 8
  via `engine/ninjatrader.py` (Sim by default); cloud monitor `tools/cloud_monitor.py` (GitHub Actions, every 15 min,
  paper ledger, phone pushes, publishes the `dashboard` branch and the nq-dashboard site).
- **Paper only, never routed by default:** second strategies / ATLAS / account B (`engine/second.py`, `second_model.json`),
  stop-hunt candidates, LIT Asia slot; old engine runs as a shadow ledger (`live_model_engine.json`).
- **Read-only add-ons:** Bot Brain, Trade pictures, AI watch, Performance page, Trade intel, Alerts plus, phone live feed,
  Live learning (`engine/live_learning.py`: real-fill costs, trade reviews vs the twin, Sunday weekly, suggestions;
  `lit_sizing.learn_costs` default false, on = caps priced at the learned slippage, only ever fewer micros).
  Mind (`engine/mind.py`, 2026-10-29): similar-setup memory (context only: not predictive out of sample), regime +
  trend-day odds, game plans 01:45 / 10:45 ET, trade reviews, nightly self-research proposals; never changes anything.

## Reference index (`docs/CLAUDE_REFERENCE.md`, read before working in that area)
| Section | Read it when |
|---|---|
| Live strategy | Changing LIT rules, sizing, eval lifecycle, switches, results |
| Second strategies | ATLAS, account B, routing a second strategy, stop-hunt candidates |
| Trade pictures / AI watch | Charts of trades, anomaly / drift / loss alerts |
| Previous strategy (shadow) | The old Liquidity Engine and its eval-timing study |
| Tested and rejected | **Before proposing any new strategy idea** (don't redo without a new idea) |
| Key commands | Backtests, run library, tests, dry runs |
| Infrastructure | PC bot, cloud monitor, NinjaTrader, phone feed, TradingView, PC-off options |
| Open work | Dashboard, Pine port, the Dec 2026 roll |
| One chat | **Any change**: where each project lives, how it ships, its tests (start here) |

## Most-used commands (run from the repo root)
- `python -X utf8 -m tests.test_lit_live`: replays every 2026 session through the live loop (must stay identical).
- `python tools/lit_losses.py live`: rebuilds run `lit_live` after a switch change.
- `python tools/export_backtest.py`: the live-settings replay -> `research/lab/backtest_live.json`.
- `python -m engine.ninjatrader --selftest`: NinjaTrader route self-test.
- `python tools/cloud_monitor.py --out <tmpdir>`: dry run of the PC-off monitor.
