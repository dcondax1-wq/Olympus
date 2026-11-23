# Owner manual: everything in one place (2026-11-20)

Owner (2026-11-19): "It's getting confusing ... I need to know exactly what's happening, how much, or what I need to do."
Phone copy: **hub/manual.html** (works offline once opened; same facts as this file; tests.test_owner_manual keeps them equal).
Numbers below are from the PC's report on Nov 20, 6:00 ET. Live numbers: the ZEUS page (hub/zeus.html) or the Board.

## 1. Who is who

### Accounts (all MFFU)

| Account | Plan | Stage | Who trades it | Money now (Nov 20) |
|---|---|---|---|---|
| Zlarior 50K | Builder 50K ($91.80) | Eval | Zlarior | $49,193. Needs +$3,807 to pass. $1,025 room |
| ATLAS 25K | Builder 25K ($63) | **Funded** | ATLAS | $24,887. First $1,000 payout at about $27,100 ($2,100 profit as MFFU shows it; a push tells you, N5). $887 room |
| Zlarior 25K #2 | Builder 25K ($63) | Eval | Zlarior | $25,000. Needs +$1,500 to pass. $1,000 room |
| Rapid EOD 25K | Rapid EOD 25K ($97.20) | Bought, not added yet | Zlarior + ATLAS (when added) | Not on the PC yet: add it (card 9 below) |

### Bots

| Bot | What it does (one sentence) | When it can enter (New York time) | Real money? |
|---|---|---|---|
| **Zlarior** (strategy **LIT**) | Waits for price to run past an old high or low, snap back, then trades the reversal with a stop 1 tick past the extreme and one target. | 02:00-15:30 ET, most trades 02:00-08:00. At most 1 trade a day, about 2-4 a week | Yes: the 50K and 25K #2 evals |
| **ATLAS** (3 small strategies) | London EMA pullback, MACD at a sweep, New York level reclaim; each takes small, quick trades. | MACD 02:00-05:00 + 09:30-11:00; EMA 03:00-09:30 (not Mondays); level reclaim 09:30-12:00 | Yes: the funded 25K |
| **BLITZ** | A test strategy that only runs on paper. Hidden on the pages on purpose. | - | **No, never** |
| **K8** (Kalshi clock bot) | Small bets on gold and silver 15-minute price markets on Kalshi. | 05:15-05:30 ET (gold down) and 16:45-17:00 ET (gold + silver up), weekdays | **No, paper** until you type the Kalshi phrase. With $55: $2.50 a bet, at most 3 a day, worst week -$13.75 |
| **ZEUS** | The name for the whole PC bot (it runs Zlarior + ATLAS through NinjaTrader). | - | - |

## What READY means (PC self-check, 2026-11-22)

