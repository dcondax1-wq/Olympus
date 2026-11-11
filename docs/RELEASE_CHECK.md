# Release check: the 5 commands before a zip goes to the owner

Run them from the repo root, in this order. Each one says GO / FAIL in plain words. Stop at the first FAIL, fix, start again from that step.
Steps 1 and 5 open a browser: only ONE browser may run on the machine, so they go under the lock (`flock -w 2400 /tmp/olympus_browser.lock ...`).

| # | What it checks | Command | Good result |
|---|---|---|---|
| 1 | Fast gate: the release gate's quick pass over the whole site | `flock -w 2400 /tmp/olympus_browser.lock python -X utf8 tests/run_gate.py --fast` | `GO` |
| 2 | Wire check: every app of `tools/new_apps.json` is in the six shared files | `python tools/wire_new_apps.py --check` | exit 0, nothing missing |
| 3 | Apps list check: the generated app lists match `jarvis/apps.js` | `python tools/apps_list_build.py --check` | exit 0 |
| 4 | Site build: the folder that is zipped / published | `python -X utf8 tools/build_web_dashboard.py --state dash/state.json --chart dash/chart.png --out <site>` then delete `<site>/runs` if the zip must be small | "wrote ..." lines, no traceback |
| 5 | Site smoke: EVERY app page of that built folder opened on a phone-sized screen | `flock -w 2400 /tmp/olympus_browser.lock python -X utf8 tools/site_smoke.py <site> --out <site>_smoke --json <site>_smoke/smoke.json` | last lines: `N of N pages ok, 0 failed`, exit 0 |

## Step 5 in detail (`tools/site_smoke.py`)
- It serves `<site>` on a free local port (read only) and opens the root page and every folder with an `index.html` at 390 x 844 with `?demo=1&q=low&welcome=0&intro=0`, one page at a time, at most 40 s a page (`--timeout`).
- Per page it records: HTTP status, console errors, uncaught exceptions, failed same-site requests, whether the page is visibly not blank (text length and painted pixels), sideways overflow, a title and the app marker, the time to first content.
- **Hard failures (exit 1):** a bad HTTP status, an uncaught exception, a console error, a failed script / style / page request, a blank page, a timeout, the kit's own "could not load" banner.
- **Warnings (exit 0, still listed):** sideways overflow, no title or app marker, a missing optional data file (a JSON that answers 404), a request that tried to leave the site.
- Output folder: one `<app>.png` per page (`_root.png` for the root), `sheet-01.jpg` ... (contact sheets, 12 pages each, a failed page has a red name bar) and `smoke.json` with everything.
- One or a few apps only: `--apps colosseum,archive,root`.
- The table it prints is the report: app / ok / first content / problem.

## Notes
- Step 1 without `--fast` is the full gate: run it on a quiet machine before a real release, not for every zip.
- If step 2 fails: `python tools/wire_new_apps.py --dry-run` shows the diff, `--apply` writes it; then bump the `sw.js` CACHE.
- If step 3 fails: `python tools/apps_list_build.py` rewrites the two lists.
- The unit tests of the smoke tool need no browser: `python -X utf8 -m tests.test_site_smoke`.
- Data builders that must run before step 4 when research changed: `python tools/archive_build.py`, `python tools/colosseum_build.py` (both have `--check`).
- Nothing here pushes, publishes or touches the bots.
