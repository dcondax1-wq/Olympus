# Update gate: a bad update can't take the bot down (TOP25 idea #4, 2026-11-20)

Branch `day-security2`, with olympus/pc e3bf212d merged in. Not landed: the lead reviews it and a red team checks it over the
weekend.

## For the owner

| What | Before | Now |
|---|---|---|
| A phone-site / docs push | Restarted the trading bot, as late as 01:01 ET, just before London | The PC takes the new files; **the bot keeps running** |
| A new bot that cannot start | Restarted into a broken server (the supervisor kept retrying it) | Checked before the restart; if it fails, the PC stays on the old code and your phone says "Update held back" |
| A new bot that keeps crashing | Kept crashing until someone fixed it by hand | 3 stops within 10 min of the update = back to the version that ran fine, plus ONE push |

Nothing for you to do.

## What changed (engine/autoupdate.py)
1. `changed_paths(sh, old, new)` and `needs_restart(paths)`. The bot restarts unless **every** changed path is on `SITE_ONLY`:
   `tools/web_public/`, `docs/`, `research/`, `tests/`, `handoff/`, `vault/`, `.github/`, and root `*.md`. It is a list of safe
   paths, not a list of bot paths: engine/, server.py, the models, scripts/, tools/*.py, web/, requirements.txt, *.bat and any
   new path all restart. An empty list (nothing known) restarts too. `BOT_PATHS` is kept only to word the reason.
   `run_update` still pulls and self-tests a site-only update. It returns `restart=False, site_only=True`; `record()` then sets no
   restart marker and no crash guard, and `DailyUpdater.check_once` does not exit.
2. `import_check(sh)` runs before every restart: `import server` (with the route count) in `engine/pc_selftest`'s sealed child
   (temp folders, no NinjaTrader folder, no live account or push keys, LE_NO_AUTOSTART, no heartbeat), 120 s. A failure rolls
   back like a failed self-test (`bad_sha`, held "Bot server starts (imports)"). Measured here: the real server imports, 79 routes.
   This closes the case the crash net cannot see: a server that dies on import never reaches any Python hook.
3. `crash_check()` is the crash-loop net. `record()` arms `crash_guard {new, old, t, starts}` for every update that restarts.
   - `DailyUpdater.start()`, run by the server at every start, counts each start.
   - Start 4 within `CRASH_WINDOW_S` = 600 s (the restart + `CRASH_RUNS` = 3 short runs) does `git reset --keep old`,
     `bad_sha = new`, a history row (mode crash), one push "Update rolled back", pip again if requirements changed, then exit 75.
     The supervisor restarts at once, on the old code.
   - A run past 10 min clears the guard.
   - If HEAD is no longer the updated commit (moved by hand), the guard is cleared and git is never touched.
   - `python -m engine.autoupdate --crash-check` is the same check, for run_bot.ps1 to call before each start (optional, below).
     With `LE_CRASH_CHECK=supervisor` the server then only looks, so no start is counted twice.

## Tests
- `tests.test_autoupdate_paths`: **23/23**, on a real temp repo (bare origin + the PC's clone):
  - the path rules, including `./`, Windows slashes and look-alike folders
  - site-only, bot, and both together
  - a server.py that can't import is rolled back; the fixed one passes
  - the crash net: count, look only, roll back, one push, the bad commit skipped next time, cleared past 10 min, hands off when
    HEAD was moved
  - DailyUpdater.start exits 75 after a rollback, and LE_CRASH_CHECK=supervisor only looks
- `tests.test_autoupdate_source` 56/56, unchanged.
- pc area: see the end of this file.

## For the lead
- **Optional wiring (scripts/run_bot.ps1, the lead's file).** Run the check before every start, not only from inside the server.
  This catches a server that crashes before `AUTOUPDATE.start()`; the import check already covers the import-time case. In the
  loop, right before `& $Python -u server.py`:
  `& $Python -X utf8 -m engine.autoupdate --crash-check 2>&1 | ForEach-Object { Write-Log ("{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), "$_") }`
  and `$env:LE_CRASH_CHECK = 'supervisor'` near the top. Without these lines the server-side count still works.
- **Known limit.** Two manual restarts within 10 min of an update count as short runs, so an otherwise good update can be rolled
  back. The PC then stays on the previous version (the one that ran fine) until a newer pc commit lands.
- **Red-team notes.**
  - `tests/` is site-only, but `engine/fill_audit.py` and `engine/lit_learn.py` import a test module lazily inside their CLI
    self-test commands. The trading loop never does.
  - A site-only update means the running server and the files on disk differ until the next real restart. That is fine for
    files the server only serves (`engine/live_site` reads tools/web_public from disk on each request).
- docs/AUTO_UPDATE.md is updated: the owner table plus a section for the lead. I also corrected its "private copy" line: GitHub
  shows the repo as public (security REPORT, owner step 1).

## Test run (pc area, every suite but win_scripts)
