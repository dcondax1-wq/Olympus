---
title: LIT order blocks - finding them like a LIT/ICT trader, and every way to trade them with LIT
family: other
date: 2026-10-18
status: rejected
summary: A new order-block detector (engine/lit_ob.py, no look-ahead, checked on 20 charts) finds the last opposite candles before a displacement that breaks structure and leaves a fair value gap, on 5m, 15m, 1H, 4H and daily candles, with mitigation, breakers, extreme vs decisional blocks and the owner's mitigation rules. It was put into the live LIT trade in every role - point of interest, entry, target, obstacle, and as a source of new trades (sweep into or inside a fresh 1H/4H/daily block, also as a second trade a day) - and scored with both live sizes (eval and two_week), picked on Jan-Jun 2026 and checked on Jul-Oct 2026. Nothing improves both halves, so nothing goes live. The reason is simple: only 10-25 of the 120 live trades sweep into a fresh higher-timeframe block, those trades are not better than the rest in Jan-Jun, and fresh HTF blocks that LIT could trade on its own add 1-16 trades a year. Two ideas are worth watching: skipping trades with a fresh opposing 15m/1H block less than 2R away halves the 2-week eval fails (H1 8.4% to 3.4%, H2 2.9% to 0%) but costs about $4.5k-6k in Jan-Jun and does not raise Monte Carlo passes; HTF block setups as a second trade a day add about 10 trades and a little money in both halves but leave the Jul-Oct 2-week pass flat (50.7% to 49.3%). Paper only.
runs: lit_ob_base, lit_ob_poi_require_15m_1h_4h_body, lit_ob_poi_require_loose_15m_1h_4h_1d, lit_ob_poi_x1_5_when_present, lit_ob_poi_skip_when_3_atr_from_any_fresh_htf_ob, lit_ob_ch12_poi_x1_5_all_origin_checks, lit_ob_entry_5m_ob_mean_threshold_tap_1m_cisd_if_within, lit_ob_entry_1m_ob_mean_threshold_after_the_1m_cisd_if_, lit_ob_target_nearer_of_1h_4h_ob_and_vix_band, lit_ob_obstacle_skip_opposing_15m_1h_ob_2r, lit_ob_ob_only_setups_15m_1h_4h_1d_depth_0_tol_1, lit_ob_ob_inside_setups_1h_4h_1d_depth_0_25, lit_ob_ob_setups_into_inside_15m_1h_4h_1d_as_a_2nd_trad, lit_ob_ob_setups_15m_1h_4h_1d_displacement_0_5_atr_as_a
---

## In one minute

- **The owner's order (2026-10-18):** "Order blocks are huge, implement these too. I want you trading all of LIT." Then:
  "Higher time frame order blocks connected with LIT is good, get entries in that too."
- **What was built:**
  - An order-block detector that marks blocks the way LIT / ICT traders do, with no look-ahead (`engine/lit_ob.py`, a pure
    function the dashboard can call to draw the same blocks).
  - A test harness that puts the blocks into the real live LIT trade (`tools/lit_ob.py`). With no order-block option it gives
    back the live trade exactly: 120 trades in 2026, +$41,734.
- **What was tested (63 variants), each with both live sizes:**
  1. The block as the **point of interest**: the sweep must run into a fresh 15m / 1H / 4H / daily block, or size up when it
     does, or skip / half-size when it is far from one.
  2. The block as the **entry**: a limit at the 5m or 1m block's mean threshold or edge, only when that level is close.
  3. The block as the **target** or as an **obstacle** in the way.
  4. **Chapter 12** of the second report: qualify the origin before using the block.
  5. **New trades from higher-timeframe blocks:** a LIT sweep + inducement + CISD into or inside a fresh 1H / 4H / daily
     block, on days the main model has nothing, or as a second trade a day.
  6. The **owner's LIT group notes on mitigation**: the block of the initial break off the peak, the FVG next to it, the
     trap rule (untaken liquidity next to the zone), full box vs refined box, orderflow continuation, flip zones.
- **Result: nothing improves both halves of 2026, so nothing changes live.**
  - Only 10 of the 120 live trades (strict definition) or about 25 (loose) sweep into a fresh higher-timeframe block.
  - In Jan-Jun (the half the choices are made on) those trades are **worse** than the rest. Requiring a block cuts LIT to
    0.2-0.8 trades a week and loses most of the money.
  - Fresh 1H / 4H / daily blocks are rare (a 1H block about 3 times a week, a 4H block less than once a week, a daily block
    about 7 times a year), and most of the LIT setups they give are the same setups the main model already takes. Trading
    them on their own adds 1 to 16 trades a year.
