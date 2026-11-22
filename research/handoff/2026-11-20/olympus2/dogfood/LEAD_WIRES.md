# LEAD_WIRES: dogfood (day-quality, 2026-11-20 evening)

1. **tools/web_public/sw.js** (lead-only): (after the 20:40 UTC merge of pc) `le-public-v180` -> `'le-public-v181'` (main.js, olympus.js and 41 pages changed;
   `python tools/bump_versions.py --apply --base <landing base>` does exactly this one line on top of what is committed).
2. **agency/index.html and agency/call.html** (the web teams' files tonight): ONE line each changed here, `olympus/olympus.js?v=o20` ->
   `o21` (the kit changed; test_agency / test_cold_calls pin it). A merge conflict on that line with a web branch: keep their line and
   set `o21` on it. Their sfx.js tag was left in place (the kit loads it anyway; it can go later).
3. Nothing in build_web_dashboard.py: `odeon/trades_lite.json` is written by tools/odeon_export.py next to trades.json (whoever runs the
   export gets both), and the committed copy is in tools/web_public/odeon/.
4. DESIGN / lead (not done, see REPORT 3): Zenith Home slots for the late cards (hero, ZEUS card, strip) = the last big layout jump.
5. day-quality already merged origin/pc (20:40 UTC): pc's on-demand sound loader (day-a11y) and the dogfood idle preload are both in
   olympus.js (one shared `#olySfxJs` tag, so never two loads); kit bumped o20 -> o21 on every page and test pin.
