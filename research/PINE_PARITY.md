# Pine vs Python parity (TradingView strategy vs engine/model.py)

## 2026-10-17 (evening lock): the locked strategy on TradingView

`tradingview/liquidity_engine.pine` trades the locked strategy (`live_model.json` + `STRATEGY.md`, evening lock of
2026-10-17) instead of the old $350 rules. Everything below was measured with `tools/pine_sim.py`, the bar-by-bar
replica of the script and of TradingView's fill model. On 2026-10-16 that replica reproduced TradingView's Strategy
Tester exactly (section below), and it still does (`--preset oct16`: 25 trades, +$8,784.50, PF 6.76; `--legacy`: 8
trades, +$547.50). The new script itself has not run on TradingView yet: there is no Pine compiler here (list of
constructs to check below).

### What changed in the script

| Rule | Before (2026-10-16) | Now (evening lock 2026-10-17, = the Python bot) |
|---|---|---|
| Risk per trade | $350 (x A+..D grade until 10-16) | **$800 up to a 20-pt stop**, wider stops $800 x 20 / stop (input "Full risk up to a stop of") |
| MLL cushion cap | on (25% of the cushion above the trailing MLL) | **off** (input kept under "Old rules") |
| Trades per day | 1 (2 until 10-16) | **1** |
| No major pool >= 1.5R | 2R fixed target | **no trade** (the setup is consumed, like the engine); input "fixed-R target instead of no trade" |
| Cold-streak filter | none | **last 15 closed trades sum <= 0R: micros x 0.25** (input "Size in a cold streak"; the morning lock had 0.5) |
| Late entry | none | **15m structure already turned the trade's way at the signal: micros x 0.5** (input "Size on a late entry") |
| Size rounding | | cold x late multiplied, **rounded down once, at least 1 micro** (`engine/sizing.py`) |
| Breakeven | +1R | **+1R, or +3R on a trending day** (10-day efficiency > 0.45, the same test that halves the size); input "Breakeven at (R) on trending days" |
| Alerts | bridge JSON | input **Alert format: Bridge JSON (TradersPost / PickMyTrade) or Phone text** |
| On the chart | entry labels | labels show size, "cold" and "late"; **status box** (version, risk rule, cold-streak state, today's trades, alert format) |
| Entry comment | `L r=.. sl=.. g=..` | same, plus ` cold` / ` late` when the size was cut (read by `tools/pine_parity.py`) |

Unchanged (already 100% at parity): pools, sweeps, IFVG/CISD trigger, confluence score, stop rules, 5R cap, time stop,
giveback, 15:55 flat, news blackout, regime half size, day-range filter, stop after a winner, $600 daily stop, roll
shift. The sizing is one function (`f_size`) with one step per rule in the engine's order, so a new size rule is one
input plus one line there (and the same line in `pine_sim.py`).

**Late entry.** The flag is the script's `m15al` (the -1 item of the confluence score: 15m trend == trade direction at
the signal bar), the same test as `engine/sizing.py is_late` (`m15_trend x dir > 0` on the order).

**Cold-streak record on TradingView.** The script stores the R of every closed trade: net result / (entry fill to the
stop at entry x contracts x $2), 3 decimals. Before each entry it adds up the last 15 (rounded to 2 decimals); 0R or
less, with at least 15 trades closed, means cold. TradingView can only use the trades in the loaded chart history
(about 8 weeks, roughly 15-25 trades), so the filter is at full size until 15 trades have closed on the chart. The
Python bot reads its shadow ledger instead (`data/shadow_ledger.json`). Once the chart holds 15 closed trades, both use
the same last 15 trades. The status box shows which state TradingView is in; input *Override* forces full or cold
if the chart is too short and the Python dashboard disagrees.

### Result

| Window | Python | TradingView | Same entries | Same entry + exit + R | Same size | Net TradingView | Net Python |
|---|---|---|---|---|---|---|---|
| Aug 23 - Oct 16 2026 (MNQ1! export), Python on the **same MNQ1! bars** | 22 | 22 | 22 | 22 | 22 | +$13,733.50 | +$13,733.50 |
| Same window, Python on its own **NQ1!** bars (`data/NQ_5m.csv`) | 22 | 22 | 20 | 19 | 15 | +$13,733.50 | +$15,736.50 |
| 5 years, Oct 2021 - Oct 2026, the engine's NQ1! bars on both sides | 780 | 780 | 780 | 780 | 780 | +$37,362.00 | +$37,362.00 |
| 5 years replayed as the unadjusted contract + roll shift (20 rolls) vs back-adjusted | 780 | 780 | identical trades, sizes and $ | | | | |
| For reference, the morning lock (`--preset am`: cold x0.5, no late rule, BE 1R): 5 years | 780 | 780 | 780 | 780 | 780 | +$26,823.50 | +$26,823.50 |

