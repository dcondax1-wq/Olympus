---
title: ATLAS more money (2026-11-19) - 10 pre-registered ideas on the funded 25K from today's $887 room; one small safe winner (keep trading 1 micro instead of giving the account up at $100), ATLAS v2 hunts make more $ but break the rules
family: risk
date: 2026-11-19
status: one adopt-candidate on the Decide card (atlas-funded-keep-trading: account_b "min_room" 0, built key, owner yes/no). 9 ideas rejected. Nothing live changed (second_model.json, data/account_b.json, live_model*.json untouched).
summary: Owner - "improve all of our strategies, there's things we can do to make more". ATLAS alone on the FUNDED MFFU Builder 25K ($24,887, $887 room). Design pre-registered and committed before any run (research/second/atlas_more_design.md). Scoring = tools/atlas_health.py's funded Monte Carlo (600 week-block paths x 126 sessions, MFFU Builder 25K funded rules, live funded preset size, live $100 stuck stop, costs in) from TODAY's account, a fresh start and the real day order, plus the fixed $250 view and a paired week-block bootstrap. Winner - A1 no stuck stop (keep trading whenever 1 micro's full stop-out still fits the room): +$10 / +$3 / +$4 a month (Jan-Jun / Jul-Oct / 2021-25-like), lost in 6 months 9.8 -> 7.7% / 10.5 -> 9.5% / 94.8 -> 94.0%, first payout unchanged (19 / 27 sessions), pays less on 0 of 600 paths in every span. ATLAS v2 (hunts x0.5) on the funded account: +$51 / +$93 / +$18 a month but 4.5-4.7 trades a week (rule 2-4), more lost accounts in a Jul-Oct market (10.5 -> 12.2%), Jan-Jun fixed $ lower, and the hunts were flat on the fresh 5 weeks (-1.1R / 0R): not switched on. Thin-room sit-outs and a tier-1 news exit lose Jul-Oct money. Fresh check Oct 19 - Nov 19 (members re-run by engine/second.run on the new bars): ATLAS 17 trades, PF 1.99, +$2,101 at $250 a trade (+11.3R): working.
runs: none (research/second/atlas_more.json, atlas_more_diag.json, atlas_more_fresh.json; tools/atlas_more.py)
---

## For the owner (one minute)

| What | Result |
|---|---|
| Is ATLAS still working? | **Yes.** Re-run on the new bars Oct 19 - Nov 19: 17 trades (3.5 a week), PF 1.99, **+$2,101 at $250 a trade**. EMA +7.5R, MACD +2.8R, S/R -1.1R. Your first funded day (-$113, a MACD short stopped on Nov 18) is in it, same trade |
| The one winner | **Don't give the funded account up at $100 of room.** Today the bot stops ATLAS for good there. Letting it keep taking 1-micro trades that still fit rescues about 1 in 5 of those accounts in a 2026-like market. **+$10 / +$3 / +$4 a month**, lost in 6 months **9.8 -> 7.7%** (Jan-Jun-like), **10.5 -> 9.5%** (Jul-Oct-like). Never pays less on any of the 600 test paths. Small money, no downside |
| ATLAS v2 (the 2 stop hunts at half size) | **More $ on paper (+$51 / +$93 a month), but no.** 4.5-4.7 trades a week (your rule: 2-4), more lost accounts in a Jul-Oct market (10.5 -> 12.2%), and on the fresh 5 weeks the hunts did nothing (-1.1R and 0R). It also cannot be routed yet (Asia hours + a limit order) |
| A member that sits out while the room is thin | **No.** "Only MACD under $500" or "EMA out under $500": -$24 to -$25 a month in Jul-Oct and more lost accounts |
| Flat before CPI / jobs / FOMC (LIT-style news rule) | **No.** Cuts 25 trades, -$82 a month in Jul-Oct (the London trades that run into 08:30 are often the big winners) |
| VIX band | Already there: EMA and MACD use it; S/R's VIX band was tested and rejected in its own research |
| Order of payouts | Already measured (payout-policy-funded25-2026-11-17.md): asking $1,000 vs the $750 ping is within $10 a month; that card is open |

Your step if you want it: answer the Decide card "ATLAS's funded 25K: keep trading 1 micro under $100 of room?".

## How it was scored
- Trades: the live ATLAS units (no hedging vs LIT incl. its armed setups, one position, max 2 a day), 2021-11 .. 2026-10-16.
- Money: MFFU Builder 25K funded rules, the live funded preset (60% of the room, $50-$750, ref stop 20, winner <= $1,000,
  $600 soft loss, 20 micros, full stop-out must fit the room), 600 Monte Carlo paths of 5-session blocks (= a week-block
  bootstrap) x 126 sessions; H1 = 2026 Jan-Jun, H2 = Jul 1 - Oct 16, REF = 2021-11 .. 2025. From TODAY's account
  (-$113, room $887), from a fresh start, and on the real day order. Base reproduces atlas_health.json exactly
  ($581 / $491 / $45 fresh, $572 / $480 / $40 from today).
- Gate G1-G10 as pre-registered (money, a real gain or -1 point lost, safety, speed, 2-4.1 trades a week, real order,
  fixed $250 view for trade-changing ideas, acts in Jul-Oct, random controls for timing rules, bootstrap interval).

## The 10 ideas (14 variants), $ a month to you from TODAY's account

| Idea | Jan-Jun-like | Jul-Oct-like | 2021-25-like | 1st payout (sessions) | Lost in 6 months | Verdict |
|---|---|---|---|---|---|---|
| **Today** | **$572** | **$480** | **$40** | 19 / 27 | 9.8 / 10.5 / 94.8% | bar |
| **A1 no stuck stop** | **$582** | **$483** | **$44** | 19 / 27 | **7.7 / 9.5 / 94.0%** | **PASS** (bootstrap 90%: +$5..+15 / +$1..+6 / +$2..+6) |
| A2 stuck at $50 | $581 | $483 | $43 | 19 / 27 | 7.8 / 9.7 / 94.3% | passes too (same finding, A1 cleaner) |
| A3 thin room < $500: only MACD | $566 | $456 | $39 | 20 / 28 | 7.8 / 9.7 / 93.0% | no: Jul-Oct -$24, no-payout up |
| A3 neighbours $300 / $700 | $576 / $561 | $474 / $417 | $40 / $40 | | 7.8 / 11.3; 5.7 / 7.8 | no |
| A4 thin room < $500: EMA out | $558 | $455 | $42 | 19 / 27 | 11.2 / 15.3 / 94.2% | no: less $, more lost |
| A4 neighbours $300 / $700 | $571 / $571 | $467 / $427 | $42 / $42 | | 9.5 / 13.7; 8.5 / 17.2 | no |
| A5 no stuck stop + 40% of room | $588 | $476 | $45 | 22 / 34 | 5.3 / 5.2 / 92.0% | no: first payout +3 / +7 sessions |
| B1 ATLAS v2 hunts x0.5 | $623 | $573 | $58 | 18 / 19 | 4.3 / **12.2** / 94.0% | no: 4.5-4.7 trades/wk, Jul-Oct lost up, H1 fixed $ down |
| B2 v2 as built (+ min_room $200) | $591 | $546 | $51 | 18 / 19 | 9.7 / **16.8** / 94.8% | no |
| B3 + Asia hunt x0.5 only | $637 | $491 | $53 | 18 / 24 | 2.5 / **18.0** / 93.3% | no: Jul-Oct lost 18% |
| C1 flat 3 min before CPI / jobs / FOMC | $580 | $398 | $38 | 19.5 / 32 | 8.7 / 14.8 / 95.3% | no: -$82 Jul-Oct |
| C2 the same unless +1R already | $572 | $433 | $39 | 19 / 30 | 9.8 / 13.2 / 95.0% | no: -$47 Jul-Oct |

Fixed $250 view (proof table; A ideas change no trade, so A1 = today): trades a week / PF / net $ / $ a month / max DD
- Today = A1: Jan-Jun 4.06 / 2.92 / $18,362 / $3,012 / -$1,062; Jul-Oct 2.95 / 2.55 / $5,256 / $1,415 / -$876; 2025 4.30 /
  1.17 / $4,466 / $364 / -$4,871; 2021-24 4.71 / 1.06 / $5,927 / $152 / -$11,403.
- B1: 4.53 / 3.04 / $17,391; 4.68 / 2.47 / $5,448; 2025 5.97 / 1.14 / $3,724; 2021-24 6.68 / 1.14 / $12,978.
- C1: 4.06 / 2.95 / $18,188; 2.95 / 2.21 / $4,095; 2025 $3,551; 2021-24 $5,685 (25 trades cut, 1 blocked).

**A1 in detail.** Of the funded accounts today's rule strands (9.8% / 10.5% / 94.8% of paths from today's account), A1
keeps 22% / 9.5% / 0.9% alive and 15% / 9.5% / 1.9% of them reach a payout they never would; the rest find no trade that
fits for 5 sessions and are counted dead (MFFU closes an account after 7 days without a trade). It pays more on 13 /
6 / 12 of 600 paths and less on 0 (paired sign test p 0.0001 / 0.016). Real day order: the same $ (no 2026 start was
stranded). Live: the built key `"min_room": 0` in data/account_b.json; the funded size rule already refuses any trade
whose 1-micro full stop-out would not fit the room, so it can never touch the floor on a stop. Caveat: a stranded
account still uses one of the 2 funded Builder 25K places until you close it.

