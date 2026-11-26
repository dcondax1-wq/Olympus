# Day-type classifier + playbook routing: pre-registered design (written 2026-11-26 BEFORE any run; not changed after results)

Lead's question (big-regime): our bots lose most on the wrong DAY TYPE (live: LIT 0/7 in a falling market; structure study:
"LIT losers fought an expansion leg" 42-52%). Can a CAUSAL day-type call, known at decision time, route each bot to the days
its trades win? PAPER RESEARCH ONLY: nothing live, no sizing / arming / live_model change.

## Already rejected (not repeated here, checked in docs/TESTED_AND_REJECTED.md)
Prior-close VIX / VXN-VIX / VIX/VIX3M / GEX / range-percentile size tilts (lit-regime-sizing), market-weather guards round 1-3
(VRP, ATR / ER percentiles, trend-day share, variance ratio, NQ-VIX co-move), GEX day-type switch for NEW setups (edge-b),
meta-labeled LIT size from facts at the fill (edge-d, meta-labeling), BLITZ trend-day SIZE tilts from 430 single facts
(ab_edge: chance), structure tags F1-F5. NEW here: (1) an explicit multi-class DAY-TYPE label, (2) one walk-forward model
that combines the facts per checkpoint (not single-fact tilts), (3) its out-of-sample accuracy is measured first, (4) routing
is directional for LIT/ATLAS (trend AGAINST the trade vs with it), (5) a data-driven router that only uses past trades.

## Data (futures only)
NQ 5m `data/NQ_5m.csv` (2021-10 .. 2026-11-20); ES 5m only from 2025-04 (ES features -> a separate 2025+ model, reported, not
used for 2021-24 routing); VIX / VXN daily closes, CBOE vix9d / vix3m (prior close only); Tier-1 calendar `data/news/events.csv`
(FOMC / CPI / PPI / NFP, high impact: scheduled in advance, so known before the day).

## Day-type label (hindsight, RTH 09:30-16:00 ET; RATR = mean of the prior 14 RTH ranges; R = RTH high - low)
Priority order, first match wins:
1. **news_exp**: Tier-1 day AND R >= 1.3 RATR.
2. **trend_up / trend_down**: R >= 0.8 RATR AND |close - open| >= 0.5 R AND close in the top (bottom) 25% of the range.
3. **reversal**: the max excursion from the open on one side >= 0.4 RATR was made FIRST, then the close is on the OTHER side of
   the open by >= 0.25 RATR.
4. **range**: everything else (rotation / balance).

## Checkpoints (features use only bars that CLOSED before the time; daily data = the prior session's close)
- **C0 prior close (18:00)**: prior day type (one-hot), prior R / RATR, prior close location in its range, 5-day efficiency
  (|C - C5| / sum |dC|), prior VIX, VIX 1-day change %, VIX/VIX3M, VIX9D/VIX, VXN - VIX, Tier-1 today flag, weekday.
- **C1 02:00**: C0 + overnight range so far / RATR, (02:00 price - prior RTH close) / RATR, 02:00 price position vs prior RTH
  range (below / inside / above as a number), overnight move direction share.
- **C2 09:30**: C0 + full overnight range / RATR, gap (RTH open - prior RTH close) / RATR, open vs prior RTH range position,
  open vs prior RTH VWAP / RATR, 08:00-09:30 move / RATR, open position within the overnight range.
- **C3 10:30**: C2 + IB (09:30-10:30) range / RATR, IB close location, (10:30 price - open) / RATR, open-drive flag (the first
  15 min never trade back through the open by > 0.05 RATR and close >= 0.15 RATR away), IB broke the prior RTH high / low
  (each), count of 5m displacement bars (body >= 1.5 x the 20-bar mean body) and their net sign, IB volume / prior 20 IB mean.
- ES variant (2025-04+ only): + ES/NQ same-sign overnight move and same-sign first-hour move. Reported separately.

## Model + accuracy (walk-forward)
Multinomial logistic regression (numpy, standardized, L2 lambda = 1.0, fixed; no tuning), expanding window, refit at each
month start on all labeled sessions before it; first prediction month = the first month with >= 150 training sessions.
Reported per checkpoint, overall and per span (2022-25 / 2026 H1 / 2026 H2): accuracy, log loss, vs baselines (a) the majority
class, (b) the train-window class frequencies (climatology log loss), (c) "today = yesterday's type". Plus per-class precision
/ recall and the 2-class views that matter: trend-vs-not and trend-direction among predicted trend days.
**Accuracy kill-gate (stage 0):** at a checkpoint, if OOS accuracy does not beat the majority class by >= 3 points in EVERY
span, or log loss does not beat climatology in every span, routing that uses that checkpoint is reported as "no information"
(the routing is still run so the money is visible, but cannot pass).

