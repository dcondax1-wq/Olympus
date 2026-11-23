# Windows Scheduled Tasks and Startup entries the repo creates (night-tasks, 2026-11-23)

## What the public status topic showed (ntfy, last 3 h, read 2026-11-23 03:38 UTC)
Every 15 minutes TWO full `tools/pc_report.py` runs (both `src: pc_report`, same heartbeat, same PC):
- run A at PC-clock :12:57 / :27:57 / :42:57 / :57:57 (`reporter.t mod 900 = 777`)
- run B at :14:59 / :29:59 / ... (`mod 900 = 899`) = the task **OlympusPCReport** (daily 00:00 + every 15 min)
The gap is a constant 122 s, also after the PC clock was corrected (~01:58 UTC: post minus reporter time fell from ~28 s
to ~3 s). So it is a second 15-minute **scheduler**, not the keeper (the keeper only runs when the report is > 20 min old,
so it would drift). **No script in this repo (or its git history) schedules pc_report at any start time but 00:00**, so
run A is a task the repo does not know: hand-made, from the old `nq-liquidity-engine` folder, or one of our names
re-pointed. Which one: the PC answers that now (below).

## Tasks the repo creates (exact names: `tools/task_audit.py` OUR_TASKS)
| Task name | Made by | Trigger | Runs |
|---|---|---|---|
| OlympusPCReport | scripts/pc_report_task.ps1 (BOTS_BACK.bat; re-installed by engine/report_keeper.py) | daily 00:00, every 15 min + sign-in | pythonw tools\pc_report.py --quiet --by task |
| OlympusLiveSite | scripts/live_link.ps1 | daily 00:00, every 15 min + sign-in | pythonw tools\pc_publish.py --provider none (no ntfy) |
| OlympusPublishNQ | scripts/publish_nq.ps1 | daily 00:00, every 15 min + sign-in | pythonw tools\pc_publish.py |
| LiquidityEngineOps | scripts/install_ops_task.ps1 (one_time_setup) | daily 00:00, every 5 min + sign-in | pythonw scripts\ops_tick.py |
| LiquidityEngine | scripts/install_autostart.ps1 | sign-in / unlock | the bot server |
| LiquidityEngine-Keeper / -WeeklyCare | scripts/pc_tune.ps1 | daily + sign-in / weekly | the keeper / PC care |
| LiquidityEngine-IndexPause / -IndexResume | scripts/pc_care.ps1 | daily | search index pause / resume |
| LiquidityEngineWake / LiquidityEngineSleep | scripts/schedule_pc.ps1 | Mon-Fri 01:30 / 16:35 ET | wake / hibernate |
| OlympusWakeDaily | tools/pc_always_on.py | daily | wake |
| OlympusClock | scripts/fix_clock.ps1 (FIX_CLOCK.bat) | every 15 min + boot (SYSTEM) | w32tm /resync |
| OlympusWeeklyBackup | scripts/backup_task.ps1 | weekly | backup |
| OlympusAgencyMail | scripts/agency_mail_task.ps1 | schedule in script | agency mail |
| OlympusMoneyInbox | MONEY_INBOX.bat | sign-in | money inbox |
| LE Money Engine | RUN_MONEY.bat (comment: made by hand) | every 30 min | money engine |
| Kalshi to Jarvis | tools/kalshi_kit/install_windows.ps1 | in script | Kalshi link |

Startup folder: `LE bot server.lnk` (engine/go.py startup_shortcuts, setup_everything), `NinjaTrader 8 (Liquidity Engine).lnk`
(one_time_setup / setup_dedicated_pc). In-process: the bot server's report keeper (engine/report_keeper.py, every 5 min, runs
pc_report only when its last run is > 20 min old).

## The fix (night-tasks)
1. **pc_report: one full run per 5 min, whoever starts it** (`MIN_GAP_S = 300`, `--force` overrides). The old run lock only
   stopped OVERLAPPING runs; the pair is 122 s apart, so a 60 s window would not have caught it. Every try goes to
   `data/pc_report/runs.jsonl` with `--by` (task / keeper / `?`) and the parent pid: the extra scheduler shows as `by "?"`.
2. **tools/task_audit.py --fix** (idempotent, `logs/task_cleanup.log`): an OUR-named task other than OlympusPCReport that
   runs pc_report -> removed by its exact name; OlympusPCReport pointing at another folder -> re-installed from this one;
   a task with a name we never use -> left alone, its exact `schtasks /Delete` line in the log and `data/pc_report/tasks.json`.
   Runs once per bot-server start (the server restarts after each update) and from TRADE_HOME (5 Phone alerts -> 3).
3. TRADE_HOME status shows "Reports: 2 Windows tasks send the 15-minute report" when the audit found more than one.

## Owner (hands-only, only if the log names a foreign task)
`python -X utf8 -m tools.task_audit` on the PC lists the tasks; logs\task_cleanup.log has the one delete line to paste.
