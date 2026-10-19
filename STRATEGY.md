# The exact strategy the bot trades: LIT (Liquidity Inducement), 2026-tuned

Market: NQ futures, traded as MNQ micros ($2 per point). Setups on 5-minute candles, entry and trade management on 1-minute
candles. All times are New York (ET); the trading day runs 18:00 to 17:00.
Settings: `live_model.json` (copy in `live_model_lit.json`) → `"model": "lit"`, parameters under `"lit"`; code `engine/lit.py`
(rules) + `engine/lit_live.py` (the live loop: PC paper bot and cloud monitor). Paper only.

**Version:** locked 2026-10-18, **loss pack adopted 2026-10-18** (rule 10: Monday rule + weekly stop). **Owner's order
(2026-10-18): LIT is the strategy, tuned and judged on 2026 only** (Jan 2 – Oct 16). Picked on Jan–Jun 2026, checked on
Jul–Oct 2026. 2021–25 is shown as a reference line, never as a gate. The previous strategy (Liquidity Engine, below) keeps
running in the cloud monitor as a shadow paper ledger for comparison. Research: `research/writeups/lit-final.md` (run
`lit_final`), `research/writeups/lit-losses.md` (run `lit_loss_pack`); the live settings are run `lit_live`.

## 1. Liquidity levels
Every one of these counts as liquidity:
- **Session highs and lows:** Asia (from 18:00, 19:00 or 20:00 to midnight), London (02:00–05:00, 03:00–04:00, 02:00–03:00),
  New York (08:00–09:00, 08:30–09:30, 09:30–10:00, 09:30–10:30) and the premarket (04:00–09:30). A box is a level only after
  its last candle has closed.
- **Previous day, week and month:** high and low of each (PDH/PDL, PWH/PWL, PMH/PML).
- **Opening gaps:** both edges of the weekly (NWOG) and the daily (NDOG) opening gap.
- **Build-ups:** equal lows or highs, i.e. two 5m swings within 0.15 ATR, 3+ candles apart, untouched in between.

## 2. The sweep
- A new 2-hour low (the **extreme**) takes out a level nobody had traded through yet, within the 2 hours before the extreme.
- It has to run at least **half an ATR** (14 bars, 5m) past the nearest level it took.
- A swept low sets up a **long**, a swept high a **short** (shorts are the mirror image of everything here).

## 3. The inducement
- Before the sweep, at least **one small 5m swing low sat above the swept level**, no more than **1 ATR** above it and at most
  **36 candles (3 hours)** old.
- Nothing touched it until the final push into the extreme ran through it: the early buyers got trapped.

## 4. Displacement and the shift (5m CISD)
- **CISD level** = the open of the first candle in the last run of down-close 5m candles into the extreme.
- **Trigger:** the first 5m close above the CISD level.
- Somewhere between the extreme and the trigger, one candle body must reach **0.8 ATR or more**.
- The candle after the trigger has to open **between 02:00 and 15:30 ET**.

## 5. Entry (1-minute confirmation)
- A **limit order at the CISD level** works for **30 minutes**.
- Once price taps it, the bot gives it up to **20 one-minute candles** to print a 1m CISD (a 1m close back above the open of
  the last run of 1m down-closes into the low since the tap), then buys **at the next 1m open** (+1 tick slippage).
- The setup is dropped if the sweep extreme breaks, the target trades before the tap, 30 minutes pass without a tap,
  20 minutes pass without the confirmation, or it is 15:55.
- A day without clean 1m bars runs the same rules on 5m candles (4 five-minute candles for the confirmation).

## 6. Stop
- **1 tick (0.25 pt) beyond the sweep extreme.** Never a fixed distance.
- Planned stop (limit to stop) under 8 or over 80 points: **no trade**. The size uses the real stop at the fill.

## 7. Target: the VIX band
- One **VIX move** = yesterday's VIX close ÷ 100 ÷ √252 × the 18:00 open.
- Longs aim at the 18:00 open **plus** one move, shorts at the 18:00 open **minus** one move.
- It has to be **1.5R or more** from the fill, else no trade. Further than **8R**: profit is banked at 8R.

