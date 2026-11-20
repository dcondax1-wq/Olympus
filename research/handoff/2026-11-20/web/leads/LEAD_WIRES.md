# LEAD WIRES (web leads)
1. Branch: this session may push only to `day-kalshi`, so the leads slice is on **day-kalshi** (commits touching only:
   tools/web_leads.py, tools/web_public/agency/leads/*, tools/web_public/agency/call.js + call.html (?v c1 -> c2), tests/test_web_leads.py,
   tests/web_leads_page.cjs, tests/fixtures/web_leads_overpass.json, tests/run_area.py (one line), research/handoff/2026-11-20/web/leads/*).
2. A link to the list from the Agency hub (agency/index.html is the hub team's): `<a href="leads/">Website leads (businesses with no website)</a>`.
3. If the agency folder has a service worker / the site build lists agency files: add `leads/index.html`, `leads/leads.js?v=l2`, `leads/leads.css?v=l2`;
   `leads/leads.json` network-first (it changes when the PC runs the finder). call.js is now ?v=c2.
4. The real list: on the PC, `python tools/web_leads.py` then commit / publish `tools/web_public/agency/leads/leads.json`
   (or have the PC's site build run it weekly into the output folder only: never rewrite a tracked file on the PC).
