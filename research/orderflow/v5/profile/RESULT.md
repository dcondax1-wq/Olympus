# Order flow v5 "profile": volume-profile setups read with order flow: RESULT (2026-11-27)

PAPER RESEARCH ONLY. Rules were written first in `DESIGN.md` (6 variants, before any number). Code: `core.py` + `run.py`
(numbers in `results.json`, every candidate listed), out-of-sample scorer `oos.py`, frozen rules `frozen.json`.
Data: 51 real NQ tick-summary days, 2026-09-27..11-26, footprint-built profiles (prior RTH day, overnight, composite).
Entry E5 (limit at the level for one 5m bar, then market +18 ticks; no level = market +18). Stop 1 tick beyond the signal
extreme, stop fill 2 ticks worse, one target that needs 1 tick through, $1.90 round trip, R includes costs. $ at 1 micro MNQ.

## Verdict: NO YES-candidate. Every variant is TOO FEW (< 20 booked trades in 51 days). One is worth watching: P6.
| var | setup | cand | gated | trades | /wk | win % | mean R | PF | $ 1 micro | max DD | halves R (old / new) | gap gated-not (old / new) | placebo p | Holm | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | 80% rule, 2 x 30-min closes inside | 8 | 5 | 5 | 0.5 | 40 | +0.13 | 0.54 | -$299 | $633 | +0.29 / -0.51 | n/a / +0.51 | 0.108 | 0.32 | TOO FEW |
| P2 | 80% rule fast, 2 x 5m closes inside | 10 | 8 | 8 | 0.8 | 38 | -0.45 | 0.28 | -$871 | $984 | -0.27 / -1.01 | n/a / +0.02 | 0.022 | 0.11 | TOO FEW |
| P3 | prior-RTH VAH/VAL fade, absorbed, 2R | 22 | 17 | 15 | 1.5 | 27 | -0.26 | 0.49 | -$786 | $934 | -0.33 / -0.18 | +0.63 / +1.12 | 0.139 | 0.32 | TOO FEW |
| P4 | composite LVN rejection, bar delta with | 82 | 0 | 0 | 0 | - | - | - | $0 | $0 | - | - | - | - | TOO FEW |
| P5 | POC magnet after an inside-value open | 7 | 2 | 2 | 0.2 | 0 | -1.02 | 0 | -$343 | $343 | -1.02 / - | -1.07 / - | 0.32 | 0.32 | TOO FEW |
| **P6** | **prior-RTH VAH/VAL fade, absorbed, target = prior POC** | 22 | 15 | **15** | **1.5** | **47** | **+0.37** | **1.92** | **+$595** | **$166** | **+0.52 / +0.19** | **+1.58 / +1.22** | **0.079** | 0.32 | TOO FEW |

In plain words:
- **The 80% rule does not work here.** Opens outside yesterday's value happened 8-10 times in 51 days, and the trade back
  across value lost: every candidate as if taken = -0.30R (classic) / -0.57R (fast). The delta gate made it less bad, not good.
- **POC magnet: no.** 7 candidates, -0.41R ungated; the two gated ones both lost.
- **LVN rejection: untested in practice.** My pre-registered gate (5m bar delta >= 10% of the bar's volume, with the trade)
  fired 0 times in 82 candidates. On NQ a 5m bar's delta is typically ~7% of its volume, so 10% was set too high. Not
  changed after the fact. For information only: all 82 candidates as if taken = -0.22R mean but +$2,398 at 1 micro (PF 1.64),
  i.e. wide-stop rejections paid and tight ones did not. That is a post-hoc look, not a result.
- **Prior-day value-area edges: absorption separates again (as in lane A).** Gated-minus-not gap is positive in both halves
  (P3 +0.63 / +1.12R, P6 +1.58 / +1.22R). Non-absorbed edge fades lost ~1R each.
- **The target decides the money.** Same 15 absorbed trades: aim at 2R (P3) = -$786; aim at yesterday's POC (P6) = +$595,
  PF 1.92, max DD $166, both halves positive ($277 / $317). At $500 risk (size follows the stop) P6 = +$2,894 in ~2.4 months.
- P6 is still **not a pass**: 15 trades (bar 20), Holm p 0.32 (bar 0.10). It is about 1.5 trades a week (house range 2-4).
  If it is real it would mostly overlap lane A in spirit (the same absorbed-fade idea at a different level), not a new edge.

## Frozen for the out-of-sample test (picked by the pre-set rule, not by hand)
`frozen.json` = **P2** (lowest Holm p, 0.111, but it lost money) and **P6** (next lowest Holm, 0.316, the only one that made
money). Both are frozen exactly as run, with the 51 in-sample day names.
Run after tonight's pull: `python -X utf8 research/orderflow/v5/profile/oos.py` (only days not in the 51; the same table;
Holm over the 2). Mock check `--holdout 10` runs (prints "MOCK run"; not a result). What would make P6 a YES-candidate on the
new days: >= 20 booked trades, net > 0, PF >= 1.20, both halves positive, gap positive in both halves, placebo + Holm < 0.10.

## Limits (honest)
- 51 days, one regime (autumn 2026); the 2021-25 check cannot be run (no ticks before 2026).
- 1-point profile bins; E5 read on 5m bars (on a bar where the limit fills, only the stop is checked: conservative).
- P2's frozen status is the rule's pick, not a belief that it works.
- No fishing: 6 variants, none changed after the run. The LVN gate miscalibration is reported, not fixed.
