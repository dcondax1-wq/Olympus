# Setup everything: one double-click (2026-11-14)

## Your step
1. Download the code zip (`OLYMPUS_BACKUP_...zip`) and its `.sha256.txt` into Downloads, open the zip, double-click `SETUP_EVERYTHING.bat` and answer what the window asks (on Sunday after 6 PM ET you type YES, then the live phrase yourself).

| What | Result |
|---|---|
| One window | the three PC jobs in order: 1 new code, 2 phone link, 3 go live on the evals; big headers, a three-line summary at the end |
| Safe to double-click again | each step is checked first and skipped when it is done (the zip is already in, the link is already on, both evals are already armed) |
| Going live | only after you type YES, and not before Sunday 18:00 ET (the window refuses an earlier YES and waits); you type the live phrase yourself |
| A failure | one line: what happened, the exact fix, "send a photo of this window" |
| Trading | unchanged: strategy, sizing and `live_model*.json` are not touched; nothing is armed without your phrase |

## What the window does
| Step | It does | Skipped when | It never does |
|---|---|---|---|
| 1 New code | finds the newest `OLYMPUS_BACKUP_*.zip` in Downloads / on the Desktop / next to the .bat (or the zip dragged onto the .bat) and its `.sha256.txt`; takes the updater out of that zip and runs `tools/update_from_zip.py --check`, then the update (same rules as UPDATE_FROM_ZIP.bat: checksum, local-only files and your `live_model*.json` kept, a backup, UNDO_UPDATE.bat undoes it) | this very zip was already applied (the update's own record: a fix made on the PC afterwards is never undone by running it again), or the folder already matches it, or the zip is older than the code already there | stop a bot with an open trade; stop the bot without your Y; start a bot server that was not running |
| ... the bot | a running bot server is stopped first only after you type Y (the STOP_BOT.bat stop: it also clears the auto-start record) and started again right after the update, hidden, with the bot itself stopped; while the market is open the same single question says so, before anything is stopped | no update needed | resume or arm the bot |
| 2 Phone link | `scripts/live_link.ps1` (LIVE_LINK.bat): Tailscale installed, signed in, HTTPS, `tailscale serve` to the bot server; its messages in this window's words; Enter tries again, LATER leaves it for another time; the link shown big and put on the clipboard | `tailscale serve` already points at the bot server (no Funnel) and the site task is there | turn on Funnel (the internet) |
| 3 Go live | the pause screen: "Is it Sunday after 6 PM ET and are both evals active on MFFU? Type YES"; then GO_LIVE_EVAL's flow: `scripts/bots_back.ps1 -NoResume`, then START BOT (`python -m engine.go`), where you type the live phrase | Zlarior (50K) and ATLAS (25K) already run live and armed (the bot's Launch card, `/api/site/launch.json`) | type, read, pass on or store the phrase; arm anything by itself |

A bot that runs on paper (or not armed) when you type YES is stopped first, so START BOT can start it on the evals.

## Inside the zip, or in the bot folder
- **Double-clicked inside the zip** (Windows runs it from a temp folder, alone): the .bat takes `scripts/setup_everything.ps1` out of the newest zip in Downloads / on the Desktop, finds the bot folder by itself (the folder the bot really ran in: its code plus `logs` / `.git` / `data/start_bot.json`; the bot's scheduled tasks and Startup shortcut; `%USERPROFILE%\nq-liquidity-engine`, the Desktop, Documents) and updates that folder.
- **In the bot folder:** the update writes SETUP_EVERYTHING.bat there, so next time it is double-clicked there. It always runs from a copy in `%TEMP%`, so the update can rewrite the .bat safely. Steps 2 and 3 always run on the bot folder's own `scripts/setup_everything.ps1`: when it differs from the copy that started (the update just brought a newer one, or the folder has a newer one than the zip), it takes over from step 2.
- **The zip unpacked somewhere** (Extract all): the same; an unpacked zip is never taken for the bot folder.

## Honest limits
- **Not run on a Windows PC yet.** Tested with PowerShell 7 on Linux, a Windows PowerShell 5.1 syntax lint and fakes for the Windows-only parts (Explorer's zip temp folder, Task Scheduler, the clipboard, NinjaTrader, Tailscale, the bot). This weekend's run is the first real one: if anything looks wrong, send a photo of the window.
- **Windows may warn the first time** ("Are you sure you want to run this software?", or SmartScreen's "More info > Run anyway"): the file came from the internet. Click Run.
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
| The window: bot-folder search, the zip, the three steps, the summary | `scripts/setup_everything.ps1` (test hooks `LE_SE_T_LOG`, `LE_SE_T_TASKS`, `LE_SE_T_NOW`) |
| "Is the zip already in?" (read only, no guards: 0 yes = this zip's SHA-256 in a finished, not undone update record, else every file the same; 10 update due; 13 older: applied before a newer one, or dated before the last update; 3 bad zip; 2 not found) | `tools/update_from_zip.py --check` |
| The update's last line now points to SETUP_EVERYTHING.bat / GO_LIVE_EVAL.bat (the undo's to GO_LIVE_EVAL.bat) | `tools/update_from_zip.py` `NEXT_WORDS` |
| Step 2 / step 3 | `scripts/live_link.ps1`, `scripts/bots_back.ps1 -NoResume`, `engine/go.py` (unchanged) |

### Wiring needed (the lead)
1. After the merge: `python tools/make_backup.py`, so the zip holds `SETUP_EVERYTHING.bat`, `scripts/setup_everything.ps1` and the new `tools/update_from_zip.py`.
2. `docs/CLAUDE_REFERENCE.md` Infrastructure / One chat: SETUP_EVERYTHING.bat (the owner's one double-click), test `tests.test_setup_everything` (area `pc`).
3. Optional: step 1 of `docs/TONIGHT_EVAL.md`, `docs/BOTS_BACK.md` and `docs/LIVE_DASHBOARD.md` can point here (the NQ app's how-to sheet is generated by `tools/nq_howto_build.py`).

## Tests
`python -X utf8 -m tests.test_setup_everything`: static (the .bat, the .ps1, this page, run_area, the update's last line), `--check`, and with pwsh: the 5.1 lint, the .bat's zip bootstrap line, and the flows (first run, second run, YES before Sunday 18:00 ET refused, Sunday YES, already armed, a paper bot stopped after YES, a server started before GitHub-free mode, the phrase typed at the gate, missing zip, bad zip, an open trade, a declined stop, the market open with the bot running (one question before any stop) and stopped, an older zip, the zip next to the .bat, no bot folder, the link failing, the newer copy going on). Fakes for the bot server, tailscale, the child scripts and START BOT; the real `tools/update_from_zip.py`. Never run `tests.test_win_scripts` in the sandbox.
