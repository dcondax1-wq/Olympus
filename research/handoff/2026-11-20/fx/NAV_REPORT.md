# NAV FX (day-manual, 2026-11-20): Home, ZEUS, the Website HQ. Owner: "It needs some 3D, it needs some effects ... no gold."

| What | Result |
|---|---|
| One shared layer | `hub/navfx.css` + `hub/navfx.js` (mine), on Home (gate/), ZEUS (hub/zeus.html) and the Agency HQ (agency/index.html) |
| No gold, navy base | The default look on these pages: navy surfaces (#0b1220...), cyan / blue / violet glows; gold tokens turn cyan. A look the owner picks (Ivory, Stocks Light ...) keeps its own colours and gets the glass + glow on top. The class is set in `<head>` and the CSS loads with the page: no brown -> navy flash. |
| Home | Glass app icons in cool colours (lit top edge, glow under, white glyph) for the 8 apps + the doors dock; the gold temple hero turned blue with one GPU filter (hue-rotate, its canvas untouched); a cheap aurora (3 blurred blobs, CSS transform drift; no blur on Save-Data / 2G-3G / <= 2 GB phones) |
| ZEUS | Glass account cards with a cyan edge, balances count up the first time they show |
| Agency HQ | Glass cards + tiles, cyan -> blue Next-step button, the retainer bar cyan -> violet with glow, pipeline + $ count up; a burst (olympus/nqfx.js milestone, loaded only then) when the $3,000 retainer goal is reached |
| 3D tilt | Only small things (icons, the doors dock, HQ tiles), only while a finger is on them; big cards never tilt |
| Roll-ups | Drawn by a ::after overlay: the real text never changes (VoiceOver and the tests read the final number at once) |
| Fast + calm | First paint unchanged (no new blocking script; one small CSS file), layout shift 0.000 on all three, reduced motion = aurora still, no tilt, no roll-up, no burst; no WebGL needed (CSS only) |
| Not used yet | DESIGN's olympus/dashfx.js was not on day-arenas at push time; navfx can hand its tilt / reveal to it later |
| Tests | nav_pages 39/39 (+ 6 fx checks: navy, aurora moving / still, tilt on / off, CLS < 0.05, the real numbers final, both motion settings), gate_page 90/90, zeus 52/52 (navfx.js allowed in its script order), web_hub 23/23, help 35/35, home_fx 19/19, olympus_shell 42/42, test_agency 118/118 |
| Shots | fx/home, fx/zeus, fx/agency: top + grid, dark + Ivory, 390 x 844 x 2 |
