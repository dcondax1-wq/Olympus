# night-tasks red team (2026-11-23): b95087a77 -> night-tasks-rt (no code change needed)

| # | Check | Result |
|---|---|---|
| 1 | task_audit --fix deletes only tasks with one of OUR exact names (OUR_TASKS) that run tools\pc_report.py, never OlympusPCReport itself; a task with any other name is never touched (one line + the exact command for the owner). Of our scripts only pc_report_task.ps1 (= OlympusPCReport) registers a task that runs pc_report.py (grep of scripts/*.ps1, pc_always_on, the kalshi kit), so --fix can only catch stale leftovers, never the keeper / ops / clock / autostart / wake tasks (they run other programs) | OK |
| 2 | Re-install of OlympusPCReport only when it points at another folder (normal user, scripts\pc_report_task.ps1). Two bot folders each running a server would flip the task between them at each start | LOW (one folder is the plan) |
| 3 | The 5-min gap (runs.jsonl, newest start): only full runs record and only full runs are skipped; --bars / --test / --setup / --card return before it; night-truth's --pulse branch sits before it and never records (merge checked) -> a pulse is never swallowed. Worst post gap with the keeper (it runs only when last.json is 20+ min old): keeper at :14, task :15 skipped, next :30 = 16 min < the cloud's 20-min PC-silent line. --force runs anyway | OK |
| 4 | Merge with night-truth-rt: tools/pc_report.py argparse lines (--pulse / --why vs --by / --force): keep BOTH; tests/test_ops.py + test_launch_checklist.py: the same fix on both sides (take either) | by hand |
Tests: task_audit 16/16, report_keeper 19/19, pc_report_sign 21/21, live_publish 86/86, trading_home 46/46.
