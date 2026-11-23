# night-startfix: lead-only lines (2026-11-22)

1. `web_next/js/next/start.js` changed (Re-arm line gated + last result line): bump its `?v=` / the web_next `sw.js`
   cache version as usual when landing (helpers never edit sw.js).
2. Self-test "Self-healing ... bare os.replace": was 13/14 on land-fixes at 2e365f26; after merging the newer land-fixes
   (the fsutil sweep) it is 14/14 on this branch. Confirmed fixed.
4. Package D's test_ops change expects land-fixes' 'FIX_CLOCK.bat' text: ship with or after land-fixes (it is merged here).
5. run_area 'pc' now also runs the 14 PC self-test suites (all green here); tests.test_pc_selftest checks every suite
   sits in an area.
3. Nothing else needs wiring (no APPS / apps.js / build_web_dashboard changes).
