---
title: Kalshi K8 commodities - the friend's "printer" bot (15-minute gold/silver clock bets + index-roll bets)
family: kalshi
date: 2026-11-19
status: real clock pattern on 3.5 months of Kalshi data, positive in both halves; PAPER candidate only (research/lab/kalshi_candidates/K8.json); nothing armed
---

# Kalshi K8 (2026-11-19): what the friend's "printer" does, and does it really win

## Owner summary (plain words)

**What his bot does.** Kalshi has "will gold be up in the next 15 minutes?" markets (also silver, natural gas, oil).
Each one lives exactly 15 minutes. His bot buys one side **20 seconds after a market opens**, at fixed clock times,
every weekday:
- **05:15 -> 05:30 ET: gold and silver DOWN.** The quarter hour before London's gold auction (10:30 London).
- **16:45 -> 17:00 ET: gold and silver UP.** The last quarter hour before the CME futures close (17:00 ET).
- Sometimes **16:00 -> 16:15 ET: silver DOWN.**
- **"Roll" tickets**, 5 days a month: natural gas UP (Brent DOWN), 2-3 contracts at 48-95c. On the 5th-9th
  business day of each month, the natural-gas and oil prices Kalshi settles on (Pyth) move to next month's futures, one
  slice a day at 17:00 ET. Natural gas jumped +0.6% to +2.7% in that quarter hour on all 15 such days we have.

**Does it really win?** Yes, the clock pattern is real in Kalshi's own results since August. Gold fell in the
05:15-05:30 window on 73% of 78 weekdays and rose in the 16:45-17:00 window on 70%. Kalshi still prices both near a coin
flip (he pays 41-66c), and that gap is the whole edge. His screenshots show 18 of 26 legs won but about -$0.50 in total.
That is because he bets more after wins (8 -> 45 contracts), so the two bad days (11/16-11/17) came at his biggest sizes.
**The same 26 bets at a flat $15 would be +$70.** His 17:00 leg went 4 of 9. A 70-75% leg does that about 1 time in
10-20, so it is not yet a reason to drop it. But those were the newest days, so watch it.

**For us, flat $10-20 a bet.** Rules were fixed on Aug-Sep and judged once on Oct 1-Nov 18. Entry = the price really
paid 15-30 seconds after the open; fees in.

| Leg (what his bot buys) | Test: bets, won, avg paid | Test result per $1 after fees (95% range) | $/month at $15 | Verdict |
|---|---|---|---|---|
| 05:30 DOWN gold | 35, 74%, 0.53 | **+38%** (+10% to +65%) | +$127 | Real: both halves (train +36%) |
| 05:30 DOWN silver | 35, 57%, 0.52 | +8% (-24% to +38%) | +$27 | Weak lately (train +30%) |
| 17:00 UP gold | 35, 80%, 0.49 | **+58%** (+29% to +84%) | +$191 | Real (train +16%, weaker in August) |
| 17:00 UP silver | 35, 74%, 0.51 | **+39%** (+8% to +65%) | +$129 | Real: both halves (train +36%) |
| 16:15 DOWN silver | 35, 63%, 0.52 | +18% (-16% to +53%) | +$60 | Fading: lost money in November |
| 16:15 DOWN gold (not his) | 35, 60%, 0.51 | +16% (-18% to +50%) | +$53 | Not proven; lost in November |
| Roll: natgas UP 17:00-17:15 | 10, 100%, 0.89 | +12% (+8% to +16%); his late 80-95c style: +6% | +$14 | Real but small, and dearer every month |
| Roll: WTI DOWN 17:00-17:15 | 10, 80%, 0.54 | +40% (-13% to +80%) | +$50 | Promising, only 20 bets in all |
| Roll: Brent DOWN 17:30-17:45 | 4, 100%, 0.85 | +16% | +$19 | One month of data only |
| His "16:15 roll" tickets (Brent / natgas 16:00-16:15) | 5 / 10 bets | -19% / +37% | about $0-50 | No roll jump in that window; too few bets |

**All 6 metals legs together (the paper candidate):** test 210 bets, 68% won, average price 0.51, **+30% per $1 after
fees** (95% range +11% to +45%; +25% if every fill were 2c worse). About 130 bets a month:
**+$387 a month at $10 a bet, +$587 at $15, +$784 at $20.** Train half: 255 bets, 72% won, +33%.
The worst run was 8 losses in a row (Nov 16 evening + all of Nov 17). The worst day was -$92 and the deepest dip -$123
(at $15 a bet). 10 of 35 test days lost money.

