---
title: K8 goes live Monday (2026-11-23, $55, $2.50 a bet): red team of the live path + the edge at your size
family: kalshi
date: 2026-11-21
status: one real hole found and fixed (a bet could be forgotten); the edge still looks real at $2.50 but only in-sample; current setting OK; gold-only offered as a Decide card
---

# K8 live on Monday: is it safe, and does it make money? (2026-11-21)

## In plain words

- **Safe:** one real hole, now fixed. If Kalshi took an order but its answer got lost (a timeout, a Kalshi 502, or the PC
  dying in the middle of the send), the bot **forgot the bet**. That bet wasn't counted by the day / week / peak stops, and
  a restart in the same 45 seconds could buy the same market **twice**. Now every bet is saved *before* it is sent. An unclear
  answer keeps it as "check": counted as already lost by every stop, and blocking a second bet on that market. After the result
  it is booked from Kalshi's own fills. Everything else held: key, phrase, sizes, stops, the price cap, settlement, errors.
- **Money:** at $2.50 a bet on the 3 live legs, the history says about **+$12 a week**. If the real edge is 10 points weaker
  (the planning case), about **+$6 a week**. No simulated run fell below $30. This is still the friend's own months. Only
  6 bets are new since Nov 18 (3 won, +$0.53), and the newest week (Nov 16-20) was the worst of 16 (6 of 15 won, -$6.54).
- **Setting:** keep $2.50 on 3 legs (the most $). A safer **gold-only** option is on the Decide card. It keeps about two
  thirds of the $ and makes the bot switching itself off about 4 times rarer. That is your yes or no.

## 1. Red team of the live path (engine/kalshi_clock.py + engine/kalshi_live.py)

