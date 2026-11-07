# Data City connected metropolis

PR #126 / branch `chatgpt/datacity-skyline-upgrade` keeps Data City read-only while giving the night city a clearer capital-and-district hierarchy.

## Result

- Enlarges the central scenery-only Data HQ so the civic core reads clearly from the grand camera.
- Composes the existing 2,600 decorative outskirts towers into fourteen small-city crowns instead of an even random field.
- Adds two glowing orbital boulevard rings around the existing 48 connected satellite towns.
- Gives both the no-WebGL recovery view and standalone map a central HQ, dense surrounding towns, dark-night depth, and working nine-district switching.
- Preserves project-relative city routes and advances the Data City module cache chain.

All research counts and idea cards still come from the existing published read-only payload. The added towers, towns, windows, streets, rings, and arcs are scenery; they do not add research rows, signals, accounts, orders, routes, or trading state. No bot, worker, shared-kit, registry, service-worker, Zlarior, LIT, or ATLAS code changes are included.

## Exact checks

- `node --check` passed for `city.js`, `scene.js`, `outskirts.js`, `districtform.js`, and the focused tests.
- `node --test tests/test_datacity_standalone_map.mjs`: 6/6 passed.
- `node tests/test_datacity_skyline.mjs`: passed.
- `git diff --check`: passed.
- 390×844 HIGH and LITE: HTTP 200, first frame visible, no page/console errors, no horizontal overflow, and no visible target under 44px.
- 390×844 forced no-WebGL: HQ plus 28 decorative town clusters, nine district controls, correct project routes, no unexpected errors/overflow, and 44px minimum targets.
- 390×844 standalone map: HQ plus 36 decorative town clusters, nine districts, selected-district results, correct project routes, no errors/overflow, and 44px minimum targets.

## Release boundary

Physical iPhone Safari is untested. The public dashboard mirror / GitHub Pages deployment is also pending, so this draft PR is not live and must not be described as deployed.
