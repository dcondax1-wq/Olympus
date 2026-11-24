# Failure map of the live chain (day-zeroerr, 2026-11-24)

Owner: "no more errors". Facts that started it: 5 of the last 7 backtest trades were missed by PC uptime
(research/writeups/livegap-2026-11-24.md); the auto-update has been HELD BACK since Nov 24 00:45 ET by a local edit; the
Rapid EOD 25K may have missed ATLAS's +6.6R Nov 20 because it was not armed; a false "ATLAS 25K is on Sim" readiness
warning (fixed on day-brain-feed, not here).

Every step of the chain from Windows to the P&L report, how it fails, what sees it today, how fast the phone hears, and what
fixes it by itself. **NEW** = built on this branch. Tests: `python -X utf8 -m tests.test_chaos_live` (39 checks, the letter in
the last column), plus the suites already named.

## Summary
| | count |
|---|---|
| Failure modes mapped | 34 |
| Already detected + alerted before today | 23 |
| Gaps found | 11 |
| Gaps closed on this branch | 7 |
| Gaps left (owner / lead / another branch) | 4 |

## The chain
| # | Step | Failure | Detector (file:line) | Phone in | Auto-fix | Test |
|---|---|---|---|---|---|---|
| 1 | Windows | PC off / asleep / Windows Update reboot | cloud "PC stopped reporting" (engine/notify pc_silent, alert_bus.py:261) from the 15-min report's silence; engine/keepawake.py:18 keeps it awake while the bot runs | 20-30 min **only when the cloud monitor runs** (see gap G8) | run_bot.ps1 + START task restart the server after a reboot; a real eval resumes only with auto-resume (engine/autoresume.py) | test_pc_silent |
| 2 | Windows | Server crashed | run_bot.ps1 supervisor restarts in 5-60 s; self_heal fix_server (engine/self_heal.py:721) | 3-3.5 min "Bot stopped" (fast_alarm.py evaluate, bot_stopped) | restart | test_nq_live_reliability |
| 3 | Clock | PC clock off > 5 s | guards.clock_problem (engine/guards.py:346), probe every 15 min | at once (kind clock = critical) | w32tm resync (guards.clock_heal, self_heal clock) | chaos f |
| 4 | server.py start | New code cannot import | autoupdate.import_check (engine/autoupdate.py:941) | at once ("Update held back") | rollback | test_autoupdate_paths |
| 5 | server.py start | New code crash-loops | autoupdate.crash_check (engine/autoupdate.py:959) | at once ("Update rolled back") | rollback to the last good sha | test_autoupdate_paths |
| 6 | server.py start | Restart that does not resume the bot | fast_alarm bot_stopped (engine/fast_alarm.py:290) | 3 min | none (the owner types the phrase) | test_nq_live_reliability |
| 7 | NinjaTrader | NinjaTrader closed | self_heal fix_nt (engine/self_heal.py:744) opens it | report | opens NinjaTrader (never logs in / arms) | test_self_heal_pc |
| 8 | NinjaTrader | Connection DISCONNECTED (MFFU / Tradovate) | adapter refuses entries (engine/ninjatrader.py:1456 _all_disconnected); fast_alarm feed_stale | 2-2.5 min | NinjaTrader reconnects itself | chaos a |
| 9 | Accounts | Account Name changed (eval -> funded rename, the missing "R") | account_rename.fix at every start (engine/account_rename.py:93); arm_report funded candidates | at START | rename with the owner's YES | test_arm_report |
| 10 | Accounts | **An account not armed / not started at 01:55** (Rapid Nov 20; day-ledgerfix: the rows are kept per day in logs/arm_daily.json and ride the PC feed as "arm") | **NEW** engine/live_guard.py arm_rows + arm_due: 01:55 and 09:00 ET, every configured account (LIT, the extra accounts, ATLAS, both Rapids, a configured account missing from the bot) | **one line at 01:55 and 09:00** (loud when any is NOT READY, quiet when all OK) | none (arming is the owner's) | chaos a, h |
| 11 | Accounts | **Routed Name not listed by NinjaTrader** | **NEW** same check: the exact Name against le_feed\\accounts.csv (ninjatrader.live_accounts) | 01:55 / 09:00 | none | chaos a |
| 12 | Bars | 1m feed 2+ bars behind / LE_BarFeed removed | fast_alarm feed_stale (engine/fast_alarm.py:290) + the bot blocks entries | 2-2.5 min | none (re-add LE_BarFeed) | chaos b |
| 13 | Bars | Bar late in the file | live._await_nt_bar re-polls on the file change; LIT not chased after 90 s (engine/live.py:174) | MISSED TRADE at once | by design | test_lit_live |
| 14 | Bars | Contract roll (Dec 2026 12-26 -> 03-27) | engine/roll_watch.py (launch_check roll item) | report / START | none | test_roll_now |
| 15 | Poll loop | Poll thread dead / stuck | fast_alarm bot_down | 90 s + 30 s | none | chaos b |
| 16 | Signal | LIT entry held on the MAIN account (feed stale, late, sizer, refused) | fill_audit.session_alerts (engine/fill_audit.py:953) | 1 min | none | chaos c |
| 17 | Signal | LIT entry during a gap / before a restart | fill_audit.unrouted_entries (engine/fill_audit.py:912) | 1 min | not chased (by design) | test_nq_live_reliability |
| 18 | Signal | **LIT entry not on an EXTRA account** (25K #2, the Rapid's LIT lane): an account with a start problem returns before it looks (engine/multi_account.py:950), so nothing was ever logged | **NEW** live_guard.missed (twin = the main loop's model, bot.seen) | **2-3 min**, once per account + entry, with the reason | none | chaos c, h |
| 19 | Signal | **ATLAS trade not on ATLAS's account / the Rapid's ATLAS** | **NEW** live_guard.missed (twin = bot.second, the paper ATLAS run); its own rule holds (account B "held") and one-position overlaps are not misses; a live-probe vs closed-bar difference is a quiet "Not taken (check)" | 2-3 min | none | chaos h |
| 20 | Signal | **Account configured but not in the running bot** (Rapid armed in data/rapid.json, lane / ATLAS not built; account B armed but not started) | **NEW** live_guard.missing_configured (launch_check.rapid_fact, account_b.raw_cfg) | 2-3 min per signal + the 01:55 line | none | chaos h |
| 21 | Order | Entry never confirmed by NinjaTrader | adapter pending_timeout -> CANCEL (engine/ninjatrader.py:2412) | MISSED (main) / **NEW** guard (extra) | cancel; a late fill is still protected | test_nt_outgoing |
| 22 | Order | Entry REJECTED | adapter retires the leg; ledger ok False | at once (fill audit / **NEW** guard for extra accounts) | nothing opened | chaos c |
| 23 | Fill | Fill much worse than the backtest | fill_audit slippage alert (4+ ticks) | report | none | test_fill_audit |
| 24 | Stop | **Bracket not delivered after the fill** (status "unprotected") | adapter re-sends every poll (engine/ninjatrader.py:1777 _protect); its warning is kind "risk", **off the phone since 2026-11-18** (engine/push.pc_app_ok) | was: Telegram only if ALERTS_SETUP; **NEW** fast_alarm.stop_missing: 60 s + 30 s, every account, never capped, dual channel | re-place through the existing order path (unchanged) | chaos d |
| 25 | Stop | **Stop CANCELLED / REJECTED at the broker** (by hand, a broker rule) | adapter flattens (engine/ninjatrader.py:2412 "bracket leg lost") | **NEW** stop_missing alarm while it is open | flatten (unchanged) | chaos d |
| 26 | Stop | Stop never reported by NinjaTrader | adapter._bracket_never_reported flattens after 30 s (engine/ninjatrader.py:2537) | **NEW** stop_missing | flatten (unchanged) | test_nt_outgoing |
| 27 | Stop | Bot stopped between the fill and the bracket | fast_alarm.no_stop (engine/fast_alarm.py:107) | 60 s + 30 s | the restarted adapter places it at its first tick | chaos e |
| 28 | Exit | Half-day halt with a position open (MFFU does not close it) | fast_alarm.halt_open | halt - 10 min | the running bot flattens at halt - 5 | test_redteam2_live |
| 29 | Exit | Position vs ledger mismatch (main account) | guards.reconcile_tick (engine/guards.py:699), kind unprotected = critical | at once | reconcile flatten (3 tries) | test_guards |
| 30 | P&L | Balance move with no trade the cloud can see (Zlarior -$220) | none | none | none | **gap G9** |
| 30b | P&L | **A never-routed model entry carried to a later session -> a flatten "in case a broker position exists" + a $0 row** (Nov 16 06:20 -> Nov 20 10:44 ET) | day-ledgerfix: engine/live.unrouted_exit_skip (LiveBot + engine/multi_account): no order when the entry's session ended or NinjaTrader shows the account flat | n/a (prevented) | today's entry with an unknown broker state keeps the safety flatten | test_ledgerfix 1 |
| 30c | P&L | **A trade copied into an account that started after it** (Zlarior 25K #2, Nov 16 -$129.40) | day-ledgerfix: engine/multi_account: no row before the account's eval_start; restore() removes such a close once | n/a | one-time repair at load | test_ledgerfix 2 |
| 31 | Report | Alert channel down | alert_bus "channel X down" once an hour; Telegram -> Discord -> ntfy -> Web Push | at once | next channel | test_alert_bus |
| 32 | Auto-update | Git lock left by a killed git | self_heal fix_git_locks (engine/self_heal.py:378) | report | deleted when 10+ min old | test_self_heal_pc |
| 33 | Auto-update | **Update held back for hours** (a local edit it may not park: live_model*.json, second_model.json, data/; local commits; not on branch pc; fetch / status failing; auto-update off). Before: "update skipped" went to the daily digest only (engine/autoupdate.py alert_for) | **NEW** live_guard.update_stuck: 3 h after the first stuck result, ONE push a day with the reason and the fix; "not flat" / trading-hours waits are not stuck; an installed update clears it. day-zerotouch2's auto-park (origin, not on pc yet) parks the hand edits it may park; this is the net under it | 3 h | parkable files: day-zerotouch2; the rest stay the owner's call | chaos g |
| 34 | Restart mid-trade | Update / restart while a trade is open | autoupdate flat checks cover LIT, ATLAS, C, Rapid (OPEN_LEG engine/autoupdate.py:79); remote restart refused 01:50-16:00 | n/a (prevented) | waits | test_nq_live_reliability |

## Gaps
| Gap | What | Status |
|---|---|---|
| G1 | NinjaTrader "UNPROTECTED / stop lost" warnings never reached the phone (kind "risk") | **closed**: fast_alarm.stop_missing (row 24-26) |
| G2 | Missed trades on extra accounts left no line at all | **closed**: live_guard.missed (row 18) |
| G3 | ATLAS accounts had no missed-trade check | **closed**: live_guard.missed (row 19) |
| G4 | A configured account missing from the running bot was silent (the Rapid, Nov 20) | **closed**: live_guard.missing_configured (row 20) |
| G5 | No armed check before the window | **closed**: 01:55 + 09:00 ET line (row 10) |
| G6 | Routed Name not checked against NinjaTrader before the window | **closed**: same line (row 11) |
| G7 | A stuck update was digest-only | **closed**: 3 h escalation (row 33) |
| G8 | Olympus `main` is README-only, so GitHub runs no workflow: the cloud "PC silent" alarm (row 1) does not run here (day-notify) | **left**: the lead wires the workflow (research/handoff/2026-11-23/day-notify/LEAD_WIRES.md). Until then a PC that is OFF is told by nobody |
| G9 | Broker cash per account is not saved daily (the unexplained -$220) | **left**: livegap proposal (save NinjaTrader cash at 17:00 ET into the day folder) |
| G10 | A position on an EXTRA account with no bot leg at all (state file lost) | **left**: guards.reconcile_tick covers the main account only; the stop_missing alarm needs a leg. Small follow-up |
| G11 | Files that are never parked (live_model*.json, second_model.json, data/) still block the update | **left by design** (strategy / account files are the owner's); now loud after 3 h instead of silent |

## How the new checks run
- `engine/live_guard.py` (read-only), driven by `engine/watchdog.Watchdog.check` every 30 s (the real server only; a test's fake
  clock never sends). Missed-trade compare every 60 s, a signal counts as missed when 2 min old. Off: `LE_LIVE_GUARD=0`.
- `engine/fast_alarm.stop_missing`: inside the fast alarm (same rate limits; never capped, like no_stop; `LE_FAST_ALARM=0` off).
- Delivery: `engine/notify.instant_problem` (Telegram / Discord first after ALERTS_SETUP.bat, else the private ntfy + the app).
- Nothing here places, changes or cancels an order. Re-placing a stop is the adapter's existing poll (`_tick_leg` -> `_protect`).
