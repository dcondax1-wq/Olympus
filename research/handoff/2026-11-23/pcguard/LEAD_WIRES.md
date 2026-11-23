# night-pcguard: lead-only lines (2026-11-23)

1. MONDAY_SETUP (night-zerotouch, engine/monday.py) skips the admin step when the task OlympusClock exists. The owner's PC
   already has it, so the guard would never run there. Change the skip to: clock task there AND `engine.win_guard.status()["on"]`
   is True. Same single UAC "Yes": monday.fix_clock already runs scripts\fix_clock.ps1 elevated, and fix_clock now calls
   scripts\win_guard.ps1 in that window. Suggested line 2/4: "Clock + Windows guard".
2. Start page: if you want the line there too, `engine.win_guard.line()` gives "Windows guard: on / OFF / not set up (...)"
   (readiness' Monday lines and TRADE_HOME status already show it).
3. tests.test_win_guard's real-script part needs pwsh (skipped in this container, which has none); run it where pwsh exists.
4. Open point to verify on the real PC: SmartActiveHoursState 0 is meant as "Windows' automatic active-hours guess off". It
   is undone by FIX_CLOCK_OFF like every other value, so a wrong guess costs nothing.
