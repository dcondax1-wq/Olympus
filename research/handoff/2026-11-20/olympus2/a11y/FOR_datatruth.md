# A11Y -> DATA TRUTH (nq/, trading/, board/): ranked issues and exact fixes

Scores (BASELINE.md, 12 screens each): **trading 77, nq 85, board 85**. Reduced motion is respected and nothing scrolls sideways.
The full list is in `raw/fixes_datatruth.md`.

1. **trading: contrast 3.95:1 in daylight (Ivory)** on the heat map's "few trades" cells. `tools/web_public/nqdeep.css:32` `.nqd-heat td`
   with `data-lvl="few"` ends at #827f7a on #fffefd (12 px). Use a token rather than a faded ink: `.nqd-heat td[data-lvl="few"] { color: var(--ag-muted); opacity: 1; }`
   (Ivory's muted #6b6152 is 6.0:1). If the fade comes from `opacity`, drop the opacity.
2. **nq + trading: `role="listitem"` on `<article>`** (axe aria-allowed-role: VoiceOver drops the list). `nq/nq.js:228` and
   `trading/trading.js:353` set `c.setAttribute('role', 'listitem')` on the account cards, which are `<article>` elements. Fix: give the
   box `role="list"` and wrap each card: `const w = document.createElement('div'); w.setAttribute('role', 'listitem'); box.insertBefore(w, c); w.appendChild(c);`.
   Or drop both roles: articles are already announced one by one.
3. **trading: empty table header** `.stat[data-bot] .st thead th:first-child` (`trading.js:230` `['', 'H1', 'H2']`): VoiceOver reads
   nothing for the row-name column. Use `['Measure', 'H1', 'H2']`, or `<th><span class="sr-only">Measure</span></th>`.
4. **board: the live feed list loses its list role** (`board/index.html:62` `<ul id="feed" aria-live="polite">`). This is a kit bug in
   olympus/a11y.js (FOR_design.md K1, which fixes it for everyone). Until it lands, wrap the list: `<div aria-live="polite"><ul id="feed" class="feed"></ul></div>`.
5. **Small text:** trading 75, nq 50, board 21 sentences < 15 px. These are the money lines the owner reads. `.ag-card h2/h3` already grows. The px
   lines are in raw/fixes_datatruth.md, grouped by CSS rule. Dynamic Type is not scored here: all three load a11y.js, which grows px text on the iPhone.

Check: `python tools/a11y_sweep.py --apps trading,nq,board --quick`.
