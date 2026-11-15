# Setup everything: one double-click (2026-11-14)

## Your step
1. Download the code zip (`OLYMPUS_BACKUP_...zip`) and its `.sha256.txt` into Downloads, open the zip, double-click `SETUP_EVERYTHING.bat` and answer what the window asks (the first time a GitHub window may open: sign in as **dcondax1-wq**; on Sunday after 6 PM ET you type YES, then the live phrase yourself).

| What | Result |
|---|---|
| One window | the PC jobs in order: 1 new code, 1b auto-update (once), 2 phone link, 3 go live on the evals; big headers, one summary line per step at the end |
| No more zips | step 1b turns on auto-update once: from then on the PC gets new code from your private backup by itself, only when no trade is open and never during trading hours (`docs/AUTO_UPDATE.md`) |
| Safe to double-click again | each step is checked first and skipped when it is done (the zip is already in, auto-update is already on, the link is already on, both evals are already armed) |
| Going live | only after you type YES, and not before Sunday 18:00 ET (the window refuses an earlier YES and waits); you type the live phrase yourself |
| A failure | one line: what happened, the exact fix, "send a photo of this window". Auto-update never stops the window: a problem there is one [SKIP] line and steps 2 and 3 go on |
| Trading | the strategy and sizing are the repo's: an OLDER copy of `live_model*.json` (a version the repo itself had) gets the new values, so an approved sizing change reaches the PC; a copy you changed yourself is kept; nothing is armed without your phrase |

## What the window does
| Step | It does | Skipped when | It never does |
|---|---|---|---|
| 1 New code | finds the newest `OLYMPUS_BACKUP_*.zip` in Downloads / on the Desktop / next to the .bat (or the zip dragged onto the .bat) and its `.sha256.txt`; takes the updater out of that zip and runs `tools/update_from_zip.py --check`, then the update (same rules as UPDATE_FROM_ZIP.bat: checksum, local-only files kept, an older `live_model*.json` copy gets the new values while one you changed is kept, a backup, UNDO_UPDATE.bat undoes it) | this PC already updates itself from the backup (step 1b ran: "This PC updates itself from the backup; no zip needed"), or this very zip was already applied (the update's own record: a fix made on the PC afterwards is never undone by running it again), or the folder already matches it, or the zip is older than the code already there | stop a bot with an open trade; stop the bot without your Y; start a bot server that was not running |
| ... the bot | a running bot server is stopped first only after you type Y (the STOP_BOT.bat stop: it also clears the auto-start record) and started again after step 1b (one stop for both), hidden, with the bot itself stopped; while the market is open the same single question says so, before anything is stopped | no update needed | resume or arm the bot |
| 1b Auto-update | asks the bot folder's own code whether it is on (`python -m engine.autoupdate --source-status`, read only); if not, turns it on (`--connect`): the folder becomes the backup's newest code (the private repo `dcondax1-wq/olympus`), with a snapshot first and everything put back if anything fails. A GitHub sign-in window may open the first time: sign in as the account named in `update_source.json` (dcondax1-wq). The bot server is stopped for it: the stop of step 1 is reused, else one Y (never with an open trade; while the market is open the question says so), and it is started again right after | already on, or this code has no auto-update yet (a newer zip brings it) | stop a bot with an open trade; stop the window: "could not reach the backup", "not now", "Git is not installed" and "put back" are each one [SKIP] line and the zip way still works |
| 2 Phone link | `scripts/live_link.ps1` (LIVE_LINK.bat): Tailscale installed, signed in, HTTPS, `tailscale serve` to the bot server; its messages in this window's words; Enter tries again, LATER leaves it for another time; the link shown big and put on the clipboard | `tailscale serve` already points at the bot server (no Funnel) and the site task is there | turn on Funnel (the internet) |
| 3 Go live | the pause screen: "Is it Sunday after 6 PM ET and are both evals active on MFFU? Type YES"; then GO_LIVE_EVAL's flow: `scripts/bots_back.ps1 -NoResume`, then START BOT (`python -m engine.go`), where you type the live phrase | Zlarior (50K) and ATLAS (25K) already run live and armed (the bot's Launch card, `/api/site/launch.json`) | type, read, pass on or store the phrase; arm anything by itself |

A bot that runs on paper (or not armed) when you type YES is stopped first, so START BOT can start it on the evals.

