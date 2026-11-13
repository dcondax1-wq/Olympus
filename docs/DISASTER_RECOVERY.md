# OLYMPUS disaster recovery: how to get EVERYTHING back (written 2026-11-08 after the GitHub account was suspended)

Read this first if the repo, the site, the bots' reporting or an account is gone. Everything below needs only files you already hold.

## What lives where (and what depends on what)
| Thing | Where it really lives | Depends on GitHub? | If GitHub is gone |
|---|---|---|---|
| NQ bots (LIT / ATLAS / BLITZ) | the main PC + NinjaTrader | No (only their check-ins and pushes) | keep trading; reporting stops |
| Kalshi bot (real money) | Oracle Cloud VM `/home/ubuntu/kalshi`, chat "kalshi-server" | No (only its status feed `kalshi-feed`) | keeps trading; dashboard feed stops |
| Dashboards and apps (the site) | built from this repo | Yes (hosting + build) | rebuild from the zip, host anywhere |
| Planner app | was only on the old `nq-dashboard` repo, branch `planner-backup` | Yes | only its patches survive in `tools/planner_patches/` |
| Code, research, history | this repo | Yes | restore from the backup zip / bundle |

## The three copies you must always have (rule: 3 copies, 2 companies, 1 on your own device)
1. **Code zip** `OLYMPUS_BACKUP_<date>.zip` (made by `python tools/make_backup.py`): all tracked files. Keep it in iCloud / Google Drive / OneDrive.
2. **A second git host** (GitLab or Codeberg, free) that mirrors the repo: `BACKUP_SETUP.bat` once (see "Second backup" below).
3. **The main PC folder** (the bot folder). Never delete it. It holds files the repo never stores (keys, alerts, NinjaTrader bar archive).

## Second backup (2026-11-13): mirror + weekly zip, one double-click

Your 3 steps:
1. On **codeberg.org** (free): sign up, **+ > New repository**, name `olympus`, tick **Private**, no README, Create. Then
   **Settings > Applications > Generate new token**, permission **repository: Read and write**, Generate, copy it.
2. On the main PC double-click **`BACKUP_SETUP.bat`**: paste the repository address (`https://codeberg.org/<you>/olympus.git`),
   paste the token (it stays hidden), press Enter for the synced folder it offers (OneDrive / iCloud / Google Drive).
3. Wait for the three **[OK]** lines (SNAPSHOT, ZIP, MIRROR) and the phone push **"Weekly backup OK"**.

| What | Result |
|---|---|
| Mirror | every branch and tag + `pc-snapshot` (the files the PC really runs) on Codeberg / GitLab, private (a public repo is refused) |
| Weekly zip | `OLYMPUS_BACKUP_<date>_<sha>.zip` + `.sha256.txt` in the synced folder, the newest 4 kept |
| When | every Sunday 11:37 (task `OlympusWeeklyBackup`; later that day if the PC was off), one phone push with the result |
| Token | `%USERPROFILE%\.olympus\backup.json`, outside the bot folder, never printed; given to git only for the push, as a header |
| Undo | `BACKUP_SETUP.bat -Remove` deletes the task (the settings file and the repo stay) |

GitLab works the same (`https://gitlab.com/<you>/olympus.git`; token: the project > Settings > Access tokens, role Maintainer,
scope `write_repository`). Check any time: `python tools/second_backup.py --status`. Limits: the token sits in a plain file
in your Windows profile (like the ntfy topic); a free host's size limit applies (Codeberg asks to keep repos small: if the
first push is refused for size, use GitLab, 10 GB). Tests: `python -X utf8 -m tests.test_second_backup`.

## Restore the site on any host in about 10 minutes
1. Unzip the backup. In the folder: `python tools/build_web_dashboard.py --state dash/state.json --chart dash/chart.png --out site`
   (`dash/state.json` and `dash/chart.png` are in the zip's `research/handoff/` or can be any earlier copy; the site builds with the last snapshot).
2. Zip the CONTENTS of `site/` (index.html at the top of the zip), drop it on Netlify Drop (`app.netlify.com/drop`) or Cloudflare Pages. You get an https address.
3. iPhone: Safari, open the address, Share, Add to Home Screen. (A new address means re-adding the app once, and on-phone data such as Ledger entries
   and journal ratings starts empty: use each app's Export JSON regularly.)

## Restore the code on a new git host
1. `unzip OLYMPUS_BACKUP_*.zip -d olympus && cd olympus && git init && git add -A && git commit -m "restore"`
   (or `git clone nq-liquidity-engine-all.bundle olympus` if you hold the full-history bundle).
2. Create an empty repo on GitLab/Codeberg, then `git remote add origin <url>` and `git push -u origin --all`.
3. Tell ChatGPT/Claude the new URL; update `handoff/START_HERE_CHATGPT.md`.

## Live data without GitHub Actions
The cloud monitor (`tools/cloud_monitor.py`) only needs Python and the bot's state. Run it on the main PC every 15 minutes (Windows Task Scheduler),
then rebuild and re-upload the site. The NQ bot itself never needed GitHub to trade.

## Kalshi feed without GitHub
The VM builds `kalshi.json` with `tools/kalshi_kit/public/kalshi_status_vm.py`. Publish it anywhere that serves https JSON with CORS (the same Netlify site,
re-deployed with a fresh `kalshi.json` next to the page, works), and point the Kalshi page at it. Never put keys in the feed; the script redacts them.

## Habits that prevent a repeat
- Run `python tools/make_backup.py --out <iCloud folder>` weekly (it is idempotent and prints the SHA-256 of what it wrote).
- Keep the site, the bots and the code under different companies (Netlify / your PC + Oracle / GitHub + a mirror).
- Do not run many automated agents and 15-minute auto-commits on one free account. Batch the cloud monitor's publishing (hourly is plenty) and keep AI agents to a few, small pull requests.
- Never make a second account to get around a suspension; appeal instead (GitHub Support, from the email GitHub sent).
- Export Ledger, Mnemosyne (journal), Mind and Jarvis memory (each app's Export JSON) once a week.
