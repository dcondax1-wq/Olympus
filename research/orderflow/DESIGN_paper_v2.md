# Order Flow paper bot v2: every lane A decision scored twice (written 2026-11-27 before any forward day; night-of-paperv2)

Adds to `DESIGN_paper.md` (frozen 76396849); nothing in it changes. PAPER ONLY. Same reads and writes, same CPU rules (nice 5 /
BELOW_NORMAL from the ops task, the kick lock), no routing, sizing or live setting. Why: research/writeups/ofexec-2026-11-27.md.
The lane's fill (next open + 1 tick) is not realistic: a market order at today's 2.75 s delay is modelled at ~18 ticks worse, and
that flips lane A to NO. The patient entry E5 keeps it YES. The forward days must score both, side by side.

## Second fill per lane A row ("E5"; the original fill, exits, R and $ stay exactly as before)
- **Limit at the swept level** (`level_px`): a sell limit at a high, a buy limit at a low. It is placed at the decision (t_dec)
  and rests 300 s.
  - If the first trade at or after the decision is already at or beyond the level our way, it fills at that trade (marketable).
  - Otherwise it fills at the level when a trade goes **>= 1 tick through it** (engine/costs.TARGET_THR_TICKS) before 300 s.
- **Cancelled** if a trade reaches the stop before that fill ("no fill: stopped before entry"). The stop lies beyond the level, so a jump to the stop fills the limit first (the stop is then booked); the rule only guards odd data.
- **Not filled in 300 s:** market at the first trade at or after t_dec + 300 s, **+18 ticks against us** (engine/costs
  ENTRY_SLIP_TICKS["OFA"]).
- On a summary replay (5m bars only, the cloud) the 300 s window is the entry bar:
  - its open beyond the level = a marketable fill;
  - its high / low >= 1 tick through = a fill at the level (the whole bar is then checked for the stop first);
  - the stop in that bar without a fill = no fill;
  - else the next bar's open + 18 ticks.
- The same stop (1 tick beyond the signal bar's extreme), 2R from the E5 fill, flat 15:55, kill. Exits use the lane's own
  `_resolve`: closed 5m bars, stop first, stop fill + 1 tick.
- **Logged on the row:** fill_e5, fill_t_e5 (ms), how_e5 (level | marketable | market+18 | none), exit_e5, why_e5, R_e5, usd_1_e5,
  usd_500_e5. Rows are never rewritten once resolved.

## Scoring (forward days from 2026-11-28 only)
The DESIGN_paper.md bar applies to each fill separately: >= 40 resolved TAKEN, taken mean R > skipped (one-sided shuffle
p < 0.10), both halves the same sign, taken $ > 0.
- E5 is "the lane's real entry" only if it passes and its taken $ at 1 micro beats the original fill's.
- Otherwise the paper stays on both, and nothing goes to Sim101 / live without the owner's yes.
