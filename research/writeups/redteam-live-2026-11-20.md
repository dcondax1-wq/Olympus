---
title: Red team of tonight's live code (2026-11-20) - what could stop the bot, slow an order, send a wrong order or ring at night
family: other
date: 2026-11-20
status: finding - 10 real bugs fixed with failing-first tests on night-redteam; strategy rules, sizing and live_model*.json untouched
summary: Independent second pair of eyes on git log 3848045b..cab5247c (combo50k hooks, fast alarm, fast entry, fill audit, multi_account join-time fix, autoupdate flat check, notify / trade alerts, phone_link, remote_ctl control_source, self_heal, account_box). Found and fixed - a phone 'Start trading' that re-armed after the owner's STOP, an old remote stop that could stop Friday's bot, a false 'not polling' push after every START / Re-arm, an alarm storm with no limit that could also eat ntfy's daily room the trade alerts need; the hourly self-heal resetting / moving files in the trading hours and with a trade open; a CLOSEPOSITION that could close ATLAS's trade on the shared Rapid account; designed rule holds ringing as MISSED TRADE at 03:00 ET; plus night-selfheal's pre-merge proposal landed. Nothing found that stops the bot, blocks a poll or slows an order.
runs: tests.test_lit_live (full, heavy.sh), tests.test_nq_live_reliability, tests.test_self_heal_pc, tests.test_notify, tests.test_trade_alerts, tests.test_fill_audit, tests.test_multi_account, tests.test_autoupdate_source, tests.test_autorun, tests.test_update_from_zip and the rest listed at the end
---

# Red team of tonight's live code (2026-11-20)

## CRITICAL (fixed, each with a failing-first test; branch night-redteam)