**The risk.** Nobody knows WHY the clock works. Pyth's tick data now needs an API key, so we cannot look inside. Kalshi
already removed some of these windows once: the 17:00-18:15 metals markets went on Oct 1, and the 17:00-17:15 one had
risen on 86-88% of days. It can stop overnight if Kalshi changes the markets, Pyth changes its index, or market makers
start pricing the clock. His bot and copycats buy at the same second, which speeds that up. The newest days were the
worst ones. **Kalshi stays paused for real money. This is a PAPER rule only** (`research/lab/kalshi_candidates/K8.json`).

## 1. The exact markets

| His word | Kalshi series | Question | Settles on (Pyth "24/7" index) | Rounded to |
|---|---|---|---|---|
| GOLD | KXGOLD15M | Gold price up in next 15 mins? | Metal.Index.1OZGOLD/USD | 2 decimals |
| SILVER | KXSILVER15M | Silver price up in next 15 mins? | Metal.Index.SILVER/USD | 3 decimals |
| NATGAS | KXNATGAS15M | Natural Gas price up in next 15 mins? | Commodities.Index.NATGAS/USD | 5 decimals |
| BRENT | KXBRENT15M | Brent Crude Oil price up in next 15 mins? | Commodities.Index.BRENT/USD | 2 decimals |
| (WTI, tested too) | KXWTI15M | WTI Oil price up in next 15 mins? | Commodities.Index.PYTHOIL/USD | 2 decimals |

- One market per quarter hour, Monday-Friday. It opens at the start of its 15 minutes (05:15:00 ET for the "5:30" market),
  closes at the end (05:30:00 ET) and settles about 25 seconds later. Nothing trades before it opens.
- **UP (YES) wins if Pyth's 1-minute close at the end is at least the 1-minute close at the start.** The start price is
  the "target price" the market shows when it opens, and it is exactly the previous market's settle. A tie goes to UP.
  DOWN = buying NO.
- His labels are the settle times: "5:30 ET metals trade" = the 05:15-05:30 market, "17:00" = 16:45-17:00,
  "16:15" = 16:00-16:15, "17:15 roll" = 17:00-17:15.
- Fee: 0.07 x contracts x p x (1-p), rounded up to the cent per order. His posted wins equal contracts x (1 - price) minus
  this fee, so he buys as a taker. His 80c / 95c roll tickets show no fee, so they were probably resting orders.
- History on the public API: gold, silver and WTI since 2026-07-31; natural gas since 08-27; Brent since 10-21. Kalshi
  stopped listing the metals markets inside the CME break (17:00-18:15 ET) on 2026-10-01.
- Size: a gold 15-minute market trades a median 400,000-500,000 contracts (Oct-Nov). Silver trades 50,000-70,000, WTI
  about 100,000, natural gas about 20,000 and Brent about 7,000.

## 2. His trades, found on the public trade list

| Day | Market (window, ET) | His ticket | Public tape | Pyth start -> end |
|---|---|---|---|---|
| 11/12 | KXGOLD15M-26NOV120530-30 (05:15-05:30) | DOWN 12 @ 58c | NO 12 @ 0.58 at 05:15:20 | 3,946.70 -> 3,945.83 |
| 11/12 | KXSILVER15M-26NOV120530-30 (05:15-05:30) | DOWN 11 @ 63c | NO 11 @ 0.63 at 05:15:20 | 51.128 -> 51.112 |
| 11/12 | KXSILVER15M-26NOV121700-00 (16:45-17:00) | UP 13 @ 63c | YES 13 @ 0.63 at 16:45:25 | 49.996 -> 50.071 |
| 11/12 | KXNATGAS15M-26NOV121715-15 (17:00-17:15) | UP 3 @ 95c | YES 3 @ 0.95 at 17:04:56 | 3.68411 -> 3.74174 (roll day 5) |
| 11/13 | KXGOLD15M-26NOV130530-30 (05:15-05:30) | DOWN 21 @ 60c | NO about 0.59, 15-30 s (split fills) | 3,901.25 -> 3,898.71 |
| 11/13 | KXSILVER15M-26NOV130530-30 (05:15-05:30) | DOWN 24 @ 53c | NO about 0.53, 15-30 s (split fills) | 50.023 -> 49.999 |
| 11/13 | KXGOLD15M-26NOV131700-00 (16:45-17:00) | UP 36 @ 41c | YES 36 @ 0.41 at 16:45:25 | 3,877.29 -> 3,884.10 |
| 11/13 | KXSILVER15M-26NOV131700-00 (16:45-17:00) | UP 29 @ 49c | YES 29 @ 0.49 at 16:45:24 | 48.639 -> 48.754 |

