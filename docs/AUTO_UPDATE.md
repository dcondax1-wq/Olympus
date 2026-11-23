# The PC updates itself (owner 2026-11-14)

Owner: "figure out a way, whether it's going back to GitHub and keeping it just in case we get banned ... I'm not
updating the files every time we make changes, so do it now."

| What | How it works |
|---|---|
| Backup | A copy of everything on your second GitHub account: repo `dcondax1-wq/olympus` (meant to be private; on 2026-11-20 GitHub showed it **public**: research/handoff/2026-11-20/security/REPORT.md, step 1). The code the PC runs is on its branch `pc`. |
| New code reaches the PC | By itself. The PC checks the backup once a day in the 17:02 ET pause and once an hour outside trading time. |
| When it never updates | During trading hours (01:50-16:00 ET on weekdays), with a trade open, or with a LIT entry waiting. |
| Your evals | An eval bot without auto-resume only updates at the weekend (the **Friday or Saturday** 17:02 ET pause), so an update never stops it in the middle of the week. If it does update, your phone says so; start it again before Sunday 6 PM ET. Starting the bot yourself (START BOT) always takes the newest code first. |
| Safety | After each update it runs its quick self-tests. If one fails, it goes back to the code it had and your phone tells you. |
| Site-only updates (2026-11-20) | When an update changes only the phone site, docs, research or tests, the PC takes the new files but **the bot keeps running**: no restart before London. Anything else (bot code, models, scripts, a file nobody listed) restarts as before. |
| A new bot that cannot start | Before any restart, the PC checks that the new bot server starts (a sealed test run). If it can't, the PC stays on the code it had and your phone says "Update held back: Bot server starts". |
| A new bot that keeps crashing | If the bot stops 3 times within 10 minutes of an update, the PC goes back to the version that ran fine, skips the bad one, and sends you ONE push ("Update rolled back"). |
| If GitHub ever bans that account too | Nothing breaks: the bot keeps running the code it has, and the code zips (`SETUP_EVERYTHING.bat`) still work. |

## Your part (once)
1. On GitHub as **dcondax1-wq**: create the private repo `olympus`, and give the Claude app access to it
   (`https://github.com/apps/claude/installations/select_target` -> dcondax1-wq -> Only select repositories -> olympus).
2. On the PC, double-click `SETUP_EVERYTHING.bat` (Sunday after 6 PM ET). Its auto-update step opens a GitHub window the
   first time: **sign in as dcondax1-wq**. After that, no more zips.

## For the lead (every change that should reach the PC)
- **Since 2026-11-20 Olympus `pc` is the main home** (owner): commit and push only there (`python tools/ship.py`, or
  `git push origin HEAD:pc` from a clone of dcondax1-wq/Olympus). The old demetrades2000-coder/nq-liquidity-engine repo is
  retired: never push to it.
- Test it, then push the release by URL, never by a remote name you have not checked: `git push https://github.com/dcondax1-wq/Olympus
  <release>:pc` (attach the repo first: add_repo `dcondax1-wq/olympus` with push access). In an old clone `origin` (or `olympus`) can
  still point at the retired repo: `git remote -v` first (audit E4, 2026-11-22). The PC installs it within the hour when it is flat. The backup's default
  branch `main` only holds a README, so none of the repo's scheduled GitHub Actions run there (private repos have few
  free minutes).
- `update_source.json` (repo root) names the backup: remote `olympus`, URL with the account name in it (so Git
  Credential Manager asks for that account, not another one saved on the PC), branch `pc`. No secret in it.
- The one-time move: `python -m engine.autoupdate --connect` (bot server stopped). However the folder got its code (zips,
  an old clone, a copied folder), it becomes exactly the backup's newest commit: every file the move can touch goes into
  a snapshot commit first (`refs/olympus/before-connect`), a file that is no version the repo ever had is also copied to
  `logs/connect-<stamp>/`, then pip + the quick self-tests run, and any failure puts everything back as it was. Files git
  never tracked are never deleted. Exit codes: 0 on, 20 backup not reachable, 21 not now (server running / trade open),
  22 no git, 1 failed and put back. `--source-status` (read only): 0 connected, 10 not yet.
- After the connect, every update is the normal strict one (`fast_forward`: fast-forwards of `olympus/pc` only, a hand
  edit blocks it with an alert, rollback on a failed self-test). GitHub-free mode (`engine/nogithub.py`) only blocks
  origin (the lost account). Tests: `tests.test_autoupdate_source` (real git, 51 checks), `tests.test_autorun`.

## The update gate (2026-11-20, `engine/autoupdate.py`; tests `tests.test_autoupdate_paths`)
- `needs_restart(changed)`: restart unless EVERY changed path is on `SITE_ONLY` (`tools/web_public/`, `docs/`, `research/`, `tests/`,
  `handoff/`, `vault/`, `.github/`, root `*.md`). Unknown or empty = restart. A site-only update still runs the self-tests, sets no
  restart marker and no crash guard, and the DailyUpdater does not exit. The paths come from `git diff --no-renames`, so a bot file
  moved into `research/` still lists its old `engine/` path (restart). `RESTART_DATA` (research/lit/mffu_rules.json,
  research/props/firm_rules.json: the running bot caches them) restarts too.
- `import_check(sh)`: before a restart, `import server` runs in engine/pc_selftest's sealed child. A failure rolls the update back,
  like a failed self-test (`bad_sha`, held = "Bot server starts (imports)").
- `crash_check()`: an update that restarted the bot arms `crash_guard` in data/autoupdate.json ({new, old, t, starts}).
  server.py calls `DailyUpdater.crash_start()` FIRST in its startup (before the bot resumes or any watcher starts), so every start
  is counted, and on a rollback nothing resumes on the bad code. With `LE_CRASH_CHECK=supervisor`, run_bot.ps1 counts instead
  through `python -m engine.autoupdate --crash-check` (not wired yet). The 10-minute window (`CRASH_WINDOW_S`) starts at the
  FIRST start after the update, not when the check began (pip + tests can take minutes). `CRASH_RUNS` + 1 starts in it =
  `git reset --keep <old>` (bot-made tracked files the bad code rewrote go back to HEAD first, else git refuses), bad_sha = crash_sha
  = new, one push (sent synchronously: the process exits right after), and the server restarts (75) on the old code. A run past
  the window clears the guard. It never touches git when HEAD is no longer the updated commit.
- Owner restarts are not crashes (2026-11-21): Bot Control's Restart, the phone's `restart` and a new supervisor (`--on-start`:
  START BOT, a reboot) call `mark_deliberate_restart`, so the next start (within `DELIBERATE_S`, 5 min) is not counted. The net
  stays armed for the starts after it. An `update` restart is not marked (its own restart is the first counted start).
- After a crash rollback the bad code stays out: START BOT / UPDATE.bat (`pull`) skip bad_sha ("Kept the version that works"), and
  a newer `pc` that only adds site / docs commits on top of crash_sha is not taken either (it would bring the same crash back
  every hour). The first newer `pc` that changes bot code after it is tried again, with the net armed; that clears crash_sha.

