# TRADER LAYER RULES (pre-registered)

Written 2026-10-16 19:25-19:45 ET, **before any trader-layer result was computed**. Code: `tools/trader_layer.py` (the layer),
`tools/lab_trader_run.py` (the scored batch), `tools/lab_models/with_trader.py` (live wrapper). Report:
`research/lab/TRADER_LAYER_REPORT.md`. Nothing in sections 1-6 changes after the first scored run; later additions are
labeled sections.

**What it is.** One shared "person" that trades every model's proposed entries. A model only says *where* and *which
way* (entry, invalidation stop, direction, time). The layer decides, like a discretionary trader:

1. whether to take it and how big (judgment + risk manager),
2. where the stop really goes and where the money is (liquidity map),
3. how to manage it bar by bar.

Inputs it reuses (read-only): `engine/narrative.py` (narrative, assess), `engine/liquidity_map.py` (draws, tiers,
obstacles, partial pick), `engine/risk_policy.py` (size, EvalAccount), `engine/draw_learner.py` (logged only: it is trained
through 2026-10-13, so it is in-sample on every period here and never drives a decision). Facts from
`DOL_PLAYBOOK.md`, `DRAW_LEARNER.md`, `CONFLUENCE_RESULTS.md`, `TRADER_HEURISTICS.md` and the coordinator's
data-verified list (19:40 ET).

## 0. Causality and fills

- 5m CME futures bars (TradingView NQ1!/ES1!), labeled by open (ET). At decision time `t_dec` only bars with
  `open + 300 <= t_dec` are read. HTF context comes from `engine/narrative.py`, which builds it from those closed bars.
- `t_dec` per source: engine trades -> `entry_t` (fill-bar open = signal close; E = signal close, S = fill - dir x
  risk_pts with fill = fill-bar open + 1 tick); MECH -> `entry_t + 300` (entry_t is the signal bar's open); CONT
  IFVG and ATM -> `entry_t` (already the signal close); SB, ICT2022 and CONT FVG are resting limits -> `entry_t` (the
  fill bar's open), judged on the bars closed before the fill bar.
- Market entries pay 1 tick; limits fill at their price. On a limit's fill bar only the stop is checked (no target
  credit). From the next bar: intrabar order **stop, then TP1, then T; stop wins any bar that touches both**. Targets
  need a 1-tick trade-through. Stop / market / time exits pay 1 tick. $1.40 round trip per MNQ. MNQ $2/pt.
- Every in-trade decision is taken at a 5m close and acts from the next bar.

## 1. Judgment (piece J)

1. **Narrative + assess.** `nar = narrative(bars5, t_dec, es5)`, `v = assess(setup, nar, bars5, es5, version="v1")`
   with the layer's own planned target as `targets` (so the brain's room/path elements judge the real plan). Grade A /
   B / C / SKIP and the thoughts come from the brain unchanged (v1 is the version that existed and was frozen at
   19:15; if v2 lands it is reported as a sensitivity row, never instead of v1).
2. **Hard vetoes** (never overridden; checked at `t_dec`, minutes ET of the decision):
   - the brain's news veto (a high-impact release within -10..+15 min);
   - lunch: 11:35 <= t < 13:30;
   - 08:30 high-impact release day and t < 09:45;
   - FOMC day: no entries (CONFLUENCE risk rule; it covers the 13:00-14:40 window);
   - no new entries at or after 15:30;
   - **never fade an open drive**: at 10:00 (bars 09:30-09:55), with O = 09:30 open, ATRd = mean of the last 14 RTH
     true ranges: OD up if O - min(low) <= 0.05 ATRd, 09:55 close - O >= 0.20 ATRd and no bar from the 3rd on touched O
     (mirror for down). A trade against the drive with t >= 10:00 is skipped while no 5m close has gone back through O;
   - **never fade a trend day**: at t, price >= 0.4 ADR10 beyond the 18:00 open and inside the extreme quarter of the
     day's range so far (the `trend_day` confluence): a trade against that move is skipped.
3. **Frequency guard (2/week).** A score-based SKIP becomes grade C when fewer than 2 layer trades were taken in the
   last 5 sessions (this one included). Hard vetoes and plan skips are never overridden.
