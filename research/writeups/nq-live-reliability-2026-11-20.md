---
title: NQ live bot reliability - every way a backtest trade can miss the account, the fix or alarm for each, entry timing and real fills
family: other
date: 2026-11-20
status: finding - live code fixes + alarms built (tests green); poll-on-the-first-tick built OFF; ATLAS entries fill ~12 ticks worse than its backtest's 1 tick
summary: Owner - "push the NQ bot to its max ... read data faster, better fills, better timing ... fundeds paying next month". Since the 50K eval started only 2 of 7 backtest trades reached the account. Every cause was traced in the code. Fixed - the audit's "no record = missed" (now "unknown", Oct 28 WAS traded), a hot-added account booking a trade it never took (Zlarior 25K #2, -$129.40 + a CLOSEPOSITION on Nov 17), an update/restart while ATLAS holds a trade. New alarms - bot on but not polling / feed 2 bars behind -> phone push within 2 minutes (was up to 15-30 min); MISSED TRADE with its reason at once (was after 16:05 or never). Every "NOT routed" line now reaches the nightly verdict, the ZEUS review and the PC's day files. Timing - the order leaves 3-5 s after the fill bar opens (2 s is the poll offset); a built-OFF switch polls on NinjaTrader's first tick instead. Fills - Zlarior 3 ticks worse than its open (1 trade), ATLAS 9 / 11 / 15 ticks worse (3 trades) vs 1 tick in the backtests.
runs: tests/test_nq_live_reliability.py, tests/test_fast_entry.py, tests/test_account_b_min_room.py; data/pc_days ledger rows 2026-11-06..18 (NinjaTrader fill prices); scratchpad entry-poll timing (engine/poll_timing on the test_lit_live LiveBot harness)
---

# NQ live bot reliability (2026-11-20)

## For the owner (one minute)

**The bot now tells your phone within 2 minutes when it cannot take a trade, and names every trade it missed and why.**
Nothing about how Zlarior or ATLAS pick or size trades changed.

| What | Before | Now |
|---|---|---|
| Bot on but stuck (not polling) in the entry hours | phone told at the next 15-min report, up to ~30 min | push in 2 min ("ZEUS not polling"), one "back to normal" |
| NinjaTrader bars stop | phone told after 5 min + up to 15 min | push in 2-2.5 min ("FEED STALE") |
| A backtest trade the bot did not take | told after 16:05 ET (or never: that push type was switched off on Nov 18) | push at once: "MISSED TRADE · Zlarior 06:12 ET: <why>" |
| A day before the PC kept records (Oct 28) | "missed: PC bot off" (it WAS traded, -$437) | "unknown: check the broker statement" |
| Zlarior 25K #2 added while the bot ran | booked a -$129.40 trade it never took + sent a close order | fixed: it ignores trades that ended before it joined |
| A restart that did not bring the bot back, in the entry hours | told at the next 15-min report | push in 3-3.5 min ("Bot stopped") |
| An update / restart while ATLAS holds a trade | possible (only Zlarior was checked) | never |
| ATLAS's funded 25K under $100 room | stops for good | your one line below keeps it trading 1 micro (your YES) |

Fills (real NinjaTrader prices): Zlarior's only fill was 3 ticks worse than the backtest's price ($1.50 on 1 micro). ATLAS's three
fills were 9, 11 and 15 ticks worse ($9, $11, $15 on 2 micros), while its backtest counts 1 tick. Only 3 trades, but all
three the same way: if it holds, ATLAS earns about $5 a micro less per trade than the backtest says.

**Next for you:** at the PC when ATLAS is flat: `python -X utf8 -m engine.account_b --min-room 0`. Keep the PC on and
NinjaTrader open in the entry hours (02:00-15:30 ET): the Nov 10 and Nov 11 misses were the PC being off (Nov 7-17).

## Every way a backtest trade can miss the account (job 1)

