# Dashboard API (`/api/dash/*`): contract for the web UI

Owner: backend session ("Dashboard data & API"). Consumer: "dash-ui" (web/**). Code: `engine/dash_api.py` (routes),
`engine/dash_data.py` (datasets, background jobs, disk cache), `engine/dash_metrics.py` (pure metrics),
`engine/dash_market.py` (price / levels / sessions / news / model), `engine/dash_system.py` (health / coverage / launch /
feed / drift / memory / confluence). Mounted in `server.py` inside `# ---- DASH EXTRAS ----`.
Server: `http://127.0.0.1:8766` (supervisor), same origin as the dashboard, so `fetch('/api/dash/...')` works.

Status legend: **live** = deployed on the running server and tested (2026-10-16 16:15 ET); **planned** = not deployed.
All 36 routes below are **live**.

## Conventions (all endpoints)

* All endpoints are `GET`, return JSON (`Cache-Control: no-store`), never place orders, never arm anything.
* Every response carries `"ok": true|false`, `"status"`, `"as_of"` (unix seconds, server clock).
* `status` is one of:
  * `"ok"`: data present.
  * `"no_data"`: nothing to show yet (e.g. no paper trades, bot has not polled). `"message"` says why. Render an empty
    state, never a zero that looks like a measurement.
  * `"computing"`: a background job is building the dataset. `"retry_after_s"` says when to poll again; `"job"` has
    progress (`state`, `step`, `steps`, `msg`). Rare after the start-up warm-up.
  * `"failed"`: the dataset build failed; `message` has the error. The last good cache is served whenever one exists.
* Errors: HTTP 400 (bad parameter) / 500 with `{"ok": false, "status": "error", "error": "ValueError: ..."}`.
* Times: unix seconds UTC (`t`, `entry_t`, ...). Trading days are `"YYYY-MM-DD"` (18:00 ET rolls to the next day, the
  engine convention). ET wall-clock strings are `"HH:MM"`.
* Money is USD; R is risk multiples; prices are NQ points (back-adjusted CME NQ1! history + live Yahoo `NQ=F`).
* `null` means unknown / not applicable. NaN never appears.
* **Data:** real CME futures only (NQ, ES). `data/_cfd_archive` is never read.

### Trade sources (`source=` on analytics endpoints)

| source | what | notes |
|---|---|---|
| `backtest` (default) | light backtest of the current model | default window = last 120 sessions (2026-05-04 .. today now), 25-session warm-up before it. Override with `days_from`, `days_to` (`YYYY-MM-DD`): a custom window is built on first request (`status:"computing"`, ~5-25 s), then cached. |
| `paper` | completed paper trades the bot routed (`data/memory.db`, source paper) | days = every weekday from the first paper trade to today. 1 paper trade so far (2026-10-13). |
| `5y` | NQ 2021-11 .. today as 32 independent 8-week windows (40 sessions + 25-session warm-up each), merged | 783 trades / 1,268 sessions. A single full-history run under-trades, so windows are used. |

Backtests run in a below-normal-priority subprocess (`python -m engine.dash_data --job ...`) and are cached to
`cache/dash/*.json`. A cache is fingerprinted by the data files and model code; when either changes, the last good
result is served with `meta.stale: true` while a rebuild runs (at most once per 10 min per dataset).

Every analytics response has `"meta"`:
```json
"meta": {"source": "backtest", "sym": "NQ", "window": {"from": "2026-05-04", "to": null}, "from": "2026-05-04", "to": "2026-10-16",
         "sessions": 120, "trades": 54, "computed_at": 1792180782, "build_secs": 20.7, "stale": false, "model_version": "e3f088b2", "status": "ok"}
```
(`5y` adds `"windows": 32`.)

---

## Endpoint index (all live)

| # | path | params | purpose |
|---|---|---|---|
| 0 | `/api/dash/index` | | machine-readable list |
| 1 | `/api/dash/overview` | | home screen in one call |
| 2 | `/api/dash/eval` | `since, balance, peak_eod, today_pnl` | MFFU 50K eval tracker + projection |
| 3 | `/api/dash/montecarlo` | `source, days_from, days_to, n, horizon, from_state, since, balance, peak_eod, seed` | eval pass probability |
| 4 | `/api/dash/equity` | `source, days_from, days_to, start` | equity curve + drawdown |
| 5 | `/api/dash/calendar` | `source, days_from, days_to` | daily P&L heatmap + months |
| 6 | `/api/dash/heatmap` | `source, days_from, days_to, metric` | entry hour x weekday |
| 7 | `/api/dash/rdist` | `source, days_from, days_to, bin` | R-multiple histogram |
| 8 | `/api/dash/streaks` | `source, days_from, days_to` | win/loss streaks |
| 9 | `/api/dash/maemfe` | `source, days_from, days_to` | MAE/MFE scatter |
| 10 | `/api/dash/breakdown` | `source, days_from, days_to, by` | stats by grade / killzone / dir / pool / ... |
| 11 | `/api/dash/frequency` | `source, days_from, days_to` | trades per week vs the 2-4 band |
| 12 | `/api/dash/history` | `by` | five-year per year / quarter / month |
| 13 | `/api/dash/regime` | | ATR / ADR / efficiency / regime / VIX |
| 14 | `/api/dash/liquidity` | `max` | liquidity map: key levels + engine pools |
| 15 | `/api/dash/sessions` | | today's session ranges vs 20-day averages |
| 16 | `/api/dash/intermarket` | `days` | NQ vs ES: change, correlation, beta, RS, SMT |
| 17 | `/api/dash/news` | `days, impact` | news + blackout timeline, day plans |
| 18 | `/api/dash/feed` | `since, types, limit` | bot event log |
| 18b | `/api/dash/stream` | `since` | SSE: `log` + `tick` events |
| 19 | `/api/dash/drift` | | paper vs backtest, trade by trade |
| 20 | `/api/dash/memory` | | memory insights, best/worst conditions |
| 21 | `/api/dash/confluence` | `status, sort` | confluence registry leaderboard |
| 22 | `/api/dash/health` | | CPU / RAM / disk / process / bot / watchdog |
| 23 | `/api/dash/coverage` | | data coverage, gaps |
| 24 | `/api/dash/replay` | `entry_t, source, days_from, days_to, before, after, tf` | bars + markers for one trade |
| 25 | `/api/dash/launch` | | launch checklist + countdown |
| 26 | `/api/dash/clock` | | killzones, countdowns, market open |
| 27 | `/api/dash/ticker` | `n` | price, change, sparkline |
| 28 | `/api/dash/model` | | live model state, setups, position |
| 29 | `/api/dash/bias` | | MTF FVG bias grid, structure, profile |
| 30 | `/api/dash/rolling` | `source, days_from, days_to, window` | rolling-window edge |
| 31 | `/api/dash/exits` | `source, days_from, days_to` | exit reasons + exit-signal counterfactuals |
| 32 | `/api/dash/trades` | `source, days_from, days_to, limit, offset, sort, order, dir, grade, exit, win` | trade table |
| 33 | `/api/dash/jobs` | `refresh` | background jobs + cache files |
| 34 | `/api/dash/prep` | | next-session prep card |

Suggested polling: `overview` / `ticker` / `model` / `clock` every 10-15 s (or the SSE `stream`); analytics on page open.

---

## 1. `GET /api/dash/overview`  (live)
```json
{"ok": true, "status": "ok",
 "bot": {"running": true, "adapter": "paper", "armed_live": false, "kill": false, "model_state": "OUTSIDE KILLZONE",
         "position": null, "last_poll": 1792181572, "poll_ms": 1518, "errors": 0, "started_at": 1792115566},
 "price": {"last": 29357.5, "t": 1792180800, "chg": -720.75, "chg_pct": -2.4, "day_high": 30224.5, "day_low": 29268.75,
           "prev_close": 30078.25, "session": "2026-10-16"},
 "today": {"date": "2026-10-16", "pnl_routed": 0.0, "trades": 0, "engine_day_pnl": 0.0, "engine_day_trades": 0},
 "week": {"key": "2026-W42", "trades": 1, "target_min": 2, "target_max": 4, "status": "below", "backtest_tpw": 2.25,
          "message": "1 paper trade this week (target 2-4)"},
 "eval": {"balance": 50000.0, "profit": 0.0, "target": 3000, "pct_to_target": 0.0, "mll": 48000.0, "cushion": 2000.0,
          "dll_used": 0.0, "source": "paper", "trades": 0},
 "next_killzone": {"name": "NY AM", "date": "2026-10-19", "start_t": 1792416600, "end_t": 1792423800, "in_s": 235000, "active": false},
 "market": {"open": true, "next_open_t": null, "next_close_t": 1792184400, "now_et": "Fri 16:12"},
 "next_blackout": {"event": "CB Consumer Confidence", "t": 1793109600, "start_t": 1793108700, "end_t": 1793111400, "in_s": 927100,
                   "date": "2026-10-27", "time_et": "10:00", "killzones_hit": ["NY AM killzone 09:30-11:30"]},
 "next_event": {"event": "Unemployment Claims", "t": 1792672200, "impact": "medium", "in_s": 490841},
 "in_blackout": false,
 "data": {"age_s": 472, "stale": false, "market_open": true, "source": "yahoo", "last_bar_t": 1792180800},
 "health": {"ok": true, "issues": [], "watchdog_ok": true, "keepawake": true},
 "launch": {"t": 1792360800, "in_s": 179200, "label": "Sun 2026-10-18 18:00 ET", "launched": false},
 "datasets": {"backtest": "ok", "backtest_stale": false}}
```
`next_blackout` looks 14 days ahead (null when no high-impact release in that range). `week.trades` counts paper trades.

## 2. `GET /api/dash/eval`  (live)
MFFU Builder 50K. Default state = paper trades since `since` (default `2026-10-18`, the launch). The real MFFU account
is traded by TradingView, so the UI may pass the owner's real numbers (e.g. kept in localStorage):

| param | default | meaning |
|---|---|---|
| `since` | `2026-10-18` | first trading day of this eval |
| `balance` | from paper trades | current balance (override; `state.source` becomes `"override"`) |
| `peak_eod` | from paper trades | highest end-of-day balance so far (drives the trailing MLL) |
| `today_pnl` | paper ledger today | today's P&L (drives the $1k soft DLL) |

```json
{"ok": true, "status": "ok",
 "plan": {"name": "MFFU Builder 50K", "start": 50000, "target": 3000, "mll": 2000, "dll": 1000, "lock_at": 50100.0,
          "internal_daily_stop": 600.0, "max_minis": 4, "eval_consistency": null},
 "state": {"source": "paper", "since": "2026-10-18", "balance": 50000.0, "profit": 0.0, "peak_eod": 50000.0,
           "trading_days": 0, "sessions": 0, "trades": 0},
 "target": {"level": 53000, "remaining": 3000.0, "pct": 0.0},
 "mll": {"level": 48000.0, "cushion": 2000.0, "pct_cushion_left": 100.0, "locked": false, "lock_needs": 2100.0,
         "note": "EOD trailing: trails the best end-of-day balance by $2,000, locks at $50,100"},
 "dll": {"soft_limit": 1000, "today_pnl": 0.0, "used": 0.0, "pct_used": 0.0, "internal_stop": 600.0, "internal_left": 600.0},
 "days": [{"date": "2026-10-19", "pnl": 0.0, "balance": 50000.0, "mll": 48000.0, "trades": 0}],
 "projection": {"avg_day_pnl": 57.71, "days_to_pass_linear": 52.0, "mc_median_days": 37.0, "mc_pass_prob": 61.2,
                "mc_fail_prob": 1.9, "mc_horizon": 60, "basis": "backtest 2026-05-04..2026-10-16 (120 sessions)", "stale": false},
 "message": "No paper trades since 2026-10-18: the account sits at its starting balance."}
```
`lock_needs` = how much higher the best EOD balance must go before the MLL locks at $50,100.

## 3. `GET /api/dash/montecarlo`  (live)
Bootstrap of (day P&L, intraday low) pairs from `source` through the MFFU EOD-trailing rules (same semantics as
`engine.analytics.simulate_eval`). `n` 100-20000 (default 3000), `horizon` 5-250 sessions (default 60),
`from_state=1` starts from the `/eval` state (accepts `since, balance, peak_eod`), `seed` default 7.
```json
{"ok": true, "status": "ok", "meta": {"...": "..."}, "n": 3000, "horizon": 60,
 "pass_prob": 61.8, "fail_prob": 2.2, "open_prob": 36.0,
 "days_to_pass": {"median": 36.0, "p25": 24.0, "p75": 46.0, "p90": 54.0, "hist": [{"d": 5, "n": 1}, {"d": 10, "n": 5}]},
 "days_to_fail_median": 42.0,
 "bands": {"days": [1, 2], "p5": [-117.5, -226.0], "p25": [-1.5, -38.0], "p50": [0.0, 0.0], "p75": [0.0, 0.0], "p95": [623.0, 1239.4]},
 "final": {"p5": 51.0, "p50": 3130.5, "p95": 4089.1},
 "sample_paths": [[623.0, 621.5]], "start": {"balance": 50000.0, "peak_eod": 50000.0}, "bootstrap_days": 120}
```
`bands.*` and `sample_paths` are P&L relative to the start balance, one value per session (`horizon` values). A path
freezes once it passes or fails. `hist` buckets days-to-pass in 5-session bins (`d` = bucket upper edge).
Heads-up for copy: the `5y` source gives a very different answer (pass ~10%, fail ~16%) than the recent 120 sessions.

## 4. `GET /api/dash/equity`  (live)
`start` default 50000.
```json
{"ok": true, "status": "ok", "meta": {},
 "trades": [{"t": 1777921500, "eq": 49998.5, "dd": -1.5, "pnl": -1.5, "r": -0.016}],
 "days": [{"date": "2026-05-04", "eq": 49998.5, "dd": -1.5, "pnl": -1.5, "trades": 1}],
 "summary": {"start": 50000.0, "net": 6925.5, "end": 56925.5, "peak": 56925.5, "max_dd": -861.5, "max_dd_date": "2026-08-05",
             "current_dd": 0.0, "longest_underwater_days": 83, "recovery_factor": 8.04}}
```
`trades[].t` = exit time. `dd` <= 0 (distance below the running peak).

## 5. `GET /api/dash/calendar`  (live)
```json
{"ok": true, "status": "ok", "meta": {},
 "days": [{"date": "2026-05-04", "dow": 0, "pnl": -1.5, "trades": 1, "r": -0.02, "regime": "trending"}],
 "months": [{"month": "2026-05", "pnl": -697.5, "trades": 15, "green_days": 0, "red_days": 11, "flat_days": 9, "sessions": 20}],
 "max_abs_pnl": 1587.0}
```
`r` is null on no-trade days. `dow` 0 = Monday.

## 6. `GET /api/dash/heatmap`  (live)
`metric` = `avg_r` (default) | `pnl` | `wr` | `n` (only echoed; every cell carries all four).
```json
{"ok": true, "status": "ok", "meta": {}, "metric": "avg_r", "hours": [9, 10, 11, 13, 14, 15], "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
 "cells": [{"hour": 9, "dow": 0, "n": 3, "pnl": -267.5, "avg_r": -0.763, "wr": 0.0}],
 "by_hour": [{"hour": 9, "n": 9, "wins": 2, "wr": 22.2, "avg_r": 0.029, "total_r": 0.26, "pnl": -16.5, "pf": 0.97, "expectancy": -1.83}],
 "by_dow": [{"dow": 0, "name": "Mon", "n": 15, "wins": 2, "wr": 13.3, "avg_r": -0.158, "total_r": -2.37, "pnl": -113.0, "pf": 0.85, "expectancy": -7.53}]}
```
Empty cells have `n: 0` and null `avg_r` / `wr`.

## 7. `GET /api/dash/rdist`  (live)
`bin` 0.05-2.0 R (default 0.25). Range clipped to [-3R, +8R].
```json
{"ok": true, "status": "ok", "meta": {}, "bin": 0.25,
 "bins": [{"lo": -1.25, "hi": -1.0, "n": 7, "wins": 0}],
 "stats": {"n": 54, "mean": 0.434, "median": -0.095, "std": 1.869, "skew": 1.57, "min": -1.05, "max": 5.17,
           "pct_ge_2r": 16.7, "pct_le_m1r": 25.9, "pct_scratch": 27.8, "expectancy_usd": 128.25}}
```

## 8. `GET /api/dash/streaks`  (live)
```json
{"ok": true, "status": "ok", "meta": {},
 "trades": {"current": {"kind": "win", "len": 2}, "max_win": 2, "max_loss": 16,
            "hist_win": [{"len": 1, "n": 8}], "hist_loss": [{"len": 1, "n": 4}],
            "sequence": [{"entry_t": 1777918800, "w": 0, "r": -0.016}]},
 "days": {"current": {"kind": "green", "len": 3}, "max_green": 3, "max_red": 12, "note": "days with trades only"}}
```
`sequence` = last 200 trades (w: 1 win, 0 loss; a scratch with pnl <= 0 counts as a loss).

## 9. `GET /api/dash/maemfe`  (live)
MAE / MFE are in R.
```json
{"ok": true, "status": "ok", "meta": {},
 "points": [{"entry_t": 1791898500, "mae": 0.364, "mfe": 2.385, "r": 2.079, "win": true, "exit": "TARGET", "grade": "D", "dir": 1}],
 "summary": {"n": 54, "winners_median_mae": 0.225, "losers_median_mfe": 0.55, "pct_winners_mae_gt_half_r": 21.4,
             "pct_losers_mfe_ge_1r": 20.0, "avg_capture": 0.78, "left_on_table_r": 6.26}}
```
`avg_capture` = mean(R / MFE) over winners; `left_on_table_r` = sum(MFE - R) over winners.

## 10. `GET /api/dash/breakdown`  (live)
`by` = comma list of `grade, killzone, dir, pool, trigger, exit, regime, dow, target, model, hour` (default: all but `hour`).
```json
{"ok": true, "status": "ok", "meta": {}, "dims": ["grade", "killzone", "dir", "pool", "trigger", "exit", "regime", "dow", "target", "model", "hour"],
 "groups": {"grade": [{"key": "A+", "n": 3, "wins": 2, "wr": 66.7, "avg_r": 2.578, "total_r": 7.73, "pnl": 2600.0, "pf": 12.1, "expectancy": 866.7}],
            "killzone": [{"key": "NY AM", "n": 24}, {"key": "NY PM", "n": 28}, {"key": "Other", "n": 2}],
            "pool": [{"key": "M15", "n": 40}, {"key": "ON", "n": 8}, {"key": "PD", "n": 4}]}}
```
`killzone`: NY AM (09:30-11:30 entries), NY PM (13:30-15:30), London, Other. `pool` / `target`: highest-priority family of
the raided / targeted pool: `PW, PD, ON, ASIA, LON, H1, EQ, M15`. `pf` = 999 when there are no losses, null with no trades.

## 11. `GET /api/dash/frequency`  (live)
Owner's hard rule: 2-4 trades per week.
```json
{"ok": true, "status": "ok", "meta": {}, "band": [2, 4],
 "weeks": [{"key": "2026-W19", "start": "2026-05-04", "sessions": 5, "n": 3, "pnl": -105.0, "r": -1.55, "zone": "in", "in_band": true, "partial": false}],
 "summary": {"weeks": 23, "avg": 2.22, "median": 2.0, "pct_in_band": 47.8, "pct_below": 43.5, "pct_above": 8.7, "pct_zero": 17.4,
             "rolling4": 3.0, "tpw_overall": 2.25, "note": "partial weeks ... excluded from the percentages"},
 "this_week": {"key": "2026-W42", "paper": 1, "backtest": 3}}
```
`zone`: `zero | below | in | above`. `pct_below` includes zero weeks. `this_week` has the paper count plus a count from
the requested source under the source's name.

## 12. `GET /api/dash/history`  (live)
Five-year windowed dataset. `by` = `quarter` (default) | `year` | `month`.
```json
{"ok": true, "status": "ok", "meta": {"source": "5y", "from": "2021-11-22", "to": "2026-10-16", "sessions": 1268, "trades": 783, "windows": 32},
 "by": "year",
 "periods": [{"key": "2022", "from": "2022-01-03", "to": "2022-12-30", "sessions": 258, "trades": 126, "tpw": 2.44, "wr": 17.5,
              "avg_r": -0.119, "total_r": -15.0, "pf": 0.62, "net": -2985.5, "max_dd": -3512.5, "pct_weeks_in_band": 53.8,
              "pct_zero_weeks": 19.2, "avg_er10": 0.318, "trending_days": 72, "longs": 59, "shorts": 67}],
 "total": {"sessions": 1268, "trades": 783, "tpw": 3.09, "wr": 22.6, "avg_r": 0.055, "pf": 1.22, "net": 10394.5, "max_dd": -4773.5}}
```
Years so far: 2021 -635, 2022 -2,986, 2023 +513, 2024 +3,826, 2025 +241, 2026 +9,436 (regime-dependent edge).

## 13. `GET /api/dash/regime`  (live)
```json
{"ok": true, "status": "ok", "session": "2026-10-16", "sessions_used": 93,
 "daily": {"atr14": 477.89, "adr20": 480.95, "adr60": 480.35, "today_range": 955.75, "today_pct_adr": 198.7, "er5": 0.823, "er10": 0.294,
           "regime": "rotational", "regime_threshold": 0.45, "regime_mode": "half", "vol_expansion": 1.026, "dir5": -1,
           "day_range_guard": {"limit_x_adr": 1.6, "used_x_adr": 1.99, "blocks_entries": true}},
 "intraday": {"atr14_5m": 20.8, "rth_avg_5m_range_20d": 34.74, "atr14_5m_pct_of_20d": 59.9},
 "vix": {"VIX": {"last": 20.42, "date": "2026-10-16", "prev_close": 16.46, "prev_date": "2026-10-15", "high": 22.31, "low": 15.72},
         "VXN": {"last": 22.89, "date": "2026-10-15", "prev_close": 22.7, "prev_date": "2026-10-14", "high": 25.17, "low": 22.79}},
 "series": [{"date": "2026-07-24", "er10": 0.499, "range": 523.5, "regime": "trending"}],
 "note": "regime = 10-session efficiency ratio of completed sessions (engine rule: > threshold = trending, half size)"}
```
`day_range_guard` mirrors the engine's `day_range_max` rule (no new entries once today's range >= 1.6 x the 20-day
average). VIX/VXN `last` may be today's partial session.

## 14. `GET /api/dash/liquidity`  (live)
`max` = how many engine pools (nearest first), default 30.
```json
{"ok": true, "status": "ok", "price": 29357.5, "t": 1792180800, "session": "2026-10-16", "adr20": 480.95,
 "levels": [{"label": "PDH", "price": 30224.5, "side": "H", "kind": "key", "swept": true, "formed": "2026-10-15", "dist": 867.0, "dist_adr": 1.8}],
 "pools": [{"label": "H1H/ITH", "price": 29753.75, "side": "H", "kinds": ["ITH", "H1H"], "strength": 2, "eq": false,
            "formed_t": 1791823500, "dist": 396.25, "dist_adr": 0.82}],
 "nearest": {"above": {"label": "ITH", "price": 29753.75, "dist": 396.25}, "below": {"label": "ITL", "price": 29268.75, "dist": -88.75}},
 "source": "live engine pools + levels computed from bars"}
```
Level labels: `PDH PDL PDC PWH PWL ONH ONL ASH ASL LOH LOL MIDNIGHT_OPEN RTH_OPEN`. `side`: H / L / C (reference
price). `kind`: key / session / open. `nearest` skips swept levels and reference prices. `pools` are empty when the
bot has not polled yet.

## 15. `GET /api/dash/sessions`  (live)
Sessions (ET): Asia 20:00-24:00, London 02:00-05:00, Overnight 18:00-09:30, NY AM 09:30-11:30, NY lunch 11:30-13:30, NY PM 13:30-16:00.
```json
{"ok": true, "status": "ok", "date": "2026-10-16", "is_current": true,
 "sessions": [{"key": "ASIA", "name": "Asia", "start_et": "20:00", "end_et": "00:00", "start_t": 1792108800, "end_t": 1792123200,
               "state": "done", "high": 30211.5, "low": 29958.75, "range": 252.5, "avg20": 142.89, "pct_of_avg": 176.9, "bars": 48}],
 "day": {"open": 30086.0, "high": 30224.5, "low": 29268.75, "range": 955.75, "last": 29357.5}}
```
`state`: done / active / upcoming. Between sessions it shows the last session (`is_current: false`).

## 16. `GET /api/dash/intermarket`  (live)
`days` = RS-series length (default 60). ES = stored CME ES + Yahoo `ES=F` refreshed every 5 min by a background job.
```json
{"ok": true, "status": "ok",
 "today": {"session": "2026-10-16", "nq_chg_pct": -2.4, "es_chg_pct": -1.15, "spread_pct": -1.25, "leader": "ES",
           "compared_to_t": 1792180800, "es_lag_s": 0, "note": null, "intraday_5m_corr": 0.904},
 "corr": {"d20": 0.904, "d60": 0.908}, "beta_60d": 1.507,
 "rs_series": [{"date": "2026-07-24", "nq": 100.0, "es": 100.0, "ratio": 1.0}],
 "smt": {"today": [{"level": "PDH", "nq_swept": true, "es_swept": true, "divergence": false, "note": null},
                   {"level": "ASH", "nq_swept": true, "es_swept": false, "divergence": true, "note": "NQ took ASH, ES held: bearish SMT"}]},
 "as_of": {"nq": 1792180800, "es": 1792180800, "es_fresh_fetch": 1792181583},
 "es_source": "stored CME ES history + Yahoo ES=F (fetched in a background job)", "days": 340}
```
Both markets are compared up to the last bar they share (`compared_to_t`); `es_lag_s` > 0 means ES data is behind.

## 17. `GET /api/dash/news`  (live)
`days` 1-31 (default 7), `impact` = `medium` (default) | `high` | `low`.
```json
{"ok": true, "status": "ok", "now": 1792181691, "from": "2026-10-16", "to": "2026-10-23", "impact": "medium",
 "events": [{"date": "2026-10-27", "time_et": "10:00", "t": 1793109600, "event": "CB Consumer Confidence", "impact": "high",
             "source": "conference-board.org", "confidence": "inferred", "weekday": "Tue", "utc_offset": "-0400",
             "blackout_start": "09:45", "blackout_end": "10:30", "flatten_at": "09:55", "killzones_hit": ["NY AM killzone 09:30-11:30"],
             "fomc_pm_off": false, "blackout_start_t": 1793108700, "blackout_end_t": 1793111400, "flatten_t": 1793109300}],
 "days": [{"date": "2026-10-19", "weekday": "Mon", "risk": "LOW", "action": "NORMAL.", "n_high": 0, "n_events": 0,
           "notes": "Fed speaker blackout in force ...", "fomc_pm_off": false}],
 "in_blackout": false, "current_blackout": null,
 "next_blackout": {"event": "...", "t": 0, "start_t": 0, "end_t": 0, "in_s": 0, "date": "...", "time_et": "...", "killzones_hit": []},
 "next_event": {"event": "Unemployment Claims", "t": 1792672200, "impact": "medium", "in_s": 490841},
 "guard": {"allowed": true, "reasons": []}, "rules": {"before_min": 15, "after_min": 30, "flatten_min": 5, "fomc_pm_off": true}}
```
Blackout fields exist on high-impact events only. `risk`: LOW / NORMAL / ELEVATED / HIGH (engine/calendar_week.py).

## 18. `GET /api/dash/feed`  (live)
`since` (unix, default 0), `types` (comma list: `system, order, sweep, signal, entry, exit, risk, warn, error, news,
tradingview, daily, skip`), `limit` 1-400 (default 100). Newest first.
```json
{"ok": true, "status": "ok", "count": 1, "running": true, "types": {"warn": 3, "system": 4},
 "events": [{"t": 1792181634, "type": "warn", "text": "feed revised 1 already-closed bar(s), e.g. 16:00 ET - decisions may change", "level": "warn"}]}
```
`level`: info / warn / error. Some rows carry `bar_t` (the bar the event happened on).

## 18b. `GET /api/dash/stream`  (live, Server-Sent Events)
`text/event-stream`. `new EventSource('/api/dash/stream')`. Events:
* `log`: one bot log row (feed row shape, without `level`), pushed within ~1 s.
* `tick` every 5 s: `{"t", "price", "bar_t", "model_state", "running", "data_age_s", "last_poll", "day_pnl_routed", "position": {...}|null}`.

`since=<unix>` first replays up to 100 log rows newer than it. The server sends `retry: 3000`.

## 19. `GET /api/dash/drift`  (live)
Paper trades vs the backtest of the same days (match = same direction, entry within 10 min).
```json
{"ok": true, "status": "ok", "days": ["2026-10-13"],
 "pairs": [{"day": "2026-10-13", "paper": {"entry_t": 1791898500, "dir": 1, "entry": 30649.0, "r": 2.079, "pnl": 248.5, "grade": "D", "exit_reason": "TARGET"},
            "backtest": {"entry_t": 1791898500, "dir": 1, "entry": 30649.0, "r": 2.079, "pnl": 248.5}, "match": "matched",
            "r_diff": 0.0, "pnl_diff": 0.0, "entry_slip_min": 0.0, "entry_px_diff": 0.0}],
 "summary": {"paper_trades": 1, "backtest_trades": 1, "matched": 1, "paper_only": 0, "backtest_only": 0, "match_rate": 100.0,
             "paper_pnl": 248.5, "backtest_pnl": 248.5, "avg_entry_slip_min": 0.0},
 "backtest_meta": {}}
```
`match`: matched / paper_only / backtest_only. With no paper trades: `status:"no_data"`. A new paper day triggers a
small backtest build (`status:"computing"` for ~5 s).

## 20. `GET /api/dash/memory`  (live)
```json
{"ok": true, "status": "ok", "counts": {"paper": 1, "live": 0, "backtest": 0},
 "realised": {"trades": 1, "wins": 1, "win_rate": 100.0, "net": 248.5, "avg_r": 2.079, "total_r": 2.08, "profit_factor": 999.0,
              "expectancy": 248.5, "first_day": "2026-10-13", "last_day": "2026-10-13"},
 "by_grade": {"D": {"trades": 1}}, "by_regime": {}, "by_exit": {},
 "signals": [], "learner": {"learn_min": 20, "threshold": 0.2, "learned": []},
 "backtest_signals": [{"key": "giveback", "n": 0, "acted": 14}],
 "conditions": {"source": "backtest", "meta": {}, "min_n": 5,
                "best": [{"dim": "grade", "key": "A+", "n": 5, "avg_r": 2.578, "wr": 60.0, "pnl": 2600.0}],
                "worst": [{"dim": "dow", "key": "Mon", "n": 15, "avg_r": -0.158}]},
 "calibration": {"realised": {}, "paper": {}, "live": {}}, "learner_states": {"import_live_state": {"updated_at": 1792180000}}}
```
`conditions` come from paper once it has >= 20 trades, from the backtest before that (`conditions.source`).

## 21. `GET /api/dash/confluence`  (live)
`status` = comma list of `ACTIVE, PROBATION, CANDIDATE, RETIRED` (default all); `sort` = `lift` (default) | `n` | `name`
(within status order ACTIVE, PROBATION, CANDIDATE, RETIRED).
```json
{"ok": true, "status": "ok", "generated": "2026-10-16 16:02", "futures_only": true,
 "counts": {"ACTIVE": 6, "PROBATION": 10, "CANDIDATE": 25, "RETIRED": 65},
 "rule": {"tpw": [2.0, 4.5], "text": "Adopt only when ..."},
 "baseline": {"nq_total": 9516.5, "nq_n": 1054, "nq_tpw": 4.08, "nq_pf": 1.12, "nq_dd": -8693.5, "es_total": -11765.25},
 "folds": [{"name": "F1", "from": "2021-10-18", "to": "2022-12-30", "sessions": 312, "role": "decide"}],
 "data": {"NQ": {"from": "2021-10-18", "to": "2026-10-16", "sessions": 1293, "trades": 1054}},
 "items": [{"id": "first_h", "name": "...", "status": "ACTIVE", "decision": "...", "verdict": "...", "lift_pooled": 0.3,
            "lift_decide": 0.2, "lift_confirm": 0.4, "n_on": 300, "n_off": 700, "ci90": [0.1, 0.5], "taken_lift": 0.2,
            "agree": 3, "valid": 3, "freq": 0.3, "es_agree": true, "wf_confirm": true, "weight": 1, "live": true,
            "mechanism": "grade", "reason": "...", "first_seen": "2026-10-16", "retired": null, "history": ["ACTIVE"]}],
 "last_run": {"run": "...", "started": "...", "secs": 0, "counts": {}, "added": [], "retired_live": [], "recommended_params": {}},
 "runs": [{"run": "...", "started": "...", "secs": 8.4, "counts": {}}]}
```
The registry is rebuilt by another session; this endpoint re-reads it whenever the file changes.

## 22. `GET /api/dash/health`  (live)
```json
{"ok": true, "status": "ok", "python": "3.12.10", "platform": "Windows-11",
 "system": {"cpu_pct": 12.0, "cpu_count": 12, "mem_pct": 89.6, "mem_used_gb": 7.11, "mem_total_gb": 7.93, "disk_pct": 78.3,
            "disk_free_gb": 48.5, "boot_t": 1792176106},
 "process": {"pid": 1234, "uptime_s": 321, "rss_mb": 410.0, "threads": 30, "cpu_pct": 3.0},
 "supervisor": {"pid": 6044, "alive": true},
 "bot": {"running": true, "adapter": "paper", "data_source": "yahoo", "kill": false, "last_poll": 1792181572, "last_ok_poll": 1792181572,
         "poll_ms": 1518, "poll_sec": 60, "errors": 0, "consecutive_errors": 0, "data_age_s": 472, "stale": false, "market_open": true,
         "entries_blocked": false, "desync": false, "revisions": 2, "fallback": false, "dropped": {}, "last_error": null,
         "last_error_t": null, "ok": true},
 "watchdog": {"ok": true, "issues": [], "thread_alive": true, "last_check": 1792181600, "server_started_at": 1792181508},
 "keepawake": {"held": true, "want": true, "since": 1792181508, "supported": true, "last_error": null},
 "autostart": {"record": true, "resumed": true, "mode": "paper", "reason": "...", "checked_at": 1792181508, "task_installed": false},
 "log": {"path": "logs\\server-20261016.log", "size_kb": 2.1},
 "issues": []}
```
Top-level `ok` is false when `issues` is non-empty. `task_installed` is null until the first (background) check.
Note: this PC has ~8 GB RAM and runs ~90% used.

## 23. `GET /api/dash/coverage`  (live)
```json
{"ok": true, "status": "ok", "stale": false, "computed_at": 1792181568,
 "files": [{"sym": "NQ", "tf": "5m", "file": "NQ_5m.csv", "rows": 354216, "from": "2021-10-18", "to": "2026-10-16", "sessions": 1293,
            "first_t": 1634508000, "last_t": 1792149000, "missing_weekdays": 12, "missing_sample": ["2025-12-25"],
            "intraday_gaps": 0, "gap_sample": [], "size_kb": 17435.2, "mtime": 1792178000}],
 "sources": {"tv-NQ1!": {"from": "2021-10-18", "to": "2026-08-21", "sessions": 1253}, "tv-MNQ1!": {"from": "2026-08-24", "to": "2026-10-16", "sessions": 40}},
 "manifest_generated": "2026-10-16T15:32:38", "price_space": "back-adjusted (additive) ...", "volume_units": {},
 "note": "missing_weekdays includes CME exchange holidays; CFD data is never listed"}
```
Files: NQ / ES at 1m, 5m, 15m, 1h, 1d plus `ltf/NQJ_1m.csv`. `intraday_gaps` = RTH gaps longer than 3 bars.

## 24. `GET /api/dash/replay`  (live)
`entry_t` required (matched within 10 min). `source` default backtest (falls back to `5y` for older trades), `before`
(bars before entry, default 36), `after` (bars after exit, default 24), `tf` = `5m` | `1m` (1m history only from 2026-09-17).
```json
{"ok": true, "status": "ok", "meta": {},
 "trade": {"day": "2026-10-13", "entry_t": 1791898500, "exit_t": 1791898800, "dir": 1, "entry": 30649.0, "exit_price": 30774.0,
           "stop0": 30589.25, "target": 30774.0, "r": 2.079, "pnl": 248.5, "grade": "D", "trigger": "CISD", "exit_reason": "TARGET",
           "pools": ["ITL"], "target_label": "H1H/ITH", "sweep_ext": 30591.25, "signal_t": 1791898200},
 "bars": {"tf": "5m", "t": [1791887700], "o": [30700.0], "h": [30710.0], "l": [30690.0], "c": [30705.0], "v": [1200.0]},
 "markers": [{"t": 1791898200, "price": null, "kind": "signal"}, {"t": 1791898500, "price": 30649.0, "kind": "entry", "dir": 1},
             {"t": 1791898800, "price": 30774.0, "kind": "exit", "reason": "TARGET"}],
 "lines": [{"price": 30589.25, "kind": "stop"}, {"price": 30774.0, "kind": "target", "label": "H1H/ITH"}, {"price": 30591.25, "kind": "sweep_extreme"}]}
```

## 25. `GET /api/dash/launch`  (live)
```json
{"ok": true, "status": "ok", "launch_t": 1792360800, "launch_label": "Sun 2026-10-18 18:00 ET", "in_s": 179377, "launched": false,
 "ready": true, "score": {"pass": 16, "warn": 1, "fail": 0, "info": 1},
 "checks": [{"key": "bot_running", "label": "Paper bot running on this PC", "state": "pass", "detail": "adapter=paper"},
            {"key": "task", "label": "Windows logon task installed (scripts/install_autostart.ps1)", "state": "warn", "detail": null},
            {"key": "mc", "label": "Eval pass probability (60 sessions, backtest bootstrap)", "state": "info", "detail": "pass 61.2% / fail 1.9% / still open 36.9%"}]}
```
Check keys: `bot_running, adapter_paper, not_armed, kill_off, watchdog, keepawake, autostart_record, task, feed, history,
pine, bridge_doc, blackouts, webhook_key, memory, frequency, mc, calendar`. `state`: pass / warn / fail / info.
`ready` = no `fail`. The webhook key itself is never returned.

## 26. `GET /api/dash/clock`  (live)
```json
{"ok": true, "status": "ok", "now": 1792181360, "now_et": "Fri 16:09", "date_et": "2026-10-16", "market_open": true,
 "next_open_t": null, "next_close_t": 1792184400,
 "killzones": [{"name": "London", "start_et": "02:00", "end_et": "05:00", "trades": false, "state": "done", "start_t": 1792130400, "end_t": 1792141200},
               {"name": "NY AM", "start_et": "09:30", "end_et": "11:30", "trades": true, "state": "done", "start_t": 1792157400, "end_t": 1792164600},
               {"name": "NY PM", "start_et": "13:30", "end_et": "15:30", "trades": true, "state": "done", "start_t": 1792171800, "end_t": 1792179000}],
 "flat_et": "15:55", "flat_t": 1792180500, "arm_from_et": "08:00",
 "next_entry_window": {"name": "NY AM", "date": "2026-10-19", "start_t": 1792416600, "end_t": 1792423800, "in_s": 235240, "active": false}}
```
`state`: upcoming / active / done (`closed` on weekends). `next_open_t` is set while the market is closed,
`next_close_t` while it is open (17:00 ET daily break / Friday close). Exchange holidays are not modelled.

## 27. `GET /api/dash/ticker`  (live)
`n` sparkline bars (10-600, default 78).
```json
{"ok": true, "status": "ok", "sym": "NQ", "last": 29357.5, "t": 1792180800, "session": "2026-10-16", "prev_close": 30078.25,
 "chg": -720.75, "chg_pct": -2.4, "day_high": 30224.5, "day_low": 29268.75, "day_open": 30086.0,
 "spark": [30189.5, 30194.25], "spark_t0": 1792157700, "spark_step_s": 300, "data_age_s": 500, "market_open": true, "bot_fresh": true,
 "source": "stored CME NQ1! history + live bot bars (Yahoo NQ=F)"}
```
`t` = open time of the last closed 5m bar; `data_age_s` = seconds since that bar closed (Yahoo is ~10 min delayed).

## 28. `GET /api/dash/model`  (live)
```json
{"ok": true, "status": "ok", "running": true, "t": 1792180800, "price": 29357.5, "model_state": "OUTSIDE KILLZONE",
 "flow": ["OUTSIDE KILLZONE", "WAITING FOR SWEEP", "ARMED - HUNTING IFVG", "ORDER PENDING", "IN TRADE", "DONE FOR DAY"], "flow_index": 0,
 "setups": {"long": {"dir": 1, "ext": 29268.75, "arm_t": 1792155000, "pools": ["ITL", "H1L/ONL/ITL/ASL"], "age_min": 443, "dist_from_ext": 88.75},
            "short": null},
 "pending": null,
 "position": null,
 "day": {"pnl": 0.0, "trades": 0, "max_trades": 2, "daily_stop": 600.0, "stop_after_win": true},
 "engine_account": {"balance": 52080.0, "mll": 50083.0, "note": "the live engine's own simulated account over its rolling window; not the MFFU balance"},
 "trend": {"h1": -1, "m15": -1}, "last_poll": 1792181572}
```
With an open position: `position = {dir, entry, stop, stop0, target, qty, qty_label, entry_t, grade, trigger, target_label,
pools, exit_signal, live_r, to_stop_pts, to_target_pts, mins_in_trade}`.

## 29. `GET /api/dash/bias`  (live)
```json
{"ok": true, "status": "ok", "t": 1792180800, "price": 29357.5, "net": -4,
 "tfs": [{"tf": "1D", "bias": -1, "last": "respected bearish", "zones": [{"dir": 1, "top": 29647.5, "bot": 29552.5, "state": "inverted"}]}],
 "structure": {"1H": -1, "15m": -1, "h1_protected_low": null, "h1_protected_high": 30225.0, "m15_protected_low": null, "m15_protected_high": null},
 "dealing_range": {"high": 30225.0, "low": 30126.0, "eq": 30175.5, "pos": -7.763, "zone": "discount", "outside": true},
 "midnight_open": 30201.5, "open_loc": "inside",
 "profile": {"poc": 29992.5, "vah": 30100.0, "val": 29780.0, "lo": 29620.0, "bin": 5.0, "hist": [945.8], "date": "2026-10-15"}}
```
`tfs` rows: 1D, 4H, 1H, 15m; `bias` -1/0/1; zone `state`: fresh / tested / inverted. `profile.hist[k]` = volume at
price `lo + k * bin`.

## 30. `GET /api/dash/rolling`  (live)
`window` 5-200 trades (default 20).
```json
{"ok": true, "status": "ok", "meta": {}, "window": 20,
 "series": [{"i": 20, "entry_t": 1782000000, "day": "2026-06-20", "wr": 25.0, "avg_r": 0.1, "pf": 1.2, "sum_r": 2.0}],
 "latest": {"i": 54, "entry_t": 1791898500, "day": "2026-10-13", "wr": 45.0, "avg_r": 1.052, "pf": 4.63, "sum_r": 21.03},
 "full": {"wr": 25.9, "avg_r": 0.434, "pf": 3.71, "n": 54}}
```

## 31. `GET /api/dash/exits`  (live)
```json
{"ok": true, "status": "ok", "meta": {},
 "reasons": [{"key": "STOP", "n": 14, "wins": 0, "wr": 0.0, "avg_r": -1.029, "total_r": -14.41, "pnl": -1518.5, "pf": 0.0, "expectancy": -108.46, "share": 25.9}],
 "signals": [{"key": "stall", "label": "No new high-water mark for 30 min while under +1R", "n": 1, "acted": 0, "seeded": 0,
              "avg_gain": 0.631, "helped": 1.0, "hurt": 0.0, "total_gain": 0.63, "learned": false}]}
```
`signals` (exit-signal counterfactuals) exist for `backtest` only; `avg_gain` = R gained on average by leaving at that
signal versus how the trade ended.

## 32. `GET /api/dash/trades`  (live)
`limit` 1-1000 (default 50), `offset`, `sort` = `entry_t | r | pnl | mfe | mae`, `order` = `desc` (default) | `asc`,
`dir` = 1 / -1, `grade` (comma list), `exit` (substring of exit reason), `win` = 1 / 0.
```json
{"ok": true, "status": "ok", "meta": {}, "total": 54, "offset": 0, "limit": 1,
 "trades": [{"day": "2026-10-13", "entry_t": 1791898500, "exit_t": 1791898800, "dir": 1, "entry": 30649.0, "exit_price": 30774.0,
             "stop0": 30589.25, "target": 30774.0, "risk_pts": 59.75, "qty": 1, "qty_label": "1 MNQ", "pnl": 248.5, "r": 2.079,
             "mae": 0.364, "mfe": 2.385, "grade": "D", "grade_points": -1, "trigger": "CISD", "trigger_tf": "5m", "pools": ["ITL"],
             "target_label": "H1H/ITH", "regime": "rotational", "exit_reason": "TARGET", "score": 3, "bars_held": 2, "model": "sweep",
             "sweep_ext": 30591.25, "signal_t": 1791898200, "pd_pos": -0.258, "open_loc": "below", "rr": 2.09,
             "killzone": "NY AM", "pool_family": "ON"}]}
```

## 33. `GET /api/dash/jobs`  (live)
`refresh=1` re-queues the default backtest, the five-year set and coverage (ignored while one is queued / running).
```json
{"ok": true, "status": "ok", "model_version": "e3f088b2", "queued": [],
 "jobs": [{"key": "bt_NQ_default", "state": "done", "queued": 1792181553, "started": 1792181553, "finished": 1792181574,
           "secs": 20.7, "step": 1, "steps": 1, "msg": "done", "error": null}],
 "cache": [{"key": "5y_NQ", "computed_at": 1792180806, "secs": 13.8, "version": "e3f088b2", "size_kb": 621.6}]}
```
`state`: queued / running / done / failed.

## 34. `GET /api/dash/prep`  (live)
Next session's plan: today if before 15:55 ET on a weekday, else the next weekday.
```json
{"ok": true, "status": "ok", "date": "2026-10-19", "weekday": "Mon", "risk": "LOW", "action": "NORMAL.",
 "notes": "Fed speaker blackout in force (no Fed chair/governor remarks expected until after Oct 28).", "events": [],
 "er10": 0.452, "regime": "trending", "provisional": true, "adr20": 476.94, "sizing": "half size (trending regime)",
 "levels": [{"label": "PDH", "price": 30224.5, "swept": false}], "killzones": ["09:30-11:30", "13:30-15:30"], "flat_et": "15:55",
 "max_trades": 2, "daily_stop": 600.0,
 "checklist": ["Paper bot RUNNING (adapter=paper)", "TradingView alerts active on the MNQ chart (live orders come from the Pine strategy)",
               "Blackouts pasted into the Pine input for the week of 2026-10-19"]}
```
`provisional: true` = the regime still includes a session that has not closed yet.

---

## Notes for dash-ui
* Every number comes from data in this repo. Empty paper history renders as `no_data`, not zeros.
* `source=paper` will be thin for weeks (1 trade). Default the analytics pages to `backtest`, offer `paper` / `5y` toggles.
* Datasets warm up 45 s after a server start (default backtest ~20 s, five-year ~1-3 min at below-normal priority).
* The live bot polls Yahoo `NQ=F` every 60 s (data ~10 min delayed): `data.age_s` up to ~600-900 s during the session is normal.
* The MFFU balance is not visible to this server (TradingView trades the real account): `/eval` takes the owner's numbers as overrides.
