# v5 "sessions": is lane A's edge in one session window? First touch vs any touch? (2026-11-27)

PAPER RESEARCH ONLY. Nothing here changes a bot, a size or an order; engine/ untouched. Rules were frozen first in `DESIGN.md`
(6 variants, pass bar, freeze rule), then `core.py` + `run.py` were run once on the 51 real NQ tick-summary days 2026-09-27..11-26.
Numbers: `results.json`. Out-of-sample scorer for tonight's new days: `oos.py`. Costs in everything: $1.90 a micro round turn,
E5 entry (limit at the level for the next 5m bar, else market +18 ticks), stop 1 tick beyond the sweep bar (+2 ticks slip), 2R target.

## Verdict: NO window passes. Best = NY midday, only WEAK. First-touch-only is worse, any-touch is noise.

| var | window / touch | trades | /week | win % | mean R | PF | $ 1 micro | max DD | halves mean R (old / new) | absorbed-minus-not gap (old / new) | placebo p | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | London 02:00-05:00 (PD + Asia H/L) | 27 | 2.6 | 30 | -0.23 | 0.93 | -$93 | $615 | -0.26 / -0.17 | +0.15 / -0.62 | 0.69 | 1.00 | NO |
| S2 | NY open 09:30-10:30 | 47 | 4.6 | 32 | -0.10 | 1.20 | +$725 | $949 | -0.20 / +0.06 | -0.46 / -0.90 | 0.90 | 1.00 | NO |
| **S3** | **NY midday 10:30-13:30** | **38** | **3.7** | **42** | **+0.15** | **1.26** | **+$669** | **$1,319** | **-0.27 / +0.53** | **+0.20 / +0.97** | **0.070** | **0.42** | **weak** |
| S4 | NY PM 13:30-15:30 | 18 | 1.8 | 39 | -0.04 | 0.63 | -$320 | $762 | -0.68 / +0.75 | -0.50 / +0.78 | 0.50 | 1.00 | TOO FEW |
| S5 | all 4 windows, FIRST TOUCH only | 50 | 4.9 | 24 | -0.37 | 0.75 | -$851 | $1,361 | -0.48 / -0.19 | -0.46 / +0.51 | 0.59 | 1.00 | NO |
| S6 | all 4 windows, ANY touch | 211 | 20.7 | 33 | -0.16 | 1.08 | +$975 | $1,699 | -0.26 / -0.04 | +0.11 / +0.07 | 0.26 | 1.00 | NO |
| (V0) | lane A exactly, same simulator (check) | 63 | 6.2 | 46 | +0.30 | 1.65 | +$2,648 | $1,164 | +0.21 / +0.41 | +0.96 / +0.68 | 0.026 | - | not scored |

V0 reproduces the v5-levels control to the dollar (63 trades, +0.295R, $2,648), so the simulator matches the sibling family.

## Plain words
- **Not concentrated in a way we can use.** By the pre-set definition the only non-NO window is midday (S3), so "concentrated in
  midday" technically holds, but S3 itself is only weak: it LOST in the older half (-0.27R), and after 6 tests its p becomes 0.42.
  ~$275 a month at 1 micro, ~$1,550 a month at $500 risk (as measured, in-sample). Not a strategy change, a thing to watch.
- **London does not work** for this setup (27 trades, -0.23R, absorption does not separate in the newer half).
- **NY open 09:30-10:30 loses** when it starts at 09:30. Descriptive (not tested): its 17 trades from the 09:30-09:40 bars are
  -0.55R, the 30 from 09:45 on are +0.15R. Lane A's 09:45 start was right; the first 15 minutes are poison. Also inside S2 the
  absorption read points the WRONG way (absorbed -0.16R vs not absorbed +0.50R, 9 trades).
- **NY PM: too few** (18 trades, 1.8/week), losing.
- **First touch only (S5) is the worst** (-0.37R, 24% wins): the first test of a level tends to break, not hold. **Any touch (S6)**
  trades 21 a week and is a coin flip after costs (-0.16R; gap +0.09R, p 0.26). Neither beats lane A's own "first rejection of
  the day per level" rule.
- So lane A's edge (V0 +0.30R) is not one window. It comes from its full recipe: 09:45 start, one signal per level per day, and
  (per the v5-levels side finding) mostly the FIRST absorbed signal of each day (40 first-of-day +0.48R vs 23 later -0.03R; I
  re-checked this on V0 here). Re-arming levels per window adds trades that do not pay (S1-S4 pooled: 114 trades, -0.12R, +$406).
- Window splits re-cut the same 51 days lane A was found on; with 18-47 trades a window, the differences are mostly noise.

## Frozen for the out-of-sample test (by the pre-set rule, not by hand)
`frozen.json` = **S3 (NY midday, weak)** and **S6 (any touch, NO)**. Run after the pull (tonight ~260 new days):
`python -X utf8 research/orderflow/v5/sessions/oos.py` (same table, Holm over the 2, halves by date). It refuses to run with 0 new
days; `--mock-last 10` is a plumbing check only (ran OK) and is NOT out-of-sample. S3 needs, on the new days, >= 20 trades,
mean R > 0 and absorbed > not absorbed in both halves, placebo and Holm p < 0.10 to become a YES-candidate. Nothing goes near a
bot without that and the owner's yes; the 2021-25 check is impossible (no ticks before 2026).
