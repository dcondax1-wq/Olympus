# research-hub-city REPORT (2026-11-21, branch night-revamp-cities)

1. **Lab & Research = the 3D Research Hub** (tools/world_build.py reads `tools/web_public/research/hub.json`, list or {items}): one place per row.
2. **Families are streets**: each family (top 8 + Other) gets its own slice of the district; "Next in <family>" walks it.
3. **Live** = tall bright crowned towers, height = the real $ a month (log scale). **Leads / shadow logs** = lit buildings under scaffolding.
   **Rejected** = ruins; the card says the one-line why + $ a month. **Decide** = a gold beacon (ring + searchlight) that pulses until answered.
4. **Tap** = the glass card: status, $ a month, family, date, summary, **Read** (opens the row's `url`, site pages only).
5. **Search**: Find ("holiday") flies there; **deep link** `cities/world/?fly=<id>` (hub id, any place id, else the best search hit).
6. **Light list** (Low / Save-Data / no WebGL): the hub entries with status, $ and Read. Same phone rules (poster first, 3D after the first touch or 6.5 s).
7. **No hub.json = no hub places**: example rows never reach the owner's city. Shots marked EXAMPLE were made with `tests/fixtures/research_hub.json`.
8. Tests: test_world_build 47/47 (3 new hub checks on the fixture), test_world_page 32/32.