- His bot sends **one taker order 20-25 seconds after the window opens**. The roll ticket went in 5 minutes into the
  window, after the jump.
- **All 25 dated legs from his screenshots match Kalshi's settled results.** On all 21 metals legs, the public price
  15-30 s after the open was within 0-2.5c of his fill, so these are real fills. The undated Brent 80c ticket could not be
  placed.
- He skipped 4 legs we can see: 11/6 silver 05:30, 11/9 gold 05:30, 11/10 silver 05:30 and 11/12 gold 17:00. **All 4 would
  have won.** No simple rule explains his skips: not price (one skip cost 51c, one taken bet 66c), not the previous
  quarter hour, not the overnight move.
- His sizing grows with his balance (8 -> 45 contracts, then back to 11-19). The two worst days came right after the
  biggest bets, so 18 wins of 26 netted about -$0.50. **The same 26 bets at a flat $15 = +$69.56**: 05:30 legs +$36.60,
  rolls +$33.78, 16:15 silver +$15.88, 17:00 legs -$16.70.

## 3. What his bot knows that the price does not

Kalshi's 15-minute prices sit near a coin flip at the open. The market seems to price "where is the price now vs the
target", not the time of day. Three things are predictable from the clock alone:

1. **05:15-05:30 ET: gold (and silver) tend to fall.** Gold fell in that window on 73% of 78 weekdays (train 72%, test
   74%), on average -4 to -8bp (about $2-3 an ounce). That is big for a window whose normal swing is 6-10bp. It follows the
   **London** clock: in the one week when London and New York clocks differ (Oct 26-30), the 05:15-05:30 ET window fell
   on only 2 of 5 days, and the 06:15-06:30 ET window (= 10:15-10:30 London) on 5 of 5. 10:30 London is the LBMA gold
   auction. Silver has the same window but weaker (train 70%, test 57%).
2. **16:45-17:00 ET: gold and silver tend to rise** (gold 70%, silver 74%). **16:00-16:15 ET they tend to fall** (gold
   66%, silver 74%). 17:00 ET is the CME close; the futures pause 17:00-18:00. While Kalshi still listed the 17:00-17:15
   window (Aug-Sep), it rose on 86-88% of days, and the 18:00-18:15 window fell on 60-65%. These are CME session
   times. The most likely cause is that Pyth's 24/7 index changes its price sources around the futures close. Pyth's
   tick history now needs an API key, so this cannot be proven.
3. **Roll days (5th-9th US business day): Pyth's natural-gas and oil indices step to the next futures month at 17:00 ET.**
   - Natural gas jumped +0.6% to +2.7% in the 17:00-17:15 window on all 15 roll days (Sep, Oct, Nov). The next month
     costs more; a normal quarter hour moves 0.27%.
   - WTI fell in the same window on 17 of 20 roll days, mostly -0.2% to -1.0% (the next month costs less).
   - Brent steps at 17:30-17:45 ET (5 of 5 down, -0.3% to -0.5%, November only).
   - The market sees the jump within the first minute: natural gas UP already costs 0.90-0.99 by 17:01. Other bots
     know the calendar too. In September the first trades after 17:00 paid 0.47-0.69 for natural gas UP; in November
     the very first 5 seconds already cost 0.80-0.93. That roll edge is being competed away.

What is NOT behind it: no settle value is known early (the target is the price at the open, the settle comes 15 minutes
later). A speed edge against Pyth's live feed cannot be checked either, because that feed now needs a key too.

## 4. How it was tested

- Kalshi PUBLIC data only (GET, no key, never an order), at most 1 request a second. That covers every settled
  15-minute market of the five series (result, target, settle), the 1-minute bid/ask candles, and the public trade list
  for the first 45 seconds of every gold/silver 05:30, 06:30, 16:15 and 17:00 market and every roll-day market. No
  outside prices were needed: the rules use only the clock (and, for filters, earlier Kalshi settles).
