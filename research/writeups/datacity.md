---
title: Olympus Data City - a nightly data machine that tests 114,200 time / confluence / while-state combinations on NQ, and a 32,000-building 3D city that shows them
family: other
date: 2026-11-03
status: info - research tool, paper only; nothing proposed for the live bot (the 2021-24 picks lose money in 2025-26)
summary: Owner orders 2026-11-02 ("a data center like a city of data") and 2026-11-03 ("make the city bigger ... insane"). tools/datacity turns CME NQ1! 5m 2021-11 -> 2026-10 plus the PC's NinjaTrader bars to 2026-11-02 into 375,079 events (sweeps of Asia / London / prior-day / prior-week / opening-range levels, breaks, FVG, IFVG, CISD, displacement, VWAP cross, gap fill, the news bar, plain 15-minute slots), each a mini-backtest (next-bar entry, structure stop, 2R or 2 hours, $1.90 + 2 ticks costs a micro). The 2026-11-03 pass adds 7 state families (opening-range width and position, RTH gap types, the VIX curve and the VIX trend, ES-NQ relative strength, turn of the month / OpEx week) and weekday x 15-minute slot - 114,200 combinations, 32,164 with 30+ trades, in 9 districts. 39 pass a Benjamini-Hochberg false-discovery guard (q 0.10, ~3.9 expected false); a sign-flip placebo passes 2. 5 are gold, all under 1 trade a week. Holdout - the 40 combinations picked on 2021-24 alone stay positive in 2025-26 only 25% of the time (-0.11R a trade), and as a one-a-day portfolio they go from PF 1.69-2.09 a year in 2021-24 to PF 0.93 in 2025 and 0.98 in 2026 (-$704, -$68 a month, 2-week eval pass/fail 3.7/6.9%). Learned confluences - an open gap in the trade's direction, NQ outpacing ES, VIX 25+ / VXN 28+, an inverted VIX curve and a trending day help a little; VIX < 15 and an ES-NQ SMT that agrees with the trade hurt. Nightly workflow publishes the JSON to the datacity branch; the 3D page is tools/web_public/datacity/.
runs: datacity_holdout_portfolio
---

## In one minute

| What | The numbers |
|---|---|
| Data | CME NQ1! 5m, 1,304 days (2021-10-18 -> 2026-11-02), 375,079 events. Never Yahoo, never CFD |
| Combinations tried | **114,200** (was 67,320); **32,164** with 30+ trades = 32,164 buildings |
| Pass the noise guard (FDR q 0.10) | **39** (about 3.9 by chance); a placebo with no edge passes 2 |
| Gold (positive in 2026, 2021-25, every year, and FDR) | **5**, all under 1 trade a week |
| Holdout (picked on 2021-24, looked at in 2025-26) | 40 picked, **25%** stay positive, mean -0.11R a trade |
| Holdout portfolio, one trade a day, $500 risk | 2021-25 PF 1.67 (+$1,691/mo) -> **2026 PF 0.98, -$704 (-$68/mo)**, 2-week eval pass/fail 3.7 / 6.9% |
| Verdict | Nothing beats LIT; nothing is proposed for the live bot. Paper only |

## What it tests

