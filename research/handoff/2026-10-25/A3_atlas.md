# A3 - ATLAS pre-launch audit (account B, MFFU Builder 25K), 2026-10-25

Agent 3 of 5. Scope: ATLAS = three INDEPENDENT setups pooled on account B (never an agreement rule):
`ema_lon_vix` = **ATLAS_LONDON_EMA**, `macd_sweep` = **ATLAS_MACD_SWEEP**, `sr_nyreclaim` = **ATLAS_NY_RECLAIM**.
Nothing was armed or routed. `second_model.json`, `engine/second.py`, `engine/account_b.py` and the research modules are
unchanged (no demonstrated live-vs-research bug was found, so there is no BUG_FIX). New: `tools/atlas_audit.py` (the evidence
script) and the CSVs in this folder.

Labels: **BASELINE** = today's code and config. **RESEARCH_VARIANT** = a what-if, not adopted. **BUG_FIX** = none.

## Verdict in one screen

1. **"One bar late" was a stress test, not what the live bot does.** It comes from `tools/second_robust.py:17` (`late1`:
   "every entry 1 / 2 five-minute bars later", an intentional robustness scenario). The live entry path does not run late.
   I re-derived every 2026 research trade the way `engine/account_b.AccountB.entry` does it (`engine/account_b.py:515-598`):
   bars cut at the decision bar's close, a flat probe bar at the real open, `now` = open + 2 s, the same `engine.second.run`.
   Result: **175 / 175 trades on the same bar with the same entry, stop and target** (EMA 86/86, MACD 44/44, S/R 45/45).
   The fill check after the fill bar closes also matches 175 / 175 (`PROBE_CHECK.csv`). Offset = 0 bars.
   The full scan probed every 5m open in each setup's window for all of 2026 (33,321 probes). The live path routes
   **exactly the 175 research entries: 0 false positives, 0 misses, 0 shifted** (`SCAN_<setup>.csv`).
2. **Prefix invariance holds.** Each setup's 2026 signals come out the same from data that stops at the decision bar. The
   code paths that could look ahead all wait for closed bars (section 2). The probe above is that test, run on all 175
   trades, not a sample.
3. **The dashboard ATLAS numbers are stale vs today's code (BASELINE re-run, `EVAL_25K_NOW.csv`).**
   - `research/second/atlas.json` still says 25K 2-week pass H1 72.3% and path +$19,737 (H1) / +$5,448 (H2) / +$2,232
     (2025) / +$9,919 (2021-24).
   - With the 2026-10-24 sizing-cap invariant in (`engine/sizing.py`, commit 15cb560) the same executor gives:
     - H1: p10 **62.2 / f10 0.0**, path **+$14,784**, PF 2.59;
     - H2: **43.5 / 0.0**, **+$6,725**, PF 3.66;
     - 2025: **28.5 / 0.0**, stuck 22.9%, **-$2,362**;
     - 2021-24: **23.4 / 0.0**, stuck 29.2%, **-$411** (before the $63 evals).
   - Not a behaviour bug; the dashboard and atlas.md need a refresh. I did not rewrite atlas.json (another agent owns the
     dashboard data).
4. **Operational gap: idle ("zombie") evals.**
   - After session 10 the 25K uses safe_eval, which caps the risk at 30% of the room. With the skip invariant, a room of
     about $100-300 fits almost no stop.
   - Account B only counts an eval as "stuck" under $100 (`engine/account_b.py:51`, `:393`). So it can sit for many
     sessions logging "size 0" and send no push. Examples are in `ATLAS_SIGNAL_LEDGER.csv`, reason `VETO_SIZE_0`
     (room $176-270, sessions 12-26).
   - RESEARCH_VARIANT: a stuck threshold of $200 / $300 (buy a new eval earlier) helps 2025 and 2021-24 but makes 2026 H2
     worse (path less fees: $300 gives +$4,385 vs +$6,347). **Not adopted.**
   - Owner rule instead: if account B logs "size 0" with room under ~$300 after session 10, treat it as stuck and buy a
     new $63 eval.
