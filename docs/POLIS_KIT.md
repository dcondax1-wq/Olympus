# POLIS kit: the modern Ancient Greek look (items 1-10 of `docs/POLIS_25.md`)

Marble, bronze, gold leaf and painted clay, lit like now. Shared files only:

- `tools/web_public/olympus/polis.js`: `window.OLYMPUS_POLIS` (ES5, no CDN, nothing fetched)
- `tools/web_public/olympus/polis.css`: the styles (load after `agora.css`)
- `tools/web_public/olympus/polis-lab.html`: every piece on one page (`?lite=1`, `?still=1`, `?t=<ISO>` pins the sundial, `?style=red`)
- `tests/test_polis_kit.py`: static + node checks + a headless browser check of the lab
- Shots: `docs/shots/polis/kit-*.png`

All art is original and drawn in code (SVG paths, CSS gradients, one canvas marble texture, canvas mosaics). No game, brand or museum image was copied.
LITE (`OLYMPUS.lite()`, `?lite=1`, `prefers-reduced-data`) and `prefers-reduced-motion` mark the page `html.polis-still`: no animation at all,
mosaics at 1x. Taps are at least 44 px. Text from data is only ever set with `textContent`.

## Use it

```html
<link rel="stylesheet" href="../olympus/polis.css?v=p1">
<script src="../olympus/polis.js?v=p1"></script>
```

| # | Piece | Call | Zero-code attribute |
|---|---|---|---|
| 1 | Meander border | `OLYMPUS_POLIS.meander(el, {color:'gold', live:true})` (draws itself once; `live` runs it round the card; `sides:'band'` for a single band) | `data-polis-meander="gold live"` |
| 2 | Column frame | `columnFrame(el, {order:'doric'\|'ionic'\|'corinthian'})` or `{rank:'normal'\|'good'\|'record'}` | `data-polis-column="ionic"` |
| 3 | Carved inscription | `inscribe(el, {plaque:true})` (cut into marble) or `{gild:true}` (gilded on dark stone). Numbers become Greek numerals on hover / tap | `data-polis-inscribe="plaque"` |
| 3 | Greek numerals | `greekNumeral(2026)` -> `͵βκϛʹ` | |
| 4 | Pottery | `pottery('owl', {style:'black'\|'red', frame:'tondo'\|'tile'\|'none', size:120})` -> SVG string | `data-polis-pottery="owl red tile"` |
| 5 | Mosaic backdrop | `mosaic(el, {pattern:'waves'\|'rosettes'\|'dolphins'\|'meander', dense:false})` | `data-polis-mosaic="waves dense"` |
| 6 | Owl coin | `coin(el, {value:1240})` -> `{set({value})}`; win = bright silver, flips; loss = dulled to bronze | `data-polis-coin="1240"` |
| 7 | Attic date | `atticDate('2026-11-11').label` -> `Maimakterion 1`; `atticStamp(el, {date})` adds a chip | `data-polis-attic="2026-11-11"` |
| 8 | Sundial | `sundial(el, {tz:'America/New_York'})` | `data-polis-sundial` |
| 9 | Oil-lamp loader | `var l = lamp(el, {label:'Loading'}); l.set(0.4); l.done()` | `data-polis-lamp="Loading trades"` |
| 10 | Laurel / olive | `laurel(el, {kind:'laurel', gold:true})` (wreath), `{kind:'olive'}` (sprig) | `data-polis-laurel="laurel gold"` |

The page runs `OLYMPUS_POLIS.auto()` once on load when it finds any `data-polis-*` attribute; call `auto(root)` again after adding markup.
Extras: `.polis-glass` (frosted, lit panel for over mosaics), `.polis-gilt` (gold-leaf text), `.polis-plaque` (marble plaque), `meanderBg(color)` (a CSS
background band), `orderFor(rank)`, `sessionNow(parts)`, `fmtUsd(v)`, `marble('light'|'dark')` (data URL of the veined texture).

## How each piece is made

1. **Meander.** One continuous key on a grid of step `s` (5 wide, 4 high): up, across, down, into the square spiral and out again, back to the
   baseline. Lines and gaps are both one step, the classical proportion. The border is four runs (rotated), corner blocks and two rails.
   Drawing = `stroke-dashoffset`; live = the run is three units longer and slides one unit, so the loop is seamless.
