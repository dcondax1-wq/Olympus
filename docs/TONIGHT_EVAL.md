# Zlarior + ATLAS on the eval tonight (owner 2026-11-12)

Owner: "I need ATLAS / Zlarior and BLITZ ready tonight, BLITZ not so much, but Zlarior and ATLAS trading on my eval."
Claude got everything ready. **You arm the eval yourself** (MFFU requires you to be there; Claude never types the live phrase).

## Your 3 steps at the PC (before 01:45 ET; entries start 02:00 ET)
1. **New code.** Double-click `STOP_BOT.bat`. Put the code zip and its `.sha256.txt` in Downloads, open the zip, copy
   `UPDATE_FROM_ZIP.bat` into the bot folder and double-click it (type Y if it asks).
2. **Double-click `GO_LIVE_EVAL.bat`.** Part 1 turns GitHub off, checks NinjaTrader and its bars, installs the phone alerts and
   shows six lines (write down the alert topic). Part 2 is START BOT: log in to NinjaTrader if it asks, then type
   `I ACCEPT LIVE RISK` when it asks. That arms Zlarior (50K) and ATLAS (25K) and leaves BLITZ on paper.
3. **iPhone:** install the free **ntfy** app, tap **+**, type the alert topic from step 2, tap **Subscribe**.

| What | Tonight |
|---|---|
| Zlarior (50K eval, LIT) | live after your phrase; drawdown left $1,145 of $2,000 at the last report (2026-11-07) |
| ATLAS (25K eval) | live after your phrase; drawdown left $822 of $1,000 at the last report |
| BLITZ | paper (unchanged) |
| Size | two-week mode: micros so one winner covers what is still needed, never more than 80% of the room (Zlarior: at most about $916 on one trade) |
| Phone | alerts on trade open / close with $, FEED STALE, bot down (ntfy); the site shows the PC's status every 15 min |
| Stop everything | `STOP_BOT.bat` (orders at the broker keep their stop and target) |

If step 2 says "the bot is already running": double-click `STOP_BOT.bat`, then `GO_LIVE_EVAL.bat` again.
Checked before sending: `tests.test_go` 65/65, `engine.ninjatrader --selftest` PASS, `tests.test_bots_back` 80/80,
`tests.test_lit_live` (every 2026 session through the live loop) identical.
