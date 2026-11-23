---
title: Order-flow program - what pros use, what our bars can test, and 3 tick designs ready to run
family: research
date: 2026-11-23
status: 6 bar tests rejected; 3 tick designs pre-registered; tick import fixed (UTC) and made simple
summary: Ten order-flow topics pro NQ traders use are written up below as testable rules, each with the data it needs. Six new bar-data tests ran with pre-set rules and costs in. All six fail. The best near miss is a stand-alone LVN rejection (PF 1.26 / 1.10 / 4.56, placebo p 0.004, uncorrelated with LIT, but only 0.5-0.7 trades a week). Three tick designs are pre-registered and run by themselves at 60+ tick days. The tick importer had a real bug (NinjaTrader exports in UTC, the importer assumed New York time) that is now fixed and tested, along with a 9x faster streaming import and no loss of same-timestamp trades. LIT is unchanged and nothing was armed.
runs: research/orderflow/of_program.py -> research/orderflow/program_results.json; of_study.py prereg() (tick mode)
---

## Short answer

| What | Result |
|---|---|
| (A) 10 pro order-flow topics → testable rules | Below. **4 need ticks with bid/ask**, **3 need DOM / market-by-order** (we will never have those from NT history), **3 can be roughed out on bars** |
| (B) 6 new bar tests, pre-registered (committed before running), costs in | **0 pass.** Best: LVN rejection, a stand-alone. It made money in all 3 spans: +$11,556 in 2021-25, +$326 in 2026 H1, +$4,990 in 2026 H2. Placebo p 0.004, LIT correlation about -0.06. It fails on H1 PF 1.10 and on trade count: 0.5-0.7 a week |
| LIT add-ons on bars (delta divergence, delta confirmation, sweep volume, 1m absorption print, poor highs) | **All cost LIT money in 2026.** Skipping "refuted" trades cost -$15k to -$22k in H1. Those trades are LIT's *best* |
| (C) 3 designs for real ticks | OF1 sweep absorption (confirm/skip LIT), OF2 block prints against the trade (skip LIT), OF3 LVN rejection on a real tick profile (extra, uncorrelated trades). File: `research/orderflow/PREREG_ticks.md` |
| (D) Tick download | `TICKS_HOWTO.md`. **Bug fixed:** NT8 exports in **UTC**, but the importer assumed New York time. That would have shifted every tick 5 hours and quietly ruined every test |
| Live strategy | **Unchanged.** Nothing armed, no live_model file touched, branch only |

## A. The ten topics: what the edge claims and how to test it

**Data key:**
- **1m** = 1m bars with volume (have it, 2025-12 on).
- **T** = every trade with its size and the bid/ask at that moment (NinjaTrader tick history, about 12 months, free; see
  TICKS_HOWTO.md).
- **D** = order-book depth / market-by-order. We don't have it, and NT history doesn't give it. NT Market Replay holds some
  Level 2 depth for single days, which is heavy.

Trades/week are rough guesses for NQ RTH, one per day at most.

| # | Topic | What the edge claims | Exact testable rule | Data | Trades/wk |
|---|---|---|---|---|---|
| 1 | Footprint / bid-ask delta | The net of aggressive buys minus sells shows who is in control. A price move that the delta disagrees with is weak | Per 5m bar, delta = Σ size × side. Test: does the sign of the delta over the sweep bars of a LIT trade predict its R? (S1/S4 in of_study) | T (the bar proxy is weak) | LIT's 2-3 (filter) |
| 2 | Cumulative delta divergence | Price makes a new high but CVD doesn't, so buyers are exhausted (Valtos / Orderflows, Axia Futures) | At a new RTH high between 10:00 and 15:00, CVD since 09:30 is below its value at the previous RTH high. Fade at the next open, stop 1 tick past the high, 2R | T | 1-2 |
| 3 | Absorption / exhaustion prints | Heavy aggression at an extreme with no follow-through means passive size absorbed it, so the move reverses (Axia "absorption" events) | In the extreme bar, zone delta within 8 ticks of the extreme is ≥ 20% of zone volume against the reversal → reversal confirmed (**OF1**) | T (1m proxy B6 rejected) | filter on LIT |
| 4 | Stacked imbalances | 3 or more prices in a row where the ask volume is ≥ R × the bid volume one tick lower show initiative buying, and the stack later acts as support. NT Volumetric bars default to a 1.5 ratio. 3.0 is the common "strong" setting | S3 in of_study: 3+ stacked 300% diagonal imbalances, the bar closes the same way → continuation at the next open, 2R | T | 1-3 |
| 5 | Initial balance / value-area auctions (Market Profile/TPO) | Steidlmayer and Dalton (*Mind Over Markets*): the 70% value area, the IB (first hour), range extension. A failed extension rotates back to the other side. Poor highs and lows (no excess) get revisited | (a) The 80% rule: **already rejected twice**. (b) IB failed extension → fade to the IB mid: **B2, rejected**. (c) A poor high/low gets revisited, and a LIT sweep of one fails: **B3, rejected (4 trades)** | 1m / 5m enough | 2-3 (B2) |
| 6 | Volume profile POC / HVN / LVN | The POC and HVNs are "fair price" where price stalls. LVNs are rejected price where price rejects or moves fast (Trader Dale *Volume Profile*) | Prior-day POC first touch: **already rejected**. LVN rejection: **B1, closest miss**, and moves to ticks as **OF3** | 1m OK, T better | 0.5-1 |
| 7 | DOM liquidity pulls / spoofs | Big resting orders that vanish as price nears are fake. Spoofing is illegal: CFTC v. Sarao (E-mini, 2015) and 3Red/Oystacher (2015, settled 2016). Pulled liquidity hints at the real direction | Count of ≥ N-lot levels within 5 ticks pulled with no fill in the last 10 s, signed → filter on LIT | **D** | n/a |
| 8 | Iceberg detection | A level that keeps refilling after fills hides a large passive order (Christensen & Woodmansey 2013, *J. of Trading*; Zotikov & Antonov 2021, *Quant. Finance*). On CME MBO a native iceberg refresh keeps its OrderID | Traded volume at one price ≥ 3x the largest displayed size there in 60 s with no price break → iceberg level; fade the first test | **D** (MBO best). T + best bid/ask is a crude hint | 0.5-1 |
| 9 | Large-lot (block) prints | Big single aggressive prints show informed size. Tape readers follow them | Trade ≥ 99.5th percentile of size over the prior 5 days. Signed block volume from the sweep to the entry against the LIT trade → skip (**OF2**) | T | filter on LIT |
| 10 | Opening auction / order imbalance | The 09:30 cash open is an auction. Nasdaq publishes its Net Order Imbalance (NOII) every second from 09:28 (plus an early indicator from 09:25), and NQ trades the cash open | Sign of the 09:29:59 NOII imbalance for QQQ / Nasdaq-100 names vs NQ 09:30-10:00 direction | NOII feed (not free here) + T. On bars, the opening drive / gap fade / ORB were **all already rejected** | 5 (one a day) |

