# Move the bot to the main PC

Two PCs must never run the bot on the same accounts (double orders), so the old PC is retired in the same step that
packs its state. Do it **after 4:05 PM ET** on a weekday (or any time on a weekend).

## On the Surface (old PC)
1. Double-click **MOVE_BOT.bat** in the bot folder, type `1`, Enter. It stops the bot, turns auto-resume off, removes the
   start-at-logon tasks and packs the bot's own state (accounts, eval numbers, trade journal, bar archive, the live
   switch) into **OneDrive\BOT_MOVE** (or the Desktop). The pack holds your private settings: keep it in your own OneDrive.

## On the main PC (new PC)
1. Install **NinjaTrader 8**, log in, connect your **MFFU** connection, tick **Tools > Options > Automated trading
   interface > AT Interface**.
2. Open **OneDrive\BOT_MOVE**, double-click **MOVE_BOT.bat**, type `2`, Enter. It installs Git and Python if missing,
   gets the bot from GitHub (sign in once), restores the pack and starts **ONE_TIME_SETUP** (power, logon tasks, icons,
   auto-update, the bot: it asks your eval account name and the phrase).
3. In NinjaTrader: import `ninjatrader\LE_BarFeed.cs` (NinjaScript Editor, F5), open the **MNQ 12-26, 5 minute, 30 days**
   chart with **LE_BarFeed**, save the workspace. Then **LE START > Start trading**.

Script: `scripts/move_bot.ps1` (`-Pack` / `-NewPC`, `-DryRun` shows the plan; refuses to pack weekdays 01:15-16:05 ET).
