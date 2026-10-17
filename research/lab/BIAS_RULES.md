# BIAS RULES: pre-registered daily-bias methods and tests (Fri 2026-10-16, written ~19:50 ET, before any result)

Owner: "Definitely look into daily BIAS, we usually want our bias to align with our trade."
Code: `engine/daily_bias.py` (methods), `tools/lab_bias_run.py` (tests). Report: `research/lab/BIAS_REPORT.md`.
Nothing below may be changed after results are seen. Any later addition must be labeled "post hoc" in the report.

Prior evidence I already know (read before writing this): TRADER_HEURISTICS Appendix A (TTrades predicts the next level
taken, not the close direction); CONFLUENCE_RESULTS (`daily_bias_with`, a TTrades variant, averaged -0.14R on 7 beds;
`trend_1h_with` +0.30R pooled, z 2.66, not significant after 92 tests). These are the reasons for the nulls below.

## 0. Common definitions

- Data: `data/NQ_5m.csv` (TradingView NQ1!, additive back-adjusted, so levels are consistent across rolls) via
  `strategy_lab.bars()`. CME day = 18:00-17:00 ET, labeled by the date it ends.
- A **full day** has >= 150 5m bars. Shorter (holiday) sessions are never used as reference candles (Y, P, swings, weeks).
- Tick 0.25. A buy-side level is **taken** when a 5m high >= level + 1 tick; sell-side when a 5m low <= level - 1 tick.
- `ADR20` = mean high-low of the prior 20 full days. `ATR14d` = mean daily true range of the prior 14 full days.
- **Causality.** At time t only 5m bars with `time + 300 <= t` exist. A daily bar is usable once its day has ended
  (17:00 ET of its date). 4H bars are 18:00-aligned (18, 22, 02, 06, 10, 14 ET) and usable after their nominal end.
  Weeks = Mon-Fri trading days by ISO week; only completed weeks are used.
- Swings = 3-candle fractal (k=1) on that timeframe: H[i] > H[i-1] and H[i] > H[i+1]; known at the close of bar i+1.
  BOS up = a close above the most recent confirmed, not yet broken swing high; BOS down mirror. Trend = last BOS.
- Every method returns `{"dir": +1/-1/0, "draw": price|None, "draw_label", "confidence": 0-1, "why"}`.

## 1. Methods

**A. `ttrades` (TTrades candle closure).** Y = last full day before today, P = the one before. tol = 0.
- CONT_UP: Y.C > P.H -> +1, target Y.H. CONT_DN: Y.C < P.L -> -1, target Y.L.
- Outside day (Y.H > P.H and Y.L < P.L) closing inside -> 0.
- REV_DN: Y.H > P.H, Y.C <= P.H, Y.L >= P.L -> -1, target Y.L. REV_UP mirror -> +1, target Y.H.
- INSIDE (Y.H <= P.H and Y.L >= P.L) -> 0.
- dir is fixed for the whole CME day. The draw at t is the target if still untaken today, else the nearest untaken
  HTF pool (inventory of B) in the bias direction.

**A2. `ttrades_carry`.** As A, but INSIDE carries the previous day's A2 value (recursively). Outside-close-inside stays 0.

**B. `htf_draw` (ICT HTF draw on liquidity).** Price p = last close at t. Inventory of pools untaken through t:
- PWH/PWL (last completed week) weight 2.0; daily swing H/L (last 60 full days) 1.5; PDH/PDL (Y.H/Y.L) 1.0;
  4H swing H/L (last 30 days) 0.5. Pools within 1 tick of each other are merged (max weight).
- Equal highs/lows: +1.0 if another distinct daily/4H swing on the same side is within 0.05 x ADR20.
- Candidates: distance d = |level - p| / ADR20 <= 1.5. Score = weight + eq bonus - d.
- S_up / S_dn = best score above / below. dir = +1 if S_up - S_dn >= 0.5, -1 if S_dn - S_up >= 0.5, else 0
  (a side with no candidate scores -inf; neither side -> 0). Draw = best pool of the winning side.
- B is evaluated at t (it moves intraday as pools are taken).

**C. `structure` (HTF structure).** d_tr = daily BOS trend (full daily bars usable at t), h4_tr = 4H BOS trend (4H bars
closed by t), pd = +1 if p is below the midpoint of the last 4 completed weeks' high-low (discount), -1 if above.
s = d_tr + h4_tr + pd; dir = sign(s); confidence = |s|/3. Draw = nearest untaken HTF pool in that direction.

**D. `open_amd` (daily open / AMD, midnight and 09:30 opens).** MO = 00:00 bar open, O930 = 09:30 bar open.
- Bullish event: a 5m bar j between 00:00 and 10:55 whose low takes an untaken sell-side pool (PDL; Asia low
  20:00-23:55, usable from 00:00; London low 02:00-04:55, usable from 05:00; overnight low 18:00-09:25, usable from
  09:30) with low_j < the open (MO; or O930 for bars from 09:30), followed by a 5m close back above that open.
  dir = +1 from that close. Bearish mirror. The latest event wins. Invalidated (dir 0) by a later close beyond the
  sweep extreme. Before any event dir = 0. Draw = nearest untaken buy-side pool (session or HTF) above.

**E. `composite` = vote of A, B, C:** +1 if at least 2 say +1 and none says -1; -1 mirror; else 0.

