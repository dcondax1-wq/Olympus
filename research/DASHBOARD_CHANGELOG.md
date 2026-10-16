# Dashboard changelog: overhaul of 2026-10-16 (dash-ui)

Front end only (`web/**`). Data comes from the dash-api contract in `research/DASHBOARD_API.md` (`/api/dash/*`) and the
existing endpoints. Rules kept: real CME futures only (no CFD data or wording), paper only, no control that arms live trading
or places orders, no credentials / webhook URLs shown. Every widget shows a "waiting for data" state instead of a number when
its source is empty or not deployed.

New files: `web/css/dash.css`, `web/js/dash/{kit,widgets,live,home,analytics,ops,ux}.js`.
Touched: `web/index.html` (command page restructured into a widget grid, 2 new pages, nav links, dash.css),
`web/js/app.js` (routing + boot), `web/js/palette.js` (extension hook), `web/js/page-robust.js` (futures-only long test),
`web/sw.js` (shell v4), small wording fixes in `page-conf.js`, `page-playbook.js`, `state.js`.

## Command Center (home)

| # | Feature | Data source |
|---|---|---|
| 1 | Mission strip: glass cockpit with bot status orb (pulsing ring), paper / armed / kill / error badges | `/api/live/state`, `/api/dash/overview.bot` |
| 2 | Live NQ futures price with up/down flash, change vs prior session, day H/L, intraday sparkline | `/api/dash/overview.price`, live 5m bars |
| 3 | Today's paper P&L, animated number ticker | `/api/dash/overview.today` (fallback `day_pnl_routed`) |
| 4 | This week's trades vs the owner's 2–4 band (segmented band meter) | `/api/dash/overview.week` (fallback `/api/memory/trades`) |
| 5 | Killzone countdown ring: live progress inside 09:30–11:30 / 13:30–15:30 ET, countdown to the next one | client ET clock |
| 6 | MFFU profit-to-target meter ($3,000) with Monte Carlo projection (pass % in 60 d, median days) | `/api/dash/eval` (+ projection) |
| 7 | MFFU EOD trailing max-loss cushion meter ($2,000, locks at $50,100) | `/api/dash/eval.mll` |
| 8 | MFFU soft daily loss meter ($1,000) with the bot's $600 stop marked | `/api/dash/eval.dll` |
| 9 | "Real account" entry: type the real MFFU balance / best EOD / today's P&L to drive the meters (saved in this browser) | `/api/dash/eval?balance=&peak_eod=&today_pnl=` |
| 10 | Launch T-minus chip, Sun 2026-10-18 18:00 ET | client clock |
| 11 | Next news blackout chip with countdown, red alarm while a blackout is active | `/api/dash/overview.next_blackout`, Pine `blackouts.txt` |
| 12 | Data-freshness pill (bar age, source, market closed) | `overview.data`, live `health` |
| 13 | Watchdog chip (uptime, keep-awake) and market open / session chip | `/api/health/watchdog` |
| 14 | "What the bot is thinking": state-machine stepper, typed plain-English narrative, armed long/short setup cards with distance to the sweep extreme, position, protected levels, recent thoughts | `/api/dash/model`, live state |
| 15 | Launch readiness: score ring, automatic checks (problems first, passes collapsed) + owner's manual checklist (TV alert, bridge, blackouts pasted, phone alerts, MFFU rules) | `/api/dash/launch` |
| 16 | Session timeline 18:00 → 17:00 ET: intraday price path, Asia / London / killzone bands, blackout windows, bot events plotted on price, NOW cursor | live bars + log, blackouts |
| 17 | Next session prep card: risk, regime, ADR, levels, events, checklist | `/api/dash/prep` |
| 18 | Live liquidity map: nearest untaken pools above / below, distance in points and ×ADR20, brightness by proximity, armed setups | `/api/dash/liquidity` |
| 19 | Session ranges today (Asia, London, overnight, NY AM, lunch, NY PM) on one price scale vs their 20-day averages, live price marker | `/api/dash/sessions` |
| 20 | Live event feed with filters (all / trades / liquidity / risk / system), repeated warnings collapsed, new rows flash | live log / SSE `/api/dash/stream` |
| 21 | Eval pass odds: Monte Carlo ring + pass / open / fail stacked bar | `/api/dash/montecarlo` (fallback `/api/montecarlo`) |
| 22 | NQ vs ES relative strength: 60-day paths, correlation 20 / 60 d, beta, leader, SMT swept-level grid | `/api/dash/intermarket` (fallback `/api/markets`) |
| 23 | Regime & volatility gauges: ER10 trendiness, day range % ADR, VIX, ER10 sparkline, day-range guard alarm when it blocks entries | `/api/dash/regime` |
| 24 | Confluence leaderboard: top pooled lift by status tab | `/api/dash/confluence` (fallback registry) |
| 25 | Memory insights: paper / live counts, realised stats, exit-signal learning progress, best / worst conditions | `/api/dash/memory` |
| 26 | Underwater chart: drawdown of cumulative strategy P&L vs the $2,000 MLL, max DD, longest underwater, time underwater | backtest |

All existing command cards (KPIs, equity, eval, model state, ladder, clock, MTF, premium/discount, brain, trades, what-if,
edge decay, rules gauges) became widgets too, so they can be moved, resized, hidden, expanded and exported.

