# NinjaTrader 8 route: the PC bot places orders through NinjaTrader

**What it does.** The PC bot runs the same strategy and settings as always (today: LIT, `live_model.json`). Instead of paper fills, it writes small
"order instruction files" into a folder that NinjaTrader 8 watches. NinjaTrader places the orders on the account you
name, for example `Sim101` for testing or the MFFU account through its Tradovate connection. NinjaTrader writes back
fills and positions, and the bot reads them. A small NinjaTrader indicator, `LE_BarFeed`, also hands the bot the real
CME bars from your chart. **No Yahoo (owner 2026-10-19, `"no_yahoo": true` in `live_model.json`, the default):** the bot
trades only on NinjaTrader's bars plus the TradingView exports in `data/`; it never calls Yahoo, and the cloud paper bot
trades on the bars this PC pushes with its heartbeat.

```
PC bot (server.py) --order files--> Documents\NinjaTrader 8\incoming --> NinjaTrader 8 --Tradovate connection--> account
NinjaTrader  ------fills/positions--> Documents\NinjaTrader 8\outgoing --> PC bot
MNQ 5m chart + LE_BarFeed --bars--> Documents\NinjaTrader 8\le_feed\MNQ_5m.csv --> PC bot (the only live feed)
                         \-1m bars-> Documents\NinjaTrader 8\le_feed\MNQ_1m.csv --> PC bot (LIT's 1-minute entry)
PC bot --keeps every bar in data\nt_bars\ (its own archive) and pushes the last days with the heartbeat--> cloud paper bot
```

**LIT needs the 1-minute file.** LIT finds its setups on 5-minute bars but enters on a 1-minute confirmation. On 5-minute
bars only, the same rules made +$6.6k in 2026 instead of +$41.7k. One MNQ 5-minute chart with LE_BarFeed writes both
files (step 4). LIT also trades the London morning: entries from **02:00 ET** (most 2026 trades entered 02:00-08:00 ET),
so NinjaTrader and the PC bot must be running from about 01:55 ET.

Why this route: Tradovate gives prop accounts no API keys, so `engine/tradovate.py` cannot reach the MFFU account.
NinjaTrader's Automated Trading Interface (ATI) can, and it needs no password or key.

Legend: **[doc]** means the NinjaTrader 8 Help Guide says so (links at the end). **[UNVERIFIED]** means it could
not be checked from the build machine. Check it on your PC with the tests in step 5.
Note: ninjatrader.com was blocked from the machine that built this. The order-file format was checked line by line
against verbatim copies of the Help Guide pages (see Sources). Open the official pages once yourself.

---

## Read this first

- **MFFU must say yes in writing first.** Do this before you put the eval or a funded account on this route. Ask MFFU
  support the questions in step 2 and keep the reply. Some guides say MFFU allows automation only while you are
  present and monitoring.
- **Sim101 first.** Run the two tests in step 5 and at least one full real signal on `Sim101`: entry, stop to
  breakeven, exit. Only then think about the MFFU account.
- **Paper until you arm it.** A real account needs three locks at once (step 11). Nothing in this repo arms them.
- **No NinjaTrader = no orders.** If NinjaTrader or the PC is off, nothing is placed, moved or closed (step 9).

## 1. Install NinjaTrader 8 (free)

1. Download NinjaTrader Desktop (NinjaTrader 8) from ninjatrader.com and install it on the Windows PC. Sign in with a
   free NinjaTrader login.
2. Install Python and the repo as usual (README). The bot and NinjaTrader must be on the **same Windows user** of the
   **same PC**: they share the `Documents\NinjaTrader 8` folder.

## 2. Connect the MFFU account (Tradovate connection)

1. Control Center > **Connections > Configure** > add a **Tradovate** connection. Log in with the Tradovate
   username and password from MFFU's onboarding email. Pick the environment MFFU tells you to use
   **[UNVERIFIED which one an MFFU eval needs]**.
2. Tick **Connect on startup**, then Connect.
3. Control Center > **Accounts** tab: write down the account's **Name** exactly, not its display name **[doc: the
   ACCOUNT field takes the account's Name property, not the Display Name]**. `Sim101` is always there for testing.
