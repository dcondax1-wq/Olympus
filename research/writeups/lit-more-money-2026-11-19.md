---
title: Zlarior (LIT) more money - 9 pre-registered ideas in 2 batches (ES filler, breakeven, fills, bias, news, through-the-trade, ES vs NQ SMT) + why live missed trades
family: other
date: 2026-11-19
status: rejected - 0 of 9 pass; nothing changes in the bot; one live-audit fix proposed (not applied)
summary: Owner - "improve all of our strategies, there's things we can do to make more". After reading the tested-and-rejected list (about 2,000 LIT variants already), 9 genuinely new single versions were written down and committed before any run, in two batches (batch 2 = the owner's added scope - fills, bias, news, managing through the trade, ES vs NQ). Each was scored on the real live LIT trades, costs in, at the LIT size, on the live Builder 50K eval path (two_week, room 0.4 to session 80) and on the funded 50K, picked on Jan-Jun 2026 and checked on Jul-Oct, 2021-25 not worse, 2-4 trades a week, week-block bootstrap. None passes. The live bot's "missed" days are mostly not missed trades - one real miss (Oct 26, $0), one order refused for a wrong account name (Oct 27, fixed, it saved ~$965), one trade that WAS taken (Oct 28, the audit could not see it), one unknown (Nov 3); two more real misses on Nov 10-11 while the PC was silent. All of them lost money in the backtest.
runs: tools/lit_more_money.py run (research/lit/more_money.json, research/lab/lit_more_money.json); designs research/lit/more_money_design_batch1.md, research/lit/more_money_design_batch2.md; tools/live_gap_proposal.py + tests/test_live_gap_proposal.py
---

# Zlarior more money (2026-11-19)

## For the owner (one minute)

**Nothing found that makes more money in both halves of 2026. Zlarior stays exactly as it is.** 9 new ideas, each one fixed
version written down before it was run. $ a month at the Zlarior size rule, costs in (today: **$5,562 Jan-Jun, $2,670
Jul-Oct, $25 in 2021-25**). "Funded" = what a funded Builder 50K pays you a month (today $929 / $915).

| Idea | Jan-Jun $/mo | Jul-Oct $/mo | 2021-25 $/mo | Funded 50K $/mo | Verdict |
|---|---:|---:|---:|---:|---|
| Extra ES (S&P micro) trades on days Zlarior has not traded yet | $4,478 | $3,026 | -$66 | $642 / $639 | No: more trades (4.5 a week), less money |
| Breakeven later on far targets, sooner on near ones | $5,194 | $2,429 | $209 | $931 / $854 | No |
| Limit order at the signal candle's close instead of market | $5,554 | $2,583 | $26 | $917 / $885 | No: same price on average, misses the runners |
| NY trades only from London's cheap / expensive side (bias) | $5,482 | $2,770 | $51 | $935 / $993 | No: loses Jan-Jun |
| Big-news days: only setups after the release | $4,277 | $2,736 | $54 | $792 / $908 | No: -$1,284 a month Jan-Jun |
| Out when price falls back through the shift level | $4,738 | $532 | -$75 | $869 / $313 | No: cuts the winners |
| Out when ES breaks its own low/high first | $5,562 | $2,771 | $30 | $929 / $959 | No: never acted Jan-Jun, 4 trades Jul-Oct (watch) |
| Only setups where ES did NOT make the same low (SMT) | $150 | $937 | $61 | $17 / $364 | No: 1 trade a week |
| When ES held up (SMT), trade ES instead of NQ | $4,945 | $5,383 | $76 | $823 / $884 | No: +$2,713 Jul-Oct but -$617 Jan-Jun |

**Why the live bot "missed" Oct 26 / 27 / 28 and Nov 3:** it mostly did not. Oct 28 WAS traded (5 micros, -$437); the
checker just has no records before Nov 3. Oct 27's order was refused because the account name lacked an "R" (already fixed
in the bot; that miss saved ~$965). Oct 26 was a real miss during a bot / feed gap ($0 trade). Nov 3: no record. Two more
real misses came on Nov 10-11 while the PC was silent. Every backtest trade that did not reach the account lost money or
scratched (Nov 3, +$28, is unknown), so the misses cost $0 so far, by luck. **Next for you: nothing.** The fix for the checker is a proposal for Claude's lead.

## Why live missed trades (job d)

The backtest twin on today's bars (data/NQ_*.csv, PC bars after Oct 16), from the eval start (Oct 19), Zlarior size rule:

| Day | Twin trade | What really happened | Evidence |
|---|---|---|---|
| Oct 26 08:37 | short, breakeven, +$0.6 | NOT routed: the model entered during a bot / feed gap | engine/live.py: "a missed 08:37 BE trade booked +$0.10 on the 50K at 23:08 ET 2026-10-26" |
| Oct 27 06:12 | short, stop, -$137 (live size: SELL 7 = -$965) | NOT on the account: every MFFU order went to an account Name without the "R", NinjaTrader refused it | engine/ninjatrader.py `_nt_said_no_account`, engine/live.py `_void_refused_days` (fixed; the -$965 booked was voided) |
| Oct 28 03:43 | short, stop, -$348 | **TRADED**: 5 MNQ, -$437 | tools/web_public/trading/trades.json `live.lit.2026-10-28_0343_short` |
| Nov 3 15:39 | long, end of day, +$28 | unknown: no PC record; the bot was re-set up and re-armed by hand 20:51-21:06 ET that evening | heartbeat remote / autopilot events |
| Nov 10 03:33 | long, stop, -$231 | NOT on the account | balance $49,313.54 (Nov 6) -> $49,192.78 (Nov 17) = only Nov 16's loss |
| Nov 11 03:56 | short, 15-minute cut, -$42 | NOT on the account | same; PC silent Nov 7-17 (report task never installed, no auto-update) |
| Nov 16 06:16 | long, stop, -$129 | **TRADED**: 1 MNQ, -$129.40 | data/pc_days 2026-11-16 trade rows |

- **The checker's bug (engine/fill_audit `_pc_on` / `_miss_reason`):** a day before the PC's own first record (its
  logs/exec_audit store and trade rows start Nov 3-6) has no uptime sample and no ledger row, so it is called
  "missed: PC bot off (no record of the bot that day)", even for Oct 28, which was traded. **Proposal (not applied, live
  code untouched):** `tools/live_gap_proposal.classify` - such a day is "unknown: before the PC's records start, check the
  broker statement", left out of the missed count and the missed $. `tests/test_live_gap_proposal.py` (12/12) pins today's
  verdict on the Oct 28 case and the proposal; area `nq`.
- **Proposal 2:** the PC's daily ntfy zip (engine/datafeed.py) carries bars + trade rows only, so a real miss like Nov 10-11
  cannot be explained from the cloud. Add the day's "NOT routed: ..." lines and uptime samples (logs/exec_audit/notes.json,
  a few KB) to it.
- **Money view:** since the eval started 2 of 7 backtest trades reached the account. At Jul-Oct's rate (about $250 a
  trade at the Zlarior size) every missed trade costs about $250 on average; the 4 that did not reach the account happened
  to be losers (-$410 at the Zlarior size; Oct 27 alone was -$965 at the eval size). Keeping the PC on and reporting is
  worth more than any idea below.
- The balance moved -$707 since the eval start; the two live trades explain -$566; the other -$141 cannot be tied to a
  trade from here (an early breakeven scratch and fees are the likely rest).

## Batch 1 (the lead's list: more trades, sessions / levels, exits)

Read first and NOT redone: Asia slot / all hours / re-arming, extra levels (Monday, 10/20-day, quarterly, weekly), flat
time 15:55 -> 16:25 / 16:55 (a do-nothing knob), every breakeven trigger already tried (0.75-1.5R, off, on a close, by ATR
/ points), time / NY-open / news / stall / lunch exits, ES alone and "NQ + ES first fill wins". Two ideas were left:

1. **ES filler** (MES micros on the same account, E3's fixed scaling: stops 2.25-22.5 ES pts, breakeven +0.75 ES pts, ES
   has 5m bars only). NQ keeps priority, trade for trade unchanged; ES may open only while NQ has not traded yet that day;
   an NQ entry closes an open ES trade first (31 of 131 ES trades). Trades go from 3.1 / 2.6 to **4.5 / 4.5 a week**, but
   the ES trades lose: LIT size Jan-Jun -$6,607, Jul-Oct +$1,321, 2025 -$4,625; eval path -$9,739 / -$4,275, 2-week pass
   44.5 -> 43.7% / 39.1 -> 42.0%, median pass 11 -> 9 / 12 -> 7.5 sessions (faster, but less money); funded 50K
   $929 -> $642 a month; max DD -$2,196 -> -$3,450. Bootstrap: no edge (78% of resamples <= 0). **Rejected.**
2. **Breakeven tied to the target** (BE at clip(0.25 x planned target R, 0.5R, 2R)): LIT size -$2,240 / -$897, 2021-25
   +$9,390 (the only 2021-25 gain of the night: the old years liked a later breakeven); eval -$8,547 / -$450, 2-week pass
   44.5 -> 55.5% in Jan-Jun (more one-hit passes) but less money; funded $931 / $854. **Rejected** (both 2026 halves lose).

## Batch 2 (the owner's added scope: fills, bias, news, through the trade, ES vs NQ)

Also read first: 12 bias methods / 31 bias filters (0 pass), news exits / breakeven / tilts, 1m "trade is wrong" cuts,
SMT as a size tilt, the fill-model study, conditional pullback limits.

