---
tags:
  - zeus/strategy
  - bot/zlarior
  - market/nq
type: "strategy"
key: "lit"
---

# Zlarior (LIT)

> [!abstract] Liquidity Inducement on NQ (MNQ micros): sweep, inducement, 5m shift, 1m entry; one target.
> Market: NQ futures, traded as MNQ micros ($2 per point). Setups on 5-minute candles, entry and trade management on 1-minute candles. All times are New York (ET); the trading day runs 18:00 to 17:00. Settings: `live_model.json` (copy in `live_model_lit.json`) → `"model": "lit"`, parameters under `"lit"`; code `engine/lit.py` (rules) + `engine/lit_live.py` (the live loop: PC paper bot and cloud monitor). Paper only.

## Rules in plain words

1. **Liquidity levels**: Every one of these counts as liquidity: - **Session highs and lows:** Asia (from 18:00, 19:00 or 20:00 to midnight), London (02:00–05:00, 03:00–04:00, 02:00–03:00), New York (08:00–09:00, 08:30–09:30, 09:30–10:00, 09:30–10:30) and the premarket (04:00–09:30). A box is a level only after its last candle has closed. - **Previous day, week and month:** high and low of each (PDH/PDL, PWH/PWL, PMH/PML). - **Opening ...
2. **The sweep**: - A new 2-hour low (the **extreme**) takes out a level nobody had traded through yet, within the 2 hours before the extreme. - It has to run at least **half an ATR** (14 bars, 5m) past the nearest level it took. - A swept low sets up a **long**, a swept high a **short** (shorts are the mirror image of everything here).
3. **The inducement**: - Before the sweep, at least **one small 5m swing low sat above the swept level**, no more than **1 ATR** above it and at most **36 candles (3 hours)** old. - Nothing touched it until the final push into the extreme ran through it: the early buyers got trapped.
4. **Displacement and the shift (5m CISD)**: - **CISD level** = the open of the first candle in the last run of down-close 5m candles into the extreme. - **Trigger:** the first 5m close above the CISD level. - Somewhere between the extreme and the trigger, one candle body must reach **0.8 ATR or more**. - The candle after the trigger has to open **between 02:00 and 15:30 ET**.
5. **Entry (1-minute confirmation)**: - A **limit order at the CISD level** works for **30 minutes**. - Once price taps it, the bot gives it up to **20 one-minute candles** to print a 1m CISD (a 1m close back above the open of the last run of 1m down-closes into the low since the tap), then buys **at the next 1m open** (+1 tick slippage). - The setup is dropped if the sweep extreme breaks, the target trades before the tap, 30 minutes pass without a ...
6. **Stop**: - **1 tick (0.25 pt) beyond the sweep extreme.** Never a fixed distance. - Planned stop (limit to stop) under 8 or over 80 points: **no trade**. The size uses the real stop at the fill.
7. **Target: the VIX band**: - One **VIX move** = yesterday's VIX close ÷ 100 ÷ √252 × the 18:00 open. - Longs aim at the 18:00 open **plus** one move, shorts at the 18:00 open **minus** one move. - It has to be **1.5R or more** from the fill, else no trade. Further than **8R**: profit is banked at 8R.
8. **Managing the trade**: - Stop to **breakeven at +1R**: since 2026-10-20 the stop goes to **entry + 1.25 points** (5 ticks: the commission and the exit tick), so a breakeven exit no longer loses the costs (rule 11). - **15-minute check** (1m days, since 2026-10-20, rule 11): 15 minutes after the fill, a trade that never reached +0.5R and closes more than 0.3R under water is closed at the next 1m open. - **Scale-in after breakeven: OFF** ...
9. **Size (size follows the stop)**: - **$800 risk up to a 20-point stop**, then 800 × 20 ÷ stop (a 40-pt stop risks $400, an 80-pt stop $200). - Micros = risk ÷ (stop × $2), rounded down, at most 40; under 1 micro means no trade. - 2026 median stop 47 points → 3 micros, about $290 at risk. - **Weekly stop** (rule 10): after 2 stop-outs in the week, the micros are halved (rounded down once, at least 1 micro). - **No cold-streak filter, no late-entry ...
10. **Loss rules (adopted 2026-10-18, `research/writeups/lit-losses.md`)**: Both were picked on Jan–Jun 2026 and helped Jul–Oct too (`engine/lit.py` options `monday` and `wk_stop`, on in `live_model.json`). - **Monday rule:** on Monday, once the session (from Sunday 18:00) has taken **Friday's high**, take **only shorts**; once it has taken **Friday's low**, take **only longs**. Both taken, or neither: no side rule. A skipped setup leaves the day free for a later one. - **Weekly stop:** ...
11. **Upgrades of 2026-10-20 (`research/writeups/lit-big-ideas.md`): two ON, scale-in OFF until the Sim check**: Each was picked on Jan–Jun 2026 and helped Jul–Oct too; they were scored on the engine itself (`tools/lit_adopt_combo.py`, runs `lit_adopt_t15_be_off` / `lit_adopt_t15_be_off_eval` for the live pair, `lit_adopt_all3` / `lit_adopt_all3_eval` with scale-in). Settings in `live_model.json` `"lit"`; the 15-minute check and the scale-in act only on days with 1-minute bars (all of 2026, none of 2021–25). - **15-minute ...

