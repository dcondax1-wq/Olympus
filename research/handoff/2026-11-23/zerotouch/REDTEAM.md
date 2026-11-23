# Zero-touch red team (2026-11-23): night-zerotouch 649fc9654 -> night-zerotouch-rt

| # | Finding | Sev | Fixed |
|---|---|---|---|
| 1 | owner_off is new: a keep-alive the owner switched OFF BEFORE this update ("atlas": false, no owner_off in the file) was turned back ON by the next START phrase | MED | an explicit false in a file without owner_off / consent = his OFF, kept as owner_off (every later START keeps it off; only KEEPALIVE_ON clears it) |
| 2 | self-heal "nt" reopened NinjaTrader every hourly run while data/autostart.json exists: a NinjaTrader the owner closes on purpose (an NT update, a break) came back every hour, forever (test: 4 opens in 14 h) | MED | at most 2 opens a day, never again when it was closed within 6 h of self-heal's own open (= on purpose): one "need" line |
| 3 | START BOT with the bot already running: no console / piped stdin at the new keep-alive question raised EOFError (traceback) | LOW | EOF / Ctrl+C = left off |
| 4 | Landing with night-cleanup: TRADE_HOME "k" (Keep-alive OFF) points at the top-folder KEEPALIVE_OFF.bat, which cleanup moves: the owner's OFF in TRADE_HOME would do nothing; MONDAY_SETUP.bat is a 13th top-folder file; 20+ texts name moved files at the old place | MED (landing) | research/handoff/2026-11-23/cleanup/merge_notify.py (general now): verified on cleanup+notify+payout+zerotouch, all green |
| 5 | engine/recovery.py names tests.test_recovery, which does not exist (test_zerotouch d covers it) | LOW | not changed |

Checked OK: keep-alive goes ON only via _step_arm's end (after the phrase check and a good start) or the "already running" question
(the typed phrase; Enter = off); auto-resume / resume_now / the Start page resume never reach step_arm; the Start page job uses
the phrase typed on the page at that START (LE_START_CONFIRM, popped); the after-update re-run carries the same START's phrase;
the consent file holds {t, day, accounts, via}, never the phrase; owner_off "*" (KEEPALIVE_OFF.bat) keeps every account off,
--on <key> clears only that key; Sim names dropped (is_sim), BLITZ / other firms never listed, an account whose arm failed is
not "armed" in its file; the keep-alive trades only through the account's real adapter (paper / Sim fills never count);
MONDAY_SETUP: an administrator window skips the update and the start (the bot never runs elevated), a normal window asks UAC
for fix_clock.ps1 only (Start-Process -Verb RunAs -Wait), UPDATE.bat with stdin NUL (no "update anyway").
Tests: test_zerotouch_rt 7/7 (5 fail on 649fc9654), zerotouch 50/50, keepalive 116/116, self_heal_pc 90/90, arm_rt 47/47, go
68/68, start_api 117/117, autorun 100/100, rapid_arm 19/19, accounts_cli 40/40, trading_home 46/46, ready 36/36, ready_rt 27/27,
win_paths all fine, ninjatrader --selftest 80/80.
