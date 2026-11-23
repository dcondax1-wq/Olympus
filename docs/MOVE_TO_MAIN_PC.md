# Move the bot to the main PC

Two PCs must never run the bot on the same accounts (double orders), so the old PC is retired in the same step that
packs its state. Do it **after 4:05 PM ET** on a weekday (or any time on a weekend).

## On the Surface (old PC)
1. Double-click **tools/bat/MOVE_BOT.bat** in the bot folder, type `1`, Enter. It stops the bot, turns auto-resume off, removes the
   start-at-logon tasks and packs the bot's own state (accounts, eval numbers, trade journal, bar archive, the live
   switch) into **OneDrive\BOT_MOVE** (or the Desktop). The pack holds your private settings: keep it in your own OneDrive.

## On the main PC (new PC)
1. Install **NinjaTrader 8**, log in, connect your **MFFU** connection, tick **Tools > Options > Automated trading
   interface > AT Interface**.
2. Open **OneDrive\BOT_MOVE**, double-click **tools/bat/MOVE_BOT.bat**, type `2`, Enter. It installs Git and Python if missing,
   gets the bot from GitHub (sign in once), restores the pack and starts **ONE_TIME_SETUP** (power, logon tasks, icons,
   auto-update, the bot: it asks your eval account name and the phrase).
3. In NinjaTrader: import `ninjatrader\LE_BarFeed.cs` (NinjaScript Editor, F5), open the **MNQ 12-26, 5 minute, 30 days**
   chart with **LE_BarFeed**, save the workspace. Then **LE START > Start trading**.

Script: `scripts/move_bot.ps1` (`-Pack` / `-NewPC`, `-DryRun` shows the plan; refuses to pack weekdays 01:15-16:05 ET).

## Surface is cooking: fresh start (no old PC state needed)
1. Switch the Surface **off** and wait 3 minutes (two PCs on the same accounts would double every order; the script checks and refuses).
2. On the main PC install **NinjaTrader 8**, log in, connect **MFFU**, tick **AT Interface**. Open PowerShell and paste:
   `powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://dcondax1-wq.github.io/pc/FRESH_START.ps1 | iex"`
   (or double-click **tools/bat/FRESH_START.bat** from the OneDrive PC_KIT folder). It shows its plan and asks Y first.
3. It installs Git and Python, gets the bot, shows your eval balance and floor from the published board (compare with MFFU, press Y), copies the NinjaTrader add-ons and starts ONE_TIME_SETUP (asks your eval account name; Enter = Sim101 practice).
4. In NinjaTrader: Control Center > New > NinjaScript Editor > press **F5** (no chart needed). Then **LE START > Start trading**.
5. Live trading is never turned on by this: you arm it yourself when you are at the PC.
