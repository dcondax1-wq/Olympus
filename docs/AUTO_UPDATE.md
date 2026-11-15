# The PC updates itself (owner 2026-11-14)

Owner: "figure out a way, whether it's going back to GitHub and keeping it just in case we get banned ... I'm not
updating the files every time we make changes, so do it now."

| What | How it works |
|---|---|
| Backup | A **private** copy of everything on your second GitHub account: repo `dcondax1-wq/olympus`. The code the PC runs is on its branch `pc`. |
| New code reaches the PC | By itself. The PC checks the backup once a day in the 17:02 ET pause and once an hour outside trading time. |
| When it never updates | During trading hours (01:50-16:00 ET on weekdays), with a trade open, or with a LIT entry waiting. |
| Your evals | An eval bot without auto-resume only updates at the weekend (the **Friday or Saturday** 17:02 ET pause), so an update never stops it in the middle of the week. If it does update, your phone says so; start it again before Sunday 6 PM ET. Starting the bot yourself (START BOT) always takes the newest code first. |
| Safety | After each update it runs its quick self-tests. If one fails, it goes back to the code it had and your phone tells you. |
| If GitHub ever bans that account too | Nothing breaks: the bot keeps running the code it has, and the code zips (`SETUP_EVERYTHING.bat`) still work. |

## Your part (once)
1. On GitHub as **dcondax1-wq**: create the private repo `olympus`, and give the Claude app access to it
   (`https://github.com/apps/claude/installations/select_target` -> dcondax1-wq -> Only select repositories -> olympus).
2. On the PC, double-click `SETUP_EVERYTHING.bat` (Sunday after 6 PM ET). Its auto-update step opens a GitHub window the
   first time: **sign in as dcondax1-wq**. After that, no more zips.

## For the lead (every change that should reach the PC)
- Test it, then push the release to the backup: `git push olympus <release>:pc` (attach the repo first: add_repo
  `dcondax1-wq/olympus` with push access). The PC installs it within the hour when it is flat. The backup's default
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
