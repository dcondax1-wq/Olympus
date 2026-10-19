# Trading with the PC off: the honest options (2026-10-17)

The strategy's brain can run for free with the PC off (TradingView Plus runs the Pine strategy on its servers; the
GitHub cloud monitor runs the Python engine every 15 minutes). The hard part is the **order into the MFFU account**:
Tradovate gives no API to prop accounts, TradingView cannot place orders from a strategy by itself, and NinjaTrader
only places orders while it is running on a Windows machine. So:

| Option | PC | Orders | Cost | Status |
|---|---|---|---|---|
| **A. TradingView brain + one tap on the phone** | truly off | TradingView alert pushes the exact order ("LONG 12 MNQ · stop 29,880.25 · target 29,990.50 · risk $780"); you place it in TradingView's Tradovate panel or the Tradovate app | free (TradingView Plus already paid) | `tradingview/liquidity_engine.pine` + `BRIDGE_SETUP.md` (phone-text alert format) |
| **B. PC acts like it's off** | wakes itself 01:30 ET (LIT trades from 02:00), hibernates 16:35 ET, screen off | the PC bot through NinjaTrader 8 on the MFFU account (`ninjatrader/SETUP.md`), real CME bars from NinjaTrader | free | `scripts/schedule_pc.ps1` (this folder) + `scripts/install_autostart.ps1` |
| **C. TradingView brain + webhook bridge** | truly off | PickMyTrade or TradersPost places the order in the Tradovate account | about $50/month (7-day trials) | `tradingview/BRIDGE_SETUP.md` |
| **D. NinjaTrader on a rented Windows server** | truly off | same as B, on a small Windows VPS running 24/5 | about $15-25/month | same scripts as B on the VPS |
| **E. A spare PC that never sleeps (the Surface)** | main PC off; the Surface is on 24/7 in a drawer, screen off | the bot through NinjaTrader on the Surface, real CME bars from NinjaTrader; it comes back by itself after restarts and reports a heartbeat to the cloud, which alerts your phone if it goes quiet | free | `scripts/setup_dedicated_pc.ps1` (one run) |

The cloud monitor stays on in every option: it is a second pair of eyes that alerts the phone when the PC bot is not
polling during a session, and keeps the public dashboard current.

**Before any real order on the MFFU eval:** ask MFFU support in writing whether automated execution is allowed on
your account (some guides say only semi-automated trading with you watching is allowed). Keep the reply. Test on
Sim101 / the Tradovate demo first. CLAUDE.md: paper only until the owner arms it; MFFU requires the owner to be present.

## Option E: the Surface as the always-on box (free, fully automatic, nothing scheduled)

The strategy decides when to trade (sweeps arm from 08:00 ET, entries in the killzones); the machine just has to be
awake and connected all the time. A low-end Surface is enough: the bot is light, NinjaTrader runs one chart.
Requirements: a 64-bit Surface with Windows 10/11 (not Windows RT, not S mode; Surface Pro X works only in emulation),
4 GB RAM or more, plugged in, on Wi-Fi/ethernet. Steps:

1. Install git, Python 3.12 (tick "Add to PATH"), clone the repo, `pip install -r requirements.txt`; install NinjaTrader 8
   and connect the MFFU account (`ninjatrader/SETUP.md`).
2. In an **Administrator** PowerShell in the project folder:
   `powershell -ExecutionPolicy Bypass -File .\scripts\setup_dedicated_pc.ps1 -NinjaTrader "C:\Program Files\NinjaTrader 8\bin\NinjaTrader.exe"`
   It checks the machine, sets never-sleep / screen-off / lid-close-does-nothing / night-time Windows updates, installs
   the bot's logon task and a NinjaTrader startup shortcut, then prints the five things to do by hand (automatic sign-in,
   NinjaTrader "connect on startup", start the bot once on Sim101, lock the screen, MFFU's written OK).
3. The heartbeat: `scripts/run_bot.ps1` turns on `LE_HEARTBEAT=1`, so the server pushes a tiny "I'm alive" commit to the
   repo's `heartbeat` branch every 5 minutes (needs git push rights on that PC: sign in once). The cloud monitor reads it
   on every run and sends a Telegram/Discord alert when the bot said it was running but has been silent for 20 minutes
   during a session (08:00-16:30 ET), at most once an hour. The public dashboard shows "PC bot · last seen N min ago".
4. What can still stop it: a power cut (plug the charger into a surge protector; the bot resumes at logon), Wi-Fi loss
   (the watchdog restarts polling; NinjaTrader reconnects), NinjaTrader's daily reconnect at 17:00-18:00 ET (normal),
   a NinjaTrader update prompt (decline during sessions). Check the dashboard once a day.

## Option B in five steps (free, hands-off)

1. Install NinjaTrader 8, connect the MFFU account, enable the automation interface and the bar feed: `ninjatrader/SETUP.md`.
2. One-time, in an **Administrator** PowerShell in the project folder:
   `powershell -ExecutionPolicy Bypass -File .\scripts\install_autostart.ps1` (bot supervisor at logon), then
   `powershell -ExecutionPolicy Bypass -File .\scripts\schedule_pc.ps1 -NinjaTrader "C:\Program Files\NinjaTrader 8\bin\NinjaTrader.exe"`.
3. Keep the user logged in (locking the screen is fine); set Windows to never sleep on its own while plugged in
   (the Sleep task hibernates it at 16:35 ET instead); laptops: lid close = do nothing.
4. Test once: put the PC to sleep, fire the Wake task a few minutes ahead (the script prints the command), and watch
   `logs\schedule-YYYYMMDD.log` and the dashboard.
5. Weekday rhythm (LIT): 01:30 ET wake, bot + NinjaTrader start, 02:00-15:30 entries (most before 08:00), 15:55 flat, 16:35 hibernate.
   If the PC was fully shut down instead of hibernated, a wake timer cannot start it: enable "Power On By RTC Alarm" in
   the BIOS for 07:45 local time, or let the Sleep task do the hibernating.