- **Two ideas to keep watching (not adopted):**
  - **Opposing block in the way:** skip a trade when a fresh opposing 15m / 1H block sits less than 2R from the entry. With
    the live two_week sizing it halves the 2-week fails (Jan-Jun 8.4% to 3.4%, Jul-Oct 2.9% to 0%) and lifts the 2-week pass
    on real starts (52.9% to 54.6%, 50.7% to 53.6%). But it costs $6,000 in Jan-Jun, and in the Monte Carlo the Jan-Jun pass
    falls (50.5% to 47.4%). It makes the eval safer, not faster.
  - **HTF block setups as a 2nd trade a day:** about 10 extra trades in 2026, +$4.5k (Jan-Jun) and +$1.5k (Jul-Oct) with
    the two_week sizing, but the Jul-Oct 2-week pass is flat to slightly worse (50.7% to 49.3%; Monte Carlo 55.4% to 55.1%),
    and it needs a second trade a day.
- **Nothing live was changed:** `live_model.json`, `engine/lit.py`, `engine/lit_live.py`, `STRATEGY.md` and the dashboards are
  untouched.

## 1. What an order block is (for a beginner)

An **order block** is the place a strong move started. Traders believe big players left orders there, so when price comes
back to it for the first time, it may react again.

- **Bullish block (a place to buy):** the last red (down-close) candle, or the last small run of red candles, right before a
  strong move up.
- **Bearish block (a place to sell):** the last green candle, or run of green candles, right before a strong move down.

Not every last red candle is an order block. The move after it has to prove it was strong:

1. **Displacement:** the move has a big candle body (at least 0.8 ATR, the same test LIT uses).
2. **It leaves a fair value gap (FVG):** a gap between candle 1's high and candle 3's low that price skipped.
3. **It breaks structure (BOS):** it closes beyond the last swing high that sits above the block and was still intact. Or,
   when the block itself took liquidity (its low ran a previous swing low), a close above the block's body is enough.
4. **No look-ahead:** the block exists only after the candle that completes all three has closed.

What a trader marks on the chart:

- **Zone:** the block's body (open to close; TTrades) or its full range with wicks (the "full mitigation box"). Both tested.
- **Mean threshold (MT):** the middle of the body.
- **Fresh vs mitigated:** the block is fresh until price touches it for the first time. That first touch is the
  **mitigation**.
- **Breaker (flip zone):** if price then closes through the far side of the block, the block failed. It flips: a failed
  demand block becomes supply, and its first retest is a possible trade the other way.
- **Extreme vs decisional:** the extreme block is the origin of the leg (it holds the lowest low since the swing that was
  broken). A decisional block is one formed later, higher in the same leg, closer to price.

### How the bot finds one (engine/lit_ob.py)

- `resample()` builds 15m, 1H, 4H and daily candles from the CME NQ 5m file. 1H = clock hours, 4H from 18:00 ET, daily = the
  CME trading day. A higher-timeframe candle counts only after its last 5m bar closed.
- `detect()` walks every up candle that follows a down candle. It takes the down run before it (1 to 3 candles, a doji inside
  is allowed, one doji may sit between the run and the move). Then it gives the move 4 candles to leave an FVG and break
  structure. The move must not trade below the block first.
- Extra rules found from the charts:
  - Runs longer than 3 candles made zones 100+ points tall: capped at 3.
  - The swing to break must sit above the block. In a slow grind, an old swing far below price was counted as "broken"; fixed.
  - A gap across the 17:00 halt or a weekend is not a displacement: rejected.
  - 1-tick FVGs in a slow grind are not displacement: the FVG must be at least 0.1 ATR.
- `lifecycle()` adds the first touch (mitigation), the close-through (breaker) and the breaker's first retest.
- `chart_zones()` returns ready-to-draw rows (times, zone, mean threshold, state) for the dashboard.
- Self-test: `python -m engine.lit_ob`.

How many blocks it finds (Oct 2021 - Oct 2026, about 1,290 trading days):

| Timeframe | Blocks | Per week | Took liquidity | Extreme | Touched within a day | Median height |
|---|---:|---:|---:|---:|---:|---:|
| 5m | 11,550 | 45 | 30% | 54% | 92% | 8 pts |
| 15m | 3,384 | 13 | 30% | 54% | 85% | 15 pts |
| 1H | 738 | 2.9 | 30% | 52% | 67% | 32 pts |
| 4H | 215 | 0.8 | 27% | 50% | 42% | 66 pts |
| Daily | 37 | 0.14 | 22% | 49% | 8% | 212 pts |

