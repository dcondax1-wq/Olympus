# PANIC: what to do if something goes wrong

Read this once now, so you know it when you need it. Every fix is 1 or 2 actions.

**The three buttons** (any one is enough to get flat):
- **HOLD TO KILL**: dashboard (http://localhost:8766, Bot Control) -> hold the red button. Flattens, cancels orders,
  stops the bot for today, turns auto-resume off.
- **NinjaTrader Flatten Everything**: in NinjaTrader right-click any chart or the Positions tab -> **Flatten Everything**.
  Closes every position and cancels every order on every connected account.
- **From the phone (PC far away)**: open **Chrome Remote Desktop** -> the Surface -> do one of the two above. If the PC
  is unreachable: open the **Tradovate / MFFU app** on the phone -> the eval account -> **Flatten** (or Exit All).

| If this happens | Do this |
|---|---|
| **A position with no stop** (NinjaTrader shows a position, no stop order in Orders) | 1. NinjaTrader **Flatten Everything** (do not try to add a stop by hand). 2. Then HOLD TO KILL so the bot stays out for today. |
| **The bot is gone** (dashboard does not open, phone says "PC silent / Surface offline") | 1. A trade open? Its stop and target are at the broker and still work. If you want out: phone -> Tradovate/MFFU app -> Flatten. 2. Later: restart the PC or START_DASHBOARD.bat; the bot never chases a missed entry. |
| **NinjaTrader disconnected mid-trade** (red connection, "FEED STALE" push) | 1. The stop and target sit on the broker's server and still work while NinjaTrader is offline. Reconnect (Connections menu) or restart NinjaTrader. 2. If it does not come back within a few minutes: phone -> Tradovate/MFFU app -> Flatten. The bot blocks new entries while bars are stale. |
| **Wrong size** (more micros than the phone notice / dashboard plan, or more than 40) | 1. NinjaTrader **Flatten Everything** at once. 2. HOLD TO KILL, then tell Claude what you saw (the order guard should refuse this: it is a bug). |
| **Eval near the floor** (push "Eval room below $800" / "$400") | 1. Nothing to do on the spot: the bot already sizes down from the room and never risks past the floor. 2. To stop for the day: HOLD TO KILL. Do not trade by hand on the eval account. |
| **"Position mismatch" push** | Bot flat but NinjaTrader holds a position: the bot closes it itself (CLOSEPOSITION). Push "FLATTEN BY HAND": NinjaTrader **Flatten Everything**. Bot shows a trade that NinjaTrader does not: check NinjaTrader's Positions tab; nothing to close. |
| **"P&L mismatch" push (17:00)** | Compare NinjaTrader Account Performance (today) with the dashboard. A few dollars = slippage. A big gap: tell Claude before the next session. |
| **"Clock drift: entries blocked" push** | Windows Settings -> Time & language -> Date & time -> **Sync now**. Entries resume by themselves on the next check (15 min). |
| **"Entry blocked" push** | Nothing to do: a guard refused an order it found unsafe (the reason is in the notice). Tell Claude if it repeats. |

**Never** arm a real account to "fix" something, and never trade by hand on the bot's account while the bot runs: the
reconcile guard closes any position on the bot's instrument that its ledger does not know about.