1. The PC checks itself 3 times a day, plus when the bot starts and the moment something breaks: **17:30 ET** (before the 18:00 open), **01:15** (45 min before the 02:00 window) and **08:45**.
2. **READY** (mint) means the bot can trade the next window: PC clock within 5 s, NinjaTrader connected, price bars fresh, every account armed, no account halted, disk and updates fine.
3. **NOT READY** (gold) means something would stop a trade. Your phone gets ONE alert (Telegram / Discord first) like "NOT READY for 02:00: PC clock 25 s behind", with the exact fix.
4. The same alert repeats at most once an hour, and the same problem never twice within 30 minutes. Fix it and the next check says READY.
5. **READY, 1 to watch** (mint) is a small thing (restart pending, disk getting low, 7-day deadline): it will not stop a trade tonight.
6. At 17:30 you get one quiet "READY for the next window" line. No news is not a promise: look at the phone pages (Trading Home first line, Brain > All bots banner).
7. Most fixes need you at the PC (arming needs your phrase, the clock sync, NinjaTrader's connection). The alert says which.
8. The check only reads. It never starts, stops, arms or changes anything.
9. On the PC: `python -X utf8 -m engine.readiness` prints it now; HEALTH_CHECK.bat shows the longer list.
10. Claude can read the same verdict from the cloud: `python tools/ready_check.py`.

## 2. A normal day (ET)

| Time | The PC does by itself | You see on the phone |
|---|---|---|
| Every 15 min, all day | Sends a status report | "PC reported X min ago" on ZEUS / Board. Over 30 min = red **PC SILENT** |
| 01:50 | Trading hours start: no updates until 16:00 | - |
| 02:00-15:30 | Zlarior and ATLAS look for entries | A push at each **entry** ("Zlarior 50K: LONG 4 MNQ @ ... risk $178, target +$450") and each **exit** ("closed +$312 (target) ... $3,495 to pass") |
| 07:30 | Morning brief | One push: each account's $, overnight trades, today's news, what needs you |
| 16:10 | Every bot is flat (MFFU rule) | Orders show "Limit 0" until 18:00: normal |
| 16:15 | Day summary | One push with the day's $ |
| 17:00-18:00 | Market break. Updates itself if flat (17:02). Sends the day's data to Claude (after 17:05) | Maybe "updated" |
| Every hour | Self-heal fixes small PC faults | Only a push if it could NOT fix something |
| 23:00-07:00 | Quiet hours | Pushes still come, no sound |

## 3. A normal week

| Day | What happens |
|---|---|
| Sun 18:00 ET | Market opens. The bot must be running by now (after a weekend update: START BOT). |
| Mon-Fri | Trading days as above. Zlarior aims for 2-4 trades a week; many days have 0 trades. That is normal. |
| Fri from 16:15 | Weekly review page (Business > ZEUS this week): $ per account, trades vs plan, next week's news days. |
| Fri / Sat 17:02 | Evals take code updates only now, so an update never stops them midweek. |

## 4. Money

| What | Fact |
|---|---|
| Payout (Builder funded, ATLAS) | When ATLAS's 25K reaches about **$27,100** and has 2+ traded days, and no single day is more than half the profit: request **$1,000** on the MFFU dashboard after the close. The bot never asks MFFU for you. |
| What you keep | Builder: **80%** ($1,000 asked = $800 to you). Rapid: **90%**. |
| Tax pot | The day a payout lands, move **30%** to a separate savings account ($800 in = $240 to the pot, about $560 is yours). Next federal estimated payment: **Jan 15, 2027** (IRS Direct Pay, 1040-ES). Not tax advice. |
| After you are paid | Tell the PC (line below). The next cycle counts from $26,100. |
| New accounts | At most $150 of your own money on evals; after that a new account is paid from a payout (after the tax pot). |
| Where to look | Business > My accounts (MFFU view) = each account like MFFU shows it. Business > My Accounts > Payout coach = the exact $ left to payout today. Business > Taxes. |

Tell the PC about a payout (at the PC, after MFFU paid; your date):
```
python -X utf8 -m engine.account_b --payout YYYY-MM-DD=1000
```

## 5. Words the pages use

| Word | Means |
|---|---|
| **Room** | $ between the balance and the account's max-loss floor. $0 room = the account fails. The bot sizes every trade to stay inside it. |
| **Drawdown / max loss** | How far the account may fall from its best close before it fails (50K: $2,000; 25K: $1,000). The floor follows your best close up. |
| **Floor** | The balance where the account fails (best close minus the max loss). |
| **To pass** | $ still needed to pass an eval (50K: +$3,000; 25K: +$1,500 from the start). |
| **Eval / funded** | Eval = the test you pay for. Funded = passed, real payouts. |
| **DLL** | Daily loss limit. MFFU's soft daily loss: hit it and the account pauses for the day, it does not fail. Builders: $1,000. Rapid EOD 25K: $500. The bot sizes so one full stop stays inside it. |
| **EOD** | End of day: Rapid EOD measures the max loss from the day's closing balance, not from every tick. |
| **Limit 0** | MFFU lets the account hold 0 contracts right now: 16:10-18:00 ET every day (normal), or the account hit its DLL, failed or passed. |
| **R** | One unit of risk: what the trade loses at its stop. +2R = won twice the risk. |
| **PF** (profit factor) | $ won / $ lost. Above 1 makes money; 2 = $2 won per $1 lost. |
| **Win %** | Share of trades that made money. |
| **Twin** | The same trade in the backtest. Live vs twin shows if the bot trades as tested. |
| **Edge check / edge light** | GREEN = the last 40 sessions look like the tested strategy. AMBER = weaker, watch. RED = advice to size down. It never changes anything by itself. |
| **Circuit breaker** | Live trades vs the twin: WATCH, SIZE DOWN or PAUSE advice. Advice only. |
| **Sweep** | Price runs past an old high or low (where stops sit), then turns. |
| **Stop / target** | The exit if wrong (1 tick past the sweep) / the one exit if right. Both sit at the broker, so they work even if the PC dies. |
| **MNQ / micro** | Micro Nasdaq future: $2 per point. |
| **Flat** | No open trade. |
| **Armed** | A real account is switched on to trade. Only you arm it, by typing I ACCEPT LIVE RISK. |
| **Paper / Sim** | Pretend trades, no money. |
| **PC SILENT** | The PC has not reported for 30+ min. |
| **Kill switch** | Close everything, cancel orders, stop the bot, auto-resume off. |
| **Decide card** | A yes/no question for you on the Board, with the $ impact. |
| **ZEUS Lab** | Ideas tested every night. Nothing changes without your yes. |

## 6. Emergency playbook (max 3 steps each)

Every line here was run in the code or read from it on 2026-11-20.
"Your PC link" = the private Tailscale address of your PC (the LIVE_LINK.bat address). Port 8444 = the bot's own phone pages.

### 1. The PC is off or the phone says PC SILENT
1. A trade open? Its stop and target sit at the broker and still work. To get out now: Tradovate / MFFU app on the phone > the account > Flatten.
2. At the PC: double-click **PC_DOCTOR.bat**. It only looks. Read MOST LIKELY CAUSE and run the line under NEXT STEP.
3. Still silent 20 min later: send Claude a photo of the PC_DOCTOR window. (The bot never chases a missed entry.)

### 2. A trade is open and the bot looks stuck
1. Do nothing first: the stop and target are at the broker; they close the trade even if the bot is frozen.
2. Want out now: your PC link + `:8444/safety/` > **FLATTEN** (tap twice). The bot keeps running, no new entry today.
3. Phone page not working: Tradovate / MFFU app > the account > Flatten. Never add a stop by hand.

### 3. NinjaTrader disconnected
1. The stop and target still work at the broker. At the PC: NinjaTrader > **Connections** > connect again (or restart NinjaTrader).
2. Keep the MNQ chart with **LE_BarFeed** open; the bot blocks new entries while bars are stale and trades again by itself.
3. Not back in a few minutes and a trade is open: Tradovate / MFFU app > Flatten.

### 4. An alert says something went wrong
1. Read the alert: most say exactly what to do (for example "FLATTEN BY HAND" = NinjaTrader > Flatten Everything).
2. At the PC: double-click **HEALTH_CHECK.bat**. Each red line says the fix.
3. Not clear? Send Claude the alert text or a photo. "Entry blocked" = a guard refused an unsafe order: nothing to do.

### 5. An account hit the daily loss limit
1. Nothing to do: it is a pause for today, not a fail. Orders show "Limit 0"; the bot stays off that account by itself.
2. Check the account's status on the MFFU dashboard (Active / Failed / Passed).
3. Do not trade it by hand. It trades again after 18:00 ET.

### 6. An update is blocked
1. The old version keeps trading: nothing is broken.
2. Your phone says "update blocked by a local change in X": send Claude that line (keep or drop it). Never edit files in the bot folder.
3. To try again at the PC after 16:00 ET, bot flat: double-click **UPDATE.bat**. [OK] = done; [FIX] = that line says what.

Read only, at the PC: is the PC connected to your backup repo?
```
python -X utf8 -m engine.autoupdate --source-status
```

### 7. The phone site shows old numbers
1. Look at the top: "PC reported X min ago". Under 30 min = the numbers are live.
2. Red PC SILENT = the PC is quiet, not the site: go to card 1.
3. Page looks old: close the Home Screen app fully (swipe it away) and open it again.

### 8. Stop everything right now (kill switch)
1. At the PC: dashboard `http://localhost:8766` > Bot Control > **HOLD TO KILL** (hold the red button). It flattens every account, cancels orders, stops the bot and turns auto-resume off.
2. From the phone: your PC link + `:8444/safety/` > **KILL** (tap twice). Same as HOLD TO KILL, and it also stops Kalshi when Kalshi is live.
3. PC unreachable: NinjaTrader > Flatten Everything (if you can reach it), or the Tradovate / MFFU app > Flatten. Starting again is only at the PC with your live phrase.

Phone KILL / FLATTEN work only after this was run once at the PC:
```
python -X utf8 -m engine.phone_safety --on
```

### 9. Add an account
1. Buy it at MFFU with the CLUB code. Open NinjaTrader: the new account shows in the Accounts tab.
2. Open `http://localhost:8766/add-account/` on the PC (or your PC link + `/add-account/` on the phone). Pick the plan, type or tap the Name, type I ACCEPT LIVE RISK.
3. Tap Add. It starts trading once the bot is flat (or: START_BOT.bat + your phrase, N1 below). Check it at the PC:
```
python -X utf8 -m engine.accounts status
```

### 10. Turn Kalshi off
1. Kalshi is paper right now: no real money moves until you type the Kalshi phrase.
2. Live and you want it off: your PC link + `:8444/kalshi-live/` > **STOP** (one tap). Phone KILL (card 8) also stops it.
3. At the PC: double-click **KALSHI_STOP.bat**, type Y. It cancels every resting Kalshi order and switches Kalshi OFF.

## 7. New this week (landed Nov 21)

### N0. Fix the PC clock for good (once)
- **What:** The bot refuses every new entry while the PC clock is more than 5 seconds off internet time (the guard is right: it polls 3 s after the minute). If Windows will not sync by itself, FIX_CLOCK.bat sets it up once: Windows Time service on Automatic, three time servers, a check every 15 minutes, a sync now, and a task named OlympusClock (runs as the system, every 15 minutes, at boot and at wake).
- **When:** Once, or when Status / the Start page / the Board says the PC clock is off or "double-click FIX_CLOCK.bat once".
1. On the PC: right-click **FIX_CLOCK.bat** > **Run as administrator** (a plain double-click only tells you to do this).
2. Wait for the last line. Safe to run twice. Undo: right-click FIX_CLOCK_OFF.bat > Run as administrator.
3. Any day after: TRADE_HOME.bat > **9 Fix the clock** (or Start page > Sync the clock) works without an administrator.
- **You see:** BEFORE "the PC clock is 24.5 s behind internet time", AFTER "under 1 s", then "[OK] The clock matches internet time and OlympusClock keeps it that way." "[FIX]" = send Claude a photo of that window.

Each: what it does, when to use it, what to tap or type, what you should see. Phone: manual > **New**.

### N1. Start the bot (and arm a new account like the Rapid)
- **What:** START BOT now also arms every account you added (the Rapid EOD 25K too) when you type your phrase.
- **When:** After you add an account, after STOP BOT, or on a new PC.
1. At the PC: double-click START_BOT.bat.
2. Check the names it lists against NinjaTrader's Accounts tab.
3. Type I ACCEPT LIVE RISK, then Enter.
- **You see:** "Rapid EOD 25K (LIT + ATLAS): armed" and your account name, then "[OK] Running." A "NOT armed" line: send Claude a photo (privately: it shows your account name). The Start page (http://localhost:8766, PC only) does the same: when an account is not armed its Armed row is red ("Rapid EOD 25K ..xxxx not armed") and the button says Arm and start trading. Type I ACCEPT LIVE RISK in its box, then tap it.

### N2. The bot skipped a trade because of my hand trade
- **What:** While you hold a hand trade on any account, the bot will not open the opposite side on ANY account (that would be a hedge, against MFFU rules). Same side is allowed. Exits and stops are never blocked.
- **When:** Rule: hand-trade only when EVERY account is flat.
1. Push "Entry blocked" ("hedging guard ... a hand trade?"): nothing to do. Close your hand trade and the bot can enter again.
2. Push "Hand trade: wait": an account is not flat. Wait.
3. Push "HEDGE BLOCKED: ATLAS close not confirmed" (bot vs bot): open NinjaTrader, check that account, flatten it by hand if it is still open.
- **Optional:** to keep a hand trade on a bot account without the bot closing it, run the line below at the PC (60 minutes, max 240). A "Position mismatch ... Left alone (your hand-trade window)." push is then normal.
```
python -X utf8 -m engine.hand_hedge --hand-trade 60
```
Off early: the same line with --off instead of --hand-trade 60.

### N3. Keep-alive: no account closed for 7 days without a trade
- **What:** MFFU can close an account with no trade for 7 days. With keep-alive ON, the bot places ONE 1-MNQ trade on that account on day 6 (15:33-15:48 ET, out about 2 min later). Cost about -$2.40, at most -$22.90. Your own trades reset the clock. It arrived OFF.
- **When:** Once: Sunday before 18:00 ET (you said yes on Nov 20).
1. At the PC: double-click KEEPALIVE_ON.bat.
2. Type KEEP ALIVE ON, then Enter.
3. See "[OK] Keep-alive is ON." No restart needed.
- **You see:** pushes "Keep-alive today on ...", the entry, then "closed ... about -$2.40". "Keep-alive ... did not go through" = place 1 MNQ by hand on that account before 16:05 ET, in and out. Off: KEEPALIVE_OFF.bat (no phrase): "[OK] Keep-alive is OFF on every account."
```
python -X utf8 -m engine.keepalive --status
```
Check it any time at the PC: which accounts are on, the last result, the next planned day.

### N4. Phone alerts: set up Telegram, send a test
- **What:** Every alert goes to Telegram first, then Discord, ntfy and the Olympus app as backups. Entries, exits and "bot stopped" go to 2 of them.
- **When:** Set up once (2 minutes, from the phone). Test any time.
1. On the phone: your PC link + :8444/alerts/ (at the PC: http://localhost:8766/alerts/).
2. Make your bot: Open BotFather, send /newbot, copy the token. Paste it, tap Connect.
3. Tap Open your bot and START within 3 minutes.
- **You see:** "Connected: test delivered", and Telegram gets "Olympus alerts are ON". Test later: that page's Send a test alert, or TEST_ALERT.bat at the PC: the phone gets "TEST: Zlarior 50K LONG opened ..." (no trade placed). At the PC instead: ALERTS_SETUP.bat (1 = Telegram, 2 = Discord, 3 = both). Back to the old way: ALERTS_OFF.bat (ALERTS_ON.bat undoes it). 23:00-07:00 ET alerts come silent; "bot stopped" and hedge alarms still ring. No sound at all: iPhone Settings > Notifications > Telegram > Allow + Sounds.

### N5. Payout push: when to ask MFFU for money
- **What:** When a funded account reaches your plan line you get ONE push: "PAYOUT READY: request $1,000". 25K: $1,000 at $2,100 profit. 50K: $2,000 at $4,100 profit (MFFU shows funded accounts from $0). It also needs 2+ traded days and no day over half the profit.
- **When:** The day the push comes, after the close.
1. Request the amount in the MFFU dashboard. The bot never asks MFFU for you.
2. Record it at the PC with the line printed in the push.
3. When the money lands: 30% to the tax pot ($1,000 asked = $800 to you = $240 to the pot).
- **You see:** on payout 5 the push adds "WAIT: this is payout 5 of 5 ... Ask Claude before you request it." MFFU allows only 5 sim payouts; after the 5th it moves that account to live and your other sim accounts go dormant.

### N6. Olympus full screen on the iPhone
- **What:** Opened from its Home Screen icon, Olympus now shows every app full screen: no Safari bars when you go from ZEUS to NQ to Kalshi.
- **When:** Once. Again if your old icon still shows Safari bars.
1. In Safari (not Chrome), open your Olympus link.
2. Tap Share (the square with the arrow) > Add to Home Screen > Add. Old icon? Delete it first.
3. Always open Olympus from that icon: phone alerts only work that way.
- **You see:** no address bar and no bottom bar. Step by step with pictures: Set up your iPhone.

### N7. An update was rolled back
- **What:** If a new update makes the bot keep stopping (4 starts in 10 minutes), the PC goes back by itself to the last version that worked and skips the bad one.
- **When:** Only when that push comes.
1. Nothing urgent: the version that worked is running again.
2. Look at ZEUS: bot running? If it says stopped, at the PC: START_BOT.bat + your phrase (it keeps the good version).
3. Tell Claude, so the bad update gets fixed.
- **You see:** push "Update rolled back": "The new code ... kept stopping (4 starts in 10 min). Back on ..., the version that ran fine; the bad one is skipped." "Update crash loop: ROLLBACK FAILED" = send Claude that text now. An open trade's stop and target still sit at the broker.

## Where things are

| Need | Page |
|---|---|
| Live numbers, PC age, today's entry windows | ZEUS (hub/zeus.html) |
| Everything that happened, newest first; Decide cards | Board |
| Each account like MFFU shows it | Business > My accounts (MFFU view) |
| Trades | Trading |
| What you still have to do | Your steps (hub/steps.html) |
| How do I...? (16+ answers) | Help (hub/help.html) |
| Holidays / early closes | Risk calendar (Pythia) |
