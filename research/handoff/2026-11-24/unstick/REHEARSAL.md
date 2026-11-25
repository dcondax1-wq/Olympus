# Rehearsal of the owner's one line (2026-11-24 ~20:10 ET, cloud sandbox)

Setup: a clone at the PC's old code 75d5a60b9 on branch main; remote `olympus` with the PC's exact URL, redirected (insteadOf)
to a copy of pc tip 1c759cfbd. PC-like local state: data/accounts.json, rapid*.json, keepalive.json (all 4 ON), combo_50k.json,
tickrec.json, account_b.json (ATLAS block, second_model.json clean), orderflow_auto/note.json (untracked), logs/.
research/orderflow/results.json dirtied with a timestamp. Before the line, the old fast_forward said exactly the PC's
"skipped: local changes in tracked files (not touched): research/orderflow/results.json".

| Step (as cmd runs it) | Result |
|---|---|
| `git stash push -m "owner park" -- research/orderflow/results.json` | PASS: tree clean (only untracked data/ left) |
| Python form (no git on PATH needed), same effect | PASS |
| UPDATE.bat 1: `ops_checks --update-guard` (20:06 ET, flat) | PASS rc 0 "flat and outside trading time" |
| UPDATE.bat 4: `autoupdate --pull` | PASS "Updated to the newest version (75d5a60 -> 1c759cf)", 532 files, tree clean |
| Again with bot-made cache/dash files dirty (as on a running PC) | PASS (bot-made files never block) |
| UPDATE.bat 5: pip | nothing new: requirements.txt unchanged 75d5a60b9..pc; no new third-party import in engine/server/pc_report (pyarrow / matplotlib stay optional, guarded) |
| UPDATE.bat 6: new server.py boots, `--wait-server` | PASS "dashboard is up"; no traceback |
| UPDATE.bat 7: `--after-update` | all new modules load (Core 6, payout, fleet, rules watch, pulse, task audit, zero-touch, recovery, fault notes, keep-alive ON x4); the 4 reds are sandbox-only (no NinjaTrader folder / le_feed bars / bot not started) |

When: weekday 16:00-01:50 ET, or any time Sat/Sun, with the bot flat. Weekday 01:50-16:00 ET -> "it is trading time (01:50-16:00
ET): updating restarts the bot. Best after 16:00 ET." + "Update anyway? Type Y then Enter:" (anything but Y -> "Not updated. Best
time: after 16:00 ET."). Trade or LIT setup open -> "[FIX] Not updating now: a trade or a setup is open. Run UPDATE after it
closes." The stash stays done in both cases, and the hourly auto-update (outside trading time) then installs it by itself.
UPDATE.bat ends with "pause" (press a key; the bot already runs in its own window).

Re-arm: stop_bot.ps1 -KeepAutostart keeps data/autostart.json; run_bot.ps1 restarts server.py; server autostart ->
engine/autoresume.decide (the same code old and new) resumes ARMED when data/auto_resume.json holds the 50K + each real extra's
own proof (written by START + I ACCEPT LIVE RISK on the old code: go.py enable-auto-resume + account_cli.resume_optin),
NINJATRADER_LIVE=1, no kill / daily-loss today, NinjaTrader connected (waits 30 min). Feed now: ar = lit/atlas/rapid/b25k_2
all [on, armed]. The feed does not show the opt-in itself: if one is missing, the push says "Extra accounts NOT resumed ...
Start them by hand" and START_BOT + the phrase is needed. Feed rd also warns "ATLAS 25K is on Sim" (separate from the update).
