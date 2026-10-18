# Go live on the MFFU eval tonight (Sun 2026-10-18, 21:00 ET)

You switch it on yourself. Claude gets everything ready but never arms a real account.
Do the Sim test first; only go to the eval when the Sim test is clean.

## Before you start (once)
1. **Merge the PR** Claude sends (GitHub app, "Merge"). The cloud app and the phone notifications run from main.
2. On the Surface, run the Claude task **"Set up the NQ LIT paper bot on this Surface"** if it isn't done yet
   (Git, Python, the bot, NinjaTrader, the bar feed). Then on the Surface: `git pull` in the bot folder.
3. NinjaTrader 8: log in, connect your MFFU account (Tradovate connection), **Tools > Options > Automated trading
   interface > AT Interface** ticked. Control Center > Accounts: write down your eval account's **Name** exactly.
4. The `LE_BarFeed` indicator is on an **MNQ 12-26, 5 minute** chart, and `Documents\NinjaTrader 8\le_feed\` has
   `MNQ_5m.csv` and `MNQ_1m.csv` with today's time.

## 21:00 ET: Sim test (10 minutes)
5. Start the bot: double-click `scripts\run_bot.ps1` (or `python server.py`), open http://localhost:8766.
6. `python -m engine.ninjatrader --selftest` → it must say PASS.
7. `python -m engine.ninjatrader --status` → shows fresh `MNQ_5m.csv` and `MNQ_1m.csv`; then
   `python -m engine.ninjatrader --sim-check` → OK; then
   `python -m engine.ninjatrader --sim-roundtrip` → three `OK` lines and `FLAT`
   (if only the close fails, retry with `--close-suffix " Globex"` and add that to step 11).
   **This is the first time the NinjaTrader route runs on a real install: if any of these fail, stay on Sim tonight
   and send Claude a photo.**
8. `python -m engine.ninjatrader --start` → the Live page log shows
   `NinjaTrader adapter: account Sim101 (SIM), MNQ 12-26, ... ready` and the strategy says **LIT**.

## Then: the eval (your step, all three locks)
9. Stop the Sim bot (dashboard **Stop**).
10. Add `$env:NINJATRADER_LIVE = '1'` and `$env:LE_HEARTBEAT = '1'` to `.env.local.ps1` in the bot folder, then
    restart `scripts\run_bot.ps1`. (The heartbeat lets the cloud push "PC bot silent" to your phone if the PC dies,
    from 01:50 ET.)
    Only your eval account should be connected in NinjaTrader: the kill switch flattens every connected account.
11. Run: `python -m engine.ninjatrader --start --account <your eval account Name> --confirm "I ACCEPT LIVE RISK"`
12. The log must show your eval account (not SIM), MNQ 12-26, LIT, sizing **two_week**, eval session 1 on Mon Oct 19.
    The sizing assumes the eval starts tonight at $50,000 with no trades. If it already has P&L, tell Claude first.
13. Windows: pause updates for a week (Settings > Windows Update > Pause), and run
    `scripts\setup_dedicated_pc.ps1` as Administrator (no restarts 01:00-17:00 ET, no sleep).

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
