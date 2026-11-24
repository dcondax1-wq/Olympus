---
title: "Stops x targets x TIME: smaller stops and take-profits from other timeframes, and TIME x PRICE"
family: stops
date: 2026-11-24
status: rejected
summary: "19 pre-registered variants on the exact live LIT trades (631, 120 in 2026, 1m fills). Tighter stops from the 1m CISD candle, the 1m entry swing and the 3m FVG cut the stop from ~44-52 pts to 7-22 pts, but at the same dollars at risk every one loses money in Jul-Oct ($8.3k-$14.0k less than live): 40-58% of trades get stopped and 28-41% of those stop-outs were live WINNERS (wicked out). Structure targets (15m / 1h liquidity, session highs, 1h FVG) and fixed 1.5 / 2 / 3R hit the target up to 2x as often but cut the big runners: all lose Jan-Jun by $8-25k. Time rules (N = 26 min, from Jan-Jun only) lose both halves. 0 pass; nothing changes. One lead: on the Rapid EOD 25K (30% best-day rule) a small fixed target passes evals where the band target cannot."
runs: tools/stops_targets_time.py (research/lab/stops_targets.json, research/lit/stops_time.json)
---

## In one minute

- **The question (owner, 2026-11-24):** our stops (~44-52 pts) and take-profits (the VIX band, up to 8R) feel too big. Can
  smaller ones, built from other timeframes, make more money? And what does TIME tell us?
- **The blunt answer: no.** A tighter stop makes each win bigger in R, but it kills the win rate, and the net is worse.
  - The tight stops get hit on **40-58%** of trades (live: 29-40%), and **3 to 4 in 10 of those stop-outs were trades the
    live stop went on to WIN** (wicked out by noise inside the sweep).
  - At the **same dollars at risk** as today, every tight stop loses money Jul-Oct ($8.3k to $14.0k less than live), and with
    a 2R / 3R target it also loses Jan-Jun.
  - The "tight stop makes a fortune" result (1m swing stop: Jan-Jun **+$75.3k**) only appears because the size rule then
    risks far more money a trade ($735 vs $279 in the 2026-10-18 test). At the same $: Jan-Jun +$42.7k (+$8.8k vs live) but Jul-Oct +$1.6k (-$8.3k) and 2021-25
    -$21.7k (-$23.0k).
- **Smaller targets:** they hit up to 2x as often (fixed 1.5R: 44-45% of trades vs 19-25%), but LIT's money is a few big
  runners to the band. Every smaller target loses Jan-Jun by $8-25k. Closest: the 1h FVG target, Jul-Oct +$235 (noise,
  p 0.50), Jan-Jun -$10.0k. A fixed 3R makes more in 2021-25 (+$20.6k vs +$1.3k) but loses both 2026 halves (-$17.7k / -$2.7k):
  the same trade-off as the 8R bank.
- **TIME x PRICE:** LIT winners show +0.5R fast (median 10 min) but need **3 hours** to reach the target (median 180 min);
  stop-outs come in ~35 min. From Jan-Jun the pre-set rule picked **N = 26 min**. A time stop / tighten / time-breakeven at
  26 min loses money in BOTH halves ($1.2k to $8.5k less than live) and in 2021-25: slow starters still win often enough in
  Jul-Oct (no +0.5R after 30 min: 12% hit the target, avg +0.19R; Jan-Jun 10%, -0.10R).
- **0 of 19 pass. Nothing changes.** The hard rule "stop 1 tick beyond the sweep extreme" stays. No proposal to the owner.
- **One lead (not a pass):** on the **Rapid EOD 25K** (best day <= 30%, our day-win cap $427) the band target never passes in
  40 sessions in this model (0%), while a fixed 1.5R target passes 42% (Jan-Jun) / 8% (Jul-Oct) / 19% (2021-25). That is a
  question for the Rapid lane's own pre-registered test, not a LIT change.

## What was tested (pre-registered before the run, 19 counted)

Same live LIT trades and fills (the setups, the limit at the 5m CISD level, the 1m CISD confirmation); only what happens after
the fill changes. `check`: with every option off, the walk reproduces all 631 live exits and points (0 mismatches).

