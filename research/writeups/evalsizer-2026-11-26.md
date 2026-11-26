# Optimal eval sizing policy: today's rule is already the best (2026-11-26)

PAPER RESEARCH ONLY (nothing changed live). Design first: `research/evalsizer/DESIGN.md` (committed before the scored run).
Code `research/evalsizer/sizer.py` -> `results.json`, DP tables `dp_tables.npz` / `dp_table.txt`. Engine = research/plans/rank.py
(as research/badcase): only the LIT eval sizing call is swapped; ATLAS lane, funded sizing and every MFFU rule unchanged; 1,000
paths, 60-session eval, 6-month slot with re-buys, owner prices. Check: T0 reproduces badcase (50K H1 83.8/16.2% vs 84/16%).

## One screen ($ = net per slot over 6 months after fees; pass / fail % in 60 sessions)
| Plan | Rule | 2026 Jan-Jun | 2026 Jul-Oct | 2021-25 | 2025 |
|---|---|---|---|---|---|
| Builder 50K | **today (room 40%)** | $7,253, 84/16% | $7,371, 85/15% | -$574, 19/81% | -$468, 21/79% |
| | bigger cap R50 | +$116, fail +3 | +$199, fail +6 | -$32 | -$35 |
| | protect PR1 (25% under $1,000 room) | -$106, fail -6 | -$278, fail -3 | +$62 | +$31 |
| | DP-optimal D2 (all-history pool) | -$173 | -$347 | +$40 | +$32 |
| Builder 25K | **today** | $3,288, 88/7% | $2,904, 83/10% | -$324, 20/80% | -$277, 21/78% |
| | R50 | +$130, fail +7 | +$180, fail +5 | -$33 | -$4 |
| | DP D2 | +$10 | -$96 | +$32 | +$28 |
| Rapid EOD 25K | **today** | $11,301, 79/0% | $4,801, 86/2% | -$300, 7/77% | -$221, 8/64% |
| | R60 (H1 pick) | +$42 | +$47 | -$9 | +$1 |
| | R25 | -$24 | -$35 | +$24 | +$12 |

**Verdict: REJECTED, today stays.** Pick on H1 = today on both Builders (bigger caps fail the +2-point fail bar). Rapid's H1 pick
(R60) loses in 2021-25. 0 of 54 variants beat today in all 4 markets; the best "min gain over 4 markets" is today itself. No card.

## Why
1. **Bold play near the target is already today's rule.** The one-winner need cap (micros so one target covers what is left)
   binds before the room cap near the target: BP6 / BP8 = today exactly.
2. **One knob, one trade-off.** Bigger room share = faster passes = more $ in 2026 markets, more $ lost in bad ones. Smaller share,
   fixed fraction, Kelly, protect and the DP = fewer fails (50K fail 16% -> 9-11%) but slower passes (7 -> 8-16 days), and in a good
   market time is the money: each slot loses $100-$1,470 in 6 months. They save $30-$100 in bad markets, which still lose money.
3. **The DP's shape** (dp_table.txt): risk 10-17% of the room with lots of trades left, ramp to 50-90% as trades run out,
   shrink near the target. It maximises the pass chance, not $ per month, so in the real engine it is slower and earns less.
4. **No sizing fixes a bad market.** In 2021-25 / 2025 every rule loses $195-$640 a slot. What fixes that is not buying
   (badcase), not sizing.

## If the owner wants fewer fails anyway (not recommended for $)
50K "protect" PR1 (room cap 25% once the room is under half the max loss): fail 16 -> 10.5% (H1), 15 -> 11% (H2), same speed in
H1, -$106 / -$278 a slot in 2026, +$62 / +$31 in bad markets. Code: `research/evalsizer/sizing_PR1_not_applied.patch` (new
two_week keys protect_below 0.5 / protect_room_f 0.25; absent = today, bit for bit). The $ option R50 is config only:
`sizing_R50_not_applied.patch` (room_f 0.5): +$116-199 in 2026 but 3-7 more fails in 100, so it misses the fail bar.

Caveats: DP ignores ATLAS and the intraday floor; block bootstrap per market; 2025 pool is one year; 54 variants counted.
