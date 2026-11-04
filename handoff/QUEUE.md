# The week queue for ChatGPT / Codex (quality work, no Claude needed)

Owner goal: every OLYMPUS app looks and feels great on an iPhone, and helps him make money. Work top to bottom.
One task = one branch `chatgpt/<task-id>` = one pull request. Read `handoff/CODEX_RUNBOOK.md` first (how to test, how to finish).
When a task is done, change `[ ]` to `[x]` here in the same PR and add one line under it: what changed, how you checked.

## Rules that never change
- Paper only. Never touch `engine/`, `live_model*.json`, `.github/`, `sw.js`, `tools/build_web_dashboard.py`, `jarvis/apps.js`,
  the `APPS` table in `olympus/olympus.js`, or any secret. A bot guard blocks the PR if you do.
- Stay inside ONE app folder per PR (`tools/web_public/<app>/`) plus its test in `tests/`. Shared kit files (`olympus/*`) only if the task says so.
- Money wording: eval cards say "Drawdown left $X of $max loss". Never "X of 10 days". Every R figure sits next to its $.
- Never blank: every view has demo data and an empty-state sentence. Taps >= 44 px at 390x844. Plain words, no jargon.
- Say honestly what you could not check (no real iPhone here).

## P1: fix what the owner said looks bad (do these first)
- [ ] **cities-layout**: `tools/web_public/cities/`. Hub shows tiny dim clusters in a huge empty void and clipped group labels
      ("BSIDIAN", "RE", "MONE"). Make the first screen look like a lively night map of cities: bigger clusters, labels fully on screen,
      the 3 most interesting cities named, fill the void (denser layout, camera framing so everything fits 390x844).
- [ ] **datacity-look-check**: `tools/web_public/datacity/`. The owner said Data City looked worse tonight; the lead restored the full profile for phones
      (`caps.js` profileOf). Compare screenshots at 390x844 `?q=high` vs `?q=high&phone=1`, keep the richer look, and find any other
      thing tonight made worse (labels, density, colours). Report with before/after screenshots in the PR description.
- [ ] **kalshicity-look**: `tools/web_public/kalshicity/`. Same pass: the city should look rich on first open, not sparse.

## P2: look and feel, one app per PR (screenshots at 390x844 before and after in the PR)
- [ ] oracle, odeon, fates, labyrinth, hephaestus, prometheus, pantheon, arena, tree, tyche, hermes, athena, ares, plutus, forum, argus,
      nemesis, chronos, mind, ledger, inbox, journal, settings: open each at 390x844 (`?demo=1`), list what looks flat, empty, clipped or
      too small, fix the 3 worst. Keep the draw-call budget in `tests/test_olympus_kit.py` (PERF table).
- [ ] Every app: first-screen answer to "what do I do right now?" in one plain sentence at the top.

## P3: money features (read-only, from already-published JSON)
- [ ] **ledger-import**: Ledger: paste-a-CSV import of payouts/fees (client-side only, nothing sent anywhere), with a preview and undo.
- [ ] **journal-weekly-card**: Mnemosyne: Sunday review card with the one rule for next week, copy as Markdown for Obsidian.
- [ ] **athena-more-drills**: Athena Train: 10 more "read the chart" drills from `research/lab/backtest_live.json` via `tools/athena_drills.py`.
- [ ] **plutus-what-if-buy**: Plutus: "if I buy another ATLAS 25K now" card using `plutus/roadmap.json` numbers (no new numbers invented).

## P4: bridge jobs (ChatGPT's own creative work, see the Bridge page for the 78 jobs)
- [ ] Do the Bridge money jobs first (prop-firm rules digest, payout rules, discount codes WITH sources, CME holidays, NQ roll dates).
      Put results in `handoff/inbox/<job-id>/` with a `DONE.md`. Mark anything unverified as UNVERIFIED.

## P5: UNFINISHED from the overnight sprint (Claude ran out of room: do these)
- [ ] **gate-full-run**: run `python -X utf8 tests/run_gate.py` on a quiet machine, write the table to `research/handoff/<date>/gate.md`, fix every real FAIL
      (not the sandbox-only software-3D "high tier draws 3 passes" checks: list those as UNVERIFIED). Only 34 of 68 suites ran.
