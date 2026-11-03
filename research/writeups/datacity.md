---
title: Olympus Data City - a nightly data machine that tests 67,320 time / confluence / while-state combinations on NQ, and a 3D city that shows them
family: other
date: 2026-11-03
status: info - research tool, paper only; nothing proposed for the live bot (the 2021-24 picks decay in 2025-26)
summary: Owner order 2026-11-02 - "a data center like a city of data ... that backtests strategies, learns confluences, is constantly learning". tools/datacity turns CME NQ1! 5m 2021-11 -> 2026-10 plus the PC's NinjaTrader bars to 2026-11-02 into 375,079 events (sweeps of Asia / London / prior-day / prior-week / opening-range levels, breaks, FVG, IFVG, CISD, displacement, VWAP cross, gap fill, the news bar, plain 15-minute slots), each a mini-backtest (next-bar entry, structure stop, 2R or 2 hours, $1.90 + 2 ticks costs a micro). 67,320 combinations (time x trigger x up to two while-states), one trade a day each; 19,942 have 30+ trades. 25 pass a Benjamini-Hochberg false-discovery guard (q 0.10, about 2.5 expected false); a sign-flip placebo passes 2. Only 2 are gold (positive in 2026, 2021-25 and every year with 8+ trades, and FDR) and both trade under 1 a week. The honest headline is the holdout - the 22 combinations picked on 2021-24 alone stay positive in 2025-26 only 27% of the time (mean -0.16R a trade), and as a one-a-day portfolio they go from PF 1.66-2.17 a year in 2021-24 to PF 1.11 in 2025 and 1.06 in 2026 ($120 a month, 2-week eval pass/fail 2.3/3.7%). Learned confluences - VIX 25+ / VXN 28+ and a trending day help a little; VIX < 15 and an ES-NQ SMT that agrees with the trade hurt. Nightly workflow publishes the JSON to the datacity branch; the 3D page is tools/web_public/datacity/.
runs: datacity_holdout_portfolio
---

## In one minute

- **What it is:** a research engine (`tools/datacity/`) plus a 3D night city (`tools/web_public/datacity/`). Every
  building is one combination of a **time**, a **confluence** and up to two **"while" states**, scored as a small
  backtest. Paper only: it never touches `live_model*.json` or any order. It only proposes.
- **How big:** 375,079 events on 1,304 CME days (2021-10-18 -> 2026-11-02), **67,320 combinations tried**, 19,942 with
  30+ trades (46,256 too thin, 1,122 exact duplicates of another combination, counted once).
- **Honest result:** most of the city is noise. 25 combinations pass the false-discovery guard, about 2.5 of them by
  chance, and a placebo with no edge at all still passes 2. Picked on 2021-24 alone, the winners mostly stop working in
  2025-26. Nothing here beats LIT, and nothing is proposed for the live bot.
- **Why keep it:** it re-scores every night on the bars the PC pushes, so a combination that starts to hold (or a
  confluence that stops helping) shows up on its own, with $ and eval numbers next to it.

## What it tests

| Part | What |
|---|---|
| Time | every 15-minute slot 18:00-16:00 ET (both directions), the six sessions (Asia 18-02, London 02-07, NY pre 07-09:30, NY AM 09:30-11:30, lunch 11:30-13:30, PM 13:30-16:00) x weekday, month, DST (summer / winter / the US-EU gap weeks), news day, VIX |
| Confluences (triggers) | sweep (wick through, close back inside within 3 bars) and break (close beyond) of the Asia high / low, London high / low, prior-day, prior-week and 09:30-09:45 opening-range highs / lows; FVG; IFVG; CISD; displacement (body >= 1.5 ATR); VWAP reclaim / loss; gap fill; the high-impact news bar (`data/news/events.csv`); a plain entry at the slot |
| While-states | VWAP side, EMA200 side (both relative to the trade), ATR regime (daily ATR tercile vs the last 250 days), VIX and VXN (CBOE close of the day before), London swept the Asia high / low / both / none, trending vs balanced so far today, previous day trend vs range, gap up / down / flat, ES-NQ SMT (with / against / none; ES bars from 2025-04 only), weekday, DST, news day. One state, or two from different families |

