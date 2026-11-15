# ATM model on TradingView: Pine port notes

`tradingview/atm_model.pine`, strategy name **"ATM Model - NQ"**. It ports `tools/lab_models/atm.py` as of 2026-10-16
19:26 ET: `PARAMS`, `MTF_PARAMS`, `run_raw` (5m), `run_raw_mtf` (the 1m timeframe ladder) and `qty_for`. It also
follows `research/lab/ATM_RULES.md` as of 19:25 (sections C-G).

Every input default equals `atm.py`:
- target `opp`, **flat $350 sizing** (the `PARAMS` default since 19:26), 1 trade a day, entries 09:30-11:30 ET, flat
  15:55;
- on a 1m chart: ladder 5-3-1, V within 30 minutes, leg search 240 minutes.

Conventions copied from `tradingview/liquidity_engine.pine`:
- the ET clock and session math;
- clock-bucket HTF candles built from the chart's own bars;
- the contract-roll shift;
- the webhook JSON (TradersPost / PickMyTrade), `bTicker`, sync exits, PickMyTrade token / account inputs;
- the MLL-cushion cap (optional here);
- the flat-at-15:55 exit.

The file is ASCII only. It has no backticks, no `${` and no backslashes, so it survives being put into a JS template
string, raw or not. I could not compile it here, because TradingView has no offline compiler (section 1.5).

## 1. Load and run

1. **Chart: NQ1! (CME_MINI:NQ1!), extended hours ON, timezone New York.** The chart's timeframe picks the engine:
   - **5 minutes:** `atm.py run_raw` (`tf` 5), the 5m version.
   - **1 minute:** `atm.py run_raw_mtf` (`tf` 1), the owner's timeframe ladder ("highest timeframe IFVG").

   Other timeframes show a warning label. `atm.py` was tested on TradingView NQ1! bars; MNQ1! prints differ by a tick
   now and then, so **run parity checks on NQ1!**. For live trading either chart works; orders go to the bridge as MNQ
   either way.
2. Orders always go out in **MNQ micros** (input *Bridge ticker (micro)*, default `MNQ`). With *Send a full tier-A size
   (10 MNQ) as 1 NQ* on (tier sizing only), a 10-micro tier-A trade goes to *Bridge ticker (mini)* (`NQ`) as quantity
   1.
3. Strategy Tester on **NQ1!**: 3 micros are booked as 0.3 NQ so the tester dollars equal MNQ dollars. Set Properties >
   Commission to **7** per contract there (the default 0.70 is per micro). If TradingView rejects fractional sizes
   (0 trades), turn off *NQ1! chart: book micro-equivalents as fractional NQ*; entries, exits and R stay the same.
4. Alert as in `BRIDGE_SETUP.md` section 3: condition *ATM Model - NQ*, **Order fills and alert() function calls**,
   message `{{strategy.order.alert_message}}`, webhook = bridge URL. Re-create the alert after any input change.
5. If the editor rejects something, these are the newest Pine features used, with the minimal fix for each:
   - `syminfo.session` (warning label only): delete the label.
   - `box.new(text=...)`: delete the text arguments.
   - `label.new(tooltip=...)`: delete the tooltip.
   - Already compiled in the liquidity engine: `strategy.exit(comment_profit=, comment_loss=, disable_alert=)`,
     `backtest_fill_limits_assumption`, `ticker.modify(backadjustment=)`, `input.text_area`.
   - `request.security(ES1!, "5", f)` with a stateful function `f`: standard, but if it errors, ES is only used by two
     confluences (sizing only under tier sizing).

## 2. Timeframe approach (the choice)

**Both of the lead's options were weighed. The chosen design: the chart's own bars are the base frame, and every higher
frame is built from them causally.**

- **5m chart = `run_raw`.**
  - The model runs on the chart's 5m bars, exactly the `atm.py` frame.
  - 15m (FVGs for the path count) and 1H (BOS trend) come from those bars with the liquidity engine's bucket code. A
    candle is processed on the bar that completes it; a bucket missing its last bar is closed on the next bucket's
    first bar. That is `atm.py`'s "counted once its clock period has closed" rule.
