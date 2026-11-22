# LEAD_WIRES: clock fix (day-clockfix 2026-11-22)

Helpers never edit sw.js, tools/build_web_dashboard.py, jarvis/apps.js or the APPS table. Lead-only lines, nothing else is needed:

1. **sw.js / build:** no new web file, so no cache-list or build change. (Docs only: docs/OWNER_MANUAL.md section N0.)
2. **Start page (tools/web_public/start/start.js):** the clock row already shows `clock.say`; it now ends with
   "double-click FIX_CLOCK.bat once, right-click > Run as administrator" when the clock is red, and the API adds `clock.fix` (that
   sentence, null when green). Optional: show `clock.fix` as a second small line under the row. The "Sync the clock" button
   (POST /api/next/start/clock) now tries the OlympusClock task when w32tm is refused; its error text carries the sentence.
3. **Update the PC after landing:** one UPDATE.bat; then the owner right-clicks FIX_CLOCK.bat > Run as administrator ONCE.
4. **make_shortcuts.ps1 (optional):** a desktop shortcut "Fix the clock" -> FIX_CLOCK.bat. Not wired here.
5. **Guard untouched:** engine/guards.py clock_max_s stays 5 s; the bot's clock never compensates.
