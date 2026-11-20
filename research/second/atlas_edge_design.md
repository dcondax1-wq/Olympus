# ATLAS edge (order type, worst leg, entry minute, ES, guards, payout path) - pre-registered design (2026-11-20, day-atlasedge)

Written and committed BEFORE any run. Tool: `tools/atlas_edge.py`. Output: `research/second/atlas_edge.json`.
Write-up: `research/writeups/atlas-edge-2026-11-20.md`. RESEARCH ONLY: no engine file, no live_model*.json, no
second_model.json, no data/account_b.json, no accounts/*.json. A full pass becomes ONE Decide card (status "open"), never a
live change.

Already done today, NOT redone (atlas-fills-2026-11-20, atlas-risk-real-fills-2026-11-20): limit at the open 5 min (F1),
limit 4 ticks worse 5 min (F2), market at +60 s for all legs (F3), fast-bar skip (F4), member hour windows (F5), London
pause (F6), room 40% (O1, card already recommended YES), $100 stop, ask $1,000, pause / probe / stop. The 1-tick day caps
of atlas-health-2026-11-18 are re-checked ONLY at real fills (E1), labelled as a re-check.

## Fixed before the runs

- Trades: tools/atlas_fills.units() (= tools/atlas_more.base_units, the live ATLAS units, never opposite LIT), then one
  position + max 2 a day (atlas_revive.one_pos), atlas_health trade format (atlas_more.to_T, weights allowed).
- Costs: N ticks a side total (tools/atlas_fills.priced): entry N ticks past the 5m open, every non-target exit N past its
  level, a target 0. Judged at N = 6 AND N = 10 (10 = the stress, the real fills ran ~11 ticks); 3 and 1 shown.
- Views: V1 fixed $250 a trade (atlas_health.fixed_view: H1 2026 Jan-Jun, H2 Jul-Oct 16, 2025, 2021-24): trades a week,
  PF, net $, $ a month, max DD. V2 funded Builder 25K Monte Carlo from TODAY's account ($24,887, $887 room,
  atlas_more.at_today), tools/atlas_risk PGF3 (MFFU Builder 25K funded rules, live funded preset, min_room 0, MFFU
  inactivity close), 1,000 week-block paths a market (H1 / H2 / REF = 2021-25), the SAME paths for every option: $ a month to
  the owner, median 1st and 2nd payout date over all paths, lost in 6 months (floor, stuck or idle), lost before the 1st payout.
- Two bases: B60 = what runs today (60% of the room), B40 = room 40% (the card recommended YES, not yet tapped).

## Gate G (families A, B, C: an entry / leg change), vs the base at the SAME cost, at BOTH N = 6 and N = 10, on B60 AND B40

(a) funded $ a month (today's account) >= base + $10 in H1 AND H2; REF >= base - $5;
(b) lost in 6 months <= base + 0.5 point in H1, H2 and REF;
(c) fixed view: PF >= base in H1 and H2; $ a month >= base - $10 in H1, H2, 2025 and 2021-24;
(d) 2.0-4.1 trades a week in H1 and H2 (fixed view);
(e) testable on all spans (2021-25 has 5m bars only; anything that needs 1m bars is information, never a pass).

## Gate E (family E: guards), the atlas_risk bar, at BOTH N = 6 and N = 10, on B60 AND B40

lost in 6 months lower by >= 0.5 point in H1 AND H2, REF not higher by more than 0.5; $ a month >= 90% of the base in H1
AND H2, REF >= base - $10.

## A - order type (fill probability from 1m bars; 5m-only spans: the entry 5m bar must CLOSE 1 tick through the limit)

Model (as F1): the order arrives when the market is already N ticks past the 5m open. A limit at L (dir space) fills only on
a trade 1 tick through L after the arrival: minute 1 must CLOSE through it, minutes 2.. may trade through. A target reached
before the fill = no trade (missed runner). Reported for each: share of signals filled, the $ (fixed view) of the winners missed.
- A1 limit at the 5m open, cancelled after 2 minutes.
- A2 limit 1 tick better than the open, 2 minutes.
- A3 limit 2 ticks better than the open, 2 minutes.
- A4 limit at the open for 2 minutes, then MARKET at the 3rd 1m open (+N ticks) unless minutes 1-2 traded the stop
  (avoided) or the target (missed); same stop / target prices, size from the new entry. 5m-only spans: unfilled -> market at
  the next 5m open (+N) unless the entry 5m bar traded the stop or target.
- A5 limit at the open, 1 minute.

## B - the leg that loses most to slippage

Selection on 2026 H1 ONLY: L* = the member whose fixed-view $ a month drops most from N = 1 to N = 10 (member alone, $250 a
trade). Then: B1 drop L*; B2 L* at half size (weight 0.5, at least 1 micro when it fits); B3 L* entered at +60 s (2026 only,
information). Per-member table at 1 / 6 / 10 for every span shown.

## C - the entry minute

- C1 per-leg minute k in {0,1,2,3,4} (market at the open of the k-th 1m bar after the 5m open, + N ticks; skipped if the
  stop or target was traded before), each leg's k picked on 2026 H1 at N = 10 (fixed-view $, leg alone); checked on H2.
  2021-25 untestable: information only.
- C2 every leg at the NEXT 5m open (+5 min), same rule, all spans testable.
- C3 per leg +0 or +5 min, picked on 2026 H1 at N = 10; checked on H2, 2025, 2021-24.

## D - ES (helper output research/second/atlas_es_trades.json, tools/atlas_es.py)

Each leg run on ES 5m bars (point params scaled by the ES / NQ price ratio). ES 5m exists only from 2025-04-14, so 2021-24
cannot be tested and D can never pass (information). Costs: MES $5 a point, $1.90 a micro round trip, (i) the NQ fill delay
in price terms (N NQ ticks x the ES / NQ price ratio, rounded up, min 1 ES tick), (ii) a 10 ES-tick stress. Fixed $250
view per leg on 2025 Apr-Dec, 2026 H1, 2026 H2 vs the same leg on NQ at the same span. Worth a follow-up only if an ES leg
beats its NQ leg on PF and $ a month in all three spans at both costs.

## E - funded-account guards (today's account, both bases)

- E1 (re-check at real fills) day stop: after a losing ATLAS trade, no more ATLAS that session.
- E2 streak pause: after 3 losing trades in a row, no trade for the next 3 sessions (the streak resets after the pause).
- E3 streak shrink: after 2 losing trades in a row, 1 micro until the next winner.
- E4 week cap: once the week's ATLAS P&L reaches -35% of the room at the week's start, no more trades that week (week =
  5 path sessions).
Streak counters update at the end of each session from that session's trades (a loss = net P&L < 0).

## F - payout path

For B60, B40 and every passing change (and, shown, the best non-passing change of each family): median 1st and 2nd payout
date from today, chance of losing the account before the 1st payout and within 6 months, $ a month, at 10 ticks (6 shown).
Post-hoc variants, if any, are labelled post-hoc and are never eligible.
