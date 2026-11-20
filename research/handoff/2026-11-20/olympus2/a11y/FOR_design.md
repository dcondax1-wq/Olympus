# A11Y -> DESIGN: the shared fixes first (kit), then your 19 apps

From the A11Y team's sweep (`python tools/a11y_sweep.py`, 2026-11-20, commit 7b2bf6a2). It covers 33 pages x 12 screens: 320 / 390 / 430 px,
dark AGORA + light Ivory, reduced motion on and off. It runs axe-core 4.10.2 plus our iPhone rules. Scores and every issue: `BASELINE.md`.
Your full fix list (one line per CSS rule, with file:line and the apps each line fixes) is `raw/fixes_design.md`. Every fix below was
checked in Chromium at 320 px where it says **verified**.

**The good news:** reduced motion is respected on every page. With it on, no page moves (screenshots taken 1 s apart are the same). Pinch
zoom is never blocked, and heading order and form labels are clean. **The bad news is mostly two things:** small body text (671 elements
across all pages) and a handful of breakages listed below.

## Part 1: kit changes (olympus/). Each one fixes many apps at once. Ranked by how many issues it clears.

### K1. a11y.js gives every `[aria-live]` list `role=status` + `aria-atomic=true` (it breaks lists for VoiceOver). Fixes ~35 issues on inbox, helios, board.
`tools/web_public/olympus/a11y.js:211-218` (`toasts()`): a `<ul aria-live="polite">` gets `role="status"`. That removes its list role, so
axe reports `aria-allowed-role` on the ul and `listitem` on every li. `aria-atomic="true"` also makes VoiceOver re-read the whole list on every
change. Fix: leave lists and tables alone.
```js
      if (skipped(el)) continue;
      var listy = /^(UL|OL|DL|TABLE|TBODY)$/.test(el.tagName);          // a live list keeps its list role; VoiceOver reads only what changed
      bad = ...;                                                          // (unchanged)
      if (!listy && !el.getAttribute('role')) el.setAttribute('role', bad ? 'alert' : 'status');
      if (!el.getAttribute('aria-live')) el.setAttribute('aria-live', bad ? 'assertive' : 'polite');
      if (!listy && !el.getAttribute('aria-atomic')) el.setAttribute('aria-atomic', 'true');
```
Hit: `inbox #list` (24), `helios ul[aria-live]` in the brief card + `.rw-row` (6), `board #feed` (5).

### K2. The type scale. Body text under 15 px is the biggest problem (671 elements, on every app).
The sentences are set in `--ag-fs-sub` (14), `--ag-fs-foot` (13) and `--ag-fs-cap` (12). The app CSS also hard-codes `13px` (304 elements) /
`14px` (164) / `12px` (93). Proposal (`tools/web_public/olympus/agora.css`):
```css
/* :23-26 */
  --ag-fs-cap: .8125rem;   /* 13  chip text, stat labels, a few words: never a sentence (was 12) */
  --ag-fs-foot: .875rem;   /* 14  short footnote labels (was 13) */
  --ag-fs-sub: .9375rem;   /* 15  secondary body = body size, softer colour (was 14) */
  --ag-fs-note: .9375rem;  /* NEW 15  any sentence in a muted colour (empty states, hints, "as of" lines) */
```
Then use the sentence token in the kit classes that hold sentences:
```css
/* agora.css:79  */ .ag-foot { font: 400 var(--ag-fs-note)/1.42 var(--ag-sans); ... }
/* agora.css:111 */ .ag-stat-sub { font: 400 var(--ag-fs-foot)/1.3 var(--ag-sans); ... }
/* agora.css:125 */ .ag-row-sub { font: 400 var(--ag-fs-note)/1.35 var(--ag-sans); ... }
/* agora.css:193 */ .ag-state-text { font: 400 var(--ag-fs-note)/1.45 var(--ag-sans); ... }
/* pulse.css:19  */ .pu-ts { font-size: var(--ag-fs-foot, .875rem); }      /* 12 -> 14: business, chrysos, demeter, helios, hera, journal, kronos, ledger, mercury, oikos */
/* pulse.css:33  */ .pu-empty { ...; font-size: var(--ag-fs-note, .9375rem); }  /* 13 -> 15: aegis, compass, demeter, helios, planner, pnyx */
```
**The AGORA app base sets the sizes, so the apps cannot win.** These rules carry `main#app` id specificity and beat an app's own
`.note { font-size: 15px }`. I proved this on agency: its own 15 px `.note` stayed at 13 px until I repeated the kit selector. These are the
lines that keep most pages' status line, notes and footers small (`tools/web_public/olympus/agora.css`):
```css
/* :303 */ main#app:where(...) > header.top .brand .sub { font: 400 var(--ag-fs-sub)/1.35 ... }     /* the page's one-line purpose: 14 -> var(--ag-fs-note) */
/* :309 */ main#app:where(...) > #status.note { ...; font: 400 var(--ag-fs-foot)/1.45 ... }          /* the status / "as of" line: 13 -> var(--ag-fs-note) */
/* :317 */ main#app:where(...) .ag-card .note { font-size: var(--ag-fs-foot); ... }                  /* every card note: 13 -> var(--ag-fs-note) */
/* :350 */ main#app:where(...) > .foot { ...; font-size: var(--ag-fs-cap); ... }                     /* the page footer: 12 -> var(--ag-fs-note) */
```
These four lines alone lift the main sentences on every AGORA app (aegis, pnyx, demeter, compass, clio, business, chrysos, hera, mercury,
oikos, planner, settings, helios, kronos, journal, ledger, agency, inbox ...).

