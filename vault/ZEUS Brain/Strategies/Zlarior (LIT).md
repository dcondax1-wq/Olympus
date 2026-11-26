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
| [[Month 2026-11\|2026-11]] | live | 1 | -$129 |

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

> [!failure]- LIT entry refinement on 1m
> 5 versions vs today (limit at the 5m CISD level, then the 1m CISD; H1 / H2 / 2021-25 $5,562 / $2,670 / $25 a month, 2-week 44.5 / 39.1). Tap 1 tick through $5,280 / $2,227 / -$171; tap at 50% of the zone 1.2 trades/wk, 2-week 37.8 / 29.0; expiry 20 min $5,266 / $2,506 / -$37; plain limit at 50% no 1m CISD $402 / $4,714 / $1,397, 2-week 16.8 / 29.0; plain limit filled only 1 tick through (touch = no fill) $3,036 / $2,087 / -$305. 0 pass: the 1m CISD confirmation carries the edge.
> Write-ups: [[entry-fine-2026-11-26|LIT entry refinement on 1m bars]]

> [!failure]- Personal futures account vs MFFU
> LIT + ATLAS, fixed-fractional, $1.24 RT, whole micros. $25k at 0.5%: +$49 / +$103 / +$3,001 / +$1,078 a month (2021-25 / 2025 / Jan-Jun / Jul-Oct), DD -24%; at 1%: +$243 / +$357 / +$10,922 / +$3,652, DD -50% (-$24k, 40 months); 2% = -83%. MFFU 50K slot: -$98 / -$78 / +$1,202 / +$1,228. LIT needs ~$14.4k (1% risk) for 90% of its 1-micro stops. Research only, owner's call.
> Write-ups: [[ownacct-2026-11-24|A personal futures account vs the MFFU prop path]]

> [!failure]- Bad-case plan
> in a 2025-like / 2021-25 market every MFFU plan loses ($-236 to -$591 per slot per 6 months, pass 6-21% vs break-even 30-119%). Early-warning rule (LIT 20-trade avg R < Jan-Jun 10th pct) fails: ON 89% of 2021-25 with a HIGHER pass rate there, fires 49% of Jul-Oct. BLITZ $150 on the Rapid: better in 3 of 4 markets, -$15 in 2021-25 = stays paper. ATLAS funded at $150 beats $250 in all 4 markets (lead, not adopted: needs the account_b replay + owner yes).
> Write-ups: [[badcase-2026-11-24|The BAD case]]

> [!failure]- Time windows removed
> LIT entries 18:00-15:30 (whole day) vs 02:00-15:30: -$10,511 / +$27,310 / +$9,644 vs +$1,275 / +$32,773 / +$8,962 (2021-25 / Jan-Jun / Jul-Oct). ATLAS members at any time 00:00-15:55 (live code, month-by-month replay): EMA -$4.3k / +$16.8k / -$3.6k vs +$12.4k / +$19.9k / +$8.1k; MACD -$4.1k / +$8.2k / -$4.5k vs +$21.4k / +$22.1k / +$2.6k; S/R +$1.1k / +$7.4k / +$3.1k vs +$8.9k / +$12.2k / +$2.9k; book 50K Jul-Oct pass 90 -> 17%. The windows ADD money: keep them.
> Write-ups: [[notime-2026-11-24|Do the time windows add money?]]

> [!failure]- Dead hours per pillar
> worst 1-3 half-hour window per book picked on 2021-24 only (PF < 0.8, 20+ trades), tested on 2025 / Jan-Jun / Jul-Oct 2026 + placebo. LIT 02:00-03:00 (-$7.6k in 2021-24) loses $10.1k / $5.2k in 2026 if skipped; ATLAS EMA 05:30-07:00 Jul-Oct -$856; MACD 02:30-03:00 Jan-Jun -$201 (p 0.057); S/R 11:00-12:00 +$1,009 / +$268 / +$15 but p 0.25; BLITZ none. 0 pass: the coverage map's bad hours are in-sample.
> Write-ups: [[dead-hours-2026-11-24|Dead hours per pillar]]