Python $ here is the engine's trade re-priced with TradingView's commission ($1.50 per MNQ round trip). The engine's own
books are higher (+$38,831.75 over 5 years) because it counts every 10 micros as one NQ mini ($4.50). TradingView and
the bridge trade MNQ only.

**Size cuts: the same trades on both sides.** Over 5 years the cold-streak cut hit the same 373 of 780 trades and the
late-entry cut the same 102; every one of the 780 sizes is equal. In the 8-week window the cold streak never fired
(the first 15 trades summed well above 0R; the record ends at +16.23R) and 4 trades were late entries (08-31, 09-01,
09-29, 10-08: 5, 1, 2 and 2 micros instead of 10, 2, 5 and 4). The trending-day breakeven changed no trade in that
window; over 5 years it is part of the 780/780 match.

R definition check: TradingView's R (own net result) and the engine's ledger R (mini commissions) differ by at most
0.054R per trade. The 15-trade sums differ by at most 0.29R (mean 0.07R). They never disagreed on full vs cold in the
765 entries with a full record. 20 entries were within 0.29R of the line, so a rare disagreement is possible; data
differences live (below) are much larger than that.

### The only source of mismatches: MNQ1! vs NQ1! prints

TradingView trades MNQ1! prints. `data/NQ_5m.csv` now holds NQ1! prints: it was rebuilt from TradingView NQ1! exports
on 2026-10-16 (commit 1278527). When the 2026-10-16 parity check ran, those weeks still held MNQ1! prints. MNQ and NQ
differ by a tick or two on many bars, so a trigger close can land on the other side of a gap, a stop distance can
change by a tick, and the 15m structure can turn one bar earlier or later:

| Entry (ET) | TradingView (MNQ1!) | Python on NQ1! | Cause |
|---|---|---|---|
| 08-27 11:20 S | 33 micros, TARGET +5.00R, +$3,910.50 | 30 micros, TARGET +5.37R, +$3,900 | stop distance 12.00 vs 13.25 pts |
| 09-11 15:15 L | 32 micros | 31 micros | stop distance |
| 09-15 15:00 L | TIME STOP, 12 micros, -$360 | no trade | NQ: the setup armed but no IFVG close-through before it expired |
| 09-17 14:45 L | 29 micros, +$3,973 | 28 micros, +$3,892 | stop distance |
| 10-06 11:30 S | 10 micros, +$2,190 | 11 micros, +$2,409 | stop distance |
| 10-08 09:45 S | late entry: 2 micros, -$3 | not late: 4 micros, -$6 | the 15m structure had turned on MNQ, not yet on NQ |
| 10-12 L | 14:15 STOP, 16 micros, -$736 | 15:20 TIME, 13 micros, +$734.50 | NQ: the 14:10 trigger close did not clear the gap; it triggered at 15:15 instead |
| 10-15 13:55 S | no trade | breakeven stop, -$4.50 | MNQ: no trigger |

Proof that this is data, not the port: with the engine run on the same MNQ1! bars (`--py-bars`), every trade, size and
dollar matches (first table row). The real TradingView list from 2026-10-16 (old script) also matches 25/25 again that
way. Against today's NQ1! file it is 79%.

What it means live: the TradingView bot and the Python bot (NQ data) will now and then take a different trade or size
by a micro or two. Over 5 years the effect is noise, not bias. On identical bars the two are the same strategy.

### What the owner should see in TradingView's Strategy Tester

MNQ1!, 5 minutes, ETH, chart timezone New York, script defaults, history Aug 23 2026 18:00 to Oct 16 2026 07:10 (the
2026-10-16 export, `data/tv_mnq_5m_2026-10-16.csv`):

