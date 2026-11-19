---
title: ATLAS health (2026-11-18) - the AMBER light is a calm-market dip, not a broken member; 17 protective rules (+5 post-hoc) for the funded 25K tested, none passes; the account's real risk is getting stranded under $100 of room
family: risk
date: 2026-11-18
status: nothing to switch, no Decide proposal. The 5 rule families are in the ZEUS Lab as kind atlas_funded (all Rejected). second_model.json, data/account_b.json, live_model*.json and every engine file untouched.
summary: ATLAS's edge light went AMBER (its last 40 sessions to Oct 16; the card shows the old eval-sized $ PF 1.41 vs a 2026 median 2.86). At a fixed size those 40 sessions were still +8.0R (PF 1.89, 3 trades a week) and the equity was only 1R under its high - ATLAS made less, it did not lose. No member is broken (S/R made the least: +0.3R on 7 trades; no member's own last 10 or 20 trades are under PF 1). The cause is the calmest market of the year: every session Aug 24 - Oct 16 had a prior VIX close under 18 (Jan-Jun: 54% were 18+) and NQ's RTH range was 1.05% (Jan-Jun 1.46%), so ATLAS's VIX-band targets shrank. Such a dip is normal for 2026 (26% of Jan-Jun's 40-session windows were as weak; Jan-Feb 2026 was worse and came back to PF 3+ by March) but would be a GOOD stretch by ATLAS's 2021-25 standard (median PF 1.0-1.2). Since Oct 19 the calm has ended (VIX 17-28, RTH range 1.74%) and the PC's paper trades to Nov 6 made +8.6R on 11 trades: with them the light would read GREEN. 17 pre-declared protective rules + 5 post-hoc neighbours on the funded 25K Monte Carlo (MFFU Builder 25K funded rules, 600 paths, from a fresh start and from today's -$113, real day order, fixed $250 view, random-timing controls): none passes. Day loss caps, skips and light-based sizes cost $18-191 a month in a Jul-Oct market or slow the first payout; the member pause passes the money / safety gate only because it never acts in Jul-Oct (Jul-Oct cannot check it). Found on the way: the live bot stops ATLAS for good once the funded room is under $100, and at today's 60%-of-the-room size that strands about 1 funded 25K in 11 within 6 months in a 2026-like market (0 of 42 on the real 2026 day order) and about 19 in 20 in a 2021-25-like market; the older funded tools showed 0% lost because they let it keep trading 1 micro. Risking 40% of the room halves the 2026 stranding at the same $ a month but the first payout comes 2-6 sessions later, so it fails the speed test.
runs: none (research/second/atlas_health.json, atlas_health_diag.json; tools/atlas_health.py)
---

## For the owner (one minute)

