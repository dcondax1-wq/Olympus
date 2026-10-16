# Live loop QA - Liquidity Engine (NQ, paper -> prop eval)

Run the harness any time (no network, writes nothing under `data/`):

    python -X utf8 -m tests.test_live_dryrun          # ~2.5 min, ~400 real Engine polls
    python -X utf8 -m tests.test_live_dryrun --quick  # ~2 min

Exit code 0 = every assertion passed. The run replays the last 3 trading sessions of `data/NQ_5m.csv`
(2026-10-13, 10-14, 10-15) bar by bar through `LiveBot` + `PaperAdapter` with a frozen clock, a history source
that only reveals bars already closed at the simulated "now", a stubbed fresh-bar fetch (also used to inject
failures) and captured alerts. Reference = a plain `Engine` run over the full 60-day files (`live=True`).

## What was verified (44 assertions, all passing on 2026-10-15)

Replay of 3 sessions (398 polls)
- No exception anywhere in the replay; `state.t` equals the simulated bar on every poll (no look-ahead, no lag).
- Entries and exits routed by the live loop match the plain backtest exactly: 10-13 09:35 L 1 MNQ -> 09:40 TARGET,
  10-15 13:55 S 2 MNQ -> 15:00 BE/TRAIL (same bar, same qty, same reason). Diff table printed by the harness.
- Flat at or after 16:00 ET on every poll of every session (engine TIME exit at 15:55).
- End-of-day summary alert fires exactly once per session (and not for the evening the bot was started).
- `snapshot()` is JSON-serialisable and now carries `health`, `kill`, `day_pnl_routed`, `trades_today`.
- Windowed Engine run (10/20/30 days) produces the same trades as the full 60-day run over the replay sessions,
  and was additionally checked at three different "now" offsets (sliding window start) before the change.

Failure injection (the loop must log, flag and continue)
- Fresh-data fetch raising -> poll completes on stored history, `health.last_error` set, nothing stale.
- Stale feed (20 min old) -> `health.stale=True`, `data_age_s`, WARN log line on the transition, recovery logged.
- Partial (still forming) last bar and an off-grid quote row -> dropped before the Engine sees them.
- Duplicate bar with revised OHLC -> de-duplicated (keep last), `health.revisions` counts it, WARN logged.
- Clock jump backwards 1 h / forwards 3 h -> logged, poll survives, closed-bar filter still correct.
- `alerts.send` raising -> logged, the order in the same poll is still routed.
- `adapter.send` raising -> failure recorded in the ledger row, poll survives.
- `data_source="tradovate"` returning None or the module missing -> falls back to Yahoo, `health.fallback=True`,
  one log line per poll.
- Feed stale for > 3 polls inside an entry window -> `health.entries_blocked=True`, the late entry is NOT routed
  and its later exit is not routed either; open positions keep being managed.
- An entry first seen more than 2 bars + 60 s after its fill bar (restart or feed gap) is not chased.
- A trade that opened and closed while the bot was down produces no phantom paper exit.
- Feed stalls across flat time with a routed position open -> clock-based `TIME SAFETY` flatten exactly once; the
  Engine's own TIME exit, when the feed catches up, is not sent again.
- `_loop` logs and continues after 3 consecutive `poll_once` failures and exits cleanly on `stop()`.
- `stop()` followed by `start()` retires the old thread (no two loops polling at once).

Restart safety
- `data/live_state.json` is written on every change (each poll, each routed order, start/stop/kill), atomically.
- A new process on the same trading day restores ledger, open routed position, day P&L routed, trades today,
  alert de-dup keys, EOD flag and the kill flag, and logs `Restored live state from live_state.json (...)`.
- The already-routed entry is not re-sent; its exit is routed exactly once with the right reason and P&L.
- A state file from another trading day is ignored (logged); a corrupt file never prevents a start.
- Restored kill flag keeps routing blocked (risk log line); `start({"clear_kill": true})` re-arms.

Kill switch, limits, news
- Kill switch flattens the open paper position (`exit KILL SWITCH`), stops the bot, blocks every later route.
- Over 60 days with defaults: never more than `max_trades_day=2` per day, never an entry after a win
  (`stop_after_win`). Stress runs show the daily-loss stop (13 days) and `max_trades_day=1` (10 skips) biting.
- A high-impact event injected at the signal time blocks the 10-15 13:55 entry in the Engine and the bot routes nothing.

Timing
- `poll_once` compute time on this machine: mean 331 ms, max 387 ms with `window_days=20` (642 ms with the full
  history). Nothing to optimise; the wall time of a real poll is dominated by network (Yahoo, Forex Factory, VIX).

## What was fixed / added (engine/live.py only; adapters and ADAPTERS untouched)

1. Health: `snapshot()["health"]` = data_source, data_age_s (now - last bar open - bar length), stale
   (age > 2 bars + 60 s), stale_polls, fallback, last_error(+t), last_ok_poll, consecutive_errors, poll_ms,
   entries_blocked, desync, revisions, dropped{forming,duplicate,misaligned,malformed}, market_open, ok.
2. Data path hardening (`clean_bars`): drop NaN/malformed/off-grid rows, de-dup keep-last, drop the forming bar;
   stored history gets the same junk-bar filter as `engine.data.load()` (it did not before). A failing fresh fetch
   no longer kills the poll (falls back to stored history). Bar revisions between polls are detected and logged.
3. Pluggable `data_source` (yahoo | tradovate) with lazy import and Yahoo fallback; `window_days` config key
   (default 20 = previous hard-coded value); `stale_polls_block` (default 3).
4. Alerts can no longer break routing (`_alert` wrapper); the EOD summary is logged too, and is not sent when the
   bot was started after the close.
