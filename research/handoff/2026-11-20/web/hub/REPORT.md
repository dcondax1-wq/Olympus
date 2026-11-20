# day-web-hub: the Website Business HQ (2026-11-20)

Owner: "an aspect in Olympus needs to be an expert on marketing 3D websites ... a giant team on that." HUB = the front door of it.

| What | Result |
|---|---|
| agency/index.html | The top half is now the HQ: **Next step today** (one sentence + one button: a due call-back by name, else Offers' next step, else "follow up your N proposals", else "find your first 20 leads", else "call 5 leads at lunch", else "audit 3 sites", else "build one 3D demo"), **Pipeline** Leads -> Called -> Proposal -> Paid, **Care plans** $ a month vs a $1,000 goal (about 12 Growth clients), **7 tiles** (Expert, Leads, Audit, Demos, Showcase, Offers -> their folders; Calls -> the list below), **This week** (6 rows, about 4 hours around a day job, ticks kept on the phone). The cold-call CRM below is unchanged (agency.js not edited; test_agency 118/118). |
| Data | Reads the CRM's own `agency.crm.v1`, the lead list agency.js already loaded (no second fetch), each slice's `agency.<slice>.summary` (contract sent to the lead), `sections.json` (which sections are live; no probing = no 404s). Sends nothing. |
| Navigation | Money door: **Websites** (replaces "More work": the door stays at 8). Search: website, 3d site, marketing, leads, audit, proposal, clients -> "Website business HQ" first (new action act-web; the Agency row's words + label "Website business"). Help: "My website business: where do I start?" (27 questions). What's new: top line. Jarvis switcher + apps.js: LEAD_WIRES 1-2. |
| Quality | 390 px, default look + Ivory: 0 console errors, layout shift 0.000, no sideways scroll, every HQ tap >= 44 px (the week rows are the tap target), body text >= 15 px, tokens only (hq.css has no raw colour). |
| Tests | new tests/test_web_hub.py 21/21 (area agency: static, node compute() incl. junk, browser incl. a seeded call-back + slice summary + week tick across a reload); test_agency 118/118; help 35/35; nav_search 6/6; nav_pages 28/28 (one ZEUS CLS 0.169 seen once, gone on re-run: timing, not this branch); gate_page 90/90 (pins: catalog nv8 in gate-nav; A to Z = every live app, Data City + Kalshi City added to the test's retired set to match doors.js / the catalog); hubs 99/100 (the gate.css colour check, red on pc). |
| Shots | hq-top-dark / -light, hq-tiles-dark / -light (390 x 844 x 2). |