**The mini-backtest (the same for every event):** decide at a 5m bar's close, enter at the next bar's open; stop 1 tick
beyond the structure (for a sweep the sweep extreme, otherwise the extreme of the last 6 bars), at least 4 and at most
120 points; target 2R; otherwise out at the close 2 hours later or at the end of the CME day. A bar that touches both
the stop and the target counts as the stop. Money per MNQ micro ($2 a point) after **$1.90 commission + 2 ticks
slippage = $2.90** a round trip. One trade a day per combination (the first matching event). Also recorded: hit rates of
1R / 2R / 3R before the stop and the move 15 / 30 / 60 minutes after the entry.

**Sized strategies:** each discovery is also replayed like the bot sizes (size follows the stop: $500 at risk, 1-40
micros) through `tools/runlib.score`, so it gets trades a week, % weeks with 2+, PF, net $, $ a month, max DD and the
MFFU Builder 50K eval speed (`p10/f10`, `dec10`, `p15/f15`, `slow_pass`, `pass_med`).

## The guards (why most of it is noise)

1. **Benjamini-Hochberg FDR** at q = 0.10 over every distinct combination with 30+ trades (two-sided test of mean R
   after costs = 0, every trade at the same $ risk). 25 pass with a positive edge; expected false: ~2.5. 2,485 pass
   with a NEGATIVE edge (costs and wide structure stops make the average trade lose).
2. **Sign-flip placebo:** the same grid with every trade's result multiplied by a random +1 / -1 (no edge by
   construction). It passes 2 (it passed 0 on the data to 2026-10-16). So "25" means "about 22 real, give or take".
3. **Holdout:** BH run on 2021-24 alone picks 22 combinations; in 2025-26, which they never saw, only 6 (27%) stay
   positive, mean -$14.49 a trade a micro (-0.16R).
4. **Stability (the colours):** gold = positive in 2026, in 2021-25 AND in every year with 8+ trades, AND passes FDR;
   green = positive in both periods; amber = one period only; grey = noise or a loser. 2021-25 must cover 3+ years with
   5+ trades (an SMT combination, with ES from 2025-04 only, can never be green or gold).

## Top 5 findings (data to 2026-11-02, $ per trade per micro after costs)

| # | Finding | 2026: $/trade, win, n, /wk | 2021-25: $/trade, win, n, /wk | Class |
|---|---|---|---|---|
| 1 | NY PM short after a VWAP loss while balanced so far today and the day gapped up (32% to 2R) | +$29, 52%, 23, 0.53 | +$16, 48%, 87, 0.40 | gold, FDR |
| 2 | Long after a bullish displacement while London swept the Asia high and the day is trending (29% to 2R) | +$7, 44%, 43, 0.99 | +$21, 50%, 153, 0.70 | gold, FDR (decaying in 2026) |
| 3 | Asia short after a VWAP loss while ATR is wild and the day gapped down (42% to 2R) | +$35, 62%, 21, 0.48 | +$8, 49%, 59, 0.27 | green, FDR (2025 lost) |
| 4 | NY PM short after a bearish FVG while ATR is wild and London swept no Asia side (31% to 2R) | +$101, 64%, 22, 0.51 | +$15, 54%, 43, 0.20 | green, FDR (2025 lost) |
| 5 | NY PM short after a VWAP loss on a gap-up day (33% to 2R) | +$34, 52%, 25, 0.58 | +$16, 50%, 91, 0.41 | green, FDR (2021: 4 trades lost) |

Sized like the bot ($500 risk, 1-40 micros): #1 makes 2026 PF 1.78 +$3,291 ($318/mo), 2021-25 PF 1.74 +$12,452
($241/mo); #2 2026 PF 1.06 +$591 ($57/mo), 2021-25 PF 1.72 +$22,977 ($444/mo); #3 2026 PF 2.51 +$5,163 ($500/mo),
2021-25 PF 1.85 +$10,690 ($207/mo); #4 2026 PF 3.38 +$7,276 ($704/mo), 2021-25 PF 1.61 +$4,970 ($96/mo). **None can
pass an MFFU 50K eval in 2 weeks on its own** (p10 0-0.5%, f10 0%, median 26-50 sessions to pass): at under one trade a
week they are building blocks, not strategies, and all of them are below the owner's 2-4 trades a week.

**The holdout portfolio** (run `datacity_holdout_portfolio`): the 10 best distinct 2021-24 picks, one trade a day,
2.0-2.5 trades a week. Per year PF 1.66 / 2.17 / 1.84 / 1.90 (2021-24, where they were picked) -> **1.11 in 2025 and
1.06 in 2026** (+$1,235, $120/mo, DD -$6,022, 2-week eval pass/fail 2.3/3.7%, median 19 sessions). 2025-26 out of
sample: 198 trades, +0.05R a trade, +$4,407. That is the decay the guard warns about.