5. **What carries the edge.** Each setup's money sits in a few trades:
   - S/R H2 with its top 3 winners removed: +$140;
   - EMA H2: +$499;
   - MACD H2: -$2,621.
   - Pooled 2026 H2 without the top 10% of winners: +$281.
   - Slippage of +1 / +2 / +4 ticks keeps 98 / 95 / 91% of the pooled H2 money.
   - Fees +$0.50 keep 99%.
   - 2021-24 is thin (PF 1.08 pooled at $500) and goes negative at +4 ticks.
   - These are 2026 bets, as the earlier write-ups already say.
6. Tests: `tests.test_second --quick` **PASS 31/31** (day-end replay EMA 86/86, MACD 44/44, S/R 45/45, LIT+Asia 187/187).
   `tests.test_second_account_b --quick` **PASS 42/42**. Its full-bot replay of 2026-10-02 routes B's EMA 03:10 trade
   **3.0 s after its 5m open**, with the research micros, stop, target and $.

## 1. Each setup from the code (actual config, `second_model.json` + research modules)

Common to all three:
- Instrument: CME NQ1! 5m bars. Live, they are LIT's NinjaTrader MNQ bars, cut to LIT's window
  (`engine/second.py:108` `_window`). The window starts at the first trading day of the previous month minus 7 days
  (`engine/lit_live.py:103`, `CUSHION_DAYS = 7`).
- Only closed bars: `engine/live.py:257` drops the forming bar. HTF bars whose clock period has not ended are "forming"
  under `live_cut` (`tools/retail_standalone.py:53-121`; MACD `tools/second_md.py:118-131`).
- Decision time = the signal bar's close. Entry = **market at the next 5m open** + 1 tick in research.
  - Live: account B probes 0-45 s after that open (`engine/account_b.py:515-522`, `MAX_AGE_S = 45`). The bot polls at
    :02 and :32 of each minute (`engine/live.py:2333`).
  - A 5m bar seen later than 45 s is skipped (missed trade), never chased.
- Execution: one position at a time and max 2 entries a day on account B (`engine/account_b.py:49`), across all three
  setups.
  - If two setups fire on the same open, the first in `second_model.json` order wins (EMA, MACD, S/R). The research
    executor sorts the same way (stable sort in `tools/second_mix.by_day`).
- Never opposite LIT (`engine/account_b.py:429-472`):
  - blocked while LIT holds, is entering, or has an armed setup the other way;
  - when LIT enters opposite, B is closed at market first (HEDGE).
  - Live is stricter than research: the research `no_hedge` only knows LIT's open positions, not LIT's armed setups.
- Costs in research: $1.90 a micro round trip, 1 tick on market entries and stop / BE / cut / flat exits; targets fill
  at the limit. Stop and target in the same bar = stop.