- **1m chart = `run_raw_mtf` (ATM_RULES section G)**, the lead's option (a). 5m, 3m and (variant) 2m bars are built
  from the chart's 1m bars in clock buckets, under the same closed-bar rule (`_resample` / `_Frame.last_closed`).
  - At every 1m close after the sweep, the latest closed 5m bar is checked, then 3m, then the 1m bar. Each frame bar
    is evaluated once.
  - The first frame with a complete V + IFVG triggers the entry at that 1m close.
  - On the trigger frame, everything is measured on that frame: leg, V (within 30 minutes = 6 / 10 / 15 / 30 bars), IFVG
    and ATR.
  - The path / pool confluences use the 5m frame's swings and 15m gaps tapped by closed 5m bars, as `atm.py` does.
- **Not used: `request.security_lower_tf` on a 5m chart.** It cannot enter at a 1m close; `atm.py`'s ladder does. An
  approximation that fires only at 5m closes would not match `run_raw_mtf` trade for trade. I tried it first and
  dropped it once `run_raw_mtf` landed.
- **3m alone is not a separate chart option.** The ladder includes 3m, built from 1m.
- **Practical limit of the 1m chart:** TradingView loads about 10k bars on the owner's Plus plan, about **7 trading
  days of 1m**. That is enough to trade live, but a TradingView backtest on 1m covers only about a week (section 7).
  The 5m chart covers about 7-8 weeks.

## 3. Rule mapping (atm.py -> Pine)

