# PC DOCTOR: why the phone hears nothing from the PC

Double-click **tools/bat/PC_DOCTOR.bat** in the bot folder. It only looks (nothing is started, stopped, armed or sent).
It prints one line per link, then **MOST LIKELY CAUSE** and **NEXT STEP (copy this line)**.
The same card on the PC's own bot page: `http://127.0.0.1:8766/api/pc/doctor?text=1` (JSON without `?text=1`).

| Line | What it checks | The usual fix |
|---|---|---|
| SERVER | the bot server answers, the bot runs | START_BOT.bat |
| BEAT | the bot's own 5-minute heartbeat file is fresh | STOP_BOT then START_BOT (when flat) |
| GITHUB | GitHub-free mode (the old GitHub account is suspended since 2026-11-08: its heartbeat branch can never update) | `python -X utf8 tools/pc_doctor.py --github-free` |
| TASK | the 15-minute report task OlympusPCReport is installed and its last run worked | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pc_report_task.ps1` |
| REPORT | the report ran in the last 20 minutes and ntfy took it | `python -X utf8 tools/pc_report.py` |
| TOPIC | your private alert topic exists and had its test push | `python -X utf8 tools/pc_report.py --setup` then `--test` |
| NTFY | ntfy.sh answers; the site's status channel got a report in 3 hours | open https://ntfy.sh on the PC |
| UPDATE | auto-update from the backup repo is connected | `python -X utf8 -m engine.autoupdate --connect` (bot server stopped) |
| HEAL | (2026-11-20) the self-heal's last run: what it fixed by itself, what it could not (docs/SELF_HEAL.md); shown once it ran | `python -X utf8 tools/pc_doctor.py --heal --apply` |

Most likely cause today (from the code, 2026-11-17): the report task OlympusPCReport is not installed (SETUP_EVERYTHING
skips the step that installs it when both evals are already armed), and the PC never connected to the backup repo
(BOTS_BACK set `credential.interactive=never` in the bot folder, which kept the GitHub sign-in window from opening), so the
2026-11-16 report keeper that would re-install the task never reached the PC. The GitHub heartbeat branch is silent since
2026-11-07 on purpose: that account was suspended.
