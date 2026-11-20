# LEAD_WIRES: dogfood (day-quality, 2026-11-20 evening)

1. **tools/web_public/sw.js** (lead-only): `const CACHE = 'le-public-v178'` -> `'le-public-v179'` (main.js, olympus.js and 41 pages changed;
   `python tools/bump_versions.py --apply --base <landing base>` does exactly this one line on top of what is committed).
2. **agency/index.html and agency/call.html** (the web teams' files tonight): ONE line each changed here, `olympus/olympus.js?v=o18` ->
   `o19` (the kit changed; test_agency / test_cold_calls pin it). A merge conflict on that line with a web branch: keep their line and
   set `o19` on it. Their sfx.js tag was left in place (the kit loads it anyway; it can go later).
3. Nothing in build_web_dashboard.py: `odeon/trades_lite.json` is written by tools/odeon_export.py next to trades.json (whoever runs the
   export gets both), and the committed copy is in tools/web_public/odeon/.
4. DESIGN / lead (not done, see REPORT 3): Zenith Home slots for the late cards (hero, ZEUS card, strip) = the last big layout jump.