## ATLAS v2: switch it on? (honest numbers)
- On the funded account it is the only idea with real $: +$51 / +$93 / +$18 a month from today's account, real day order
  Jul-Oct $856 vs $283.
- It fails the rules: 4.5-4.7 trades a week (2-4), lost accounts in a Jul-Oct market 10.5 -> 12.2% (fresh start 9.2 ->
  10.7%), real order Jan-Jun 3.8% lost (today 0%), Jan-Jun fixed $ $18,362 -> $17,391. The built `min_room` 200 is an EVAL
  rule: on the funded account it strands more (16.8%).
- The hunts' own rules were picked partly on 2021-25 (only 2026 H2 was clean), and on the fresh 5 weeks they made -1.1R
  (trend hunt, 6 trades) and 0R (Asia hunt, 2 trades); ATLAS + hunts x0.5 there: +$1,928 vs +$2,101 without.
- It cannot be routed today (account B: market orders at the 5m open, no 18:00-02:00 entries, candidates refused).
- Verdict: keep it OFF; the paper shadow keeps counting.

## Members re-checked ($250 a trade, costs in, on the account)

| Member | Jan-Jun | Jul-Oct | 2025 | 2021-24 | Fresh Oct 19 - Nov 19 |
|---|---|---|---|---|---|
| EMA | 1.99/wk PF 2.58 $1,207/mo | 1.28/wk PF 4.93 $1,064/mo | 2.05/wk PF 0.96 -$42/mo | 2.16/wk PF 1.05 $53/mo | 9 trades PF 2.13 +$1,117 |
| MACD | 1.05/wk PF 3.30 $1,147/mo | 0.77/wk PF 1.88 $257/mo | 1.18/wk PF 1.51 $337/mo | 1.34/wk PF 1.11 $93/mo | 6 trades PF 1.65 +$654 |
| S/R | 1.02/wk PF 3.18 $659/mo | 0.90/wk PF 1.27 $95/mo | 1.07/wk PF 1.12 $68/mo | 1.21/wk PF 1.01 $6/mo | 4 trades PF 0.87 -$68 |
| Asia hunt (own) | PF 2.75 $562/mo | PF 1.19 $173/mo | PF 1.50 $380/mo | PF 1.26 $246/mo | 2 trades $0 |
| Trend hunt (own) | PF 2.02 $399/mo | PF 2.59 $645/mo | PF 1.68 $447/mo | PF 1.43 $291/mo | 6 trades PF 0.68 -$186 |