## Performance by period

| Period | Trades | Per week | Win | PF | Net | Per month | Max DD |
|---|---|---|---|---|---|---|---|
| Jan-Jun 2026 (picked on) | 80 | 3.12 | 58.8% | 4.98 | +$33,901 | +$5,562 | -$2,196 |
| Jul-Oct 2026 (check) | 40 | 2.56 | 50.0% | 2.91 | +$9,919 | +$2,670 | -$1,396 |
| 2026 all | 120 | 2.91 | 55.8% | 4.19 | +$43,820 | +$4,467 | -$2,196 |
| 2021-25 (reference) | 511 | 2.38 | 53.8% | 1.01 | +$1,265 | +$25 | -$19,426 |

_From research/anatomy/explain.json (costs in)._

| | 2026 (Jan 2 – Oct 16) | 2026 H1 (picked on) | 2026 H2 (check) | 2021–25 (reference only) |
|---|---:|---:|---:|---:|
| Trades · per week · weeks with 2+ | 120 · 2.91 · 86% | 80 · 3.12 · 85% | 40 · 2.56 · 81% | 510 · 2.38 · 76% |
| Win rate (a breakeven exit now counts as a small win) | 55.0% | 58.8% | 47.5% | 53.7% |
| Profit factor | **4.07** | 4.98 | 2.69 | 1.01 |
| Net · per month | **+$43,820 · $4,467** | +$33,901 · $5,561 | +$9,919 · $2,671 | +$1,265 · $25 |
| Max drawdown | −$2,196 | −$2,196 | −$1,396 | −$19,436 |
| MFFU 50K eval within 2 weeks (pass / fail) | 31.6% / 1.0% | 36.7% / 1.6% | 23.1% / 0.0% | 6.0% / 13.3% |
| Within 1 month (pass / fail) | 57.3% / 4.9% | 64.1% / 7.8% | 46.2% / 0.0% | 13.2% / 33.0% |
| Pass rate (passed ÷ decided) · median sessions to pass | **90.8%** · 14 | 83.7% · 10 | 100% · 20.5 | 30.0% · 20 |

### Trades by month

| Month | Source | Trades | Net $ |
|---|---|---|---|
| [[Month 2026-01\|2026-01]] | backtest | 17 | +$10,042 |
| [[Month 2026-02\|2026-02]] | backtest | 13 | +$2,322 |
| [[Month 2026-03\|2026-03]] | backtest | 10 | +$7,432 |
| [[Month 2026-04\|2026-04]] | backtest | 14 | +$6,705 |
| [[Month 2026-05\|2026-05]] | backtest | 17 | +$5,092 |
| [[Month 2026-06\|2026-06]] | backtest | 9 | +$2,309 |
| [[Month 2026-07\|2026-07]] | backtest | 9 | +$898 |
| [[Month 2026-08\|2026-08]] | backtest | 9 | +$459 |
| [[Month 2026-09\|2026-09]] | backtest | 14 | +$1,903 |
| [[Month 2026-10\|2026-10]] | backtest | 8 | +$6,660 |
| [[Month 2026-10\|2026-10]] | live | 1 | -$437 |
| [[Month 2026-10\|2026-10]] | paper | 3 | -$1,538 |