### ATLAS_LONDON_EMA (`ema_lon_vix`, run `ema2_lon_vix`, `tools/second_ema.py`)
| Item | Code (file:line) | Actual |
|---|---|---|
| Hours | `second_ema.py:56` WINS["lon"]=(180,570); mask `:450` uses the entry-bar minute (signal + 5) | entry bar opens 03:00-09:25 ET; candidates only for signal bars opening 01:50-15:30 (`:217`) |
| Weekday | `:490` reg "nomon" (dow of the signal bar) | no Mondays |
| Trend | `:71-75` t15/t60 = sign(EMA21-EMA50) of the **closed** 15m / 1h bars; `:456` "t15_60" | both > 0 for longs, both < 0 for shorts |
| EMAs | `retail_standalone.py:123` `ewm(span, adjust=False)` | EMA 21/50 on 15m and 1h closes; 5m EMA 50 for the pullback |
| Pullback | `:197-211` a run of counter-trend candles (C<O for a long); `:202` a new down series that makes a lower low resets the level to its open; run ends after 24 bars (`:209`) | the CISD level = the open of the first candle of that run |
| Touch | `:254` touch50 = run low <= 5m EMA50 at the low bar + 0.1 x ATR(14, 5m); mask `:470` | pull = e50 |
| Sweep | `:195` fractal k=2 confirmed at q+2; `:227` swing low confirmed **before the run started** (qq+2 < start), within 48 bars, above the run low, < 1.5 ATR away | sweep = 1 |
| Signal | `:212` 5m close > CISD level (displacement disp = 0.0, so no body rule) | |
| Stop | `:221` 1 tick beyond the run's low (the sweep wick, signal bar included); `:222-223` 6-80 pts else no trade | structural |
| Entry | `:220` next 5m open + 1 tick (market) | ENTRY_MODE "mkt" (`:270`) |
| VIX | `:130-135` VIX close of the last date **before** the trading day (CBOE `data/VIX_1d.csv`), `:149` vmove = VIX/100/sqrt(252) x 18:00 open | known from 18:00 the evening before (the CBOE close of about 16:15 ET) |
| Target | `simulate :346-354` 18:00 open +/- 1 VIX day move, at least 1.5R else no trade, banked at 8R | tgt "vix" |
| Management | `:393`/`:401` stop to entry + 1.25 pts once a bar's high reaches +1R (from the next bar); no 15-minute check; flat at the 15:50 bar close - 1 tick (`:395`, `retail_standalone.py:77-83`) | be 1.0, beo 1.25 |
| Expiry | run expires after 24 bars; first qualifying CISD of the day only (`:719`) | 1 a day |
| Paper size | `:731` `max(1, min(40, int(500/(stop x $2))))` | 3-40 micros (stops 6-80 pts, so the max(1) never binds) |

### ATLAS_MACD_SWEEP (`macd_sweep`, run `md2_best`, `tools/second_md.py`)
| Item | Code | Actual |
|---|---|---|
| Hours | `second_md.py:42` KZ "lon_ny"; `greedy :527` on the fill bar's minute | entry 02:00-05:00 and 09:30-11:00 ET; no signal 15:30-18:00 (`:249`) |
| Levels | `sweep_events :200-224` engine/lit.Market.levels (LIT levels: PDH/PDL, PW, PM, Asia / London / NY / pre boxes, build-ups, gaps), class set "all" | first breach of each level in its trading day, searched only from the bar **after** the level is known (`:210` `a = max(ki + 1, s)`) |
| Sweep window | `:248` W = 24 bars (2 h) after the sweep | |
| CISD | `cisd_level :184` open of the first bar of the last against-run into the extreme (search 3 back); `:253` the extreme bar itself cannot be the signal | close through it |
| MACD | `macd_state :157` EMA12-EMA26 (line), signal 9, on **5m** closes (tf 5); osc "line" | |
| Pivots | `pivots :164` centred 5-bar window (k=2): a pivot at P is confirmed at the close of P+2; `:273` only pivots with P+2 <= the last closed bar at the signal | pivot delay = 2 bars (10 min), intentional |
| Pair choice | `:271-276` window [x-48, x-3] tf bars before the extreme; P = the lowest confirmed pivot low (highest high), deterministic | no hindsight: all inputs known at j |
| Divergence | `:279` sweep extreme at or beyond the prior pivot (lower/equal low); `:281` MACD at the extreme bar > MACD at P (long) | regular divergence; the first CISD close of a sweep decides (break) |
| Filter | `md_filter :570` depth = (level - extreme)/ATR(sweep bar) >= 0.5 (`:288`), reg none, maxpd 1 | |
| Stop | `:284` 1 tick beyond the sweep extreme; `sim_one :446` 6-80 pts | |
| Entry | `sim_one :425-427` market at the next 5m open + 1 tick (the first 1m open of that bar in 2026) | |
| VIX / target | `:449-457` 18:00 open +/- VIX day move (engine/lit.Market ctx, VIX close of the previous date `engine/lit.py:247-251`), at least 1.5R else no trade, banked 8R | |
| Management | no BE; `:495-498` 15 min after the fill: not at BE, MFE < 0.5R and close < entry - 0.3R -> out at the next open - 1 tick; flat at 15:55 (`:475`); 1m path in 2026 | tc True |
| Paper size | `q_usd :757` `max(0, min(40, int(500/(stop x $2))))` | 3-40 micros |

