# revamp-cities: what the lead must wire (helpers may not edit these files)

1. **Service worker cache** (`tools/web_public/sw.js` line 94): `const CACHE = 'le-public-v157';` -> `'le-public-v158'` (or the next
   free number when you land), so phones drop the old World / Cities / Data City / warp files. New files to serve as-is (no precache
   needed): `cities/world/poster.jpg` (55 KB, the World's loading photo), `cities/world-card.jpg` (6 KB, the Cities door card).
2. **Recommended, owner-visible** (`tools/web_public/jarvis/apps.js` line 89): the Cities door opens the new 3D city directly:
   `app('cities', 'Cities', 'trading', '#b88a50', 'A world of city islands', { glyph: '◈' }),` ->
   `app('cities', 'Cities', 'trading', '#b88a50', 'The 3D city of everything: every app, every idea tested', { glyph: '◈', url: '../cities/world/' }),`
   The old island map stays one tap away (the World's breadcrumb "Worlds > Cities and ..." and `cities/`), and `cities/` keeps its
   own big "Olympus World" card. Check `tests.test_apps_list` / `tests.test_olympus_map` for a pinned Cities url before landing;
   if it is pinned, skip this item (the card on `cities/` already leads there).
3. `docs/OLYMPUS_MAP.md` line 63 (rebuilt by `tools/olympus_map_build.py`): the Cities row's blurb follows item 2 if you take it.
4. **Intro (jarvis/entry.js changed): `entry.js?v=e1` -> `?v=e2`** in `jarvis/index.html` line 152, `jarvis/sw.js` line 54, and the pin in
   `tests/test_jarvis_hub.py` line 1593.
5. **Jump (olympus/warp.js + warp.css changed): `?v=w2` -> `?v=w3`** in `olympus/themes.js` 761 (warp.js), `olympus/agora.css` 8,
   `jarvis/index.html` 18, `index.html` 8, `kalshi/index.html` 5 (warp.css), `hub/doors.html` 64, `hub/help.html` 64, `hub/zeus.html` 94,
   `atlas/index.html` 22 (warp.js), `cities/world/index.html` 22 + 26, `jarvis/sw.js` 54 and `kalshi/sw.js` 14 (both files), and the pins in
   `tests/test_warp.py` lines 78, 83, 84, 102, 108, 109, 125. (Left for you so every page and pin moves together in one commit.)