_backtest = the bot's rules replayed on futures data (costs in); paper / live = what the bot really did._

## Why it wins and loses

- Jan-Jun 2026: 33 losing trades cost -$8,524: never worked 61%, worked then turned 34%, shaken out then went our way 0%, news 6%.
- Jul-Oct 2026: 20 losing trades cost -$5,202: never worked 65%, worked then turned 31%, shaken out then went our way 4%, news 0%.
- 2021-25: 236 losing trades cost -$98,882: never worked 67%, worked then turned 27%, shaken out then went our way 4%, news 1%.
- Stops are mostly real, not wicks: a stop 50% wider would have reached the target first on 0.0% / 5.0% / 4.3% of stop-outs (Jan-Jun / Jul-Oct / 2021-25); the median stopped trade was only +0.21R our way at best and was out in 33 min (Jan-Jun).
- A careful-human skip list (against both trends / late / news within 30 min / prior-day level under 1R ahead) flags 45% of the losing $ but also 19% of the winning $ (Jan-Jun): skipping them = -$4,320 Jan-Jun, -$5,518 Jul-Oct, +$3,264 in 2021-25.
- Why winners win (Jan-Jun): the best 20% of winners made +$33,838 (100% of the net); the median winner went only 0.19R against us first and took 106 min; 62% of winners came on days that closed our way (losers 31%).
- Hindsight, not a rule: on days that closed our way the trades made +$27,744 / +$9,375 / +$52,621, on days that closed against us +$6,517 / +$544 / -$50,950 (Jan-Jun / Jul-Oct / 2021-25). The day's direction is only known after the close.
- Known at the entry, nothing separates losers from winners better than chance: 18 of 86 fact buckets were worse (or better) in all three periods, vs 15.4 on average with the results shuffled (p 0.274).

## Tested and rejected

> [!failure]- Zlarior more money, 2 pre-registered batches
> 9 single versions, LIT $/month H1 / H2 / 2021-25 vs today $5,562 / $2,670 / $25: ES (MES) LIT filler on days NQ has not traded yet, NQ preempts (4.5 trades/wk) $4,478 / $3,026 / -$66, eval 2-week pass 44.5 -> 43.7, funded $929 -> $642 a month; breakeven at clip(0.25 x target R, 0.5-2R) $5,194 / $2,429 / $209; LIMIT entry at the 1m CISD close (1 tick through, else market) $5,554 / $2,583 / $26 (fills 112/119 at the same price on average; the 7 misses are runners, chase ~5 pts); NY setups only on London's discount side $5,482 / $2,770 / $51; Tier-1 news day: only setups after the release $4,277 / $2,736 / $54; out on a 5m close back through the CISD level before +0.5R $4,738 / $532 / -$75; ...
> Write-ups: [[lit-more-money-2026-11-19|Zlarior]]

> [!failure]- Win / loss anatomy rules
> `tools/win_loss_anatomy.py`, ZEUS Lab kind `anatomy` + one atlas_tilt. 4 pre-declared single versions from the strongest findings of the per-trade anatomy, on the real backtests (costs in): Zlarior x1.25 on a pullback in the daily trend (prior close vs its 20-day SMA with the trade, 1h EMA 20/50 against; 15 + 6 trades) Jan-Jun +$349 / Jul-Oct -$6 a month at the LIT size (the Jul-Oct winners were 2-3 micro trades x1.25 cannot change), eval +$163 / +$130, flip p 0.08 / 1.0; Zlarior skip the careful-human checklist (against the daily AND 1h trend / the day already moved 1 daily ATR / big US release within 30 min / prior-day high-low under 1R ahead) -$412 / -$1,514 a month, 1.8 / 1.5 trades a ...
> Write-ups: [[win-loss-anatomy-2026-11-18|Why we win, why we lose]]

