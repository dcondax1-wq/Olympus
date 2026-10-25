# A1 pre-launch audit: data, timing and look-ahead (LIT + ATLAS)

Agent 1 of 5, 2026-10-25 (go-live 18:00 ET). Paper only: nothing was armed, routed or ordered; no `live_model*.json` was
touched. Labels: **BASELINE** = what the code does today; **BUG_FIX** = a demonstrated defect, fixed with a regression test;
**RESEARCH_VARIANT** = measured only, not adopted.

## Summary

| # | Finding | Label | Effect on LIT live tonight |
|---|---|---|---|
| 1 | No look-ahead found. All 220 LIT signals of 2026 come out identical on data cut at the trigger bar. So do all 175 ATLAS trades (EMA 86, MACD 44, S/R 45), each cut at its signal bar and again at its entry bar. | BASELINE | none |
| 2 | VIX / VXN: the target band uses the CBOE close dated *before* the trading date. A same-date row (final or partial) is never read. Proven by a fixture and on all 206 days of 2026. | BASELINE | none |
| 3 | NinjaTrader 1m-only feed (no `MNQ_5m.csv`): the 5m bar built from 1m bars was returned as closed with only 4 of its 5 minutes, at 10:05:01, before LE_BarFeed had written the 10:04 bar. | **BUG_FIX** (`engine/ninjatrader.py`) | Only if the chart is a 1m chart. The documented 5m chart setup never used this path. |
| 4 | `lit_live.early_close` missed the CME 13:15 ET close on July 3 when July 4 falls on Tue-Fri. The data shows it on 2023-07-03, 2024-07-03 and 2025-07-03. | **BUG_FIX** (`engine/lit_live.py`) | None before July 2027. No 2026 date changes. |
| 5 | The 1m data cleaning (`engine/data._clean_1m`, volume rule) drops 226 genuine 2026 1m windows. The live feed keeps them. So the live CISD entry differs from the backtest on 2 trades (03-23, 05-05), plus Good Friday (known). Re-running the backtest without that rule gives exactly the live trades: 2026 net **-$730** (+$43,820 -> +$43,089), H2 unchanged. | RESEARCH_VARIANT | Live is ~1.7% below the headline on 2026 and the same on H2 |
| 6 | NQ1! vs MNQ1! (37 sessions, 5m): 25 of 69 LIT signals exist on one feed only. Trades share their entry on 11 of the 15 days with a trade. Net over those days: NQ +$2,374 vs MNQ +$379 (5m execution). MNQ 1m: **UNTESTED** (no MNQ 1m data). | measurement | Live (MNQ bars) will not reproduce the NQ backtest trade for trade |
| 7 | Intrabar ambiguity, 2026 LIT: 0 bars touch both the stop and the target. 5 bars touch both the +1R breakeven trigger and the breakeven level. Bad-way bound **-$4,233** (H1 -$2,114, H2 -$2,119, i.e. 21% of the H2 net). The OHLC shape suggests the engine's order on all 3 trades with $ at stake. | measurement | A bound, not a measured loss |
| 8 | The 1m-or-5m execution choice is a whole-day rule in the backtest (Good Friday, known). Live judges it per poll, and the forming window's 1m bars count only in the numerator. On 2026-01-14 (cover right at 97%) the choice flips between 1m and 5m from poll to poll. The trade is identical. | measurement, fragility | none in 2026 |

## 1. Dataset inventory

Script: `a1_inventory.py`. Outputs: `a1_inventory.csv`, `a1_gaps_by_session.csv` (per file and trading day, missing slots by
session part) and `a1_gap_summary.csv`. All times are ET; a trading day runs 18:00 -> 17:00.

