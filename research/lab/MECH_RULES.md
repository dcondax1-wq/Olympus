# MECH: the public "Mechanical Model" / IFVG model (PB Blake and other ICT-derived educators)

Implementation: `tools/lab_models/mech_ifvg.py` (`NAME = "mech_ifvg"`). Data: TradingView CME futures NQ1! / ES1!, 5m bars.
Written 2026-10-16. Research took about 40 minutes and used web pages only (see "Sources and how reliable they are").

## The rules (base version = the most common published version)

1. **Liquidity map.** Before the session, mark these levels:
   - the prior day's high and low (PDH/PDL; full CME session 18:00–17:00)
   - the Asia high/low (20:00–00:00 ET)
   - the London high/low (02:00–05:00 ET)
   - the untaken 1H swing highs/lows from today and yesterday (a 3-candle fractal, usable once the next 1H candle has closed)

   Equal highs/lows count too, but need no extra rule: taking an EQH means trading through the higher of two 1H swing highs.
2. **Window.** Trade the NY AM "golden hour" only: 09:30–11:00 ET. The sweep, the trigger and the entry must all happen
   inside it.
3. **Sweep.** A 5m candle trades at least 1 tick through a level that is still fresh, meaning nothing has traded through it
   since it formed. A low taken means look for a long; a high taken means look for a short. If more levels on the same side
   are taken, the setup just extends, and the sweep extreme moves with price.
4. **Manipulation leg.** This is the swing high → swing low leg that ran into the level. Its origin is the highest high
   (lowest low for shorts) of the 12 five-minute candles (1 hour) before the sweep extreme. The leg ends at the extreme.
5. **Trigger (IFVG).** Take the fair value gaps formed inside that leg (bearish FVGs for a long, bullish FVGs for a short)
   that have not been closed through yet. The trigger is the **first 5m candle that closes its body beyond the far edge of
   one of those gaps**. That inverts the gap, and it must happen after the sweep. Any real 3-candle gap counts; no minimum
   size is taught.