**The pictures:** `research/study/lit_ob/detector_*.png` (20 charts on 5m / 15m / 1H / 4H). They show clear blocks, edge cases
(a doji in the run, an inside-bar block, a price gap, back-to-back blocks) and candidates the rules reject, each with the
reason (no FVG, no structure break, weak move, price went back below the block first, an opening gap).
`research/study/lit_ob/trade_*.png`: 6 live 2026 LIT trades whose sweep ran into a fresh HTF block (3 winners, 3 losers).

## 2. How the tests were run

- **The trades are the real live LIT trades:** the same sweeps, inducements, 5m CISD, limit at the CISD level, 1m CISD
  confirmation, stop 1 tick beyond the sweep extreme, VIX-band target, breakeven at 1R, Monday rule and weekly stop. Only the
  order-block option changes. Check: with no option the harness gives run `lit_live` exactly (120 trades, +$41,734).
- **Both live sizes:**
  - **eval:** $800 up to a 25-pt stop, then 800 x 25 / stop, never more than 60% of the room to the MFFU trailing floor.
  - **two_week (live since 2026-10-18, config C):** "one winner passes" sizing. It sizes each trade to the target, so a
    "size up when there is a block" rule changes nothing in this mode. Only skips and half sizes do.
- **MFFU Builder 50K evals:** a fresh eval on every session. "2-wk" = pass / fail within 10 sessions, "1-mo" = within 20.
- **Pick on 2026 H1 (Jan 2 - Jun 30), check on 2026 H2 (Jul 1 - Oct 16).** 2021-25 is a reference line (5m only, no 1m data).
- Costs in: $1.40 per micro, 1 tick of slippage on market entries and stop / breakeven / end-of-day exits.

## 3. The results

Each test shows H1 (pick), H2 (check) and the 2021-25 reference. Money columns are the eval mode; the last two columns are the
live two_week mode.

TABLES_HERE

## 4. What each test says, in plain words

**Test 2 - block as the point of interest (the classic LIT sequence).**
- Liquidity builds, the inducement is taken, then the real liquidity is swept **into** a fresh 15m / 1H / 4H block.
  - Strict version: the first touch of the block happens in the last hour of the sweep leg, and the extreme is no more
    than 1 ATR past the block's far edge.
  - Loose version: up to 6 hours, 2 ATR.
- Only 10 (strict) to 25 (loose) of the 120 live trades do that. In Jan-Jun they average 0.1-0.4R against 0.8-0.9R for
  the rest (1 micro, before sizing).
- **Require it:** 0.2-0.8 trades a week. Far below the 2-a-week minimum, and it loses $27k-35k of Jan-Jun profit.
- **Size up 1.25x / 1.5x when present:** +$200 to +$1,300 in Jan-Jun and -$600 to +$540 in Jul-Oct, eval mode only. The
  2-week and 1-month fails go up a little. Too thin to matter, and it does nothing in the two_week mode.
- **Skip or half when far from any fresh HTF block:** most live trades are far from one. The best trades are the ones more
  than 3 ATR away. It costs $15k-34k.
- **Extreme vs decisional, breakers, daily blocks:** same picture. All under 1 trade a week, none better in both halves.

**Test 3 - block as the entry.** After the 5m CISD the bot knows the 5m block that made it. That block is the down-close run
into the extreme, and its body top **is** the CISD level, so today's limit is already the block's edge.
- **Mean threshold:** a deeper limit at the block's middle, only when it is within 25% / 50% of the stop distance.
  - 25%: +$3.3k in H1 but -$0.8k in H2.
  - 50%: far fewer fills.
- **Plain limit without the 1m confirmation:** loses in H2.
- **Wick top (a shallower limit):** better in H2, worse in H1.
- **1m block after the 1m CISD** (a limit at its edge or middle instead of the next 1m open): worse in both halves. The
  winners leave without a pullback.
- This repeats the earlier finding (`research/lit/entry.md`): deeper LIT limits lose more winners than they save in stop.

**Test 4 - block as target or obstacle.**
- **The nearest opposing fresh block as the target:**
  - Alone: -$22k to -$28k in H1.
  - The nearer of it and the VIX band: -$1.3k to -$7.6k in H1 and -$3.1k to -$4.1k in H2.
  - The VIX band stays.
- **Obstacle (skip a trade when an opposing fresh block is close):**
  - 1R: worse in H1.
  - 1.5R: mixed.
  - 2R to 2.5R: fails drop a lot in both halves. 2-week fails go from 8.4% to 3.4% (H1) and from 2.9% to 0% (H2) with the
    two_week size, and passes on real starts rise (52.9% to 54.6%, 50.7% to 53.6%).
  - But it skips 20 of 80 H1 trades and costs $6,000 there (eval mode -$4,500).
  - The Monte Carlo (4,000 shuffled 20-session paths) shows H1 passes **falling** (50.5% to 47.4%) and H2 rising (55.4% to
    57.8%), fails 6.2% to 3.4% and 5.5% to 2.0%.
  - 3R drops below 2 trades a week.
  - **Verdict: a fail-reducer, not a faster pass.** It does not meet the bar.

