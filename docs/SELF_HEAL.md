# SELF-HEAL: what the PC fixes by itself, and what it tells you about

Owner, 2026-11-20: "Fix, and have something that will auto fix." and "Save room for my PC, we need everything to run perfect."

**You do nothing.** Once an hour the 15-minute PC report task (OlympusPCReport) runs the self-heal (`engine/self_heal.py`).
It fixes the faults below by itself, writes one log line per fix, and tells you only when it could NOT fix something:
ONE Board event and ONE phone alert ("PC self-heal: needs you"), at most once a day per fault.
It never starts, stops, arms or routes the bot, never writes an order, never runs inside the live loop or the bot server.

## Fixed by itself

| Fault | What it does |
|---|---|
| A stale git lock (`.git/index.lock` ...) left by a killed git: every later update fails | Deletes it when it is 10+ minutes old and no git is running |
| A file in the update's way (git: "untracked files would be overwritten") | Same bytes as the update's: removed. Different: moved to `logs/self_heal/keep-<time>/` (your copy kept) |
| A bot-made file (cache, VIX / GEX data, check reports) the last update tripped on | Copied to `keep-<time>/`, then put back to the committed version (the bot rewrites it anyway) |
| (both rows above) | First a snapshot commit of the file at `refs/olympus/self-heal` (as the auto-update's connect does). Get one back: `git checkout refs/olympus/self-heal -- <file>` |
| A bot order file NinjaTrader never processed (it was closed) | Withdrawn after 2 minutes (copy in `logs/self_heal/oif/`), so it can never fill late. The adapter's own rule, also when no bot runs |
| `logs/supervisor.pid` naming a process that is gone or another program (after a crash / restart) | Deleted (STOP_BOT would otherwise wait for, then stop, that program) |
| A Python package from requirements.txt missing | Installed, only after 16:00 ET on weekdays (or the weekend) and with no trade open |
| The PC clock 2+ seconds off internet time | `w32tm /resync` (Windows' own clock sync) |
| Disk: the weekly clean (and at once when under 10 GB free) | Removes only old files that rebuild or are rotation output (below) |

The weekly clean (outside 01:50-16:00 ET on weekdays): dated logs and old `.gz` logs after 30 days (the order audit after 365),
old code zips `OLYMPUS_BACKUP_*.zip` after 14 days (the newest 2 stay), `backups\le-*.zip` after 14 days (the newest 3 stay),
`reports\tmp` after 7 days, the replay cache `research\runs\_cache` after 14 days, Python caches of deleted files or another
Python version, NinjaTrader's own `log` / `trace` text files after 14 days, test leftovers in TEMP after 2 days.
**Never touched:** `data\` (trades, journal, state, bars), `live_model*.json`, `second_model.json`, notes, `.env*`, your copies
(`logs\connect-*`, `logs\self_heal\keep-*`), NinjaTrader's database / workspaces / templates, any file git tracks except the
bot-made ones listed in `engine/generated_files.py`. CLEAN_STORAGE.bat stays the big manual clean (Windows junk too).

## Tells you (it could not fix)

| You get | Do this |
|---|---|
| "update blocked by a local change in X" (a hand edit of a tracked file, or a `data\` file the update also brings) | Send Claude that line: keep or drop it |
| "the bot server does not answer while it should run" (Board only: the 15-minute report already pushes "bot down") | Double-click BOTS_BACK.bat (a real account is never armed by it) |
| "only X GB free after the clean" | Double-click CLEAN_STORAGE.bat (dry run first) |
| "pip could not install ..." | `python -m pip install -r requirements.txt` |
| "Windows did not sync the clock" | Windows Settings > Time & language > Date & time > Sync now |
| "a stale git lock / order file could not be deleted" | Restart the PC once |

## Check it

- PC DOCTOR shows a **HEAL** line (what it fixed this week, what needs you).
- The PC report carries one ext line `sh` (public: no folder, no name): "Self-heal: all fine · fixed 2 this week · 45 GB free ·
  bot folder 3.1 GB (data 1.20, runs 0.25, logs 0.10) · last clean freed 0.40 GB". The pages merge it (pc_feed.js); a card that
  shows `sh.line` is the lead's wiring.
- By hand: `python -X utf8 tools/pc_doctor.py --heal` (dry run, changes nothing), `... --heal --apply` (fix now),
  `python -X utf8 -m engine.self_heal --clean` (the weekly clean's dry run), `--sizes` (what grows), `--status`.
- Off: set `LE_SELF_HEAL=0`. Files (gitignored): `logs/self_heal/` (state.json, tiny.json, heal-YYYYMM.log, keep-*, oif/).
- Tests: `python -X utf8 -m tests.test_self_heal_pc` (temp folders and temp git repos; area `pc`).

## Git weight every PC clone carries (proposal, nothing moved yet; history is never rewritten)

Tracked files are 789 MB, the git pack 667 MB. Not read by any code on the PC:

| What | Size | Proposal |
|---|---:|---|
| `docs/shots/` (238 test screenshots) | 54 MB | move to an archive branch, restore line in docs/ARCHIVE.md (as night-clean did) |
| `research/handoff/2026-11-18`, `2026-11-19` (72 pictures + an mp4) | 27 MB | same; .gitignore the hand-off media |
| `research/lab/chart_examples/` + `research/study/*.png` | 18 MB | same |
| `research/design/` (icon sources and previews) | 9 MB | same |
| duplicates (datacity/city.json x2, fx.js x2, tree.json x2, icons x2) | 7 MB | keep one copy, the build copies it |
| `research/runs/` (2,345 backtest runs) | 246 MB | keep the few the live bot reads (lit_live, lit_2wk_rec, the live variants); the run library to its own branch the dashboard fetches on demand |

The lead decides; a PC clone with `--filter=blob:none` would also skip old versions of all of these.
