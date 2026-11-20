# A11Y -> HOME + CITIES (gate/, cities/, datacity/, widget/): ranked issues and exact fixes

Scores (BASELINE.md, 12 screens each): **gate 82, widget 82, cities 85**. Reduced motion is respected: the 3D cities draw a still frame
(the screen is the same 1 s apart). The full list is in `raw/fixes_home.md`.

1. **cities: contrast 2.55:1** on the live chip. `cities/agora-cities.css:17` `.chip b { color: var(--oly-th-n37, #f3ece0) }` sits on the olive
   fill #8f9b5a (`.live` chip, "157/173", 13 px). Fix: dark ink on the light olive fill: `.chip.live b { color: #1b1610; }` (6.0:1 on #8f9b5a).
   Or keep the light ink and darken the fill to `#4f5a2c` (6.3:1).
2. **gate: tap target 40 px.** `gate/gate.css:347` `.g-now:has(#money) .g-facts .g-fact { min-height: 40px }` -> `min-height: 44px` (the "Trade window ..." fact links, 324x40).
3. **gate: no focus ring on search `input#q`** (keyboard / VoiceOver). The Gate does not load a11y.js. Add
   `<script src="../olympus/a11y.js" defer></script>` to gate/index.html, or in gate.css:
   `#q:focus-visible { outline: 3px solid var(--oly-accent, #c8a24a); outline-offset: 2px; }`.
4. **gate: `.g-mstrip`** has `role="list"` but its children are not `role="listitem"` (axe aria-required-children). Put `role="listitem"` on
   each `.g-acct`, or drop the role on the strip.
5. **cities `#chips`** and **widget `#code`** scroll sideways inside themselves but cannot be reached by keyboard
   (`scrollable-region-focusable`). Add `tabindex="0"` plus an `aria-label` ("City filters" / "Widget code").
6. **Small text:** gate has 24 sentences under 15 px. `gate/gate.css:210` `.g-qline` 13 px (the door subtitles: on every Gate view)
   -> `.9375rem`. `:37` `.g-hint` 13 -> 15. `:362` `.g-nowfoot` 12 -> 15. `:351` `.g-fsub` **11 px** -> `.75rem` minimum.
   `:122` `.g-sw small` 12 -> 13. `:74` `.g-hline`, `:159` `.g-lknow-t span` 13 -> 15. `:178` `.g-quiet` 14 -> 15.
   widget: `widget/widget.css:59` `pre.code { font-size: 11px }` -> `.75rem`. `:38` `.sub` .85rem -> .9375rem.
   cities: `cities/index.html:92` `.world-fab .wf-t small { font-size: 12px }` -> `.8125rem`.
7. **Dynamic Type:** gate and widget do not load a11y.js, so their px text never grows on the iPhone. Load a11y.js (see 3) or move the px sizes to rem.

Check: `python tools/a11y_sweep.py --apps gate,cities,widget --quick`.
