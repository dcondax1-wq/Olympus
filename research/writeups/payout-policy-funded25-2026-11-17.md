---
title: Funded Builder 25K payout policy - when and how much to request (ATLAS alone and LIT + ATLAS $250)
family: risk
date: 2026-11-17
status: adopt-candidate (a request habit, no trade changes) - ask for the full $1,000 max each time. A hair more $ and fewer lost accounts in both 2026 halves, the same in 2021-25, first payout about 2 trading days later.
summary: ATLAS's 25K eval passed; the funded 25K comes this week. 8 request policies on the SAME 600 Monte Carlo paths of 126 sessions (tools/money/funded25.py tooling, builder_levers seeds, costs in, the live one-account rule), MFFU Builder 25K sim funded rules (research/lit/mffu_rules.json - $1,000 EOD trailing, floor locks at start + $100 and sits there after the 1st payout, payouts above the $1,100 buffer, $250-$1,000, 80%, best day <= 50% of the cycle, 2 traded days, 48 h first wait, 5 sim payouts). Picked on H1 (2026 Jan-Jun), checked on H2 (Jul-Oct 2026). Ask at the $1,000 max - ATLAS alone $594 / $498 a month vs $592 / $497 with today's $750 line, lost 5.3 / 6.3% vs 5.7 / 7.3%; LIT + ATLAS $250 $602 / $535 vs $599 / $529, lost 8.5 / 14.5% vs 8.8 / 15.3%; 2021-25 a wash ($47 vs $48, $35 vs $35). Asap ($250) gets the first payout 1-2 sessions sooner but $4-14 a month less than today's line; a $300 / $500 cushion costs $11-39 a month for at most 1.8 points less lost; waiting for best day <= 40% is the worst ($24-74 a month less).
runs: none (research/lab/payout25.json, tools/money/payout25.py)
---

## For the owner

**Ask for the full $1,000 each time** (wait until the balance is **$27,100** = start + $1,100 buffer + $1,000, with 2 traded
days and no day over half the cycle). After it the balance is $26,100, the floor sits at $25,100: $1,000 of room again.

| Funded 25K, 6 months (Jan-Jun / **Jul-Oct** / 2021-25) | $ a month to you | 1st payout (trading days) | No payout in 6 m | Account lost |
|---|---|---|---|---|
| **Ask at the $1,000 max (pick)**, ATLAS alone | $594 / **$498** / $47 | 20 / **28** | 5.0 / **6.2** / 79.5% | 5.3 / **6.3** / 93.0% |
| Today's line ($750 above the buffer), ATLAS alone | $592 / **$497** / $48 | 18 / **26** | 5.0 / **5.5** / 78.2% | 5.7 / **7.3** / 93.2% |
| Asap ($250 allowed), ATLAS alone | $581 / **$487** / $49 | 17 / **24** | 4.8 / **5.2** / 77.2% | 6.0 / **7.3** / 93.0% |
| **Ask at the $1,000 max (pick)**, LIT + ATLAS $250 | $602 / **$535** / $35 | 15 / **20** | 7.5 / **12.3** / 82.3% | 8.5 / **14.5** / 91.5% |
| Today's line, LIT + ATLAS $250 | $599 / **$529** / $35 | 14 / **18** | 7.5 / **12.2** / 81.8% | 8.8 / **15.3** / 91.3% |

First payout dates from a first funded trade on Thu 2026-11-19 (the median path): ATLAS alone with the pick about **Dec 16**
(Jan-Jun pace) / **Dec 29** (Jul-Oct pace); LIT + ATLAS $250 about Dec 9 / Dec 16. The money is small either way: the
choice of WHEN to ask moves less than $15 a month. What matters more is not breaking the account and trading every week.

## All policies (600 paths each, same paths)

ATLAS alone (H1 / H2 / REF): $ a month, 1st payout median sessions, no payout %, lost %, payouts in 6 months

| Policy | $ a month | 1st payout | No payout | Lost | Payouts |
|---|---|---|---|---|---|
| today: ask at $750 | 592 / 497 / 48 | 18 / 26 / 17 | 5.0 / 5.5 / 78.2 | 5.7 / 7.3 / 93.2 | 4.48 / 3.77 / 0.37 |
| asap: $250 | 581 / 487 / 49 | 17 / 24 / 16 | 4.8 / 5.2 / 77.2 | 6.0 / 7.3 / 93.0 | 4.50 / 3.81 / 0.39 |
| ask at $500 | 585 / 493 / 49 | 17 / 25 / 16 | 5.0 / 5.3 / 77.3 | 6.0 / 7.7 / 93.2 | 4.49 / 3.78 / 0.38 |
| **ask at $1,000 (max)** | **594 / 498 / 47** | 20 / 28 / 20 | 5.0 / 6.2 / 79.5 | **5.3 / 6.3** / 93.0 | 4.46 / 3.74 / 0.35 |
| cushion $300 | 565 / 473 / 45 | 17 / 25 / 16.5 | 5.0 / 5.3 / 77.3 | 5.3 / 7.0 / 91.7 | 4.51 / 3.79 / 0.39 |
| cushion $500 | 554 / 458 / 40 | 18 / 26 / 17 | 5.0 / 5.5 / 78.2 | 5.0 / 6.0 / 92.0 | 4.51 / 3.79 / 0.38 |
| consistency <= 40% | 556 / 423 / 37 | 21 / 29 / 22 | 5.0 / 6.0 / 81.8 | 5.0 / 6.5 / 91.5 | 4.19 / 3.25 / 0.28 |
| cycle-timed ($1,000 on day 2, -$250 a day) | 581 / 487 / 49 | 17 / 24 / 16 | 5.0 / 5.2 / 77.2 | 6.0 / 7.3 / 93.0 | 4.49 / 3.81 / 0.39 |

