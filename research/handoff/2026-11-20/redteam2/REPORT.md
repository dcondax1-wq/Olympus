# Red team 2 (Fri 2026-11-20): what could cost money in the next 10 trading days

## For the owner (one minute)

| What could cost money | How likely | Fixed? |
|---|---|---|
| **Thanksgiving Thu 11-26 (halt 13:00 ET), Fri 11-27 and Christmas Eve 12-24 (halt 13:15 ET): MFFU does NOT close your trade at a half-day halt.** If the bot is stopped (you pressed STOP, a crash, a restart that did not resume) with a trade open, the trade is still open at the halt = **the account fails** (ATLAS's funded 25K, the Zlarior 50K eval). Before today, nothing warned you. | Low (needs a trade open + the bot down at 12:45-13:00), but it costs a whole account (ATLAS funded: ~$1,000 payout path + the account) | **Yes.** Your phone now rings "CLOSE THE TRADE NOW" from 10 min before the halt when the bot is stopped (from 4 min before when it runs but its own close did not work). Never muted by the daily alarm limit. |
| **A restart in the 1-5 seconds between the entry fill and its stop** (power cut, crash, Windows update) on an eval without auto-resume: the trade sits at the broker with **no stop** until you start the bot. | Very low | **Yes.** Your phone rings "TRADE HAS NO STOP" after 60 s. Starting the bot places the stop at once (tested: no second entry). |
| Adding the Rapid EOD 25K today in the middle of the session | Low | Nothing breaks (tested), but "Start trading" restarts the bot (1-3 min off). **Add it any time; press Start trading after 16:00 ET** (it cannot trade before Sunday night anyway). |
| Christmas Day 12-25 and New Year's Day 1-1 (closed), New Year's Eve 12-31 (full day) | - | Already right: no entry on closed days, normal 15:55 flat on 12-31 (all 7 lanes replayed). |
| MFFU rules (16:10 flat, max contracts, Rapid $500 daily loss, news, best day, floor) | - | All enforced in code; checked against MFFU's pages today (table in the write-up). Builder funded (ATLAS) and every eval may trade Tier-1 news; only Rapid/Pro **funded** may not (the bot already flattens those -3/+2.5 min). |
| Today's Kalshi change | - | Safe: display only, cannot crash or slow the bot server (it is not loaded there). |

**Your part:** on Thanksgiving and Christmas Eve, if your phone says "CLOSE THE TRADE NOW", close it in NinjaTrader (right-click the position > Close). That's all.

CME's own page (cmegroup.com) answered 503 again today: the half-day times are the ones the bars of 2021-2025 show and other
schedules agree on (Thu 11-26 13:00 ET, Fri 11-27 and Thu 12-24 13:15 ET). Re-check on cmegroup.com the week before.

## Findings (ranked)

| # | Rank | Finding | Fix | Test |
|---|---|---|---|---|
| H1 | CRITICAL | No alarm when a broker position is still open just before a CME half-day halt. MFFU: "During holiday trading hours, auto-liquidation will not occur at the half-time market close, and the trader is responsible for closing the positions. Failure to close the positions before the market closes will result in breaching of the account" (help center, Permitted Times to Trade). The adapter's own flat (halt - 5 min, engine/ninjatrader._tick_flat_time) runs only while the bot runs; LiveBot.stop() leaves the bracket at the broker (by design); an eval without auto-resume stays stopped after a crash. | engine/fast_alarm.halt_open: reads NinjaTrader's position files of every non-Sim account in the last 10 min before an early close; bot stopped -> push from halt - 10, bot running -> from halt - 4; never capped by DAY_MAX; no "back to normal" once the halt passed. Reads no file at any other minute of the year. | tests/test_redteam2_live.py h1-h10 (6 fail on the old code) |
| H2 | HIGH | A restart between the entry fill and its bracket with no resume = a position with no stop at the broker. The write-ahead state (S1 2026-11-15) protects it at the next tick, but only once the bot runs again; the "Bot stopped" alarm does not say the trade is naked. | engine/fast_alarm.no_stop: bot not running + a same-day data/ninjatrader_state*.json leg in entry_sent / pending / unprotected (sent > 60 s ago) + NinjaTrader shows that real account in a position -> "TRADE HAS NO STOP". | r1-r5 (3 fail on the old code; r5 proves the restarted adapter protects once and sends no second entry) |
| L1 | LOW | "Start trading" / Re-arm mid-session (engine/onboard.rearm -> go.step_arm) stops the bot, may restart the server (server_stale / env change) and waits up to 90 s for the checklist: 1-3 min without polls in the entry window. A LIT entry is not chased after 90 s. | Advice, no code: arm the new account after 16:00 ET. | - |
| L2 | LOW | `python -m engine.rapid --account` (the old CLI path) checks the Name against Zlarior's 50K and ATLAS's 25K only (rapid._other_names), not the extra accounts (Zlarior 25K #2). The Add-account box and ADD_ACCOUNT.bat use engine/account_cli.name_problem, which checks every account. | Owner path is safe; patch in LEAD_WIRES (L2). | - |
| L3 | LOW | Rapid EOD 25K with MFFU's $500 DLL: the bot sizes a full stop (2 ticks slip + commission) inside the same $500, so a worse fill can touch MFFU's DLL at the stop. A soft pause for the rest of the day (resets 18:00 ET), never a fail. | None needed. | - |

Not re-reported: last night's C1-C9 (redteam-live-2026-11-20).
