# Startup and recovery runbook (bot on NinjaTrader, from 2026-10-25)

Plain steps for the Surface. Every command goes into a PowerShell window opened in the bot folder. Copy the grey text
exactly. `<Name>` = your account's **Name** exactly as NinjaTrader's Control Center > **Accounts** tab shows it (same
capitals, keep the dashes), in quotes.

## 1. Once per real account: the allowlist
The bot only sends orders to account Names you listed yourself. Sim101 never needs it.

`python -m engine.ninjatrader --allow-account "<Name>"`

It answers `Allowed: <Name>`. Check the list any time: `python -m engine.ninjatrader --list-allowed`.
Remove one: `python -m engine.ninjatrader --disallow-account "<Name>"`. (Account B's Name too, if you use it.)

## 2. Start (every time)
1. NinjaTrader open, logged in, connected; the MNQ 12-26 chart with LE_BarFeed open.
2. `powershell -ExecutionPolicy Bypass -File scripts\run_bot.ps1` (leave that window open).
3. In a second window: `python -m engine.ninjatrader --start --account "<Name>" --confirm "I ACCEPT LIVE RISK"`
   (for the Sim test: `python -m engine.ninjatrader --start`).

What you should see on the Live page log (http://localhost:8766):
- `NinjaTrader adapter: account <Name> (LIVE ACCOUNT), MNQ 12-26, ... ready`.
  If it says `DISABLED (...)`, the text says why: `not in the account allowlist` = step 1; `another bot process already
  trades account` = a second copy is running (see 5); `NINJATRADER_LIVE=1` = restart run_bot.ps1 (GO_LIVE step 10).
- **The bot starts DISARMED for entries.** Within a poll or two: `STARTUP RECONCILED ... entries allowed`.
  Until then the log shows `STARTUP DISARMED (no new entries yet): <reason>`. Usual reasons and the fix:

| Reason in the log | What to do |
|---|---|
| `bar feed not fresh` | The LE_BarFeed chart is closed / disconnected, or it is the 17:00-18:00 break. Fix the chart; it clears itself. |
| `PC clock check ... still running` | Wait a minute. |
| `NinjaTrader shows LONG/SHORT ... that no bracket of the bot explains` | A position the bot did not open. Close it in NinjaTrader (Positions tab > Flatten) if it is not yours to keep. |
| `Chart is on the old contract` | Put the LE_BarFeed chart on the contract named in the message. |
| `every NinjaTrader connection DISCONNECTED` | Reconnect NinjaTrader (Connections menu). |
| `NinjaTrader reports reset` or `state file was unreadable` | Look at NinjaTrader's Positions and Orders tabs. If they are what you expect, run `python -m engine.ninjatrader --confirm-reset`. |
| `eval start unknown`, `eval anchor ...`, `eval room ... <= 0` | Do not trade: send Claude a photo of the line. |

## 3. Check while running
`python -m engine.ninjatrader --status` (folders, account, positions, bar feed age). Phone pushes tell you about
fills, blocks and problems.

## 4. Shutdown (normal)
1. Flat first (no open trade), or let the trade finish; the bot is flat at 15:55 ET by itself.
2. Dashboard **Stop** (or `python -m engine.ninjatrader --stop`). This also frees the account for a Sim check.
3. To end the server too: `powershell -ExecutionPolicy Bypass -File scripts\stop_bot.ps1`.

## 5. After a crash, a reboot or a NinjaTrader restart
- **Bot crashed / PC rebooted**: start again as in 2 (auto-resume does it if you turned it on). The bot reloads the
  open trade from `data\ninjatrader_state.json` and waits for `STARTUP RECONCILED`. It never chases a missed entry.
- **NinjaTrader restarted**: the bot blocks new entries and pushes `outgoing reports vanished`. The stop and target
  stay at the broker. When NinjaTrader is connected again it usually clears by itself; if not, check Positions + Orders,
  then `python -m engine.ninjatrader --confirm-reset`.
- **"another bot process already trades account ..."**: two copies are running. `powershell -ExecutionPolicy Bypass -File scripts\stop_bot.ps1`,
  wait 10 s, then start once (step 2).

---

## EMERGENCY (one page)

**Get flat first, ask questions later. Any ONE of these is enough:**

1. **HOLD TO KILL** on the dashboard (http://localhost:8766). This is your global kill: NinjaTrader *Flatten
   Everything* on **every** connected account, the bot stops for today, auto-resume off.
   Same from a PowerShell window: `python -m engine.ninjatrader --kill` (works even when the dashboard is down).
2. In **NinjaTrader**: right-click a chart or the Positions tab > **Flatten Everything**.
3. Away from the PC: phone > **Tradovate / MFFU app** > the account > **Flatten / Exit all**.

| You see | Do this |
|---|---|
| A position with no stop in NinjaTrader's Orders tab | NinjaTrader **Flatten Everything**, then HOLD TO KILL. Never add a stop by hand. |
| More micros than the phone said, or more than 40 | NinjaTrader **Flatten Everything**, then HOLD TO KILL, then tell Claude. |
| Phone: `FLATTEN NOT CONFIRMED` or `KILL ... flat not confirmed` | Open NinjaTrader Positions. Still open: **Flatten Everything** there, or the MFFU app. |
| Phone: `FLATTEN BY HAND` | NinjaTrader **Flatten Everything**. |
| Dashboard does not open / phone says PC silent | A trade open keeps its stop and target at the broker. Want out: MFFU app > Flatten. |
| NinjaTrader disconnected mid-trade | Reconnect. Not back within a few minutes: MFFU app > Flatten. |

Good to know:
- A **remote flatten** from the phone, or the bot closing account B, closes **only that account** (it no longer uses
  Flatten Everything). Only your HOLD TO KILL / remote **kill** / `--kill` touches every account.
- After a kill the bot stays off for the rest of the day. To trade again tomorrow, start it as in 2.
- Never arm a real account to "fix" something, and never trade by hand on the bot's account while it runs.