| File | Symbol / source | First bar | Last bar | Rows | sha1[:12] | dup / out-of-order / off-grid / 17-18h bars |
|---|---|---|---|---:|---|---|
| `NQ_5m.csv` | TradingView CME NQ1!, back-adjusted to NQZ26 (`NQ_rolls.json`, repo method) | 2021-10-17 18:00 | 2026-10-16 16:55 | 354,333 | 21380e2635ec | 0 / 0 / 0 / 0 |
| `NQ_1m.csv` | TradingView CME NQ1! 1m | 2025-12-28 18:00 | 2026-10-16 16:59 | 286,503 | d6ffd3ecfe77 | 0 / 0 / 0 / 0 |
| `ltf/NQJ_1m.csv` | TradingView CME_MINI NQ1! 1m (verified extra source; wins per 5m window in `load_ltf`) | 2026-01-14 10:51 | 2026-10-07 16:14 | 11,664 | bdf2f0e166a0 | 0 / 0 / 0 / 0 |
| `ltf/NQJ_5m.csv` | same, 5m | 2026-01-14 10:50 | 2026-10-07 16:10 | 2,333 | 2355698faf8c | 0 / 0 / 0 / 0 |
| `tv_mnq_5m_2026-10-16.csv` (= `tv_exports/MNQ1_5m_ETH_badj_2026-10-16.csv`) | TradingView CME **MNQ1!** 5m ETH | 2026-08-23 18:00 | 2026-10-16 07:10 (**partial last bar**, volume 154) | 10,875 | 6f1dbe8969db | 0 / 0 / 0 / 0 |
| `NQ_15m.csv`, `NQ_1h.csv` | built from 5m | 2021-10-17 | 2026-10-16 | 118,111 / 29,538 | fe2b33139f2f / 8d246e7bf7f5 | 0 |
| `NQ_1d.csv` | NQ daily (stamped 00:00 UTC) | 2021-10-18 | 2026-10-16 | 1,293 | af34014db0b4 | not used by LIT / ATLAS |
| `ES_5m.csv` | TradingView CME ES1! | 2025-04-13 18:00 | 2026-10-16 16:55 | 107,307 | 2e5662db88c8 | 0 / 0 / 0 / 0 |
| `clean/raw/NQ_5m_unadjusted.csv` | NQ 5m by contract (unadjusted) | 2021-10-17 | 2026-10-16 | 354,333 | 429751c9ae30 | 0 |
| `VIX_1d.csv` | CBOE VIX daily | 2021-10-15 | 2026-10-16 | 1,258 | e5c621f32bbf | 0 dup / 0 out-of-order |
| `VXN_1d.csv` | CBOE VXN daily | 2021-10-18 | 2026-10-16 | 1,255 | 313484bd7e8f | 0 / 0 |
| `CBOE_vol_1d.csv` | VIX9D / VIX3M / VIX1D / VVIX / SKEW | 2015-01-02 | 2026-09-17 | 2,944 | 4bd988cb91ff | not used by LIT / ATLAS |

`data/nt_bars/` does not exist in the repo: it is gitignored and lives on the PC only.

### Missing and odd bars

- **NQ 5m (2021-10 -> 2026-10):** a full grid inside every session, with one exception. On **2025-11-28** (the day after
  Thanksgiving) 129 slots are missing between 18:00 and 09:30: 51 Asia, 72 London, 6 premarket. ES_5m has the same hole.
  This only affects the 2021-25 reference.
- **Short sessions:** 48 in total; 7 in 2026 (MLK, Presidents, Good Friday 09:10, Memorial, Juneteenth, Jul 3, Labor).
  Each one ends at `early_close` (section 5). One-off: 2025-01-09 (Carter day of mourning, 09:30 halt) is not coded.
- **NQ 1m (2026):** 12 missing minutes on 6 days: 01-06 (1, Asia), 02-16 (2), 03-16 (1), 04-03 (6), 04-21 (1), 07-03 (1).
  No duplicates, no out-of-order bars, nothing off the minute grid.
- **Flat no-volume bars** (dropped by `engine.data.load`): 0 in every file.
- **VIX / VXN:**
  - 2026 rows are missing only on CBOE holidays. VIX also has rows on **2026-05-25 (Memorial Day) and 2026-09-07 (Labor
    Day)**, with real OHLC, as CBOE published them. Those rows are read only by the next trading date (no leak either way).
  - The CBOE_vol file ends 2026-09-17; LIT and ATLAS do not read it.

