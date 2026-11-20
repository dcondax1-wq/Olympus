# DESIGN team report (day-arenas, 2026-11-20, owner: "make Olympus as a whole better")

## In one table (my 20 pages x dark and Ivory light = 40 page views, measured by `tools/design_audit.py` at 390 x 844)

| What the bar checks | Before | After |
|---|---|---|
| Page views with no miss at all | 13 of 40 | **26 of 40** |
| All misses | 51 | **19** |
| Texts below AA contrast | 22 | **0** |
| Texts under 12 px | 176 | **0** |
| Taps under 44 px | 2 | **0** |
| Pages that stay dark under a light look | 3 (Settings, Atlas, Fates) | **1** (Fates: a 3D stage by design) |
| Layout shift on Zenith Home | 0.15 (banner at 4 s) + 0.02 | **0.01 + 0.02** |
| Ledger / Settings tab labels | 11 px (a shell.css rule for Zenith's bar hit them) | **13-15 px pills** |

The 19 misses left: 3D scene start long tasks in the headless browser (Ledger 1.2 s, Kronos 1.5 s, Fates 1.7 s, Oikos 0.4 s; a phone GPU is much faster),
files only the PC publishes (`business.json`, `money/household.json` on a local server; `kalshi.json`, `money/scoreboard.json` on a local build),
Fates staying dark, Atlas keeping its own sheet (now on the shared colour slots), and Zenith's small 0.02 shift. Tables: `audit_before.md`, `audit_after.md`.

## What changed
1. **The design system is one source**: `docs/DESIGN_SYSTEM.md` (the 4 shared files and their order, every token, the component set, the 8 audit rules,
   Settings = the one place) and the live page **`/olympus/kit.html`** (every token and component as the apps draw them, pulse cards with example data,
   motion demo, a look picker that previews only).
2. **The audit tool**: `python tools/design_audit.py --site <site>` (kit sheets, light-ready, console errors, failed requests, first paint, longest task,
   layout shift, sideways, taps < 44 px incl. invisible tap rings, text < 12 px, AA contrast on the real background incl. srgb colours, fonts, radii).
3. **Every app in my slice on the kit**: `data-oly-shell="app"` + `shell.css` last on all of them (plan.html, Settings, Atlas added); the 12 px floor
   (Kronos calendar, Hera fleet card, Business dash tags, Oikos, Fates, pulse badges, Zenith tab labels and ZEUS card tags); text-safe colours for every
   pill / tag (Mercury, Clio, Kronos blue pills; Journal's "ONE rule"; Zenith's REAL tag; Atlas buttons and door headings); Atlas on the shared colour slots
   with the light look; plan.html and Atlas paint the chosen look themselves (no kit engine there).
4. **Zenith**: the "PC silent" banner now has the strip's one-row shape (no jump when it arrives late); the header's 38-40 px keys answer a 44 px tap
   (invisible ring); the inline shell layer stays in step with shell.css.
5. **Settings is the one place**: new **Phone notifications** card (on / off on this phone, link to the card, what the PC sends and where to change it)
   and **How old the numbers are** (last PC report and cloud copy the money cards saw, Live / Quiet / Old), both offline from this phone's storage;
   Settings now also renders in a light look and its tab pills are back.
6. **Motion**: one curve (`--ag-ease`) and three speeds (200 / 260 / 340 ms) for the bars, cards and the Compass needle across the slice; reduced motion
   stops everything (shell.css). Sounds: unchanged kit cues (`data-oly-cue`, pulse taps), the Sound switch decides.
7. **Fixes found on the way**: shell.css's Zenith bottom-bar rule shrank Ledger's and Settings' in-page tabs (I caused it this morning by adding shell.css;
   scoped now); test_decide's browser part waited forever because the owner answered all 15 cards (it serves its own open copy now).

## Tests
smoke 9/9; pulse 156/156; settings 92/92; atlas_ui 36/36 + node 4/4 + 3/3; business 85/85; business_pages 40/40; money_door 48/48; decide 31/31;
ledger 88/88; kronos 54/54; hera 40/40; fates 79/79; oikos 65/65; journal 86/86; compass 57/57; mercury 40/40; clio 47/47; chrysos 61/61; pnyx 51/51;
aegis 53/53; demeter 41/41; helios 55/55; planner 170/170; zenith_nq 20/20 (version pin updated); zenith_mode 70/70; olympus_shell 42/42; site_sweep 4/4; apps_list 44/44.

## Shots
`shots/before-<page>-dark|light.jpg` and `shots/after-<page>-dark|light.jpg` for all 20 pages (390 x 844, 2x).
Cross-team asks: `ASKS.md`. Lead-only edits: `LEAD_WIRES.md`.
