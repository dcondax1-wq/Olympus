# night-nq-of: LEAD WIRES (the Order Flow room)

New files (mine): tools/web_public/nq/orderflow.html, orderflow.js, orderflow.css, tests/test_nq_of.py (+ build_of_room.py: Zlarior $ scrub).
Nothing else was edited. Please wire:

1. **NQ nav** (tools/web_public/nq/index.html line ~53, the `.tags` row): add after the Accounts button
   `<a class="btn brainlink" href="orderflow.html" aria-label="Open the Order Flow room: levels, absorption reads, paper trades">Order Flow</a>`
2. **Data**: `python -X utf8 tools/build_of_room.py` writes tools/web_public/nq/of_room.json. Run it in the hourly pull / nightly
   learn (after tools/of_realday_verdict.py) and publish it with the site. Without the file the page shows an honest empty state.
3. **Cache / sw.js**: nq/ has no own worker (sw.js OTHER_APPS lists 'nq/'): nothing to add. If nq/ ever gets a precache list,
   add orderflow.html/.js/.css (of_room.json must stay network-first).
4. **tests/run_area.py**: `AREAS["nq"].append("nq_of")` (browser part; ~30 s).
5. **Engine (optional, privacy)**: engine/of_paper.line() puts Zlarior's REAL $ in the lane-B words ("won $934"); that line rides
   the public status ext ("ofp".ln) and of_paper.json. The page and build_of_room now strip it, but the clean fix is in
   of_paper.line: `won` / `lost` without the amount (the public le-bars post already carries real trade $, so this is tidy-up,
   not a leak of something new).
6. Browser tests in this container: the shared kit looks for /opt/pw-browsers/chromium-*/chrome-linux/chrome; this image has
   chrome-linux64/. I added a local symlink (not in the repo). tests/browser_kit.chrome_exe could also try chrome-linux64.
