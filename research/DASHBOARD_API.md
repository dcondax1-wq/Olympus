# Dashboard API (`/api/dash/*`): contract for the web UI

Owner: backend session ("dash-api"). Consumer: "dash-ui" (web/**). Code: `engine/dash_*.py`, mounted in `server.py`
inside the `# ---- DASH EXTRAS ----` block. Server: `http://127.0.0.1:8766` (supervisor), same origin as the dashboard.

Status legend: **live** = deployed on the running server and tested; **planned** = in this contract, not deployed yet.

## Conventions (all endpoints)

* All endpoints are `GET`, return JSON, never place orders, never arm anything. Read-only analytics.
* Every response carries `"ok": true|false`, `"status"`, and `"as_of"` (unix seconds, server clock).
* `status` is one of:
  * `"ok"`: data present.
  * `"no_data"`: nothing to show yet (e.g. no paper trades). A human-readable `"message"` explains why. Render an
    empty state, never a zero that looks like a measurement.
  * `"computing"`: a background job is building the dataset. `"retry_after_s"` says when to poll again; `"job"`
    has progress (`step`, `steps`, `msg`). Cached results usually exist after the first warm-up, so this is rare.
* Errors: HTTP 400 `{"ok": false, "error": "..."}`.
* Times: unix seconds UTC (`t`, `entry_t`, ...); trading days are `"YYYY-MM-DD"` (18:00 ET rolls to the next day, the
  engine convention). ET wall-clock strings are `"HH:MM"` and labelled `_et`.
* Money is USD, R is risk multiples. Prices are NQ points (back-adjusted CME NQ1! history + live Yahoo `NQ=F`).
* **Data:** real CME futures only (NQ, ES). CFD data is never read or shown.

### Trade sources (`source=` param on analytics endpoints)

| source | what | notes |
|---|---|---|
| `backtest` (default) | light backtest of the current model over a window | default window = last 120 sessions; override with `days_from`, `days_to` (`YYYY-MM-DD`). Computed in a background subprocess, cached to disk (`cache/dash/`), invalidated when the data file or the model code changes. |
| `paper` | completed paper trades the bot routed (`data/memory.db`, source paper) | empty until the paper bot trades; endpoints return `status:"no_data"` |
| `5y` | five-year NQ history (2021-10 .. now) run as independent 8-week windows (40 sessions + 25-session warm-up each), merged | computed once in the background (~1-3 min), cached to disk |

Every analytics response has a `"meta"` block describing the dataset:

```json
"meta": {"source": "backtest", "sym": "NQ", "from": "2026-04-20", "to": "2026-10-16", "sessions": 120,
         "trades": 61, "computed_at": 1792180000, "stale": false, "model_version": "a1b2c3d4"}
```

`stale: true` = served from the last good cache while a recompute runs (model code or data changed).

---

## Endpoint index

| # | path | purpose | status |
|---|---|---|---|
| 0 | `/api/dash/index` | this list, machine readable | planned |
| 1 | `/api/dash/overview` | one call for the home screen | planned |
| 2 | `/api/dash/eval` | MFFU 50K eval tracker | planned |
| 3 | `/api/dash/montecarlo` | eval pass probability (bootstrap) | planned |
| 4 | `/api/dash/equity` | equity curve + drawdown series | planned |
| 5 | `/api/dash/calendar` | daily P&L calendar heatmap | planned |
| 6 | `/api/dash/heatmap` | hour-of-day x weekday performance | planned |
| 7 | `/api/dash/rdist` | R-multiple histogram | planned |
| 8 | `/api/dash/streaks` | win/loss streaks, current streak | planned |
| 9 | `/api/dash/maemfe` | MAE/MFE scatter per trade | planned |
| 10 | `/api/dash/breakdown` | performance by grade / killzone / direction / pool / trigger / exit / regime / weekday | planned |
| 11 | `/api/dash/frequency` | trades per week vs the 2-4 band | planned |
| 12 | `/api/dash/history` | 5-year per-year / per-quarter stats | planned |
| 13 | `/api/dash/regime` | volatility / regime gauges | planned |
| 14 | `/api/dash/liquidity` | liquidity map: pools and key levels with distance | planned |
| 15 | `/api/dash/sessions` | today's Asia / London / NY ranges vs 20-day averages | planned |
| 16 | `/api/dash/intermarket` | NQ vs ES relative strength / correlation / SMT | planned |
| 17 | `/api/dash/news` | week news + blackout timeline, next blackout | planned |
| 18 | `/api/dash/feed` | bot event log (filterable) | planned |
| 18b | `/api/dash/stream` | Server-Sent Events: live log + heartbeat | planned |
| 19 | `/api/dash/drift` | paper vs backtest on the same days | planned |
| 20 | `/api/dash/memory` | memory insights (learned exit signals, best/worst conditions) | planned |
| 21 | `/api/dash/confluence` | confluence registry leaderboard | planned |
| 22 | `/api/dash/health` | CPU / RAM / disk / uptime / watchdog / keep-awake / autostart | planned |
| 23 | `/api/dash/coverage` | data coverage per instrument / timeframe, gaps | planned |
| 24 | `/api/dash/replay` | bars around one trade + entry/stop/target/exit markers | planned |
| 25 | `/api/dash/launch` | launch checklist + countdown to Sun 2026-10-18 18:00 ET | planned |
| 26 | `/api/dash/clock` | killzone schedule, countdowns, market open/closed | planned |
| 27 | `/api/dash/ticker` | last price, change, day high/low, sparkline | planned |
| 28 | `/api/dash/model` | model state machine, armed setups, open position with live R | planned |
| 29 | `/api/dash/bias` | multi-timeframe FVG bias grid, structure, dealing range, volume profile | planned |
| 30 | `/api/dash/rolling` | rolling-window edge (win rate, avg R, PF over last N trades) | planned |
| 31 | `/api/dash/exits` | exit reasons + exit-signal counterfactuals | planned |
| 32 | `/api/dash/trades` | trade table (filter, sort, paginate) | planned |
| 33 | `/api/dash/jobs` | background job status; `POST`-free warm-up trigger via `?refresh=1` | planned |
| 34 | `/api/dash/prep` | session prep summary (next session plan in one card) | planned |

---

## 0. `GET /api/dash/index`
```json
{"ok": true, "status": "ok", "as_of": 1792180000,
 "endpoints": [{"path": "/api/dash/overview", "params": [], "desc": "home screen"}, "..."]}
```

## 1. `GET /api/dash/overview`
Everything the home screen needs in one call. Cheap (no backtest run; uses cached datasets if present).
```json
{"ok": true, "status": "ok", "as_of": 1792180000,
 "bot": {"running": true, "adapter": "paper", "armed_live": false, "kill": false, "model_state": "OUTSIDE KILLZONE",
         "position": null, "last_poll": 1792179990, "poll_ms": 4607, "errors": 0},
 "price": {"last": 29349.25, "t": 1792179300, "chg": -412.5, "chg_pct": -1.39, "day_high": 29811.0, "day_low": 29268.75},
 "today": {"date": "2026-10-16", "pnl_routed": 0.0, "trades": 0, "engine_day_pnl": 0.0},
 "week": {"key": "2026-W42", "trades": 0, "target_min": 2, "target_max": 4, "status": "below",
          "backtest_tpw": 2.69, "message": "0 trades so far this week (target 2-4)"},
 "eval": {"balance": 50000.0, "profit": 0.0, "target": 3000, "pct_to_target": 0.0, "mll": 48000.0, "cushion": 2000.0,
          "source": "paper"},
 "next_killzone": {"name": "NY AM", "start_t": 1792416600, "start_et": "09:30", "in_s": 236000, "active": false},
 "next_blackout": {"event": "Housing Starts / Building Permits", "t": 1792499400, "impact": "low", "in_s": 319400},
 "data": {"age_s": 465, "stale": false, "market_open": true, "source": "yahoo", "last_bar_t": 1792179300},
 "health": {"ok": true, "issues": [], "watchdog_ok": true, "keepawake": true},
 "launch": {"t": 1792360800, "in_s": 180800, "label": "Sun 2026-10-18 18:00 ET"}}
```

## 2. `GET /api/dash/eval`
MFFU Builder 50K eval tracker. Default state = paper trades since `since` (default `2026-10-18`, the launch).
Because the real MFFU account is traded by TradingView, the UI may pass the owner's real numbers to override:

| param | default | meaning |
|---|---|---|
| `since` | `2026-10-18` | first trading day of this eval |
| `balance` | from paper trades | current account balance (override) |
| `peak_eod` | from paper trades | highest end-of-day balance so far (drives the trailing MLL) |
| `today_pnl` | paper ledger today | today's realised P&L (drives the $1k soft DLL) |

```json
{"ok": true, "status": "ok", "as_of": 1792180000,
 "plan": {"name": "MFFU Builder 50K", "start": 50000, "target": 3000, "mll": 2000, "dll": 1000, "lock_at": 50100,
          "internal_daily_stop": 600},
 "state": {"source": "paper", "since": "2026-10-18", "balance": 50000.0, "profit": 0.0, "peak_eod": 50000.0,
           "trading_days": 0, "trades": 0},
 "target": {"level": 53000.0, "remaining": 3000.0, "pct": 0.0},
 "mll": {"level": 48000.0, "cushion": 2000.0, "pct_cushion_left": 100.0, "locked": false,
         "lock_needs": 2100.0, "note": "EOD trailing: trails the best end-of-day balance by $2,000, locks at $50,100"},
 "dll": {"soft_limit": 1000, "today_pnl": 0.0, "used": 0.0, "pct_used": 0.0, "internal_stop": 600,
         "internal_left": 600.0},
 "projection": {"avg_day_pnl": 140.7, "days_to_pass_linear": 21.3, "mc_median_days": 18.0, "mc_pass_prob": 61.5,
                "basis": "backtest last 120 sessions"},
 "days": [{"date": "2026-10-19", "pnl": 0.0, "balance": 50000.0, "mll": 48000.0}]}
```

## 3. `GET /api/dash/montecarlo`
Bootstrap of daily P&L (+ intraday low) pairs from `source`, simulated through the MFFU rules.

| param | default | |
|---|---|---|
| `source`, `days_from`, `days_to` | backtest | dataset |
| `n` | 3000 | simulated evals (max 20000) |
| `horizon` | 60 | trading days per simulation (max 250) |
| `from_state` | 0 | 1 = start from the current eval state (`/api/dash/eval`; accepts the same overrides) |

```json
{"ok": true, "status": "ok", "meta": {"source": "backtest", "trades": 61, "sessions": 120},
 "n": 3000, "horizon": 60, "pass_prob": 61.5, "fail_prob": 22.1, "open_prob": 16.4,
 "days_to_pass": {"median": 18, "p25": 11, "p75": 29, "p90": 41, "hist": [{"d": 5, "n": 40}, {"d": 10, "n": 211}]},
 "bands": {"days": [1, 2, 3], "p5": [-300.0], "p25": [0.0], "p50": [120.0], "p75": [480.0], "p95": [1500.0]},
 "final": {"p5": -1800.0, "p50": 3000.0, "p95": 3100.0},
 "sample_paths": [[0, 120.0, -40.0]],
 "start": {"balance": 50000.0, "peak_eod": 50000.0}}
```

## 4. `GET /api/dash/equity`
Params: `source`, `days_from`, `days_to`, `start` (default 50000).
```json
{"ok": true, "status": "ok", "meta": {},
 "trades": [{"t": 1791898800, "eq": 50248.5, "dd": 0.0, "pnl": 248.5, "r": 2.08}],
 "days": [{"date": "2026-10-13", "eq": 50248.5, "dd": 0.0, "pnl": 248.5, "trades": 1}],
 "summary": {"net": 10974.5, "max_dd": -462.0, "max_dd_date": "2026-09-03", "longest_underwater_days": 9,
             "current_dd": 0.0, "peak": 60974.5, "recovery_factor": 23.8}}
```

## 5. `GET /api/dash/calendar`
Params: `source`, `days_from`, `days_to`.
```json
{"ok": true, "status": "ok", "meta": {},
 "days": [{"date": "2026-10-13", "dow": 1, "pnl": 248.5, "trades": 1, "r": 2.08, "regime": "rotational"}],
 "months": [{"month": "2026-10", "pnl": 1250.0, "trades": 6, "green_days": 3, "red_days": 1, "flat_days": 8}],
 "max_abs_pnl": 2470.5}
```

## 6. `GET /api/dash/heatmap`
Hour of entry (ET) x weekday. Params: `source`, `days_from`, `days_to`, `metric` (`avg_r` default | `pnl` | `wr` | `n`).
```json
{"ok": true, "status": "ok", "meta": {}, "metric": "avg_r",
 "hours": [9, 10, 11, 13, 14, 15], "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
 "cells": [{"hour": 9, "dow": 0, "n": 4, "pnl": 820.0, "avg_r": 0.61, "wr": 50.0}],
 "by_hour": [{"hour": 9, "n": 12, "avg_r": 0.4}], "by_dow": [{"dow": 0, "n": 8, "avg_r": 0.2}]}
```

## 7. `GET /api/dash/rdist`
Params: `source`, `days_from`, `days_to`, `bin` (default 0.25 R).
```json
{"ok": true, "status": "ok", "meta": {}, "bin": 0.25,
 "bins": [{"lo": -1.25, "hi": -1.0, "n": 7, "wins": 0}],
 "stats": {"n": 42, "mean": 0.845, "median": -0.02, "std": 1.6, "skew": 1.4, "pct_ge_2r": 21.4, "pct_le_m1r": 16.7,
           "expectancy_usd": 261.3}}
```

## 8. `GET /api/dash/streaks`
Params: `source`, `days_from`, `days_to`.
```json
{"ok": true, "status": "ok", "meta": {},
 "trades": {"current": {"kind": "win", "len": 1}, "max_win": 2, "max_loss": 11,
            "hist_win": [{"len": 1, "n": 10}], "hist_loss": [{"len": 1, "n": 4}],
            "sequence": [{"entry_t": 1791898500, "w": 1, "r": 2.08}]},
 "days": {"current": {"kind": "green", "len": 1}, "max_green": 3, "max_red": 4}}
```

## 9. `GET /api/dash/maemfe`
MAE / MFE in R per trade. Params: `source`, `days_from`, `days_to`.
```json
{"ok": true, "status": "ok", "meta": {},
 "points": [{"entry_t": 1791898500, "mae": 0.36, "mfe": 2.38, "r": 2.08, "win": true, "exit": "TARGET", "grade": "D", "dir": 1}],
 "summary": {"winners_median_mae": 0.31, "losers_median_mfe": 0.42, "pct_winners_mae_gt_half_r": 18.0,
             "avg_capture": 0.62, "left_on_table_r": 14.2}}
```
`avg_capture` = mean(R / MFE) over winners; `left_on_table_r` = sum(MFE - R) over winners.

## 10. `GET /api/dash/breakdown`
Params: `source`, `days_from`, `days_to`, `by` (comma list; default all of `grade,killzone,dir,pool,trigger,exit,regime,dow,target,model`).
```json
{"ok": true, "status": "ok", "meta": {},
 "groups": {"grade": [{"key": "A", "n": 8, "wins": 4, "wr": 50.0, "avg_r": 1.1, "total_r": 8.8, "pnl": 3100.0, "pf": 4.2}],
            "killzone": [{"key": "NY AM", "n": 30}, {"key": "NY PM", "n": 12}],
            "pool": [{"key": "PDL", "n": 5}]}}
```
`killzone`: NY AM (09:30-11:30 entries), NY PM (13:30-15:30), other. `pool`: highest-priority kind of the raided pool(s).

## 11. `GET /api/dash/frequency`
Owner's hard rule: 2-4 trades per week. Params: `source`, `days_from`, `days_to`.
```json
{"ok": true, "status": "ok", "meta": {}, "band": [2, 4],
 "weeks": [{"key": "2026-W41", "start": "2026-10-05", "n": 3, "pnl": 820.0, "in_band": true, "zone": "in"}],
 "summary": {"weeks": 24, "avg": 2.6, "median": 3, "pct_in_band": 58.3, "pct_below": 25.0, "pct_above": 16.7,
             "pct_zero": 8.3, "rolling4": 2.75},
 "this_week": {"key": "2026-W42", "paper": 0, "backtest": 2}}
```

## 12. `GET /api/dash/history`
Five-year NQ stats from the `5y` dataset. Params: `by` (`year` | `quarter` | `month`, default `quarter`).
```json
{"ok": true, "status": "ok", "meta": {"source": "5y", "from": "2021-11-22", "to": "2026-10-16", "windows": 32},
 "by": "quarter",
 "periods": [{"key": "2022Q1", "sessions": 61, "trades": 30, "tpw": 2.46, "wr": 36.7, "avg_r": 0.41, "pf": 1.9,
              "net": 4210.0, "max_dd": -1100.0, "pct_weeks_in_band": 54.0, "pct_zero_weeks": 8.0, "avg_er10": 0.31}],
 "total": {"sessions": 1250, "trades": 610, "tpw": 2.44, "wr": 35.0, "avg_r": 0.33, "pf": 1.7, "net": 52000.0}}
```
`status:"computing"` with `job` progress while the first build runs.

## 13. `GET /api/dash/regime`
```json
{"ok": true, "status": "ok", "as_of": 1792180000,
 "daily": {"atr14": 412.3, "adr20": 398.1, "adr60": 361.0, "today_range": 542.25, "today_pct_adr": 136.2,
           "er5": 0.82, "er10": 0.29, "regime": "rotational", "regime_threshold": 0.45, "vol_expansion": 1.02,
           "day_range_guard": {"limit_x_adr": 1.6, "used_x_adr": 1.36, "blocks_entries": false}},
 "intraday": {"atr14_5m": 38.5, "atr14_5m_pct_of_20d": 112.0},
 "vix": {"VIX": {"close": 18.2, "date": "2026-10-15"}, "VXN": {"close": 22.4, "date": "2026-10-15"}},
 "series": [{"date": "2026-10-15", "er10": 0.31, "range": 410.0, "regime": "rotational"}]}
```

## 14. `GET /api/dash/liquidity`
Pools the engine currently tracks + key levels, each with distance from price. Params: `max` (default 30).
```json
{"ok": true, "status": "ok", "price": 29349.25, "t": 1792179300, "adr20": 398.1,
 "levels": [{"label": "PDH", "price": 30225.0, "side": "H", "dist": 875.75, "dist_adr": 2.2, "kind": "key",
             "swept": false}],
 "pools": [{"label": "H1H/ONH/PDH/ITH", "price": 31290.0, "side": "H", "kinds": ["ITH", "H1H", "ONH", "PDH"],
            "strength": 2, "dist": 1940.75, "dist_adr": 4.9, "formed_t": 1791764100}],
 "nearest": {"above": {"label": "LOL", "price": 29400.0, "dist": 50.75}, "below": {"label": "ITL", "price": 29268.75, "dist": -80.5}},
 "source": "live engine"}
```
Key level labels: `PDH PDL PWH PWL ONH ONL ASH ASL LOH LOL RTH_OPEN MIDNIGHT_OPEN PDC`.

## 15. `GET /api/dash/sessions`
Today's session ranges (ET): Asia 20:00-24:00, London 02:00-05:00, overnight 18:00-09:30, NY AM 09:30-11:30,
NY lunch 11:30-13:30, NY PM 13:30-16:00.
```json
{"ok": true, "status": "ok", "date": "2026-10-16",
 "sessions": [{"key": "ASIA", "name": "Asia", "start_et": "20:00", "end_et": "00:00", "high": 30211.75, "low": 29959.25,
               "range": 252.5, "avg20": 180.4, "pct_of_avg": 140.0, "state": "done"}],
 "day": {"open": 29760.0, "high": 30225.0, "low": 29268.75, "range": 956.25}}
```
`state`: `done` | `active` | `upcoming`.

## 16. `GET /api/dash/intermarket`
NQ vs ES (CME futures only). Params: `days` (default 60).
```json
{"ok": true, "status": "ok",
 "today": {"nq_chg_pct": -1.39, "es_chg_pct": -0.92, "spread_pct": -0.47, "leader": "ES"},
 "corr": {"d20": 0.91, "d60": 0.88, "intraday_5m_today": 0.95},
 "beta_60d": 1.24,
 "rs_series": [{"date": "2026-08-07", "nq": 100.0, "es": 100.0, "ratio": 1.0}],
 "smt": {"today": [{"level": "PDL", "nq_swept": true, "es_swept": false, "note": "NQ took PDL, ES held: bullish SMT"}]},
 "as_of": {"nq": 1792179300, "es": 1792179300}, "es_source": "yahoo ES=F + stored ES_5m"}
```

## 17. `GET /api/dash/news`
Params: `days` (default 7), `impact` (`medium` default | `high` | `low`).
```json
{"ok": true, "status": "ok", "now": 1792180000,
 "events": [{"date": "2026-10-20", "time_et": "08:30", "t": 1792499400, "event": "Housing Starts / Building Permits",
             "impact": "low", "blackout_start": null, "blackout_end": null, "flatten_at": null,
             "killzones_hit": [], "fomc_pm_off": false, "source": "census.gov", "confidence": "official"}],
 "days": [{"date": "2026-10-20", "risk": "LOW", "action": "NORMAL.", "n_high": 0, "notes": null}],
 "next_blackout": {"event": "CB Consumer Confidence", "start_t": 1793110500, "end_t": 1793113200, "in_s": 930500},
 "in_blackout": false, "guard": {"allowed": true, "reasons": []}}
```

## 18. `GET /api/dash/feed`
Params: `since` (unix, default 0), `types` (comma list: `system,order,sweep,signal,entry,exit,risk,warn,error,news,tradingview,daily,skip`), `limit` (default 100, max 400).
```json
{"ok": true, "status": "ok", "count": 2,
 "events": [{"t": 1792180067, "type": "warn", "text": "feed revised 1 already-closed bar(s)...", "level": "warn"}],
 "types": {"warn": 12, "system": 5}}
```

## 18b. `GET /api/dash/stream` (Server-Sent Events)
`text/event-stream`. Events: `log` (one bot log row, same shape as feed rows), `tick` every 5 s
(`{"t", "price", "model_state", "running", "data_age_s", "position": {...}|null}`). Use `new EventSource('/api/dash/stream')`.
Optional `since` param replays log rows newer than it first.

## 19. `GET /api/dash/drift`
Paper trades vs the backtest of the same days (match = same direction, entry within 10 min).
```json
{"ok": true, "status": "no_data", "message": "No completed paper trades yet: drift appears after the first paper trade."}
```
With data:
```json
{"ok": true, "status": "ok", "days": ["2026-10-19"],
 "pairs": [{"day": "2026-10-19", "paper": {"entry_t": 1, "dir": 1, "r": 1.2, "pnl": 300.0},
            "backtest": {"entry_t": 1, "dir": 1, "r": 1.5, "pnl": 370.0}, "match": "matched", "r_diff": -0.3}],
 "summary": {"paper_trades": 1, "backtest_trades": 1, "matched": 1, "paper_only": 0, "backtest_only": 0,
             "match_rate": 100.0, "pnl_diff": -70.0, "avg_entry_slip_min": 0.0}}
```

## 20. `GET /api/dash/memory`
```json
{"ok": true, "status": "ok",
 "counts": {"paper": 0, "live": 0, "backtest": 0},
 "realised": {"trades": 0, "net": 0.0, "win_rate": 0.0, "avg_r": 0.0},
 "signals": [{"key": "giveback", "n": 0, "avg_gain": 0.0, "learned": false, "to_go": 20}],
 "conditions": {"source": "backtest", "best": [{"dim": "grade", "key": "A", "n": 8, "avg_r": 1.1}],
                "worst": [{"dim": "killzone", "key": "NY PM", "n": 12, "avg_r": -0.2}]},
 "calibration": {"realised": {}},
 "message": "No paper trades in memory yet; conditions come from the backtest."}
```

## 21. `GET /api/dash/confluence`
Params: `status` (comma list of `ACTIVE,PROBATION,CANDIDATE,RETIRED`, default all), `sort` (`lift` default | `n` | `name`).
```json
{"ok": true, "status": "ok", "generated": "2026-10-16 15:08", "counts": {"ACTIVE": 8, "PROBATION": 10, "CANDIDATE": 57, "RETIRED": 24},
 "rule": {"tpw": [2.0, 4.5], "text": "..."}, "baseline": {"nq_tpw": 2.6, "nq_pf": 3.1},
 "items": [{"id": "amd_day_open", "name": "PO3: raid beyond daily open", "status": "RETIRED", "decision": "retire",
            "verdict": "NOISE", "lift_pooled": 0.296, "lift_decide": -0.022, "lift_confirm": 0.858, "n_on": 33, "n_off": 18,
            "ci90": [-0.658, 1.217], "agree": 1, "valid": 3, "weight": 0, "mechanism": "grade (needs engine hook)",
            "reason": "...", "history": ["RETIRED", "RETIRED"]}],
 "last_run": {"run": "20261016-150814", "secs": 8.4, "added": [], "retired_live": []}}
```

## 22. `GET /api/dash/health`
```json
{"ok": true, "status": "ok",
 "system": {"cpu_pct": 12.0, "cpu_count": 8, "mem_pct": 61.0, "mem_used_gb": 9.8, "mem_total_gb": 16.0,
            "disk_pct": 70.1, "disk_free_gb": 140.2, "boot_t": 1792000000},
 "process": {"pid": 1234, "uptime_s": 321, "rss_mb": 410.0, "threads": 14, "cpu_pct": 3.0, "python": "3.12.10"},
 "supervisor": {"pid": 6044, "alive": true},
 "bot": {"running": true, "adapter": "paper", "last_ok_poll": 1792180065, "poll_ms": 4607, "consecutive_errors": 0,
         "data_age_s": 465, "stale": false, "revisions": 2, "last_error": null},
 "watchdog": {"ok": true, "issues": [], "thread_alive": true},
 "keepawake": {"held": true, "since": 1792179937},
 "autostart": {"record": true, "resumed": true, "task_installed": false},
 "log": {"path": "logs/server-20261016.log", "size_kb": 2.1}}
```

## 23. `GET /api/dash/coverage`
```json
{"ok": true, "status": "ok",
 "files": [{"sym": "NQ", "tf": "5m", "rows": 354216, "from": "2021-10-18", "to": "2026-10-16", "sessions": 1293,
            "missing_weekdays": 12, "intraday_gaps": 3, "last_bar_t": 1792179300, "mtime": 1792178000}],
 "sources": {"tv-NQ1!": {"from": "2021-10-18", "to": "2026-08-21", "sessions": 1253}},
 "manifest_generated": "2026-10-16T15:32:38", "price_space": "back-adjusted ..."}
```

## 24. `GET /api/dash/replay`
Params: `entry_t` (required), `source` (default backtest; also `paper`, `5y`), `before` (bars before entry, default 36),
`after` (bars after exit, default 24), `tf` (`5m` default | `1m` when true 1m bars exist).
```json
{"ok": true, "status": "ok",
 "trade": {"entry_t": 1791898500, "exit_t": 1791898800, "dir": 1, "entry": 30649.0, "stop0": 30589.25, "target": 30774.0,
           "exit_price": 30774.0, "r": 2.08, "pnl": 248.5, "grade": "D", "trigger": "CISD", "exit_reason": "TARGET",
           "pools": ["ITL"], "target_label": "H1H/ITH", "sweep_ext": 30580.0, "signal_t": 1791898200},
 "bars": {"tf": "5m", "t": [], "o": [], "h": [], "l": [], "c": [], "v": []},
 "markers": [{"t": 1791898500, "price": 30649.0, "kind": "entry"}, {"t": 1791898800, "price": 30774.0, "kind": "exit"}],
 "lines": [{"price": 30589.25, "kind": "stop"}, {"price": 30774.0, "kind": "target"}]}
```

## 25. `GET /api/dash/launch`
```json
{"ok": true, "status": "ok", "launch_t": 1792360800, "launch_label": "Sun 2026-10-18 18:00 ET", "in_s": 180800,
 "ready": false, "score": {"pass": 12, "warn": 2, "fail": 1},
 "checks": [{"key": "bot_paper", "label": "Paper bot running", "state": "pass", "detail": "adapter=paper"},
            {"key": "not_armed", "label": "Live NOT armed on this PC", "state": "pass"},
            {"key": "blackouts", "label": "Pine blackouts cover launch week", "state": "warn", "detail": "..."}]}
```
`state`: `pass` | `warn` | `fail` | `info`.

## 26. `GET /api/dash/clock`
```json
{"ok": true, "status": "ok", "now": 1792180000, "now_et": "Fri 15:48", "market_open": true,
 "next_open_t": 1792360800, "next_close_t": 1792184400,
 "killzones": [{"name": "London", "start_et": "02:00", "end_et": "05:00", "trades": false, "state": "done"},
               {"name": "NY AM", "start_et": "09:30", "end_et": "11:30", "trades": true, "state": "done"},
               {"name": "NY PM", "start_et": "13:30", "end_et": "15:30", "trades": true, "state": "done"}],
 "flat_et": "15:55", "next_entry_window": {"name": "NY AM", "start_t": 1792416600, "in_s": 236600}}
```

## 27. `GET /api/dash/ticker`
Params: `n` (sparkline bars, default 78 = one RTH day of 5m).
```json
{"ok": true, "status": "ok", "sym": "NQ", "last": 29349.25, "t": 1792179300, "prev_close": 29761.75, "chg": -412.5,
 "chg_pct": -1.39, "day_high": 30225.0, "day_low": 29268.75, "spark": [29400.0, 29380.5], "spark_t0": 1792156200,
 "data_age_s": 465, "source": "live bot bars (yahoo NQ=F) + stored CME NQ1!"}
```

## 28. `GET /api/dash/model`
```json
{"ok": true, "status": "ok", "model_state": "ARMED - HUNTING IFVG",
 "flow": ["WAITING FOR SWEEP", "ARMED - HUNTING IFVG", "ORDER PENDING", "IN TRADE", "DONE FOR DAY"], "flow_index": 1,
 "setups": {"long": {"dir": 1, "ext": 29268.75, "arm_t": 1792155000, "pools": ["ITL"], "age_min": 42}, "short": null},
 "pending": null,
 "position": {"dir": 1, "entry": 0, "stop": 0, "target": 0, "qty": 0, "live_r": 0.4, "to_stop_pts": 0, "to_target_pts": 0},
 "day": {"pnl": 0.0, "trades": 0, "max_trades": 2, "daily_stop": 600}}
```

## 29. `GET /api/dash/bias`
```json
{"ok": true, "status": "ok", "net": -4,
 "tfs": [{"tf": "1D", "bias": -1, "last": "respected bearish", "zones": [{"dir": 1, "top": 29647.5, "bot": 29552.5, "state": "inverted"}]}],
 "structure": {"1H": -1, "15m": -1, "h1_protected_low": null, "h1_protected_high": null},
 "dealing_range": {"high": 30225.0, "low": 30126.0, "eq": 30175.5, "pos": -7.8, "zone": "discount"},
 "midnight_open": 30201.5, "open_loc": "inside",
 "profile": {"poc": 29992.5, "vah": 30100.0, "val": 29780.0, "date": "2026-10-15", "lo": 29620.0, "bin": 5.0, "hist": []}}
```

## 30. `GET /api/dash/rolling`
Params: `source`, `days_from`, `days_to`, `window` (trades, default 20).
```json
{"ok": true, "status": "ok", "meta": {}, "window": 20,
 "series": [{"i": 20, "entry_t": 1791898500, "wr": 35.0, "avg_r": 0.62, "pf": 2.4, "sum_r": 12.4}],
 "latest": {"wr": 35.0, "avg_r": 0.62, "pf": 2.4}, "full": {"wr": 33.3, "avg_r": 0.845}}
```

## 31. `GET /api/dash/exits`
Params: `source`, `days_from`, `days_to`.
```json
{"ok": true, "status": "ok", "meta": {},
 "reasons": [{"key": "TARGET", "n": 9, "avg_r": 2.4, "pnl": 6100.0, "share": 21.4}],
 "signals": [{"key": "giveback", "n": 10, "avg_gain": 0.6, "acted": true}]}
```

## 32. `GET /api/dash/trades`
Params: `source`, `days_from`, `days_to`, `limit` (default 50, max 1000), `offset`, `sort` (`entry_t` | `r` | `pnl`),
`order` (`desc` default), `dir` (1|-1), `grade`, `exit`, `win` (1|0).
```json
{"ok": true, "status": "ok", "meta": {}, "total": 42, "offset": 0, "limit": 50,
 "trades": [{"day": "2026-10-13", "entry_t": 1791898500, "exit_t": 1791898800, "dir": 1, "entry": 30649.0, "exit_price": 30774.0,
             "stop0": 30589.25, "target": 30774.0, "qty": 1, "qty_label": "1 MNQ", "pnl": 248.5, "r": 2.08, "mae": 0.36, "mfe": 2.38,
             "grade": "D", "trigger": "CISD", "pools": ["ITL"], "target_label": "H1H/ITH", "regime": "rotational",
             "exit_reason": "TARGET", "killzone": "NY AM", "bars_held": 2}]}
```

## 33. `GET /api/dash/jobs`
`?refresh=1` re-queues the default datasets (ignored while one runs).
```json
{"ok": true, "status": "ok",
 "jobs": [{"key": "backtest:2026-04-20:2026-10-16", "state": "done", "started": 1792180000, "finished": 1792180009,
           "secs": 9.1, "error": null}, {"key": "5y", "state": "running", "step": 12, "steps": 32, "msg": "window 2023-05-01"}]}
```

## 34. `GET /api/dash/prep`
Next session's plan in one card (today if before 15:55 ET on a weekday, else the next trading day).
```json
{"ok": true, "status": "ok", "date": "2026-10-19", "weekday": "Mon",
 "risk": "LOW", "action": "NORMAL.", "events": [], "notes": "Fed speaker blackout in force ...",
 "regime": "rotational", "er10": 0.29, "adr20": 398.1,
 "levels": [{"label": "PDH", "price": 30225.0}], "killzones": ["09:30-11:30", "13:30-15:30"], "flat_et": "15:55",
 "checklist": ["Paper bot RUNNING adapter=paper", "TradingView alerts active on MNQ1!", "Blackouts pasted for week of 2026-10-19"]}
```

---

## Notes for dash-ui
* Poll cadence: `overview` / `ticker` / `model` every 10-15 s (or use `stream`); analytics endpoints on page open.
* Heavy datasets warm up in the background at server start (~10 s for the 120-session backtest, 1-3 min for `5y`).
* The live bot runs on 5m bars from Yahoo `NQ=F` (delayed); `data.age_s` up to ~10 min during the session is normal.
* Endpoints never invent numbers: empty paper history = `status:"no_data"`.
