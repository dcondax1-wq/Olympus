# Troubleshooting: the top 15 problems

First step every time: double-click **LE HEALTH CHECK** on the Surface. Each red line says what to do. The same plain
words are used in the phone notices (`engine/ops_checks.py`, table `ERRORS`). Daily routine: `docs/DAILY_CHECKLIST.md`.

| # | You see | Fix |
|---|---|---|
| 1 | **FEED STALE** / "Bar feed 1m: last bar N min old" | Open NinjaTrader. The MNQ chart with **LE_BarFeed** must stay open and the connection green. Reload the chart (F5). The bot trades again by itself. |
| 2 | **NinjaTrader disconnected** | NinjaTrader > **Connections** > connect your account's connection. Check the internet. An open trade keeps its stop and target at the broker. |
| 3 | **Bot server: the dashboard does not answer** | Double-click **LE DASHBOARD** (starts the server). Still down after 2 min: look at the "Liquidity Engine bot" window's last red line. |
| 4 | **Bot: server up, bot STOPPED** | Dashboard > **Start** on your eval account (you type your phrase). Paper / Sim restarts by itself; the eval only with auto-resume on. |
| 5 | **Account: orders go to Sim101, not your eval** | Dashboard > **Stop**, pick the eval account, Arm, your phrase, **Start**. |
| 6 | **NinjaTrader folder: incoming missing** | NinjaTrader > Tools > Options > **Automated trading interface**: tick **AT Interface**, restart NinjaTrader. |
| 7 | **Controlled Folder Access** red / "Access is denied" | Windows Security > Virus & threat protection > Ransomware protection > **Allow an app** > add `python.exe` (HEALTH CHECK shows its path). |
| 8 | **OneDrive** yellow (NinjaTrader folder synced) | OneDrive > Settings > Sync and backup > Manage back up: turn **Documents** off, or pause syncing on trading days. |
| 9 | **Power / sleep** yellow | Settings > System > Power: Sleep **Never** when plugged in. Control Panel > Power Options > lid: **Do nothing**. |
| 10 | **Windows Update** yellow (not paused / restart pending) | Settings > Windows Update > **Pause updates**. Restart pending: restart yourself after 16:00 ET, then HEALTH CHECK. |
| 11 | **Clock** off by seconds | Settings > Time & language > Date & time: **Set time automatically** on, **Sync now**. |
| 12 | **Heartbeat push failed** (phone says "PC bot silent" while it runs) | Git sign-in expired. Open a terminal in the bot folder, run `git fetch`, sign in when the window asks; then STOP BOT + LE DASHBOARD. |
| 13 | **UPDATE**: "git pull failed" / "changed by hand" | The old version keeps running. Don't edit files in the bot folder. Send the UPDATE window (photo) to Claude. |
| 14 | **UPDATE / HEALTH**: "Python package is missing" | Double-click **LE UPDATE** (it runs pip install). Or in the bot folder: `python -m pip install -r requirements.txt`. |
| 15 | **Disk space** red | Empty the Recycle Bin; Settings > System > Storage > **Cleanup recommendations**. Old logs are zipped and backups pruned by themselves. |

More:
- **"Another copy of the bot is already running"**: **LE STOP BOT**, wait 10 s, **LE DASHBOARD**.
- **No phone notices at all**: open the Liquidity app from the Home Screen, Settings > notifications **on**
  (`docs/NOTIFICATIONS.md`). The PC links itself on the next cloud run (heartbeat on).
- **No 01:40 notice**: the helper task is missing or the PC was asleep. Double-click `SETUP_SHORTCUTS.bat` once (it adds the
  task `LiquidityEngineOps`); its log is `logs\ops-YYYYMMDD.log`.
- **Contract roll** (Dec 2026: MNQ 12-26 -> MNQ 03-27 on Thu Dec 10): on Wed Dec 9 after 16:00 ET change the LE_BarFeed
  chart's instrument to **MNQ 03-27**, Data Series > Days to load **30**, OK, then HEALTH CHECK. Orders switch by themselves.
- **State lost after a crash**: `backups\le-backup-YYYYMMDD-HHMM.zip` has the last 14 nights (bot state, NinjaTrader
  brackets, ledgers, bars). Ask Claude before restoring one.
- One error line you don't understand: in the bot folder, `python -m engine.ops_checks --translate "<the line>"`.
