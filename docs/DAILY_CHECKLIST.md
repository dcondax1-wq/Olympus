# Daily checklist (MFFU 50K eval, LIT bot)

One page for every day. The long first-time steps are in `docs/GO_LIVE_TONIGHT.md`. Something red?
`docs/TROUBLESHOOTING.md`.

**Last visit to the Surface:** `docs/ONE_TIME_SETUP.md` (one line to paste, then `ONE_TIME_SETUP.bat` does the rest:
no sleep, no update restarts, starts at logon, auto-update, the phone says "Surface offline" if it goes quiet).

**Your desktop icons** (made once by double-clicking `SETUP_SHORTCUTS.bat` in the bot folder):

| Icon | What it does |
|---|---|
| **LE START** | opens the dashboard's Start page (starts the bot server first if it is off). Press **Start trading**: it updates, waits for NinjaTrader and the live bars, runs the Sim test once and starts both accounts. It also opens by itself when the PC starts |
| **LE STOP BOT** | stops the bot and the dashboard (asks first) |

The older icons (LE START BOT, LE UPDATE, LE DASHBOARD, LE HEALTH CHECK) are gone: the Start page does their work.
`HEALTH_CHECK.bat` and `UPDATE.bat` are still in the bot folder.

**On your phone, by itself** (Liquidity app, notifications on):

| When (ET) | Notice |
|---|---|
| 01:40 | **All green for tonight**, or **Fix before 02:00 ET: ...** with the one fix |
| every trade | entry, then the result |
| 16:05 | **Day summary**: trades, P&L, $ to go, session X of 10 |
| Sunday evening | **Week** report: trades, P&L, eval, PC health |
| when it happens | internet back after a drop, NinjaTrader disconnected / reconnected, **Surface offline since HH:MM ET** (once per outage, 01:30-16:00 ET) and **Surface back online** |
| day 5 without a trade | MFFU inactivity: place 1 MNQ by hand (MFFU can close the account after 7 days). Only when the bot is down: while it runs, the keep-alive's own notices below are the ONE warning a day per account |
| the last safe day | **Keep-alive today on ...** (switch ON: the bot buys 1 MNQ at 15:33 ET, out about 2 minutes later, about -$2.40; then **Keep-alive on ...: BUY 1 MNQ** and **... closed LONG about -$2.40**) or **TODAY is the last safe day** (switch OFF: place it by hand), and the session before: **the next session is the last safe day** |
| eval passed / failed | what to do next |
| a week + a day before a roll | switch the NinjaTrader chart to the new contract (steps in the notice) |

## Holiday plan (Nov 2026 - Jan 2027)
MFFU does **not** flatten you at a CME early close: a position still open at the halt = the account **fails**. The bot
(every account: Zlarior, ATLAS, the Rapid, extra accounts, BLITZ) stops new entries 15 min before the halt and is flat
5 min before it. Times ET (CT = ET - 1 h).

| Day | CME (equity futures) | Bot: last entry / flat |
|---|---|---|
| Thu Nov 26 Thanksgiving | halts 13:00 (12:00 CT), reopens 18:00 | 12:44 / 12:55 |
| Fri Nov 27 | early close 13:15 (12:15 CT) | 12:59 / 13:10 |
| Thu Dec 24 Christmas Eve | early close 13:15 (12:15 CT), reopens Sun 18:00 | 12:59 / 13:10 |
| Fri Dec 25 Christmas | closed | no trading |
| Thu Dec 31 | normal day | normal / 15:55 |
| Fri Jan 1 New Year's Day | closed | no trading |
| Mon Jan 18 MLK | halts 13:00 | 12:44 / 12:55 |

- [ ] Don't trade by hand after the bot's last entry time on these days. Never hold anything at 13:00 / 13:15.
- [ ] About a week before (Nov 19, Dec 17): check MFFU's holiday email/notice. If it shows an EARLIER close than this table,
      tell Claude the same day.
- [ ] 7-day rule: on holiday weeks the phone warns early when only 1 session is left (e.g. no trade since Mon Dec 21 means
      warned Thu Dec 24 morning; Fri is closed). Then place 1 MNQ by hand before 12:59.