**Sources:**
- Dalton, Jones & Dalton, *Mind Over Markets* (Wiley, 1990 / 2013): the 70% value area and the initial balance.
- Steidlmayer, *Steidlmayer on Markets* (Wiley, 1989 / 2002).
- CBOT Market Profile handbook (1980s; exact date not confirmed).
- Trader Dale, *Volume Profile: The Insider's Guide to Trading* and *Order Flow: Trading Setups*.
- Axia Futures, "The Footprint Edge" course (absorption).
- Orderflows / Michael Valtos (CVD / footprint material).
- NinjaTrader 8 help: Order Flow Volumetric Bars (imbalance ratio default 1.5), Importing / Exporting.
- CME Group education, Market by Order (iceberg OrderID).
- CFTC press releases pr7156-15 (Sarao), pr7264-15 and pr7504-16 (3Red / Oystacher).
- Nasdaq Trader ETA2021-6 (NOII every second from 09:28, EOII from 09:25).
- Lee & Ready (1991), *J. Finance* 46(2), the trade-side rule used by the importer.
- Easley, López de Prado & O'Hara (2012), bulk volume classification (BVC), used for B4.
- **Not confirmed:** a primary source for the "80% rule" (it is folklore attributed to Dalton-style teaching).

## B. What our bars can test now (pre-registered, costs in)

**Setup:**
- The rules were written into `research/orderflow/of_program.py` and **committed before the first run**.
- Sizing and costs: $500 risk, micros sized by the stop (cap 40), $1.40 a micro round trip, 0.25 pt slippage on entry and on
  stop exits.
- Data: 5m NQ 2021-10 → 2026-11, 1m 2025-12 on. Spans are 2021-25 / 2026 H1 / 2026 H2.
- **Skipped as repeats:** the 80% rule, the failed VA-edge auction, the prior-day POC, the IB breakout, the IB
  sweep-and-reclaim scalp, the 24 VWAP/VP size tilts, and the 5m CLV proxies from this morning.

### Stand-alone setups (net $, PF, trades/week)

| Setup | 2021-25 | 2026 H1 | 2026 H2 | Placebo p | Corr. with LIT | Verdict |
|---|---|---|---|---|---|---|
| **B1 LVN rejection** (prior-day profile) | 155 tr, PF 1.26, **+$11,556**, 0.71/wk, $230/mo | 12 tr, PF 1.10, +$326 | 10 tr, PF 4.56, +$4,990 | **0.004** | -0.06 / -0.02 / -0.10 | **Rejected** (H1 PF < 1.15; too few trades). Best lead → OF3 |
| B2 IB failed extension → IB mid | 590 tr, PF 0.84, **-$36,471** | 72 tr, PF 1.80, +$19,679 | 53 tr, PF 1.20, +$3,739 | 0.026 | about 0 | **Rejected.** It works only in 2026, the classic regime flip |

### LIT add-ons ($ change vs all LIT trades; all LIT = +$4,738 / +$30,033 / +$8,212)

