---
title: The four pillars (LIT, ATLAS, BLITZ, ORDER FLOW) - each case at its honest strongest; BLITZ on the Rapid 25K eval is good enough to switch on only at $150, not the built $300
family: money
date: 2026-11-23 (night, run 2026-11-24 early ET)
status: research only, paper. Nothing armed, no live_model*.json touched. One owner yes/no proposed (BLITZ Rapid lane $300 -> $150).
summary: LIT GREEN (last 40 sessions PF 4.62 vs backtest 3.91) but no edge in 2021-25 (PF 1.01). ATLAS GREEN (PF 2.27 vs 2.75) at real fills, 2021-25 PF 0.82. BLITZ pre-registered test on the Rapid 25K eval - the built $300 lane fails the eval 0.5% -> 3.1% (Jan-Jun); at $150 1.2%, passes every pre-set check, +$45 / +$91 a month. ORDER FLOW - recorder built, never compiled, 0 tick days; first test about Nov 26-30 with the backfill, else Feb 22 2027; priors low.
runs: research/pillars/blitz_rapid.py -> research/pillars/blitz_rapid.json (design research/pillars/DESIGN.md, commit 24d5d94e2); tools/edge_health.py; pillars file research/lab/pillars.json
---

## For the owner (one minute)

| Pillar | Status | $ a month: Jan-Jun / Jul-Oct / 2021-25 | Biggest risk | Next step |
|---|---|---|---|---|
| **LIT (Zlarior)** | LIVE, edge GREEN | **$5,562 / $2,670 / $25** (live size, no account rules) | No edge outside 2026 (2023 lost $13.0k) | Fix the held-back PC update (only 2 of 7 trades reached the account) |
| **ATLAS** | LIVE (funded 25K + Rapid), edge GREEN | **$2,614 / $1,172 / -$550** ($250 a trade, real fills); funded 25K to you $503 / $402 / $19 | Loses at real fills outside 2026 | Re-check fills at 10+; combo on the 25K #2 stays OFF until a 10-tick re-run |
| **BLITZ** | Paper, hidden; Rapid lane built OFF | add-on on the Rapid 25K at $150: **+$45 / +$91 / -$1**; alone $963 / $667 / $73 at $150 | Built at $300 it fails the Rapid eval 6x more (0.5% -> 3.1%) | **Your yes/no:** cut the lane to $150, then switch it on yourself |
| **ORDER FLOW** | Not ready, 0 tick days | none yet (bar proxy for OF3: about $230 / month, under 1 trade a week) | Recorder never compiled: a red F5 blocks the live feed too | At the PC, quiet evening: install + enable the tick recorder |

## 1. LIT (Zlarior)

| Span (Zlarior size rule, costs in) | Trades / week | Win % | PF | $ a month | Max DD |
|---|---:|---:|---:|---:|---:|
| 2026 Jan-Jun (picked here) | 3.12 | 58.8 | 4.98 | $5,562 | -$2,196 |
| 2026 Jul-Oct (checked) | 2.56 | 50.0 | 2.91 | $2,670 | -$1,396 |
| 2021-25 | 2.38 | 53.8 | 1.01 | $25 | -$19,426 |
Sources: lit-edge-2026-11-20.md, `tools/lit_losses.py live`. At a fixed $500 a trade: $5,126 / $3,707 / $38 a month.

- **Edge health now (tools/edge_health.py, bars to 2026-11-20): GREEN.** Last 40 sessions: 17 trades (2.1 a week), win 52.9%,
  PF 4.62, about $3,147 a month, vs a backtest median PF for a 40-session window of 3.91 (Jan-Jun) / 3.15 (Jul-Oct) / 1.10 (2021-25).
  So the last 40 sessions look like 2026, not like 2021-25. The last 20 sessions are the cold run: 7 trades, 2 won, PF 0.03,
  -$901 a month. A 7-trade stretch that bad shows up about 1 time in 11.
- **Live vs backtest so far (since the 50K eval start, Oct 19):** the account is -$786 and its backtest twin is -$858 over 7 trades.
  Live looks $72 better, but only because **5 of the 7 trades never reached the account**: a feed gap, a refused order, a silent PC,
  and one unknown. All 5 were small losers. Those gaps would have missed winners just as easily. The one fill we measured was
  3 ticks worse than the model (about $1.50).
