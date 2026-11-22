---
title: ATLAS funded 25K at real fills - room 40% now wins, keep trading (don't pause), $750 ping and the Rapid ATLAS lane stay
family: second
date: 2026-11-20
status: finding - one card flips. atlas-funded-room-40 recommend no -> YES (passes the pre-registered bar at 6 and 10 ticks). atlas-funded-keep-trading stays yes. payout-ping-1000 stays no. atlas-on-rapid stays yes. Pause / stop: no. Nothing live changed.
summary: At 10 ticks a side (ATLAS's real fills) the funded 25K from today's $887 room makes $503 / $402 / $19 a month (Jan-Jun / Jul-Oct / 2021-25-like) and is lost in 6 months 17.6 / 21.7 / 98.8% of the time. Risking 40% of the room instead of 60% gives $527 / $393 / $16 and 11.0 / 14.0 / 98.2% lost, first payout 3-8 trading days later: it passes the bar. The owner's keep-trading YES is right (the old $100 stop loses 20.3 / 23.5%). Asking at $1,000 passes narrowly on its own (16.0 / 20.7%) but adds under 1 point once room 40% is in and pays later. A 4-week pause costs $34-55 a month and is no safer; stopping is $0. Trading 1 micro for 5 weeks also passes (12.7 / 18.9%). Rapid 25K: ATLAS $250 still adds $609-1,662 a month at 10 ticks.
runs: tools/atlas_risk.py run / posthoc -> research/second/atlas_risk.json; design research/second/atlas_risk_design.md (committed e4e63c97 before any run)
---

# ATLAS's funded 25K at real fills (2026-11-20)

## For the owner (one minute)

**ATLAS's real entries fill about 10 ticks late. With that cost, 60% of the room a trade is too big for the $887 left on the
funded 25K. Say YES to "room 40%": same money, the account is lost about a third less often. Keep ATLAS trading; don't pause it.**

At real fills (10 ticks a side), from today's account, over the next 6 months:

| What | Jan-Jun-like market | Jul-Oct-like | 2021-25-like (calm) |
|---|---|---|---|
| Today (60% of the room, keep trading under $100) | $503 a month, 1st payout Dec 23, lost 17.6% | $402, Jan 7, lost 21.7% | $19, none, lost 98.8% |
| **Room 40% (card: yes)** | **$527, Dec 29, lost 11.0%** | **$393, Jan 19, lost 14.0%** | $16, none, lost 98.2% |
| Old $100 stop (before your yes) | $489, Dec 23, lost 20.3% | $396, Jan 7, lost 23.5% | $18, none, lost 98.9% |
| Ask at $1,000 instead of $750 | $511, Dec 28, lost 16.0% | $401, Jan 12, lost 20.7% | $17, none, lost 98.5% |
| Pause ATLAS 4 weeks | $469, Jan 20, lost 15.7% | $347, Feb 5, lost 22.0% | $15, none, lost 98.6% |
| Stop ATLAS (a 1-micro hand trade each week keeps it open) | $0, none, lost 0% | $0 | $0 |
| Rapid 25K with ATLAS $250 (as built) / without | $1,883 / $221 a month | $800 / $191 | -$50 / -$22 |

"Lost" mostly means the room shrinks until not even 1 micro fits and MFFU closes the account after 7 days without a trade
(2-3 in 100 actually hit the floor). In a calm 2021-25-like market ATLAS loses the funded account almost surely whatever we
do: that is the real danger, and no sizing fixes it.

**Next for you:** tap YES on "ATLAS's funded 25K: risk 40% of the room" on the Decide card. Claude then changes the funded
preset (Sim check first). Nothing else.

## What was asked and the answers

The fills study (atlas-fills-2026-11-20.md) found ATLAS's first 3 live fills 9-15 ticks worse than the backtest. All open
decisions about ATLAS's money were valued at 1 tick. Re-judged here at 3 / 6 / 10 ticks a side from today's real account
($24,887, $887 room, one traded day in the cycle; board 2026-11-20 02:09 ET).

The bar (fixed before any run, research/second/atlas_risk_design.md): an option is better only if, at BOTH 6 and 10 ticks,
it lowers the 6-month loss chance in Jan-Jun-like AND Jul-Oct-like markets by at least 0.5 points (2021-25 not up more than
0.5) AND keeps the $ a month at 90%+ of today's in both 2026 halves (2021-25 within $10).

| Option (card) | Verdict | 10 ticks: $ a month H1 / H2 / REF, lost in 6 m H1 / H2 / REF | Card now |
|---|---|---|---|
| O1 room 40% (atlas-funded-room-40) | **better** | $527 / $393 / $16 vs $503 / $402 / $19; 11.0 / 14.0 / 98.2% vs 17.6 / 21.7 / 98.8% | recommend **yes** (was no), open |
| O2 back to the $100 stop (atlas-funded-keep-trading) | not better: loses more | $489 / $396 / $18; 20.3 / 23.5 / 98.9% | stays **yes** |
| O3 ask at $1,000 (payout-ping-1000) | better, narrowly (6 ticks Jul-Oct: exactly 0.5 points) | $511 / $401 / $17; 16.0 / 20.7 / 98.5% | stays **no** (see below) |
| O4a Rapid without ATLAS (atlas-on-rapid) | not better: $ -76% to -89% | $221 / $191 / -$22 vs $1,883 / $800 / -$50 | stays **yes** |
| O4b Rapid ATLAS $150 | not better: $ -12% / -19% | $1,517 / $707 / -$50 | stays yes |
| O5a pause 4 weeks | not better: no safer in Jul-Oct, -$55 a month | $469 / $347 / $15; 15.7 / 22.0 / 98.6% | (answer: no pause) |
| O5b 1 micro for 25 sessions, then normal | better | $514 / $383 / $15; 12.7 / 18.9 / 98.8% | not a card (see below) |
| O5c stop ATLAS | not better: $0 | $0; 0% | (answer: no stop) |

Why payout-ping stays "no" although O3 passed: the design made passing necessary for a yes, not sufficient. Its safety gain
is 0.5-1.6 points (6-18 paths of 1,000 saved, 1-2 lost the other way), once room 40% is in it adds only 0.4-0.9 points
(post-hoc PH1: 10.6 / 13.1% vs 11.0 / 14.0%), each payout comes 2-5 trading days later, and the same switch costs the 25K #2
(Zlarior, LIT, untouched by ATLAS's fills) about $5 a month (research/lab/payday_levers.json L2). Room 40% does the safety
job far better. The card's text now says so.

### Should ATLAS keep trading the funded 25K at 10 ticks, or pause until fast_entry or more fills prove the slippage smaller?

**Keep trading.** At 10 ticks it still makes $503 / $402 a month in 2026-like markets (the fills study's rule, > $50 in both
halves, holds), against $0 stopped. A pause does not do what it promises:
- it costs $34 / $55 a month (Jan-Jun / Jul-Oct-like) and pushes the first payout to Jan 20 / Feb 5;
- it is not safer where it matters (Jul-Oct-like lost 21.7 -> 22.0%), because the account still has to climb from $887 of
  room afterwards with the same 60% bets;
- MFFU closes an account after 7 days with no trade, so a pause still needs a 1-micro trade each week by hand;
- and it proves nothing: the funded 25K is the only place ATLAS trades live, so a paused ATLAS makes no new fills.
  fast_entry (built OFF) is the one change aimed at the cause, but only real fills can price it.

What does work is trading smaller, not stopping. Room 40% (the card) is the simplest. Trading 1 micro for the next 25
sessions (about 10 fills at ATLAS's rate), then back to normal, also passes the bar against today (12.7 / 18.9% lost,
$514 / $383). Post-hoc (added after the run, shown, never eligible): room 40% plus the 1-micro start gives 8.5 / 13.2% lost
for $519 / $370 a month; worth a pre-registered test only if the owner wants the extra safety after the room 40% yes.

## Full numbers

Funded 25K from today's account ($ a month to the owner, median first payout over ALL paths, lost in 6 months), 1,000
week-block paths a market, the same paths for every option:

| Option | Ticks | Jan-Jun-like | Jul-Oct-like | 2021-25-like |
|---|---:|---|---|---|
| Today | 1 | $581, Dec 18, 7.9% | $490, Jan 4, 8.6% | $44, none, 93.5% |
| | 3 | $563, Dec 21, 9.9% | $471, Jan 4, 11.2% | $36, none, 96.0% |
| | 6 | $538, Dec 22, 12.9% | $437, Jan 6, 16.8% | $26, none, 97.7% |
| | 10 | $503, Dec 23, 17.6% | $402, Jan 7, 21.7% | $19, none, 98.8% |
| Room 40% | 1 | $590, Dec 23, 4.9% | $480, Jan 11, 5.0% | $45, none, 90.8% |
| | 3 | $574, Dec 24, 6.8% | $460, Jan 12, 6.9% | $34, none, 93.4% |
| | 6 | $553, Dec 28, 8.9% | $433, Jan 14, 9.5% | $25, none, 96.7% |
| | 10 | $527, Dec 29, 11.0% | $393, Jan 19, 14.0% | $16, none, 98.2% |
| Old $100 stop | 6 | $525, Dec 22, 15.7% | $432, Jan 6, 18.5% | $25, none, 98.0% |
| | 10 | $489, Dec 23, 20.3% | $396, Jan 7, 23.5% | $18, none, 98.9% |
| Ask $1,000 | 6 | $543, Dec 24, 12.3% | $434, Jan 7, 16.3% | $25, none, 97.4% |
| | 10 | $511, Dec 28, 16.0% | $401, Jan 12, 20.7% | $17, none, 98.5% |
| Pause 4 weeks | 6 | $505, Jan 19, 11.6% | $371, Feb 2, 16.7% | $22, none, 96.6% |
| | 10 | $469, Jan 20, 15.7% | $347, Feb 5, 22.0% | $15, none, 98.6% |
| 1 micro 25 sessions | 6 | $550, Jan 6, 7.9% | $416, Jan 20, 13.6% | $23, none, 97.1% |
| | 10 | $514, Jan 8, 12.7% | $383, Jan 22, 18.9% | $15, none, 98.8% |
| PH1 room 40% + ask $1,000 (post-hoc) | 10 | $529, Dec 31, 10.6% | $392, Jan 22, 13.1% | $15, none, 98.0% |
| PH2 room 40% + 1 micro start (post-hoc) | 6 | $550, Jan 7, 6.0% | $408, Jan 27, 8.1% | $25, none, 94.9% |
| | 10 | $519, Jan 11, 8.5% | $370, Jan 29, 13.2% | $15, none, 98.4% |

Room 40% at 3 ticks: $574 / $460 / $34, 6.8 / 6.9 / 93.4%. Every 1 / 3-tick row is in research/second/atlas_risk.json.
Same-path counts at 10 ticks: room 40% saves 76 / 100 accounts that today's sizing loses (Jan-Jun / Jul-Oct-like) and
loses 10 / 23 that today's keeps; the old $100 stop loses 27 / 18 extra and saves none.

Rapid EOD 25K (not bought yet: a fresh Rapid from Nov 20; $ a month after every eval fee and re-buy; a funded Rapid lost =
floor or stuck under $100, then re-bought):

| ATLAS lane | Ticks | Jan-Jun-like | Jul-Oct-like | 2021-25-like |
|---|---:|---|---|---|
| $250 (as built) | 1 | $2,322, Feb 2, 21.3% | $1,016, Feb 10, 28.9% | -$12, none, 28.4% |
| | 6 | $2,074, Feb 5, 24.0% | $895, Feb 15, 33.9% | -$37, none, 21.5% |
| | 10 | $1,883, Feb 10, 27.2% | $800, Feb 18, 38.0% | -$50, none, 18.8% |
| $150 | 6 | $1,634, Feb 12, 10.0% | $758, Feb 23, 27.0% | -$40, none, 14.9% |
| | 10 | $1,517, Feb 17, 12.0% | $707, Feb 25, 28.8% | -$50, none, 12.4% |
| off (Zlarior alone) | any | $221, none (55% never paid), 5.6% | $191, none (50%), 14.1% | -$22, none, 3.6% |

The 1-tick Rapid row matches tools/money/payday_plan.py's R25 (Feb 2 / Feb 10, 21.3 / 28.9% lost) exactly. With ATLAS a funded
Rapid is lost more often because far more runs get funded at all; without it half the runs see no payout in 6 months. The
$150 lane is the safer choice (38.0 -> 28.8% lost Jul-Oct-like) for $93-366 a month less; it fails the 10% money bar.

## How it was done

- tools/atlas_risk.py: ATLAS's trades re-priced with tools/atlas_fills.priced (entry N ticks past the 5m open, every
  non-target exit N ticks, targets 0; sizes unchanged); only ATLAS re-priced (Zlarior's one real fill was 4 ticks).
- Funded 25K: tools/atlas_more PGF2 (MFFU Builder 25K funded rules, the live preset 60% of the room <= $750, a winner
  <= $1,000, the $750 request line, min_room 0 with MFFU's inactivity close as 5 idle sessions under $100) from
  tools/atlas_health.at_today, plus three knobs: ask (the request line), pause (no ATLAS trade for the first 20
  sessions; a $3 weekly token trade subtracted), probe (max 1 micro for the first 25 sessions).
- Rapid: tools/money/money_plan.RSeat on rapid25.acct("25k", keep $500), ATLAS's trades patched in the way
  tools/atlas_fills.rapid_rows does.
- First payout = the median over all 1,000 paths with "never" counted as never (so "none" = half or more never pay);
  dates from Fri Nov 20 = session 1, Thanksgiving skipped (tools/money/payday_plan.calendar).
- 126 sessions = 6 months; $ = payouts after MFFU's split / 6, before the 30% tax pot.

Limits: three real fills are the whole cost evidence (10-ticks-a-side exits are an assumption: no real exit price exists);
the 2021-25-like rows say ATLAS has no edge at real fills whatever the sizing; the Monte Carlo reshuffles weeks of the past.
money_plan.py used to rewrite these cards at 1 tick on every run: its write_decisions now leaves alone any item whose
"valued" names tools/atlas_risk.py (refresh them with `tools/atlas_risk.py run` + `cards`), and tests.test_money_plan checks
those items against research/second/atlas_risk.json "cards" instead of the 1-tick lab file (22/22). payout-ping-1000 stays
money_plan's (its numbers include the 25K #2), so a money_plan re-run drops its "at real fills" sentence.

## Files

tools/atlas_risk.py (new, research: run / posthoc / cards / show), research/second/atlas_risk_design.md (committed first,
e4e63c97), research/second/atlas_risk.json, tools/web_public/business/decisions.json (4 cards' text; room-40, keep-trading and
atlas-on-rapid values at 10 ticks; statuses kept), tools/money/money_plan.py (write_decisions keeps real-fill values),
tests/test_money_plan.py (part b reads them), STATE.md (finding line + owner step 5). Tests: tests.test_decide 20/20,
tests.test_money_plan 22/22, tests/smoke.py 8/8. Nothing live changed: no engine file, no live_model*.json, no second_model.json, no data/account_b.json.
