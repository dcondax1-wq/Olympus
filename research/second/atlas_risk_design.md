# ATLAS funded-25K risk at real fills - pre-registered design (2026-11-20, night-atlasrisk)

Written and committed BEFORE any run. Tool: `tools/atlas_risk.py`. Output: `research/second/atlas_risk.json`.
Write-up: `research/writeups/atlas-risk-real-fills-2026-11-20.md`. Research only: no engine file, no live_model*.json,
no second_model.json, no data/account_b.json changes. The only product change allowed: the Decide card text
(tools/web_public/business/decisions.json, schema kept, tests.test_decide must pass).

Why: tools/atlas_fills.py (research/writeups/atlas-fills-2026-11-20.md) found ATLAS's first 3 live fills 9-15 ticks worse
than the backtest. Every open Decide item about ATLAS's money was valued at 1 tick a side. Re-judge them at 3 / 6 / 10.

## Fixed before the runs

- Today's real state (python tools/board.py read, 2026-11-20 02:09 ET): ATLAS Builder 25K FUNDED $24,887, $887 of room,
  one traded day (-$113) in the cycle, the 48 h wait over (tools/atlas_health.at_today). The owner's YES (2026-11-19):
  min_room 0 (no $100 stuck stop; MFFU's 7-day inactivity close modelled as 5 idle sessions under $100 of room). The
  Rapid EOD 25K is not bought yet: a fresh Rapid from Fri Nov 20.
- Costs: N = 3, 6, 10 ticks a side in total (the backtest's 1 included), tools/atlas_fills.priced: entry N ticks past the
  5m open, every non-target exit N ticks past its level, a target (resting limit) 0. Sizes unchanged. N = 1 shown as the
  old valuation, never judged. Only ATLAS's trades are re-priced (Zlarior's real fill was 4 ticks; LIT is left at 1).
- Funded 25K engine: tools/atlas_more PGF2 (MFFU Builder 25K funded rules, the live funded preset 60% of the room <= $750,
  a winner <= $1,000, the bot's request line ask_above $750) from today's account, 1,000 week-block paths per market
  (tools/uprisk.mc_paths, seed builder_levers.A4.SEED_LIFE, 126 sessions = 6 months), the SAME paths for every option.
- Rapid 25K engine: tools/money/money_plan.RSeat on tools/money/rapid25.acct("25k", keep $500) (LIT + ATLAS $250 at 30%
  of the room, the 30% best-day guard; a stuck funded Rapid = lost, re-bought), ATLAS's trades re-priced the way
  tools/atlas_fills.rapid_rows does, 1,000 paths, the same paths for every option.
- Markets: H1 = 2026 Jan-Jun-like, H2 = 2026 Jul-Oct-like, REF = 2021-25-like.
- Metrics (each option x cost x market):
  $ a month to the owner = 6-month payouts after MFFU's split / 6 (Rapid: minus every eval fee and re-buy); before the 30%
  tax pot. Median first-payout date over ALL paths (Nov 20 = session 1, weekends and Thanksgiving Nov 26 skipped; "none
  in 6 months" when half or more of the paths never pay). Chance of losing the funded account in 6 months: funded 25K =
  floor touched, stuck, or the inactivity close (atlas_more dead_6m); Rapid = any funded Rapid lost or stuck.

## Options (each = one change against what runs / is approved today, the base)

| Id | Card | Base (today) | Challenger |
|---|---|---|---|
| O1 | atlas-funded-room-40 | 60% of the room, min_room 0 | 40% of the room, min_room 0 |
| O2 | atlas-funded-keep-trading | min_room 0 (the owner's YES) | the old $100 stop (min_room 100) |
| O3 | payout-ping-1000 | ask at $750 above the buffer | ask at $1,000 |
| O4a | atlas-on-rapid | ATLAS $250 next to LIT (built) | ATLAS off (LIT alone) |
| O4b | atlas-on-rapid | ATLAS $250 | ATLAS $150 a trade |
| O5a | pause question | keep trading (base of O1) | PAUSE: no ATLAS trade for 20 sessions (4 weeks), then the base; MFFU's 7-day rule kept by a 1-micro token trade a week (about $3 each, subtracted) |
| O5b | pause question | keep trading | PROBE: 1 micro on every signal that fits for 25 sessions (about 10 fills at ATLAS's rate), then the base |
| O5c | pause question | keep trading | STOP for 6 months: $0, the account held by token trades (worked out, not simulated) |

O2's challenger is the old rule: if it is not better, the owner's YES stands (the card stays "yes" either way).

## The bar (fixed now)

A challenger is BETTER than its base only if, at BOTH 6 and 10 ticks a side, on the same paths:
1. its 6-month loss chance is lower in H1 AND in H2 by at least 0.5 points, and not higher in REF by more than 0.5; AND
2. its $ a month to the owner is at least 90% of the base's in H1 AND in H2, and in REF at least the base's minus $10
   (REF's $ is near $0, where a 10% band means nothing).
3 ticks is shown, not judged.

Card actions decided now:
- atlas-funded-room-40: "recommend" -> yes (with the reason) only if O1 passes the bar; else it stays "no" with the
  realistic-cost numbers. Status stays "open".
- atlas-funded-keep-trading: status and recommend stay "yes"; the impact text gets the real-fill numbers.
- payout-ping-1000: recommend -> yes only if O3 passes; else unchanged ("no").
- atlas-on-rapid: recommend stays "yes" unless O4a or O4b passes (then the passer is named).
- Every changed card: the impact text keeps the 1-tick line and adds one plain "At real fills (6-10 ticks a side): ..."
  sentence with the 10-tick numbers.
- The pause question (O5) is answered at 10 ticks (6 shown): "pause" only if O5a, O5b or O5c passes the bar at 10 ticks;
  else "keep trading", and the answer names the $ and the loss chance of each. Also stated: keeping trading still pays
  only if the base's $ a month at 10 ticks is over $50 in H1 and H2 (the fills study's worth rule).