## Which checkpoint a trade sees
The latest checkpoint that is <= the trade's entry time on that session: entries before 02:00 -> C0, 02:00-09:29 -> C1,
09:30-10:29 -> C2, >= 10:30 -> C3. (LIT trades mostly 01:00-09:00 -> C0/C1; ATLAS London -> C1, NY -> C2/C3; BLITZ -> C2/C3.)

## Routing versions (15, counted; multipliers on the trade's size, 0 = skip)
p_with / p_against = predicted P(trend in / against the trade's direction); top = the argmax class.
- LIT (sweep reversal):  L1 skip when top = trend against;  L2 x0.5 when top = trend against;  L3 x1.5 when top in {range, reversal};
  L4 skip when p_against >= 0.40;  L5 data router (below), skip.
- ATLAS (trend pullback): A1 skip when top = range;  A2 x0.5 when top = range;  A3 x1.5 when top = trend with;
  A4 skip when top = trend against;  A5 data router, skip.
- BLITZ (momentum):  B1 skip when top = range;  B2 x0.5 when top = range;  B3 x1.5 when top = trend with;  B4 skip when top = trend against;
  B5 data router, skip.
- Data router: at each month start, for that bot, mean R of its PAST trades (before the month) grouped by the predicted
  class-with-direction (trend_with / trend_against / reversal / range / news_exp); skip the next month's trades in groups with
  n >= 20 and mean R < 0.
- Shown for information only (not tradeable, cannot pass): ORACLE routing with the TRUE label (same rules), to show whether
  even a perfect day call would pay.

## Money / accounts (costs in)
- LIT: live trades (`tools/stops_targets_time.units`, risk-matched `size_matched`, costs in) -> H1 / H2 / 2021-25 net, PF,
  $/month, max DD, trades/week; Builder 50K eval two_week path (`tools/lit_edge.eval_path`, multiplier "m"): net, 2-week pass /
  fail %, median days; plus the account4_sim 60-session MC eval (`research/regime_guard` lit_eval: skip / half = risk / m).
- ATLAS: live stream `tools/atlas_health.stream` at fixed $250 (costs in) + funded Builder 25K MC (`atlas_health.score`, w = m).
- BLITZ: stored backtest rows (`research/learn/lessons.jsonl.gz`, usd) + a rolling-start Builder 25K eval (target $1,500,
  MLL $1,000, lock $100, DLL $600).

## Pass gate (ALL, for a version)
1. The checkpoint(s) it uses pass the accuracy kill-gate.
2. Net $ higher than today in 2026 H1, 2026 H2 AND 2021-25 (2021-10 .. 2022-06 has no prediction -> unchanged); PF not lower in any.
3. Trades/week >= 2 in H1 and H2 (LIT, ATLAS); BLITZ >= 1.
4. Accounts: LIT 50K two_week net higher and 2-week fail % not higher in H1 and H2, MC 60-session pass not lower by > 2 pts;
   ATLAS funded $/month not lower and dead-in-6-months not higher in H1 and H2; BLITZ 25K 2-week pass not lower, fail not higher.
5. Placebo: the same number of trades per span hit at random (2,000 draws, same multiplier) -> the 2026 H1+H2 $ gain must beat
   >= 99.67% of draws (0.05 / 15).
A version that passes every line becomes a needs-owner-yes card with exact rules. Otherwise rejected with the numbers.

## Round 2 addendum (written 2026-11-26 after round 1 = 0/15 pass, BEFORE any round-2 run)
Why: round 1's ORACLE rows (true label, not tradeable) show day type matters a lot for BLITZ only (skip true range days:
H2 $3.4k -> $6.7k, 2021-25 $4.6k -> $20.6k, H1 flat), and BLITZ enters 10:00-15:00, when more of the day is already seen.
LIT (01:00-09:00) and ATLAS (02:00-10:30) trade before any later checkpoint, and their ORACLE rows already fail 2026
(LIT skip true trend-against days: H1 $33.9k -> $29.2k), so round 2 is BLITZ only.
- New checkpoints C4 11:30, C5 12:30, C6 13:30 = C3 features + (bars closed before the time) RTH range so far / RATR,
  (price - RTH open) / RATR, price location in the range so far, (price - RTH VWAP so far) / RATR, which extreme printed
  first (+1 low first / -1 high first), move since 10:30 / RATR, |price - open| / range so far. Same model, same walk-forward,
  same kill-gate. A BLITZ trade sees the latest checkpoint <= its entry (10:30-11:29 -> C3, as in round 1).
- Versions (4): R2-B1 skip when top = range; R2-B2 x0.5 when top = range; R2-B3 skip when P(range) >= 0.60;
  R2-B4 x1.5 when top = trend with. Same money / 25K eval / placebo gates; placebo bar 0.05 / 19 (rounds 1 + 2 counted).