| Area | Verdict | Where / what |
|---|---|---|
| **Lost answer / PC dies mid-send** | **HOLE, fixed** | `ClockLoop.send` (was engine/kalshi_clock.py:876): the row was written only after a good answer. A network error / 5xx / timeout gave `error()` + no row, though Kalshi may have filled it. The window was not saved yet, so a crash plus a restart inside 10-45 s re-sent. Fix: the row is saved before the POST (`posting`). An unclear answer becomes `check`. A clear 4xx refusal removes it. `OPEN_ST` counts posting / check / sent / open in every stop and in one-bet-per-market. `filled_market()` books a `check` row from `/portfolio/fills?ticker=` after the settle. Tests r1-r6 in tests/test_kalshi_clock.py |
| Key handling | holds | the key lives outside the repo (`OLYMPUS_HOME\kalshi\`), errors are redacted (`KL.redact`), the phone page saves it only over Tailscale with the page header (test w2), and a 401 = OFF at once (f4) |
| The phrase gate | holds | `KL.arm`: the exact phrase only. The arm record is bound to the settings hash + the executor version: any change to research/lab/kalshi_clock.json or to the phone bet size = OFF until the phrase is typed again (f6b, w4). **The executor version moved to 2026-11-21.1 with this fix, so after the PC updates, the phrase is needed again (type it on Monday, after the update).** |
| Bet sizing | holds | the walk buys whole contracts with price <= 70c and cost <= $2.50 (fee on top, ~7c). `check_order` re-checks stake, cap, slot, day bets (3), one bet per market. A phone pick of $5 is armed by the phrase; $8+ cannot pass the -$8 day stop |
| Max loss | holds | before every order: today's worst case (settled $ - every open bet at full cost) >= -$8, the week >= -$13.75, the peak drawdown + all open bets <= $19.25. The kill rules (58% after 60 bets, 58c average price on the last 30) run on the LIVE ledger |
| Duplicate orders | holds now | one bet per market (from the saved ledger, so it survives restarts), the window is marked done, and the lock file allows one loop only (`run()` / `KL._lock`) |
| API errors | holds | GET retries once. POST is never retried (a 429 is retried by the API layer only because Kalshi did not take it). 3 errors in a row = OFF + push. 410 (API changed) = OFF. Balance not read = no bet |
| Market close / settlement | holds | an order only if the market is active and closes > 60 s later. The limit expires by +55 s. Results come from Kalshi's own `result` and our fills; give up after 6 h as `unknown` |
| Other bots on the same key | holds | arming only runs K8: the old maker plan (research/lab/kalshi_live_plan.json) is `rejected` and has no markets, so `maker_runnable` is False |
| Clock | holds | the PC clock is corrected to Kalshi's Date header every 30 min (g1) |

Tests: tests/test_kalshi_clock.py 46/46 (6 new); smoke 11/11; run_area kalshi 18/18 suites, 1,277 checks, 0 failed (the city page failed once on a page-load race, then passed 105/105 on a re-run).

## 2. The edge at your size (research/kalshi_k8_live/, pre-registered in PREREG.md)

| Window (3 live legs, $2.50, exact fees, the price a $2.50 order really paid from +20 s) | Bets | Won | Avg price | $ a bet | $ a week (95%) |
|---|---|---|---|---|---|
| Aug 3-Nov 20 (in-sample to Nov 18) | 236 | 72.9% | 51.5c | +$0.89 | **+$12.23** (+$8.15 to +$16.29) |
| Last 4 weeks | 60 | 73.3% | 52.0c | +$0.89 | +$12.32 (+$3.48 to +$20.76) |
| New since Nov 18 (tells nothing yet) | 6 | 50% | 50.2c | +$0.09 | +$1.23 |
| Planning case: 10 points fewer wins | | 62.9% | | +$0.45 | **+$6.17** |

20,000 simulated runs from $55 with every stop and the real calendar (Thanksgiving Thu-Fri: no evening legs):

| Setting | $ a week (history / planning) | After 4 weeks: average (bad 1-in-20) | Week stop hit 4 / 12 wk | Bot switches itself OFF 4 / 12 wk | Below $30 |
|---|---|---|---|---|---|
| **$2.50, 3 legs (now)** | +$12.23 / +$6.17 | $103 ($70) | 8% / 22% | 4% / 14% (planning 17% / 41%) | 0% |
| $2.50, gold only | +$8.02 / +$3.97 | $88 ($67) | 1% / 4% | 1% / 3% (planning 7% / 20%) | 0% |
| $1.00, 3 legs | +$4.03 / +$2.05 | $71 ($61) | 0% / 0% | 0% / 0% | 0% |

- **Ruin:** none of the 20,000 runs went under $30, so the $55 cannot be wiped out with these stops. The worst that happens is
  the bot switching itself OFF after a -$19.25 dip from its best point (you and Claude look, then decide).
- **Fills:** $2.50 = 4-5 contracts. Others bought at least that much of our side in 20-30 s on 91% (gold 05:15), 100% (gold 16:45)
  and 94% (silver 16:45) of days.
- **Price creep: no.** The weekly average was 49-55c with no trend (the last 4 weeks: 55, 49, 55, 49c).
- **Per leg:** gold 05:15 75% won (+$0.97 a bet), gold 16:45 70% (+$0.80), silver 16:45 74% (+$0.92). None is the weak leg.

## 3. The safer setting (a Decide card, not a change)

The edge is not weaker than thought (no creep, all legs positive), so nothing changes by itself. Because the newest week was
the worst, **gold-only** is offered as a yes/no: `tools/web_public/business/decisions.json` id `kalshi-k8-gold-only`
(recommend: no, keep 3 legs; a yes = `live_legs` without silver, then the phrase again).

## 4. Monday

The owner's one-page checklist: `docs/KALSHI_MONDAY.md`.

Files: research/kalshi_k8_live/ (PREREG.md, fetch.py, edge.py, edge.json, EDGE.md, data/tape.jsonl), engine/kalshi_clock.py
(send / settle / filled_market / OPEN_ST), engine/kalshi_live.py (EXEC_VERSION), tests/test_kalshi_clock.py (r1-r6).
