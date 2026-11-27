# All strategies on our 4 accounts: fastest FIRST payout (2026-11-27, pre-registered BEFORE any scored run)

Owner: "if all strategies ran on our accounts we'd be good" / "I don't think it takes a month and a half to get payouts".
Question: which mix of bots per account (LIT, ATLAS, BLITZ, POSEIDON) under ONE shared per-account risk manager gets each
account to its first payout fastest without raising the fail rate much? PAPER RESEARCH ONLY: no live_model*.json, combo
file, sizing or arming change. Code: `allstrats.py` (this folder) -> `results.json`, write-up `RESULT.md`.

## Engine (reused, not rebuilt)
research/plans/rank.py + research/onebook/book.py (real fills: LIT at engine/costs.py, ATLAS 10 ticks a side
atlas_risk.T_at(10), BLITZ stored fills; live LIT two_week eval sizing room_f 0.4 to session 80; added bots on
rapid_levers.q_add lanes = min(lane $, 30% of the room, the soft day left); MFFU rules per plan: EOD trailing MLL with lock,
soft day $500 (25K) / $1,000 (50K) both bots shared, 30% best-day guard on the Rapid eval, 50% best day + 5 payouts on
Builder funded, Rapid daily payouts with the bot's $500 keep and >= $250 since the last, Tier-1 news flat -2/+2 min on Rapid
funded, stuck line = dead account, re-buy at the owner's price the next session).
Shared per-account risk manager (applied to EVERY row, the live combo rule): one position at a time on the account (first in
keeps it; a later signal of any bot while one is open is skipped), ties LIT > ATLAS > BLITZ, ATLAS never opposite LIT
(stored hedge ban = direction lock), one shared soft day and one shared room, everyone flat by the close.
POSEIDON (order-flow lane A): only 51 days of real ticks (2026-09/11), none in 2026 H1 or 2021-25, so it CANNOT be in the
Monte Carlo; reported as a flag row only (forward paper, gate 0 = 30 trades), never in a pick.

## Start = today's real accounts (board.py read 2026-11-27 15:44 ET), first session Mon 2026-11-30
| account | plan, price | state used |
|---|---|---|
| Z50 Zlarior | Builder 50K eval, $91.80 | $49,482 (bal -518), room $1,313 (floor -1,831, peak +169), session 29 done |
| N25 Zlarior 25K #2 | Builder 25K eval, $63 | $25,019 (bal +19), room $996 (floor -977), session 7 done |
| R25 Rapid EOD 25K | Rapid EOD 25K eval, $97.20 | $25,299 (bal +299), room $1,000 (floor -701), 1 traded day, best day $304 |
| A25 ATLAS | Builder 25K FUNDED | MFFU $401 (floor -599, peak 401), 0 payouts, cycle = one $401 day (conservative for 50%) |
Calendar: CME sessions from Nov 30; Dec 25 + Jan 1 + Jan 18 closed. Dec 31 = session 23, Jan 31 = session 42.
A failed eval / lost funded account is re-bought the next session (fee counted); the slot's first payout may then come from
the new account. 126 sessions (6 months) per path, 1,000 paths a market, 5-session week blocks, seed 23, the SAME paths for
every mix. Markets: H1 = 2026 Jan-Jun-like, H2 = 2026 Jul 1-Oct 16-like (the trade stores end Oct 16: the Oct 17-Nov 26
drought, LIT 7 trades, is NOT in them = flagged), REF = 2021-11..2025, Y25 = calendar 2025 (incl. the April tariff drought).

## Mixes (eval bots / funded bots; lanes on a 25K, x2 on the 50K): 11 per account, 44 rows + 4 flag rows, all counted
| id | eval | funded |
|---|---|---|
| M00 TODAY | Z50: LIT + ATLAS x0.5 (combo_50k a50_eval); N25: LIT; R25: LIT + ATLAS $250; A25: ATLAS | Z50 LIT + ATLAS; N25 LIT; R25 LIT + ATLAS; A25 ATLAS |
| M01 | LIT | LIT |
| M02 | ATLAS | ATLAS |
| M03 | LIT + ATLAS | LIT + ATLAS |
| M04 | LIT + ATLAS x0.5 | LIT + ATLAS |
| M05 | LIT + ATLAS + BLITZ $150 | same |
| M06 | LIT + ATLAS + BLITZ $300 | same |
| M07 | LIT + BLITZ $150 | same |
| M08 | ATLAS + BLITZ $150 | same |
| M09 | LIT + ATLAS x0.5 + BLITZ $150 | LIT + ATLAS + BLITZ $150 |
| M10 | LIT | LIT + ATLAS + BLITZ $150 (eval clean, "all strats" once funded) |
(A25 is already funded: only the funded column applies there.)

## Reported per account x mix x market
median sessions (and date) to the slot's FIRST payout over ALL paths (unpaid = censored at 126), % paid by Dec 31 /
Jan 31, current-eval fail % (fails before passing, 60 sessions; A25: % lost before the first payout), median sessions to
pass, 6-month $/month to the owner after split and fees, p10 6-month net, funded lost %, fixed-size view: trades/week, PF,
net $, max DD.

## Pick rule (fixed now), per account
1. Eligible in H1: fail % <= M00's fail % + 3 points.
2. Pick = the eligible mix with the highest H1 % paid by Jan 31 (tie: lower median first-payout sessions, then $/month).
3. Card only if, vs M00: paid-by-Jan-31 % higher in H1 AND H2 (both 2026 halves better), $/month not lower in H1 AND H2,
   fail % in H2 <= M00 + 3 points, and in REF $/month not lower by more than $50 and fail % <= M00 + 5 points (not much
   worse). Y25 reported, not judged. 11 mixes a account = a win by 1 of 11 with tiny margins is called noise (< 2 points).
Expected (written before the run): first payouts are bound by the payout RULES (Builder funded needs buffer + $1,000 and a
50% best day; Builder eval needs the target), so more bots mostly move the fail rate, not the date; BLITZ adds little.