- **The 2021-25 weakness, plainly:** LIT has no edge outside 2026. PF 1.01, +$25 a month, max drawdown -$19.4k. By year: 2022
  +$13.9k, **2023 -$13.0k (PF 0.62)**, 2024 +$0.7k, 2025 +$3.2k. 2026 has made all of the money: +$43.8k, PF 4.19. If the market
  goes back to 2021-25, the edge light should turn RED. In 2021-25 RED runs lasted up to 79 sessions, so that light is the guard.

## 2. ATLAS

| Span (real fills: 10 ticks a side, $250 a trade) | Trades / week | Win % | PF | $ a month | Max DD |
|---|---:|---:|---:|---:|---:|
| 2026 Jan-Jun | 4.06 | 36.5 | 2.39 | $2,614 | -$1,476 |
| 2026 Jul-Oct | 2.95 | 37.0 | 2.07 | $1,172 | -$1,177 |
| 2021-25 | 4.61 | 19.3 | 0.82 | -$550 | -$37,122 |
Sources: atlas-fills-2026-11-20.md, atlas-edge-2026-11-20.md, research/onebook/results.json. Funded 25K, what you get: $503 / $402 / $19 a month.

- **Edge health: GREEN** (bars to 2026-11-19). Last 40 sessions: 27 trades (3.4 a week), win 48.1%, PF 2.27. The backtest median
  is 2.75 / 2.73 / 1.06. That is a little below a typical 2026 window, and well above 2021-25.
- **Live vs backtest:** 3 real entry fills so far came in **9, 11 and 15 ticks** worse than the model's 1 tick. ATLAS buys at market on
  the 5m open while price is still running. That is why the backtest now uses 10 ticks. Funded profit is **$401**. The repo has no ATLAS
  live-vs-twin $ list and no list of missed trades, so that gap is unknown. (Open card: fast-entry 2-week test, about +$100.)
- **2021-25 plainly:** at real fills ATLAS loses: PF 0.82, -$550 a month at $250. 2025 alone has PF 0.90. A calm market loses the
  funded 25K almost every time.
- **As a combo on the 50K** (one-account-combo-final + red team): $2,554 / $1,501 / $16 a month vs LIT alone $905 / $805 / -$10.
  The cost: 2-week eval fails rise from 0.5% to 0.0 / 4.4 / 7.0%. The red team found that the Jul-Oct gain rests on ATLAS's 5 best
  days (without them about -$23 a month), and 2022 comes out -$141. The advice stays: add it after the 50K passes.
- **As a combo on the 25K #2** (engine/combo25.py, landed, 23/23 checks, **OFF**): $914 / $554 / $35 a month vs LIT alone
  $402 / $315 / $13. 2-week pass rises from 46.8 / 41.2 / 11.8% to 67.6 / 53.2 / 24.9%. 2-week fails rise from 0 / 0 / 0% to
  1.3 / 0.7 / 4.5%. **These numbers are optimistic.** They use 1-tick ATLAS fills and full size, while the live lane uses x0.5 in
  the eval. Re-run it at 10 ticks before you switch it on. The switch, which you type yourself with the live phrase:
  `python -X utf8 -m engine.combo50k --on --account "<25K #2 Name>"`.

## 3. BLITZ: paper and hidden; an eval-only lane on the Rapid 25K is built and OFF

**Plain answer: switch it on only at $150 a trade, not the $300 that was built.** At $300 it fails the Rapid 25K eval 6 times as
often in a Jan-Jun-like market (0.5% -> 3.1%). At $150, Jan-Jun fails are 1.2%. It still passes more often and sooner, and it
passes every check set before the run. The gain is small: about +$45 / +$91 a month (Jan-Jun / Jul-Oct-like), and a few
sessions sooner to pass. In a 2021-25-like market BLITZ is about break-even and does not save the account. Changing the size is a
live-money change, so it is your yes / no.

