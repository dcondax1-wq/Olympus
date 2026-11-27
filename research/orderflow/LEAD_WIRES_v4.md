# LEAD_WIRES from order flow v4 (night-of-features, 2026-11-27). For the lead; this helper changed no engine file.

Verdict on 51 real NQ tick days (2026-09-27 .. 11-26), rules frozen first (`DESIGN_v4.md`): **0 of 21 tests passed** after
the deflation (Holm, bar adjusted p < 0.10). Nothing earns a bot change. Ranked for forward logging (best first):

| rank | feature | why it is on the list | cost live |
|---|---|---|---|
| 1 | V7 first-15-minute delta (09:30-09:45 delta / volume, trade with it) | inside lane A's 40 absorbed trades: kept 19 +$1,696 vs skipped 21 -$113 at 1 micro, better in BOTH halves (info only) | cheap: one sum at 09:45 |
| 2 | V6 VWAP location (fade 1 ATR away from RTH VWAP) | standalone 152 trades +$4,414 at 1 micro (~$1,800/month), PF 1.52, both halves up, raw p 0.038 -> adj 0.46: NOT proven; 15 a week (too many for the bots) | cheap: running price x volume |
| 3 | V5 delta slope into entry (3 bars, with the trade) | lane A filter raw p 0.039, both halves up, but flips sign inside absorbed trades (overlaps absorption) | cheap: 3-bar delta sum |
| 4 | V3 absorption strength (volume / range >= 1.5 x 12-bar median) | lane A filter raw p 0.055, both halves up, kept 15 +$1,546; overlaps absorption | medium |
| 5-7 | V2 CVD divergence, V1 stacked imbalances, V4 large-lot prints | no edge: V1 / V2 standalone lose ~$1,600-2,500; V4 big prints too rare (block size 4 lots) | - |

LIT filter: TOO FEW (18 LIT replay trades in the tick days, floor 20) for every feature; nothing to say about Zlarior yet.

## What to wire (in order of value / effort)
1. **No PC change needed for the forward test.** Every night's `python -X utf8 tools/data_pull.py --of` brings the new days'
   summaries; run `python -X utf8 research/orderflow/of_v4.py` after it (e.g. next to `run_battery()` in tools/data_pull.py).
   It scores the pre-registered watch list W1-W4 (DESIGN_v4 addendum) on days from 2026-11-27 only.
2. Optional, for the owner's eyes: `engine/oflive.said_at()` (the daily journal line per LIT trade) could add V7 (sign of the
   09:30-09:45 delta vs the trade) and V6 (above / below RTH VWAP at the sweep). Both are standard-library sums over the bars /
   footprint it already loads in `_summary()`. Read-only, logging only; it must not touch a decision.
3. Nothing for `engine/of_paper.py`: its frozen rules (DESIGN_paper.md) stay as they are; v4 reads come from the summaries.

When the forward floors are met (W1 needs 20 absorbed lane A trades, about 5 weeks at the current ~4 a week), a FORWARD PASS
goes to the owner as a yes / no, with the caveat that no tick data exists before 2026-09 (the 2021-25 check cannot be done).
