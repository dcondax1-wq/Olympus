# Strategy Brain: lead wires (day-mind, 2026-11-23)

The page lives at `tools/web_public/cities/mind/` (inside the Cities folder): **no APPS entry and no sw.js change are needed**.
`cities/` is already in sw.js `OTHER_APPS` (never cached there), and the page's one cross-origin request (three.js r160 from cdnjs)
is never touched by the worker (`url.origin !== location.origin` returns early). Nothing below edits a forbidden file; these are the
lines only the lead may add.

Already done on the branch (not forbidden): a door in `cities/index.html` next to Research Brain
(`<a class="brain" href="mind/" ...>Strategy Brain</a>`), and `tests/run_area.py` `AREAS["cities"].append("mind_brain")`.

1. **Optional Jarvis tile** (only if the lead wants it as its own app in the switcher): in `jarvis/apps.js` add an entry with
   `url: '../cities/mind/'`, name "Strategy Brain", group `trading`, door ZEUS Trading. Then `python tools/apps_list_build.py` and
   `python tools/olympus_map_build.py` (the map test fails when it is stale). Note: the id `mind` is TAKEN (the vault brain at
   `tools/web_public/mind/`), so use another id, e.g. `strategybrain`.
2. **Optional Olympus door shortcut**: in `olympus/doors.js` (ZEUS Trading door) a shortcut to `../cities/mind/` with the words
   "How each bot thinks". Not a forbidden file, but it is the lead's map, so it is left to the lead.
3. **Optional link from the NQ Brain** (`nq/brain.html`) and the Research Brain header (`cities/brain.html`): a chip
   `<a class="chip" href="mind/">Strategy Brain</a>` (from `cities/brain.html`) or `../cities/mind/` (from `nq/`).
4. **Data it reads** (all already published by the build): `../../odeon/trades.json` (the ledger + paper + replays, with each engine
   event's time and 1m bars), `../brain-data.json` (Research Brain findings; rebuilt by `tools/build_brain_hub.py`),
   `../../home.json` (`live.pc.glance`), and the PC's post via `../../pc_feed.js` + `../../status_feed.json`. When the trade file is
   rebuilt (`odeon` builder), the timelines follow by themselves.
5. **PC-side, for richer real-trade timelines** (not needed for the page to work): real / paper LIT rows in `odeon/trades.json`
   carry only `session`, `setup`, `entry`, `exit` events, so their Sweep / Inducement / CISD chips say "not recorded" (honest).
   If the PC's trade export adds the engine's `sweep` / `idm` / `cisd5` / `cisd1` events with times (as the backtest rows have), every
   step of a real trade is timed with no page change.
6. **Optional perf budget**: `tools/perf_budgets.json` `"strategybrain": {"eager_js_kb": 40, "three": true}` if it becomes an app
   (as a Cities sub-page, `perf_sweep --static` does not list it).

Tests: `python -X utf8 -m tests.test_mind_brain` (59 checks: static, node on the real trades + findings + label placement, Chromium 390 x 844 (layout, labels, low power) through Node
Playwright; `MB_NO_BROWSER=1` skips the browser, `MIND_SHOTS=<dir>` saves the shots) and `python tests/run_area.py cities`.
Screenshots: `research/handoff/2026-11-23/mind/shots/` (1 brain, 2 LIT live chain, 3 real trade timeline, 4 backtest timeline with
every step, 5 ATLAS S/R timeline, 6 the 2D fallback).

## Round 3 (Strategy Lab + Today, 2026-11-23)

7. **day-mind now contains `night-hub2`** (Research Hub v2: `cities/hub.html`, `hub.js`, `hub.css`, `hub-data.json`,
   `tools/build_research_hub.py`, `tests/test_research_hub2.py`), merged so the Strategy Lab tab could be added to it. Conflicts resolved
   in `cities/index.html` (Research Brain + Research Hub half tiles, Strategy Brain full width) and `tests/run_area.py` (both lines kept).
   The small hub follow-up `ef53e041f` (keep-alive line, on night-integrate) is NOT in day-mind.
8. **Rebuild the Strategy Lab data before each site build**: in `tools/ship.py` (or the lead's build step) run
   `python tools/build_strategy_lab.py` (writes `cities/lab-data.json`; `--check` exits 1 when stale). Once the two research sessions land
   `research/lab/popular_ict.json` / `popular_classic.json`, the next build replaces the SAMPLE fixture by itself (fixture: false, banner
   gone). The "Best add-on to LIT" is picked only from those files (never a SAMPLE row, never a LEADERBOARD LIT variant). It needs every
   span positive with PF >= 1.3 and 1-5 trades a week, and the worst span's $/month decides. Accepted shapes: a list or {strategies|rows: [...]};
   spans as {name: {tpw, win, pf, usd_mo, maxdd}}, a list, or one flat object; optional `rules` (string or list, first 3 lines shown).
9. **Today strip** reads `glog` (pc_report ext, 8 lines a bot) else the glance's 4 `log` lines a bot. Nothing new is needed from the PC.
   With more lines in `glog` (e.g. LOG_N 8 -> 24 in engine/brain_glance.py), the owner would see the whole day, not just the last 8 steps.
10. Tests: `tests/test_strategy_lab.py` (20: builder, popular-file shapes, best add-on rule, hub tab in Chromium: sort, filter, rows) added to
    `run_area cities`; `tests.test_mind_brain` now 66.
