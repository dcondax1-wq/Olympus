# night-missedalarm: a patch for the red team (NOT landed)

Bot-side (engine/live_guard.py, read-only watchdog code; never arms, routes or sizes). Built on origin/pc as commit a8ffad19 (local
branch `night-missedalarm`); handed over as a patch because this helper may only push big-regime:

    git checkout -b night-missedalarm origin/pc && git am research/handoff/2026-11-27/missedalarm/0001-live_guard-missedalarm.patch

What it changes in `engine/live_guard`:
1. An account whose miss reason is "not armed" (its spec armed false, or a configured Rapid not armed at START) gets ONE line a day:
   key `guard:miss:<model>:<account>:<trading day>:notarmed` (before: one line per missed signal).
2. That line in the owner's words: title "<account> is not armed", body "<account> is not armed: it missed Zlarior long at 03:40 ET
   (~$420 risk at its size). Arm it at the PC: STOP BOT, START_BOT.bat, type I ACCEPT LIVE RISK. (One line a day per account.)"
3. "~$ at its size" on every miss (`_size_hint`): the account's own max risk a trade (rules.max_risk_usd) else the twin's risk
   (ATLAS: the paper twin's trade risk_usd; LIT: the main position's risk_usd); with the twin's R when known: "~+$1,659 at its
   size: +6.6R on ~$250 risk". All in try/except: {} on any problem.
Other miss reasons (refused, start problem, did not run) keep the MISSED TRADE line, now with the size hint.

Tests: `tests/test_missed_alarm.py` (new, 8 checks: unarmed + signal -> one line; armed -> none; 2nd signal same day -> none; next
day -> a new key; Rapid ATLAS +6.6R -> ~+$1,659; other reasons keep MISSED TRADE; ids masked; junk never raises) +
`tests/test_chaos_live` unchanged 40/40. Checks run on the patch: see CHECKS below.
