# CLOCK fix red team (2026-11-23), day-clockfix 7f22befd6 -> day-clockfix-rt

Paper / read-only review + fixes to the clock scripts only. No trade code touched (diff vs pc: engine/guards.py, live*.py, lit*.py,
second.py, account_b.py, ninjatrader.py, live_model*.json = 0 lines).

| # | Finding | Sev | Fixed here |
|---|---------|-----|------------|
| 1 | SYSTEM task action was the bare name `w32tm.exe` (resolved by search path, not pinned) | HIGH | Registered with the absolute path from `[Environment]::GetFolderPath('System')` + `Test-Path` before registering; argument fixed `/resync /force`, nothing interpolated |
| 2 | FIX_CLOCK*.bat `cd` into the user-writable bot folder, then run `net`, `where`, `powershell` unqualified while ELEVATED: cmd looks in the current folder first, so a planted `powershell.exe/.bat` there runs as admin | MED | `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`, `%SystemRoot%\System32\net.exe`, `where` dropped (`if exist`) |
| 3 | MaxPos/NegPhaseCorrection 86400 (1 day); a bad NTP answer could step the clock up to a day. Comment "the default refuses big steps" was wrong (Windows default 54000 s) | MED | `$MaxStep = 3600` (1 h; 24.5 s drift still fixed), comment corrected |
| 4 | `-Off` only removed the task, left the 15-min poll / peers / 1-day limits | LOW | `-Off` restores Windows defaults: `time.windows.com,0x9`, 604800, 54000/54000, `w32tm /config /update`; service stays on |
| 5 | ps1 ran `w32tm` / `sc.exe` by bare name | LOW | full System32 paths |
| 6 | engine/go.sync_clock runs bare `w32tm` / `schtasks` unelevated (same user, so no escalation) | LOW | not changed (would churn tests a1-a4; no privilege gain) |

Checked OK: task ACL `D:(A;;FA;;;BA)(A;;FA;;;SY)(A;;GRGX;;;AU)` = normal users may read + run, never change the action; triggers
boot / every 15 min / wake, 5 min run limit; non-admin: bat stops at `net session`, ps1 `Test-Admin` exits 1 before any write;
no path stops or disables w32time (Restart falls back to Start); idempotent (Set-ItemProperty, Register -Force);
sync_clock: one pass, 40 s timeout each, fix_clock GATED while a trade may be open, no phrase/arming; "will not sync" gone;
ASCII + CRLF on all three scripts; no PS7-only syntax.

Tests added: tests/test_clockfix.py f1-f10 (all fail on 7f22befd6, pass here). Runs: test_clockfix 40/40, test_guards 69/69,
test_self_heal_pc 90/90, test_trading_home 42/42, test_pc_health 80/80, ninjatrader --selftest 80/80, smoke 10/11 (zenith_mode:
no playwright in this container, same before the change), test_lit_live see the commit. test_start_api: no fastapi here (lead runs it).
Not testable here: a real Windows run of fix_clock.ps1 (no Windows/pwsh in the container) - first owner run is the real test.

Verdict: SAFE TO LAND with the day-clockfix-rt fixes (not on 7f22befd6 alone: item 1 + 2).