> [!failure]- LIT high-VIX downtrend
> after 0 real winners in 7 live-window twin trades (NQ 31k -> 25k). V1 longs off / V2 all off when prior VIX > 25 and the 20-day trend is down: both lose in 2021-25 (+$1,265 -> -$646 / -$5,698) and Jan-Jun (-$1.2k / -$3.1k; eval -$3.1k / -$7.5k), 0 trades in Jul-Oct, placebo p 0.65 / 0.83. VIX 25+ is LIT's best band (PF 2.5 / 22.7); the live losers came at VIX 17-21. 7+ trades without a +0.5R winner: 25 runs in 2021-25, 4 in Jan-Jun 2026 (longest 12) = variance. Watch only: VIX 20-25 + downtrend (2021-25 PF 0.01, n28; Jan-Jun PF 5.9, n5).
> Write-ups: [[lit-vix-downtrend-2026-11-24|LIT in high-VIX falling markets]]

> [!failure]- Walk-forward portfolio of every stored run + 24-hour coverage
> 1,983 runs, 508 pass the PICK rule (2021-24 + Jan-Jun 2026; corr with LIT / ATLAS < 0.3), greedy-Sharpe adds 6 at 25% of LIT's swing. Hold-outs vs LIT + ATLAS: 2025 +$5,453 vs +$4,480 but PF 1.09 vs 1.13, DD -$10.6k vs -$7.6k; Jul-Oct +$19,324 vs +$16,311 but PF 2.49 vs 3.36, 50K pass/fail 64/36 vs 100/0; +15 trades/week. Fails. Coverage: 02:00-15:30 ET covered every weekday, 18:00-02:00 (Asia) empty (Asia ideas already rejected).
> Write-ups: [[portfolio-2026-11-24|24-hour coverage + a walk-forward portfolio of everything built]]