### Tick size and $ multipliers in code

- `TICK = 0.25` and `PV = 2.0` ($/pt, one MNQ micro) everywhere sizing happens: `engine/lit.py:36`, `engine/second.py:49`,
  `engine/brain.py`, `engine/guards.py:58`, `engine/fill_audit.py`, `engine/account_b.py`, `engine/eval_mc.py`,
  `tools/retail_standalone.py`.
- Full NQ = $20/pt appears only in `engine/risk_policy.py:79` (NQ_PV, 1 NQ = 10 MNQ).
- Commission: the LIT backtest uses $1.40 / micro (`engine/lit.py`). ATLAS live and the MFFU checks use $1.90.
- Signals are computed on NQ1! prices and traded with MNQ micros. Both quote the same index points with the same 0.25
  tick, so no price conversion is needed. Only the basis differs: after a roll, `pcbars.merge_basis` back-adjusts by a
  constant (section 6 gives the noise between the two).

## 2. Bar time stamps, end to end

**Convention: every bar carries its OPEN time** (unix seconds, UTC). A bar is usable only once `time + secs <= now`.

| Stage | Code | What it does |
|---|---|---|
| TradingView exports | data check (`tests/test_a1_timing.py` §1) | Every trading day's first bar is stamped 18:00 ET, nothing sits in 17:00-17:59, a normal day ends at 16:55 (5m) / 16:59 (1m). That is open stamping; a close-stamped file would start 18:05 and end 17:00. |
| LE_BarFeed (NinjaTrader) | `ninjatrader/LE_BarFeed.cs:85` `Calculate = Calculate.OnBarClose;` and `:257` `return (closeUtc.Ticks - EpochTicks) / TimeSpan.TicksPerSecond - 60L * minutes;` | Writes a bar only when it closes. NinjaTrader stamps the close in its display time zone; the code converts that to UTC and subtracts one bar to get the open. |
| Feed sanity | `engine/ninjatrader.py:1791` | Refuses a feed with bars stamped 17:00-17:59 ET. A close-stamped or time-zone-shifted feed is caught by this. |
| Closed-bar rule (PC bot) | `engine/live.py:257` `df = df[df["time"] + secs <= now]` | Drops the forming bar from every merged 1m / 5m frame. |
| 5m from 1m (cloud) | `engine/pcbars.py:358` `fresh5 = fresh5[fresh5["time"] + 300 <= last1 + 60]` | A 5m bar built from the PC's 1m bars counts only when its 4th minute (the 5th 1m bar) has been written. |
| 5m from 1m (PC, 1m-only feed) | `engine/ninjatrader.py:1808` (**BUG_FIX**) `df = df[df["time"] + mins * 60 <= last_open + bsecs]` | Before the fix the last group was returned as a closed 5m bar however many minutes it held. |
| LIT early mode | `engine/lit_live.py:217` `_forming_5m`, `:188` `M.n_closed` | The forming 5m bar enters the market only as a flat bar at its open (H = L = C = O). |
| LIT detector | `engine/lit.py:430` `for i in range(s + (6 if evening else leg), e - 1):` and `:494` | The trigger `i` stops one bar short of the last bar, so the forming bar is never a trigger. |
| LIT 1m windows | `engine/lit.py:912-915` | A 5m window counts only with exactly 5 one-minute bars that rebuild the 5m bar. The tail (forming window) is kept for execution, never for a 5m decision. |
| ATLAS HTF bars | `tools/retail_standalone.py:105` | Live: an HTF bar whose clock period has not ended is still forming (`open_last`), and `to5` does not use it. |

**The "1m timestamp divisible by 5" case.** The prefix tests check this directly (`tests/test_a1_timing.py` §2). A 5m bar
never becomes available just because a 1m bar stamped hh:m5 or hh:m0 has arrived:

- **PC, 1m-only feed:** 1m bars through 10:03 at 10:05:01 give no 10:00 bar. It appears once 10:04 is written, with all
  5 minutes (volume 50).
- **Cloud:** 1m bars through 10:03 leave the last 5m bar at 09:55. A 10:05 print completes 10:00 (no trade in 10:04).
- **lit_live early mode at 10:02:05:** the market holds the closed bars to 09:55 plus the 10:00 bar flat at its open.
  `n_closed` excludes it.

Before the BUG_FIX, the first check failed: the 10:00 bar was returned with 4 minutes and passed `live.clean_bars`.

## 3. VIX availability (prior-day close only)

- **Rule:** `engine/lit.py:250` `j = bisect.bisect_left(dd, d) - 1` takes the last VIX date strictly before trading date
  `d`, then `:253` `vix_move = close / 100 / sqrt(252) * open18`. ATLAS uses the same rule: `tools/second_ema.py:133`,
  `tools/second_sr.py:96`, and MACD reads `lit.Market`.
- **Fixture** (`tests/test_a1_timing.py` §3):
  - The VIX file has a 10-08 row 4x the others (72.0) and a partial 10-09 row (99.0).
  - Trading dates 10-05..10-09 read 15 / 16 / 17 / 18 / 72. Monday reads Friday, and the 72.0 reaches only 10-09.
  - The 10-08 band equals open18 + 18.0/100/sqrt(252) x open18.
- **Real data:** all 206 trading days of 2026 use the last VIX and VXN close dated before the trading date.
- **Live file:** `engine/news._cboe_daily` lets CBOE's rows win for the last 10 stored dates, so a partial "today" row
  later gets its final close. That row is never read for its own trading date (strict `<`). From 18:00 ET it is read as
  the prior close; CBOE's close is at 16:15.
- **Residual:** if every CBOE fetch failed between 16:15 and the next morning, a partial row from before 16:15 could stand
  in for the prior close. That is a staleness case, not a look-ahead.

## 4. Prefix invariance (`tests/test_prefix_invariance.py`)

Method: the reference is the **whole-history** run. For LIT that is `lit.Market()` + `candidates` + the research 1m rule +
`run_live` signals + the `tools/lit_final.run` trades. For ATLAS it is the research trades in `research/second/*_best.json`.
Each item is re-run through the **live code** (`engine/lit_live.run(early=True)` as the PC bot polls; `engine/second.run`)
on data truncated at its decision bar: 5m and 1m bars closed by then, plus the open of the forming 1m bar.