**Chapter 12 of the second report** (give each block one job; qualify the origin before refining the box; nested blocks;
first opposition).
- **One job per block:** built in. The point of interest, the entry block, the opposing block and the breaker are separate
  objects, each tested in its own role (tests 2-4).
- **Qualify the origin** (four objections), as checks on the point-of-interest block:
  - "No relevant extension": the detector already demands a structure break.
  - "No qualifying sweep": the block must have taken liquidity.
  - "Liquidity beyond the zone": no untaken LIT level within 2 ATR beyond the far edge.
  - "Imbalance beyond it": no unfilled FVG within 2 ATR beyond the far edge.
  - Results, size x1.5 with each check: H1 +$1.1k to +$1.3k, H2 -$0.6k to +$0. With all four, only 1 trade a year is left.
    Requiring them: 1 trade.
- **Nested blocks:** the extreme-only and decisional-only selectors were run separately (test 2). Every selector gave the
  same answer, with the same sign in both halves: requiring a block loses. The conclusion does not depend on the selector.
- **Protected high / low:** already in the bot. The LIT setup is cancelled when the sweep extreme (the protected low)
  breaks before the fill.
- **Targets from the entry location / first opposition:**
  - First opposing 15m/1H/4H block when it is at least 1R away, else the VIX band: H1 -$9.1k, H2 -$4.8k.
  - 1H/4H only: H1 -$1.3k, H2 -$3.1k.
  - Rejected.

**Test 5 - higher-timeframe blocks as new LIT entries** (the owner's "get entries in that too").
- **Into:** a fresh 1H / 4H / daily (and 15m) block's edge is treated as the liquidity. Price trades into it, then the
  usual inducement, displacement and 5m CISD, and the same 1m entry.
- **Inside:** once price is inside a fresh block, a 5m swing low it makes there is the liquidity. The LIT sweep of that
  internal low, with inducement and CISD, is the setup.
- Of 292 "into" setups in 2026:
  - 65 are the main model's own setups.
  - 88 fail the displacement and 63 the inducement.
  - 53 are valid new setups, but 36 of those fall on days the main model already trades.
- Inside: 97 setups, 8 valid new, 6 on main-model days.
- **On free days only (one trade a day):** +1 to +6 trades a year. H2 is flat or worse.
- **As a second trade a day (after or before the main trade, at most one OB trade a day):**
  - 15m/1H/4H/daily: +10 trades. Eval +$1.4k (H1) / +$0.2k (H2). two_week +$4.5k / +$1.5k. 2-week pass 52.9% to 55.5%
    (H1) but 50.7% to 49.3% (H2). Monte Carlo 50.5% to 52.5% (H1), 55.4% to 55.1% (H2).
  - 1H/4H/daily only: +3 trades, about $0.
  - With the displacement relaxed to 0.5 ATR: +16 trades, H1 up (2-week 57.1%), H2 down (44.9%).
- **Verdict:** the main LIT model already trades almost every HTF block setup. The rest is too small and does not hold in
  Jul-Oct.

**The owner's LIT group notes on mitigation** (`research/lit/owner_lit_notes.md`).

MIT_HERE

## 5. Recommendation

- **Adopt nothing.** No order-block rule improves both 2026 halves under the live two_week sizing, and none keeps more money
  in Jan-Jun.
- **The detector stays useful:**
  - `engine/lit_ob.py` (pure, tested, no look-ahead) can draw the blocks on the dashboards with `chart_zones()`.
  - The harness `tools/lit_ob.py` can re-test any order-block idea on the live LIT trade.
- **Watch list:**
  - The 2R obstacle rule as a possible "safe eval" switch, if the owner ever prefers fewer fails over passes.
  - HTF block setups as a 2nd trade a day, once there is more 1m data.
- Engine options would be: `ob_obstacle: {"tfs": ["15m","1h"], "rr": 2.0}` and
  `ob_setups: {"tfs": ["15m","1h","4h","1d"], "second": true}`. Neither is implemented in the engine: neither passed.

## Files

- Detector: `engine/lit_ob.py` (`python -m engine.lit_ob` self-test).
- Harness: `tools/lit_ob.py` (`check`, `grid`, `save`, `charts`, `detector`).
- Every number: `research/lit/ob_results.json`; Monte Carlo of the two candidates: `research/lit/ob_mc.json`.
- Charts: `research/study/lit_ob/`.
- Runs: `lit_ob_*` (family other, tags lit, lit_ob). The stored trades are the eval-mode path; the verdict of each run
  carries both sizes.
