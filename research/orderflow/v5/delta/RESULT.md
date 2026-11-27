# Order flow v5, family "delta": result (2026-11-27, look 1 of 1)

PAPER RESEARCH ONLY. Rules frozen first in `DESIGN.md` (6 variants, nothing else scored). Code `core.py` + `run.py`
(`python -X utf8 research/orderflow/v5/delta/run.py`, ~2 s) -> `results.json`. Data: 51 usable real NQ tick-summary days
2026-09-27..2026-11-26 (44 RTH days), quote-rule sides. $ at 1 micro (MNQ), $1.90 a round turn, E5 entry at the signal close
(limit 5 min, then market +18 ticks), stop 1 tick beyond the extreme (min 8 ticks), stop slip 2 ticks, one target.

## Verdict: NO YES-candidate. Best = O2 / O1 (overnight delta bias), both only "weak". Frozen for tonight's new days.

| var | rule | pool | labelled | trades | /wk | win % | mean R | PF | $ 1 micro | max DD | $ at $500 risk | halves mean R (old / new) | halves gap R | gap R | placebo p | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 | delta burst z>=2 + breakout -> continue | 817 | 84 | 79 | 8.98 | 39.2 | -0.147 | 0.91 | -$445 | $1,330 | -$6,039 | -0.074 / -0.230 | 0.002 / -0.170 | -0.075 | 0.716 | 1.0 | NO |
| M2 | delta burst z>=3 + breakout -> continue | 817 | 23 | 23 | 2.61 | 26.1 | -0.390 | 0.37 | -$976 | $984 | -$4,374 | -0.314 / -0.508 | -0.226 / -0.443 | -0.313 | 0.913 | 1.0 | NO |
| V1 | 15m swing take-out + CVD divergence -> fade | 146 | 55 | 55 | 6.25 | 30.9 | -0.199 | 0.77 | -$556 | $783 | -$5,006 | -0.509 / +0.080 | -0.003 / +0.653 | +0.334 | 0.063 | 0.377 | NO |
| V2 | V1 + closed back inside (failed take-out) | 77 | 37 | 37 | 4.20 | 32.4 | -0.153 | 0.77 | -$468 | $697 | -$2,984 | -0.453 / +0.200 | +0.189 / +0.536 | +0.359 | 0.098 | 0.393 | NO |
| **O1** | 09:30 bar direction agrees with overnight delta | 44 | 26 | 26 | 2.95 | 42.3 | +0.098 | 1.17 | **+$477** | $1,227 | +$1,093 | +0.070 / +0.130 | +0.272 / +0.450 | +0.359 | 0.177 | 0.530 | weak |
| **O2** | trade the overnight-delta direction at 09:35 | 88 | 44 | 44 | 5.00 | 38.6 | -0.007 | 1.19 | **+$620** | $1,374 | +$722 | +0.267 / -0.308 | +0.519 / +0.416 | +0.470 | 0.077 | 0.385 | weak |

(pool = price-only rows simulated as if taken; labelled = rows with the order-flow read; gap R = labelled minus unlabelled mean R
over the pool = what the delta read adds beyond price; placebo = label shuffle, O2 = random side per day.)

## What it says, in plain words
1. **Delta bursts do not help continuation (M1, M2).** Breakout bars with a 2-sigma or 3-sigma delta burst behave like breakout
   bars without one (gap -0.08R / -0.31R; the stronger burst is WORSE: 3-sigma bursts look like the end of the move, 6 of 23 won).
   The whole breakout pool loses after costs (-0.09R). Clear NO.
2. **CVD divergence at 15m swings does separate, but fading still loses (V1, V2).** Take-outs WITH a divergence lose less than
   take-outs without one (+0.33 to +0.36R better, raw p 0.06-0.10), but the book itself is -0.15 to -0.20R and lost in the older
   half. Holm 0.38-0.39. NO as a trade. (Not tested, not a result: the no-divergence take-outs lost -0.51R as fades, which hints
   that a new 15m high WITH delta behind it tends to keep going; that would need its own pre-registration.)
3. **Overnight cumulative delta has some say about the first hour (O1, O2), but not enough to call it.** Trading the side the
   overnight delta points to beat the opposite side in BOTH halves (gap +0.47R overall, +0.52 / +0.42 by half; raw p 0.077),
   and made +$620 at 1 micro over 44 days (+$556 older half, +$64 newer). But the book mean R is ~0 (-0.007: winners are the
   wide-stop days), the newer half's mean R is negative (-0.31R), PF 1.19 < 1.20, and Holm over the 6 is 0.385. O1 (only when the
   first 5m bar agrees) is positive in both halves (+0.07 / +0.13R, +$226 / +$250) but only 26 trades, p 0.18. Both = weak.

## Frozen for the out-of-sample test (`frozen.json`, rules exactly as above, core.py sha256 stored)
- **O2** (best by verdict, Holm, $) and **O1** (second). Run on any new days with
  `python -X utf8 research/orderflow/v5/delta/oos.py` (scores every usable day in data/pc_days NOT among the 51; same table,
  Holm over the 2; warns if core.py changed). Pass bar on the new days alone = the same YES-candidate bar, gap sign as in-sample.
- With ~260 new days, O2 gets ~210+ trades and O1 ~130: enough to settle it. My prior: most likely it fades to ~0 (the newer
  half already did in R), so treat a pass as a surprise worth a second check, not as an edge.

## Limits (honest)
- 44 RTH days. The O ideas get one trade a day, so 26-44 trades: one or two big open days move the totals.
- 5m summaries only: the E5 limit at the signal close filled on 99% of trades (the next 5m bar almost always trades 1 tick through
  the close); the real queue can be worse. The +18-tick market fallback was used once.
- Stops on the O trades are the 09:30 bar's range (median ~46 points); M stops are the burst bar (~66 points). At 1 micro the $
  is small; at $500 risk the size is 1-5 micros.
- Nothing here changes a bot. A future pass is only a reason to paper-forward it; the strategy-proof protocol (both 2026 halves +
  2021-25) cannot be met with tick data that starts 2026-09.