LIT + ATLAS $250 (H1 / H2 / REF)

| Policy | $ a month | 1st payout | No payout | Lost | Payouts |
|---|---|---|---|---|---|
| today: ask at $750 | 599 / 529 / 35 | 14 / 18 / 20 | 7.5 / 12.2 / 81.8 | 8.8 / 15.3 / 91.3 | 4.51 / 4.00 / 0.27 |
| asap: $250 | 595 / 515 / 35 | 14 / 16 / 20 | 7.5 / 12.2 / 81.7 | 8.8 / 15.5 / 91.3 | 4.51 / 4.02 / 0.27 |
| ask at $500 | 597 / 524 / 35 | 14 / 17 / 20 | 7.5 / 12.2 / 81.7 | 8.8 / 15.5 / 91.3 | 4.51 / 4.00 / 0.27 |
| **ask at $1,000 (max)** | **602 / 535 / 35** | 15 / 20 / 21.5 | 7.5 / 12.3 / 82.3 | **8.5 / 14.5** / 91.5 | 4.52 / 4.01 / 0.26 |
| cushion $300 | 588 / 515 / 34 | 14 / 17 / 20 | 7.5 / 12.2 / 81.7 | 8.5 / 14.3 / 91.5 | 4.52 / 4.05 / 0.27 |
| cushion $500 | 580 / 510 / 33 | 14 / 18 / 20 | 7.5 / 12.2 / 81.8 | 8.3 / 13.5 / 91.2 | 4.53 / 4.06 / 0.27 |
| consistency <= 40% | 575 / 476 / 22 | 19 / 22 / 30.5 | 7.5 / 12.7 / 86.7 | 8.0 / 14.7 / 89.7 | 4.33 / 3.62 / 0.17 |
| cycle-timed | 595 / 515 / 35 | 14 / 16 / 20 | 7.5 / 12.2 / 81.7 | 8.8 / 15.5 / 91.3 | 4.51 / 4.02 / 0.27 |

Pick rule (written before the run): on H1 the most $ a month with no more lost (+0.5 points) and at most +2 points of
no-payout vs today; it must also not lose $ vs today on H2 with the same guards. "Ask at $1,000 (max)" wins H1 for both mixes
and holds on H2. The margins are within Monte Carlo noise for the $ (a few dollars); the lost-account drop (0.3-1.0 points)
is consistent across both halves and both mixes.

## Why

* Each request uses one of the **5 sim payouts** (after the 5th MFFU moves the account to live). A small request burns one
  for less money; waiting for the full $1,000 means fewer, bigger payouts and more room on the account in between.
* The floor locks at **$25,100** after the first payout. Taking $1,000 from $27,100 leaves $1,000 of room; taking $300 from
  $26,400 leaves $1,000 too, but the next cycle then starts from a lower balance with the same lock.
* Cushions keep extra room, but the funded sizing (60% of the room, at most $750 a trade) already shrinks near the floor, so
  the extra $300-$500 left on the account buys little safety (at most 1.8 points less lost) and delays the money.
* Waiting for the best day at 40% instead of MFFU's 50% only delays requests that MFFU would approve.

## Notes

* "Account lost" here = the floor hit **or** the account stuck under $100 of room at month 6 (the bot stops trading it then).
  research/writeups/funded25-lit-atlas-2026-11-17.md counted only floor hits (0%); the paths are the same.
* 2021-25 (the reference years with no clear edge): every policy pays about $35-49 a month and loses 90%+ of accounts; the
  policy does not save a bad market.
* $ a month counts sim payouts only, 80% to you, before tax (move 30% to the tax pot: net about 56% of each request).
* The 7-day inactivity rule (no trade in 7 calendar days wipes the profits) is not in the paths (the bot trades most
  days); the payout coach counts it down.
* Today's bot push (engine/funded_life builder25k ask_above $750) still says PAYOUT READY at $750 above the buffer; the coach
  (engine/payout_coach.py, My Accounts / Board) shows "MFFU would pay $X today; the plan waits for the full $1,000". Changing
  the push line to $1,000 is a one-number change for the lead (`PLANS["builder25k"]["ask_above"]`) if the owner says yes.

    python -X utf8 tools/money/payout25.py --n 600        # ~90 s, writes research/lab/payout25.json
