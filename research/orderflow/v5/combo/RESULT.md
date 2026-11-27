# Order flow v5 "combo": lane A x LIT / ATLAS / regime / day-type context: RESULT (2026-11-27)

PAPER RESEARCH ONLY. Rules written first in `DESIGN.md` (6 variants, before any number). Code `core.py` + `run.py`
(numbers in `results.json`), out-of-sample scorer `oos.py`, frozen rules `frozen.json`.
Data: 51 real NQ tick-summary days 2026-09-27..11-26. Lane A = the absorbed level fade through the v5 shared E5 simulator
(limit at the level, then market +18 ticks). Stop 1 tick beyond the sweep bar, 2R target, $1.90 round trip, R includes costs.
Check: the control C0 reproduces v5/levels V0 exactly (63 trades, +0.295R, +$2,648).

## Verdict: NO YES-candidate. Best = C2 "LIT armed the same side" = weak (fails Holm).
| var | context (book = absorbed AND ...) | trades | /wk | win % | mean R | PF | $ at 1 micro | $/month | max DD | halves R (old / new) | flag on | gap (on - off) | halves gap | placebo p | Holm | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C0 | lane A alone (control) | 63 | 6.2 | 46 | +0.30 | 1.65 | +$2,648 | +$1,090 | $1,164 | +0.21 / +0.41 | - | - | - | - | - | not scored |
| C1 | ATLAS 15m + 1h EMA trend with the fade | 14 | 1.4 | 50 | +0.52 | 3.51 | +$1,463 | +$603 | $347 | +0.55 / +0.46 | 18% | +0.48 | +0.70 / +0.18 | 0.130 | 0.62 | TOO FEW |
| **C2** | **LIT armed same side** | **55** | **5.4** | **49** | **+0.39** | **1.76** | **+$2,849** | **+$1,173** | **$1,164** | **+0.38 / +0.41** | 86% | **+0.70** | **+1.29 / +0.27** | **0.088** | **0.53** | **weak** |
| C3 | S1 wide-range regime | 27 | 2.6 | 48 | +0.41 | 1.56 | +$1,363 | +$561 | $1,164 | n/a / +0.41 | 42% | +0.32 | n/a (S1 off all older half) | 0.176 | 0.62 | weak |
| C4 | VIX > 1-year median | 39 | 3.8 | 49 | +0.38 | 1.84 | +$2,314 | +$953 | $1,164 | +0.12 / +0.52 | 63% | +0.22 | -0.18 / +1.43 | 0.267 | 0.62 | NO |
| C5 | inside-open (balance) day | 23 | 2.3 | 39 | +0.08 | 1.13 | +$191 | +$79 | $889 | -0.05 / +0.29 | 37% | -0.33 | -0.44 / -0.09 | 0.837 | 0.84 | NO |
| C6 | vote >= 3 of the 5 | 31 | 3.0 | 52 | +0.50 | 1.70 | +$1,749 | +$720 | $1,164 | +0.38 / +0.54 | 50% | +0.39 | +0.14 / +0.72 | 0.124 | 0.62 | weak |

In plain words:
- **No context makes lane A provably better.** Every filter that cuts trades raises mean R a bit, but none survives the
  6-test correction (best Holm 0.53; the bar is 0.10).
- **C2 (only when LIT has swept a level on the same side) is the closest.** It keeps 55 of 63 trades, both halves positive
  (+0.38R / +0.41R), the gap positive in both halves, raw p 0.088. It drops 11 absorbed candidates (mean -0.47R, 9 of 11 are
  opening-range fades with no LIT level swept). Net effect vs lane A alone: +$200 at 1 micro over 51 days, same max DD.
  That is a small, plausible tweak ("don't fade an opening-range break that took no real liquidity"), not proof. Still 5.4
  trades a week (above the 2-4 band).
- **ATLAS trend (C1)** agrees with the fade only 18% of the time (fades are mostly counter-trend), so 14 trades: too few.
- **S1 wide-range (C3)** was OFF for the whole older half and ON for the whole newer half, so it cannot be split-tested here;
  it is just "the newer half" (+0.41R).
- **VIX (C4)**: the gap flips sign between halves. **Inside-open days (C5)** are WORSE for the fade (gap -0.33R), the
  opposite of the balance-day idea. Both NO.
- In $ terms none of them beats lane A alone by a meaningful amount: the best (C2) adds ~$80 a month at 1 micro.

## Frozen for tonight's out-of-sample test (picked by the pre-set rule, not by hand)
`frozen.json` = **C2 (LIT armed same side)** and **C6 (vote >= 3 of 5)**, the two best by (verdict, Holm p, net $). Both weak.
Run after the pull: `python -X utf8 research/orderflow/v5/combo/oos.py` (same table for every usable day not in the 51; Holm
over the 2; writes oos_results.json). Checked on a mock split (`--mock 12`): it runs. The new days are probably older history
(2025-26): ATLAS / LIT / S1 / VIX context all come from data/NQ_5m.csv / NQ_1d.csv / VIX_1d.csv, which cover 2021 onward.
OOS pass = the same YES bar on the new days. A pass is only a reason to log the LA flag next to lane A in paper.

## Limits (honest)
- 76 resolved absorbed candidates, 51 days, one regime per half. C2's "off" group is only 11 trades.
- Coarse 5m E5 fills (as v5/levels); stop slippage 2 ticks (real stop fills still unmeasured, see ofexec).
- Nothing here changes a bot. The strategy protocol (both 2026 halves AND 2021-25) cannot be met with tick days.
