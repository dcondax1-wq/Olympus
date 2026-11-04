# KALSHI CITY

A night city built from the Kalshi bot's bets, plus the engine that keeps learning which slices of those bets have an edge. Read only: it reads the public
`kalshi-feed` (`kalshi.json`), never calls Kalshi, never holds a key, never places an order.

| Piece | File | What it does |
|---|---|---|
| The engine | `tools/kalshi_edges.py` | reads `kalshi.json`, keeps every bet it has ever seen (`ledger.json`), re-measures every edge, writes `edges.json`, appends dated lessons to `learning_log.json`, writes `jarvis.json`. `--orders FILE.csv` adds the one-off order export (hour-of-day edges) |
| The refresh | `.github/workflows/kalshicity.yml`, `tools/cronos/registry.py` | every 6 hours, state on the `kalshicity` branch, the three site files pulled into `kalshicity/` at every publish (CRONOS, `docs/CRONOS.md`) |
| The demo | `tools/kalshi_demo.py` | 1,500 invented bets with planted edges -> `fixture.json` (the DEMO city, offline) |
| The lessons | `tools/kalshicity_learned.py` | `research/kalshi/edge_tables.json` -> `learned.json` (the "What we learned" sheet; the page writes the words from the numbers) |
| The page | `tools/web_public/kalshicity/` | `cityfeed.js` data, `citylayout.js` where everything stands, `cityscene.js` the 3D city on the OLYMPUS render core, `cityfx.js` the effects, `cityrig.js` cameras, `lessons.js` lessons + ask card, `kalshicity.js` the page |
| Tests | `tests/test_kalshi_edges.py`, `tests/test_kalshicity_page.py`, `tests/test_cronos.py` | engine maths vs an independent mirror (50); modules in node + the page at 390 x 844 incl. effects, sound, lessons (60+); CRONOS wiring |

## What an edge is
Any 1 to 3 of five dimensions fixed (the rest `*`): strategy, market, hour (ET, 4 h block), price band (the bot's own edges), side. Per edge: n, win rate vs the
market's implied probability (mean entry price), EV per $1 staked (realised, fees in), Wilson 95% range, a z-test of wins against sum(price), the 7 / 30 day
windows, the decay, Kelly (full, safe on the Wilson low end, quarter of safe), the stake in $, the chance of losing half the bankroll at that stake (Lundberg bound
on the Wilson low win rate), and a status: NEW (< 30 bets: grey, no stake), GROWING, HOLDING, DECAYING, DEAD. Advice: DO MORE (proven, z >= 1.645, sized), KEEP,
WATCH, STOP (DEAD), COLLECT (too few bets).

The feed carries only the last 40 bets, so the engine **accumulates**: each run adds the bets it has not seen. The feed's whole-life totals (strategies, markets,
price bands) are edges too (`src: feed`; the implied price is the band's mean price or the break-even rate w / (1 + EV)); a daily snapshot of those totals gives them real
7 / 30 day windows after a week. Combinations that hold exactly the same bets as a simpler edge are dropped. Run every <= 6 hours or bets are missed (the feed window is
about a day; `ledger.seen_share` says how much the engine has seen one by one).

## City
District = market (ring round Downtown, which holds strategies, bands, hours, sides). Height = EV per $1, roof glow = recent win rate, roof colour = status, windows
= bets (gold won, red lost), grey and low = n < 30, going up with a crane = a new edge, crumbling with embers = one that just died. Roads: capital out (cool cars) and back
(gold won, red lost); pink cars = open orders. Weather = last 7 days (clear / overcast / rain / storm; fog = bot paused). Day / night = New York time. Dark far towers are scenery
(no data; the guide says so). Tiers via OLYMPUS: low 700 towers, high 2,600, ultra 4,200 + bloom; reduced motion = a still scene.

## Effects (`cityfx.js`, the OLYMPUS fx library + the city's own)
| Effect | When | From |
|---|---|---|
| god rays | dusk and dawn | `OLYMPUS_FX.godRays` |
| lightning storm | weather storm, or rain with a risk of ruin >= 90%; thunder when sound is on | `OLYMPUS_FX.lightning` |
| aurora over the Vault, spire lens flare | night, no storm | `OLYMPUS_FX.aurora`, `lensFlare` |
| sun / moon lens flare | follows the hour | `OLYMPUS_FX.lensFlare` |
| neon signs | the tallest edges named in neon (flicker = fading, STOP = dead) | own sprites |
| wet streets | rain: every glowing building leaves a neon reflection streak, the ground turns glossy | own instanced quads + ground roughness |
| fireworks | a new DO MORE edge in today's log | own GPU points |
| edge scanner | the engine learned something new (once per new batch, every 5 min refresh, the round button): ring + sweep from Downtown, the new edges' buildings pulse | own |
| sound | the note button (off by default): ambience pad, thunder, tick on a building, portal on a camera change, rank-up on fireworks | `OLYMPUS.sfx` |
Budgets: the library effects follow `OLYMPUS_FX.tier()` (low: 3 god-ray cones, 2 aurora sheets, <= 400 particles); reduced motion or `off` = no moving effect (the signs and the streaks stay as stills).

## Wiring the lead does (this folder only adds files)
1. `olympus/olympus.js` APPS: `kalshicity: ['Kalshi City', 'K', '#2ef2d0']`
2. `jarvis/apps.js`: `app('kalshicity', 'Kalshi City', 'money', '#2ef2d0', "The Kalshi bot's edges as a night city", { glyph: 'K' })`
3. `tools/build_web_dashboard.py` app tuple (line ~1212): add `"kalshicity"` (without it the folder is not published and the CRONOS pull has nowhere to land); `jarvis/sw.js` bump if it lists apps.
4. Done in the repo (CRONOS): `.github/workflows/kalshicity.yml`, the registry task, `tools/cronos/site.py` BRANCHES, `docs/CRONOS.md`. The first workflow run seeds the `kalshicity` branch from the
   committed files in `tools/web_public/kalshicity/`; run it once by hand (Actions, kalshicity, Run workflow).

## Refreshing the lessons
`python tools/kalshi_research.py` (the research agent's script) then `python tools/kalshicity_learned.py`. After the owner's CSV export:
`python tools/kalshi_edges.py --feed <kalshi.json or the live address> --orders orders.csv`.
