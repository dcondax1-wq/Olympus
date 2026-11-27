# Setup grades (A+/A/B/C) + conviction sizing for every bot: pre-registered 2026-11-27 evening, BEFORE any grade was computed

Owner: "the bot should risk a good amount based on each trade, what it thinks: A+ setups, B+ setups."
Already rejected (docs/TESTED_AND_REJECTED.md): meta-labeling 102 facts / 10 models (2026-10-23), edge-d meta size (2026-11-22),
setup grade "calm person" 7 warnings (2026-11-18), A+ quality score + 13 size tilts (lit-edge 2026-10-30), grade/confidence sizing.
What is new here: one frozen grade per bot from a wider fact list, every bot, maps that also skip C, a leverage control.

## Trades (fixed sources, costs in)
tools/money/combo_account.trades() (the live-combo reference store, 2021-11-01 .. 2026-10-16): Z = LIT/Zlarior, A = ATLAS
(EMA / MACD / S-R members), B = BLITZ. R = pts / risk (costs as stored). Periods: H1 = 2026 Jan-Jun (FIT), H2 = 2026 Jul 1 -
Oct 16 (check; the store ends there), REF = 2021-11 .. 2025 (check).
POSEIDON (order-flow lane A): real ticks only from Sep 2026 (51 days, ~40 trades, research/orderflow): no Jan-Jun trades, so no
grade can be fitted on H1. Reported as NOT GRADABLE; its forward gate (30 paper trades) stays the only test.

## Facts at entry (only bars before the entry bar; NQ 5m futures, VIX daily prior close, data/news/events.csv)
stop_pts, stop_atr (stop / 5m ATR14), rr (target / stop; BLITZ has no fixed target: dropped), atr_regime (5m ATR / mean 5m ATR
of the prior 20 sessions), vix (prior close), trend_d (with (+1) / against (-1) the prior close vs its 20-day SMA), trend_h
(with / against 5m EMA240 vs EMA600 ~ 1h EMA20/50), range_adr (day's range so far / 14-day ADR), news_min (minutes to the nearest
high-impact event that day, capped 240), session bucket (<09:30, 09:30-12:00, >=12:00 ET), day of week; LIT only: sweep depth
(ATR), displacement (ATR), inducement count (from engine/lit candidates, matched by day + side); ATLAS only: member.

## Graders (2)
- G1 fitted on H1 only: each numeric fact -> its H1 percentile, signed by the sign of its H1 Spearman rho with R; categorical
  facts (session, weekday, member) -> H1 mean R per bucket shrunk (n x mean / (n + 10)), as a percentile. Score = mean.
- G2 trader's prior, NOT fitted: + with daily trend, + with 1h trend, + bigger rr, + smaller stop_atr, + VIX 15-25, + news > 30
  min away, + range_adr < 1; LIT also + depth, + displacement, + inducements. Score = mean of signed H1 percentiles.
- Grades by H1 score quantiles, frozen: C < 25%, B 25-60%, A 60-85%, A+ >= 85%.

## Sizing maps (3) and the leverage control
M1 A+ 1.5 / A 1.25 / B 1.0 / C 0.5;  M2 A+ 1.5 / A 1.0 / B 1.0 / C skip;  M3 A+ 2.0 / A 1.5 / B 1.0 / C 0.5.
Control for each map: a FLAT multiplier = that map's mean multiplier over the period's trades (same average risk, no grade).
2 graders x 3 maps x 3 bots = 18 variants. Holm over 18.

## Tests
1. Separation: Spearman(score, R) on H2 and REF; mean R by grade; permutation p (5,000 shuffles of the score).
2. Raw money per bot at a reference size (LIT engine qty_for, ATLAS $500, BLITZ $300 a trade): trades/wk, PF, net $, $/mo, max DD.
   p = share of 5,000 within-period grade shuffles whose map net >= the real one, on H2 (one-sided); Holm over 18.
3. Account (LIT + ATLAS on the Builder 50K, combo_account live row a50_eval, every MFFU rule, 1,000 paths): for the 6
   grader x map pairs applied to both Z and A: eval pass / fail %, median sessions to pass, first payout session, $/mo per slot.
   BLITZ is paper (owner 2026-11-24): raw only.
PASS (per variant) = raw net > live in H1 AND H2, REF net not below live by > 5% of |live| or $500, Holm p < 0.05, beats its
flat control in H1 and H2; account $/mo higher in H1 and H2 with fresh-eval fail not +3 points. Expected: NO (entry facts = chance before).
