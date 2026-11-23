# PC guard red team (2026-11-23): night-pcguard d3e5dd922 -> night-pcguard-rt

| # | Finding | Sev | Fixed |
|---|---|---|---|
| 1 | -Off (elevated) put back whatever %ProgramData%\Olympus\win_guard_prev.json said: the registry PATH and NAME (Set-RegDword $it.a $it.b), the powercfg GUIDs and the adapter property all came from the file. Any user may create a folder in ProgramData: a non-admin process that plants Olympus\win_guard_prev.json before the first run (it then owns the folder) gets the elevated undo to write any DWORD anywhere in HKLM (e.g. EnableLUA = 0) | HIGH (local privilege escalation) | -Off restores only the exact values the script writes (the 7 Windows Update values, the 4 powercfg GUIDs on a GUID-shaped plan, the 2 adapter properties as Enabled / Disabled, numbers only); anything else in the file is ignored with a [FIX] line; the folder is created admin + SYSTEM write, users read |
| 2 | The real-script runs (tests b) need pwsh, which this container does not have (installing it was not allowed here): only the static checks ran | note | run `python -X utf8 -m tests.test_win_guard` on a machine with pwsh (LE_PWSH) before / after landing |
| 3 | Active hours from today's ET -> local conversion: on a PC outside New York the window drifts 1 h for the weeks between US and local DST changes | LOW | not changed |

Checked OK: every program by its System32 path (powercfg.exe); only HKLM WindowsUpdate UX / Policies WindowsUpdate (+AU), the current
power plan on AC, physical adapters with -NoRestart (no reset, NinjaTrader keeps its connection); never Defender, firewall,
accounts, BitLocker, services, bcdedit; the "before" values saved before each change (an interrupted run can be undone), kept
from the first run; a value that was not there is removed on undo; the SYSTEM clock task still runs only w32tm.exe; runs in
FIX_CLOCK's one admin window (fix_clock.ps1 and win_guard.ps1 are both in the bot folder: the same trust as fix_clock itself, the
owner starts it). Tests: win_guard_rt 6/6 (new, static), win_guard 18/18 (b skipped: no pwsh), clockfix 40/40, pc_guard 56/56,
trading_home 46/46, ready 36/36, win_paths all fine.
