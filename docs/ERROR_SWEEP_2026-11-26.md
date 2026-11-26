# Real-error sweep from the PC's own reports (big-zeroerr2, 2026-11-26)

Owner: "no more errors". Sources read here, honestly: the public status feed (ntfy keeps only the last ~12 h: 102 posts,
2026-11-26 00:17-12:00 ET, incl. 20 board events, the self-heal (sh), remote (rc), readiness (rd) and glog blocks), the control
branch receipt in the feed (rc), research/findings/LEDGER.md (the lead's 14-day round notes from the feed) and STATE.md. Not
available from the cloud: the PC's own logs (server-*.log, self_heal heal-*.log), the heartbeat branch (silent on purpose), so a
root cause the reports do not show is marked "not provable" and the fix bounds the damage instead.

Ranked by money risk (missed trades / wrong state first).

| # | Cluster | Count (what the PC said) | Cause in code | Fix | Owner must act? |
|---|---|---|---|---|---|
| 1 | **Server hung 7 h** (11-25 17:22 -> 00:36 ET) | heartbeat frozen at 17:22; BOT DOWN in every post until 00:36; 3 x self-heal "bot server does not answer" | WHY it froze: not provable from the reports (no PC log in the feed). WHY it lasted: run_bot.ps1 restarts only a server that EXITS; self_heal.fix_server only reported; the server's own alarms live inside the hung process | **NEW engine/hang_guard.py**: a separate process pings /api/health/ping every 20 s; 150 s silent + flat = kill -> the supervisor restarts in ~5 s -> auto-resume re-arms (under 5 min, tests.test_zeroerr2 b: 17:22 -> restarted by 17:27); a trade open = not killed, one line, restart once flat. server.py arms faulthandler from its event loop: a frozen loop dumps every thread's stack to logs/hang_stacks.txt (kept in logs/hang/), so the NEXT hang names its cause | no |
| 2 | **Nobody was told about #1 overnight** | 0 pushes reached the owner 17:22-00:36 | the in-server fast alarm froze with the server; the cloud PC-silent watch does not run (Olympus main is README-only, failure map G8) and is 03-15 ET only anyway | hang_guard sends from outside the server through engine/alert_bus as kind bot_stopped (Telegram first, always rings, quiet hours included) | only if ALERTS_SETUP.bat (Telegram) was never run |
| 3 | **Update held back since 11-23 21:30** (every fix since then not on the PC) | 132 board lines in 12 h ("held back by a local change it may not touch: ", the name cut off); remote update refused 11-24 16:11 + 17:07; same family 11-20 (rollback every hour: '?' in 2 file names) and 10-27 (lit_journal) | bot-written tracked file research/orderflow/results.json (tickrec autopilot); the PC's old code posts the line every 15 min with the file name at the end (cut at 90 chars) | already in pc: generated_files entry, auto-park, Telegram /update + /update force, the writers-sandbox test (day-handsfree), names first + once a day (day-updfix) | **yes, once**: the STATE.md line (stash results.json + UPDATE.bat) |
| 4 | **False "ATLAS 25K is on Sim"** readiness warning | 43 of 102 posts (rd warn) | engine/preflight.arms read the label ("ATLAS <account>") instead of the kind | already in pc (day-brain-feed); disappears with #3's update | no |
| 5 | FEED STALE blip 11-26 10:15 ET | 1 post (gone at 10:30) | one late LE_BarFeed 1m bar; the adapter blocks entries while stale (no LIT setup was pending) | none needed; LE_Feed's self re-request takes over when it goes live (day-ops2) | no |
| 6 | Clock 8.4 s behind / NinjaTrader folder in OneDrive (health check WARNs) | health check | w32time not set up (FIX_CLOCK never run); Documents backed up by OneDrive | day-ops2: START syncs / runs FIX_CLOCK with one Windows Yes; tools/bat/NT_OFF_ONEDRIVE.bat | one Yes + one click |
| 7 | Rapid EOD "refused: start config is not armed" (11-20) | 2 reports | arming race: the server resumed before account_cli.arm wrote | fixed 11-21 (every account armed before any server restart) | no |
| 8 | Fake "bot stopped / paper" status on the public topic (11-25 19:43) | 1 post | the cloud rehearsal sandbox posted to the real topic | lead's day-noleak | no |

Tests: `python -X utf8 -m tests.test_zeroerr2` (20 checks: the guard, the 11-25 replay, a real hung process, a real faulthandler
dump, the wiring, the fixed clusters' code). Off switch: LE_HANG_GUARD=0.