### BLITZ itself (fixed $ a trade, no account rules, costs in: $1.90 a micro + 1 tick each way; research/pillars/blitz_rapid.json "blitz_fixed")
| Span | Trades / week | Win % | PF | $ a month at $150 | Max DD at $150 | $ a month at $300 | Max DD at $300 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026 Jan-Jun (1m) | 8.5 | 56.7 | 1.70 | +$963 | -$952 | +$1,226 | -$1,506 |
| 2026 Jul-Oct (1m) | 6.8 | 56.6 | 1.62 | +$667 | -$646 | +$1,422 | -$1,198 |
| 2021-25 (5m bars) | 8.6 | 50.1 | 1.05 | +$73 | -$5,084 | +$122 | -$11,101 |
These are the same numbers as blitz-review-2026-11-18 (trade for trade). 2024 lost about $200 a month. One more tick of
slippage takes 2021-25 to +$18 a month. BLITZ trades 6-9 times a week, more than the 2-4 a week rule allows for a main strategy.
That is why it is only ever an add-on lane. No real-money fill has been measured yet: its live paper ledger is on the PC.

Write-ups read (grep blitz research/writeups): blitz-2026-backtest, blitz-25k, blitz-edge-2026-10-30b, atlas-blitz-edge-2026-10-30,
blitz-streak-size-2026-10-31, blitz-review-2026-11-18, rule-native-2026-11-17, one-account-book-2026-11-22, prop-economics-2026-11-23
(day-propecon), rapid25-slot-2026-11-22, and engine/rapid_blitz.py's research note. They all say the same thing: a real 2026 edge
(random directions lose, p 0.02-0.05), break-even in 2021-25, 0 of 8 exit ideas and 0 own-account plans pass. Its only paying use
is as extra small winning days next to LIT / ATLAS on an account that has the 30% best-day rule (the Rapid EOD eval).

### The Rapid 25K eval test (pre-registered: research/pillars/DESIGN.md, commit 24d5d94e2, BEFORE the run)
Engine: research/onebook/book.py -> research/plans/rank.py (real fills, ATLAS 10 ticks a side). 2,000 eval paths x 60 sessions,
1,000 slot paths x 126 sessions (6 months, fees in, re-buy on fail). BLITZ in the EVAL only (as built), LIT + ATLAS funded.
One position per account: a BLITZ trade that overlaps a LIT / ATLAS trade is dropped (as engine/rapid_blitz.py does live).

| Variant (Rapid EOD 25K) | Eval pass % H1 / H2 / 21-25 | **Eval fail % H1** / H2 / 21-25 | Median sessions to pass H1 / H2 | 6-month slot $ a month H1 / H2 / 21-25 | Pre-set checks |
|---|---|---|---|---|---|
| V0 today: LIT + ATLAS | 80.5 / 85.5 / 7.5 | **0.5** / 2.0 / 77.0 | 33 / 26 | $1,884 / $800 / -$50 | baseline |
| V1 + BLITZ $300 (the BUILT lane) | 81.5 / 93.0 / 13.9 | **3.1** / 1.9 / 81.8 | 26 / 19 | $1,992 / $924 / -$54 | **fails** (H1 fail +2.6 points) |
| V2 no BLITZ from a LIT entry to 30 min after its exit | 81.0 / 93.0 / 14.0 | 3.3 / 1.9 / 81.8 | 26 / 19 | $1,984 / $924 / -$53 | fails |
| V2b no BLITZ within 30 min before or after LIT (uses the future: diagnostic) | 82.3 / 93.0 / 14.1 | 3.0 / 1.9 / 81.7 | 26 / 19 | $1,999 / $924 / -$53 | not eligible |
| V3 BLITZ half size once the day is at 50% of the best-day cap | 81.6 / 93.0 / 13.7 | 3.2 / 1.9 / 81.9 | 26 / 19 | $1,989 / $924 / -$55 | fails |
| V4 BLITZ stops for the day after its first loser | 82.6 / 89.7 / 11.2 | 1.3 / 2.2 / 80.8 | 31 / 22 | $1,951 / $871 / -$53 | eligible, lower pass |
| **V5 BLITZ at $150 (half the built size)** | **83.0 / 91.2 / 13.0** | **1.2** / 2.5 / 79.8 | 30 / 21 | **$1,928 / $891 / -$51** | **PICK: passes all** |
| BLITZ alone on its own Rapid 25K (eval + funded) | 30.6 / 49.9 / 17.4 | 0.0 / 0.0 / 0.9 | 37 / 37 | $104 / $267 / -$9 | not worth a $97 slot |

