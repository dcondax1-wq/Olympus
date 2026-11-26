# LIT Asia slot at real Asia costs. Pre-registration (2026-11-26, written BEFORE any run)

PAPER RESEARCH ONLY: no live file / size / arming change (live_model*.json untouched). Code research/litasia/asia.py -> results.json;
write-up research/writeups/litasia-2026-11-26.md.

**Prior result (lit-more-entries.md, lead 1 `asiaslotn_rr3_x1.0`).** 1 Asia trade 18:00-02:00 ET, banked at 3R, in its own slot,
plus the normal 02:00-15:30 trade, at 1 tick a side:
- H1 +$34,661 vs +$33,891 (+$770); H2 +$13,686 vs +$9,493 (+$4,193);
- **2021-25 -$15,505 vs +$1,211 (-$16.7k)**;
- 2-week eval fails H1 5.9 -> 6.7%, H2 0.0 -> 2.9%.

The owner's full bar (2026 halves AND 2021-25) is therefore already failed. This run asks only whether the 2026 gain survives
realistic Asia costs. LIT's own bar is H1 pick / H2 check, so if the gain dies there too, the lead is closed.

**Fixed, no choices.** The same engine and variant via tools/lit_more_entries.py (the exact live LIT + the Asia slot, rerun on
today's code and data). Extra slippage on the trades that enter 18:00-02:00 ET only (NQ's overnight book is thinner than the
London / NY book): +1 / +2 / +4 ticks a side, on the entry and on a non-target exit; a target is a resting limit (+0).

**Views.**
- LIT size ($800 up to 20 pts, the engine's pnl less the extra ticks x $0.50 x the trade's micros).
- The eval path (the live two_week units, pts less the extra ticks): fresh 2-week evals on every session, pass / fail.
- Spans: H1, H2, 2021-25.
- MFFU: overnight positions inside one CME session (18:00-17:00) are allowed. Holding past 16:10 ET / news rules are unchanged:
  the Asia trade ends the same session.

**Verdict.** "Asia slot dead" if at +2 ticks (the central case) the Asia slot adds no money in H1 OR H2 at the LIT size, or the
2-week eval fails rise in both halves. Otherwise: "2026-only lead; fails the full bar on 2021-25" (no card either way, per the
owner's bar).