- Check it yourself: `python -m engine.cme_calendar 2026-11-20`. Proof: `python -X utf8 -m tests.test_holiday_replay`.

---

## Night before (before 01:45 ET)
- [ ] Surface **plugged in**, lid open or set to "do nothing", Wi-Fi on.
- [ ] **NinjaTrader 8** open, connection green, the MNQ chart with **LE_BarFeed** open (30 days loaded).
- [ ] Open **LE START**: no red lines on the Start page.
- [ ] Dashboard shows the bot **running** on your **eval** account (not Sim101), unless you want Sim tonight.
- [ ] At 01:40 the phone says **All green for tonight**. If it says **Fix ...**, do that one thing.
- [ ] At the desk: tap **I'm here** (Bot page, or phone Remote page) so the presence log shows you watching (MFFU); **Pause until tomorrow** / **Resume entries** sit on the same pages, and the weekly **Hands-off score** shows each time you stepped in.

## Morning (any time)
- [ ] Glance at the phone: entries / results overnight. Nothing to do unless a notice says so.
- [ ] Red notice? Open **LE START** on the Surface (or `HEALTH_CHECK.bat` in the bot folder) (or `docs/TROUBLESHOOTING.md`).
- [ ] Never move or cancel the bot's orders in NinjaTrader by hand.