### ATLAS_NY_RECLAIM (`sr_nyreclaim`, run `sr2_nyreclaim_usd500`, `tools/second_sr.py`)
| Item | Code | Actual |
|---|---|---|
| Hours | `second_sr.py:652` WINDOWS["ny12"] = (570,720) on the entry bar; `select :441` | entry 09:30-12:00 ET, 1 a day (maxpd 1) |
| Levels | `levels :112-163`, set "all_or": prior session RTH high/low (pd), overnight 18:00-09:30 (on), Asia 20:00-24:00, London 02:00-05:00, prior ISO week (pw), opening range 09:30-10:00 (or); each box known at its end | built only from bars inside the box |
| Level before breach | `:198` first breach bar >= known time + 5 min; pd / pw from the 2nd bar of the session | the reference existed before the breach (conservative by one bar) |
| Breach | `:204-208` previous close on the other side and this bar's wick through | first touch only |
| Reclaim | `:223` conf "close": within W = 4 bars (sweep bar included) a 5m **close** back beyond the level (a close reclaim, not a wick) | |
| Strength | `:234` body >= 0.3 x ATR(14, 5m) at the bar before the sweep (`:211`); depth 0.0 (`:232`) | |
| Inducement | `:238-243` a 5m fractal confirmed before the sweep bar (f <= j-3, confirmed f+2 <= j-1), between the level and 1 ATR from it, in the last 36 bars, this session | idm True |
| Stop | `:246` 1 tick beyond the sweep extreme (through the reclaim bar); `outcomes :362-364` 6-80 pts | max_stop 80 |
| Entry | `:360` next 5m open + 1 tick, next-bar execution (k0 = signal + 1) | entry "mkt" |
| Target | fixed 2R (tg 2.0, bank none); VIX not used | |
| Management | no BE; `_walk :419` 15-minute check on the 3rd bar: not moved, MFE < 0.5R, close < entry - 0.3R -> out at the next open (T15); flat at the 15:50 bar close (`:88`) | tc True |
| Paper size | `qty_rule :791` `max(0, min(40, int(500/(stop x $2))))` | 3-40 micros |

### Sizing: what the $500 is and what account B really trades
- **$500 = PRICE risk** in the research and the paper ledger: `int(500 / (stop pts x $2))`. Commission ($1.90 a micro) and
  slippage (1 tick = $0.50 a micro on the stop) are extra.
  - A full stop-out therefore costs up to `q x ((stop + 0.25) x 2 + 1.90)`. Worst case is 40 micros on a 6.25-pt stop:
    **$596**, 19% over the $500.
  - A gap through the stop is not bounded.
- **Account B (tonight) does not use the $500.** `engine/account_b.qty` (`engine/account_b.py:169-191`), sizing "need"
  (the default in `normalize :105`) = LIT's two_week rule on the 25K preset:
  - Micros so that one target hit covers what is left to the $1,500 target.
  - Capped (each cap a ceiling, 1 micro priced at (stop + 1 tick) x $2 + $1.90, fewer than 1 micro means skip, commit
    15cb560) at:
    - 50% of the room to the $1,000 EOD trailing floor;
    - the $600 soft daily loss;
    - 20 micros.
  - The DLL guard (`:194-221`) prices a stop-out at (stop + 2 ticks) x $2 + $1.90 against $600 + today's P&L.
  - After session 10: safe_eval, capped at 30% of the room.
  - Sample sizes (`sz.py` run, fresh eval with room $1,000):
    - 20 pts stop / 60 pts target: 11 micros;
    - 40 / 120: 6 micros;
    - 80 / 160: 3 micros;
    - with today already -$300: 6 / 3 / 1;
    - session 11: 7 / 3 / 1.
