# night-hermetic red team (2026-11-23): d1a7839c1 -> night-hermetic-rt

| # | Finding | Sev | Fixed |
|---|---|---|---|
| 1 | test_launch_checklist, test_ops and test_heartbeat made the LIVE data/push_pc_key.json (engine/push makes the PC key on first use). On the owner's PC the key exists (no visible harm today), but with the new write guard in raise mode a fresh / missing key turns the Sunday self-test red, and on any checkout a test wrote a live key | MED | each sets engine.push.PC_KEY_PATH to a temp file; tools/hermetic_scan.py --selftest: 0 dirty of 25 (was 1), test_hermetic 14/14 (was 12/14) |
| 2 | test_live_dryrun: 0 reference trades in its window, IndexError | pre-existing | the same on origin/pc (data window) |

Checked OK: the write guard (tests/write_guard/sitecustomize.py) loads only with tests/write_guard on PYTHONPATH AND LE_WRITE_GUARD
set, which only engine/pc_selftest.child_env does (the self-test children, with a temp HOME / USERPROFILE / OLYMPUS_HOME); the live
bot never gets it. go._arm_status_path: the real START keeps data/arm_status.json (SECOND_PATH is None on the PC; only
tools/rehearse_day sets it, to a temp file). pc_report.gather writes the agency card only for the real root. Merge with
night-integrate 7bd71589e: clean.
Tests: hermetic 14/14, hermetic_scan --selftest 0 dirty of 25, heartbeat 38/38, launch_checklist 69/69, ops 114/114, nqops 34/34,
public_build_privacy 59/59, pc_selftest 65/65, arm_rt 47/47, arm_report 28/28, go 68/68, state_pulse 58/58.
