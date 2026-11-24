# THE FOUR PILLARS: lead wires (day-pillars, 2026-11-24)

Owner 2026-11-23 23:00 ET: "Orderflow and BLITZ alongside LIT and ATLAS are gonna make us. Those are our 4 pillars. Make that into a thing
for Olympus." Branch `day-pillars`, cut from origin/pc 312bcbd00. No forbidden file was edited (tests/test_pillars.py checks
sw.js, tools/build_web_dashboard.py, jarvis/apps.js and olympus/olympus.js against origin/pc). These are the lines only the lead may add.

1. **App row** (the page is a new folder `tools/web_public/pillars/`): add to `jarvis/apps.js` BUILT_INS
   `{ id: 'pillars', name: 'Four Pillars', url: '../pillars/', group: 'trading', color: '#f1c14b', what: 'LIT, ATLAS, BLITZ, ORDER FLOW: status, accounts, edge, thinking, next' }`
   (door: ZEUS Trading, first in its list), then `python tools/apps_list_build.py` and `python tools/olympus_map_build.py`, and REMOVE
   `"pillars"` from the temporary exemption in `tests/test_apps_list.py` (line ~80, marked with a comment). Optional: the olympus.js APPS entry.
2. **sw.js**: add `'pillars/'` to `OTHER_APPS` (network first, last good copy offline), like `cities/` and `nq/`. Without it the
   page and its `pillars-data.json` are served cache-first / stale-while-revalidate (one visit late after each change).
3. **Build step**: in `tools/ship.py` (or the lead's site build) run `python tools/build_pillars.py` (`--check` exits 1 when
   `pillars/pillars-data.json` is stale), next to `build_strategy_lab.py` and `build_brain_hub.py`. Its numbers come from
   research/lab/backtest_live.json (LIT), research/second/atlas.json (ATLAS), research/writeups/blitz-review-2026-11-18.md (BLITZ),
   research/lab/orderflow.json (ORDER FLOW) and edge.json; each pillar shows its source.
4. **The order-flow line in the PC post** (the page says "Waiting: the PC's post does not carry the tick count yet" until this lands):
   - DONE on the branch: `engine/tickrec.py` `tiny()` + `write_tiny()`; the autopilot writes `data/tickrec_tiny.json` after each ingest
     (`{"on":true,"d":23,"of":60,"bf":"running","o":"2026-09-14","l":"2026-11-23","t":...}`, < 120 bytes; tests/test_tickrec_tiny.py 7/7).
   - LEAD: in `tools/pc_report.py`, next to the orderflow_note line (~line 542), ONE line, plain JSON, NO import (test_tickrec's rule:
     nothing imports engine.tickrec): `snap["tr"] = read_json(os.path.join(root, "data", "tickrec_tiny.json"), None)`
     and make sure `tr` rides in the lite CORE post (or an ext part: pc_feed.js merges unknown ext keys into the core). The page reads
     `lite.tr` (or `lite.pc.tr`). Note: the autopilot runs only outside 01:40-16:05 ET, so the count is from the last quiet window.
5. **BLITZ is still HIDDEN by the switch** (`dashboard_view.json` hidden_bots ["blitz"], engine/hidden_bots.py, owner 2026-11-15). The pillar
   shows BLITZ from its research numbers and engine/blitz.py's rules only, says "built and switched off", and lists the Rapid accounts
   it was meant for as OFF; no live BLITZ data is read anywhere (tests.test_hidden_bots 64/64). Showing live BLITZ data needs the owner's
   yes (hidden_bots [] in dashboard_view.json); CLAUDE.md line 3 ("BLITZ hidden") and STATE.md's BLITZ row may want the pillar wording.
6. **A bug fixed on the way, live on pc today**: the Strategy Brain's 2D layer (`.flat`, empty and `hidden`) had `display: grid`, which
   beats the hidden attribute, so it sat over the 3D canvas and swallowed every tap on a lobe (the lobe chips still worked). Fixed in
   cities/mind/mind.css (`.flat[hidden] { display: none }`); the old test only read a leftover sheet title, it now demands the tapped lobe.
7. **NQ page**: a "Pillars" button in the header (the tag row now wraps instead of widening the page: nq.css v=a9, test_nq_chart's pin
   moved with it) and the 4-chip strip under the status lines (loaded after `load` by a dynamic import, so the NQ eager-JS budget stays
   at 0 over; it reuses `window.NQ.S.lite`, never polls ntfy itself).
8. **Research Hub**: a Pillars row on both tabs (Research + Strategy Lab), `hub.html?pillar=lit|atlas|blitz|of` opens it filtered.
   One rule for the Hub and the Brain: `pillars/pillarof.js`. (The Hub's family 2 is "Rapid + fleet money", not BLITZ: only 0 / 1 map.)
9. **Strategy Brain**: regrouped into the 4 pillars (LIT, ATLAS, BLITZ, ORDER FLOW = the 4 big lobes and the first 4 chips; ATLAS's EMA /
   MACD / S/R beside it; the research neurons orbit the pillar they belong to: Research Brain findings, the 59 LIT variants, the 43
   order-flow proxy tests; a study belongs to the pillar it names FIRST, order-flow words win). Its header links to the Pillars page.
10. Tests (all in run_area): `tests/test_pillars.py` 67 (cities + nq), `tests/test_tickrec_tiny.py` 7 (pc), `tests.test_mind_brain` 66.
    Shots: `research/handoff/2026-11-24/pillars/shots/` (390 x 844 @2x, fixture = the Accounts test's real-shape post + a glance + the tick line).