V0 and V1 reproduce engine/rapid_blitz.py's research note exactly (80.5 / 0.5 -> 81.5 / 3.1 Jan-Jun; 85.5 / 2.0 -> 93.0 / 1.9 Jul-Oct).

V5 checked against the rules set before the run: H1 fail 1.2% (bar <= 1.5%), H2 fail 2.5% (bar <= 3.0%), 6-month slot H1 +$269
and H2 +$546 vs today, 2021-25 -$307 vs -$300 (bar: not worse by more than $100). **All pass.** First payout: median 49 / 52
sessions vs 53 / 56 today.

**Why the extra fails happen (read after the run):** they come from BLITZ losing days, not from clashes with LIT and not from big
days near the cap. LIT trades almost always end before 10:30 ET, and BLITZ starts at 11:00, so the 30-minute LIT gap (V2) removes
2 of 207 trades and changes nothing. The near-cap half size (V3) changes nothing either. Cutting BLITZ's risk per day helps:
half size (V5) or one loser and done (V4) takes the Jan-Jun fails from 3.1% back to 1.2-1.3%. V5 keeps more of the pass-speed gain.

**Multiple-testing note:** 4 eligible variants (V2-V5) x 3 spans, plus 2 not eligible. Every path is drawn from the same ~125
(Jan-Jun) / 78 (Jul-Oct) real sessions, so 2,000 paths do not add data: the 1.2% vs 0.5% Jan-Jun fail rate is 24 vs 10 paths
built from the same few bad BLITZ days. V5's money gain (+$45 / +$91 a month) is small, about the size of the noise
(a 6-month slot's SE is about $200 a month, prop-economics-2026-11-23). Treat V5 as "the safe size if you want the lane", not as a
proven money-maker. Its real value is passing the eval about 3-5 sessions sooner and 2.5-5.7 points more often in 2026-like markets.

**Verdict.** Good enough to switch on **only at $150**, on the Rapid 25K eval only, as a paper-proven add-on. At the built $300:
no (it fails the pre-set eval-fail bar). Your yes is needed twice: (1) change the lane's $300 to $150 (a code change on a helper
branch, then the lead lands it), and (2) switch it on with the live phrase yourself. Not on its own account (+$104 / +$267 / -$9 a month).

## 4. ORDER FLOW: readiness (research/orderflow/PREREG_ticks.md, TICKS_HOWTO.md, engine/tickrec.py, ninjatrader/LE_TickRec.cs)

