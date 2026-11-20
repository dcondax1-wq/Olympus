# ATLAS real fills - pre-registered design (2026-11-20, night-atlasfills)

Written and committed BEFORE any cost or fix run. Tool: `tools/atlas_fills.py`. Output: `research/second/atlas_fills.json`.
Write-up: `research/writeups/atlas-fills-2026-11-20.md`.

Finding to explain (night-nqlive): ATLAS's 3 real NinjaTrader fills were 9 / 11 / 15 ticks worse than its model price
(10 / 12 / 16 ticks vs the 5m open; the backtest counts 1 tick). Zlarior's 1 fill: 3 ticks.

## Facts fixed before the runs (from the code and the stored trades)

- Live ATLAS entry: engine/account_b.AccountB.entry: on the first poll after a 5m close (+2 s poll offset), the members run on
  the closed 5m bars + a probe bar at the forming 1m open; the first member with a signal is routed as a MARKET order
  (engine/ninjatrader place_line "MARKET"), then the stop + target bracket after the fill. No stop or limit entry.
- Backtest entry (research/second/{ema,md,sr}_best.json, all 1,395 trades checked): the 5m open after the signal close
  + 1 tick worse; stop exits = the stop + 1 tick worse; target exits = the target exactly.

## Cost scenarios (job 2)

N ticks PER SIDE, total (the backtest's 1 tick included): the entry N ticks worse than the 5m open; every non-target exit
(stop, breakeven stop, cut, flat, T15, HEDGE) N ticks worse than its level; a target (resting limit) 0. N = 1 (today's
backtest), 3, 6, 10. Reference row (not judged): "as measured" = entry 13 ticks (the 3 fills' mean vs the open, 12.7),
exits 1 tick (no real exit price exists). Sizes unchanged (the bot sizes from the model entry and stop); the worst open
point w1 moves with the entry. Views:
  V1 fixed $250 a trade, real days, costs in: trades a week, PF, net $, $ a month, max DD for 2026 H1 / Jul-Oct 16 / 2025 /
     2021-24 (tools/atlas_health.fixed_view).
  V2 the FUNDED Builder 25K Monte Carlo of tools/atlas_more.py (600 week-block paths, seed BL.A4.SEED_LIFE, MFFU funded
     rules, the live funded preset size) with today's approved rule (min_room 0 = atlas_more A1_stuck_off, owner YES
     2026-11-19): from a fresh funded start and from today's account ($24,887, $887 room): $ a month to the owner, first
     payout (median session), dead in 6 months (floor touched or stuck or MFFU's 7-day inactivity close).
  V3 the Rapid 25K ATLAS lane: tools/money/rapid25.py row "25K, keep $500" (LIT + ATLAS $250 at 30% of the room) with
     only ATLAS's trades re-priced (LIT at its own costs), and the same row with ATLAS off: slot $ a month, first payout,
     no payout in 6 months, funded lost (1,000 paths, rapid25's seeds).
Verdict rule "ATLAS still worth running at N ticks" (pre-declared): funded 25K $ a month > $50 in BOTH 2026 halves AND the
fixed-view PF >= 1.2 in both 2026 halves; the Rapid lane is worth it if LIT + ATLAS pays more than LIT alone in both halves.
2021-25: stated as is (PF < 1 = no long-run edge at that cost).

## The fixes (job 3) - at most 6, fixed now

F1 LIMIT AT THE SIGNAL PRICE: a limit at the 5m open (0 ticks worse), cancelled after 5 minutes. Under scenario N the market
   at the order's arrival is N ticks past the open (that is what a market order would get), so the limit rests and fills at
   the open only when price trades 1 tick through it after the arrival: 2026 (1m bars) minute 1 CLOSES 1 tick through the
   open (it must have crossed back after the arrival) or minutes 2-5 trade 1 tick through; 2021-25 (5m bars only) the entry
   5m bar closes 1 tick through (conservative). A target reached before the fill = no trade (the runner is missed);
   otherwise the trade's exit is unchanged and its entry is the open (0 ticks).
F2 LIMIT 4 TICKS WORSE: the same with the limit 4 ticks worse than the open: N <= 4 fills at once at N ticks (= market),
   N > 4 rests at 4 ticks worse and fills on 1 tick through it within 5 minutes.
F3 ENTER ON THE 1m CLOSE: a market order at the open of the 2nd 1m bar (5m open + 60 s) instead of the 5m open, the same stop
   and target prices, size from the new entry; no trade if minute 1 already traded the stop (avoided) or the target
   (missed). Same N-tick costs. 1m bars exist only for 2026: 2021-25 cannot be tested, so F3 cannot pass the proof rule
   (shown as information).
F4 SKIP FAST SIGNAL BARS: no entry when the 5m signal bar's range (high - low) is more than 2.0 x the median range of the 20
   5m bars before it (known at the order time; every span has 5m bars). Threshold fixed here, not tuned.
F5 PER-MEMBER TIME WINDOW: each member's entry window [start hour, end hour) ET picked on 2026 Jan-Jun at N = 6 (fixed-view
   net $), grid = whole hours inside the member's own entry hours, at least 2 hours wide; then checked on Jul-Oct and
   2021-25 at N = 6 and 10.
F6 LONDON PAUSE: no ATLAS entry before 08:00 ET (the London part of EMA and MACD), the "thin London book" idea. Judged at the
   same N for every hour; a view with London at N and NY at N / 2 is shown, not judged.

## Gate (each fix vs today's rules at the SAME cost; must hold at BOTH N = 6 and N = 10)

(a) funded 25K $ a month (fresh start) >= today + $10 in H1 AND H2; 2021-25 >= today - $5;
(b) dead in 6 months <= today + 0.5 point in H1, H2 and 2021-25;
(c) fixed view: PF >= today's in H1 and H2; $ a month >= today's - $10 in H1, H2, 2025 and 2021-24;
(d) 2.0-4.1 trades a week in H1 and H2 (fixed view; today's H1 is 4.06);
(e) at N = 3 it costs at most $10 a month (funded, H1 and H2);
(f) testable on all three spans (F3 is not).
A winner gets an OFF switch in engine/account_b.py with a test and a Decide card; every loser goes in TESTED_AND_REJECTED.
Post-hoc variants, if any, are labelled post-hoc and are never eligible.

## Not testable on bars (said, not run)

Polling on NinjaTrader's first tick (engine/fast_entry, built OFF): it moves the order ~1.8 s earlier inside the first
minute; 1-minute bars cannot price that. It needs Sim days with tick-time fills.
