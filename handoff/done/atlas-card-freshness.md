# Atlas status card freshness

Atlas is a static dashboard hub. Its card had no `stale_after`, so Jarvis greyed it after the default 30 minutes even while the link remained available. Set the supported 14-day window (`1,209,600` seconds), matching the static publication cadence contract in `jarvis/apps.js`.

Parsed the updated JSON and checked the validator range. This changes no live feed or trading code.
