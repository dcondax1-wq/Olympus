# Remote control from the phone (free, through GitHub)

Send one safe command to the PC bot from anywhere: status, **update now**, pause, flatten, stop, kill, restart, or a start
on Sim. No paid service, no token on the phone: you write one small file on GitHub with your own login, the PC reads it.

**Which repo (2026-11-20):** the one the PC updates from. Since 2026-11-14 that is the backup repo on the second account
(`update_source.json`: remote `olympus`), so the file is **`control/command.json` on branch `control` of
dcondax1-wq/olympus**: https://github.com/dcondax1-wq/olympus/edit/control/control/command.json. The old account (origin)
is gone; `engine/remote_ctl.control_source` follows `update_source.json` (no file, or `LE_UPDATE_SOURCE=origin`: origin as
before). GitHub-free mode (`engine/nogithub.py`) turns the remote off only when it would read origin, like the auto-update.

## How to use it (3 steps)

1. Phone app (Home Screen app) -> **More -> Remote** (`#/remote`). Tap the command: **Status**, **Update now**, **Pause
   until tomorrow**, **Flatten** are first; Stop, KILL, Restart, Start on Sim101, I'm here, Resume below. The page builds the
   exact text with a fresh id and time. The first time only: type the backup repo in the box (the second account, a slash,
   `olympus`) and tap **Save repo** (kept on that phone; the account name is not in the public site's code).
2. Tap **Copy and open GitHub**. GitHub's editor opens on `control/command.json`, branch `control` of the backup repo (in
   the GitHub app: repo `olympus`, branch `control`, the file `control/command.json`, the pencil). Select all, paste.
3. **Commit changes**. Within about a minute the phone gets a notice with the result ("Remote update: done", or why it
   was refused). The Remote page and the heartbeat show "remote: last cmd X done at HH:MM ET" and "Reads commands from
   olympus (control)".

**The PC acts within ~60 s; Update now and Restart only when the bot is flat, and never 01:50-16:00 ET on a weekday.**

A command expires **15 minutes** after you made it. If the PC was off, the old command is ignored (you get a notice
saying so) and nothing happens later by surprise.

## The commands

| cmd | what the PC does | when |
|---|---|---|
| `kill` | same as HOLD TO KILL: flatten everything (NinjaTrader FLATTENEVERYTHING), stop the bot, auto-resume OFF, autostart cleared. Restart only at the PC. | any time |
| `stop` | stop the bot once it is flat (an open trade or an armed LIT setup finishes first). `"now": true` closes the position first, then stops. | any time |
| `flatten` | close the open position now. The bot keeps running and trades again from the next trading day (no new entry today). | any time |
| `status` | push a fresh heartbeat and send a phone notice: running / stopped, account, position, LIT stage, feed age, version. | any time |
| `update` | **Update now**: the auto-update now (`engine/autoupdate.py`: the update source only = the backup's `pc` branch, fast-forward only, self-tests, roll back on failure), then a restart when it updated. Does not need the daily auto-update to be switched on. A real-account bot without auto-resume stays stopped after the restart until you start it. | flat, nothing pending, outside 01:50-16:00 ET on a weekday, server run by `run_bot.ps1` |
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
  fast-forwards to the update source (`olympus/pc`, which a writer could change anyway), runs the self-tests and rolls
  back on failure.
- Nothing remote can open a trade on a real account or arm live trading.
- Keep the repo private and do not add collaborators you would not hand the PC to. Turn it off with `LE_REMOTE=0`.

## Setup (once)

- The `control` branch of the backup repo holds an expired no-op (`{"id": "noop-0", "ts": 0, "cmd": "none"}`: skipped
  silently) + a README. Made by `python tools/init_control_branch.py` (its default remote follows `update_source.json`:
  `olympus`; it never overwrites an existing branch), or with plain git from the copy in `tools/control_branch/control/`:
  `git init -q -b control /tmp/ctl && cp -r tools/control_branch/control /tmp/ctl/ && git -C /tmp/ctl add -A &&
  git -C /tmp/ctl commit -qm "control branch" && git -C /tmp/ctl push https://github.com/dcondax1-wq/olympus control`.
- `scripts/run_bot.ps1` sets `LE_REMOTE=1` (like `LE_HEARTBEAT=1`). The PC fetches with the same git login it updates
  with (remote `olympus`; if that remote is missing, the URL in `update_source.json`). Set `$env:LE_REMOTE = '0'` in
  `.env.local.ps1` to turn it off.
- Without GitHub at all: the bot server's private Tailscale link `https://<pc>.<tailnet>.ts.net:8444/safety/` (pause,
  flatten, kill; `engine/phone_safety.py`, `engine/phone_link.py`: port 8444 because 443 belongs to the old Jarvis app).
- Code: `engine/remote_ctl.py` (thread in `server.py`, every ~60 s; `control_source` picks the repo), `LiveBot.flatten_now`
  (`engine/live.py`), the heartbeat's `remote` block (`engine/heartbeat.py`, with `via`), the phone page `VIEWS.remote`
  (`tools/web_public/main.js`). Tests: `python -X utf8 -m tests.test_remote_ctl` (local bare git repos, fake NinjaTrader;
  the backup-repo path in `olympus_tests`).
