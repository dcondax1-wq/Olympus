# LEAD_WIRES: Research Hub (day-litedge, 2026-11-21)

The hub is built INTO Clio (`tools/web_public/clio/`, already registered everywhere; the day-arenas audit had folded Archive and
Pinakes into it), so there is no new app, no new folder in sw.js OTHER_APPS and no new build_web_dashboard copy line.
Clio has no own service worker; its ?v= tags were bumped in clio/index.html (clio.css?v=h3, clio.js?v=h3).

Optional lead-only edits (owner wording "Research Hub"; not needed for the page to work):

1. `tools/web_public/jarvis/apps.js` line 144:
   `app('clio', 'Clio', 'trading', '#d8c9a8', 'The research library: every study in plain words', { glyph: 'Κ' }),`
   -> `app('clio', 'Research Hub', 'trading', '#9d59ee', 'What works, what we tried, open leads, money decisions', { glyph: 'Κ' }),`
2. `tools/web_public/olympus/olympus.js` APPS table: the `clio:` entry's name 'Clio' -> 'Research Hub' (same glyph), then
   `python tools/apps_list_build.py` (+ `--check`).
3. `tools/build_web_dashboard.py` (keeps hub.json fresh on every site build, not just nightly): after the writeups/index.json
   block (~line 1040) add
   ```python
   try:                                   # day-litedge 2026-11-21: the Research Hub (Clio's owner view)
       subprocess.run([sys.executable, os.path.join(ROOT, "tools", "research_hub.py"), "--out", os.path.join(out, "clio", "hub.json")],
                      cwd=ROOT, timeout=120, check=False)
   except Exception as e:  # noqa: BLE001
       print(f"  research hub: skipped ({e})")
   ```
   (research_hub.py exits 2 and writes nothing if the privacy scan finds anything.)

Already wired on this branch (not lead-only): tools/learn_night.py step "hub" (after decide), tests/run_area.py area
`olympus` += clio_page, research_hub.

After merging: `python tools/writeups_index.py` (adds lit-edge-2026-11-20 + lit-eval-rescue-2026-11-20).
