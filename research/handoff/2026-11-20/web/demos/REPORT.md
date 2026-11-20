# WEB · demos: 5 sellable 3D website demos + the gallery (branch day-arenas, 2026-11-20)

Owner ask (13:30 ET): "an expert on marketing 3D websites ... for business". This slice = the thing he opens on his phone in front of a
prospect: `agency/demos/` (gallery) and five real one-page sites for FICTIONAL local businesses. All 3D is made in code (no downloaded
models or pictures to licence); three.js r160 (MIT) is the copy already in `jarvis/`, RoomEnvironment from `olympus/three-addons/`.

| Demo | Trade | The 3D | Price (research offers.json) |
|---|---|---|---|
| `restaurant/` Lantern & Thyme | restaurant · café · bakery | the dish turns on a plate (margherita / tagliatelle / tiramisu, steam) | starter site $1,500 + $79/mo (AR menus: weak evidence, sold as a site) |
| `roofer/` Northgable Roofing | roofer · contractor · remodeler | a house: slide from the storm-worn roof to the new one, 4 shingle colours | $2,400 (site $1,500 + before / after $900) + $108/mo |
| `detailer/` Glossworks | car detailer · dealer · wrap shop | a car in a showroom: before / after ceramic, 4 paints | $2,400 (site + before / after) + $108/mo |
| `estate/` Willow Row Lofts | real estate · venue · rentals | walk-through: overview from above, then living / kitchen / bedroom / terrace at eye height | phone-scan 3D tour $500 a scan + $25/mo |
| `shed/` Cedar Hollow Sheds | sheds · pergolas · carports · trailers | configurator-lite: size, roof (gable / barn / lean-to), colour, extras (windows, double doors, porch, ramp); the shed rebuilds in 3D, the price and "or $/mo" update live, the quote carries the build | configurator-lite $3,500 + $99/mo (research #9: leads double) |
| `index.html` gallery | the owner's pitch tool | stills of each demo, what it shows, a 10-second pitch line, the prices; **Client mode** hides prices + pitch lines (remembered on the phone); **Make it theirs** | |

**Make it theirs** (the part most agencies don't do): on the gallery the owner types the prospect's business name, town and phone, picks a
demo, then "Open their demo" or "Copy the link" (to text it to them). The demo opens with THEIR name in the logo, title and footer, their
town, and their number on every Call button. It's marked "Sample site for <name>" and the reviews say "samples: yours go here".
Everything is in the link (`?biz=&city=&tel=`): nothing is saved or sent. Text only and capped at 40 characters, so typed HTML stays plain text (tested).

Prices from the research team's `offers.json` (day-archive 3110fc34), in `data-price` attributes (10). `summary.json` feeds the Agency HQ tile (n 5, label, next step).

## Every demo has
Hero that sells in 5 s (headline, one line, Book + Call, star rating), the 3D stage, the menu / services / packages / steps, 3 reviews,
a drawn map + hours + Directions, a sticky Call / Book bar on the phone, a booking sheet that checks the fields and thanks (demo: sends
nothing, says so), a "Demo site · fictional" strip with a link back to the gallery, `noindex`, 555-01xx phone numbers, no house numbers.

## Phone first (measured, 390 x 844)
| Check | Result |
|---|---|
| First load before any 3D | 32-37 kB per demo, gallery ~120 kB with the 4 stills (budget 400 kB) |
| Slow line (Fast 3G + 4x CPU) | first paint 0.53-0.58 s on every page; 3D arrives 5-7 s later, after the page |
| Layout shift | 0.000 on all 5 pages (the stage has a fixed ratio, the canvas fades in over the drawn picture) |
| No WebGL / lost context | the drawn SVG picture stays; picks, the roof slider and the room buttons still work on it |
| Taps / text | every button and pick >= 44 px, every sentence >= 15 px, no sideways scroll |
| Reduced motion | no auto-turn, camera cuts instead of flights |
| Laptop (1280 x 800) | headline + buttons on the left, the whole 3D stage + picks on the right, above the fold |
| Network | nothing asked from another host (system fonts; Directions is a plain link) |
| Battery | renders only while the stage is on screen and the tab is visible; stops when nothing moves |

## Files (all new)
`tools/web_public/agency/demos/`: `index.html`, `demo.css`, `demo.js` (picks, slider, booking sheet), `stage.js` (the shared three.js
stage: drag to turn with pan-y scroll, eye / orbit cameras, flyTo, pause off screen), `<demo>/index.html`, `<demo>/scene.js`, `<demo>/thumb.jpg`.
`tests/test_web_demos.py` (40 checks) + its line in `tests/run_area.py` (AREAS 'agency').

## Tests
`web_demos` 51/51 · `smoke` 10/10 · `public_build_privacy` 59/59 (it first caught the made-up house numbers; removed).

## Not done / next
- Next step after Make it theirs: their logo colour (one `?c=` accent) and their photo on the hero.
- The car and the flat are stylised (made from shapes). A real client job would use their photos, or a free CC0 model if licensed.

Screens: `shots/` (390 x 844 @2x): each demo top / 3D / reviews / no-WebGL, the roofer booking sheet, the gallery, client mode,
Make it theirs (the form, and the restaurant opened as "Rosa's Pizzeria").