From engine/live.py (_route_primary, poll_once, _loop, _sleep_s), engine/lit_live.py, engine/autoupdate.py, engine/autoresume.py,
engine/watchdog.py, engine/guards.py, engine/fill_audit.py, engine/multi_account.py, server.py (_autostart_resume),
engine/remote_ctl.py and scripts/run_bot.ps1.

| # | Cause | Seen live? | What happens now |
|---|---|---|---|
| 1 | PC / server off | Nov 7-17 (Nov 10, 11 missed) | The PC cannot report its own death: the cloud's "PC stopped reporting" (20 min, engine/notify pc_silent) stays the alarm. run_bot.ps1 restarts a crashed server in 5-60 s. |
| 2 | Bot on, poll loop stuck / erroring | - | NEW fast alarm (engine/fast_alarm.py): no good poll for 90 s, or the poll thread dead -> "ZEUS not polling" push. The old watchdog alert (kind "system") stops at engine/push.pc_app_ok since Nov 18. |
| 3 | NinjaTrader feed stale | Oct 26 (likely) | The bot blocks new entries at once (no Yahoo). NEW: the 1m feed 2 bars behind (120 s) or the bot's own feed block -> "FEED STALE" push. The 15-min report needed a 5-min-old bar first. |
| 4 | 1m bar late in the file | - | Unchanged and fine: the bot re-polls the moment the 1m file changes (engine/live._await_nt_bar, up to 20 s); a LIT entry is not chased after 90 s (LIT_MAX_LATE_S). |
| 5 | Auto-update restart in an entry window | - | Unchanged rules: never 01:50-16:00 ET on a weekday (covers LIT 02:00-15:30 and ATLAS), only when flat with no setup armed. NEW: ATLAS (account B), account C and the Rapid lane's open position / open bracket also block it. Remote restart: also refused 01:50-16:00 while the bot runs. |
| 6 | A restart that does not re-arm | Nov 3 (re-armed by hand that evening) | A real account resumes only with your auto-resume opt-in (engine/autoresume.py); without it an update waits for the Friday / Saturday halt. The board shows hourly evening restarts resuming fine. NEW: a bot still stopped 3 min after a server start in the entry hours while data/autostart.json says it was running (Stop / kill clear it) -> "Bot stopped" push (the server's own "bot NOT resumed" alert is kind "system": off the phone since Nov 18); an entry the model took before the restart -> MISSED TRADE "the entry came before this bot start at HH:MM ET" (engine/live skipped it silently). |
| 7 | The model entered during a gap (bot down / feed burst) | Oct 26 | NEW: MISSED TRADE "the model entered while the bot was down or its feed was behind" at its exit line; the reason also lands in the audit row. |
| 8 | Live-only filters | - | None that cuts backtest trades: news guard OFF, calendar guard (0 blocked in the 2026 replay), 1 entry a day = the backtest. Live-only by design: the PC clock off by > 5 s (bad bars), your own pause / remote flatten (never alarmed as missed). |
| 9 | Room / size 0 skips | - | By design (eval room caps). Was logged "at 0 instead of N" with no reason in the audit ("held back by the bot"). NEW: "size 0: <why>" and a MISSED TRADE push. |
| 10 | Account name mismatch | Oct 27 (saved $965) | Fixed Oct 27 (engine/account_rename at every start); a refused order is the fill check's push. |
| 11 | Extra account added while the bot runs | Nov 17 20:26 ET | FIXED (engine/multi_account): it booked the Nov 16 06:16 model exit (-$129.40) on Zlarior 25K #2 and sent NinjaTrader a CLOSEPOSITION for it. Now a trade that ended before the account joined is skipped, and an exit of an entry it never routed books $0 (as LiveBot does since Oct 26). The flatten-in-case after a gap stays. |
| 12 | "No record" days | Oct 26-28 | FIXED (engine/fill_audit, tools/live_gap_proposal.classify landed): a day before the PC's first record is "unknown: check the broker statement", out of the missed count and $. |

Where the reasons go now: the bot's own "NOT routed / NOT traded / size 0 / never routed" lines are copied every minute into
logs/exec_audit/notes.json (fill_audit.collect), shown in the nightly verdict (logs/exec_audit/nightly/<day>.json
"not_routed", `python -m engine.fill_audit nightly` prints them), as one info line in the ZEUS daily review, and in the PC's
day files as days/<day>/gaps.json (with the uptime samples and held-back entries, account ids cut to the last 4), so a miss
like Nov 10-11 can be explained from the cloud (`python tools/data_pull.py --latest`).

Phone path (engine/notify.instant_problem): the private ntfy alert topic, type "problems" (IMPORTANT, on by default, rings in
quiet hours). The 15-minute report skips its own copy of the same condition / missed entry (notify.problem_dup), so one alert,
one phone. Off switch: LE_FAST_ALARM=0 (the fast alarm) or notify_settings.json "problems": false (all problem pushes).
The fast alarm runs only for a bot on a broker account (never paper), weekdays 01:58-15:55 ET with CME open (holidays and
early halts excluded), from 3 minutes after a start; a test's fake clock never pushes.

## Timing (job 2)

Real entries (the PC ledger's route time minus the fill bar's open, data/pc_days 2026-11-06..18):

| Entry | Routed after the bar opened |
|---|---|
| Zlarior Nov 16 06:16 BUY 1 | 4 s |
| ATLAS Nov 6 04:00 SELL 2 | 5 s |
| ATLAS Nov 17 08:20 SELL 2 | 4 s |
| ATLAS Nov 18 04:50 SELL 2 | 3 s |

Where the time goes: 2.0 s is the poll offset (engine/live.next_wake: polls at +2 s and +32 s each minute, so that
NinjaTrader's LE_BarFeed has written the closed 1m bar AND the new minute's open, which LIT sizes from: without that open 26
of 119 entries in 2026 would size 1-4 micros differently and 17 targets differ, research/lit/live_check.json enter_now); then
the poll itself. Measured with engine/poll_timing on the test_lit_live LiveBot harness (paper, Oct 6 + Oct 13 2026, 3,019
polls, this cloud machine): the entry poll takes 158-285 ms from its start to the order (other polls: median 201 ms, p90 289
ms): bars merge 68-116 ms (the biggest part), the LIT model 50-128 ms, the 1m bars 23-37 ms, routing 2 ms, the state save 1
ms. So of the PC's 3-5 s, 2 s is waiting by design and the rest is the PC's own (slower, shared with NinjaTrader) poll plus
waiting for the minute's first trade. Caching more would save tenths of a second; the 2 s wait is the big part.

**Built, OFF by default: poll on the first tick** (engine/fast_entry.py). The minute's first poll waits for NinjaTrader's files
instead of the clock: it wakes at +0.15 s and polls the moment the new minute's open and the closed 1m bar (at a 5m close also the 5m bar) are in the
files (checked every 50 ms), at the latest at the usual +2 s. Same bars, same open, same decisions, only earlier: up to
~1.8 s on an active minute. Switch: `python -X utf8 -m engine.fast_entry --on` (or the start cfg "poll_on_tick", or env
LE_POLL_ON_TICK=1). tests/test_fast_entry.py 21/21; OFF = engine/live._sleep_s byte-for-byte today's wait. Not turned on:
the $ it saves cannot be measured from 1-minute bars (no tick data), so it needs a Sim day first. Live = backtest after all of tonight's changes: tests.test_lit_live full (heavy.sh, research/lit/live_check.json) 120/120 trades identical, 9,923 intraday polls 0 differences (+29 on the known Good Friday day, as before), market cache 0 of 100 differ, LiveBot 2/2 entries + exits, 0 errors; --quick the same (the poll itself is untouched; only the sleep between polls has the OFF switch).

Not changed: ATLAS (account B) is routed after LIT, the state save, account C, the ES learning refresh and the Bot Brain in
each poll (engine/live.poll_once). In the harness the ES refresh and the Bot Brain take 0-3 ms, so moving ATLAS earlier
gains nothing measurable; its 3-5 s are the same 2 s poll offset + the poll, which the switch above also cuts.

## Fills (job 3)

The only real NinjaTrader fill prices (ledger result.legs fill_px), against the MNQ 1m bar open the backtests fill at:

| Entry | Model price | Bar open | Real fill | Worse by | $ at the real size |
|---|---:|---:|---:|---:|---:|
| Zlarior Nov 16 06:16 BUY 1 | 27,798.75 | 27,798.50 | 27,799.50 | 3 ticks (4 vs the open) | $1.50 |
| ATLAS EMA Nov 6 04:00 SELL 2 | 27,037.75 | 27,038.00 | 27,035.50 | 9 ticks | $9.00 |
| ATLAS EMA Nov 17 08:20 SELL 2 | 27,367.50 | 27,367.75 | 27,364.75 | 11 ticks | $11.00 |
| ATLAS MACD Nov 18 04:50 SELL 2 | 27,395.50 | 27,395.75 | 27,391.75 | 15 ticks | $15.00 |

Both backtests count 1 tick on a market entry (live_model.json costs; tools/atlas_* SLIP 0.25). So: **Zlarior ~2 ticks over
the model (1 trade: not enough to say)**; **ATLAS ~10.7 ticks over the model on every one of its 3 entries**, about $5.30 a
micro a trade. ATLAS's live trades so far: 3 trades, +$1,510 (PF 6.4), so the slippage is ~2% of that, but on its average
backtest trade ($124 a trade at $250 risk, Oct 19 - Nov 19) 2 micros x $5.30 = ~$11 is ~9% of the edge. All three were
shorts at a 5-minute open on a fast bar (the 1m bar ran 6-10 points in the trade's direction): price was already moving our
way, which is also why a limit order at the open is no fix (it would miss exactly the runners; LIT's limit-entry test on
2026-11-19 lost $8-87 a month for the same reason). The bot books its ledger at the model's prices (the Nov 6 stop -$168.81 =
the model's, the real loss was ~$9 more); NinjaTrader's balance anchor (engine/broker_balance) keeps the room right.
Exits: no exit fill prices in the rows (CLOSEPOSITION / bracket fills are not priced there), so exit slippage is unknown.

What would settle it: 10+ ATLAS fills. If the median stays above ~4 ticks, re-run ATLAS's gates at that entry cost
(CLAUDE.md "Strategy changes"; the ZEUS review already proposes it once the median of 8+ matched trades is over 1 tick).

## Small owner items (job 4)

- `python -X utf8 -m engine.account_b --min-room 0` (owner YES 2026-11-19, Decide atlas-funded-keep-trading): writes "min_room"
  into the PC-local data/account_b.json only, keeps every other key (armed, account, stage, payouts), refuses a bad value or
  no ATLAS account; `--min-room default` puts the $100 line back. In force once ATLAS is flat or after a restart.
  tests/test_account_b_min_room.py 21/21.
- Stale tests fixed (expected numbers only, room_f 0.4 = CLAUDE.md "eval two_week room_f 0.4"): test_account_b_funded 20 -> 17
  micros; test_second_account_b 25K 20 -> 17 and the 30-pt stop 8 -> 6. Now 67/67 and 47/47 (--quick).

## Files

engine/fast_alarm.py (new), engine/fast_entry.py (new, OFF), engine/fill_audit.py, engine/notify.py, engine/watchdog.py,
engine/autoupdate.py, engine/multi_account.py, engine/datafeed.py, engine/zeus_review.py, engine/account_b.py, engine/live.py
(_sleep_s: the OFF switch only). Tests: tests/test_nq_live_reliability.py, tests/test_fast_entry.py,
tests/test_account_b_min_room.py; tests/test_account_b_funded.py, tests/test_second_account_b.py (numbers).
