# Pine vs Python parity (TradingView strategy vs engine/model.py)

2026-10-16. Question: why did the TradingView strategy (`tradingview/liquidity_engine.pine`, saved as
"Liquidity Engine - Sweep IFVG DOL" on the "Liquidity Engine Bot" layout, CME_MINI:MNQ1! 5m ETH) take 8 trades
when the Python engine took 25 on the same weeks, and can the gap be closed?

## Result

| Aug 24 - Oct 16 2026, MNQ1! 5m | Trades | Net P&L | PF | Same entries as Python | Same entry + exit class + R (0.3R tol.) |
|---|---|---|---|---|---|
| Python engine (`engine.backtest.run`, DEFAULTS) | 25 | +$8,816 (+$8,784.50 with MNQ-only commissions) | - | - | - |
| TradingView **before** (script of commit fdaea88) | 8 | +$547.50 | 2.76 | 3 (10%) | 2 (7%) |
| TradingView **after** (this commit, Strategy Tester read 16:50 ET) | **25** | **+$8,784.50** | **6.76** | **25 (100%)** | **25 (100%)** |

TradingView after the fix: 25 trades, 12 wins / 13 losses (48%), avg trade +$351.38, largest loss -$276,
max drawdown $380, commission $175.50. Trades per ISO week: 4, 5, 1, 4, 3, 1, 4, 3 (about 3.2 a week). Python has
the same counts. The two 1-trade weeks (Sep 7-11 with Labor Day, Sep 28 - Oct 2) belong to the model, not the port.

The only P&L gap is commissions. Python books 10 or more micros as minis ($4.50 round turn per mini), Pine pays
$1.50 per micro. That is $31.50 over trades 3, 10 and 17. With Python set to micros only, the totals are equal to
the cent.

## How it was measured

- `tools/pine_sim.py` is a bar-by-bar Python replica of the Pine script plus TradingView's broker emulator: next-open
  market fills with 1-tick slippage, OHLC intrabar path for stop and limit, 1-tick trade-through for limits,
  $0.75 per contract per fill. Run on the TradingView MNQ1! export (`data/tv_mnq_5m_2026-10-16.csv`), it reproduces
  both TradingView runs exactly: `--legacy` gives the old 8 trades and +$547.50, and the fixed script gives
  25 trades and +$8,784.50, with every price equal.
- `tools/pine_parity.py <tv_trades.csv>` matches a TradingView "List of trades" against `engine.backtest`. Entry
  comments now carry `sl=` so R uses the actual fill, like the engine's `risk_pts`.
- TradingView trade lists: `research/pine_parity/tv_trades_before_2026-10-16.csv`,
  `research/pine_parity/tv_trades_after_2026-10-16.csv`. Both were read from the Strategy Tester report on the
  owner's chart. Diff output: `research/pine_parity/parity_before.json`, `parity_after.json`.
- The engine's NQ bars for these weeks are the same TradingView MNQ1! prints (same OHLCV), back-adjusted to NQZ26.
  Before the 2026-09-14 18:00 roll they sit +295.5 pts above the raw MNQ1! that TradingView shows.

## Root cause: the 1H / 15m structure never ran on TradingView

The old script built the 1H and 15m swing structure with a user-defined type (`Struct`) updated through methods
(`Agg.feed` -> `Struct.step`). On TradingView those updates never took effect. Evidence:

1. Every one of the 8 TradingView entry labels reads score `s1`. With no 1H trend, no dealing range and no 15m
   trend, the score can only be the +1 clean-path point.
2. Freezing the structure in the replica reproduces TradingView's trade list exactly: 8 trades, +$547.50, all
   entry and exit prices equal.
3. The saved TradingView source was byte-identical to the repo file (same SHA-256), so this was runtime behaviour,
   not a stale copy.

Effects:
- **No 15m/1H swing pools.** There were no ITH/ITL/H1H/H1L levels and no equal highs/lows formed from them. These
  are the levels most sweeps hit, so TradingView armed only 52 setups against Python's 144 (the replica with the
  fix arms exactly 144).
- **Score and grade.** There was no 1H-trend or discount/premium term, so grades fell (B -> D) and sizes shrank.
  The +1 score let counter-trend setups through that Python rejects.
- **Targets.** Swing targets were missing, so targets differed.

Fix: the structure is now plain `var` state, inlined for 1H and 15m (no objects, no methods). It is the same
algorithm as `engine.model.Structure`: 2-bar fractals, BOS/CHoCH, protected low/high flips, a 13-candle buffer,
each HTF candle processed on the 5m bar that closes it.

## Every pre-fix difference, by cause

