# Red team 3 (2026-11-21): full-fleet dry run of the weekend landing (olympus/pc 7adf312d) vs base e141caae

## For the owner

| What | Result |
|---|---|
| Every account together (Zlarior 50K, Zlarior 25K #2, ATLAS funded 25K, Rapid EOD 25K LIT + ATLAS lanes), 11 real days, the new code vs Friday's | **Identical trades and $ on every day** (-$1,089.65 both, 15 entries both). No trade lost to a new guard, no double order, no error |
| Sunday 18:00 open, every minute to Monday 16:20 (Nov 16) | identical (LIT long 06:16 on both evals, stopped -$388.20 each) |
| A Thanksgiving-week half day (Fri 11-13 replayed as a 13:15 halt; Labor Day 13:00 real) | identical, flat before the halt, no entry in the last 15 min |
| Your hand trade open on another account | the new guard refuses the bot's opposite entry (it works in the full bot, not only in its test) |

Money note (not new, a decision already on your Decide card "rapid25-lit-bank"): on the Rapid EOD 25K eval the 30% best-day
rule caps a winning day at $428, and LIT's targets are ~375-430 points ($750-860 for ONE micro), so the Rapid's LIT lane took
**0 of 5** LIT trades in these days and ATLAS's lane 1 of 9 signals (6 skipped for the same cap, 2 for the no-hedge rule). As
built, the Rapid 25K barely trades.

## How (tools/fleet_dryrun.py, branch day-redteam3)

tools/rehearse_day.py (the real engine.live.LiveBot, PAPER, every lane's NinjaTrader adapter on ONE simulated NinjaTrader, the
accounts built through ADD_ACCOUNT / START BOT arming exactly as on the PC) + what it never wrote: NinjaTrader's
`le_feed\MNQ_1m.csv` (fresh bars) and `le_feed\accounts.csv` (one row per account a minute, cash + open P&L from the fake's
positions). **Without those files engine/hand_hedge reads NinjaTrader as "not running" and steps aside: the rehearsal (and the
landing's update gate) never ran the hand-hedge guard at all.** `--root` runs the same days on any checkout (base / landing),
`--early day=HH:MM` replays a day as a CME early close, `--hand ACCOUNT=SIDE` plants a hand position, `FD_LOGS=<text>` prints
the matching lane logs in full.

## Base vs new, trade by trade

| Day | Entries base | Entries new | $ base | $ new | Same |
|---|---|---|---|---|---|
| 2026-09-07 (Labor Day, halt 13:00) | 2 | 2 | 216.00 | 216.00 | yes |
| 2026-11-06 | 1 | 1 | -84.40 | -84.40 | yes |
| 2026-11-09 | 0 | 0 | 0 | 0 | yes |
| 2026-11-10 | 3 | 3 | -678.90 | -678.90 | yes |
| 2026-11-11 | 2 | 2 | -212.00 | -212.00 | yes |
| 2026-11-12 | 2 | 2 | -260.80 | -260.80 | yes |
| 2026-11-13 | 2 | 2 | -76.30 | -76.30 | yes |
| 2026-11-16 | 2 | 2 | -776.40 | -776.40 | yes |
| 2026-11-17 | 1 | 1 | 895.95 | 895.95 | yes |
| 2026-11-18 | 1 | 1 | -112.80 | -112.80 | yes |
| 2026-11-19 | 0 | 0 | 0 | 0 | yes |
| **11 days** | **16** | **16** | **-1,089.65** | **-1,089.65** | **all** |

(polls every 5 min + every minute around trades and closes; rehearse_day checks 188/188 on both). Per lane (both): Zlarior 50K
4 entries -$733.50, Zlarior 25K #2 4 / -$618.40, ATLAS funded 25K 7 / +$392.65, Rapid ATLAS lane 1 / -$130.40, Rapid LIT lane 0.
Every log line with NOT routed / NOT OK / hedging guard / PRICE LIMIT / open P&L / HEDGE was compared too: the same lines.

Extra runs (both versions):

| Run | Base | New |
|---|---|---|
| Sunday open, every minute from 18:00 Sun 11-15 (Mon 11-16) | 17/17, LIT 06:16 long x2, -$388.20 x2 | identical |
| Fri 11-13 as a 13:15 half day | ATLAS 03:40 long, stop -$76.40, 08:05 long, BE | identical |
| Hand LONG 1 MNQ planted on ATLAS's locked eval, 11-17 | ATLAS short 08:20, target +$895.95 (a cross-account hedge) | refused 08:20 on both ATLAS lanes ("hedging guard: NinjaTrader shows LONG 1 MNQ ... ..RH03"); ATLAS long 10:15 (same side, allowed), stop -$110.40 |
| Every-minute 11-10 + 11-17 | see the end | see the end |

## Bugs found

None in the landing. One harness bug of my own on the way (stamping NinjaTrader's position files with the replay clock made the
adapter's wall-clock close check look "not confirmed" and blocked ATLAS's 08:05 trade on both versions); fixed in the harness,
the files keep real times. Consequence: in the replay the accounts.csv rows always read older than the files, so the
accounts.csv "blind" refusal cannot fire here (neither falsely nor truly); its file-time rule is covered by
tests.test_hand_hedge 14-19.

Not covered: the keep-alive (OFF by default: before_entry returns at its first line), the 2% price-limit rule beyond "no false
block" (no 4.75% move in these days; the landing's own `--scenarios pricelimit` covers the forced case), a real PC reboot.