Rule for the apps (put it in docs/DESIGN_AGORA.md): **a sentence is never under 15 px. A label of 1-4 words may be 13 px. Nothing is under 12 px.**
The per-app px lines (e.g. `aegis/aegis.css:24 .note { font-size: 13px }` -> `var(--ag-fs-note)`) are listed in `raw/fixes_design.md`, grouped by rule.

### K3. Tap targets in the kit: the chip and the segmented control are under 44 px.
```css
/* agora.css:146 */ .ag-chip { ...; min-height: 44px; ... }                 /* was 36px */
/* agora.css:151 */ .ag-seg button, .ag-seg a { ...; min-height: 44px; ... } /* was 38px */
/* a11y.css:10   */ html[data-oly-text="big"] :where(.oly-chip) { min-height: 44px; }   /* was 36px */
```
Measured, not only read in the CSS: zenith `header.top .iconbtn` is 38x38 (`tools/web_public/polish.css:36` `height: 38px` ->
`height: 44px; width: 44px`): Search, Refresh, Status. The launcher button `.oly-lbtn` (42x40) lives in `launcher.js`, a lead-only file,
so it is on the lead's list (LEAD_WIRES.md).

### K4. The tab bar in shell.css: 11 px fixed text (ledger, settings).
`tools/web_public/olympus/shell.css:68` `font-size: 11px` -> `font-size: .75rem;` (12 px, and it grows with Dynamic Type). The bar's safe
area is already right: `--o-sab` = `env(safe-area-inset-bottom)`.

### K5. The page title does not grow with Dynamic Type (21 apps).
`agora.css:73` `.ag-title { font-size: clamp(1.5rem, 7vw, var(--ag-fs-h1)) }`: between 320 and 430 px the 7vw middle wins, so a bigger
text size barely moves the title. Fix: `font-size: clamp(1.5rem, 1.25rem + 2.5vw, var(--ag-fs-h1));` (the same size on a 390 px phone,
and it grows with rem).

### K6. Grid blowout: one wide child makes the page scroll sideways at 320 px (atlas, journal, oikos). Kit guard proposed.
A CSS grid with no `grid-template-columns` sizes its column to the widest child's min-content (a nowrap chip row, a table). One kit line
stops this for every card and list:
```css
/* agora.css, section 2 (base) */
:where(main#app, .ag-card, .card, .ag-list) { grid-template-columns: minmax(0, 1fr); }
:where(main#app, .ag-card, .card) > * { min-width: 0; }
```
(Safe: it only applies where the element is already `display: grid`. Flex and block ignore grid-template-columns.) The exact per-app fixes
are in Part 2, verified.

