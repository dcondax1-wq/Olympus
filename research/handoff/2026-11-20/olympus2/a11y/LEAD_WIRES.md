# A11Y: lines for the lead (lead-only files: launcher.js, sw.js, build_web_dashboard.py, jarvis/apps.js, olympus.js APPS table, olympus/doors.js)

1. **The launcher button is 42x40 px (tap target under 44).** Measured on Zenith (`button#olyLauncherBtn`, "Open the OLYMPUS app launcher").
   In `tools/web_public/launcher.js`, the injected style `.oly-lbtn{...min-width:40px;height:40px;...}` -> `min-width:44px;height:44px`.
2. **Nothing for sw.js** (checked: it does not precache agency.css, inbox.css or tyche.css). The three app fixes bumped their own `?v=` strings.
3. **Optional, test lane:** `tests/run_area.py` AREAS could get `"a11y": ["a11y_sweep"]` (I did not touch the runner's area table). The
   suite runs in about 20 s: `python -X utf8 -m tests.test_a11y_sweep`.
4. **The re-run after landing (before / after for the owner):**
   `python tools/a11y_sweep.py --compare research/handoff/2026-11-20/olympus2/a11y/baseline.json`
   writes `scratch/a11y/<time>/COMPARE.md` (a per-app score table, before -> after) and prints it. About 9 min with 3 Chromiums
   (`--workers 2` on a busy box). It takes `/tmp/olympus_browser.lock` itself, like run_area.
   Needs Python Playwright: `pip install playwright==1.63.0` if `import playwright` fails (it uses the pre-installed Chromium, no download).
