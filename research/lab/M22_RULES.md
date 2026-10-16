# ICT 2022 Mentorship model: rules as implemented (track M22)

Code: `tools/lab_models/ict2022.py` (NAME `ict2022`). Runner: `tools/lab_m22_run.py`. Results: `research/lab/M22_REPORT.md`.

**What the model is.** It is the intraday model ICT (Michael Huddleston) taught in his free 2022 YouTube mentorship. The sequence has four steps:
1. The market raids a liquidity pool.
2. It displaces the other way with a market structure shift (MSS).
3. You enter on the retrace into the fair value gap (FVG) the displacement left.
4. You target the liquidity on the opposite side.

Every source agrees on this skeleton. The details below are where they differ, and the choice made for each is written down.

## Rules (straight, no discretion)

1. **Market and charts.** NQ1! / ES1! futures, traded as MNQ ($2/pt) or MES ($5/pt). The 15-minute chart is used to mark liquidity. The 5-minute chart is used for the raid, MSS, FVG and entry.
2. **Daily bias (draw on liquidity).** Compare yesterday's daily candle (18:00–17:00 ET) with the candle before it:
   - closed above that candle's high: longs only
   - closed below its low: shorts only
   - traded above its high but closed back inside: shorts only
   - traded below its low but closed back inside: longs only
   - anything else (an inside day, or both sides run with a close inside): no bias, no trade
3. **Killzones.** 08:30–11:00 ET and 13:30–15:55 ET. The raid, the MSS and the fill must all happen inside the same killzone.
4. **Liquidity pools.** Untaken pools are:
   - prior-day high/low (PDH/PDL)
   - Asia high/low (20:00–00:00)
   - London high/low (02:00–05:00)
   - every 15-minute short-term swing high/low printed since 18:00. A short-term swing is a 3-candle fractal; it counts once the next 15m candle has closed.

   A pool that is traded through outside a killzone is spent.
5. **Raid.** A 5m candle inside a killzone trades at least 1 tick through a pool:
   - through a sell-side pool (below a low): look for longs
   - through a buy-side pool (above a high): look for shorts

   The raid extreme is the lowest low (or highest high) printed until the MSS.
6. **MSS with displacement.**
   - The MSS: a 5m candle **closes** beyond the last 5m short-term swing that formed before the raid extreme. That swing is the one that started the move into the raid.
   - The displacement: the leg from the raid extreme through the MSS candle (plus one candle to complete the gap) must leave a fair value gap. No FVG means no trade.
   - If price trades back through the raid extreme after the MSS, the setup is void.
7. **Entry.** A limit order at the near edge of the **first** FVG of that leg:
   - long: candle-3 low, the top of the bullish gap
   - short: candle-3 high, the bottom of the bearish gap

   The order fills only if a later candle trades through it by 1 tick. If price is already back inside the gap when the MSS candle closes, skip the setup.
8. **Stop.** 1 tick beyond the raid extreme. Size is floor($350 / (stop distance × $/pt)), capped at 40 micros. Skip the setup if the size is 0.
9. **Target.** The nearest opposite pool that already existed when the raid happened and lies beyond the entry:
   - long: buy-side above
   - short: sell-side below

   Swings printed by the raid or the displacement itself do not count as targets. If no pool exists, use the −2 standard-deviation projection of the manipulation leg: the swing level from rule 6 plus 2 × its distance to the raid extreme, in the trade's direction. One target only: no partials, no breakeven, no trailing.
10. **Cancel** the unfilled order in any of these cases:
    - the killzone ends
    - price reaches the target before the fill ("let it pass, don't chase")
    - a newer setup arms
11. **Day rules.**
    - At most 2 trades a day.
    - Done for the day after a winner, or after 2 losers.
    - Daily stop of −$700.
    - Flat at 15:55 ET.
    - One position at a time.

**Variants, declared before the first scoring run.** These are the only ones run.
- `canon`: the rules above.
- `nobias`: rule 2 switched off (both directions every day).
- `rr2`: rule 9 replaced by a fixed 2R target.

The AM-only numbers in the report are the AM subset of `canon`. That subset is exactly what an AM-only run would produce, because PM trades never change AM decisions.

## Risk management

| Item | What ICT / followers teach | Used here |
|---|---|---|
| Risk per trade | 1% of equity, and less after losses. One example cuts to 0.5% after a loss and rebuilds slowly (Ep. 41; "ICT Forex – Considerations in Risk Management"). Prefer several small losses to one big one. | Fixed $350 (0.7% of 50K), owner default |
| Frequency | One setup per day at most. About one good trade a week is enough for the "5 handles a week" funded-account goal. Add frequency only with experience; don't overtrade (Ends series 3/4 and 4/4). | Max 2 a day; done after a winner or 2 losers |
| Funded accounts | Equity should make new highs with shallow pullbacks. Cut size after losses. The ES template is a 4-pt hard stop and a 5.25-pt target on a 1–4m FVG (Ends series). | −$700 daily stop (MFFU soft DLL is $1k; the MLL is $2k EOD) |
| Partials | Ep. 41: take partials at "low-hanging fruit" and move the stop to breakeven at about 75% of the target; ICT calls this "a foundation, not an ironclad rule". Ends series: one target, all out. | One target, all out |

## Where the sources disagree and what was chosen

