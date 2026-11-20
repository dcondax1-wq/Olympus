---
title: Zlarior eval rescue (2026-11-20) - from today's hole, keep the live sizing, smaller room share, pause on the edge light, or re-buy on a blow? Builder 50K and Builder 25K #2 on one Monte Carlo
family: risk
date: 2026-11-20
status: rejected (no change) - today's sizing earns the most on both accounts in both 2026 halves; room 0.3 halves the 50K's blow risk for about $50-80 a month less; nothing changes live
summary: From today's state (50K $49,193, $1,025 room, $3,807 to go; 25K #2 fresh), both evals on one 1,000-path Monte Carlo of real LIT sessions (tools/money/lit_two_evals paths, costs in, + a 10-tick stress), 4 pre-registered variants, each with re-buy on a blow ($91.80 / $63) for the 6-month money. Today's sizing (two_week room 0.4) makes the most - 50K $728 / $699 a month, 25K $357 / $308 (Jan-Jun / Jul-Oct-like) - and passes the 50K in a median 14-16 sessions (72% / 71% within 60, 25% / 24% blow). Room 0.3 cuts the 50K blow to 11% / 10% and passes slightly more often (78% / 74%) but 5-7 sessions later and $49 / $77 a month less; room 0.2 less again. Pausing while the edge light is not green costs $171-222 a month; the light is GREEN today (1.88 R a week vs 1.16), so a pause would not even start. The 25K #2 almost never blows on any variant (0-3%). No Decide card. The cold run is normal LIT variance.
runs: tools/research/rescue.py (research/lit/rescue.json); design research/lit/rescue_design_2026-11-20.md
---

# Zlarior eval rescue (2026-11-20)

## For the owner (one minute)

**Keep both evals exactly as they are.** Today's sizing makes the most money on both accounts in both 2026 halves.

$ a month = what the account pays you over the next 6 months after fees (funded payouts minus eval fees), with a fresh
eval bought ($91.80 / $63) whenever one blows. "Pass / blow" = within 60 sessions, no re-buy. Jan-Jun-like / Jul-Oct-like
market.

**Builder 50K (from today's hole: $1,025 room, $3,807 to go)**

| Choice | Pass | Blow | Sessions to pass (median) | $ a month |
|---|---:|---:|---:|---:|
| **Today (room 0.4)** | 72% / 71% | 25% / 24% | 14 / 16 | **$728 / $699** |
| Smaller: room 0.3 | 78% / 74% | 11% / 10% | 19 / 23 | $679 / $622 |
| Smaller: room 0.2 | 76% / 64% | 3% / 3% | 27 / 31 | $614 / $540 |
| Pause until the edge light is green | 60% / 50% | 14% / 15% | 21 / 22 | $557 / $477 |
| +10 ticks a trade (today) | 66% / 65% | 32% / 29% | 14 / 17 | $623 / $638 |

**Builder 25K #2 (fresh, $1,500 to pass)**

| Choice | Pass | Blow | Sessions to pass | $ a month |
|---|---:|---:|---:|---:|
| **Today (room 0.4)** | 87% / 83% | 3% / 2% | 9 / 8 | **$357 / $308** |
| Room 0.3 | 88% / 81% | 0% / 0% | 12 / 15 | $345 / $289 |
| Room 0.2 | 84% / 72% | 0% / 0% | 18 / 24 | $324 / $253 |
| Pause | 74% / 66% | 1% / 1% | 9 / 5 | $297 / $252 |
| +10 ticks a trade (today) | 83% / 79% | 5% / 3% | 9 / 8 | $296 / $275 |

- **(a) Today** wins on $: one LIT winner can pass the 50K, and a blow costs only $91.80 to restart, so trading
  smaller buys safety the money does not need. Both together: $1,084 / $1,007 a month (first payout around session
  45-53, late January).
- **(b) Smaller** (room 0.3): if a blow would hurt more than the $91.80 (nerves, or MFFU limits on re-buys), this is the
  honest trade-off - blow risk 25% -> 11% for about $50-80 a month less and a week later pass. Not better on $ in
  either half, so no Decide card.
- **(c) Pause**: the light is GREEN today (1.88 R a week over the last 40 sessions; the cold run is only the last 7
  trades), so it would not pause now. As a standing rule it sits out ~20 of 60 sessions and costs $171-222 a month on
  the 50K (and the drift switch was already rejected, drift-switch-2026-11-17).
- **(d) Re-buy on a blow** is already in every $ number above; it is the right plan at $91.80 / $63.
- **2021-25-like market** (no LIT edge): every choice is about $0 a month; smaller sizing only blows less.

## Is the cold run normal?
Yes. Last 7 twin trades -$858 (-4.2R), no target since Oct 14. In 2026, 8.8% of all 7-trade stretches were as bad or worse
(worst -6.2R); the longest 2026 run without a target was 20 trades (2021-26: 42); today's is 7. Details:
lit-edge-2026-11-20.md.

## Method
tools/research/rescue.py uses tools/money/lit_two_evals as is (its mk_eval, LEv sizing = engine/sizing.lit_qty, the
builder_levers Seat / funded rules, the same paths and seeds). Its "today" rows equal research/lab/lit_two_evals.json
exactly (H1 72.0 / 24.8 / 14, 25K 87.3 / 2.6, seats $728 / $357; H2 71.0 / 23.8 / 16, $699 / $308). room_f overrides the
eval's two_week share only. The pause rolls the edge light (tools/edge_health cuts: 40 sessions, GREEN above 1.16 R a
week) from the real last 40 sessions (stored to Oct 16 + the twin since Oct 19) along each path. Stress = 10 ticks
(2.5 pts) off every trade. The 50K's start state is the 2026-11-17 hole (session 23); the balance has not moved since.
