# Remote control (phone -> PC bot)

The PC bot reads `control/command.json` on this branch every ~60 s (engine/remote_ctl.py, on with LE_REMOTE=1).

1. Phone app -> System -> **Remote**: tap the command (Status, Update now, Pause, Flatten, ...). Tap **Copy and open GitHub**.
2. GitHub opens this file's editor (https://github.com/dcondax1-wq/olympus/edit/control/control/command.json; in the GitHub app: branch `control`,
   `control/command.json`, the pencil). Select all, paste.
3. **Commit changes**. Within about a minute the phone gets a notice with the result.

The PC acts within ~60 s; update / restart only when the bot is flat, and never 01:50-16:00 ET on a weekday.

Commands: `kill` (flatten everything + stop + auto-resume off), `stop` (after flat; `"now": true` flattens first),
`flatten` (close the position, keep running, no new entry today), `update` / `restart` (only when flat, outside trading
hours), `status` (a fresh heartbeat + a notice), `pause` (no new entries until a time), `start` (Sim accounts only,
never a real account).

Rules: every command needs a new `id` and a `ts` within the last 15 minutes; an id runs once. No command changes the
config or the strategy, and nothing here can start a real account. See docs/REMOTE_CONTROL.md.
