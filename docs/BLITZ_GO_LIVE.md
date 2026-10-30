# BLITZ goes live on its own 25K

BLITZ (the scalper) trades its own MFFU Builder 25K, next to Zlarior (50K) and ATLAS (25K), and never against them.
Do this on Sunday evening or on Monday before 11:00 ET (BLITZ's first check of the day).

1. Buy the MFFU Builder 25K (your price, with your code) and log in to it in NinjaTrader. Its Name shows in the Accounts tab.
2. On the PC, open the Start page (desktop icon **LE START**) and go to **BLITZ · 25K**. Type that Name, press **Set BLITZ's 25K**, type
   `I ACCEPT LIVE RISK` and press **Arm BLITZ**.
3. Check that every line of the card's **Go-live check** is green. If one is red, do what its line says. The card runs this
   check, which is the same as this console line:

       python -X utf8 -m engine.account_c --preflight

That is all. Zlarior and ATLAS keep trading as before, and BLITZ joins at the bot's next poll.

## What you will see on the phone on the first day

- **Nothing before 11:00 ET.** BLITZ checks the market only at 11:00, 11:30 ... 15:30.
- **No trade after a quiet day.** The BLITZ card then says, for example, *"BLITZ skipped today: yesterday's 09:30-16:00 range 239 pts
  < 0.8 x its 14-day mean 404 pts"*. This happens on about 1 day in 3 (63 of 2026's 198 days). Oct 29 and Oct 30 are both skip
  days. On some other days the price never leaves BLITZ's band at a check, so there is no trade either. In 2026 BLITZ traded on 45%
  of days.
- **A trade:** *"LONG · BLITZ MFFUEVBLDR… (REAL)"* and *"Entered 3 MNQ (BLITZ scalp)"*, a few seconds after the check minute.
- **The end of that trade,** 30 minutes later or earlier at its stop: *"LONG · BLITZ MFFUEVBLDR… (REAL)"* and *"+$214 … (BLITZ
  scalp)"*. A trade can lose up to its stop.
- **Size:** the first trade is about 3 micros at a 60-point stop, with about $370 at risk. A wider stop means fewer micros. The size
  is never more than 20 micros. BLITZ takes at most 6 trades a day and is flat by 15:55.
- **A bad day stops by itself:** after -$600 BLITZ takes no more trades that day (*"locked out today"*).
- **If Zlarior or ATLAS enters the other way,** BLITZ is closed first (*"HEDGE"*) and their order waits until NinjaTrader shows
  BLITZ flat.
- **"EVAL PASSED":** BLITZ stops trading that account. Request the funded account in MFFU, then use Start page > BLITZ · 25K >
  Passed → funded.
- **Rare red alerts:**
  - *"CLOSE NOT CONFIRMED"*: look at NinjaTrader. The bot keeps re-sending the close.
  - *"order NOT placed"*: nothing is open and no money is at risk.
  - *"PAUSED (performance contract)"*: BLITZ has done worse than its research floor. Resuming is your decision.

The clocks go back on Sunday Nov 1. You do not need to do anything: BLITZ's times stay New York time.

## What was proved before this (2026-10-29)

`python -X utf8 -m tests.test_rehearsal_blitz --jobs=4` runs the real bot server with a fake NinjaTrader on a virtual clock. LIT
was on Sim101, ATLAS on Sim102 and BLITZ on Sim103. All 345 checks passed. All 27 routed BLITZ trades (78 micros, 63 trail moves)
matched the BLITZ backtest: entry minute, side, micros, fill, stop and 20R target, every trail move (each one tighter), exit
and $. The only differences were the ones the no-hedging rule causes. No account ever held long while another held short.
The rehearsal covered these days:

- a normal 6-trade day;
- the eval passed on day 1 (no trade after it);
- ATLAS entering the other way mid-trade and at the same minute (BLITZ closed first);
- LIT holding the other side (BLITZ's signal skipped);
- CME early closes at 13:00 and 13:15 (BLITZ flat 5 minutes before, no entry in the last 15 minutes);
- a server restart mid-trade (no second entry, the trade managed to its exit);
- an entry NinjaTrader refused (never booked, nothing left working);
- your pause;
- HOLD TO KILL.

The results are in `research/scalp/blitz_rehearsal.json`. The rules and the numbers to expect are in `BLITZ_STRATEGY.md`.
