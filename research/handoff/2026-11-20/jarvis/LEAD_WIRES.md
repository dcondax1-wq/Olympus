# day-jarvis: lines for the lead (files I may not edit)

Round 1 (biz.js?v=b1, backdrop ?v=b6, jarvis-v79) is already on pc. Round 2 (team JARVIS, 2026-11-20 afternoon):

## tools/web_public/jarvis/sw.js

1. `const CACHE = 'jarvis-v80';` and put `'jarvis-v79'` first in `OLD`.
2. In `SHELL`: `'./biz.js?v=b1'` becomes `'./biz.js?v=b2'` (index.html now asks for b2; biz.js changed a lot).
3. In `SHELL`: add `'./ask.js'` (the Ask Jarvis button script; other apps load it from `../jarvis/ask.js`).
4. In `SHELL`: add `'../olympus/a11y.js'` and `'../olympus/a11y.css'` (A11Y: index.html now loads the kit's a11y.js; it pulls a11y.css next to itself).

## Other apps (DESIGN team / the kit, not lead-only)

One line per page, or in the kit loader: `<script src="../jarvis/ask.js" defer data-app="<app id>"></script>`.
Details: `research/handoff/2026-11-20/olympus2/jarvis/ASKS.md`. Each app that adds it should list `../jarvis/ask.js` in its own
service worker's precache if it has one (root `sw.js` for Zenith pages).

## Optional

- `tests/run_area.py` jarvis area: add `node tests/test_jarvis_biz.mjs` (1 s) and `python -X utf8 -m tests.test_jarvis_ask` (~40 s, browser).