| Cause | Trades |
|---|---|
| No setup on TradingView: the swept pool was a 15m/1H swing level that never existed there | 21 Python-only |
| Knock-on: TradingView had taken a different (counter-trend) trade that day and stopped after a winner | 1 Python-only |
| Python rejected the setup as counter-1H-trend (score < 1); TradingView had no trend term | 3 TradingView-only |
| Knock-on: Python was already done for the day (stop after a winner / 2 trades) | 2 TradingView-only |
| Same entry, different target (Python's swing-pool target missing on TradingView) | 1 exit difference |
| Same trade | 2 |

The other candidate causes were checked and ruled out as count drivers on this window:
- **Risk too small (q < 1):** 1 consumed setup on each side.
- **Limited history / warm-up:** Python started cold on 2026-08-24 gives the same 25 trades.
- **Regime half-size:** affected size only. On TradingView it was switched on wrongly after the Sep 14 roll,
  e.g. 09-24.
- **maxTrades / stopAfterWin / dayStop:** only knock-on effects.
- **Fill model:** P&L only.

### Pre-fix trade list vs Python

| Entry (ET) | Side | Python (grade / qty, exit, R) | TradingView before the fix | Status | Cause |
|---|---|---|---|---|---|
| 08-24 14:40 | S | A+ / 5 TIME +1.77R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITH 29519.75, a 15m/1H swing level that never existed on TV |
| 08-25 14:35 | L | A+ / 6 GIVEBACK -0.18R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITL 29509.50, a 15m/1H swing level that never existed on TV |
| 08-27 11:20 | S | A / 18 TARGET +5.00R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITH 29917.75, a 15m/1H swing level that never existed on TV |
| 08-27 14:00 | S | - | C / 3 STOP -0.00R | TV ONLY | Python was done for the day (11:20 winner, stop after a winner); TV never had the 11:20 setup |
| 08-28 10:40 | S | - | C / 3 STOP -1.00R | TV ONLY | Python: confluence 0 < 1 (counter-1H-trend). TV had no 1H trend term, so its score was always the +1 clean-path point |
| 08-28 11:15 | S | B / 3 TARGET +5.03R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of EQH.H1H/ONH/ITH/ASH 30002.75, a 15m/1H swing level that never existed on TV |
| 08-31 09:40 | S | D / 3 STOP -1.01R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITH 29805.00, a 15m/1H swing level that never existed on TV |
| 08-31 14:40 | S | D / 1 TIME STOP -0.50R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of EQH.ITH 29738.75, a 15m/1H swing level that never existed on TV |
| 09-01 09:50 | L | - | D / 1 TIME STOP +0.02R | TV ONLY | Python: confluence 0 < 1 (counter-1H-trend), same reason |
| 09-01 11:05 | S | C / 2 GIVEBACK -0.07R | - | PY ONLY | TV was already done for the day: it took a counter-trend trade at 09:50 that Python rejected (score 0), and that trade won (stop after a winner) |
| 09-03 15:10 | S | D / 2 TIME +0.44R | D / 2 FLAT +0.45R | MATCH | same trade, same grade and size |
| 09-04 14:20 | L | A+ / 6 TIME +1.62R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of EQL.ITL 29771.50, a 15m/1H swing level that never existed on TV |
| 09-11 15:15 | L | C / 10 GIVEBACK -0.06R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITL 29712.00, a 15m/1H swing level that never existed on TV |
| 09-15 15:00 | L | A / 8 TIME STOP -0.57R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of EQL.ITL 29240.00, a 15m/1H swing level that never existed on TV |
| 09-17 14:45 | L | D / 6 TARGET +5.23R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITL 29717.25, a 15m/1H swing level that never existed on TV |
| 09-18 09:40 | L | D / 1 STOP -1.00R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITL 29767.50, a 15m/1H swing level that never existed on TV |
| 09-18 10:10 | L | C / 4 GIVEBACK -0.69R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITL 29744.50, a 15m/1H swing level that never existed on TV |
| 09-23 09:35 | S | D / 1 TARGET +3.58R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITH 30966.00, a 15m/1H swing level that never existed on TV |
| 09-24 10:45 | S | B / 4 BE/TRAIL -0.00R | D / 1 STOP -0.00R | MATCH | same trade; TV grade D vs Python B (no 1H trend / dealing-range points on TV) and half size: the unadjusted Sep 14 roll jump made the 10-day efficiency look trending. Size 1 vs 4 |
| 09-25 14:20 | S | A+ / 10 TARGET +4.78R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITH 30927.50, a 15m/1H swing level that never existed on TV |
| 09-29 09:40 | L | D / 2 STOP -1.01R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITL 30628.50, a 15m/1H swing level that never existed on TV |
| 10-06 09:35 | S | - | D / 2 GIVEBACK -0.68R | TV ONLY | Python: confluence -1 < 1 (counter-1H-trend, 3 obstacles), same reason |
| 10-06 11:30 | S | B / 6 TIME +4.01R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ONH/ITH 31539.25, a 15m/1H swing level that never existed on TV |
| 10-07 15:05 | S | B / 3 TIME STOP -0.63R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITH 31373.75, a 15m/1H swing level that never existed on TV |
| 10-08 09:45 | S | D / 2 BE/TRAIL -0.00R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITH 31268.75, a 15m/1H swing level that never existed on TV |
| 10-08 10:00 | L | D / 2 TARGET +4.19R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITL 31166.50, a 15m/1H swing level that never existed on TV |
| 10-08 10:40 | S | - | C / 2 TARGET +3.74R | TV ONLY | Python was done for the day (two trades already, 10:00 winner) |
| 10-12 14:15 | L | C / 6 STOP -1.01R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of ITL 30879.25, a 15m/1H swing level that never existed on TV |
| 10-12 15:20 | L | C / 5 TIME +1.08R | - | PY ONLY | no setup armed on TV: Python armed on a sweep of H1L/ITL 30857.75, a 15m/1H swing level that never existed on TV |
| 10-13 09:35 | L | D / 1 TARGET +2.09R | D / 1 STOP +0.00R | EXIT DIFF | same entry; TV grade D, size 1; Python target was a swing pool that did not exist on TV -> TV stopped at breakeven |

## Fixes in the script (and what each one is worth)

| Fix | Why | Effect on Aug 24 - Oct 16 (leave-one-out from the full fix) |
|---|---|---|
| 1H/15m structure as plain `var` state | root cause above | without it: 8 trades, 10% parity |
| Retire stale pools **before** adding prior-day / prior-week pools (engine order) | a new prior-week high landing on an older level was merged into it and deleted on the same bar | without it: 09-17 target 2.04R instead of 5.23R (prior-week high missing) |
| Roll shift from the back-adjusted copy of the symbol (`ticker.modify(..., backadjustment = backadjustment.on)`) | the engine trades back-adjusted NQ. Without the shift, every remembered level from before 2026-09-14 is 295.5 pts off for days, and the 10-day regime efficiency counts the roll jump | without it: 24 trades (09-23 missing), 09-24 size 2 instead of 4 |
| Rule exits fill at the signal close (`strategy.close_all(immediately=true)`), handled before new entries, flat on the session's last bar, realized day P&L | engine exits TIME / GIVEBACK / TIME STOP / NEWS FLAT at the close and may re-enter on the same bar | +$10.50 here. Over 2023-11..2024-10: 3 trades (holiday early close MLK 2024-01-15, same-bar re-entry 2024-05-28) |
| Swing pools born at the 1H/15m candle close | engine `t0` = HTF close. Decides whether a level survives a retirement boundary | no effect in the tested windows; kept for exactness |
| News list prefilled from the engine's calendar (`tools/pine_news.py`) | Python blocks 15 min before / 30 min after high-impact releases, no FOMC afternoons, flattens 5 min before; the old Pine default list was empty | none on this window. Over 2023-11..2024-10 an empty list gives 241 trades vs 179 (71% parity) |
| `sl=` in the entry comment | exact R in the parity tool | reporting only |

## Longer windows (replica on the engine's own bars)

TradingView only loads about 8 weeks, so the replica checked five one-year windows of the engine's back-adjusted NQ
history. The three Python-only features below were switched off on the Python side (`exit_learn` False,
`account_reset_cushion` 0, `contract` "micro"):

| Window | Python | Pine replica | Same entry | Same entry + exit + R |
|---|---|---|---|---|
| 2021-11-01 .. 2022-10-31 | 64 | 64 | 64 | 64 |
| 2022-11-01 .. 2023-10-31 | 52 | 52 | 52 | 52 |
| 2023-11-01 .. 2024-10-31 | 179 | 179 | 179 | 179 |
| 2024-11-01 .. 2025-10-31 | 143 | 143 | 143 | 143 |
| 2025-10-01 .. 2026-10-16 | 66 | 66 | 66 | 66 |

With those features on (the DEFAULTS), 2025-10..2026-10 gives Python 123 vs Pine 66. Two engine features cause it:
- **Account reset after a blown eval.** The engine reset the simulated account on 2025-12-16 and kept trading.
  Pine keeps the near-zero cushion and cannot size 1 micro.
- **Walk-forward exit learner.** It started acting on zone_reentry / opp_fvg / two_against exits.

Neither can be ported 1:1. See tradingview/BRIDGE_SETUP.md section 7.

## After the fix, trade by trade (TradingView Strategy Tester vs Python)

| # | Entry (ET) | Side | Python grade / qty | Python exit | Python R | Python $ | TV grade / qty | TV exit | TV R | TV $ | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 08-24 14:40 | S | A+ / 5 | TIME | +1.77 | +858 | A+ / 5 | FLAT | +1.77 | +857.50 | MATCH |
| 2 | 08-25 14:35 | L | A+ / 6 | GIVEBACK | -0.18 | -99 | A+ / 6 | GIVEBACK | -0.18 | -99.00 | MATCH |
| 3 | 08-27 11:20 | S | A / 18 | TARGET | +5.00 | +2,144 | A / 18 | TARGET | +5.00 | +2,133.00 | MATCH |
| 4 | 08-28 11:15 | S | B / 3 | TARGET | +5.03 | +1,587 | B / 3 | TARGET | +5.03 | +1,587.00 | MATCH |
| 5 | 08-31 09:40 | S | D / 3 | STOP | -1.01 | -174 | D / 3 | STOP | -1.01 | -174.00 | MATCH |
| 6 | 08-31 14:40 | S | D / 1 | TIME STOP | -0.50 | -52 | D / 1 | TIME STOP | -0.50 | -52.00 | MATCH |
| 7 | 09-01 11:05 | S | C / 2 | GIVEBACK | -0.07 | -20 | C / 2 | GIVEBACK | -0.07 | -20.00 | MATCH |
| 8 | 09-03 15:10 | S | D / 2 | TIME | +0.44 | +65 | D / 2 | FLAT | +0.44 | +65.00 | MATCH |
| 9 | 09-04 14:20 | L | A+ / 6 | TIME | +1.62 | +747 | A+ / 6 | FLAT | +1.62 | +747.00 | MATCH |
| 10 | 09-11 15:15 | L | C / 10 | GIVEBACK | -0.06 | -20 | C / 10 | GIVEBACK | -0.06 | -30.00 | MATCH |
| 11 | 09-15 15:00 | L | A / 8 | TIME STOP | -0.57 | -240 | A / 8 | TIME STOP | -0.57 | -240.00 | MATCH |
| 12 | 09-17 14:45 | L | D / 6 | TARGET | +5.23 | +822 | D / 6 | TARGET | +5.23 | +822.00 | MATCH |
| 13 | 09-18 09:40 | L | D / 1 | STOP | -1.00 | -109 | D / 1 | STOP | -1.00 | -109.00 | MATCH |
| 14 | 09-18 10:10 | L | C / 4 | GIVEBACK | -0.69 | -176 | C / 4 | GIVEBACK | -0.69 | -176.00 | MATCH |
| 15 | 09-23 09:35 | S | D / 1 | TARGET | +3.58 | +354 | D / 1 | TARGET | +3.58 | +354.50 | MATCH |
| 16 | 09-24 10:45 | S | B / 4 | BE/TRAIL | -0.00 | -6 | B / 4 | STOP | -0.00 | -6.00 | MATCH |
| 17 | 09-25 14:20 | S | A+ / 10 | TARGET | +4.78 | +1,286 | A+ / 10 | TARGET | +4.78 | +1,275.00 | MATCH |
| 18 | 09-29 09:40 | L | D / 2 | STOP | -1.01 | -160 | D / 2 | STOP | -1.01 | -160.00 | MATCH |
| 19 | 10-06 11:30 | S | B / 6 | TIME | +4.01 | +1,314 | B / 6 | FLAT | +4.01 | +1,314.00 | MATCH |
| 20 | 10-07 15:05 | S | B / 3 | TIME STOP | -0.63 | -180 | B / 3 | TIME STOP | -0.63 | -180.00 | MATCH |
| 21 | 10-08 09:45 | S | D / 2 | BE/TRAIL | -0.00 | -3 | D / 2 | STOP | -0.00 | -3.00 | MATCH |
| 22 | 10-08 10:00 | L | D / 2 | TARGET | +4.19 | +626 | D / 2 | TARGET | +4.19 | +626.00 | MATCH |
| 23 | 10-12 14:15 | L | C / 6 | STOP | -1.01 | -276 | C / 6 | STOP | -1.01 | -276.00 | MATCH |
| 24 | 10-12 15:20 | L | C / 5 | TIME | +1.08 | +280 | C / 5 | FLAT | +1.08 | +280.00 | MATCH |
| 25 | 10-13 09:35 | L | D / 1 | TARGET | +2.09 | +248 | D / 1 | TARGET | +2.09 | +248.50 | MATCH |
| | **Total** | | | | | **+8,816** | | | | **+8,784.50** | |

## Re-run

```
python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --parity      # replica of the current script vs engine
python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --legacy      # the pre-fix script (TradingView's old 8 trades)
python -X utf8 tools/pine_parity.py research/pine_parity/tv_trades_after_2026-10-16.csv --from 2026-08-24
python -X utf8 tools/pine_news.py --from 2026-10-18 --days 14                # news lines to paste into the strategy input
```

Every change to `tradingview/liquidity_engine.pine` should be mirrored in `tools/pine_sim.py` and re-checked with
`--parity` before it goes to TradingView.