4. **Ask MFFU in writing** and keep the reply:
   - Can my Builder 50K account be traded from NinjaTrader 8 Desktop through the Tradovate connection? Does that need
     a NinjaTrader license or any paid add-on? If it costs money, stop here: the project rule is no paid services.
   - Which Tradovate environment do I pick in NinjaTrader for this account?
   - Is fully automated order entry allowed? That means my own program sending orders through NinjaTrader's Automated
     Trading Interface, with a stop and target on every trade, on the eval and on a funded account.
   - What does "present and monitoring" mean? Must I sit at the screen, or is phone alerts plus a kill switch enough?
     Is a PC that runs the bot all day acceptable?
   - Any rules on order count, news, or being flat before the close (the bot is flat by 15:55 ET)?

## 3. Turn on the Automated Trading Interface

1. Control Center > **Tools > Options > Automated trading interface** > tick **AT Interface** **[doc]**.
   Leave "Ignore duplicate OIF files" as it is: the bot never reuses a file name.
2. Restart NinjaTrader once **[UNVERIFIED whether a restart is required]**. These folders now exist:
   `Documents\NinjaTrader 8\incoming` and `Documents\NinjaTrader 8\outgoing`.
3. If NinjaTrader asks you to confirm every order (an order-confirmation option under Tools > Options), the bot's
   orders could wait for a click **[UNVERIFIED]**. Step 5 shows whether they go through on their own.

## 4. The bar feed: `LE_BarFeed`

1. Copy `ninjatrader\LE_BarFeed.cs` from the repo into `Documents\NinjaTrader 8\bin\Custom\Indicators\`.
2. Control Center > **New > NinjaScript Editor** > Indicators > double-click **LE_BarFeed** > press **F5** (compile).
   A message at the bottom says whether it compiled. The editor adds a block called "NinjaScript generated code" at
   the end of the file. That is normal. If the bottom panel lists errors, check which file each one names: an error
   in another script (any file other than `LE_BarFeed.cs`) also stops the compile. Send a photo of the error list.
3. **New > Chart**: instrument **MNQ 12-26** (the front month; the bot uses the same one), Type **Minute**,
   Value **5**, **Days to load 30**, Trading hours **CME US Index Futures ETH** (the default for MNQ; RTH-only bars
   would miss the overnight pools and every London trade). Then right-click the chart > **Indicators** >
   **LE_BarFeed** > Add. In its settings leave **Also write 1-minute bars** ticked (the default) > OK.
   This one chart is all you need: the indicator adds a 1-minute series of the same instrument by itself (you do not
   see it on the chart) and writes it to a second file. (It always loads that 1-minute series, even with the box
   unticked; unticked it just does not write the file.)
   To see that it works: Control Center > **New > NinjaScript Output**. After the chart has loaded it shows
   `LE_BarFeed: 8000 bars written to ...MNQ_5m.csv` and `LE_BarFeed: 20000 bars written to ...MNQ_1m.csv`
   (fewer bars at first is fine).
4. Do **not** add LE_BarFeed to a separate 1-minute MNQ chart as well: two writers on `MNQ_1m.csv` would fight. (If you
   ever want a 1-minute chart with LE_BarFeed for something else, untick "Also write 1-minute bars" on the 5-minute
   one.)
5. Check, in File Explorer, the folder `Documents\NinjaTrader 8\le_feed`:
   - `MNQ_5m.csv` gets one new line every 5 minutes;
   - `MNQ_1m.csv` gets one new line every minute (a minute with no trade has no line; that is normal).
   `python -m engine.ninjatrader --status` shows `Bar feed 5m: ... bars, last open ...` and `Bar feed 1m: ...`.
   The bot's log says `FEED STALE: NinjaTrader ... new entries blocked` when one of them is missing or stale.
6. Save the workspace (Control Center > Workspaces > Save) so the chart comes back after a restart.
7. **Quarterly roll** (next: Thursday 2026-12-10): switch the chart to **MNQ 03-27**. The bot switches its order
   instrument by itself on the same date, using the same 8-days-before-expiry rule as `engine/tradovate.py`.
   - Do it **Wednesday 2026-12-09 after 17:00 ET** (before the 18:00 reopen), then save the workspace. If the chart
     stays on MNQ 12-26, the bot reads December prices but sends its orders, stop and target to March, which trades
     about 1% (~300 pts) higher: the stop and target would be in the wrong place.
   - Before that, once: **Tools > Options > Market data > Merge policy = "Merge back adjusted"** (normally the
     default; check it). With "Merge non back adjusted" the chart's own history jumps ~300 pts at the rollover and the bot cannot
     repair it.
   - The bot checks every overlap between the TradingView history, its NinjaTrader archive and the live files: when
     the newer bars sit a roll gap away (100-300 pts) it shifts the older ones onto the new contract and logs
     `... back-adjusted onto NinjaTrader's contract`. MNQ and NQ1! on the same contract need no shift (same prices).
     Tested end to end in `tests/test_roll.py`. After switching, run `python tools/roll_check.py` (it should say OK).
     The full December plan, day by day: `docs/ROLL_DEC_2026.md`.

