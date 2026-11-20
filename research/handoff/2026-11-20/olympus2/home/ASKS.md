# HOME + CITIES: cross-slice asks (olympus2, 2026-11-20)

1. **Lead / every app page:** `olympus/intro-app.js?v=i10` -> `?v=i11` in the 73 pages that load it (`grep -rl "intro-app.js?v=i10" tools/web_public`),
   and the pin in tests if any; the file changed (1.15 s film, once per app per day).
2. **NAV (hub/):** `hub/doors.html`: `olympus/home-fx.css?v=x1` -> `?v=x2`, `olympus/home-fx.js?v=x1` -> `?v=x2` (faster intro + tap to skip on the Doors page).
3. **DATA TRUTH:** the Home's open-trade line reads `board.<lit|atlas>.position` (side, dir, qty, stop, target, entry_t, unrealized_usd); the 25K #2
   and Rapid accounts have no position field in the PC's `accounts` rows, so a trade there is not shown yet. A `position` per account row would fix it.
4. **KALSHI:** the Home reads `kalshi/k8.json` legs (`live`, `tz`, `open`, `last_day`, `last_res`, `name`); please keep those field names.