> [!failure]- Zlarior's two live evals together
> the 50K hole + the 25K #2 on ONE Monte Carlo (same paths, live sizing). ATLAS's zombie-eval rule on Zlarior (1-micro last bullet at 80% of the room + give up under $200): pair +$57 / +$51 a month only by killing evals (2-week fails 50K 4.9 -> 10.4 / 3.1 -> 6.9%, 25K 0 -> 8.1 / 0 -> 8.3%, both dead in 20 sessions 0.4 -> 16.3%); stagger (alternate full / half size per signal): -$80 / -$49 a month, 25K 2-week pass 48 -> 31%. Today both evals die together 0.3-0.4% within 20 sessions: the joint risk is waiting, not failing. Rejected.
> Write-ups: [[lit-ideas-2026-11-18b|Zlarior ideas night 2]]

> [!failure]- ZEUS Lab LIT ideas
> 10 pre-declared single versions on the live LIT trades (LIT size + two_week eval path room 0.4, costs in), $/month vs today H1 / H2: time stop 60 min without +1R -$695 / -$945; out at 09:29 if not at BE -$317 / +$33 (5 + 2 trades); BE at 09:29 if +0.5R $0 / $0; out 2 min before CPI / jobs / PPI / FOMC if not at BE +$64 / $0 (1 trade); BE before news if +0.5R $0; after BE out when 60 min without a new best -$1,516 / -$457; BE only on a 1m close at +1R -$326 / $0; NR7 day after x1.25 -$24 / -$11 (eval +$66 / +$149); London build-up sweeps x1.25 +$295 / +$14 but eval H1 -$4, 2-week pass 44.5 -> 41.2, flip p 0.15 / 0.51 (nearest miss, re-tested nightly); 18:00 gap against x0.75 -$408 / -$188. ...
> Write-ups: [[zeus-lab-lit-ideas-2026-11-18|ZEUS Lab]]

> [!failure]- Market-regime warning features
> VIX, RTH range %, overnight share, trend efficiency, sweep reclaim (40-session means) as a 2026-vs-2021-25 light: only overnight share separates (BA 0.94) and it is a yearly drift that calls 2022 (LIT's good year) bad and precedes a worse LIT in 2021-25. Kept: the light from LIT's own last 40 sessions (warning only).
> Write-ups: [[edge-health-2026-11-17|Edge health, 2026-11-17]]

> [!failure]- Drift switch
> cut LIT to paper/half after a rolling loss (51 versions): 0 pass; never fires in 2026; 2021-25 fewer failed evals but same less payout; no better than random cuts.
> Write-ups: [[drift-switch-2026-11-17|"Edge stopped working" switch]]

> [!failure]- B-holds
> while ATLAS (account B) holds a trade, skip LIT's opposite entry instead of closing B (HEDGE). Both accounts 2026 +$52.3k -> +$53.6k, 2021-25 -$3.2k -> -$5.0k; ATLAS 25K 2-week pass H1 65.5 -> 60.5 (stuck 0.8 -> 3.4); 9 clashes in 2026, 35 in 2021-25. Rejected: LIT priority stays.
> Write-ups: [[b-holds-vs-lit-priority|B-holds vs LIT priority]]

> [!failure]- The owner's LIT Complete Report
> The owner's LIT Complete Report (2026-10-18, `research/writeups/lit-report-tests.md`, `tools/lit_report.py`, runs `lit_rep_*`): reclaim, confirmation deadline, acceptance, displacement quality (top-quarter close, 1.5-3x median body, FVG), 2+ inducements, inducement room, 2+ levels swept, leg premium/discount, double-sided sweep, first obstacle (0.5R = lone spike), continuation / flip 2nd trade, costs inside the $800, Berlin-time London boxes (no 2026 change, 2021-25 +$5.8k): none adopted. The report's ch.21 model makes 0 trades in 2026. Beginner guide: `research/writeups/lit-playbook.md`.
> Write-ups: [[lit-playbook|LIT playbook]], [[lit-report-tests|LIT report tests]]

> [!failure]- LIT studies of 2026-10-18/19
> HTF confluences (75, chance level, `lit-htf-confluences.md`); order blocks incl. HTF OB entries and the owner's mitigation notes (84, `lit-order-blocks.md`); entry precision (43, today's entry is best, `lit-entry-precision.md`); all-hours / Asia / per-session / re-arm / F-BoS build-up (30, `lit-all-hours.md`); report-2 continuation, sessions, Smart Money Trap, inducement speed/hierarchy (176, `lit-adv-continuation.md`); BE/partials/targets (`lit-adv-management.md`: BE at entry + 1.25 pts is a small candidate); backtest honesty audit (-$500 of $41.7k, `lit-adv-audit-smt.md`); NQ/ES divergence; more setups: ES/MES, 15m/30m/1h, missed fills, looser filters (95, `lit-more-setups.md`); ...
> Write-ups: [[lit-adv-audit-smt|LIT advanced report ch.7 audit]], [[lit-adv-continuation|LIT advanced report ch2-4]], [[lit-adv-management|LIT advanced management]], [[lit-all-hours|LIT all hours]], [[lit-big-ideas|LIT big ideas]], [[lit-entry-precision|LIT entry precision]], [[lit-funded-firms|LIT on 3 funded accounts]], [[lit-htf-confluences|LIT higher-time-frame confluences]], [[lit-loss-learning|LIT loss learning]], [[lit-more-setups|LIT more setups a week]], [[lit-new-entries|LIT new entries and confluences]], [[lit-order-blocks|LIT order blocks]]

