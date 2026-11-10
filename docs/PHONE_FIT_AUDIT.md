# Phone-fit audit of the night's apps (2026-11-10)

Tool: `python tools/phone_fit_audit.py` (reusable, read only). It serves `tools/web_public` on a free port, opens each app at 390x844 and 375x667 with `?demo=1&q=low` in ONE Chromium, and checks:
no horizontal scroll, nothing wider than the viewport, no clipped text, every tap target >= 44 px, no console error / failed request / off-origin request, no heading under a fixed bar, text contrast >= 4.5:1 (3:1 for large text) against the real background.
Prints a table, saves a screenshot per view (`--out`), `--json` for the raw report, `--apps a,b`, `--small-only`, `--timeout` per app view (a stuck app is a FAIL, the run goes on). Exit code 1 on any FAIL. A missing optional `*.json` (the app falls back to its fixture) and a blocked off-origin request are WARN, not FAIL.

## Before and after (34 app views: 17 apps x 2 sizes)

| App | Before | Fix (the app's own CSS, appended at the end) | After |
|---|---|---|---|
| delphi, planner, mint, mercury, stoa, aegis, lyceum, nike | clean | none | clean |
| pnyx, sibyl, oikos, arbiter, moirai | contrast: gain / loss words 4.30:1 and 4.29:1 (olive / terracotta on the raised panels) | `.pos / .neg / .pill.ok / .pill.bad` lightened (#a0ac6e, #e08a6b: 6+:1) | clean |
| chrysos | contrast: pill and gain words 3.51:1, a note 4.02:1 | same colours, `.note` uses the soft text token | clean |
| kronos | clipped text in the calendar day cells ("+$1,020" cut at 34 px), day numbers 4.28:1, gain / loss 3.67:1 on green / red cells | grid 10 px wider inside its card, 10 px amounts without clipping, lighter cell colours | clean |
| epilogue | contrast: pressed "Ticked: done" button 4.16:1 | pressed colour #a0ac6e | clean |
| argo | contrast: delete "x" 4.29:1 | `.btn.del` #e08a6b | clean |
| kairos, kratos, pythia, mintcity, gallery | not in this tree: the audit skips them (run it again after they merge) | | |

Totals: 20 failing checks before, 0 after. The tests of every touched app still pass (pnyx 51, chrysos 59, sibyl 56, oikos 65, arbiter 50, kronos 54, moirai 49, epilogue 53, argo 59).

## Notes
- Only app CSS was touched; no logic, no tests, none of the files the lead owns.
- WARN left on purpose: `oikos` asks for the optional `money/oikos.json` (404 on the static server, falls back to its fixture even with `?demo=1`).
- The root cause of 8 of the 9 colour fixes is two shared tokens: `--ag-olive` #7f8a52 and `--ag-terra` #c96a4a are 4.2:1 to 4.3:1 on the raised panel (#26211b / #2a2217). A one-line change of those two tokens in `olympus/agora.css` (for example #a0ac6e and #e08a6b for TEXT use) would fix every other app at once; it was left alone because the brief says each app's own files.

---
# Round 2 (2026-11-10, later): the last five apps, the shared tokens, the iPhone mode

## 1. kairos, kratos, pythia, mintcity, gallery (and argo) at 390x844 / 375x667
Before: kairos (small labels on the heat cells 2.3:1 to 4.4:1, the empty cells were faded with `opacity`), gallery (the hint on the lit stage 4.10:1). kratos, pythia, mintcity, argo were clean.
Fixed in their own CSS: kairos (small labels use the soft / text ink, an empty cell is dashed and plain, not faded), gallery (the hint uses the soft ink). After: 0 failing checks. There is no `compass` app in this tree (nothing to audit).

## 2. Shared tokens (`olympus/agora.css`)
Added `--ag-olive-text: #a0ac6e` and `--ag-terra-text: #e08a6b` (6:1 or better on the raised panels; the fills `--ag-olive` / `--ag-terra` are unchanged) and `.ag-good` / `.ag-bad` now use them. Nothing else in the file changed.
Checks (machine under heavy load, so sections were run separately): `tests.test_olympus_themes` baseline was 112/112 before the change; after it, `jarvis` 43/43, `default zenith` 61/61, the nine app pages 78/78 (the computed-variable baseline still equals `tests/fixtures/olympus_default_vars.json`: nothing was regenerated). `tests.test_olympus_a11y` 20/20. One full-file run of the themes test stopped at a `#moreB` click timeout in the Jarvis section (a Look sheet intercepting the click while the load average was above 20); the same section passes alone, and it passed before the change under the same file.
Apps can now use the tokens (clio, dionysus, demeter, hestia do, with a hex fallback).

## 3. `--iphone` mode and the whole suite
`python tools/phone_fit_audit.py --iphone --all` uses Playwright's `iPhone 14` (390x664 visible area, DPR 3, touch, mobile) and `iPhone SE` (320x568, the narrowest iPhone) descriptors over every folder of `tools/web_public` that has an `index.html` and a `jarvis.json` (57 apps). Hidden helper text (1 px `.sr`) and intended line clamps are not counted as clipped text.

### New / AGORA apps (28, all fixed): clean at both devices
aegis, apollo, arbiter, argo, chrysos, clio, delphi, demeter, dionysus, epilogue, gallery, hera, hestia, kairos, kratos, kronos, lyceum, mercury, mint, mintcity, moirai, nike, oikos, planner, pnyx, pythia, sibyl, stoa.

| App | iPhone finding | Fix (its own files) |
|---|---|---|
| argo | the island hit areas were 42 px high on a 320 px screen | hit ring radius 28 -> 34 (map units) |
| mintcity | the five district buttons were 39 px wide on a 320 px screen | hit rectangle 56 -> 66 wide |
| kairos | 37 px heat cells at 320 px | 3 columns under 340 px |
| clio, demeter, dionysus, hestia | gain / loss words and headings 4.3:1 | use `--ag-olive-text` / `--ag-terra-text` |

### Old apps: failures left for the lead (not touched). `contrast` on text over a canvas / 3D scene (mind, observatory, oracle) can be a false reading
| App | FAILs (first example; device) |
|---|---|
| arena | clip: buttonbutton 53>50 (iP14, iPSE); tap: buttonbutton 38x44 (iPSE) |
| ares | tap: buttonbutton 41x44 (iPSE) |
| argus | contrast: b#fixN 3.43:1 "1" (iP14, iPSE) |
| bridge | contrast: bb 3.90:1 "2" (iP14, iPSE) |
| cities | clip: h1#title 141>80 (iPSE) |
| datacity | clip: h1h1 80>44 (iPSE); tap: button.tab 35x44 (iPSE) |
| fates | contrast: b.r 3.89:1 "10%" (iP14, iPSE); clip: span.l 91>73 (iPSE) |
| forum | contrast: span.dglyph 3.78:1 "Κ" (iP14, iPSE) |
| hephaestus | contrast: button.chip.nt 2.70:1 "4R" (iP14, iPSE) |
| hermes | clip: span#pos.pos 100>37 (iPSE) |
| kalshicity | clip: p#bot.live 1162>332 (iP14, iPSE); tap: buttonbutton 38x44 (iP14, iPSE) |
| labyrinth | tap: buttonbutton 39x44 (iPSE) |
| ledger | contrast: b#mNet.pos 4.19:1 "+$5.80" (iP14, iPSE) |
| mind | clip: spanspan 226>135 (iP14, iPSE); contrast: bb 1.00:1 "MIND" (iP14, iPSE) |
| nemesis | clip: span#wkSub 107>36 (iPSE) |
| observatory | contrast: spanspan 1.39:1 "Data City" (iP14, iPSE); tap: a.back 37x48 (iPSE) |
| odeon | tap: button.tick.k-sweep 14x14 (iP14, iPSE) |
| oracle | clip: span#demo-tag.tag 127>90 (iP14, iPSE); contrast: timetime 3.38:1 "00:10" (iP14, iPSE); tap: input#scrub 40x44 (iPSE) |
| plutus | clip: p#vline.vline h 31>28 (iP14, iPSE) |
| tree | clip: span.c 188>169 (iPSE) |
| tyche | clip: b#h-roi 54>50 (iPSE); tap: buttonbutton 33x44 (iPSE) |

Clean at both iPhone sizes among the old apps: athena, atlas, chronos, inbox, journal, pantheon, prometheus, settings.
Raw reports: `python tools/phone_fit_audit.py --iphone --all --json iphone.json`. WARN lines (missing optional JSON, blocked off-origin feeds such as the Kalshi and dashboard raw files) are not failures.