### K7. Light theme (Ivory): hard-coded hex ink skips the theme and fails contrast in daylight.
`mercury/mercury.css:30` `.pill.info { color: #7fa7c2 }` gives 2.51:1 on Ivory's #fffdfa. Use `color: var(--ag-aegean-text)`: themes.js
`extras()` already gives a 4.6:1 info ink for every look. The rule for the apps: **ink colours are tokens (`--ag-*-text`), never hex**.
The same bug sits in trading `nqdeep.css .nqd-heat td` (DATA TRUTH's file) and kalshi.

### K8. Money in colour alone (hera, ledger, oikos, journal). Add a kit helper.
Some amounts are only red or only green, with no sign and no word: `$161` red, `$13,082` green. Proposal: `OLYMPUS.money(v, {sign:true})`
returns `+$1,280` / `−$80` (a real minus sign; VoiceOver reads "minus"). The `.pos` / `.neg` colour stays. The apps switch their `.neg` /
`.pos` tiles to it. Exact elements: hera `#cashTiles .tile b.neg`, `#mTiles .tile b.neg/.pos` (hera.js:50, :58). ledger
`.card ul.kv span.v.neg/.pos`. oikos `#leaks span.usd.neg`, `#taxKv dd.neg`. journal `b#tInt`.

### K9. The pages without a11y.js get no focus ring, no auto names and no px-text growth on the iPhone.
`olympus/a11y.js` is missing from: **zenith (index.html), atlas**, plus widget, kalshi, jarvis, gate and the hubs (their teams are told).
The two yours: add `<script src="olympus/a11y.js" defer></script>` (zenith) and `<script src="../olympus/a11y.js" defer></script>`
(atlas). That alone fixes atlas's invisible focus on `input#query` (`atlas.css:65` `outline:0`). It also stops counting zenith's 21 and
atlas's 36 px-text (Dynamic Type) issues, because on a touch phone a11y.js grows px text too, through iOS text-size-adjust.

## Part 2: your apps, ranked (score = BASELINE.md; issues = every element failing a rule)

| App | Score | Fix first (exact) |
|---|---|---|
| atlas | 71 | **sideways scroll at 320 px** (page 344 px wide): `atlas.css:57` `.deck{margin:26px 0 24px;display:grid;gap:14px}` -> add `grid-template-columns:minmax(0,1fr)` (**verified**: 344 -> 320). Focus on `input#query`: K9. Link `aside.command-glass p > a` "The four doors, short" is 150x19: `display:inline-flex;min-height:44px;align-items:center` |
| oikos | 73 | **sideways scroll at 320**: `oikos.css:92` `.lad{...}` -> `table-layout:fixed` + `.lad .pill{white-space:normal}` (**verified**: 338 -> 320). **12 bars with role=img and no name**: `oikos.js:57` `bar(frac, cls)` sets `role=img` with no label -> `b.setAttribute('aria-label', Math.round(frac*100) + '% ' + (label \|\| ''))` (household.js:26 already does this right). Colour-only money: K8. `.lad td small` 11px (`oikos.css:89`) -> `.75rem` |
| zenith | 79 | tap: `polish.css:36` iconbtn 38 -> 44 (K3). px text in the index.html `<style>`: `.note` :145 12.5px, `.zeus-g` 13px, `.pl-kicker` 12.5px, `.pl-plain` 13.5px, `.zeus-n small` 11px -> rem tokens (K2), and a11y.js (K9) |
| journal | 81 | **sideways scroll at 320** (363 px): `journal.css` -> `#tlist .trade { grid-template-columns: minmax(0, 1fr); }` (**verified**: 363 -> 320; the nowrap `.chips` row at :66 was the wide child). 27 small-text lines, colour-only `b#tInt` (K8) |
| kronos | 85 | `index.html:56` `<div class="grid" id="grid" role="grid">` has gridcells with no `role="row"` (26 axe issues: aria-required-children/parent). Fix: `role="list"` on #grid and `role="listitem"` on each `.cell` in `kronos.js:46` (each keeps its aria-label "Nov 1: no trade"). Or wrap each week in `<div role="row">` |
| ledger | 88 | K4 (tab bar 11px), K8 (`span.v.neg`/`.pos`), 23 small-text |
| hera | 85 | K8 (4 tiles), 24 small-text |
| mercury | 85 | K7: `mercury.css:30` `.pill.info{color:#7fa7c2}` -> `var(--ag-aegean-text)` (12 pills, light theme 2.51:1). `.pill` (:29) is `font: 700 12px` -> `var(--ag-fs-cap)` |
| helios | 85 | K1 (the live ul) |
| aegis, pnyx, demeter, fates, business, chrysos, compass, clio, planner, settings | 92 | small-text only (settings: K4 too) (K2 + their px lines in raw/fixes_design.md). demeter `#mults .ag-chip` is 44x44 already, fine |

## How to check after landing
`python tools/a11y_sweep.py --apps atlas,oikos,journal --quick` (2 min). Then the whole site against this baseline:
`python tools/a11y_sweep.py --compare research/handoff/2026-11-20/olympus2/a11y/baseline.json` (about 9 min, 3 Chromiums).