What LE_BarFeed writes: `time,open,high,low,close,volume`, where time is the bar's **open** in unix seconds (UTC).
That is the bot's bar layout, in both files. It writes the chart's history once when the chart
loads, then one short line per closed bar. It rewrites a file only every 1,000 bars (keeping 8,000 five-minute bars,
about 29 days, and 20,000 one-minute bars, about 14 days), so it is cheap on a small PC. The bot checks each file on
every poll (the 5-minute file for the setups, the 1-minute file for LIT's entry):

| The bot sees | It does |
|---|---|
| file fresh | uses NinjaTrader's bars and adds them to its archive `data\nt_bars\NQ_5m.csv` / `NQ_1m.csv` |
| file shorter than the history gap, or missing more than 10% of the last 3 days' bars | uses what it has: the TradingView export (`data\NQ_5m.csv`, `data\NQ_1m.csv`, ends 2026-10-16) + the archive + the file; NinjaTrader's bars win wherever both have one. A real hole between them is logged (`... bars missing between the stored history and the NinjaTrader feed`): load more days on the chart |
| file missing, or stale during market hours (last bar more than 7 minutes old) | **FEED STALE**: no new entries from that poll on (no Yahoo fallback); an open trade keeps its stop and target at the broker and is still managed. The log says `FEED STALE: NinjaTrader ... new entries blocked`, the health block and the phone say FEED STALE. Fresh bars again: `Feed recovered` |
| bars stamped 17:00-17:59 ET (CME is closed then) or in the future | treats the times as wrong (time zone or close-stamped bars): FEED STALE as above |

ES bars (the partner market, only for the learning loop's ES notes) come only from an MES 5-minute chart with LE_BarFeed;
without one those notes are "unknown" (no trade decision uses them).

**The history the bot needs.** LIT looks back to the first day of the previous month. Today that is the TradingView
export (to 2026-10-16) plus NinjaTrader's 30 days (the chart's "Days to load"), which overlap. From then on the bot's
own archive (`data\nt_bars\`, kept 120 days of 5m and 40 days of 1m, never committed) carries the history forward, so
leave the bot running (or refresh the TradingView export) and keep "Days to load" at 30 or more.

**If it does not compile.** NinjaScript cannot be compiled outside NinjaTrader. It was compiled here (2026-10-18)
against stand-ins for the NinjaTrader parts with the Help Guide's signatures, together with the editor's
"generated code" block and NinjaTrader's standard `using` lines, as C# 5 (the oldest compiler any NinjaTrader 8
has used): no errors, no warnings. A test then ran it through every chart state with 13 days of 5- and 1-minute
bars across both daylight-saving changes and with NinjaTrader set to New York, Chicago, Berlin and UTC time: the files
held exactly the right bars, and the bot's own reader accepted them. Check these lines first:

- `NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo`: NinjaTrader's display time zone **[doc: "Application
  TimeZoneInfo"]**. Only if this line errors, replace it with `TimeZoneInfo.Local`. That is correct only while
  NinjaTrader's time zone (Tools > Options > General) is the same as Windows' time zone.
- `Log(..., LogLevel.Warning)`: if it errors, delete that one line. `Print` alone is enough.
- `NinjaTrader.Core.Globals.UserDataDir`, `Volumes[s][0]`, `Times[s][0]`, `CurrentBars[s]`, `BarsInProgress`,
  `AddDataSeries(BarsPeriodType.Minute, 1)` (in `State.Configure`), `File.Replace`, `IsSuspendedWhileInactive` are
  standard NinjaScript.
- The editor's own "NinjaScript generated code" block must stay as it made it.

## 5. Test on Sim101 (no money involved)

Run these in a PowerShell window in the project folder, with NinjaTrader open and connected.

1. `python -m engine.ninjatrader --status`
   Shows the folder, the connections NinjaTrader reports, positions, open brackets and the bar feed.
2. `python -m engine.ninjatrader --sim-check` (any time NinjaTrader is connected)
   Places a 1-lot MNQ **buy limit 20% below the market** on Sim101, so it can never fill, then cancels it.
   Expect three `OK` lines: file picked up, order report found (it prints NinjaTrader's exact text, for example
   `{'state': 'WORKING', ...}`), and cancel confirmed.
3. `python -m engine.ninjatrader --sim-roundtrip` (market open: Sun 18:00 to Fri 17:00 ET, not 17:00-18:00)
   On Sim101: buys 1 MNQ at market with a stop 40 points below and a target 80 above, moves the stop to 20 below,
   then flattens. Expect three `OK` lines and `FLAT` at the end. You will see the orders appear and disappear on the
   chart. If step 3 says "flat not confirmed", NinjaTrader may want the exchange in the CLOSEPOSITION instrument.
   Flatten by hand, run `python -m engine.ninjatrader --sim-roundtrip --close-suffix " Globex"`, and if that passes,
   add `--close-suffix " Globex"` to every `--start` below.
4. Start the bot on Sim101. The server must be running (`scripts\run_bot.ps1`, or `python server.py`). Then run
   `python -m engine.ninjatrader --start`. That starts adapter `ninjatrader` on account `Sim101` with NinjaTrader's
   bars. The dashboard's Execution menu does not list NinjaTrader yet; use this command. The dashboard's **Stop**
   and **HOLD TO KILL** buttons work for it.
   (The same thing as an API call: POST `/api/live/start` with
   `{"adapter": "ninjatrader", "armed": true, "nt_account": "Sim101", "data_source": "ninjatrader", "present": true}`.)
5. Leave it running until the first real signal (about 3 a week, most of them between 02:00 and 08:00 ET). On the
   chart you should see: the entry (a market order once the 1-minute confirmation prints), a stop 1 tick beyond the
   sweep extreme and the target (the VIX band, or the 8R bank) right after it, the stop moving to the entry once the
   trade is +1R (breakeven), and the exit (stop, target, or the 15:55 ET flat).
   Every price the bot sends is on the 0.25 tick grid: the stop to the nearest tick, the target rounded toward the
   entry (the VIX band is rarely a tick price), so the broker's target sits at or just in front of the model's.
   A Sim101 bot restarts by itself after a crash or reboot, like paper.

## 6. What the bot sends (exact lines)

Example: long 2 MNQ on Sim101, stop 24990.25, target 25080. The ids are made per trade, for example
`LE1792591500K7Q2ME`. **[doc]** One command per line, 13 fields separated by `;`:
`COMMAND;ACCOUNT;INSTRUMENT;ACTION;QTY;ORDER TYPE;LIMIT PRICE;STOP PRICE;TIF;OCO ID;ORDER ID;STRATEGY;STRATEGY ID`.

| When | File content |
|---|---|
| Entry (market) | `PLACE;Sim101;MNQ 12-26;BUY;2;MARKET;0;0;DAY;;<id>E;;` |
| Once NinjaTrader reports the fill: stop and target as one OCO pair | `PLACE;Sim101;MNQ 12-26;SELL;2;STOPMARKET;0;24990.25;DAY;<id>O;<id>S;;`<br>`PLACE;Sim101;MNQ 12-26;SELL;2;LIMIT;25080.00;0;DAY;<id>O;<id>T;;` |
| Breakeven, or any stop move the model makes (0 = leave unchanged) | `CHANGE;;;;0;;0;25020.25;;;<id>S;;` |
| Partial fill completed (resize both legs) | `CHANGE;;;;4;;0;0;;;<id>S;;` and the same for `<id>T` |
| Exit (time stop, giveback, 15:55, news; also a harmless sync after a bracket fill) | `CLOSEPOSITION;Sim101;MNQ 12-26;;;;;;;;;;` then, once NinjaTrader shows flat, `CANCEL;;;;;;;;;;<id>S;;` for any leg still working |
| Kill switch | `FLATTENEVERYTHING;;;;;;;;;;;;` |

Why the stop and target wait for the fill: if the entry failed, a stop or target already sitting at the broker could
open a position by itself. The wait is normally well under a second.

What NinjaTrader writes back **[doc]**: `outgoing\<ORDER ID>.txt` = `STATE;FILLED;AVERAGE PRICE` (for example
`FILLED;2;25020.25`). `outgoing\MNQ 12-26 Globex_Sim101_Position.txt` = `LONG;2;25020.25`. A file named after the
connection = `CONNECTED` or `DISCONNECTED`. The outgoing folder is emptied when NinjaTrader restarts.

## 7. Reading the log

- **Dashboard, Live page log.** These are the lines to look for:
  - `NinjaTrader adapter: account Sim101 (SIM), MNQ 12-26, folder ..., ready` (start)
  - `NinjaTrader ENTRY -> oif_le_...txt: PLACE;...` and `NinjaTrader BRACKET -> ...` (a trade)
  - `NinjaTrader MOVE STOP -> ...: CHANGE;...` (breakeven)
  - `NinjaTrader CLOSE (TIME STOP) -> ...: CLOSEPOSITION;...` (exit)
  - `NinjaTrader: bracket closed the trade: TARGET filled ...`
- **`logs\ninjatrader_oif.log`**: every line ever sent, with the time and the file name.
- **NinjaTrader's Log tab** (Control Center): NinjaTrader's own view, including why an order was rejected.

| Message | Meaning, what to do |
|---|---|
| `did not pick up ... withdrawn, NOT executed` | NinjaTrader is closed, or AT Interface is off (step 3). The file was deleted so it can never run late. |
| `REFUSED: ...` | A safety gate said no (size above 40 micros or 4 minis, before the session start (02:00 ET for LIT, 08:00 for the old engine) or after 15:55 ET, weekend, kill on, a position already open, live lock). Nothing was sent. |
| `fill not reported yet` | The entry went in but no fill report came within 6 s. The stop and target go in at the next poll. After 45 s the entry is cancelled and you get an alert. |
| `... REJECTED ...: flattening at once` | NinjaTrader refused the stop or target. The position was closed. Read NinjaTrader's Log tab for the reason. |
| `FLATTEN NOT CONFIRMED` (also a phone alert) | NinjaTrader still shows a position. The stop stays, and the bot retries every 30 s. Look at NinjaTrader now. |
| `FEED STALE: NinjaTrader ... new entries blocked` | The chart with LE_BarFeed is closed or disconnected. Check NinjaTrader; no trade opens until its bars are fresh. |
| `NinjaTrader outgoing file ... not understood` | NinjaTrader wrote something unexpected. The bot ignores it. Send the line to Claude. |

## 8. Stop and kill

- **Stop** (no new trades): dashboard **Stop**, or `python -m engine.ninjatrader --stop`. An open trade keeps its
  stop and target in NinjaTrader, but the bot no longer moves the stop or makes time exits. Close it yourself.
- **Kill switch**: dashboard **HOLD TO KILL**, or `python -m engine.ninjatrader --kill`. This sends
  `FLATTENEVERYTHING`: NinjaTrader cancels every order and flattens every position **on every account connected in
  NinjaTrader** **[doc]**, not only the bot's account. The bot stops, and the kill flag holds for the rest of the day.
  If the server is down, `--kill` writes the file to NinjaTrader itself. If NinjaTrader is down too, flatten in the
  Tradovate or MFFU app.
- **In NinjaTrader by hand**: Chart Trader **Close**, or the Positions tab > right-click > Flatten. The bot notices a
  position you closed by hand and cancels its leftover stop and target.
- **Flat-time rule**: while the bot runs, between 15:55 and 17:00 ET it closes any MNQ position on its account, also
  one you opened by hand. Positions after 18:00 ET are left alone. A bot trade still open before the session start
  (02:00 ET for LIT) or after 15:55 ET is closed.

## 9. If NinjaTrader or the PC is off

- **No orders at all.** No entries, no breakeven, no time stop, no giveback exit and no 15:55 flat. The bot notices
  and logs it (section 7), and the cloud monitor alerts your phone when the PC bot goes quiet (heartbeat,
  `scripts/PC_OFF_OPTIONS.md`).
- **A trade that is already open** keeps the stop and target already at the broker. If NinjaTrader is closed when
  one of them fills, check in the Tradovate app that the other one was cancelled **[UNVERIFIED whether the OCO link
  holds without NinjaTrader]**. Nobody flattens it at 15:55 ET.
- **For a truly PC-off setup**:
  - TradingView with a webhook bridge (`tradingview/BRIDGE_SETUP.md`; about $50 a month).
  - A spare PC that stays on, such as the Surface (section 10).
  - A Windows VPS running NinjaTrader 24/5 (about $15-25 a month; paid, so only with your OK).

## 10. Low-end PC (the Surface as the always-on box)

- **One chart only**: MNQ 5-minute with LE_BarFeed (it writes the 1-minute file too). No second chart.
- **Nothing else open**: no Market Analyzer, no SuperDOM, no extra charts or workspaces, no browser left running.
- **Connect on startup** ticked for the Tradovate/MFFU connection (step 2). Save the workspace (step 4) so the chart
  comes back after a reboot.
- **Decline NinjaTrader update prompts during sessions.** Update on a weekend.
- **The daily reconnect is normal.** CME closes 17:00-18:00 ET. NinjaTrader may disconnect and reconnect then. The
  bot does not trade then.
- LE_BarFeed is built to be light: one short appended line per bar, and a rewrite only every 1,000 bars.
- Setup for the box: `scripts/PC_OFF_OPTIONS.md` (option E) and `scripts/setup_dedicated_pc.ps1`. The script sets
  never-sleep, installs the bot's logon task, adds a NinjaTrader Startup shortcut, and lists what to do by hand.
- Keep the Windows clock synced (Settings > Time & language > Sync now). The bot's 15:55 flat uses it.

## 11. Going live on the MFFU account (only after MFFU's written OK)

All three locks are needed at once, or every order is refused:

1. The server runs with `NINJATRADER_LIVE=1`. Add `$env:NINJATRADER_LIVE = '1'` to `.env.local.ps1` (gitignored),
   then stop everything with `scripts\stop_bot.ps1` and start `scripts\run_bot.ps1` again (it reads the file only when
   it starts; `stop_bot.ps1 -RestartServer` keeps the old environment). Run both as
   `powershell -ExecutionPolicy Bypass -File scripts\<name>.ps1`.
2. The start says armed.
3. The start carries the phrase `I ACCEPT LIVE RISK`.

Command:
`python -m engine.ninjatrader --start --account <the MFFU account Name> --confirm "I ACCEPT LIVE RISK"`

A real-account bot never restarts by itself after a crash or reboot; you start it by hand. Stay present, as MFFU
requires. LIT trades from 02:00 ET (most trades 02:00-08:00), so "present" means awake then.

Before the first live start, check:
- The account Name is exactly as in NinjaTrader's Accounts tab. Any name that is not `Sim...` / `Playback...` counts
  as live.
- Only the eval account is connected. The kill switch (`FLATTENEVERYTHING`) flattens **every** connected account.
- The plan's maximum position size. The bot can send up to 40 micros. If MFFU allows fewer on your plan, the bot has to
  be capped below that (ask Claude) before you arm it.
- `lit_sizing.eval_start` in `live_model.json` (or `eval_start` in the start config) is the first session of *this*
  eval. The two_week size counts the eval's profit from the bot's own trades since that day, not from the broker's
  statement.
- Windows Update is paused (Settings > Windows Update > Pause), and `scripts\setup_dedicated_pc.ps1` was run again as
  Administrator after 2026-10-18, so restarts can only land 17:00-01:00 ET.
- Steps 5.2 and 5.3 passed on Sim101 on this PC, and the first Sim101 trade showed the stop and target as one OCO pair
  (section 13 item 6).
- Both legs are sent `DAY`. If the PC dies with a trade open, the stop and target stay at the broker until they fill or the
  17:00 ET close, but nobody flattens at 15:55 ET. Then flatten in the MFFU / Tradovate app yourself. Size caps stay on: 40 micros or 4 minis at most. To go back to testing, start again with
`--account Sim101`, and remove the line from `.env.local.ps1`.

## 12. Settings (start-config keys; defaults in brackets)

| Key | Meaning |
|---|---|
| `nt_account` [`Sim101`] | Account Name in NinjaTrader (or env `NINJATRADER_ACCOUNT`). `Sim101`, `SimNNN` and `PlaybackNNN` count as simulation; any other name is live. |
| `nt_folder` [Documents\NinjaTrader 8] | NinjaTrader's user folder (or env `NINJATRADER_FOLDER`); found automatically, OneDrive Documents included |
| `nt_instrument` [front month, for example `MNQ 12-26`] | Force the instrument name |
| `nt_contract` [`micro`] | `micro` = MNQ only. `auto` = 10 or more micros go as NQ minis, as the backtest's commission model does (two brackets). |
| `nt_close_suffix` [empty] | Text added to the instrument in CLOSEPOSITION, for example `" Globex"` (step 5.3; `--close-suffix`) |
| `nt_write_mode` [`direct`] | `direct` writes each file in one go; `move` writes it next door, then moves it into incoming (the guide allows both; `--write-mode`) |
| `nt_ack_wait_s` [4] / `nt_fill_wait_s` [6] / `nt_verify_wait_s` [4] / `nt_pending_timeout_s` [45] | How long to wait for NinjaTrader at each step |
| `data_source` (or `data`) [`ninjatrader` while `no_yahoo` is on] | `ninjatrader` reads LE_BarFeed's files (5m and 1m). `yahoo` is turned into `ninjatrader` while `no_yahoo` is on |
| `no_yahoo` [`live_model.json` `no_yahoo`: true] | true: no Yahoo anywhere (FEED STALE blocks entries instead of a fallback). false: the old behaviour (Yahoo NQ=F as the feed or the fallback) |
| `nt_session_from` [LIT: 120 = 02:00 ET; engine: 480 = 08:00 ET] | First ET minute (after midnight) an entry is accepted; a bot trade still open before it is closed |
| `lit_sizing` [from `live_model.json`: `{"mode": "two_week", "eval_start": "2026-10-19"}`] | LIT size switch: `two_week` (on since 2026-10-18: micros so the target covers what is left to +$3,000, at most 60% of the room to the max-loss floor and the $1,000 soft daily loss, max 40, min 1; it counts sessions from `eval_start`), `eval`, `normal`, `fast_eval` or `safe_eval`. Without a known eval state it falls back to `eval`. |
| `eval_start` [`live_model.json` `lit_sizing.eval_start`] | First session (yyyy-mm-dd, the trading day; Sunday evening counts as Monday) of the eval this account is on. Set it again after every eval reset, or the size is worked out from the wrong balance. |
| `accounts` [none: one account] | Extra accounts that trade the same LIT signals, each with its own size, eval clock and daily-loss lock-out (section 12b). |

## 12b. Several accounts on one bot (off until you add one)

The bot's own account (`--account`) trades exactly as before. Every account you add trades the same entry, stop and
target with its own orders and its own micros (worked out from its own balance, floor and eval session). One account
locked out (daily loss, max-loss floor reached) never stops the others; the kill switch flattens all of them.

1. Add the account once (it goes into `data/accounts.json`, which stays on the PC):
   `python -m engine.multi_account --add --id lucid50k --nt-account "<Name in the Accounts tab>" --preset lucid_pro_50k --eval-start 2026-10-21`
   Presets: `python -m engine.multi_account --presets` (mffu_builder_50k, lucid_pro_50k, fn_rapid_daily_50k,
   mffu_rapid_50k, mffu_rapid_eod_50k, paper_50k). Check: `python -m engine.multi_account --list`.
2. Test on a Sim account first: `--nt-account Sim102`, then the usual `python -m engine.ninjatrader --start`. The log
   shows `[lucid50k] SIM Sim102 ... ready`; the Accounts page shows a row per extra account.
3. A real account trades only with all three locks for that account: `python -m engine.multi_account --set --id lucid50k --armed yes`,
   the live phrase typed at `--start` (it is given to every account marked armed, in memory only), and `NINJATRADER_LIVE=1`.
4. After the pass: `python -m engine.multi_account --set --id lucid50k --mode funded --funded-start <first funded day>`;
   record each payout with `--payout 2026-12-01=1000` (the room to the floor is worked out after it).
5. Auto-resume after a restart: each extra real account needs its own opt-in,
   `python -m engine.ninjatrader --enable-auto-resume --extra --account "<Name>" --confirm "<the live phrase>"`;
   one without it is left out of the resume (you get a push saying so) while the others come back.
6. Off again: `python -m engine.multi_account --disable --id lucid50k` (or `--remove`), then Stop and `--start`.

### Add the 25K (MFFU Builder 25K eval next to the 50K)

How the copy works: the bot writes one NinjaTrader order file per account (`PLACE;<account>;MNQ ...`), each with its own
micros, stop and target, and reads each account's own fills and positions back. Nothing is copied inside NinjaTrader
(no trade copier). The extra accounts' orders are sent at the same moment as the 50K's (one thread each), so they
reach NinjaTrader within milliseconds of each other; each account then waits for its own fill report (up to ~6 s).

1. In NinjaTrader, Control Center > Accounts: wait until the new 25K account shows (its Name, e.g. `MFFUEVAL25xxxx`).
2. Add it (first session = the trading day of its first trade, e.g. 2026-10-21):
   `python -m engine.multi_account --add --id mffu25k --name "MFFU 25K Eval" --nt-account "<the 25K Name>" --preset mffu_builder_25k --eval-start 2026-10-21`
   (or copy `ninjatrader/accounts.example.json` to `data/accounts.json` and put the Name in `nt_account`).
   Its rules ($1,500 target, $1,000 trailing max loss locking at $25,100, $600 soft daily loss, 20 micros) are the
   preset's; change any of them in the file's `"rules"` if MFFU says otherwise. If the 25K already has P&L, add `--prior-pnl -50`.
   Sizing (research/writeups/lit-builder-25k.md): "one winner passes" on the 25K's own +$1,500, at most 50% of its room
   and its $600 daily loss, max 20 micros (about half the 50K's micros on the same signal); safe_eval at 30% of the room
   after session 10. When its room falls under $100 it stops trading and your phone gets "25K stuck: room $X, buy a new one".
   Tip from the research: starting the 25K a week after the 50K makes the two evals far less likely to die together.
   The bot never holds a long on one account and a short on another (MFFU's hedging rule).
3. Real account, so it needs its own locks: `python -m engine.multi_account --set --id mffu25k --armed yes`, then Stop and
   `python -m engine.ninjatrader --start --account "<the 50K Name>" --confirm "<the live phrase>"` (with NINJATRADER_LIVE=1).
   The log shows `[MFFU 25K Eval] LIVE ... ready`; if it says DISABLED it names the missing lock.
4. Auto-resume for it too: `python -m engine.ninjatrader --enable-auto-resume --extra --account "<the 25K Name>" --confirm "<the live phrase>"`.

## 13. Assumptions to verify on a real install

1. The order-file format matches the official pages (it was checked against copies). Steps 5.2 and 5.3 prove it.
2. NinjaTrader picks up files the bot writes straight into `incoming`. A field report says a temp file *inside*
   `incoming` is rejected as "Unknown OIF file type"; the bot never does that. If 5.2 says "did not pick up" while
   NinjaTrader runs with AT Interface on, try `nt_write_mode` `move`.
3. The order report is `outgoing\<ORDER ID>.txt`, with states spelled like `FILLED`, `PARTFILLED`, `WORKING`,
   `ACCEPTED`, `CANCELLED`, `REJECTED`. The bot ignores case and spaces. Step 5.2 prints the real text.
4. The position file is `<instrument> <exchange>_<account>_Position.txt`. `--status` lists it after a fill.
5. CLOSEPOSITION accepts `MNQ 12-26` without the exchange. Step 5.3 checks it; otherwise use `nt_close_suffix`.
6. OCO on the Tradovate connection: when the target fills, NinjaTrader cancels the stop. The first Sim101 trade shows
   it. The bot cancels a leftover leg either way.
7. A market fill is reported within 6 s, and order confirmation does not hold ATI orders back.
8. LE_BarFeed compiles (section 4); its bar times are bar opens. The bot rejects shifted times. The added 1-minute
   series loads as many days as the chart (30); `MNQ_1m.csv` keeps the last 20,000 one-minute bars.
9. Orders are processed while NinjaTrader is minimized and the screen is locked or off.
10. The account Name string, the Tradovate environment, and whether a NinjaTrader license is needed (ask MFFU).
11. NinjaTrader's own rollover date for MNQ matches the bot's (8 days before the 3rd-Friday expiry).
12. MFFU's written OK for automated trading (step 2).

## Sources

NinjaTrader 8 Help Guide, Automated Trading Interface (ATI):
- File Interface: https://ninjatrader.com/support/helpGuides/nt8/file_interface.htm
- Order Instruction Files (OIF): https://ninjatrader.com/support/helpGuides/nt8/order_instruction_files_oif.htm
- Commands and Valid Parameters: https://ninjatrader.com/support/helpGuides/nt8/commands_and_valid_parameters.htm
- Information Update Files (outgoing folder): https://ninjatrader.com/support/helpGuides/nt8/information_update_files.htm
- Options > Automated trading interface (AT Interface switch): https://ninjatrader.com/support/helpGuides/nt8/options_ati.htm
- Order State Definitions: https://ninjatrader.com/support/helpGuides/nt8/order_state_definitions.htm
- ATI overview: https://ninjatrader.com/support/helpGuides/nt8/automated_trading_interface_at.htm
- Application TimeZoneInfo (NinjaScript, used by LE_BarFeed): https://ninjatrader.com/support/helpGuides/nt8/application_timezoneinfo.htm

The text was checked against verbatim copies of those pages: github.com/HalfTick/ninjatrader-docs
(`docs/strategies/order_instruction_files_oif.md`, `docs/operations/commands_and_valid_parameters.md`) and
github.com/Naina-Tech-Inc/nt8sdk (`docs/ATI_DOCUMENTATION.md`). The direct-write field report comes from a public
NT8 ATI client (github.com/lhzwb2008/ftmo-test, `ninjatrader_client.py`).

Code: `engine/ninjatrader.py` holds the adapter, the bar-feed reader, the command line and the self-test
(`python -m engine.ninjatrader --selftest`, offline, simulated NinjaTrader folders). The bot loop is
`engine/live.py`. The indicator is `ninjatrader/LE_BarFeed.cs`.
