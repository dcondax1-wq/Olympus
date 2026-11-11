# POLIS: 25 things that make OLYMPUS a modern Ancient Greek civilization (owner 2026-11-11)

Owner: "It should look like a modern Ancient Greek civilization ... find 25 things you could add at least."
The idea: marble, bronze, gold leaf and painted clay, but lit like now (glass, light, motion, live data).
Not a museum, not neon. A living city-state that runs the owner's money. AGORA look (`docs/DESIGN_AGORA.md`).
Everything is original and drawn in code or from CC0 sources (rows in `docs/ASSETS_LICENSES.md`).

## A. The look (agent "Polis kit": shared files `olympus/polis-*.js|css`, demo `olympus/polis-lab.html`)
1. **Meander (Greek key) borders** that draw themselves on load and run like a ticker on live cards.
2. **Column frames**: Doric / Ionic / Corinthian capitals and fluted shafts as SVG card frames; the order shows rank (Doric = normal, Ionic = good, Corinthian = record).
3. **Carved inscription type**: titles cut into marble (inset shadow, chisel serif, Greek-style letter spacing), numbers can show as Greek numerals on hover.
4. **Painted pottery art**: black-figure / red-figure SVG illustration set (owl, laurel, trireme, bull, horse, lyre, torch, amphora, warrior, scales) used for icons and empty states.
5. **Mosaic backgrounds**: procedural tessera mosaics (waves, rosettes, dolphins) as quiet page backdrops; denser under hero sections.
6. **Owl tetradrachm coins**: dollars shown with a minted coin; wins flip a silver coin, losses dull it to bronze.
7. **Attic calendar**: every date can show the Attic month and day ("Pyanepsion 21") next to the normal date.
8. **Sundial clock**: the session clock as a sundial whose shadow tracks the real New York time (RTH and Asia marked as hour lines).
9. **Oil-lamp loader**: loading states are a clay lamp whose flame grows; no spinners.
10. **Laurel and olive marks**: laurel wreaths for passes / records, olive sprigs for steady weeks; animated gold leaf on new records.

## B. Civic life (agent "Polis life": build script `tools/polis_build.py` -> `polis.json`, shared `olympus/polis-life.js`)
11. **The Herald**: important moments are cried out by a herald banner with a short line (eval passed, trade closed, Kalshi fill), reading published JSON only.
12. **Oracle of the day**: the morning game plan written as a Delphi reading (plain words under it), with the facts it is based on.
13. **Festival calendar**: market events as festivals (FOMC = Panathenaia, CPI = Dionysia, NFP = Thesmophoria, roll week = Synoikia) with a countdown.
14. **Torch relay streak**: the run of green weeks / rule-kept days as a torch passed runner to runner; the flame dies on a break.
15. **The olive grove**: each account is an olive tree that grows rings and fruit with equity; a funded account is a full tree.
16. **Amphora of every trade**: each closed trade becomes a painted amphora (scene picked from the trade: long = rising horse, short = diving dolphin), shelved by month in a storeroom.
17. **Hall of statues**: the best trades and passes stand as statues with a carved plaque (date, $, R).
18. **Stoic line of the day**: one short public-domain line (Marcus Aurelius, Epictetus, Seneca) picked by the day's state (after a loss: on patience; after a win: on not getting greedy).

## C. The city (agent "Polis home": new app `polis/` + 2.5D skyline module `olympus/polis-skyline.js`)
19. **Acropolis skyline**: a layered painted skyline (Parthenon, stoas, theatre, harbour) that follows the real sky over New York (dawn, noon, dusk, night, weather).
20. **City map of OLYMPUS**: every app is a building on a hill map (Trading on the Acropolis, Money at the harbour and mint, Life in the gardens); tap a building to enter.
21. **Districts light up with activity**: a building glows when its app has fresh news; the treasury smokes gold when $ comes in.
22. **Citizens' rolls**: the cast of people listed as citizens with their role and deme (team), linked to the People system.
23. **The assembly (ekklesia) board**: open decisions for the owner shown as motions with a vote stone (read-only: shows the proposal and the numbers).
24. **Harbour of the bots**: LIT, ATLAS, BLITZ and the Kalshi bot as ships in the harbour: in port (off), under sail (on), returning with cargo (P&L).
25. **Night sky of myths**: at night the skyline sky shows Greek constellations (Orion, the Pleiades, Draco) drawn from real star positions, and a shooting star on a new record.

## Rules for the three agents
- Paper only; read published JSON only; never touch engine/, live_model*.json or bot code.
- New files only (other agents are rebuilding characters, environments, scene direction and AGORA v2 right now). Do not edit `sw.js`,
  `tools/build_web_dashboard.py`, `jarvis/apps.js` or the `olympus.js` APPS table; list the "wiring needed" in your report.
- ES5, works on an iPhone, respects reduced motion, LITE mode, 44 px taps, no console errors, no external CDN at run time.
- Show the work: screenshots in `docs/shots/polis/` read back and judged by the agent itself before reporting.