| Check | Result |
|---|---|
| LIT a: signal at the trigger bar's close: limit, stop, target, risk, R:R, label, swept levels, sweep extreme, inducements, displacement, high/low-of-week flag | **220/220 identical**, 0 differ, 0 missing; 2 first seen at the entry bar's close (03-23, 05-05: harness only, see below) |
| LIT a: execution bar size 1m / 5m of the signal | 218/220; 01-14 (cover at the 97% line, see #8) and 04-03 (Good Friday) |
| LIT b: entry decided at the 1m CISD close = backtest trade (entry, stop, target, micros, not an estimate) | 118/120; 04-03 known, 03-23 harness only |
| LIT b: position / finished trade at the fill bar's close | 118/120 (same two) |
| LIT c: phantom signals at the cut time | 0 |
| LIT with the raw `NQ_1m.csv` as the feed (`--full`, the live `feed_1m` path, forming open from the raw file) | signals **220/220 identical, 0 late**; bar size 219/220 (04-03); entries and positions 117/120: 04-03 known, 03-23 and 05-05 = finding #5 (live = the RESEARCH_VARIANT backtest) |
| ATLAS EMA / MACD / S/R a: cut at the signal bar's close: same side, same stop, no trade yet | **86/86, 44/44, 45/45** |
| ATLAS b: cut at the entry bar's close: research entry, stop, target | **86/86, 44/44, 45/45** |

What "harness only" means for 03-23 and 05-05:

- The research-clean 1m bars drop the trigger bar's genuine 1m window (finding #5). With no 1m bars for that window, the
  early view cannot rebuild it and waits for the entry bar's close.
- The PC bot does not use the clean bars. Its raw feed keeps the window and sees the setup at once.

Run time:

- Quick mode (default): LIT 113 s + ATLAS 77 s + loading = about 3.5 min.
- `--full`: 451 s.
- Known days are listed in `KNOWN` in the test. Any other difference fails it.
- Results: `a1_prefix_invariance.json`.

Already-established look-ahead work (not redone): `tools/lookahead_audit.py` (499 runs, 0 flagged), `tests/test_lit_lookahead.py`
(5m cuts, 5m signals only) and `tests/test_second.py` b (20 sampled trades per member). What is new here:

- every signal and every trade, not samples;
- the 1m execution path and the 1m CISD decision;
- the raw-feed path.

## 5. Targeted fixtures (`tests/test_a1_timing.py`, 25/25 pass)

- **Session boxes:**
  - A box's known index is its last bar (asia20 = the 23:55 bar).
  - Cut mid-box (22:00), the partial box's index is the cut's last bar, so no setup can use it. Liquidity needs index <
    extreme; a target needs index <= trigger < last bar.
  - Real data: all 2,989 swept session boxes of the 2026 setups closed before the sweep extreme.
- **ATR:** Wilder ATR on a prefix equals the full-data ATR on that prefix, both synthetic and on the real 2021 -> 2026-03-02
  market.
- **Monday rule:**
  - The Monday trading day starts Sunday 18:00 ET (dow 0). The Friday levels run Thursday 18:00 -> Friday 17:00.
  - `monday_state` at 02:00 / 03:00 / 09:00 / 10:00 / 11:00 reads none / high / high / both / both, using bars up to
    each bar only.
  - After the high-only take, a long is blocked and a short is not; once both sides are taken, nothing is blocked.
- **DST week 2026-10-26..30:**
  - Every trading day starts 18:00 ET (22:00 UTC, 23:00 UTC from the Nov 2 session).
  - The London box `lon25` (02:00-05:00 ET) ends on the 04:55 ET bar in both weeks: 08:55 UTC on 10-27, 09:55 UTC on
    11-03. LIT follows the **New York clock**.
  - In the mismatch week the real London open is 04:00 ET instead of 03:00 ET, so the "London" box covers 02:00-05:00 ET
    = 06:00-09:00 London. That is the clock the strategy was tested on (fixed ET), not a code defect.
  - The entry window 02:00-15:30 and the 15:55 flat are ET too.
- **Early closes:**
  - `early_close`: 2026-11-26 13:00, 11-27 13:15, 12-24 13:15 ET (CME 12:00 / 12:15 CT); MLK 2027 13:00; Good Friday
    2027 (03-26) 09:15. **BUG_FIX:** July 3 is 13:15 when July 4 is Tue-Fri (2025, 2028); 2026-07-03 stays 13:00
    (observed holiday).
  - Cross-check: all 48 short sessions in `NQ_5m.csv` end at `early_close`, except 2025-01-09 (one-off). No early-close
    date in the data runs a full session.
  - After the 13:14 bar on 11-27 there is no next-bar fill (`_next_bar_same_day`). The session is over 5 min after the
    halt, not before.

## 6. NQ vs MNQ signal sensitivity (`a1_nq_vs_mnq.py`, `a1_nq_vs_mnq.json`, `a1_nq_vs_mnq_signals.csv`)

**Data:** the only MNQ data is the TradingView MNQ1! 5m export, 2026-08-23 18:00 -> 2026-10-16 07:10. There is no MNQ 1m
and `data/nt_bars` is absent.

**Bars** (10,875 shared bars; before the 09-14 roll, MNQ1! sits on NQU26 prices, a constant -294.75 = the repo's roll
gap, removed):

| | exact | within 1 tick | within 1 pt | p1 / p99 | max abs |
|---|---:|---:|---:|---|---:|
| open | 23.6% | 57.8% | 93.5% | -1.75 / +1.75 | 72.5 (09-13 18:00 opening print) |
| high | 25.2% | 60.5% | 92.7% | -1.75 / +2.5 | 37.75 |
| low | 23.6% | 58.4% | 92.2% | -2.75 / +1.75 | 28.25 |
| close | 22.1% | 54.1% | 93.3% | -1.75 / +1.5 | 28.75 |

- An MNQ bar's range is 0.43 pt wider on average. 80 bars have a wick 5-38 pts beyond NQ's: MNQ's book is thinner.
- The `engine/pcbars.py` docstring ("a tick apart at most on a bar's extremes, the same closes") is too optimistic. Its
  roll detection still works: the median offset is about 0, below its 2-pt threshold.

**LIT**, the live way (NQ1! history before 08-23 18:00 + MNQ 5m after it, as `merge_basis` builds it) vs NQ1! only, over
37 sessions (08-24 .. 10-15):

- **Signals:** 69 (day, time, side) keys in all.
  - 44 exist on both, with limit / stop a median 0.25 pt apart (p90 1.4 / 1.9 pt, max 13.25 / 6.25) and target a median
    2 pt apart.
  - **25 exist on one feed only** (10 NQ-only, 15 MNQ-only).
- **Trades (5m execution on both):** NQ 12, MNQ 13.
  - 11 days share entry time and side, and 10 of those share the exit kind.
  - 4 days trade on one feed only.
  - Net: NQ +$2,374, MNQ +$379.
  - The gap comes mostly from 09-23 (target, +$1,883 vs +$596, different stop so different size) and 10-14 (an NQ-only
    target, +$559), plus three MNQ-only losers.
- **1m execution:** **UNTESTED.** Mixing NQ 1m bars with MNQ 5m bars fails the 1m rebuild rule (1 pt tolerance) on most
  windows. Every MNQ day fell back to 5m, so that run equals the 5m run and is not evidence. In live, NinjaTrader's MNQ 1m
  and 5m come from one feed and rebuild exactly.

**ATLAS** (day-end replay, 37 sessions, 1m = research NQ 1m):

| Member | Trades NQ / MNQ | Same entry | Same entry and exit | Net NQ / MNQ |
|---|---|---:|---:|---|
| EMA | 13 / 14 | 12 | 5 | +$1,360 / +$891 |
| MACD | 10 / 10 | 7 | 0 | +$1,000 / +$335 |
| S/R | 9 / 9 | 9 | 4 | +$1,785 / +$1,826 |

**Reading:** the 37-session sample is small, but it is clear that LIT's sweep / CISD logic reacts to tick-level wick
differences. Live results on MNQ bars will scatter around the NQ backtest. The backtest's 2026 numbers are NQ1! numbers.
Recommendation, for the owner and the next session (not adopted):

- export MNQ1! 1m from TradingView for Aug-Oct and rerun this with true MNQ 1m execution;
- or run LIT's decisions on NQ bars routed to MNQ, which needs NQ bars on the PC.

## 7. Intrabar ambiguity (`a1_intrabar.py`, `a1_intrabar.json`, `a1_intrabar_trades.csv`)

- **Engine order inside a bar:** stop check first, then the target, then the breakeven move, which acts from the next bar
  (`engine/lit.py:1128`, `:1133`).
- **Independent re-walk:** it reproduces the engine's exit on 120/120 trades of 2026.

| Ambiguous bar | 2026 trades | Engine takes | Bound |
|---|---:|---|---|
| A: stop and target in one bar | **0** | stop (bad way) | 0 |
| B: breakeven stop and target in one bar | **0** | BE (bad way) | 0 |
| C: +1R breakeven trigger and the breakeven level (entry +/- 1.25) in one bar, original stop not touched | **5** (01-22, 06-17, 08-12, 08-25, 10-14) | trade stays open, BE from the next bar (good way) | 2 ended BE anyway ($0). 3 ended TARGET: **-$4,233** if each had exited at BE in that bar (01-22 -$2,114, 08-25 -$1,540, 10-14 -$579) |

- 2026 net with every ambiguous bar going the bad way: **+$39,587** (vs +$43,820).
  - H1: +$31,787 (vs +$33,901).
  - H2: **+$7,800** (vs +$9,919).
- The bars' OHLC suggest the engine's order on all three target trades:
  - 01-22 09:30 short: open 26,528.25, high +2.75, then down to 26,473.
  - 10-14 08:30 short: high +8.75, then -201.
  - 08-25 04:23 long: low -15 first, then high +36.
  - So the real cost is probably $0. Without tick data this cannot be proven.
- 5m-executed trades (Good Friday): the limit-fill bar gets no target or BE credit, so the ambiguity there goes the bad
  way.

## 8. Bugs fixed (BUG_FIX, each with a failing example turned into a regression test)

1. **`engine/ninjatrader.py` `NinjaTraderBars.recent_bars`:** a bar aggregated from finer bars (5m from a 1m-only feed,
   15m / 1h from 5m) was returned even when its last minute had not closed.
   - Failing example: 1m bars through 10:03 at 10:05:01 gave a 10:00 5m bar with 4 minutes, which passed `clean_bars`.
   - Fix: keep a group only when `time + secs <= last base bar open + base secs`, the same rule as `CloudFeed`.
   - Test: `tests/test_a1_timing.py` §2.
2. **`engine/lit_live.py` `early_close`:** missed July 3 at 13:15 ET when July 4 falls Tue-Fri.
   - Failing example: the data's short sessions 2023-07-03, 2024-07-03 and 2025-07-03 returned None.
   - Fix: one rule line.
   - Test: `tests/test_a1_timing.py` §8, which cross-checks every short session in the 5m file.
   - Effect on 2026: none (07-03-2026 is the observed holiday at 13:00).

Neither fix changes a backtest number or a 2026 replay: `tests.test_lit_live --days` still gives 120/120.

## Commands run

```
python -X utf8 research/handoff/2026-10-25/a1_inventory.py
python -X utf8 -m tests.test_a1_timing                      # 25/25
python -X utf8 -m tests.test_prefix_invariance --full       # 16/16 (451 s); quick mode (no flag) ~3.5 min
python -X utf8 research/handoff/2026-10-25/a1_clean1m_variant.py
python -X utf8 research/handoff/2026-10-25/a1_nq_vs_mnq.py
python -X utf8 research/handoff/2026-10-25/a1_intrabar.py
python -X utf8 -m tests.test_lit_live --days                # 120/120 identical (before and after the fixes)
python -X utf8 -m tests.test_guards                         # 69/69 (uses early_close)
python -X utf8 -m tests.test_no_yahoo --quick               # 18/18 (NinjaTrader feed paths)
```

## Remaining uncertainties

- **MNQ:**
  - There is no MNQ 1m data, so LIT on MNQ 1m execution is untested.
  - The MNQ sample is only 37 sessions of 5m.
  - TradingView's MNQ1! bars and NinjaTrader's MNQ bars were assumed identical; that was not checked.
- **Intrabar order:** cannot be resolved without tick data. The $4,233 is a bound.
- **The `_clean_1m` volume rule:** whether the backtest or the live feed is "right" is a research choice. The live feed
  matches the variant. The headline should be read as about $730 optimistic for 2026 and unchanged for H2.
- **1m cover rule:** the per-poll rule counts the forming window's 1m bars in the numerator only, so a day near 97% cover
  can flip between 1m and 5m execution from poll to poll (2026-01-14). No 2026 trade changed. A NinjaTrader feed with full
  1m bars always has 100% cover.
- **2025-01-09:** this kind of one-off CME halt is not coded in `early_close`.
- **CBOE holiday rows (05-25, 09-07):** taken at face value.
