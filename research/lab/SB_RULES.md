# ICT Silver Bullet: rules as publicly taught (NQ / ES futures)

Written 2026-10-16, **before** any scoring. These rules and the three variants below were fixed first, and every
variant that was run is reported in `SB_REPORT.md`. Code: `tools/lab_models/silver_bullet.py` (defaults = the base
rules). Runner: `tools/lab_sb_run.py`.

## The rules (base version)

1. **Windows (New York local time).** The setup must come from the **10:00–11:00** window (AM) or the **14:00–15:00**
   window (PM). ICT also teaches 03:00–04:00 (London), but the bot skips it.
2. **Liquidity pools.** Before and during the session, mark these:
   - prior week high/low
   - prior day high/low
   - Asia high/low (20:00–00:00)
   - London high/low (02:00–05:00)
   - the 09:00–10:00 hour high/low
   - for the PM window, the NY AM session high/low (09:30–12:00)
   - every short-term high/low on the 5m chart, meaning a candle whose high (low) is beyond both neighbours.

   A pool is *taken* once price trades 1 tick beyond it.
3. **Raid first.** For a long, price must take a sell-side pool. That raid must happen at most 60 minutes before the
   first candle of the setup FVG, and the low of the move must be at or before FVG candle 1. Shorts mirror this.
4. **Displacement FVG inside the window.** After the raid, price displaces the other way and leaves a 3-candle fair value
   gap:
   - Bullish: candle 1's high is below candle 3's low. Bearish: candle 1's low is above candle 3's high.
   - The displacement candle (candle 2) must open at or after the window start, and candle 3 must close inside the
     window.
   - A gap formed before the window does not count.
5. **Draw on liquidity (direction).** Target the **nearest untaken pool** on the far side that is at least
   **10 handles (40 ticks)** from the entry. This is ICT's "minimum trade framework" for index futures. Take the trade
   only if that draw pays **at least 2R**. If no such pool exists, there is no trade.
6. **One attempt per window.** The **first** FVG that meets rules 3–5 is the setup. If its order doesn't fill inside the
   window, there's no trade in that window.
7. **Entry.** Place a limit order at the FVG's **near edge**: the top of a bullish gap, the bottom of a bearish one. It
   fills only if a later 5m bar trades 1 tick through it, still inside the window. Cancel the order if price reaches the
   target first, or at the end of the window.
8. **Stop.** 1 tick beyond **FVG candle 1**: below its low for longs, above its high for shorts.
9. **Target.** The draw-on-liquidity pool price from rule 5. Once filled, the trade may run past the window. Exit at the
   target, the stop, or **flat at 15:55 ET**.
10. **Risk (bot defaults, consistent with the teaching):**
    - Risk a fixed $350 per trade: MNQ $2/pt, MES $5/pt, max 40 micros. Skip a setup if 1 micro would risk more than $350.
    - At most one trade per window, so at most 2 a day.
    - Stop for the day after a winner ("no second trade after a morning win"), after 2 losers, or at −$700 on the day.

## Pre-declared variants (exactly three; each changes one documented choice)

| name | change | why it is a documented alternative |
|---|---|---|
| `base` | rules 1–10 (AM + PM) | the most common version, chosen element by element |
| `am` | AM window only (10:00–11:00) | "one trade, then done" / never use the PM window to recover a loss (ChartingLens, ictkillzone) |
| `ce` | entry at the FVG's 50% (consequent encroachment) instead of the near edge | completetradersedge, ictkillzone and ChartingLens all use the 50% entry |
| `rr2` | fixed 2R target instead of the pool; setups are selected exactly as in base | community 2R target (FXOpen, ChartingLens) |

There was no other parameter search. The 60-minute raid lookback, the 1-tick fill and stop buffers, and the 5m chart
are implementation choices fixed before scoring.

## Where the sources disagree, and what was picked

