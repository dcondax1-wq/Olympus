# Siri / Shortcuts pack: lead wires (day-jarvis)

Helper may not edit sw.js, so these are for the lead:

1. `tools/web_public/jarvis/sw.js`: add to SHELL
   ```
   './shortcuts.html',
   './shortcuts.js?v=1',
   ```
   and bump CACHE (any new name, e.g. `jarvis-shell-sc1`).
2. Still pending from the expert job: SHELL `biz.js?v=b2` -> `biz.js?v=b3` (index.html and ask.js already load b3; smoke site_checks flags it until applied).

No build file needed: the spoken shortcuts read the PC's public ntfy post from `status_feed.json` directly.
Tests: `python -X utf8 -m tests.test_jarvis_shortcuts` (15/15), registered in `run_area.py jarvis`.