No member to drop: each is positive in every span except EMA in 2025 (-$42/mo); S/R is the weakest since July (dropping it
was rejected 2026-11-17: Jan-Jun $592 -> $417 a month). MACD has the best R a trade in every span.
The armed-setup block (no ATLAS entry while LIT has a setup armed the other way) costs nothing: without it 1-2 more trades
in 2026 and the funded $ is LOWER ($586 / $487 -> $582 / $462 from today, 300 paths). Keep it (it is a safety rule).

## Multiple testing and limits
- 10 ideas, 14 variants (A3 / A4 with 2 neighbours). 2 pass (A1, A2): one finding (the stuck line), not two.
- G9 random controls were not needed (no timing / state idea passed G1-G8 + G10).
- The paired sign test was added after the main run; its counts come from the stored path shares (the re-run was lost
  in a container restart; the numbers are the same 600 paths).
- The Lab's many-tests bar (0.2 / all cells searched) is stricter than p 0.016 in Jul-Oct: the Lab will keep A1 below
  READY; it is a dominance result (never worse on any path), not a selection among many tries.
- The fresh 5 weeks are 24 sessions and the LIT no-hedge block is not applied there (approximate).

## Decide card (added: atlas-funded-keep-trading)
"ATLAS's funded 25K: keep trading 1 micro when the room drops under $100, instead of stopping for good?" +$3 a month in a
Jul-Oct-like market (+$10 Jan-Jun-like, +$4 2021-25-like); lost in 6 months 10.5% -> 9.5% (9.8% -> 7.7% Jan-Jun-like);
first payout unchanged. Recommend yes.

Files: `research/second/atlas_more_design.md` (pre-registration, committed first), `tools/atlas_more.py` (fresh, diag,
ideas, control, register), `research/second/atlas_more.json` / `_diag.json` / `_fresh.json`, ZEUS Lab kind `atlas_more`
(tools/zeus_lab.py). Rerun (~2 min + queue): `python -X utf8 tools/atlas_more.py fresh` then `diag` then `ideas`.
