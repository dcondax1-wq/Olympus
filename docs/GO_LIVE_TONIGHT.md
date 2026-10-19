# Go live on the MFFU eval tonight (Sun 2026-10-18, 21:00 ET)

You switch it on yourself. Claude gets everything ready but never arms a real account.
Do the Sim test first; only go to the eval when the Sim test is clean.

## Before you start (once)
1. **Merge the PR** Claude sends (GitHub app, "Merge"). The cloud app and the phone notifications run from main.
2. On the Surface, run the Claude task **"Set up the NQ LIT paper bot on this Surface"** if it isn't done yet
   (Git, Python, the bot, NinjaTrader, the bar feed). Then on the Surface, in a PowerShell window in the bot folder:
   `git pull`, then `pip install -r requirements.txt` (the pull added `cryptography`, which the PC's phone notices need).
3. NinjaTrader 8: log in, connect your MFFU account (Tradovate connection), **Tools > Options > Automated trading
   interface > AT Interface** ticked. Control Center > Accounts: write down your eval account's **Name** exactly.
4. The `LE_BarFeed` indicator is on an **MNQ 12-26, 5 minute** chart, and `Documents\NinjaTrader 8\le_feed\` has
   `MNQ_5m.csv` and `MNQ_1m.csv` with today's time. On a Surface, Documents is often inside OneDrive
   (`C:\Users\<you>\OneDrive\Documents\NinjaTrader 8`); the bot finds that by itself, and step 7's first line
   (`NinjaTrader folder : ...  (exists True, incoming True, outgoing True)`) shows which folder it uses.
   If that line says `incoming False`, the folder is somewhere else: find the `NinjaTrader 8` folder that holds
   `le_feed` in File Explorer, then
   `Add-Content .env.local.ps1 '$env:NINJATRADER_FOLDER = "C:\full\path\to\NinjaTrader 8"'`, restart run_bot.ps1 and
   add `--folder "C:\full\path\to\NinjaTrader 8"` to every `python -m engine.ninjatrader` command below.
   **If Documents is in OneDrive: OneDrive tray icon > Pause syncing > 24 hours** before you go to bed (OneDrive can
   briefly lock the order and bar files while it uploads them; NinjaTrader itself advises against syncing its folder).

## 21:00 ET: Sim test (10 minutes)
5. Start the bot: in a PowerShell window in the bot folder run
   `powershell -ExecutionPolicy Bypass -File scripts\run_bot.ps1` and leave that window open (double-clicking a `.ps1`
   file only opens it in Notepad). Open http://localhost:8766. Run the commands below in a second PowerShell window
   in the bot folder.
6. `python -m engine.ninjatrader --selftest` → it must say PASS.
7. `python -m engine.ninjatrader --status` → `Bar feed 5m` and `Bar feed 1m` lines with a `last open` a few minutes
   ago (that is `MNQ_5m.csv` and `MNQ_1m.csv`; not `NOT USABLE`); then
   `python -m engine.ninjatrader --sim-check` → OK; then
   `python -m engine.ninjatrader --sim-roundtrip` → three `OK` lines and `FLAT`
   (if only the close fails, retry with `--close-suffix " Globex"` and add that to step 11).
   If step 2 or 3 shows `position None` while NinjaTrader shows the position, check Windows Settings > Time & language >
   Language & region > Regional format: it must use a dot for decimals (English (United States)); restart NinjaTrader
   after changing it. If an order file can't be written (`PermissionError`), Windows Security > Ransomware protection >
   Controlled folder access is on: allow `python.exe` there.
   **This is the first time the NinjaTrader route runs on a real install: if any of these fail, stay on Sim tonight
   and send Claude a photo.**
8. `python -m engine.ninjatrader --start` → the Live page log shows
   `NinjaTrader adapter: account Sim101 (SIM), MNQ 12-26, ... ready` and the strategy says **LIT**.

## Then: the eval (your step, all three locks)
9. Stop the Sim bot (dashboard **Stop**).
10. Stop the server completely: `powershell -ExecutionPolicy Bypass -File scripts\stop_bot.ps1` (the run_bot window
    says `supervisor stopped`). Then add the two lines to `.env.local.ps1` in the bot folder (these commands create the
    file if it is missing; Notepad could save it as `.env.local.ps1.txt`):
    `Add-Content .env.local.ps1 ''` (starts a new line), then `Add-Content .env.local.ps1 '$env:NINJATRADER_LIVE = "1"'`
    and `Add-Content .env.local.ps1 '$env:LE_HEARTBEAT = "1"'`.
    Start `powershell -ExecutionPolicy Bypass -File scripts\run_bot.ps1` again: its `supervisor pid ... starting` line
    must end with `loaded .env.local.ps1 (values not shown)`. The file is read only when run_bot.ps1 starts, so the dashboard Stop or
    `stop_bot.ps1 -RestartServer` is not enough. (run_bot.ps1 turns the heartbeat on by itself anyway. The heartbeat lets
    the cloud push "PC bot silent" to your phone if the PC dies; the cloud checks every 30 min from about 02:00 ET.)
    Only your eval account should be connected in NinjaTrader: the kill switch flattens every connected account.
11. Run: `python -m engine.ninjatrader --start --account <your eval account Name> --confirm "I ACCEPT LIVE RISK"`
    Type the Name exactly as the Accounts tab shows it (same capitals, dashes kept) and in quotes, e.g.
    `--account "MFFUEV12345"`; NinjaTrader ignores orders for an account name it doesn't know.
12. The command prints `Bot start: OK` and the line
    `NinjaTrader adapter: account <your eval Name> (LIVE ACCOUNT), MNQ 12-26, folder ..., ready`.
    If that line says `DISABLED (...)` instead of `ready`, the bot runs but every order is refused: the text says which
    lock is missing (usually: restart run_bot.ps1 as in step 10). Within a minute the Live page log also shows
    `Strategy locked: LIT - Liquidity Inducement (2026-tuned) + loss pack`. The sizing and the eval session are not in the
    log; check them with
    `$s = Invoke-RestMethod http://localhost:8766/api/live/state; $s.state.strategy.model; $s.state.eval_2wk.text`
    → `lit` and `session 1 of 10, 10 left, $3,100 to go` (Sunday evening counts as Monday Oct 19; sizing `two_week`
    and eval start 2026-10-19 come from `live_model.json`). If `--start` says `already running`, press **Stop** first.
    The sizing assumes the eval starts tonight at $49,900 (-$100, live_model.json lit_sizing.eval_prior_pnl). If the balance is different, tell Claude first.
13. Windows: pause updates for a week (Settings > Windows Update > Pause), and in a PowerShell opened with
    **Run as administrator**, in the bot folder, run
    `powershell -ExecutionPolicy Bypass -File scripts\setup_dedicated_pc.ps1 -NinjaTrader "C:\Program Files\NinjaTrader 8\bin\NinjaTrader.exe"`
    (no restarts 01:00-17:00 ET, no sleep; it does not touch the running bot).

## Overnight
- Leave the Surface **plugged in, awake, NinjaTrader open and connected**. No trade can happen before **02:00 ET**;
  most LIT trades are 02:00-08:00 ET.
- The stop and target are placed at the broker right after the fill (a few seconds; up to ~1 minute if NinjaTrader is
  slow to report the fill). After that, a dropped PC can't leave the trade unprotected, but it can't move the stop to
  breakeven or flatten at 15:55 either (MFFU auto-closes at 16:10).
  A real-account bot does **not** restart by itself after a crash or reboot: if the PC restarts, start step 11 again.
- Phone: entries and results arrive as notifications (tap **Turn on** in the app once).

## Know this
- **Your call on being present.** The project rule says MFFU wants the owner present for automated trading; MFFU's help
  center (searched 2026-10-18) says bots are allowed with your own settings and doesn't confirm a presence rule.
  Ask MFFU support in writing if you want to be sure.
- **Kill switch:** dashboard **HOLD TO KILL**, or in NinjaTrader right-click > Flatten Everything.
- One trade a day at most; size is set by the two-week rule (~$990 at risk at most, a full stop stays inside the
  $1,000 daily limit). It never trades the old strategy on this account.
- If nothing trades for 5 days, place 1 MNQ by hand (MFFU closes accounts after 7 quiet days).
- Back to testing: start again with `--account Sim101` and delete the line from `.env.local.ps1`.
