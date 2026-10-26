# Go live on the MFFU eval tonight (Sun 2026-10-18, 21:00 ET)

**Easiest way (2026-10-26): double-click `START_BOT.bat` in the bot folder, or use the dashboard Start page**
(http://localhost:8766 on the PC, sidebar **Start**: the same steps as one checklist, one button per red line, and your
accounts; it only works on the PC itself, the phone can only look). START_BOT.bat (after the first run it is the
**LE START BOT** icon on the desktop). One window does all of this page: update, both accounts set up once, the
Sim101 test once (market open), then you type `I ACCEPT LIVE RISK` and it arms the 25K, sets the live switch, starts
the server and the bot on the 50K and prints the launch checklist. Double-click again any time: done steps are
skipped, a running bot is left alone (`engine/go.py`, tests `python -X utf8 -m tests.test_go`). It opens NinjaTrader
and waits for your log-in; the same typed line turns on auto-resume and adds NinjaTrader + the bot server to the Windows
Startup folder, so afterwards turning the PC on (and logging in to NinjaTrader) brings the bot back by itself.

You switch it on yourself. Claude gets everything ready but never arms a real account.
Do the Sim test first; only go to the eval when the Sim test is clean.

**Daily use after the first night:** the one-page [DAILY_CHECKLIST.md](DAILY_CHECKLIST.md) (night before / morning /
after close / weekly) replaces these steps; problems: [TROUBLESHOOTING.md](TROUBLESHOOTING.md). Double-click
`SETUP_SHORTCUTS.bat` once for the desktop icons (UPDATE, DASHBOARD, HEALTH CHECK, STOP BOT) and the phone notices
(01:40 pre-session check, 16:05 day summary, Sunday week report, drops, MFFU reminders) with the nightly backup.

## No Yahoo (update 2026-10-19): do this on the Surface now
The bot no longer uses Yahoo anywhere (`"no_yahoo": true` in `live_model.json`). It trades only on NinjaTrader's MNQ bars
plus the TradingView history in `data/`, and the cloud paper bot trades on the bars your PC sends it.
1. Stop the bot: `powershell -ExecutionPolicy Bypass -File scripts\stop_bot.ps1`.
2. `git pull`
3. Start it again: `powershell -ExecutionPolicy Bypass -File scripts\run_bot.ps1`, then the same `--start` command you use
   (step 8 for Sim, step 11 for the eval). The Live page log shows `data=ninjatrader (no Yahoo)`.
4. Within ~5 minutes the cloud README's Feed line says `OK ... (PC NinjaTrader bars, no Yahoo)` instead of
   `WAITING - waiting for NinjaTrader bars from the PC`.
What changes for you:
- If NinjaTrader's chart stops writing bars (closed, disconnected), the bot opens **no new trade** and the phone says
  **FEED STALE**. An open trade keeps its stop and target at the broker. Fix NinjaTrader and it trades again by itself.
- The cloud paper bot needs the PC's bars: with the PC off it waits and takes no paper trades.
- Keep the NinjaTrader chart at **30 days loaded**. The bot also keeps its own copy of every bar (`data\nt_bars\`).

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
   ago (that is `MNQ_5m.csv` and `MNQ_1m.csv`; not `NOT USABLE`: with no Yahoo the bot takes no trade without them); then
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
11. Once per account (2026-10-25, the account allowlist): `python -m engine.ninjatrader --allow-account "<your eval account Name>"`.
    Then run: `python -m engine.ninjatrader --start --account <your eval account Name> --confirm "I ACCEPT LIVE RISK"`
    (the bot starts DISARMED and allows entries once the log says `STARTUP RECONCILED`; see
    `research/handoff/2026-10-25/STARTUP_AND_RECOVERY_RUNBOOK.md`)
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
  A real-account bot does **not** restart by itself after a crash or reboot unless you turned on auto-resume
  ("Make it run on its own" below): without it, if the PC restarts, start step 11 again.
- Phone: entries and results arrive as notifications (tap **Turn on** in the app once).

## Make it run on its own (optional, you turn it on once)
Two switches, both off until you type them on the Surface (PowerShell in the bot folder). Nothing else changes.

**1. Auto-update** (new code from GitHub without you):
`python -m engine.autoupdate --enable`
- It checks once a day at 17:02-17:50 ET (the CME halt) and whenever `run_bot.ps1` starts (e.g. after a reboot).
- Only when the bot is **flat** (no trade, no limit or 1m entry waiting) and never 01:50-16:00 ET on a weekday.
- Only a clean fast-forward of `main`. If you edited a file or the bot's folder has its own commits, it changes
  nothing and your phone says why.
- It runs the self-tests; if one fails it goes straight back to the version it had and tells your phone
  ("Bot update failed, rolled back"). On success the server restarts by itself (a few seconds).
- The phone app and the cloud README show `running version abc1234, updated Tue 17:05 ET; auto-update on`.
- Off: `python -m engine.autoupdate --disable`. Log: `logs\update-YYYYMMDD.log`.

**2. Auto-resume on your eval** (the bot comes back on the eval after its own crash, an update or a Windows restart):
`python -m engine.ninjatrader --enable-auto-resume --account "<your eval account Name>" --confirm "<the phrase from step 11>"`
- It remembers that exact account and today's date (in `data\auto_resume.json`, which is never uploaded; the phrase
  itself is not stored). If the bot is not running it also starts it now, like step 11.
- It comes back only when: `NINJATRADER_LIVE = "1"` is still in `.env.local.ps1`, the account is exactly the same,
  NinjaTrader shows a connected connection (after a reboot it waits up to 30 min for NinjaTrader), the kill switch was
  not used today, there was no daily loss of $1,000+ today, and no start failed in the last 10 minutes.
- Every time it comes back your phone says **"Bot resumed on <account> after <reason>"**; when it refuses, the phone says
  why and you start it by hand (step 11).
- It does **not** come back after you press **Stop** (a stop stays a stop) or after the kill switch.
- Off: `python -m engine.ninjatrader --disable-auto-resume`. The kill switch (**HOLD TO KILL** or `--kill`) also turns it
  off; to have it again, type the enable command again.
- With auto-resume off, after an auto-update your phone says "Updated to abc1234: bot is stopped on your eval, type
  the start command to resume" and you type step 11.
- For a reboot to bring everything back you also need `setup_dedicated_pc.ps1` (step 13: the logon task, NinjaTrader at
  logon) and automatic sign-in (Autologon, printed by that script).

## Know this
- **Your call on being present.** The project rule says MFFU wants the owner present for automated trading; MFFU's help
  center (searched 2026-10-18) says bots are allowed with your own settings and doesn't confirm a presence rule.
  Ask MFFU support in writing if you want to be sure.
- **Kill switch:** dashboard **HOLD TO KILL**, or in NinjaTrader right-click > Flatten Everything.
- One trade a day at most; size is set by the two-week rule (~$990 at risk at most, a full stop stays inside the
  $1,000 daily limit). It never trades the old strategy on this account.
- If nothing trades for 5 days, place 1 MNQ by hand (MFFU closes accounts after 7 quiet days).
- Back to testing: start again with `--account Sim101` and delete the line from `.env.local.ps1`.
