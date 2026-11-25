# Order-flow ideas, FORWARD-ONLY protocol (pre-registered 2026-11-25, before any tick data reached the cloud)

Paper research only. Why a separate protocol: the idea mill (research/ideamill, DESIGN_v3) discovers on 2021-24 and holds out
2025 / 2026; tick data has no 2021-24 at all (NinjaTrader's servers keep about 1 year). So order-flow ideas get their own
time split inside the tick history, the SAME family-first FDR as v3, a placebo through the same gates, and they must then
win on brand-new days before anything reaches the owner. Code: `research/orderflow/of_forward.py`; `tools/ideamill.py` runs it
as the `of` grammar (`--of`, and inside every `--batch`) and it switches itself on when the summaries arrive.

## Ideas (pre-registered = DESIGN2.md, unchanged)
49 order-flow features (groups A delta, B footprint, C large lots, D trapped traders, E effort/result, F level, G depth,
H CVD) x 3 entries (LIT filter, ATLAS MD filter, LVL = stand-alone level fade) x 2 sides (hi / lo vs the Discovery median).
- **Family** = (entry, feature group): 3 x 8 = **24 families** (G only once >= 40 depth days exist). Variants = the group's
  features x 2 sides (A 12, B 22, C 12, D 4, E 8, F 8, G 16, H 16).

## Days and the split
- Tick days with an order-flow summary and >= 50,000 trades, sorted by date.
- **Off** under 60 tick days (the battery, DESIGN.md, covers 40-60).
- **Provisional** from 60 days: Discovery = the oldest 60 %, Confirm = the newest 40 % of the days available. Reported, but a
  provisional run can never produce a candidate (it is a dry run of the machinery).
- **Frozen** the first run with >= 120 tick days (or the backfill reported done): `split_day` = the day at the 60 % mark,
  `confirm_end` = the newest day of that run; written once to `research/ideamill/of_split.json`, never moved. Later
  backfill days OLDER than split_day join Discovery; days after confirm_end are **Forward** days only.

## Gates (same as DESIGN_v3; q = 0.10)
- **A, families (Discovery):** each variant's Discovery p = its one-sided permutation p (filter: skipping the same number of
  random trades; stand-alone: coin-flip direction; 1,000 draws). Family p = **Simes** over its scored variants. BH across the
  scored families at q = 0.10.
- **B, variants:** inside a passing family, BH over its variants at q x R / F (R = families passed, F = families scored), and
  Discovery gain > 0 with >= 30 Discovery trades (filters: trades kept; stand-alones: signals).
- **C, deflated Sharpe** of the variant's Discovery daily P&L, N = the family's variants: DSR >= 0.95.
- **D, Confirm:** gain > 0, >= 10 trades, permutation p < 0.10; stand-alones also PF >= 1.10.
- **E, Forward paper:** >= 20 trades on Forward days with gain > 0 -> **needs-owner-yes** (then the full CLAUDE.md proof). Until
  then "forward paper".
- **Placebo:** every variant also runs with its keep-mask shuffled (filters, seeded by the variant id) or its trades'
  direction coin-flipped (stand-alones), through the SAME gates A-E. The placebo counts are printed next to the real ones; if
  the placebo passes as often as the real ideas, nothing is believed.
- Every run is logged (`research/ideamill/of_trials.jsonl`), and the counts go into the idea mill's `summary.json` under `of`.
