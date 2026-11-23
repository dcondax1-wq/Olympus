# night-cleanup red team (2026-11-23): 1a317eafc -> night-cleanup-rt

| # | Finding | Sev | Fixed |
|---|---|---|---|
| 1 | A shortcut the owner made himself (Desktop / Startup / Start menu) to one of the 42 moved .bat files opens "the item has been moved" after the update; nothing re-points it (make_shortcuts.ps1 only makes LE START -> START_DASHBOARD.bat and LE STOP BOT -> STOP_BOT.bat, both kept at the root) | MED | tools/bat_shortcuts.py, once a day from the 15-minute report: a .lnk whose target is <bot folder>\X.bat, X.bat gone from the root and present in tools\bat, is pointed at tools\bat\X.bat (working folder = the bot folder); nothing else touched; PowerShell by full path, 40 s limit, paths through the environment |
| 2 | Merge with night-notify(-rt): 3 conflicts (docs/ALERTS.md, engine/alert_bus.py docstring, engine/trade_home.py MENU + do_choice). night-notify's new "T Test all alerts" runs run_bat("TEST_ALERT.bat") at the ROOT: after this branch that file is tools\bat\TEST_ALERT.bat, so T would say "[FIX] Nothing reached your phone" without running anything | MED (landing) | resolution below; night-notify-rt's own texts now say "TRADE_HOME.bat > T" |
| 3 | MNQ-vs-NQ volume seam after 2026-10-16 documented only in STATE.md | LOW | data/SEAMS.md (+ the 1d build, the ES Oct 19-22 gap, the 10-day context refresh window) |
| 4 | data/import_futures.build_daily writes a day the PC missed hours of as one finished bar (append-only: never corrected) | LOW | documented in data/SEAMS.md; not changed |
| 5 | Moved .bat files still tell the owner "double-click ONE_TIME_SETUP.bat / LIVE_LINK.bat / UPDATE.bat ... again" by bare name (10 echo lines; most mean the same file) | LOW | not changed (.bat edits are lead-only for helpers) |

Resolution for the night-notify merge (scripted + verified: research/handoff/2026-11-23/cleanup/merge_notify.py, then bat_menu 18/18, trading_home, alert_map, alert_bus, notify_rt, notify, alert_drill, bat_shortcuts, trade_alerts all green on the merged tree): keep BOTH menus (cleanup's 10-14 + M, then notify's T) and in do_choice keep both branches,
with T = run_bat("tools/bat/TEST_ALERT.bat", run); alert_bus docstring + docs/ALERTS.md: keep cleanup's tools/bat paths AND
notify's ZERO-SETUP paragraph (the tests below pass on that tree).

Checked OK: (1) nothing unattended runs a moved .bat: Startup = START_DASHBOARD.bat (root), scheduled tasks run .ps1 / .py only,
autoupdate edits are comments; tools/bat is not SITE_ONLY, so such an update restarts the server (the safe default); engine /
tools messages carry tools\bat paths; phone links are the pc/ download copies. (2) LE_HOME header: %~dp0, then ..\..\ when
there is no engine\ beside it; quoted (spaces), %%~fI keeps a trailing \; no remaining %~dp0 path in tools/bat; the TEMP
self-copies (QUICK_ARM, UNDO_UPDATE) get the root from %~2; FIX_CLOCK_OFF keeps the full System32 paths. (3) the 12 root
files are the daily ones (TRADE_HOME, START_BOT, STOP_BOT, START_DASHBOARD, UPDATE, UPDATE_FROM_ZIP, HEALTH_CHECK,
SETUP_EVERYTHING, ADD_ACCOUNT, ALERTS_SETUP, FIX_CLOCK, KEEPALIVE_ON) + the two desktop / Startup targets. (4) data: every CSV
change is an append after the old last row; one CBOE row completed (2026-09-17 skew blank -> 145.7) inside the 10-day refresh
window; gamma keeps the old GEX unless a real DIX.csv as long as the stored one comes back. (5) no secret, no key: CBOE
cdn-api + SqueezeMetrics are free public files, no Yahoo (test_no_yahoo 23/23); CBOE vol / GEX are context, not price data.
Tests: test_bat_shortcuts 8/8 (new), bat_menu 18/18, context_refresh 23/23, trading_home 46/46, datafeed 42/42, datafeed_sign
8/8, datapipe 36/36, datapipe_fills OK, autoupdate_paths 48/48, update_from_zip 113/113, setup_everything 43/43, no_yahoo
23/23, clockfix 40/40, ready_rt 27/27, arm_rt 47/47, pc_report_sign 21/21, live_publish 86/86, trade_alerts 83/83,
tools/win_paths.py all fine, smoke 10/11 (zenith_mode: no playwright here). test_win_scripts NOT run (rule).
