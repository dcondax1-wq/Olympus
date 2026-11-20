---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
  - lane/combo50k
type: "research"
date: "2026-11-17"
status: "rejected - nothing passes both 2026 halves; today's entry (tap of the 5m CISD level, first 1m CISD, buy the next 1m open) stays"
source: "research/writeups/lit-smart-entries-2026-11-17.md"
aliases:
  - "LIT smart entries"
---

# LIT smart entries

> [!failure] Verdict: rejected
> rejected - nothing passes both 2026 halves; today's entry (tap of the 5m CISD level, first 1m CISD, buy the next 1m open) stays

**Full title:** LIT smart entries (2026-11-17) - same setups, smarter ways in - conditional pullback limits, 1m confirmation combos, entry timing around the 15-minute check

## Summary

Owner 2026-11-17 "smart entries". 31 new entry rules on the exact live LIT setups (engine/lit.py candidates, live filters, one trade a day, Monday rule, weekly stop; stop 1 tick beyond the sweep extreme, VIX-band target >= 1.5R banked at 8R, BE + 1.25, the 15-minute check, costs in), picked on Jan-Jun 2026 and checked on Jul-Oct, 2021-25 shown (5m days), scored at the LIT size, on the live eval path (two_week room_f 0.4 kept to session 80) and on the funded 50K. Limit fills only when price trades through by 1 tick and the fill bar gets no target / breakeven credit. None is better in both halves. Pullback limits after a big 1m CISD candle get a better price but put breakeven and the 15-minute check closer, and Jul-Oct winners dip first: H2 loses $5.3-9.1k (of $9.9k). Waiting 5-15 minutes for the trade to prove itself misses the fast runners (-$8-26k a half). Half now / half at minute 15 kills the one-winner eval pass (2-week pass 44.5% -> 15%). Closest: 1m CISD or a 1m break of structure, whichever first (+$1,778 Jan-Jun, -$787 Jul-Oct; eval path -$877 / +$2,069): rejected. Wide-stop half size and an entry-quality score were not re-run (already rejected). Nothing to switch on. Paper only.

## Money first

- **Keep today's entry.** 31 new cells, 0 pass the gate; not one is up in both halves even at the LIT size alone.
- Nothing in `engine/`, `live_model.json` or `live_model_lit.json` changed. No adopt-candidate, no lead worth a paper shadow.
- Honest caveats: 1m bars, not ticks (inside a minute the stop is assumed first; a limit needs a trade-through, which is
  conservative); a limit fill is managed from the next 1m bar, so its 15-minute check runs 1 minute later than a market
  fill's; samples are thin (80 / 40 trades); 2021-25 has no 1m bars, so the 1m rules cannot be checked there.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-17]]
- Strategies: [[Zlarior (LIT)]], [[50K combo]]
- Refers to: [[2026-11-04_lit_ideas_night|LIT ideas night]], [[2026-11-15-lit-deep|LIT deep edge]], [[lit-1m-management|LIT on the 1-minute chart]], [[lit-edge-2026-10-30|Zlarior edge night]], [[lit-entry-precision|LIT entry precision]], [[lit-tight-stops-size|LIT tight stops and bigger size]], [[lit-trade-selection|LIT trade selection]], [[lit-untested-entries|LIT untested entry ideas]]
- Runs: `none saved (grid in research/lit/smart_entries.json)`
- Source: `research/writeups/lit-smart-entries-2026-11-17.md`
- Back to [[ZEUS Home]]
