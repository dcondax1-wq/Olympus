# Monday integration rehearsal (night-integrate, 2026-11-23)

Base: `origin/land-fixes` 3ab7e559f (= pc + clockfix-rt + ready-rt + armfix-rt + fsutil + ATLAS glance fix + audit backlog).
Branch `night-integrate` only; nothing pushed to `pc`. No arming, no strategy / sizing change.

## Merged heads (in order)
| # | Branch | Head | Conflicts |
|---|---|---|---|
| 1 | night-notify | a71400732 | none |
| 2 | night-notify-rt | 53f51adc1 | tests/run_area.py |
| 3 | night-payout | a9bfa0745 | none (already had night-notify) |
| 4 | night-cleanup-rt (includes night-cleanup) | 17ce52d83 | docs/ALERTS.md, engine/alert_bus.py, engine/trade_home.py (+ a real bug, below) |
| 5 | site-land (Research Hub v2) | b45a5d74e | none |
| 6 | night-startfix | a224c401f | none |
| 7 | night-truth | ea1fe0b67 | tests/test_launch_checklist.py, tests/test_ops.py, tools/data_health.py |
| 8 | night-clockauto | d4b95e4b9 | none |
| 9 | night-zerotouch | 649fc9654 | STATE.md, docs/OWNER_MANUAL.md, engine/keepalive.py, tests/run_area.py (+ moved-.bat paths, below) |
| 10 | night-reds | 82b3ad644 | tests/test_ops.py |
| 11 | night-payplan | 14ab88069 | none |

## Resolutions (both sides' intent kept, no safety check dropped)
- **run_area.py (notify-rt, zerotouch):** append-only lines, both kept (`package_b` + `notify_rt`; `bat_menu`, `context_refresh`, `bat_shortcuts` + `zerotouch`), `if __name__` block kept last.
- **docs/ALERTS.md (cleanup-rt):** cleanup's `tools/bat/` paths + notify's "off also stops the zero-setup copies" note.
- **engine/alert_bus.py (cleanup-rt):** cleanup's `Test: tools/bat/TEST_ALERT.bat` line + notify's whole ZERO-SETUP PATH paragraph.
- **engine/trade_home.py MENU / do_choice (cleanup-rt):** all of cleanup's 10-14 + M, then notify / payout's T (test alerts) and P (payout). All handlers kept.
- **BUG FOUND in the merge (mine to fix):** notify's T action ran `run_bat("TEST_ALERT.bat")`, but cleanup moved that file to `tools/bat/`, and
  `bat_path` does not search there, so T would always say "[FIX] Nothing reached your phone". Fixed to `run_bat("tools/bat/TEST_ALERT.bat")`;
  tests/test_alert_map g now checks the tools/bat path (either slash, so it passes on the PC too). Then ran cleanup-rt's own
  `research/handoff/2026-11-23/cleanup/merge_notify.py` (renames notify's old-place names in docs/ALERTS.md, test_alert_map, alerts_setup).
- **tests/test_launch_checklist.py (truth):** kept HEAD's sealed version (12 base lines exact on a temp data folder + 3 fake extra accounts = 15).
  It already covers truth's D4 intent (the PC's extra accounts must not make it red) and is stricter.
- **tests/test_ops.py (truth, then reds):** truth = HEAD's text; reds' version kept (stricter: also checks "Run as administrator" in the fix). 114/114.
- **tools/data_health.py WHY (truth):** kept HEAD (cleanup), which is the newer truth: the ES/MES feed exists (`engine/ninjatrader.feed_instruments`),
  and cleanup added the GEX / CBOE / 1d refreshers (`tools/context_refresh.py`, `data_pull --latest` builds 1d). truth's text described the
  state before cleanup.
- **STATE.md (zerotouch):** both bullets (ONE FRONT DOOR + ZERO-TOUCH).
- **docs/OWNER_MANUAL.md keep-alive (zerotouch):** zerotouch's new "When: nothing extra ... START turns it on" text, with cleanup's `tools/bat/KEEPALIVE_OFF.bat` path.
- **engine/keepalive.py save (zerotouch):** zerotouch's new `owner_off` + `consent` fields AND land-fixes' `fsutil.replace` (the safe Windows replace), not `os.replace`.
- **zerotouch vs cleanup's .bat move:** zerotouch's new lines named moved files at the old top-folder place (KEEPALIVE_OFF, BOTS_BACK, ONE_TIME_SETUP):
  TRADE_HOME menu `k` pointed at a missing file (test_bat_menu b red). Repathed every such name to `tools/bat/` (engine/go.py, keepalive.py,
  recovery.py, trade_home.py ACTIONS k, test_zerotouch, docs/OWNER_MANUAL, STATE.md, web_next/js/next/start.js text).
- **MONDAY_SETUP.bat (zerotouch, new) stays in the top folder** as the one weekly double-click: test_bat_menu KEEP 12 -> 13 (NO_NUMBER: routine 8 is
  its menu twin) and docs/BAT_FILES.md has its reason line. **Lead decision** if it should instead move to tools/bat + a menu number.

## Tests
See the table in the final summary (sent to the lead). Script used for the moved-.bat lint: test_bat_menu d (all files, not only the first 25).

## Lead-only edits needed (not done here)
- None from the merges for sw.js / build_web_dashboard.py / jarvis/apps.js / the APPS table. web_next/js/next/start.js text changed
  (one string): if web_next's worker precaches it with a ?v= tag, the lead bumps it (site_checks is green).
- tools/build_research_hub.py in ship / nightly after build_brain_hub.py (hub2 LEAD_WIRES).