| # | Severity | What could go wrong on the owner's PC | Fix commit |
|---|---|---|---|
| C1 | high | **Alarm storm.** engine/fast_alarm pushed one alarm + one "back to normal" every time a condition flapped (a NinjaTrader feed that hiccups every minute = 2 pushes a minute, no limit), and problem pushes were not counted in ntfy's daily budget (the status posts already use ~220 of ~250). A bad morning could ring the phone dozens of times AND leave no ntfy room for the entry / exit alerts. Now: a repeat of the same condition within 30 min stays silent unless it lasts 5 min (a lasting problem is never silent, also right after a "back to normal"), at most 6 alarms a day, every problem push counted in the day's budget (tools/pc_report keeps its 12-post reserve for trade alerts). One lock now guards the read-modify-write of logs/notify/instant_sent.json (push threads, fill audit and watchdog wrote it without one). | fd0f4cd3, ac7146a1 |
| C2 | high | **Self-heal acting in the trading hours / with a trade open.** The hourly run reset a bot-made tracked file at Tue 10:00 ET (test b2) and moved / removed untracked files the update brings at any hour, with no flat check at all (pip was the only gated remedy, and its flat check saw LIT only). A file the running bot imports, removed at 01:40 when the update then did not land before the 01:50 blackout, stays missing for a whole trading day. Now: the update / pid / clock remedies never run while a trade may be open on ANY account (LIT's files + every data/ninjatrader_state*.json bracket: ATLAS, the extra accounts, the Rapid lanes), the update remedy never 01:50-16:00 ET on a weekday, and the hourly run only names untracked files in the way. | 9529550b |
| C3 | high | **A wrong order on the Rapid EOD.** Its LIT lane (engine/multi_account) and ATLAS's lane (engine/rapid.RapidAtlas) share ONE NinjaTrader account with two adapters. The lane's "in case" flatten for an exit of an entry it never routed (the model entered during a bot / feed gap) is a CLOSEPOSITION of the whole account: with ATLAS holding a trade it closes ATLAS's trade at market. The night-nqlive join-time fix covered only trades that ended before an account joined. Now: no flatten while the other strategy on that account (shared(): the Rapid's ATLAS lane, ATLAS's funded 25K lane) holds a position or an open bracket; unknown = no flatten. | 0448ea4f |
| C4 | medium | **False alarm at night.** Every held-back entry became a loud "MISSED TRADE" ntfy push that rings in quiet hours, also when the bot's own rule held it back on purpose (soft daily loss, weekly stop / size 0, the equity filter, the 50K's one-position rule). After a weekly stop every 03:00 ET LIT signal would wake the owner. Now a rule hold is a quiet "Held back by a rule" notice (no sound 23:00-07:00, normal priority by day); malfunctions (feed stale, seen late, refused, never routed, a restart, STARTUP DISARMED, unknown) stay loud. | c9502fd9 |
| C5 | high | **A phone 'Start trading' could override the owner's STOP.** engine/account_box: "not flat" = it waits and re-arms by itself every 30 s for up to 8 h. onboard.rearm arms AT ONCE when no bot runs, so after the owner pressed STOP BOT / HOLD TO KILL (or a remote stop / kill, a guard stop, a crash) the waiting thread started live trading again within 30 s. Now the wait drops ("the bot was stopped while this waited") the moment the bot is not running; one tap starts it again. | 5807426e |
| C6 | medium | **An update / restart / Re-arm under an extra account's trade.** autoupdate.bot_flat_reason (also the Re-arm's STOP check, start_api._flat_reason) looked at LIT, ATLAS, account C and the Rapid's ATLAS lane, not at the extra accounts (Zlarior 25K #2, the Rapid's LIT lane) or the fleet's followers, which can hold a LIT trade the bot's own account did not take. Now they count too. The watchdog also keeps the PC awake before the fast alarm runs, and an alarm error can never stop its loop. | 6d92cb89 |
| C7 | high | **False 'ZEUS not polling' / 'FEED STALE' after every START, Re-arm or server restart in the entry hours.** LiveBot.started_at is the trading day's FIRST start (min with the restored state) and health.last_ok_poll / last_1m_bar_t survive a STOP, so the fast alarm's 3-minute start grace never applied: a Re-arm at 13:00 after a STOP at 10:00 pushed "No good poll for 180 min" (high priority) before the run's first poll. Now the grace and the age count from when this run is first seen running; a run that never polls still alarms after 3 min. | e398e49e |
| C8 | high | **An old remote 'stop once flat' stopping Friday's bot.** Remote control was OFF on the GitHub-free PC since 2026-11-08 and comes back ON tonight (control_source = the backup repo). A pending stop left in data/remote_done.json had no expiry: at the first flat moment after the next server start it would STOP the bot (and clear its auto-resume). Now a pending stop older than 18 h is dropped and named, never run. | b7727817 |
| C9 | medium | **False 'Bot stopped' alarm on CME holidays.** tools/pc_report.entry_hours (its "Bot stopped" condition) was weekday 01:50-15:30 only: a bot stopped on Christmas Day, New Year's Day or Thanksgiving afternoon (after the 13:00 halt; next Thursday) alarmed. Now a holiday closure / early halt (engine/cme_calendar.halted) is never entry hours. The fast alarm already used engine/live.market_open. | abb2d0d0 |
| P5 | (proposal) | night-selfheal's proposal landed: engine/autoupdate.fast_forward clears untracked files the update brings right before `git merge --ff-only` (same bytes: removed; other bytes: snapshot + copy kept), puts them back when the merge still fails or the update rolls back, and keeps git's FULL merge error (it was cut to its last 200 characters: the file names git lists first were lost, and self_heal reads them from that reason). | 9529550b |

Not critical, checked and fine: phone_link (Windows only, daemon thread, every Tailscale call has a 20 s timeout, never 443 / Funnel, its
failure cannot reach the server start); remote_ctl control_source (the expired no-op on olympus/control is "blank" = silent; an
invalid id is never re-notified; update / restart stay gated to flat + outside 01:50-16:00); account_box arming (the typed phrase
only, private link + same-origin + rate limit); fast_entry OFF = exactly today's wait (enabled() is False, the old next_wake line
runs); the alerts are fire-and-forget (pc_notify only builds the payload and starts a thread; ntfy / app sends run in it).

## Smaller fixes (low, each with a test)

