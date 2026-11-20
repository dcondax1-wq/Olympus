# Payday plan + levers + loss cuts: design (fixed and committed BEFORE any run, 2026-11-20 ~21:50 ET)

Owner (2026-11-19): "Compare losses, cut losses, maximize on wins, figure out how to make more money. We need these fundeds
paying next month latest." Paper research only: nothing live changes (no live_model*.json, second_model.json, engine file).

## 1. The payday plan (no choice made here: a forecast)

Start state = today's board (python tools/board.py read, 2026-11-19 21:40 ET):
- Z50 Zlarior, Builder 50K eval: $49,193, $3,807 to pass, $1,025 room, eval session 25 on Nov 20 (live two_week 40% of the
  room to session 80). Funded: LIT alone (combo ON after the pass is lever L4's other side).
- N25 Zlarior 25K #2, Builder 25K eval: $25,000, $1,500 to pass, $1,000 room, session 3 on Nov 20 (no trade Nov 18-19).
- A25 ATLAS, Builder 25K FUNDED: $24,887 ($887 room), the cycle holds one traded day (-$113), 48 h first wait over. Funded
  preset 60% of the room; ping at $750 above the $1,100 buffer (first payout = balance >= $26,850, 2 traded days a cycle,
  best day <= 50% of the cycle).
- R25 Rapid EOD 25K: bought tonight, first session Nov 20, LIT + ATLAS $250, the 30% best-day guard, the $500 soft day,
  funded keeps $500 above the $1,100 buffer (engine/rapid.PLANS = tools/money/rapid25.py).
- Calendar: CME sessions from Fri Nov 20 (engine/cme_calendar); Thanksgiving Thu Nov 26 counted as NO session (closed /
  13:00 halt, the bot does not trade it); Fri Nov 27 half day counted as a normal session (slightly optimistic); Dec 25 and
  Jan 1 closed.
- Engine: tools/money/money_plan.py seats (the live sizing code, MFFU rules as coded there), every account on the SAME
  Monte Carlo paths (tools/uprisk.mc_paths, 5-session week blocks, seed BL.A4.SEED_LIFE), 126 sessions, n = 1,000 a market.
  Markets: H2 = 2026 Jul-Oct-like (THE quoted row), H1 = Jan-Jun-like, REF = 2021-25-like (no edge). Costs in.
- Outputs per account: first payout date median and 80% range (p10-p90 over ALL paths; a path with no payout in 6 months
  counts as "later than May 2027"), its $ to the owner (after MFFU's split; and after the 30% tax pot), the chance it pays by
  Dec 31 / Jan 15 / Jan 31, the chance the account is lost BEFORE its first payout (eval failed, or funded blown / stuck
  under $100: a re-buy happened before any payout), 6-month lost %. Fleet: the chance at least one account pays by Dec 31 /
  Jan 15 (= at least one funded account pays: payouts only come from funded accounts).
- Owner yes 2026-11-19 "ATLAS keeps trading 1 micro under $100 of room": not in the money_plan seats (they count < $100 as
  lost). Quoted from tools/atlas_more.py (lost in 6 months 10.5 -> 9.5% Jul-Oct, first payout unchanged); the base is left
  as money_plan has it (slightly pessimistic on A25 lost).

## 2. Levers (8, pre-registered; each = ONE change on one account, everything else as today, same paths)

| id | account | change |
|---|---|---|
| L1 atlas-funded-room-40 | A25 | funded preset 60% -> 40% of the room a trade (open Decide card) |
| L2 payout-ping-1000 | A25 + N25 once funded | ask at $1,000 above the buffer instead of $750 (open Decide card) |
| L3 a25-need | A25 | need-based funded size: risk only what makes the target reach the next $1,000 request line, never more than today's 60% rule, min 1 micro (uprisk.Funded "need": 1.0) |
| L4 combo50k-now | Z50 | ATLAS on Zlarior's 50K NOW at 50% of its size in the eval (combo_account a50_eval, first in keeps the account), from today's hole; vs Zlarior alone in the eval and the combo once funded (= the "after the pass" advice). Run on tools/money/combo_account.py's own Slot (week-block paths, seed 202, n = 600 a market), both sides on the same paths |
| L5 n25-cap300 | N25 | eval two_week 40% of the room (owner rule kept) + a $300 cap a trade (inside room_f 0.4) |
| L6 r25-atlas150 | R25 | ATLAS lane $150 instead of $250 |
| L7 r25-atlas350 | R25 | ATLAS lane $350 instead of $250 |
| L8 rapid25-lit-bank | R25 | LIT 1 micro banked at the day's 30% room when the guard says 0 (open Decide card) |

Already in docs/TESTED_AND_REJECTED.md, NOT re-run: ask at $500 / asap $250 on the 25K (payout-policy-funded25), Rapid eval
day caps / loose guard (rapid-levers, 50K), keep $1,000 on the Rapid (valued 2026-11-18), LIT on ATLAS's funded 25K (lost
+16 pts), the zombie-eval rule on Zlarior.

JUDGE (fixed now): a lever is "better on both" only if in BOTH H2 and H1, on the account it touches:
  (a) payout sooner: P(first payout by Jan 15) up >= 1.0 pt AND the median first payout not later (<= 0 trading days), and
  (b) safety: P(account lost before its first payout) up <= 0.5 pt AND 6-month lost up <= 1.0 pt,
  and in REF (2021-25-like) P(lost before first payout) up <= 2.0 pts, and H2 $ a month (6-month cash) down <= $25.
A Decide card is made (or an open card's recommendation set) ONLY for a lever that passes all of it.

## 3. Loss anatomy + untested loss cuts

Data: research/anatomy/trades_lit.json (631 Zlarior trades, live-loop backtest, LIT size) and trades_atlas.json (1,288 ATLAS
member trades after the account-B rules, $250 a trade), built by tools/win_loss_anatomy.py on 2026-11-19. The Rapid lanes
trade these same signals (their $ differ only by size), so their losses are these trades.
Cluster table per bot and period (H1 / H2 / 2021-25): share of losing $ and net R per trade by hour, weekday, Tier-1 news
day / news inside the trade, ATLAS member, stop size (terciles of risk points within the bot), VIX band. A "cluster" =
worse than the bot's average in all three periods.

Loss-cut rules not in docs/TESTED_AND_REJECTED.md (tested there: ATLAS day caps "stop after a loss", weekly brake, skip the
day after a losing day, skip / halve after LIT WON the other side, x1.25 after LIT was stopped on the other side, LIT cold
streak, member pauses, VIX skips, stop-size skips, news flats):
  C1 atlas-after-lit-loss: no new ATLAS entry on a day once a Zlarior trade has CLOSED at a loss earlier that day (any side).
  C2 lit-after-atlas-loss: no new Zlarior entry on a day once an ATLAS trade has CLOSED at a loss earlier that day.
Proof bar (CLAUDE.md): C2 touches LIT = picked on 2026 Jan-Jun AND checked on Jul-Oct (both better) and 2021-25 not worse;
C1 touches ATLAS = better in BOTH 2026 halves AND 2021-25; costs in; 2-4 trades a week kept (ATLAS's own count stays as is
minus the cut ones); report trades/week, PF, net $, $/month, max DD; plus the A25 funded seat (first payout, lost) for C1 and
the Z50 eval 2-week pass / fail for C2. "Better" = net $ up AND max DD not worse, in every required period. A rule that
cuts fewer than 5 trades in a 2026 half is reported as "too few to judge" (not passed).