| Point | Versions found | Chosen (reason) |
|---|---|---|
| Killzones | 08:30–11:00 (Ep. 2, Ep. 41); 09:30–11:30 + 13:30–15:30 (Ends series 3/4) | Owner's 08:30–11:00 + 13:30–16:00, flat 15:55 |
| Raided liquidity | short-term highs/lows (Ep. 2); PDH/PDL, prior-week H/L, session H/L, 08:30–09:30 H/L (Ends 4/4); PDH/PDL, session extremes, equal highs/lows (LuxAlgo) | PDH/PDL, Asia, London, 15m short-term swings. Prior-week H/L and equal highs/lows are not coded. |
| MSS | close through the short-term swing (LuxAlgo); "break of a short-term low" (Ep. 2, Ep. 6) | Candle **close** beyond the last 5m short-term swing before the raid extreme |
| Displacement | "energetic" move that leaves an FVG; no numeric threshold anywhere | Any FVG in the leg. No size or ATR filter, because none is taught. |
| Which FVG | "the FVG the displacement leaves" (LuxAlgo, Ep. 6); "at or just above equilibrium of the swing" (Ends 4/4); "nearest 50% of the range" (TradingIQ script); "first FVG of the displacement" (common phrasing, owner's brief) | First FVG |
| Entry price | limit at the gap's near edge (Ends 3/4: "limit at the FVG high" for longs; Ep. 6: "just above candle 3's high" for shorts); some followers use CE (50%) | Near edge (ICT's own wording) |
| Stop | beyond the raid extreme (LuxAlgo, TradingFinder, TradingIQ "0% of range"); above the FVG candle (Ep. 22); 4-pt hard stop on ES via 1–4m FVG (Ends series) | Beyond the raid extreme (most common, owner's spec) |
| Target | opposite pool (LuxAlgo; TradingFinder: PDH or another level); 100% of the range (TradingIQ); 5.25 pts fixed (Ends series); −2…−2.5 SD scale-outs (SD-projection videos) | Nearest external opposite pool, with −2 SD fallback. `rr2` variant: 2R. |
| Bias | weekly candle expectation (Ends series); 15m–1h draw (LuxAlgo); prior-day candle close/sweep (Tradezella and the common "daily bias" rule) | Prior-day candle rule (the only one that can be coded without discretion) |

**Deviations forced by the data.**
- ICT drops to 1–4m charts to find an FVG that fits a small stop. Only 5m history exists for the full 18 months, so everything runs on 5m. Stops are therefore wider (18-month median about 61 pts on NQ and 11 pts on ES) and position sizes are small (median 2 MNQ / 6 MES; on average about $285 / $315 is actually risked instead of $350).
- Prior-week H/L and equal highs/lows are not coded as pools.

**One spec fix made during the mechanics check, before any scoring.**
- First draft: the target was the nearest untaken opposite pool of any age. That draft could pick the short-term swing printed by the displacement itself, which is internal to the setup and not the draw on liquidity.
- Fix: the target is now restricted to pools that existed at the raid.
- What I had seen at that point: the smoke-test printout (NQ and ES, 2026-09-01..10-16; 6 NQ and 8 ES trades) did show P&L. The trigger for the fix was a trade with a planned 0.32R target.
- The fix did not help that window. NQ went from 6 trades (5 stops, 1 time exit) to 7 trades (6 stops, 1 time exit).
- No other rule was changed after any output was seen.

## Sources (all secondary; ICT's videos were read through AI transcript summaries, so check exact wording against the videos)
- LuxAlgo, Model 2022 concept: https://www.luxalgo.com/library/concept/model-2022/
- LuxAlgo, 2022 Model ICT entry indicator page: https://www.luxalgo.com/library/indicator/FK960gz8-2022-model-ict-entry-strategy-one-setup-for-life/
- LuxAlgo, standard-deviation projections: https://www.luxalgo.com/library/concept/standard-deviation-projections/
- 2022 ICT Mentorship Episode 2 (summary): https://videohighlight.com/v/tmeCWULSTHc
- 2022 ICT Mentorship Episode 6 (summary): https://videohighlight.com/v/Bkt8B3kLATQ
- 2022 ICT Mentorship Episode 41 & Final (summary): https://videohighlight.com/v/2XhDi5GoNUI
- 2022 ICT Mentorship Ends Series Part 3 of 4 (summary): https://videohighlight.com/v/_MCYKZGAHmY
- 2022 ICT Mentorship Ends Series Part 4 of 4 (summary): https://videohighlight.com/v/SO3SJFNRim8
- Standard Deviation Projections, ICT concepts (summary): https://videohighlight.com/v/kTWXpAo1uE8
- ICT Forex, Considerations in Risk Management (summary): https://videohighlight.com/v/tlKC9nvLRK0
- TradingIQ "ICT Master Suite" (open-source 2022-model implementation): https://www.tradingview.com/script/ABYnIcdl-ICT-Master-Suite-Trading-IQ/
- TradingFinder "2022 Model ICT Entry Strategy" (script listing): https://it.tradingview.com/scripts/mentorship
- Tradezella, daily bias from the prior-day candle: https://www.tradezella.com/learning-items/timing-context
- Context on ICT backtests: https://gist.ly/youtube-summarizer/i-backtested-25000-ict-silver-bullet-trades and https://offbeatforex.com/is-ict-strategy-profitable/