| What | Fix |
|---|---|
| Self-heal deleted `logs/supervisor.pid` when the pid ran but its name could not be read (psutil access denied read as "another program") | e2d03d91 |
| Self-heal deleted old git locks when the running programs could not be read at all (it assumed "no git running": a long git could be at work) | 0ea883ad |
| A self-heal "needs you" push rang at night (the hourly run also runs 16:00-01:50 ET, priority high): now silent in the quiet hours | b61e1756 |

## Checked, not changed (and why)

- **combo50k OFF is today's bot.** No switch file = `combo50k.build` returns None, `_combo_sync` returns at once, `_combo_live` is False
  (no combo-tagged prov), `_combo_lit_skip` returns None for every non-combo position, `_combo_tags` adds nothing, guards / circuit breaker /
  fleet.lead_snapshot only act on combo rows (none exist). The full live = backtest replay is unchanged (tests.test_lit_live below). ON: one
  position per account is enforced twice (`_combo_block`: Zlarior's routed position, any working leg, an entry in progress; the NinjaTrader
  adapter refuses a second bracket while one is open); no hedge across accounts (`_combo_opposite`: ATLAS's 25K, the extra accounts, the Rapid's
  ATLAS lane, the fleet; ATLAS's 25K sees the combo position through the 50K's ledger); ATLAS's combo trades never reach followers or extra
  accounts (lead_snapshot drops combo rows; extra accounts mirror only LIT's own model); size = account_b's builder50k sizing on the 50K's own
  room (ledger + the broker's real room) x 0.5 in the eval, capped at min(guards.max_micros, 40).
- **fast_entry OFF**: `enabled()` is False (no cfg key, no env, no data/fast_entry.json), the old `next_wake` line runs: same wait.
- **Alerts never slow an order**: the adapter builds the payload and `push.pc_notify` only checks the key and starts a thread; the app send,
  ntfy post and exit context (the live.json read) all run in that thread. Duplicates: one key per trade and account (`fill:` / `out:` +
  `:acctb` / `:acctr` / `:<id>`), claimed once (push.Notifier.claim), the 15-minute report skips what the phone already got.
- **phone_link**: Windows only, a daemon thread, every Tailscale call 20 s timeout with stdin closed, never 443 / Funnel, never a port
  another app serves; its failure is one log line.
- **remote_ctl control_source**: the expired no-op `noop-0` on olympus/control is "blank" (silent); update / restart stay gated to flat +
  outside 01:50-16:00; kill / stop / flatten only reduce risk; start is Sim only.
- **account_box arming**: only the exact typed phrase, only from the PC itself or a device signed in to the owner's tailnet (never the home
  WiFi, Funnel or another tunnel), same-origin + its own header + JSON + 8 presses / 10 min; the phrase is never logged.
- **account_b --min-room**: writes only `data/account_b.json` (the block next to second_model.json, every other key kept, atomic); refuses
  when ATLAS has no account; never arms.
- **multi_account join-time fix**: right; a trade that ENDED before the account joined is skipped, an unrouted exit books $0.

Not fixed (low, named for the lead):
- A brand-new account added by a Re-arm still sends its "in case" CLOSEPOSITION for a model trade that entered before it joined and ends
  after: harmless on an empty account (a flat CLOSEPOSITION does nothing), only a manual position the owner holds there would be closed.
  Changing the gap-flatten rule is a design call (LiveBot does the same on its own account).
- Self-heal's pip remedy (only when a requirements.txt package is missing, outside 01:50-16:00, flat) runs pip while the server runs: a
  dependency upgrade of a loaded package (numpy / pandas DLLs) could fail half-way on Windows. Every package is pinned and installed today.
- onboard.rearm (the PC dashboard's Re-arm, and the Add account box) arms at once when `go.bot_running()` reads False; an HTTP glitch
  that reads False twice (rearm + arm_problem) while the bot runs would skip the flat check. Pre-existing; the Add account box's wait now
  never re-arms a bot that is not running (C5).
- The phone remote's control fetch (every 60 s) and the hourly update's fetch can overlap in the same checkout: that hour's update then
  skips ("git fetch failed") and the next hour retries.