5. Persistence + restore (`data/live_state.json`), kill flag persisted for the day, `clear_kill` to re-arm.
6. Routing safety: desync detection (routed entry no longer in the model -> `health.desync` + risk log), late
   entries are not chased, stale-feed entry block, exits for never-routed entries are not sent on paper (sent with
   a warning on real adapters), clock-based safety flatten after flat time, every ledger row carries `entry_t`.
7. Thread safety: generation counter so `stop()`/`start()` cannot leave two poll loops running; `start(spawn=False)`
   for harness use; single clock (`bot.clock`) so every time comparison is testable.
8. `news.guard()` now receives the bot's `now` (identical in production, where `bot.clock` is `time.time`; it made
   the guard transitions replayable).

No trading logic or DEFAULTS in `engine/model.py` were changed. `engine/data.py` and `data/fetch.py` needed no fix.

## Engine observations (documented, not changed - engine/model.py is out of scope)

- `engine/data.py:resample()` aligns 4h buckets with a fixed 22:00 UTC offset (18:00 EDT). In winter (EST) the
  18:00 ET session start is 23:00 UTC, so 4H FVG buckets shift by an hour from November to March. Affects the MTF
  4H layer only (`w_mtf` default 0, `mtf_gate` off), so decisions should be unaffected with defaults; fix it when
  the MTF weights are turned on (`engine/data.py:89-91`).
- `Engine.__init__` calls `gamma.prev_day_map()` -> `refresh_history()` which downloads SqueezeMetrics with a
  30 s timeout when `data/GEX_1d.csv` is older than 12 h. In live that is a one-off stall of up to 30 s inside a
  poll (cached afterwards by file mtime). Harmless but visible as a slow first poll.
- Account state is inferred from bars: `balance`, `day_pnl`, `day_trades`, `mll` in `state` are the Engine's own
  simulation over the window (start_balance + simulated P&L), not the broker's. Risk sizing with `dd_aware` only
  caps when simulated drawdown exceeds the cushion, so it will not track a real drawdown that happened outside the
  20-day window or that differs from the simulation (slippage, partial fills).
- The Engine's news block uses `data/news/events.csv` + `data/news/ff_archive.csv` (archived from the live Forex
  Factory feed by `news.ff_calendar()`), not the live `news.guard()`, which is informational only in the loop. If
  the machine is offline at poll time the archive is still used, but events never archived are unknown to the
  Engine.

## Remaining risks, ranked

1. Yahoo NQ=F is ~10 min delayed and occasionally revises bars. With a delayed feed the Engine acts on bars that
   closed up to 15 min earlier: fills in paper look fine, fills at a broker will not match. Do not execute real
   orders from Yahoo; use `data_source="tradovate"` once `engine/tradovate.py` delivers bars, and watch
   `health.revisions` / `health.desync` on the first days.
2. State-is-a-function-of-bars: if a closed bar is revised, the model can "forget" a trade it already sent. The
   bot now flags DESYNC and never re-sends, but it will not flatten on its own (it cannot know the broker side).
   Operator action on DESYNC: check the broker position by hand.
3. Broker-side truth is never read back. Rejections, partial fills, bracket cancellations, or a manual trade on
   the account are invisible to the bot. For the eval: keep the broker platform open next to the dashboard.
4. Sizing/limits are simulated (see Engine observations). The internal $600 daily stop is on simulated P&L; a
   bad fill day could breach the prop DLL earlier than the bot thinks. Keep a hard stop at the broker too.
5. Single process, single thread: a poll that hangs inside `yfinance` or `urllib` (no global timeout) delays the
   next decision; `poll_sec=60` means up to ~2 minutes between decisions on a bad network day. The safety flatten
   mitigates the close; it does not mitigate a stop that the broker bracket must already hold.
6. Session boundary of the state file is the ET trading day (18:00 roll). A restart between 17:00 and 18:00 ET
   restores the day; after 18:00 it starts clean by design.
7. `/api/live/poll` (manual "Poll now" with no bot running) builds a minimal cfg and does not restore state; use
   Start for anything that should persist.

## Pre-open checklist (operator, ~09:00 ET)

1. `python -X utf8 -m tests.test_live_dryrun --quick` -> exit code 0.
2. `python data\fetch.py NQ ES` (or confirm `data/NQ_5m.csv` ends at yesterday's 17:00 ET); check `ES_5m` too.
3. Check `data/news/ff_thisweek.json` is from this week and today's high-impact USD events are in
   `data/news/ff_archive.csv` (CPI/PPI/FOMC/NFP) - the Engine's blackout uses that file.
4. Delete or inspect `data/live_state.json` if yesterday ended with a kill or a known-bad state (it is ignored
   automatically on a new trading day; only today's file is restored).
5. Start the bot in paper first; on the dashboard confirm `health.ok`, `data_age_s` < 400 and `stale=false`
   after the first poll, `market_open=true`, `fallback=false` if `data_source="tradovate"`.
6. Confirm `cfg.params` are the intended ones (flat_mod 955, daily_max_loss 600, max_trades_day 2) and
   `window_days` 20; confirm the broker bracket (stop + target) is attached to every entry on the broker side.
7. Alerts: send a test alert from Settings; confirm the phone receives it.
8. Know the two buttons: KILL SWITCH flattens paper/broker-side via the adapter and blocks routing for the day;
   restart after a kill needs `clear_kill=true` (or delete `data/live_state.json`).
9. Watch the log for `DATA STALE`, `DESYNC`, `SAFETY FLATTEN`, `NOT routed` - each one means "look at the broker".
10. 15:55 ET: confirm flat on the broker platform, not only on the dashboard. 16:05 ET: EOD alert arrives once.
