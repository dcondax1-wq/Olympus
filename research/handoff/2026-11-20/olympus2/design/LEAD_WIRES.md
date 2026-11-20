# LEAD_WIRES: DESIGN team (day-arenas, 2026-11-20)

1. `tools/web_public/sw.js` line 94: `le-public-v*` -> next number. The root `index.html` (Zenith) changed: `zenith_agora.css?v=a5df`,
   `polish.css?v=4f`, `more.js?v=q6be`, `olympus/zeus_core.js?v=6`, the inline shell layer in step with `olympus/shell.css`.
   Every other folder I changed is in `OTHER_APPS` (not cached by the root worker); their `?v=` tags are bumped.
2. `jarvis/apps.js`, the `olympus.js` APPS table, `tools/build_web_dashboard.py`: no change. New static files publish as they are:
   `olympus/kit.html` (the live design-system page), `settings/extras.js`, `tools/design_audit.py` (a tool, not on the site).
3. Optional: a door / hub link "Design system" -> `olympus/kit.html` (for you and helpers; the owner never needs it).
4. Kit versions for the other slices' pages (optional, housekeeping): `olympus/agora.css?v=a7` -> `a8` everywhere (ASKS 8); `olympus/olympus.js` stays
   `?v=o15` (the shared test kit pins it; the veil change reaches phones through the normal 10-minute cache).
5. New kit files publish as they are: `olympus/age.js`, `olympus/age.css` (DATA's age component, the kit copy), `olympus/kit.html`.
