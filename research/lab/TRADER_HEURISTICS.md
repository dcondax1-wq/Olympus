# TRADER HEURISTICS: how discretionary NQ/ES day traders think, made mechanical (16 Oct 2026)

Input for `engine/narrative.py`, the bot's "trader brain". Each heuristic below has these fields:

- **Traders say:** what practitioners mean, with source links.
- **Fails when:** how traders themselves say it breaks.
- **Evidence:** published statistics, our own NQ check, or "anecdotal".
- **Mech:** an exact causal rule on 5m NQ/ES bars, with suggested thresholds.
- **Effect:** what the bot should do with it.

Read sections 0 and 8 first. Section 9 lists the 15 heuristics with the broadest agreement.

## 0. Conventions

### 0.1 Reliability codes

| code | meaning |
|---|---|
| **E-pub** | Published statistics on NQ/ES: nqstats.com (NQ 2016–2025, about 2,500 sessions), Linnsoft (ES), edgeful (only the last 6 months), or academic papers. |
| **E-own** | Checked on our own `data/NQ_5m.csv` in this note: NQ1!, 2021-10-18 to 2026-10-16, 1,289 full CME sessions. These are base rates only. They are not trade P&L and include no costs. |
| **E-lab** | Already tested in this repo. See `CONFLUENCE_RESULTS.md`, `DOL_PLAYBOOK.md` §9 and `FIVE_YEAR_REPORT.md`. |
| **M** | Practitioner consensus from 3 or more *independent lineages*, with no statistics. |
| **S** | A single source or a single lineage. |
| **X** | Contradicted by data, ours or published. |

**Lineages.** ICT, innercircletrader.net, most LuxAlgo "ICT concept" pages and ICT-derived TradingView scripts count as **one** lineage. Agreement among them is not independent confirmation. TTrades is ICT-derived but adds his own rules. Auction market theory (Dalton/Steidlmayer), Al Brooks, prop-firm coaches and the statistics sites are separate lineages.

### 0.2 Effect vocabulary

| effect | meaning |
|---|---|
| `SKIP` | Hard veto. |
| `GRADE±n` | Move the setup grade up or down n steps. |
| `SIZE×k` | Multiply size by k. |
| `TGT near` | Target the first opposing pool, VWAP, or a 50% level. |
| `TGT far` | Target the primary draw. |
| `HOLD` | Runner allowed; no early breakeven. |
| `QUICK` | Time stop, early profit, no runner. |

**Frequency guardrail.** The user requires 1–4 trades a week (memory: trade-frequency-constraint).

- Only the few heuristics marked `SKIP` should veto: news windows, lunch, and chop.
- Everything else adjusts grade, size, target or management.
- The lab's lesson applies: *candidate lift ≠ taken-trade lift*. Every heuristic must be re-scored on taken trades over all periods (FIVE_YEAR_REPORT).

### 0.3 Primitives (reuse `DOL_PLAYBOOK.md` §0–§1; new ones below)

The playbook supplies these and they are **not** redefined here:

- causality rules C1–C3: a 5m bar is labeled by its open and known at open + 5 min; HTF bars are built from 5m bars and used only once closed; the CME day runs 18:00–17:00 and the week runs Sun 18:00–Fri 17:00;
- swings D1, displacement D2, FVG D3, NDOG/NWOG D5, gap states D6, the pool inventory D7, EQH/EQL D8;
- pool status D9: taken = 1 tick through; swept = close back inside within 2 bars; run/accepted = 2 closes beyond, or one 1H close;
- BOS/MSS/protected low D10, CISD D11, dealing range and EQ D12.

New primitives, all in ET:

- **P1 anchors.**
  - `GO` = 18:00 bar open. `MO` = 00:00 bar open (the midnight open). `O800`, `O830` and `O930` = the opens of those bars.
  - `ON` = 18:00–09:25 (`ONH`/`ONL`).
  - `OR30` = 09:30–09:55 bars, known at 10:00.
  - `IB` = 09:30–10:25 bars, known at 10:30.
  - `Q1` = 08:00–09:55, `Q2` = 10:00–11:55 (the nqstats noon curve).
  - `LUNCH` = 11:30–13:30. `PM` = 13:30–15:55.
  - When you use an nqstats probability, use **its** windows: Asia 20:00–01:55, London 02:00–07:55, NY 08:00–16:00. DOL_PLAYBOOK's Asia 20:00–00:00 and London 02:00–05:00 are different.
- **P2 volatility.**
  - `ATR5` = Wilder 14 on 5m.
  - `ADR20` = mean CME-day range over the prior 20 sessions. This matches `tools/lab_confluences.py`. DOL_PLAYBOOK's ADR10 is an acceptable alternative, but pick one.
  - `R20` = median of the last 20 RTH (09:30–16:00) ranges.
  - `ATRd` = mean of the last 14 RTH true ranges, excluding today. This is the AMT unit used in §1–§2: `e` = 0.05·ATRd, `m` = 0.10·ATRd. ADR20 may replace it, but use one unit consistently.
  - `tod_rng[t]` and `tod_vol[t]` = 20-session median range and volume for the 5m bar at clock time t.
- **Size caps.** Any `SIZE×` > 1.0 below is capped by R1/R4: never above 1.0× during the eval after a win, and risk never above the R4 budget.
- **P3 prior references.**
  - `PDH`/`PDL` (CME day).
  - `pRTH_H`/`pRTH_L`/`pRTH_C`. `pRTH_C` is the close of the 15:55 bar.
  - `PWH`/`PWL`, `MonH`/`MonL` (Monday RTH), `WO` (the Sunday 18:00 open).
- **P4 VWAP.** `rVWAP` is anchored at 09:30 and `gVWAP` at 18:00. Both use typical price (H+L+C)/3 × volume of closed 5m bars.
- **P5 approximate volume profile from 5m bars** (prior RTH session):
  - Use bins of 2.5 pts on NQ and 0.5 on ES.
  - Spread each bar's volume evenly over the bins its [L, H] covers.
  - `pPOC` is the bin with the most volume.
  - Build the value area the CBOT way: start at the POC and add the larger of the two-bin blocks above and below until the area holds ≥ 70% of volume. That gives `pVAH`/`pVAL`.
  - This is a TPO/volume-profile approximation. Real TPO letters use 30-min periods.
- **P6 chop metrics**, on the last n = 12 closed 5m bars:
  - `ER12` = |C_t − C_{t−12}| / Σ|C_i − C_{i−1}|.
  - `STACK12` = Σ(H_i − L_i) / (max H − min L).
  - `OVL12` = mean over the 12 bars of overlap(bar_i, bar_{i−1}) / range(bar_i).
  - `relVol6` = Σ range of the last 6 bars / Σ `tod_rng` of those 6 slots.
  - `CI14` = Choppiness Index(14).
  - `XV24` = number of 5m closes that switch side of rVWAP in the last 24 bars.
- **P7 time-of-day normalization.** `rel_rng[t]` = (H − L)[t] / tod_rng[t]. A "displacement vs time of day" is rel_rng ≥ 1.5 with the close in the outer 25% of the bar.
- **P8 news calendar.** `engine/news.py` is a static calendar, so it is not lookahead.
  - Tier 1: CPI, NFP, FOMC statement and press conference, PCE, PPI, GDP.
  - Tier 2 (10:00): ISM, JOLTS, UMich.
  - Fallback flag: a bar at 08:30, 10:00 or 14:00 with rel_rng ≥ 3.

### 0.4 Our own NQ checks (E-own), all in one place

Run on 2026-10-16. The code is reproduced in Appendix A.

| # | check | result |
|---|---|---|
| 1 | **TTrades close-above-PDH** (n=395): does the next session take yesterday's high? | 80.3% vs base 55.3%. It takes that high *first*, before yesterday's low, 78.2% vs 49.7%. |
| 2 | **TTrades close-below-PDL** (n=289): does the next session take yesterday's low? | 67.1% vs 46.2%. First: 64.7% vs 38.5%. |
| 3 | **Swept-high-closed-inside → low** (n=202) | 58.4% (+12 pts). |
| 4 | **Swept-low-closed-inside → high** (n=187) | 62.0% (+7 pts). |
| 5 | Same bias vs the next day's close direction | 52% / 42%. The bias does not predict the next day's **close direction**; it predicts the **next level taken**. |
| 6 | **Weekly extremes** (245 full weeks) | In up weeks the weekly low was on Mon 53%, Tue 21%, Wed 16%, Thu 9%, Fri 1%. In down weeks the weekly high was on Mon 37%, Tue 25%, Wed 21%. The high or low of the week falls on Mon/Tue 76% of the time. **Caveat:** for a random walk the extremes also cluster at the ends of the window (arcsine law). |
| 7 | **Side of the midnight open at 10:30** | Equals the side at the RTH close 76% of the time. At 09:30 it is 67%. |
| 8 | **Below the 09:30 open at 10:30** (n=602) | RTH closes above the open only 28.6% of the time, against 76.0% when price is above it at 10:30. "Buy below the open" without a reclaim is backwards. This matches E-lab `below_rth_open` −0.25R. |
| 9 | **"ADR used up"** | Range used by 11:00 does **not** shrink the remaining extension. After 11:00 the day extends either extreme by ≥ 0.25 ADR on 33–36% of days at every level of used range, and on **51%** when > 1.3 ADR is used. |
| 10 | **Compression** | Next-day range after an inside day = 1.07 × ADR20; after an NR7 = 0.91 (base 1.03). There is **no expansion edge**. |
| 11 | **RTH gap fill** (09:30 open vs pRTH_C) by \|gap\|/ADR20 | ≤ 0.05: 95%. 0.05–0.1: 79% by 10:30 / 88% by close. 0.1–0.2: 63/77%. 0.2–0.35: 37/55%. > 0.35: 10/33%. |
| 12 | **Opening-drive proxy** (09:30–10:00: open within 10% of one OR30 extreme, 10:00 close in the far 25%, OR30 ≥ 0.15 ADR; 8.7% of days up, 8.2% down) | Trades back to the 09:30 open later only 37% (up) / 32% (down). RTH closes beyond the 10:00 close 61% / 56%. |
| 13 | **Engine five-year log** (987 trades) | The 2nd trade of a day, which only follows a loss, averaged −0.022R (n=221), against +0.038R for 1st trades. The previous trade's result does not change the next trade's expectancy (+0.026R after a loss, +0.024R after a win). |

---

## 1. Daily bias

