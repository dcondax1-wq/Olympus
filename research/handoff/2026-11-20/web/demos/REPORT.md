# WEB · demos: 4 sellable 3D website demos + the gallery (branch day-arenas, 2026-11-20)

Owner ask (13:30 ET): "an expert on marketing 3D websites ... for business". This slice = the thing he opens on his phone in front of a
prospect: `agency/demos/` (gallery) and four real one-page sites for FICTIONAL local businesses. All 3D is made in code (no downloaded
models or pictures to licence); three.js r160 (MIT) is the copy already in `jarvis/`, RoomEnvironment from `olympus/three-addons/`.

| Demo | Trade | The 3D | Draft price (build + monthly) |
|---|---|---|---|
| `restaurant/` Lantern & Thyme | restaurant · café · bakery | the dish turns on a plate (margherita / tagliatelle / tiramisu, steam) | $1,800 + $99/mo |
| `roofer/` Northgable Roofing | roofer · contractor · remodeler | a house: slide from the storm-worn roof to the new one, 4 shingle colours | $2,900 + $149/mo |
| `detailer/` Glossworks | car detailer · dealer · wrap shop | a car in a showroom: before / after ceramic, 4 paints | $1,500 + $79/mo |
| `estate/` Willow Row Lofts | real estate · venue · rentals | walk-through: overview from above, then living / kitchen / bedroom / terrace at eye height | $3,500 agent site, $450 per listing |
| `index.html` gallery | the owner's pitch tool | stills of each demo, what it shows, a 10-second pitch line, the prices; **Client mode** hides prices + pitch lines (remembered on the phone) | |

Prices are DRAFTS (the research team's RESEARCH.md was not out at 14:00 ET); they sit in `data-price` attributes, one line each to change.

## Every demo has
Hero that sells in 5 s (headline, one line, Book + Call, star rating), the 3D stage, the menu / services / packages / steps, 3 reviews,
a drawn map + hours + Directions, a sticky Call / Book bar on the phone, a booking sheet that checks the fields and thanks (demo: sends
nothing, says so), a "Demo site · fictional" strip with a link back to the gallery, `noindex`, 555-01xx phone numbers, no house numbers.

## Phone first (measured, 390 x 844)
| Check | Result |
|---|---|
| First load before any 3D | 32-33 kB per demo, gallery ~120 kB with the 4 stills (budget 400 kB) |
| Slow line (Fast 3G + 4x CPU) | first paint 0.53-0.58 s on every page; 3D arrives 5-7 s later, after the page |
| Layout shift | 0.000 on all 5 pages (the stage has a fixed ratio, the canvas fades in over the drawn picture) |
| No WebGL / lost context | the drawn SVG picture stays; picks, the roof slider and the room buttons still work on it |
| Taps / text | every button and pick >= 44 px, every sentence >= 15 px, no sideways scroll |
| Reduced motion | no auto-turn, camera cuts instead of flights |
| Network | nothing asked from another host (system fonts; Directions is a plain link) |
| Battery | renders only while the stage is on screen and the tab is visible; stops when nothing moves |

## Files (all new)
`tools/web_public/agency/demos/`: `index.html`, `demo.css`, `demo.js` (picks, slider, booking sheet), `stage.js` (the shared three.js
stage: drag to turn with pan-y scroll, eye / orbit cameras, flyTo, pause off screen), `<demo>/index.html`, `<demo>/scene.js`, `<demo>/thumb.jpg`.
`tests/test_web_demos.py` (40 checks) + its line in `tests/run_area.py` (AREAS 'agency').

## Tests
`web_demos` 40/40 · `smoke` 10/10 · `public_build_privacy` 59/59 (it first caught the made-up house numbers; removed).

## Not done / next
- Prices: swap in the research team's numbers when RESEARCH.md lands (`data-price` in `agency/demos/index.html`).
- A "your logo / your photos" swap (one JSON per prospect) would turn a demo into a personalised mock-up in a minute: not started.
- The car and the flat are stylised (made from shapes). A real client job would use their photos, or a free CC0 model if licensed.

Screens: `shots/` (390 x 844 @2x): each demo top / 3D / reviews / no-WebGL, the roofer booking sheet, the gallery and client mode.
