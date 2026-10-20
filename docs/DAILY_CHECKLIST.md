# Daily checklist (MFFU 50K eval, LIT bot)

One page for every day. The long first-time steps are in `docs/GO_LIVE_TONIGHT.md`. Something red?
`docs/TROUBLESHOOTING.md`.

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
| when it happens | internet back after a drop, NinjaTrader disconnected / reconnected, PC silent |
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

## Rules that never change
- The bot never arms a real account by itself. You start the eval bot yourself (dashboard, your phrase).
- **No trade for 5 days**: place 1 MNQ by hand (in and out) or let the min-days trade run (MFFU's 7-day rule).
- **Eval passed**: the bot stops on that account. Tell Claude before trading the funded account (sizing changes).
- **Eval failed**: buy a new MFFU Builder 50K with your discount code (you paid $91.80; look for a current code), tell
  Claude the new account name and its first day.
