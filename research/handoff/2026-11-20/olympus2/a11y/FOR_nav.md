# A11Y -> NAV (hub/ + search): ranked issues and exact fixes

The sweep (`python tools/a11y_sweep.py`, 2026-11-20) covered 12 screens per page: 320/390/430 px, dark + Ivory, reduced motion on/off.
**hub/doors.html 89, hub/zeus.html 93**: the best on the site. No contrast, name, tap, sideways-scroll, motion or focus failures.
The full list is in `raw/fixes_nav.md`.

1. **Small text (the only real issue).** Sentences under 15 px. Change each line, or take DESIGN's K2 tokens (FOR_design.md) and point these at `var(--ag-fs-note)` (15 px):
   - `hub/doors.html:52` `.dr-line { font-size: .875rem }` -> `.9375rem` (the door's one-line purpose: it is a sentence)
   - `hub/doors.html:48` `.dr-door small`, `:59` `.dr-row small`, `:71` `.dr-foot`: `var(--ag-fs-foot)` (13) -> `var(--ag-fs-note, .9375rem)`
   - `hub/zeus.html:55` `.zs-feed-none` .875rem -> .9375rem. `:85` `.zs-src`, `:92` `.zs-win small`, `:99` `.zs-note-src`, `:105` `.zs-btn small`,
     `:111` `.zs-info summary small`, `:121` `.zs-stamp`: 13 px -> keep 13 px only where it is 1-4 words (`.zs-stamp`, `.zs-src`); sentences to 15 px.
2. **Dynamic Type:** `nav#doorGrid > a.dr-door > em.dr-tag` does not grow (px). Write it in rem.
3. **a11y.js is not loaded** on hub/doors.html or hub/zeus.html. Add `<script src="../olympus/a11y.js" defer></script>`. It brings the shared
   keyboard focus ring, auto names for icon-only buttons and px-text growth on the iPhone. Nothing fails today without it, but new icon buttons would.
4. Search (the Gate's `input#q` and Atlas's `input#query`) shows **no focus ring** when reached by keyboard. Those inputs belong to the HOME
   and DESIGN teams; the fix (load a11y.js, or `:focus-visible { outline: 3px solid var(--oly-accent) }`) is in their files.

Check: `python tools/a11y_sweep.py --apps hub,hub-zeus --quick`.