| question | versions found | picked |
|---|---|---|
| windows | 03–04 / 10–11 / 14–15 NY everywhere. FXOpen alone moves London to 02–03 in summer. | 10–11 and 14–15 (London skipped for the bot) |
| must the FVG form in the window? | yes (ICT lecture summary, LuxAlgo, ChartingLens, ictkillzone) | yes |
| can the trade run past the window? | yes (ICT summary, HowToTrade); strict camp says the fill must happen inside the hour | fill inside the window; the trade may run after it |
| direction | ICT: draw on liquidity first (PDH/PDL, session H/L, PWH/PWL, gaps). Many add a higher-timeframe bias with no fixed rule. | draw on liquidity (rule 5); no HTF bias filter, since sources give no mechanical one |
| raid required? | ICT summaries don't require one; most coded versions do (Flux Charts; JadeCap's raid of the Asia/London/9 AM high-low); LuxAlgo calls a raid ideal | required (rule 3) |
| which FVG? | the first FVG in the bias direction (HowToTrade); the first after the structure shift (ictkillzone) | the first qualifying FVG, one attempt |
| timeframe | ICT 15m or lower; 1–3m most typical; JadeCap 5m | 5m (only ~4 weeks of 1m data exist; checked separately on 1m) |
| entry | near edge (FXOpen, HowToTrade, 2022 Entry Model script) vs 50% CE (completetradersedge, ictkillzone, ChartingLens) | near edge; CE as a variant |
| stop | candle 1 (FXOpen, HowToTrade, TradingFinder, innercircletrader.net) vs the raid/swing extreme (LuxAlgo, ChartingLens, ictkillzone, 2022 script) vs the far edge of the FVG (Backtrex) | candle 1, the tally called by the research. The swing stop is implemented (`stop: "swing"`) but **not run**, because of the 3-variant cap |
| target | ICT: the draw on liquidity, needing ≥10 handles of room (his examples are ES; he aims to bank about 5 handles). Community: at least 2R, some 3R. Partials at 5 handles + breakeven (HowToTrade), or 50/25/25 (ictkillzone) | the draw, needing ≥10 handles and ≥2R; fixed 2R as a variant; no partials |
| NQ minimum | no NQ number from ICT. Backtrex: 10–15 NQ handles | ICT's 10 handles / 40 ticks applied to both. On NQ the 2R floor almost always binds first |
| trades per window/day | one per window (LuxAlgo, innercircletrader.net); one and done (ChartingLens); no second trade after an AM win (ictkillzone) | one per window, stop after a win (base); AM only = one and done |

## Risk management its teachers recommend (prop / small accounts)

**ICT's risk lecture:**
- His examples start at 2% risk; 5% is too much.
- After a loss, halve the risk, stepping down to 0.5%.
- Keep drawdown under about 5%, and raise risk again only after recovering about half of it.
- Never add to a loser.

He gives no rule specific to the Silver Bullet or to prop accounts.

**Teachers:**
- JadeCap's guide: start at 0.1–0.25% risk with 1 contract.
- Size every trade to the stop distance (ChartingLens).
- One and done; no revenge trade in the PM window after an AM loss.

**For the bot:**
- The lab protocol fixes $350 risk per trade, which is 0.7% of a 50K account.
- The −$700 daily stop sits well inside MFFU's $1,000 soft DLL.
- ICT's half-risk-after-a-loss rule is a possible live overlay; it is **not** tested here.

## Sources

The research pass could not read ICT's own transcript, because YouTube and transcript sites blocked access. Claims
marked "ICT" come second-hand, from summaries of his 2023 lecture. Treat them as reported, not verified.

- ICT, *2023 ICT Mentorship – ICT Silver Bullet Time Based Trading Model*: https://www.youtube.com/watch?v=tRq1hyGGtl4
  - summary: https://videohighlight.com/v/tRq1hyGGtl4
  - summary: https://gist.ly/youtube-summarizer/ict-silver-bullet-trade-setup-time-based-algorithmic-trading-model
  - study notes: https://manage2damage.notion.site/Silver-Bullet-Lecture-a72bbc8dda784234b371a699f5d67384
- ICT risk-management lecture (summary): https://videohighlight.com/v/tlKC9nvLRK0
- FXOpen: https://fxopen.com/blog/en/what-is-the-ict-silver-bullet-strategy-and-how-does-it-work/
- LuxAlgo:
  - https://www.luxalgo.com/library/concept/silver-bullet/
  - TradingView script: https://www.tradingview.com/script/fq4wSUev/
- Flux Charts (TradingView): https://www.tradingview.com/script/1kwkYj40-ICT-Silver-Bullet-Flux-Charts/
- JadeCap:
  - TradingView script: https://www.tradingview.com/script/K6B5kxjJ-ICT-Silver-Bullet-JadeCap/
  - guide: https://blog.pickmytrade.trade/jadecap-ict-silver-bullet-strategy-complete-guide-for-tradingview-traders.md
- ICT Silver Bullet 2022 Entry Model (TradingView): https://www.tradingview.com/script/edyKC9Ey-ICT-Silver-Bullet-2022-Entry-Model/
- ChartingLens: https://chartinglens.com/blog/ict-silver-bullet-strategy
- ictkillzone: https://www.ictkillzone.com/ict-silver-bullet
- HowToTrade: https://howtotrade.com/trading-strategies/ict-silver-bullet/
- completetradersedge: https://completetradersedge.com/ict-silver-bullet-strategy/
- TradingFinder: https://tradingfinder.com/education/forex/ict-silver-bullet/
- innercircletrader.net: https://innercircletrader.net/tutorials/ict-silver-bullet-strategy/
- Backtrex: https://backtrex.com/en/blog/ict-silver-bullet-strategy-trading-guide
- Published tests:
  - 25,000-variant NQ/ES study: https://www.youtube.com/watch?v=KML09tRtHM8
    - summary: https://gist.ly/youtube-summarizer/i-backtested-25000-ict-silver-bullet-trades
  - TTrades replay: https://videohighlight.com/v/o0v4KQxZbpU
