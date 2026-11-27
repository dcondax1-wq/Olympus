# night-nq-brain: what the lead wires (files I do not own)

1. `tools/web_public/sw.js`: precache / version the two NEW files of the NQ Brain page:
   - `nq/brainmind.js?v=m4`
   - `nq/brainmind.css?v=m3`
   (and bump the cache name so phones drop the old nq/brain.html). `brain.js` stays `?v=7` (tests/test_tgweek pins it).
2. Nothing for `build_web_dashboard.py`, `jarvis/apps.js` or the `olympus.js` APPS table: no new app, the page is the same URL.
3. Data: the page reads `brain/learn.json` (already built nightly by tools/forward_paper.py -> tools/build_brain_learn.py).
4. Test area: `nq_brain_mind` added to run_area nq (tests/run_area.py).

## QA 2026-11-27 items that live in files I do not own
5. QA #9 floating round buttons: on nq/brain the only fixed controls are the shell's `.oly-ask-btn` ("Ask Jarvis", bottom-left, ~y 716 on a
   390 x 844 phone) and the OLYMPUS seal ("O", bottom-right). Both come from olympus.js / agora-ui.js (the shell), not from the Brain page.
   Suggest: on app pages, dock them in the bottom bar or hide them while a 3D canvas is under them. I did not touch the shell.
6. QA #11 the pillar chip "312/60 tick d..." / "Collecting · 100% · 312 of 60": the chip text is built in `pillars/pillarscore.js` (line ~92 /
   ~154: `${d} of ${of} NQ tick days`, `${m.tick.d}/${m.tick.of} tick days`). Fixed on my side: brain/braincore.js (the Brain app's ORDER
   FLOW next card) now reads "Ready: 312 tick days collected (needed 60)". The pillars chip needs the same `d >= of -> Ready` in pillarscore.js.
7. 3D label overlap: olympus/brain3d.js (DESIGN's) draws the full stage name; the NQ Brain now passes short 3D names (Induce, Displace,
   Limit, 1m CISD, Done). If brain3d.js labels still collide elsewhere, its label offset is the place.
