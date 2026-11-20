# Siri / Shortcuts pack: lead wires (day-jarvis)

Helper may not edit sw.js, so these are for the lead:

1. `tools/web_public/jarvis/sw.js`: add to SHELL
   ```
   './shortcuts.html',
   './shortcuts.js?v=2',
   ```
   and bump CACHE (any new name, e.g. `jarvis-shell-sc1`).
2. Still pending from the expert job: SHELL `biz.js?v=b2` -> `biz.js?v=b4` (index.html and ask.js load b4 since the MFFU funded view; smoke site_checks flags it until applied).

No build file needed: the spoken shortcuts read the PC's public ntfy post from `status_feed.json` directly.
Tests: `python -X utf8 -m tests.test_jarvis_shortcuts` (15/15), registered in `run_area.py jarvis`.

## MFFU funded view (owner correction 2026-11-20)
biz.js `fundedView` / `fundedLine`: a funded account is spoken from $0 the way MFFU shows it (ATLAS "$401", floor -$1,000,
earliest payout at $1,350, goal $1,000 at $2,100, you get $800; 50K: -$2,000 / $2,600 / $2,000 at $4,100). Uses
`PC_FEED.mffuView(acct)` when a page has it (archive team, not landed yet; accepts a number or {profit} / {balance}), else balance - start.
Evals unchanged. Accounts + payout-now answers; the Siri accounts steps add a "Calculate" (balance minus 25,000).
