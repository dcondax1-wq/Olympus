# How fragile is LIT (Zlarior)? Robustness & fragility audit (2026-11-26)

PAPER RESEARCH ONLY: nothing live changed. Plan written before the runs (`research/fragility/DESIGN.md`). Code
`research/fragility/{fragility,sizing}.py` -> `results.json`, `sizing.json`. Engine = engine/lit.run_x, live params.
Today's LIT: $5,562 / $2,670 / $25 a month (2026 Jan-Jun / Jul-Oct / 2021-25), 50K 2-week pass 44.5 / 39.1%. Fresh weeks
Oct 19 - Nov 20: -$858 (1.4 trades a week).

## Verdict
**LIT sits on a plateau, not a knife-edge, but its 2026 money is mostly the 2026 market.** Trust about a quarter of the
2026 rate: about $1,000-1,400 a month forward per 50K at the LIT size, not $4,250. Plan evals for a 2021-25-like market
too. In that market today's 40% room size fails about half the evals. **Sizing: keep today's 40% (room_f 0.4).** My simplified sim (below, section 5) suggested 0.3 cuts fails, but big-evalsizer re-checked it in the real eval engine (research/plans/rank.py: every MFFU rule, the soft day stop, the one-winner need cap, the ATLAS lane): 0.3 does NOT cut fails there, and 0.4 earns more in every market mix (branch big-evalsizer, research/evalsizer/mix_check.json).

## 1. Parameter surface (each knob alone at -20 / -10 / +10 / +20%, $/month)
| Knob | Jan-Jun | Jul-Oct | 2021-25 | 2-week pass H1 / H2 | Neighbours keeping >= 80% of today's $ (H1 / H2) |
|---|---|---|---|---|---|
| sweep depth 0.5 | 5,562..5,652 | 2,669..2,670 | -24..48 | 44.5 / 39.1 (flat) | 4/4 / 4/4 |
| **displacement 0.8** | 3,862..5,960 | **923..2,347** | -360..-173 | 31.1..52.1 / 33.3..37.7 | 3/4 / **1/4** |
| inducement distance 1.0 | 5,051..5,705 | 1,004..3,037 | 51..80 | 39.5..45.4 / 21.7..40.6 | 4/4 / 3/4 |
| inducement age 36 | 5,551..5,591 | 2,670..3,874 | 4..18 | 44.5 / 39.1..53.6 | 4/4 / 4/4 |
| 1m CISD window 22 | 3,992..5,562 | 1,957..2,692 | -30..160 | 33.6..44.5 / 30.4..39.1 | 3/4 / 3/4 (only -20% hurts) |
| limit expiry 6 bars | 5,260..5,562 | 2,672..2,766 | -28..4 | flat | 4/4 / 4/4 |
| VIX band x1.0 | 5,400..5,535 | 2,044..2,872 | -24..100 | 46.2..47.9 / 36.2..47.8 | 4/4 / 3/4 |
| min target 1.5R / min stop 8 / max stop 80 / window end 15:30 / 15-min check | ~flat | ~flat | small | ~flat | 4/4 / 4/4 |
| **8R bank** | 4,507..6,134 | **1,708..2,381** | -58..87 | 41.2..51.3 / 34.8..49.3 | 4/4 / **1/4** |
| breakeven 1R | 5,194..5,540 | 1,607..2,670 | -325..63 | ~flat | 4/4 / 3/4 |
| stop buffer 0 / 2 / 3 ticks | 5,453..5,672 | 2,667..2,728 | -171..41 | 41.2..44.5 / 39.1..47.8 | 3/3 / 3/3 |
| window start 02:00 (+-12 / 24 min) | 3,838..5,536 | 2,198..3,085 | -104..58 | 34.5..44.5 / 37.7..44.9 | 3/4 / 4/4 |
Most knobs are flat (the rule rarely binds). Two are sensitive in Jul-Oct: **displacement** (+10% -> -$894 a month, +20% ->
-$1,747) and the **8R bank** (any move costs $290-960 a month in Jul-Oct). Today's values sit near the top of both, i.e. they
were tuned. A small sensitivity: starting later than 02:00 (+24 min: -$1,724 in H1). No knob flips 2021-25 into real money:
its range is -$360..+$160 a month around today's +$25.

## 2. Costs (extra ticks per side per micro, on top of $1.90 + 1 tick)
| | Jan-Jun $/mo | Jul-Oct $/mo | 2021-25 $/mo (PF) | 2-week pass H1 / H2 |
|---|---|---|---|---|
| today | 5,562 | 2,670 | +25 (1.01) | 44.5 / 39.1 |
| +1 tick | 5,485 | 2,626 | **-51 (0.97)** | 44.5 / 39.1 |
| +2 ticks | 5,408 | 2,581 | -126 (0.94) | 43.7 / 39.1 |
| +4 ticks | 5,253 | 2,492 | -277 (0.87) | 42.9 / 39.1 |
2026 barely notices costs (big R targets). 2021-25's edge is gone at +1 tick a side. Live LIT fills matched the backtest to
$1.50 on 2 trades (livegap), so today's cost model is fair. There is no cost cushion outside a 2026-like market.