| What | Result |
|---|---|
| Is ATLAS broken? | **No.** At a fixed size its last 40 sessions to Oct 16 made **+8.0R** (PF 1.89, 3 trades a week), only 1R under its best. It made less money, it did not lose money. The "PF 1.41" on the card is the old eval sizing (losers had 4-6 micros, winners 1-2); your funded account sizes by its room, not like that |
| Which member? | **None is broken.** S/R made the least (+0.3R on 7 trades), EMA +3.5R, MACD +4.2R. No member's own last 10 or 20 trades are under PF 1, on Oct 16 or on Nov 6 |
| Why weaker | **The calmest market of the year.** Aug 24 - Oct 16: VIX under 18 every single day (Jan-Jun: half the days were 18+), NQ's daily range 1.05% (Jan-Jun 1.46%). ATLAS's targets grow with the VIX, so its winners were smaller |
| Normal or not? | **Normal for 2026.** A quarter of all 40-session stretches in Jan-Jun were this weak or weaker. Jan-Feb 2026 was worse (PF 0.7-1.8) and was back to PF 3+ by March. (In 2021-25 ATLAS made almost nothing: PF 1.89 would have been one of its best stretches) |
| Since Oct 16 | **The calm has ended.** VIX 17-28, NQ ranges 1.74%. The PC's own paper trades Oct 19 - Nov 6: **+8.6R on 11 trades**; with them the light would read GREEN, just over the line (2.26 vs 2.14 R a week). Nov 9-17 has no data in the cloud; your first funded day was -$113 |
| 17 protective rules | **None passes.** Stop after a loss, day caps ($275 / $367 / a third of the room), skip the day after a loss, smaller size while AMBER / RED: each costs $18-191 a month or slows the first payout in a Jul-Oct-like market. Pausing a cold member never acts in a 2026 market, so 2026 cannot prove it |
| Hidden risk found | The bot stops ATLAS for good when the funded room falls under $100. At today's size (60% of the room a trade) that strands about **1 funded 25K in 11** within 6 months in a 2026-like market (0 of 42 on the real 2026 order), and **19 in 20** if ATLAS goes back to its 2021-25 form. Earlier studies said "0% lost" because they kept trading 1 micro |
| A smaller size (40% of the room)? | Halves that 1-in-11 to about 1 in 20, **same $ a month**, but the first payout comes **2-6 sessions later**. It fails the speed test, so it is not proposed; it is yours to ask for if safety matters more to you than speed |
| Your funded 25K from today ($887 room) | **$572 / $480 a month** to you (Jan-Jun / Jul-Oct-like markets), first payout after about 19 / 27 sessions, stranded 9.8 / 10.5% within 6 months (2021-25-like market: $40 a month, 95%) |

Your steps: none. Keep ATLAS as it is. Nothing changed.

## 1. Diagnosis (tools/atlas_health.py diag -> research/second/atlas_health_diag.json)

Trades = the live ATLAS units (tools/atlas.account_units: never opposite LIT incl. its armed setups, HEDGE close), then
ATLAS's own one position + max 2 a day, 2021-11 .. 2026-10-16 (the last day of NQ bars in the cloud). R per trade at a
fixed risk, costs in ($1.90 a micro, slippage in the stored exits). "Last 40" = Aug 24 - Oct 16.

**Members (account trades, R):**

| Member | Jan-Jun | Jul-Aug | Last 40 |
|---|---|---|---|
| EMA | 51 trades +34.0R, PF 2.45 | 12, +15.1R, PF 5.71 | 10, **+3.5R**, PF 2.33 |
| MACD | 27, +39.8R, PF 3.62 | 6, +5.2R, PF 2.75 | 7, **+4.2R**, PF 2.65 |
| S/R | 26, +21.5R, PF 3.10 | 9, +0.5R, PF 1.08 | 7, **+0.3R**, PF 1.07 |

