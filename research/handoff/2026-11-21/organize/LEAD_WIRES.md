# LEAD_WIRES: organize (day-a11y 2026-11-21)

1. **`tools/web_public/jarvis/apps.js`: the switcher sorts by the arenas**, so Jarvis matches Home. Replace GROUPS (lines 68-71) with:
   ```js
   export const GROUPS = Object.freeze([
     Object.freeze({ id: 'trading', name: 'NQ BOT' }), Object.freeze({ id: 'money', name: 'BUSINESS' }),
     Object.freeze({ id: 'life', name: 'JARVIS' }), Object.freeze({ id: 'more', name: 'EVERYTHING ELSE' }),
   ]);
   ```
   - Then move the Kalshi apps (`kalshi`, `dionysus`, `sibyl`, `tyche`) to a new group `{ id: 'kalshi', name: 'KALSHI' }` (insert it second), and `cities`, `colosseum` to `{ id: 'cities', name: 'CITIES' }`.
   - Then `python tools/apps_list_build.py` and `python tools/olympus_map_build.py`.
   - The arena of every app is in `olympus/gate-catalog.js` (`OLYMPUS_GATE.arenaOf(id)`) if you'd rather derive it.
2. **Version bumps at landing** (`tools/bump_versions.py`; I left the tags as they were so the pinned tests stay green):
   - `olympus/gate-nav.js` g9 -> g10, `olympus/gate-catalog.js` nv10 -> nv11, `gate/gate.css` g22 -> g23.
   - `olympus/a11y.js` has no `?v=`; add one where pages load it, or the phones keep the old copy until their cache expires.
3. **sw.js: nothing to change.** `hub/` (the new `hub/arena.html` + `arena.js` + `arena.css`) is already in OTHER_APPS (never cached by the root worker).
4. **The olympus.js APPS table: plain names** (proposal, owner's call). It shows Greek names in the kit header. If the owner agrees, set the label to the catalog's plain name for:
   - `aegis` 'Risk guard', `pnyx` 'Rules calculator', `moirai` 'Eval simulator', `labyrinth` 'Size your eval', `kratos` 'Discipline score',
   - `nemesis` 'Losing trades', `pythia` 'Risk calendar', `clio` 'Research explained', `pinakes` 'Data tables', `kronos` 'P&L calendar'.
5. **Agency team (optional):** retire `agency/call.html` (the B2 call copilot) in favour of `agency/portal/`. It's not in the catalog, so add `['call', 'agency/call.html', ...]` to RETIRED/REPLACE, or a one-line redirect on the page.
