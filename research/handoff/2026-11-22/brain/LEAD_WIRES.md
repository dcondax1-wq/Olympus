# Research Brain: lead wires (day-brain4, 2026-11-22)

The brain lives at `cities/brain.html` (inside Data City's folder: no APPS entry, no sw.js change: `cities/` is already an "own folder" in
`OTHER_APPS`). Nothing below edits a forbidden file; these are the lines only the lead may add.

1. **A door to it** (one tap from Data City). Add to the Data City top row / chip strip (wherever the lead places Data City links):
   `<a class="chip" href="brain.html">Research Brain</a>` in `tools/web_public/cities/index.html`
   (or from Jarvis: in the `cities` app card add `{ url: '../cities/brain.html' }` only if the lead wants it as its own tile; no APPS line is needed otherwise).
2. **Rebuild the neurons before each site build** (they follow LEDGER.md + TESTED_AND_REJECTED.md): in `tools/ship.py` (or the lead's build step) run
   `python tools/build_brain_hub.py` first; `python tools/build_brain_hub.py --check` exits 1 when `cities/brain-data.json` is stale.
3. **Write-up links** point at `../writeups/<name>.md`, which the build already publishes (`build_web_dashboard._docs` -> `<site>/writeups/`).
4. **Pulse sweep** reads `../home.json` then `../data.json` (public, same-site, optional): a non-empty `open_position(s)` / `positions` / `in_trade`
   in `board` or `live` = LIVE TRADE badge + sweep. If the lead's JSON uses another key, edit `findLive` in `cities/brain.js`.
5. Optional `tools/perf_budgets.json`: `"brain": {"eager_js_kb": 40, "three": true}` if the lead wants it tracked as its own page (it is not an app, so
   `perf_sweep --static` does not list it: 0 over budget today). Tests: `python tests/run_area.py cities` runs `tests.test_brain_hub` (33 checks).