Each member's own paper ledger (every signal, the record a member pause would watch): last-10 / last-20 PF on Oct 16
EMA 2.31 / 2.80, MACD 1.55 / 2.98, S/R 1.66 / 1.94; on Nov 6 (with the PC's paper trades) 2.56 / 1.58, 2.41 / 2.98,
2.62 / 1.93. None under 1. S/R is the flattest since July but still positive.

**Regime (the market ATLAS traded):**

| | Jan-Jun | Jul-Aug | Last 40 | Oct 19 - Nov 17 (fresh) |
|---|---|---|---|---|
| Days with prior VIX close < 15 / 15-18 / 18-22 / 22+ | 4 / 42 / 34 / 20% | 16 / 68 / 16 / 0% | **25 / 75 / 0 / 0%** | **0 / 32 / 55 / 14%** (CBOE, 22 days) |
| VIX mean | 19.4 | 16.3 | 15.6 | closes 16.6-28.2 |
| NQ RTH range, % of price | 1.46 | 1.36 | **1.05** | **1.74** (PC bars, Oct 19 - Nov 6) |
| RTH trend efficiency (1 = straight line) | 0.131 | 0.118 | 0.119 | 0.112 |

| R a trade by prior VIX | Jan-Jun | Last 40 | 2025 | 2021-24 |
|---|---|---|---|---|
| under 15 | -0.30 (4) | -0.44 (4) | -0.34 (27) | -0.10 (245) |
| 15-18 | +0.93 (47) | **+0.49 (20)** | +0.22 (111) | +0.08 (140) |
| 18-22 | +1.14 (37) | none | +0.14 (52) | +0.30 (180) |
| 22+ | +0.68 (16) | none | +0.04 (32) | -0.04 (201) |

- At Jan-Jun's +0.92R a trade the last 40 sessions' 24 trades would have made +22.0R; they made +8.0R. With Jan-Jun's R
  per trade **inside each VIX bucket** they would have made +17.3R: a third of the gap is the missing VIX 18+ days, the
  rest is smaller results on the calm-end 15-18 days (+0.49R vs +0.93R a trade, NQ ranges 1.05%). Same story either way:
  a small-range market makes small VIX-band targets.
- Day type (trend / mixed / chop by RTH efficiency): the last 40 had no trend day; chop days +0.32R a trade (Jan-Jun
  +0.73R). No bucket loses.

**Is it normal? (40-session windows, fixed-size R, every end day)**

| | Jan-Jun 2026 | Jul-Oct 16 | 2025 | 2021-24 |
|---|---|---|---|---|
| Windows | 128 | 78 | 258 | 780 |
| R-PF p10 / median / p90 | 1.05 / 2.82 / 3.64 | 1.67 / 3.09 / 5.40 | 0.50 / 1.22 / 1.83 | 0.45 / 1.01 / 1.97 |
| As weak as Oct 16 (R-PF <= 1.89) | **26.6%** | **24.4%** | 90.7% | 88.2% |
| R-PF <= 1.41 | 18.8% | 3.8% | 67.1% | 68.6% |
| Eval-sized $ PF <= 1.41 (the card's number) | 10.9% | 16.7% | 58.9% | 76.4% |
| Light GREEN / AMBER / RED | 73 / 16 / 11% | 64 / 36 / 0% | 7 / 55 / 38% | 12 / 35 / 54% |
| Next 40 sessions after a weak window: median R-PF, share positive | 3.08, 100% (vs 3.23 after any) | (no data yet) | 1.22, 72% (vs 1.19, 66%) | 0.98, 49% (vs 1.00, 50%) |

- 2026 has had two such dips: **Jan 1 - Feb 18** (the tail of a weak late 2025: R-PF 0.7-1.8), back above PF 2 by Feb 25
  and at 3+ in March; and **Sep 18 - Oct 16** (R-PF 1.5-1.9, two one-day recoveries). The current one is the milder.
- A weak window says nothing about the next one beyond the market it came from: in 2026 the next 40 sessions were as
  good as after any window; in 2021-25 they were as flat as after any window. What decides ATLAS's money is whether the
  market stays 2026-like, which the light cannot foresee (the same finding as the LIT drift switch, 0/51).

**Drawdowns at a fixed 1R a trade:** Jan-Jun deepest -5.1R (14 sessions under a high), Jul-Oct -4.9R (40 sessions), on
Oct 16 -1.0R (4 sessions since its high). 2025: -22.9R, 162 sessions. 2021-24: -50.7R, never back to its 2022 high
(618 sessions). So the 2026 dip is shallow; a 2021-25-like spell is what would hurt.

## 2. What the missing data after Oct 16 may hide

- **Known:** VIX (CBOE's free daily file) Oct 19 - Nov 17: 0 days under 15, 55% at 18-22, 14% at 22+. The PC's NinjaTrader
  bars to Nov 6: NQ ranges 1.74%. The members' own PC paper trades Oct 19 - Nov 6 (heartbeat branch, before the account
  rules): EMA 6 trades +1.7R, MACD 3 +5.9R, S/R 2 +1.0R = **+8.6R, PF 2.19**, but only 3 winners in 11 (two big ones: EMA
  +5.8R on Oct 20, MACD +8.0R on Oct 27); by prior VIX: 18-22 six trades +13.7R, 15-18 four trades -4.1R, 22+ one -1.0R.
  Appended to the account record (one position, max 2 a day) the light on Nov 6 is GREEN: 25 trades, R-PF 2.72,
  2.26 R a week (line 2.14). Approximate: LIT's no-hedge block is not applied to those trades.
- **Unknown:** Nov 9 - Nov 17 (7 sessions): no bars and no ATLAS trades anywhere in the cloud (PC silent, no data branch
  on the backup yet; the new channel `python tools/data_pull.py --latest --edge` works once the PC has updated). Nov 18:
  the funded account's first live day, -$113 (one trade says nothing).
- **The caution:** the November VIX closes of 22.9-28.2 (Nov 5-6, Nov 16-17) are a fear market. In 2021-24 ATLAS made -0.04R a trade on 201
  trades at VIX 22+ (2025 +0.04R on 32; Jan-Jun 2026 +0.68R on 16). If VIX stays above 22 for weeks, ATLAS's history says
  flat, not spring-like. Its best bucket in every span is VIX 18-22.

## 3. Protective rules on the funded 25K (tools/atlas_health.py rules -> research/second/atlas_health.json)

**How it was scored.** The MFFU Builder 25K funded rules of tools/uprisk.Funded (= engine/funded_life builder25k: $1,000
EOD trailing floor locked at start + $100, payouts above the $1,100 buffer, $250-$1,000 a request, 80% to you, 50%
consistency, 2 traded days a cycle, 48 h first wait, 5 payouts), ATLAS alone at the live funded preset size (engine/
account_b.funded_qty: risk 60% of the room, $50-$750, a winner at most $1,000, the $600 soft daily loss, 20 micros), on
the 600 Monte Carlo paths of tools/money/funded25.py (126 sessions, 5-session blocks; H1 = 2026 Jan-Jun, H2 = Jul-Oct 16,
REF = 2021-11..2025). One addition: the live bot's **stuck stop** (engine/account_b MIN_ROOM: under $100 of room = no new
trade, "buy a new eval"); "dead" = floor touched or stuck. Without the stuck stop the "today" row reproduces
funded25.py exactly ($592 / $497 / $48, first payout 18 / 26 / 17, no payout 5.0 / 5.5 / 78.2%). Every rule is also run
from **today's account** (balance -$113, room $887), on the **real day order** (a funded start every 5 sessions, 126
sessions or to Oct 16: 26 / 16 / 216 starts) and in the **fixed view** (every trade at $250, real days, costs in).