| Add-on rule | 2021-25 | 2026 H1 | 2026 H2 | Verdict |
|---|---|---|---|---|
| B3 skip sweeps of a prior-day **poor** high/low | -$273 (4 trades) | 0 trades | 0 trades | Rejected: almost never happens. A poor extreme *does* get revisited more often the next day (50% vs 37%, n=32) |
| B4 S1' 5m BVC delta divergence: take only divergent trades | +$4,395 | **-$30,597** | -$7,343 | Rejected (the same flip as the CLV proxy) |
| B4 S4' 5m BVC: skip "refuted" trades | +$273 | **-$15,068** | -$3,748 | Rejected |
| B4 S1' 1m BVC divergence | n/a | -$28,708 | -$4,324 | Rejected |
| B4 S4' 1m BVC: skip refuted | n/a | **-$21,629** | -$4,749 | Rejected: the refuted trades are LIT's best (PF 7.4 / 3.1) |
| B5 skip thin sweeps (sweep-bar volume < its 20-bar mean) | -$2,515 | +$123 | -$6,086 | Rejected |
| B6 1m absorption print at the sweep (≥ 2x volume, close in the far half): take only those | n/a | -$23,723 | -$9,711 | Rejected |

**What it means:**
- No bar-based order-flow filter improves LIT. Every filter that skips trades loses 2026 money.
- One pattern repeats across three different proxies and both 2026 halves: **LIT trades where the flow kept pushing against
  the entry were the best ones.** That fits a trapped-traders story, but bars can't show it at the extreme. It is exactly
  what OF1 measures on ticks.
- It is post-hoc, and 2021-25 doesn't show it. So it is a hypothesis, not a finding.

## C. The 3 designs for real ticks

Full rules are in `research/orderflow/PREREG_ticks.md`, and the code is `of_study.py prereg()`. It runs by itself at 60+
tick days and was smoke-tested end to end on 84 synthetic tick days. That test only proves the code runs; its numbers mean
nothing.

1. **OF1 Sweep absorption (confirm or skip LIT).** Within 8 ticks of the sweep extreme, aggressive volume against the
   reversal is ≥ 20% of that zone's volume → keep the trade; otherwise skip it. It is the real version of the one pattern
   every proxy agreed on.
2. **OF2 Block prints against the trade (skip LIT).** A single trade ≥ the 99.5th percentile of the last 5 days, aggressing
   against the trade between the sweep and the entry → skip.
3. **OF3 LVN rejection on a real tick profile (uncorrelated extra trades).** B1's rule with the true volume at each price,
   plus delta on the touch bar in the trade's direction. B1 is the only bar test with a strong placebo and positive money in
   all spans.

Gates are fixed in advance:
- **OF1/OF2:** more net $ than all LIT in both 2026 halves, while keeping at least half the trades.
- **OF3:** PF ≥ 1.15 and net > 0 in each half, at least 0.5 trades a week, placebo p < 0.10.
- **Ticks cover only about 12 months.** A pass is a candidate. It then needs 3 months of forward-recorded ticks and the
  normal LIT change process.

The earlier S1-S4 real-mode tests stay in `of_study.py` as they were.

## D. Tick download made simple (and what was broken)

`TICKS_HOWTO.md`: 2 sections of clicks (Download, then Export), then one line: `pip install pyarrow && python -m engine.tickrec import`.

Fixes to `engine/tickrec.py`. Tests: `tests/test_tickrec.py` 20/20 (18 before, 2 new); `python -m engine.tickrec selftest` OK.
1. **Time zone (real bug).** NinjaTrader 8 **always exports in UTC** (help guide "Exporting"). The importer defaulted to New
   York time, and the old steps told the owner to pass his PC's time zone. Every tick would have landed 4-5 hours off, and
   the "busiest minute" check would have flagged it only if he read it. **The default is now UTC**, and `--tz` is only for
   other sources.
2. **Lost trades (real bug).** Re-import de-duplication dropped *identical* rows. NQ prints many identical trades in the
   same timestamp, so real volume was being deleted. It now keeps each repeat as often as it appears in either copy.
   Re-importing still adds nothing.
3. **Speed and memory.** The old line-by-line parser held a whole multi-GB file in Python lists (it would run out of memory
   on a quarter of ticks). It now streams 2M lines at a time. 3M lines import in 27 s with pyarrow, so a year takes about
   30-60 min. The tick-rule loop is vectorised.
4. **Simpler.** With no file given, `import` reads every `.txt` in `Documents\NinjaTrader 8\le_ticks\export`. The root (NQ/ES)
   comes from NT's file name. Each file prints `tz_check` and `with_bid_ask%`.

**Not verified:**
- The exact column layout of an NT8 *tick* export with bid/ask (`yyyyMMdd HHmmss fffffff;last;bid;ask;volume`) is from
  NinjaTrader forum staff, not the help guide, and older posts disagree. Both the 5-field and 3-field layouts parse. If
  `with_bid_ask%` comes back near 0, sides fall back to the tick rule, which is weaker.
- The "about 12 months of ticks" depth is also forum-only.
- `LE_TickRec.cs` is still uncompiled.

## Safety
- Research only, branch `day-ofprogram` (built on `day-orderflow`), not merged to `pc`.
- No live_model file touched and nothing armed.
- `engine.tickrec` still imports nothing that trades, and nothing in the bot imports it. The test checks both.
