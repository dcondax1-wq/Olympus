# LEAD_WIRES: the 6 main dashboards (day-a11y 2026-11-22)

1. **sw.js:** nothing to add (`gate/`, `jarvis/`, `hub/` are own folders). Bump the cache name (`le-public-v186` -> v187) so the phones drop the old Home.
   Version bumps at landing (`tools/bump_versions.py`):
   - `gate/gate.css` g22 -> g23, `gate/arenas.js`;
   - `jarvis/switcher.js` (wherever its `?v=` lives);
   - `olympus/gate-catalog.js` nv10 -> nv11, `olympus/gate-nav.js` g9 -> g10.
2. **`jarvis/apps.js` GROUPS = the same 6** (replaces yesterday's wire #1), so the Jarvis screen's sections match Home:
   ```js
   export const GROUPS = Object.freeze([
     Object.freeze({ id: 'trading', name: 'NQ BOT' }), Object.freeze({ id: 'life', name: 'JARVIS' }), Object.freeze({ id: 'web', name: 'WEBSITES' }),
     Object.freeze({ id: 'data', name: 'DATA CITY' }), Object.freeze({ id: 'money', name: 'MONEY' }), Object.freeze({ id: 'kalshi', name: 'KALSHI' }),
     Object.freeze({ id: 'more', name: 'MORE' }),
   ]);
   ```
   - Set the group: `agency` -> 'web'; `cities`, `colosseum`, `clio`, `archive`, `athena`, `prometheus`, `tree`, `pinakes`, `datacity` -> 'data'; `kalshi`, `dionysus`, `sibyl`, `tyche`, `kalshicity` -> 'kalshi'.
   - Then `python tools/apps_list_build.py` and `python tools/olympus_map_build.py`.
3. **olympus.js APPS table:**
   - `business: ['Business', 'B', '#c8a24a']` -> `['Money', '$', '#3b82f6']` (the Home tile's name);
   - `cities` label -> 'Data City' (the kit header matches Home).
4. **Optional, owner's phone:** nothing to do. The existing Olympus icon now opens Home by itself. If he ever re-adds the icon, add it from Home (`gate/`).
