# Lead checklist for Monday's landing (2026-11-23)

Built by night-leadwires from every `research/handoff/2026-11-2[23]/*/LEAD_WIRES.md` on every origin `night-*` / `day-*` branch
(17 files, read with `git show origin/<branch>:<path>`), `research/handoff/2026-11-23/INTEGRATION.md` (night-integrate), and the
"lead" notes in the open branches' commit messages. "Done" was checked against `origin/land-fixes` (L) or `origin/night-integrate` (I) at
04:30 UTC. Nothing lead-only was edited here.

**Land through `night-integrate`:** it already merges notify(-rt), payout(-rt), cleanup(-rt), site-land / hub2, startfix, truth, clockauto(-rt),
zerotouch(-rt), reds, payplan, fleetmgr-rt, r50k-rt and rulewatch-rt. It also already resolved the cross-branch clashes: TEST_ALERT path,
zerotouch's old .bat paths, EVREOD, and the fsutil.replace rule. **Not in it:** night-pcguard, night-blitzfills, night-brief, night-decide,
night-docs, night-hermetic, night-roll, night-tasks (no -rt review yet).

## A. Required for Monday

| # | File | Exact edit | Branch(es) | Why Monday |
|---|---|---|---|---|
| A1 | `tools/web_public/sw.js` | `const CACHE = 'le-public-v208'` -> `'le-public-v209'` (or +1 on whatever L has at landing) | every site-changing branch (home6, redsweep, truth, startfix, hub2, cleanup's pc/ kit copies) | phones drop the old shell. The v187 ask in home6 is superseded: L is already v208 |
| A2 | `web_next/sw.js` | `const SHELL = 'le-shell-next-v60'` -> `'le-shell-next-v61'` | night-startfix (start.js Re-arm line + last result), night-integrate (one start.js string), night-zerotouch (start text: the phrase also turns keep-alive on) | the Start page is the Monday screen. `app.js` imports `./next/start.js` with no ?v=, so only the SHELL bump refreshes it |
| A3 | `tools/ship.py` (or the nightly build step) | before the site build: `python tools/build_brain_hub.py` then `python tools/build_research_hub.py` (in that order: hub reads brain-data.json) | day-brain4 (brain #2), night-hub2 (#1) | `tests.test_brain_hub` a and `tests.test_research_hub2` go red on a stale file (night-reds rebuilt brain-data by hand tonight). L has neither line |
| A4 | owner, PC (hands) | after the PC takes pc: **MONDAY_SETUP.bat** (I: update -> clock UAC "Yes" -> START + the typed phrase, which now also turns keep-alive ON -> alert test). Without I: UPDATE.bat, FIX_CLOCK.bat right-click > Run as administrator once, START_BOT.bat + phrase, KEEPALIVE_ON.bat + KEEP ALIVE ON, tools\bat\TEST_ALERT.bat | clockfix #3, zerotouch, tradehome | the clock guard blocks entries above 5 s. Rapid / 25K #2 need the phrase to arm |
| A5 | lead decision | **MONDAY_SETUP.bat at the top** (I: 13 top files, `tests/test_bat_menu` KEEP 13) **or** `tools/bat/` + a TRADE_HOME number | zerotouch vs cleanup | the integration kept it on top. Either way, test_bat_menu and docs/BAT_FILES.md must agree |
| A6 | `engine/monday.py` (only if night-pcguard lands Monday) | the clock step's skip `when the task OlympusClock exists` -> `when OlympusClock exists AND engine.win_guard.status()["on"]`; step text 2/4 "Clock + Windows guard" | night-pcguard #1 (needs zerotouch first: merge pcguard on top of I) | the owner's PC already has OlympusClock, so with zerotouch's skip the new Windows guard would never run there |

## B. Optional (better, not blocking)

| # | File | Exact edit | Branch |
|---|---|---|---|
| B1 | `tools/web_public/jarvis/apps.js` (after the `fates` line) + the same entry in the olympus.js APPS table | `app('tradehome', 'Trading Home', 'trading', '#f1c14b', 'Today: bot, keep-alive, alerts, accounts, next $', { url: '../nq/trading_home.html', glyph: '⌂' }),` | day-tradehome #1 (not on L) |
| B2 | `scripts/make_shortcuts.ps1` `$items` (next to 'LE STOP BOT') | `@{ Name = 'LE TRADING HOME'; File = 'TRADE_HOME.bat'; Icon = 27; Tip = 'One menu: status, start bot, keep-alive, add account, alerts, stop, update' }`, then run `tests.test_win_scripts` once on the PC side | day-tradehome #4 (not on L). Compatible with cleanup: TRADE_HOME.bat stays at the top and test_bat_menu e only checks that shortcut targets exist at the top |
| B3 | Trading Home "Today" line (apps.js / `nq/trading_home_core.js`) | when `pc.glance.bots[i].nar` exists, show it instead of the bare "armed false" | day-armfix (not on L) |
| B4 | `tools/pc_feed.py` CORE_OWN + `nq/trading_home_core.js` alerts row | core `"al": 1 if snap.get("alert_bus") else 0`; read `lite.al` | day-tradehome #5 (not on L) |
| B5 | `tools/build_web_dashboard.py:1343` | `... until the PC runs RUN_MONEY.bat)` -> `... until the PC runs tools/bat/RUN_MONEY.bat)` (print text; test_bat_menu ALLOW lists it) | night-cleanup / night-reds |
| B6 | `CLAUDE.md` "Where things are" | `` `git push\n  origin HEAD:pc` `` -> `` `git push https://github.com/dcondax1-wq/Olympus HEAD:pc` `` (docs/AUTO_UPDATE.md already says so) | night-truth E4 |
| B7 | `tools/web_public/mind/index.html` | `mind.css?v=m5g` -> `m5h` (the #top column fix). Still m5g on L | day-a11y redsweep #2 |
| B8 | `tools/web_public/cities/index.html` | Brain chip is done on L and the Hub half-bar is done on I. Optional Jarvis tiles in the `cities` card: `{ url: '../cities/brain.html' }`, `{ url: '../cities/hub.html' }` | day-brain4 #1, night-hub2 #2 |
| B9 | `tools/perf_budgets.json` | `"brain": {"eager_js_kb": 40, "three": true}` | day-brain4 #5 |
| B10 | Start page JS (`web_next/js/next/start.js`) | show `clock.fix` under the clock row (clockfix #2); show `status().keepalive.on` under Armed (zerotouch); `engine.win_guard.line()` (pcguard #2). Each needs A2's SHELL bump again | clockfix, zerotouch, pcguard |
| B11 | `ADD_ACCOUNT.bat` | Lucid item 6: `echo   6  New LucidPro 50K eval ...` + `if "%c%"=="6" ( "%PY%" -X utf8 -m engine.accounts add --plan lucidpro50k --name "%NAME%" )` (mirror item 5's variables). TRADE_HOME menu 4 already lists Lucid as OFF until Lucid's written OK | day-nqdash3 lucid A |
| B12 | repo secret (owner / lead hands) | Actions secret `LE_NTFY_TOPIC` = the PC's private topic (TEST_ALERT prints it), so the cloud's PC-SILENT alert reaches the ntfy app | night-notify |
| B13 | `tools/pc_report.py` `_life` | keep `"why"` (cut ~80 chars) per account so mffucenter.js's `life_why` line shows | night-truth |
| B14 | `engine/brain_glance.py` (helper job, not lead-only) | (a) a glance row for 25K #2 (`b25k_2`); (b) rapid room from plan_rules + eval.days when no broker anchor | night-truth Package C |
| B15 | PC task | `python -m agency.pipeline` before the 15-min report (writes data/agency_pipeline/summary.json). pc_report already reads `pipeline.read_card()` on L; verify the summary file is made on the PC | day-a11y pipeline #2 |
| B16 | env (cloud) | python `playwright` is not importable in the cloud containers (node's is), so kalshi_page, kalshicity_page, brain_hub b, money_pipeline c and smoke zenith_mode cannot run there | night-reds |
| B17 | `jarvis/apps.js` vs the kit APPS / page pre-paint | `tests.test_agora_audit` "accents agree with jarvis/apps.js": dionysus, nq, business differ (already red before tonight) | night-reds |

## C. Done already (no action, listed so nobody redoes them)

| Ask | Where |
|---|---|
| home6: jarvis/apps.js GROUPS = the 6 (+ MORE); olympus.js `business` -> 'Money', `cities` -> 'Data City'; bump_versions tags | L (gate.css is g25) |
| redsweep: jarvis/sw.js SHELL + nqbars / expertcore / dashfx, CACHE jarvis-v94 | L |
| pipeline: pc_report ext "ap" (EXT_ORDER, snapshot, lite) | L |
| caller: `AREAS["agency"].append("trade_scripts")` | L (night-cleanup moved the appends above `__main__`; they never ran before) |
| truth: mffumodel.js ?v=4 -> 5 in business/mffu.html and board/index.html | I |
| startfix #2 / night-reds: test_selfheal bare os.replace | day-fsutil (in L) + night-reds |
| integration: TEST_ALERT path (T menu), zerotouch's moved .bat paths, EVREOD rule, fsutil.replace in payout / fleet_mgr | I |
| payout-rt "one phone alert per payout event" | lead decision already taken (I) |

## D. Conflicts between the branches' asks, and the call

| Clash | Call |
|---|---|
| home6 asks `business: ['Money', '$', '#3b82f6']`; L has `'#f1c14b'` | keep the gold (OLYMPUS NIGHT accents, owner 2026-11-20). The blue ask predates the look |
| home6 asks CACHE v186 -> v187; L is already v208 | superseded: one +1 bump at landing (A1) |
| pipeline #3 asks sw.js to precache business/pipeline.*; `business/` is in sw.js OTHER_APPS (own folder, never handled) | **do not add**: it would be dead entries. Same for truth's "sw bump for nq/ and business/" (both own folders): the page ?v= tags are the real bump (done on I) |
| cleanup: 12 top .bat files; zerotouch adds MONDAY_SETUP.bat on top | I keeps 13 (A5, lead decides) |
| zerotouch's clock skip (OlympusClock exists) vs pcguard's guard | pcguard's rule (A6) once pcguard lands; until then the guard is not installed on the owner's PC, which is harmless (FIX_CLOCK_OFF undoes it anyway) |
| tradehome shortcut (B2) vs cleanup's .bat move | compatible: TRADE_HOME.bat is a kept top file |
| lucid ADD_ACCOUNT item (B11) vs TRADE_HOME menu 4 | compatible: both keep Lucid HELD until `engine.accounts lucid-ok` |
| 11-20 branches night-effects, night-nqdash2, night-revamp-dash, night-revamp-main still differ from L and edit sw.js / jarvis/apps.js / olympus.js / build_web_dashboard.py themselves | out of tonight's scope. Check they are superseded before any merge. Do not merge them blind: they would roll the shared lead files back to 11-20 |