> [!failure]- BLITZ on its own 25K, "like a person"
> as account C (never opposite LIT / ATLAS, closed first; costs $0 in 2026, $16/mo at $150 in 2021-25): structure stops (last 1m / 5m swing, the move's low, caps; 45), liquidity targets / partials / swing trails / change-of-character exits / no clock (1,920), opening drive, London band, retest limits, 15m / 1h BOS filters (32), funded-only structure rule: none beats today's rule in H1, H2 and 2021-25. 25K size: 40% of the room, 100% from eval session 5 (decided in 2 weeks 71-74% vs 29-41%, same money: slot $270 / $37 / -$40 a month; random directions make the same H2 slot $). The post-hoc 1.0 x ATR / 45 min / no trail variant is worse on LIT's 50K too (H2).
> Write-ups: [[blitz-25k|BLITZ on its own MFFU Builder 25K]]

> [!failure]- Zlarior edge night
> target band from NQ's 5/10/20-day range or a VIX/range blend, re-anchored at the entry / midnight open / time left; BE at max or min(1R, k ATR or X pts); 15-minute check threshold in ATR; slow-trade nearer target; pre-registered A+ quality score and 13 single-fact / mined size tilts (200-draw placebo; also on the funded path: size-ups -$16..+$16/mo, cuts cost up to -$109/mo); weekly catch-up (looser setup Thu/Fri when < 2 trades: +0.13 tr/wk); re-entry after the 15-minute cut or a BE (30 trades, -3.35R); a 2nd trade a day re-run (H1 -$1.0k..-5.0k); funded $2,000 cap as a take-profit (-$37 / -$70/mo); eval room-cap size + take-profit at the need (H2 2-week pass 33%); eval-only 3-6R bank; ...
> Write-ups: [[lit-edge-2026-10-30|Zlarior edge night]]

> [!failure]- Rapid EOD levers
> on LIT + ATLAS $500 Rapid EOD 50K: eval give-up / re-buy (room < $500-1,000, session > 30/45, 30%-rule need > $3-4k: +$12-104/mo = noise, 2021-25 worse), eval day caps (none, stop at +$500/+$700, balance-aware guard: today's 30% size guard is best), Asia slot at LIT size (funded lost 9.4% / 2.0% / 27.3%), fixed $1,000 payout requests, different mixes per account for more $ (identical copies pay more in both halves; different mixes only cut the no-pay risk): rejected. Lead: keep a $1,000 funded cushion.
> Write-ups: [[rapid-levers-2026-11-16|Rapid EOD 50K levers]]

> [!failure]- ATLAS deep edge
> loser autopsy (member, side, hour, stop pts / ATR / vs the member's median, target R, daily trend, VIX, LIT's day, the members' paper day) finds no trade bucket that loses in all spans except the known 06:00 / 11:00 hours. Rejected (16 variants): skip / halve after LIT won the other side (slot +$19 / +$29, but 4 H2 trades worth -0.05R; random same-size skips pass the 2026 test 6.7% of draws = chance), same-side retry skip (retries are the best bucket) or x1.25 / x1.5, skip while LIT holds / after LIT won the same side, stop > 1.6x / 2x the member's median, first trades at x0.5 / x0.75 until green, eval weekly brake $400 / $600, daily-trend skip / halve, one signal per side a day. The one ...
> Write-ups: [[2026-11-15-atlas-deep|ATLAS deep edge]]

> [!failure]- E3 same edge, more markets
> live LIT and the 3 ATLAS members unchanged on ES1! as MES (points x 0.28, BE 0.75 ES pts; ES = 5m only, 2025-04+, no 1m, no 2021-24), each on its own MFFU eval. ES LIT H1 -$3.8k / H2 +$12.7k / 2025 -$15.9k (NQ 5m-exec +$6.6k / +$1.5k / -$0.5k), 50K 2-week 27.7/10.9 and 44.9/15.9, corr LIT 0.14. ES ATLAS -$6.3k / +$2.2k / -$2.8k (NQ ATLAS +$47.3k / +$12.1k / +$13.0k): positive before costs, but costs are 7-13% of R on ES vs 2.5-5% on NQ (same tick, ~0.19x the points). NQ LIT NY-only slot as its own account +$12.8k / -$1.2k / -$2.6k at 1/wk; ES London / NY slots lose a span. Asia not redone. Nothing adopted; the 2nd stream stays NQ ATLAS.
> Write-ups: [[es-and-sessions-2026-11-13|Same edge, more markets]]

> [!failure]- E-LIT deep edge
> structural SKIP rules (engine `skip_keys`, the day left free for a later setup), Jan-Jun tercile and q80 cuts, 16 versions: target > 333 / 431 pts, target > 1.05 / 1.22 VIX day-moves, day range so far > 0.80 / 0.92 VIX moves, stop > 0.152 / 0.175 VIX moves, stop > 2.51 / 2.81 x 5m ATR, an opposing level within 0.97R / 0.61R, planned target < 7.46R / 6.13R, deep sweep + big displacement ("breakout"): none passes (best: target > 1.22 VIX moves LIT +$1,602 / +$81 but eval H1 -$2,872); the skipped trades still make +0.3-0.9R and a later setup rarely replaces them; trades fall to 1.2-2.4 a week in H2. Missed-setup census (cap 3 a day, limit / 1m CISD window doubled, 00:00-15:55, min target ...
> Write-ups: [[2026-11-15-lit-deep|LIT deep edge]]

> [!failure]- Regime sizing
> LIT x1.25 / x0.75 by the prior close's regime: GEX sign / level ($bn), VIX level / 1-day change, VXN - VIX spread, VIX/VIX3M, prior NQ range percentile, 2-3 buckets each + every 2x2 pair, VIX / spread as a 1-year percentile. Jan-Jun splits flip in Jul-Oct (VIX falling +1.09R vs +0.61R H1, +0.14R vs +1.24R H2); H2 sits in one bucket (VIX low, spread high, gamma positive on 38-40 of 40). Only gate-passer VIX/VIX3M high x range: +$37 / +$119/mo, placebo 0.53, 5+2 H2 trades, VIX3M ends 2026-09-17, 2021-25 -$1,089, 2-week pass 44.5 -> 42.0%. None adopted; Rapid not run.
> Write-ups: [[lit-regime-sizing-2026-11-17|LIT regime sizing]]

> [!failure]- Learn loop first night
> Zlarior size x1.25 on low dealer gamma / after a tight Asia range / on a many-times-touched or an old swept level / on a fast fill after the CISD, x0.75 the day after a VIX jump; ATLAS x1.25 after Zlarior was stopped on the other side, x0.5 on a two-way day: all 8 rejected (best: old level +$138 / +$125 a month at the LIT size but eval path Jul-Oct -$34). The loop re-checks them on new bars.


## Write-ups

| Date | Write-up | Verdict |
|---|---|---|
| 2026-11-19 | [[one-account-combo-redteam-2026-11-19\|Red team]] | research |
| 2026-11-19 | [[one-account-combo-final-2026-11-19\|One account, Zlarior + ATLAS on the Builder 50K]] | research |
| 2026-11-19 | [[one-account-combo-2026-11-19\|ONE account, several bots]] | research |
| 2026-11-19 | [[lit-more-money-2026-11-19\|Zlarior]] | rejected |
| 2026-11-18 | [[zeus-lab-lit-ideas-2026-11-18\|ZEUS Lab]] | research |
| 2026-11-18 | [[win-loss-anatomy-2026-11-18\|Why we win, why we lose]] | finding |
| 2026-11-18 | [[setup-grade-2026-11-18\|Setup grade]] | rejected |
| 2026-11-18 | [[rapid25-lit-lane-2026-11-18\|Rapid EOD 25K]] | research |
| 2026-11-18 | [[lit-ideas-2026-11-18b\|Zlarior ideas night 2]] | rejected |
| 2026-11-18 | [[blitz-review-2026-11-18\|BLITZ review]] | rejected |
| 2026-11-17 | [[rapid-25k-vs-50k-2026-11-17\|MFFU Rapid EOD 25K vs Rapid EOD 50K for LIT + ATLAS]] | research |
| 2026-11-17 | [[public-strategies-2026-11-17\|Famous published strategies on CME NQ]] | rejected |
| 2026-11-17 | [[payout-policy-funded25-2026-11-17\|Funded Builder 25K payout policy]] | adopt-candidate |
| 2026-11-17 | [[lit-walkforward-2026-11-17\|LIT walk-forward re-tuning]] | rejected |
| 2026-11-17 | [[lit-smart-entries-2026-11-17\|LIT smart entries]] | rejected |
| 2026-11-17 | [[lit-regime-sizing-2026-11-17\|LIT regime sizing]] | rejected |
| 2026-11-17 | [[funded25-lit-atlas-2026-11-17\|ATLAS's funded Builder 25K]] | research |
| 2026-11-17 | [[drift-switch-2026-11-17\|"Edge stopped working" switch]] | rejected |
| 2026-11-16 | [[stack-one-account-2026-11-16\|More strategies on ONE MFFU account]] | promising |
| 2026-11-15 | [[2026-11-15-s2-edge\|S2 edge]] | promising |
| 2026-11-15 | [[2026-11-15-lit-deep\|LIT deep edge]] | rejected |
| 2026-11-14 | [[account-4-2026-11-14\|Account #4]] | adopt-candidate |
| 2026-11-13 | [[millionaire-plan-2026-11-13\|The millionaire plan]] | adopt-candidate |
| 2026-11-13 | [[eval-guard-2026-11-13\|Eval guard]] | research |
| 2026-11-13 | [[es-and-sessions-2026-11-13\|Same edge, more markets]] | rejected |
| 2026-11-04 | [[2026-11-04_second_strategies_night\|Second strategies night]] | research |
| 2026-11-04 | [[2026-11-04_lit_ideas_round3\|LIT ideas round 3]] | research |
| 2026-11-04 | [[2026-11-04_lit_ideas_round2\|LIT ideas round 2]] | research |
| 2026-11-04 | [[2026-11-04_lit_ideas_night\|LIT ideas night]] | rejected |
| 2026-11-03 | [[2026-11-03-slippage\|How much slippage each bot survives]] | info |
| 2026-11-03 | [[2026-11-03-prometheus\|PROMETHEUS]] | rejected |
| 2026-11-03 | [[2026-11-03-night-rnd\|Night R&D 2026-11-03]] | adopt-candidate |
| 2026-11-03 | [[2026-11-03-money-plan\|The money plan on today's settings]] | adopt-candidate |
| 2026-11-03 | [[2026-11-03-fates\|FATES]] | info |
| 2026-11-03 | [[2026-11-03-eval-dp\|Zlarior eval size worked out state by state]] | promising |
| 2026-10-30 | [[lit-edge-2026-10-30\|Zlarior edge night]] | adopt-candidate |
| 2026-10-29 | [[structure-management\|Trade like a person]] | adopt-candidate |
| 2026-10-29 | [[mind\|Mind]] | finding |
| 2026-10-28 | [[scalp-na-mffu\|BLITZ]] | promising |
| 2026-10-28 | [[lit-reversal-exit\|LIT reversal exits]] | rejected |

... and 63 older (see the families).

## Links

- Account: [[Account Zlarior]]
- [[ZEUS Lessons]] · [[ZEUS Decisions]] · [[ZEUS Home]]
