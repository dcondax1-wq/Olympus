# FX on Trading, Business (index, accounts, mffu), Planner (day-a11y 2026-11-20)

Owner: "It needs some 3D, it needs some effects." NO GOLD.

- **Look:** Trading and Business load `nq/nqtheme.css` last: navy, cyan #22d3ee, blue #3b82f6 and violet #8b5cf6, with green / red only for $. The Planner keeps its sea blue: every kit gold token now points at #7fa7c2 (planner.css), and the sundial lost its gold.
- **Effects:** one layer, `trading/panelfx.js` (+ `panelfx.css`, which it injects after the paint), loaded deferred at the end of each page:
  - a particle aurora behind the cards: a fixed 2D canvas, so no WebGL is needed; 1/3 resolution, ~24 fps, paused when the tab is hidden;
  - glass cards with a soft glow and a light along the top edge;
  - glowing chart lines (12 at most), plus a light trail on the first one (olympus/nqfx.js);
  - big numbers roll up once when first seen;
  - cards below the first screen fade and rise in;
  - Trading: a green win burst from the day's P&L when it is a gain (NQFX.win).
- **Safety:** reduced motion gives one still frame, with no roll, reveal or burst. Save-Data, a slow line or a small phone also get the still frame. Print shows no effects. When DESIGN's olympus/dashfx.js is on a page, it takes over the card reveal.
- **Phone profile (390x844, CPU x4, Fast 3G), pc -> this branch:**

| App | first paint ms | largest paint ms | KB | blocking ms | CLS | errors |
|---|---|---|---|---|---|---|
| trading | 2880 -> 2864 | 4576 -> 4636 | 358 -> 390 | 230 -> 293 | 0.001 -> 0.001 | 0 -> 0 |
| business | 2684 -> 2644 | 5768 -> 6340 | 308 -> 339 | 45 -> 62 | 0.002 -> 0.002 | 0 -> 0 |
| planner | 2224 -> 2176 | 5744 -> 5540 | 288 -> 294 | 3 -> 4 | 0.004 -> 0.004 | 0 -> 0 |
[]

First paint is unchanged (within noise). CLS is unchanged (the aurora canvas is fixed inline before its CSS lands). Extra download: about 30 KB (nqfx + the kit's fx-core / text / burst).

Tests: test_panelfx 45/45 (new; it is in run_area trading), trading 71/71, business_pages 40/40, business 78/78, mffu_center 40/40 (now allows the two effect scripts after the page), planner_page 170/170, planner_addons 9/9, planner_temple 16/16. Roll-ups are off under automation (navigator.webdriver) so tests read exact numbers. Shots: */index-390.png and *-390-scrolled.png (390x844 @2x).

LEAD_WIRES: none needed (no lead-only file touched). Later: move panelfx.js into olympus/ once DESIGN's dashfx.js lands, so other dashboards can use it.