| Strategy Tester figure | Expected |
|---|---|
| Total closed trades | 22 |
| Net profit | +$13,733.50 |
| Gross profit / gross loss | $15,904.00 / $2,170.50 |
| Profit factor | 7.33 |
| Percent profitable | 45.45% (10 wins, 12 losses) |
| Avg trade | +$624.25 |
| Largest winning / losing trade | +$3,973.00 / -$736.00 |
| Commission paid | $288.00 |
| Max drawdown | not reproduced exactly: TradingView includes open-trade swings. The closed-trade drawdown is -$919 |

(The morning lock gave 22 trades, +$13,190.50, PF 5.86 on the same window; the difference is the four late-entry
sizes.)

Every trade, in TradingView's "List of trades" layout: `research/pine_parity/expected_tv_trades_locked_2026-10-16.csv`.

| # | Entry (ET) | Side | Micros | Exit | $ |
|---|---|---|---|---|---|
| 1 | 08-24 14:40 | S | 3 | FLAT 15:55 | +514.50 |
| 2 | 08-25 14:35 | L | 4 | GIVEBACK | -66.00 |
| 3 | 08-27 11:20 | S | 33 | TARGET | +3,910.50 |
| 4 | 08-28 11:15 | S | 2 | TARGET | +1,058.00 |
| 5 | 08-31 09:40 | S | 5 (late entry, half) | STOP | -290.00 |
| 6 | 09-01 11:05 | S | 1 (late entry, half) | GIVEBACK | -10.00 |
| 7 | 09-03 15:10 | S | 5 | FLAT 15:55 | +162.50 |
| 8 | 09-04 14:20 | L | 5 | FLAT 15:55 | +622.50 |
| 9 | 09-11 15:15 | L | 32 | GIVEBACK | -96.00 |
| 10 | 09-15 15:00 | L | 12 | TIME STOP | -360.00 |
| 11 | 09-17 14:45 | L | 29 | TARGET | +3,973.00 |
| 12 | 09-18 09:40 | L | 2 | STOP | -218.00 |
| 13 | 09-23 09:35 | S | 3 | TARGET | +1,063.50 |
| 14 | 09-24 10:45 | S | 5 | STOP (breakeven) | -7.50 |
| 15 | 09-25 14:20 | S | 15 | TARGET | +1,912.50 |
| 16 | 09-29 09:40 | L | 2 (late entry, half) | STOP | -160.00 |
| 17 | 10-05 10:00 | S | 1 | GIVEBACK | -44.00 |
| 18 | 10-06 11:30 | S | 10 | FLAT 15:55 | +2,190.00 |
| 19 | 10-07 15:05 | S | 3 | TIME STOP | -180.00 |
| 20 | 10-08 09:45 | S | 2 (late entry, half) | STOP (breakeven) | -3.00 |
| 21 | 10-12 14:15 | L | 16 | STOP | -736.00 |
| 22 | 10-13 09:35 | L | 2 | TARGET | +497.00 |

Your chart will not start at exactly the same bar: TradingView loads a fixed number of bars back from the newest one.
Tested starts from Aug 24 09:30 to Aug 25 18:00 only drop the earliest trades; every remaining trade is identical. A
chart that starts on a Sunday evening can change that first day's trade (no prior-day levels yet: from Aug 30 18:00 the
Aug 31 trade is a 15:15 long of 1 micro instead of the 09:40 short). A chart opened on the weekend also includes Oct 16
after 07:10. The NQ1! data has no trade that afternoon.

### 2026 and 5 years: replica vs the official baseline

The official numbers (`research/runs/baseline.json`, rebuilt 2026-10-17 21:04; `python tools/runlib.py show baseline`)
replay the live loop: a fresh 20-day window every session. TradingView runs straight through its chart, like this
replica.

