# Money FX on Board, Ledger, Hera (day-archive 2026-11-20)

Owner: "It needs some 3D, it needs some effects" + no gold. 390x844 shots: `<app>/top-390.png` (first screen) and `<app>/payout-card.png`.

| What | Where |
|---|---|
| Navy terminal palette (cyan / blue / violet, green / red only for $) | `../nq/nqtheme.css` loaded last + `olympus/moneyfx.css` (glass glow, cyan pressed chips, no brown buttons) |
| Payout goal card: 3D vault (DESIGN's `nqfx.js` NQFX.vault, cyan light seam, crystal bars), an "earliest payout" ring with a rolled-up %, the numbers in MFFU's terms (`PC_FEED.mffuView`) | `olympus/moneyfx.js` fills any `[data-moneyfx="payout"]` card; one card + one tag per app |
| Ledger's own 3D vault scene | recoloured from gold to navy steel + cyan / blue light (`ledger/ledgerscene.js`) |

Fast: the kit and three.js load after `load` + idle; the vault box has a fixed aspect ratio (CLS measured 0.00002-0.00004); reduced motion /
no WebGL = the kit's still 2D vault; the note always says every number. Tests: hera 39/40 (= pc), ledger 88/88, board 59/59, ledger_freeze
all pass, site_checks fine. Not changed: the gold app icons (Hera crown, Ledger wheel) in the page headers (DESIGN's icon set).
`dashfx.js` (DESIGN, card glow / tilt / reveal) had not landed when this was pushed: moneyfx.css gives the card glow meanwhile.