6. **Entry.** Enter at the close of the inversion candle with a market order.
7. **Stop.** 1 tick beyond the sweep extreme, i.e. the swing low/high of the manipulation (PB's stop "for beginners").
8. **Target.** The nearest untaken opposing liquidity that is **at least 1R** away:
   - candidates are any level from rule 1, plus the leg's own swing high/low from rule 4
   - closer levels are ignored
   - the target is capped at **3R** (PB: roughly 1:1 to 1:3)
   - if no level qualifies, there is no trade
9. **Break-even.** Once price trades +1R, move the stop to entry. The move takes effect from the next candle.
10. **Size and limits.**
    - Fixed $350 risk: micros = floor($350 / (stop pts × $/pt)). A stop too wide for 1 micro means no trade.
    - At most 2 trades a day, one position at a time.
    - **Done for the day after a winner**, or after 2 losers, or at −$700 on the day.
    - Flat at 15:55 ET.

Mechanics: decisions use closed 5m candles only. The trade is managed from the candle after entry. If the stop and target
are both hit inside the same candle, the stop counts first. Costs are set by `strategy_lab.make_trade`: 1 tick slippage on
market and stop fills, $1.40 per micro round trip, MNQ $2/pt and MES $5/pt.

## Documented variants (exactly three configurations were run)

| name | change vs base | source |
|---|---|---|
| `base` | rules 1–10 | PB 2026 (window, 1–3R to the nearest high/low, limits) + older PB Mech Model (external liquidity) |
| `smt` | + **SMT required**: the partner index (ES when trading NQ, NQ when trading ES) must *not* have taken its own matching level (the same session, prior day, or 1H candle) by the trigger close | older PB Mech Model uses SMT as a veto; most ICT educators use it as confirmation |
| `rr2` | target = **fixed 2R** instead of the nearest liquidity. Break-even at +1R is kept | the middle of PB 2026's "~1:1 to 1:3" range, and the brief's own example (DOL vs 2R) |

No other configuration was run. The fixed-1R target of the older Mech Model was **not** run, to stay inside the
three-variant cap. The numbers in rules 1–10 (12-bar leg, 1 tick, 1R/3R, 1R BE) were set before the first scored run and
never changed. Only one scored run was made per variant and symbol: `tools/lab_mech_run.py`, on the refreshed TradingView
data.

## Risk management as taught

- **PB 2026:**
  - max 1–2 trades a day
  - done after a win; after one loss "probably also done"; done after two losses
  - same risk on every trade (he gives no % figure)
- **Third-party PB script:** max 2 signals per session.
- **Not taught anywhere we found:** a daily dollar stop, or prop-firm-specific rules.
  - We used the house default of −$700, which with $350 risk is the same as 2 losers.
  - Flat at 15:55 is an MFFU requirement, not a PB rule.

## Where the sources disagree, and what we picked

| topic | versions | picked |
|---|---|---|
| levels | older Mech Model: external liquidity (PDH/PDL, Asia/London, session, equal and swing H/L). 2026 model: HTF "key levels" (3m–4H FVGs, CISD, rejection blocks) | external liquidity: it is the "mechanical" one, the most often listed, and the one the brief asked for |
| HTF bias | older: not needed ("works at all-time highs", longs and shorts). 2026: Daily/4H/1H FVG-respect bias is step 1 | **no bias filter** (it is discretionary, and the older model says it is not needed) |
| window | 09:30–11:00 only (2026, script default) vs also 13:00–15:00 (older) | 09:30–11:00 |
| IFVG timeframe | PB: the highest timeframe from 1–5m that has a gap in the leg; don't take a lower-TF inversion first | 5m, which is the highest of 1–5m and the only one in our history. Legs with gaps only on 1–4m are not traded |
| which gap | PB: not specified. Cutler: prefers a single FVG. PJ Trades: "first presented IFVG" filter | the first gap to be inverted (the one nearest the sweep) |
| entry | body close (PB, PJ) vs limit at the IFVG or its midpoint (others) | close |
| stop | swing extreme (PB for beginners, PJ) vs the IFVG edge (Cutler, ICT tutorial) | swing extreme + 1 tick |
| target | 1R (older PB, scripts) vs 1–3R at the nearest high/low (PB 2026) vs 2nd/3rd swing (PJ) | nearest liquidity ≥1R capped at 3R (base); fixed 1R as a variant |
| break-even | at 1:1 (older PB) vs "after certain levels" (2026) vs midpoint (PJ) | at +1R |
| SMT | veto when against (older PB) vs not mentioned (2026) vs confirmation (common ICT usage) | off in base; "required" as a variant |
| CISD | a key-level type and limit-entry spot in the 2026 version; paired with the 1m inversion in Mech 2.0 | not used as a trigger (IFVG only) |

## Known gaps between the teaching and this 5m build

- PB confirms on the 1–5m charts. With 5m-only history we trade only the 5m inversions. Real PB entries are often on 1–3m:
  stops are tighter and there are more setups. Our NQ stops are much wider: the 2026 median is about 95 NQ points.
- The 2026 version's HTF key levels and HTF bias are discretionary and not implemented.
- "Closest obvious high/low on the execution timeframe" is approximated by the leg's swing high/low plus the liquidity map.

## Sources and how reliable they are

PB Blake has no written rulebook. YouTube transcripts and Whop/TikTok/Reddit pages were not readable from here. The PB rules
above come from AI-generated summaries of his videos and from a third-party TradingView script built on his model.
Treat them as close but not verbatim.

PB Blake / PB Trading:
- [S1] PB Blake (YouTube @PBBlakeYT), *My NEW UPDATED Trading Strategy for 2026 (70% Winrate)*:
  https://www.youtube.com/watch?v=9O6JU5_xTd8. Summary read: https://youtubesummary.com/summary/9O6JU5_xTd8
- [S2] *PB Trading MECH MODEL 2.0* (mentorship lesson, re-upload): https://www.youtube.com/watch?v=Pj_-D23gr_8. Summary
  read: https://videohighlight.com/v/Pj_-D23gr_8
- [S3] *PB Trading Premium Whop – Blake's Mechanical Model* (AI Q&A summary):
  https://www.cofyt.app/search/pb-trading-premium-whop-blakes-mechanical-model-EeUjueN-Fr8el1RbEKhsnU
- [S4] EZ$ PB Blake v1.0 (TradingView, third-party implementation of PB's 2026 model):
  https://www.tradingview.com/script/h179SZH8-EZ-PB-Blake-v1-0/
- [S5] Mech Model – Strategy v3.1 (TradingView, "based off PB Blake's Mech Model", closed source):
  https://www.tradingview.com/script/dEvnTCc5-Mech-Model-Strategy-v3-1/
- [S6] FuturesHive profile: https://www.futureshive.com/blog/pb-blake-pb-trading-nq-futures-specialist

Other educators (these come from the research sub-agent's reading and were not re-checked one by one):
- [S7] Josh Cutler IFVG model (TradeZella): https://www.tradezella.com/strategies/ifvg-trading-model
- [S8] PJ Trades IFVG model (Flux Charts, TradingView): https://www.tradingview.com/script/PYg9cFMp-Inversion-Fair-Value-Gap-Model-PJ-Trades/
- [S9] ICT IFVG tutorial: https://innercircletrader.net/tutorials/ict-inversion-fair-value-gap/
- [S10] Ifvgs with Targets (TradingView): https://www.tradingview.com/script/MqMa4li7-Ifvgs-with-Targets/
- [S11] IFVG MODEL [RTP] (TradingView): https://www.tradingview.com/script/hcZouPJI-IFVG-MODEL-RTP/
- [S12] FVG/IFVG indicator, "Blastoise's model" (TradingView): https://de.tradingview.com/script/A3jJo1CH-FVG-IFVG-Indicator-Blastoise-s-85-Win-Rate-Model

The published win rates (70%, 70–80%, 80%+) are marketing claims and have not been verified.