## What the city learned about confluences

Median change in R a trade when one state is added to the same trigger and window (over every base with 30+ trades both
ways), and the share of bases where it helps in 2026 AND in 2021-25:

| Helps | R | both | Hurts | R | both |
|---|---|---|---|---|---|
| ES-NQ SMT against the trade (2025-26 only) | +0.11 | 50% | ES-NQ SMT with the trade (2025-26 only) | -0.07 | 14% |
| VIX 25+ | +0.04 | 23% | VIX < 15 | -0.04 | 23% |
| VXN 28+ | +0.04 | 31% | VXN < 20 | -0.03 | 20% |
| trending so far today | +0.03 | 37% | after a trend day | -0.02 | 20% |
| gap down | +0.03 | 35% | flat open | -0.01 | 25% |

All small: no state adds more than about 0.1R on its own, and none helps in both periods in more than half of the bases.
High volatility helps these structure-stop trades; a quiet VIX hurts them. "SMT with the trade" (the textbook reading)
is the worst state here, on a short ES history.

## How to read the city

- **Districts:** Times (north-west), Confluences (north-east), While-states (south, the biggest), Strategies (west, violet
  towers, the sized discoveries and the holdout portfolio), Discoveries (monuments round the plaza). The cyan tower in the
  middle is LIT (Zlarior) with run `lit_live`: 2026 PF 4.19 +$43,820, H2 check PF 2.91 +$9,919 (~$2,670/mo), 2021-25
  PF 1.01 +$1,265.
- **A building:** height = $ per trade per micro; colour = stability (gold / green / amber / grey); lit windows = sample
  size; a pulsing roof = rising lately (the last 26 weeks above the whole sample, or R up since the previous run).
  Tap it for the card: the plain-language finding, $, win rate, hit 1R / 2R / 3R, moves after 30 / 60 minutes, trades
  a week, 2026 vs 2021-25, every year and a quarter-by-quarter sparkline.
- **Buttons:** Top (the top 10), Today (new / rising discoveries and the top setups that fired on the last day), Find
  (search + class filter), Fly (a fly-through), Sky (day / night), HQ / LQ (quality; it drops to LQ by itself when a
  phone cannot hold 40 fps), Read (this page in short, with the confluence lift). Pinch and drag to orbit.
- The city shows every gold, the best greens and ambers and the biggest greys, so the noise is visible too.

## Constantly learning

- `python -m tools.datacity --heartbeat` appends the PC's NinjaTrader MNQ 5m bars (heartbeat `bars_5m.csv.gz` and the
  cloud's `pc_bars_5m.csv`; never Yahoo) to `research/datacity/bars_extra.csv.gz`, then rebuilds only the new days of the
  event table (cached; a tail of 420 days makes every rolling feature exact: incremental == full is a test) and
  re-scores everything (~1 minute).
- `history.json` keeps one row per day of data (the top 100 with R, $ and n), so a combination's trend is visible run
  to run; `discoveries.json` flags new and rising ones and lists the top setups that fired on the last day.
- `.github/workflows/datacity.yml` runs it Mon-Fri at 22:37 ET (03:37 UTC) and force-pushes one commit with the JSON
  (+ the bar store) to the `datacity` branch (~700 KB). The page's own copy (`tools/web_public/datacity/city.json`) is
  what this commit ships.

## Caveats

- 5m bars only: a bar through both the stop and the target counts as a loss (conservative); 1m data exists for 2026 only.
- One trade a day per combination keeps trades independent, but most combinations then trade under once a week; the
  owner's 2-4 a week is met only by mixing several (the holdout portfolio), and that mix decays out of sample.
- The p-values use a normal approximation (30+ trades) and BH assumes positive dependence; nested combinations are
  highly correlated, so the effective number of tests is smaller than 19,942 (BH is then conservative, not loose).
- The ES-NQ SMT state has 2025-04 -> 2026 only; it can never count as holding in 2021-25.
- Costs: $1.90 commission + 2 ticks a round trip a micro; real fills on fast news bars can be worse.
- Paper only. The data city never changes the bot. A finding becomes a candidate only after the usual test: better in
  2026 and 2021-25, 2-4 trades a week, MFFU eval speed, a write-up and the owner's yes.