## Deep Stats page (new, `?page=analytics`)

| # | Feature | Data source |
|---|---|---|
| 27 | Source switch (loaded backtest · 5-year windowed · paper) + range (all / 3y / 1y / 6m / 120 sessions) + trades CSV | `S.res`, `/api/dash/trades?source=` |
| 28 | P&L calendar heatmap: every session, one row per year (GitHub style) | same |
| 29 | Five years by quarter: net bars + trades/week line against the 2–4 band, full table (sessions, trades, /wk, % weeks in band, win %, avg R, PF, net, max DD) | `/api/dash/history` (5y) or computed |
| 30 | Trades per week vs the 2–4 band: histogram, % in band, zero-trade weeks, last 4 weeks, 52-week sparkline | same |
| 31 | Hour × weekday heatmap (avg R / net $ / win % / count) | same |
| 32 | Monthly returns matrix (year × month) | same |
| 33 | Edge breakdown by grade, killzone, direction, regime, exit, trigger, weekday, hour | same |
| 34 | MAE / MFE scatter with capture %, left-on-table R | same |
| 35 | Streaks: current, longest win / loss runs, losing-run histogram, last 160 trades strip | same |
| 36 | R-multiple distribution with mean / median / skew / ≥2R / ≤−1R | same |
| 37 | Exit mix donut with avg R per reason | same |
| 38 | Holding time vs R | same |
| 39 | Rolling 20-trade edge (avg R + win %) | same |
| 40 | Cumulative R, longs vs shorts | same |

## Ops & Data page (new, `?page=ops`)

| # | Feature | Data source |
|---|---|---|
| 41 | System health tiles: server, bot, poll time, data age, errors, feed hygiene, entry guard, watchdog, keep-awake, auto-resume, CPU / RAM / disk, supervisor | `/api/dash/health`, watchdog, live health |
| 42 | Latency monitor: dashboard API round trip p50 / p95 sparkline, bot poll duration | client-measured |
| 43 | News & blackout timeline: 8 trading days × 07:00–17:00 ET, killzones, releases by impact, Pine blackout windows, now marker | `/api/dash/news`, blackouts |
| 44 | Data coverage: symbol × timeframe matrix, history bars 2021→today, gaps (futures only) | `/api/dash/coverage` |
| 45 | Paper vs backtest drift: matched trades, slip, P&L gap, per-day ΔR | `/api/dash/drift` |
| 46 | Background jobs: dash datasets, confluence learning cycle, data refresh | `/api/dash/jobs` |
| 47 | Searchable bot log with CSV export | live log |

## Platform & UX

| # | Feature | Notes |
|---|---|---|
| 48 | Widget framework: drag ⠿ to reorder (mouse + touch), layout saved per page | `localStorage le.dash.layout.*`, try/catch |
| 49 | Layout drawer: show / hide, size S / M / L / W / XL, move, reset | ⚙ Layout or W |
| 50 | Per-widget expand to a full-screen modal | ⤢, Esc closes |
| 51 | Per-widget export: CSV data + PNG snapshot; whole-page snapshot (X) | html-to-image 1.11.11 (cdnjs) |
| 52 | Toast notifications for new bot events + notification centre (✉ with unread badge, history, pop-up toggle) | sound stays on the 🔔 toggle (sound.js) |
| 53 | Keyboard shortcuts (G+letter pages, 1–5, Z, F, T, D, R, N, W, X, M, ?) + help overlay | `?` |
| 54 | Extended command palette: zen, TV wall, dark/light, themes, risk calc, notifications, layout, snapshot, shortcuts, real-account entry, "Widget:" jump-and-expand | Ctrl+K or / |
| 55 | Zen / focus mode (hides rail, ticker, status bar) | Z |
| 56 | TV-wall fullscreen: rotates Command → Deep Stats → Ops every 45 s with a progress bar | F, Esc exits |
| 57 | Quick theme switcher (all skins, dark / light filter) + D toggles dark ↔ light | ◐ or T |
| 58 | Floating risk calculator: MNQ / NQ size for $ risk and stop, MFFU caps, target, losses-to-MLL, SL / TP prices (information only) | ⚖ or R |
| 59 | Terminal status bar: mode, server latency, bot state, data age, next killzone, dash endpoints live, last event, ET clock, T-minus | desktop only |
| 60 | Dash API gate: `/api/dash/*` is called only when `/api/dash/index` lists it; otherwise fallback or waiting state; live SSE stream with polling fallback | `kit.js dash()` |

## Fixes

* Robustness › Long-horizon validation now runs the five-year NQ futures history (the old NQX CFD test is gone); CFD wording
  removed from Confluence Lab, Playbook and the trend-model hint.
* Service worker registers after the boot backtest (it timed out while the server was busy) and is skipped inside the Claude
  desktop preview pane, which cannot host one.

## Verified (2026-10-16, http://127.0.0.1:8766)

All 22 pages visited with zero JavaScript errors; 375 px phone width has no horizontal overflow on Command, Deep Stats and Ops;
dark (Terminal) and light (Arctic) themes checked; drag-reorder, layout drawer, expand, palette, shortcuts, zen, TV wall,
risk calculator, notifications and PNG rendering exercised.
