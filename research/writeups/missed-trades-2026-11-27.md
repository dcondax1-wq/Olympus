# Every live-vs-twin gap, Oct 23 - Nov 26 2026: what live missed, why, and what it cost

The owner's question behind it: the Replay Theater's day notes show "Live Zlarior 50K: 0 trades vs the twin's 1; gap MISSED". So:
every place in the last 35 days where a live account did not do what its backtest twin did, the root cause from the evidence,
and the dollars per cause. READ ONLY research: nothing live changed. Data: `research/livegap/missed_2026-11-27.json` (every row
with its evidence). Sources: `research/livegap/LIVEGAP.json` (the audit of 2026-11-24 on 30 pulled PC day folders), `research/livegap/daily.json`,
the twins re-run to Nov 26 (`tools/web_public/nq/replay/*.json`), the live board (`tools/board.py read`, Nov 27 00:38 ET).
Sign: **live minus twin** in $. Minus = money left on the table; plus = live was better (the miss dodged a loser).

## The answer in one table
| Cause | Gaps | $ (live minus twin) | Bug? | Fix |
|---|---|---|---|---|
| **Not armed** (Rapid EOD 25K never armed; Nov 3 re-armed by hand after the signal) | 2 | **-$1,712.95** | no: an owner step | Arm the Rapid (owner, at the PC); + a "disarmed account missed a signal" alert (below) |
| Sizing by design (ATLAS funded: the $1,000 best-day cap -> 1 micro) | 1 | -$516.00 | no: owner-approved rule | none (a choice, see below) |
| Slippage (ATLAS live fills vs twin) | 4 | -$51.14 | no | none (inside the cost model: 4 fills, net -$51) |
| Feed / bot gap Oct 26 08:30-08:45 | 1 | -$0.50 | unknown | watch (one 15-minute gap, a breakeven trade) |
| Order refused: account Name without the 'R' (Oct 27) | 1 | +$689.50 | **yes, FIXED Oct 27** | already fixed (`engine/ninjatrader._nt_said_no_account`) |
| Bot not running: PC bot OFF Nov 9 15:55 -> Nov 15 20:39 ET | 7 | +$1,094.97 | yes (no alarm), fixed since | already fixed (report task + hands-free + Telegram /status) |
| **Total left on the table** | | **-$2,304.40** | | |
| Misses that dodged losers | | +$1,784.64 | | luck, not a plan |

**The one gap that matters: the Rapid EOD 25K was never armed.** On Fri Nov 20 03:45 ET ATLAS's EMA member went short and hit its
+6.6R target. The ATLAS 25K took it (1 micro, +$512). The Rapid EOD 25K, which should carry ATLAS at <= $250 risk, took nothing: its
balance is still **$24,995** (= never traded), and the owner's to-do still reads "At the PC: STOP BOT, then START_BOT.bat, type
I ACCEPT LIVE RISK; check 'Rapid EOD 25K ... armed'" (the account was added DISARMED on Nov 19: "Added disarmed; START BOT + your
phrase"). That one trade = **+$1,658.75 at $250 risk**, 33% of the way to the Rapid's $1,505 still to pass.

