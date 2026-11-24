---
tags:
  - zeus/strategy
  - bot/atlas
  - market/nq
type: "strategy"
key: "atlas"
---

# ATLAS

> [!abstract] The second-strategy team next to LIT (engine/second.py): each member is its own rule; ATLAS trades them on its own account.
> Second strategies next to LIT (engine/second.py computes signals only). "route": false (default) = paper; "route": true = the PC bot routes it to its own account next to LIT (engine/live.py: LIT first, one position at a time, max 2 trades a day, eval-safe size). Switch: python -m engine.second --route <key> on|off. Cloud-only strategies are never routed. Switch one off: "on": false. "candidate": true = a candidate ATLAS member (stop-hunt research, research/writeups/stophunt.md): paper only, never routed, not on account B.

## Members

- [[ATLAS member EMA (ema_lon_vix)|London EMA trend pullback]]: ON
- [[ATLAS member LIT+Asia (lit_asia)|LIT + Asia slot (paper shadow)]]: ON
- [[ATLAS member MACD (macd_sweep)|MACD divergence at a liquidity sweep]]: ON
- [[ATLAS member Asia hunt (sh_asia)|Asia resweep hunt]]: ON
- [[ATLAS member Trend hunt (sh_trend)|Trend inducement hunt]]: ON
- [[ATLAS member S-R (sr_nyreclaim)|NY sweep-and-reclaim of the day's levels (S/R)]]: ON

## Performance by period

| Period | Trades | Per week | Win | PF | Net | Per month | Max DD |
|---|---|---|---|---|---|---|---|
| Jan-Jun 2026 (picked on) | 112 | 4.38 | 54.5% | 3.02 | +$25,737 | +$4,223 | -$1,533 |
| Jul-Oct 2026 (check) | 51 | 3.27 | 56.9% | 2.73 | +$8,228 | +$2,215 | -$1,224 |
| 2026 all | 163 | 3.96 | 55.2% | 2.94 | +$33,966 | +$3,463 | -$1,533 |
| 2021-25 (reference) | 1125 | 5.25 | 37.2% | 1.09 | +$15,162 | +$297 | -$12,430 |

_From research/anatomy/explain.json (costs in)._

### Trades by month

| Month | Source | Trades | Net $ |
|---|---|---|---|
| [[Month 2026-01\|2026-01]] | backtest | 22 | -$619 |
| [[Month 2026-02\|2026-02]] | backtest | 23 | +$20,161 |
| [[Month 2026-03\|2026-03]] | backtest | 18 | +$7,956 |
| [[Month 2026-04\|2026-04]] | backtest | 23 | +$5,644 |
| [[Month 2026-05\|2026-05]] | backtest | 18 | +$9,577 |
| [[Month 2026-06\|2026-06]] | backtest | 14 | +$11,450 |
| [[Month 2026-07\|2026-07]] | backtest | 12 | +$6,332 |
| [[Month 2026-08\|2026-08]] | backtest | 18 | +$2,272 |
| [[Month 2026-09\|2026-09]] | backtest | 17 | -$219 |
| [[Month 2026-10\|2026-10]] | backtest | 10 | +$5,233 |
| [[Month 2026-11\|2026-11]] | live | 3 | +$1,510 |

_backtest = the bot's rules replayed on futures data (costs in); paper / live = what the bot really did._

## Why it wins and loses

- Jan-Jun 2026: 51 losing trades cost -$12,724: never worked 60%, worked then turned 31%, shaken out then went our way 7%, news 2%.
- Jul-Oct 2026: 22 losing trades cost -$4,746: never worked 50%, worked then turned 50%, shaken out then went our way 0%, news 0%.
- 2021-25: 707 losing trades cost -$171,071: never worked 56%, worked then turned 36%, shaken out then went our way 7%, news 1%.
- Stops are mostly real, not wicks: a stop 50% wider would have reached the target first on 8.7% / 0.0% / 7.1% of stop-outs (Jan-Jun / Jul-Oct / 2021-25); the median stopped trade was only +0.29R our way at best and was out in 30 min (Jan-Jun).
- A careful-human skip list (against both trends / late / news within 30 min / prior-day level under 1R ahead) flags 37% of the losing $ but also 48% of the winning $ (Jan-Jun): skipping them = -$13,732 Jan-Jun, -$2,570 Jul-Oct, +$5,716 in 2021-25.
- Why winners win (Jan-Jun): the best 20% of winners made +$22,380 (87% of the net); the median winner went only 0.33R against us first and took 100 min; 67% of winners came on days that closed our way (losers 50%).
- Hindsight, not a rule: on days that closed our way the trades made +$21,380 / +$7,881 / +$79,693, on days that closed against us +$4,628 / +$347 / -$64,486 (Jan-Jun / Jul-Oct / 2021-25). The day's direction is only known after the close.
- Known at the entry, nothing separates losers from winners better than chance: 12 of 90 fact buckets were worse (or better) in all three periods, vs 15.7 on average with the results shuffled (p 0.781).

## Tested and rejected

> [!failure]- 2026-11-22 Regime guard round 3
> (research/regime/guard3.py, regime-guard3-2026-11-22.md): shadow-setup hit rate R1, intraday variance ratio R2, trend-day share R3, thin volume R4, NQ-VIX co-movement R5, 2-of-5 vote R6; half / out; LIT and ATLAS. **0 of 22 pass, all fail the stage-0 kill-gate.** R1 sweeps pay worse in 2026 than in 2021-25 (flags 2026 87.5/80.8% vs OLD 70.4%). R5 flags LIT's best days. Best placebo 47.5% / 68.5% (95 needed). Closes the regime lever for market-weather and market-wide sweep signals, not every possible signal. ATLAS funded baseline moved 8.5/9.2/94.5 -> 8.2/8.3/94.2 because of a code change after 153552591; verdict unaffected.

> [!failure]- ATLAS edge at real fills
> 14 of 15 fail at 6 and 10 ticks on 60% and 40% sizing. Limit at the 5m open / 1-2 ticks better with a 1-2 min timeout (only ~52% fill, the runners are missed: funded $151-285 a month Jan-Jun-like vs $503), limit 2 min then market, the next 5m open, per leg +0 / +5 min (picked +0), drop EMA (-$301 a month Jul-Oct-like), EMA half size, the day stop after a loss (re-check at real fills), 3 losses -> 3 sessions off, a weekly cap at 35% of the room. Info only (1m bars, 2021-25 untestable): EMA +60 s, per-leg minute (MACD +1: Jul-Oct $436 vs $402). ES versions of the 3 legs (`tools/atlas_es.py`): PF 0.60-0.84 in 2026 at 3 ES ticks, all lose at 10. Passed: 2 losses in a row -> 1 micro (Decide ...
> Write-ups: [[atlas-edge-2026-11-20|ATLAS edge at real fills]]

> [!failure]- ATLAS real-fill fixes
> ATLAS's 3 real entries filled 10 / 12 / 16 ticks past the 5m open (market order 3-5 s after a 5m close, price still running our way). Judged at 6 AND 10 ticks a side vs today at the same cost (funded 25K, fixed view, 2026 halves + 2021-25): 0 of 6 pass. Limit at the open 5 min (misses 17-18% of 2026's trades = the runners, funded $550 -> $314 a month Jan-Jun at 6 ticks), limit 4 ticks worse (-$272), enter on the 1m close +60 s (Jul-Oct +$57, Jan-Jun -$75, 2021-25 untestable: no 1m bars), skip a signal bar > 2x its 20-bar median (skips 30%, good trades), member hours picked on Jan-Jun (Jul-Oct -$164: overfit), London pause before 08:00 ET (Jul-Oct $438 -> $74). Post-hoc, never eligible: ...
> Write-ups: [[atlas-fills-2026-11-20|ATLAS real fills]]

> [!failure]- Payday levers + cross-bot loss cuts
> judged on the FIRST PAYOUT date AND the chance of losing the account (today's balances, 1,000 same paths a market; Jul-Oct / Jan-Jun). 8 levers, 0 pass: ATLAS funded 40% of the room (first payout +5 / +5 days, paid by Jan 15 66 -> 58 / 84 -> 81%, lost 10.2 -> 5.8%: safer, later), ask at $1,000 (+2 / +4 days), ATLAS "need" funded size (-$91 / -$70 a month), 25K #2 40% + $300 cap (+5 / +2 days), Rapid ATLAS $150 (+6 / +3 days, -$198 / -$522) or $350 (lost in 6 m 28.9 -> 36.8%), Rapid LIT bank lane (eval lost first 8.4 -> 11.6% Jan-Jun), ATLAS on Zlarior's 50K NOW vs after the pass (nearest miss: sooner, eval deaths 26 -> 8% Jan-Jun, but 6-month lost 8.3 -> 9.7% and 2021-25-like 48 -> 63%). ...
> Write-ups: [[payday-plan-2026-11-20|Payday plan]]

> [!failure]- ATLAS more money
> 10 pre-registered ideas (14 variants) on the FUNDED 25K from today's $887 room (600 week-block paths, live stuck stop, costs in). Rejected: thin-room sit-outs (only MACD / EMA out while the room is under $300 / $500 / $700: Jul-Oct -$6 to -$63 a month, more lost or no-payout), no stuck stop + 40% of the room (first payout +3 / +7 sessions), ATLAS v2 hunts x0.5 on the funded account (+$51 / +$93 / +$18 a month but 4.5-4.7 trades a week, Jul-Oct lost 10.5 -> 12.2%, real-order Jan-Jun lost 0 -> 3.8%, Jan-Jun fixed $ down; fresh Oct 19 - Nov 19 hunts -1.1R / 0R), v2 as built (+ min_room $200: Jul-Oct lost 16.8%), Asia hunt only (Jul-Oct lost 18%), flat 3 min before CPI / jobs / FOMC (-$82 a ...
> Write-ups: [[atlas-more-money-2026-11-19|ATLAS more money]]

> [!failure]- Win / loss anatomy rules
> `tools/win_loss_anatomy.py`, ZEUS Lab kind `anatomy` + one atlas_tilt. 4 pre-declared single versions from the strongest findings of the per-trade anatomy, on the real backtests (costs in): Zlarior x1.25 on a pullback in the daily trend (prior close vs its 20-day SMA with the trade, 1h EMA 20/50 against; 15 + 6 trades) Jan-Jun +$349 / Jul-Oct -$6 a month at the LIT size (the Jul-Oct winners were 2-3 micro trades x1.25 cannot change), eval +$163 / +$130, flip p 0.08 / 1.0; Zlarior skip the careful-human checklist (against the daily AND 1h trend / the day already moved 1 daily ATR / big US release within 30 min / prior-day high-low under 1R ahead) -$412 / -$1,514 a month, 1.8 / 1.5 trades a ...
> Write-ups: [[win-loss-anatomy-2026-11-18|Why we win, why we lose]]

> [!failure]- Zlarior's two live evals together
> the 50K hole + the 25K #2 on ONE Monte Carlo (same paths, live sizing). ATLAS's zombie-eval rule on Zlarior (1-micro last bullet at 80% of the room + give up under $200): pair +$57 / +$51 a month only by killing evals (2-week fails 50K 4.9 -> 10.4 / 3.1 -> 6.9%, 25K 0 -> 8.1 / 0 -> 8.3%, both dead in 20 sessions 0.4 -> 16.3%); stagger (alternate full / half size per signal): -$80 / -$49 a month, 25K 2-week pass 48 -> 31%. Today both evals die together 0.3-0.4% within 20 sessions: the joint risk is waiting, not failing. Rejected.
> Write-ups: [[lit-ideas-2026-11-18b|Zlarior ideas night 2]]

> [!failure]- ATLAS funded 25K protective rules
> 17 pre-declared + 5 post-hoc on the funded 25K Monte Carlo WITH the live $100 stuck stop (600 paths, fresh start + today's -$113, real day order, fixed $250, random-timing controls): member pause on its own last 10 / 20 trades (PF < 1 -> paper / x0.5), size by the edge light (AMBER / RED x0.75 / x0.5 / paper, last-40 R-PF < 1.5 x0.5), day caps (stop after a loss, $275, $367, a third of the room), 30-40% of the room in a hole or always, skip the day after a losing day. 0 pass: caps / skips / light sizes cost $18-191 a month in Jul-Oct or slow the first payout; the member pause never acts in Jul-Oct (Jan-Jun +$9, 2021-25 stranded 94.5 -> 90.5%, random halving 93%); 40% of the room halves ...
> Write-ups: [[atlas-health-2026-11-18|ATLAS health]]

> [!failure]- ATLAS new members
> 29 pre-declared versions, 5m NQ RTH, stop 1 tick beyond structure, 2R or VIX-band target, $250 a trade, costs in: VWAP pullback with trend (8; all lose Jul-Oct), opening-drive continuation on a 1m trigger (8; 2021-25 = 5m proxy), prior-day value-area re-entry = 80% rule re-measure (1; stops too wide for $250), 15m Keltner squeeze (8; 0.1-0.4 a week), prior-day POC first touch (4). 0 hold H1/H2/2025/2021-24 (coin-flip 0). Picks as a 4th member on the funded 25K ($250 / 30% room): opening drive $541/$353 -> $578/$253 a month, no-pay 15 -> 34% Jul-Oct, 4.49/wk; POC $521/$279; with S/R out both ~-$90/mo. ZEUS Lab: atlas_member_* Rejected. Nothing changed.
> Write-ups: [[atlas-members-2026-11-18|ATLAS new members]]

> [!failure]- Regime guard
> VRP (RV20 > VIX), 1-year ATR20 / ER20 bottom-third, 2-of-3 vote, half / out for LIT + ATLAS: 0 of 8. None is more common in 2021-25 than 2026 (G1/G4 fire most in Jul-Oct); LIT's 2021-25 $ is made on the flagged days (+$2,065 -> -$1.8k..-$5.9k). Post-hoc lead: ATLAS worse on chop days in all 3 periods; out = ATLAS Jan-Jun -$4,746, funded 2021-25 lost 94.5 -> 85.7%. NQ/ES correlation not testable (ES daily from 2025-04).
> Write-ups: [[regime-guard-2026-11-20|Regime guard]]

> [!failure]- B-holds
> while ATLAS (account B) holds a trade, skip LIT's opposite entry instead of closing B (HEDGE). Both accounts 2026 +$52.3k -> +$53.6k, 2021-25 -$3.2k -> -$5.0k; ATLAS 25K 2-week pass H1 65.5 -> 60.5 (stuck 0.8 -> 3.4); 9 clashes in 2026, 35 in 2021-25. Rejected: LIT priority stays.
> Write-ups: [[b-holds-vs-lit-priority|B-holds vs LIT priority]]

> [!failure]- BLITZ on its own 25K, "like a person"
> as account C (never opposite LIT / ATLAS, closed first; costs $0 in 2026, $16/mo at $150 in 2021-25): structure stops (last 1m / 5m swing, the move's low, caps; 45), liquidity targets / partials / swing trails / change-of-character exits / no clock (1,920), opening drive, London band, retest limits, 15m / 1h BOS filters (32), funded-only structure rule: none beats today's rule in H1, H2 and 2021-25. 25K size: 40% of the room, 100% from eval session 5 (decided in 2 weeks 71-74% vs 29-41%, same money: slot $270 / $37 / -$40 a month; random directions make the same H2 slot $). The post-hoc 1.0 x ATR / 45 min / no trail variant is worse on LIT's 50K too (H2).
> Write-ups: [[blitz-25k|BLITZ on its own MFFU Builder 25K]]

> [!failure]- ATLAS funded 25K day limit
> eval unchanged, funded max 1 a day: slot $ H1 / H2 / 2021-25 $454 / $275 / -$3 a month vs today's $568 / $382 / -$2, below a random-1-a-day control ($541 / $361); the H1 pick max 3 (= max 4) is +$44 H1, $0 H2 on 4 seeds. Keep 2 a day. Funded-only VIX band per member: no member loses in any H1 VIX tercile, so nothing to skip (`atx_funded_vix.json`). Funded half off at 0.75 / 1 / 1.5R + BE runner: H1 slot $336 / $366 / $414 vs $568 (runs `atxd_partial_*`): rejected. Funded re-entry after a stop-out (same setup once more, same direction): slot H1 $404 / H2 $257 / 2021-25 -$15 vs $568 / $382 / -$2, inside a coin-flip-direction control (run `atxd_reentry_1r`): rejected.
> Write-ups: [[atlas-funded-one-a-day-2026-10-31|ATLAS funded 25K]]

> [!failure]- ATLAS + BLITZ edge night
> - BLITZ trend-day SIZE (range so far, first-hour range / volume, overnight range / open's place in it, gap, VIX change, 2-sigma excursion, VWAP side / distance, held at the previous check, time; 430 tilts): 39 survivors vs 36 on shuffled facts = chance. - BLITZ + a 10:30 check: H1 25K slot $270 -> $54. - BLITZ in-day streak size (2026-10-31, `blitz-streak-size-2026-10-31.md`, `tools/bzx_streak.py`, run `bzx_streak`): eval size x m after a same-day BLITZ loss / win (7 cells, 10 shuffled controls). H1 pick x0.5 after a loss: slot $286 / $53 / -$40 a month vs today $286 / $52 / -$39; 2021-25 no better than shuffled (after-loss trades are the BETTER ones there). - BLITZ cold-streak size on its ...
> Write-ups: [[atlas-blitz-edge-2026-10-30|ATLAS + BLITZ edge night]], [[blitz-streak-size-2026-10-31|BLITZ in-day streak size]]

> [!failure]- Rapid EOD levers
> on LIT + ATLAS $500 Rapid EOD 50K: eval give-up / re-buy (room < $500-1,000, session > 30/45, 30%-rule need > $3-4k: +$12-104/mo = noise, 2021-25 worse), eval day caps (none, stop at +$500/+$700, balance-aware guard: today's 30% size guard is best), Asia slot at LIT size (funded lost 9.4% / 2.0% / 27.3%), fixed $1,000 payout requests, different mixes per account for more $ (identical copies pay more in both halves; different mixes only cut the no-pay risk): rejected. Lead: keep a $1,000 funded cushion.
> Write-ups: [[rapid-levers-2026-11-16|Rapid EOD 50K levers]]

> [!failure]- ATLAS deep edge
> loser autopsy (member, side, hour, stop pts / ATR / vs the member's median, target R, daily trend, VIX, LIT's day, the members' paper day) finds no trade bucket that loses in all spans except the known 06:00 / 11:00 hours. Rejected (16 variants): skip / halve after LIT won the other side (slot +$19 / +$29, but 4 H2 trades worth -0.05R; random same-size skips pass the 2026 test 6.7% of draws = chance), same-side retry skip (retries are the best bucket) or x1.25 / x1.5, skip while LIT holds / after LIT won the same side, stop > 1.6x / 2x the member's median, first trades at x0.5 / x0.75 until green, eval weekly brake $400 / $600, daily-trend skip / halve, one signal per side a day. The one ...
> Write-ups: [[2026-11-15-atlas-deep|ATLAS deep edge]]

> [!failure]- E3 same edge, more markets
> live LIT and the 3 ATLAS members unchanged on ES1! as MES (points x 0.28, BE 0.75 ES pts; ES = 5m only, 2025-04+, no 1m, no 2021-24), each on its own MFFU eval. ES LIT H1 -$3.8k / H2 +$12.7k / 2025 -$15.9k (NQ 5m-exec +$6.6k / +$1.5k / -$0.5k), 50K 2-week 27.7/10.9 and 44.9/15.9, corr LIT 0.14. ES ATLAS -$6.3k / +$2.2k / -$2.8k (NQ ATLAS +$47.3k / +$12.1k / +$13.0k): positive before costs, but costs are 7-13% of R on ES vs 2.5-5% on NQ (same tick, ~0.19x the points). NQ LIT NY-only slot as its own account +$12.8k / -$1.2k / -$2.6k at 1/wk; ES London / NY slots lose a span. Asia not redone. Nothing adopted; the 2nd stream stays NQ ATLAS.
> Write-ups: [[es-and-sessions-2026-11-13|Same edge, more markets]]

> [!failure]- Learn loop first night
> Zlarior size x1.25 on low dealer gamma / after a tight Asia range / on a many-times-touched or an old swept level / on a fast fill after the CISD, x0.75 the day after a VIX jump; ATLAS x1.25 after Zlarior was stopped on the other side, x0.5 on a two-way day: all 8 rejected (best: old level +$138 / +$125 a month at the LIT size but eval path Jul-Oct -$34). The loop re-checks them on new bars.

> [!failure]- edge2
> 10 pre-registered. ATLAS deep limits 8 / 16 ticks better for 15 min: fill 38-45%, miss $22-39k of winners, funded $ halves. ATLAS stop entry +12 ticks / 5 min (A3): H1 funded $511 -> $631, lost 16 -> 3%, 2021-24 PF 0.80 -> 0.99, but H2 $401 -> $398 / 20.7 -> 23.5% and 2025 6t -$74/mo: fails (PAPER LEAD - skipped signals lose every year, -0.22..-0.66R); +20 ticks / 10 min worse in H2. New NQ setups at $250: IB failed-break fade, IB break-retest limit, prior-day level break-retest limit, opening gap fade to the prior close, first-hour trend at 10:30 (+$45 / +$197 / +$121 a month, PF 1.08 H1, 0.5/wk H2), overnight-inside breakout: none PF >= 1.2 in all 3 periods; all add -$500 days on a ...
> Write-ups: [[edge2-2026-11-21|edge2]]

> [!failure]- Holidays / roll / FOMC windows
> Thanksgiving week, CME roll-date week, Dec 15 - Jan 5, FOMC days x sit out / half, LIT and ATLAS (LIT roll = already rejected): 0 of 14. 2021-25 windows all weak (LIT PF 0.14-0.89, ATLAS 0.51-0.75 vs ~1.1) but 2026 windows profitable (FOMC LIT +$634/trade, ATLAS roll PF 8.9): sit-outs lose Jan-Jun $ (LIT FOMC -$2,535, ATLAS roll -$2,985). Thanksgiving / late Dec have no 2026 sample (untestable). Nearest: ATLAS FOMC out (funded lost down in all 3, but Jan-Jun fixed -$1,223).
> Write-ups: [[holidays-2026-11-21|Thanksgiving week, roll weeks, Dec 15]]

> [!failure]- Rapid 25K slot
> one engine at real fills (rank.py): ATLAS only $707 / $141 a month vs today's LIT + ATLAS $1,883 / $800 (rejected again); bank lane = card rapid25-lit-bank NO (eval fail 0.5 -> 3.1%); a Rapid EOD 50K in the slot $5,001 / $2,281 a month but 2021-25 -$560 vs -$300 and eval fail 2.5 / 4.6% vs 0.3 / 2.4%: fails the pre-set safety bar (already on cards buy-rapid50-now / plan-rapid50k-max2-rebuys). Today's lanes stay.
> Write-ups: [[rapid25-slot-2026-11-22|Rapid 25K slot]]

> [!failure]- One-account combined book
> 13 books x 4 MFFU accounts (+ today = 53) on rank.py at real fills: first-come, LIT-priority 50% day budget, ATLAS NY-only / London-only / strict windows, ATLAS x0.5 eval, LIT eval then both funded, LIT x0.75 / x0.5, + BLITZ $300, ATLAS lane x2. Pick (Jan-Jun, eval fail <= LIT + 2 pts): Rapid EOD 50K LIT + ATLAS, LIT x0.5 in the eval $4,918 / $2,204 / -$88 a month vs today's 2 accounts $981 / $857 / -$62; paired 2021-25 -$156 (SE $32), 2022 -$781, Jul-Oct without ATLAS's 5 best days +$114 (SE $136): fails the 2021-25 bar, no card. Every mixing trick makes less than plain first-come in Jul-Oct (-$60 to -$1,352/mo); the gain is the Rapid 50K account (open card plan-rapid50k-max2-rebuys). ...
> Write-ups: [[one-account-book-2026-11-22|One account, combined book]]


## Write-ups

| Date | Write-up | Verdict |
|---|---|---|
| 2026-11-23 (night, run 2026-11-24 early ET) | [[four-pillars-2026-11-23\|The four pillars]] | research |
| 2026-11-22 | [[rapid25-slot-2026-11-22\|Rapid 25K slot]] | rejected |
| 2026-11-22 | [[plan-ranking-2026-11-22\|Plan ranking]] | research |
| 2026-11-22 | [[one-account-book-2026-11-22\|One account, combined book]] | research |
| 2026-11-21 | [[live-vs-model-2026-11-21\|Live vs model, every real trade so far]] | info |
| 2026-11-21 | [[holidays-2026-11-21\|Thanksgiving week, roll weeks, Dec 15]] | rejected |
| 2026-11-21 | [[edge2-2026-11-21\|edge2]] | rejected |
| 2026-11-20 | [[skeptic-live-patches-2026-11-20\|Skeptic check of the two live sizing patches]] | research |
| 2026-11-20 | [[skeptic-atlas-streak-2026-11-20\|Skeptic check of Decide card atlas-funded-streak-1micro]] | research |
| 2026-11-20 | [[regime-guard-2026-11-20\|Regime guard]] | rejected |
| 2026-11-20 | [[atlas-risk-real-fills-2026-11-20\|ATLAS funded 25K at real fills]] | finding |
| 2026-11-20 | [[atlas-fills-2026-11-20\|ATLAS real fills]] | finding |
| 2026-11-20 | [[atlas-edge-2026-11-20\|ATLAS edge at real fills]] | rejected |
| 2026-11-20 | [[atlas-costs-split-2026-11-20\|ATLAS with split costs]] | info |
| 2026-11-19 | [[one-account-combo-redteam-2026-11-19\|Red team]] | research |
| 2026-11-19 | [[one-account-combo-final-2026-11-19\|One account, Zlarior + ATLAS on the Builder 50K]] | research |
| 2026-11-19 | [[one-account-combo-2026-11-19\|ONE account, several bots]] | research |
| 2026-11-19 | [[atlas-more-money-2026-11-19\|ATLAS more money]] | adopt-candidate |
| 2026-11-18 | [[win-loss-anatomy-2026-11-18\|Why we win, why we lose]] | finding |
| 2026-11-18 | [[setup-grade-2026-11-18\|Setup grade]] | rejected |
| 2026-11-18 | [[atlas-members-2026-11-18\|ATLAS new members]] | rejected |
| 2026-11-18 | [[atlas-health-2026-11-18\|ATLAS health]] | rejected |
| 2026-11-17 | [[rapid-25k-vs-50k-2026-11-17\|MFFU Rapid EOD 25K vs Rapid EOD 50K for LIT + ATLAS]] | research |
| 2026-11-17 | [[payout-policy-funded25-2026-11-17\|Funded Builder 25K payout policy]] | adopt-candidate |
| 2026-11-17 | [[funded25-lit-atlas-2026-11-17\|ATLAS's funded Builder 25K]] | research |
| 2026-11-17 | [[drift-switch-2026-11-17\|"Edge stopped working" switch]] | rejected |
| 2026-11-17 | [[builder25k-eval-sizing-2026-11-17\|Eval sizing for a FRESH MFFU Builder 25K]] | adopt-candidate |
| 2026-11-17 | [[atlas-revive-2026-11-17\|ATLAS revive]] | research |
| 2026-11-16 | [[stack-one-account-2026-11-16\|More strategies on ONE MFFU account]] | promising |
| 2026-11-16 | [[builder-levers-2026-11-16\|Three MFFU Builder levers for money sooner]] | adopt-candidate |
| 2026-11-15 | [[2026-11-15-atlas-deep\|ATLAS deep edge]] | adopt-candidate |
| 2026-11-13 | [[es-and-sessions-2026-11-13\|Same edge, more markets]] | rejected |
| 2026-11-04 | [[2026-11-04_second_strategies_night\|Second strategies night]] | research |
| 2026-11-04 | [[2026-11-04_lit_ideas_night\|LIT ideas night]] | rejected |
| 2026-11-04 | [[2026-11-04_atlas_round3\|ATLAS round 3]] | research |
| 2026-11-03 | [[2026-11-03-slippage\|How much slippage each bot survives]] | info |
| 2026-11-03 | [[2026-11-03-fates\|FATES]] | info |
| 2026-10-31 | [[atlas-funded-one-a-day-2026-10-31\|ATLAS funded 25K]] | rejected |
| 2026-10-30 | [[discretion-score-2026-10-30\|Discretion score for ATLAS and BLITZ]] | rejected |
| 2026-10-30 | [[blitz-edge-2026-10-30b\|BLITZ edge, rounds 2-4]] | rejected |

... and 26 older (see the families).

## Links

- Account: [[Account ATLAS]]
- [[ZEUS Lessons]] · [[ZEUS Decisions]] · [[ZEUS Home]]
