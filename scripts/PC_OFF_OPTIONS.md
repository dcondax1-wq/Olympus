# Trading with the PC off: the honest options (2026-10-17)

The strategy's brain can run for free with the PC off (TradingView Plus runs the Pine strategy on its servers; the
GitHub cloud monitor runs the Python engine every 15 minutes). The hard part is the **order into the MFFU account**:
Tradovate gives no API to prop accounts, TradingView cannot place orders from a strategy by itself, and NinjaTrader
only places orders while it is running on a Windows machine. So:

| Option | PC | Orders | Cost | Status |
|---|---|---|---|---|
| **A. TradingView brain + one tap on the phone** | truly off | TradingView alert pushes the exact order ("LONG 12 MNQ · stop 29,880.25 · target 29,990.50 · risk $780"); you place it in TradingView's Tradovate panel or the Tradovate app | free (TradingView Plus already paid) | `tradingview/liquidity_engine.pine` + `BRIDGE_SETUP.md` (phone-text alert format) |
| **B. PC acts like it's off** | wakes itself 07:50 ET, hibernates 16:35 ET, screen off | the PC bot through NinjaTrader 8 on the MFFU account (`ninjatrader/SETUP.md`), real CME bars from NinjaTrader | free | `scripts/schedule_pc.ps1` (this folder) + `scripts/install_autostart.ps1` |
| **C. TradingView brain + webhook bridge** | truly off | PickMyTrade or TradersPost places the order in the Tradovate account | about $50/month (7-day trials) | `tradingview/BRIDGE_SETUP.md` |
| **D. NinjaTrader on a rented Windows server** | truly off | same as B, on a small Windows VPS running 24/5 | about $15-25/month | same scripts as B on the VPS |

The cloud monitor stays on in every option: it is a second pair of eyes that alerts the phone when the PC bot is not
polling during a session, and keeps the public dashboard current.

**Before any real order on the MFFU eval:** ask MFFU support in writing whether automated execution is allowed on
your account (some guides say only semi-automated trading with you watching is allowed). Keep the reply. Test on
Sim101 / the Tradovate demo first. CLAUDE.md: paper only until the owner arms it; MFFU requires the owner to be present.

## Option B in five steps (free, hands-off)

1. Install NinjaTrader 8, connect the MFFU account, enable the automation interface and the bar feed: `ninjatrader/SETUP.md`.
2. One-time, in an **Administrator** PowerShell in the project folder:
   `powershell -ExecutionPolicy Bypass -File .\scripts\install_autostart.ps1` (bot supervisor at logon), then
   `powershell -ExecutionPolicy Bypass -File .\scripts\schedule_pc.ps1 -NinjaTrader "C:\Program Files\NinjaTrader 8\bin\NinjaTrader.exe"`.
3. Keep the user logged in (locking the screen is fine); set Windows to never sleep on its own while plugged in
   (the Sleep task hibernates it at 16:35 ET instead); laptops: lid close = do nothing.
4. Test once: put the PC to sleep, fire the Wake task a few minutes ahead (the script prints the command), and watch
   `logs\schedule-YYYYMMDD.log` and the dashboard.
5. Weekday rhythm: 07:50 ET wake, bot + NinjaTrader start, 08:00 sweeps arm, killzones trade, 15:55 flat, 16:35 hibernate.
   If the PC was fully shut down instead of hibernated, a wake timer cannot start it: enable "Power On By RTC Alarm" in
   the BIOS for 07:45 local time, or let the Sleep task do the hibernating.
