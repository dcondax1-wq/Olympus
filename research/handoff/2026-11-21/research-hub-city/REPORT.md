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

**Update with the real file** (day-litedge 73561b86, 146 items): all 146 placed (612 places). Links `../clio/?...` are read from the site root;
Clio's `../cities/?fly=<id>` is forwarded to the World. Rejected figures show as "Test quoted", never as profit. A street per family with 4+ entries
(today: Other 104, Risk 27, Filters 4; the rest on Other) and never thinner than 6 degrees; a hub file that cannot fit = the city without the hub
(never a broken nightly build). Shots 4-5 are REAL data. Tip for the hub: real family values (not 'other') give more streets.

**Update 2** (hub families fixed, day-litedge 5823f76b): 9 streets (lit, ops, risk, atlas, kalshi, filters, money, management, sessions), all 146 placed.
Lab & Research gets its need share + 6 degrees per extra street, so the city stays at radius 173 (not 236): 14,165 buildings on a phone
(13,477 without the hub), low tier 10,983.
