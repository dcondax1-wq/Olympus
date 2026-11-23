# HERMETIC (night-hermetic, 2026-11-23): tests never change the bot's live files

Why: the PC's weekly self-test (engine/pc_selftest.py) runs test suites ON THE OWNER'S PC. On 2026-11-22 a pc-area suite left
`data/arm_status.json`, which changed the Brain glance (an "ATLAS is NOT armed" note) and turned tests.test_brain red. Any test that
writes `data/`, `logs/`, `cache/` or a top config file can change live state the same way.

## What protects it now
| Layer | What |
|---|---|
| Write guard | `tests/write_guard/sitecustomize.py`: a Python audit hook (open-for-write, rename/replace, remove, rmdir, rmtree, mkdir of a new folder, truncate, `sqlite3.connect`) on `data/`, `logs/`, `cache/`, `live_model*.json`, `second_model.json`, `dashboard_view.json`, `notify_settings.json`, `update_source.json`, `*.local.ps1`, `~/.olympus`. `LE_WRITE_GUARD=raise`: refused (PermissionError). `=log`: logged (the scan). It ignores temp folders, makedirs on a folder that exists, clean-ups of missing paths, and bare names relative to a dir_fd (shutil.rmtree of a temp folder). Opening the existing live sqlite db is only logged. |
| Self-test child | `engine/pc_selftest.child_env`: every suite runs with the guard in **raise** mode (PYTHONPATH + `LE_WRITE_GUARD_ROOT`), and HOME / USERPROFILE / OLYMPUS_HOME point into the suite's temp folder. The temp TMP, NinjaTrader folder, board and inbox redirects were already there. So a dirty suite now fails loudly instead of changing a live file. |
| Every test process | `tests/__init__.py`: `LE_MEMORY_DB` = a temp db for every `python -m tests.*` and its children (`engine/memory.DB_PATH` honours it). |
| Scan | `tools/hermetic_scan.py [areas] [--selftest] [--suites a,b]`: one suite at a time, with two detectors. (1) The guard in log mode. (2) A sha1 snapshot of `data/ logs/ cache/` + the config files before and after, which also catches node / PowerShell writers. Any change is put back afterwards. Output: `scratch/hermetic/scan.json`. |
| Guard test | `tests/test_hermetic.py` (area pc): guard unit checks, the child_env seal, and a sample of the formerly dirty suites run under the snapshot (must be unchanged). |

## Scan result: PC self-test suites + run_area pc / nq / fleet (142 suites, one at a time)
14 were dirty. All are fixed; the rescan list is below.
| Suite(s) | Live file | Cause | Fix |
|---|---|---|---|
| go, start_api, rapid_arm (+ arm_report / arm_rt paths) | `data/arm_status.json` | `engine/go._summary` always saved to `arm_report.PATH` | `go._arm_status_path()`: next to the config a test redirected (SECOND_PATH / CFG in temp), or a patched `arm_report.PATH`; the real START is unchanged |
| bots_back, state_pulse, roll_now, pc_guard, launch_kit | `data/agency_pipeline/summary.json` | `pc_report.gather()` rewrote the money pipeline card for any root | written only when root is the real repo |
| nqops | `logs/ops-<day>.log` | `ops_checks.tick` logs to `LOG_DIR` | the test points `OC.LOG_DIR` at its temp folder |
| public_build_privacy | `logs/site_privacy_cache.json` | the scrub cache's default path | the test sets `LE_SCRUB_CACHE` to its temp folder (children inherit). It already restores `tools/web_hub_snapshot.json` (written by the lead-only builder) |
| lite, rapid25 (+ every LiveBot replay) | `data/memory.db` (created) | `LiveBot._remember` -> `engine.memory.MEMORY` | `LE_MEMORY_DB` (tests/__init__.py) + the Replay harness (tests/test_live_dryrun.install_globals) points MEMORY at its temp folder |
| cross_hedge / hand_hedge | `data/handsoff.jsonl` | `handsoff.record(path=PATH)` bound the path at import time, so a patch was ignored | `path=None -> PATH` at call time; the test points `handsoff.PATH` at its temp folder |
| bots_back, second_backup | (none: false positive) | an "it refuses a settings folder inside the repo" check cleans up a folder that never existed | the guard ignores clean-ups of missing paths |

Not dirty but red / slow in the scan (not part of this job): `obsidian_brain`, `land_branch` and `why_page` rc 1 (they were already red here); `lit_live`, `combo_50k`, `shadow_leads` and `fleet` took longer than the 600 s scan budget.

## Not scanned dynamically
The other ~390 suites (jarvis / olympus / zenith / kalshi / cities / agency / money / board / journal areas; mostly page and browser tests, not in the PC self-test). The self-test's guard covers any of them that join pc_selftest.SUITES later. Run `python tools/hermetic_scan.py <area>` per area to sweep them (about 1-2 h each).

## For the lead
- The guard runs in **raise** mode in the self-test, so a future suite that writes a live file goes red. If it had passed before, that holds the auto-update (the regression rule), which is the point. Its first [FAIL] line names the file.
- Shipping order: ship this together with or after night-truth (it is branched from it).