- **Split fixed before any profit was computed: TRAIN = 2026-08-03 .. 09-30 (43 weekdays), TEST = 10-01 .. 11-18 (35 weekdays).**
  The legs come from his posts, not from my own search. Filters were picked on TRAIN only (at least 20 train bets) and
  read once on TEST. The candidate rule was declared in code before the full test read: every metals leg that made at
  least +5% per $1 on at least 20 train bets. 95% ranges resample whole days.
- **Entry = what a bot really pays 15-30 seconds after the open**: the average price takers paid for our side on the public
  trade list in that span. His fills are at 20-25 s and match it within 0-2.5c. Cross-check: the ask at 60 seconds.
- Flat stake, whole contracts, fee rounded up per order, held to the settle.
- **Honesty notes.**
  - He most likely found these windows in these same months, so both halves are his history too. They still show the
    pattern did not come from one lucky month. The only clean test starts now: paper bets from 11-19.
  - I saw early test numbers for gold's 16:15 leg before writing the candidate rule down. The rule uses only train
    numbers, and that leg would pass it anyway.

## 5. Results per leg (flat $15, taker, fee in)

Entry = price paid 15-30 s after the open (public tape). "Paid" = average price of our side.

| Leg | Train: bets, won, paid, per $1 | Test: bets, won, paid | Test per $1 (95% range) | Test avg win / loss | Worst streak | Bets/mo | $/mo at $15 |
|---|---|---|---|---|---|---|---|
| 05:30 DOWN gold | 42, 71%, 0.51, +36% | 35, 74%, 0.53 | **+38%** (+10% to +65%) | +13.16 / -15.29 | 4 | 22 | +127 |
| 05:30 DOWN silver | 41, 68%, 0.51, +30% | 35, 57%, 0.52 | +8% (-24% to +38%) | +13.55 / -15.15 | 3 | 22 | +27 |
| 10:30 London DOWN gold (variant) | 42, 71%, 0.51, +36% | 35, 83%, 0.54 | +54% (+27% to +77%) | +13.08 / -15.31 | 1 | 22 | +179 |
| 10:30 London DOWN silver (variant) | 41, 68%, 0.51, +30% | 35, 57%, 0.53 | +5% (-27% to +34%) | +12.75 / -15.15 | 3 | 22 | +17 |
| 17:00 UP gold | 43, 63%, 0.52, +16% | 35, 80%, 0.49 | **+58%** (+29% to +84%) | +14.79 / -15.29 | 2 | 22 | +191 |
| 17:00 UP silver | 43, 74%, 0.53, +36% | 35, 74%, 0.51 | **+39%** (+8% to +65%) | +13.31 / -15.35 | 3 | 22 | +129 |
| 16:15 DOWN silver | 43, 84%, 0.53, +54% | 35, 63%, 0.52 | +18% (-16% to +53%) | +13.42 / -15.31 | 3 | 22 | +60 |
| 16:15 DOWN gold | 43, 70%, 0.54, +26% | 35, 60%, 0.51 | +16% (-18% to +50%) | +14.26 / -15.27 | 3 | 22 | +53 |
| roll: natgas UP 17:00-17:15 | 5, 100%, 0.77, +29% | 10, 100%, 0.89 | +12% (+8% to +16%) | +1.71 / none | 0 | 8 | +14 |
| roll: WTI DOWN 17:00-17:15 | 10, 90%, 0.66, +34% | 10, 80%, 0.54 | +40% (-13% to +80%) | +11.41 / -15.45 | 1 | 8 | +50 |
| roll: Brent DOWN 17:30-17:45 | none | 4, 100%, 0.85 | +16% | +2.34 / none | 0 | 8 | +19 |
| roll ticket: natgas UP 16:00-16:15 | 5, 100%, 0.56, +74% | 10, 80%, 0.58 | +37% (-7% to +76%) | +10.91 / -15.19 | 2 | 8 | +47 |
| roll ticket: Brent DOWN 16:00-16:15 | none | 5, 40%, 0.45 | -19% | +15.61 / -15.38 | 3 | 10 | -30 |

The roll legs were too few (5-10 train bets) to join the candidate under the rule declared in code. At the 60-second
ask they are smaller: natural gas +6%, WTI +11%, Brent +25%. A bot that buys natural gas at 90c+ after the jump, like
his tickets, made +6% on all 15 roll days (5 a month, about $8 a month at $15).