- **A. Tighter stops (3 stops x 3 targets = 9):** A1 1 tick beyond the **1m CISD candle** (the 1m bar whose close confirmed
  the entry); A2 beyond the **1m swing that formed the entry** (lowest 1m low from the tap to the confirmation; = the
  2026-10-18 "tap" stop, kept only as the control for the new targets, the wick count and the three accounts); A3 beyond the
  bottom of the newest **3m FVG** formed between the sweep extreme and the fill (none -> the live stop). Never wider than the
  live stop, at least 5 pts. Targets: the live target price, 2R, 3R of the new stop. BE at +1R and the 15-min check on the new
  stop. 2021-25 has no 1m bars: A1 / A2 run the same rule on 5m bars there (a proxy); A3 falls back to the live stop.
- **B. Targets from other timeframes, live stop (7):** the nearest level at least 1.5R and at most 8R away (else the live
  band), exit 1 tick in front: B1 untaken **15m** swing high (2 days), B2 untaken **1h** swing high (5 days), B3 untaken
  **opposing session high/low** (today's Asia, London, the previous day), B4 near edge of the unfilled opposing **1h FVG**
  (5 days); fixed **1.5R / 2R / 3R** controls. (Shorts mirror everything.)
- **C. TIME (3), N from the Jan-Jun distribution only:** N = the 80th percentile of minutes-to-+0.5R of Jan-Jun target winners
  = **26 min**. Pre-set condition for C1 (Jan-Jun trades with no +0.5R at N win < 15% and average < 0R): met (21 trades, 9.5%,
  -0.10R). C1 out at N without +0.5R; C2 stop to -0.5R at N without +0.5R; C3 stop to breakeven at N if in profit.
- **Sizing views:** risk-matched (the honest one: the live trade's $ at risk spread over the new stop, so more micros, max 40,
  weekly stop), the LIT rule as written, and the live eval two_week sizing (room 0.4) on each account.
- **Costs in:** $1.40 a micro round trip + 1 tick on stop / EOD / cut exits (evals $1.90). Targets fill at the price.
- **Gate:** both 2026 halves better (risk-matched $ AND the live 50K eval path), no more 2-week fails, 2+ trades/week, 2021-25
  not worse, and the Jul-Oct gain beats a paired bootstrap at p < 0.05/19 = 0.0026 (Bonferroni).

## Results: money (risk-matched; avg R = $ per trade / the live trade's $ at risk)

| Variant | stop pts (med) H1/H2 | target hit % H1/H2 | full stop % H1/H2 | avg R H1/H2 | PF H1/H2 | $/month H1 / H2 / 2021-25 | max DD H1/H2 | net vs live H1 / H2 / 2021-25 | H2 p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| LIVE (1 tick beyond the 5m sweep, VIX band) | 44.2 / 51.6 | 18.8 / 25.0 | 28.8 / 40.0 | 0.825 / 0.769 | 4.98 / 2.91 | $5,562 / $2,670 / $25 | $-2,196 / $-1,396 | - | - | baseline |
| A1 1m CISD candle stop, live target price | 7.0 / 7.2 | 6.2 / 5.0 | 46.2 / 55.0 | 0.652 / -0.165 | 3.21 / 0.79 | $4,062 / $-368 / $-199 | $-5,220 / $-3,116 | -9,143 / -11,286 / -11,399 | 0.9845 | rejected |
| A1 1m CISD candle stop, 2R | 7.0 / 7.2 | 27.5 / 20.0 | 46.2 / 55.0 | -0.009 / -0.26 | 1.19 / 0.6 | $351 / $-697 / $-438 | $-3,333 / $-3,458 | -31,760 / -12,507 / -23,605 | 0.9935 | rejected |
| A1 1m CISD candle stop, 3R | 7.0 / 7.2 | 16.2 / 10.0 | 46.2 / 55.0 | -0.028 / -0.316 | 1.12 / 0.37 | $212 / $-1,100 / $-288 | $-4,333 / $-4,516 | -32,608 / -14,005 / -15,949 | 0.9992 | rejected |
| A2 1m entry swing stop, live target price | 14.4 / 17.1 | 10.0 / 7.5 | 40.0 / 45.0 | 1.246 / 0.211 | 4.88 / 1.31 | $7,011 / $442 / $-425 | $-4,060 / $-3,290 | +8,831 / -8,276 / -22,958 | 0.9363 | rejected |
| A2 1m entry swing stop, 2R | 14.4 / 17.1 | 26.2 / 17.5 | 40.0 / 45.0 | 0.056 / -0.113 | 1.18 / 0.49 | $324 / $-715 / $-179 | $-3,330 / $-3,290 | -31,928 / -12,573 / -10,379 | 0.9982 | rejected |
| A2 1m entry swing stop, 3R | 14.4 / 17.1 | 22.5 / 12.5 | 40.0 / 45.0 | 0.177 / -0.089 | 1.48 / 0.59 | $869 / $-573 / $-291 | $-3,607 / $-3,290 | -28,607 / -12,046 / -16,113 | 0.9972 | rejected |
| A3 3m FVG stop, live target price | 15.2 / 21.9 | 11.2 / 7.5 | 42.5 / 57.5 | 1.208 / -0.141 | 5.26 / 0.7 | $7,611 / $-537 / $20 | $-3,543 / $-2,783 | +12,491 / -11,913 / -232 | 0.999 | rejected |
| A3 3m FVG stop, 2R | 15.2 / 21.9 | 33.8 / 22.5 | 42.5 / 57.5 | 0.148 / -0.133 | 1.62 / 0.75 | $1,104 / $-442 / $110 | $-3,076 / $-2,599 | -27,169 / -11,561 / +4,341 | 0.9895 | rejected |
| A3 3m FVG stop, 3R | 15.2 / 21.9 | 28.8 / 15.0 | 42.5 / 57.5 | 0.327 / -0.104 | 2.12 / 0.86 | $1,991 / $-260 / $411 | $-3,077 / $-2,599 | -21,765 / -10,885 / +19,730 | 0.976 | rejected |
| B1 next 15m liquidity | 44.2 / 51.6 | 30.0 / 35.0 | 28.8 / 40.0 | 0.311 / 0.448 | 2.46 / 2.17 | $2,045 / $1,642 / $259 | $-1,990 / $-1,047 | -21,434 / -3,822 / +11,978 | 0.8858 | rejected |
| B2 next 1h liquidity | 44.2 / 51.6 | 26.2 / 25.0 | 28.8 / 40.0 | 0.565 / 0.434 | 3.64 / 2.13 | $3,690 / $1,585 / $126 | $-1,990 / $-1,470 | -11,409 / -4,032 / +5,165 | 0.9978 | rejected |
| B3 opposing session high/low | 44.2 / 51.6 | 23.8 / 22.5 | 28.8 / 40.0 | 0.59 / 0.593 | 4.0 / 2.41 | $4,197 / $1,981 / $97 | $-1,990 / $-1,396 | -8,317 / -2,561 / +3,666 | 0.961 | rejected |
| B4 1h FVG | 44.2 / 51.6 | 20.0 / 30.0 | 28.8 / 40.0 | 0.584 / 0.663 | 3.8 / 2.95 | $3,921 / $2,734 / $190 | $-2,196 / $-1,047 | -10,003 / +235 / +8,449 | 0.5035 | rejected |
| B5 fixed 1.5R | 44.2 / 51.6 | 43.8 / 45.0 | 28.8 / 40.0 | 0.266 / 0.248 | 2.06 / 1.64 | $1,477 / $899 / $24 | $-2,009 / $-1,076 | -24,897 / -6,579 / -22 | 0.9637 | rejected |
| B6 fixed 2R | 44.2 / 51.6 | 32.5 / 37.5 | 28.8 / 40.0 | 0.29 / 0.327 | 2.34 / 1.8 | $1,874 / $1,127 / $115 | $-1,978 / $-1,047 | -22,479 / -5,732 / +4,608 | 0.957 | rejected |
| B7 fixed 3R | 44.2 / 51.6 | 25.0 / 27.5 | 28.8 / 40.0 | 0.373 / 0.484 | 2.91 / 2.38 | $2,665 / $1,936 / $404 | $-1,868 / $-1,047 | -17,659 / -2,729 / +19,383 | 0.8055 | rejected |
| C1 time stop: no +0.5R after 26 min -> out | 44.2 / 51.6 | 16.2 / 20.0 | 12.5 / 17.5 | 0.822 / 0.58 | 5.78 / 2.8 | $5,372 / $2,181 / $-175 | $-2,047 / $-1,526 | -1,160 / -1,819 / -10,208 | 0.8223 | rejected |
| C2 tighten: no +0.5R after 26 min -> stop to -0.5R | 44.2 / 51.6 | 17.5 / 22.5 | 12.5 / 17.5 | 0.81 / 0.614 | 4.76 / 2.45 | $5,223 / $2,171 / $-48 | $-2,399 / $-1,747 | -2,065 / -1,854 / -3,719 | 0.9127 | rejected |
| C3 time-BE: after 26 min in profit -> breakeven | 44.2 / 51.6 | 13.8 / 20.0 | 21.2 / 35.0 | 0.585 / 0.515 | 4.68 / 2.1 | $4,174 / $1,449 / $-247 | $-2,196 / $-1,796 | -8,457 / -4,535 / -13,895 | 0.9597 | rejected |

Win % in dollars is the same for every target of 1R or more (a trade that reaches +1R moves to breakeven and ends green either
way), so "target hit %" and "full stop %" are the honest columns. Trades/week are the live 3.12 / 2.56 for every variant
(no variant adds or removes trades). H2 p = paired bootstrap, share of resamples where the variant does not beat live in Jul-Oct.

## Results: eval odds (live two_week sizing, a fresh eval started on every session of the span)

| Variant | 50K 2-wk pass/fail H1 | H2 | 2021-25 | 50K 40-session pass H1/H2/21-25 | 25K 2-wk pass H1/H2 | 25K 40-s pass/fail H2 | Rapid 25K 40-s pass H1/H2/21-25 | days to pass 50K H1/H2 |
|---|---|---|---|---|---|---|---|---|
| LIVE (1 tick beyond the 5m sweep, VIX band) | 44.5/0.0 | 39.1/0.0 | 10.9/0.8 | 93.3 / 66.7 / 26.3 | 43.7 / 39.1 | 87.2/0.0 | 0.0 / 0.0 / 0.0 | 10.0 / 9.5 |
| A1 1m CISD candle stop, live target price | 21.8/0.0 | 29.0/0.0 | 10.5/0.9 | 64.0 / 87.2 / 22.8 | 21.8 / 29.0 | 64.1/0.0 | 0.0 / 0.0 / 0.0 | 12.0 / 13.0 |
| A1 1m CISD candle stop, 2R | 1.7/0.0 | 0.0/31.9 | 3.8/6.5 | 10.1 / 0.0 / 14.2 | 1.7 / 0.0 | 0.0/89.7 | 7.9 / 0.0 / 11.3 | 13.0 / None |
| A1 1m CISD candle stop, 3R | 11.8/4.2 | 0.0/29.0 | 8.6/5.7 | 21.3 / 0.0 / 17.4 | 11.8 / 0.0 | 0.0/89.7 | 0.0 / 0.0 / 8.4 | 8.0 / None |
| A2 1m entry swing stop, live target price | 40.3/0.0 | 42.0/0.0 | 11.9/1.1 | 71.9 / 69.2 / 23.6 | 40.3 / 42.0 | 64.1/0.0 | 0.0 / 0.0 / 0.0 | 9.0 / 7.0 |
| A2 1m entry swing stop, 2R | 10.1/0.0 | 4.3/0.0 | 4.0/2.3 | 31.5 / 17.9 / 14.9 | 10.1 / 4.3 | 17.9/0.0 | 19.1 / 0.0 / 8.5 | 19.0 / 21.0 |
| A2 1m entry swing stop, 3R | 23.5/0.0 | 15.9/0.0 | 6.6/3.1 | 55.1 / 53.8 / 18.2 | 25.2 / 15.9 | 35.9/0.0 | 43.8 / 0.0 / 3.7 | 11.5 / 15.0 |
| A3 3m FVG stop, live target price | 42.0/0.0 | 26.1/0.0 | 10.9/0.8 | 86.5 / 30.8 / 26.3 | 44.5 / 26.1 | 30.8/10.3 | 0.0 / 0.0 / 0.0 | 10.0 / 7.0 |
| A3 3m FVG stop, 2R | 16.0/3.4 | 11.6/8.7 | 8.2/1.1 | 41.6 / 12.8 / 27.9 | 10.9 / 7.2 | 7.7/10.3 | 33.7 / 0.0 / 13.8 | 12.0 / 7.0 |
| A3 3m FVG stop, 3R | 28.6/0.8 | 15.9/10.1 | 12.0/1.1 | 55.1 / 38.5 / 34.7 | 26.1 / 15.9 | 20.5/12.8 | 42.7 / 0.0 / 8.6 | 9.0 / 9.0 |
| B1 next 15m liquidity | 31.1/0.0 | 29.0/0.0 | 10.9/1.1 | 58.4 / 35.9 / 34.8 | 29.4 / 27.5 | 23.1/0.0 | 37.1 / 10.3 / 10.1 | 9.5 / 10.5 |
| B2 next 1h liquidity | 34.5/0.0 | 26.1/0.0 | 11.0/1.1 | 80.9 / 23.1 / 34.3 | 31.1 / 18.8 | 20.5/0.0 | 10.1 / 0.0 / 11.5 | 11.0 / 9.0 |
| B3 opposing session high/low | 39.5/0.0 | 31.9/0.0 | 13.0/0.8 | 70.8 / 28.2 / 30.8 | 37.8 / 31.9 | 20.5/0.0 | 4.5 / 0.0 / 6.1 | 8.0 / 8.5 |
| B4 1h FVG | 40.3/0.0 | 36.2/0.0 | 11.3/1.1 | 86.5 / 87.2 / 27.8 | 39.5 / 36.2 | 76.9/0.0 | 0.0 / 0.0 / 0.3 | 10.5 / 13.0 |
| B5 fixed 1.5R | 25.2/0.0 | 18.8/0.0 | 5.7/1.1 | 55.1 / 28.2 / 25.2 | 23.5 / 14.5 | 28.2/0.0 | 41.6 / 7.7 / 18.5 | 11.0 / 9.5 |
| B6 fixed 2R | 30.3/0.0 | 20.3/0.0 | 8.2/1.1 | 65.2 / 20.5 / 27.9 | 26.9 / 20.3 | 25.6/0.0 | 37.1 / 17.9 / 13.8 | 10.5 / 11.0 |
| B7 fixed 3R | 42.0/0.0 | 30.4/0.0 | 12.0/1.1 | 86.5 / 43.6 / 34.7 | 37.0 / 23.2 | 33.3/0.0 | 14.6 / 28.2 / 8.6 | 9.0 / 10.0 |
| C1 time stop: no +0.5R after 26 min -> out | 49.6/0.0 | 29.0/0.0 | 7.2/0.3 | 96.6 / 46.2 / 14.8 | 50.4 / 29.0 | 46.2/0.0 | 0.0 / 7.7 / 0.0 | 9.0 / 11.5 |
| C2 tighten: no +0.5R after 26 min -> stop to -0.5R | 50.4/0.0 | 29.0/0.0 | 8.7/0.3 | 95.5 / 43.6 / 19.5 | 49.6 / 29.0 | 51.3/0.0 | 0.0 / 0.0 / 0.0 | 9.0 / 11.0 |
| C3 time-BE: after 26 min in profit -> breakeven | 35.3/0.0 | 36.2/0.0 | 8.4/0.7 | 91.0 / 87.2 / 20.5 | 36.1 / 34.8 | 66.7/0.0 | 0.0 / 0.0 / 0.0 | 12.0 / 15.0 |

Builder 50K $91.80 (+$3,000, $2,000 trailing), Builder 25K $63 (+$1,500, $1,000 trailing, 20 micros), Rapid EOD 25K $97.20
(+$1,500, best day <= 30%, 4 days, our $500 soft day stop and $427 day-win cap, 20 micros: an approximation of the bot's own
caps). 2-wk = pass / fail within 10 sessions; 40-s = within 40 sessions.

## How often a tight stop gets wicked out

| Tight stop | stopped out % H1/H2 | of those, the live trade WON (wicked out) H1/H2 | LIT rule as written H1 / H2 / 2021-25 net |
|---|---|---|---|
| A1 1m CISD candle stop, live target price | 46.8 / 55.0 | 15 of 37 (40.5%) / 9 of 22 (40.9%) | +35,463 / -314 / -36,042 |
| A2 1m entry swing stop, live target price | 40.0 / 45.0 | 9 of 32 (28.1%) / 7 of 18 (38.9%) | +75,271 / +7,338 / -29,463 |
| A3 3m FVG stop, live target price | 41.1 / 65.6 | 9 of 30 (30.0%) / 8 of 21 (38.1%) | +64,853 / -6,626 / +801 |

The LIT-rule column is the trap: as written ($800 up to a 20-pt stop) a tight stop risks far more $ a trade, so Jan-Jun looks
huge. At the same $ at risk the edge is gone.

## TIME x PRICE (LIT, 1m days)

| | Jan-Jun (79 trades) | Jul-Oct (40) |
|---|---|---|
| minutes to target (25 / 50 / 75 / 90%) | 64 / 180 / 337 / 424 | 106 / 180 / 258 / 310 |
| minutes to stop (25 / 50 / 75 / 90%) | 16 / 33 / 73 / 110 | 16 / 40 / 60 / 148 |
| winners: minutes to +0.5R | 4 / 10 / 19 / 29 | 8 / 10 / 14 / 64 |
| winners: minutes to +1R | 10 / 22 / 50 / 68 | 17 / 37 / 100 / 194 |

No +0.5R yet after N minutes -> share that still hit the target / average R (trades):

| N min | 10 | 15 | 20 | 30 | 45 | 60 |
|---|---|---|---|---|---|---|
| Jan-Jun | 11% / +0.32R (53) | 10% / +0.28R (42) | 14% / +0.65R (28) | 10% / -0.10R (21) | 7% / -0.37R (14) | 0% / -0.61R (9) |
| Jul-Oct | 14% / +0.35R (28) | 9% / +0.02R (22) | 11% / +0.12R (18) | 12% / +0.19R (17) | 18% / +0.53R (11) | 25% / +1.10R (8) |

What it means: price proves itself first, time pays later. A LIT winner usually shows +0.5R within ~20 minutes, but its
target is hours away. Slow starters were weak in Jan-Jun and fine in Jul-Oct: a clock exit is a coin that flipped. The live
15-minute check already takes the clearly bad ones.

Other bots (hold time by result, runs atlas_base / blitz25k_today_acct_c): **ATLAS** winners are held a median 92 min
(Jan-Jun) / 52 (Jul-Oct), losers 38 / 12; trades closed in under 15 min win 8-33%, trades held 2h+ win 65-100% (2021-25
+1.47R a trade). **BLITZ** already has a ~31-35 min clock: exits under 15 min win 0-3% (stops), 30-60 min win 64-69%.
Neither shows a clock rule worth a new test.

## Verdict

- **REJECTED, all 19.** No stop, target or clock change beats live in both 2026 halves at the same $ risk; none comes near the
  Bonferroni bar (best Jul-Oct p 0.50, the 1h FVG target).
- **Keep:** stop 1 tick beyond the 5m sweep extreme, size follows the stop, the VIX band target banked at 8R, BE at +1R, the
  15-minute check.
- **Why bigger is right for LIT:** the sweep extreme is the real invalidation; anything inside it is noise that LIT's winners
  routinely trade through before running ~3 hours to the band.
- **Lead for later (Rapid lane only):** a pre-registered Rapid EOD 25K test of small fixed targets (1.5R / 2R) against the 30%
  best-day rule. Not adopted; not a LIT change.

Paper only. Nothing live changed; `live_model*.json` untouched. Re-run: `python -X utf8 tools/stops_targets_time.py all` (~1 min).