| What | Today |
|---|---|
| Tick recorder | A NinjaTrader 8 AddOn records every NQ / ES trade (time in ms, price, size, best bid, best ask). The feed has no buy/sell flag, so the side comes from the quote rule (at the ask = buy), or the tick rule when the quote is missing or fake (NinjaTrader's Bid = Last fill-in is detected and dropped). It has no DOM and no icebergs. |
| Running? | **No evidence it is.** It is OFF until `python -m engine.tickrec enable`, and it has never been compiled. **0 tick days verified** (the data is PC-only and not visible from the cloud). |
| Backfill | The same AddOn asks NinjaTrader's history server (futures, MFFU login) for Tick 1 data, newest first, up to 365 days back. It only asks outside 02:00-16:05 ET. Not verified: how deep the history goes (about 12 months, per the forum), whether GetBid / GetAsk are filled in for old days, and whether expired contracts can be fetched. Without bid / ask it falls back to the tick rule, which is weaker. **It never reaches 2021-25**, so order flow can never get the 3-span check. |
| Data each test needs | 60 NQ tick days (OF2 needs 5 more days to set the block size). |
| First run of OF1-OF3 | **With the backfill:** about **Nov 26-30**, if you install it on the evening of Nov 24 (Thanksgiving week is fine). **Recording forward only:** the 60th session is **2027-02-22**, and those 60 days would be one Jul-Oct-like span only. |

Honest priors (43 pre-registered bar-proxy tests, **0 pass**; orderflow-program-2026-11-23.md, orderflow-2026-11-23.md; the red
teams fixed code, not conclusions):
- **OF1 (sweep absorption, keep or skip a LIT trade): low-moderate.** Skipping LIT trades that the proxy delta "refuted" cost
  -$15k to -$22k in 2026 Jan-Jun. Those trades were LIT's best (PF 5-7). A filter on a PF-5 strategy has little room to help.
- **OF2 (block prints against the trade, skip): low.** No bar proxy exists, and the block size depends on how NinjaTrader bundles prints.
- **OF3 (low-volume-node rejection on a real tick profile, stand-alone): low.** The bar version had PF 1.26 / 1.10 / 4.56
  (2021-25 / Jan-Jun / Jul-Oct), +$11.6k over 5 years (about $230 a month), on 0.5-0.7 trades a week. It fails when split into
  AM / PM, and the best round-2 variant lost in Jan-Jun. Even a pass is under 1 trade a week, below the 2-4 rule.
- Plain: order flow is a **cheap lottery ticket, not a plan.** It costs disk and one evening at the PC. Expect "rejected" at 60 days.

Risks: (1) LE_TickRec.cs has never been compiled, and a red F5 blocks every NinjaScript, including the live feed (LE_Feed). Install it
only when flat, and delete the file if F5 shows red. (2) 60 days give about 35-40 LIT trades on 2026-only data with 2 looks, so the
test is weak. (3) The PC's update has been held back since Nov 23, so the PC may not have the newest recorder code yet.

## 5. What this does not prove
- All 2026 numbers come from the year LIT was picked on, so they are optimistic. The 2021-25 rows are the honest floor, and all four
  pillars are about break-even or worse there.
- BLITZ has no real-money fills. ATLAS has 3. LIT has 1 measured fill.
- The PC was not reachable from here. Live ledgers (BLITZ paper, tick days) were not read.

## Files
- research/lab/pillars.json (the 4 pillars: spans, accounts, risks, next)
- research/pillars/DESIGN.md (pre-registered), research/pillars/blitz_rapid.py, research/pillars/blitz_rapid.json

## The four pillars, side by side

| Pillar | Status | $ a month: Jan-Jun / Jul-Oct / 2021-25 | Biggest risk | Next step |
|---|---|---|---|---|
| **LIT (Zlarior)** | LIVE, edge GREEN | **$5,562 / $2,670 / $25** (live size, no account rules) | No edge outside 2026 (2023 lost $13.0k) | Fix the held-back PC update (only 2 of 7 trades reached the account) |
| **ATLAS** | LIVE (funded 25K + Rapid), edge GREEN | **$2,614 / $1,172 / -$550** ($250 a trade, real fills); funded 25K to you $503 / $402 / $19 | Loses at real fills outside 2026 | Re-check fills at 10+; combo on the 25K #2 stays OFF until a 10-tick re-run |
| **BLITZ** | Paper, hidden; Rapid lane built OFF | add-on on the Rapid 25K at $150: **+$45 / +$91 / -$1**; alone $963 / $667 / $73 at $150 | Built at $300 it fails the Rapid eval 6x more (0.5% -> 3.1%) | **Your yes/no:** cut the lane to $150, then switch it on yourself |
| **ORDER FLOW** | Not ready, 0 tick days | none yet (bar proxy for OF3: about $230 / month, under 1 trade a week) | Recorder never compiled: a red F5 blocks the live feed too | At the PC, quiet evening: install + enable the tick recorder |

## Summary (5 lines)
1. LIT: the edge light is GREEN. The last 40 sessions show PF 4.62 against a 2026 backtest median of 3.91. It made $5,562 / $2,670 a month in 2026 but only $25 a month in 2021-25 (2023 lost $13k). Only 2 of 7 trades reached the account: fix the PC.
2. ATLAS: the edge light is GREEN, at PF 2.27 against a median of 2.75. At real fills it makes $2,614 / $1,172 a month in 2026 and loses $550 a month in 2021-25. The 25K #2 combo stays OFF until a 10-tick re-run.
3. BLITZ: the built $300 Rapid lane fails the eval 6x more often in Jan-Jun (0.5% to 3.1%). At $150 that falls to 1.2%, and it passes every check set before the run. It adds about +$45 / +$91 a month and passes about 3-5 sessions sooner. Switch on only at $150; that is your yes/no.
4. A 30-minute gap from LIT fixes nothing, because LIT is done before BLITZ starts at 11:00. The fails come from BLITZ's losing days, so a smaller size is the fix.
5. ORDER FLOW: 0 tick days. The first test is about Nov 26-30 if you install the recorder (otherwise Feb 22 2027), and every prior is low. Treat it as a lottery ticket, not a plan.
