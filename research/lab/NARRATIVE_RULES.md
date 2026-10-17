# NARRATIVE RULES: the bot's "trader brain" (pre-registered)

**Version 1 written 2026-10-16 19:00-19:15 ET, before any outcome was computed.** Code: `engine/narrative.py`; evaluator: `tools/lab_narrative_run.py`. Nothing in sections 1-6 may change after the first scored run. Later versions (v2 = trader-heuristics fold-in, experience layer) are added as **new, labeled sections** and are reported next to v1, never instead of it.

Priors used to set the v1 weights (stated so the reader can discount them): DOL_PLAYBOOK.md (definitions), CONFLUENCE_RESULTS.md (with-trend +0.30R pooled, NQ>ES strength +0.17R, news days negative on 2025 beds, "below the open" backwards *without* bias), DRAW_LEARNER.md (distance, PM and within-reach predict whether a draw is hit). Those studies used overlapping 2025-2026 data, so the 2026 dev/confirm test of v1 is **not fully independent** of them. The 2021-2024 engine trades and the walk-forward experience layer are the cleaner checks.

## 0. Causality

- Bars: 5m CME futures (TradingView NQ1!/ES1!), labeled by open time (ET). At decision time `t` only bars with `open + 300 <= t` exist.
- HTF bars (1H clock-aligned; 4H anchored at 18:00 ET; daily = CME day 18:00-17:00 labeled by its end date; week = trading days of one ISO week) are built from those closed 5m bars and are usable only after their last 5m bar has closed.
- `t` for an engine trade = its `entry_t` (the fill bar's open = the signal bar's close). For an ATM trade `entry_t` is already the signal close.
- Pre-market narrative = the state at 09:30 ET (the 09:25 bar is the last one). Later calls add an intraday update (rule 2.7) but never change the pre-market part.

## 1. Shared measurements

1. `ATR5` = Wilder ATR(14) on 5m; `ADR10` = mean high-low of the last 10 completed CME days.
2. Swings: k=1 (3-candle fractal) on 1H / 4H / daily; k=2 on 5m (DOL D1).
3. Structure direction on a TF = the sign of the most recent BOS: a close above the latest confirmed, unbroken swing high = +1; a close below the latest confirmed, unbroken swing low = -1 (DOL D10, close-based).
4. Pools (untaken = no 5m high >= level + 1 tick / low <= level - 1 tick since the pool became usable):
   PDH/PDL, PWH/PWL, prior RTH H/L (09:30-16:00), today's Asia (20:00-00:00), London (02:00-05:00), ATM (07:00-09:25) and overnight (18:00-09:30) H/L, 4H swings (last 10 days), daily swings (last 60 days), and EQH/EQL = two 1H swings within max(2 ticks, 0.1 ATR_1h), >= 3 bars apart (last 5 days). Tier A = all except 1H EQH/EQL, which are Tier B.