## 8. Managing the trade
- Stop to **breakeven at +1R**.
- **Flat by 15:55 ET** (the live bot flattens on the clock too). On a CME early-close day (US holidays 13:00 ET, the day after
  Thanksgiving and Christmas Eve 13:15 ET) the NinjaTrader route stops new entries 15 minutes and flattens 5 minutes before the
  halt (execution safety, 2026-10-18; the backtest exits at the day's last bar).
- **One trade a day**, never two at once.

## 9. Size (size follows the stop)
- **$800 risk up to a 20-point stop**, then 800 × 20 ÷ stop (a 40-pt stop risks $400, an 80-pt stop $200).
- Micros = risk ÷ (stop × $2), rounded down, at most 40; under 1 micro means no trade.
- 2026 median stop 47 points → 3 micros, about $290 at risk.
- **Weekly stop** (rule 10): after 2 stop-outs in the week, the micros are halved (rounded down once, at least 1 micro).
- **No cold-streak filter, no late-entry rule.** Eval-safe switch, off: `how_out: 0.5` (half size when the sweep extreme falls
  outside Tuesday 03:00 – Wednesday 11:30; LIT final numbers): 2026 +$27.8k instead of +$38.9k, max DD −$2.3k, no eval failed
  within 2 weeks.
- **Two-week eval sizing (ON since 2026-10-18, `"lit_sizing": {"mode": "two_week"}`, config C of
  `research/writeups/lit-two-week-eval.md`, run `lit_2wk_rec`).** Owner's order: an eval must be passed within 2 weeks
  (10 sessions). In plain words: **"one winner passes"**.
  1. When LIT enters, the target is already known (the VIX band, 1.5R to 8R).
  2. The bot buys enough micros that, if this one trade reaches its target, the eval reaches +$3,000.
  3. Then it caps the size so a full stop-out (stop + 1 tick + commission) stays inside **60% of the room** between the eval
     balance and the trailing max-loss floor, and inside MFFU's **$1,000 soft daily loss**; at most 40 micros, at least 1.
  4. No new trade once the day already reached the eval target. The weekly stop's half size does **not** apply in this mode
     (the Monday rule still does). Near the target the size shrinks by itself.
  - Results (the 120 real LIT trades of 2026, a fresh eval on every session, MFFU 50K at $91.80):

    | | Jan–Jun starts (picked) | Jul–Oct starts (check) |
    |---|---|---|
    | Passed within 2 weeks | **52.9%** | **50.7%** |
    | Failed within 2 weeks | 8.4% | 2.9% |
    | Still open after 10 sessions | 38.7% | 46.4% |
    | Cost per 2-week pass ($91.80 ÷ pass rate) | **$174** | **$181** |
    | Monte Carlo 2-week pass (fail) | 50.5% (6.2%) | 55.4% (5.5%) |

    The previous eval mode passed 40% / 25% ($228 / $373 per 2-week pass). Back to back on 2026 (a new eval after each pass,
    fail or 10 open sessions): 15 passes in 32 evals, $196 a pass; the eval accounts made +$42,211 ($4,303/month, PF 2.50).
    2021-25 reference (5m entries, never a gate): 15.4% pass / 5.6% fail.
  - **Risk:** the first trade of a fresh eval can risk up to **~$990** (a full stop-out); the worst day in the study was
    **−$1,008** (the soft daily loss plus 1 tick). Typical trade size is larger than before on purpose.
  - **Reset at session 10.** Sessions are counted from `lit_sizing.eval_start` in `live_model.json` (now `2026-10-19`; the PC
    start cfg `"eval_start"` overrides it). An eval still open after session 10 shows **"reset recommended"** (README "Eval
    clock", state key `eval_2wk`): buy a new eval and set `eval_start` to its first session. A pass or a fail needs the same.
  - If the target, the stop or the eval state is missing at an entry, the bot sizes it with the eval mode below and logs why.
  - Code: `engine/sizing.py` (`two_week_qty`, `eval_state`, `eval_session`, `eval_clock`, `lit_qty` mode `two_week`), settings
    `lit_sizing.two_week` (`base need`, `room_f 0.6`, `wk false`, `dll_cap true`, `stop_at_target true`).
- **Eval sizing (on 2026-10-18 until the two-week mode replaced it; `"mode": "eval"` switches back):** $800 up to a **25-point** stop, then 800 × 25 ÷ stop
  (times the weekly stop's half, rounded down once), then never more than **60% of the room** between the eval balance and the
  trailing max-loss floor. Typical trade: about 4 micros, about $330 at risk (the LIT rule alone: 3 micros, $275). Run
  `lit_tight_eval_800_25_room60` (`research/writeups/lit-tight-stops-size.md`): 2-week passes H1 37.5% / H2 29.5% (the LIT rule
  28.9% / 23.1%), 2-week fails 3.1% / 0.0% (unchanged), $/month H1 $5,464 / H2 $2,818 ($5,377 / $2,413), median 10.5 / 17.5
  sessions to pass (13.5 / 21); whole-2026 pass rate 84.8% (LIT rule 95.5%), worst day −$806. Tighter stops were tested and
  rejected: they win Jan-Jun and lose Jul-Oct (breakeven at 1R gets hit by normal pullbacks). 1 NQ fixed fails 28-38% of evals
  within 2 weeks: never on the eval. Set `"mode": "normal"` to go back to the plain LIT rule.
- **Other sizing switches** (`"lit_sizing": {"mode": ...}`), off unless chosen:
  The PC bot and the cloud monitor's paper ledger apply them (`engine/sizing.py` `lit_qty`), with one rounding:
  - `"fast_eval"`: $800 up to a **40-point** stop, then 800 × 40 ÷ stop (times the weekly stop's half, rounded down once).
    Run `lit_x_fast_eval` (LIT final): the best 2-week pass rate in both halves (H1 52% vs 33%, H2 47% vs 23%) and half the
    sessions to a pass, but 21–27% of evals fail within 2 weeks. Eval mode only.
  - `"safe_eval"`: never risk more than **60% of the room** between the eval balance and the trailing max-loss floor:
    micros capped at 0.6 × room ÷ (stop × $2), at least 1. Run `lit_x_room_cap60` (LIT final): 1-month fails H1 25.8% → 10.2%,
    pass rate H1 66% → 80%; H2 unchanged (it never binds there).
- Costs in every number: $1.40 per micro round trip, 1 tick slippage on market entries and on stop / breakeven / end-of-day
  exits; limit fills and targets fill at their price.

## 10. Loss rules (adopted 2026-10-18, `research/writeups/lit-losses.md`)
Both were picked on Jan–Jun 2026 and helped Jul–Oct too (`engine/lit.py` options `monday` and `wk_stop`, on in `live_model.json`).
- **Monday rule:** on Monday, once the session (from Sunday 18:00) has taken **Friday's high**, take **only shorts**; once it has
  taken **Friday's low**, take **only longs**. Both taken, or neither: no side rule. A skipped setup leaves the day free for a
  later one.
- **Weekly stop:** after **2 STOP exits** in the current calendar week (ET, Monday to Friday, by trading day), the rest of that
  week trades at **half size** (micros rounded down once, at least 1). Breakeven and end-of-day exits do not count. Monday
  starts at full size again. The live bots count the week's stop-outs from their own ledger (cloud: its LIT paper ledger; PC:
  its routed exits), and the model's own replay for any day the ledger does not cover.

## How LIT performed (`python tools/export_backtest.py` → `research/lab/backtest_live.json`, costs included, run `lit_live`)

LIT with the loss pack (rules 1–10, exactly what the bots trade):

| | 2026 (Jan 2 – Oct 16) | 2026 H1 (picked on) | 2026 H2 (check) | 2021–25 (reference only) |
|---|---:|---:|---:|---:|
| Trades · per week · weeks with 2+ | 120 · 2.91 · 86% | 80 · 3.12 · 85% | 40 · 2.56 · 81% | 510 · 2.38 · 76% |
| Win rate | 26.7% | 22.5% | 35.0% | 17.5% |
| Profit factor | **3.66** | 4.44 | 2.46 | 1.01 |
| Net · per month | **+$41,734 · $4,254** | +$32,773 · $5,377 | +$8,962 · $2,413 | +$1,275 · $25 |
| Max drawdown | −$2,315 | −$2,315 | −$1,466 | −$20,462 |
| MFFU 50K eval within 2 weeks (pass / fail) | 26.7% / 1.9% | 28.9% / 3.1% | 23.1% / 0.0% | 6.6% / 14.3% |
| Within 1 month (pass / fail) | 55.3% / 3.9% | 61.7% / 6.2% | 44.9% / 0.0% | 12.9% / 34.4% |
| Pass rate (passed ÷ decided) · median sessions to pass | **95.5%** · 16 | 92.3% · 13.5 | 100% · 21 | 28.4% · 20 |
| Back to back (new eval after each pass / fail) | 10 passed, 2 failed | 8 / 2 | 2 / 0 | 11 / 35 |

Eval columns from the research library scoring (`tools/lit_final.py`, a new eval started on every session); the dashboard's
Results page counts only evals with a full 2-week / 1-month window inside the period, so it shows slightly different figures
(2026: 24.9% / 2.0% and 52.4% / 4.3%).

Without the loss pack (LIT final, run `lit_final`): 2026 127 trades, PF 3.06, +$38,873, max DD −$3,097, 2-week 29.1% / 9.2%,
1-month 48.1% / 16.0%, pass rate 79.9%; H1 PF 3.55 +$30,661; H2 PF 2.19 +$8,212; 2021–25 PF 1.03 +$3,806, DD −$20,695. The
pack: +$2.1k in H1 and +$0.75k in H2, the worst month −$466 → −$34, 1-month eval fails 16% → 4%, a pass takes a median 16
sessions instead of 12, 86% of weeks with 2+ trades instead of 90%; 2021–25 $2.5k less (the Monday rule costs money there).

Same months, old strategy: 2026 PF 3.94, +$20,487 (H1 +$4,919, H2 +$15,568), max DD −$2,249.

**Read this honestly:**
- **Expect the H2 rate (about $2,400 a month), not the full-year $4,254.** H1 was tuned, H2 was not; the old bot did better in H2.
- **2021–25 shows no edge** (PF 1.01, drawdown −$20.5k). Those years have no 1m data, so the 1m entry cannot be checked there.
  On 5m candles only, the same rules (LIT final) make +$6.6k in 2026: **the edge needs 1-minute bars.**
- **A few trades carry it:** the top 3 are 38% of 2026's net; the longest run without a winner is 12 trades.
- **It is a London-morning strategy:** 95 of 120 trades enter 02:00–08:00 ET. LIT's own New York entries (08:00–15:30 ET) are
  25 of 120, 0.61 a week, H2 PF 1.10 (+$94); in LIT final 27 of 127, 0.66 a week, H2 PF 0.65. MFFU wants the owner present for
  live trading, so that clashes; paper trading is not affected.
- Months 2026: Jan +9.5k, Feb +2.2k, Mar +7.2k, Apr +6.3k, May +5.3k, Jun +2.2k, Jul +0.5k, Aug −0.03k, Sep +1.8k, Oct (to the
  16th) +6.7k.
- Robust in the checks that were run (LIT final): every one of 23 neighbouring settings stays profitable in both halves (2026
  +$26.9k to +$44.3k); 2 extra ticks of slippage still leave +$38.2k.

**Live loop (paper):** the PC bot (`engine/live.py`) and the cloud monitor (`tools/cloud_monitor.py`) run `engine/lit_live.py` on
the bars from the first day of the previous month on, plus 1m bars. **No Yahoo (owner 2026-10-19):** the bars are the
TradingView exports (`data/NQ_5m.csv`, `data/NQ_1m.csv`) + NinjaTrader's MNQ bars (LE_BarFeed on the PC, kept in the PC's
archive `data/nt_bars/`); the cloud monitor trades on the bars the PC pushes with its heartbeat (`engine/pcbars.py`). VIX for
the target band comes from CBOE's own daily file. A stale NinjaTrader feed blocks new entries (FEED STALE) instead of
falling back to another source; with the PC's bars missing the cloud paper bot takes no new entries ("waiting for
NinjaTrader bars from the PC"). The rules, the size and the orders are unchanged.
`tests/test_lit_live.py` replays every 2026 session through it (with the loss pack) and gets the backtest's trades. The cloud monitor runs every
30 minutes from 02:00 to 16:25 ET (plus the fast-entry watcher while a setup is armed), and its bars are up to ~5 minutes
behind the PC's (1 minute while a setup is armed); its paper ledger still records every trade at the model's prices.

## Previous strategy (shadow): Liquidity Engine, eval mode

The strategy the bot traded until 2026-10-18. It keeps running in the cloud monitor as a shadow paper ledger (README section
"Old strategy (shadow, paper)", no alerts) on `live_model_engine.json`; the PC bot runs it with `"model": "engine"` in its
start settings. Its replay: `python tools/runlib.py baseline`; its last dashboard bundle: `research/lab/backtest_engine.json`.
Archived in one place (rules in plain words, numbers, every file, the steps to switch back): `research/archive/engine-2026-10-17/README.md`;
both dashboards show it under System / Modules → Archive.

Market: NQ futures, traded as MNQ micros ($2 per point), on 5-minute candles. All times are New York (ET).
Settings: engine defaults + `grade_sizing: false`, `conviction_step: 0`, `max_trades_day: 1`, `risk_usd: 800`, `risk_ref_stop: 20`, `dd_aware: false`, `use_fallback: false`, `be_at_r_trending: 3.0`, `memory_seed: false`, `equity_filter: {lookback: 15, min_sum_r: 0, cold_mode: half, cold_size: 0.25}`, `sizing: {late_mult: 0.5}` (`live_model_engine.json`, the old `live_model.json`).

**Version:** locked 2026-10-17 (evening) for Monday 2026-10-19. Changes from the morning lock: quarter size in cold streaks (was half), half size on late entries (new), breakeven at +3R on trending days (was +1R). Research: `research/writeups/risk-summary.md`, `trade-construction-summary.md`; every experiment: `research/runs/`.

### 1. Mark the liquidity
These are the pools the bot watches:
- **Major pools:**
  - prior day high/low
  - prior week high/low
  - overnight high/low
  - London high/low (02:00–05:00)
  - Asia high/low (20:00–00:00)
  - 1H swing highs/lows
  - any equal highs/lows (two levels within 6 points)
- **Minor pools:** 15-minute swing highs/lows.

### 2. Wait for a sweep
- From **08:00 ET**, price trades at least **1 tick through** a pool. That pool is now "taken".
- Sweeping a **low** arms a **long** setup; sweeping a **high** arms a **short**.
- The lowest price of the sweep (highest for shorts) is the **extreme**. If price keeps running, the extreme moves with it.
- The setup expires **60 minutes** after the last new extreme.

### 3. Entry trigger, only inside the killzones (09:30–11:30 and 13:30–15:30)
- **IFVG:** look at the leg that ran into the sweep (from its origin, up to 120 minutes before the extreme, to the extreme). Take the first fair value gap of at least **3 points** inside that leg. The trigger is the first candle whose **body closes back through that gap** (above it for longs, below it for shorts).
- **CISD:** used only when the leg has no fair value gap. The trigger is a candle closing back through the open of the run of candles that made the extreme.
- **Fill:** the open of the next 5-minute candle.

### 4. Confluence check (needs a score of at least 1)
- **+1** if the 1H trend agrees with the trade; **−1** if it's against it.
- **+1** if the sweep happened in **discount** of the 1H swing range for a long, or **premium** for a short.
- **+1** for a clean path: at most 1 unswept swing between entry and target. **−1** if there are 3 or more.
- **−1** if the 15-minute trend already points the trade's way (the entry is late).

### 5. Stop
- **Beyond the sweep extreme + 2 points.**
- **Minimum 10 points:** a tighter stop is widened to 10.
- **Maximum 60 points:** if the stop would be wider, use the far side of the inverted gap instead, provided that's 10–60 points. Otherwise **skip the trade**.

### 6. Target (draw on liquidity, always a real level)
- The **nearest untaken major pool** at least **1.5R** away: prior day high/low, prior week high/low, overnight, London and Asia highs/lows, 1H swing highs/lows, or equal highs/lows. The exit order sits 1 tick in front of it.
- **If that draw is more than 5R away**, the trade still aims at it, but profit is banked at **5R on the way**. Big draws like last week's high are rarely reached the same day.
- **No major pool in range: no trade.** There are no fixed-R targets without a draw.
- Tested and rejected:
  - holding for the far draw with no cap (2026 PF 2.21)
  - exiting at the last minor pool on the way (2026 PF 1.67)
  - draws limited to the day's reach (PF ~1.8)

### 7. Managing the trade
- **Breakeven:** at **+1R**, move the stop to entry + 1 tick. **On a trending day** (10-day efficiency above 0.45, the same test that halves the size) wait until **+3R**: reversal trades against a trend need room, and the giveback rule below still protects them.
- **Time stop:** if the trade hasn't reached **+0.5R within 30 minutes**, close it.
- **Giveback:** once it has been **+0.5R**, a candle closing back through the entry closes it.
- **Close everything by 15:55 ET.**
- **News:** close 5 minutes before a high-impact release.

### 8. Risk management (size follows the stop)
- **Risk $800 when the stop is 20 points or less.** With a wider stop the risk shrinks in proportion: a 40-pt stop risks $400, a 60-pt stop about $267.
  - Micros = risk ÷ (stop points × $2), rounded down, max 40.
  - Examples from 2026:
    - 13.75-pt stop: 28 micros, $770 at risk
    - 53-pt stop: 2 micros, about $212 at risk
- **Why:** over 5 years, stops under 20 pts averaged +0.34R per trade and 20–30 pts +0.10R, while 30–60 pts averaged about 0R.
- **Half size** in a trending market (10-day efficiency above 0.45).
- **Half size on a late entry:** when the 15-minute structure has already turned the trade's way at entry (the −1 item of the confluence score), part of the move is gone, so the size is halved. These trades lost money in both 2021–25 and 2026.
- The size rules multiply (cold streak × late entry), rounded down once, never below 1 micro.
- **1 trade per day.** Done for the day after a winner.
- **No new entries:**
  - from 15 minutes before to 30 minutes after a high-impact US release (CPI, NFP, FOMC…)
  - after 13:00 on FOMC days
  - once the day's range has reached 1.6× the 20-day average

### 9. Cold-streak filter (quarter size in bad stretches)
- The bot keeps a **shadow record of every signal** in rules 1–8 (`data/shadow_ledger.json`).
- Before each entry it adds up the R of the **last 15 signals that have already finished**.
- **Above 0R:** full size.
- **0R or below:** the trade is **still taken, at a quarter of the size** (was half until 2026-10-17: over 2021–25 the quarter size beat the half at every lookback and threshold tested). Alerts say "0.25x SIZE - cold-streak filter".
- Full size comes back **automatically** as soon as the last 15 signals add back up above 0R.
- Every setup is traded, so it keeps 2–4 setups a week. Only the size changes. Cold streaks can last 13–18 weeks; during them most trades are 1 micro (about $100 at risk).
- **When to buy or reset the MFFU eval (2026-10-17 Monte Carlo, `research/writeups/monte-carlo-evals.md`):** start it while the filter shows **full size**. An eval started at full size passed 22% within a month (failed 8%, median 20 sessions to pass); one started in a cold streak passed 4% (median 36 sessions) because quarter-size trades can neither reach +$3,000 nor lose $2,000. The best moment is **within 5 sessions of the switch back to full size** (`eval-game.md`: 2021–25 pass 26% / fail 4.5% within a month, 2026 50%); full size for 20+ sessions is the weakest start (2021–25: 7% pass / 12% fail). The dashboards and the cloud README show this as **Eval timing: GO · BEST / GO / GO · LATE / WAIT** (`eval_timing` in the cloud state, `engine/equity_filter.py`), and the cloud monitor sends an alert when it flips. It changes nothing about the trading.

### How it performed (fresh rerun of its settings on TradingView NQ1! futures data, commissions and slippage included; run `baseline`)

| | 2026 (Jan 2 – Oct 16) | 2021–25 | All 5 years (Nov 2021 – Oct 2026) |
|---|---:|---:|---:|
| Trades | 89 | 679 | 768 |
| Setups per week | 2.16 (2+ in 71% of weeks) | 3.17 (2+ in 92% of weeks) | 3.0 (2+ in 89% of weeks) |
| Win rate | 25.8% | 21.1% | 21.6% |
| Profit factor | 3.94 | 1.27 | 1.54 |
| Net | +$20,487 ($2,088/month) | +$16,379 ($321/month) | +$36,866 ($606/month) |
| Max drawdown | −$2,249 | −$9,265 | −$9,265 |

Before this lock (half size in cold streaks, breakeven at 1R on every day): 2026 +$20,111 (PF 3.48, max DD −$2,661), 2021–25 +$6,491 (PF 1.09, max DD −$11,401), all years +$26,602 (PF 1.32). Run `live_2026-10-17am` in the research library.

**Read the 2021–25 number as a range, not a point** (`research/writeups/parameter-robustness.md`): every neighbouring setting stays profitable in both periods (105 combinations: 2021–25 +$6.8k to +$18.3k, 2026 +$19.6k to +$23.4k), but the cold-streak lookback of 15 is a ridge: 14 gives +$13.3k, 13 gives +$7.8k, 17 gives +$10.7k over 2021–25. The honest 5-year figure is **+$8k to +$17k ($150–$330 a month)**; 2026 does not depend on it. Costs (`stress-tests.md`): one extra tick of slippage or doubled commission keeps 80–86% of the 2021–25 profit; 3 ticks plus doubled commission keeps 42%. Nothing in the calendar (`calendar-effects.md`: weekday, month, OPEX, FOMC/CPI/NFP days, roll weeks) is worth a rule.

**MFFU 50K eval ($3k target, $2k trailing max loss).** A new eval was started on every trading day:

| | 2026 | 2021–25 | All 5 years |
|---|---:|---:|---:|
| Passed / failed within 2 weeks | 20.4% / 0.0% | 4.1% / 1.9% | 6.7% / 1.6% |
| Passed / failed within 1 month | 34.0% / 0.0% | 8.8% / 5.2% | 13.1% / 4.4% |
| Passes slower than 3 weeks · median sessions to pass | 53.8% · 18 | 81.2% · 32.5 | 75.9% · 31 |
| Back to back (new eval after each pass/fail) | 4 passed, 1 failed | 8 passed, 10 failed | 12 passed, 11 failed |

**Owner's eval-speed rule (2026-10-17):** an eval should be decided within 2 weeks and never take over 3 weeks to pass. At this size most passes still take 3 weeks or more. The researched "fast-eval" press (run `risk_fast_press1000`: $800 on any stop while the eval is less than $1,000 down) halves the time to pass and decides 27% / 15% of evals within 2 weeks (2026 / 2021–25) at the same cost per funded account, but fails about twice as many evals a year. It is built in (`sizing.press` in `live_model_engine.json`) and OFF until the owner turns it on.

**Also tested and not adopted:**
- 10–15 pt stops (structural stops are rarely that tight; fixed 15-pt stops get wicked out and lose money)
- the ATM model with a sharp V (about 0.2–1.5 trades a week, about break-even)
- re-sweep, inducement, FBOS and RBOS as size rules (no edge that held in both 2021–25 and 2026; they are recorded on every trade and shown in the trade reports)

All variants are in `research/lab/variant_results.json`.

**What to expect:**
- No setting passes "for sure" in 2 weeks. At $800 the $3k target is about 4 full winners' worth of R, and the $2k limit is about 2–3 full losses.
- Cold streaks of 13–18 weeks happen; during them most trades are 1 micro. That is the rule working, not the bot being broken.
- It wins about 1 trade in 4. Winners are big (often 2–5R); wide-stop losers are small because size follows the stop.
- 2026 was a good year for this model. Over 5 years at this size, more back-to-back evals failed than passed.
- Past results are not a promise. Paper-trade it before risking money.
