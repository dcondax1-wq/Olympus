# LEAD_WIRES: day-quality 2026-11-20

Lead-only files I did not touch. Exact edits:

1. **Root phone cache (tools/web_public/sw.js)**: `const CACHE = 'le-public-v<N>';` -> N+1 once, for the Athena shelf rebuild
   (athena/library.json ?v=a5, athena.js ?v=a8, athena/jarvis.json "200 entries"). Skip it if today's landing already moves N.
2. **Jarvis search index (stale, `widget` app missing)**: `python tools/jarvis_search_build.py` writes
   tools/web_public/jarvis/search-index.json (1214 docs); jarvis/sw.js precaches it without a ?v, so `const CACHE = 'jarvis-v<N>'`
   -> N+1 with the old name pushed onto `OLD` (or `python tools/bump_versions.py --apply --base <landing base>` does both).
   Not committed by me because it needs that sw.js bump. Fixes 1 of the 2 jarvis_skills reds.
3. **Gate's agora.css is behind**: tools/web_public/gate/index.html loads `olympus/agora.css?v=a4` while every other page loads a7
   (the bump tool never saw the Gate's script-array tags; fixed today). day-cities3 owns gate/: one-line edit `a4` -> `a7`, or
   leave it: the next agora.css change now bumps the Gate too.

No engine / live-bot file was edited. engine/self_heal.py got one new REPORT-ONLY check ("site", status info, never an alert,
changes nothing): it is not on the never-edit list, but the lead may want to read `fix_site` (20 lines) before it reaches the PC.