5. Dealing ranges: daily DR = [min(PDL, today's low so far), max(PDH, today's high so far)]; weekly DR = [min(PWL, this week's low so far), max(PWH, this week's high so far)]. Position p = (price - low)/(high - low): discount p < 0.45, premium p > 0.55, else equilibrium.
6. Remaining range = ADR10 - (today's running high - low). `reach` = max(0.5 ADR10, remaining) (DOL-4).
7. News = `data/news/events.csv`, impact `high` (CPI, NFP, FOMC, PPI, ...).

## 2. Pre-market narrative `narrative(bars5, t, es5)`

2.1 **HTF bias score** (sum; positive = bullish):

| component | rule | weight |
|---|---|---:|
| daily structure | last daily BOS up / down | +/-1.0 |
| 4H structure | last 4H BOS up / down | +/-0.75 |
| 1H structure | last 1H BOS up / down (as of 09:30) | +/-0.5 |
| prior-day candle (TTrades closure) | closed above the day-before high, or swept the day-before low and closed back inside = +1; mirror = -1; inside day = 0; outside day = +/-0.5 by close location; else 0 | +/-1.0 |
| prior-day close location | CLV >= 0.75 = +0.5, <= 0.25 = -0.5 | +/-0.5 |
| overnight raid | one side of Asia/London taken and price back on the other side of it at 09:30, the other side untaken (sell-side raided = +0.5) | +/-0.5 |
| weekly extreme | weekly DR p > 0.85 = -0.25, p < 0.15 = +0.25 | +/-0.25 |

`bias` = long if score >= +1.0, short if <= -1.0, else neutral. `conviction` = min(1, |score| / 3).

2.2 **Expected daily PO3**: with a long bias and price below the 18:00 daily open at 09:30 -> "manipulation low pending (Judas), then expansion up"; long bias and price above the open with the session low already below the open -> "manipulation done, expansion phase"; long bias and price above the open without a low under it -> "no manipulation yet: watch for a dip under the open". Shorts mirror. Neutral bias -> "two-sided, wait for a raid".

2.3 **Overnight**: which of Asia / London / ATM H/L were taken by 09:30 (and by `t`), NDOG (18:00 open - 16:55 close), RTH gap (09:30 open vs prior 15:55 close, in ADR units; known only from 09:35).

2.4 **Primary draw**: the nearest untaken Tier-A pool in the bias direction at least 0.15 ADR10 away; if it lies beyond `reach`, the story says so and the draw becomes the nearest Tier-A/B pool inside reach (if any). Neutral bias: the nearer of the two sides' nearest Tier-A pools, labeled two-sided.

2.5 **Day type** score: +1 prior day inside or NR4 (smallest range of 4); +1 |RTH gap| >= 0.25 ADR (from 09:35); +0.5 CPI/NFP day; -1 overnight range >= 0.6 ADR (range already used); -1 FOMC day; -0.5 prior day range >= 1.3 ADR. `day_type` = expansion if >= +1, consolidation if <= -1, else normal.

2.6 Output: `bias`, `conviction`, `draw` {price, label, dist_pts, within_reach}, `day_type`, `po3`, `overnight`, `htf`, `news`, `adr10`, `story` (a short trader paragraph built from the above).

2.7 **Intraday update** (t > 09:30): today's range, remaining range, which pools were taken since 09:30, `draw_hit` (the primary draw traded through), and **bias failure**: two consecutive 5m closes beyond the opposite-side Tier-A pool nearest the 09:30 price (long bias: below it) -> bias becomes neutral ("bias failed"). The update is appended to the story.

## 3. Setup judgment `assess(setup, narrative, bars5, es5)`

Each element returns a score and a one-line reason. Weights are fixed here.

| id | element | rule (long; shorts mirror) | score |
|---|---|---|---|
| E1 | align | with the bias: +2 x max(conviction, 0.5); neutral: 0; against: -2 x max(conviction, 0.5) | -2..+2 |
| E2 | manipulation into the draw | the swept pool is on the side opposite the draw, aligned with the bias, draw untaken: +1. Against the bias and the bias draw is still untaken (fading the narrative): -0.5. After the draw was delivered: a with-bias trade -0.5, a fade 0 | -0.5..+1 |
| E3 | location | daily-DR position at entry < 0.35 (discount): +1; > 0.65 (premium): -1 | -1..+1 |
| E4 | timing | decision 09:30-10:30 +1; 10:30-11:00 0; 11:00-12:00 -1; 12:00-13:30 -1.5; >= 13:30 -1; before 09:30 -0.5 | -1.5..+1 |
| E5 | quality | strongest body between the sweep extreme and the decision >= 1.5 ATR5 +1, >= 1.0 +0.5, < 0.7 -0.5; V speed (bars from extreme to decision) <= 3 +0.5, >= 9 -0.5; IFVG >= 0.25 ATR5 (when known) +0.25; trigger TF >= 15m +0.25; capped to [-1, +1.5] | -1..+1.5 |
| E6 | intermarket | SMT (NQ took the reference low of the prior 2 h, ES did not) +1; NQ-ES return since 09:30 (18:00 before 09:30) in the trade's favor +0.5, against -0.5; no ES data 0 | -0.5..+1.5 |
| E7 | room | target within reach +0.5, beyond reach -1; today's range already >= 1.0 ADR10: -1 more | -2..+0.5 |
| E8 | path (DOL-6) | n_res (fresh 5m k=2 swings of today+yesterday and live 15m opposing FVGs in the corridor, merged) <= 1: +0.5; >= 3: -0.5 | -0.5..+0.5 |
| E9 | news | CPI/NFP/FOMC day: -1; a high-impact release within -10..+15 min of the decision: SKIP (hard veto) | -1 |
| E10 | PO3 location | bias long and entry below the 18:00 daily open ("buying the manipulation"): +0.5; neutral bias or against: 0 | 0..+0.5 |

**Total** S = E1 + ... + E10. **Grade**: A if S >= 3.0; B if 0.5 <= S < 3.0; C if -2.0 <= S < 0.5; **SKIP** if S < -2.0 or the news veto. `decision` = TAKE for A/B/C, SKIP otherwise.

Outcome-blind calibration (allowed once): if on the 2026 dev trades any of A/B/C holds < 10% or > 60% of trades, the A and C cutoffs move to the dev 70th and 25th score percentiles; this check reads scores only, never R.

**size_tier**: A = $700 risk, max 10 MNQ (1 NQ); B = $350; C = $175 (min 1 MNQ); SKIP = 0.

**target_plan**: expansion or normal day with LRLR/neutral path and grade A/B -> `partial_runner` (50% at the first IRL >= 1R, runner to the ERL draw/target). Consolidation day, HRLR, or grade C -> `first_draw` (all out at the first draw >= 1R; if none, the setup's own target).

**manage_mode**: `hold` (expansion day, grade A/B) or `quick` (consolidation day, grade C, or PM entry).

**thoughts**: 2-4 sentences naming the strongest positive and negative elements and the plan.

## 4. In-trade thinking `manage(position, bars_since_entry, narrative)`

Checked at each 5m close, first match wins; every action has a one-line reason.

1. M1 stop / target / TP1 fills are intrabar (stop first on a tie).
2. M2 **cut on no progress**: 12 bars (60 min; `quick` 9 bars) after entry, MFE < +0.5R and no partial -> exit.
3. M3 **opposing displacement**: a 5m CISD against the trade (close beyond the open of the first candle of the latest in-favor series that began after entry) made by a displacement candle (body >= 1.0 ATR5, body >= 60% of range) while MFE < +1R -> exit; after the partial -> exit the runner.
4. M4 **IRL rejects**: price came within 0.1R of TP1 (or took it) and the bar closes as an opposing displacement candle (body >= 0.8 ATR5, close in the far 30% of its range) -> take profit on everything left.
5. M5 **break-even**: after the partial fills, or after a 5m BOS in favor (close beyond a 5m swing that formed after entry) with MFE >= +0.5R -> stop to entry + 2 ticks.
6. M6 **trail** (`hold` mode, after break-even): at each 5m BOS in favor, stop = max(stop, protected low - max(2 ticks, 0.1 ATR5)).
7. M7 session: at 12:00 exit if the stop is still below entry; flat at 15:55.
8. Otherwise hold, with a reason (e.g. "consecutive displacement in favor, letting it run").

## 5. Evaluation (fixed before running)

- **Primary bed (a)**: `research/lab/conf_testbed_orig1day.json`, 2026 (dev 01-02..06-30, confirm 07-01..10-16) and 2025-04-14..12-31. Outcome = the engine's own trade R and P&L (its own management). Setups are rebuilt causally from bars: entry = fill-bar open + 1 tick, stop = entry - dir x risk_pts, sweep = most extreme bar of the last 36 bars that matches the stop, swept pool = the most significant pool that bar took, target = entry + dir x rr_plan x R.
- **Ranking question**: avg R by grade, A > B > C on dev AND confirm; plus Spearman(score, R) and A-minus-C with a bootstrap CI.
- **Policy readouts** (both fixed now): P-drop = remove C and SKIP, A at $700 (max 10 MNQ), B at $350; P-tier = keep C at $175. Re-sized P&L = per-contract P&L x new quantity. Stats from `strategy_lab.stats()` (net, PF, max DD, 50K rolling pass vs zero-edge, losing months, trades/week); `score()` is called only for the final named runs.
- **Extra check (same v1, no tuning)**: the 987 engine trades of `research/five_year/run_live.json` (2021-11..2026-10).
- **(b)** the ATM model's own trades via `tools/lab_models/atm.py run()` (flat sizing for ranking), same questions.
- **Alternatives (at most 3, all reported)**: Alt-1 = v2 (trader-heuristics fold-in, section 7 when written); Alt-2 = experience-adjusted grades (section 6); Alt-3 = brain management (section 4) replacing the engine's exits on the same entries.
- **Thought logs (c)**: 2026 bed trades sorted by entry time; winners and losers taken at evenly spaced ranks (5 each), not hand-picked.
- Frequency is reported with every readout; the owner needs about 2-5 trades a week.

## 5b. Implementation notes (written 19:15 ET, after the outcome-blind distribution check, before any scored run)

- Outcome-blind check on the 2026 dev bed (54 trades, scores only): A 18.5%, B 31.5%, C 42.6%, SKIP 7.4%. Every share is inside 10-60%, so **the fixed cutoffs stand** (no recalibration).
- Day type in the pre-market (t <= 09:30) uses the pre-open gap (09:25 close vs the prior RTH 15:55 close); the actual 09:30 open is only known from 09:35 and is reported in the intraday update.
- Bias failure (2.7) uses the opposite-side Tier-A pool nearest the 09:30 price, whatever it is (often the ATM or overnight extreme), exactly as written.
- `manage_mode` has a third value, `normal` (neither hold nor quick): 60-min stall rule, break-even rules, no trailing.
- Engine setups: the swept pool is the most significant pool that was still untaken 6 bars before the raid extreme and was traded through by the final leg into it. "Local raid" when none.
- E5 V speed = bars from the raid extreme to the signal bar (the ATM model's own `bars_to_v` when given).

## 7. Version 2: trader-heuristics fold-in (written 19:20-19:30 ET, BEFORE any v2 run)

Source: `research/lab/TRADER_HEURISTICS.md` (sections 0-7 as of 19:13 ET; sections 8-9 were not yet written). Selection rule: keep a heuristic only if the file rates it **E-pub/E-own** or **M with 3+ independent lineages** and gives a causal mechanical rule. Single-lineage items (macros/Silver Bullet S3, weekly profiles B4, Quarterly Theory) and items the file marks **X** (compression T5, ADR exhaustion N3) are left out or removed.

**Honesty note:** v2 was written after the v1 results were known (v1 did not rank trades). The selection rule above is the heuristics file's own reliability codes, not the v1 per-element results, which I did not inspect element by element. Still, v2 is not as blind as v1.

v2 = v1 with these changes (weights fixed here):

| id | heuristic (file id) | rule (long; shorts mirror) | score | replaces |
|---|---|---|---|---|
| H1 | HTF alignment (B6, broadest agreement) | trade dir = last 1H BOS dir and the daily BOS dir not opposed: +1; trade against the 1H BOS dir: -1 | -1..+1 | E1 |
| H2 | TTrades draw (B1, E-own) | yesterday vs the day before, tol = max(0.05 ADR10, 4 pts): CONT_UP (Y.C > P.H + tol) target Y.H; CONT_DN mirror; REV_DN (Y.H > P.H, Y.C <= P.H, Y.L >= P.L) target Y.L; REV_UP mirror; inside day: target by candle colour (weak); outside day: none. Target live until touched, void if the opposite Y extreme trades first. Trade toward a live target: +1 (CONT) / +0.5 (REV, inside); a continuation in the target's direction after it was touched: -1; against: 0 | -1..+1 | new |
| H3 | one-side rule (B3, nqstats + E-own) | one prior-RTH extreme already taken today (since 09:30) and the trade's target lies at/beyond the *other* prior-RTH extreme: -1 | -1..0 | new |
| H4 | early direction persists (T7, E-pub + E-own) | decision >= 10:30: price on the trade's side of the midnight open, the 09:30 open and RTH VWAP: +1; on the wrong side of both MO and O930: -1, unless the setup swept a named pool with >= 1.0 ATR5 displacement (then 0); before 10:30: 0 | -1..+1 | new |
| H5 | killzone timing (G4) + first minutes (N5) | signal close <= 09:45: -1 (N5; the file says SKIP, I use -1 to protect the 2/wk floor); 09:50-11:00 or 13:30-15:00: +1; 11:30-13:30: -1; after 15:30: SKIP | -1..+1 | E4 |
| H6 | lunch chop (S4, 4+ lineages + E-pub) | signal close 11:35-13:30 and not `lunch_ok` (by 11:30 the IB extended >= 1.0 IB range on one side, other side untouched): SKIP | veto | new |
| H7 | displacement quality (G2, 5+ sources) | leg = raid extreme -> signal bar. Checks: (a) best in-direction body/range >= 0.6; (b) leg span >= 1.5 ATR5; (c) an in-direction 5m FVG >= 0.2 ATR5 inside the leg; (d) a CISD or 5m BOS in the leg. 4/4: +1; 3: 0; <= 2: -1; 3+ no-progress closes in the leg: -1 | -1..+1 | E5 |
| H8 | SMT / relative strength (G3) | SMT or NQ-vs-ES strength in the trade's favor since the open: +1; never negative | 0..+1 | E6 |
| H9 | news windows (S6/N4, 5+ lineages) | keep the v1 day penalty (-1 CPI/NFP/FOMC) and the v1 release-window veto, plus SKIP: Tier-1 08:30 day with signal close <= 09:40; FOMC day with signal close >= 13:00; FOMC-minutes day 13:55-14:15; the 10:00 bar on a 10:00-release day | -1 / veto | E9 |
| H10 | room (E7 without the ADR-exhaustion part, N3 = X) | target inside reach +0.5, beyond -1 | -1..+0.5 | E7 |

**Amendment v2-final (19:35-19:45 ET, after the coordinator relayed the file's broadest-agreement list; still before any v2 run).** Hard skips are allowed ONLY for news windows, lunch, the first 15 minutes, risk stops and fading a trend/open-drive day. Changes and additions:

| id | heuristic (file id) | rule (long; shorts mirror) | score |
|---|---|---|---|
| H5 (amended) | first 15 minutes (N5) | signal close <= 09:45: **SKIP** (was -1); the rest of H5 unchanged | veto |
| H9 (amended) | news windows | the Tier-1 08:30 window ends at 09:45 (covered by H5); FOMC window = 13:00-14:40 (not the whole afternoon) | veto |
| H11 | primary draw (B2) | candidates = untaken pools 0.25-1.5 ADR10 from price; score = 2 (PWH/PWL) or 1 (PDH/PDL/prior RTH/daily swing) or 0.5 (session/4H/EQ), +0.5 if EQ, minus distance/ADR10; draw side = side of the best score; if the best-above and best-below scores differ by < 0.5 the day is two-sided. Toward the draw side: +1; against: -1; two-sided: -1 | -1..+1 |
| H12 | open drive (T1) | at 10:00 (09:30-09:55 bars): O930 within 0.05 ATRd of the OR30 low, OR30 close in its top 30%, last close >= O930 + 0.20 ATRd, no bar from the 3rd on trades back to O930 (ATRd = ADR10). Decision >= 10:00 and the trade fades the drive: **SKIP**; with the drive: +1 | veto / +1 |
| H13 | IB side (T3) | decision >= 10:30: ib_bias = +1 if the 10:25 close is above the IB mid and the IB low printed first (strong), +0.5 if only above the mid (weak); mirror. Trade with ib_bias: +1 strong / +0.5 weak; against: 0 | 0..+1 |
| H14 | gap fill / go (T6) | gap = O930 - prior RTH close, gA = abs(gap)/ADR10 (decision >= 09:35). gA < 0.2 and a fade toward the prior close before 10:30 with the gap unfilled: +1. Large gap (gA >= 0.35 or O930 outside the prior RTH range): a fade before a 30-min close back inside the prior range: -1 (not a skip); a with-gap trade: +1 | -1..+1 |
| H15 | 10 AM reversal (S1) | decision 09:50-10:30, the raid-extreme bar opened 09:50-10:20 and took the OR30 extreme on the side of the opening move (sign of the 09:55 close - O930); not when the OR30 closed in its outer 10% and the 10:00 bar is a same-direction displacement: +1 | 0..+1 |
| H16 | room to the first obstacle (N2/G5) | distance from entry to the nearest obstacle (fresh 5m swing, live 15m opposing FVG, untaken Tier-A/B pool) in the trade direction / R: < 1 -> -1.5; 1-2 -> -1; >= 3 -> +1 | -1.5..+1 |
| risk | daily stops (R2/R3) | in every policy readout on beds with more than one trade a day: no new trade after 2 losses, after the day reaches -$600, or after a +1R winner (no effect on the 1-trade-a-day beds) | - |

v2-final element list: H1, H2, H3, H4, H5, H6, H7, H8, H9, H10, H11, H12, H13, H14, H15, H16, plus E2 (manipulation / draw delivered, = N3 draw version), E3 (location, = G6) and E10 (PO3 location). E8 (path) is replaced by H16. Same cutoffs and calibration rule.

Kept unchanged from v1: E2, E3, E10.

**v2 outcome-blind checks (19:22 ET, before the v2 outcome run).**
- Dev grade shares at the fixed cutoffs: A 3.7%, B 22.2%, C 25.9%, SKIP 48.1% -> the calibration rule fires. Because the v2 score range is wider, the recalibrated cuts are A >= dev P70, B >= dev P25, C >= min(-2.0, dev P5); below that = score-SKIP. (The v1 text did not say where the SKIP line goes when recalibrating; this choice is made here, outcome-blind.)
- Vetoes on the 2026 bed: first 15 minutes 17 of 54 dev and 8 of 39 confirm trades; open-drive fade 1 + 1. The first-15-minute skip alone takes the bed from 2.26 to about 1.65 trades a week, so v2's policy readouts are expected to fail the 2/week floor on the engine's trades. That is reported, not patched.
- Extra readout (same v2 scores, no new rule): grades from the score alone with vetoes ignored, to separate "does the score rank trades?" from "what do the vetoes do?".

Grades: same cutoffs (A >= 3.0, B >= 0.5, C >= -2.0) and the same outcome-blind calibration rule on the 2026 dev bed. `assess`, `manage` and the evaluation protocol (beds, policies, metrics) are unchanged. v2 is Alt-1.
- Opens: MO = open of the 00:00 ET bar; O930 = open of the 09:30 bar; RTH VWAP = typical price x volume of the closed bars since 09:30.

## 6. Experience layer (walk-forward "learn like a person"), pre-registered with v1

- Memory = every past trade the brain has "seen": engine five-year trades (run_live.json), both test beds, and the ATM trades when available, de-duplicated by (entry time, direction). Each carries its element scores (computed causally at its own entry) and its realised R.
- At the start of each month M the brain re-weighs each element e using **only trades that closed before M**:
  - groups: e > 0 (liked), e < 0 (disliked), e = 0 (silent). Delta = mean R(liked) - mean R(disliked) when both have >= 10 trades; otherwise liked vs not-liked, or not-disliked vs disliked.
  - recency weights with a 12-month half-life; effective n = (sum w)^2 / sum w^2.
  - shrinkage: Delta_s = Delta x n_h / (n_h + 40), n_h = 2 / (1/n1 + 1/n2).
  - trust_e = clip(1 + Delta_s / 0.3, 0, 2): an element that kept paying is doubled at most; one that kept failing is ignored (never inverted). Cold start (< 10 trades on a side): trust 1.
- Experience score = sum of trust_e x E_e; graded with the same cutoffs as v1. Each month's learning is logged in plain English (the biggest trust changes and the evidence).
- Question: does the experience grade rank 2026 dev and confirm trades better than the fixed v1 (and v2) grades? Same metrics as above.

## 8. Later additions (after the scored runs; none changes a grade)

- **19:25 ET, owner request.**
  - New option: `assess(..., require_bias_alignment=True)` vetoes counter-bias setups unless the bias is neutral. It is off by default.
  - It was reported on vs off, together with a descriptive study of 6 bias definitions (`lab_narrative_run.py bias`). Nothing was selected from that study.
- **19:25 ET, thoughts text.** The thoughts now open with the bias line, for example: "Bias bullish (conviction 0.67): daily structure bullish; yesterday closed above the day-before high (NQ takes that high next day ~80%) ... so longs preferred. This trade is WITH/AGAINST the bias." This is text only.
- **19:25 ET, `narrative(..., bias_source=...)` hook.** `use_daily_bias(method)` lets `engine/daily_bias.py` (the other agent's module) replace the brain's bias once that module exists. It is untested here because the module is due after this deadline.
- **19:28 ET, generic setups.** Setups with no `targets` get the nearest untaken Tier-A pool at least 1R away, else entry + 2R. The engine and ATM beds always carry their own targets, so their results are unchanged. The lab-model beds use this rule.
- **19:28 ET, daily stops in the policy readouts.** After 2 losses, a day at -$600, or a +1R winner, no new trades are taken (R2/R3). The engine and ATM beds trade once a day, so they are unaffected.
- **19:36 ET, HTF bar closes.** HTF bars now count only once their clock period has ended (1H/15m at the clock, 4H blocks anchored 18:00, the CME day at 17:00). This makes a live frame behave exactly like research. All results were re-run and are identical. The no-lookahead check found 0 of 60 setups differing between full history and a frame cut at the decision time.

