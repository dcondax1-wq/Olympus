# Research Hub v2: lead wires (night-hub2, 2026-11-22)

The hub lives at `cities/hub.html` (+ `hub.js`, `hub.css`, `hub-data.json`), inside the Cities folder: `cities/` is already an "own folder"
in `sw.js` OTHER_APPS, so no sw.js / APPS / apps.js change is needed. Doors already in place (site files): the Cities bar
(`cities/index.html`, a "Research Hub" half-bar next to "Research Brain"), the Brain header "Hub" link (`brain.html`), and the hub's big
"Open the 3D Research Brain" button. The lines below are the lead's only.

1. **Rebuild the hub data before each site build** (it follows research/writeups, decisions.json, accounts.json, fleet_plan.json,
   brain-data.json, STATE.md): in `tools/ship.py` / the nightly step run `python tools/build_research_hub.py` AFTER
   `python tools/build_brain_hub.py` (it reads brain-data.json). `python tools/build_research_hub.py --check` exits 1 when stale.
   `tests.test_research_hub2` fails on a stale file, so a Decide answer or a new write-up needs that one line before the push.
2. **Optional Jarvis tile**: in the `cities` app card add `{ url: '../cities/hub.html' }` (jarvis/apps.js / olympus.js APPS = lead only).
3. **Tonight's edge hunt** text is curated in `tools/build_research_hub.py` (HUNT list; every number is checked against its write-up at
   build time). Next night's hunt: replace the HUNT list + head and the date.
4. Card links open the write-up in Clio's reader (`../clio/?read=<slug>`), which reads `../writeups/<slug>.md` that
   `build_web_dashboard._docs` already publishes. "Open Decide" links to `../board/#decide`.
5. Tests: `python tests/run_area.py cities` now runs `tests.test_research_hub2` (its own line in run_area.py). The old
   `tests/test_research_hub.py` is Clio's hub and is untouched. The browser half needs pip playwright; with a pip version whose own browser
   is missing it falls back to `/opt/pw-browsers/chromium` (cloud) or `RH_CHROME=<path>`.