> [!failure]- Stops x targets x TIME
> 19 pre-registered variants on the live LIT trades, risk-matched $ + 3 MFFU evals, Bonferroni p < 0.0026. Tighter stops (1m CISD candle 7 pts, 1m entry swing 14-17, 3m FVG 15-22) x live price / 2R / 3R: every one loses Jul-Oct ($8.3k-$14.0k under live); 40-58% stopped, 28-41% of those were live winners (wicked out); the 1m swing's Jan-Jun +$75k is the size rule risking more $ (same $: +$8.8k / -$8.3k / 2021-25 -$23.0k). Targets 15m / 1h liquidity, opposing session high, 1h FVG, fixed 1.5 / 2 / 3R: hit up to 2x as often, all lose Jan-Jun $8-25k (1h FVG H2 +$235, p 0.50; 3R 2021-25 +$19k but both 2026 halves lose). TIME: winners +0.5R median 10 min, target median 180 min; N = 26 min from ...
> Write-ups: [[stops-targets-time-2026-11-24|"Stops x targets x TIME]]

> [!failure]- More trades: frequency vs edge
> 19 LIT versions (depth 0.4/0.3, no inducement, disp 0.7/0.6, limit 45/60 min, 1m CISD 30, no 1m CISD step, 2 a day, 2nd after a stop, 2nd opposite side, + Asia, 6 pairs) + 7 ATLAS loosenings + ES. Single gates add 1-3% trades; the frequency levers (Asia +54%, 2 a day +23%, no idm + 2 a day +59%) lose 2021-25 (+$25 -> -$85..-$316/mo, 50K 40-session fail 54 -> 61-78%). Nearest miss Asia: 2-week pass 48.7/55.1 vs 44.5/39.1 but 2021-25 -$12.2k, walk-forward 4/18. 2nd-after-stop: +10% trades, eval same, paper lead. ATLAS: every loosening loses a 2026 half (A4 MACD hist H1 25K pass 94 -> 76). ES LIT alone PF 0.50 in 2025. 0 pass; LIT/ATLAS unchanged.
> Write-ups: [[more-trades-2026-11-25|More trades]]

> [!failure]- Edge hunt lane D: small meta-labeled SIZE + re-entry on LIT
> 31 pre-registered versions. 16 walk-forward size rules (logistic / depth-2 tree x 7 or 13 facts known at the fill x 0.5 / 1.5, 0.75 / 1.25, down-only 0.5, up-only 1.5; monthly refit, purged + embargoed, MFFU caps on the eval path): all 12 that cut size lose 2026 H1 (-$1.6k..-$15.7k) and pass fewer 2-week evals (6.7-37% vs 44.5%); the 4 up-only ones are leverage (a flat x1.25 with no model makes more in H1); the only one through the money gate (tree 13 facts, up-only 1.5: +$5.7k / +$3.2k / +$0.5k, eval +$3.1k / +$0.2k) is chance (shuffled multipliers beat it 29% / 45%, shuffled labels 23% / 15%, in-sample H1 +$12.4k vs +$5.7k), funded +$15-18 a month with more account loss (1.7 -> 1.9%, 3.0 ...
> Write-ups: [[edge-d-meta-2026-11-22|Edge hunt lane D]], [[meta-labeling|Meta-labeling]]

> [!failure]- Edge hunt C, calendar / money-flow timing
> 174 variants on NQ 5m, structural 1-tick stop, LIT size, costs in, permutation p per cell: turn of month (last 2 / first 3 / all 5), OpEx week / Friday / Monday after, quarter end / start, month-end pension fade (2 / 3 / 5%), day of week (long + short), last-hour long / momentum / fade, Globex overnight, intraday drift, each x 3 targets, plus x1.5 / x0.5 LIT dials on 13 windows. 0 pass: every long cell wins 2026 and loses 2021-25; the only cell positive in all 3 spans (Monday long, no target) is a lottery (top 3 trades > 100% of net, p .44 / .14 / .075, random long-only day sets pass 6.6%); dials are chance (best H1 p .10). Last-hour momentum beats random days (p .05 / .04) but loses ...
> Write-ups: [[edge-c-calendar-2026-11-22|Edge hunt lane C]]

> [!failure]- 2026-11-22 Regime guard round 3
> (research/regime/guard3.py, regime-guard3-2026-11-22.md): shadow-setup hit rate R1, intraday variance ratio R2, trend-day share R3, thin volume R4, NQ-VIX co-movement R5, 2-of-5 vote R6; half / out; LIT and ATLAS. **0 of 22 pass, all fail the stage-0 kill-gate.** R1 sweeps pay worse in 2026 than in 2021-25 (flags 2026 87.5/80.8% vs OLD 70.4%). R5 flags LIT's best days. Best placebo 47.5% / 68.5% (95 needed). Closes the regime lever for market-weather and market-wide sweep signals, not every possible signal. ATLAS funded baseline moved 8.5/9.2/94.5 -> 8.2/8.3/94.2 because of a code change after 153552591; verdict unaffected.

> [!failure]- Zlarior edge, 5 pre-registered ideas
> LIT $/month H1 / H2 / 2021-25 vs today $5,562 / $2,670 / $25: limit 2 ticks better than the model fill for 1 min, else market $5,184 / $2,585 / $26; skip a setup when the 1m entry is > 60 min after the sweep bar $849 / $824 / $119 (1.2 / 0.8 trades a week); Tier-1 day target capped at 4R $4,997 / $2,616 / $89; MES instead of MNQ when ES's planned target R >= 1.25 x NQ's $5,069 / $9,656 / $198 (fails Jan-Jun, eval -$10.6k / +$7.0k; paper lead, forward only); no +1R breakeven in the first 10 min $5,068 / $2,670 / $25. 0 pass. Fill map: limits 10-50% of the risk better fill 0-60% and miss $17-34k of Jan-Jun winners. +10 ticks a trade: $5,176 / $2,447 / -$353. Cold run (7 twin trades -4.2R) = ...
> Write-ups: [[lit-edge-2026-11-20|Zlarior]]

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

> [!failure]- Order-flow program on bars
> 6 tests, $500 / costs in: LVN rejection (stand-alone, PF 1.26 / 1.10 / 4.56, placebo p 0.004, 0.5-0.7/wk: H1 PF and count fail; moved to ticks as OF3), IB failed extension -> IB mid (-$36k 2021-25, + only in 2026), LIT skip on poor prior-day highs/lows (4 trades), BVC delta divergence / confirmation on 5m and 1m (cost LIT -$15k to -$31k in 2026 H1: "refuted" trades are LIT's best), skip thin sweeps, 1m absorption print. 0 pass. Real-tick versions pre-registered (PREREG_ticks.md).
> Write-ups: [[orderflow-program-2026-11-23|Order-flow program]]

> [!failure]- Market-regime warning features
> VIX, RTH range %, overnight share, trend efficiency, sweep reclaim (40-session means) as a 2026-vs-2021-25 light: only overnight share separates (BA 0.94) and it is a yearly drift that calls 2022 (LIT's good year) bad and precedes a worse LIT in 2021-25. Kept: the light from LIT's own last 40 sessions (warning only).
> Write-ups: [[edge-health-2026-11-17|Edge health, 2026-11-17]]

> [!failure]- Regime guard
> VRP (RV20 > VIX), 1-year ATR20 / ER20 bottom-third, 2-of-3 vote, half / out for LIT + ATLAS: 0 of 8. None is more common in 2021-25 than 2026 (G1/G4 fire most in Jul-Oct); LIT's 2021-25 $ is made on the flagged days (+$2,065 -> -$1.8k..-$5.9k). Post-hoc lead: ATLAS worse on chop days in all 3 periods; out = ATLAS Jan-Jun -$4,746, funded 2021-25 lost 94.5 -> 85.7%. NQ/ES correlation not testable (ES daily from 2025-04).
> Write-ups: [[regime-guard-2026-11-20|Regime guard]]

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

> [!failure]- Holidays / roll / FOMC windows
> Thanksgiving week, CME roll-date week, Dec 15 - Jan 5, FOMC days x sit out / half, LIT and ATLAS (LIT roll = already rejected): 0 of 14. 2021-25 windows all weak (LIT PF 0.14-0.89, ATLAS 0.51-0.75 vs ~1.1) but 2026 windows profitable (FOMC LIT +$634/trade, ATLAS roll PF 8.9): sit-outs lose Jan-Jun $ (LIT FOMC -$2,535, ATLAS roll -$2,985). Thanksgiving / late Dec have no 2026 sample (untestable). Nearest: ATLAS FOMC out (funded lost down in all 3, but Jan-Jun fixed -$1,223).
> Write-ups: [[holidays-2026-11-21|Thanksgiving week, roll weeks, Dec 15]]

> [!failure]- Rapid 25K slot
> one engine at real fills (rank.py): ATLAS only $707 / $141 a month vs today's LIT + ATLAS $1,883 / $800 (rejected again); bank lane = card rapid25-lit-bank NO (eval fail 0.5 -> 3.1%); a Rapid EOD 50K in the slot $5,001 / $2,281 a month but 2021-25 -$560 vs -$300 and eval fail 2.5 / 4.6% vs 0.3 / 2.4%: fails the pre-set safety bar (already on cards buy-rapid50-now / plan-rapid50k-max2-rebuys). Today's lanes stay.
> Write-ups: [[rapid25-slot-2026-11-22|Rapid 25K slot]]

> [!failure]- One-account combined book
> 13 books x 4 MFFU accounts (+ today = 53) on rank.py at real fills: first-come, LIT-priority 50% day budget, ATLAS NY-only / London-only / strict windows, ATLAS x0.5 eval, LIT eval then both funded, LIT x0.75 / x0.5, + BLITZ $300, ATLAS lane x2. Pick (Jan-Jun, eval fail <= LIT + 2 pts): Rapid EOD 50K LIT + ATLAS, LIT x0.5 in the eval $4,918 / $2,204 / -$88 a month vs today's 2 accounts $981 / $857 / -$62; paired 2021-25 -$156 (SE $32), 2022 -$781, Jul-Oct without ATLAS's 5 best days +$114 (SE $136): fails the 2021-25 bar, no card. Every mixing trick makes less than plain first-come in Jul-Oct (-$60 to -$1,352/mo); the gain is the Rapid 50K account (open card plan-rapid50k-max2-rebuys). ...
> Write-ups: [[one-account-book-2026-11-22|One account, combined book]]

> [!failure]- 2026-11-22 Lucid accounts on a $300 a month fleet
> REJECTED as a way to speed up at $300: adding 1/2/3/5 LucidPro 50K (LIT only, assumed $126) to the Rapid EOD 50K + FundedNext 50K plan out of the SAME $300 budget leaves Jan-Jun-like unchanged (+$264 +- $324 with 2, -$53 +- $370 with 3) and only helps Jul-Oct-like (+$4.7k to +$5.6k over 6 months); buying Lucid FIRST (5 accounts) loses $16.3k Jan-Jun-like and halves the worst 10% ($27.2k -> $16.3k), because the Lucid copies displace the bigger accounts. It works only with a larger budget ($500: 3 Lucid = Decide card lucid-3-at-500-budget). 75 fleets tried.
> Write-ups: [[fleet-v2-2026-11-22|Fleet v2]]

> [!failure]- Popular ICT/SMC strategies as taught
> Silver Bullet, Judas Swing, Asia sweep, London breakout, PDH/PDL sweep, NY open FVG, PO3/AMD, ICT 2022, Turtle Soup, Unicorn; 5m, stop 1 tick beyond the swing, 2R, LIT sizing, costs in. 0 of 10 pass (PF > 1 in all three spans and Holm p < 0.05; best raw p 0.17, all Holm 1.0); 9 of 10 lose 2026 H1. Only ICT 2022 adds $ to LIT in both 2026 halves (+$369 / +$681 a month on a Rapid 50K, ~5 trades/wk) but DD $2.2k -> $4.8k, H1 eval fails 1.6% -> 34%, loses 2021-25. Corr LIT -0.06..+0.38. Nothing adopted.
> Write-ups: [[popular-ict-2026-11-23|Popular ICT / SMC strategies on CME NQ, run exactly as taught]]


## Write-ups

| Date | Write-up | Verdict |
|---|---|---|
| 2026-11-26 | [[entry-fine-2026-11-26\|LIT entry refinement on 1m bars]] | research |
| 2026-11-25 | [[more-trades-2026-11-25\|More trades]] | research |
| 2026-11-24 | [[proedge-2026-11-24\|Pro / institutional edges]] | rejected |
| 2026-11-24 | [[lit-vix-downtrend-2026-11-24\|LIT in high-VIX falling markets]] | research |
| 2026-11-23 (night, run 2026-11-24 early ET) | [[four-pillars-2026-11-23\|The four pillars]] | research |
| 2026-11-22 | [[rapid25-slot-2026-11-22\|Rapid 25K slot]] | rejected |
| 2026-11-22 | [[plan-ranking-2026-11-22\|Plan ranking]] | research |
| 2026-11-22 | [[one-account-book-2026-11-22\|One account, combined book]] | research |
| 2026-11-22 | [[edge-d-meta-2026-11-22\|Edge hunt lane D]] | rejected |
| 2026-11-21 | [[live-vs-model-2026-11-21\|Live vs model, every real trade so far]] | info |
| 2026-11-21 | [[holidays-2026-11-21\|Thanksgiving week, roll weeks, Dec 15]] | rejected |
| 2026-11-20 | [[skeptic-atlas-streak-2026-11-20\|Skeptic check of Decide card atlas-funded-streak-1micro]] | research |
| 2026-11-20 | [[regime-guard-2026-11-20\|Regime guard]] | rejected |
| 2026-11-20 | [[lit-eval-rescue-2026-11-20\|Zlarior eval rescue]] | rejected |
| 2026-11-20 | [[lit-edge-2026-11-20\|Zlarior]] | rejected |
| 2026-11-20 | [[atlas-costs-split-2026-11-20\|ATLAS with split costs]] | info |
| 2026-11-19 | [[one-account-combo-redteam-2026-11-19\|Red team]] | research |
| 2026-11-19 | [[one-account-combo-final-2026-11-19\|One account, Zlarior + ATLAS on the Builder 50K]] | research |
| 2026-11-19 | [[one-account-combo-2026-11-19\|ONE account, several bots]] | research |
| 2026-11-19 | [[lit-more-money-2026-11-19\|Zlarior]] | rejected |
| 2026-11-18 | [[zeus-lab-lit-ideas-2026-11-18\|ZEUS Lab]] | rejected |
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

... and 79 older (see the families).

## Links

- Account: [[Account Zlarior]]
- [[ZEUS Lessons]] · [[ZEUS Decisions]] · [[ZEUS Home]]