## Inside the zip, or in the bot folder
- **Double-clicked inside the zip** (Windows runs it from a temp folder, alone): the .bat takes `scripts/setup_everything.ps1` out of the newest zip in Downloads / on the Desktop, finds the bot folder by itself (the folder the bot really ran in: its code plus `logs` / `.git` / `data/start_bot.json`; the bot's scheduled tasks and Startup shortcut; `%USERPROFILE%\nq-liquidity-engine`, the Desktop, Documents) and updates that folder.
- **In the bot folder:** the update writes SETUP_EVERYTHING.bat there, so next time it is double-clicked there. It always runs from a copy in `%TEMP%`, so the update can rewrite the .bat safely. The rest always runs on the bot folder's own `scripts/setup_everything.ps1`: when it differs from the copy that started (the update or the auto-update connect just brought a newer one, or the folder has a newer one than the zip), it takes over (a server this window stopped is started first).
- **The zip unpacked somewhere** (Extract all): the same; an unpacked zip is never taken for the bot folder.

## Honest limits
- **Not run on a Windows PC yet.** Tested with PowerShell 7 on Linux, a Windows PowerShell 5.1 syntax lint and fakes for the Windows-only parts (Explorer's zip temp folder, Task Scheduler, the clipboard, NinjaTrader, Tailscale, the bot, GitHub's sign-in). This weekend's run is the first real one: if anything looks wrong, send a photo of the window.
- **Windows may warn the first time** ("Are you sure you want to run this software?", or SmartScreen's "More info > Run anyway"): the file came from the internet. Click Run.
- **Step 1b needs you on GitHub's sign-in window** the first time (sign in as dcondax1-wq, not another account). If it cannot reach the backup (cancelled, no internet, the repo not ready yet), the window says so and goes on; double-click SETUP_EVERYTHING.bat again later to try again.
- **Once auto-update is on, you need no more zips.** The window skips any zip it finds, and UPDATE_FROM_ZIP.bat refuses (a zip would make the code differ from the backup and stop every auto-update). For the newest code right away, double-click UPDATE.bat.
- **Step 2 needs you on the Tailscale pages** the first time (install, sign in with the same account as the iPhone, Enable HTTPS). The window waits for your Enter; it cannot click for you.
- **The phone link shows the dashboard only while the bot server runs.** If the server was not running before, it starts in step 3 (Sunday).
- **Step 3 needs NinjaTrader logged in** and, the first time, the two account names (START BOT asks once) and the Sim test (only while the market is open).
- **The clock check uses this PC's clock** (New York time computed from UTC). A wrong PC clock means a wrong answer; Windows sets it by itself.
- **A big zip takes a while:** the first check and the update each read the whole zip (about 0.9 GB unpacked): a minute or a few. The window says so; do not close it.
- **Not checked by the window:** the MFFU dashboard (you check both evals are active before YES) and the ntfy subscription on the iPhone (BOTS_BACK's six lines show the alert topic).
- **A second window at the same time** is not guarded against: run one at a time.

## For Claude (how it is built)
| Piece | File |
|---|---|
| The double-click (runs from a `%TEMP%` copy; the script next to it, else taken out of the newest zip; the missing / old zip lines) | `SETUP_EVERYTHING.bat` |
| The window: bot-folder search, the zip, the steps, the summary | `scripts/setup_everything.ps1` (test hooks `LE_SE_T_LOG`, `LE_SE_T_TASKS`, `LE_SE_T_NOW`) |
| "Is the zip already in?" (read only, no guards: 0 yes = this zip's SHA-256 in a finished, not undone update record, else every file the same; 10 update due, also when that record kept a `live_model*.json` that is an older repo version; 13 older: applied before a newer one, or dated before the last update; 3 bad zip; 2 not found) | `tools/update_from_zip.py --check` |
| `live_model*.json` 3-way: the repo's own versions (SHA-256, BOM and line ends aside) | `tools/model_versions.json`, built by `python tools/model_versions.py` (`--check`: stale); `tools/make_backup.py` refuses a stale ref |
| The update's last line now points to SETUP_EVERYTHING.bat / GO_LIVE_EVAL.bat (the undo's to GO_LIVE_EVAL.bat) | `tools/update_from_zip.py` `NEXT_WORDS` |
| Step 1b: on? (0 on, 10 due, anything else one SKIP) / turn it on (`--connect --port N`, attached to the window: 0 on, 20 not reachable, 21 not now, 22 no git, 1 put back) | `python -m engine.autoupdate --source-status` / `--connect` (`engine/autoupdate.py`, `update_source.json` "account") |
| Step 2 / step 3 | `scripts/live_link.ps1`, `scripts/bots_back.ps1 -NoResume`, `engine/go.py` (unchanged) |

### Wiring needed (the lead)
1. After the merge: push the release to the backup's branch `pc` first (`--connect` moves the folder to that commit), then `python tools/make_backup.py`, so the zip holds `SETUP_EVERYTHING.bat`, `scripts/setup_everything.ps1`, the new `tools/update_from_zip.py` and a current `tools/model_versions.json`.
2. `docs/CLAUDE_REFERENCE.md` Infrastructure / One chat: SETUP_EVERYTHING.bat (the owner's one double-click, now with step 1b), tests `tests.test_setup_everything` (area `pc`) and `tests.test_update_from_zip`; after any `live_model*.json` change run `python tools/model_versions.py` and commit the list with it.
3. Optional: step 1 of `docs/TONIGHT_EVAL.md`, `docs/BOTS_BACK.md` and `docs/LIVE_DASHBOARD.md` can point here (the NQ app's how-to sheet is generated by `tools/nq_howto_build.py`).

## Tests
`python -X utf8 -m tests.test_setup_everything`: static (the .bat, the .ps1, step 1b's calls and lines, this page, run_area, the update's last line), `--check`, and with pwsh: the 5.1 lint, the .bat's zip bootstrap line, and the flows (first run, second run, YES before Sunday 18:00 ET refused, Sunday YES, already armed, a paper bot stopped after YES, a server started before GitHub-free mode, the phrase typed at the gate, missing zip, bad zip, an open trade, a declined stop, the market open with the bot running (one question before any stop) and stopped, an older zip, the zip next to the .bat, no bot folder, the link failing, the newer copy going on) and step 1b (first run: one stop for the update and the connect, `--connect --port N` with the server down in the bot folder, the server started once after; already on; exits 20 / 21 / 22 / 1 / other each one SKIP line and the window goes on; an odd probe answer; the bot running: its own Y, n keeps it running; an open trade; the market open with the bot stopped or running; a connect that brings another copy of the script; the connect reads the window's keyboard). Fakes for the bot server, tailscale, the child scripts, START BOT and `engine.autoupdate`; the real `tools/update_from_zip.py`. Never run `tests.test_win_scripts` in the sandbox.