2. **Columns.** Capitals as SVG: Doric (abacus, echinus, annulets, no base, as in real Doric), Ionic (volutes drawn as real spirals, egg-and-dart),
   Corinthian (two rows of acanthus, the upper row in gold leaf, helices, flower). Shafts are CSS: veined marble + 20 flutes + cylinder light + a
   slight taper (entasis). Entablature per order (triglyphs and metopes; fasciae and dentils; gold egg-and-dart) and three temple steps.
3. **Inscriptions.** The marble is a tileable canvas texture made once (periodic value noise, diagonal veins). Letters are cut by a dark-to-light
   gradient clipped to the text and a 1 px light lip below (CSS `filter: drop-shadow`, because AGORA forbids `text-shadow`).
4. **Pottery.** Each motif is layered like a real pot: the glaze silhouette, figure-coloured strokes (oars, spear, strings), added red and white,
   then detail lines. Black-figure: black glaze on clay, details **incised** to the clay colour. Red-figure: the same drawing inverted, clay figures on
   black, details as black relief lines and dilute glaze. Tondo frames have a tongue border, wheel marks and a glaze highlight.
5. **Mosaic.** A grid of slightly turned, irregular tesserae; a pattern function picks the stone (sea, gold, terracotta, ivory, black) for each
   tessera; dolphins are tested against the dolphin motif's path. Drawn once per size, never animated.
6. **Coins.** An irregular silver flan with an incuse square, the owl, olive sprig, crescent and ΑΘΕ in relief (SVG lighting filter: diffuse + specular
   on the blurred alpha), a gleam sweep on a win; a loss blends a bronze multiply layer and patina over the silver.
