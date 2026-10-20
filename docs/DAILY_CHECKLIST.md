# Daily checklist (MFFU 50K eval, LIT bot)

One page for every day. The long first-time steps are in `docs/GO_LIVE_TONIGHT.md`. Something red?
`docs/TROUBLESHOOTING.md`.

**Last visit to the Surface:** `docs/ONE_TIME_SETUP.md` (one line to paste, then `ONE_TIME_SETUP.bat` does the rest:
no sleep, no update restarts, starts at logon, auto-update, the phone says "Surface offline" if it goes quiet).

**Your desktop icons** (made once by double-clicking `SETUP_SHORTCUTS.bat` in the bot folder):

| Icon | What it does |
|---|---|
| **LE DASHBOARD** | opens the dashboard; starts the bot server first if it is off |
| **LE HEALTH CHECK** | one screen: green = fine, yellow = look at it, red = fix it (the fix is on the next line) |
| **LE UPDATE** | gets the new version: stop, update, restart, self-test. Refuses during a trade |
| **LE STOP BOT** | stops the bot and the dashboard (asks first) |

**On your phone, by itself** (Liquidity app, notifications on):

| When (ET) | Notice |
|---|---|
| 01:40 | **All green for tonight**, or **Fix before 02:00 ET: ...** with the one fix |
| every trade | entry, then the result |
| 16:05 | **Day summary**: trades, P&L, $ to go, session X of 10 |
| Sunday evening | **Week** report: trades, P&L, eval, PC health |
| when it happens | internet back after a drop, NinjaTrader disconnected / reconnected, **Surface offline since HH:MM ET** (once per outage, 01:30-16:00 ET) and **Surface back online** |
| day 5 without a trade | MFFU inactivity: place 1 MNQ by hand (MFFU closes the account at 7 days) |
| eval passed / failed | what to do next |
| a week + a day before a roll | switch the NinjaTrader chart to the new contract (steps in the notice) |

---

## Night before (before 01:45 ET)
- [ ] Surface **plugged in**, lid open or set to "do nothing", Wi-Fi on.
- [ ] **NinjaTrader 8** open, connection green, the MNQ chart with **LE_BarFeed** open (30 days loaded).
- [ ] Double-click **LE HEALTH CHECK**: no red lines.
- [ ] Dashboard shows the bot **running** on your **eval** account (not Sim101), unless you want Sim tonight.
- [ ] At 01:40 the phone says **All green for tonight**. If it says **Fix ...**, do that one thing.

## Morning (any time)
- [ ] Glance at the phone: entries / results overnight. Nothing to do unless a notice says so.
- [ ] Red notice? Open **LE HEALTH CHECK** on the Surface (or `docs/TROUBLESHOOTING.md`).
- [ ] Never move or cancel the bot's orders in NinjaTrader by hand.

## After the close (after 16:00 ET)
- [ ] **Day summary** arrived (16:05): trades, P&L, eval $ to go, session X of 10.
- [ ] Updates: only now. Double-click **LE UPDATE** if Claude told you there is a new version.
- [ ] Leave the PC, NinjaTrader and the bot on. The backup runs by itself after 16:35 (`backups\`, 14 days kept).

## Weekly (Sunday evening)
- [ ] Read the **Week** report on the phone.
- [ ] Windows Update: **Pause updates** (up to 5 weeks) if HEALTH CHECK shows it yellow; install them on a weekend, then
      restart the PC and run **LE HEALTH CHECK**.
- [ ] NinjaTrader: restart it once (it frees memory), reconnect, check the LE_BarFeed chart, then **LE HEALTH CHECK**.
- [ ] Before Sunday 18:00 ET the bot should be running again for Monday.

## Switch on scale-in (once, when you have 15 minutes with the market open)
Scale-in (one add after breakeven, `STRATEGY.md` rule 11) is built but **OFF** until this check passes on a real
NinjaTrader. The 15-minute check and breakeven + costs are already on.
1. **First, recompile LE_BarFeed** (it now also writes `le_feed\MNQ_instrument.txt`, the roll guard that refuses an entry
   when the chart and the order contract differ): NinjaTrader → New → NinjaScript Editor → open `LE_BarFeed` → press
   **F5**. No red errors at the bottom. Then remove and re-add LE_BarFeed on the MNQ chart (30 days loaded).
2. Bot **stopped**, NinjaTrader on **Sim101**, market **open** (not 17:00-18:00 ET, not the weekend).
3. In a command window in the bot folder: `python -m engine.ninjatrader --sim-roundtrip-add`
4. It buys 1 MNQ with a stop and a target, moves the stop up, refuses one bad add, then **adds 1 MNQ** and stops at
   "Press Enter to flatten". **Before you press Enter**, open NinjaTrader's **Orders** tab:
   - the stop shows **quantity 2** (Sell 2, Stop Market) at the price the window printed,
   - the target shows **quantity 2** (Sell 2, Limit) at the price the window printed,
   - prices **unchanged**, quantity **not 0**, no third order, the position (Positions tab) **Long 2**.
   Take a phone photo of the Orders tab.
5. Press Enter: it flattens. Every line (1 to 5) must start with OK, no FAIL; Sim101 flat, no orders left.
6. All OK: **tell Claude** ("scale-in Sim check passed", with the photo), or set it yourself in **both**
   `live_model.json` and `live_model_lit.json`, under `"lit"`:
   `"scale_in": {"pb": 0.25, "f": 1.0, "rat_k": 1.0, "min_rk": 2.0, "n": 1}` — then restart the bot (LE UPDATE).
   Any FAIL, quantity 0 or a wrong price: leave it off and send Claude the window text and the photo.

## Rules that never change
- The bot never arms a real account by itself. You start the eval bot yourself (dashboard, your phrase).
- **No trade for 5 days**: place 1 MNQ by hand (in and out) or let the min-days trade run (MFFU's 7-day rule).
- **Eval passed**: the bot stops on that account. Tell Claude before trading the funded account (sizing changes).
- **Eval failed**: buy a new MFFU Builder 50K with your discount code (you paid $91.80; look for a current code), tell
  Claude the new account name and its first day.