| | 2026 replica | 2026 baseline | 2021-25 replica | 2021-25 baseline | 5y replica | 5y baseline |
|---|---|---|---|---|---|---|
| Trades | 89 | 89 | 681 | 679 | 770 | 768 |
| Per week (% weeks with 2+) | 2.16 (71%) | 2.16 (71%) | 3.18 (92%) | 3.17 (92%) | 3.01 (89%) | 3.00 (89%) |
| Win rate | 25.8% | 25.8% | 21.1% | 21.1% | 21.7% | 21.6% |
| Profit factor | 3.86 | 3.94 | 1.24 | 1.27 | 1.50 | 1.54 |
| Net | +$20,110 | +$20,487 | +$15,001 | +$16,379 | +$35,111 | +$36,866 |
| Max drawdown | -$2,271 | -$2,249 | -$9,461 | -$9,265 | -$9,461 | -$9,265 |
| Cold-streak trades (x0.25) | 26 | 25 | 347 | 348 | 373 | 373 |
| Late-entry trades (x0.5) | 11 | | 91 | | 102 | |
| MFFU eval pass / fail within 2 weeks | 20.8% / 0% | 20.8% / 0% | 4.1% / 2.0% | 4.1% / 1.9% | 6.7% / 1.7% | 6.7% / 1.6% |
| Within 1 month | 31.6% / 0% | 31.6% / 0% | 8.8% / 6.4% | 8.9% / 5.3% | 12.2% / 5.3% | 12.5% / 4.4% |
| Back-to-back evals passed / failed | 4 / 1 | 4 / 1 | 8 / 10 | 8 / 10 | 12 / 11 | 12 / 11 |

Same entries: 766 of 770 / 768, same size on 762. The net gap is mostly commission (MNQ-only $1.50 vs the engine's
minis: -$1.5k over 5 years) plus the few trades the 20-day window changes. Expect TradingView to land close to the
official numbers, a little lower.

### Pine constructs to check on the first compile

There is no Pine compiler here. The new code uses the same constructs as the parts that already ran on TradingView
(multi-line ternaries, tuples from functions, var arrays, `strategy.close_all(immediately=true)`, `comment_profit` /
`comment_loss`, which printed TARGET / STOP in the 2026-10-16 trade list). New, and not yet seen compiling:
1. `strategy.exit(..., alert_profit=..., alert_loss=...)` (4 calls). They set the phone-text "TARGET HIT" / "STOP HIT"
   messages. They were added to Pine together with `comment_profit` / `comment_loss`, which do compile. If the editor
   rejects them, delete the `alert_profit=...` and `alert_loss=...` arguments: the bracket alert then sends
   `alert_message` (bridge exit JSON, or the phone text "STOP OR TARGET HIT ... check your broker").
2. `math.round(x, 2)` / `math.round(x, 3)` (round with a precision argument), in `f_tradeR` and `f_coldState`.
3. `str.tostring(x, "#,##0.00")` and `"#,##0"` (thousands separators in phone text). This always compiles; if the
   output looks wrong, change the pattern to `"#.00"` / `"#"`.
4. `table.new` / `table.cell(..., text_halign=text.align_left)` for the status box. Turn the box off with input *Show
   the status box* if it misbehaves.
5. The middle dot `·` in strings (phone text). Plain Unicode; replace it with `-` if the push notification shows junk.
6. `strategy.closedtrades.entry_price(k)`, `.size(k)` and `.profit(k)` read in a loop. All standard v5.
7. `f_plan` returns a 10-element tuple (`[ok, stop, target, score, qty, grade, pts, risk, qtyFull, late]`); the 9-element
   version is what the 2026-10-16 script used, so this is only one element more.

Runtime checks after the first compile:
- The status box shows "Liquidity Engine eval mode 2026-10-17 evening" and, on its second line, "late entry x0.5 · BE
  1R (3R trending)".
- Strategy Tester figures as in the table above; the four late entries carry "late" in their labels and entry comments.
- Data Window: "Cold streak: R of the last N trades" is na until 15 trades have closed, then +16.23 at the end of this
  window.

### Re-run

```
python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --parity --py-bars   # port only: engine on the same MNQ1! bars
python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --parity             # vs the engine on its NQ1! file
python -X utf8 tools/pine_sim.py --parity                                           # 5 years on the engine's bars (~45 s)
python -X utf8 tools/pine_sim.py --unadjust                                         # same, as TradingView sees it (roll shift)
python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --alerts --set "alertFmt=Phone text"   # every alert text
python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --preset am          # the morning lock (22 trades, +$13,190.50)
python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --preset oct16       # the 2026-10-16 script (25 trades)
python -X utf8 tools/pine_parity.py "<TradingView List of trades export>.csv" --from <first day on the chart>
python -X utf8 tools/pine_parity.py research/pine_parity/tv_trades_after_2026-10-16.csv --defaults --no-cold --from 2026-08-24 --py-bars data/tv_mnq_5m_2026-10-16.csv
```

