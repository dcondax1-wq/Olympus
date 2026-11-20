# day-web-hub: lead wires (2026-11-20)

1. **Jarvis switcher, Business area** (`tools/web_public/jarvis/switcher.js` line ~58, JARVIS team): put Websites right after Business:
```js
export const FIRST = ['cities', 'kalshi', 'nq', 'home', 'planner', 'business', 'agency', 'zenith'];
```
2. **jarvis/apps.js** (lead-only) line ~138, the Agency row's line (the switcher and A to Z show it):
```js
  app('agency', 'Websites', 'money', '#d08c4a', 'Website business HQ: next step, leads, audits, 3D demos, offers, calls', { glyph: 'Ε' }),
```
   then `python tools/apps_list_build.py` (olympus/apps-list.js) and `python tools/olympus_map_build.py`.
3. **Versions for cached phones** (files I did not touch): `gate/index.html` line 61 `olympus/gate-catalog.js?v=nv7` -> `nv8` (+ the
   pin in `tests/test_gate_page.py` line 74); `launcher.js` line 55 `doors.js?v=d9` -> `d10` both paths (+ `tests/test_apps_list.py` line 140).
   I bumped hub/index.html + olympus/gate-nav.js (catalog nv8) and hub/doors.html (doors.js d10).
4. **Money door at 8**: "Websites" (agency/) REPLACED "More work" (business/work.html; still reachable from Business and search), so
   the door stays at 8 shortcuts. Undo: swap the row back in olympus/doors.js (+ web_next/js/next/doors.js, byte-identical).
5. **sections.json** (`agency/sections.json`): set `live: false` for any section whose branch you do not land today (its tile then says
   "Being built" instead of a dead link); `summary_file: true` for a section that ships `<slice>/summary.json`.
6. **Contract for the 7 slices** (already sent): localStorage `agency.<slice>.summary` =
   `{n, label, next, t, pipe: {leads, called, proposal, paid}, mrr}` (all optional). Offers' `next` becomes the HQ's next step when no
   call-back is due; the HQ takes the MOST of each pipeline stage across the CRM and the slices (never a sum: no double count).
7. **sw.js**: none. agency/ has no worker; hq.js + hq.css load with ?v=1 / ?v=3.