## After the close (after 16:00 ET)
- [ ] **Day summary** arrived (16:05): trades, P&L, eval $ to go, session X of 10.
- [ ] Updates: only now. Double-click **LE UPDATE** if Claude told you there is a new version.
- [ ] Leave the PC, NinjaTrader and the bot on. The backup runs by itself after 16:35 (`backups\`, 14 days kept).

## Weekly (Sunday evening)
- [ ] Read the **Week** report on the phone.
- [ ] Windows Update: **Pause updates** (up to 5 weeks) if HEALTH CHECK shows it yellow; install them on a weekend, then
      restart the PC and open **LE START**.
- [ ] NinjaTrader: restart it once (it frees memory), reconnect, check the LE_BarFeed chart, then **LE START**.
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

## Pass day / fail day (the bot handles it, `engine/eval_life.py`)
- **Pass** (eval balance $53,000 = +$3,000): the bot stops trading that eval by itself. If MFFU still needs a 2nd traded
  day, it takes one 1-micro trade the next session, then nothing. Your phone gets **"EVAL PASSED 🎉 next steps"**:
  1. Check MFFU shows the eval PASSED. 2. Sign the funded agreement. 3. When the funded account appears in NinjaTrader
     the phone says **New MFFU account: <Name>** and the Start page shows **Use as Zlarior's funded account**: stop the
     bot, tap it (nothing is armed; Start trading asks for the phrase). 4. Or by hand, one command adds it with funded
     sizing (40% of the room, max $800, a winner <= $1,500):
     `python -X utf8 -m engine.eval_life --to-funded --account "<Name>" --start <first funded day>`, then restart the bot.
     It is disarmed: a real account trades only after you arm it yourself (as for the eval).
  5. Payouts: ask only once the balance is **$53,600+** ($1,500 above the $2,100 buffer), up to $2,000 a request. Record
     each one: `python -X utf8 -m engine.eval_life --payout 2026-12-01=2000`. Check: `--funded-status`.
- **Fail** (the max-loss floor reached): the bot stops trading that eval. The phone says **"EVAL FAILED"**: stop the bot
  on it, buy a new Builder 50K at your price ($91.80 with a code last time; verify the code at checkout), tell Claude the
  new account and its first session. A 2nd eval starts 5 sessions after the first, never the same day.

## Optional: the eval weekly loss stop (OFF)
Research (`research/writeups/lit-risk-money.md`): once the eval is down $1,200 in a calendar week, no new trade until
Monday. 2-week fails 9.2 -> 5.0% (Jan-Jun) with the same passes, money-neutral. Switch it on with one line in **both**
`live_model.json` and `live_model_lit.json`, under `"lit_sizing"`: `"wk_loss_usd": 1200` (remove it to switch off), then
restart the bot. The PC Today page and the phone's Eval HQ show it: weekly loss stop off / armed / tripped; the phone gets
one push when it trips.

## Optional: second strategies on this account (OFF)
The bot can also trade the EMA London pullback (`ema_lon_vix`), the MACD sweep (`macd_sweep`) or the S/R NY reclaim
(`sr_nyreclaim`) on the same NinjaTrader account as LIT. Built and tested on Sim, **OFF**. Research
(`research/writeups/second-route.md`): on the eval it adds little (H2 +$11.2k vs LIT alone +$9.1k) and more H1 fails
(10.9% vs 5.9% in 2 weeks), so leave it off on the eval.
1. Switch one on (it checks NinjaTrader's self-test first and refuses if it fails):
   `python -m engine.second --route ema_lon_vix on`
2. The bot picks it up on its next poll. LIT always comes first: one position at a time, no second-strategy entry while
   LIT is in a trade or has a setup armed, a second trade is closed at market when LIT enters, max 2 trades a day.
   Pushes for it say the account name like LIT's, with "(EMA)" in the text; the paper ones keep "PAPER".
3. Switch it off the same way: `python -m engine.second --route ema_lon_vix off`

## Optional: Account B, the second strategies on their own account (OFF)

EMA + MACD + S/R on a second MFFU account (a Builder 25K, $63, is the pick: `research/writeups/second-account-b.md`).
LIT stays alone on its 50K. Try it on a Sim account first.
1. In NinjaTrader, note the account Name (a Sim account first, e.g. Sim102), then:
   `python -m engine.second --account-b "Sim102" --plan builder25k --start 2026-10-26`
2. The bot picks it up on its next poll: own orders, own eval card ("Account B Sim102"), max 2 trades a day, never
   opposite to LIT (B is closed first when LIT enters the other way).
3. Off: `python -m engine.second --account-b off`
4. **ATLAS's eval passed** (push "EVAL PASSED"): the bot stops it. Request the funded account at MFFU, note its NEW
   Name, stop the bot, then Start page > Accounts > ATLAS's 25K > **Passed → funded** (or
   `python -X utf8 -m engine.account_b --to-funded --account "<funded Name>" --start <first day>`). It is not armed:
   type the phrase at the next start. Payouts: request at MFFU when the push says PAYOUT READY, then
   `python -X utf8 -m engine.account_b --payout <day>=<$>` (`research/writeups/atlas-funded.md`).

## Rules that never change
- The bot never arms a real account by itself. You start the eval bot yourself (dashboard, your phrase).
- **No trade for 5 days** (MFFU's 7-day rule: one FILLED trade in every 7 calendar days, or MFFU can close the account and a
  funded one loses its profits): place 1 MNQ by hand (in and out, before 15:50 ET). Nothing to type after it: the bot reads
  the fill from NinjaTrader's own Log within a few minutes (an "Execution" line for that account) and its warnings stop.
  Only if a warning still comes the next day, at the PC: `python -X utf8 -m engine.keepalive --traded <account>` (lit, atlas,
  x:b25k_2, rapid; add the date `yyyy-mm-dd` if it was not today: never a future day, at most 7 days back, an unknown
  account name is refused; it prints the new deadline). Or let the bot do it: the keep-alive
  trade (`engine/keepalive.py`, lands OFF; you said yes 2026-11-20: double-click `KEEPALIVE_ON.bat` and type KEEP ALIVE ON
  to switch it on for every MFFU account, `KEEPALIVE_OFF.bat` to switch it off).
- **On a keep-alive day (switch ON), do not trade that account by hand between 15:33 and 15:50 ET**: the bot's close is a
  CLOSEPOSITION of the whole account, so it would close your trade too.
- **Eval passed**: the bot stops on that account. Tell Claude before trading the funded account (sizing changes).
- **Eval failed**: buy a new MFFU Builder 50K with your discount code (you paid $91.80; look for a current code), tell
  Claude the new account name and its first day.