**F. `session_amd` (owner's session AMD; added on the coordinator's instruction at ~19:45 ET, before results).**
"Asia typically accumulates, if London manipulates New York will distribute, if London is in the process of manipulating
New York will usually follow through." State decided at 09:25 ET from closed bars (last close = the 09:20 bar's, c925);
dir = 0 before 09:25; fixed for the rest of the day.
- Asia = 20:00-23:55 bars (prior evening) high/low. London = 02:00-04:55 bars. Extended window (variant) = 02:00-09:20.
- London took the Asia low = a London low <= Asia L - 1 tick (high mirror).
- REV_UP: took the low, not the high, and c925 > Asia L (variant `lo`: c925 > the 02:00 London open) -> NY distributes UP.
- REV_DN: mirror. INPROC_DN: took the low, not the high, c925 <= Asia L (variant: <= London open). INPROC_UP mirror.
- BOTH (took both) -> 0. NONE (took neither) -> 0.
- Two readings of INPROC are tested, both pre-registered: **F1 `samd_cont`** = INPROC continues (INPROC_DN -> -1);
  **F2 `samd_rev`** = INPROC completes the reversal (INPROC_DN -> +1). **F0 `samd_rev_only`** = REV states only.
- Draw for UP = the nearest untaken of {London H, Asia H, PDH} above price (mirror for DOWN).

**E2. `composite2` = vote of A, B, C, D, F0:** +1 if at least 2 say +1 and none says -1; mirror; else 0.

**Reference (not a bias method; the benchmark from CONFLUENCE_RESULTS): `h1_trend`** = 1H (clock-aligned) BOS trend.

## 2. Raw predictive test (no strategy)

- Days 2022-01-03 .. 2026-10-16 with a 09:30 bar and >= 70 RTH bars. Bias computed at t = 09:30 (bars closed by 09:30).
- RTH = 09:30 open (O930) to the 15:55 close (C). Metrics on biased days (dir != 0):
  coverage; direction accuracy P(sign(C - O930) = dir); move = dir x (C - O930) / ADR20;
  hit_draw = P(RTH takes the draw), the draw being untaken at 09:30; hit_mirror = P(RTH takes the distance-matched
  opposite level O930 - (draw - O930)); MFE edge = (excursion with the bias - excursion against) / ADR20.
- Nulls: (1) the mirror level (controls for distance/proximity); (2) random bias = 2,000 permutations of dir across the
  biased days (keeps the long/short mix, so NQ's up-drift is in the null). One-sided p = share of permutations >= real.
- Splits: calendar years 2022-2026; dev 2026-01-02..06-30 / confirm 2026-07-01..10-16.
- Sanity check: reproduce Appendix A (CONT_UP -> the CME day takes Y.H about 80%).
- F also gets the coordinator's state table: frequency per state; NY direction in the predicted direction;
  max excursion each way in ATR14d; P(NY takes Asia H / London H / PDH) (mirror for DOWN) by 12:00 and by 16:00 among
  days the level is untaken at 09:30; NONE days: which Asia side NY takes; unconditional baselines; by year; 2026 monthly.

## 3. Alignment test on each model's trades

- Beds (NQ): ENG1 `conf_testbed_orig1day.json` (ytd + y2025); ENG2 `conf_testbed_engine.json`; SB
  `SB_trades_NQ_base.json`; MECH `MECH_trades_NQ_base.json`; M22 `M22_trades/M22_NQ_nobias.json` (canon already filters on
  a TTrades-like bias, so nobias is the fair bed; canon reported for information); CONT `CONT_trades/CONT_NQ_FVG.json`
  (IFVG_AMPM for information); ATM `ATM_trades_1m_base.json` and `ATM_trades_1m_best.json` (1m/3m, 2026 only; the owner's
  model, priority), ATM 5m all-signal diagnostic `ATM_trades_diag_noskip_flat.json` for information.
- Bias at the trade's `entry_t` (for the engine that is the fill bar, so the last bar used closed at the fill bar's open).
  aligned = trade dir == bias dir; counter = opposite; neutral = 0.
- Per split: n, win %, avg R with bootstrap 95% CI, PF, net $. Aligned-only and skip-counter (aligned + neutral):
  trades/week, net, PF, by dev / confirm / y2025 (2025-04-14..12-31) and 2026 by month.
- Primary statistic: diff = avg R(aligned) - avg R(counter).
- Null: permute bias labels among trades of the same direction within a bed (2,000 times; the same permutation for every
  method, so method correlation is kept). Per-test p (two-sided); Benjamini-Hochberg at q = 0.10 over all method x bed
  tests; family-wise 95% line = the 95th percentile of the max |z| over all tests per permutation.
- Pooled per method: equal-weight mean diff over the independent beds ENG1, SB, MECH, M22, CONT, ATM1m (ENG2 contains
  ENG1; ATM best is a subset of ATM base), with its own permutation p.
- ATM question (coordinator): ATM always fades a sweep of the 07:00-09:25 range, so "sweep against the bias, then
  reverse toward the draw" is exactly the aligned split, and "sweep with the bias" the counter split. Reported as such,
  with Jul-Oct shown.
- "Best method" = the highest pooled alignment z; it is chosen after seeing results and labeled as such. Its 2026
  monthly aligned-only table is reported per model.