| # | Idea (one version) | LIT size change Jan-Jun / Jul-Oct / 2021-25 | Eval path change, 2-week pass / fail | Trades/wk | Bootstrap (share <= 0) |
|---|---|---|---|---|---|
| 1 | Fills: LIMIT at the 1m CISD close for one bar (1 tick through), else market | -$51 / -$326 / +$48 | -$2,156 / -$46; 44.5 -> 41.2 / 39.1 | 3.1 / 2.6 | 0.64 |
| 2 | Bias: NY setups only on London's discount side | -$488 / +$370 / +$1,318 | -$157 / +$333; = / = | 3.1 / 2.4 | 0.55 |
| 3 | News: Tier-1 days, only setups after the first release | -$7,829 / +$244 / +$1,495 | -$5,516 / +$2,421; 42.9 / 42.0 | 2.7 / 2.2 | 0.92 |
| 4 | Through: out on a 5m close back below the CISD level (and entry) before +0.5R | -$5,020 / -$7,945 / -$5,086 | -$6,295 / -$5,149; 49.6 / 24.6 | 3.1 / 2.6 | 0.99 |
| 5 | Through: out when ES closes beyond its own sweep-window extreme before +0.5R | $0 / +$374 / +$244 | $0 / +$1,586; = / = | 3.1 / 2.6 | 0.04 |
| 6 | ES vs NQ: keep only SMT setups (ES held) | -$32,987 / -$6,439 / +$1,837 | -$33,097 / -$5,792; 1.7 / 27.5 | 0.8 / 1.0 | 1.00 |
| 7 | ES vs NQ: SMT present -> trade MES instead of MNQ | -$3,760 / +$10,076 / +$2,615 | -$4,473 / +$3,661; = / = | 3.1 / 2.6 | 0.24 |

No 2-week fails anywhere (0.0% in every row, as today). In plain words:
- **Fills.** The two real Zlarior fills we have: Oct 28 short filled exactly at the model price (29,945.00), Nov 16 long
  filled 3 ticks worse than the model (27,799.50 vs 27,798.75). The backtest's market fill at the next bar's open + 1 tick
  is fair. A limit at the signal candle's close fills 112 of 119 times in 2026 (1 tick through), on average at the same
  price as today's market fill (0.01 pt; the close beats the open + 1 tick 64 times, loses 46). The 7 times it does not
  fill, price ran away on the best trades (+1.6R each, 11R in all) and the chase costs ~5 pts each. Checked too: the backtest fills a target on a
  touch; requiring 1 tick through it changes **0** trades (targets are not tick prices and price always went through).
- **Bias.** London's discount side changes 2-3 trades a half: noise; Jan-Jun loses.
- **News.** On big-news days the setups before the release are mostly London trades that work: skipping them costs
  Jan-Jun -$7.8k (12 trades changed).
- **Through the trade.** The shift-failure cut fires on 67 trades in 2026 and kills the winners that dip first (Jul-Oct
  $2,670 -> $532 a month). The ES-confirmation cut is the night's nearest miss: it never acted in Jan-Jun, cut 4 trades in
  Jul-Oct (+$374) and a few in 2025 (+$244). Too few to call; the gate needs both halves better. Watch only.
- **SMT.** ES did not make the same new low/high on only 22% of Zlarior's trades since 2025-04 (46 of 207). Keeping only
  those leaves ~1 trade a week. Trading ES instead on those days (30 trades in 2026) made +$10.1k in Jul-Oct but lost
  $3.8k in Jan-Jun at the LIT size (eval path -$4.5k / +$3.7k, funded $929 / $915 -> $823 / $884): it fails the pick half,
  and ES runs on 5m bars without the 15-minute check, so it is not like for like. Not a rule.

## Method

- Base = the live LIT trades (tools/lit_edge `ctx()["T"]`, 631 trades, 120 in 2026, = run lit_live). The executor
  `tools/lit_more_money.manage_v` with every option off reproduces all 631 trades (exit + points, `check`: 0 differ).
- Entry filters use the engine's `skip_keys` (a skipped setup leaves the day free for a later one, like the live loop).
- ES: data/ES_5m.csv 2025-04-14 .. 2026-10-16 only (no ES 1m), MES at $5 / ES pt = 2.5 MNQ points so the same $ sizing;
  slippage 1 ES tick = $1.25 a micro; commission as MNQ. 2021-25 for the ES ideas = 2025 only.
- Scoring: tools/lit_edge.evaluate (LIT size; back-to-back + fresh-start evals on the Builder 50K with the live two_week
  sizing, room 0.4 to session 80, $1.90 a micro; funded 50K 1,000-path Monte Carlo with the live funded sizing).
- Gate G1-G6 (design files): both 2026 halves better at the LIT size and on the eval path, 2-week fails not up, pass not
  down > 2 points, 2021-25 >= -$600, 2-4 trades a week, week-block bootstrap (5,000 draws, weeks resampled within each
  half) share <= 0 at most 0.10, funded not lower by > $10 a month. 0 of 9 pass all; the closest (ES-confirmation cut)
  fails G1/G2 (no change in Jan-Jun).
- **Ideas tried: 9** (batch 1: 2, batch 2: 7), plus 1 honesty check (target touch fills), not an idea.

## Files

- `tools/lit_more_money.py` (check / run / gap), results `research/lit/more_money.json`, Lab rows
  `research/lab/lit_more_money.json` (kind `lit_more_money`, all 9 rejected).
- Designs (committed before the runs): `research/lit/more_money_design_batch1.md`, `research/lit/more_money_design_batch2.md`.
- Live gap: `tools/live_gap_proposal.py`, `tests/test_live_gap_proposal.py`.