**The key finding for the brain.** On NQ the popular bias methods predict **which level gets taken next** (the draw) much better than **which way the day closes** (E-own #1–#5, #7, #8).

- Use bias to choose **targets** and to grade entries **toward** an untaken draw.
- Do not use it as a direction-of-day veto.
- Once the draw is taken, the bias has done its job (TFO: only 53.7% of hits close through).

**B1. TTrades candle-closure daily bias** (also applied to weekly candles).

Breadth: TTrades, coded independently by TFO and joshuuu, plus the ICT lineage's generic closure rule. Reliability: **E-own (strong for the CONT states, weak for the REV states)**.

- **Traders say** ([TFO script](https://www.tradingview.com/script/xdwgV3Fx-TTrades-Daily-Bias-TFO/), [joshuuu script](https://es.tradingview.com/script/ezS0ydMQ-daily-bias-ttrades-x-joshuuu), [Fractal Model summary](https://lilys.ai/es/notes/trading-strategy-20260202/only-trading-strategy-2026)):
  - Close above the prior high → tomorrow targets today's high (continuation).
  - Trade above the prior high but close back inside → reversal; tomorrow targets today's low.
  - The mirrors hold for the low.
  - An inside day takes its bias from the candle colour (TFO) or is neutral (joshuuu).
  - An outside day that closes inside gives no bias.
  - joshuuu's stricter reversal: the close must return inside the prior day's **body**. The bias stays live until its target is hit, then resets.
  - It works the same on weekly candles.
  - Execution comes from lower timeframes, 1H→5m or 30m→3m: a sweep-and-close-back candle at a point of interest, then a CISD, then the entry.
- **Fails when:**
  - Inside and outside days.
  - After the target is hit (the bias "completes").
  - Equal highs form where you want to sell.
  - Repeated continuation failures, which means the market is ranging.
  - Closes only a tick or two through the level (anecdotal).
  - The hit rate flatters the rule, because a strong close sits near the new high. Judge it by expectancy.
- **Evidence:**
  - TFO's example (CL, not NQ): 76.7% of PDH-bias days traded through the high.
  - **E-own (NQ, 1,287 days, CME day):**

| yesterday's state | n | next day takes the target | takes it FIRST | opposite side taken | next day closes with the bias |
|---|---:|---:|---:|---:|---:|
| close above prior high → target Y.H | 395 | **80.3%** (base 55.3%) | **78.2%** (base 49.7%) | 22.0% | 52.2% |
| close below prior low → target Y.L | 289 | **67.1%** (base 46.2%) | **64.7%** (base 38.5%) | 22.8% | 42.2% |
| swept high, closed inside → Y.L | 202 | 58.4% (+12.3) | 51.5% | 47.0% | 51.0% |
| swept low, closed inside → Y.H | 187 | 62.0% (+6.7) | 58.8% | 42.8% | 49.2% |
| inside, red → Y.L / green → Y.H | 62 / 87 | 77.4% / 75.9% | 64.5% / 65.5% | 47% / 44% | — |
| outside day, closed inside | 65 | Y.H 35%, Y.L 45% | — | — | — |

Notes on the table:
- The base rate for an up close (CME day) is 52.7%, so the last column shows **no** directional lift.
- E-own used tol = 0, a plain close beyond the level. The tol in the Mech below is a proposed refinement, so re-measure with it.
- Part of the lift is proximity: the 18:00 open sits near Y.H after a strong close. Condition on distance/ADR20 before relying on the size of the lift.

- **Mech:**
  - At 18:00, Y = the last closed CME day and P = the one before. tol = max(0.05·ADR20, 4 pts) for NQ.
  - `CONT_UP`: Y.C > P.H + tol → `b1_target` = Y.H.
  - `CONT_DN`: Y.C < P.L − tol → `b1_target` = Y.L.
  - `REV_DN`: Y.H > P.H, Y.C ≤ P.H and Y.L ≥ P.L → `b1_target` = Y.L. **A-grade** only if Y.C ≤ max(P.O, P.C), i.e. back inside the body, **and** the wick above P.H is ≥ 0.1·ADR20.
  - `REV_UP`: the mirror.
  - `INSIDE`: target by colour, weak.
  - `OUTSIDE_IN`: none.
  - Live state: the bias is valid until `b1_target` is touched. It is **void** if the opposite Y extreme trades first.
  - Run the same states on weekly candles (`wk_bias`).
- **Effect:**
  - Trades **toward** an untaken `b1_target`: `GRADE+1` for CONT states, `GRADE+0.5` (or 0) for REV states.
  - Use `b1_target` as `TGT far` when it is ≥ 2R away. Otherwise use it as TP1.
  - After it is touched: continuation trades in that direction need a new draw (B2), else `GRADE−1`.
  - Never `SKIP` because a trade is against `b1`; next-day close direction is about 50/50.
  - Weekly agrees: `GRADE+1`. Weekly opposes: `SIZE×0.5`.

**B2. ICT higher-timeframe draw on liquidity and PD arrays (the "narrative").**

Breadth: ICT lineage (LuxAlgo, FxCanli, TFlab), which is consistent with the DOL_PLAYBOOK inventory. Reliability: **M** (one lineage) with no published statistics. E-lab: `DRAW_LEARNER.md` measures which draws get hit, and `trend_1h_with` is the best confluence.

- **Traders say** ([LuxAlgo draw on liquidity](https://www.luxalgo.com/library/concept/draw-on-liquidity.md), [FxCanli](https://www.tradingview.com/script/pseOoULc-FxCanli-Range), [TFlab dealing range](https://www.metalsmine.com/thread/1347835-ict-trading-range-explained-tflab)):
  - Price moves from liquidity to liquidity: PDH/PDL, PWH/PWL, session highs and lows, equal highs/lows, and unfilled FVGs.
  - Buy in discount (below the dealing range's 50%) toward buy-side liquidity, in line with higher-timeframe order flow.
  - **Choosing between two draws:**
    - one working draw at a time;
    - the higher timeframe wins;
    - engineered equal highs/lows beat a single swing;
    - untapped beats probed;
    - the nearest compelling pool in line with higher-timeframe structure.
  - **ERL↔IRL alternation:** after external liquidity is purged, the next draw is the unfilled imbalance inside the range, and vice versa.
- **Fails when:**
  - A pool is partly taken, rejected short of, or blown through.
  - News reshuffles the map.
  - Confirmation bias.
  - Invalidation: a hard rejection short of the pool with opposing displacement; a sweep that stalls and reverses (the draw is complete); displacement through a significant opposing pool.
- **Mech** (from DOL_PLAYBOOK D7/D12 and agent research):
  - Candidates = untaken pools within [0.25, 1.5] × ADR20 of price.
  - Score = 2·weekly + 1·daily + 1·EQH/EQL + 1·untapped − 1·probed − distance/ADR20 + DRAW_LEARNER p(hit) (if available).
  - **Event overrides:**
    - `ERL_FAIL`: yesterday swept the 20-day high, PDH or PWH and closed back below → the draw is the nearest IRL below (bullish FVG CE or DR 50%).
    - `ERL_DISP`: closed beyond with CLV ≥ 0.7 → the next ERL out.
    - `IRL_TAP`: yesterday tagged the CE of an unfilled bullish daily FVG and closed above the zone in discount → the top-scored ERL above.
  - `draw_side` = the event side, else sign(best score above − best score below).
  - `two_sided` = the score gap is < 1 and price is within 0.45–0.55 of the 20-day DR.
- **Effect:**
  - Trades toward the primary draw: `GRADE+1`. Against it: `GRADE−1`.
  - `two_sided`: `TGT near` only and `GRADE−1` for everything. It is **not** a skip; the frequency guardrail applies.
  - Draw > 1.0 × ADR20 away: it is a multi-day draw, so `TGT near` intraday.

**B3. The previous day's high/low as the day's draw, and the "one side" rule.**

Breadth: ICT, TTrades, AMT ("one-timeframing out of the prior range"), plus three stats sources. Reliability: **E-pub + E-own**.

- **Traders say:**
  - Most days raid one side of yesterday's range.
  - Opening inside → expect one side.
  - Gapping outside → the gap side usually holds.
- **Evidence:**
  - [nqstats RTH breaks](https://nqstats.com/rth_breaks.html), on inside-open days:
    - Exactly one side is taken 74.0% of the time, both 8.3%, neither 17.7%.
    - Once one side is breached, the other follows only about **10%** of the time (122/1,210, agent calculation).
    - Gap-up opens never breach pRTH_L 88.1% of the time.
  - E-own CME day: PDH taken 55.3%, PDL 46.2%, both 13.1%, neither 11.6%.
  - [Midnight Confluence script](https://www.tradingview.com/script/m907Lt35/) (vendor backtest, NQ/ES/GC): when the 09:30 open and MO sit on the same side of the prior-RTH midline, the bias toward the nearer boundary is 2.4–3.5×. In conflict it is 1.6–2.9×. A "magnet" conflict (MO within 20% of the opposite boundary) flattens it to about 1.0× on NQ.
- **Mech:**
  - At 09:30: `posO` = (O930 − pRTH_L)/(pRTH_H − pRTH_L) and `posM` = the same for MO.
  - `IN_AGREE_UP` = both > 0.5 → the draw is pRTH_H. `IN_AGREE_DN` is the mirror.
  - `IN_CONFLICT` = they disagree. `MAGNET` = conflict with posM within 0.2 of the opposite boundary.
  - `first_side` = the first of pRTH_H/pRTH_L taken today (D9).
- **Effect:**
  - `IN_AGREE`: `GRADE+1` toward the agreed boundary.
  - `MAGNET`: `GRADE−1` for all and `TGT near`.
  - After `first_side`: **never target the other side** (`TGT near` = pRTH mid or IB mid for reversals). Continuation beyond the breached level gets `TGT near` (+0.25–0.5 ADR20).
  - Gap opens: see T6/T2.

**B4. Weekly profiles: which day makes the week's high or low.**

Breadth: ICT weekly profiles (one lineage) plus edgeful. Reliability: **X for unconditional weekday timing** (E-own ≈ the random-walk null). **S** for conditional use.

- **Traders say** ([LuxAlgo profiles](https://www.luxalgo.com/library/concept/session-and-weekly-profiles.md), [ICT Month 07 summary](https://videohighlight.com/v/wFjeUzJys7w), [edgeful weekday report](https://www.edgeful.com/blog/posts/high-and-low-by-weekday-report)):
  - **Classic Tuesday low:** Monday hovers above a higher-timeframe discount array, Tuesday drives into it for the low of the week, and Wednesday–Friday expand. The mirror is the Tuesday high.
  - Wednesday reversal; consolidation-then-Thursday reversal.
  - Seek-and-destroy: both sides raided, so stand aside.
  - LuxAlgo: these are "prototypes, not schedules" with "no dependable published hit rate".
- **Evidence:**
  - E-own #6 vs the arcsine null for a 5-day random walk (Mon 29.5 / Tue 14.1 / Wed 12.8 / Thu 14.1 / Fri 29.5%, agent calculation):
    - Our weekly **lows** fall Mon 32.2 / Tue 15.5 / Wed 13.1 / Thu 12.7 / Fri 26.5%.
    - Our weekly **highs** fall Mon 18.4 / Tue 14.3 / Wed 16.3 / Thu 14.7 / Fri 36.3%.
    - These sit **on the null**, tilted by NQ's upward drift.
  - "Up weeks make the low Mon/Tue 74%" is the mechanical consequence of knowing the week was up. It is useless unless you can predict the week.
- **Mech:**
  - `wk_bias` (B1 on weekly bars).
  - `wtd_low_swept` = from Tuesday on, a sweep (D9) of Monday's low or the week-to-date low between 02:00 and 11:00 that lands in a daily bullish FVG or in the lower half of the 20-day DR, followed by a 5m CISD (D11).
  - `seek_destroy` = both Monday's high and low taken by Wednesday's close.
- **Effect:**
  - `wk_bias` = +1 and `wtd_low_swept` on Tue/Wed: `GRADE+1` long. TP1 = Monday high or the week-to-date high, runner to PWH (hold no later than Thursday 16:00).
  - `seek_destroy`: `SIZE×0.5` until a clean B1 state appears.
  - **No weekday-only rule.**

**B5. Daily PO3 / AMD and the opens: midnight (MO), 18:00 (GO), 09:30.**

Breadth: ICT lineage, Quarterly Theory (Daye) and LuxAlgo statistics. Reliability: **E-own** shows the unconditional "buy below the open" is **X**. The conditional, reclaim-based version is **M**.

- **Traders say** ([MMXM OHLC PO3 summary](https://videohighlight.com/v/fgJArs1zGpo), [LuxAlgo midnight retracement](https://it.tradingview.com/script/2Q6FR6pq-Midnight-Open-Retracement-LuxAlgo/), [HTF PO3 script](https://www.tradingview.com/script/dWeooXlh-HTF-Power-of-Three-Pro/), Quarterly Theory script listings):
  - A bullish day opens, manipulates **below the open** (the Judas swing, often in London, into discount or a raid of the Asia low or PDL), then distributes up and closes near its high. So buy below the open, and only in bullish bias.
  - The "true day open" is the **midnight open**.
  - In Quarterly Theory the NY AM "true open" is **07:30**, and 06:00 starts the NY AM quarter.
- **Fails when:**
  - Open-drive days never revisit the open: about 26–37% of days never touch MO after 09:30 (LuxAlgo numbers).
  - The manipulation leg is the real move.
  - News resets the pattern.
  - Mondays are weaker.
  - The different opens disagree.
- **Evidence:**
  - LuxAlgo (NQ, 6 months): with the 09:30 open above MO, MO is touched later 74% of the time; with it below, 63%.
  - **E-own:**
    - Up days have the 18:00 open in the bottom quarter of the range 50% of the time and close in the top quarter 67%. Down days are the mirror at 55% / 50%. So the shape is common, but that is description, not prediction.
    - The side of MO at 10:30 predicts the side of the RTH close 76% of the time.
    - **Price below O930 at 10:30 → the RTH close finishes above O930 only 28.6% of the time.**
  - E-lab: `below_rth_open` −0.25R and `below_tso` −0.26R.
- **Mech:**
  - `manip_long` = B-bias (B1/B2) is +1 and, between 02:00 and 10:30:
    - a 5m low sweeps a named pool (Asia L, London L, PDL, week-to-date L) by ≥ 1 tick while price is below MO;
    - then, within 6 bars, a CISD (D11) or a close above the sweep bar's high;
    - **and then a 5m close back above MO** (or above O930 after 09:30): the reclaim.
  - `open_drive_kill` = by 10:30, price is ≥ MO + 0.5·ATRd without having traded below MO → cancel all below-open logic.
- **Effect:**
  - `manip_long` with a reclaim: `GRADE+1`, `TGT far` = the B1/B2 draw, `HOLD` if entered before 10:30.
  - A long below MO and O930 **without** a reclaim after 10:30: `GRADE−1` (T7).
  - `open_drive_kill`: at most one continuation entry at a 5m FVG, `TGT near`.

**B6. Higher-timeframe structure alignment (trade with the 1H/4H/daily order flow).**

Breadth: the broadest agreement in this file. It appears in ICT (HTF order flow), TTrades (weekly → daily → LTF), Al Brooks ("always in" direction), AMT (the other-timeframe trader controls the trend; one-time-framing) and every prop coach ("trade with the trend"). Reliability: **E-lab (weak)**: `trend_1h_with` +0.30R pooled, z 2.66, positive in 5 of 8 families, not significant after multiple testing; `trend_5m_with` +0.21R. It also cuts frequency.

- **Mech:**
  - `h1_trend` = the direction of the last 1H BOS (D10 on 1H bars, k=1).
  - `d_trend` = sign(the last daily close − the 20-day DR mid), confirmed by the last daily BOS.
  - `aligned_htf` = the trade direction equals `h1_trend`, and `d_trend` is not opposed.
- **Effect:**
  - `aligned_htf`: `GRADE+1`. Opposed: `GRADE−1` and `TGT near`.
  - **Not a SKIP.** As a filter it fails the 2/week constraint (CONFLUENCE_RESULTS).

## 2. Day-type reading (auction market theory: Dalton, Steidlmayer)

This section uses `ATRd`, the mean of the last 14 RTH true ranges excluding today. Thresholds are written as multiples of it:

- `e` = 0.05·ATRd. On NQ with an ATRd of about 350, that is about 17 pts.
- `m` = 0.10·ATRd.
- ADR20 can stand in for ATRd if only one daily volatility unit is wanted.

**T1. Open type, classified at 10:00 and finalized at 10:30.**

Breadth: AMT lineage (Dalton), plus ATAS, LuxAlgo, Crowstack and futures.io, all secondary. Reliability: **M**, plus **E-own** for the drive proxy.

- **Traders say** ([LuxAlgo open types](https://luxalgo.com/library/concept/open-types/), [ATAS open drive](https://atas.net/blog/open-drive/), [Crowstack ORR](https://crowstack.substack.com/p/five-easy-tapes-open-rejection-reverse); Dalton, *Mind Over Markets*):
  - **Open-Drive (OD).** Price drives from the first prints and does not trade back through the open. It is the most confident open, the open often becomes one extreme of the day, and you join it rather than fade it.
  - **Open-Test-Drive (OTD).** Price probes a known reference (prior high/low, value-area edge, ON H/L), finds no business there, then drives the other way. The probe extreme is the stop.
  - **Open-Rejection-Reverse (ORR).** The initial move is rejected and comes back through the open. Two-sided trade follows, with less conviction.
  - **Open-Auction (OA).** Price rotates around the open. Inside prior value this means balance. Outside the prior range, price must either be accepted out there or snap back to old value.
  - Conviction ranks OD > OTD > ORR > OA.
- **Fails when:**
  - A drive on thin volume stalls.
  - OTD and ORR are hard to tell apart early.
  - A 10:00 release flips the read.
  - An overnight inventory correction looks like a drive.
- **Evidence:**
  - No source publishes open-type statistics.
  - **E-own #12:** an OD proxy (8–9% of days on each side) later revisits the 09:30 open only 32–37% of the time, and the RTH session closes beyond the 10:00 close 56–61% of the time.
  - Linnsoft (ES, about 1,490 days): when the first 30-min period closed up, 90.9% of days later traded above the 30-min high; when it closed down, 85% later broke the 30-min low. This is a search snippet ([linnsoft](https://linnsoft.com/topic/open-period-breakout-statistics-time-day)).
- **Mech** (up side; mirror for down). Inputs since 09:30:
  - O = O930.
  - U = max(H) − O and D = O − min(L).
  - C = last close.
  - `Xo` = number of bars, from bar 3 onward, whose range contains O.
  - The `RVOL` window is 09:30–10:00, compared with its 20-session median.

  Rules, in precedence order:
  - `OD_up`: D ≤ e, C − O ≥ 0.20·ATRd, the OR30 close-location is ≥ 0.70, Xo = 0, and RVOL ≥ 1.0.
    - Strong OD also requires 5m one-time-framing (each low ≥ the prior low − 0.01·ATRd, at most 1 violation).
    - Early proxy at 09:35: bar-1 close-location ≥ 0.8 and bar-1 RVOL ≥ 1.5.
  - `OTD_up`: e < D ≤ 0.20·ATRd, with the probe low printed by the 09:50 bar.
    - The probe low must lie within 0.03·ATRd of {pRTH_L, pVAL, pVAH, pPOC, ONL, ONH}.
    - After that: C − O ≥ 0.15·ATRd, and no low ≤ O once a close above O + e has printed.
  - `ORR_up` (the initial down move is rejected): D ≥ m within bars 1–3, and a 5m close above O by 10:30.
    - Either C − O < 0.15·ATRd or price re-crosses O.
    - Tag it `ORR_into_value` if O was outside the prior VA and price re-entered it.
  - `OA`: none of the above, Xo ≥ 2 and \|C − O\| ≤ 0.07·ATRd.
    - Subtype by where O sits: inside the prior VA / inside the prior range / outside the prior range.
- **Effect:**

| open | grade, size | entry, stop | target, management | rule |
|---|---|---|---|---|
| OD | `GRADE+1`. `SIZE×1.25` only if O is outside the prior range and RVOL ≥ 1.2 | First pullback to rVWAP or the OR30 mid. Stop at O ∓ e: a trade back through the open kills the thesis. | `TGT far` (1.5–2 × IBR beyond the IB, or 0.8–1.0·ATRd from O). `HOLD`; trail under the prior 30-min period's low. | **`SKIP` every fade of an OD day.** |
| OTD | `GRADE+1` | Trade with the drive; stop beyond the probe extreme. | 1.0–1.5 × IBR extension. | If the probe extreme is retaken: exit and reclassify. |
| ORR | Continuation `GRADE−1`, `SIZE×0.5–0.75` | Responsive trades only. | `TGT near` (O, rVWAP, IB mid). `QUICK`. | `ORR_into_value` hands off to T2 (80% rule). |
| OA in value | — | No breakout entries until an accepted IB break (T3). Fade the IB and VA edges. | `TGT near` (rVWAP/POC). `QUICK`. | — |
| OA outside range | — | Wait. | Acceptance (6 straight 5m closes beyond the prior range) → continuation, `TGT far`. Two closes back inside → snap-back to pVAH/pVAL, then pPOC. | — |

**T2. Where the open sits vs prior value and range, and the 80% rule.**

Breadth: AMT lineage plus independent stats on prior-range location. Reliability: **E-pub** for the range-location rates; **S/X** for the "80%".

- **Traders say:**
  - Open inside the prior value area means balance: expect rotation and responsive trades.
  - Open outside value shows directional intent.
  - Open outside the prior range means price must either be accepted out there or snap back.
  - **80% rule:** open outside the prior VA, then trade back inside for two consecutive 30-min periods, and price traverses to the other side of the VA about 80% of the time. The rule is attributed to Dalton's *Profile Report* ([NexusFi 80% rule](https://nexusfi.com/a/concepts/80-percent-rule), snippet; [TV 80% backtest](https://it.tradingview.com/script/rsTzArCv-80-Rule-Backtest)).
- **Evidence:**
  - [nqstats RTH breaks](https://nqstats.com/rth_breaks.html) (NQ 2016–2025, n=2,488):
    - **Opens above pRTH_H (26.3%):** closes above it 69.9%, never breaches pRTH_L 88.1%.
    - **Opens below pRTH_L (14.6%):** closes below it 59.5%, never breaches pRTH_H 90.4%.
    - **Opens inside the range (59.1%):** breaks one side only 74.0%, both sides 8.3%, neither 17.7%.
  - **80% rule:** independent forum tests got about 62% (120 setups, 75 completed; a TradeStation test about 62%). Plan for about 60% at best.
- **Mech:**
  - `open_loc` ∈ {in_VA, in_range_out_VA, above_range, below_range}, computed at 09:30 with an e buffer, using pVAH/pVAL from P5.
  - `rule80_short` (O > pVAH; mirror for below):
    - Trigger: 9 consecutive 5m closes below pVAH, or two 30-min period closes below it. Only the first trigger counts, and it must come by 13:00.
    - Stop = max(pVAH + e, the high of the two periods).
    - T1 = pPOC, T2 = pVAL.
    - Skip when the open type is OD/OTD away from value, or when the VA width is < 1.5 × the stop.
- **Effect:**
  - `above_range`/`below_range`: trades that need the opposite pRTH extreme get `GRADE−1`; the opposite side holds about 88–90% of the time.
  - `in_range`: once one side of the prior range is taken, targets beyond the other side get `TGT near`, since both sides are taken only 8.3% of the time.
  - `rule80`: `SIZE×0.5–0.75`, `TGT near` = pPOC always. A runner to the far VA edge is allowed only on a balance-mode day (T4).

**T3. Initial balance (IB, 09:30–10:30).** A break is near-certain, so the information is in **which side, acceptance, and a double break**.

Breadth: AMT plus three independent stats sources. Reliability: **E-pub**.

- **Traders say:**
  - Most days break the IB.
  - A narrow IB raises trend-day odds; a wide IB means rotation.
  - After a double IB break, stand aside, or only fade back to the IB mid or VWAP.
  - Use 0.5×, 1× and 2× IB extensions as targets ([LuxAlgo IB](https://luxalgo.com/library/concept/initial-balance.md), [edgeful IB](https://www.edgeful.com/blog/posts/ib-by-rejection-deep-dive)).
- **Evidence:**
  - [nqstats IB breaks](https://nqstats.com/ib_breaks.html) (NQ, n=2,571):
    - By 16:00: either side breaks 96.1%, IB high 62.9%, IB low 54.9%, both about 21.7%.
    - **IB close above its mid:** the IB high breaks 82.3% of the time. **Close above mid and the IB low printed before the IB high:** 84.0%. Mirror: below mid 76.5%; below mid with the high first 78.0%.
  - Linnsoft ES ([linnsoft IB](https://linnsoft.com/tags/ib)):
    - 1,000 days: high side only 36.6%, low only 29.7%, both 31.6%, neither 2.1%.
    - 1,441 days: both 26.5%.
  - edgeful NQ, 6 months: a single break about 73–80%.
  - LuxAlgo: there are no dependable statistics for narrow vs wide IB; that idea is lore.
- **Mech:**
  - At 10:30: `ib_mid`, `ib_close_side` = sign(the 10:25 close − ib_mid), `ib_order` = whether the low or the high printed first.
  - `ib_bias` = +1 if close > mid and the low printed first, −1 for the mirror, otherwise sign(close − mid) with a weaker weight.
  - `ib_accept_up` = 3 consecutive 5m closes ≥ IBH + 0.1·IBR. `ib_fail_up` = a break that re-enters the IB within 3 bars.
  - `ib_double` = both IBH and IBL taken (D9).
- **Effect:**
  - Trades in `ib_bias` direction after 10:30: `GRADE+1`, TGT = IB extreme + 0.5–1.0 × IBR.
  - Counter-`ib_bias` breakout trades: `GRADE−1`.
  - `ib_fail` on one side: `GRADE+1` for reversals to the IB mid, or to the other side.
  - `ib_double`: no new breakout entries for the day (`SKIP` breakout type), only fades to the IB mid/rVWAP with `TGT near`.

**T4. Trend day vs balance day: the live day-type score.**

Breadth: AMT, Al Brooks ("trend from the open" vs trading-range days), ICT/prop lore ("trend days: don't fade"), and stats. Reliability: **M** for the score, **E-pub** for its components. E-lab: `trend_day_with` +0.20R on 3 of 5 beds; `trend_1h_with` is the best confluence at +0.30R pooled, but not significant after multiple testing. The CONT trend model only rescued Q4 2025 and was rejected.

- **Traders say** ([LuxAlgo day-type taxonomy](https://luxalgo.com/library/concept/day-type-taxonomy.md), [LuxAlgo one-time-framing](https://luxalgo.com/library/concept/one-timeframing.md); Dalton; Al Brooks webinar notes such as "50% of strong moves on the open fail and reverse"):
  - **Trend day:** a narrow IB, relentless one-sided extension, one-time-framing, price holding one side of VWAP, a close near the extreme, and an open near the other extreme.
  - **Normal / normal-variation:** a wide IB, with an extension of up to about 1 × IB.
  - **Neutral:** both IB sides extended. Neutral-center closes mid-range.
  - Trend days are a minority, under 10% per ATAS (unsourced), but they cause most of the losses from fading.
- **Mech** (score recomputed at every 5m close from 10:30; causal):

| input | points |
|---|---|
| O outside the prior range, in the drive direction | +2 |
| O outside the prior VA but inside the range | +1 |
| Open type | OD +2, OTD +1, ORR −1, OA-in-value −2 |
| IBR/ATRd in the bottom 30% of the trailing 60 days | +1 |
| IBR/ATRd in the top 30% | −1 |
| 30-min one-time-framing so far (each period's low ≥ the prior period's low, or the mirror) | +1 |
| No 5m close on the other side of rVWAP since 09:45 | +1 |
| `XV24` ≥ 4 | −1 |
| Gap ≥ 0.3·ATRd with the half-gap level untouched at 10:30 | +1 |
| Accepted IB break (T3) | +1 |
| IB break that failed within 3 bars | −2 |
| `ib_double` | sets the day to NEUTRAL |
| Day range ≥ 0.7 × ADR20 with the last close in the outer 20% of the range | +1 |

  - Mode: **TREND** if the score is ≥ 5, **NORMAL-VARIATION** if 2–4, **BALANCE** if ≤ 1.
  - Sign the score by direction: direction = sign(last close − O930).
- **Effect:**

| mode | entries | size | target | management |
|---|---|---|---|---|
| TREND | With-trend only. **`SKIP` counter-trend.** | `SIZE×1.0–1.25` | `TGT far` (2 × IBR beyond the IB edge, or hold to 15:50) | `HOLD`. No breakeven before +1R / TP1. Trail under 30-min lows. |
| NORMAL-VARIATION | First accepted IB break, or a pullback after it. | — | 1 × IBR beyond the edge, partial at 0.5 × IBR | Flat by 15:30. |
| BALANCE / NEUTRAL | No breakouts. Fade the IB/VA edges toward rVWAP or POC. | `SIZE×0.5–0.75` | `TGT near` | `QUICK` |

  - Keep only two hard rules from this section: never fade an OD or TREND day, and no breakouts after `ib_double`. Everything else is grade, size and target (frequency guardrail).

**T5. Inside days, NR4/NR7: compression → expansion.**

Breadth: Crabel and Raschke lineage, LuxAlgo, Bulkowski. Reliability: claims **S/E-pub-old**; **X on NQ 2021–2026 (E-own)**.

- **Traders say:** A narrow or inside day precedes expansion (Crabel's alternation principle). Bracket both sides the next day, or trade in the direction of the open ([LuxAlgo NR4/NR7](https://luxalgo.com/library/concept/nr4-nr7-narrow-range-bars.md), [Crabel S&C V.7:11](https://store.traders.com/-v07-c11-insided-pdf.html), [Bulkowski NR7](https://thepatternsite.com/nr7.html)).
- **Fails when:** The pattern does not give direction, first breaks often fail, and narrow bars cluster in dead tape and before holidays.
- **Evidence:**
  - Crabel, S&P 1982–87: the day after an inside day, trading in the direction of the open won 68% of the time. That sample is pre-electronic.
  - Bulkowski, NR7 on stocks: 46% break-even failure rate.
  - **E-own #10 (NQ, 1,289 days):**
    - After an inside day, the next range is 1.07 × ADR20 against a base of 1.03, and P(≥ 1.2 ADR) is 24.8% against 26.2%.
    - **After an NR7, the next range is 0.91 × ADR20.** Volatility clustering beats "alternation".
  - edgeful: when the open is inside the prior range, NQ touches the prior high or low on 88% of days.
- **Mech:** `inside_y` = Y.H ≤ P.H and Y.L ≥ P.L. `nr7_y` = Y.range is the minimum of the last 7.
- **Effect:**
  - **No grade or size change.** Do not adopt the +1 trend-score point some sources propose; our data contradict it.
  - Use the inside-day high and low as **near draws** (both sides get taken on about 44–47% of the next days, E-own #1 inside rows), with `TGT near`.

**T6. Gaps: gap-and-go vs gap-fill.**

Breadth: four or more independent sources with statistics (SPY 1993–2026, edgeful, nqstats, ours). Reliability: **E-pub + E-own**. E-lab: `gap_big` (≥ 0.25 ADR) +0.12R pooled.

- **Traders say:**
  - Fade small gaps that open inside the prior range, toward the half or full fill.
  - Go with large gaps that open beyond the prior range and drive.
  - Make the half-gap the primary target on NQ.
  - Spikes against the fade before the fill are common ([edgeful half vs full gaps](https://www.edgeful.com/blog/posts/half-gaps-vs-full-gaps), [thetrading.tools gap analysis](https://thetrading.tools/gap-analysis), [TV ES/NQ gap stats](https://www.tradingview.com/script/32pGGSWx-Gap-Fill-Probability-Statistics-ES-NQ/)).
- **Evidence:**
  - **E-own #11:** fill rates by size, set out in the Mech table below.
  - SPY 1993–2026 same-day fill:
    - Gaps of 0.1–0.25%: 78–80%.
    - 0.25–0.5%: 60–66%.
    - 0.5–1%: 43–46%.
    - Over 1%: 26–33%.
  - edgeful 6 months, NQ: full fill 51–55%, half fill 69–76%; ES full fill 63–64%.
  - nqstats: gap above pRTH_H closes above it 69.9% of the time.
- **Mech:**
  - At 09:30: `gap` = O930 − pRTH_C; `gA` = \|gap\| / ADR20; `HG` = pRTH_C + gap/2.
  - Gap classes, with E-own fill rates by 10:30 / by the close:

| class | condition | fills by 10:30 | fills by close |
|---|---|---|---|
| tiny | gA < 0.05 | 95% | 96% |
| small | 0.05–0.2 | 63–79% | 77–88% |
| medium | 0.2–0.35 | 37% | 55% |
| large | ≥ 0.35, or O beyond pRTH_H/pRTH_L | 10% | 33% |

- **Effect:**
  - **tiny/small:** treat pRTH_C as a near draw. A fade toward it in the first hour gets `GRADE+1`, `TGT near` = HG first, then pRTH_C. If the open type is OD away from pRTH_C, cancel the fade.
  - **medium:** wait for 10:30 acceptance or rejection (T2).
  - **large:** gap-and-go. **`SKIP` fades of the gap** until a 30-min close back inside the prior range. With-gap pullbacks that hold above O get `GRADE+1`, +1 on the T4 score, `TGT far`, `HOLD`.

**T7. Early direction persists: which side of the opens price is on by 10:30.**

Breadth: academic, stats sites, AMT, ICT ("trade from the correct side of the open"). Reliability: **E-pub + E-own**.

- **Traders say:**
  - ICT: in a bullish day, stay above the midnight open after the manipulation. Shorts only from premium above the open.
  - AMT: a conviction open holds one side of VWAP.
  - The first half hour predicts the last half hour ([Gao et al. 2018](https://alphaarchitect.com/2014/08/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/)).
- **Evidence:**
  - **E-own #7/#8:**
    - The side of MO at 10:30 matches the RTH close's side 76% of the time.
    - Below O930 at 10:30 → the RTH close finishes above O930 only 28.6% of the time. Above O930 at 10:30 → it finishes above 76%.
  - Linnsoft: a 30-min close direction is followed by a break of that side's 30-min extreme 85–91% of the time (ES).
  - nqstats IB, from T3.
  - E-lab: `below_rth_open` −0.25R and `below_tso` −0.26R. Buying below the open without context is a losing confluence.
- **Mech:** `side_mo` = sign(close − MO), `side_o930` = sign(close − O930), `side_vwap` = sign(close − rVWAP), all evaluated from the 10:25 bar close onward. `aligned` = all three agree.
- **Effect:**
  - After 10:30, a trade **with** an `aligned` side: `GRADE+1`.
  - A trade **against** both MO and O930: `GRADE−1`. It is acceptable only as a T3/T4 reversal with a sweep plus displacement.
  - Before 10:30 this heuristic does not apply. See B5 (PO3) for the pre-10:30 "manipulation below the open" logic.

## 3. Session templates (time of day)

**S1. The AM makes one extreme, the PM the other; the morning extreme usually forms by about 10:15.**

Breadth: three independent lineages (stats sites, Al Brooks, prop and ICT time-of-day lore). Reliability: **E-pub**.

- **Traders say:**
  - The first hour sets the high or the low.
  - The "10 AM reversal": the opening move stalls or reverses at about 09:50–10:10, often on 10:00 data.
  - Al Brooks's "18-bar rule": by the close of the 18th 5m bar (about 11:00), the day's high or low is in roughly 80–90% of the time ([Brooks forum](https://www.brookstradingcourse.com/support-forum/general-trading-discussion/18-bars-in-emini-is-it-same-the-in-all-markets-or-need-to-adjust/), [TV script](https://www.tradingview.com/script/3DkQZipV-Brooks-18-Bars-KintsugiTrading/)).
  - 10 AM reversal pages: [daytradingtoolkit](https://daytradingtoolkit.com/strategies/10-am-reversal-day-trading-strategy), [moneyshow](https://moneyshow.com/articles/daytraders-30678).
- **Fails when:** on trend days, which reverse at 10:00 maybe once every month or two (anecdotal), and when 10:00 data confirms the morning move.
- **Evidence:**
  - [nqstats noon curve](https://nqstats.com/noon_curve.html) (NQ, 08:00–16:00, n=2,479):
    - The high and low fall on opposite sides of noon on 72.8% of days. Both are in the AM on 21.8%, both in the PM on 5.4%.
    - The AM extreme forms at a mean of 10:12 (SD 72 min); the PM extreme at a mean of 14:04 (SD 88 min).
    - Q1 (08:00–10:00) sets the AM extreme 85% of the time.
    - If Q2 breaks only the Q1 high, the day is an AM-low + PM-high day 82% of the time. If Q2 breaks only the Q1 low, it is AM-high + PM-low 72%. Both or neither: a coin flip.
    - Caveat: the Q2 rates are conditioned on opposite-side days, so re-measure them unconditionally.
  - [Linnsoft](https://www.linnsoft.com/comment/1070) (ES, 1,000 days to 2010): the high of day falls in the first 30 min 24.6% of the time, the low 27%. Each 30-min period between 11:30 and 14:00 holds the high or low only about 3% of the time.
  - SPY lows tend to form earlier than highs ([script](https://tw.tradingview.com/script/J17hSoQd-Day-Extreme-Reversal-Signals/)): 37% of lows are in by 10:00, but only 18% of highs.
- **Mech:**
  - `q1_hi`, `q1_lo` are known at 10:00.
  - At 12:00, set `pm_bias`: +1 if 10:00–11:55 traded above q1_hi but not below q1_lo, −1 for the mirror, otherwise 0.
  - "10 AM reversal" trigger:
    - The \|09:55 close − O930\| move is ≥ 0.5× its 20-day median.
    - Bars from 09:50 to 10:25 sweep the OR30 extreme on the side of the move (D9 swept), followed by an MSS (D10).
    - Exclude it if the OR30 closed in its outer 10% **and** the 10:00 bar is a displacement in the same direction (a power-trend open).
    - On Tier-2 data days the 10:00 bar itself is never the signal bar.
- **Effect:**
  - Reversal at 09:50–10:25 after a sweep of ONH/ONL, PDH/PDL or the London H/L: `GRADE+1`, TGT near = OR30 mid, then the opposite OR30 extreme.
  - After 12:00 with `pm_bias` ≠ 0: `GRADE+1` for trades in the bias direction, `TGT far` (beyond the AM extreme), `HOLD` to 15:50. `GRADE−1` against it.
  - With `pm_bias` = 0: PM trades `TGT near`.
  - Asymmetry (single source, SPY): lows form earlier and hold more often than highs. So morning longs off a fresh low may `HOLD`, and morning shorts off a fresh high should get `TGT near`.

**S2. London pattern → the NY draw ("NY continues or reverses London"; the Judas swing).**

Breadth: ICT lineage plus independent stats. Reliability: **E-pub** (nqstats, single site) for the break rates; S for the Judas framing.

- **Traders say:**
  - On a bullish day, London runs below the Asian low (the Judas swing, measured against the midnight open) and NY expands higher. The mirror applies on bearish days.
  - Continuation days just extend; "seek and destroy" days take both sides, so stand aside.
  - Whether a day is reversal or continuation is often only certain afterwards ([LuxAlgo](https://www.luxalgo.com/library/concept/judas-swing.md), [LuxAlgo profiles](https://www.luxalgo.com/library/concept/session-and-weekly-profiles/), [TFlab](https://www.metalsmine.com/thread/1344653-ict-judas-swing-explained-tflab)).
- **Evidence:** [nqstats ALN](https://nqstats.com/aln_sessions.html), London pattern classified at 08:00:
  - **P3** (London took the Asia high only; 41% of days): NY breaks the London high 80.8%, the low 65.5%. If NY breaks the London low **first**, the chance of the London high drops to 51.2%.
  - **P4** (took the Asia low only; 30%): NY breaks the London low 75.0%. That drops to 46.2% if the London high breaks first.
  - **P1** (London engulfs Asia; 22%): about a coin flip, both sides broken 42.5%.
  - **P2** (Asia engulfs London; 7%): both broken 56%.
  - NY breaks neither London extreme on about 1% of days.
  - The London extreme survives NY on only 19–35% of days, so "London set the day's extreme" is the minority case.
- **Mech:**
  - Use the nqstats windows (Asia 20:00–01:55, London 02:00–07:55).
  - At 08:00, `aln` ∈ {P1, P2, P3, P4}.
  - Primary NY pool: London high for P3, London low for P4, none for P1/P2.
  - `aln_broken_against` = NY's first London break (at or after 08:00) is on the side opposite the primary pool.
- **Effect:**
  - P3/P4 with the primary pool untaken: trades toward it `GRADE+1`, `TGT far` = that pool.
  - Reversal trades whose target is beyond the primary pool's opposite side: `GRADE−1`.
  - `aln_broken_against` true: `TGT near` only, never the far London extreme.
  - Both London extremes traded through before 10:30: no more opening-template trades. Hand off to the IB/PM logic.
  - Judas variant: a short is A-grade only if the swept high is above both MO and O930, i.e. premium (mirror for longs).

**S3. ICT macros and the Silver Bullet.**

Breadth: one lineage. Reliability: **S**; no statistics exist. LuxAlgo itself calls the premise unverifiable.

- **Traders say:**
  - Algorithmic "macros" run from xx:50 to xx:10: 09:50–10:10, 10:50–11:10, 13:10–13:40 and 15:15–15:45. Price runs a nearby pool and/or rebalances an FVG within about 20 minutes ([LuxAlgo macros](https://www.luxalgo.com/library/concept/ict-macros/), [toodegrees script](https://it.tradingview.com/script/yYlyRmyz-ICT-Algorithmic-Macro-Tracker-Open-Source-by-toodegrees)).
  - Silver Bullet: from 10:00 to 11:00 (and 14:00 to 15:00), the first FVG after a liquidity sweep is entered on the retrace toward the nearest pool ([TV explainer](https://pl.tradingview.com/chart/EURUSD/jOkVQBxm-What-Is-the-ICT-Silver-Bullet-Strategy-and-How-Does-It-Work)).
- **Evidence:**
  - On NQ, after the first breach of the prior hour's high or low, price returns to the hour open 61.5% of the time (17,701 events, [nqstats hour stats](https://nqstats.com/hour_stats.html)).
  - E-lab: the `silver_bullet` lab model has no proven edge (CONFLUENCE_RESULTS beds).
- **Mech:** `in_macro` = the signal bar closes in (09:50, 10:10], (10:50, 11:10], (13:10, 13:40] or (15:15, 15:45]. `in_sb` = 10:05–10:55 or 14:05–14:55.
- **Effect:**
  - At most `GRADE+1`, and only for sweep → reclaim → MSS reversals that complete within 4 bars inside a macro.
  - Never `SKIP` for being outside a macro.
  - For in-hour sweep reversals, use the current hour's open as `TGT near` (61.5% revisit).
  - Validate against control windows (xx:20–xx:40) and drop the tag if it adds nothing.

**S4. Lunch chop (about 11:30–13:30).**

Breadth: four or more independent lineages (prop firms, AMT, ICT "lunch macro" avoidance, stats). Reliability: **E-pub** for the volume and range lull.

- **Traders say:** Volume and range dry up and breakouts fail, so stay out until 13:30/14:00. Exceptions are trend days and headline shocks ([NinjaTrader](https://www.ninjatrader.com/futures/blogs/best-time-of-day-to-trade-futures/), [LuxAlgo time-of-day](https://www.luxalgo.com/library/concept/intraday-time-of-day-effects/), [proptradingvibes](https://proptradingvibes.com/blog/best-time-to-trade-futures)).
- **Evidence:** [Linnsoft](https://www.linnsoft.com/comment/189) (ES, 2,000 days, 2009–2017):
  - 09:30–10:00 holds the day's largest 30-min range 39% of the time.
  - Each half hour from 11:30 to 14:00 holds it only 1–4% of the time, and the most volume only 0.3–1%.
- **Mech:** `in_lunch` = the signal bar closes 11:35–13:30. Trend exception (`lunch_ok`): by 11:30 the IB has extended ≥ 1.0 × IB range on one side and the other side is untouched.
- **Effect:**
  - `in_lunch` and not `lunch_ok`: `SKIP` new entries.
  - `lunch_ok`: allow only with-trend pullbacks to rVWAP or the broken IB extreme. `SIZE×0.5`, `TGT near`.
  - Trades open at 11:30 that are below +0.5R: `QUICK` (exit at the 11:45 close, or tighten to −0.3R).
  - Shock bar (vol ≥ 2.5 × tod_vol and rel_rng ≥ 2.5): wait 3 bars, then treat it as a news release (S6).

**S5. PM session: continuation, PM reversal, the last hour.**

Breadth: stats + ICT + prop lore. Reliability: **E-pub** that PM extremes are larger; S for the specific reversal windows.

- **Traders say:**
  - After lunch, the AM direction usually resumes to a new extreme.
  - ICT: the 13:10–13:40 macro or the 14:00–15:00 Silver Bullet sweeps the AM extreme and reverses.
  - 15:00–16:00 often trends. The ~15:50 MOC imbalances cause late spikes.
- **Evidence:**
  - nqstats: the median move from O800 to the PM high is +0.88% and to the PM low −1.05%. To the AM extreme it is only +0.31% / −0.36%, so the PM extreme is usually the bigger one, which fits continuation.
  - Academic intraday momentum ([Gao, Han, Li, Zhou 2018, JFE](https://alphaarchitect.com/2014/08/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/)): the first half hour (from the prior close) predicts the last half hour on SPY. The effect is stronger on volatile and news days. Out-of-sample R² is about 0.018, which is small.
  - Linnsoft: 15:30–16:00 has the most volume on 20% of days.
  - E-own #9: after 11:00, a further ≥ 0.25 ADR extension happens on only about 1/3 of days.
- **Mech:**
  - `pm_bias` from S1. If it is 0, fall back to the IB bias (T3).
  - PM reversal = bars 13:30–14:25 sweep the high or low of day (D9), then an MSS.
  - `am_move` = (close at 11:55 − O930) / ADR20.
- **Effect:**
  - `pm_bias` ≠ 0: with-bias pullbacks to rVWAP or an FVG `GRADE+1`, `TGT` = day extreme + 0.25 R20, `HOLD` to 15:50.
  - PM reversal against the bias: `SIZE×0.5`, `TGT near` (rVWAP or the 14:00 open), time exit 15:15.
  - No new entries after the 15:30 close. Flat by 15:55 (house rule).
  - `pm_bias` = 0 and \|am_move\| < 0.3: `GRADE−1` for every PM trade. These are coin-flip PMs.

**S6. News-day templates (08:30 CPI/NFP/PPI, 10:00 data, 14:00 FOMC).**

Breadth: five or more independent lineages (prop-firm blogs, futures.io/NexusFi, ICT, academic). Reliability: **E-pub** for the FOMC and volume facts; M for the waiting rules. E-lab: `news_day` / `cpi_nfp_day` hurt on both 2025 engine beds (−0.57R, −0.75R/−0.66R).

- **Traders say:**
  - **08:30:** Don't trade the release candle; wait 5–15 min. The first spike is often faded, but a strong pre-market displacement can carry into the open. Spreads widen and stops slip ([NexusFi NFP](https://nexusfi.com/a/market-structure/nonfarm-payrolls-futures-trading), [proptradingvibes news](https://proptradingvibes.com/blog/trading-during-news-events), [Tickblaze CPI](https://community.tickblaze.com/strategies/post/trading-news---cpi-nVYEC7Cq3j26VC3)).
  - **FOMC:** Mornings are dull. The 14:00 spike often reverses within 5–10 min. The 14:30 press conference makes the larger and more lasting move, so do nothing for the first 30 min. Many skip the afternoon entirely ([NexusFi FOMC](https://nexusfi.com/a/strategies/fomc-trading-futures), [PineConnector](https://www.pineconnector.com/blogs/pico-blog/how-to-trade-fomc-meetings)).
- **Evidence:**
  - Pre-FOMC drift: S&P +49 bp in the 24 h before the announcement, 1994–2011 ([Lucca & Moench, NY Fed SR512](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.html)). It largely **disappeared after 2015** ([Kurov, Wolfe & Gilbert](https://www.skidmore.edu/economics/documents/KurovWolfeGilbert-TheDisappearingPre-FOMC-Announce-Drift-200914.pdf)). Do not trade the drift.
  - E-mini volume drops before announcements (Lucca & Moench).
  - nqstats AM-TBR: touches at the 08:31 news bar revert to the 08:00 open by noon 76.7% of the time.
- **Mech:**
  - **Tier-1 08:30 day:** no entries before the 09:40 bar closes. `NR` = the 08:30–09:25 range; `D` = sign(close of the 08:55 bar − O830).
    - *Fade:* between 09:30 and 10:30, a sweep of the NR extreme in direction D, then a reclaim within 2 bars, then an MSS. Trade against D, TGT = NR mid, then the opposite NR extreme.
    - *Go:* the 08:30 bar has rel_rng ≥ 3 and, after 09:30, is accepted beyond the NR extreme in direction D. Enter on the first pullback to the NR edge, `TGT far` = 1 × R20, `HOLD`.
    - If NR ≥ 2× its normal size: `SIZE×0.5`, because the stops are wider (this protects the $1k DLL).
  - **FOMC day:**
    - Morning: `TGT` × 0.7, no continuation entries after 11:00.
    - No entries 13:00–14:40. Open trades go to breakeven or flat by 13:55.
    - From the 14:45 close: only a sweep–reclaim of the 14:00–14:40 range extremes, or acceptance plus displacement beyond it, with `SIZE×0.5` and flat by 15:50.
    - Default: `SKIP` the whole FOMC afternoon. It is only 8 days a year, and CONFLUENCE_RESULTS suggests no-FOMC as a risk rule.
  - **FOMC minutes 14:00:** no entries 13:55–14:15.
  - **Tier-2 10:00:** the 10:00 bar is never a signal bar. Wait for the 10:05 close. A 10:00-bar sweep of an OR30 extreme with the 10:05 bar closing back inside is a valid S1 trigger, `GRADE+1`.

**S7. Day-of-week.**

Breadth: ICT weekly profiles plus lore. Reliability: **S/E-own** for the weekly-extreme timing; there are no published hit rates for the ICT profiles ([LuxAlgo](https://www.luxalgo.com/library/concept/session-and-weekly-profiles/)).

- **Traders say:**
  - "Monday sets the range."
  - A bullish week's low forms Mon or Tue (the "classic Tuesday low"), then the market expands Wed–Fri. There are also the Wednesday reversal and the consolidation-then-Thursday-reversal templates.
  - Friday afternoons chop, and NFP Fridays are special.
- **Evidence:**
  - E-own #6 (the weekly low of up weeks is Mon/Tue 74%; the weekly high of down weeks is Mon/Tue 62%). Much of this is the arcsine law.
  - edgeful (6 months only): the average NQ NY range runs Mon 296 → Fri 366 pts, so Monday is about 20% below Thu/Fri ([edgeful](https://www.edgeful.com/blog/posts/nq-futures-trading)).
  - E-lab: `dow_wed` hurt on one bed, which is noise.
- **Mech:**
  - `wk_bias` = TTrades rule (B1) applied to weekly candles, computed Sunday 18:00.
  - `wk_low_in` = Wednesday onward, in a `wk_bias` = +1 week, the Mon/Tue low was a sweep (D9) of PWL or of a weekly pool, and it has not been traded through since. The mirror is `wk_high_in`.
- **Effect:**
  - Never `SKIP` a weekday; it removes 20% of opportunities.
  - `wk_low_in`: shorts targeting below the week's low `GRADE−1`; longs toward PWH `GRADE+1`.
  - Optional target scaling by a causal weekday factor: the trailing-252-day median RTH range for that weekday ÷ the overall median (roughly Mon 0.9 … Fri 1.1).
  - Friday after 13:30: `SIZE×0.5` (anecdotal).

## 4. When NOT to trade

Every source agrees on the principle: experienced traders mostly *wait*. Only N1 (extreme), N4 and N5 are hard skips. The others change grade or size, because of the 1–4 trades a week constraint.

**N1. Chop: overlapping bars, no displacement, low participation.**

- **Breadth:** about 6 independent sources (daytradingtoolkit, EliteTrader, two NexusFi threads, BabyPips, EnergyExch). **Reliability:** **M**, anecdotal.
- **Traders say:** price zigzags with no follow-through, usually late morning and midday. Pros sit out or cut size. "Chop" depends on the timeframe; if the noise is bigger than your stop, drop to MNQ. Sources: [daytradingtoolkit sit-out](https://daytradingtoolkit.com/beginners-guide/when-to-sit-out-not-trading), [chop](https://daytradingtoolkit.com/dictionary/chop), [NexusFi](https://nexusfi.com/showthread.php?p=546120), [BabyPips](https://forums.babypips.com/t/good-bad-day-trading-conditions/34986).
- **Mech:** `chop` is true when at least 2 of these hold:
  - `ER12` ≤ 0.25
  - `OVL12` ≥ 0.60, the average share of each bar's range that overlaps the previous bar
  - range of the last 12 bars ≤ 0.20 × ADR20
  - `relVol6` ≤ 0.70, the range of the last 6 bars ÷ the sum of the `tod_rng` medians for those slots

  `chop_hard` = Choppiness Index(14) ≥ 61.8 and relVol6 ≤ 0.60. `chop_day` = 3 or more 5m swing reversals between 09:30 and 10:00, each followed by less than 0.5 × ATR5.

  Re-fit the cutoffs to the 70th/30th percentiles of our own history.
- **Effect:**
  - `chop`: `GRADE−1`, require the displacement leg to be ≥ 2 × ATR5, `QUICK` (single target).
  - `chop_hard`: `SKIP`.
  - `chop_day`: at most 1 trade, `SIZE×0.5`.

**N2. No clear draw, or not enough room (price in the middle).**

- **Breadth:** ICT lineage, plus prop and grading-checklist blogs (curvedtrading), plus AMT ("don't trade the middle of balance"). **Reliability:** **M**.
- **Mech:** `room` = distance to the first opposing obstacle ÷ planned risk. Obstacles are:
  - untaken opposing pools (D7)
  - unfilled opposing 5m FVGs ≥ 0.3 × ATR5
  - unfilled 1H FVGs
  - confirmed swings
  - pRTH mid / EQ when the entry is in the other half

  Also let `mid_range` = entry within ±10% of the prior-day EQ, or of the 20-day DR mid, and no B1/B2 draw.
- **Effect:**

  | condition | effect |
  |---|---|
  | `room` < 1 | `SKIP` |
  | 1 ≤ `room` < 2 | `GRADE−1`; single target 2 ticks before the obstacle |
  | `room` ≥ 3 | `GRADE+1` |
  | `mid_range` | `GRADE−1` |

  E-lab: `near_eq_pdr` was tested and is not a strong effect, so keep it a grade, not a veto.

**N3. The draw is already hit, or the ADR is used up.**

- **Breadth:** about 4 indicator vendors (TV ADR exhaustion, LuxAlgo ADR), plus ICT ("don't chase after the draw is taken"). **Reliability:** **X for the ADR version** (E-own #9); **M** for the draw version.
- **Traders say:** <50% of ADR used is early; 50–85% is active; >85% is near exhaustion; >100% calls for extreme caution. Counterpoint: blowing through the ADR can mean a trend day. Sources: [LuxAlgo ADR](https://www.luxalgo.com/library/indicator/average-daily-range/), [TV ADR probability map](https://ar.tradingview.com/script/rH2pZylf-Daily-Range-Exhaustion-ADR-Probability-Map/).
- **Evidence (E-own #9, NQ):** after 11:00, the day extends beyond its extremes by ≥ 0.25 ADR on 33–36% of days whatever the range used. When > 1.3 ADR is used it is **51%**. ADR exhaustion as a skip is not supported. Vendors offer no backtest.
- **Mech:** `draw_hit` = the primary draw from B1/B2/B3/S2 was taken (D9) before the signal bar. `adr_used` = (running CME-day H − L) / ADR20.
- **Effect:**
  - `draw_hit` and trade continues in the same direction: `GRADE−1` unless the next pool is within 1 × ADR20; `TGT near`; `QUICK`.
  - `draw_hit` and reversal trade: allowed. The swept draw is the stop anchor, and S1/T3 apply.
  - `adr_used` alone: **no effect**. Optional: use `adr_used` > 1.3 as a T4 trend-day point.

**N4. News windows and event days.**

See S6. Hard skips:
- Tier-1 08:30 days: before the 09:40 close.
- FOMC: 13:00–14:40, by default the whole afternoon.
- Minutes: 13:55–14:15.
- The 10:00 bar on Tier-2 days.
- The prop firm's news blackout, if it has one. Firm rules conflict, so check MFFU's current rule.

**N5. The first minutes after the 09:30 open.**

- **Breadth:** 5 or more (EliteTrader, NexusFi OR, TradingView education, Kilo), plus Al Brooks: "50% of strong moves on the open fail". **Reliability:** **M**.
- **E-lab:** a first-45-minute penalty is already adopted as a sizing tweak (discovery scan).
- An ORB paper's gross edge vanished after costs in independent replications (agent finding via eltraderfinanciado and an MQL5 replication; snippets).
- **Mech/Effect:** `SKIP` signal bars that close at or before 09:45. Add the 09:30–09:44 high and low to the pool inventory. Test 10:00 as an alternative start.

**N6. Holidays, half-days, low participation.**

- **Breadth:** 3 or more. **Reliability:** **M**.
- **Mech/Effect:**
  - `SKIP` CME early-close sessions and the day after Thanksgiving (calendar file).
  - `rvol30` = 09:30–10:00 volume ÷ the 20-session median for that window. If `rvol30` < 0.6: `SIZE×0.5` and at most 1 trade.
  - Friday after 12:00–13:30: `SIZE×0.5` (anecdotal).

**N7. After losses, or after a win.**

See R2 and R3.

## 5. What makes an A+ setup vs B/C

**The lab warning first.** The five-year test found that the engine's A–D grade **does not rank trades** (FIVE_YEAR_REPORT). Any scorecard below must show A+ > A > B **out of sample** before it drives size. Until then, use it to choose targets and management, and to break ties, not to size.

**G1. Sweep of meaningful liquidity INTO a higher-timeframe PD array.**

- **Breadth:** ICT, TTrades (fractal model: HTF candle sweeps the prior candle's extreme and closes back inside, then an LTF CISD), SMC vendors, and AMT's "failed auction / excess". 6 or more sources, but mostly one lineage plus AMT. **Reliability:** **M**; no audited stats.
- **Sources:** [TTrades fractal model script](https://cn.tradingview.com/script/hXvtdarw-TTrades-Fractal-Model), [ICT sweep+FVG script](https://kr.tradingview.com/script/MJtwipsw-ICT-Sweep-FVG-Entry-v6-Pro-Pack), [eltraderfinanciado killzones](https://www.eltraderfinanciado.com/ar/blog/killzones-ict).
- **Mech:** sweep (D9) of a pool within the 6 bars before the displacement.
  - +2 if the pool is PDH/PDL, PWH/PWL or ONH/ONL.
  - +1 if Asia/London/EQH/EQL/OR.
  - +1 more if the sweep extreme sits inside an unfilled 1H FVG, or within 0.25 × ATR5 of a 1H swing, or in HTF discount/premium per D12.
- **Effect:** no sweep at all → **`GRADE−1`** for reversals. Continuations are exempt; they use the T4 logic. Score 3 or more → A+ candidate.

**G2. Displacement quality.**

- **Breadth:** 5 or more (LuxAlgo, Backtrex, TV displacement scripts, ICT, Brooks "strong trend bars"). **Reliability:** **M**.
- **Traders say:** bodies clearly larger than recent bars, small wicks, consecutive closes, leaves an FVG, breaks the last opposing swing. A slow drift through a level doesn't count. Sources: [LuxAlgo displacement](https://www.luxalgo.com/library/concept/displacement/), [Backtrex](https://backtrex.com/en/blog/ict-displacement-candle-market-concept).
- **Mech:** four checks.
  - (a) The leg's best body/range ≥ 0.6.
  - (b) The leg spans ≥ 1.5 × ATR5, or rel_rng ≥ 1.5 per P7.
  - (c) It leaves an FVG ≥ 0.2 × ATR5.
  - (d) BOS (D10) or CISD (D11).
- **Effect:**

  | result | effect |
  |---|---|
  | all 4 | `GRADE+1` |
  | 3 | 0 |
  | ≤ 2 | `GRADE−1` |
  | 3 or more overlapping bars in the leg | `GRADE−1` (choppy displacement) |

**G3. SMT divergence (NQ vs ES).**

- **Breadth:** ICT lineage only. **Reliability:** **S/E-lab**. `nq_rs_with` (long the stronger index since the open) scored +0.17R pooled, positive in 6 of 8 families, not significant.
- **Mech:** on the NQ sweep bar, check whether ES swept its matching pool within ±2 bars. `smt` = ES failed to sweep. Also `rs_with` = the NQ/ES return since O930 favours the trade direction. Needs `data/ES_5m.csv`, which starts 2025-04-13.
- **Effect:** `smt` or `rs_with`: `GRADE+1`. Missing ES data: 0. Never penalize the absence of SMT.

**G4. Time-of-day alignment (killzones).**

- **Breadth:** ICT plus prop plus stats (S1, S4). **Reliability:** **E-pub** for "AM good, lunch bad"; **S** for the exact ICT windows.
- **Mech:** +1 if the signal closes 09:45–11:00 or 13:30–15:00. −1 for 11:30–13:30. Lunch is already a skip in S4 unless `lunch_ok`. `SKIP` after 15:30.

**G5. Clean path / R:R.** Use N2 `room`. "A+ needs at least 2R of room" is near-universal in grading checklists (curvedtrading, Pepperstone, ICT).

**G6. Bias agreement and entry location.**

- **Breadth:** universal. **Reliability:** **M**. E-own: location versus the opens matters (T7/B5).
- **Mech:**
  - With B1/B2 draw and B6 HTF: +1 each.
  - Long in the OTE (0.62–0.79 retracement of the leg) or below the D12 EQ: +1.
  - Long above the dealing-range EQ: −1. Shorts are the mirror.
  - Against the bias: it needs G2 = 4/4 and a G1 sweep of PDH/PDL/ON.

**G7. Explicit downgrades (what experienced traders refuse).**

| condition | effect | where |
|---|---|---|
| counter-trend on a TREND day | `SKIP` | T4 |
| entry at equilibrium / mid-range | −1 | N2 |
| continuation after the draw is hit | −1 | N3 |
| choppy displacement | −1 | G2 |
| lunch | `SKIP` | S4 |
| after 15:30 | `SKIP` | — |
| news within the window | `SKIP` | S6 |
| fading a level tested 3 or more times in the last 48 bars (extreme within 0.1 × ATR5) | −1 | — |
| targeting that level | +1 | — |
| stop wider than 0.35 × ADR20 | `SIZE` shrinks, so contracts round down; skip if 0 MNQ | — |

**G8. Scorecard (a starting point to validate, not to trust).**

- **Points:**
  - G1: 0–3
  - G2: −1 to +1
  - G3: 0–1
  - G4: −1 to +1
  - room: −1 to +1
  - G6: −1 to +2
  - T4/T7 alignment: −1 to +1
  - minus 1 each for `chop`, `two_sided`, `draw_hit` continuation, and a low-participation day
- **Grade by share of the maximum:** A+ ≥ 80%, A 60–79%, B 40–59%, C < 40%. C is a skip only if frequency allows.
- **Validation:**
  - Calibrate the cutoffs so at least 90% of weeks still have one or more trades.
  - **Require OOS monotonicity A+ > A > B on every period**, or else size flat.
- **Sources:** [curvedtrading grading](https://curvedtrading.com/articles/en/trading/how-to-grade-your-trading-setups/), [Pepperstone](https://pepperstone.com/ar/market-analysis/trading-guides/high-probability-trade-setups), [daytradingtoolkit](https://daytradingtoolkit.com/beginners-guide/when-to-sit-out-not-trading).

## 6. Trade management

DOL_PLAYBOOK §5 (MGMT-1…7) already specifies the mechanics. This section adds *when a trader chooses which profile*. House history: R-based partials, trailing stops, BE at 0.5R, profit locks and the IFVG-failure exit all lost. `giveback` won and is adopted.

**M1. Runner vs early profit depends on the day type and the draw.**

- **Breadth:** ICT ("partials at internal liquidity, runner to external"), AMT (hold on trend days, take quick profits on balance days), prop coaches. **Reliability:** **M**.
- **Mech:** `mgmt_profile` = HOLD if all of:
  - T4 = TREND, or (`pm_bias` agrees and the time is before 15:00)
  - the draw distance is ≥ 2R
  - G8 grade ≥ A

  Otherwise `mgmt_profile` = QUICK.
  - HOLD: TP1 = 50% at the first internal pool ≥ 1R (DOL-based, not R-based). The runner goes to the draw minus 2 ticks.
  - QUICK: 100% at the first pool, or at 1.5–2R.
  - A morning runner is closed by 11:30 unless the target is within 0.5 × ATR5, or `lunch_ok` holds.
- **Effect:** `HOLD` / `QUICK` as defined. Test this against the current exits on all periods; it changes exits only.

**M2. Failure to continue (momentum reading).**

- **Breadth:** 5 or more: EliteTrader time stops, Elder via TV, Kilo, TradesViz, LuxAlgo non-price exits, and ICT ("if it doesn't move away from the FVG quickly, it's wrong"). **Reliability:** **M**.
- **Sources:** [EliteTrader time stops](https://www.elitetrader.com/et/threads/time-stops-for-intraday-trades.58721/post-896419), [Elder time stops](https://il.tradingview.com/chart/EURUSD/JsH2RCAg-Trade-Management-Using-Time-Stops), [LuxAlgo non-price exits](https://www.luxalgo.com/library/concept/non-price-exits.md).
- **Mech:**
  - (a) Time stop: if MFE is still < +0.5R after K bars, exit. K = the 80th percentile of the bars winners needed to reach +0.5R in our backtest; start at K = 3–6.
  - (b) A 5m close back beyond the entry FVG's far edge, or 2 closes beyond its CE: exit.
  - (c) An opposing displacement candle (D2) before TP1: exit, or move the stop to that candle's extreme, whichever is tighter.
  - (d) Stall: 3 bars within 0.25 × ATR5 of the target without a touch. Exit the runner.
  - (e) `giveback` (adopted): reached +0.5R then closed below entry. Exit.
- **Effect:** `QUICK` exits. Each sign is logged counterfactually, as engine `_exit_signals` already does.

**M3. Moving to breakeven: when, and what it costs.**

- **Breadth:** 7 or more. Most use +1R; edgeful uses halfway to TP1. Everyone warns that "too early" kills winners. **Reliability:** **E-pub (thin)** plus **E-lab**.
- **Evidence:**
  - traderpeter: 265 trades, BE at +1R with a 4R target. 63% of the trades that reached +1R came back to entry ([traderpeter](https://traderpeter.substack.com/p/there-might-be-more-potential-in)).
  - ATAS cites Quantified Strategies: early BE cuts long-run profit ([ATAS](https://atas.net/blog/break-even-in-trading/)).
  - E-lab: BE at 0.5R **lost** on the 4-period total.
- **Rule of thumb (agent derivation):** a BE move at +1R loses money if more than 1/(T+1) of the trades it stops would have reached a target of T R. That is 20% at T = 4 and 33% at T = 2.
- **Mech/Effect:**
  - No BE before TP1 fills. After TP1, the runner's stop goes to entry + fees + 1 tick.
  - HOLD profile on TREND days: no BE before +1R, and only after a new 5m swing forms beyond entry.
  - Choose by simulated eval-pass probability, not expectancy alone. BE trades EV for variance, which can matter against a $2k MLL.

**M4. Scaling in and out.**

- **Breadth:** 2–3. **Reliability:** **S**.
- **Evidence:** traderpeter's "add at +1R with the stop at the original entry" added about 69R in one sample.
- **Mech/Effect:** scale-out is per M1. Scale-in: **off during the evaluation**. Later, A+ only: at +1R or more, a new with-trend FVG forms, add 1 unit, and move the original stop to entry so the worst case stays ≤ 1R.

## 7. Risk and psychology

**R1. Size by setup quality, not by the last result.**

- **Breadth:** 4 or more (curvedtrading, edgeful tiers, daytradingtoolkit, Bellafiore's "PlayBook" idea of sizing up your best setups, from recall). **Reliability:** **M**. E-lab: grade does not rank trades yet, and "grade_sizing off" was a weak candidate.
- **Mech:** size = base × grade × streak × conditions.
  - grade multiplier: A+ 1.0, A 0.75, B 0.5, **only after G8 passes the monotonicity test, else 1.0**
  - streak multiplier: 0.75 after 2 straight losses, 0.5 after 3 or more, reset after a win of +0.5R or more
  - conditions multiplier: 0.5 if 2 or more of {`chop_day`, rvol30 < 0.6, FOMC day, `seek_destroy`}

  Never above 1.0× after a win during the eval. Round down to whole MNQ.

**R2. Daily stop: 2 losses or a dollar cap; a max number of trades.**

- **Breadth:** 7 or more (proptraderedge, edgeful, TSB, CrossTrade, daytradingtoolkit, LuxAlgo, Topstep coaching). The common rule is to stop after 2–3 losses. **Reliability:** **M**, plus E-own #13.
- **Sources:** [edgeful 9 rules](https://www.edgeful.com/blog/posts/futures-risk-management-9-rules-prevent-blown-accounts), [TSB](https://traderssecondbrain.com/guides/when-to-stop-trading-after-losses), [CrossTrade](https://crosstrade.io/learn/risk-management/daily-loss-limits).
- **Evidence (E-own #13):** 2nd trades of the day, which come only after a loss, averaged −0.022R vs +0.038R for first trades (n=221). That is not significant, but it points the same way. Streaks across trades show no effect, so the rule is **variance control, not edge**.
- **Math:** at a 45% win rate, 3 straight losses happen about 17% of the time. The expected longest losing streak in 150 trades is about 7.
- **Mech:**
  - `SKIP` all further entries after 2 losses, or when the day's P&L ≤ −$600. That keeps a slippage cushion under MFFU's $1,000 soft DLL.
  - Max 2 entries a day; the engine already caps this.
  - If the week reaches −$1,000, no new entries that week.

**R3. Stop after a good win ("one and done").**

- **Breadth:** 4: Topstep's official Personal Daily Profit Target tool, edgeful's "1 trade/day", trader lore on overconfidence. **Reliability:** **M**. E-own: the engine already stops after a win; 2nd trades exist only after losses.
- **Mech:** if the first closed trade is ≥ +1R, stop for the day. Optional exception: one A+ before 11:00 at `SIZE×0.5`, stopping if the day's P&L falls back to 50% of the first win. Also stop at the consistency cap (R5) if the plan has one.

**R4. Evaluation drawdown: size from the buffer, not the account.**

- **Breadth:** 8 or more (NexusFi sizing and risk rules, Tradovate prop blog, proptradingvibes, TradingFunder, TV prop guide, JPTradingCapital, EliteTrader). **Reliability:** **M** plus an agent simulation.
- **Sources:** [NexusFi sizing](https://nexusfi.com/a/prop-firms/funded-account-position-sizing), [Tradovate risk](https://prop.tradovate.com/blogs/how-to-manage-risk-in-prop-trading), [TradingFunder trailing DD](https://tradingfunder.com/how-to/manage-trailing-drawdown/).
- **Traders say:** "1–2% of the account" means $500–1,000 on 50K, which is 25–50% of a $2k MLL. That is far too much. Protect the buffer early, because the trailing MLL ratchets up.
- **Mech:** base risk = clamp(10% of buffer until the MLL locks or the account is up $1k, then 15%; between $100 and $400). Buffer = balance − EOD MLL floor. Contracts = risk ÷ (stop pts × $2), floored. If that gives 0, `SKIP`.
- **Simulated pass odds (agent; assumes +0.3R mean, 1.4R SD, $2k buffer, $3k target, no DLL effects, so it is an upper bound):**

  | risk per trade (% of buffer) | pass probability | trades needed |
  |---|---|---|
  | 10% | ≈ 95% | ≈ 46 |
  | 15% | ≈ 87% | ≈ 26 |
  | 20% | ≈ 80% | ≈ 17 |

  Re-run with the bot's real numbers. The five-year mean is only about +0.02R.

**R5. Consistency rules.**

- **Breadth:** firm-specific. Topstep: best day < 50% of the total ([Topstep help](https://intercom.help/topstep-llc/en/articles/8284208)). Apex: 30–50% at payout. MFFU: sources conflict ([QuantVPS MFF](https://www.quantvps.com/blog/my-funded-futures-consistency)). Our memory note says MFFU Builder has **no consistency rule in the eval**, and the sim-funded rule is disputed.
- **Mech:** `daily_cap` = firm ratio × profit target − base risk, only if the plan has the rule. When it is reached: flatten and stop.

**R6. Psychology, translated for a bot.**

- **Breadth:** 4 or more (Steenbarger's 64-trader coping study via [Zerodha Varsity](https://zerodha.com/varsity/chapter/coping-skillfully-to-achieve-success/), prop coaches: no revenge trades, no overconfidence after a win).
- **Mech:**
  - R1–R5 *are* the bot's psychology.
  - The operator must not change size or override intraday.
  - Log every manual override and review them weekly.
  - Never change parameters during a drawdown without a re-test on all periods (house protocol).

## 8. Putting it together: the trader's day as a state machine (for `engine/narrative.py`)

An experienced trader does not score every bar the same way. They form a **story** before the open, revise it at fixed checkpoints, and judge each setup against the story. Mechanically, that means four parts:

1. state that updates on a schedule;
2. a short veto list;
3. additive grade adjustments weighted by evidence;
4. a management profile.

### 8.1 Checkpoints (everything is computed on the close of the named bar)

| time (ET) | compute | heuristics |
|---|---|---|
| 18:00 (new CME day) | `b1_state`/`b1_target` (daily) and `wk_bias` (Sunday); pool inventory, primary draw, `draw_side`, `two_sided`; `h1_trend`/`d_trend`; T5 flags (as levels only); news tier for the day; holiday flag | B1, B2, B4, B6, T5, P8, N6 |
| 00:00 | `MO` | B5, T7 |
| 08:00 | `aln` pattern and the NY primary pool; `O800` | S2, S1 |
| 08:30 (news days) | `NR` tracking; news lock until 09:45 | S6 |
| 09:30 | `posO`/`posM` agreement, `open_loc`, `gap_class` (`HG`, pRTH_C as draw) | B3, T2, T6 |
| 09:30–09:45 | no entries; record the 09:30–09:44 high/low as pools | N5 |
| 10:00 | provisional `open_type`; OR30; `q1_hi`/`q1_lo` | T1, S1 |
| 09:50–10:25 | 10 AM reversal trigger window | S1, S3 |
| 10:30 | final `open_type`; `ib_bias`/`ib_order`; first `trend_score`/`day_mode`; `side_mo`/`side_o930`/`side_vwap`; `open_drive_kill` | T1, T3, T4, T7, B5 |
| each 5m close | pools taken (`first_side`, `draw_hit`); `ib_accept`/`ib_fail`/`ib_double`; `trend_score`; `chop` flags; `room`; risk governor | B3, N3, T3, T4, N1, N2, R2–R5 |
| 11:35–13:30 | lunch lock unless `lunch_ok` | S4 |
| 12:00 | `pm_bias` | S1, S5 |
| 13:00–14:40 (FOMC) | lock | S6 |
| 15:30 / 15:55 | no new entries / flat | S5 |

### 8.2 Order of evaluation for a candidate signal

1. **Risk governor.** R2 (2 losses or −$600), R3 (+1R win → done), R5 cap, R4 (if size rounds to 0 MNQ, skip).
2. **Time and news vetoes:**
   - S6 windows;
   - S4 lunch (unless `lunch_ok`);
   - N5 (before 09:45);
   - after 15:30;
   - N6 holiday / early close.
3. **Day-type vetoes:**
   - fading an OD day (T1);
   - counter-trend on a TREND day (T4);
   - breakout entries after `ib_double` (T3);
   - fading a large gap before a 30-min close back inside (T6).
4. **Structure vetoes:** `room` < 1 (N2); `chop_hard` (N1).
5. **Grade.** Start from the G8 scorecard. Add the context adjustments from B1–B6, T1–T7, S1–S7 and N1–N3. **Weight each adjustment by its evidence:**

   | evidence class | weight |
   |---|---|
   | E-pub / E-own | 1.0 |
   | M | 0.5 |
   | S | 0.25 |
   | X | 0 |

   Clamp the result to [−3, +3].
6. **Size.** R1 × R4.
7. **Target and management.**
   - `target_mode` = far (the primary draw) only if `mgmt_profile` = HOLD (M1) and `room` ≥ 2. Otherwise near (the first pool, or HG, VWAP, POC or the IB mid by day mode).
   - Exits: M2 signals plus `giveback`.
   - Breakeven policy: M3.
8. **Log everything.** Log every narrative field with every candidate and every taken trade, so that `engine/discovery.py` can re-test each heuristic on *taken* trades over all periods. This is the house lesson: candidate lift is not taken-trade lift.

**When context conflicts** (for example B1 bullish but S2 = P4 bearish):

- Sum the weighted adjustments. Do not vote.
- If the net is ≤ 0 for the trade direction, use `TGT near` and `QUICK`.
- Seasoned traders say "two-sided means small and quick". The bot should not freeze, because of the frequency guardrail.

### 8.3 Suggested output object

```python
@dataclass
class Narrative:
    t: int                      # close time of the last closed 5m bar (unix)
    phase: str                  # 'ON' | 'PRE' | 'OPEN' | 'AM' | 'LUNCH' | 'PM' | 'CLOSE'
    b1_state: str; b1_target: float | None; b1_live: bool          # B1
    wk_bias: int                                                     # B1 weekly
    draw_side: int; primary_draw: dict | None; two_sided: bool; draw_hit: bool  # B2/B3/N3
    first_side: str | None; open_agree: str | None                  # B3 ('IN_AGREE_UP', 'MAGNET', ...)
    aln: str | None; aln_broken_against: bool                       # S2
    open_loc: str | None; gap_class: str | None; open_type: str | None  # T2/T6/T1
    ib_bias: int; ib_double: bool; trend_score: int; day_mode: str; day_dir: int  # T3/T4
    side_mo: int; side_o930: int; side_vwap: int                    # T7
    pm_bias: int                                                     # S1/S5
    news_tier: int; news_lock: bool; lunch_lock: bool                # S6/S4
    chop: bool; chop_hard: bool; chop_day: bool                      # N1
    vetoes: list[str]           # names of active vetoes for the candidate
    grade_adj: dict[str, float] # heuristic id -> weighted adjustment
    size_mult: float; target_mode: str; mgmt_profile: str            # R1/R4, M1
    story: str                  # one line for the dashboard, e.g.
    # "CONT_UP -> PDH 21450 untaken | P3 London | OD up, TREND 6 | above MO/O930/VWAP | longs only, hold runner"
```

### 8.4 Where sources disagree, and what we picked

| topic | claim | data | pick |
|---|---|---|---|
| ADR exhaustion | Vendors: skip or reverse above 85–100% ADR. | E-own #9: no shrinkage; more extension above 1.3 ADR. | No ADR veto. `draw_hit` drives targets. |
| Compression → expansion | Crabel/Raschke. | E-own #10: NR7 → smaller next day. | Levels only, no grade. |
| Weekly profiles | "Tuesday low of week." | E-own #6 ≈ arcsine null. | Conditional sweep rule only (B4). |
| Buy below the open | ICT PO3. | E-own #8, E-lab: backwards without a reclaim. | Only with sweep + CISD + reclaim (B5). |
| TTrades bias | Read as day direction. | Next-day close ≈ 50/50, draw +25 pts. | Use as **draw/target**, not direction (B1). |
| 80% rule | 80%. | Forum tests about 62%. | Near target (POC) first (T2). |
| Size by grade | Universal. | Five-year: grade does not rank. | Flat size until OOS monotone (R1/G8). |
| Day-of-week skips | Mon/Fri lore. | Thin data; skipping costs about 20% of frequency. | No weekday veto (S7). |
| ICT macros / Silver Bullet | "Algorithmic." | No stats; LuxAlgo calls it unverifiable. | At most +1 with control-window validation (S3). |

## 9. The 15 heuristics with the broadest cross-source agreement

Ranked by the number of independent lineages, with evidence breaking ties. Each has a one-line mechanical rule.

1. **Trade toward an untaken draw on liquidity (B2/B3).** Primary draw = the best-scored untaken pool within [0.25, 1.5] × ADR20. `GRADE+1` toward it, `−1` against, and target it.
2. **The prior day's range: one side, rarely both (B3).** On an inside open, after the first pRTH extreme is taken, never target the other side; it follows only about 10% of the time (nqstats).
3. **Trade with the higher-timeframe order flow (B6).** `GRADE+1` if the trade direction equals the last 1H BOS direction and the daily trend is not opposed; `−1` otherwise. Never a skip.
4. **The early-session side persists (T7).** After 10:30, `GRADE+1` with the agreed side of MO, O930 and rVWAP, and `−1` below/above both opens. Below O930 at 10:30, the RTH close finishes above it only 29% of the time.
5. **Never fade an open-drive or trend day (T1/T4).** OD = by 10:00, D ≤ 0.05·ATRd, C − O ≥ 0.20·ATRd, no bar from bar 3 on touches O. If `trend_score` ≥ 5: `SKIP` counter-trend, `HOLD` runners, `TGT far`.
6. **Balance days: fade the edges, take quick profits (T4).** If `trend_score` ≤ 1 or `ib_double`: no breakouts, fade the IB/VA edges toward rVWAP/POC, `SIZE×0.5–0.75`, `QUICK`.
7. **The IB will break, so read which side (T3).** At 10:30, IB close > mid and the IB low printed first → `ib_bias` = +1 (the IB high breaks 84% of the time). Trades with it `GRADE+1`; after a double break, no breakouts.
8. **Gap size decides fill or go (T6).** gA = \|O930 − pRTH_C\| / ADR20. Below 0.2, pRTH_C/HG is a near draw. At 0.35 or more, or an open beyond pRTH, `SKIP` gap fades until a 30-min close back inside.
9. **The morning extreme forms by about 10:15, and the PM makes the other (S1).** 09:50–10:25: sweep → reclaim → MSS of the OR30 extreme = `GRADE+1` reversal. At 12:00, Q2 breaking only one side of Q1 sets `pm_bias`.
10. **Stay out of lunch (S4).** `SKIP` signals closing 11:35–13:30 unless the IB extended ≥ 1 × IBR on one side only (then with-trend pullbacks at `SIZE×0.5`).
11. **Don't trade the release; wait for the second move (S6).** Tier-1 08:30 days: no entries before 09:45. FOMC: none 13:00–14:40, and the afternoon is skipped by default.
12. **No displacement, no trade (G2/N1).** The leg must span ≥ 1.5 × ATR5, have a body/range ≥ 0.6, and leave an FVG ≥ 0.2 × ATR5. `chop` (2 of ER12 ≤ 0.25, OVL12 ≥ 0.6, rng12 ≤ 0.2·ADR20, relVol6 ≤ 0.7) → `GRADE−1`; `chop_hard` → `SKIP`.
13. **Require room to the target (N2/G5).** `room` = distance to the first opposing obstacle ÷ risk. `room` < 1 → `SKIP`; 1–2 → `GRADE−1` with a single target; ≥ 3 → `GRADE+1`.
14. **Bias = where price is drawn, not how the day closes (B1).** If yesterday closed beyond the prior high (low), target yesterday's high (low): NQ takes it 80% (67%) of the time against a base of 55% (46%). Void if the opposite extreme trades first. Never a direction veto.
15. **The daily risk governor (R2/R3/R4).** Stop after 2 losses or day P&L ≤ −$600, and after a first win of ≥ +1R. Risk 10–15% of the buffer above the EOD MLL per trade, $100–400, floored to whole MNQ.

**Next by breadth:**
- No entries before 09:45 (N5).
- No breakeven before TP1, because BE at 0.5R lost in the lab (M3).
- Exit on failure to continue: K-bar time stop, a close back through the FVG, or `giveback` (M2).

---

## Appendix A. The E-own checks (reproducible)

The script was run ad hoc: piped to `python -I -` with `data/NQ_5m.csv` as `argv[1]`. Per the write scope it is not saved in the repo.

**Definitions:**
- CME session date = (ET timestamp + 6 h).date(). Sessions with fewer than 200 5m bars are dropped (holidays, half days).
- ADR20 = mean range of the prior 20 sessions.
- "First" = which of Y.H/Y.L is exceeded first, by 5m bar order. Same-bar ties are counted as neither.
- Opening-drive proxy:
  - over the 09:30–09:55 bars, the open is within 10% of one OR30 extreme;
  - the 09:55 close is in the far 25% of OR30;
  - OR30 ≥ 0.15·ADR20.
- Gap = O930 − close of the prior session's 15:55 bar. "By 10:30" means the first 12 RTH bars.
- The engine log check uses `research/five_year/run_live.json` (987 trades; max 2/day, stop after a win).

```python
import sys, numpy as np, pandas as pd
df = pd.read_csv(sys.argv[1])
df["t"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert("America/New_York")
df = df.sort_values("t").reset_index(drop=True)
df["sd"] = (df["t"] + pd.Timedelta(hours=6)).dt.date          # CME session date
df["hm"] = df["t"].dt.hour * 100 + df["t"].dt.minute
g = df.groupby("sd")
D = pd.DataFrame({"o": g["open"].first(), "h": g["high"].max(), "l": g["low"].min(),
                  "c": g["close"].last(), "n": g.size()})
D = D[D["n"] >= 200].copy(); D.index = pd.to_datetime(D.index)
D["rng"] = D.h - D.l; D["adr20"] = D.rng.rolling(20).mean().shift(1)
bars = {pd.Timestamp(k): v for k, v in df.groupby("sd")}
def first_touch(day, up, dn):
    b = bars[day]; u = b.high.values > up; d = b.low.values < dn
    iu = np.argmax(u) if u.any() else 10**9; idn = np.argmax(d) if d.any() else 10**9
    return "none" if iu == idn == 10**9 else "same" if iu == idn else ("up" if iu < idn else "dn")
# TTrades classes: Y = yesterday, P = day before, T = today
rows = []
for i in range(2, len(D)):
    T, Y, P = D.iloc[i], D.iloc[i-1], D.iloc[i-2]
    if Y.c > P.h: cls, b = "close_above_PDH", 1
    elif Y.c < P.l: cls, b = "close_below_PDL", -1
    elif Y.h > P.h and Y.l < P.l: cls, b = "outside_close_inside", 0
    elif Y.h > P.h: cls, b = "swept_PDH_closed_inside", -1
    elif Y.l < P.l: cls, b = "swept_PDL_closed_inside", 1
    else: cls, b = ("inside_up", 1) if Y.c > Y.o else ("inside_down", -1)
    rows.append(dict(cls=cls, bias=b, hit_h=T.h > Y.h, hit_l=T.l < Y.l,
                     first=first_touch(D.index[i], Y.h, Y.l), up_day=T.c > T.o))
R = pd.DataFrame(rows)   # then: per-class target-hit, target-first and close-direction rates vs base rates
# Weekly extremes: group 5-session weeks (W-FRI periods), argmax(h)/argmin(l) weekday, split by up/down week.
# Opens: MO = 00:00 bar open, O930 = 09:30 bar open, c1030 = 10:25 bar close, rc = 15:55 bar close.
# ADR used: range from 18:00 to the 10:55 bar vs. extension of either extreme after 11:00, in ADR20 units.
# Compression: inside day / NR7 vs next-session range / ADR20.
# Gaps: |O930 - prior rc| / ADR20 buckets; filled = RTH trades back to prior rc (by 10:30 = first 12 bars).
```

**Caveats:**
- These are base rates. No costs, no entries, no stops.
- Part of the TTrades lift is proximity: a strong close sits near the level.
- Part of the weekly and PO3 "shape" results is the arcsine law.
- The data are NQ1! continuous. Roll gaps can create a few artificial gaps or outside days, about 4 a year.
- The window is 2021-10 to 2026-10, mostly a bull regime. Split by regime and by long/short before trusting any single number.

## Appendix B. Primary evidence sources

- **nqstats.com** (NQ 2016–2025; single site, independent of ICT): [IB breaks](https://nqstats.com/ib_breaks.html), [RTH breaks](https://nqstats.com/rth_breaks.html), [ALN sessions](https://nqstats.com/aln_sessions.html), [noon curve](https://nqstats.com/noon_curve.html), [AM TBR](https://nqstats.com/am_tbr.html), [hour stats](https://nqstats.com/hour_stats.html).
- **Linnsoft ES time-of-day and IB studies:** [comment 1070](https://www.linnsoft.com/comment/1070), [comment 189](https://www.linnsoft.com/comment/189), [IB tag](https://linnsoft.com/tags/ib).
- **edgeful** (6-month NQ/ES reports): [NQ futures](https://www.edgeful.com/blog/posts/nq-futures-trading), [gaps](https://www.edgeful.com/blog/posts/half-gaps-vs-full-gaps), [weekday](https://www.edgeful.com/blog/posts/high-and-low-by-weekday-report).
- **Academic:**
  - Gao, Han, Li, Zhou (2018), "Market Intraday Momentum", *JFE*.
  - Lucca & Moench, [NY Fed SR512](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.html) (pre-FOMC drift).
  - [Kurov, Wolfe & Gilbert](https://www.skidmore.edu/economics/documents/KurovWolfeGilbert-TheDisappearingPre-FOMC-Announce-Drift-200914.pdf) (the drift disappeared).
  - Zarattini, Aziz & Barbon (2024), "Beat the Market" ([SFI](https://www.sfi.ch/de/publications/n-24-97-beat-the-market-an-effective-intraday-momentum-strategy-for-s-p500-etf-spy)): a noise-area intraday momentum model whose bands could serve as an alternative T4 trend trigger. An independent TV replication found weaker results.
- **Practitioner lineages:**
  - ICT and followers ([LuxAlgo concept library](https://www.luxalgo.com/library/concept/draw-on-liquidity.md), innercircletrader.net);
  - TTrades ([TFO](https://www.tradingview.com/script/xdwgV3Fx-TTrades-Daily-Bias-TFO/), [joshuuu](https://es.tradingview.com/script/ezS0ydMQ-daily-bias-ttrades-x-joshuuu));
  - AMT/Dalton ([LuxAlgo open types](https://luxalgo.com/library/concept/open-types/), [ATAS](https://atas.net/blog/open-drive/), [Crowstack](https://crowstack.substack.com/p/five-easy-tapes-open-rejection-reverse));
  - Al Brooks ([18-bar forum](https://www.brookstradingcourse.com/support-forum/general-trading-discussion/18-bars-in-emini-is-it-same-the-in-all-markets-or-need-to-adjust/));
  - prop and risk coaches ([NexusFi prop sizing](https://nexusfi.com/a/prop-firms/funded-account-position-sizing), [Topstep help](https://intercom.help/topstep-llc/en/articles/8284208), [traderpeter BE study](https://traderpeter.substack.com/p/there-might-be-more-potential-in)).
- **Access limits during research:**
  - Reddit was blocked for the research tools, and no first-party ICT or TTrades transcripts could be fetched. YouTube was seen only through third-party summaries.
  - NexusFi and marketcalls returned 403, so only snippets were seen.
  - Claims marked "snippet" or "recall" in the agents' notes are flagged where used.
