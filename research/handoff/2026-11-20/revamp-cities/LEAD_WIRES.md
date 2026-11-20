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
