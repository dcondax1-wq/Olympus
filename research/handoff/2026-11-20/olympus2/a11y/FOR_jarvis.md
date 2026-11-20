# A11Y -> JARVIS (jarvis/): ranked issues and exact fixes

Score **82** (BASELINE.md). Jarvis does well: no contrast, name, tap, sideways-scroll or focus failures, and reduced motion fully stops the
orb (no frames drawn). The full list is in `raw/fixes_jarvis.md`.

1. **`#stage` nested-interactive** (axe, serious for VoiceOver): `jarvis/index.html:1085` `<div class="stage" id="stage" role="button" tabindex="0" aria-label="Talk to Jarvis">` has focusable controls inside it.
   VoiceOver then reads one big button and the inner ones are lost. Fix: take `role="button"` / `tabindex` off `#stage`, and put the tap
   action on one real `<button aria-label="Talk to Jarvis">` (the orb) inside it.
2. **Dynamic Type: 99 px-text elements, and Jarvis does not load a11y.js.** None of Jarvis's text grows with the iPhone text size. Quickest fix:
   `<script src="../olympus/a11y.js" defer></script>` in jarvis/index.html (on a touch phone it scales all text, px included, through iOS
   text-size-adjust). Lasting fix: px -> rem in `jarvis.css`. `:34` `button, input, select, textarea { font-size: inherit }` is fine.
   Start with `:57` `.pm.main { font-size: 14px }` -> `.9375rem`, `:853` `.wnb .wn-t` 14px -> `.9375rem`, `:524` `.tl-row small` 13.5px
   -> `.875rem`, `:865` `.hc-row small` 13px -> `.8125rem`.
3. **Small text (25 sentences < 15 px):** `section#sec-talk > p.hint2`, `section#p-addons > p.qby`, `.hc-sub` in `.hc-bot.hc-wide`,
   `#p-system .srow .st`, `span#when`. These are hints and status lines the owner reads: 15 px (`.9375rem`). The zenith block shown inside
   Jarvis (`.zeus-n small` 11px, `.zeus-g` 13px) comes from zenith's inline style (DESIGN: FOR_design.md).

Check: `python tools/a11y_sweep.py --apps jarvis --quick`.
