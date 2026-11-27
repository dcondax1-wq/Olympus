# LEAD WIRES: night-nq-speed

1. `tools/web_public/sw.js` precache: add `nq/nqfeed.js` next to the other nq/*.js entries (and bump the cache version as usual).
2. One tag in the head of each NQ page, right after the pc_feed.js tag (not defer, not module):
   `<script src="../pc_feed.js?v=n9"></script><script src="nqfeed.js?v=1"></script>`
   nq/index.html, nq/live.html, nq/accounts.html, nq/brain.html. (Page owners tonight, or the lead when landing.)
3. Optional, page owners: `NQ_FEED.cached()` + `NQ_FEED.on(cb)` for the 0.25-0.5 s paint (NQCORE_API.md section 2).
Proof after wiring: `python -X utf8 tools/nq_speed_probe.py --variant before --runs 3` (the "before" variant then IS the wired page).