Results: `research/pine_parity/parity_locked_2026-10-16.json` (NQ1! engine),
`parity_locked_2026-10-16_mnq_bars.json` (same bars), `parity_locked_5y.json`, and the expected trade list
`expected_tv_trades_locked_2026-10-16.csv`. The morning lock's versions of these files are in commit a603087.

If `live_model.json` changes, change the same input in the script and `DEFAULT_INPUTS` in `tools/pine_sim.py`, then
re-run `--parity`. It warns when the cold-streak size, the late-entry size or the trending-day breakeven differ from
`live_model.json`.

---

## 2026-10-16: why TradingView took 8 trades instead of 25 (old rules, fixed)

2026-10-16. Question: why did the TradingView strategy (`tradingview/liquidity_engine.pine`, saved as
"Liquidity Engine - Sweep IFVG DOL" on the "Liquidity Engine Bot" layout, CME_MINI:MNQ1! 5m ETH) take 8 trades
when the Python engine took 25 on the same weeks, and can the gap be closed?

### Result

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

### How it was measured

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
- The engine's NQ bars for these weeks were then the same TradingView MNQ1! prints (same OHLCV), back-adjusted to NQZ26
  (since commit 1278527 `data/NQ_5m.csv` holds NQ1! prints; see the 2026-10-17 section).
  Before the 2026-09-14 18:00 roll they sit +295.5 pts above the raw MNQ1! that TradingView shows.

### Root cause: the 1H / 15m structure never ran on TradingView

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

### Every pre-fix difference, by cause

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

#### Pre-fix trade list vs Python

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

### Fixes in the script (and what each one is worth)

| Fix | Why | Effect on Aug 24 - Oct 16 (leave-one-out from the full fix) |
|---|---|---|
| 1H/15m structure as plain `var` state | root cause above | without it: 8 trades, 10% parity |
| Retire stale pools **before** adding prior-day / prior-week pools (engine order) | a new prior-week high landing on an older level was merged into it and deleted on the same bar | without it: 09-17 target 2.04R instead of 5.23R (prior-week high missing) |
| Roll shift from the back-adjusted copy of the symbol (`ticker.modify(..., backadjustment = backadjustment.on)`) | the engine trades back-adjusted NQ. Without the shift, every remembered level from before 2026-09-14 is 295.5 pts off for days, and the 10-day regime efficiency counts the roll jump | without it: 24 trades (09-23 missing), 09-24 size 2 instead of 4 |
| Rule exits fill at the signal close (`strategy.close_all(immediately=true)`), handled before new entries, flat on the session's last bar, realized day P&L | engine exits TIME / GIVEBACK / TIME STOP / NEWS FLAT at the close and may re-enter on the same bar | +$10.50 here. Over 2023-11..2024-10: 3 trades (holiday early close MLK 2024-01-15, same-bar re-entry 2024-05-28) |
| Swing pools born at the 1H/15m candle close | engine `t0` = HTF close. Decides whether a level survives a retirement boundary | no effect in the tested windows; kept for exactness |
| News list prefilled from the engine's calendar (`tools/pine_news.py`) | Python blocks 15 min before / 30 min after high-impact releases, no FOMC afternoons, flattens 5 min before; the old Pine default list was empty | none on this window. Over 2023-11..2024-10 an empty list gives 241 trades vs 179 (71% parity) |
| `sl=` in the entry comment | exact R in the parity tool | reporting only |

### Longer windows (replica on the engine's own bars)

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

### After the fix, trade by trade (TradingView Strategy Tester vs Python)

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

### Re-run (2026-10-16 study)

```
python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --preset oct16    # the fixed script of 2026-10-16 (25 trades)
python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --legacy          # the pre-fix script (TradingView's old 8 trades)
python -X utf8 tools/pine_parity.py research/pine_parity/tv_trades_after_2026-10-16.csv --defaults --no-cold --from 2026-08-24 --py-bars data/tv_mnq_5m_2026-10-16.csv
python -X utf8 tools/pine_news.py --from 2026-10-18 --days 14                    # news lines to paste into the strategy input
```

`--defaults --no-cold` compares with the engine DEFAULTS of that day instead of `live_model.json`; `--py-bars` runs the
engine on the MNQ1! export, because `data/NQ_5m.csv` has held NQ1! prints since commit 1278527.

Every change to `tradingview/liquidity_engine.pine` should be mirrored in `tools/pine_sim.py` and re-checked with
`--parity` before it goes to TradingView.