8. **Sundial.** An equatorial face seen from above: the shadow turns 15° an hour with the sun's real hour angle over New York (longitude and
   equation of time included, NOAA solar formulas), noon (today's solar noon) at the top. Hour marks are placed where the shadow will be at each
   New York clock hour today, so the shadow reads clock time. Night (sunset to sunrise, computed) is shaded with stars, and a silver moon hand
   keeps the hour. Arcs: RTH 09:30-16:00 (gold), Asia 18:00-24:00 (aegean), London 02:00-05:00 (olive). Updates every 20 s (60 s on LITE), pauses
   when the tab is hidden.
9. **Lamp.** A terracotta lamp in profile with ovolo dots, the filling hole, handle and nozzle; the flame (three layers) grows from the wick, flickers
   gently, and lights the lamp's own shoulder and a warm halo. `set(p)` sizes the flame to the progress.
10. **Laurel / olive.** Leaves placed along the wreath circle in pairs; each leaf has its own gold gradient (object bounding box), so the leaf
    catches light like beaten leaf; a specular sweep crosses all leaves (one clip path) on a new record. Red victory ribbon on the laurel.

## 7. The Attic calendar: the method (an approximation, documented)

Athens counted lunar months. `atticDate()` rebuilds them from the sky:

1. **New moons.** Every true new moon (conjunction) is computed with Meeus, *Astronomical Algorithms* (2nd ed., ch. 49): the mean phase and the
   25 periodic terms (the 14 planetary terms, under 30 s, are left out; TT to UT with ΔT = 69 s). Checked against Meeus' example 49.a and the
   published 2026 new moons (worst error under 3 minutes).
2. **The Noumenia (day 1).** A month began when the first thin crescent was seen at dusk. We take the first Athens sunset (37.97 N, 23.73 E, real
   sunset from the NOAA solar formulas, clock UTC+2) that comes at least 24 hours after the conjunction: a crescent is rarely visible sooner.
   The Greek day ran from sunset to sunset, so the Noumenia is the civil date of the daylight after that sunset.
3. **The year.** Hekatombaion 1 is the Noumenia of the first new moon after the summer solstice (Meeus ch. 27, with the 24-term correction;
   checked against example 27.a). The year runs to the next Hekatombaion 1: 12 or 13 months. In a 13-month year the extra month is
   **Poseideon II**, after Poseideon, the usual Athenian choice. Months come out 29 days (hollow) or 30 (full), as they did. Over 2015-2040 about
   10 years in 27 have 13 months, close to the Metonic 7 in 19.
4. **Labels.** `Maimakterion 1`, plus `dayName` (Noumenia, Hene kai Nea for the last day), `decade` (waxing / middle / waning), the Greek name and
   Greek numeral, and the Olympiad (Olympiad 1 began in the summer of 776 BC; 2026/27 is Olympiad 701, year 2).
5. **Limits (say this when showing it).** The real calendar was run by the archons, who could insert days or a month for festivals or politics, and
   crescent sighting depends on weather and the moon's angle. So this is *the calendar the astronomy implies*, not a record of what any archon
   declared; a historical date can differ by a day (or, near a leap year, a month). A moment (a `Date`) is first turned into its New York calendar
   date; a `'YYYY-MM-DD'` string is used as given.

Worked examples: 2026-07-16 = Hekatombaion 1 (Olympiad 701.2); 2026-10-12 = Pyanepsion 1; 2026-11-10 = Pyanepsion 30 (Hene kai Nea);
2026-11-11 = Maimakterion 1.

## Tests

```
python -X utf8 -m tests.test_polis_kit --static                                   # static + node (no browser)
flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_polis_kit    # + the headless browser check of the lab
```

## Wiring (for the lead; no shared file was edited)

Each app adds the two lines above, then:

| App | Adopt |
|---|---|
| Hestia (today) | `sundial` as the trading clock; `atticStamp` next to the date; `coin` for today's P&L; `lamp` while JSON loads |
| Helios / accounts, Performance | `columnFrame` by rank (`orderFor`): normal / good / record week cards; `laurel` gold on a new equity high, olive sprig on a steady week |
| Delphi, Oracle (game plan) | `inscribe({plaque:true})` for the reading title; `mosaic('waves', dense)` under the hero |
| Pnyx, Ekklesia (decisions) | `meander` on open motions, `live` while a vote is open |
| Journal / trade list, Trade pictures | `pottery` icons per trade (long = `horse`, short = `dolphin`, stop = `warrior`, target = `laurel`) and `coin` per closed trade |
| Treasury / Money apps (Mint, money machines) | `coin` for every $ figure; `inscribe({gild:true})` for totals; `pottery('scales')` as the empty state |
| Every app | replace spinners with `lamp`; `pottery(name, {frame:'tile'})` for empty states; `data-polis-attic` on dates |
| Polis home (agent C) / Polis life (agent B) | the skyline and civic modules can call `pottery`, `laurel`, `coin`, `atticDate`, `meander` directly |
| `sw.js` | add `olympus/polis.js`, `olympus/polis.css` (and `olympus/polis-lab.html` if the lab should work offline) to the precache list |

## Polis life in the apps (QA round 6, 2026-11-11)

`olympus/polis-life.js` draws the city's civic pieces from `olympus/polis.json`. An app places one with zero code:

```html
<script src="../olympus/polis-life.js?v=pl2" defer></script>
<section class="pl-place" data-polis-life="grove" aria-label="The olive grove: one tree per account" hidden></section>
```

The file is loaded once per page; each piece is drawn as one AGORA v2 card (`.pl-placed`: radius 20, `--ag-e2`, 18 px title). A piece with
nothing to show stays hidden (no empty civic cards); `data-polis-life-empty="show"` keeps the quiet line. `?demo=1` reads `polis-demo.json`
and says DEMO under the piece. A page that redraws itself (the Zenith home) uses `OLYMPUS_POLIS_LIFE.keep(host, kind, {when, label, before})`:
the piece is put back after every redraw, before the next paint, and a wiped herald stops its timer. `place(root)` runs the zero-code pass again.

| App | Piece | Where |
|---|---|---|
| Zenith home (root `index.html`) | herald | under the status and the accounts (`zenith_agora.css` orders it, keeps it out of the fold) |
| Herald | herald | between the newsstand and the paper |
| Pythia | oracle, festivals | after Today; after Coming up |
| Chronos | festivals | in the About sheet |
| Helios, Aegis | grove | after Drawdown left; after All three shields |
| Nike, Kronos | amphorae | after The shelves; after the month |
| Colosseum | statues | after Hall of champions |
| Journal | stoic | after the hero (Mind keeps no stoic line: its contract is that the page fetches nothing, and the line lives in `polis.json`) |
| Polis | all eight | right under the skyline (empty pieces hidden; no file = the labelled demo) |

Kit pieces placed the same round: the gold laurel beside Nike's "Your wins", the oil lamp while Polis's city life loads.
