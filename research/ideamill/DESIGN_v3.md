# IDEA MILL v3: hierarchical (family-first) testing + a wider grammar. Pre-registration, written 2026-11-25 BEFORE any v3 run

PAPER RESEARCH ONLY. Builds on DESIGN.md (+ addendum v2); everything not changed here stays: NQ futures bars, entry at the next
open, one trade a day per idea, flat 15:55, 1.45 points of costs, >= 100 discovery trades, DISCOVERY = 2021-11 .. 2024-12,
HOLD-OUTS = 2025, 2026 H1, 2026 Jul-Oct 16 (untouched until a gate says so), the moving-block bootstrap p (block 5, 1,000 draws,
normal tail of mean / SE_boot), the sign-flip placebo, every trial logged (proto 3 rows in trials.jsonl.gz).

## Why v3
v2 tested 24,480 variants with ONE Benjamini-Hochberg pass: the bar (p <= 4e-6) is so high that even a planted edge as strong as
LIT's best half-year failed. v3 tests FAMILIES first, then variants only inside the families that pass.

## Grammar v3 (adds 8 triggers to v2's 18; the rest unchanged)
New, each a pure function on the bar context: prior-MONTH high/low sweep and break; Asia range (18:00-02:00) break after 02:00;
London range (02:00-05:00) break after 05:00; opening drive (09:30-09:45 move >= 3 x 5m ATR -> go with it at 09:45);
3-bar reversal (3 bars one way, then a bar that closes beyond the first bar's open the other way); exhaustion bar (range >= 2.5 x
5m ATR with the close in the far 40% from its direction = a long wick -> fade); ATR-band break (close beyond EMA20 +- 2 x 5m ATR,
crossing it -> go with it). ES-led signals stay "untestable" until ES has a discovery span (ES bars start 2025-04).
Order-flow features (day-ofmax) are NOT in v3: they have no discovery span yet (tick data from 2026-11); a hook only.
Variants per family: 3 timeframes x 5 windows x 9 filters x 2 stops x 4 exits = 1,080.

## Protocol v3 (hierarchical FDR, Benjamini & Bogomolov 2014)
- **Family** = (trigger, direction): 26 triggers x 2 = **52 families**.
- **Stage A, families (discovery only):** each family's p = the **Simes** combination of the discovery p of its scored
  variants (valid under the positive dependence of variants of one rule). BH at **q = 0.10 across the 52 families**.
- **Stage B, variants:** inside each family that passed, BH over its scored variants at **q x R / 52** (R = families passed:
  the Benjamini-Bogomolov selective level), plus mean net R > 0.
- Stage C: the deflated-Sharpe haircut (N = the trials of that family) >= 0.95.
- Stage D, hold-outs: mean net R > 0, PF >= 1.10 and >= 10 trades in EACH of 2025, 2026 H1, 2026 Jul-Oct.
- Stage E: forward paper >= 20 new trades, mean > 0 -> only then needs-owner-yes (+ the full CLAUDE.md proof).
- Placebo: the same Stages A-D on the sign-flipped trades.

## The pre-designated confirmation track (named here, BEFORE its hold-outs are looked at)
The v2 discovery scan pointed at ONE family: 1h close beyond VWAP +- 2 sd, go WITH it, NY PM ("1h|vwap_band|fade|nypm|...").
It was picked by looking at discovery, so discovery cannot confirm it. Its ONLY test is the hold-outs, spent here, once:
- **C1** the named variant `1h|vwap_band|fade|nypm|none|atr|T12` (the v2 best): passes if mean net R > 0 and PF >= 1.10 with
  >= 10 trades in EACH of 2025, 2026 H1, 2026 Jul-Oct;
- **C2** the family average: the equal-weight mean net R of the family's scored variants (9 filters x 2 stops x 4 exits),
  > 0 in EACH of the 3 hold-outs.
Both must pass for the family to go to forward paper (journal status "paper"). Otherwise it is rejected and logged.
