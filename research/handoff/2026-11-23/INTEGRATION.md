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

### Round 2 (new -rt heads after 03:30 UTC)
| # | Branch | Head | Conflicts |
|---|---|---|---|
| 12 | night-notify-rt (2nd) | eb230be27 | tests/run_area.py |
| 13 | night-payout-rt | c4c8dc4a7 | none |
| 14 | night-cleanup-rt (2nd) | ab8a8aad4 | none |
| 15 | night-clockauto-rt | 3a23c382c | none |
| 16 | night-zerotouch-rt | ab7cf0098 | engine/go.py, tests/run_area.py |
| 17 | night-fleetmgr-rt (brings night-fleetmgr, night-rulewatch-rt, night-r50k) | cb513a246 | tests/run_area.py, tools/web_public/nq/trading_home_core.js |
| 18 | night-r50k-rt | 8763055ca | tests/run_area.py (+ a semantic clash, below) |
| 19 | night-rulewatch-rt | b0311df0b | none (already in via fleetmgr-rt) |

### Round 3 (heads after 04:00 UTC)
| # | Branch | Head | Conflicts |
|---|---|---|---|
| 20 | night-cleanup-rt (3rd) | 74f430d6b | none |
| 21 | night-payout-rt (2nd) | 6e7d8c0cb | none |
| 22 | night-reds (2nd) | 38853e73e | none |
| 23 | night-startfix-rt | 39b660f20 | none |
| 24 | night-truth-rt | 40fe89303 | none |
| 25 | night-brief-rt (brings night-brief) | aca9fee75 | none |
| 26 | night-pcguard-rt (brings night-pcguard + night-tasks) | ffeda5c02 | FIX_CLOCK.bat, engine/trade_home.py, tools/pc_report.py |
| 27 | night-tasks-rt | b12908fa0 | none (notes only) |

### Round 4 (heads after 04:25 UTC)
| # | Branch | Head | Conflicts |
|---|---|---|---|
| 28 | night-reds-rt (brings night-reds 3rd) | e019ca079 | tests/test_bat_menu.py (same ALLOW fix on both sides) |
| 29 | night-roll-rt (brings night-roll) | 5069d0098 | engine/trade_home.py, tests/run_area.py, tests/test_ops.py |
| 30 | night-verify-rt (brings night-verify) | 26ff54e39 | engine/trade_home.py, tests/run_area.py |

### Round 5 (heads after 04:55 UTC)
| # | Branch | Head | Conflicts |
|---|---|---|---|
| 31 | night-alertproof-rt (brings night-alertproof) | b513495b1 | none |
| 32 | night-hermetic-rt (brings night-hermetic) | f354e5c37 | none |
| 33 | night-k7proof-rt (brings night-k7proof) | 636d44b0d | none |
| 34 | night-mondaysim-rt (brings night-mondaysim) | 1cb533b08 | tests/run_area.py |
| 35 | night-rollback-rt (built on night-integrate 7bd71589e) | dcccbdd45 | tests/run_area.py |
| 36 | night-faststart-rt (brings night-faststart) | 70645b3b4 | research/lit/live_check.json (a test-written file: kept ours) |

