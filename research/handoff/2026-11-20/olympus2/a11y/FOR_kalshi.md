# A11Y -> KALSHI (kalshi/, dionysus/, sibyl/, kalshicity/): ranked issues and exact fixes

Scores (BASELINE.md, 12 screens each): **kalshi 71** (tied lowest on the site), **dionysus 92**. Sibyl and Kalshi City are archived, so
they were not swept. The full list is in `raw/fixes_kalshi.md`.

## kalshi
1. **Contrast from stacked opacity** (dark theme): "paper only" is 4.35:1 and the "done" times are 3.02:1. The cause is `opacity` on muted
   text inside rows that are already dimmed (`.6 x .8`). `kalshi/kalshi.css`:
   - `:956` `.k8w li.pp { font-size: 12.5px; opacity: .6; ... }` -> drop the opacity: `color: var(--mut); font-size: .8125rem;`
   - `:958` `.k8w li i, .k8p li i { ...; font-size: 11.5px; opacity: .8 }` -> `font-size: .75rem; color: var(--mut); opacity: 1;`
   - `:955` `.k8w li em.done { opacity: .6; ... }` -> `color: var(--mut); opacity: 1;` (`--mut` #a39883 is 6.1:1 on --bg2)
2. **Tap targets 21 px tall:** the hub links `section#khub ul.kh-l > li > a` ("The bot's own 1,836 bets") and `ul.kh-a > li > a`
   ("Kalshi City") are 328x21. The `li` is 44 px, but only the text line is tappable. `kalshi.css:980` add:
   `.kh-l li > a, .kh-a li > a { display: flex; align-items: center; min-height: 44px; }`
3. **Colour alone:** `section#krw dl.krw-g dd.up` "$5.54" is green with no sign. Print `+$5.54` (kalshi.js already has `MINUS` for the minus sign).
4. **Small text: 37 sentences < 15 px**, and the page does not load a11y.js, so its **78 px-text elements never grow**. Add
   `<script src="../olympus/a11y.js" defer></script>` (this also brings the focus ring and auto names). Then `.k8p li` 13.5px (`:960`),
   `.k8w li` 14px (`:949`) and `.k8w-h` 13px (`:947`) -> `.9375rem`. Every line is in raw/fixes_kalshi.md.

## dionysus
Only small text (31 sentences): the lines are in raw/fixes_kalshi.md. Use DESIGN's K2 sentence token `var(--ag-fs-note, .9375rem)` once it lands.

Check: `python tools/a11y_sweep.py --apps kalshi,dionysus --quick`.
