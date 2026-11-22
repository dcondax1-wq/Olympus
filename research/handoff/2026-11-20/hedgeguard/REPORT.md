# Hand-trade hedge guard (idea #1, branch day-redteam2, 2026-11-20): paper only, nothing lands before the weekend + a red-team pass

## For the owner (one minute)

| What | Before | Now (on the branch, not on the PC yet) |
|---|---|---|
| You hold a hand trade on one MFFU account, the bot wants the other side on another account | The bot could not see your hand trade: it would go long on one account while you are short on another = a hedging breach on every account involved | Refused. The bot reads NinjaTrader's own position files of every MFFU account before each entry |
| You and the bot on the same side | allowed | allowed (copying is fine) |
| NinjaTrader not running / its feed stale (files can't be trusted) | - | the hand check steps aside (the bot's own checks still run) and your phone gets ONE "Hand-trade check off" notice that day |
| You place a hand trade on an account the bot trades | the bot closes it in about a minute | still the default; NEW optional window: `python -X utf8 -m engine.hand_hedge --hand-trade 60` (max 240 min, ends by itself, `--off` to end it) and the bot leaves it alone on its own account |

Until this lands: place a hand trade only while every bot account is flat, one account at a time.

## What was built

| File | Change |
|---|---|
| engine/hand_hedge.py (new) | `opposite_hand(d, bot, router, own)`: scans `outgoing\*_<account>_Position.txt` (the same files guards._broker_net reads) of every non-Sim account, NQ / MNQ only (ES / MES ignored), cached 2 s. Refuses direction d when another account holds the opposite side and no bot lane explains that position (no open bracket of any bot adapter on that account: LIT, ATLAS B, account C, the Rapid's ATLAS lane, every extra account; no fleet follower position there). The caller's own account is skipped (`own`). Stale = NinjaTrader's LE_BarFeed 1m file older than 300 s or missing (a position file's age means nothing: NinjaTrader writes it only on a change and wipes outgoing\ at restart) -> None + one push a day. Every error -> None (never blocks on a guess, never raises). Plus the hand-trade window file data/hand_trade.json and its CLI. |
| engine/multi_account.py `AccountRouter.opposite_open` | after the existing ledger checks: `hand_hedge.opposite_hand(d, bot, self, own=...)`; own = the extra account's `nt_account` (exclude=Account), the bot's main adapter account (exclude=None). Every caller gets it: LiveBot._route (LIT main), each extra account's LIT copy (Account._process), account_b (ATLAS 25K, Rapid ATLAS lane) and account_c (BLITZ), which call it with exclude=object(). |
| engine/guards.py `reconcile_tick` | while the owner's hand-trade window is open: no CLOSEPOSITION of a position the ledger does not explain on the bot's own account; one "Hand trade left alone" notice. The hedge rule stays on in the window. |

**Not fed into `others_opposite()` on purpose:** it decides "wait while the bot's hedge close (LiveBot._hedge_clear) closes ATLAS /
BLITZ first". A hand trade is not something the bot may close, so a hand position there would only start a hedge close of an
unrelated bot position. `opposite_open` runs first in Account._process, so a hand position already refuses the extra
account's entry (q = 0) before others_opposite is asked.

## Lead wire (bot file, not applied): the one-account bot

`LiveBot._route` asks `self.accts.opposite_open` only when extra accounts exist (`self.accts` is None for a one-account bot).
The PC has extra accounts today (Zlarior 25K #2, the Rapid), so it is covered there; for a one-account start apply
`research/handoff/2026-11-20/hedgeguard/patch_live_route_one_account.diff` (engine/live.py, 7 lines: the same call when accts is
None). account_b / account_c call `ac.opposite_open` only when `b.accts` exists too: same gap, same one-line fix if wanted.

## Tests

| Test | Result |
|---|---|
| tests.test_hand_hedge (new, also run by tests.test_cross_hedge) | 14/14 (4 red on the code before: 1 hand LONG vs bot SHORT, 6 hand NQ mini, 8 stale notice, 11 window) |
| tests.test_cross_hedge (the night-rehearse suite, unchanged checks) | 13/13 + hand trades |
| engine.ninjatrader --selftest / test_multi_account (full) / test_fleet / test_rapid25 / test_rapid / test_guards / test_nq_live_reliability / test_redteam2_live / test_lit_live --quick | EXIT 0 / 55/55 / 131/131 / 94/94 / 60/60 / 69/69 / 119/119 / 15/15 / OK |

Checks in test_hand_hedge: hand LONG 2 MNQ on the 25K #2 + bot SHORT on the 50K = refused (account named by its last 4);
same side allowed; an extra account's own position skipped; a position a bot lane explains left to the ledger checks; Sim101
and MES positions ignored; a hand NQ mini SHORT on ATLAS's 25K blocks LIT LONG; FLAT again = allowed; stale feed = steps aside
+ one notice; no feed file = steps aside; paper bot = nothing read; window open = no CLOSEPOSITION + one notice; window closed =
the old CLOSEPOSITION; window capped at 240 min and ends by itself.

Red-team points for the weekend pass: (1) a bot position in the moment between its legs retiring and NinjaTrader's file going
FLAT reads as "hand" for a second: it can only block (fail-safe), never route; (2) the file name is split at its FIRST "_"
(instrument names never have one), so an account Name with "_" is read too (check 6b); (3) the window only
covers the bot's own (LIT) account reconcile; ATLAS's adapter still closes a stray position at its flat time.
