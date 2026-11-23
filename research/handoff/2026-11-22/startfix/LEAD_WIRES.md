# night-startfix: lead-only lines (2026-11-22)

1. `web_next/js/next/start.js` changed (Re-arm line gated + last result line): bump its `?v=` / the web_next `sw.js`
   cache version as usual when landing (helpers never edit sw.js).
2. Self-test "Self-healing ... bare os.replace": NOT fixed on land-fixes. The fsutil sweep is commit c8a20176 on
   `origin/day-fsutil` (20 sites + tests/test_fsutil_state.py), not landed in land-fixes or pc. Land day-fsutil; then
   tests.test_selfheal is 14/14 (13/14 on land-fixes today).
3. Nothing else needs wiring (no APPS / apps.js / build_web_dashboard changes).
