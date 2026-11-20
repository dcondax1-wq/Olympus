# web-expert: lines for the lead / other teams

Work is on branch **day-jarvis** (this session can push only that branch), merged with olympus/pc 4f637df3 first.

## Lead-only: tools/web_public/jarvis/sw.js
- `SHELL`: `'./biz.js?v=b2'` becomes `'./biz.js?v=b3'` (biz.js gained the 'web' answers; index.html and ask.js now ask for b3). Bump `CACHE`.

## HUB team (agency/index.html, agency.js): one link to the expert
- A card or button on the Agency home: **"Website expert"** -> `expert/` ("Diagnose a prospect, prices, what to say, 3D by trade").
- Agency has no service worker of its own (root `sw.js` lists `agency/` in OTHER_APPS), so nothing to precache.

## Doors / catalog (HUB team)
- Search words for `agency/expert/`: website, 3D site, immersive, pricing, cold call, objections, local SEO, Google Business Profile, reviews, retainer.

## Tests
- `tests/run_area.py` AREAS 'agency' += `web_expert` (done, above main()). `node tests/test_jarvis_biz.mjs` covers the Jarvis 'web' answers.
