# The .bat files: where each one is (night-cleanup 2026-11-22)

**Use one file: double-click `TRADE_HOME.bat`.** Every owner step is a number in its menu; `M` = More tools lists every other button.
The 42 rarely used / one-time / undo files moved to `tools\bat\` and still work there (each finds the bot folder by itself:
its first lines set `LE_HOME`). Scheduled tasks never ran a .bat (they run python / powershell directly), so nothing on the PC's
timers changed. Only if you once typed the optional `schtasks ... RUN_MONEY.bat` line yourself: run it again from `tools\bat\RUN_MONEY.bat`'s top comment.

## Kept at the top of the folder (12)

| File | Why it stays | Menu |
|---|---|---|
| `ADD_ACCOUNT.bat` | each new account; the dashboard Add-account box and docs name it | menu 4 (the same steps) |
| `ALERTS_SETUP.bat` | once: Telegram / Discord | menu 5 -> 1 |
| `FIX_CLOCK.bat` | must be right-clicked > Run as administrator once (a menu cannot elevate) | menu 9 (sync); first time: right-click > Run as administrator |
| `HEALTH_CHECK.bat` | one screen of green / yellow / red; UPDATE.bat and START_DASHBOARD.bat name it | menu 10 |
| `MONDAY_SETUP.bat` | weekly: the ONE Monday double-click (update, clock, START with your phrase = keep-alive on, alert test; night-zerotouch) | - (routine 8 is the menu twin) |
| `KEEPALIVE_ON.bat` | weekly: MFFU 7-day keep-alive (you type the phrase) | menu 3, routine 8 |
| `SETUP_EVERYTHING.bat` | RECOVERY: run from inside a downloaded code zip (it looks for the bot folder from where it is); must be at the zip's top | menu M -> 11 |
| `START_BOT.bat` | daily: start + arm (you type the phrase); the 'LE START' flow and docs point here | menu 2, routine 8 |
| `START_DASHBOARD.bat` | AUTOSTART: the Windows Startup shortcut 'LE bot server.lnk' (engine/go.py) and the desktop icon LE START point at this exact path | menu M -> 25 |
| `STOP_BOT.bat` | daily: stop; the desktop icon LE STOP BOT points here (scripts/make_shortcuts.ps1) | menu 6 |
| `TRADE_HOME.bat` | THE front door: every step below is a number in its menu | - |
| `UPDATE.bat` | the manual update the bot's own messages name (engine/autoupdate, self_heal) | menu 7 |
| `UPDATE_FROM_ZIP.bat` | RECOVERY: the update when GitHub is down; you drag the zip onto it in the bot folder | menu M -> 12 |

## Moved to tools\bat\ (42)

| Old name (top folder) | Now | Menu |
|---|---|---|
| `AGENCY_DAY.bat` | `tools\bat\AGENCY_DAY.bat` | menu M -> 36 |
| `ALERTS_OFF.bat` | `tools\bat\ALERTS_OFF.bat` | menu M -> 5, menu 5 -> 4 |
| `ALERTS_ON.bat` | `tools\bat\ALERTS_ON.bat` | menu M -> 4, menu 5 -> 3 |
| `BACKUP_SETUP.bat` | `tools\bat\BACKUP_SETUP.bat` | menu 12 |
| `BOTS_BACK.bat` | `tools\bat\BOTS_BACK.bat` | menu M -> 7 |
| `BOT_LITE.bat` | `tools\bat\BOT_LITE.bat` | menu M -> 22 |
| `CLEAN_PC.bat` | `tools\bat\CLEAN_PC.bat` | menu M -> 19 |
| `CLEAN_STORAGE.bat` | `tools\bat\CLEAN_STORAGE.bat` | menu 14 |
| `CLOUDFLARE_SETUP.bat` | `tools\bat\CLOUDFLARE_SETUP.bat` | menu M -> 29 |
| `CONNECT_DAY.bat` | `tools\bat\CONNECT_DAY.bat` | menu M -> 32 |
| `EMAIL_SETUP.bat` | `tools\bat\EMAIL_SETUP.bat` | menu M -> 38 |
| `EMAIL_STOP.bat` | `tools\bat\EMAIL_STOP.bat` | menu M -> 39 |
| `FIX_CLOCK_OFF.bat` | `tools\bat\FIX_CLOCK_OFF.bat` | menu M -> 21 |
| `FRESH_START.bat` | `tools\bat\FRESH_START.bat` | menu M -> 27 |
| `GITHUB_SIGNIN.bat` | `tools\bat\GITHUB_SIGNIN.bat` | menu M -> 14 |
| `GO_LIVE_EVAL.bat` | `tools\bat\GO_LIVE_EVAL.bat` | menu M -> 9 |
| `KALSHI_KEY_SETUP.bat` | `tools\bat\KALSHI_KEY_SETUP.bat` | menu M -> 33 |
| `KALSHI_LIVE.bat` | `tools\bat\KALSHI_LIVE.bat` | menu M -> 34 |
| `KALSHI_STOP.bat` | `tools\bat\KALSHI_STOP.bat` | menu M -> 35 |
| `KEEPALIVE_OFF.bat` | `tools\bat\KEEPALIVE_OFF.bat` | menu M -> 3 |
| `NT_OFF_ONEDRIVE.bat` (new, day-ops2) | `tools\bat\NT_OFF_ONEDRIVE.bat` | menu M -> 42 |
| `RESTORE_NEW_PC.bat` (new, day-ops2) | `tools\bat\RESTORE_NEW_PC.bat` | menu M -> 43 |
| `LIVE_LINK.bat` | `tools\bat\LIVE_LINK.bat` | menu 11 |
| `MONEY_INBOX.bat` | `tools\bat\MONEY_INBOX.bat` | menu M -> 31 |
| `MOVE_BOT.bat` | `tools\bat\MOVE_BOT.bat` | menu M -> 28 |
| `NO_CHART_MODE.bat` | `tools\bat\NO_CHART_MODE.bat` | menu M -> 23 |
| `ONE_TIME_SETUP.bat` | `tools\bat\ONE_TIME_SETUP.bat` | menu M -> 26 |
| `PC_CARE.bat` | `tools\bat\PC_CARE.bat` | menu 13 |
| `PC_DOCTOR.bat` | `tools\bat\PC_DOCTOR.bat` | menu M -> 2 |
| `POSTCARD_SETUP.bat` | `tools\bat\POSTCARD_SETUP.bat` | menu M -> 40 |
| `POSTCARD_STOP.bat` | `tools\bat\POSTCARD_STOP.bat` | menu M -> 41 |
| `PUBLISH_NQ.bat` | `tools\bat\PUBLISH_NQ.bat` | menu M -> 17 |
| `QUICK_ARM.bat` | `tools\bat\QUICK_ARM.bat` | menu M -> 10 |
| `ROLL.bat` | `tools\bat\ROLL.bat` | menu M -> 15 |
| `RUN_AGENCY.bat` | `tools\bat\RUN_AGENCY.bat` | menu M -> 37 |
| `RUN_MONEY.bat` | `tools\bat\RUN_MONEY.bat` | menu M -> 30 |
| `SETUP_SHORTCUTS.bat` | `tools\bat\SETUP_SHORTCUTS.bat` | menu M -> 24 |
| `STATUS.bat` | `tools\bat\STATUS.bat` | menu M -> 1 |
| `TEST_ALERT.bat` | `tools\bat\TEST_ALERT.bat` | menu M -> 6, menu 5 -> 2, routine 8 |
| `UNDO_BOTS_BACK.bat` | `tools\bat\UNDO_BOTS_BACK.bat` | menu M -> 8 |
| `UNDO_LIVE_LINK.bat` | `tools\bat\UNDO_LIVE_LINK.bat` | menu M -> 16 |
| `UNDO_PC_TUNE.bat` | `tools\bat\UNDO_PC_TUNE.bat` | menu M -> 20 |
| `UNDO_PUBLISH_NQ.bat` | `tools\bat\UNDO_PUBLISH_NQ.bat` | menu M -> 18 |
| `UNDO_UPDATE.bat` | `tools\bat\UNDO_UPDATE.bat` | menu M -> 13 |

Checked by `python -X utf8 -m tests.test_bat_menu` (every menu number opens a file that exists, every moved file is in the menu,
no code or doc still names a moved file by its old top-folder path).
