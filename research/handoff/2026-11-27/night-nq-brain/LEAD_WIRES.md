# night-nq-brain: what the lead wires (files I do not own)

1. `tools/web_public/sw.js`: precache / version the two NEW files of the NQ Brain page:
   - `nq/brainmind.js?v=m1`
   - `nq/brainmind.css?v=m1`
   (and bump the cache name so phones drop the old nq/brain.html). `brain.js` stays `?v=7` (tests/test_tgweek pins it).
2. Nothing for `build_web_dashboard.py`, `jarvis/apps.js` or the `olympus.js` APPS table: no new app, the page is the same URL.
3. Data: the page reads `brain/learn.json` (already built nightly by tools/forward_paper.py -> tools/build_brain_learn.py).
4. Test area: `nq_brain_mind` added to run_area nq (tests/run_area.py).