- The min-1 invariant now skips: a trade that does not fit 1 micro inside every cap is not traded. In the replays this
  appears as `VETO_SIZE_0` with the sizer's own reason.
- The B order's P&L is the model's per-micro result x B's micros (`engine/account_b.py:665`).

## 2. Look-ahead checks per setup

**London EMA**
- **EMA init / warm-up:** `ewm(span, adjust=False)` is seeded with the first close of the live window, at least 5 weeks
  back. For the 1h EMA 50 that is about 575+ bars, so the seed's weight is (49/51)^575, about 1e-10. The 5m and 15m
  EMAs are converged even more. That is why live (window) and research (whole file) agree.
- **Completed bars only:** t15 / t60 are read from the last **closed** 15m / 1h bar (`retail_standalone.to5`, with
  live_cut the forming HTF bar is excluded). The 5m EMA 50 at the low bar uses closes known by then.
- **Pullback:** a counter-trend candle run of at most 24 bars that touches the 5m EMA 50 (+0.1 ATR) and takes a swing
  low confirmed before the run began. The signal is the close back through the run's first open.

**MACD**
- Price pivots and MACD pivots are confirmed when the decision is made. A pivot needs 2 more closed tf bars (delay 2 bars
  = 10 min on 5m), filtered at `:273`.
- The MACD value at the extreme bar uses closes up to the extreme. With tf 5 the extreme bar is always closed at j. For
  higher tf, `:260-268` recomputes the forming bar from the known close.
- The pair is chosen deterministically (the lowest confirmed pivot in the window), so there is no hindsight pair choice.
- One decision per sweep: the first CISD close passes or kills it.