## 3. Trade-order luck (20,000 resampled 50K evals, 40%-of-room sizing, MFFU 50K rules, up to 80 trades)
| Trade pool | Pass | Fail | Median trades to decide | Max DD median / worst 5% | Longest losing run median / 95% | P(7+ losers in a row during the eval) |
|---|---|---|---|---|---|---|
| 2026 Jan-Oct (120 trades, mean +0.81R) | 95.1% | 4.3% | 11 | -$689 / -$1,991 | 2 / 6 | 2.5% |
| 2026 Jul-Nov 20 (47, +0.54R) | 85.6% | 13.0% | 13 | -$979 / -$2,017 | 3 / 7 | 8.3% |
| 2021-25 (511, +0.01R) | 36.1% | 61.5% | 25 | -$2,006 / -$2,030 | 3 / 6 | 4.5% |
In any 23 trades (~40 sessions), a 7+ losing run happens 3.3% (2026) / 4.3% (2021-25) of the time. The live 7-trade cold run
since Oct 19 is a 1-in-25-ish event, not proof the edge is gone. Win rate is only 14-28% (>= 0.5R), so long dry runs are normal.

## 4. Data-snooping haircut (deflated Sharpe, Bailey & Lopez de Prado)
1,483 LIT runs are stored in research/runs (a lower bound: grid searches inside tools were not all stored, hence a 3x stress).
| | Live LIT Sharpe (annual) | Best-of-N luck level | Deflated Sharpe (P real > 0) | Share above the luck level |
|---|---|---|---|---|
| 2026 Jan-Oct, N 1,483 | 3.65 | 2.68 | 0.93 | 27% |
| 2026, N x3 (4,449) | 3.65 | 2.91 | 0.87 | 20% |
| 2021-26, N 1,483 | 0.93 | 3.84 | 0.00 | 0% |
2026's LIT edge is probably real (DSR 0.87-0.93). But only ~20-27% of its Sharpe sits above what the luckiest of ~1,500-4,500
tried variants would show. Over 2021-26 as a whole, the live LIT is not distinguishable from the best of many tries (it was
picked on 2026). Daily $ is heavily skewed (skew 3.9, kurtosis 20): a few big winners carry it.

## 5. Eval sizing: SUPERSEDED, my simplified sim (`sizing.py`: 20,000 evals, 40 trades ~ 70 sessions, pools mixing 2026 and 2021-25 trades)
| Market mix (share of 2026-like trades) | room 0.25 | **room 0.30** | room 0.40 (today) | room 0.50 | room 0.60 |
|---|---|---|---|---|---|
| 100% 2026 | 90.2 / 0.5 (12) | **90.4 / 1.2 (11)** | 89.5 / 4.1 (10) | 87.7 / 7.7 (9) | 85.5 / 12.0 (8) |
| 50% | 69.4 / 2.5 (15) | **70.5 / 5.1 (14)** | 70.8 / 13.0 (12) | 69.7 / 20.7 (11) | 68.1 / 27.1 (10) |
| **25% (the haircut)** | 53.6 / 5.2 (17) | **56.1 / 10.5 (15)** | 57.7 / 21.7 (13) | 57.4 / 31.1 (12) | 56.0 / 38.3 (10) |
| 0% (2021-25-like) | 25.0 / 20.9 (18) | **27.8 / 32.2 (16)** | 31.7 / 48.6 (14) | 33.4 / 56.6 (12) | 34.7 / 59.6 (12) |
(pass % / fail % (median trades to pass)). Going from 0.4 to 0.3 keeps the pass rate within 0-4 points in every mix and cuts
fails by a third to a half, for ~2 more trades. Above 0.4 adds fails, not passes. At $91.80 an eval, at the 25% mix that is
~11 fewer failed evals per 100 bought.

**Correction (same day):** in the real engine (rank.py, 1,000 paths, 60 sessions) 0.3 does not cut fails. 50K at a 50% 2026 mix: 0.4 $1,913 / 52 / 48 vs 0.3 $1,746 / 54 / 46; at a 25% mix: 0.4 $387 / 34 / 65 vs 0.3 $329 / 34 / 66 ($ a slot over 6 months, pass / fail). My sim left out the soft daily loss cap, the one-winner need cap and the ATLAS lane. Those bind before the room cap on most trades, so the table above overstates the gain. Keep 0.4.