- [ ] **hub-look-test-clock**: `tests/test_jarvis_hub.py` part `look` (What's new check) fails when run 01:45-02:00 or 09:15-10:00 ET because a bots card appears first.
      Make the page in the test switch the scheduled bot cards off (see how `test_jarvis_talk.py` does it). Tests only.
- [ ] **odeon-reduced-motion-wait**: `test_odeon_page` "d. reduced motion still plays the reel" waits a fixed 1 s: make it wait for the clock to move.
- [ ] **themes-test-rerun**: `tests/test_olympus_themes.py` baseline `tests/fixtures/olympus_default_vars.json` was edited by hand for the a11y contrast fixes
      (Tree --dim/--faint, Zenith --muted): re-run the full test and fix anything else it flags.
- [ ] **planner-webkit**: Planner (published separately from the `planner-backup` branch) was never tested in WebKit or by the crawler: test it and report.
- [ ] **kalshicity-reads-whatif**: the Kalshi City page only fetches 5 files; let it also show the `whatif.json` and `forward.json` strips (optional files, never blank).
- [ ] **root-worker-offline-olympus**: the root dashboard offline loses `olympus/themes.js` and icons because `olympus/` is skipped by the root worker.
      Write the proposal in `handoff/inbox/root-worker-offline/QUESTION.md` (do not edit `sw.js`: the owner/Claude does).
- [ ] **cities-fixture-drift**: `tests/test_cities_page.py` "catalogue and fixture are reproducible" rewrites `cities/fixture.json`: make the generator deterministic and the test compare without rewriting.
- [ ] **argus-arena-high-tier**: Argus and Arena "high tier draws 3 render passes" fail only on software GL. Make the test skip with a clear message when the renderer is SwiftShader, and say so in the PR.
- [ ] **hermes-argus-404**: Hermes `datacity/discoveries.json` and Argus `cronos/status.json` 404 on a bare site: write the proposal to make them optional site files in `handoff/inbox/optional-site-files/QUESTION.md`.

## P6: MORE GRAPHICS on every arena (one app per PR; keep the draw-call budget in `tests/test_olympus_kit.py` PERF; LITE must stay cheap; screenshots 390x844 high + low)
Use the shared effects: `olympus/fx-*.js` (42 effects, `data-oly-fx` attributes: see `docs/OLYMPUS_RENDER.md` and `docs/OLYMPUS_DESIGN.md`), `fx-atmos.js` (shafts, dust, embers, contact shadows, polished floor), `render.js` and `materials.js`.
- [ ] **arena-graphics**: stands lit by torches, waving banners, a sand floor with footprints after each trade, confetti on a win streak, a gold scoreboard sign.
- [ ] **oracle-graphics**: drifting incense smoke, animated prophecy runes on the floor, price-level pillars that glow when price is near, a dawn-to-dusk sky tied to the ET clock.
- [ ] **odeon-graphics**: stage spotlights that follow the replay, a curtain that opens on load, audience silhouettes, a gold laurel burst on a winning trade.
- [ ] **fates-graphics**: threads with moving light pulses, a loom with a turning spindle, a mist layer, a slowly rotating constellation backdrop.
- [ ] **labyrinth-graphics**: flickering torchlit walls, fog in the corridors, a glowing runner trail, a minotaur eye on the danger sheet.
- [ ] **hephaestus-graphics**: forge sparks on each setting change, heat shimmer, ingot colour = risk level, molten metal drip.
- [ ] **prometheus-graphics**: fire that grows with the champion's score, ember trails between generations, lineage lines as glowing threads.
- [ ] **pantheon-graphics**: gods as lit statues with rim light, a cloud layer under the temple, lightning when the Council flips lean.
- [ ] **tree-graphics** (Daphne): falling leaves, light through the canopy, branch glow where a rule holds in both halves, seasons by month.
- [ ] **tyche-graphics**: spinning coins with real reflections, a roulette wheel for the day's pace, gold dust on a win, dim smoke on a loss day.
- [ ] **hermes-graphics**: winged messenger trails across the sky for each recap, wind streaks, speed lines on a fast pass.
- [ ] **athena-graphics**: an owl on a column with eye glow, floating scrolls that open on tap, library dust in light beams, shelf lights in the topic colour.
- [ ] **ares-graphics**: war banners that ripple, a spear forest on the horizon, a heat-red sky when drawdown is low, a shield that cracks as drawdown shrinks.
- [ ] **plutus-graphics**: a bigger vault with coin showers on a payout, polished gold reflections, a pulse ring around the month's net.
- [ ] **forum-graphics**: marble columns with sun shafts, banners with the trading-day countdown, a crowd silhouette at the base.
- [ ] **argus-graphics**: a hundred-eyed sphere whose eyes open as gates go green and close red, a scanner beam, a status constellation.
- [ ] **nemesis-graphics**: scales that tip with the leaks, dark smoke, red cracks on the floor for the biggest leak.
- [ ] **chronos-graphics**: clock gears that turn at the session pace, sand falling for the time left, a sun and moon arc by ET time.
- [ ] **mind-graphics**: a neuron galaxy with pulses along links, new notes that bloom as stars, a calm nebula background.
- [ ] **datacity-graphics**: skyline lights that change with VIX, rain or fog by regime, taxi trails, neon signs per district, a day/night cycle (keep the full-detail look on phones).
- [ ] **cities-graphics**: the first screen must look like a living map: skylines in each cluster, flights between clusters, glowing roads, bigger labels fully on screen.
- [ ] **kalshicity-graphics**: lit towers for edges, a river of money through leaks (red) and edges (gold), a clock tower for fees.
- [ ] **ledger-graphics**: a vault door that opens on first open, gold bars stacking with net profit, red cracks on a loss month.
- [ ] **inbox-graphics**: letters flying into a glowing mailbox, unread orbs that pulse, a calm background.
- [ ] **journal-graphics** (Mnemosyne): a memory pool that ripples when you rate a trade, neuron links between days, mood colours.
- [ ] **settings-graphics**: a control-room look with glowing switches (keep it light and fast).
- [ ] **zenith-graphics**: a hero card with an animated price ribbon, depth glass cards, glow edges that follow the green/amber/red status.
- [ ] **launcher-graphics**: tiles with their own tiny animated glyph and a starfield behind the sheet.
- [ ] **intro-films**: make each per-app intro (`olympus/intro-app.js`, FLAVOUR table) unique to its app (<= 2.4 s, skippable, silent unless sound is on).
- [ ] **transitions**: `jarvis/transitions.js`: more distinct arena-to-arena transitions (portal, lightning, coin burst, smoke wipe), all <= 1 s, none in LITE or reduced motion.
- [ ] **fx-library**: add 10 NEW effects to the shared library (god-ray volumetrics, heat distortion, water ripples, snow, lightning arc, gold shimmer, glitch, hologram scan, smoke columns, fireworks), each documented and with a LITE fallback.

## P7: MORE features that help the owner make money (read-only, plain words)
- [ ] **zenith-weekly-money**: a Zenith "This week" card: trades, net $, drawdown left, days to the next payout window.
- [ ] **ares-pass-planner**: Ares "what do I need to pass": sessions left x $ per session against the 2-4 trades a week plan.
- [ ] **forum-news-guard**: Forum shows high-impact news today and which falls inside the bot's 02:00-15:30 window.
- [ ] **plutus-payout-calendar**: a payout calendar using the MFFU rules in `research/props/mffu_rules.json`.
- [ ] **kalshi-sizing-card**: Kalshi "safe bet size" card using the risk-of-ruin numbers (suggestions only).
- [ ] **obsidian-sync-check**: a Mind card that checks the Obsidian starter pack is current (`tools/obsidian_pack.py --check`) and says what to do.

## Done log
(add one line per finished task: id, PR number, date)
