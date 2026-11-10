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
