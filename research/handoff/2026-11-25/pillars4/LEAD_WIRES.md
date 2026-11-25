# day-pillars4 (2026-11-25): pillars more 3D, more data, organized; Brain reads the brain feed first (lead-only wiring)

Owner (2026-11-25): "I want the pillars to be made more 3D, more quality, more data, make everything more organized, more research."
Branch `day-pillars4` (from origin/pc 94341394). Helpers never edit sw.js, build_web_dashboard.py, jarvis/apps.js, the olympus.js APPS table.

## Wires (lead)
1. **`tools/web_public/sw.js`**: bump `CACHE` `le-public-v217` -> `le-public-v218` (`python tools/bump_versions.py --check --base origin/pc`
   asks for exactly this one; every `?v=` is already bumped). If the shell list names pages, add `pillars/data.html` (new page).
2. **`tools/build_web_dashboard.py`**: run `python tools/build_pillars.py` before the copy (pillars-data.json now carries `rejected` per
   pillar from docs/TESTED_AND_REJECTED.md, `rejected_shared`, `mill` from research/ideamill/summary.json, ORDER FLOW `progress`; it goes
   stale whenever those files change: `--check` exits 1). The whole `pillars/` folder ships (new: data.html, data.js, data.css, datacore.js,
   today.js, todaycore.js). Nothing else new.
3. Optional `olympus/gate-catalog.js` row (Home "Go to" search): `['pillardata', 'pillars/data.html', 'Pillar data', 'Each pillar in numbers', 'trades $, week / month, win rate, PF, next setup, verdicts', 'bots', 'bots', 'pillar data trades win rate profit factor pf month week verdicts rejected idea mill order flow looks', 'nq']`
4. Publish as usual and open `/pillars/`, `/pillars/data.html#lit`, `/brain/#lit`, `/gate/` on the phone.

## What changed
- **Per-pillar DATA page** `pillars/data.html#lit|atlas|blitz|of` (model `datacore.js`, pure, node-tested): header Home › Pillars › LIT
  with a 44 px back to the pillar; 4 pillar tabs; live status + accounts with today $; **Money**: this week / this month $, win rate, PF,
  all-time + avg R, a real-$ sparkline, the open trade (REAL closed MFFU trades only: trading/trades.json src live + the PC post's newest
  `lite.at` rows, de-duped; paper twin listed, never counted); **last 10 trades**; **Next setup** + steps (the brain feed first, its age chip),
  limit / stop / target, link to the Brain room; **What it learned** (research/learn via brain/learn.json + the weekly lessons);
  **Research**: backtest spans, `Tested and rejected: N` with the newest 12 rows for that pillar, the idea mill (56,160 ideas, 31,724
  scored, 0 passed); ORDER FLOW: tick days N/60 (PC), looks used 0/2 (pre-registered), battery 0/40, the 3 designs. With no PC post the
  live parts show the Brain fixture labelled SAMPLE; money / trades / research are always the real files.
- **Brain** (`braincore.js`): reads `status.bf` (`lite.bf.bots[id]`, engine/brain_feed) BEFORE the glance for next / think / levels
  (`[{name, done}]` steps: first open = now; `"6/10"` tight form; `"HH:MM words"` think lines; a bot with `{err}` falls back), `feedAge`
  (<= 20 min green, <= 45 gold "late", older red "OLD: this is where the bot was then") shown as a chip on top of Next trade with the ET
  time, `M.market` from bf.market. Header now solid (content no longer shows through), crumbs Home › Pillars › LIT Brain, back returns
  to that pillar, a "LIT data ›" link in each pillar room.
- **Home Today strip** (`pillars/today.js` + `todaycore.js`, mounted in gate/index.html under the pillars band): Today $ (sum of the
  accounts), each account's today $, the open trade, the next setup (brain feed first), each a link (Accounts / Brain / data page).
  It has zero layout height (sits in the gap above the search): search 152, 6 dashboards 228, More 844 unchanged.
- **Pillars page**: back = Home (`../gate/`, was `../nq/`), Home › Pillars crumbs, one-line header at 390 (War Room = 44 px gold ⚔ square
  under 460 px, its label kept for screen readers; the owner quote shows on wider screens), a "go deeper" row under each pillar's name
  (LIT data / Brain room / Trades or Research), footer: Pillar data, Brain, Trades.
- **3D temple** (`pillars-scene.js` c2): hq columns 12 segments per flute x 96 rings, procedural marble veins + gold thread + chisel
  grain, finer gold capitals (necking rings, bead ring, top plate), a light shaft per column in its colour (brighter live / tapped, one draw
  call), GPU dust in the shafts, more sparks on live columns, tap = glide + small orbit settle + push-in, **depth of field on the tapped
  column** (hq + WebGL2 only). Draw calls hq 18 / low 12 (cap 24). Low tier unchanged.
- **Brain 3D** (`brain-scene.js` b3): the temple's HDR bloom, a breathing glow per region (brighter with its pulse / when it fires, others
  dim on select), 56 tracts with travelling signals (hq; 28 low), 8,000 neurons (hq), 520 GPU dust motes, fly-to + orbit settle, depth of
  field around the selected region (hq only); tiers hq -> DPR 1.25 -> no bloom -> low (software GL starts low). Draw calls 8 (cap 10).
- **Brain ticker fix**: a re-render while the newest thought was still typing took the half-typed text as the whole line ("Ch"); each line
  now carries `data-full`. Crumb links are 44 px tap targets on Brain / Pillars / data pages.
- **ORDER FLOW colour** `#5fd0c9` (cyan) -> lilac `#c9a7ff` everywhere (pillars, Home + Zenith chips, Strategy Brain, Research Hub).
- Versions: pillarscore / pillarsfeed p4, pillars.js c2, pillars.css c3, scene c2, hero.js c3 (gate, Zenith, NQ), mindcore m6, mind.js m9,
  hub.css h4, brain.js / brain.css b5, brain-scene b3, braincore b3, pillars.css c4, data.js d3 / data.css d3 / datacore d2, today t1.

## Tests
test_pillars 116/116 (new section p: 33 checks: static, data vs sources, node datacore / todaycore / braincore bf, browser data pages,
Pillars row, Home strip layout, Brain feed age; pillars_browser.cjs now waits for data-mode + a drawn frame: software GL is slow here),
test_brain_app 70/70 (3 new brain-feed checks), test_pillars_hero 30/30, test_warroom 27/27, test_nq_page 52/52, smoke 11/11,
test_gate_page static 35/35 (its browser half needs Python Playwright, not installed in this container; the Home layout is pinned by test_pillars p + test_pillars_hero b).

## Shots
`shots/before/` vs `shots/after/` (390 x 844 @2x): 01 Pillars hq, 02 tap ATLAS (DOF), 03 Home (Today strip), 04 Pillars panel (go-deeper
row), 05 LIT data (+05b full, 05c ATLAS), 06 ORDER FLOW data, 08 Brain LIT room (brain feed age), 09/10 Brain hq. `shots.cjs` re-makes
the before set; the after set comes from `PILLARS_SHOTS=<dir> python -X utf8 -m tests.test_pillars` (the test's real-shape PC post).
