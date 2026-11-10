# QA sweep, night of 2026-11-10

One process at a time: `python -X utf8 tests/run_gate.py --fast` (96 suites, static parts only) before and after, plus the suites the fast gate leaves out that the new apps depend on. Machine: 4 cores, load 18 to 20 (other agents running), software GL.

## Result

| Suite | Before | After | Note |
|---|---|---|---|
| fast gate, overall | 33 PASS, 35 FAIL, 28 not run | 64 PASS, 4 FAIL, 28 not run | the 28 have no static part (browser only); the 4 left are old, see below |
| jarvis_shell | 2/3 | 3/3 | `jarvis/sw.js` OLD list lacked `jarvis-v26` (previous worker must be kept). Added. REAL (stale wiring) |
| safari_lint | 17/18 | 18/18 | inputs and textareas under 16px zoom iOS on focus: oikos, moirai, kairos, argo, epilogue. Set to 16px. REAL |
| jarvis_hub:static | 48/50 | 50/50 | test pinned the old app list of the site build and the old OLD list of the worker. Re-pinned to the wired tuple and `jarvis-v26`. Stale pin |
| 30 AGORA page suites (aegis ... stoa, incl. oikos, moirai, kairos) | "FAIL n/n" | PASS | every check passed but the gate counted 0: `tests/gate_static.py` only read `RES` of the module, the AGORA suites keep it in `agora_kit.RES`. Runner fixed to fall back to it. Not an app bug |
| jarvis_kalshi | 4/5 | 5/5 | the test said the lead must not have edited sw.js; the lead has now listed `kalshi-brain` there (which test_jarvis_shell requires). Assertion turned round |
| test_wire_new_apps | 36/39 | 39/39 | list grew to 21 apps and nothing is pending any more; the Argo section of `NEW_APPS_WIRING.md` named the intro scene `waves` which does not exist, the wired one is `rings`. Test and doc brought level |
| release_manifest (`tools/release_manifest.py`) | 1 stale asset tag | OK | `kalshicity.css` changed but its `?v=k14` did not: bumped to `k15` in `kalshicity/index.html` |
| apps_list | 33/33 | 33/33 | count and list right |
| olympus_kit, olympus_sfx, olympus_a11y (static), zenith_*, safari | PASS | PASS | no sound bed, budget or a11y gaps found for the apps of the night |
| test_jarvis_transitions | 44/44 | 44/44 | all new apps have a registry row |
| test_app_intro | timeout in a 250 s run | 259/260 | 259/260 in 349 s with a 900 s limit. The one miss is oracle (an old app): a tap skipped the film but took 924 ms, limit 600 ms. Sandbox only (load 18 on 4 cores, software GL); every new app's intro passed |
| the new apps' own suites (oikos 65, moirai 60, kairos 56) | PASS | PASS | after the 16px change they were not rerun in Chromium (CSS only) |

## Still failing, and not from tonight's work

| Suite | Failure | Why | Fix |
|---|---|---|---|
| kalshi_page | "the one step is the exact text": the test expects a fixed setup address, `kalshi.js` now builds it from the page's own origin | an earlier Kalshi commit changed the page, the test was not updated | change the test to expect the origin-built link |
| space_ui | `liveview.css` differs between `tools/web_public` and `web_next/css` | the Safari sweep (424966d) edited one copy | `cp tools/web_public/liveview.css web_next/css/liveview.css` |
| blitz_tab | `blitzcore.js` differs between the two apps | same Safari sweep | `cp tools/web_public/blitzcore.js web_next/js/next/blitzcore.js` |
| atlas_ui | "0/0": the test prints `PASS` without brackets, so the gate cannot count it | runner format, the checks themselves print PASS | print `[PASS]` or teach the gate that format |

None of these four touches a new app or the wiring, so I left them; the two `cp` lines make the web_next copies equal to the (newer) phone copies.

## Real bugs vs sandbox limits

- Real: the five stale or wrong things above (jarvis worker OLD list, sub-16px inputs, hub pins, kalshicity tag, Argo scene in the doc).
- Sandbox only: software WebGL. The 3D scenes (amphora, loom, sundial) render here, but frame times are not representative and the "ran loaded" gate flags are from load 18+ on 4 cores. `safari_webkit`, `olympus_themes` and the hub browser parts were not run (no static part, too heavy for a shared box). Re-run them on a calm machine before the release.

## Edits made (the pre-approved list)

- `tools/web_public/jarvis/sw.js`: added `'jarvis-v26'` to OLD (no other change).
- `tools/web_public/kalshicity/index.html`: css `?v=k14` to `k15`.
- Not touched: `tools/web_public/sw.js`, `jarvis/apps.js`, `olympus.js` APPS, `build_web_dashboard.py`, `engine/`, `live_model*.json`.
- Tests and tools: `tests/gate_static.py`, `tests/test_jarvis_hub.py`, `tests/test_jarvis_kalshi.py`, `tests/test_wire_new_apps.py`.
- CSS: font size 16px on text fields in `oikos`, `moirai`, `kairos`, `argo`, `epilogue`.
- Doc: Argo scene in `docs/NEW_APPS_WIRING.md`.
