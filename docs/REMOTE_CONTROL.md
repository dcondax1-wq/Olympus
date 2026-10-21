# Remote control from the phone (free, through GitHub)

Send one safe command to the PC bot from anywhere: kill, stop, flatten, status, update, restart, or a start on Sim.
No paid service, no token on the phone: you write one small file on GitHub with your own login, the PC reads it.

## How to use it (3 steps)

1. Phone app (Home Screen app) -> **System -> Remote**. Tap the command (Status, Flatten, Stop, KILL, ...). The page
   builds the exact text with a fresh id and time.
2. Tap **Copy and open GitHub**. GitHub's editor opens on `control/command.json`, branch `control`
   (`https://github.com/<owner>/<repo>/edit/control/control/command.json`; in the GitHub app: branch `control`, the
   file `control/command.json`, the pencil).
3. Select all, paste, **Commit changes**. Within about a minute the phone gets a notice with the result
   ("Remote kill: done", or why it was refused). The cloud README row "Remote control" and the heartbeat show
   "remote: last cmd X done at HH:MM ET".

A command expires **15 minutes** after you made it. If the PC was off, the old command is ignored (you get a notice
saying so) and nothing happens later by surprise.

## The commands

| cmd | what the PC does | when |
|---|---|---|
| `kill` | same as HOLD TO KILL: flatten everything (NinjaTrader FLATTENEVERYTHING), stop the bot, auto-resume OFF, autostart cleared. Restart only at the PC. | any time |
| `stop` | stop the bot once it is flat (an open trade or an armed LIT setup finishes first). `"now": true` closes the position first, then stops. | any time |
| `flatten` | close the open position now. The bot keeps running and trades again from the next trading day (no new entry today). | any time |
| `status` | push a fresh heartbeat and send a phone notice: running / stopped, account, position, LIT stage, feed age, version. | any time |
| `update` | the auto-update now (`engine/autoupdate.py`: main only, fast-forward only, self-tests, roll back on failure), then a restart when it updated. Does not need the daily auto-update to be switched on. | flat, nothing pending, outside 01:50-16:00 ET on a weekday, server run by `run_bot.ps1` |
| `restart` | restart the server (exit 75; `run_bot.ps1` starts it again). The eval comes back only with auto-resume on; a Sim bot resumes by itself. | flat, nothing pending, server run by `run_bot.ps1`; while the bot runs also outside 01:50-16:00 ET on a weekday |
| `start` | start on a **Sim** account (`"account": "Sim101"`) or paper. A real account is always refused. | bot stopped |
| `pause` | no NEW entries until `"until"`: `"HH:MM"` (New York), `"tomorrow"` (00:00 ET tonight) or `"YYYY-MM-DD"` (max 14 days). Open trades keep stop / target. | always |
| `resume_entries` | lift the pause (not a remote flatten's "done for today"; does not start a stopped bot) | always |
| `present` | "I'm here" check-in for 4 h (`"hours"` optional) in the presence log (`engine/presence.py`) | always |

Example: `{"id": "kill-1760983320-ab12", "ts": 1760983320, "cmd": "kill"}`. Several at once:
`{"commands": [{...}, {...}]}`. `ts` is unix seconds (or ms, or an ISO time like `2026-10-20T14:02:00-04:00`).

## Rules the PC enforces

- Each command needs a new `id` (1-64 letters, digits, `. _ : -`) and a `ts` from the last 15 minutes (up to 5 minutes
  in the future for a phone clock that runs fast). An id runs once: done ids are kept in `data/remote_done.json`
  (gitignored), written **before** the command runs, so a crash or the restart itself never runs it twice.
- There is no command that changes the config, the strategy, the size or a switch; anything else is refused with a
  notice.
- **No remote start on a real account** (MFFU: live trading only with you present). The start body is built on the PC
  from scratch: `adapter`, `confirm`, `nt_account`, `present` or any other field in the command are never used.
- The PC fetches the branch into a private ref (`refs/le/control`): your working tree, index and branch are never touched.

## Security

Anyone with **write access to the repo** can write this file, so treat repo write access like access to the bot:

- `kill`, `stop`, `flatten` only reduce risk; `status` only reads. The worst a stranger could do with them is stop the
  bot or close a trade early.
- `update` and `restart` are the only ones that change what runs. They are gated: flat, nothing pending, outside
  trading hours (update always, restart while the bot runs), the server supervised by `run_bot.ps1`. `update` only
  fast-forwards to `origin/main` (which a writer could change anyway), runs the self-tests and rolls back on failure.
- Nothing remote can open a trade on a real account or arm live trading.
- Keep the repo private and do not add collaborators you would not hand the PC to. Turn it off with `LE_REMOTE=0`.

## Setup (once)

- The `control` branch is made by `python tools/init_control_branch.py` (the cloud monitor workflow runs it on every
  run; a no-op once the branch exists, it never overwrites it). On the PC you can run it too. It holds a blank command
  (`"cmd": "none"`) that the PC ignores.
- `scripts/run_bot.ps1` sets `LE_REMOTE=1` (like `LE_HEARTBEAT=1`). The PC needs git with push/fetch rights in the
  project folder (it already has them for the heartbeat). Set `$env:LE_REMOTE = '0'` in `.env.local.ps1` to turn it off.
- Code: `engine/remote_ctl.py` (thread in `server.py`, every ~60 s), `LiveBot.flatten_now` (`engine/live.py`), the
  heartbeat's `remote` block (`engine/heartbeat.py`), the phone page `VIEWS.remote` (`tools/web_public/index.html`).
  Tests: `python -X utf8 -m tests.test_remote_ctl` (local bare git repo, fake NinjaTrader).
