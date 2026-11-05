# Olympus Atlas hub

Added a read-only visual hub at `tools/web_public/atlas/` with the generated app catalog, search, favorites, recent destinations, category filters, keyboard shortcuts, and a projected city backdrop with pause/reduced-motion support.

Checks: `node --check atlas.js` and JSON parsing passed locally. Full repo tests and browser screenshot could not run in this environment because the private Git checkout is not authenticated and Playwright has no browser binary.

Lead wiring needed: add Atlas to the app registry and OLYMPUS APPS table, publisher tuple, root worker asset list; regenerate the apps list and run the full gate. This branch does not alter live trading.