### Round 6 (the lead's queued notes, read at 06:21 UTC)
| # | What | Head | Conflicts / notes |
|---|---|---|---|
| - | **night-pcguard(-rt) taken OUT** (lead: no pwsh test) | d323ecf86 | pcguard's 3 commits reverted by hand in ONE commit; night-tasks(-rt) kept (they came in the same merge) |
| 37 | night-decide | f5fffc734 | none |
| 38 | night-docs | e0e2db1f8 | STATE.md (docs' new 'Waiting on you' list kept + cleanup's ONE FRONT DOOR line); OWNER_MANUAL: MONDAY_SETUP.bat + the 'Your week' menu line = the merged menu (k, 10-14, M, T, P, R) |
| 39 | night-reds3 | 36a77cf07 | tests/test_me_hub.py: reds3's check kept (stricter: every after_run call under 'if not a.dry_run') |
| 40 | night-reds2 | 44b8a06b1 | tests/run_area.py |
| 41 | night-hermetic (final) | 786ab34e2 | none |
| 42 | night-faults | 43b898647 | none |
| 43 | night-asks | 278c24ab6 | none |
| 44 | night-addacct | 2fe11aa53 | none |
| 45 | night-secps | b16577d0a | none |
| 46 | night-startcheck (on faststart-rt) | 01eb3bd42 | none |
| 47 | night-startmsg (contains mondaysim-rt) | 4c26877eb | tests/run_area.py |
| 48 | night-seedata | fdcdde105 | none |
| 49 | night-payday | 30f16ca82 | business/mffu.html ?v= tags: the higher of each (payoutcoach v3, mffumodel v6, mffucenter v3); lead wire done: gate/index.html payoutcoach v=3 + test_gate_page pin |
| 50 | night-livevsbt (contains night-briefv2) | e84586e4c | tools/morning_brief.py, tests/test_notify.py (below) |
| 51 | night-newsweek | 4dfbefad9 | tests/run_area.py |
| 52 | night-tgweek | f8e3d2212 | tests/run_area.py, tests/test_notify.py (tgweek's 'half day, closes 13:15 ET' on build_full) |
| 53 | night-k7cloud (no workflow file in it) | e058d1c21 | tests/run_area.py |
| 54 | night-statesafe | ed76c71a2 | engine/live.py, engine/account_b.py, engine/post_update_check.py (below) |

Not merged: night-blitzfills (lead: out), night-wirepatch (lead applies at landing), night-calls, night-leadwires, night-landrehearsal (not on any list).

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

- **engine/go.py keep-alive prompt (zerotouch-rt):** zerotouch-rt's try/except (no console / piped stdin = left OFF, never a crash) + cleanup's
  `tools/bat/KEEPALIVE_OFF.bat` path.
- **trading_home_core.js (fleetmgr-rt vs startfix/truth):** HEAD's account lines (`accounts: acctRows`) AND fleetmgr's info-only Fleet line; one
  return with both. node --check OK; site_checks fine (the page loads it without a ?v= tag).
- **payout_autopilot.py `_write` (night-payout), fleet_mgr.py state save (night-fleetmgr) and post_update_check.save (night-verify) vs land-fixes:** bare `os.replace` -> `fsutil.replace`
  (land-fixes' Windows / OneDrive lock rule; test_selfheal red otherwise).
- **EVREOD semantic clash (startfix vs r50k):** night-startfix made `EVREOD` MFFU's confirmed Rapid EOD prefix (seen on the owner's PC); r50k's
  test still expected an EVREOD name with nothing learned to be "a choice". Kept startfix's rule (newer real-PC evidence; it arms nothing,
  the owner still taps and types the phrase). The test's "still a choice" case now uses a guess-only `MFFUEVRPD...` name, plus a new check
  that EVREOD at $50,000 = Rapid EOD 50K. test_rapid50k_onboard 27/27, test_onboard 38/38.