| atm.py | Pine |
|---|---|
| `bars()` day = date of (ET + 6h), `mod` = ET minutes of the bar open | `dKey`, `mod`; trading day 18:00-17:00; the chart's first day is skipped |
| R1 range bars `[420, 570)`, >= half present, `RH > RL`, first RTH bar before 11:30 | `rngH/rngL/rngN`, `dayOk` on the first bar at/after 09:30 |
| mtf: skip a day after a data hole of more than 4 days | `gapMs > 4.5 days` (1m chart only) |
| R2 sweep 1 tick beyond arms; 1 tick through the other side kills | `lowHit/highHit`, `killL/killS`, from the 09:30 bar while bars open before 11:30 |
| R3 extreme (strictly lower low restarts), leg origin = last k=2 fractal confirmed by now within the lookback, else the first highest bar | `lE/lExt`; `f_signal` (chart bars) / `f_signalA` (frame arrays), `f_piv` / `f_pivA` |
| R4 V within N bars: reclaim close, >= 50% of the leg, displacement body >= 1 ATR14 or >= 60% of range (cumulative) | same; ATR = Wilder seeded with the first TR (`ewm(alpha=1/14, adjust=False)`), per frame |
| R5 IFVG of the leg, >= 1 tick, not closed through before e, close through from max(e, c3+1) | same (suffix max for "closed through inside the leg", as `_frame_signal`) |
| G3 ladder: frames 5 -> 3 (-> 2) -> 1 at each 1m close, latest closed bar once (`s["last"]`), dead when no frame is inside its window | `f_ladder`, `lV5..lV1`, `lE5/lE3/lE2` |
| R6 entry = signal close; a skipped signal uses up the extreme | `entered`, `lDead := true` |
| R7 / G5 stop = extreme -/+ max(2 ticks, 0.1 x ATR14 of the trigger frame) | `stopPx`, `atrTf`; the order price is rounded one grid step outward (section 4) |
| R8 skip if the opposite side < 1.5R, or `size(R + 0.25, $350) < 1` | same, with a gray "skip" label |
| R8 targets (a) `opp` (b) `first_clear` (c) `partial` | `tgtMode`; `f_firstClear`, `f_eqPools`, `f_nres` (1m chart: 5m swings, EQ untaken on 1m from the swing's confirmation) |
| R9 flat at the close of the bar opening 15:50 (5m) / 15:54 (1m); 1 trade a day | `strategy.close_all(immediately=true)` at `mod >= flatMod - tf`, `session.islastbar`, new-day safety net |
| D confluences, G6 (`v_fast` = first 1m close back inside within 10 min, `ifvg_big` with the trigger frame's ATR, tol from the last closed 5m ATR) | `cTrend, cSmt, cRs, cOpen, cBig, cFast, cLrlr, cPool`; ES from `request.security(ES1!, "5")` |
| E tiers, `qty_for` (flat default; DLL cut) | same; realized day P&L from TradingView's fills, in micro dollars |

## 4. Fill model and costs

- `process_orders_on_close=true`: the market entry fills at the signal bar's close + 1 tick (`slippage=1`). That is
  `make_trade`'s entry + `SLIP_PTS`. The bracket is live from the next bar, like `sim()` from `i0 + 1`.
- **Stop:** `atm.py`'s stop is usually off the 0.25 grid (ATR buffer) and triggers on `low <= stop`. The order goes
  at the stop rounded down (long) or up (short) to the grid, which triggers on exactly the same bars. The fill is the
  grid stop minus 1 tick of slippage, or the open on a gap (`atm.py`: `min(open, stop)` minus 1 tick), so it differs
  by less than 1 tick. The entry comment carries the exact model stop (`sl=`) for `pine_parity.py`.
- **Targets:** the limit sits 1 tick inside the level, and `backtest_fill_limits_assumption=1` fills it when price
  reaches the level. That is `atm.py`'s `hi >= level`, filled at `level - 1 tick`, no slippage.
- **Time exit:** the close of the flat bar minus 1 tick. Also on `session.islastbar` (holiday early close) and if a
  position ever reaches a new trading day.
- **Commission:** $0.70 per contract per fill = $1.40 round trip per micro (`strategy_lab.COMMISSION_RT`).
- **Precedence:** stop and target fill intrabar before the bar-close time exit, matching `atm.py` (stop, TP1, target,
  15:55).

## 5. What was verified here (no TradingView needed)

I wrote a literal Python transcription of the Pine logic for each engine: bar by bar, Pine-style offsets and frame
arrays, the same incremental state. I ran it against `atm.run_raw` / `atm.run_raw_mtf` on the lab's data:
`data/NQ_5m.csv` + `data/ES_5m.csv`, and the stitched TradingView 1m file `data/clean/NQ_1m_tv.csv` (209 sessions,
2025-12-29..2026-10-16).

It compares:
- entry time, side, price and stop;
- the trigger frame;
- all 8 confluences, score and tier;
- the first-clear pool level.

It matched exactly in every configuration:

| engine | config | window | atm.py | Pine logic | identical |
|---|---|---|---:|---:|---:|
| 5m | base (`PARAMS`) | 2025-04-14 .. 2026-10-16 | 11 | 11 | 11 |
| 5m | `min_rr` 1.0 | 18 months | 28 | 28 | 28 |
| 5m | `min_rr` 0 + `first_clear` | 18 months | 91 | 91 | 91 |
| 5m | `min_rr` 0, `v_bars` 8, `v_retrace` 0.618, `partial`, `entry_end` 720 | 18 months | 83 | 83 | 83 |
| 1m ladder | `m1_base` | 1m file | 58 | 58 | 58 |
| 1m ladder | `m1_nbars6` (`v_bars_fixed` 6) | 1m file | 48 | 48 | 48 |
| 1m ladder | `m1_tf5321` (ladder 5-3-2-1) | 1m file | 61 | 61 | 61 |
| 1m ladder | `min_rr` 1.0 + `partial` | 1m file | 96 | 96 | 96 |
| 1m ladder | `min_rr` 0 + `first_clear` | 1m file | 138 | 138 | 138 |

This checks the signal side: the logic, offsets and state machine of the port. It cannot check Pine compilation,
TradingView's broker emulator or `request.security` timing. In 18 months of 5m `atm.py` trades, including all 91
no-skip signals, **no bar touched both stop and target** and **no bar opened beyond the target**.

## 6. Known differences from the Python reference

**Fill model (unavoidable)**
1. **Stop and target in the same bar:** `atm.py` takes the stop; TradingView follows its OHLC path. 0 times on 5m.
2. **Gap through the target:** TradingView fills the limit at the better open; `atm.py` fills at the limit. 0 times.
3. **Stop fill price:** up to 1 tick from `atm.py`'s (grid rounding). The trigger bar is the same; R differs by about
   0.01-0.03.
4. **Partial mode only:**
   - The stop-to-entry move is placed at the TP1 bar's close. If that close is already back through the entry,
     TradingView fills it there; `atm.py` acts on the next bar.
   - TradingView lists the TP1 leg and the runner as two trades.

**Data**

5. **Back-adjusted vs raw prices.** `atm.py`'s files are back-adjusted to the front month; TradingView shows raw prices.
   - Within a day the offset is constant, so entries, stops, targets and R are identical.
   - Cross-day memory (prior day / prior RTH, 1H structure, 15m FVGs, the ATR's previous close) is shifted by the roll
     gap at a roll, as in the liquidity engine.
   - Residual: `nq_rs_with` compares percent changes on raw prices. Before the last roll that differs by about 1%
     relative, which can flip that one confluence (tier only).
6. **History start.** The 1H trend and the ATR seeds depend on where the chart's history begins, so the first days on
   TradingView can have a different `trend_1h_with` (tier only). The 1m chart's short history (about 7 days) makes
   this more likely there.
7. **ES timing.**
   - On history, `request.security(ES1!, "5")` returns the ES 5m state as of the last closed ES bar (lookahead off).
     That is what `atm.py` uses (ES bars closed by the signal).
   - In real time on a 1m chart it returns the forming ES 5m bar, so the SMT / NQ>ES flags can differ intrabar. This
     matters for tier sizing only.
8. **1m chart, a 5m bucket with a missing last minute:** the highest-since-confirmation value of a 5m swing (first-clear
   EQ pools only) skips the first 1m bar of the next bucket. This is rare: it needs a missing 1m bar.

**Rules / scope**

9. **Holiday early closes:** `atm.py` exits on the day's last bar; Pine uses `session.islastbar` (UNVERIFIED in real
   time) plus the new-day safety net.
10. **`max_trades_day` 2 with the DLL cutting a trade to 0 micros:** `atm.py`'s unsized raw trade still blocks the scan
    until its exit; Pine resumes on the next bar. This cannot happen at 1 trade a day.
11. **`skip_news`** (off in both): `atm.py` reads `data/news/events.csv`; Pine needs the dates pasted into *Days to
    skip*.
12. **Pine-only options, all off by default:**
    - the MLL-cushion cap (on, it caps risk at $500 at the start of an eval with a $2,000 cushion);
    - tier A routed as 1 NQ (bridge routing only, same risk).

**Live (not backtest)**

13. Entries are market orders sent at the bar close; bridge, Tradovate and real slippage add their own differences.
    TradersPost's `breakeven` (partial mode) moves the stop to the average fill, not the signal close.
14. **Partial mode over the bridge is UNVERIFIED.** The TP1 message is an `exit` with a `quantity` (TradersPost) or a
    `close` with `full_closed:false` (PickMyTrade). If the broker bracket keeps its full size after a partial, a stop
    fill could over-fill. Use target `opp` or `first_clear` live until it has been paper-tested.

## 7. How to run the parity check

`tools/pine_parity.py` provides `read_tv()` (the TradingView *List of trades* export) and `compare()`. Its built-in
Python side is the Liquidity Engine, so feed it `atm.run()` instead.

1. On TradingView: NQ1!, 5m or 1m, ETH, chart timezone **New York**, the strategy with the inputs to check. Then
   Strategy Tester > List of trades > Export (CSV).
2. From the `nqbot` folder in PowerShell (edit the top lines; `ENGINE` is `"5m"` or `"1m"`):

```powershell
@'
import sys
sys.path.insert(0, ".")
from tools import pine_parity as pp
from tools.lab_models import atm
from tools.strategy_lab import bars
from tools.lab_atm_run import load_1m_stitched

CSV = r"C:\Users\<you>\Downloads\ATM_Model_-_NQ.csv"   # the export
A, Z = "2026-08-24", "2026-10-16"                               # first / last trading day in the export
ENGINE = "5m"                                                   # chart timeframe: "5m" or "1m"
PARAMS = {}                                                     # chart inputs changed from default, atm.py names

es = bars("ES", "5m", A, Z, warmup_days=10)
if ENGINE == "1m":
    nq = load_1m_stitched()
    PARAMS = {**PARAMS, "tf": 1}
else:
    nq = bars("NQ", "5m", A, Z, warmup_days=10)
py = [dict(entry_t=t["entry_t"], dir=t["dir"], entry=t["entry"], exit=t["exit"], exit_t=t["exit_t"],
           risk_pts=t["risk_pts"], qty=t["qty"], reason=t["exit_kind"], grade=t["tier"], pnl_r=t["r"])
      for t in atm.run(nq, PARAMS, es)]
pp.compare(py, pp.read_tv(CSV), day_from=A, day_to=Z)
'@ | python -X utf8 -
```

3. Read the result:
   - **Expect 100% entry parity**, and the same exit class (TARGET / STOP / TIME) with R within the 0.3 tolerance.
   - TradingView shows the signal bar's open time and `atm.py` its close time, so `dt` reads -5 min on 5m and -1 min on
     1m. Both are inside the 10-min tolerance.
   - A `PY ONLY` / `TV ONLY` row means a different chart (MNQ1!, RTH session, another timeframe), different inputs, or
     one of the differences in section 6.
   - In partial mode every TP1 leg shows as an extra `TV ONLY` row.
4. **The default configs trade too rarely for a strong check inside TradingView's history.**
   - **5m base:** 11 trades in 18 months; 1 in Aug 24 - Oct 16 (2026-10-02 short, time exit, +0.92R).
   - **1m `m1_base`:** about 1.4 a week, but the 1m chart only loads about 7 trading days. In Oct 7-16 there is 1 trade
     (2026-10-14 long, 3m-triggered, stop).
   - Add a pass with *Skip if the opposite ATM side is closer than (R)* = **0** on the chart and
     `PARAMS = {"min_rr": 0.0}`. That gives 12 5m trades in Aug 24 - Oct 16 and exercises the whole entry chain.
     Optionally also set *Target* = `first_clear` / `"target": "first_clear"`.

   Chart input names to `atm.py` keys:

   | chart input | `atm.py` key |
   |---|---|
   | *Skip if the opposite ATM side is closer than (R)* | `min_rr` |
   | *Target* | `target` |
   | *V within N bars* (5m) | `v_bars` |
   | *V within N minutes* (1m) | `v_minutes` |
   | *Or V within this many trigger-frame bars* | `v_bars_fixed` |
   | *Ladder* 5-3-2-1 | `ladder: [5, 3, 2, 1]` |
   | *Max trades / day* | `max_trades_day` |
   | *Sizing* | `sizing` |

## 8. Before using it for money

`research/lab/ATM_REPORT.md` (19:30) finds no edge in either version:
- 5m base: 0.17 trades a week;
- 1m ladder: about 1.4 a week, break-even over 2026, all variants losing from July, max drawdown $3.2k-4.4k against the
  $2k MLL.

It recommends not automating the model for money and not using the tiers; at most, paper-run `m1_base` beside the
owner's own entries. The Pine reproduces the Python model; it does not change that verdict. For a paper run use the 1m
chart, the defaults, and the bridge's paper/demo subscription.

## 9. If `atm.py` changes

Any change to `PARAMS`, `MTF_PARAMS`, `run_raw` or `run_raw_mtf` needs the same change in the Pine. Then re-run the
parity check above, or ask for the logic-transcription check of section 5. That throwaway script was not committed.
