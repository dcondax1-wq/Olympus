# ZEUS features: what serious trading bots have, and what ZEUS has (2026-11-18, night-feat)

Owner: "think what trading bots have, do all the work". This is the checklist that serious automated futures systems and
prop-trading tools work from (exchange and regulator controls: kill switch, messaging throttle, order size maximums,
heartbeat, cancel-on-disconnect; vendor checklists: reconciliation, duplicate-order guard, synchronous pre-trade gate),
checked against the code. The older and longer comparison is `research/writeups/competitor-features.md` (42 features, 2026-10-21).

Sources looked at: CFTC Electronic Trading Risk Principles (2020, Reg 38.255: throttles, order size maximums, heartbeats,
https://www.cftc.gov/LawRegulation/FederalRegister/finalrules/2020-27622.html), FIA overview of CME / ICE risk controls
(kill switch, cancel-on-disconnect, message throttling,
https://www.fia.org/sites/default/files/2025-01/Exchange%20Risk%20Controls%20%E2%80%93%20Overview%20of%20CME%20and%20ICE%20risk%20controls.pdf),
NexusFi automated risk controls / emergency protocols (https://nexusfi.com/a/automation/automated-risk-controls),
TradersPost bot-failure guide (https://blog.traderspost.io/article/automated-trading-bot-failures-prevent-them).

## The audit

| # | Feature | ZEUS | Where |
|---|---|---|---|
| 1 | Remote pause / flatten / kill from the phone | **HAVE (built tonight)**. Before: PARTIAL, the phone remote read a GitHub branch and GitHub is gone; the Tailscale link was read-only | `engine/phone_safety.py` (/safety/), `engine/remote_ctl.py` |
| 2 | Broker-connection watchdog, auto-reconnect | HAVE: NinjaTrader reconnects itself; ZEUS reads its connection files, entries wait while DISCONNECTED and resume on reconnect | `engine/ninjatrader.py` connections, `engine/nt_log.py`, `engine/autopilot.py` |
| 3 | Position reconciliation (bot vs broker) + orphan-order sweep | HAVE: reconcile every poll (manual trade / close / size alarms), orphan orders cancelled when the state file is lost, leftover legs cancelled after a flatten | `engine/guards.py` reconcile_tick, `engine/ninjatrader.py` |
| 4 | Per-trade risk limit + max daily loss lock | HAVE: size from the stop and the room, order sanity, max micros, daily-loss guard, max 8 entries a day per account | `engine/risk_policy.py`, `engine/guards.py`, `engine/ninjatrader.py` max_entries_day |
| 5 | Slippage and fill-quality tracking | HAVE: every trade vs the backtest on the same bars, $ lost to execution, latency | `engine/fill_audit.py`, `tools/fill_check.py` |
| 6 | Trade journal with screenshots | HAVE: a picture per trade, Trading page, Odeon replay. PARTIAL: no owner tags | `engine/trade_chart.py`, `tools/web_public/trading/` |
| 7 | Session / news calendar | HAVE: CME holidays and early closes, official BLS / Fed calendar, news guard | `engine/cme_calendar.py`, `engine/news_official.py` |
| 8 | Drawdown alerts | HAVE: "room getting low" pushes (now OFF by default, owner's choice), critical "drawdown left" alert repeats until Got it | `engine/notify.py`, `engine/alerts_plus.py` |
| 9 | Heartbeat watchdog | HAVE: in-process watchdog, 5-min PC report, PC-silent push (the cloud check is built, not live until `main` is updated) | `engine/watchdog.py`, `tools/pc_report.py`, `tools/pc_silent_check.py` |
| 10 | Backup PC / failover | MISSING on purpose: a hot spare could double the orders. `tools/bat/MOVE_BOT.bat` moves the bot by hand; the stop and target live at the broker, so a dead PC leaves the trade protected | `scripts/move_bot.ps1` |
| 11 | Latency monitoring | HAVE: poll time per stage, 15-min trend, signal-to-route latency per trade | `engine/poll_timing.py`, `engine/pc_health.py`, `engine/fill_audit.py` |
| 12 | Data-gap detection | HAVE: bar gap alarms, FEED STALE blocks new entries, frozen feed in a trade alarm | `engine/live.py`, `engine/pcbars.py`, `engine/ai_watch.py` |
| 13 | Rollover handling | HAVE: the order contract switches by date, roll warning, tools/bat/ROLL.bat for the chart | `engine/roll_watch.py`, `engine/ninjatrader.py` nt_instrument |
| 14 | Equity-curve circuit breaker | **HAVE (advice, built tonight night-risk)**: live vs backtest twin per strategy, last 10 trades; SIZE DOWN / PAUSE advice to the Board + phone, never acts. The old equity filter (acts on size) stays OFF: a strategy change | `engine/circuit_breaker.py`, `engine/equity_filter.py`, `engine/guards.py` |
| 15 | Per-strategy attribution | HAVE per account (each live account runs one strategy). PARTIAL for a Rapid with two lanes (not bought) | `tools/trading_export.py`, `engine/fleet.py` |
| 16 | Paper / live parity checks | HAVE: live loop == backtest 120/120, live vs twin on the Trading page | `tests/test_lit_live.py`, `engine/fill_audit.py` |
| 17 | Audit log | **HAVE (one timeline built tonight)**. Before: PARTIAL, the facts sat in 5 files | `engine/audit_trail.py`; OIF log, `engine/handsoff.py`, `engine/board_events.py`, `engine/rulelog.py` |
| 18 | Version pinning / rollback | HAVE: fast-forward only, self-tests, roll back on failure, bad version remembered, tools/bat/UNDO_UPDATE.bat, rules fingerprint PC vs cloud | `engine/autoupdate.py`, `engine/alerts_plus.py` |
| 19 | Secrets handling | HAVE: keys only in PC env vars / files, repo secret scan, no phrase in the order log, account ids kept out of public pages | `tests/test_repo_secrets.py`, `docs/PRIVACY.md` |
| 20 | Duplicate-order guard | HAVE: one entry per setup, re-route after restart refused | `engine/guards.py` dup_problem |
| 21 | Unprotected-position alarm | HAVE: a fill without its stop is closed at once + critical alert | `engine/ninjatrader.py` _tick_watch, `engine/alerts_plus.py` |
| 22 | Clock sync check | HAVE | `engine/ops_checks.py` check_clock, `engine/guards.py` clock_problem |
| 23 | Alerts that repeat until acknowledged | HAVE | `engine/alerts_plus.py` |
| 24 | Notification levels | HAVE; **defaults set to "important only" tonight** (owner) | `engine/notify.py`, `notify_settings.json` |
| 25 | Messaging throttle (runaway orders) | **HAVE (built tonight night-risk)**: every order file counted per account (burst / day / stop-change loop) = alarm ON; entry block OFF until switched on; entries still capped 8 a day | `engine/msg_throttle.py`, `engine/ninjatrader.py` |
| 26 | Cancel-on-disconnect | N/A: an exchange / broker feature NinjaTrader's ATI does not offer; the OCO bracket at the broker covers a dead PC | - |
| 27 | Prop-rule lifecycle (passed / failed / locked stand down) | HAVE | `engine/lifecycle.py` |
| 28 | Trader-present record (MFFU) | HAVE | `engine/presence.py` |

## Built tonight (the 3 that most protect the money; no strategy change, nothing arms)

### 1. Phone PAUSE / FLATTEN / KILL (owner said YES), OFF until he turns it on
- Page: `https://<this-pc>.<tailnet>.ts.net/safety/` (the tools/bat/LIVE_LINK.bat address + `/safety/`). Add it to the Home Screen.
- Buttons: **PAUSE** new trades until the next 4 PM ET (in the day: the rest of the session; at night: the whole next one), **RESUME**, **FLATTEN all now** (second tap), **KILL** = flatten all + stop (second tap).
  Each runs the same code as the old GitHub remote (`RemoteControl.run_cmd`): phone notice, hands-off record, heartbeat.
- It can never start, arm, update or change settings: there is no such button or code path. Start stays on the PC with the phrase.
- Who can press: only the PC itself or his own signed-in Tailscale devices (`live_site.private_why`); the home WiFi, Funnel
  (internet) and other tunnels are refused; ntfy is never a way in. A page on another site cannot press (custom header + JSON
  + Origin check), and 8 presses per 10 minutes at most. Every press is logged in `data/phone_safety_log.jsonl`.
- Turn on once at the PC: `python -X utf8 -m engine.phone_safety --on` (off: `--off`; `LE_PHONE_SAFETY=0` forces off).
- Tests: `python -X utf8 -m tests.test_phone_safety` (privacy + pc areas).

### 2. "Important only" notifications (owner)
- ON: trade results, PASSED / FAILED / LOCKED / LOST / target reached / payout READY (new type `account_status`), the daily
  summary, PC silent. OFF: trade opened, 25-75 % milestones, room low, problems (bot down / FEED STALE / NinjaTrader closed), other.
- The PC ops task's critical alerts (unprotected position, KILL fired, drawdown left) are outside these settings and still ring.
- Tests: `tests.test_notify`, `tests.test_lifecycle`.

### 3. One audit trail: who did what
- `python -X utf8 -m engine.audit_trail` (or the "What happened" list on the phone page): phone presses, PC / phone
  stop / kill / flatten / pause, manual trades seen by reconcile, bot started / stopped, orders sent (no account name),
  PASSED / LOCKED, code updates. Read-only, ON.

## Built night-risk (2026-11-18): the 2 partials that protect the MFFU accounts (#14, #25)
Left PARTIAL on purpose: #6 owner tags and #15 Rapid two-lane attribution (no money at risk). Nothing here changes a strategy decision.

### ZEUS circuit breaker (#14), ADVICE, ON
- Per strategy (Zlarior from `engine/fill_audit`'s twin rows, ATLAS from account B's ledger vs `tools/trade_watch`'s twin): last 10
  closed live trades, gap = live R - twin R (each trade clipped to +-2R so one feed freak never trips it alone), $ shown first.
- gap <= -2R WATCH (Board only), <= -3R **SIZE DOWN** ("half size until explained"), <= -5R **PAUSE** ("phone /safety/ PAUSE + check").
  Push once per step up (type account_status, key `breaker:`), Board `risk_alert`; back above -1.5R = "back to normal" line.
- A losing streak the twin also had = OK (normal variance). Missed trades are counted, not added (they lose no money).
- It never sizes or pauses by itself. Check: `python -X utf8 -m engine.circuit_breaker`. Off: `LE_BREAKER=0`.

### Runaway-order throttle (#25): alarm ON, block OFF
- Every order file each NinjaTrader adapter writes is counted: > 20 in 60 s, > 150 a CME day, or > 12 stop/target changes on one
  order = trip: critical alert + Board `risk_alert` + one push (type problems, key `risk:throttle:`). Account shown by last 4.
- Block (acts on orders, so OFF): `python -X utf8 -m engine.msg_throttle --block-on` -> a tripped account takes no NEW entries / adds
  until the next CME day or `--reset`. Stops, cancels, closes, flatten and KILL are never throttled.
- Tests: `python -X utf8 -m tests.test_risk_monitors` (nq + pc areas), `python -m engine.ninjatrader --selftest`.

## For the lead
- Link `/safety/` from the Gate or the PC app (apps tables are the lead's).
- Ships with the next PC update (when flat); then the owner types the `--on` line once.
