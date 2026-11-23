# night-startfix red team (2026-11-23): a224c401f -> night-startfix-rt

No fix needed in the code. One test file added (tests/test_startfix_rt.py, 16 cases).

| # | Finding | Sev |
|---|---|---|
| 1 | The hard / soft split: every route that could trade wrong stays HARD (stop): Zlarior on another Name, the 25K also an extra (double size), not NinjaTrader, not running, ATLAS ARMED on another Name / plan / Zlarior's 50K. SOFT is only an UNARMED ATLAS (its live gate refuses its orders). The NOT ARMED row + NOT TRADING banner still print (rows from arm_b), the Start page says "ATLAS NOT armed" once (no 60 s loop) | OK |
| 2 | known_role (used by new_accounts.candidates): exact-Name match over role_of + inventory + the Rapid files; a NEW Name is never "known"; no partial / case match. account_cli.add's name_problem refuses a Name any route already uses (one NinjaTrader account added once) | OK |
| 3 | A runtime "one account, two routes" check would be extra safety for hand-edited files, but the bot itself puts the Rapid's LIT lane in its cfg "accounts": a naive check would stop every START. Not added; if wanted it must skip the lane rows | LOW |
| 4 | MFFUEVREOD = Rapid only with a 25K / 50K balance (else the choice); a Builder Name never reads as Rapid | OK |
| 5 | remove_account of a Rapid: refused while the bot runs (never mid-trade); to_funded tags the row so START arms it with the typed phrase only | OK |

Merges (by hand): with night-zerotouch-rt engine/keepalive.py save_config = the same combine as night-truth (zerotouch's
json.dump with start + owner_off + consent, then fsutil.replace); with night-truth-rt tests/test_ops.py + test_launch_checklist.py
= the same fix on both sides: take startfix's. Clean with night-cleanup-rt, night-notify-rt, night-payout-rt.
Tests: startfix_rt 16/16, go 76/76, onboard 38/38, start_api 117/117, arm_rt 47/47, arm_report 28/28, new_accounts 14/14,
launch_checklist 69/69, ops 114/114, pc_selftest 66/66, accounts_cli 40/40, rapid 60/60, rapid25 95/95, account_box 41/41.