The London variant of the 05:30 leg differs only in the 5 days of Oct 26-30 (London 10:30 = 06:30 ET). It is better,
but that evidence sits in the test half, so it stays a variant to check in March 2027 (US and UK clocks differ again
Mar 15-26).

Same legs with the 60-second ask instead (a slower bot): the edge survives. Gold 05:30 +37% train / +40% test, silver
05:30 +39% / +18%, gold 17:00 +17% / +53%, silver 17:00 +35% / +38%, silver 16:15 +54% / +13%, gold 16:15 +20% / +6%.
While they were listed (Aug-Sep), the 17:00-17:15 metals windows cost 0.69-0.76 at 60 s and still made +14% to +21%.

## 6. Is the market catching up? (month by month, 60-second ask)

| Leg | Aug: paid, won | Sep | Oct | Nov (to 18th) |
|---|---|---|---|---|
| 05:30 DOWN gold | 0.50, 60% | 0.51, 82% | 0.54, 64% | 0.55, 92% |
| 05:30 DOWN silver | 0.48, 63% | 0.52, 73% | 0.54, 59% | 0.50, 54% |
| 17:00 UP gold | 0.54, 57% | 0.48, 68% | 0.51, 82% | 0.51, 77% |
| 17:00 UP silver | 0.54, 71% | 0.52, 77% | 0.51, 77% | 0.52, 69% |
| 16:15 DOWN silver | 0.56, 81% | 0.55, 86% | 0.49, 64% | 0.59, 62% |
| 16:15 DOWN gold | 0.56, 71% | 0.55, 68% | 0.52, 68% | 0.59, 46% |

The price of the main legs stayed at 0.48-0.55 every month while they kept winning 54-92%: the market has not learned
the clock. The 16:15 legs are the exception. In November they cost 0.59 and lost money, so drop them first if the
paper test disappoints. Last two weeks (Nov 5-18, 10 bets each): gold 05:30 9/10 won, gold 17:00 8/10, silver 16:15 8/10,
silver 17:00 6/10, gold 16:15 6/10, silver 05:30 5/10.

## 7. Do filters separate the winning days? (picked on train only, then read once on test)

Tried on every metals leg:
- price caps (at most 0.50 ... 0.70) and price floors (at least 0.45 ... 0.55);
- whether the previous quarter hour went up or down;
- the 4-hour move before the window;
- the session before: Asia for the 05:30 legs, London + New York for the 17:00 legs;
- Monday-Wednesday vs Thursday-Friday.

| Leg | Filter picked on train | Test with it | Test without |
|---|---|---|---|
| 05:30 DOWN gold | Monday-Wednesday only | +45% on 21 bets | +38% on 35 |
| 05:30 DOWN silver | previous quarter hour UP | +13% on 15 | +8% on 35 |
| 17:00 UP gold | 4-hour move before was DOWN | +72% on 16 | +58% on 35 |
| 17:00 UP silver | price at most 0.55 | +41% on 28 | +39% on 35 |
| 16:15 DOWN silver | previous quarter hour UP | +48% on 18 | +18% on 35 |
| 16:15 DOWN gold | previous quarter hour UP | +16% on 21 | +16% on 35 |

**Verdict: no filter is worth adding yet.** Each one keeps only 15-28 test bets, and the gains are within noise. Added
up, the filtered version makes about $530 a month at $15 against $587 unfiltered, because it bets less often. One hint
showed up in both halves for the DOWN legs: they did better after an UP quarter hour (gold 05:30: +47% train / +57%
test, vs +12% / +8% after a DOWN quarter hour). Log it in the paper test; do not trade it yet.

## 8. Control: mine the clock blindly and see what breaks

Suppose we pick quarter hours only because they leaned one way in Aug-Sep, with no story behind them (4 series x 96
windows). At a strict bar (|z| >= 3) that finds only silver 16:15 DOWN and silver 17:00 UP, the windows his bot already
trades: test +25% on 70 bets. At a looser bar (|z| >= 2.5) it adds gold 05:30 (+40%), gold 16:15 (+6%) and gold
23:45 DOWN, which **lost 37%** in the test: pooled +14% on 167 bets. So a window that merely leaned one way is not
enough. The legs kept here have a reason (London auction time, CME close) AND a record in both halves.

## 9. Can $10-20 a bet fill?