4. **Bias option `bias_align`** (coordinator, 19:50): `grade` (default: the brain's E1 alignment element counts),
   `off` (E1 weight 0), `require` (skip when the brain's bias is long/short and the trade is against it; neutral bias
   passes). `require` is a hard veto. Bias source = `narrative()` bias (pre-market score with the intraday
   bias-failure update).

## 2. Stop and plan (piece P)

1. **Stop** = the model's invalidation stop moved away by the playbook buffer `buf = max(2 ticks, 0.1 x ATR14_5m)` at
   the signal bar. R = |E - S|. The stop is never tightened.
2. **Draw inventory** at `t_dec` from `liquidity_map.draws()`: ERL pools = the brain's untaken pools (PDH/PDL, PWH/PWL,
   prior RTH H/L, Asia/London/ATM/overnight H/L, 4H and daily swings, 1H swings, 1H equal highs/lows) plus fresh 5m
   (k=2, today + yesterday) and 15m (k=1, last 5 days) swings; IRL = live opposing FVGs on 5m/15m/1H (brain's
   `live_gaps`, CE-touch mitigation) and 4H/1D (same rule, the 10 nearest). Tiers, significance and obstacles are
   liquidity_map's.
3. `reach` = max(0.5 ADR10, ADR10 - today's range so far).
4. **Inside-open one-side rule** (coordinator / nqstats): when the session opened inside the prior day's range
   (the 09:30 open after 09:30, else the 18:00 open) and one prior-day extreme (PDH or PDL, prior RTH H or L) has
   already been taken today, the opposite prior-day and prior-RTH extremes are removed from the targets.
5. **Final target T**, first that applies:
   a. TTrades draw: yesterday closed above the day-before high (CONT_UP) and the trade is long -> PDH, if untaken, >= 1R
      and within reach (mirror: CONT_DN, short, PDL);
   b. the most significant Tier A/B ERL >= 1R within reach (`pick_primary(pick="significance")`);
   c. the nearest draw of any kind >= 1R within reach;
   d. no draw at all within 12R on that side (price discovery) -> E + 2R (DOL-9);
   e. otherwise **skip: the draw is under 1R or out of reach** (never tighten the stop to make it work).
   Exit price: pools at level -/+ 2 ticks (into the pool), gaps at their near edge.
6. **Plan shape**:
   - *quick* (consolidation day per the brain, or decision at/after 12:00 ET, or HRLR = 3+ obstacles before T): all
     out at the **first draw** (nearest draw >= 1R within reach; else T);
   - else if T >= 3R: 50% (q1 = min(n-1, ceil(n/2))) at **TP1 = first internal draw** (`pick_partial`, >= 1R, short
     of T), runner to T; no TP1 candidate or n = 1 -> all at T;
   - else (1-3R): all at T (single target).
   Plans are fixed at entry (MGMT-9).

## 3. Management (piece M)

At each 5m close, first match wins (MGMT-8):
1. 15:55 ET: flat.
2. Opposing CISD with displacement (MGMT-5): close beyond the open of the first candle of the latest in-favor series
   that began after entry, made by a candle with body >= 1.0 ATR5 and body >= 60% of its range, or one that leaves an
   opposing 5m FVG -> exit.
3. Giveback (MGMT-6, adopted house rule): MFE has reached +0.5R and the bar closes back beyond the entry -> exit.
4. Time (MGMT-7): 12 bars after entry with MFE < +0.5R -> exit; at the 12:00 close, exit if the stop is still on the
   losing side of the entry.
5. Break-even (MGMT-2): after TP1 fills or once MFE >= +1R -> stop to E +/- 2 ticks.
6. Trail (MGMT-3, after break-even): at each 5m BOS in favor (close beyond a k=2 swing that formed after entry), stop =
   max(stop, protected low - buf).
The stop only moves in the trade's favor.

## 4. Size and day rules (piece S)

1. `risk_policy.size(grade, R + entry slippage, account_state, day_state, cfg)`: tiers A $700 (max 10 MNQ) / B $350 /
   C $175, hard guards on (a worst-case stop-out can never reach the trailing MLL or the $1,000 DLL).
2. Simulated account = `risk_policy.EvalAccount` run back to back: a new eval starts the day after a PASS or FAIL, and
   also when the guard leaves no room for even 1 MNQ (a near-dead eval is abandoned and counted as such).
3. **Day rules (on in every layer config, including S off)**: one position at a time; at most 2 trades a day; done
   after 2 losers, at day P&L <= -$600, or after a winner of +1R or more (coordinator / TRADER_HEURISTICS R2-R3).
4. S off -> flat $350, `strategy_lab.size()` contracts, no tiers, no account guards (fallback if risk_policy fails).

## 5. Configs (fixed now; at most 7 per model)

| id | J judgment | P stop+plan | M management | S sizing | bias_align |
|---|---|---|---|---|---|
| RAW | the model's own trades, exits and sizing (as delivered) | | | | |
| FULL | on | on | on | on | grade |
| noJ | off: every setup is grade B, no vetoes, no guard | on | on | on | n/a |
| noP | on | off: the model's own stop (no buffer) and the model's own target as the single exit; no room skip | on | on | grade |
| noM | on | on | off: only stop / TP1 / T and the 15:55 flat | on | grade |
| noS | on | on | on | off: flat $350 | grade |
| BIAS | as FULL | on | on | on | **require** |

Sensitivity rows (reported separately, not part of the comparison): FULL with intrabar ambiguity resolved on 1m bars
(2026 only, `data/NQ_1m.csv`); FULL with brain v2 if it exists at run time; BIAS with `engine/daily_bias.py` if it lands.

## 6. Setup sources and scoring

- Models (NQ, futures only): `ENG1` engine live pick (`conf_testbed_orig1day.json`), `ENG2` engine at 2/day
  (`conf_testbed_engine.json`), `SB` (`SB_trades_NQ_base.json`), `MECH` (`MECH_trades_NQ_base.json`), `M22`
  (`M22_trades/M22_NQ_canon.json`), `CONT` (`CONT_trades/CONT_NQ_IFVG_AMPM.json`, the module default), `ATM`
  (`ATM_trades_base_flat.json`), `ATMX` (the ATM no-skip diagnostic, `ATM_trades_diag_noskip_flat.json`: every signal,
  so the layer's own judgment decides), `ATM1M` (`ATM_trades_1m_*.json`) if it arrives in time, and `PORT` = the union
  of ENG1 + SB + MECH + M22 + CONT setups (the layer's one-position / 2-a-day rules arbitrate).
- Only entries, directions, stops (and, for noP, targets) are read from those files; their exits are ignored.
- Periods: dev, confirm, ytd, aug_oct (one 2026 replay) and y2025 (2025-04-14..12-31). Scorecard =
  `strategy_lab.stats()` (net, PF, trades/week, win %, avg R + bootstrap CI, max DD, losing months, rolling MFFU 50K
  pass vs the zero-edge baseline, back-to-back passes/fails). `score()` (which appends to `confirm_log.csv`) is called
  only for the final named rows, with the `TRADER_LAYER_` prefix.
- Multiple testing: 7 configs x 9 sources x 5 periods. Differences inside the bootstrap CI or of a few hundred dollars
  are noise; the report says so row by row. The engine's Aug-Oct is the window its defaults were tuned on.

## 5b. Implementation notes (written after the first scored run, 19:35 ET; no rule changed)

- The ATM 1m files arrived at 19:22 (`ATM_trades_1m_base.json` = `ATM1M`, `ATM_trades_1m_best.json` = `ATM1MB`). Their
  entries sit inside 5m bars, so every ATM1M config walks the first (partial) 5m bar on 1m bars; in every 1m-path run
  (ATM1M, ATM1MB and the `FULL_1m` rows) the path inside each 5m bar is walked minute by minute, stop first inside each
  minute, and the break-even move after TP1 / +1R applies from the next minute. All other decisions stay on 5m closes.
- Replay check (everything off, flat $350, no layer day rules): the simulator reproduces SB 94/94 and CONT 20/20 trades
  exactly and M22 53/54; MECH, ATM and the engine differ only by their own in-trade management, which the layer does not
  copy.

## 7. Post-hoc rows (written 19:55 ET, AFTER the first results; labeled post-hoc everywhere, never a candidate on this data)

The first run showed the layer cutting frequency by 25-50% and the liquidity-map plan cutting winners. Two extra rows
answer questions the owner and coordinator asked; they were chosen after seeing results, so they are descriptive only:

- `JF` (judgment filter only): the layer's judgment (vetoes, brain grade, frequency guard) decides take/skip on the
  model's OWN trades; outcome, size and day rules stay the model's own (the raw trade is kept or dropped). Isolates
  "does a person picking the trades help?" from the plan / management / sizing pieces.
- `BIASoff`: FULL with `bias_align = off` (the brain's E1 alignment weight set to 0), so all three bias options are shown.
- `BIAS_db`: BIAS (`require`) with the bias taken from `engine/daily_bias.py` (`bias(bars5, t)`, its `DEFAULT_METHOD`
  = `ttrades`; BIAS_REPORT.md had not named a best method at 19:45). The daily_bias direction also replaces the brain's
  bias inside assess().

- `Monly` (added 20:15 ET, post-hoc): management only. The model's own stop and target, flat $350, no judgment,
  layer day rules on; only the in-trade management (BE, trail, CISD, giveback, time exits) is the person's. Asked
  because the ablation showed management as the piece that helped the ATM model in both 2026 halves while judgment
  halved its frequency.

- `FULL_rec` (added 20:05 ET, sensitivity): FULL sized with the risk manager's final `POLICIES["RECOMMENDED"]`
  (published 20:00: flat $350, cap 35% of the cushion, hard guards) instead of the pre-registered A/B/C tiers; the
  layer's day rules unchanged.

## 8. Coordinator variants (specified by the coordinator at 19:50 from the chart gallery; written 19:55 ET before they ran)

1. **Retest entry** (`entry = "retest"`), on top of FULL, for market-entry sources (SB, M22 and CONT-FVG already enter
   on limits). At the decision the person rests a limit at the trigger zone instead of paying the trigger close:
   - zone = ATM's own IFVG (info.ifvg_hi for longs / ifvg_lo for shorts); else the edge of the opposing 5m FVG that the
     signal close inverted (formed within the last 24 bars, no close beyond it in between); else the CISD level (open of
     the first candle of the opposing series the signal closed through); else the signal body's midpoint;
   - filled when a later bar trades 1 tick through it within the window; cancelled if the stop or the final target
     trades first, the session ends, or the window passes. If the zone is not at least 1 tick better than the trigger
     close, the market entry is kept.
   - After a fill: entry = the limit (no slippage), R and contracts recomputed from it; plan levels unchanged.
   - Windows: `RTa` = 30 min (6 x 5m) and `RTb` = 60 min (12 x 5m); for the 1m ATM sources 15 and 30 min (15 / 30 x 1m).
   - 2026 fills and management on 1m bars (compare with `FULL_1m`; ATM1M's FULL is already on 1m); 2025 on 5m.
   - Reported: fill rate (fills / setups that reached the retest step), trades/week and the usual scorecard.
2. **Recent-swing stop for the ATM model** (`stop_mode = "recent_swing"`, ATM1M and ATM1MB, 1m data): the model stop
   is replaced by the most recent swing (2 bars each side) on the trigger timeframe (1m or 3m, built from 1m), formed
   between the sweep extreme and the entry, moved away by max(2 ticks, 0.1 x ATR of the trigger timeframe); no swing ->
   the model stop; a stop closer than **1.0 x ATR of the trigger timeframe** -> skip; never wider than the model stop.
   The layer's own buffer is then added as in FULL. Rows: `SW_FULL` (FULL + this stop) and `SW_noP` (the model's own
   target = the opposite ATM side, with this stop). Reported: median stop, planned R:R, skip rate, trades/week.
   - Added 20:05 ET after the SW rows showed that few setups have such a swing on the trigger timeframe (a truncated
     count read "4 of 57" at the time; the full count is 11 of 57): `SW1_FULL` / `SW1_noP` take the swing on **1m
     bars whatever the trigger timeframe** (the other reading of the coordinator's "1m/3m"); same buffer, same 1.0 x
     ATR(trigger TF) minimum. Labeled as a follow-up variant (result: 12 of 57).
3. **Daily bias from `engine/daily_bias.py` method D `open_amd`** (coordinator 20:10, from BIAS_REPORT.md: no method
   predicts the NY session; D is the best but does not survive correction). On top of FULL (the brain keeps its own
   narrative bias inside its grade):
   - `DB_grade`: +1 to the brain's score when the trade is with D, -1 when against, 0 when D is neutral; the grade is
     re-cut with the brain's fixed cutoffs (A >= 3, B >= 0.5, C >= -2).
   - `DB_skip`: skip only trades against D (neutral passes).
   - "off" = `BIASoff`. The final pick uses grade/context only unless `DB_skip` helps dev, confirm AND 2025 while
     keeping about 1.5/wk or more (coordinator's rule, fixed before the run).
   - `BIAS_db` (earlier row) is pinned to method `ttrades` with the bias swapped into the brain, exactly as it ran.