**NY reclaim**
- The level existed before the breach (search starts 5 min after the box's end).
- The signal (reclaim) bar is not part of any level. The reclaim is a close beyond the level, not a wick.
- Execution at the next bar's open.
- One subtlety, conservative: the first bar after a box ends is never a breach bar.

**Prefix invariance, measured.** `PROBE_CHECK.csv` re-derives every 2026 research trade (175) from bars that end at
its decision bar (plus the flat probe bar at the real open), using the live code. 175 / 175 have the same bar, side, entry,
stop and target. The day-end replay test (`tests/test_second.py` a.) cannot show this alone, because at 17:00 every HTF
bar of the day is closed. The probe and the scan close that gap.

## 3. "One bar late": classification

| Candidate cause | Finding |
|---|---|
| Bar start vs end time | Both sides use bar-OPEN timestamps. Research `entry_t` = open of the bar after the signal (`second_ema.py:722`, `second_md.tr_rec :766`, `second_sr.trades_of :813`). Live `tb` = last closed 5m bar + 300 = that same open (`account_b.py:518`). No shift. |
| Double shift | None. The probe appends exactly one bar at `tb`. A trade must have `entry_t == tb` and be OPEN (`account_b.py:541`). |
| Pivot delay | MACD pivots k=2, EMA sweep fractal k=2, S/R inducement fractal k=2: all intentional, all in the research too. |
| Next-bar indexing | Research ei = signal + 1 = live tb. Same. |
| CSV / feed latency | NinjaTrader writes a bar on the next bar's first tick. The bot polls at :02 / :32. A bar seen after 45 s is skipped (missed trade), never entered late. |
| Intentional | `tools/second_robust.py` late1 / late2 is a stress scenario only. |
| **Measured offset (2026)** | **0 bars for 175 / 175 research trades** (`PROBE_CHECK.csv`, verdict SAME_BAR_SAME_LEVELS) |

Full scan (every 5m open in each window, all 2026 sessions, probed as live: `SCAN_<key>.csv`):
| Setup | 5m opens probed (2026-01-02..10-16) | Live entries | Research trades | Same bar & stop | Live-only (false positive) | Research-only (missed) | Shifted +/-1-2 bars |
|---|---|---|---|---|---|---|---|
| London EMA | 16,065 | 86 | 86 | 86 | 0 | 0 | 0 |
| MACD sweep | 11,106 | 44 | 44 | 44 | 0 | 0 | 0 |
| NY reclaim | 6,150 | 45 | 45 | 45 | 0 | 0 | 0 |

So across 33,321 live probes the bot would have routed exactly the 175 research entries, each on its research bar and none a bar early or late.

The real live risk is **fill price, not bar**. A market order 2-32 s after the open can be a few ticks away from the open.
That is the +1 / +2 / +4 tick rows in section 6.

## 4. Performance (`PERFORMANCE_BY_SETUP.csv`, BASELINE, costs in)

Spans:
- H1 = 2026-01-01..06-30 (pick half);
- H2 = 2026-07-01..10-16 (check half);
- 2025;
- 2021-24 = 2021-11-01..2024-12-31.

Columns: trades, net_pnl, PF, positive_trade_rate, average_win / average_loss, max_drawdown, weekly_frequency,
zero_trade_weeks (of weeks), % weeks with 2+, tail_concentration (% of the net from the best 10% of trades), net without
the top 3, $ per month.

**Each setup alone at $500 price risk (paper ledger scale)**

| Setup | H1 | H2 | 2025 | 2021-24 |
|---|---|---|---|---|
| London EMA | 60 tr, +$19,867, PF 2.72, 2.34/wk | 26, +$8,136, PF 3.10, 1.67/wk | 130, +$6,256, PF 1.18 | 420, +$5,607, PF 1.05 |
| MACD sweep | 29, +$22,090, PF 3.78, 1.13/wk | 15, +$2,569, PF 1.75, 0.96/wk | 72, +$8,190, PF 1.35 | 266, +$12,053, PF 1.13 |
| NY reclaim | 29, +$12,213, PF 3.72, 1.13/wk | 16, +$2,914, PF 1.89, 1.03/wk | 71, +$4,991, PF 1.26 | 256, +$4,844, PF 1.06 |
| Pooled (no interaction) | 118, +$54,169, PF 3.26, 4.61/wk, 0 zero weeks | 57, +$13,618, PF 2.28, 3.65/wk, 1/16 zero | 273, +$19,436, PF 1.25 | 942, +$22,504, PF 1.08 |

**Routed account-B path (Builder 25K, need size, max 2 a day, one position, no hedge vs LIT, soft DLL, a new eval after
each pass / fail / stuck)**

This is `tools/second_account_b.py` with `engine/account_b.qty`. My logged replay reproduces its path exactly: H1 94
trades / +$14,784.

| | H1 | H2 | 2025 | 2021-24 |
|---|---|---|---|---|
| Trades / per week | 94 / 3.67 | 35 / 2.24 | 135 / 2.62 | 524 / 3.22 |
| Net path (before evals) / per month | +$14,784 / +$2,426 | +$6,725 / +$1,811 | -$2,362 / -$192 | -$411 / -$11 |
| PF / win % | 2.59 / 51.1 | 3.66 / 57.1 | 0.80 / 39.3 | 0.99 / 35.7 |
| Max DD | -$1,086 | -$905 | -$6,026 | -$7,019 |
| Zero-trade weeks | 1/27 | 4/16 | 11/53 | 19/165 |
| Weeks with 2+ | 85% | 56% | 64% | 77% |
| Pass/fail/stuck/open (back-to-back) | 8/0/1/1 | 4/0/1/1 | 1/0/6/1 | 15/0/33/1 |
| Fresh eval each session: p10 / f10 / dec10 | 62.2 / 0.0 / 63.0 | 43.5 / 0.0 / 43.5 | 28.5 / 0.0 / 51.4 | 23.4 / 0.0 / 52.6 |
| p15 / f15 / slow_pass / pass_med | 71.9 / 0 / 4.4% / 5 | 54.7 / 0 / 13.3% / 6 | 30.7 / 0 / 2.5% / 4 | 25.5 / 0 / 4.2% / 4 |
| 1 month (p20 / f20) | 74.3 / 0.0 | 61.0 / 0.0 | 32.2 / 0.0 | 26.5 / 0.0 |
| Path less $63 evals | +$14,154 | +$6,347 | -$2,866 | -$3,498 |

Share by setup on the routed path (H1 / H2):
- EMA: +$986 (PF 1.18) / +$3,036;
- MACD: +$7,942 / +$1,029;
- S/R: +$5,856 / +$2,660.

On the "need" size the EMA's many small wins weigh little, while MACD's few big targets carry the eval.

**Ledgers**
- `ATLAS_TRADE_LEDGER.csv` holds LIT's ledger columns plus setup_id, book, label, ET times, prices and eval number.
  - Book `ALONE_USD500`: every stored research trade 2021-11 to 2026-10-16, with MFE / MAE in R from the 5m bars.
  - Book `ACCTB_25K_NEED`: the routed path per span. MAE comes from the executor's worst open $; MFE is not available
    there.
- `ATLAS_SIGNAL_LEDGER.csv`: candidates that did not become a B trade, with reason codes:
  - `VETO_HEDGE_LIT_OPPOSITE_OPEN`;
  - `TAKEN_BUT_CLOSED_AT_LIT_OPPOSITE_ENTRY`;
  - `VETO_ONE_POSITION_BUSY`;
  - `VETO_MAX_2_PER_DAY`;
  - `VETO_SIZE_0: <sizer's reason, room, day P&L, session>`;
  - `VETO_NO_EVAL_RUNNING_THAT_DAY`;
  - and, for the EMA's own 2026 selection, `REJECT_ONE_PER_DAY` (121) and
    `REJECT_NO_VALID_EXIT_OR_TARGET_UNDER_1.5R` (23).
- MACD and S/R research-internal rejections (generator candidates the selection dropped) are not itemised.

## 5. Eval findings

- **Stale numbers:** `research/second/atlas.json` and atlas.md vs today's code (above). The dashboard shows H1 72.3% /
  +$19.7k. Today's code gives 62.2% / +$14.8k (H1), 43.5% / +$6.7k (H2), and a negative 2025 / 2021-24 path. The two
  2026 halves still pass the owner's rule (no 2-week fails, 2-4 trades a week). 2025 and 2021-24 do not make money on
  this path.
- **Idle evals:** see verdict point 4. RESEARCH_VARIANT stuck threshold (`EVAL_25K_STUCK200.csv`,
  `EVAL_25K_STUCK300.csv`):

| Stuck under | H1 p10 / path less fees | H2 p10 / path less fees | 2025 | 2021-24 |
|---|---|---|---|---|
| $100 (live) | 62.2 / +$14,154 | 43.5 / +$6,347 | 28.5 / -$2,866 | 23.4 / -$3,498 |
| $200 | 62.2 / +$14,355 | 43.5 / +$5,915 | 28.1 / +$422 | 23.2 / -$4,788 |
| $300 | 60.5 / +$18,784 | 43.5 / +$4,385 | 27.7 / +$505 | 22.0 / +$2,016 |

  It is not better in both 2026 halves, so it is not adopted. It is listed so the owner knows an idle account is the
  same as a stuck one.

## 6. Robustness per setup (`ROBUSTNESS_BY_SETUP.csv`, alone at $500, RESEARCH_VARIANT rows)

How the tests work:
- **+k ticks:** k ticks against on the market entry and on each market exit (stop / BE / cut / flat). Target limits get
  none, and the micros are unchanged.
- **Fee:** +$0.50 a micro round trip.
- **Top winners removed:** the best 1 / 3 / 10% of trades in the span.
- **1 bar late:** the research code re-run (`research/second/robust.json` late1).

| % of the base $ kept | EMA H1 / H2 | MACD H1 / H2 | S/R H1 / H2 | Pooled H1 / H2 | 2025 E / M / S | 2021-24 E / M / S |
|---|---|---|---|---|---|---|
| +1 tick | 98 / 98 | 99 / 97 | 99 / 98 | 99 / 98 | 76 / 94 / 92 | 5 / 80 / 65 |
| +2 ticks | 95 / 96 | 99 / 94 | 99 / 96 | 97 / 95 | 53 / 87 / 84 | -90 / 60 / 30 |
| +4 ticks | 91 / 91 | 97 / 88 | 97 / 92 | 95 / 91 | 6 / 74 / 68 | -280 / 20 / -40 |
| fee +$0.50 | 99 / 99 | 100 / 98 | 100 / 99 | 99 / 99 | 88 / 97 / 95 | 50 / 89 / 79 |
| top 1 removed | 80 / 52 | 82 / -16 | 92 / 67 | 93 / 71 | 38 / 53 / 80 | 29 / 67 / 80 |
| top 3 removed | 42 / 6 | 48 / -102 | 77 / 5 | 79 / 34 | -87 / -37 / 41 | -111 / 2 / 39 |
| 1 bar late (stress) | 56 / 4 | 75 / 68 | 28 / -58 | - | -143 / 155 / 22 | -227 / 16 / -116 |

Reading:
- Costs barely matter in 2026.
- 2021-24 EMA is break-even and dies at +2 ticks.
- H2 money hangs on 1-3 trades per setup.
- A late entry would hurt EMA and S/R. The live path does not enter late; it skips.

## 7. Commands, tests, evidence

```
python -X utf8 -m tests.test_second --quick            # PASS 31/31 (189 s)
python -X utf8 -m tests.test_second_account_b --quick  # PASS 42/42 (1166 s); the full-bot replay of 2026-10-02 routes B's EMA 03:10 trade 3.0 s after its 5m open
python -X utf8 tools/atlas_audit.py probe [key]        # PROBE_CHECK*.csv (175 trades, ~1 min)
python -X utf8 tools/atlas_audit.py scan <key>         # SCAN_<key>.csv (every 5m open of 2026 in the window; 20-80 min each)
python -X utf8 tools/atlas_audit.py perf               # PERFORMANCE_BY_SETUP / ATLAS_TRADE_LEDGER / ATLAS_SIGNAL_LEDGER / ROBUSTNESS_BY_SETUP
python -X utf8 tools/atlas_audit.py evals [min_room]   # EVAL_25K_NOW.csv (+ RESEARCH_VARIANT EVAL_25K_STUCK<x>.csv)
```
The account-B replay needs `research/runs/_cache/second_mix_units.pkl`. It is built on the first call (gitignored,
about 1 min).

## 8. Uncertainties

- **No-hedge in research is weaker than live.** Live also blocks a B entry while LIT has an armed setup in the other
  direction, so live may skip a few more B trades than the path shows. This is not measured here (it needs LIT's
  intraday setup state).
- **LIT trades used for no_hedge** are `tools/lit_final.run` with `live_model.json` "lit" (cached units). If the
  2026-10-24 safe switches changed LIT entries, the cache was built today and reflects them. It was not cross-checked
  trade by trade against run `lit_live`.
- **VIX:** EMA and MACD read the CBOE file's previous-date close. A failed download keeps the old file silently
  (`engine/news._cboe_daily`). The repo copy ends 2026-10-16. Tonight's (2026-10-26 trading day) targets need the
  2026-10-23 close in `data/VIX_1d.csv` on the PC. Check it before 18:00. S/R does not use VIX.
- **The fill price** is the open +2-32 s, not the open. The tick tables cover 1-4 ticks; a fast open can be worse.
- **2-week pass numbers** come from 2026 trades the strategies were tuned on (H1) plus 46 H2 trades on account B. They are
  thin samples (MACD 15, S/R 16 trades in H2 alone).
- The MACD 2021-24 span here starts 2021-11-01 (266 trades). `robust.json` counts from 2021-10 (271).