**Pre-declared** (in the tool's docstring before the first run): 17 versions in 5 families (16 new + the VIX < 15 re-measure). **Gate**: the family's
Jan-Jun pick (most funded $ a month in Jan-Jun) must keep the funded $ a month (H1 / H2 >= today - $10, REF >= today -
$5), have no more dead accounts in any span and 1 point fewer in one, first payout <= +1 session and no payout <= +0.5
point in both halves, 2-4.1 trades a week, the same from today's account, the same on the real order, beat 90% of 40
random-timing controls (timing rules), and, the project rule, **act in Jul-Oct** (else Jul-Oct cannot check it).

Funded 25K, $ a month to you / median first payout (sessions) / no payout in 6 months / dead in 6 months:

| Rule | Jan-Jun market | Jul-Oct market | 2021-25 market | From today ($887 room): H1 / H2 / REF $ and dead | Verdict |
|---|---|---|---|---|---|
| **ATLAS today** | **$581 / 18 / 7.3% / 8.5%** | **$491 / 25 / 7.0% / 9.2%** | **$45 / 16 / 79.8% / 94.5%** | $572 9.8% / $480 10.5% / $40 94.8% | bar |
| M1 member last-10 PF < 1 -> paper | $572 / 20 / 6.8 / 8.5 | $300 / 34.5 / 16.7 / 20.7 | $36 / 34.5 / 79.3 / 88.8 | $562 / $290 / $33 | no: Jul-Oct -$191 |
| M2 member last-20 PF < 1 -> paper | $582 / 18 / 6.7 / 8.3 | $491 = | $46 / 33 / 74.8 / 88.3 | $573 / $480 / $38 | never acts in Jul-Oct |
| **M3 member last-20 PF < 1 -> x0.5 (M pick)** | $590 / 18 / 6.5 / 7.7 | $491 = (0 trades changed) | $50 / 24 / 75.7 / 90.5 | $586 / $480 / $46 | **never acts in Jul-Oct** |
| L1 AMBER x0.75, RED x0.5 | $582 / 19 / 5.8 / 7.2 | $473 / 28 / 7.0 / 9.7 | $48 / 38.5 / 75.0 / 87.5 | $574 / $462 / $43 | no: Jul-Oct -$18, slower |
| L2 AMBER x0.5, RED x0.5 | $592 / 19.5 / 5.0 / 6.3 | $452 / 29 / 7.2 / 10.7 | $44 / 44 / 76.3 / 83.2 | $585 / $444 / $39 | no: Jul-Oct -$39 |
| L3 RED -> paper | $544 / 19 / 9.5 / 11.3 | $491 = (no RED day) | $47 / 37 / 75.7 / 80.8 | $535 / $480 / $44 | no: Jan-Jun -$37 |
| L4 AMBER x0.5, RED -> paper | $558 / 20 / 7.0 / 8.7 | $452 / 29 / 7.2 / 10.7 | $35 / 58 / 78.7 / **65.0** | $553 / $444 / $30 | no: -$23 / -$39 / -$10 |
| L5 last-40 R-PF < 1.5 -> x0.5 (L pick) | $597 / 19 / 5.0 / 6.2 | $453 / 28 / 7.7 / 10.7 | $45 / 39 / 77.2 / 87.5 | $591 / $441 / $40 | no: Jul-Oct -$38, more dead |
| D1 no new trade after a losing trade | $505 / 21 / 11.0 / 14.5 | $354 / 31 / 15.8 / 20.2 | $40 / 22.5 / 80.7 / 92.7 | $495 / $341 / $37 | no: -$76 / -$137 |
| D2 day cap $275 (25% of the buffer) | $537 / 20 / 8.8 / 11.7 | $453 / 27 / 9.5 / 11.2 | $40 / 30 / 79.2 / 90.7 | $528 / $442 / $35 | no: -$44 / -$38 |
| D3 day cap $367 (a third of the buffer) | $562 / 18 / 7.8 / 10.0 | $461 / 25 / 10.5 / 12.7 | $41 / 20.5 / 79.7 / 92.8 | $552 / $450 / $36 | no: -$19 / -$30 |
| D4 day cap = a third of the room (D pick) | $572 / 19 / 6.0 / 5.8 | $448 / 26 / 12.3 / 6.3 | $43 / 26 / 79.3 / 91.0 | $568 / $430 / $39 | no: Jul-Oct -$43, no payout 12.3% |
| S1 40% of the room while under the start | $581 / 18 / 7.3 / 8.7 | $489 / 26 / 7.2 / 9.0 | $45 / 18 / 79.2 / 94.7 | $577 / $479 / $41 | no: no fewer dead |
| S2 30% of the room while under the start | $582 / 18 / 6.8 / 8.3 | $483 / 27 / 7.7 / 9.3 | $47 / 20 / 78.0 / 94.0 | $576 / $477 / $42 | no: no fewer dead |
| **S3 40% of the room always (S pick)** | $588 / **20** / 5.2 / **5.8** | $485 / **31** / 4.2 / **4.5** | $48 / 22.5 / 78.3 / 92.5 | $583 6.7% / $473 6.0% / $42 | **no: first payout +2 / +6 sessions** |
| K1 skip prior VIX < 15 (re-measure, post-hoc) | $591 / 18 / 6.2 / 7.3 | $581 / 23 / 1.2 / 1.3 | $47 / 27.5 / 77.3 / 87.3 | $582 / $575 / $41 | passes the gate but post-hoc (see below) |
| K2 skip the session after a losing day (K pick) | $559 / 21 / 6.2 / 7.7 | $334 / 35 / 15.2 / 18.0 | $44 / 20 / 78.0 / 91.3 | $549 / $323 / $39 | no: -$22 / -$157 |
| *post-hoc: K1 at VIX 14.5 / 15.5 / 16* | $581 / $587 / $574 | $543 / $490 / **$330** | $48 / $38 / $34 | | knife edge |
| *post-hoc: S4 50% of the room always* | $584 / 19 / 6.5 / 7.7 | $492 / 28 / 5.7 / 6.0 | $47 / 18 / 79.0 / 93.8 | $575 / $483 / $41 | first payout +1 / +3 |
| *post-hoc: S5 40% while under its best day-end balance* | $589 / 19 / 5.2 / 6.0 | $487 / 30 / 5.0 / 5.7 | $46 / 20 / 78.7 / 93.0 | $583 / $482 / $43 | first payout +1 / +5 |

Real day order (funded starts every 5 sessions; Jul-Oct starts have at most 77 sessions of data, so their $ a month is
mostly payout speed): today $626 / $283 / $53 a month, dead 0 / 0 / 92.6%; M3 $626 / $283 / $64, 0 / 0 / 88.0%; S3
$619 / $187 / $67, 0 / 0 / 86.1%; L4 $593 / $141 / $49, 0 / 0 / 56.5%; K1 $679 / $436 / $56, 0 / 0 / 84.3%.

Fixed view (every trade at $250 x the rule's size, real days in order, costs in): trades a week / PF / net $ / $ a month
/ max drawdown. D4 and S1-S5 change only funded sizes, so their fixed view is today's.

| Rule | Jan-Jun | Jul-Oct 16 | 2025 | 2021-11..2024 |
|---|---|---|---|---|
| ATLAS today | 4.06 / 2.92 / $18,362 / $3,012 / -$1,062 | 2.95 / 2.55 / $5,256 / $1,415 / -$876 | 4.30 / 1.17 / $4,466 / $364 / -$4,871 | 4.71 / 1.06 / $5,927 / $152 / -$11,403 |
| M1 | 3.28 / 2.90 / $15,136 / $2,483 / -$1,071 | 2.56 / 1.98 / $3,331 / $897 / -$962 | 2.03 / 1.35 / $4,221 / $344 / -$2,543 | 2.33 / 1.10 / $5,126 / $131 / -$9,139 |
| M2 | 3.24 / 3.16 / $17,695 / $2,903 / -$1,290 | = today | 2.79 / 1.19 / $3,204 / $261 / -$3,802 | 2.68 / 1.18 / $9,956 / $255 / -$9,271 |
| M3 | 4.02 / 3.05 / $17,972 / $2,949 / -$1,195 | = today | 4.13 / 1.16 / $3,471 / $283 / -$4,083 | 4.57 / 1.11 / $7,663 / $196 / -$9,199 |
| L1 | 3.83 / 3.02 / $16,442 / $2,697 / -$1,074 | 2.95 / 2.63 / $4,922 / $1,325 / -$876 | 4.17 / 1.04 / $700 / $57 / -$3,686 | 4.58 / 1.11 / $6,775 / $174 / -$6,285 |
| L2 | 3.75 / 3.10 / $15,812 / $2,594 / -$1,062 | 2.63 / 2.26 / $3,650 / $983 / -$995 | 3.88 / 1.02 / $265 / $22 / -$3,052 | 4.44 / 1.01 / $303 / $8 / -$7,144 |
| L3 | 3.55 / 2.94 / $16,606 / $2,724 / -$1,723 | = today | 2.66 / 0.96 / -$699 / -$57 / -$5,017 | 2.28 / 1.34 / $15,192 / $390 / -$4,020 |
| L4 | 3.48 / 3.21 / $15,796 / $2,592 / -$1,062 | 2.63 / 2.26 / $3,650 / $983 / -$995 | 2.36 / 0.79 / -$1,826 / -$149 / -$3,397 | 2.14 / 1.16 / $4,388 / $113 / -$3,937 |
| L5 | 3.83 / 3.09 / $16,664 / $2,734 / -$1,062 | 2.88 / 2.29 / $4,306 / $1,159 / -$876 | 4.01 / 1.01 / $157 / $13 / -$3,226 | 4.52 / 1.08 / $4,452 / $114 / -$5,848 |
| D1 | 3.44 / 2.70 / $14,039 / $2,303 / -$1,222 | 2.56 / 2.25 / $3,760 / $1,012 / -$835 | 3.76 / 1.06 / $1,552 / $126 / -$6,499 | 3.94 / 1.10 / $8,235 / $211 / -$11,336 |
| D2 | 3.67 / 2.80 / $15,269 / $2,505 / -$1,132 | 2.69 / 2.25 / $3,896 / $1,049 / -$953 | 3.93 / 1.08 / $1,870 / $152 / -$6,042 | 4.27 / 1.09 / $7,446 / $191 / -$10,992 |
| D3 | 3.95 / 2.85 / $16,583 / $2,721 / -$1,140 | 2.88 / 2.39 / $4,711 / $1,268 / -$1,071 | 4.26 / 1.11 / $2,931 / $239 / -$5,492 | 4.69 / 1.07 / $6,504 / $167 / -$11,214 |
| K1 (re-measure) | 3.91 / 3.12 / $18,776 / $3,080 / -$1,062 | 2.50 / 3.56 / $6,077 / $1,636 / -$808 | 3.78 / 1.27 / $6,388 / $520 / -$4,172 | 3.22 / 1.17 / $10,923 / $280 / -$9,365 |
| K2 | 3.36 / 2.87 / $14,883 / $2,442 / -$947 | 2.44 / 2.06 / $2,976 / $801 / -$1,008 | 3.06 / 1.21 / $3,877 / $316 / -$3,707 | 3.27 / 1.08 / $5,811 / $149 / -$8,681 |

(The fixed view is the proof-rule table of strategy quality; the funded rows are your money. $250 a trade with no payout
caps shows far more $ than a funded 25K can pay out: requests are $250-$1,000, above a $1,100 buffer, 50% consistency.)

**Random-timing control** (`control`, 40 draws x 300 paths: the same number of trades resized per span, at random
trades), for the four that passed the money / safety gate. Share of random draws as good, per measure:

| Rule | Jan-Jun $ | Jan-Jun dead | 2021-25 $ | 2021-25 dead | all at once |
|---|---|---|---|---|---|
| M2 last-20 -> paper | 15% | 42% | 18% | 22% | 1 / 40 |
| M3 last-20 -> x0.5 | 12% | 50% | 15% | 10% (random 93.0% vs rule 90.0% vs today 95.3%) | 0 / 40 |
| K1 VIX < 15 (post-hoc) | 5% | 10% | 35% | 2.5% | 0 / 40 |
| K1 at 14.5 (post-hoc) | (no Jan-Jun trade) | | 38% | 20% | 0 / 40 |

**Why nothing passes:**
- **Day caps, the stop-after-a-loss and the cool-off day** cut ATLAS's second trade of the day or the next day. In 2026
  those trades were good ones (ATLAS's payout days are few and big), so the account pays less and later and is stranded
  MORE often (D1 Jul-Oct 9.2 -> 20.2%), not less.
- **Size by the edge light** sizes down in Jul-Oct (AMBER 36% of its days) right before the trades that recovered: -$18 to
  -$39 a month there. Pausing on RED (L4) is the only rule that really protects a 2021-25-like account (stranded 94.5 ->
  65%) but costs money in every span ($558 / $452 / $35 vs $581 / $491 / $45).
- **The member pause (M2 / M3)** passes the money / safety gate only because it never acts in Jul-Oct: no member's last
  20 trades were under PF 1 there, so Jul-Oct cannot confirm it. Its Jan-Jun +$9 a month is within the $10 seed noise; in
  2021-25 it trims stranded accounts 94.5 -> 90.5% (+$5 a month), and random half-size cuts of the same trades already
  give 93% (it beats 85-90% of them on money and 2021-25 stranding, 50% on Jan-Jun stranding: weak). The 2026-10-30 eval test of member weights from the last 5-20
  trades was 0/24 for the same reason. Not proposed.
- **Skip VIX < 15 (the atlas-revive lead)** looks better with the stuck stop counted (stranded in Jul-Oct 9.2 -> 1.3%,
  $491 -> $581 a month, Jan-Jun +$10, 2021-25 +$2 and 94.5 -> 87.3%, random skips 0/40), but it is still post-hoc (found
  by looking at Jul-Oct; Jan-Jun has 4 such trades and cannot pick it) and a knife edge in money (Jul-Oct $543 at 14.5,
  $581 at 15, $490 at 15.5, $330 at 16). VIX has been above 16.6 every day since Oct 19, so it would change nothing now.
  It stays a lead in the Lab (atlas_skip_vix15).
- **Smaller risk (S3 40% of the room)** is the one real trade-off: 2026 stranding 8.5 / 9.2% -> 5.8 / 4.5% (from today's
  account 9.8 / 10.5% -> 6.7 / 6.0%), no payout 7.3 / 7.0% -> 5.2 / 4.2%, $ a month $581 / $491 -> $588 / $485, but the
  median first payout moves 18 / 25 -> 20 / 31 sessions (from today 19 / 27 -> 21 / 33). The pre-declared gate allows +1
  session, so it fails. 50% of the room (post-hoc) sits in between (6.0% stranded in Jul-Oct, first payout +1 / +3).
  "Only while under the start balance" (S1 / S2) changes almost nothing (stranded 8.7 / 9.0% and 8.3 / 9.3%): with a
  trailing floor the room is small after any pull-back from a run-up, not only below the start, so a smaller size has to
  apply all the time to matter.

## 4. The stranding risk in plain numbers

The bot (engine/account_b, funded stage) stops trading the funded account when its room to the floor is under $100 (1
micro no longer fits most stops; push "buy a new eval"). The room cannot come back without trading, so that account is
done. At 60% of the room a trade, two losses in a row leave 16% of the room (e.g. $887 -> $355 -> $142), a third leaves
6%. In 2026-like markets the big winners usually come first; in a 2021-25-like market (ATLAS PF 1.06-1.17 at $250 a
trade) they do not: 94.5% of funded 25Ks are stranded within 6 months (92.6% on the real 2021-25 order), with about $45 a
month paid before that. The older funded tools (funded25.py, atlas-revive) let the account trade 1 micro below $100 and
showed "lost 0%"; with the live stop the same paths give $581 / $491 / $45 a month instead of $592 / $497 / $48.

## 5. Honest limits
- 2026 is 166 sessions; the last-40 window is 24 trades; the fresh PC paper trades are 11. One big winner moves a window.
- The Monte Carlo strings 5-session blocks at random; on the real 2026 order no funded start was stranded (0 of 42), so
  the 1-in-11 is a "worse luck of the order" figure. +-$10 a month is seed noise.
- The light's cuts (2.14 / 0.17 R a week) are percentiles of ATLAS's own 2021-25 windows, so the L rules see 2021-25
  through cuts made from it (not fitted to money).
- No member re-run on the PC's bars (same as edge_health); Nov 9 - Nov 17 is missing; the Nov 6 light is approximate.

Files: `tools/atlas_health.py` (diag, rules, control, register; the ZEUS Lab runner `lab_result`),
`research/second/atlas_health_diag.json`, `research/second/atlas_health.json`, ZEUS Lab kind `atlas_funded`
(tools/zeus_lab.py, 5 families: atlas_funded_member_pause / _light_size / _day_cap / _hole_size / _skip, all Rejected).
Rerun (~8 min): `python -X utf8 tools/edge_health.py --fetch` (CBOE VIX) then `python -X utf8 tools/atlas_health.py all`.
