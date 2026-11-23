# Fault injection: the live loop (night-faults 2026-11-23)

Branch `night-faults` (from origin/land-fixes). ERROR HANDLING ONLY: no entry, size, stop, target or strategy line changed.
No lead-only file touched. Tests: `python -X utf8 -m tests.test_faults` (34 checks, areas nq + pc), plus the existing
NinjaTrader self-test (80/80) which already injects most broker faults.

Poll order matters (engine/live.py poll_once): adapter ticks (brackets, late fills, flat-time safety) run FIRST, before the
data fetch; LIT decides, routes and the state is saved BEFORE any other lane (account C, ATLAS, Rapid ATLAS, fleet, keep-alive,
paper work), and every lane is in its own try (checked by test f3). A poll that raises is logged, counted
(consecutive_errors) and the loop goes on; the fast alarm (engine/fast_alarm.py) pushes when no good poll for 90 s in hours.

| # | Fault | Before | After |
|---|---|---|---|
| 1a | LE_BarFeed file missing / empty / stale / bars in the future / 17:00 stamps | None + reason -> FEED STALE, new entries blocked, open bracket kept (selftest) | same (covered) |
| 1b | last line half-written | not parsed until whole (2026-11-03) | same |
| 1c | **a short / junk line FIRST in an appended chunk** (torn write, add-on restart) | the fast tail parser raised -> whole file "unreadable" -> entries blocked up to 15 min (until the next full read) | **line-by-line fallback: junk dropped, bars kept** (engine/ninjatrader.NinjaTraderBars.load) |
| 1d | duplicate bar / out of order / NaN row | de-duplicated (last kept), sorted, dropped | same (test a2) |
| 1e | DST / clock jump | backwards: "clock moved backwards" warn; bars are UTC epochs (no DST effect); clock guard blocks entries when the PC clock drifts | same |
| 1f | **history export (data/NQ_5m.csv) rewritten / torn mid-session** | read_csv raised EVERY poll: no routing at all until fixed (fast alarm only) | **the last good copy read this session is used (identical bars), one note an hour; no good copy yet = raises as before** |
| 2a | NinjaTrader disconnect / reconnect, mid-position | connection view blocks entries; brackets stay at the broker; reconcile on return (selftest: freeze, restart, cancel-pending) | same (covered) |
| 2b | order file locked (PermissionError) | 3 tries, then ok False + reason (entry NOT routed, logged) | same + **the unpublished copy is removed from le_outbox at once** (was swept later) |
| 2c | incoming folder missing | ok False, "NinjaTrader folder not found" | same |
| 2d | fill confirmation late / missing / partial | late fill gets its bracket; freeze = alert + 'unprotected' then bracket; partial = resized (selftest) | same (covered) |
| 2e | entry / stop REJECTED | no bracket / flattened at once + alert (selftest) | same |
| 3a | adapter state corrupt / empty / older shape | kept aside, state_problem: new entries blocked until NinjaTrader shows flat (never read as flat) | same (test c2) |
| 3b | live_state.json corrupt | warn, clean start (silent to the owner) | same + **one push a day (real bot)** |
| 3c | **data/accounts.json corrupt** | [] = the added accounts silently do not trade | [] (never armed) + **log + logs/faults.json + one push a day** |
| 3d | **data/rapid.json corrupt** | {} = the Rapid silently off | same safe default + **the note** |
| 3e | **data/account_b.json corrupt** | falls back to second_model.json (ships null) = ATLAS silently off | same fallback + **the note** |
| 3f | ATLAS state corrupt | silent clean start (bracket still in NinjaTrader) | same + warn line + note |
| 4 | an exception in one lane (ATLAS, Rapid ATLAS, account C, fleet, keep-alive, one extra account) | each wrapped; extra accounts: Account.process catches per account | same (tests f1-f3 lock it in) |
| 5a | **disk full: the bot's state save** | health.last_error only (silent) | **logged + one private push per 30 min** ("Bot cannot save its state ... CLEAN_STORAGE.bat"); trading goes on |
| 5b | **disk full: the adapter's write-ahead state** | last_error only (silent; a restart could lose track of an open bracket) | **logged + ONE alert per 30 min** |
| 6a | internet down: phone pushes (ntfy / app / alert bus) | background threads (push.pc_notify, keep-alive), never block | same |
| 6b | **internet down with Telegram / Discord chat alerts ON** | alerts.send posted synchronously (10 s timeout x 2 channels) inside _emit_events, which runs BEFORE routing: an entry could wait ~20 s | **posted in a daemon thread when chat is on** (chat off = unchanged synchronous path) |

Not changed on purpose (safe default already): a poll whose model run raises (corrupt bars everywhere) stops that poll's
routing but not the adapter ticks; the fast alarm tells the owner. Gates: tests.test_lit_live 0 differences except the known
2026-04-03; NinjaTrader self-test 80/80; update gate origin/land-fixes -> HEAD: see the run line in the lead report.