| Part | What |
|---|---|
| Time | every 15-minute slot 18:00-16:00 ET (both directions), and weekday x every slot; the six sessions (Asia 18-02, London 02-07, NY pre 07-09:30, NY AM 09:30-11:30, lunch 11:30-13:30, PM 13:30-16:00) x weekday, month, DST, news day, VIX, turn of the month / OpEx week, the VIX curve and trend, opening-range width, gap type |
| Confluences (triggers) | sweep (wick through, close back inside within 3 bars) and break (close beyond) of the Asia high / low, London high / low, prior-day, prior-week and 09:30-09:45 opening-range highs / lows; FVG; IFVG; CISD; displacement (body >= 1.5 ATR); VWAP reclaim / loss; gap fill; the high-impact news bar; a plain entry at the slot |
| While-states | VWAP side, EMA200 side, ATR regime, VIX and VXN (CBOE close of the day before), London swept the Asia high / low / both / none, trending vs balanced so far today, previous day trend vs range, gap up / down / flat, ES-NQ SMT, weekday, DST, news day; **new:** opening-range width (narrow / normal / wide vs the last 250 days, from 09:45), price beyond / inside the opening range (with or against the trade, from 09:45), RTH gap type (no gap, gap up filled / open, gap down filled / open, from 09:30), the VIX curve (VIX / VIX3M < 0.9 contango, 0.9-1.0 flat, > 1.0 inverted), the VIX trend (close vs its 5-day mean: falling / steady / rising), ES-NQ relative strength (% change since 18:00, NQ ahead of ES by 0.15%+ the trade's way / in step / behind; ES from 2025-04 only), the turn of the month (last 2 / first 3 weekdays) and OpEx week |

The new families are crossed with three partners each (for example the opening-range width with VWAP side, the day type and
the gap); the original eight are crossed with each other as before. Every state uses bars up to the decision bar only (a
test cuts the data mid-session and checks it), day states come from earlier days or a calendar known in advance.

**The mini-backtest (the same for every event):** decide at a 5m bar's close, enter at the next bar's open; stop 1 tick
beyond the structure (for a sweep the sweep extreme, otherwise the extreme of the last 6 bars), at least 4 and at most
120 points; target 2R; otherwise out at the close 2 hours later or at the end of the CME day. A bar that touches both
the stop and the target counts as the stop. Money per MNQ micro ($2 a point) after **$1.90 commission + 2 ticks
slippage = $2.90** a round trip. One trade a day per combination (the first matching event).

**Sized strategies:** each discovery is also replayed like the bot sizes (size follows the stop: $500 at risk, 1-40
micros) through `tools/runlib.score`, with trades a week, % weeks with 2+, PF, net $, $ a month, max DD and the MFFU
Builder 50K eval speed (`p10/f10`, `dec10`, `p15/f15`, `slow_pass`, `pass_med`).

## The districts

| District | Tried | Tested (buildings) | Pass FDR | Gold |
|---|---|---|---|---|
| Times (slots, session opens) | 248 | 246 | 0 | 0 |
| Confluences (every trigger) | 238 | 150 | 0 | 0 |
| The Week (weekday x session, weekday x slot) | 2,130 | 1,438 | 0 | 0 |
| Seasons (month, turn of the month, OpEx week) | 3,894 | 1,549 | 0 | 0 |
| Volatility (VIX, VXN, ATR, VIX curve, VIX trend) | 37,250 | 12,718 | 18 | 2 |
| Gaps (gap up / down, filled / open) | 23,500 | 6,032 | 8 | 1 |
| Opening range (width, beyond / inside) | 12,000 | 2,224 | 3 | 1 |
| ES-NQ (SMT, relative strength; 2025-26 only) | 21,750 | 3,243 | 7 | 0 |
| While-states (VWAP, EMA, London vs Asia, day type, DST, news) | 13,190 | 4,564 | 3 | 1 |

A combination lives in the district of its most specific state (ES-NQ first, then opening range, gaps, volatility, the
week, seasons). Plus the Strategies (the sized discoveries), the Harbor (LIT's 631 trades of run `lit_live` as ships) and
the plaza (LIT's tower and the 12 discoveries).

## The guards (why most of it is noise)

1. **Benjamini-Hochberg FDR** at q = 0.10 over every distinct combination with 30+ trades. 39 pass with a positive edge;
   expected false: ~3.9. 3,874 pass with a NEGATIVE edge (costs and wide structure stops make the average trade lose).
2. **Sign-flip placebo:** the same grid with every trade's result multiplied by a random +1 / -1. It passes 2.
3. **Holdout:** BH run on 2021-24 alone picks 40 combinations; in 2025-26, which they never saw, only 10 (25%) stay
   positive, mean -$8.37 a trade a micro (-0.11R). More combinations tried = more that look good by luck.
4. **Stability (the colours):** gold = positive in 2026, in 2021-25 AND in every year with 8+ trades, AND passes FDR;
   green = positive in both periods; amber = one period only; grey = noise or a loser. 2021-25 must cover 3+ years with
   5+ trades (an ES-NQ combination, with ES from 2025-04 only, can never be green or gold).

## Top findings (data to 2026-11-02, $ per trade per micro after costs)

| # | Finding | 2026: $/trade, win, n, /wk | 2021-25: $/trade, win, n, /wk | Sized ($500 risk): 2026 / 2021-25 |
|---|---|---|---|---|
| 1 | NY AM short after a bearish displacement while beyond the opening range with the trade and trending (gold, new) | +$177, 73%, 11, 0.25 | +$46, 53%, 72, 0.33 | PF 6.64 +$4,066 ($393/mo) / PF 1.90 +$12,360 ($239/mo) |
| 2 | Long after an Asia high break while VIX rising and wild ATR (gold, new) | +$69, 67%, 12, 0.28 | +$50, 68%, 31, 0.14 | PF 3.27 +$2,634 ($255/mo) / PF 2.42 +$5,694 ($110/mo) |
| 3 | NY PM short after a VWAP loss while balanced so far today and gap up (gold) | +$29, 52%, 23, 0.53 | +$16, 48%, 87, 0.40 | PF 1.78 +$3,291 ($318/mo) / PF 1.74 +$12,452 ($241/mo) |
| 4 | NY lunch short after a bearish IFVG while VIX rising and against VWAP (gold, new) | +$26, 48%, 23, 0.53 | +$36, 51%, 101, 0.46 | PF 1.35 +$1,703 ($165/mo) / PF 1.76 +$15,554 ($300/mo) |
| 5 | Long after a bullish displacement while London swept the Asia high and trending (gold, decaying) | +$7, 44%, 43, 0.99 | +$21, 50%, 153, 0.70 | PF 1.06 +$591 ($57/mo) / PF 1.72 +$22,977 ($444/mo) |

**None can pass an MFFU 50K eval in 2 weeks on its own** (p10 0%, median 38-50 sessions to pass where it passes at all):
at under one trade a week they are building blocks, not strategies, and all are below the owner's 2-4 trades a week.

**The holdout portfolio** (run `datacity_holdout_portfolio`): the 10 best distinct 2021-24 picks, one trade a day,
2.65-2.86 trades a week. Per year PF 1.69 / 2.01 / 1.81 / 2.09 (2021-24, where they were picked) -> **0.93 in 2025 and
0.98 in 2026** (-$704, -$68/mo, DD -$7,866, 2-week eval pass/fail 3.7/6.9%, median 23 sessions). 2025-26 out of sample:
252 trades, -0.03R a trade, -$3,017. The bigger grid makes the decay worse than the 67,320-combination grid did (PF 1.06 in
2026 then): exactly what the guard warns about.

## What the city learned about confluences

Median change in R a trade when one state is added to the same trigger and window (over every base with 30+ trades both
ways), and the share of bases where it helps in 2026 AND in 2021-25:

| Helps | R | both | Hurts | R | both |
|---|---|---|---|---|---|
| ES-NQ SMT against the trade (2025-26 only) | +0.11 | 50% | ES-NQ SMT with the trade (2025-26 only) | -0.07 | 14% |
| a gap down still open | +0.07 | 42% | VIX < 15 | -0.04 | 23% |
| NQ outpacing ES the trade's way (2025-26 only) | +0.06 | 35% | VXN < 20 | -0.03 | 20% |
| a gap up still open | +0.06 | 36% | after a trend day | -0.02 | 20% |
| VIX 25+ / VXN 28+ | +0.04 | 23-31% | NQ lagging ES the trade's way | -0.01 | 21% |
| the VIX curve inverted | +0.04 | 36% | flat open | -0.01 | 25% |
| beyond the opening range with the trade | +0.03 | 35% | | | |

All small: no state adds more than about 0.1R on its own, and none helps in both periods in more than half of the bases.
Fear (VIX 25+, an inverted curve) and an unfilled gap help these structure-stop trades; a quiet VIX hurts them.

## The 3D city (tools/web_public/datacity/)

| Part | What |
|---|---|
| Scale | every tested combination is a building: ~32,000 + the strategies, discoveries and 631 ships. Full cards for ~1,200 (all gold, the best greens, the biggest greys); the rest ship as compact number rows (`skyline` in city.json) decoded with the same words |
| Drawing | one instanced mesh per tile (4 x 4 blocks), frustum-culled; far tiles become impostors (one 3 x 3 cluster a block, all blocks in one draw); 35 draw calls in the overview, ~47 close up, within a budget of 120 at 40k buildings (test) |
| Sky | the futures clock: sunrise at the 18:00 ET Asia open, noon at the NY open, sunset at the 16:00 close, night in the break and the weekend; Sky cycles clock / night / day |
| Weather | the VIX (CBOE close): clear < 15, haze < 20, rain < 25 (wet streets, ripples), a storm with lightning at 25+ |
| Effects | neon windows (lit = sample size, a few flicker), neon edges and crowns, wet-street reflections, god-ray searchlights and district sky beams, drifting fog layers, flying traffic along splines, holographic billboards cycling the discoveries, a beam of light onto a found building |
| Useful | Today layer (buildings whose trigger and states were true on the last session, and "armed" ones whose day states were), Watchlist (pins, kept on the device), history sparklines (quarter by quarter, per year, run by run), search by words / class / district, minimap, tap a district (or a far block) to fly there, a captioned tour |
| Honesty | grey stays grey; the Today glow never recolours a building; the plaza and the tour say how many are noise |
| Plug-ins | a new data source adds a district by dropping one JSON in `research/datacity/plugins/` (the nightly run validates it, copies it next to the page and lists it in city.json), or next to the page listed in `plugins.json`; contract in `data.js` |
| LITE | automatic below 40 fps when the owner did not choose: no reflections, one fog layer, fewer cars / drops / stars, pixel ratio <= 1.5 |

## Constantly learning

- `python -m tools.datacity --heartbeat` appends the PC's NinjaTrader MNQ 5m bars (never Yahoo) and rebuilds only the
  new days of the event table (incremental == full is a test), then re-scores everything (~1-2 minutes). The Today layer
  is computed from that same incremental table.
- `history.json` keeps one row per day of data (the top 100 with R, $ and n); the cards draw it run by run.
- `.github/workflows/datacity.yml` runs it Mon-Fri at 22:37 ET and force-pushes the JSON to the `datacity` branch
  (research/datacity JSON <= 3 MB, a test).

## Caveats

- 5m bars only: a bar through both the stop and the target counts as a loss (conservative).
- One trade a day per combination keeps trades independent, but most combinations then trade under once a week.
- p-values use a normal approximation (30+ trades); nested combinations are correlated, so BH is conservative, not loose.
- ES-NQ states have 2025-04 -> 2026 only; they can never count as holding in 2021-25. VIX3M comes from CBOE's file.
- Paper only. The data city never changes the bot. A finding becomes a candidate only after the usual test: better in
  2026 and 2021-25, 2-4 trades a week, MFFU eval speed, a write-up and the owner's yes.