- **tools/pc_report.py (pcguard/tasks vs notify/payout/fleetmgr/rulewatch/cleanup-rt):** night-tasks moved the soft after-run hooks into
  `after_run(quiet)` (tests replace it so they never touch the PC's data/). The branches merged before it added 5 hooks inline
  (alert digest, payout autopilot, fleet manager, MFFU rules watch, moved-.bat shortcut fixer). All 5 now sit INSIDE `after_run`
  (same order, same try/except), and the main block calls `after_run(a.quiet)`. argparse: both sides' flags kept (`--pulse`, `--why`, `--by`, `--force`).
- **engine/trade_home.py alerts menu (pcguard/tasks vs cleanup):** cleanup's 3 = Alerts bus ON, 4 = OFF kept; night-tasks' "One report task"
  (tools.task_audit --fix) is now **5**; the status screen's to-do says "choose 5, then 5"; tests/test_task_audit follows (16/16).
- **FIX_CLOCK.bat (pcguard vs cleanup):** pcguard's PC GUARD comment lines + cleanup's `tools\bat\FIX_CLOCK_OFF.bat` undo path. pcguard's edit of the
  root FIX_CLOCK_OFF.bat landed on tools/bat/FIX_CLOCK_OFF.bat via git's rename detection. Its old-place names in docs/OWNER_MANUAL, engine/win_guard,
  scripts/win_guard.ps1, tests/test_win_guard, tools/morning_brief (STATUS.bat), tools/pc_report (CONNECT_DAY.bat), tools/task_audit were repathed.
- **brain-data.json (reds' rebuild):** now quotes LEDGER.md's old "GITHUB_SIGNIN.bat" line (history), so test_bat_menu ALLOWs that one generated file.

- **engine/trade_home.py (roll + verify vs pcguard/tasks/cleanup/notify/payout):** every helper kept (`_guard_line`, `_report_tasks`,
  `_roll_fact`, `_update_check`); `status_screen(..., tasks, guard, roll, upd)` takes all four; MENU = cleanup 10-14 + M, T, P, then roll's R;
  do_choice keeps M / P / T and adds R. R runs **tools/bat/ROLL.bat** (night-roll called `ROLL.bat` at the top folder, where cleanup no
  longer has it: R would have said "did not open"). Roll's / verify's owner lines that named ROLL.bat, ONE_TIME_SETUP.bat, CLEAN_PC.bat
  by the old place (engine/readiness READY fix, trade_home, post_update_check) now say tools/bat/.
- **notify-rt test b6 vs night-brief (date-dependent red):** night-brief sends a CME trading day's digest inside the 16:15 day summary
  ("in the day summary"); notify-rt's b6 ran on today's date, so it was red on every weekday. b6 now runs on a Saturday (one digest a
  day, then 'done today'), which keeps both intents; 27/27.
- **tests/test_ops.py (roll vs reds):** reds' stricter clock check kept (it also wants "Run as administrator").

- **morning brief (night-payday vs night-briefv2/livevsbt):** briefv2 made the PUSHED brief a new 5-line `build()` and renamed the old
  builder `build_full()`; night-payday's "REQUEST PAYOUT TODAY: ATLAS 25K $1,000 - ..." line lived only in the old builder, so the push
  would have lost it. build_full keeps payday's line AND livevsbt's line (keep = MAX_LINES - 4 - pay - lvb). The 5-line `build()` now puts
  payday's line FIRST (money in hand first) and the title ends " - REQUEST PAYOUT TODAY", only while a payout is ready. New check in
  test_notify h; test_live_vs_bt d3's source pin follows the merged line. notify 103/103, live_vs_bt 21/21, daily_brief 46/46.
- **state file damaged (night-statesafe vs night-faults):** faults made LIT / ATLAS start a clean day + one owner push when the state file
  is unreadable; statesafe (later, red team #19 pending) never starts a clean day: today's .bak, else a proved rebuild from exec_audit,
  else NO NEW ENTRIES today + its own alert. statesafe's version kept in live._restore and account_b._load (faults' clean-day branch is
  exactly what statesafe replaces; keeping both would push twice). faults 34/34, state_safe 30/30.
- **more bare os.replace:** fault_note.py (night-faults), go.py start_last (night-startmsg), post_update_check (statesafe made the same
  fix: its version kept) -> fsutil.replace. selfheal 14/14.
- **old-place .bat names in the new branches:** faults' CLEAN_STORAGE.bat text (engine/live.py, engine/ninjatrader.py: message text only),
  docs' STATE lines -> tools/bat/. docs/STATE_HISTORY.md (verbatim history) added to test_bat_menu's HISTORY. pcguard's
  CLAUDE_REFERENCE entry removed (pcguard is out).
- **Research Hub:** hub-data.json rebuilt (Decide statuses moved); its keep-alive line now reads the START-phrase rule from STATE.md.
- **live_check.json** = pc's copy (lead); tools/web_hub_snapshot.json = pc's copy (checked).
- **jarvis_biz (payplan red):** its payout pin followed night-payplan's payday.json (ATLAS about $800 around Wed Dec 23, source 2026-11-23). 130/130.

## Tests
Final full run on 7b8a653f7 (+ jarvis_biz news pin after it). 'mine' = caused by the merge (fixed above); 'pre-existing' = red on
land-fixes / pc too; 'branch' = red on that branch alone.
| Check | Result | Reds |
|---|---|---|
| python tests/smoke.py | 11/11 green | - |
| python -m engine.ninjatrader --selftest | OK | - |
| python tools/site_checks.py | all fine | - |
| python -m tests.test_lit_live (41dcac8e8) | OK: intraday 9,923 polls 0 differences (+29 on the known day 2026-04-03, the same on land-fixes); day-end 120/120 identical; paper LiveBot errors 0 | - |
| run_area pc | 127 suites PASS, 1 red | me_hub: every check passes, the run fails on a browser timeout clicking the Mix tab (pre-existing, same on land-fixes) |
| run_area money | 20 PASS, 1 red | business_goals: goals.json milestone dates moved with night-payplan's new payday plan (branch: payplan). Needs `python tools/money/goals_build.py` with the live board at landing (a cloud --offline build also rewrites accounts.json with 'PC: no report seen') |
| run_area nq | 53 PASS, 0 red | - |
| run_area cities | 5 PASS, 3 red | node_suites jarvis_biz (mine: news_week rebuild moved 'next big one' to newsweek's Nov 24 row; re-pinned after the run, 130/130); cities_page d (district banners) and kalshicity_page c (orb overlaps the 3D button): pre-existing (red on pc + hub before any merge) |
Not in any area, checked once: test_nq_desk 32/33 (colour tokens), pre-existing (same on land-fixes).

## Lead-only edits needed (not done here)
- **wirepatch:** `git apply --check research/handoff/2026-11-23/lead_wires.patch` fails only on its tools/ship.py hunk (reds2's vault_sync
  changed main() around it); the other hunks apply.
  **Fixed by night-wirepatch2 21f370c33 (10:48 UTC):** `git apply --check` of its `lead_wires_v2.patch` is CLEAN on night-integrate
  937029213 (checked 10:52 UTC). Not merged here: it only carries the patch for the lead (sw.js, build_web_dashboard.py, CLAUDE.md, ship.py).
- **business_goals:** `python tools/money/goals_build.py` (with the live board) at landing.
- **sw.js:** seedata / payday / decide page bumps (payoutcoach v3, mffumodel v6, mffucenter v3, gate g21, nq r33, decide.js) need the cache bump.
- **Check for the owner (not a Monday blocker):** tools/bat/MONEY_INBOX.bat registers the sign-in task "OlympusMoneyInbox" with its OWN full
  path (`/TR "%~f0" run`). If it was ever run from the top folder, that task now points at a file cleanup moved to tools/bat
  (cleanup's notes say no task runs a .bat: this one does). Fix: run tools/bat/MONEY_INBOX.bat once (it re-creates the task with /F).
- **MONDAY_SETUP.bat stays in the top folder** (13 kept .bat files): move it to tools/bat + a menu number only if you prefer.
- None from the merges for sw.js / build_web_dashboard.py / jarvis/apps.js / the APPS table. web_next/js/next/start.js text changed
  (one string): if web_next's worker precaches it with a ?v= tag, the lead bumps it (site_checks is green).
- tools/build_research_hub.py in ship / nightly after build_brain_hub.py (hub2 LEAD_WIRES).