## Every gap (Oct 23 - Nov 26)
| When (ET) | Account | Twin did | Live did | Kind | Live - twin | Root cause | Evidence |
|---|---|---|---|---|---|---|---|
| Mon Oct 26 08:37 | Zlarior 50K | SHORT 5 MNQ, BE +0.02R (+$0.50) | nothing | MISSED | -$0.50 | feed / bot gap 08:30-08:45 | `engine/live.py` comment at the un-routed exit (23:08 ET): "the model entered during it, never routed" |
| Tue Oct 27 06:12 | Zlarior 50K | SHORT 5 MNQ, STOP -1.00R (-$689.50) | refused | MISSED | +$689.50 | order refused: account Name without 'R' (bug, fixed) | `engine/ninjatrader._nt_said_no_account`, `engine/live._void_refused_days`: the bot booked 6 MNQ -$827 that was voided |
| Wed Oct 28 03:43 | Zlarior 50K | SHORT 5 MNQ, STOP -$437 | the same | identical | $0 | - | live entry 29,945.00 = twin |
| Tue Nov 03 15:39 | Zlarior 50K | LONG 2 MNQ, EOD +0.21R (+$54.20) | nothing | MISSED | -$54.20 | not armed: re-set up and re-armed by hand 20:51-21:06 ET | heartbeat remote / autopilot events; no record of the 15:39 signal |
| Fri Nov 06 04:00 | ATLAS 25K | SHORT, STOP -1.03R | 2 micros -$168.81 | slipped | +$8.44 | fill | live vs twin price |
| Tue Nov 10 03:33 | Zlarior 50K | LONG 3 MNQ, STOP -$347.70 | nothing | MISSED | +$347.70 | bot not running (Nov 9 15:55 -> Nov 15 20:39) | `data/pc_days/2026-11-09` + `2026-11-16` gaps.json: no uptime sample; balance $49,313.54 (Nov 6) -> $49,192.78 (Nov 17) = only Nov 16's -$129 |
| Tue Nov 10 03:55 | ATLAS 25K | LONG, STOP -1.03R | nothing | MISSED | +$176.56 | bot not running | same |
| Wed Nov 11 03:56 | Zlarior 50K | SHORT 1 MNQ, 15-min cut -0.31R (-$42.40) | nothing | MISSED | +$42.40 | bot not running | same |
| Wed Nov 11 09:40 | ATLAS 25K | SHORT, STOP -1.02R | nothing | MISSED | +$175.18 | bot not running | same |
| Thu Nov 12 09:45 | ATLAS 25K | SHORT, STOP -1.02R | nothing | MISSED | +$175.53 | bot not running | same |
| Fri Nov 13 03:40 | ATLAS 25K | LONG, STOP -1.03R | nothing | MISSED | +$177.77 | bot not running | same |
| Fri Nov 13 08:05 | ATLAS 25K | LONG, BE 0.00R | nothing | MISSED | -$0.17 | bot not running | same |
| Mon Nov 16 06:16 | Zlarior 50K | LONG 1 MNQ, STOP -$129.40 | the same | identical | $0 | - | live = twin |
| Tue Nov 17 08:20 | ATLAS 25K | SHORT, TARGET +6.87R | 2 micros +$1,791.89 | slipped | -$74.78 | fill | live vs twin price |
| Tue Nov 17 10:15 | ATLAS 25K | LONG, STOP | nothing | not a gap | $0 | the one-position rule (another member open) | engine rule |
| Wed Nov 18 04:50 | ATLAS 25K (funded) | SHORT, STOP -1.04R | 2 micros -$112.80 | slipped | +$15.20 | fill | live vs twin price |
| Fri Nov 20 03:45 | ATLAS 25K (funded) | SHORT, TARGET +6.64R | **1 micro +$512.31** | size | -$516.00 | funded sizing by design | `engine/sizing.funded_qty`, 25K funded preset max_win $1,000: stop 38.75 pts, target 258 pts = $516 a micro; 2 micros = $1,032 > $1,000 cap |
| **Fri Nov 20 03:45** | **Rapid EOD 25K** | **ATLAS EMA SHORT, TARGET +6.64R (+$1,658.75 at $250)** | **nothing** | **MISSED** | **-$1,658.75** | **not armed** | board: balance $24,995; owner to-do "check 'Rapid EOD 25K ... armed'"; Nov 19 note "Added disarmed" |
| Nov 21 - 26 | all | no twin trade on any day | - | - | - | - | twins re-run to Nov 26 (replay + forward_paper: 4 sessions, 0 events) |

Not attributable to one trade (balance moves with no row in the cloud): Zlarior 50K -$219.60 (fees + rows not in the cloud),
ATLAS 25K +$324.51 (rows missing for the silent days), Zlarior 25K #2 +$24 (no twin trade since its Nov 18 start).
Checked and NOT found: "different bars" (both traded LIT days have the live entry = the twin's to the tick), news pause, guard
block, sizing 0.

## Bugs and fixes
1. **Account Name without the 'R' (Oct 27):** a bug, **fixed the same day** (`engine/ninjatrader._nt_said_no_account` refuses loudly,
   `engine/live._void_refused_days` voids the booked trade). No action.
2. **The PC bot was off for 6 days (Nov 9-15) and nobody knew:** the report task was not installed, so no alarm. Fixed since:
   the 15-minute report, the hands-free landing (Telegram /status, reboot recovery) and the board's "PC last reported". Here it
   dodged losers (+$1,095), but the next silent week could cost a winner. No action beyond keeping those alarms on.
3. **A disarmed account silently misses signals (Rapid EOD 25K):** not a code bug (the owner's arm step is pending), but the bot
   knows it happened and says nothing. **Proposed fix (bot side, for the red team, NOT landed):** in `engine/setup_progress`
   (watchdog, off the order thread, read-only), when a strategy's signal routes to the accounts and one of its follower accounts is
   on the broker but NOT armed, send ONE line per account per day: "Rapid EOD 25K is not armed: it missed ATLAS EMA short at
   03:45 (the twin's +6.6R). Arm it at the PC: START_BOT + I ACCEPT LIVE RISK." The data is already there (`followers()` builds
   "Not on: Rapid EOD 25K - not armed" for the setup lines). Tests: a disarmed follower -> one line, an armed one -> none, the cap /
   quiet hours as today. I can build it on a branch for your red team on request.
4. **Auto-update held back since Nov 24 00:45 ET** (board self_heal: "held back by a local change it may not touch"; still on
   Nov 26 23:30): no trade differed yet (no twin trade Nov 21-26), but the PC runs pre-Nov-24 code. The owner's one line from
   PLAN_SUNDAY (`git stash push -m "owner park" -- research/orderflow/results.json && UPDATE.bat`) clears it.

## What the owner does (hands only)
1. At the PC: STOP BOT, START_BOT.bat, type I ACCEPT LIVE RISK, and check that "Rapid EOD 25K ... armed" shows. That alone would
   have banked the Nov 20 +$1,659 on the Rapid.
2. The update unblock line above (the bot is on Nov 24 code).