Yes. Counting what takers bought on our side in the first 45 seconds (test half, median):

| Leg | Contracts bought on our side, first 45 s |
|---|---|
| gold 05:30 | about 5,000 |
| gold 17:00 | about 11,700 |
| silver 17:00 | about 1,800 |
| silver 16:15 | about 1,050 |
| silver 05:30 (thinnest; smallest day 26) | about 220 |

A $15 bet is about 28 contracts. His own 36-45 contract orders filled at one price.

## 10. What the PC would need

1. **Kalshi public market data** (our Kalshi paper tools already read it): the ticker of each window and its best ask
   20 s after the open. The ticker comes from the ET date and time, e.g. `KXGOLD15M-26NOV190530-30` settles at 05:30 ET
   on Nov 19.
2. **A synced clock** (Windows time sync): the orders must go out 15-30 s after 05:15:00, 16:00:00 and 16:45:00 ET.
3. **Nothing from NinjaTrader is needed for the clock legs.** To watch the drift itself, and to time roll legs later,
   the data feed (`engine/datafeed.py`) could carry 1-minute bars of:
   - COMEX gold **GC** and silver **SI** (front month), 04:45-05:45 and 15:45-17:15 ET every day;
   - NYMEX natural gas **NG**, WTI **CL** and Brent (NYMEX **BZ**), front AND second month, 16:55-17:50 ET on the 5th-9th
     business day. The spread sign says which way the roll jumps.
4. For real money only (the owner's decision, never Claude's): his own Kalshi API key on the PC.

## 11. What is not proven (read before any money)

- **The clean test has not happened yet.** He chose these windows, probably from these same months. Both of our halves
  agree, but only paper bets from 2026-11-19 on are truly new. Kill rule in K8.json: stop if the first 60 paper bets
  win under 55% (break-even is about 53% at these prices).
- **Why it works is unknown.** 05:30 follows the London clock (gold auction), 16:00 and 17:00 are CME session times.
  Pyth's history and live feed now need an API key, so we cannot look inside the index.
- **It can vanish overnight.** Kalshi already removed the 17:00-18:15 metals windows on Oct 1. Pyth can change its index.
  Market makers can start pricing the clock: today we pay about 0.52, and if that drifts toward 0.65-0.70 the edge is gone.
- **Crowding.** His bot and any copycats buy in the same seconds, which pushes the price up.
- **Correlated losses.** Gold and silver usually lose on the same morning or evening. Losing days come in -$30 to -$90
  lumps at $15 a bet, and the newest days (Nov 16-17) were the worst of the test.
- **Roll legs are tiny** once the jump shows (90c+ tickets: about +6% per $1, 5 days a month). Catching the jump at
  17:00:00 is a speed race against other bots and was not tested as a rule.

## 12. Files and reruns (`research/kalshi_edge_K8/`; raw data in /home/user/kalshi_cache/kmetal, not in git)

| File | What |
|---|---|
| `kk8.py` | polite public client: GET only, one request a second across all K8 processes, cache |
| `harvest_markets.py` | every settled market of a series (target, settle, result) |
| `harvest_candles.py` | 1-minute bid/ask candles (batches for recent markets, one by one for archived ones) |
| `harvest_open_trades.py` | the public trade list of the first 45 s of chosen windows (the real entry price) |
| `k8lib.py` | loaders, fee, roll calendar (5th-9th business day) |
| `analyze.py` | leg windows, entry quotes, stats |
| `study.py` | the whole test -> `results.json` and `data/legs_bets.csv` (one row per bet) |
| `report.py` | the tables above, from `results.json` |
| `make_candidate.py` | writes `research/lab/kalshi_candidates/K8.json` only if the declared candidate passes |
| `tests/test_kalshi_k8.py` | offline checks: fee rounding, his posted wins, roll calendar, flat-bet maths |

Rerun (about 2 hours of polite downloading, then 2 seconds of maths):
1. `python research/kalshi_edge_K8/harvest_markets.py KXGOLD15M KXSILVER15M KXNATGAS15M KXWTI15M KXBRENT15M`
2. `harvest_candles.py <series> --live`, then `--hist --windows 0530,1700,1615,1715`
3. `harvest_open_trades.py`
4. `python research/kalshi_edge_K8/study.py && python research/kalshi_edge_K8/report.py && python research/kalshi_edge_K8/make_candidate.py`
